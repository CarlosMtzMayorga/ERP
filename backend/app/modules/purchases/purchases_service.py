import uuid
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta, date
from typing import List, Optional, Tuple, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.purchases.models import (
    PurchaseDocument,
    PurchaseDocumentItem,
    PayableDocument,
)
from app.modules.purchases.schemas import (
    PurchaseOrderCreate,
    GoodsReceptionCreate,
    SupplierInvoiceCreate,
    PurchasesDashboardMetrics,
    TopSupplierMetric,
    XMLInvoicePreview,
    XMLConceptPreview,
    ConfirmXMLImportRequest,
)
from app.modules.purchases.xml_parser import parse_cfdi_40_xml
from app.modules.inventories.inventory_service import record_entry
from app.modules.tenants.models import FiscalFoliosSeries, Branch
from app.modules.tenants.folios_service import consume_next_folio
from app.modules.master_data.models import (
    Product,
    Supplier,
    Warehouse,
    Currency,
)


def _round(val: Decimal, decimals: int = 4) -> Decimal:
    fmt = Decimal("10") ** -decimals
    return val.quantize(fmt, rounding=ROUND_HALF_UP)


async def ensure_folio_series(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    branch_id: Optional[uuid.UUID],
    doc_type: str,
    serie: str,
    initial_folio: int = 1
):
    """Garantiza la existencia de una serie de folios para evitar bloqueos por 404."""
    stmt = select(FiscalFoliosSeries).where(
        FiscalFoliosSeries.tenant_id == tenant_id,
        FiscalFoliosSeries.document_type == doc_type
    )
    res = await db.execute(stmt)
    existing = res.scalars().first()
    if not existing:
        new_serie = FiscalFoliosSeries(
            tenant_id=tenant_id,
            branch_id=branch_id,
            document_type=doc_type,
            serie=serie,
            initial_folio=initial_folio,
            current_folio=0,
            is_default=True
        )
        db.add(new_serie)
        await db.flush()


async def create_purchase_order(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: PurchaseOrderCreate,
    user_id: Optional[uuid.UUID] = None
) -> PurchaseDocument:
    """
    Crea una Orden de Compra (OC) en estado BORRADOR.
    Calcula subtotales, prorrateos de fletes preliminares e impuestos.
    """
    await ensure_folio_series(db, tenant_id, data.branch_id, "OC", "OC", 1)
    serie, next_folio, _ = await consume_next_folio(db, tenant_id, "OC", branch_id=data.branch_id)
    formatted_folio = f"{serie}-{next_folio:05d}"

    # Validar proveedor
    supplier = await db.get(Supplier, data.supplier_id)
    if not supplier or supplier.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado.")

    subtotal_total = Decimal("0.0000")
    discount_total = Decimal("0.0000")
    tax_iva_total = Decimal("0.0000")
    tax_ieps_total = Decimal("0.0000")

    # Primera pasada: calcular subtotal de items para base de prorrateo
    raw_items: List[Dict[str, Any]] = []
    for item_data in data.items:
        product = await db.get(Product, item_data.product_id)
        if not product or product.tenant_id != tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Artículo {item_data.product_id} no encontrado.")

        item_sub = _round(item_data.quantity * item_data.unit_cost)
        disc_amount = _round(item_sub * item_data.discount_rate)
        line_subtotal = item_sub - disc_amount
        subtotal_total += line_subtotal
        discount_total += disc_amount

        raw_items.append({
            "product": product,
            "data": item_data,
            "line_subtotal": line_subtotal,
            "disc_amount": disc_amount,
        })

    # Segunda pasada: prorratear flete y calcular impuestos
    items_to_create: List[PurchaseDocumentItem] = []
    accumulated_freight = Decimal("0.0000")

    for idx, raw in enumerate(raw_items, start=1):
        product = raw["product"]
        item_data = raw["data"]
        line_sub = raw["line_subtotal"]

        if subtotal_total > 0 and data.freight_total > 0:
            if idx == len(raw_items):
                # Penny exact balance para el flete prorrateado
                freight_prorated = data.freight_total - accumulated_freight
            else:
                freight_prorated = _round((line_sub / subtotal_total) * data.freight_total)
                accumulated_freight += freight_prorated
        else:
            freight_prorated = Decimal("0.0000")

        effective_unit_cost = _round((line_sub + freight_prorated) / item_data.quantity)
        vat_amount = _round(line_sub * item_data.vat_rate)
        ieps_amount = _round(line_sub * item_data.ieps_rate)
        line_total = line_sub + vat_amount + ieps_amount

        tax_iva_total += vat_amount
        tax_ieps_total += ieps_amount

        doc_item = PurchaseDocumentItem(
            tenant_id=tenant_id,
            product_id=product.id,
            line_number=idx,
            sku=product.sku,
            description=product.name,
            quantity_ordered=item_data.quantity,
            quantity_received=Decimal("0.0000"),
            unit_cost=item_data.unit_cost,
            discount_rate=item_data.discount_rate,
            discount_amount=raw["disc_amount"],
            freight_prorated=freight_prorated,
            effective_unit_cost=effective_unit_cost,
            subtotal=line_sub,
            sat_clave_prod_serv=item_data.sat_clave_prod_serv or product.sat_clave_prod_serv,
            sat_clave_unidad=item_data.sat_clave_unidad or product.sat_clave_unidad,
            unit_name=product.unit_name,
            vat_rate=item_data.vat_rate,
            vat_amount=vat_amount,
            ieps_rate=item_data.ieps_rate,
            ieps_amount=ieps_amount,
            total=line_total,
            source_item_id=item_data.source_item_id
        )
        items_to_create.append(doc_item)

    total_doc = subtotal_total + tax_iva_total + tax_ieps_total + data.freight_total

    order = PurchaseDocument(
        tenant_id=tenant_id,
        branch_id=data.branch_id,
        warehouse_id=data.warehouse_id,
        supplier_id=data.supplier_id,
        currency_id=data.currency_id,
        document_type="ORDEN_COMPRA",
        status="BORRADOR",
        serie=serie,
        folio=next_folio,
        formatted_folio=formatted_folio,
        expected_date=data.expected_date,
        source_document_id=data.source_document_id,
        source_document_type="REQUISICION" if data.source_document_id else None,
        subtotal=subtotal_total,
        discount_total=discount_total,
        freight_total=data.freight_total,
        tax_iva_total=tax_iva_total,
        tax_ieps_total=tax_ieps_total,
        total=total_doc,
        notes=data.notes,
        user_id=user_id,
        items=items_to_create
    )
    db.add(order)
    await db.flush()
    return order


async def authorize_purchase_order(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    purchase_order_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None
) -> PurchaseDocument:
    """Autoriza una Orden de Compra para habilitar su recepción física en almacén."""
    stmt = (
        select(PurchaseDocument)
        .options(selectinload(PurchaseDocument.items))
        .where(PurchaseDocument.id == purchase_order_id, PurchaseDocument.tenant_id == tenant_id)
    )
    res = await db.execute(stmt)
    po = res.scalar_one_or_none()
    if not po:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden de compra no encontrada.")

    if po.status != "BORRADOR":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede autorizar una orden en estado '{po.status}'."
        )

    po.status = "AUTORIZADA"
    await db.flush()
    return po


async def receive_merchandise(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: GoodsReceptionCreate,
    user_id: Optional[uuid.UUID] = None
) -> PurchaseDocument:
    """
    Registra una Recepción de Mercancía en Almacén.
    
    INTEGRACIÓN CRÍTICA CON INVENTARIOS (FASE 3):
    1. Afecta el Kardex Inmutable con movimiento 'ENTRADA_COMPRA'.
    2. Recalcula dinámicamente el Costo Promedio Ponderado en ProductWarehouseStock y Product.
    3. Si el artículo usa costeo PEPS/FIFO, genera la Capa de Costo ('CostLayer').
    4. Prorratea fletes adicionales directamente en el costo unitario efectivo de los artículos recibidos.
    5. Actualiza cantidades recibidas y estado de la Orden de Compra (Backorders: PARCIALMENTE_RECIBIDA / RECIBIDA).
    """
    await ensure_folio_series(db, tenant_id, data.branch_id, "REC", "REC", 1)
    serie, next_folio, _ = await consume_next_folio(db, tenant_id, "REC", branch_id=data.branch_id)
    formatted_folio = f"{serie}-{next_folio:05d}"

    po: Optional[PurchaseDocument] = None
    po_items_map: Dict[uuid.UUID, PurchaseDocumentItem] = {}

    if data.purchase_order_id:
        stmt = (
            select(PurchaseDocument)
            .options(selectinload(PurchaseDocument.items))
            .where(
                PurchaseDocument.id == data.purchase_order_id,
                PurchaseDocument.tenant_id == tenant_id
            )
        )
        res = await db.execute(stmt)
        po = res.scalar_one_or_none()
        if not po:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden de Compra no encontrada.")

        if po.status not in ("AUTORIZADA", "PARCIALMENTE_RECIBIDA"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La Orden de Compra '{po.formatted_folio}' está en estatus '{po.status}' y no permite recepciones."
            )

        po_items_map = {item.id: item for item in po.items}

    subtotal_total = Decimal("0.0000")
    raw_reception_items: List[Dict[str, Any]] = []

    # 1. Calcular subtotales preliminares de la recepción
    for rec_item in data.items:
        prod = await db.get(Product, rec_item.product_id)
        if not prod or prod.tenant_id != tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Artículo {rec_item.product_id} no encontrado.")

        # Obtener costo acordado de la OC si no fue especificado directamente
        unit_cost = rec_item.unit_cost
        source_item: Optional[PurchaseDocumentItem] = None
        if rec_item.source_item_id and rec_item.source_item_id in po_items_map:
            source_item = po_items_map[rec_item.source_item_id]
            if unit_cost is None:
                unit_cost = source_item.unit_cost
        elif unit_cost is None:
            unit_cost = prod.last_cost or prod.base_price

        item_sub = _round(rec_item.quantity_received * unit_cost)
        subtotal_total += item_sub

        raw_reception_items.append({
            "product": prod,
            "data": rec_item,
            "unit_cost": unit_cost,
            "line_subtotal": item_sub,
            "source_item": source_item
        })

    # 2. Prorratear flete y afectar Kardex / Valuación por partida
    created_items: List[PurchaseDocumentItem] = []
    accumulated_freight = Decimal("0.0000")
    total_tax_iva = Decimal("0.0000")

    for idx, raw in enumerate(raw_reception_items, start=1):
        prod = raw["product"]
        rec_data = raw["data"]
        unit_cost = raw["unit_cost"]
        line_sub = raw["line_subtotal"]
        source_item = raw["source_item"]

        # Prorrateo de flete
        if subtotal_total > 0 and data.freight_total > 0:
            if idx == len(raw_reception_items):
                freight_prorated = data.freight_total - accumulated_freight
            else:
                freight_prorated = _round((line_sub / subtotal_total) * data.freight_total)
                accumulated_freight += freight_prorated
        else:
            freight_prorated = Decimal("0.0000")

        # Costo unitario efectivo (incluyendo flete prorrateado)
        effective_unit_cost = _round((line_sub + freight_prorated) / rec_data.quantity_received)
        vat_amount = _round(line_sub * prod.vat_rate)
        total_tax_iva += vat_amount

        # Actualizar cantidad surtida en la Orden de Compra de origen (Backorder tracking)
        if source_item:
            source_item.quantity_received += rec_data.quantity_received

        doc_item = PurchaseDocumentItem(
            tenant_id=tenant_id,
            product_id=prod.id,
            line_number=idx,
            sku=prod.sku,
            description=prod.name,
            quantity_ordered=source_item.quantity_ordered if source_item else rec_data.quantity_received,
            quantity_received=rec_data.quantity_received,
            unit_cost=unit_cost,
            discount_rate=Decimal("0.0000"),
            discount_amount=Decimal("0.0000"),
            freight_prorated=freight_prorated,
            effective_unit_cost=effective_unit_cost,
            subtotal=line_sub,
            sat_clave_prod_serv=prod.sat_clave_prod_serv,
            sat_clave_unidad=prod.sat_clave_unidad,
            unit_name=prod.unit_name,
            vat_rate=prod.vat_rate,
            vat_amount=vat_amount,
            total=line_sub + vat_amount,
            source_item_id=source_item.id if source_item else None
        )
        created_items.append(doc_item)

    total_reception = subtotal_total + total_tax_iva + data.freight_total

    reception = PurchaseDocument(
        tenant_id=tenant_id,
        branch_id=data.branch_id,
        warehouse_id=data.warehouse_id,
        supplier_id=data.supplier_id,
        currency_id=data.currency_id,
        document_type="RECEPCION",
        status="RECIBIDA",
        serie=serie,
        folio=next_folio,
        formatted_folio=formatted_folio,
        source_document_id=po.id if po else None,
        source_document_type="ORDEN_COMPRA" if po else None,
        subtotal=subtotal_total,
        discount_total=Decimal("0.0000"),
        freight_total=data.freight_total,
        tax_iva_total=total_tax_iva,
        total=total_reception,
        notes=data.notes,
        user_id=user_id,
        items=created_items
    )
    db.add(reception)
    await db.flush()

    # 3. AFECTACIÓN FÍSICA Y FINANCIERA EN KARDEX INMUTABLE (Fase 3)
    for doc_item in created_items:
        await record_entry(
            db=db,
            tenant_id=tenant_id,
            warehouse_id=data.warehouse_id,
            product_id=doc_item.product_id,
            quantity=doc_item.quantity_received,
            unit_cost=doc_item.effective_unit_cost,  # Costo con flete prorrateado
            movement_type="ENTRADA_COMPRA",
            reference_type="RECEPCION_COMPRA",
            reference_id=reception.id,
            reference_folio=reception.formatted_folio,
            notes=f"Recepción {reception.formatted_folio}" + (f" de OC {po.formatted_folio}" if po else ""),
            user_id=user_id
        )

    # 4. Actualizar estado de la Orden de Compra previa (Backorders)
    if po:
        all_fulfilled = True
        any_received = False
        for item in po.items:
            if item.quantity_received > 0:
                any_received = True
            if item.quantity_received < item.quantity_ordered:
                all_fulfilled = False

        if all_fulfilled:
            po.status = "RECIBIDA"
        elif any_received:
            po.status = "PARCIALMENTE_RECIBIDA"

    await db.flush()
    return reception


async def create_supplier_invoice(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: SupplierInvoiceCreate,
    user_id: Optional[uuid.UUID] = None
) -> Tuple[PurchaseDocument, PayableDocument]:
    """
    Registra una Factura de Proveedor (manual o confirmada vía XML).
    
    CRÍTICO FASE 7 (ENTREGABLE 4 - GENERACIÓN DE PASIVO CXP):
    Al guardar y aprobar la factura, genera de forma atómica el pasivo en 'PayableDocument'
    por el saldo total, calculando 'due_date' según los días de crédito del proveedor.
    """
    await ensure_folio_series(db, tenant_id, data.branch_id, "FAC_PROV", "FP", 1)
    
    if data.serie and data.folio:
        serie = data.serie
        next_folio = data.folio
    else:
        serie, next_folio, _ = await consume_next_folio(db, tenant_id, "FAC_PROV", branch_id=data.branch_id)

    formatted_folio = f"{serie}-{next_folio}"

    supplier = await db.get(Supplier, data.supplier_id)
    if not supplier or supplier.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado.")

    subtotal_total = Decimal("0.0000")
    discount_total = Decimal("0.0000")
    tax_iva_total = Decimal("0.0000")
    tax_ieps_total = Decimal("0.0000")

    items_to_create: List[PurchaseDocumentItem] = []
    for idx, item_data in enumerate(data.items, start=1):
        product = await db.get(Product, item_data.product_id)
        if not product or product.tenant_id != tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Artículo {item_data.product_id} no encontrado.")

        item_sub = _round(item_data.quantity * item_data.unit_cost)
        disc_amount = _round(item_sub * item_data.discount_rate)
        line_subtotal = item_sub - disc_amount
        vat_amount = _round(line_subtotal * item_data.vat_rate)
        ieps_amount = _round(line_subtotal * item_data.ieps_rate)
        line_total = line_subtotal + vat_amount + ieps_amount

        subtotal_total += line_subtotal
        discount_total += disc_amount
        tax_iva_total += vat_amount
        tax_ieps_total += ieps_amount

        doc_item = PurchaseDocumentItem(
            tenant_id=tenant_id,
            product_id=product.id,
            line_number=idx,
            sku=product.sku,
            description=product.name,
            quantity_ordered=item_data.quantity,
            quantity_received=item_data.quantity,
            unit_cost=item_data.unit_cost,
            discount_rate=item_data.discount_rate,
            discount_amount=disc_amount,
            freight_prorated=item_data.freight_prorated,
            effective_unit_cost=item_data.unit_cost,
            subtotal=line_subtotal,
            sat_clave_prod_serv=item_data.sat_clave_prod_serv or product.sat_clave_prod_serv,
            sat_clave_unidad=item_data.sat_clave_unidad or product.sat_clave_unidad,
            unit_name=product.unit_name,
            vat_rate=item_data.vat_rate,
            vat_amount=vat_amount,
            ieps_rate=item_data.ieps_rate,
            ieps_amount=ieps_amount,
            total=line_total,
            source_item_id=item_data.source_item_id
        )
        items_to_create.append(doc_item)

    total_invoice = subtotal_total + tax_iva_total + tax_ieps_total + data.freight_total
    issue_dt = data.issue_date or datetime.now(timezone.utc)

    invoice = PurchaseDocument(
        tenant_id=tenant_id,
        branch_id=data.branch_id,
        warehouse_id=data.warehouse_id,
        supplier_id=data.supplier_id,
        currency_id=data.currency_id,
        document_type="FACTURA_PROVEEDOR",
        status="FACTURADA",
        serie=serie,
        folio=next_folio,
        formatted_folio=formatted_folio,
        issue_date=issue_dt,
        source_document_id=data.source_document_id,
        source_document_type="RECEPCION" if data.source_document_id else None,
        cfdi_uuid=data.cfdi_uuid,
        subtotal=subtotal_total,
        discount_total=discount_total,
        freight_total=data.freight_total,
        tax_iva_total=tax_iva_total,
        tax_ieps_total=tax_ieps_total,
        total=total_invoice,
        notes=data.notes,
        user_id=user_id,
        items=items_to_create
    )
    db.add(invoice)
    await db.flush()

    # Si proviene de una Recepción u OC previa, marcarla como FACTURADA
    if data.source_document_id:
        src_doc = await db.get(PurchaseDocument, data.source_document_id)
        if src_doc and src_doc.tenant_id == tenant_id:
            src_doc.status = "FACTURADA"

    # GENERACIÓN AUTOMÁTICA DEL PASIVO (CUENTAS POR PAGAR - CXP)
    credit_days = data.credit_days if data.credit_days is not None else supplier.credit_days
    base_date = issue_dt.date() if isinstance(issue_dt, datetime) else issue_dt
    due_date = base_date + timedelta(days=credit_days)

    payable = PayableDocument(
        tenant_id=tenant_id,
        supplier_id=supplier.id,
        branch_id=data.branch_id,
        purchase_document_id=invoice.id,
        document_type="FACTURA_PROVEEDOR",
        serie=serie,
        folio=next_folio,
        formatted_folio=formatted_folio,
        cfdi_uuid=data.cfdi_uuid,
        issue_date=issue_dt,
        due_date=due_date,
        credit_days=credit_days,
        original_total=total_invoice,
        original_subtotal=subtotal_total,
        original_vat=tax_iva_total,
        original_retention_vat=Decimal("0.0000"),
        original_retention_isr=Decimal("0.0000"),
        current_balance=total_invoice,
        currency_code="MXN",
        status="PENDIENTE"
    )
    db.add(payable)
    await db.flush()

    return invoice, payable


async def preview_xml_invoices(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    xml_contents: List[Union[str, bytes]]
) -> List[XMLInvoicePreview]:
    """
    Parsea una lista de archivos XML CFDI 4.0 y busca coincidencias con Proveedores y Artículos del sistema.
    """
    previews: List[XMLInvoicePreview] = []

    # Precargar productos y proveedores para mapeo en memoria rápido
    suppliers_res = await db.execute(select(Supplier).where(Supplier.tenant_id == tenant_id))
    suppliers_by_rfc = {s.rfc.strip().upper(): s for s in suppliers_res.scalars().all()}

    products_res = await db.execute(select(Product).where(Product.tenant_id == tenant_id))
    products = products_res.scalars().all()
    products_by_barcode = {p.barcode.strip(): p for p in products if p.barcode}
    products_by_sku = {p.sku.strip().upper(): p for p in products if p.sku}
    products_by_sat_key = {p.sat_clave_prod_serv.strip(): p for p in products if p.sat_clave_prod_serv}

    for xml_raw in xml_contents:
        parsed = parse_cfdi_40_xml(xml_raw)
        emisor_rfc = parsed["emisor_rfc"].strip().upper()

        supplier = suppliers_by_rfc.get(emisor_rfc)
        supplier_exists = supplier is not None
        supplier_id = supplier.id if supplier else None
        credit_days = supplier.credit_days if supplier else 30

        concept_previews: List[XMLConceptPreview] = []
        for c in parsed["concepts"]:
            # Intentar match con producto interno
            matched_prod: Optional[Product] = None
            no_ident = (c.get("no_identificacion") or "").strip().upper()
            clave_sat = (c.get("clave_prod_serv") or "").strip()

            if no_ident and no_ident in products_by_barcode:
                matched_prod = products_by_barcode[no_ident]
            elif no_ident and no_ident in products_by_sku:
                matched_prod = products_by_sku[no_ident]
            elif clave_sat and clave_sat in products_by_sat_key:
                matched_prod = products_by_sat_key[clave_sat]

            concept_previews.append(
                XMLConceptPreview(
                    clave_prod_serv=c["clave_prod_serv"],
                    no_identificacion=c.get("no_identificacion"),
                    cantidad=c["cantidad"],
                    clave_unidad=c["clave_unidad"],
                    unidad=c.get("unidad"),
                    descripcion=c["descripcion"],
                    valor_unitario=c["valor_unitario"],
                    importe=c["importe"],
                    descuento=c.get("descuento", Decimal("0.0000")),
                    objeto_imp=c.get("objeto_imp", "02"),
                    iva_importe=c.get("iva_importe", Decimal("0.0000")),
                    iva_tasa=c.get("iva_tasa", Decimal("0.1600")),
                    matched_product_id=matched_prod.id if matched_prod else None,
                    matched_sku=matched_prod.sku if matched_prod else None
                )
            )

        preview = XMLInvoicePreview(
            uuid=parsed["uuid"],
            serie=parsed.get("serie"),
            folio=parsed.get("folio"),
            fecha=parsed["fecha"],
            forma_pago=parsed.get("forma_pago"),
            metodo_pago=parsed.get("metodo_pago"),
            moneda=parsed.get("moneda", "MXN"),
            tipo_cambio=parsed.get("tipo_cambio", Decimal("1.0000")),
            subtotal=parsed["subtotal"],
            descuento=parsed["descuento"],
            total_iva=parsed["total_iva"],
            total_retenciones=parsed["total_retenciones"],
            total=parsed["total"],
            emisor_rfc=parsed["emisor_rfc"],
            emisor_nombre=parsed["emisor_nombre"],
            emisor_regimen=parsed.get("emisor_regimen"),
            receptor_rfc=parsed["receptor_rfc"],
            supplier_exists=supplier_exists,
            supplier_id=supplier_id,
            supplier_credit_days=credit_days,
            concepts=concept_previews
        )
        previews.append(preview)

    return previews


async def confirm_xml_invoices_import(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: ConfirmXMLImportRequest,
    user_id: Optional[uuid.UUID] = None
) -> List[Tuple[PurchaseDocument, PayableDocument]]:
    """
    Confirma la importación masiva de facturas XML del SAT:
    1. Si el proveedor no existe, lo crea automáticamente.
    2. Si los conceptos no están asociados a un producto, busca o crea un artículo genérico de compras.
    3. Registra la Factura de Proveedor ('FACTURA_PROVEEDOR').
    4. Genera el pasivo en Cuentas por Pagar ('PayableDocument').
    """
    results: List[Tuple[PurchaseDocument, PayableDocument]] = []

    # Obtener o crear artículo comodín para gastos/conceptos no mapeados
    generic_prod_res = await db.execute(
        select(Product).where(Product.tenant_id == tenant_id, Product.sku == "COMPRA-GEN")
    )
    generic_prod = generic_prod_res.scalar_one_or_none()
    if not generic_prod:
        generic_prod = Product(
            tenant_id=tenant_id,
            sku="COMPRA-GEN",
            name="Gastos y Compras Generales SAT",
            product_type="PRODUCTO",
            costing_method="PROMEDIO",
            sat_clave_prod_serv="01010101",
            sat_clave_unidad="H87",
            unit_name="PZA",
            vat_rate=Decimal("0.1600")
        )
        db.add(generic_prod)
        await db.flush()

    for inv in data.invoices:
        # 1. Asegurar proveedor
        supplier_id = inv.supplier_id
        if not supplier_id:
            supp_res = await db.execute(
                select(Supplier).where(Supplier.tenant_id == tenant_id, Supplier.rfc == inv.emisor_rfc.strip().upper())
            )
            existing_supp = supp_res.scalar_one_or_none()
            if existing_supp:
                supplier_id = existing_supp.id
            else:
                supp_code = f"PRV-{inv.emisor_rfc[:4]}-{uuid.uuid4().hex[:4].upper()}"
                new_supp = Supplier(
                    tenant_id=tenant_id,
                    code=supp_code,
                    rfc=inv.emisor_rfc.strip().upper(),
                    legal_name=inv.emisor_nombre.strip() or "PROVEEDOR IMPORTADO XML",
                    zip_code="06000",
                    fiscal_regime_code=inv.emisor_regimen or "601",
                    credit_days=inv.supplier_credit_days or 30,
                    is_active=True
                )
                db.add(new_supp)
                await db.flush()
                supplier_id = new_supp.id

        # 2. Convertir conceptos a items
        items: List[PurchaseDocumentItem] = []
        for idx, c in enumerate(inv.concepts, start=1):
            product_id = c.matched_product_id or generic_prod.id
            items.append(
                PurchaseDocumentItem(
                    tenant_id=tenant_id,
                    product_id=product_id,
                    line_number=idx,
                    sku=c.matched_sku or generic_prod.sku,
                    description=c.descripcion[:250],
                    quantity_ordered=c.cantidad,
                    quantity_received=c.cantidad,
                    unit_cost=c.valor_unitario,
                    discount_rate=Decimal("0.0000"),
                    discount_amount=c.descuento,
                    freight_prorated=Decimal("0.0000"),
                    effective_unit_cost=c.valor_unitario,
                    subtotal=c.importe - c.descuento,
                    sat_clave_prod_serv=c.clave_prod_serv,
                    sat_clave_unidad=c.clave_unidad,
                    unit_name=c.unidad or "PZA",
                    vat_rate=c.iva_tasa,
                    vat_amount=c.iva_importe,
                    total=c.importe - c.descuento + c.iva_importe
                )
            )

        serie = inv.serie or "XML"
        folio = int(inv.folio) if inv.folio and inv.folio.isdigit() else 1
        formatted_folio = f"{serie}-{folio}"

        # Parsear fecha
        try:
            issue_date = datetime.fromisoformat(inv.fecha.replace("Z", "+00:00"))
        except Exception:
            issue_date = datetime.now(timezone.utc)

        purchase_doc = PurchaseDocument(
            tenant_id=tenant_id,
            branch_id=data.branch_id,
            warehouse_id=data.warehouse_id,
            supplier_id=supplier_id,
            currency_id=data.currency_id,
            document_type="FACTURA_PROVEEDOR",
            status="FACTURADA",
            serie=serie,
            folio=folio,
            formatted_folio=formatted_folio,
            issue_date=issue_date,
            cfdi_uuid=inv.uuid,
            subtotal=inv.subtotal,
            discount_total=inv.descuento,
            freight_total=Decimal("0.0000"),
            tax_iva_total=inv.total_iva,
            tax_ieps_total=Decimal("0.0000"),
            retention_iva_total=inv.total_retenciones,
            total=inv.total,
            notes=f"Importado automáticamente de XML CFDI 4.0. UUID: {inv.uuid}",
            user_id=user_id,
            items=items
        )
        db.add(purchase_doc)
        await db.flush()

        due_date = issue_date.date() + timedelta(days=inv.supplier_credit_days or 30)

        payable = PayableDocument(
            tenant_id=tenant_id,
            supplier_id=supplier_id,
            branch_id=data.branch_id,
            purchase_document_id=purchase_doc.id,
            document_type="FACTURA_PROVEEDOR",
            serie=serie,
            folio=folio,
            formatted_folio=formatted_folio,
            cfdi_uuid=inv.uuid,
            issue_date=issue_date,
            due_date=due_date,
            credit_days=inv.supplier_credit_days or 30,
            original_total=inv.total,
            original_subtotal=inv.subtotal,
            original_vat=inv.total_iva,
            original_retention_vat=inv.total_retenciones,
            original_retention_isr=Decimal("0.0000"),
            current_balance=inv.total,
            currency_code=inv.moneda or "MXN",
            status="PENDIENTE"
        )
        db.add(payable)
        await db.flush()

        results.append((purchase_doc, payable))

    return results


async def get_dashboard_metrics(
    db: AsyncSession,
    tenant_id: uuid.UUID
) -> PurchasesDashboardMetrics:
    """Calcula las métricas de compras y cuentas por pagar para el Dashboard."""
    now = datetime.now(timezone.utc)
    first_day_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    # 1. Total compras del mes (Facturas y recepciones recibidas/facturadas)
    monthly_stmt = select(func.coalesce(func.sum(PurchaseDocument.total), 0)).where(
        PurchaseDocument.tenant_id == tenant_id,
        PurchaseDocument.document_type.in_(("RECEPCION", "FACTURA_PROVEEDOR")),
        PurchaseDocument.status.in_(("RECIBIDA", "FACTURADA")),
        PurchaseDocument.issue_date >= first_day_month
    )
    monthly_total = (await db.execute(monthly_stmt)).scalar_one()

    # 2. Órdenes de compra pendientes
    pending_oc_stmt = select(func.count(PurchaseDocument.id)).where(
        PurchaseDocument.tenant_id == tenant_id,
        PurchaseDocument.document_type == "ORDEN_COMPRA",
        PurchaseDocument.status.in_(("BORRADOR", "AUTORIZADA", "PARCIALMENTE_RECIBIDA"))
    )
    pending_oc_count = (await db.execute(pending_oc_stmt)).scalar_one()

    # 3. Saldo pendiente de pago en CxP
    cxp_stmt = select(func.coalesce(func.sum(PayableDocument.current_balance), 0)).where(
        PayableDocument.tenant_id == tenant_id,
        PayableDocument.status.in_(("PENDIENTE", "PARCIAL"))
    )
    unpaid_balance = (await db.execute(cxp_stmt)).scalar_one()

    # 4. Proveedores activos
    suppliers_count_stmt = select(func.count(Supplier.id)).where(
        Supplier.tenant_id == tenant_id,
        Supplier.is_active.is_(True)
    )
    active_suppliers = (await db.execute(suppliers_count_stmt)).scalar_one()

    # 5. Top proveedores
    top_stmt = (
        select(
            Supplier.id,
            Supplier.legal_name,
            Supplier.rfc,
            func.coalesce(func.sum(PurchaseDocument.total), 0).label("total_purchased"),
            func.count(PurchaseDocument.id).label("orders_count")
        )
        .join(PurchaseDocument, PurchaseDocument.supplier_id == Supplier.id)
        .where(
            PurchaseDocument.tenant_id == tenant_id,
            PurchaseDocument.status.in_(("RECIBIDA", "FACTURADA"))
        )
        .group_by(Supplier.id, Supplier.legal_name, Supplier.rfc)
        .order_by(desc("total_purchased"))
        .limit(5)
    )
    top_res = (await db.execute(top_stmt)).all()
    top_suppliers = [
        TopSupplierMetric(
            supplier_id=r[0],
            legal_name=r[1],
            rfc=r[2],
            total_purchased=Decimal(str(r[3])),
            orders_count=r[4]
        )
        for r in top_res
    ]

    return PurchasesDashboardMetrics(
        monthly_purchases_total=Decimal(str(monthly_total)),
        pending_purchase_orders_count=pending_oc_count,
        unpaid_invoices_balance=Decimal(str(unpaid_balance)),
        active_suppliers_count=active_suppliers,
        top_suppliers=top_suppliers
    )
