import uuid
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.tenant_context import get_current_tenant_id
from app.core.dependencies import get_current_user, require_permission
from app.modules.auth.models import User
from app.modules.master_data.models import BankAccount, Currency
from app.modules.banking.models import BankTransaction
from app.modules.banking.schemas import (
    BankingDashboardMetrics,
    BankAccountResponse,
    BankAccountCreate,
    BankTransactionResponse,
    BankTransactionCreate,
    InterbankTransferCreate,
    ReconciliationRequest,
)
from app.modules.banking import banking_service

router = APIRouter(prefix="/banking", tags=["Bancos y Chequeras"])


@router.get("/dashboard", response_model=BankingDashboardMetrics)
async def get_banking_dashboard(
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("banking:read"))
):
    """Retorna las métricas ejecutivas de tesorería: saldos contables, conciliados y flujo mensual."""
    return await banking_service.get_banking_dashboard(db, tenant_id)


@router.get("/accounts", response_model=List[BankAccountResponse])
async def list_bank_accounts(
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("banking:read"))
):
    """Lista las cuentas bancarias activas de la empresa."""
    stmt = (
        select(BankAccount)
        .options(selectinload(BankAccount.currency))
        .where(BankAccount.tenant_id == tenant_id)
        .order_by(BankAccount.bank_name)
    )
    res = await db.execute(stmt)
    accounts = res.scalars().all()
    return [
        BankAccountResponse(
            id=a.id,
            bank_name=a.bank_name,
            account_number=a.account_number,
            clabe=a.clabe,
            currency_id=a.currency_id,
            currency_code=a.currency.code if a.currency else "MXN",
            current_balance=a.current_balance,
            reconciled_balance=a.reconciled_balance,
            is_active=a.is_active
        )
        for a in accounts
    ]


@router.post("/accounts", response_model=BankAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_bank_account(
    payload: BankAccountCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("banking:read"))
):
    """Registra una nueva cuenta bancaria."""
    account = BankAccount(
        tenant_id=tenant_id,
        bank_name=payload.bank_name.strip(),
        account_number=payload.account_number.strip(),
        clabe=payload.clabe.strip(),
        currency_id=payload.currency_id,
        sat_banco_code=payload.sat_banco_code,
        current_balance=payload.initial_balance,
        reconciled_balance=Decimal("0.00"),
        is_active=True
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)

    if payload.initial_balance > 0:
        await banking_service.record_bank_transaction(
            db=db,
            tenant_id=tenant_id,
            bank_account_id=account.id,
            amount=payload.initial_balance,
            direction="IN",
            transaction_type="DEPOSITO",
            reference_type="SALDO_INICIAL",
            notes="Saldo inicial de apertura de cuenta",
            user_id=current_user.id
        )
        await db.commit()
        await db.refresh(account)

    return BankAccountResponse(
        id=account.id,
        bank_name=account.bank_name,
        account_number=account.account_number,
        clabe=account.clabe,
        currency_id=account.currency_id,
        currency_code="MXN",
        current_balance=account.current_balance,
        reconciled_balance=account.reconciled_balance,
        is_active=account.is_active
    )


@router.get("/transactions", response_model=List[BankTransactionResponse])
async def list_bank_transactions(
    bank_account_id: Optional[uuid.UUID] = Query(None),
    is_reconciled: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("banking:read"))
):
    """Consulta el libro mayor de movimientos bancarios con filtros por cuenta o estado de conciliación."""
    query = (
        select(BankTransaction)
        .options(selectinload(BankTransaction.bank_account))
        .where(BankTransaction.tenant_id == tenant_id)
    )
    if bank_account_id:
        query = query.where(BankTransaction.bank_account_id == bank_account_id)
    if is_reconciled is not None:
        query = query.where(BankTransaction.is_reconciled == is_reconciled)

    query = query.order_by(desc(BankTransaction.transaction_date)).limit(limit)
    res = await db.execute(query)
    txs = res.scalars().all()

    return [
        BankTransactionResponse(
            id=t.id,
            bank_account_id=t.bank_account_id,
            transaction_type=t.transaction_type,
            direction=t.direction,
            amount=t.amount,
            previous_balance=t.previous_balance,
            new_balance=t.new_balance,
            reference_type=t.reference_type,
            reference_id=t.reference_id,
            reference_folio=t.reference_folio,
            operation_number=t.operation_number,
            transaction_date=t.transaction_date,
            is_reconciled=t.is_reconciled,
            reconciled_at=t.reconciled_at,
            notes=t.notes,
            bank_name=t.bank_account.bank_name if t.bank_account else None,
            account_number=t.bank_account.account_number if t.bank_account else None
        )
        for t in txs
    ]


@router.post("/transactions", response_model=BankTransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_manual_transaction(
    payload: BankTransactionCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("banking:read"))
):
    """Registra un depósito o retiro manual en una cuenta bancaria con control de sobregiro."""
    direction = "IN" if payload.transaction_type.upper() == "DEPOSITO" else "OUT"
    tx, _ = await banking_service.record_bank_transaction(
        db=db,
        tenant_id=tenant_id,
        bank_account_id=payload.bank_account_id,
        amount=payload.amount,
        direction=direction,
        transaction_type=payload.transaction_type.upper(),
        reference_type="MANUAL",
        operation_number=payload.operation_number,
        notes=payload.notes,
        user_id=current_user.id
    )
    await db.commit()
    await db.refresh(tx)

    return BankTransactionResponse(
        id=tx.id,
        bank_account_id=tx.bank_account_id,
        transaction_type=tx.transaction_type,
        direction=tx.direction,
        amount=tx.amount,
        previous_balance=tx.previous_balance,
        new_balance=tx.new_balance,
        reference_type=tx.reference_type,
        reference_id=tx.reference_id,
        reference_folio=tx.reference_folio,
        operation_number=tx.operation_number,
        transaction_date=tx.transaction_date,
        is_reconciled=tx.is_reconciled,
        reconciled_at=tx.reconciled_at,
        notes=tx.notes
    )


@router.post("/transfers", status_code=status.HTTP_201_CREATED)
async def execute_interbank_transfer(
    payload: InterbankTransferCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("banking:read"))
):
    """Realiza una transferencia de fondos entre dos cuentas bancarias de la empresa."""
    tx_out, tx_in = await banking_service.transfer_between_accounts(
        db=db,
        tenant_id=tenant_id,
        source_account_id=payload.source_account_id,
        target_account_id=payload.target_account_id,
        amount=payload.amount,
        operation_number=payload.operation_number,
        notes=payload.notes,
        user_id=current_user.id
    )
    await db.commit()
    return {
        "success": True,
        "message": f"Transferencia de ${payload.amount:,.2f} realizada exitosamente.",
        "withdrawal_transaction_id": tx_out.id,
        "deposit_transaction_id": tx_in.id
    }


@router.post("/reconcile")
async def reconcile_bank_transactions(
    payload: ReconciliationRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("banking:reconcile"))
):
    """Coteja y marca movimientos bancarios como conciliados, actualizando el saldo conciliado."""
    count, account = await banking_service.reconcile_transactions(
        db=db,
        tenant_id=tenant_id,
        bank_account_id=payload.bank_account_id,
        transaction_ids=payload.transaction_ids,
        user_id=current_user.id
    )
    await db.commit()
    return {
        "success": True,
        "reconciled_count": count,
        "reconciled_balance": account.reconciled_balance,
        "book_balance": account.current_balance
    }
