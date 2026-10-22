import pytest
import uuid
import datetime
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import Base
from app.modules.auth.models import User
from app.modules.tenants.models import Tenant, Branch, FiscalFoliosSeries
from app.modules.master_data.models import Currency, Warehouse, ProductCategory, Product, Customer
from app.modules.inventories.models import ProductWarehouseStock, KardexMovement, CostLayer
from app.modules.inventories import inventory_service
from app.modules.accounting.models import Account, JournalEntry, JournalEntryLine
from app.modules.accounting.chart_of_accounts import seed_default_chart_of_accounts
from app.modules.accounting.schemas import (
    JournalEntryCreate,
    JournalEntryLineCreate,
    AccountCreate
)
from app.modules.accounting import accounting_service
from app.modules.sales import sales_service


async def setup_accounting_test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, session_factory


@pytest.mark.asyncio
async def test_accounting_rejects_unbalanced_journal_entry():
    """
    Test 1: Regla Matemática Inquebrantable de Partida Doble.
    Verifica que el sistema rechaza estrictamente cualquier póliza donde
    la suma de los Cargos (debit) no sea igual a la suma de los Abonos (credit).
    """
    engine, session_factory = await setup_accounting_test_db()
    async with session_factory() as db:
        tenant_id = uuid.uuid4()
        acc_map = await seed_default_chart_of_accounts(db, tenant_id)

        caja_acc = acc_map["1101"]      # Deudora
        ventas_acc = acc_map["4101"]    # Acreedora

        # Póliza Descuadrada: Cargo $1,000.00 vs Abono $950.00 (Diferencia $50.00)
        unbalanced_data = JournalEntryCreate(
            entry_type="INGRESO",
            entry_date=datetime.date.today(),
            concept="Venta de mostrador descuadrada",
            lines=[
                JournalEntryLineCreate(
                    account_id=caja_acc.id,
                    concept="Entrada a caja",
                    debit=Decimal("1000.00"),
                    credit=Decimal("0.00")
                ),
                JournalEntryLineCreate(
                    account_id=ventas_acc.id,
                    concept="Ingreso por ventas",
                    debit=Decimal("0.00"),
                    credit=Decimal("950.00")
                )
            ]
        )

        with pytest.raises(HTTPException) as exc_info:
            await accounting_service.create_journal_entry(
                db=db,
                tenant_id=tenant_id,
                data=unbalanced_data
            )

        assert exc_info.value.status_code == 400
        assert "descuadrada" in exc_info.value.detail.lower()

        # Verificar que no se guardó la póliza ni se alteraron los saldos de las cuentas
        stmt_entries = select(JournalEntry).where(JournalEntry.tenant_id == tenant_id)
        entries_res = await db.execute(stmt_entries)
        assert len(entries_res.scalars().all()) == 0

        await db.refresh(caja_acc)
        assert caja_acc.current_balance == Decimal("0.00")


@pytest.mark.asyncio
async def test_balanced_journal_entry_updates_account_balances():
    """
    Test 2: Valida que una póliza cuadrada se aplica exitosamente y actualiza
    los saldos contables conforme a su naturaleza (Deudora: +deb -cred; Acreedora: +cred -deb).
    """
    engine, session_factory = await setup_accounting_test_db()
    async with session_factory() as db:
        tenant_id = uuid.uuid4()
        acc_map = await seed_default_chart_of_accounts(db, tenant_id)

        bancos_acc = acc_map["1102"]    # Deudora
        capital_acc = acc_map["3101"]   # Acreedora

        # Aportación inicial de capital: Cargo Bancos $50,000.00 / Abono Capital Social $50,000.00
        balanced_data = JournalEntryCreate(
            entry_type="INGRESO",
            entry_date=datetime.date.today(),
            concept="Aportación de Capital Social",
            lines=[
                JournalEntryLineCreate(
                    account_id=bancos_acc.id,
                    concept="Depósito bancario de socios",
                    debit=Decimal("50000.00"),
                    credit=Decimal("0.00")
                ),
                JournalEntryLineCreate(
                    account_id=capital_acc.id,
                    concept="Emisión de acciones",
                    debit=Decimal("0.00"),
                    credit=Decimal("50000.00")
                )
            ]
        )

        entry = await accounting_service.create_journal_entry(
            db=db,
            tenant_id=tenant_id,
            data=balanced_data
        )

        assert entry.id is not None
        assert entry.folio.startswith("PI-")
        assert entry.total_debit == Decimal("50000.00")
        assert entry.total_credit == Decimal("50000.00")
        assert entry.status == "APLICADA"

        # Verificar saldos
        await db.refresh(bancos_acc)
        await db.refresh(capital_acc)
        assert bancos_acc.current_balance == Decimal("50000.00")
        assert capital_acc.current_balance == Decimal("50000.00")


@pytest.mark.asyncio
async def test_sales_invoice_triggers_automatic_journal_entry_with_exact_cogs():
    """
    Test 3: Verifica que la emisión de una Factura de Venta (Fase 4) dispara
    automáticamente su póliza contable con el cálculo exacto del Costo de Ventas (COGS)
    y el cuadre estricto de partida doble en tiempo real.
    """
    engine, session_factory = await setup_accounting_test_db()
    async with session_factory() as db:
        tenant_id = uuid.uuid4()
        branch_id = uuid.uuid4()
        warehouse_id = uuid.uuid4()
        customer_id = uuid.uuid4()
        currency_id = uuid.uuid4()

        # 1. Configurar infraestructura maestra
        tenant = Tenant(
            id=tenant_id,
            rfc="EME200101XYZ",
            legal_name="EMPRESA MODELO SA DE CV",
            fiscal_regime_code="601",
            zip_code="06000"
        )
        branch = Branch(id=branch_id, tenant_id=tenant_id, code="SUC-01", name="Matriz", zip_code="06000")
        warehouse = Warehouse(id=warehouse_id, tenant_id=tenant_id, branch_id=branch_id, code="ALM-01", name="Almacén Central")
        currency = Currency(id=currency_id, tenant_id=tenant_id, code="MXN", name="Peso Mexicano", exchange_rate=Decimal("1.0000"), is_base=True)
        customer = Customer(
            id=customer_id,
            tenant_id=tenant_id,
            code="CTE-01",
            legal_name="CLIENTE CORPORATIVO SA DE CV",
            rfc="CLI200101XYZ",
            fiscal_regime_code="601",
            zip_code="06000",
            credit_limit=Decimal("50000.00")
        )
        cat = ProductCategory(id=uuid.uuid4(), tenant_id=tenant_id, code="CAT-01", name="Electrónica")
        
        fac_serie = FiscalFoliosSeries(
            tenant_id=tenant_id,
            branch_id=branch_id,
            document_type="FAC",
            serie="F",
            initial_folio=1,
            current_folio=0,
            is_default=True
        )

        # Producto con método de costeo Promedio/PEPS
        product = Product(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            category_id=cat.id,
            sku="PROD-LAPTOP",
            name="Laptop Enterprise",
            costing_method="PEPS",
            product_type="PRODUCTO",
            unit_name="PZA",
            sat_clave_prod_serv="43211503",
            sat_clave_unidad="H87",
            average_cost=Decimal("400.0000"),
            last_cost=Decimal("400.0000"),
            is_active=True
        )

        db.add_all([tenant, branch, warehouse, currency, customer, cat, product, fac_serie])
        await db.commit()

        # Siembra del Catálogo de Cuentas Contables Anexo 24
        await seed_default_chart_of_accounts(db, tenant_id)

        # 2. Entrada de Inventario (Capa de Costo de 20 unidades a $400.00 c/u)
        await inventory_service.record_entry(
            db=db,
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            product_id=product.id,
            quantity=Decimal("20.00"),
            unit_cost=Decimal("400.00"),
            movement_type="ENTRADA_COMPRA",
            reference_type="COMPRA",
            reference_folio="OC-001"
        )

        # 3. Emitir Factura de Venta: 5 unidades a $1,000.00 c/u + 16% IVA
        # Subtotal = $5,000.00
        # IVA = $800.00
        # Total = $5,800.00
        # Costo de Ventas (COGS PEPS) = 5 * $400.00 = $2,000.00
        invoice_doc = await sales_service.create_sales_document(
            db=db,
            tenant_id=tenant_id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            customer_id=customer_id,
            currency_id=currency_id,
            document_type="FACTURA",
            payment_form="03",  # Transferencia
            payment_method="PUE",  # Contado
            items_input=[
                {
                    "product_id": product.id,
                    "quantity": Decimal("5.00"),
                    "unit_price": Decimal("1000.00"),
                    "vat_rate": Decimal("0.1600")
                }
            ]
        )

        assert invoice_doc.subtotal == Decimal("5000.00")
        assert invoice_doc.tax_iva_total == Decimal("800.00")
        assert invoice_doc.total == Decimal("5800.00")
        assert invoice_doc.total_cost_cogs == Decimal("2000.00")

        # 4. Verificar la Póliza Automática generada por el hook de Ventas
        stmt_entry = (
            select(JournalEntry)
            .where(
                JournalEntry.tenant_id == tenant_id,
                JournalEntry.source_module == "SALES",
                JournalEntry.source_id == invoice_doc.id
            )
            .options(selectinload(JournalEntry.lines).selectinload(JournalEntryLine.account))
        )
        res_entry = await db.execute(stmt_entry)
        entry = res_entry.scalar_one_or_none()

        assert entry is not None
        assert entry.source_folio == invoice_doc.formatted_folio
        
        # Validación de Partida Doble:
        # Cargos: Bancos ($5,800.00) + Costo de Ventas ($2,000.00) = $7,800.00
        # Abonos: Ventas ($5,000.00) + IVA Trasladado ($800.00) + Inventarios ($2,000.00) = $7,800.00
        assert entry.total_debit == Decimal("7800.00")
        assert entry.total_credit == Decimal("7800.00")
        assert len(entry.lines) == 5

        lines_by_acc = {l.account.account_number: l for l in entry.lines}
        
        # 1102 Bancos Nacionales (Cargo por el total pagado)
        assert lines_by_acc["1102"].debit == Decimal("5800.00")
        assert lines_by_acc["1102"].credit == Decimal("0.00")

        # 4101 Ventas Gravadas (Abono por subtotal)
        assert lines_by_acc["4101"].debit == Decimal("0.00")
        assert lines_by_acc["4101"].credit == Decimal("5000.00")

        # 2108 IVA Trasladado Cobrado (Abono por IVA)
        assert lines_by_acc["2108"].debit == Decimal("0.00")
        assert lines_by_acc["2108"].credit == Decimal("800.00")

        # 5101 Costo de Ventas (Cargo exacto por el costo PEPS)
        assert lines_by_acc["5101"].debit == Decimal("2000.00")
        assert lines_by_acc["5101"].credit == Decimal("0.00")

        # 1115 Inventarios (Abono exacto descargando el costo del activo)
        assert lines_by_acc["1115"].debit == Decimal("0.00")
        assert lines_by_acc["1115"].credit == Decimal("2000.00")


@pytest.mark.asyncio
async def test_financial_reporting_engine_pnl_and_balance_sheet():
    """
    Test 4: Valida la generación recursiva del Estado de Resultados (P&L) y Balance General,
    comprobando la ecuación fundamental de la contabilidad: Activo == Pasivo + Capital Contable.
    """
    engine, session_factory = await setup_accounting_test_db()
    async with session_factory() as db:
        tenant_id = uuid.uuid4()
        acc_map = await seed_default_chart_of_accounts(db, tenant_id)

        # 1. Asiento de Capital Inicial: $100,000.00 en Bancos
        await accounting_service.create_journal_entry(
            db=db,
            tenant_id=tenant_id,
            data=JournalEntryCreate(
                entry_type="INGRESO",
                entry_date=datetime.date.today(),
                concept="Capital Social Inicial",
                lines=[
                    JournalEntryLineCreate(account_id=acc_map["1102"].id, concept="Bancos", debit=Decimal("100000.00"), credit=Decimal("0.00")),
                    JournalEntryLineCreate(account_id=acc_map["3101"].id, concept="Capital Social", debit=Decimal("0.00"), credit=Decimal("100000.00"))
                ]
            )
        )

        # 2. Asiento de Operación:
        # Ventas: $30,000.00
        # Costo de Ventas: $12,000.00 (Salida de inventario)
        # Gasto Sueldos: $8,000.00 (Salida de bancos)
        # Ingreso a bancos por ventas: $30,000.00
        await accounting_service.create_journal_entry(
            db=db,
            tenant_id=tenant_id,
            data=JournalEntryCreate(
                entry_type="DIARIO",
                entry_date=datetime.date.today(),
                concept="Operaciones del mes",
                lines=[
                    JournalEntryLineCreate(account_id=acc_map["1102"].id, concept="Cobro ventas", debit=Decimal("30000.00"), credit=Decimal("0.00")),
                    JournalEntryLineCreate(account_id=acc_map["4101"].id, concept="Ventas", debit=Decimal("0.00"), credit=Decimal("30000.00")),
                    JournalEntryLineCreate(account_id=acc_map["5101"].id, concept="Costo de ventas", debit=Decimal("12000.00"), credit=Decimal("0.00")),
                    JournalEntryLineCreate(account_id=acc_map["1115"].id, concept="Descarga almacén", debit=Decimal("0.00"), credit=Decimal("12000.00")),
                    JournalEntryLineCreate(account_id=acc_map["6101"].id, concept="Gasto Sueldos", debit=Decimal("8000.00"), credit=Decimal("0.00")),
                    JournalEntryLineCreate(account_id=acc_map["1102"].id, concept="Pago nómina bancos", debit=Decimal("0.00"), credit=Decimal("8000.00")),
                ]
            )
        )

        today = datetime.date.today()

        # Verificar Estado de Resultados:
        # Ventas Netas: $30,000.00
        # Costo de Ventas: $12,000.00
        # Utilidad Bruta: $18,000.00 (Margen: 60%)
        # Gastos Operativos: $8,000.00
        # Utilidad Neta: $10,000.00
        pnl = await accounting_service.get_income_statement(db, tenant_id, start_date=today, end_date=today)
        assert pnl.net_sales == Decimal("30000.00")
        assert pnl.cost_of_goods_sold == Decimal("12000.00")
        assert pnl.gross_profit == Decimal("18000.00")
        assert pnl.gross_margin_percentage == Decimal("60.00")
        assert pnl.operating_expenses == Decimal("8000.00")
        assert pnl.net_income == Decimal("10000.00")

        # Verificar Balance General:
        # Activos:
        #   Bancos: 100,000 + 30,000 - 8,000 = 122,000.00
        #   Inventarios: -12,000.00 (sin saldo inicial)
        #   Total Activo = 110,000.00
        # Pasivos: 0.00
        # Capital Contable:
        #   Capital Social: 100,000.00
        #   Utilidad del Ejercicio: 10,000.00
        #   Total Capital = 110,000.00
        # Total Pasivo + Capital = 110,000.00 == Total Activo!
        bs = await accounting_service.get_balance_sheet(db, tenant_id, as_of_date=today)
        assert bs.total_assets == Decimal("110000.00")
        assert bs.total_liabilities == Decimal("0.00")
        assert bs.total_equity == Decimal("110000.00")
        assert bs.total_liabilities_and_equity == Decimal("110000.00")
        assert bs.is_balanced is True
