import uuid
from decimal import Decimal
from datetime import datetime, timezone, date
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_tenant
from app.modules.auth.models import User
from app.modules.tenants.models import Tenant
from app.modules.master_data.models import Customer
from app.modules.cxc.models import ReceivableDocument, PaymentReceipt, PaymentReceiptDocRel
from app.modules.cxc.cxc_service import (
    get_customer_aging_analysis,
    apply_payment_receipt,
    check_customer_credit_status
)

router = APIRouter(prefix="/cxc", tags=["Módulo 5: Cuentas por Cobrar (CxC) & Complemento de Pagos 2.0"])


# --- Schemas ---

class PaymentAllocationInput(BaseModel):
    receivable_id: uuid.UUID
    amount_paid: Decimal = Field(..., gt=0)


class ApplyPaymentRequest(BaseModel):
    branch_id: uuid.UUID
    customer_id: uuid.UUID
    payment_form: str = Field("03", description="01 Efectivo, 03 Transferencia, 02 Cheque")
    amount: Decimal = Field(..., gt=0)
    allocations: List[PaymentAllocationInput]
    payment_date: Optional[datetime] = None
    operation_number: Optional[str] = None
    notes: Optional[str] = None


class CustomerCreditCheckResponse(BaseModel):
    is_authorized: bool
    message: str
    overdue_documents: List[Dict[str, Any]] = []


# --- Endpoints ---

@router.get("/dashboard")
async def get_cxc_dashboard(
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user)
):
    """
    Dashboard de Cobranza:
    Métricas de cartera total, vencida, porcentaje vencido y desglose por antigüedad.
    """
    aging = await get_customer_aging_analysis(db=db, tenant_id=tenant.id)

    # Clientes con mayor deuda
    cust_res = await db.execute(
        select(
            Customer.id,
            Customer.legal_name,
            Customer.credit_limit,
            Customer.credit_days,
            func.sum(ReceivableDocument.current_balance).label("total_debt")
        )
        .join(ReceivableDocument, ReceivableDocument.customer_id == Customer.id)
        .where(
            ReceivableDocument.tenant_id == tenant.id,
            ReceivableDocument.status.in_(["PENDIENTE", "PARCIAL"])
        )
        .group_by(Customer.id, Customer.legal_name, Customer.credit_limit, Customer.credit_days)
        .order_by(func.sum(ReceivableDocument.current_balance).desc())
        .limit(5)
    )
    top_debtors = [
        {
            "customer_id": r.id,
            "customer_name": r.legal_name,
            "credit_limit": float(r.credit_limit),
            "credit_days": r.credit_days,
            "total_debt": float(r.total_debt)
        }
        for r in cust_res.all()
    ]

    return {
        "total_receivable": aging["total_receivable"],
        "current_receivable": aging["current_receivable"],
        "overdue_total": aging["overdue_total"],
        "overdue_percentage": aging["overdue_percentage"],
        "buckets": aging["buckets"],
        "top_debtors": top_debtors,
        "total_pending_documents": len(aging["documents"])
    }


@router.get("/aging")
async def get_cxc_aging(
    customer_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user)
):
    """
    Reporte de Antigüedad de Saldos Contable:
    Segmentación por rangos (Al Corriente, 1-30, 31-60, 61-90, Más de 90 días).
    """
    return await get_customer_aging_analysis(db=db, tenant_id=tenant.id, customer_id=customer_id)


@router.get("/customers/{customer_id}/credit-check", response_model=CustomerCreditCheckResponse)
async def check_credit(
    customer_id: uuid.UUID,
    attempted_amount: Decimal = Query(Decimal("0.00"), ge=0),
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user)
):
    """
    Audita en tiempo real el estatus crediticio del cliente:
    Verifica límite de crédito y ausencia de facturas vencidas.
    """
    authorized, reason, overdue = await check_customer_credit_status(
        db=db,
        tenant_id=tenant.id,
        customer_id=customer_id,
        attempted_amount=attempted_amount
    )
    return CustomerCreditCheckResponse(
        is_authorized=authorized,
        message=reason,
        overdue_documents=overdue
    )


@router.get("/customers/{customer_id}/statement")
async def get_customer_account_statement(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user)
):
    """
    Estado de Cuenta por Cliente:
    Historial cronológico de cargos (facturas) y abonos (recibos de pago) con saldo insoluto.
    """
    cust_res = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.tenant_id == tenant.id))
    customer = cust_res.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado.")

    # 1. Obtener todos los documentos por cobrar (Cargos)
    rec_res = await db.execute(
        select(ReceivableDocument)
        .where(ReceivableDocument.tenant_id == tenant.id, ReceivableDocument.customer_id == customer_id)
        .order_by(ReceivableDocument.issue_date.asc())
    )
    receivables = rec_res.scalars().all()

    # 2. Obtener todos los abonos aplicados (Abonos)
    payments_res = await db.execute(
        select(PaymentReceiptDocRel)
        .join(PaymentReceipt, PaymentReceipt.id == PaymentReceiptDocRel.payment_receipt_id)
        .where(PaymentReceipt.tenant_id == tenant.id, PaymentReceipt.customer_id == customer_id)
        .options(selectinload(PaymentReceiptDocRel.payment_receipt))
        .order_by(PaymentReceiptDocRel.created_at.asc())
    )
    payments = payments_res.scalars().all()

    # Consolidar timeline contable
    transactions = []
    for r in receivables:
        transactions.append({
            "type": "CARGO",
            "date": r.issue_date,
            "due_date": r.due_date,
            "folio": r.formatted_folio,
            "concept": f"{r.document_type} {r.formatted_folio}",
            "amount": float(r.original_total),
            "balance": float(r.current_balance),
            "status": r.status
        })

    for p in payments:
        transactions.append({
            "type": "ABONO",
            "date": p.payment_receipt.payment_date,
            "due_date": None,
            "folio": p.payment_receipt.formatted_folio,
            "concept": f"Abono a {p.serie or ''}-{p.folio or ''} (Parcialidad {p.installment_number})",
            "amount": float(p.amount_paid),
            "balance": float(p.remaining_balance),
            "status": "APLICADO"
        })

    transactions.sort(key=lambda x: x["date"] or datetime.min.replace(tzinfo=timezone.utc))

    total_debt = sum(r.current_balance for r in receivables if r.status in ("PENDIENTE", "PARCIAL"))

    return {
        "customer": {
            "id": customer.id,
            "code": customer.code,
            "legal_name": customer.legal_name,
            "rfc": customer.rfc,
            "credit_limit": float(customer.credit_limit),
            "credit_days": customer.credit_days,
            "current_balance": float(total_debt)
        },
        "transactions": transactions
    }


@router.get("/receivables/pending")
async def list_pending_receivables(
    customer_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user)
):
    """
    Lista las facturas con saldo insoluto pendiente para aplicarles pago.
    """
    query = (
        select(ReceivableDocument)
        .options(selectinload(ReceivableDocument.customer))
        .where(
            ReceivableDocument.tenant_id == tenant.id,
            ReceivableDocument.status.in_(["PENDIENTE", "PARCIAL"]),
            ReceivableDocument.current_balance > 0
        )
        .order_by(ReceivableDocument.due_date.asc())
    )
    if customer_id:
        query = query.where(ReceivableDocument.customer_id == customer_id)

    res = await db.execute(query)
    docs = res.scalars().all()

    today = date.today()
    return [
        {
            "id": d.id,
            "customer_id": d.customer_id,
            "customer_name": d.customer.legal_name if d.customer else "Cliente",
            "folio": d.formatted_folio,
            "cfdi_uuid": d.cfdi_uuid,
            "issue_date": str(d.issue_date.date()) if d.issue_date else None,
            "due_date": str(d.due_date),
            "is_overdue": today > d.due_date,
            "days_overdue": (today - d.due_date).days if today > d.due_date else 0,
            "original_total": d.original_total,
            "current_balance": d.current_balance,
            "status": d.status
        }
        for d in docs
    ]


@router.post("/payments", status_code=status.HTTP_201_CREATED)
async def create_payment_endpoint(
    req: ApplyPaymentRequest,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user)
):
    """
    Aplica pago parcial o total generando el Complemento de Recepción de Pagos (REP 2.0 / CFDI 4.0).
    """
    allocations_raw = [
        {"receivable_id": a.receivable_id, "amount_paid": a.amount_paid}
        for a in req.allocations
    ]

    receipt = await apply_payment_receipt(
        db=db,
        tenant_id=tenant.id,
        branch_id=req.branch_id,
        customer_id=req.customer_id,
        user_id=user.id,
        payment_form=req.payment_form,
        amount=req.amount,
        allocations=allocations_raw,
        payment_date=req.payment_date,
        operation_number=req.operation_number,
        notes=req.notes
    )
    await db.commit()

    return {
        "message": "Complemento de Recepción de Pagos (REP 2.0) aplicado y timbrado con éxito.",
        "receipt_id": receipt.id,
        "folio": receipt.formatted_folio,
        "uuid": receipt.cfdi_uuid,
        "amount": receipt.amount,
        "stamped_at": receipt.cfdi_stamped_at,
        "status": receipt.status,
        "related_documents_count": len(receipt.related_docs)
    }


@router.get("/payments")
async def list_payments_endpoint(
    customer_id: Optional[uuid.UUID] = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user)
):
    """
    Lista el historial de recibos de pago REP 2.0 emitidos.
    """
    query = (
        select(PaymentReceipt)
        .options(
            selectinload(PaymentReceipt.customer),
            selectinload(PaymentReceipt.related_docs)
        )
        .where(PaymentReceipt.tenant_id == tenant.id)
        .order_by(PaymentReceipt.payment_date.desc())
        .limit(limit)
    )
    if customer_id:
        query = query.where(PaymentReceipt.customer_id == customer_id)

    res = await db.execute(query)
    payments = res.scalars().all()

    return [
        {
            "id": p.id,
            "folio": p.formatted_folio,
            "cfdi_uuid": p.cfdi_uuid,
            "customer_name": p.customer.legal_name if p.customer else "Cliente",
            "payment_date": p.payment_date,
            "payment_form": p.payment_form,
            "amount": p.amount,
            "status": p.status,
            "stamped_at": p.cfdi_stamped_at,
            "docs_count": len(p.related_docs)
        }
        for p in payments
    ]

