import uuid
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta, date
from typing import List, Optional, Tuple, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.purchases.models import PayableDocument
from app.modules.cxp.models import SupplierPayment, SupplierPaymentDocRel
from app.modules.cxp.schemas import (
    ApplySupplierPaymentRequest,
    PaymentScheduleSummary,
    PaymentScheduleItem,
    CxPDashboardMetrics,
)
from app.modules.banking.banking_service import record_bank_transaction
from app.modules.tenants.models import FiscalFoliosSeries
from app.modules.tenants.folios_service import consume_next_folio
from app.modules.master_data.models import Supplier, BankAccount


def _round_2(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def ensure_cxp_folio_series(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    branch_id: Optional[uuid.UUID],
    doc_type: str = "PAG_PROV",
    serie: str = "PP",
    initial_folio: int = 1
):
    """Garantiza la existencia de la serie de folios para comprobantes de pago a proveedor."""
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


async def get_payment_schedule(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    supplier_id: Optional[uuid.UUID] = None
) -> PaymentScheduleSummary:
    """
    Consulta las cuentas por pagar vigentes agrupadas y ordenadas por fecha de vencimiento.
    Calcula adeudos vencidos, exigibles hoy, en la semana y a futuro.
    """
    today = date.today()
    week_limit = today + timedelta(days=7)

    query = (
        select(PayableDocument)
        .options(selectinload(PayableDocument.supplier))
        .where(
            PayableDocument.tenant_id == tenant_id,
            PayableDocument.status.in_(("PENDIENTE", "PARCIAL")),
            PayableDocument.current_balance > Decimal("0.00")
        )
    )
    if supplier_id:
        query = query.where(PayableDocument.supplier_id == supplier_id)

    query = query.order_by(PayableDocument.due_date.asc(), PayableDocument.created_at.asc())
    res = await db.execute(query)
    payables = res.scalars().all()

    items: List[PaymentScheduleItem] = []
    total_debt = Decimal("0.00")
    overdue_total = Decimal("0.00")
    due_today_total = Decimal("0.00")
    due_this_week_total = Decimal("0.00")
    due_later_total = Decimal("0.00")

    for p in payables:
        balance = _round_2(Decimal(str(p.current_balance)))
        total_debt += balance
        days_until = (p.due_date - today).days
        is_overdue = days_until < 0

        if is_overdue:
            overdue_total += balance
        elif days_until == 0:
            due_today_total += balance
        elif days_until <= 7:
            due_this_week_total += balance
        else:
            due_later_total += balance

        items.append(
            PaymentScheduleItem(
                id=p.id,
                supplier_id=p.supplier_id,
                supplier_name=p.supplier.legal_name if p.supplier else "Proveedor General",
                supplier_rfc=p.supplier.rfc if p.supplier else "XAXX010101000",
                formatted_folio=p.formatted_folio,
                cfdi_uuid=p.cfdi_uuid,
                issue_date=p.issue_date,
                due_date=p.due_date,
                days_until_due=days_until,
                is_overdue=is_overdue,
                credit_days=p.credit_days,
                original_total=_round_2(Decimal(str(p.original_total))),
                original_retention_vat=_round_2(Decimal(str(p.original_retention_vat))),
                original_retention_isr=_round_2(Decimal(str(p.original_retention_isr))),
                current_balance=balance,
                status=p.status
            )
        )

    return PaymentScheduleSummary(
        total_debt=total_debt,
        overdue_total=overdue_total,
        due_today_total=due_today_total,
        due_this_week_total=due_this_week_total,
        due_later_total=due_later_total,
        items=items
    )


async def apply_supplier_payment(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: ApplySupplierPaymentRequest,
    user_id: Optional[uuid.UUID] = None
) -> Tuple[SupplierPayment, Any]:
    """
    Aplica un pago a proveedor y liquida/abona a una o varias facturas de compra.
    
    INTEGRACIÓN ATÓMICA CON BANCOS (FASE 8):
    1. Consume un consecutivo de folio para el recibo de egreso.
    2. Invoca 'record_bank_transaction' extrayendo fondos de la cuenta bancaria con bloqueo
       'SELECT ... FOR UPDATE' y rechaza con HTTP 400 si hay sobregiro (fondos insuficientes).
    3. Distribuye el monto entre las facturas seleccionadas o de la más antigua a la más reciente.
    4. Calcula con precisión matemática las retenciones proporcionales reales (IVA / ISR) efectuadas.
    5. Actualiza los saldos y estados de los pasivos (PENDIENTE -> PARCIAL -> LIQUIDADO).
    """
    total_payment = _round_2(data.amount)
    if total_payment <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El monto del pago debe ser mayor a cero."
        )

    # 1. Validar proveedor
    supplier = await db.get(Supplier, data.supplier_id)
    if not supplier or supplier.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado.")

    # 2. Generar folio consecutivo
    await ensure_cxp_folio_series(db, tenant_id, data.branch_id, "PAG_PROV", "PP", 1)
    serie, next_folio, _ = await consume_next_folio(db, tenant_id, "PAG_PROV", branch_id=data.branch_id)
    formatted_folio = f"{serie}-{next_folio:05d}"

    # 3. AFECTACIÓN BANCARIA ATÓMICA CON CONTROL DE SOBREGIRO
    bank_tx, bank_acc = await record_bank_transaction(
        db=db,
        tenant_id=tenant_id,
        bank_account_id=data.bank_account_id,
        amount=total_payment,
        direction="OUT",
        transaction_type="PAGO_PROVEEDOR",
        reference_type="PAGO_PROVEEDOR",
        reference_folio=formatted_folio,
        operation_number=data.operation_number,
        notes=data.notes or f"Pago a proveedor {supplier.legal_name} con folio {formatted_folio}",
        user_id=user_id
    )

    # 4. Determinar distribución de facturas a pagar
    distributions: List[Tuple[uuid.UUID, Decimal]] = []

    if data.distributions and len(data.distributions) > 0:
        sum_dist = sum(_round_2(d.amount_to_apply) for d in data.distributions)
        if sum_dist != total_payment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La suma de las aplicaciones (${sum_dist:,.2f}) no coincide con el total del pago (${total_payment:,.2f})."
            )
        for dist in data.distributions:
            distributions.append((dist.payable_document_id, _round_2(dist.amount_to_apply)))
    else:
        # Auto-distribución de la factura más antigua a la más reciente (FIFO de pasivos)
        query = (
            select(PayableDocument)
            .where(
                PayableDocument.tenant_id == tenant_id,
                PayableDocument.supplier_id == data.supplier_id,
                PayableDocument.status.in_(("PENDIENTE", "PARCIAL")),
                PayableDocument.current_balance > Decimal("0.00")
            )
            .order_by(PayableDocument.due_date.asc(), PayableDocument.created_at.asc())
            .with_for_update()
        )
        res = await db.execute(query)
        pending_docs = res.scalars().all()

        remaining_cash = total_payment
        for doc in pending_docs:
            if remaining_cash <= 0:
                break
            doc_balance = _round_2(Decimal(str(doc.current_balance)))
            alloc = min(remaining_cash, doc_balance)
            distributions.append((doc.id, alloc))
            remaining_cash -= alloc

        if remaining_cash > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El monto a pagar (${total_payment:,.2f}) excede el saldo insoluto total adeudado al proveedor."
            )

    # 5. Aplicar pagos a cada PayableDocument y calcular retenciones proporcionales
    doc_rels: List[SupplierPaymentDocRel] = []
    payment_obj = SupplierPayment(
        tenant_id=tenant_id,
        supplier_id=data.supplier_id,
        branch_id=data.branch_id,
        bank_account_id=data.bank_account_id,
        serie=serie,
        folio=next_folio,
        formatted_folio=formatted_folio,
        payment_date=datetime.now(timezone.utc),
        payment_method=data.payment_method,
        amount=total_payment,
        operation_number=data.operation_number,
        notes=data.notes,
        status="APLICADO",
        user_id=user_id
    )
    db.add(payment_obj)
    await db.flush()

    for doc_id, amount_applied in distributions:
        doc = await db.get(PayableDocument, doc_id, with_for_update=True)
        if not doc or doc.tenant_id != tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Documento de pasivo {doc_id} no encontrado.")

        prev_balance = _round_2(Decimal(str(doc.current_balance)))
        if amount_applied > prev_balance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El abono de ${amount_applied:,.2f} excede el saldo insoluto de ${prev_balance:,.2f} en factura {doc.formatted_folio}."
            )

        new_balance = prev_balance - amount_applied
        doc.current_balance = new_balance
        if new_balance <= Decimal("0.0001"):
            doc.status = "LIQUIDADO"
        else:
            doc.status = "PARCIAL"

        # Cálculo de retenciones proporcionales reales (IVA / ISR)
        orig_tot = Decimal(str(doc.original_total))
        orig_sub = Decimal(str(doc.original_subtotal))
        orig_vat = Decimal(str(doc.original_vat))
        orig_ret_vat = Decimal(str(doc.original_retention_vat))
        orig_ret_isr = Decimal(str(doc.original_retention_isr))

        if orig_tot > 0:
            factor = amount_applied / orig_tot
            prop_sub = _round_2(orig_sub * factor)
            prop_vat = _round_2(orig_vat * factor)
            prop_ret_vat = _round_2(orig_ret_vat * factor)
            prop_ret_isr = _round_2(orig_ret_isr * factor)
        else:
            prop_sub = amount_applied
            prop_vat = Decimal("0.00")
            prop_ret_vat = Decimal("0.00")
            prop_ret_isr = Decimal("0.00")

        # Conteo de parcialidades previas
        cnt_stmt = select(func.count(SupplierPaymentDocRel.id)).where(
            SupplierPaymentDocRel.payable_document_id == doc.id
        )
        prior_installments = (await db.execute(cnt_stmt)).scalar_one()

        rel = SupplierPaymentDocRel(
            tenant_id=tenant_id,
            supplier_payment_id=payment_obj.id,
            payable_document_id=doc.id,
            installment_number=prior_installments + 1,
            previous_balance=prev_balance,
            amount_paid=amount_applied,
            remaining_balance=new_balance,
            proportional_subtotal=prop_sub,
            proportional_vat=prop_vat,
            proportional_retention_vat=prop_ret_vat,
            proportional_retention_isr=prop_ret_isr
        )
        doc_rels.append(rel)

    db.add_all(doc_rels)
    await db.flush()

    return payment_obj, bank_tx


async def get_cxp_dashboard_metrics(
    db: AsyncSession,
    tenant_id: uuid.UUID
) -> CxPDashboardMetrics:
    """Calcula las métricas financieras de CxP y el resumen del calendario de pagos."""
    now = datetime.now(timezone.utc)
    first_day_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    # 1. Total pagado este mes
    paid_stmt = select(func.coalesce(func.sum(SupplierPayment.amount), 0)).where(
        SupplierPayment.tenant_id == tenant_id,
        SupplierPayment.status == "APLICADO",
        SupplierPayment.payment_date >= first_day_month
    )
    paid_this_month = (await db.execute(paid_stmt)).scalar_one()

    # 2. Calendario de pagos y pasivos vigentes
    schedule = await get_payment_schedule(db, tenant_id)

    # 3. Proveedores acreedores activos con saldo pendiente
    creditors_stmt = select(func.count(func.distinct(PayableDocument.supplier_id))).where(
        PayableDocument.tenant_id == tenant_id,
        PayableDocument.status.in_(("PENDIENTE", "PARCIAL")),
        PayableDocument.current_balance > Decimal("0.00")
    )
    active_creditors = (await db.execute(creditors_stmt)).scalar_one()

    return CxPDashboardMetrics(
        total_accounts_payable=schedule.total_debt,
        overdue_payable=schedule.overdue_total,
        paid_this_month=Decimal(str(paid_this_month)),
        active_creditors_count=active_creditors,
        schedule_summary=schedule
    )

