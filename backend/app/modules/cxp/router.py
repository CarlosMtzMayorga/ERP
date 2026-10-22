import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.tenant_context import get_current_tenant_id
from app.core.dependencies import get_current_user, require_permission
from app.modules.auth.models import User
from app.modules.cxp.models import SupplierPayment, SupplierPaymentDocRel
from app.modules.cxp.schemas import (
    ApplySupplierPaymentRequest,
    SupplierPaymentResponse,
    SupplierPaymentDocRelResponse,
    PaymentScheduleSummary,
    CxPDashboardMetrics,
)
from app.modules.cxp import cxp_service

router = APIRouter(prefix="/cxp", tags=["Cuentas por Pagar (CxP)"])


@router.get("/dashboard", response_model=CxPDashboardMetrics)
async def get_cxp_dashboard(
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("cxp:read"))
):
    """Retorna las métricas ejecutivas de cuentas por pagar, calendario y montos adeudados."""
    return await cxp_service.get_cxp_dashboard_metrics(db, tenant_id)


@router.get("/schedule", response_model=PaymentScheduleSummary)
async def get_payment_schedule(
    supplier_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("cxp:read"))
):
    """Consulta el calendario cronológico de vencimientos de facturas de compra por pagar."""
    return await cxp_service.get_payment_schedule(db, tenant_id, supplier_id=supplier_id)


@router.post("/payments", response_model=SupplierPaymentResponse, status_code=status.HTTP_201_CREATED)
async def apply_payment_to_supplier(
    payload: ApplySupplierPaymentRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("cxp:schedule_payment"))
):
    """
    Aplica un pago a un proveedor, liquidando una o varias facturas de compra.
    Afecta atómicamente la cuenta bancaria con control de sobregiro y calcula retenciones proporcionales.
    """
    payment, _ = await cxp_service.apply_supplier_payment(db, tenant_id, payload, user_id=current_user.id)
    await db.commit()
    await db.refresh(payment)

    # Recargar con relaciones
    stmt = (
        select(SupplierPayment)
        .options(
            selectinload(SupplierPayment.supplier),
            selectinload(SupplierPayment.bank_account),
            selectinload(SupplierPayment.related_docs)
        )
        .where(SupplierPayment.id == payment.id)
    )
    p_loaded = (await db.execute(stmt)).scalar_one()

    rels = [
        SupplierPaymentDocRelResponse(
            payable_document_id=r.payable_document_id,
            installment_number=r.installment_number,
            previous_balance=r.previous_balance,
            amount_paid=r.amount_paid,
            remaining_balance=r.remaining_balance,
            proportional_subtotal=r.proportional_subtotal,
            proportional_vat=r.proportional_vat,
            proportional_retention_vat=r.proportional_retention_vat,
            proportional_retention_isr=r.proportional_retention_isr
        )
        for r in p_loaded.related_docs
    ]

    return SupplierPaymentResponse(
        id=p_loaded.id,
        formatted_folio=p_loaded.formatted_folio,
        supplier_id=p_loaded.supplier_id,
        supplier_name=p_loaded.supplier.legal_name if p_loaded.supplier else None,
        supplier_rfc=p_loaded.supplier.rfc if p_loaded.supplier else None,
        bank_account_id=p_loaded.bank_account_id,
        bank_name=p_loaded.bank_account.bank_name if p_loaded.bank_account else None,
        account_number=p_loaded.bank_account.account_number if p_loaded.bank_account else None,
        payment_date=p_loaded.payment_date,
        payment_method=p_loaded.payment_method,
        amount=p_loaded.amount,
        operation_number=p_loaded.operation_number,
        status=p_loaded.status,
        notes=p_loaded.notes,
        related_docs=rels
    )


@router.get("/payments", response_model=List[SupplierPaymentResponse])
async def list_supplier_payments(
    supplier_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("cxp:read"))
):
    """Consulta el historial de pagos y transferencias emitidos a proveedores."""
    query = (
        select(SupplierPayment)
        .options(
            selectinload(SupplierPayment.supplier),
            selectinload(SupplierPayment.bank_account),
            selectinload(SupplierPayment.related_docs)
        )
        .where(SupplierPayment.tenant_id == tenant_id)
    )
    if supplier_id:
        query = query.where(SupplierPayment.supplier_id == supplier_id)

    query = query.order_by(desc(SupplierPayment.payment_date)).limit(limit)
    res = await db.execute(query)
    payments = res.scalars().all()

    output = []
    for p in payments:
        rels = [
            SupplierPaymentDocRelResponse(
                payable_document_id=r.payable_document_id,
                installment_number=r.installment_number,
                previous_balance=r.previous_balance,
                amount_paid=r.amount_paid,
                remaining_balance=r.remaining_balance,
                proportional_subtotal=r.proportional_subtotal,
                proportional_vat=r.proportional_vat,
                proportional_retention_vat=r.proportional_retention_vat,
                proportional_retention_isr=r.proportional_retention_isr
            )
            for r in p.related_docs
        ]
        output.append(
            SupplierPaymentResponse(
                id=p.id,
                formatted_folio=p.formatted_folio,
                supplier_id=p.supplier_id,
                supplier_name=p.supplier.legal_name if p.supplier else None,
                supplier_rfc=p.supplier.rfc if p.supplier else None,
                bank_account_id=p.bank_account_id,
                bank_name=p.bank_account.bank_name if p.bank_account else None,
                account_number=p.bank_account.account_number if p.bank_account else None,
                payment_date=p.payment_date,
                payment_method=p.payment_method,
                amount=p.amount,
                operation_number=p.operation_number,
                status=p.status,
                notes=p.notes,
                related_docs=rels
            )
        )
    return output
