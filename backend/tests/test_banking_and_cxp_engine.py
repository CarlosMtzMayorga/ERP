import pytest
import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta, date
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import Base
from app.modules.tenants.models import Tenant, Branch, FiscalFoliosSeries
from app.modules.auth.models import User
from app.modules.master_data.models import Currency, Warehouse, Product, Supplier, Customer, BankAccount
from app.modules.purchases.models import PayableDocument
from app.modules.banking.models import BankTransaction
from app.modules.cxp.models import SupplierPayment, SupplierPaymentDocRel
from app.modules.cxp.schemas import (
    ApplySupplierPaymentRequest,
    PaymentDistributionItem,
)
from app.modules.banking import banking_service
from app.modules.cxp import cxp_service


async def setup_treasury_test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, session_factory


@pytest.mark.asyncio
async def test_supplier_payment_decreases_bank_account_balance():
    """
    Test 1: Verifica que el pago a un proveedor disminuye atómicamente el saldo
    de la cuenta bancaria seleccionada y genera el movimiento de salida en BankTransaction.
    """
    engine, session_factory = await setup_treasury_test_db()
    async with session_factory() as db:
        tenant_id = uuid.uuid4()
        branch_id = uuid.uuid4()

        branch = Branch(id=branch_id, tenant_id=tenant_id, code="SUC-01", name="Matriz", zip_code="06000")
        currency = Currency(id=uuid.uuid4(), tenant_id=tenant_id, code="MXN", name="Peso Mexicano", exchange_rate=Decimal("1.0000"), is_base=True)
        supplier = Supplier(id=uuid.uuid4(), tenant_id=tenant_id, code="PRV-01", rfc="PROV010101XYZ", legal_name="PROVEEDOR INDUSTRIAL S.A.", zip_code="06000", credit_days=30)
        
        # Cuenta bancaria con saldo inicial de $50,000.00
        bank_acc = BankAccount(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            bank_name="BBVA México",
            account_number="0123456789",
            clabe="012180001234567890",
            currency_id=currency.id,
            current_balance=Decimal("50000.00"),
            reconciled_balance=Decimal("0.00"),
            is_active=True
        )

        # Pasivo de factura por pagar: $12,500.00
        payable = PayableDocument(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            supplier_id=supplier.id,
            branch_id=branch_id,
            formatted_folio="FP-00101",
            issue_date=datetime.now(timezone.utc),
            due_date=date.today() + timedelta(days=15),
            credit_days=30,
            original_total=Decimal("12500.00"),
            original_subtotal=Decimal("10775.86"),
            original_vat=Decimal("1724.14"),
            current_balance=Decimal("12500.00"),
            status="PENDIENTE"
        )
        db.add_all([branch, currency, supplier, bank_acc, payable])
        await db.commit()

        # Ejecutar pago por $12,500.00
        pay_req = ApplySupplierPaymentRequest(
            supplier_id=supplier.id,
            branch_id=branch_id,
            bank_account_id=bank_acc.id,
            amount=Decimal("12500.00"),
            payment_method="03",
            operation_number="SPEI-99887766",
            notes="Liquidación total factura FP-00101"
        )

        payment, bank_tx = await cxp_service.apply_supplier_payment(db, tenant_id, pay_req)
        await db.commit()

        # Validar decremento atómico en cuenta bancaria: 50,000 - 12,500 = 37,500.00
        await db.refresh(bank_acc)
        assert bank_acc.current_balance == Decimal("37500.00")

        # Validar transacción inmutable en el libro mayor de bancos
        assert bank_tx.direction == "OUT"
        assert bank_tx.amount == Decimal("12500.00")
        assert bank_tx.previous_balance == Decimal("50000.00")
        assert bank_tx.new_balance == Decimal("37500.00")
        assert bank_tx.transaction_type == "PAGO_PROVEEDOR"
        assert bank_tx.operation_number == "SPEI-99887766"

        # Validar liquidación del pasivo en CxP
        await db.refresh(payable)
        assert payable.current_balance == Decimal("0.00")
        assert payable.status == "LIQUIDADO"

    await engine.dispose()


@pytest.mark.asyncio
async def test_overdraft_control_blocks_insufficient_funds():
    """
    Test 2: Control de Sobregiro (Overdraft Control).
    Verifica que no se puede realizar un egreso/pago si la cuenta bancaria
    no tiene fondos suficientes, rechazando con HTTPException 400.
    """
    engine, session_factory = await setup_treasury_test_db()
    async with session_factory() as db:
        tenant_id = uuid.uuid4()
        branch_id = uuid.uuid4()

        currency = Currency(id=uuid.uuid4(), tenant_id=tenant_id, code="MXN", name="Peso Mexicano", exchange_rate=Decimal("1.0000"), is_base=True)
        supplier = Supplier(id=uuid.uuid4(), tenant_id=tenant_id, code="PRV-02", rfc="PROV020202XYZ", legal_name="ACEROS DEL NORTE", zip_code="06000")
        branch = Branch(id=branch_id, tenant_id=tenant_id, code="SUC-01", name="Matriz", zip_code="06000")

        # Cuenta bancaria con solo $5,000.00 disponibles
        bank_acc = BankAccount(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            bank_name="Santander",
            account_number="5544332211",
            clabe="014180554433221100",
            currency_id=currency.id,
            current_balance=Decimal("5000.00"),
            reconciled_balance=Decimal("0.00"),
            is_active=True
        )

        payable = PayableDocument(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            supplier_id=supplier.id,
            branch_id=branch_id,
            formatted_folio="FP-00200",
            issue_date=datetime.now(timezone.utc),
            due_date=date.today(),
            credit_days=0,
            original_total=Decimal("20000.00"),
            original_subtotal=Decimal("17241.38"),
            original_vat=Decimal("2758.62"),
            current_balance=Decimal("20000.00"),
            status="PENDIENTE"
        )
        db.add_all([branch, currency, supplier, bank_acc, payable])
        await db.commit()

        # Intento de transferir $20,000.00 teniendo solo $5,000.00
        pay_req = ApplySupplierPaymentRequest(
            supplier_id=supplier.id,
            branch_id=branch_id,
            bank_account_id=bank_acc.id,
            amount=Decimal("20000.00"),
            payment_method="03"
        )

        with pytest.raises(HTTPException) as excinfo:
            await cxp_service.apply_supplier_payment(db, tenant_id, pay_req)

        assert excinfo.value.status_code == 400
        assert "Fondos insuficientes" in excinfo.value.detail

        # El saldo debe permanecer intacto en $5,000.00
        await db.refresh(bank_acc)
        assert bank_acc.current_balance == Decimal("5000.00")

    await engine.dispose()


@pytest.mark.asyncio
async def test_multiple_invoices_payment_distribution_and_proportional_retentions():
    """
    Test 3: Liquidación múltiple de facturas simultáneas y cálculo de retenciones proporcionales (IVA / ISR).
    """
    engine, session_factory = await setup_treasury_test_db()
    async with session_factory() as db:
        tenant_id = uuid.uuid4()
        branch_id = uuid.uuid4()

        branch = Branch(id=branch_id, tenant_id=tenant_id, code="SUC-01", name="Matriz", zip_code="06000")
        currency = Currency(id=uuid.uuid4(), tenant_id=tenant_id, code="MXN", name="Peso Mexicano", exchange_rate=Decimal("1.0000"), is_base=True)
        supplier = Supplier(id=uuid.uuid4(), tenant_id=tenant_id, code="PRV-FLETE", rfc="FLE900101XYZ", legal_name="TRANSPORTES Y FLETES SA", zip_code="06000")

        bank_acc = BankAccount(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            bank_name="Banorte",
            account_number="9988776655",
            clabe="072180998877665544",
            currency_id=currency.id,
            current_balance=Decimal("100000.00"),
            reconciled_balance=Decimal("0.00"),
            is_active=True
        )

        # Factura 1: $10,000.00 con retención de flete (4% retención IVA = $400.00)
        # Total = 10,000 + 1,600 (IVA) - 400 (Ret IVA) = $11,200.00
        doc1 = PayableDocument(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            supplier_id=supplier.id,
            branch_id=branch_id,
            formatted_folio="FP-FLETE-1",
            issue_date=datetime.now(timezone.utc),
            due_date=date.today() - timedelta(days=5),  # Vencida hace 5 días
            credit_days=15,
            original_total=Decimal("11200.00"),
            original_subtotal=Decimal("10000.00"),
            original_vat=Decimal("1600.00"),
            original_retention_vat=Decimal("400.00"),
            original_retention_isr=Decimal("0.00"),
            current_balance=Decimal("11200.00"),
            status="PENDIENTE"
        )

        # Factura 2: $5,000.00
        doc2 = PayableDocument(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            supplier_id=supplier.id,
            branch_id=branch_id,
            formatted_folio="FP-FLETE-2",
            issue_date=datetime.now(timezone.utc),
            due_date=date.today() + timedelta(days=10),
            credit_days=15,
            original_total=Decimal("5800.00"),
            original_subtotal=Decimal("5000.00"),
            original_vat=Decimal("800.00"),
            original_retention_vat=Decimal("0.00"),
            original_retention_isr=Decimal("0.00"),
            current_balance=Decimal("5800.00"),
            status="PENDIENTE"
        )
        db.add_all([branch, currency, supplier, bank_acc, doc1, doc2])
        await db.commit()

        # Pago de $14,100.00 distribuido:
        # $11,200.00 a doc1 (liquidación total)
        # $2,900.00 a doc2 (abono parcial del 50%)
        pay_req = ApplySupplierPaymentRequest(
            supplier_id=supplier.id,
            branch_id=branch_id,
            bank_account_id=bank_acc.id,
            amount=Decimal("14100.00"),
            payment_method="03",
            distributions=[
                PaymentDistributionItem(payable_document_id=doc1.id, amount_to_apply=Decimal("11200.00")),
                PaymentDistributionItem(payable_document_id=doc2.id, amount_to_apply=Decimal("2900.00")),
            ]
        )

        payment, bank_tx = await cxp_service.apply_supplier_payment(db, tenant_id, pay_req)
        await db.commit()

        # Validar saldos
        await db.refresh(doc1)
        assert doc1.current_balance == Decimal("0.00")
        assert doc1.status == "LIQUIDADO"

        await db.refresh(doc2)
        assert doc2.current_balance == Decimal("2900.00")
        assert doc2.status == "PARCIAL"

        # Validar retención real en doc1: 100% de la retención = $400.00
        rels_stmt = select(SupplierPaymentDocRel).where(SupplierPaymentDocRel.supplier_payment_id == payment.id)
        rels = (await db.execute(rels_stmt)).scalars().all()
        assert len(rels) == 2

        rel1 = next(r for r in rels if r.payable_document_id == doc1.id)
        assert rel1.amount_paid == Decimal("11200.00")
        assert rel1.proportional_retention_vat == Decimal("400.00")

        # Saldo bancario: 100,000 - 14,100 = 85,900.00
        await db.refresh(bank_acc)
        assert bank_acc.current_balance == Decimal("85900.00")

    await engine.dispose()


@pytest.mark.asyncio
async def test_bank_reconciliation_separates_book_and_reconciled_balances():
    """
    Test 4: Valida la separación entre Saldo Contable y Saldo Conciliado.
    """
    engine, session_factory = await setup_treasury_test_db()
    async with session_factory() as db:
        tenant_id = uuid.uuid4()
        currency = Currency(id=uuid.uuid4(), tenant_id=tenant_id, code="MXN", name="Peso Mexicano", exchange_rate=Decimal("1.0000"), is_base=True)

        bank_acc = BankAccount(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            bank_name="HSBC",
            account_number="1122334455",
            clabe="021180112233445566",
            currency_id=currency.id,
            current_balance=Decimal("0.00"),
            reconciled_balance=Decimal("0.00"),
            is_active=True
        )
        db.add_all([currency, bank_acc])
        await db.commit()

        # Transacción 1: Depósito de $10,000.00
        tx1, _ = await banking_service.record_bank_transaction(
            db, tenant_id, bank_acc.id, Decimal("10000.00"), "IN", "DEPOSITO", "VENTAS"
        )
        # Transacción 2: Depósito de $5,000.00
        tx2, _ = await banking_service.record_bank_transaction(
            db, tenant_id, bank_acc.id, Decimal("5000.00"), "IN", "DEPOSITO", "COBRANZA"
        )
        # Transacción 3: Retiro de $2,000.00
        tx3, _ = await banking_service.record_bank_transaction(
            db, tenant_id, bank_acc.id, Decimal("2000.00"), "OUT", "RETIRO", "GASTOS"
        )
        await db.commit()

        await db.refresh(bank_acc)
        # Saldo contable = 10,000 + 5,000 - 2,000 = $13,000.00
        assert bank_acc.current_balance == Decimal("13000.00")
        assert bank_acc.reconciled_balance == Decimal("0.00")

        # Conciliar únicamente tx1 ($10,000.00) y tx3 ($2,000.00)
        reconciled_count, updated_acc = await banking_service.reconcile_transactions(
            db, tenant_id, bank_acc.id, [tx1.id, tx3.id]
        )
        await db.commit()

        assert reconciled_count == 2
        # Saldo conciliado = 10,000 - 2,000 = $8,000.00
        assert updated_acc.reconciled_balance == Decimal("8000.00")
        # El saldo contable permanece en $13,000.00
        assert updated_acc.current_balance == Decimal("13000.00")

    await engine.dispose()

