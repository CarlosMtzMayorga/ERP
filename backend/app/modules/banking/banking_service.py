import uuid
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.master_data.models import BankAccount, Currency
from app.modules.banking.models import BankTransaction
from app.modules.banking.schemas import (
    BankingDashboardMetrics,
    BankAccountResponse,
    BankTransactionResponse,
)


def _round_currency(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def record_bank_transaction(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    bank_account_id: uuid.UUID,
    amount: Decimal,
    direction: str,  # "IN" o "OUT"
    transaction_type: str,  # "DEPOSITO", "RETIRO", "PAGO_PROVEEDOR", "COBRO_CLIENTE", "TRANSFERENCIA_ENTRADA", "TRANSFERENCIA_SALIDA"
    reference_type: str,
    reference_id: Optional[uuid.UUID] = None,
    reference_folio: Optional[str] = None,
    operation_number: Optional[str] = None,
    notes: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    for_update: bool = True
) -> Tuple[BankTransaction, BankAccount]:
    """
    Registra una transacción bancaria inmutable en el libro mayor (Append-Only).
    
    CONTROL DE CONCURRENCIA Y SOBREGIRO (OVERDRAFT CONTROL):
    1. Aplica bloqueo exclusivo 'SELECT ... FOR UPDATE' en la fila de la cuenta bancaria.
    2. Valida que existan fondos suficientes si la transacción es de salida ('OUT').
       Si el saldo es insuficiente, aborta la transacción con HTTP 400.
    3. Materializa el nuevo saldo contable en la cuenta bancaria.
    4. Genera el registro de auditoría en 'BankTransaction'.
    """
    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El monto de la transacción bancaria debe ser mayor a cero."
        )

    direction_norm = direction.strip().upper()
    if direction_norm not in ("IN", "OUT"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dirección bancaria inválida: '{direction}'. Debe ser 'IN' o 'OUT'."
        )

    # 1. Bloqueo de fila para evitar condiciones de carrera concurrentes
    stmt = select(BankAccount).where(
        BankAccount.id == bank_account_id,
        BankAccount.tenant_id == tenant_id
    )
    if for_update:
        stmt = stmt.with_for_update()

    res = await db.execute(stmt)
    account = res.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cuenta bancaria no encontrada."
        )

    if not account.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La cuenta bancaria '{account.bank_name} - {account.account_number}' se encuentra inactiva."
        )

    amount_norm = _round_currency(amount)
    previous_balance = _round_currency(account.current_balance)

    # 2. Control estricto de sobregiro
    if direction_norm == "OUT" and previous_balance < amount_norm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Fondos insuficientes en la cuenta bancaria '{account.bank_name} {account.account_number}'. "
                f"Saldo contable disponible: ${previous_balance:,.2f}, Monto requerido: ${amount_norm:,.2f}."
            )
        )

    # 3. Cálculo del nuevo saldo contable
    if direction_norm == "IN":
        new_balance = previous_balance + amount_norm
    else:
        new_balance = previous_balance - amount_norm

    account.current_balance = new_balance

    # 4. Inserción inmutable en BankTransaction (Append-Only Ledger)
    tx = BankTransaction(
        tenant_id=tenant_id,
        bank_account_id=bank_account_id,
        transaction_type=transaction_type.upper(),
        direction=direction_norm,
        amount=amount_norm,
        previous_balance=previous_balance,
        new_balance=new_balance,
        reference_type=reference_type.upper(),
        reference_id=reference_id,
        reference_folio=reference_folio,
        operation_number=operation_number,
        transaction_date=datetime.now(timezone.utc),
        is_reconciled=False,
        reconciled_at=None,
        notes=notes,
        user_id=user_id
    )
    db.add(tx)
    await db.flush()

    return tx, account


async def reconcile_transactions(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    bank_account_id: uuid.UUID,
    transaction_ids: List[uuid.UUID],
    user_id: Optional[uuid.UUID] = None
) -> Tuple[int, BankAccount]:
    """
    Coteja y marca como 'Conciliadas' una lista de transacciones bancarias.
    Actualiza el 'Saldo Conciliado' de la cuenta bancaria en base al estado de cuenta real.
    """
    stmt = (
        select(BankAccount)
        .where(BankAccount.id == bank_account_id, BankAccount.tenant_id == tenant_id)
        .with_for_update()
    )
    res = await db.execute(stmt)
    account = res.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cuenta bancaria no encontrada.")

    # Obtener transacciones a conciliar
    tx_stmt = select(BankTransaction).where(
        BankTransaction.tenant_id == tenant_id,
        BankTransaction.bank_account_id == bank_account_id,
        BankTransaction.id.in_(transaction_ids),
        BankTransaction.is_reconciled.is_(False)
    )
    tx_res = await db.execute(tx_stmt)
    transactions = tx_res.scalars().all()

    now_utc = datetime.now(timezone.utc)
    for tx in transactions:
        tx.is_reconciled = True
        tx.reconciled_at = now_utc

    # Recalcular saldo conciliado total
    in_sum_stmt = select(func.coalesce(func.sum(BankTransaction.amount), 0)).where(
        BankTransaction.tenant_id == tenant_id,
        BankTransaction.bank_account_id == bank_account_id,
        BankTransaction.is_reconciled.is_(True),
        BankTransaction.direction == "IN"
    )
    in_sum = (await db.execute(in_sum_stmt)).scalar_one()

    out_sum_stmt = select(func.coalesce(func.sum(BankTransaction.amount), 0)).where(
        BankTransaction.tenant_id == tenant_id,
        BankTransaction.bank_account_id == bank_account_id,
        BankTransaction.is_reconciled.is_(True),
        BankTransaction.direction == "OUT"
    )
    out_sum = (await db.execute(out_sum_stmt)).scalar_one()

    account.reconciled_balance = Decimal(str(in_sum)) - Decimal(str(out_sum))
    await db.flush()

    return len(transactions), account


async def transfer_between_accounts(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    source_account_id: uuid.UUID,
    target_account_id: uuid.UUID,
    amount: Decimal,
    operation_number: Optional[str] = None,
    notes: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None
) -> Tuple[BankTransaction, BankTransaction]:
    """
    Ejecuta una transferencia interbancaria atómica entre dos cuentas de la empresa.
    """
    if source_account_id == target_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La cuenta origen y destino no pueden ser la misma."
        )

    # 1. Salida en cuenta origen
    tx_out, src_acc = await record_bank_transaction(
        db=db,
        tenant_id=tenant_id,
        bank_account_id=source_account_id,
        amount=amount,
        direction="OUT",
        transaction_type="TRANSFERENCIA_SALIDA",
        reference_type="TRANSFERENCIA",
        operation_number=operation_number,
        notes=notes or f"Traspaso a cuenta destino",
        user_id=user_id
    )

    # 2. Entrada en cuenta destino
    tx_in, tgt_acc = await record_bank_transaction(
        db=db,
        tenant_id=tenant_id,
        bank_account_id=target_account_id,
        amount=amount,
        direction="IN",
        transaction_type="TRANSFERENCIA_ENTRADA",
        reference_type="TRANSFERENCIA",
        reference_id=tx_out.id,
        operation_number=operation_number,
        notes=notes or f"Traspaso recibido de cuenta {src_acc.bank_name}",
        user_id=user_id
    )

    return tx_out, tx_in


async def get_banking_dashboard(
    db: AsyncSession,
    tenant_id: uuid.UUID
) -> BankingDashboardMetrics:
    """Calcula las métricas consolidadas de saldos contables, conciliados y flujos del mes."""
    now = datetime.now(timezone.utc)
    first_day_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    # Cuentas bancarias
    acc_stmt = (
        select(BankAccount)
        .options(selectinload(BankAccount.currency))
        .where(BankAccount.tenant_id == tenant_id, BankAccount.is_active.is_(True))
    )
    acc_res = await db.execute(acc_stmt)
    accounts = acc_res.scalars().all()

    total_book = sum(a.current_balance for a in accounts)
    total_reconciled = sum(a.reconciled_balance for a in accounts)

    # Flujo del mes
    inflow_stmt = select(func.coalesce(func.sum(BankTransaction.amount), 0)).where(
        BankTransaction.tenant_id == tenant_id,
        BankTransaction.direction == "IN",
        BankTransaction.transaction_date >= first_day_month
    )
    monthly_inflow = (await db.execute(inflow_stmt)).scalar_one()

    outflow_stmt = select(func.coalesce(func.sum(BankTransaction.amount), 0)).where(
        BankTransaction.tenant_id == tenant_id,
        BankTransaction.direction == "OUT",
        BankTransaction.transaction_date >= first_day_month
    )
    monthly_outflow = (await db.execute(outflow_stmt)).scalar_one()

    # Transacciones recientes
    tx_stmt = (
        select(BankTransaction)
        .options(selectinload(BankTransaction.bank_account))
        .where(BankTransaction.tenant_id == tenant_id)
        .order_by(desc(BankTransaction.transaction_date))
        .limit(20)
    )
    tx_res = await db.execute(tx_stmt)
    recent_txs = tx_res.scalars().all()

    accounts_payload = [
        BankAccountResponse(
            id=a.id,
            bank_name=a.bank_name,
            account_number=a.account_number,
            clabe=a.clabe,
            currency_id=a.currency_id,
            currency_code=a.currency.code if a.currency else "MXN",
            current_balance=Decimal(str(a.current_balance)),
            reconciled_balance=Decimal(str(a.reconciled_balance)),
            is_active=a.is_active
        )
        for a in accounts
    ]

    recent_payload = [
        BankTransactionResponse(
            id=t.id,
            bank_account_id=t.bank_account_id,
            transaction_type=t.transaction_type,
            direction=t.direction,
            amount=Decimal(str(t.amount)),
            previous_balance=Decimal(str(t.previous_balance)),
            new_balance=Decimal(str(t.new_balance)),
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
        for t in recent_txs
    ]

    return BankingDashboardMetrics(
        total_book_balance=Decimal(str(total_book)),
        total_reconciled_balance=Decimal(str(total_reconciled)),
        monthly_inflow=Decimal(str(monthly_inflow)),
        monthly_outflow=Decimal(str(outflow_stmt if False else monthly_outflow)),
        accounts=accounts_payload,
        recent_transactions=recent_payload
    )

