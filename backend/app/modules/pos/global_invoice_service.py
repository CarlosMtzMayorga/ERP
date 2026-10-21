import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple
from xml.etree import ElementTree as ET
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.pos.models import POSTicket
from app.modules.sales.models import SalesDocument, SalesDocumentItem
from app.modules.tenants.models import Tenant, Branch, CSDCertificate
from app.modules.master_data.models import Customer, Currency
from app.modules.tenants.folios_service import consume_next_folio
from app.modules.fiscal_mexico.cfdi_builder import sign_cadena_original, stamp_with_mock_pac
from app.modules.fiscal_mexico.tax_engine import quantize_2


def calculate_global_invoice_breakdown(tickets: List[POSTicket]) -> Dict[str, Any]:
    """
    Cálculo matemático normativo de Factura Global del SAT:
    Para cada ticket con IVA incluido, desglosa la Base Gravable y el IVA:
    Base = round(Total / 1.16, 2)
    IVA = round(Total - Base, 2)
    """
    subtotal_sum = Decimal("0.00")
    vat_sum = Decimal("0.00")
    total_sum = Decimal("0.00")
    conceptos_data = []

    for t in tickets:
        gross_total = quantize_2(t.total)
        base = quantize_2(gross_total / Decimal("1.16"))
        vat = quantize_2(gross_total - base)

        subtotal_sum += base
        vat_sum += vat
        total_sum += gross_total

        conceptos_data.append({
            "ticket_id": t.id,
            "folio": t.formatted_folio,
            "subtotal": base,
            "vat": vat,
            "total": gross_total
        })

    return {
        "subtotal": subtotal_sum,
        "vat": vat_sum,
        "total": total_sum,
        "conceptos": conceptos_data
    }


def build_global_cfdi_xml(
    tenant: Tenant,
    csd: CSDCertificate,
    serie: str,
    folio: int,
    periodicity: str,  # 01 = Diaria, 02 = Semanal, 04 = Mensual
    months: str,       # 01 .. 12
    year: int,
    breakdown: Dict[str, Any]
) -> Tuple[str, str, str]:
    """
    Construye el XML del CFDI 4.0 Global con el nodo obligatorio cfdi:InformacionGlobal.
    """
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    cert_clean = "".join([
        line.strip() for line in csd.certificate_pem.splitlines()
        if not line.startswith("-----")
    ])

    subtotal_str = f"{breakdown['subtotal']:.2f}"
    vat_str = f"{breakdown['vat']:.2f}"
    total_str = f"{breakdown['total']:.2f}"

    # 1. Cadena Original Global SAT
    cadena_parts = [
        "4.0",
        serie,
        str(folio),
        now_str,
        "01",           # FormaPago 01 Efectivo o consolidado
        subtotal_str,
        "MXN",
        total_str,
        "I",            # Ingreso
        "01",           # Exportacion No aplica
        "PUE",
        tenant.zip_code,
        periodicity,
        months,
        str(year),
        tenant.rfc,
        tenant.legal_name,
        tenant.fiscal_regime_code,
        "XAXX010101000",
        "PUBLICO EN GENERAL",
        tenant.zip_code,
        "616",          # Sin obligaciones fiscales
        "S01"           # Sin efectos fiscales
    ]

    for c in breakdown["conceptos"]:
        cadena_parts.extend([
            "01010101",
            c["folio"],
            "1",
            "ACT",
            "Venta",
            f"{c['subtotal']:.2f}",
            f"{c['subtotal']:.2f}",
            "02"
        ])

    cadena_original = "||" + "|".join(cadena_parts) + "||"

    # 2. Sello Digital
    sello = sign_cadena_original(cadena_original, csd.encrypted_private_key)

    # 3. Ensamblado de Elementos XML
    ns_cfdi = "http://www.sat.gob.mx/cfd/4"
    ns_xsi = "http://www.w3.org/2001/XMLSchema-instance"
    ET.register_namespace("cfdi", ns_cfdi)
    ET.register_namespace("xsi", ns_xsi)

    root = ET.Element(
        f"{{{ns_cfdi}}}Comprobante",
        {
            f"{{{ns_xsi}}}schemaLocation": "http://www.sat.gob.mx/cfd/4 http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd",
            "Version": "4.0",
            "Serie": serie,
            "Folio": str(folio),
            "Fecha": now_str,
            "Sello": sello,
            "FormaPago": "01",
            "NoCertificado": csd.certificate_number,
            "Certificado": cert_clean,
            "SubTotal": subtotal_str,
            "Moneda": "MXN",
            "Total": total_str,
            "TipoDeComprobante": "I",
            "Exportacion": "01",
            "MetodoPago": "PUE",
            "LugarExpedicion": tenant.zip_code
        }
    )

    # Nodo Obligatorio CFDI 4.0: InformacionGlobal
    ET.SubElement(
        root,
        f"{{{ns_cfdi}}}InformacionGlobal",
        {
            "Periodicidad": periodicity,
            "Meses": months,
            "Año": str(year)
        }
    )

    # Emisor
    ET.SubElement(
        root,
        f"{{{ns_cfdi}}}Emisor",
        {
            "Rfc": tenant.rfc,
            "Nombre": tenant.legal_name,
            "RegimenFiscal": tenant.fiscal_regime_code
        }
    )

    # Receptor Público en General
    ET.SubElement(
        root,
        f"{{{ns_cfdi}}}Receptor",
        {
            "Rfc": "XAXX010101000",
            "Nombre": "PUBLICO EN GENERAL",
            "DomicilioFiscalReceptor": tenant.zip_code,
            "RegimenFiscalReceptor": "616",
            "UsoCFDI": "S01"
        }
    )

    # Conceptos
    conceptos_el = ET.SubElement(root, f"{{{ns_cfdi}}}Conceptos")
    for c in breakdown["conceptos"]:
        c_el = ET.SubElement(
            conceptos_el,
            f"{{{ns_cfdi}}}Concepto",
            {
                "ClaveProdServ": "01010101",
                "NoIdentificacion": c["folio"],
                "Cantidad": "1",
                "ClaveUnidad": "ACT",
                "Descripcion": "Venta",
                "ValorUnitario": f"{c['subtotal']:.2f}",
                "Importe": f"{c['subtotal']:.2f}",
                "ObjetoImp": "02"
            }
        )
        imp_c = ET.SubElement(c_el, f"{{{ns_cfdi}}}Impuestos")
        tras_c = ET.SubElement(imp_c, f"{{{ns_cfdi}}}Traslados")
        ET.SubElement(
            tras_c,
            f"{{{ns_cfdi}}}Traslado",
            {
                "Base": f"{c['subtotal']:.2f}",
                "Impuesto": "002",
                "TipoFactor": "Tasa",
                "TasaOCuota": "0.160000",
                "Importe": f"{c['vat']:.2f}"
            }
        )

    # Impuestos Globales
    imp_global = ET.SubElement(
        root,
        f"{{{ns_cfdi}}}Impuestos",
        {"TotalImpuestosTrasladados": vat_str}
    )
    tras_global = ET.SubElement(imp_global, f"{{{ns_cfdi}}}Traslados")
    ET.SubElement(
        tras_global,
        f"{{{ns_cfdi}}}Traslado",
        {
            "Base": subtotal_str,
            "Impuesto": "002",
            "TipoFactor": "Tasa",
            "TasaOCuota": "0.160000",
            "Importe": vat_str
        }
    )

    xml_str = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
    return xml_str, cadena_original, sello


async def generate_global_invoice(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    branch_id: uuid.UUID,
    periodicity: str = "01",  # 01 = Diaria
    months: Optional[str] = None,
    year: Optional[int] = None,
    ticket_ids: Optional[List[uuid.UUID]] = None
) -> SalesDocument:
    """
    Genera y timbra la Factura Global CFDI 4.0 agrupando tickets de público en general.
    """
    now = datetime.now(timezone.utc)
    months_str = months or now.strftime("%m")
    year_val = year or now.year

    # 1. Obtener tickets pendientes de facturación global
    query = (
        select(POSTicket)
        .where(
            POSTicket.tenant_id == tenant_id,
            POSTicket.status == "PAID",
            POSTicket.is_globally_invoiced == False
        )
    )
    if ticket_ids:
        query = query.where(POSTicket.id.in_(ticket_ids))
    elif branch_id:
        query = query.where(POSTicket.branch_id == branch_id)

    res = await db.execute(query)
    tickets = res.scalars().all()

    if not tickets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se encontraron tickets pendientes de facturación global para el periodo seleccionado."
        )

    # 2. Obtener CSD Activo
    csd_res = await db.execute(
        select(CSDCertificate).where(CSDCertificate.tenant_id == tenant_id, CSDCertificate.is_active == True)
    )
    csd = csd_res.scalar_one_or_none()
    if not csd:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No hay Certificado CSD activo para timbrar la factura global.")

    # 3. Obtener Tenant y Sucursal
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()

    # Consumir Folio de Factura
    serie_code, folio_num, _ = await consume_next_folio(
        db=db,
        tenant_id=tenant_id,
        document_type="FAC",
        branch_id=branch_id
    )
    formatted_folio = f"{serie_code}-{folio_num}"

    # 4. Desglose impositivo de tickets
    breakdown = calculate_global_invoice_breakdown(tickets)

    # 5. Construcción y Sellado XML CFDI 4.0
    xml_raw, cadena, sello = build_global_cfdi_xml(
        tenant=tenant,
        csd=csd,
        serie=serie_code,
        folio=folio_num,
        periodicity=periodicity,
        months=months_str,
        year=year_val,
        breakdown=breakdown
    )

    # 6. Timbrado Mock PAC
    pac_res = stamp_with_mock_pac(xml_raw, sello)

    # Buscar cliente genérico
    cust_res = await db.execute(
        select(Customer).where(Customer.tenant_id == tenant_id, Customer.rfc == "XAXX010101000")
    )
    customer = cust_res.scalar_one_or_none()
    if not customer:
        customer = Customer(
            tenant_id=tenant_id,
            code="PUBLICO",
            rfc="XAXX010101000",
            legal_name="PUBLICO EN GENERAL",
            fiscal_regime_code="616",
            zip_code=tenant.zip_code
        )
        db.add(customer)
        await db.flush()

    # Obtener moneda base
    curr_res = await db.execute(select(Currency).where(Currency.tenant_id == tenant_id, Currency.is_base == True))
    currency = curr_res.scalar_one_or_none()
    currency_id = currency.id if currency else tickets[0].branch_id

    # 7. Crear SalesDocument de Factura Global
    global_invoice = SalesDocument(
        tenant_id=tenant_id,
        branch_id=branch_id,
        warehouse_id=tickets[0].warehouse_id,
        customer_id=customer.id,
        currency_id=currency_id,
        document_type="FACTURA",
        status="TIMBRADO",
        serie=serie_code,
        folio=folio_num,
        formatted_folio=formatted_folio,
        subtotal=breakdown["subtotal"],
        discount_total=Decimal("0.00"),
        tax_iva_total=breakdown["vat"],
        tax_ieps_total=Decimal("0.00"),
        retention_iva_total=Decimal("0.00"),
        retention_isr_total=Decimal("0.00"),
        total=breakdown["total"],
        total_cost_cogs=Decimal("0.00"),
        payment_form="01",
        payment_method="PUE",
        cfdi_use="S01",
        cfdi_uuid=pac_res["uuid"],
        cfdi_xml=pac_res["stamped_xml"],
        cfdi_stamped_at=datetime.fromisoformat(pac_res["stamped_at"]).replace(tzinfo=timezone.utc),
        cfdi_sello=sello,
        cfdi_cadena_original=cadena,
        notes=f"Factura Global SAT ({len(tickets)} tickets incluidos)"
    )
    db.add(global_invoice)
    await db.flush()

    # 8. Marcar tickets como facturados globalmente
    ticket_ids_to_update = [t.id for t in tickets]
    await db.execute(
        update(POSTicket)
        .where(POSTicket.id.in_(ticket_ids_to_update))
        .values(
            is_globally_invoiced=True,
            global_invoice_id=global_invoice.id
        )
    )

    return global_invoice
