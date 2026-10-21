import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_tenant, require_permission
from app.modules.auth.models import User
from app.modules.tenants.models import Tenant
from app.modules.sales.models import SalesDocument, SalesDocumentItem
from app.modules.master_data.models import Customer, Product, Currency
from app.modules.sales.sales_service import (
    create_sales_document,
    convert_order_to_invoice,
    stamp_invoice_cfdi
)

router = APIRouter(prefix="/sales", tags=["Módulo 3: Ventas y Facturación CFDI 4.0"])


# --- Schemas ---
class SalesItemInput(BaseModel):
    product_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)
    discount_rate: Decimal = Field(Decimal("0.0000"), ge=0, le=1)
    vat_rate: Optional[Decimal] = None
    ieps_rate: Optional[Decimal] = None
    retention_vat_rate: Optional[Decimal] = None
    retention_isr_rate: Optional[Decimal] = None
    description: Optional[str] = None


class SalesDocumentCreateRequest(BaseModel):
    branch_id: uuid.UUID
    warehouse_id: uuid.UUID
    customer_id: uuid.UUID
    currency_id: uuid.UUID
    document_type: str = Field(..., description="COTIZACION, PEDIDO, REMISION, FACTURA")
    items: List[SalesItemInput]
    payment_form: str = "03"
    payment_method: str = "PUE"
    cfdi_use: str = "G03"
    price_list_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    approve_immediately: bool = True


class SalesItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    sku: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    subtotal: Decimal
    vat_amount: Decimal
    ieps_amount: Decimal
    retention_vat_amount: Decimal
    retention_isr_amount: Decimal
    total: Decimal
    unit_cost: Decimal

    class Config:
        from_attributes = True


class SalesDocumentResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime
    document_type: str
    status: str
    serie: str
    folio: int
    formatted_folio: str
    customer_id: uuid.UUID
    customer_name: Optional[str] = None
    customer_rfc: Optional[str] = None
    subtotal: Decimal
    discount_total: Decimal
    tax_iva_total: Decimal
    tax_ieps_total: Decimal
    retention_iva_total: Decimal
    retention_isr_total: Decimal
    total: Decimal
    total_cost_cogs: Decimal
    cfdi_uuid: Optional[str] = None
    cfdi_stamped_at: Optional[datetime] = None
    source_document_id: Optional[uuid.UUID] = None
    items: List[SalesItemResponse] = []

    class Config:
        from_attributes = True


class SalesDashboardResponse(BaseModel):
    monthly_sales_total: Decimal
    stamped_invoices_count: int
    pending_orders_count: int
    average_ticket: Decimal
    top_products: List[Dict[str, Any]] = []


# --- Endpoints ---
@router.get("/dashboard", response_model=SalesDashboardResponse, summary="Dashboard comercial y de facturación")
async def get_sales_dashboard(
    tenant: Tenant = Depends(get_current_tenant),
    _has_perm: bool = Depends(require_permission("sales:read")),
    db: AsyncSession = Depends(get_db)
):
    # Total ventas del mes (facturas y remisiones activas)
    today = datetime.now(timezone.utc)
    month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    sales_agg = await db.execute(
        select(
            func.coalesce(func.sum(SalesDocument.total), Decimal("0.0000")),
            func.coalesce(func.avg(SalesDocument.total), Decimal("0.0000"))
        ).where(
            SalesDocument.tenant_id == tenant.id,
            SalesDocument.document_type.in_(("FACTURA", "REMISION")),
            SalesDocument.status.in_(("PENDIENTE", "TIMBRADO", "SURTIDO")),
            SalesDocument.created_at >= month_start
        )
    )
    month_total, avg_ticket = sales_agg.one()

    # Facturas timbradas
    stamped_res = await db.execute(
        select(func.count(SalesDocument.id)).where(
            SalesDocument.tenant_id == tenant.id,
            SalesDocument.document_type == "FACTURA",
            SalesDocument.status == "TIMBRADO"
        )
    )
    stamped_count = stamped_res.scalar() or 0

    # Pedidos pendientes de surtir
    pending_orders_res = await db.execute(
        select(func.count(SalesDocument.id)).where(
            SalesDocument.tenant_id == tenant.id,
            SalesDocument.document_type == "PEDIDO",
            SalesDocument.status.in_(("APROBADO", "PENDIENTE", "PARCIALMENTE_SURTIDO"))
        )
    )
    pending_orders_count = pending_orders_res.scalar() or 0

    # Top 5 productos más vendidos
    top_query = (
        select(
            SalesDocumentItem.sku,
            SalesDocumentItem.description,
            func.sum(SalesDocumentItem.quantity).label("units_sold"),
            func.sum(SalesDocumentItem.total).label("revenue")
        )
        .join(SalesDocument, SalesDocument.id == SalesDocumentItem.sales_document_id)
        .where(
            SalesDocument.tenant_id == tenant.id,
            SalesDocument.status.in_(("TIMBRADO", "SURTIDO", "PENDIENTE"))
        )
        .group_by(SalesDocumentItem.sku, SalesDocumentItem.description)
        .order_by(func.sum(SalesDocumentItem.total).desc())
        .limit(5)
    )
    top_res = await db.execute(top_query)
    top_products = [
        {
            "sku": row.sku,
            "description": row.description,
            "units_sold": float(row.units_sold),
            "revenue": float(row.revenue)
        }
        for row in top_res.all()
    ]

    return SalesDashboardResponse(
        monthly_sales_total=month_total,
        stamped_invoices_count=stamped_count,
        pending_orders_count=pending_orders_count,
        average_ticket=avg_ticket,
        top_products=top_products
    )


@router.get("/documents", response_model=List[SalesDocumentResponse], summary="Listar documentos de ventas (Cotizaciones, Pedidos, Facturas)")
async def list_sales_documents(
    document_type: Optional[str] = Query(None, description="COTIZACION, PEDIDO, REMISION, FACTURA"),
    status: Optional[str] = Query(None),
    customer_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    tenant: Tenant = Depends(get_current_tenant),
    _has_perm: bool = Depends(require_permission("sales:read")),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(SalesDocument)
        .options(
            selectinload(SalesDocument.customer),
            selectinload(SalesDocument.items)
        )
        .where(SalesDocument.tenant_id == tenant.id)
    )

    if document_type:
        query = query.where(SalesDocument.document_type == document_type.upper())
    if status:
        query = query.where(SalesDocument.status == status.upper())
    if customer_id:
        query = query.where(SalesDocument.customer_id == customer_id)

    query = query.order_by(SalesDocument.created_at.desc()).limit(limit).offset(offset)
    res = await db.execute(query)
    docs = res.scalars().all()

    output = []
    for d in docs:
        resp = SalesDocumentResponse(
            id=d.id,
            created_at=d.created_at,
            document_type=d.document_type,
            status=d.status,
            serie=d.serie,
            folio=d.folio,
            formatted_folio=d.formatted_folio,
            customer_id=d.customer_id,
            customer_name=d.customer.legal_name if d.customer else "Cliente Mostrador",
            customer_rfc=d.customer.rfc if d.customer else "XAXX010101000",
            subtotal=d.subtotal,
            discount_total=d.discount_total,
            tax_iva_total=d.tax_iva_total,
            tax_ieps_total=d.tax_ieps_total,
            retention_iva_total=d.retention_iva_total,
            retention_isr_total=d.retention_isr_total,
            total=d.total,
            total_cost_cogs=d.total_cost_cogs,
            cfdi_uuid=d.cfdi_uuid,
            cfdi_stamped_at=d.cfdi_stamped_at,
            source_document_id=d.source_document_id,
            items=[SalesItemResponse.model_validate(it) for it in d.items]
        )
        output.append(resp)
    return output


@router.get("/documents/{document_id}", response_model=SalesDocumentResponse, summary="Detalle completo de un documento de venta")
async def get_sales_document_detail(
    document_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    _has_perm: bool = Depends(require_permission("sales:read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(SalesDocument)
        .options(
            selectinload(SalesDocument.customer),
            selectinload(SalesDocument.items)
        )
        .where(SalesDocument.id == document_id, SalesDocument.tenant_id == tenant.id)
    )
    res = await db.execute(stmt)
    d = res.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento de venta no encontrado.")

    return SalesDocumentResponse(
        id=d.id,
        created_at=d.created_at,
        document_type=d.document_type,
        status=d.status,
        serie=d.serie,
        folio=d.folio,
        formatted_folio=d.formatted_folio,
        customer_id=d.customer_id,
        customer_name=d.customer.legal_name if d.customer else "N/A",
        customer_rfc=d.customer.rfc if d.customer else "N/A",
        subtotal=d.subtotal,
        discount_total=d.discount_total,
        tax_iva_total=d.tax_iva_total,
        tax_ieps_total=d.tax_ieps_total,
        retention_iva_total=d.retention_iva_total,
        retention_isr_total=d.retention_isr_total,
        total=d.total,
        total_cost_cogs=d.total_cost_cogs,
        cfdi_uuid=d.cfdi_uuid,
        cfdi_stamped_at=d.cfdi_stamped_at,
        source_document_id=d.source_document_id,
        items=[SalesItemResponse.model_validate(it) for it in d.items]
    )


@router.post("/documents", response_model=SalesDocumentResponse, status_code=status.HTTP_201_CREATED, summary="Crear documento comercial (Cotización, Pedido, Factura)")
async def api_create_sales_document(
    payload: SalesDocumentCreateRequest,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("sales:create")),
    db: AsyncSession = Depends(get_db)
):
    items_raw = [it.model_dump() for it in payload.items]

    doc = await create_sales_document(
        db=db,
        tenant_id=tenant.id,
        branch_id=payload.branch_id,
        warehouse_id=payload.warehouse_id,
        customer_id=payload.customer_id,
        currency_id=payload.currency_id,
        document_type=payload.document_type,
        items_input=items_raw,
        payment_form=payload.payment_form,
        payment_method=payload.payment_method,
        cfdi_use=payload.cfdi_use,
        price_list_id=payload.price_list_id,
        notes=payload.notes,
        user_id=user.id,
        approve_immediately=payload.approve_immediately
    )
    await db.commit()
    await db.refresh(doc)

    # Re-cargar con relaciones
    stmt = select(SalesDocument).options(
        selectinload(SalesDocument.customer),
        selectinload(SalesDocument.items)
    ).where(SalesDocument.id == doc.id)
    doc_loaded = (await db.execute(stmt)).scalar_one()

    return SalesDocumentResponse(
        id=doc_loaded.id,
        created_at=doc_loaded.created_at,
        document_type=doc_loaded.document_type,
        status=doc_loaded.status,
        serie=doc_loaded.serie,
        folio=doc_loaded.folio,
        formatted_folio=doc_loaded.formatted_folio,
        customer_id=doc_loaded.customer_id,
        customer_name=doc_loaded.customer.legal_name if doc_loaded.customer else "N/A",
        customer_rfc=doc_loaded.customer.rfc if doc_loaded.customer else "N/A",
        subtotal=doc_loaded.subtotal,
        discount_total=doc_loaded.discount_total,
        tax_iva_total=doc_loaded.tax_iva_total,
        tax_ieps_total=doc_loaded.tax_ieps_total,
        retention_iva_total=doc_loaded.retention_iva_total,
        retention_isr_total=doc_loaded.retention_isr_total,
        total=doc_loaded.total,
        total_cost_cogs=doc_loaded.total_cost_cogs,
        cfdi_uuid=doc_loaded.cfdi_uuid,
        cfdi_stamped_at=doc_loaded.cfdi_stamped_at,
        items=[SalesItemResponse.model_validate(it) for it in doc_loaded.items]
    )


@router.post("/documents/{order_id}/convert-to-invoice", response_model=SalesDocumentResponse, summary="Convertir Pedido a Factura (Descarga inventario y consume reservas)")
async def api_convert_order_to_invoice(
    order_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("sales:invoice")),
    db: AsyncSession = Depends(get_db)
):
    invoice = await convert_order_to_invoice(
        db=db,
        tenant_id=tenant.id,
        order_id=order_id,
        user_id=user.id
    )
    await db.commit()
    await db.refresh(invoice)

    stmt = select(SalesDocument).options(
        selectinload(SalesDocument.customer),
        selectinload(SalesDocument.items)
    ).where(SalesDocument.id == invoice.id)
    inv_loaded = (await db.execute(stmt)).scalar_one()

    return SalesDocumentResponse(
        id=inv_loaded.id,
        created_at=inv_loaded.created_at,
        document_type=inv_loaded.document_type,
        status=inv_loaded.status,
        serie=inv_loaded.serie,
        folio=inv_loaded.folio,
        formatted_folio=inv_loaded.formatted_folio,
        customer_id=inv_loaded.customer_id,
        customer_name=inv_loaded.customer.legal_name if inv_loaded.customer else "N/A",
        customer_rfc=inv_loaded.customer.rfc if inv_loaded.customer else "N/A",
        subtotal=inv_loaded.subtotal,
        discount_total=inv_loaded.discount_total,
        tax_iva_total=inv_loaded.tax_iva_total,
        tax_ieps_total=inv_loaded.tax_ieps_total,
        retention_iva_total=inv_loaded.retention_iva_total,
        retention_isr_total=inv_loaded.retention_isr_total,
        total=inv_loaded.total,
        total_cost_cogs=inv_loaded.total_cost_cogs,
        cfdi_uuid=inv_loaded.cfdi_uuid,
        cfdi_stamped_at=inv_loaded.cfdi_stamped_at,
        source_document_id=inv_loaded.source_document_id,
        items=[SalesItemResponse.model_validate(it) for it in inv_loaded.items]
    )


@router.post("/documents/{invoice_id}/stamp", response_model=SalesDocumentResponse, summary="Timbrar CFDI 4.0 con sello CSD y PAC")
async def api_stamp_invoice(
    invoice_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    _has_perm: bool = Depends(require_permission("sales:invoice")),
    db: AsyncSession = Depends(get_db)
):
    invoice = await stamp_invoice_cfdi(
        db=db,
        tenant_id=tenant.id,
        invoice_id=invoice_id
    )
    await db.commit()
    await db.refresh(invoice)

    stmt = select(SalesDocument).options(
        selectinload(SalesDocument.customer),
        selectinload(SalesDocument.items)
    ).where(SalesDocument.id == invoice.id)
    inv_loaded = (await db.execute(stmt)).scalar_one()

    return SalesDocumentResponse(
        id=inv_loaded.id,
        created_at=inv_loaded.created_at,
        document_type=inv_loaded.document_type,
        status=inv_loaded.status,
        serie=inv_loaded.serie,
        folio=inv_loaded.folio,
        formatted_folio=inv_loaded.formatted_folio,
        customer_id=inv_loaded.customer_id,
        customer_name=inv_loaded.customer.legal_name if inv_loaded.customer else "N/A",
        customer_rfc=inv_loaded.customer.rfc if inv_loaded.customer else "N/A",
        subtotal=inv_loaded.subtotal,
        discount_total=inv_loaded.discount_total,
        tax_iva_total=inv_loaded.tax_iva_total,
        tax_ieps_total=inv_loaded.tax_ieps_total,
        retention_iva_total=inv_loaded.retention_iva_total,
        retention_isr_total=inv_loaded.retention_isr_total,
        total=inv_loaded.total,
        total_cost_cogs=inv_loaded.total_cost_cogs,
        cfdi_uuid=inv_loaded.cfdi_uuid,
        cfdi_stamped_at=inv_loaded.cfdi_stamped_at,
        source_document_id=inv_loaded.source_document_id,
        items=[SalesItemResponse.model_validate(it) for it in inv_loaded.items]
    )


@router.get("/documents/{invoice_id}/xml", summary="Descargar archivo XML timbrado del CFDI")
async def download_cfdi_xml(
    invoice_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    _has_perm: bool = Depends(require_permission("sales:read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(SalesDocument).where(SalesDocument.id == invoice_id, SalesDocument.tenant_id == tenant.id)
    res = await db.execute(stmt)
    inv = res.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factura no encontrada.")
    if not inv.cfdi_xml:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El documento no cuenta con XML timbrado.")

    filename = f"{inv.formatted_folio}_{inv.cfdi_uuid or 'precfdi'}.xml"
    return Response(
        content=inv.cfdi_xml,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

