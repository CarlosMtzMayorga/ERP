import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.tenant_context import get_current_tenant_id
from app.core.dependencies import get_current_user, require_permission
from app.modules.auth.models import User
from app.modules.purchases.models import PurchaseDocument, PayableDocument
from app.modules.purchases.schemas import (
    PurchaseOrderCreate,
    GoodsReceptionCreate,
    SupplierInvoiceCreate,
    PurchaseDocumentResponse,
    PurchaseDocumentItemResponse,
    PayableDocumentResponse,
    PurchasesDashboardMetrics,
    XMLInvoicePreview,
    ConfirmXMLImportRequest,
)
from app.modules.purchases import purchases_service

router = APIRouter(prefix="/purchases", tags=["Compras y Abastecimiento"])


@router.get("/dashboard", response_model=PurchasesDashboardMetrics)
async def get_purchases_dashboard(
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("purchases:read"))
):
    """Retorna las métricas ejecutivas de compras, órdenes pendientes y saldo adeudado a proveedores."""
    return await purchases_service.get_dashboard_metrics(db, tenant_id)


@router.get("/documents", response_model=List[PurchaseDocumentResponse])
async def list_purchase_documents(
    document_type: Optional[str] = Query(None, description="REQUISICION, ORDEN_COMPRA, RECEPCION, FACTURA_PROVEEDOR"),
    status_filter: Optional[str] = Query(None, alias="status"),
    supplier_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("purchases:read"))
):
    """Lista documentos de compras con filtros por tipo, estado o proveedor."""
    query = (
        select(PurchaseDocument)
        .options(selectinload(PurchaseDocument.items), selectinload(PurchaseDocument.supplier))
        .where(PurchaseDocument.tenant_id == tenant_id)
    )
    if document_type:
        query = query.where(PurchaseDocument.document_type == document_type.upper())
    if status_filter:
        query = query.where(PurchaseDocument.status == status_filter.upper())
    if supplier_id:
        query = query.where(PurchaseDocument.supplier_id == supplier_id)

    query = query.order_by(desc(PurchaseDocument.issue_date), desc(PurchaseDocument.folio)).limit(limit)
    result = await db.execute(query)
    docs = result.scalars().all()

    output = []
    for d in docs:
        resp = PurchaseDocumentResponse.model_validate(d)
        if d.supplier:
            resp.supplier_name = d.supplier.legal_name
            resp.supplier_rfc = d.supplier.rfc
        output.append(resp)
    return output


@router.get("/documents/{document_id}", response_model=PurchaseDocumentResponse)
async def get_purchase_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("purchases:read"))
):
    """Obtiene el detalle completo de un documento de compra y sus partidas."""
    stmt = (
        select(PurchaseDocument)
        .options(selectinload(PurchaseDocument.items), selectinload(PurchaseDocument.supplier))
        .where(PurchaseDocument.id == document_id, PurchaseDocument.tenant_id == tenant_id)
    )
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento de compra no encontrado.")

    resp = PurchaseDocumentResponse.model_validate(doc)
    if doc.supplier:
        resp.supplier_name = doc.supplier.legal_name
        resp.supplier_rfc = doc.supplier.rfc
    return resp


@router.post("/orders", response_model=PurchaseDocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    payload: PurchaseOrderCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("purchases:create"))
):
    """Genera una Orden de Compra (OC) en estado BORRADOR con prorrateo preliminar de fletes."""
    order = await purchases_service.create_purchase_order(db, tenant_id, payload, user_id=current_user.id)
    await db.commit()
    await db.refresh(order)
    return PurchaseDocumentResponse.model_validate(order)


@router.put("/orders/{order_id}/authorize", response_model=PurchaseDocumentResponse)
async def authorize_purchase_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("purchases:create"))
):
    """Autoriza una Orden de Compra para habilitar su recepción física en almacén."""
    po = await purchases_service.authorize_purchase_order(db, tenant_id, order_id, user_id=current_user.id)
    await db.commit()
    await db.refresh(po)
    return PurchaseDocumentResponse.model_validate(po)


@router.post("/receptions", response_model=PurchaseDocumentResponse, status_code=status.HTTP_201_CREATED)
async def receive_merchandise(
    payload: GoodsReceptionCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("purchases:create"))
):
    """
    Registra la recepción física de mercancía en almacén.
    Afecta el Kardex inmutable con 'ENTRADA_COMPRA', recalcula costo promedio,
    crea capa PEPS (FIFO), prorratea fletes y actualiza backorders en la OC.
    """
    reception = await purchases_service.receive_merchandise(db, tenant_id, payload, user_id=current_user.id)
    await db.commit()
    await db.refresh(reception)
    return PurchaseDocumentResponse.model_validate(reception)


@router.post("/invoices", response_model=PurchaseDocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier_invoice(
    payload: SupplierInvoiceCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("purchases:create"))
):
    """
    Registra una Factura de Proveedor y genera automáticamente el pasivo en Cuentas por Pagar (CxP).
    """
    invoice, payable = await purchases_service.create_supplier_invoice(db, tenant_id, payload, user_id=current_user.id)
    await db.commit()
    await db.refresh(invoice)
    return PurchaseDocumentResponse.model_validate(invoice)


@router.post("/xml/preview", response_model=List[XMLInvoicePreview])
async def preview_xml_files(
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("purchases:xml_import"))
):
    """
    Parsea archivos XML CFDI 4.0 de proveedores y retorna la pre-visualización con
    validación de RFC emisor y mapeo preliminar de productos internos.
    """
    xml_contents: List[bytes] = []
    for f in files:
        content = await f.read()
        xml_contents.append(content)

    return await purchases_service.preview_xml_invoices(db, tenant_id, xml_contents)


@router.post("/xml/confirm", status_code=status.HTTP_201_CREATED)
async def confirm_xml_import(
    payload: ConfirmXMLImportRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("purchases:xml_import"))
):
    """
    Confirma la importación masiva de facturas XML, persistiendo las facturas de proveedor
    y generando atómicamente los pasivos en Cuentas por Pagar (CxP).
    """
    created_pairs = await purchases_service.confirm_xml_invoices_import(db, tenant_id, payload, user_id=current_user.id)
    await db.commit()
    return {
        "success": True,
        "imported_invoices_count": len(created_pairs),
        "message": f"Se importaron con éxito {len(created_pairs)} facturas de proveedor y sus pasivos en CxP."
    }


@router.get("/payables", response_model=List[PayableDocumentResponse])
async def list_accounts_payable(
    status_filter: Optional[str] = Query(None, alias="status"),
    supplier_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("purchases:read"))
):
    """Lista los pasivos vigentes con proveedores (Cuentas por Pagar - CxP)."""
    query = (
        select(PayableDocument)
        .options(selectinload(PayableDocument.supplier))
        .where(PayableDocument.tenant_id == tenant_id)
    )
    if status_filter:
        query = query.where(PayableDocument.status == status_filter.upper())
    if supplier_id:
        query = query.where(PayableDocument.supplier_id == supplier_id)

    query = query.order_by(PayableDocument.due_date, desc(PayableDocument.created_at)).limit(limit)
    res = await db.execute(query)
    payables = res.scalars().all()

    output = []
    for p in payables:
        resp = PayableDocumentResponse.model_validate(p)
        if p.supplier:
            resp.supplier_name = p.supplier.legal_name
            resp.supplier_rfc = p.supplier.rfc
        output.append(resp)
    return output
