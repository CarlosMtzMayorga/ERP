import uuid
from decimal import Decimal
from datetime import datetime, timezone, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select, and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.cxc.models import ReceivableDocument, PaymentReceipt, PaymentReceiptDocRel
from app.modules.master_data.models import Customer
from app.modules.sales.models import SalesDocument
from app.modules.tenants.models import Tenant, Branch, CSDCertificate
from app.modules.tenants.folios_service import consume_next_folio
from app.modules.fiscal_mexico.cfdi_builder import sign_cadena_original, stamp_with_mock_pac
from app.modules.fiscal_mexico.tax_engine import quantize_2


async def check_customer_credit_status(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    attempted_amount: Decimal
) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Hook de Validación Crediticia en Tiempo Real:
    1. Verifica si el cliente tiene facturas vencidas (fuera de sus días de crédito).
    2. Verifica si el saldo total acumulado + el monto intentado supera su límite de crédito.
    Si alguna condición falla, la transacción debe ser rechazada.
    """
    cust_res = await db.execute(
        select(Customer).where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
    )
    customer = cust_res.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado.")

    # Si no tiene límite de crédito y días de crédito = 0, no permite ventas a crédito
    # (A menos que sea venta de contado / 0 días con límite 0)
    today = date.today()

    # 1. Consultar cartera pendiente del cliente
    rec_res = await db.execute(
        select(ReceivableDocument)
        .where(
            ReceivableDocument.tenant_id == tenant_id,
            ReceivableDocument.customer_id == customer_id,
            ReceivableDocument.status.in_(["PENDIENTE", "PARCIAL"])
        )
    )
    docs = rec_res.scalars().all()

    total_debt = sum(d.current_balance for d in docs)
    overdue_docs = []

    for d in docs:
        if d.due_date < today:
            days_overdue = (today - d.due_date).days
            overdue_docs.append({
                "folio": d.formatted_folio,
                "due_date": str(d.due_date),
                "days_overdue": days_overdue,
                "balance": float(d.current_balance)
            })

    # Regla 1: Facturas vencidas bloquean inmediatamente nuevas operaciones
    if overdue_docs:
        return (
            False,
            f"El cliente '{customer.legal_name}' cuenta con {len(overdue_docs)} documento(s) vencido(s) fuera de su plazo de crédito ({customer.credit_days} días).",
            overdue_docs
        )

    # Regla 2: Exceder límite de crédito asignado
    if customer.credit_limit > Decimal("0.00"):
        new_projected_debt = total_debt + attempted_amount
        if new_projected_debt > customer.credit_limit:
            return (
                False,
                f"Límite de crédito excedido para '{customer.legal_name}'. Límite: ${customer.credit_limit:.2f}, Saldo actual: ${total_debt:.2f}, Intento: ${attempted_amount:.2f}.",
                []
            )

    return True, "Crédito autorizado.", []


async def create_receivable_from_sales_document(
    db: AsyncSession,
    sales_doc: SalesDocument,
    customer: Customer,
    credit_days: Optional[int] = None
) -> ReceivableDocument:
    """
    Crea la cuenta por cobrar (cargo) a partir de una factura o remisión a crédito / PPD.
    """
    days = credit_days if credit_days is not None else customer.credit_days
    issue_dt = sales_doc.created_at or datetime.now(timezone.utc)
    due_d = issue_dt.date() + timedelta(days=days)

    receivable = ReceivableDocument(
        tenant_id=sales_doc.tenant_id,
        customer_id=customer.id,
        branch_id=sales_doc.branch_id,
        sales_document_id=sales_doc.id,
        document_type=sales_doc.document_type,
        serie=sales_doc.serie,
        folio=sales_doc.folio,
        formatted_folio=sales_doc.formatted_folio,
        cfdi_uuid=sales_doc.cfdi_uuid,
        issue_date=issue_dt,
        due_date=due_d,
        credit_days=days,
        original_total=sales_doc.total,
        original_subtotal=sales_doc.subtotal,
        original_vat=sales_doc.tax_iva_total,
        original_retention_vat=sales_doc.retention_iva_total,
        original_retention_isr=sales_doc.retention_isr_total,
        current_balance=sales_doc.total,
        currency_code="MXN",
        status="PENDIENTE"
    )
    db.add(receivable)
    await db.flush()
    return receivable


def calculate_proportional_taxes_rep(
    original_subtotal: Decimal,
    original_vat: Decimal,
    original_ret_vat: Decimal,
    original_ret_isr: Decimal,
    original_total: Decimal,
    amount_paid: Decimal
) -> Dict[str, Decimal]:
    """
    Motor Fiscal SAT REP 2.0 (Complemento de Recepción de Pagos CFDI 4.0):
    Calcula matemáticamente los impuestos proporcionales de un abono parcial respecto al total de la factura original.
    Garantiza que la suma cuadre exactamente al centavo con el importe pagado:
    BaseP + IVAP - RetencionesP = ImpPagado
    """
    if original_total <= Decimal("0.0000"):
        raise ValueError("El total original de la factura debe ser mayor a cero.")

    factor = amount_paid / original_total

    prop_subtotal = quantize_2(original_subtotal * factor)
    prop_vat = quantize_2(original_vat * factor)
    prop_ret_vat = quantize_2(original_ret_vat * factor)
    prop_ret_isr = quantize_2(original_ret_isr * factor)

    # Ajuste de centavos (Penny Balancing normativo del SAT)
    net_calc = prop_subtotal + prop_vat - prop_ret_vat - prop_ret_isr
    diff = quantize_2(amount_paid) - net_calc

    # Si hay diferencia de centavos por redondeos intermedios, se compensa en la BaseP
    if diff != Decimal("0.00"):
        prop_subtotal += diff

    return {
        "factor": factor,
        "proportional_base": prop_subtotal,
        "proportional_vat": prop_vat,
        "vat_rate": Decimal("0.1600") if original_vat > 0 else Decimal("0.0000"),
        "proportional_retention_vat": prop_ret_vat,
        "proportional_retention_isr": prop_ret_isr,
        "amount_paid": quantize_2(amount_paid)
    }


async def get_customer_aging_analysis(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    customer_id: Optional[uuid.UUID] = None
) -> Dict[str, Any]:
    """
    Antigüedad de Saldos Contable:
    Segmenta la cartera en los rangos normativos:
    - Al Corriente (no vencido)
    - 1 a 30 días
    - 31 a 60 días
    - 61 a 90 días
    - Más de 90 días
    """
    query = (
        select(ReceivableDocument)
        .options(selectinload(ReceivableDocument.customer))
        .where(
            ReceivableDocument.tenant_id == tenant_id,
            ReceivableDocument.status.in_(["PENDIENTE", "PARCIAL"])
        )
        .order_by(ReceivableDocument.due_date.asc())
    )
    if customer_id:
        query = query.where(ReceivableDocument.customer_id == customer_id)

    res = await db.execute(query)
    docs = res.scalars().all()

    today = date.today()

    bucket_current = Decimal("0.00")
    bucket_1_30 = Decimal("0.00")
    bucket_31_60 = Decimal("0.00")
    bucket_61_90 = Decimal("0.00")
    bucket_over_90 = Decimal("0.00")
    total_receivable = Decimal("0.00")

    detailed_docs = []

    for d in docs:
        bal = d.current_balance
        total_receivable += bal

        days_overdue = (today - d.due_date).days if today > d.due_date else 0

        bucket_name = "AL_CORRIENTE"
        if days_overdue <= 0:
            bucket_current += bal
            bucket_name = "AL_CORRIENTE"
        elif 1 <= days_overdue <= 30:
            bucket_1_30 += bal
            bucket_name = "1_A_30"
        elif 31 <= days_overdue <= 60:
            bucket_31_60 += bal
            bucket_name = "31_A_60"
        elif 61 <= days_overdue <= 90:
            bucket_61_90 += bal
            bucket_name = "61_A_90"
        else:
            bucket_over_90 += bal
            bucket_name = "MAS_DE_90"

        detailed_docs.append({
            "id": d.id,
            "folio": d.formatted_folio,
            "cfdi_uuid": d.cfdi_uuid,
            "customer_name": d.customer.legal_name if d.customer else "Cliente",
            "issue_date": str(d.issue_date.date()) if d.issue_date else None,
            "due_date": str(d.due_date),
            "days_overdue": days_overdue,
            "original_total": float(d.original_total),
            "current_balance": float(d.current_balance),
            "status": d.status,
            "bucket": bucket_name
        })

    overdue_total = bucket_1_30 + bucket_31_60 + bucket_61_90 + bucket_over_90
    overdue_percentage = (
        quantize_2((overdue_total / total_receivable) * 100) if total_receivable > 0 else Decimal("0.00")
    )

    return {
        "total_receivable": quantize_2(total_receivable),
        "current_receivable": quantize_2(bucket_current),
        "overdue_total": quantize_2(overdue_total),
        "overdue_percentage": overdue_percentage,
        "buckets": {
            "current": quantize_2(bucket_current),
            "days_1_30": quantize_2(bucket_1_30),
            "days_31_60": quantize_2(bucket_31_60),
            "days_61_90": quantize_2(bucket_61_90),
            "days_over_90": quantize_2(bucket_over_90)
        },
        "documents": detailed_docs
    }


async def apply_payment_receipt(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    branch_id: uuid.UUID,
    customer_id: uuid.UUID,
    user_id: uuid.UUID,
    payment_form: str,
    amount: Decimal,
    allocations: List[Dict[str, Any]],  # [{"receivable_id": UUID, "amount_paid": Decimal}]
    payment_date: Optional[datetime] = None,
    operation_number: Optional[str] = None,
    notes: Optional[str] = None
) -> PaymentReceipt:
    """
    Aplica un Recibo de Pago (REP 2.0 / CFDI 4.0 tipo P):
    1. Valida que la suma de abonos coincida exactamente con el monto del pago.
    2. Aplica bloqueos 'SELECT ... FOR UPDATE' en las cuentas por cobrar.
    3. Decrementa saldos insolutos y calcula impuestos proporcionales.
    4. Genera y timbra el XML del REP 2.0 con Mock PAC.
    """
    if amount <= Decimal("0.00"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El monto del pago debe ser mayor a cero.")

    if not allocations:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debe asignar el pago al menos a una factura pendiente.")

    allocated_sum = sum(Decimal(str(a["amount_paid"])) for a in allocations)
    if quantize_2(allocated_sum) != quantize_2(amount):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La suma asignada a las facturas (${allocated_sum:.2f}) no coincide con el total del pago recibido (${amount:.2f})."
        )

    # 1. Obtener CSD activo y Tenant
    csd_res = await db.execute(
        select(CSDCertificate).where(CSDCertificate.tenant_id == tenant_id, CSDCertificate.is_active == True)
    )
    csd = csd_res.scalar_one_or_none()
    if not csd:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se encontró un Certificado CSD activo para sellar el REP 2.0.")

    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()
    cust_res = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.tenant_id == tenant_id))
    customer = cust_res.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado.")

    # 2. Consumir Folio de Pago (PAGO o REP)
    serie_code, folio_num, _ = await consume_next_folio(
        db=db,
        tenant_id=tenant_id,
        document_type="PAGO",
        branch_id=branch_id
    )
    formatted_folio = f"{serie_code}-{folio_num}"

    # 3. Crear cabecera del Recibo de Pago
    pay_dt = payment_date or datetime.now(timezone.utc)
    payment_receipt = PaymentReceipt(
        tenant_id=tenant_id,
        customer_id=customer_id,
        branch_id=branch_id,
        user_id=user_id,
        serie=serie_code,
        folio=folio_num,
        formatted_folio=formatted_folio,
        payment_date=pay_dt,
        payment_form=payment_form,
        currency_code="MXN",
        exchange_rate=Decimal("1.0000"),
        amount=quantize_2(amount),
        operation_number=operation_number,
        status="TIMBRADO",
        notes=notes
    )
    db.add(payment_receipt)
    await db.flush()

    # 4. Obtener todos los documentos por cobrar involucrados de forma atómica
    rec_ids = [uuid.UUID(str(a["receivable_id"])) for a in allocations]
    rec_stmt = (
        select(ReceivableDocument)
        .options(selectinload(ReceivableDocument.installments))
        .where(ReceivableDocument.id.in_(rec_ids), ReceivableDocument.tenant_id == tenant_id)
    )
    # En PostgreSQL aplica bloqueo de fila
    if db.bind and db.bind.dialect.name == "postgresql":
        rec_stmt = rec_stmt.with_for_update()

    rec_res = await db.execute(rec_stmt)
    rec_map = {r.id: r for r in rec_res.scalars().all()}

    doc_rels = []
    tot_base_p = Decimal("0.00")
    tot_vat_p = Decimal("0.00")

    for alloc in allocations:
        rec_id = uuid.UUID(str(alloc["receivable_id"]))
        alloc_amt = quantize_2(Decimal(str(alloc["amount_paid"])))

        rec_doc = rec_map.get(rec_id)
        if not rec_doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Documento por cobrar {rec_id} no encontrado.")

        if alloc_amt > rec_doc.current_balance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El abono de ${alloc_amt:.2f} excede el saldo insoluto actual (${rec_doc.current_balance:.2f}) de {rec_doc.formatted_folio}."
            )

        # Calcular número de parcialidad directamente de los installments existentes
        num_parcialidad = len(rec_doc.installments) + 1

        prev_bal = rec_doc.current_balance
        new_bal = prev_bal - alloc_amt

        # Cálculo de impuestos proporcionales REP 2.0
        prop_taxes = calculate_proportional_taxes_rep(
            original_subtotal=rec_doc.original_subtotal,
            original_vat=rec_doc.original_vat,
            original_ret_vat=rec_doc.original_retention_vat,
            original_ret_isr=rec_doc.original_retention_isr,
            original_total=rec_doc.original_total,
            amount_paid=alloc_amt
        )

        tot_base_p += prop_taxes["proportional_base"]
        tot_vat_p += prop_taxes["proportional_vat"]

        # Crear DoctoRelacionado
        doc_rel = PaymentReceiptDocRel(
            tenant_id=tenant_id,
            payment_receipt_id=payment_receipt.id,
            receivable_document_id=rec_doc.id,
            document_uuid=rec_doc.cfdi_uuid or str(uuid.uuid4()),
            serie=rec_doc.serie,
            folio=str(rec_doc.folio),
            currency_dr=rec_doc.currency_code,
            equivalence_dr=Decimal("1.0000"),
            installment_number=num_parcialidad,
            previous_balance=prev_bal,
            amount_paid=alloc_amt,
            remaining_balance=new_bal,
            proportional_base=prop_taxes["proportional_base"],
            proportional_vat=prop_taxes["proportional_vat"],
            vat_rate=prop_taxes["vat_rate"],
            proportional_retention_vat=prop_taxes["proportional_retention_vat"],
            proportional_retention_isr=prop_taxes["proportional_retention_isr"]
        )
        doc_rels.append(doc_rel)
        db.add(doc_rel)

        # Actualizar saldo del documento origen
        rec_doc.current_balance = new_bal
        if new_bal == Decimal("0.0000"):
            rec_doc.status = "LIQUIDADO"
        else:
            rec_doc.status = "PARCIAL"

    await db.flush()

    # 5. Generar XML CFDI 4.0 con Complemento de Pagos 2.0
    from xml.etree import ElementTree as ET
    ns_cfdi = "http://www.sat.gob.mx/cfd/4"
    ns_pago20 = "http://www.sat.gob.mx/Pagos20"
    ns_xsi = "http://www.w3.org/2001/XMLSchema-instance"

    ET.register_namespace("cfdi", ns_cfdi)
    ET.register_namespace("pago20", ns_pago20)
    ET.register_namespace("xsi", ns_xsi)

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    pay_str = pay_dt.strftime("%Y-%m-%dT%H:%M:%S")

    # Cadena Original REP 2.0
    cadena_parts = [
        "4.0",
        serie_code,
        str(folio_num),
        now_str,
        csd.certificate_number,
        "0.00",
        "XXX",
        "0.00",
        "P",            # TipoDeComprobante Pago
        "01",           # Exportacion No aplica
        tenant.zip_code,
        tenant.rfc,
        tenant.legal_name,
        tenant.fiscal_regime_code,
        customer.rfc,
        customer.legal_name,
        customer.zip_code,
        customer.fiscal_regime_code,
        "CP01",         # Pagos
        # Nodo Totales REP 2.0
        f"{tot_vat_p:.2f}",
        f"{tot_base_p:.2f}",
        f"{amount:.2f}",
        # Pago
        pay_str,
        payment_form,
        "MXN",
        f"{amount:.2f}"
    ]
    cadena_original = "||" + "|".join(cadena_parts) + "||"
    sello = sign_cadena_original(cadena_original, csd.encrypted_private_key)

    cert_clean = "".join([
        line.strip() for line in csd.certificate_pem.splitlines()
        if not line.startswith("-----")
    ])

    root = ET.Element(
        f"{{{ns_cfdi}}}Comprobante",
        {
            f"{{{ns_xsi}}}schemaLocation": "http://www.sat.gob.mx/cfd/4 http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd http://www.sat.gob.mx/Pagos20 http://www.sat.gob.mx/sitio_internet/cfd/Pagos/Pagos20.xsd",
            "Version": "4.0",
            "Serie": serie_code,
            "Folio": str(folio_num),
            "Fecha": now_str,
            "Sello": sello,
            "NoCertificado": csd.certificate_number,
            "Certificado": cert_clean,
            "SubTotal": "0",
            "Moneda": "XXX",
            "Total": "0",
            "TipoDeComprobante": "P",
            "Exportacion": "01",
            "LugarExpedicion": tenant.zip_code
        }
    )

    # Emisor y Receptor
    ET.SubElement(root, f"{{{ns_cfdi}}}Emisor", {
        "Rfc": tenant.rfc,
        "Nombre": tenant.legal_name,
        "RegimenFiscal": tenant.fiscal_regime_code
    })
    ET.SubElement(root, f"{{{ns_cfdi}}}Receptor", {
        "Rfc": customer.rfc,
        "Nombre": customer.legal_name,
        "DomicilioFiscalReceptor": customer.zip_code,
        "RegimenFiscalReceptor": customer.fiscal_regime_code,
        "UsoCFDI": "CP01"
    })

    # Conceptos (Obligatorio en CFDI 4.0 tipo P: Clave 84111506 "Pago", Importe 0)
    conceptos_el = ET.SubElement(root, f"{{{ns_cfdi}}}Conceptos")
    ET.SubElement(conceptos_el, f"{{{ns_cfdi}}}Concepto", {
        "ClaveProdServ": "84111506",
        "Cantidad": "1",
        "ClaveUnidad": "ACT",
        "Descripcion": "Pago",
        "ValorUnitario": "0",
        "Importe": "0",
        "ObjetoImp": "01"
    })

    # Complemento Pagos 2.0
    comp_el = ET.SubElement(root, f"{{{ns_cfdi}}}Complemento")
    pagos20_el = ET.SubElement(comp_el, f"{{{ns_pago20}}}Pagos", {"Version": "2.0"})

    # Totales Pagos 2.0
    ET.SubElement(pagos20_el, f"{{{ns_pago20}}}Totales", {
        "TotalTrasladosBaseIVA16": f"{tot_base_p:.2f}",
        "TotalTrasladosImpuestoIVA16": f"{tot_vat_p:.2f}",
        "MontoTotalPagos": f"{amount:.2f}"
    })

    # Nodo Pago
    pago_el = ET.SubElement(pagos20_el, f"{{{ns_pago20}}}Pago", {
        "FechaPago": pay_str,
        "FormaDePagoP": payment_form,
        "MonedaP": "MXN",
        "TipoCambioP": "1",
        "Monto": f"{amount:.2f}"
    })
    if operation_number:
        pago_el.attrib["NumOperacion"] = operation_number

    # Documentos Relacionados
    for dr in doc_rels:
        docto_el = ET.SubElement(pago_el, f"{{{ns_pago20}}}DoctoRelacionado", {
            "IdDocumento": dr.document_uuid,
            "Serie": dr.serie or "",
            "Folio": dr.folio or "",
            "MonedaDR": dr.currency_dr,
            "EquivalenciaDR": "1",
            "NumParcialidad": str(dr.installment_number),
            "ImpSaldoAnt": f"{dr.previous_balance:.2f}",
            "ImpPagado": f"{dr.amount_paid:.2f}",
            "ImpSaldoInsoluto": f"{dr.remaining_balance:.2f}",
            "ObjetoImpDR": "02"
        })
        imp_dr = ET.SubElement(docto_el, f"{{{ns_pago20}}}ImpuestosDR")
        tras_dr = ET.SubElement(imp_dr, f"{{{ns_pago20}}}TrasladosDR")
        ET.SubElement(tras_dr, f"{{{ns_pago20}}}TrasladoDR", {
            "BaseDR": f"{dr.proportional_base:.2f}",
            "ImpuestoDR": "002",
            "TipoFactorDR": "Tasa",
            "TasaOCuotaDR": f"{dr.vat_rate:.6f}",
            "ImporteDR": f"{dr.proportional_vat:.2f}"
        })

    # ImpuestosP a nivel Pago
    imp_pago = ET.SubElement(pago_el, f"{{{ns_pago20}}}ImpuestosP")
    tras_pago = ET.SubElement(imp_pago, f"{{{ns_pago20}}}TrasladosP")
    ET.SubElement(tras_pago, f"{{{ns_pago20}}}TrasladoP", {
        "BaseP": f"{tot_base_p:.2f}",
        "ImpuestoP": "002",
        "TipoFactorP": "Tasa",
        "TasaOCuotaP": "0.160000",
        "ImporteP": f"{tot_vat_p:.2f}"
    })

    xml_raw = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")

    # 6. Timbrado Mock PAC
    pac_res = stamp_with_mock_pac(xml_raw, sello)

    payment_receipt.cfdi_uuid = pac_res["uuid"]
    payment_receipt.cfdi_xml = pac_res["stamped_xml"]
    payment_receipt.cfdi_stamped_at = datetime.fromisoformat(pac_res["stamped_at"]).replace(tzinfo=timezone.utc)
    payment_receipt.cfdi_sello = sello
    payment_receipt.cfdi_cadena_original = cadena_original

    await db.flush()
    return payment_receipt
