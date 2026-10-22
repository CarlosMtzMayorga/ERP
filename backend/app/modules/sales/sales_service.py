import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.sales.models import SalesDocument, SalesDocumentItem
from app.modules.tenants.models import Tenant, Branch, CSDCertificate
from app.modules.master_data.models import Customer, Product, Currency
from app.modules.tenants.folios_service import consume_next_folio
from app.modules.fiscal_mexico.tax_engine import calculate_item_taxes, calculate_document_totals, quantize_2
from app.modules.fiscal_mexico.cfdi_builder import generate_cfdi_xml, stamp_with_mock_pac
from app.modules.inventories.inventory_service import (
    create_reservation,
    record_exit,
    get_or_create_stock
)
from app.modules.inventories.models import InventoryReservation


async def create_sales_document(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    branch_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    customer_id: uuid.UUID,
    currency_id: uuid.UUID,
    document_type: str,  # COTIZACION, PEDIDO, REMISION, FACTURA
    items_input: List[Dict[str, Any]],
    payment_form: str = "03",
    payment_method: str = "PUE",
    cfdi_use: str = "G03",
    price_list_id: Optional[uuid.UUID] = None,
    source_document_id: Optional[uuid.UUID] = None,
    source_document_type: Optional[str] = None,
    notes: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    approve_immediately: bool = True
) -> SalesDocument:
    """
    Crea un documento de venta encadenado.
    Calcula impuestos con alta precisión decimal.
    Si es Pedido Aprobado -> Genera reserva en Inventarios (Soft Allocation).
    Si es Factura/Remisión directa -> Descarga inventario físico en Kardex y evalúa COGS.
    """
    if not items_input:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El documento debe incluir al menos una partida.")

    # 1. Consumir Folio Atómico con bloqueo pesimista
    doc_type_clean = document_type.upper()
    folio_lookup_type = "FAC" if doc_type_clean == "FACTURA" else doc_type_clean
    serie_code, folio_num, _ = await consume_next_folio(
        db=db,
        tenant_id=tenant_id,
        document_type=folio_lookup_type,
        branch_id=branch_id
    )

    formatted_folio = f"{serie_code}-{folio_num}"

    # 2. Procesar y calcular cada partida
    processed_items = []
    items_tax_input = []
    total_cogs = Decimal("0.0000")

    for idx, item in enumerate(items_input, start=1):
        product_res = await db.execute(
            select(Product).where(Product.id == item["product_id"], Product.tenant_id == tenant_id)
        )
        product = product_res.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Artículo con ID {item['product_id']} no existe.")

        qty = Decimal(str(item["quantity"]))
        unit_price = Decimal(str(item["unit_price"]))
        disc_rate = Decimal(str(item.get("discount_rate", "0.0000")))

        # Motor impositivo SAT
        vat_rate = Decimal(str(item.get("vat_rate", product.vat_rate)))
        ieps_rate = Decimal(str(item.get("ieps_rate", product.ieps_rate)))
        ret_vat_rate = Decimal(str(item.get("retention_vat_rate", "0.0000")))
        ret_isr_rate = Decimal(str(item.get("retention_isr_rate", "0.0000")))

        tax_res = calculate_item_taxes(
            quantity=qty,
            unit_price=unit_price,
            discount_rate=disc_rate,
            vat_rate=vat_rate,
            ieps_rate=ieps_rate,
            retention_vat_rate=ret_vat_rate,
            retention_isr_rate=ret_isr_rate,
            sat_objeto_imp=product.sat_objeto_imp
        )

        items_tax_input.append(tax_res)

        item_model = SalesDocumentItem(
            tenant_id=tenant_id,
            product_id=product.id,
            line_number=idx,
            sku=product.sku,
            description=item.get("description", product.name),
            quantity=qty,
            unit_price=unit_price,
            discount_rate=disc_rate,
            discount_amount=tax_res["discount_amount"],
            subtotal=tax_res["subtotal"],
            sat_clave_prod_serv=product.sat_clave_prod_serv,
            sat_clave_unidad=product.sat_clave_unidad,
            unit_name=product.unit_name,
            sat_objeto_imp=product.sat_objeto_imp,
            vat_rate=vat_rate,
            vat_amount=tax_res["vat_amount"],
            ieps_rate=ieps_rate,
            ieps_amount=tax_res["ieps_amount"],
            retention_vat_rate=ret_vat_rate,
            retention_vat_amount=tax_res["retention_vat_amount"],
            retention_isr_rate=ret_isr_rate,
            retention_isr_amount=tax_res["retention_isr_amount"],
            total=tax_res["total"],
            unit_cost=Decimal("0.0000"),
            total_cost=Decimal("0.0000")
        )
        processed_items.append((item_model, product))

    # 3. Consolidar totales del documento
    doc_totals = calculate_document_totals(items_tax_input)

    # Hook de Validación de Crédito y Cobranza (CxC):
    # Si es Pedido, Remisión o Factura a crédito (PPD), se evalúa si el cliente tiene facturas vencidas o sobregiro
    if doc_type_clean in ("PEDIDO", "REMISION", "FACTURA"):
        from app.modules.cxc.cxc_service import check_customer_credit_status, create_receivable_from_sales_document
        is_credit = (payment_method == "PPD") or (doc_type_clean in ("PEDIDO", "REMISION"))
        if is_credit:
            credit_ok, credit_reason, _ = await check_customer_credit_status(
                db=db,
                tenant_id=tenant_id,
                customer_id=customer_id,
                attempted_amount=doc_totals["total"]
            )
            if not credit_ok:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Rechazado por Control de Crédito: {credit_reason}"
                )

    status_initial = "BORRADOR"
    if doc_type_clean == "PEDIDO" and approve_immediately:
        status_initial = "APROBADO"
    elif doc_type_clean in ("REMISION", "FACTURA"):
        status_initial = "PENDIENTE"  # Pendiente de timbrar o entregar

    doc = SalesDocument(
        tenant_id=tenant_id,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        customer_id=customer_id,
        price_list_id=price_list_id,
        currency_id=currency_id,
        document_type=doc_type_clean,
        status=status_initial,
        serie=serie_code,
        folio=folio_num,
        formatted_folio=formatted_folio,
        source_document_id=source_document_id,
        source_document_type=source_document_type,
        exchange_rate=Decimal("1.0000"),
        subtotal=doc_totals["subtotal"],
        discount_total=doc_totals["discount_total"],
        tax_iva_total=doc_totals["tax_iva_total"],
        tax_ieps_total=doc_totals["tax_ieps_total"],
        retention_iva_total=doc_totals["retention_iva_total"],
        retention_isr_total=doc_totals["retention_isr_total"],
        total=doc_totals["total"],
        total_cost_cogs=Decimal("0.0000"),
        payment_form=payment_form,
        payment_method=payment_method,
        cfdi_use=cfdi_use,
        notes=notes,
        user_id=user_id
    )

    for item_model, _ in processed_items:
        doc.items.append(item_model)

    db.add(doc)
    await db.flush()  # Para tener doc.id

    # 4. Integración Estricta con Inventarios:
    # A) Si es Pedido Aprobado -> Generar Apartado (Soft Allocation)
    if doc_type_clean == "PEDIDO" and doc.status == "APROBADO":
        for item_model, product in processed_items:
            if product.product_type == "PRODUCTO":
                await create_reservation(
                    db=db,
                    tenant_id=tenant_id,
                    warehouse_id=warehouse_id,
                    product_id=product.id,
                    quantity=item_model.quantity,
                    reference_type="PEDIDO_VENTA",
                    reference_id=doc.id,
                    reference_folio=doc.formatted_folio,
                    user_id=user_id
                )

    # B) Si es Factura o Remisión Directa -> Descargar Inventario y evaluar COGS
    elif doc_type_clean in ("FACTURA", "REMISION") and not source_document_id:
        doc_total_cogs = Decimal("0.0000")
        for item_model, product in processed_items:
            if product.product_type == "PRODUCTO":
                mov, _, consumptions = await record_exit(
                    db=db,
                    tenant_id=tenant_id,
                    warehouse_id=warehouse_id,
                    product_id=product.id,
                    quantity=item_model.quantity,
                    movement_type="SALIDA_VENTA",
                    reference_type="FACTURA" if doc_type_clean == "FACTURA" else "REMISION",
                    reference_id=doc.id,
                    reference_folio=doc.formatted_folio,
                    notes=f"Venta en {doc.formatted_folio}",
                    user_id=user_id
                )
                item_model.unit_cost = mov.unit_cost
                item_model.total_cost = mov.total_cost
                doc_total_cogs += mov.total_cost
        doc.total_cost_cogs = doc_total_cogs

    # C) Si es Factura PPD -> Generar Cargo en Cuentas por Cobrar (CxC)
    if doc_type_clean == "FACTURA" and payment_method == "PPD":
        cust = (await db.execute(select(Customer).where(Customer.id == customer_id))).scalar_one()
        await create_receivable_from_sales_document(db=db, sales_doc=doc, customer=cust)

    # D) Si es Factura -> Contabilización Automática en Tiempo Real (Fase 10 - Contabilidad)
    if doc_type_clean == "FACTURA":
        try:
            from app.modules.accounting.accounting_service import create_automatic_sales_journal_entry
            await create_automatic_sales_journal_entry(db=db, tenant_id=tenant_id, sales_doc=doc)
        except Exception as e:
            print(f"[ACCOUNTING] Log contable automático: {e}")

    return doc


async def convert_order_to_invoice(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    order_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None
) -> SalesDocument:
    """
    Convierte un Pedido en Factura:
    1. Consume la reserva de inventario (Soft Allocation).
    2. Ejecuta la salida oficial en el Kardex y evalúa el costo de lo vendido (PEPS/Promedio).
    3. Marca el pedido como SURTIDO.
    4. Genera la Factura con trazabilidad al Pedido origen.
    """
    order_stmt = (
        select(SalesDocument)
        .options(
            selectinload(SalesDocument.items),
            selectinload(SalesDocument.customer)
        )
        .where(
            SalesDocument.id == order_id,
            SalesDocument.tenant_id == tenant_id,
            SalesDocument.document_type == "PEDIDO"
        )
    )
    order_res = await db.execute(order_stmt)
    order = order_res.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado.")
    if order.status in ("SURTIDO", "CANCELADO"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"El pedido ya se encuentra en estado '{order.status}'.")

    # Preparar partidas para la nueva factura
    invoice_items_input = []
    for item in order.items:
        invoice_items_input.append({
            "product_id": item.product_id,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "discount_rate": item.discount_rate,
            "vat_rate": item.vat_rate,
            "ieps_rate": item.ieps_rate,
            "retention_vat_rate": item.retention_vat_rate,
            "retention_isr_rate": item.retention_isr_rate,
            "description": item.description
        })

    # Consumir Folio de Factura
    serie_code, folio_num, _ = await consume_next_folio(
        db=db,
        tenant_id=tenant_id,
        document_type="FAC",
        branch_id=order.branch_id
    )
    formatted_folio = f"{serie_code}-{folio_num}"

    # Crear factura
    invoice = SalesDocument(
        tenant_id=tenant_id,
        branch_id=order.branch_id,
        warehouse_id=order.warehouse_id,
        customer_id=order.customer_id,
        price_list_id=order.price_list_id,
        currency_id=order.currency_id,
        document_type="FACTURA",
        status="PENDIENTE",
        serie=serie_code,
        folio=folio_num,
        formatted_folio=formatted_folio,
        source_document_id=order.id,
        source_document_type="PEDIDO",
        exchange_rate=order.exchange_rate,
        subtotal=order.subtotal,
        discount_total=order.discount_total,
        tax_iva_total=order.tax_iva_total,
        tax_ieps_total=order.tax_ieps_total,
        retention_iva_total=order.retention_iva_total,
        retention_isr_total=order.retention_isr_total,
        total=order.total,
        total_cost_cogs=Decimal("0.0000"),
        payment_form=order.payment_form,
        payment_method=order.payment_method,
        cfdi_use=order.cfdi_use,
        notes=f"Facturación derivada del Pedido {order.formatted_folio}",
        user_id=user_id
    )

    # Buscar reservas activas vinculadas al pedido
    reservations_res = await db.execute(
        select(InventoryReservation).where(
            InventoryReservation.tenant_id == tenant_id,
            InventoryReservation.reference_id == order.id,
            InventoryReservation.status == "RESERVED"
        )
    )
    reservations_by_prod = {r.product_id: r for r in reservations_res.scalars().all()}

    total_invoice_cogs = Decimal("0.0000")

    for order_item in order.items:
        # Descargar de inventario usando la reserva
        res_record = reservations_by_prod.get(order_item.product_id)
        res_id = res_record.id if res_record else None

        mov, _, _ = await record_exit(
            db=db,
            tenant_id=tenant_id,
            warehouse_id=order.warehouse_id,
            product_id=order_item.product_id,
            quantity=order_item.quantity,
            movement_type="SALIDA_VENTA",
            reference_type="FACTURA",
            reference_id=order.id,
            reference_folio=formatted_folio,
            notes=f"Salida de almacén por Factura {formatted_folio} (Pedido {order.formatted_folio})",
            user_id=user_id,
            reservation_id=res_id
        )

        inv_item = SalesDocumentItem(
            tenant_id=tenant_id,
            product_id=order_item.product_id,
            line_number=order_item.line_number,
            sku=order_item.sku,
            description=order_item.description,
            quantity=order_item.quantity,
            unit_price=order_item.unit_price,
            discount_rate=order_item.discount_rate,
            discount_amount=order_item.discount_amount,
            subtotal=order_item.subtotal,
            sat_clave_prod_serv=order_item.sat_clave_prod_serv,
            sat_clave_unidad=order_item.sat_clave_unidad,
            unit_name=order_item.unit_name,
            sat_objeto_imp=order_item.sat_objeto_imp,
            vat_rate=order_item.vat_rate,
            vat_amount=order_item.vat_amount,
            ieps_rate=order_item.ieps_rate,
            ieps_amount=order_item.ieps_amount,
            retention_vat_rate=order_item.retention_vat_rate,
            retention_vat_amount=order_item.retention_vat_amount,
            retention_isr_rate=order_item.retention_isr_rate,
            retention_isr_amount=order_item.retention_isr_amount,
            total=order_item.total,
            unit_cost=mov.unit_cost,
            total_cost=mov.total_cost
        )
        invoice.items.append(inv_item)
        total_invoice_cogs += mov.total_cost

    invoice.total_cost_cogs = total_invoice_cogs
    order.status = "SURTIDO"

    db.add(invoice)
    await db.flush()

    if invoice.payment_method == "PPD":
        from app.modules.cxc.cxc_service import create_receivable_from_sales_document
        cust = (await db.execute(select(Customer).where(Customer.id == invoice.customer_id))).scalar_one()
        await create_receivable_from_sales_document(db=db, sales_doc=invoice, customer=cust)

    # Contabilización Automática en Tiempo Real
    try:
        from app.modules.accounting.accounting_service import create_automatic_sales_journal_entry
        await create_automatic_sales_journal_entry(db=db, tenant_id=tenant_id, sales_doc=invoice)
    except Exception as e:
        print(f"[ACCOUNTING] Log contable automático conversión pedido: {e}")

    return invoice


async def stamp_invoice_cfdi(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    invoice_id: uuid.UUID
) -> SalesDocument:
    """
    Timbra fiscalmente una factura:
    1. Obtiene CSD activo de la empresa.
    2. Genera XML CFDI 4.0 con Cadena Original y Sello SHA-256 with RSA.
    3. Simula timbrado con PAC (Mock PAC) agregando TimbreFiscalDigital 1.1 con UUID SAT.
    4. Actualiza estado a TIMBRADO.
    """
    doc_stmt = (
        select(SalesDocument)
        .options(
            selectinload(SalesDocument.items),
            selectinload(SalesDocument.customer),
            selectinload(SalesDocument.currency)
        )
        .where(
            SalesDocument.id == invoice_id,
            SalesDocument.tenant_id == tenant_id,
            SalesDocument.document_type == "FACTURA"
        )
    )
    doc_res = await db.execute(doc_stmt)
    invoice = doc_res.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factura no encontrada.")
    if invoice.status == "TIMBRADO":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La factura ya se encuentra timbrada.")

    # Obtener CSD activo
    csd_res = await db.execute(
        select(CSDCertificate).where(
            CSDCertificate.tenant_id == tenant_id,
            CSDCertificate.is_active == True
        )
    )
    csd = csd_res.scalar_one_or_none()
    if not csd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay un Certificado CSD activo configurado para timbrar en esta empresa."
        )

    # Obtener Tenant
    tenant_res = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_res.scalar_one()

    # Generar XML y Sellado Digital
    xml_raw, cadena, sello = generate_cfdi_xml(
        document=invoice,
        tenant=tenant,
        customer=invoice.customer,
        csd=csd
    )

    # Timbrado con Mock PAC
    pac_res = stamp_with_mock_pac(xml_raw, sello)

    # Actualizar factura timbrada
    invoice.status = "TIMBRADO"
    invoice.cfdi_uuid = pac_res["uuid"]
    invoice.cfdi_xml = pac_res["stamped_xml"]
    invoice.cfdi_stamped_at = datetime.fromisoformat(pac_res["stamped_at"]).replace(tzinfo=timezone.utc)
    invoice.cfdi_sello = sello
    invoice.cfdi_cadena_original = cadena

    return invoice
