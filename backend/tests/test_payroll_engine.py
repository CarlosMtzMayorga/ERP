import pytest
import uuid
import datetime
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import Base
from app.modules.tenants.models import Tenant, Branch, FiscalFoliosSeries, CSDCertificate
from app.modules.auth.models import User
from app.modules.master_data.models import Currency, BankAccount
from app.modules.banking.models import BankTransaction
from app.modules.payroll.models import (
    Employee,
    PayrollPeriod,
    PayrollIncident,
    PayrollReceipt,
    PayrollReceiptItem
)
from app.modules.payroll.fiscal_engine import (
    calculate_isr_retention,
    calculate_imss_employee_retention,
    calculate_employee_payroll,
    quantize_2
)
from app.modules.payroll.schemas import (
    EmployeeCreate,
    PayrollPeriodCreate,
    DisbursePayrollRequest
)
from app.modules.payroll import payroll_service
from tests.test_csd_and_folios import generate_test_csd


async def setup_payroll_test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, session_factory


def test_fiscal_engine_exact_isr_and_imss_math():
    """
    Test 1: Verifica que el motor calcula exactamente la retención de ISR (Art. 96 LISR)
    y la cuota obrera del IMSS con base en un SDI y días laborados específicos.
    """
    # Escenario 1: Sueldo quincenal base = $7,500.00 (15 días a $500.00/día)
    taxable_base = Decimal("7500.00")
    days = Decimal("15.00")
    isr = calculate_isr_retention(taxable_base, days=days)
    # Límite inferior: 6,471.46, Cuota fija: 591.79, Tasa: 17.92%
    # Excedente = 1,028.54 * 0.1792 = 184.314368 -> Total = 776.10
    assert isr == Decimal("776.10")

    # Escenario 2: IMSS Cuota Obrera con SDI = $524.50 por 15 días
    # Base fija (2.375%): 524.50 * 0.02375 = 12.456875
    # Excedente 3 UMA (0.40%): (524.50 - 325.71) * 0.0040 = 0.79516
    # Diario = 13.252035 * 15 = 198.780525 -> Cuota = 198.78
    sdi = Decimal("524.50")
    imss = calculate_imss_employee_retention(sdi, days=days)
    assert imss == Decimal("198.78")

    # Escenario 3: Liquidación integral del empleado
    calc = calculate_employee_payroll(
        daily_salary=Decimal("500.00"),
        integrated_daily_salary=Decimal("524.50"),
        period_days=Decimal("15.00"),
        incidents=[]
    )
    assert calc["days_worked"] == Decimal("15.00")
    assert calc["days_paid"] == Decimal("15.00")
    assert calc["base_salary"] == Decimal("7500.00")
    assert calc["total_perceptions"] == Decimal("7500.00")
    assert calc["isr_retention"] == Decimal("776.10")
    assert calc["imss_employee_retention"] == Decimal("198.78")
    assert calc["total_deductions"] == Decimal("974.88")  # 776.10 + 198.78
    assert calc["total_net"] == Decimal("6525.12")  # 7500.00 - 974.88


@pytest.mark.asyncio
async def test_payroll_disbursement_decreases_bank_balance_and_blocks_overdraft():
    """
    Test 2: Verifica que la dispersión de nómina impacta el libro mayor de bancos,
    disminuyendo el saldo de la chequera patronal, y que el control anti-sobregiro
    bloquea la dispersión si la cuenta bancaria no tiene fondos suficientes.
    """
    engine, session_factory = await setup_payroll_test_db()
    async with session_factory() as db:
        tenant_id = uuid.uuid4()
        branch_id = uuid.uuid4()

        branch = Branch(id=branch_id, tenant_id=tenant_id, code="SUC-01", name="Matriz", zip_code="06000")
        currency = Currency(id=uuid.uuid4(), tenant_id=tenant_id, code="MXN", name="Peso Mexicano", exchange_rate=Decimal("1.0000"), is_base=True)

        # Cuenta bancaria patronal con saldo de $10,000.00 MXN
        bank_acc = BankAccount(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            bank_name="BBVA México",
            account_number="0123456789",
            clabe="012180001234567890",
            currency_id=currency.id,
            current_balance=Decimal("10000.00"),
            reconciled_balance=Decimal("0.00"),
            is_active=True
        )

        # Empleado
        emp = Employee(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            code="EMP-001",
            first_name="Juan",
            last_name="Pérez",
            rfc="PERJ800101XYZ",
            curp="PERJ800101HDFRRN01",
            nss="12345678901",
            zip_code="06000",
            daily_salary=Decimal("500.0000"),
            integrated_daily_salary=Decimal("524.5000"),
            status="ACTIVO",
            is_active=True
        )

        db.add_all([branch, currency, bank_acc, emp])
        await db.commit()

        # Crear y calcular periodo de nómina (Neto calculado = $6,525.12)
        period_data = PayrollPeriodCreate(
            name="Quincena 1 Octubre",
            payroll_type="O",
            periodicity="04",
            start_date=datetime.date(2026, 10, 1),
            end_date=datetime.date(2026, 10, 15),
            payment_date=datetime.date(2026, 10, 15),
            days_paid=Decimal("15.00")
        )
        period = await payroll_service.create_payroll_period(db, tenant_id, period_data)
        period = await payroll_service.calculate_payroll_period(db, tenant_id, period.id)
        assert period.total_net == Decimal("6525.12")
        assert period.status == "CALCULADA"

        # CASO A: Dispersión exitosa (Fondos suficientes: $10,000.00 >= $6,525.12)
        res_disb = await payroll_service.disburse_payroll(
            db=db,
            tenant_id=tenant_id,
            period_id=period.id,
            bank_account_id=bank_acc.id,
            notes="Dispersión Q1 Octubre"
        )
        assert res_disb["disbursed_net_amount"] == Decimal("6525.12")

        # Verificar saldo remanente en banco: 10,000.00 - 6,525.12 = 3,474.88
        await db.refresh(bank_acc)
        assert bank_acc.current_balance == Decimal("3474.88")

        # Verificar que se generó la transacción de salida en el libro mayor bancario
        stmt_tx = select(BankTransaction).where(
            BankTransaction.tenant_id == tenant_id,
            BankTransaction.bank_account_id == bank_acc.id,
            BankTransaction.reference_id == period.id
        )
        tx_res = await db.execute(stmt_tx)
        tx = tx_res.scalar_one_or_none()
        assert tx is not None
        assert tx.direction == "OUT"
        assert tx.transaction_type == "RETIRO"
        assert tx.amount == Decimal("6525.12")
        assert tx.new_balance == Decimal("3474.88")

        # CASO B: Control anti-sobregiro (Overdraft block)
        # Crear segundo periodo idéntico con neto $6,525.12
        # El banco ahora solo tiene $3,474.88 disponible -> Debe abortar con HTTP 400
        period2_data = PayrollPeriodCreate(
            name="Quincena 2 Octubre",
            payroll_type="O",
            periodicity="04",
            start_date=datetime.date(2026, 10, 16),
            end_date=datetime.date(2026, 10, 31),
            payment_date=datetime.date(2026, 10, 31),
            days_paid=Decimal("15.00")
        )
        period2 = await payroll_service.create_payroll_period(db, tenant_id, period2_data)
        period2 = await payroll_service.calculate_payroll_period(db, tenant_id, period2.id)

        with pytest.raises(HTTPException) as exc_info:
            await payroll_service.disburse_payroll(
                db=db,
                tenant_id=tenant_id,
                period_id=period2.id,
                bank_account_id=bank_acc.id
            )
        assert exc_info.value.status_code == 400
        assert "insuficiente" in exc_info.value.detail.lower()

        # Saldo bancario intacto
        await db.refresh(bank_acc)
        assert bank_acc.current_balance == Decimal("3474.88")


@pytest.mark.asyncio
async def test_payroll_batch_stamping_cfdi_12_with_csd_and_pac():
    """
    Test 3: Valida el Timbrado en Lote de los recibos de nómina CFDI 4.0 con Complemento
    de Nómina 1.2 sellado criptográficamente con CSD en memoria y firmado por el PAC SAT.
    """
    engine, session_factory = await setup_payroll_test_db()
    async with session_factory() as db:
        tenant_id = uuid.uuid4()
        branch_id = uuid.uuid4()
        demo_rfc = "EME200101XYZ"

        tenant = Tenant(
            id=tenant_id,
            rfc=demo_rfc,
            legal_name="EMPRESA MODELO SA DE CV",
            fiscal_regime_code="601",
            zip_code="06000"
        )
        branch = Branch(id=branch_id, tenant_id=tenant_id, code="SUC-01", name="Matriz", zip_code="06000")

        # Generar CSD criptográfico
        from app.modules.fiscal_mexico.csd_service import validate_and_process_csd
        cer_bytes, key_bytes, _ = generate_test_csd(passphrase="Secret123!", rfc=demo_rfc)
        csd_dict = validate_and_process_csd(
            cer_bytes=cer_bytes,
            key_bytes=key_bytes,
            passphrase="Secret123!",
            expected_rfc=demo_rfc
        )
        csd = CSDCertificate(
            tenant_id=tenant_id,
            rfc=demo_rfc,
            certificate_number=csd_dict["certificate_number"],
            valid_from=csd_dict["valid_from"],
            valid_to=csd_dict["valid_to"],
            certificate_pem=csd_dict["certificate_pem"],
            encrypted_private_key=csd_dict["encrypted_private_key"],
            key_passphrase_hash="hash",
            is_active=True
        )

        emp = Employee(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            code="EMP-001",
            first_name="Laura",
            last_name="Gómez",
            rfc="GOML900101ABC",
            curp="GOML900101MDFRR01",
            nss="98765432109",
            zip_code="06000",
            daily_salary=Decimal("600.0000"),
            integrated_daily_salary=Decimal("629.4000"),
            status="ACTIVO",
            is_active=True
        )

        db.add_all([tenant, branch, csd, emp])
        await db.commit()

        # Crear y calcular periodo
        period_data = PayrollPeriodCreate(
            name="Quincena Timbrado Test",
            payroll_type="O",
            periodicity="04",
            start_date=datetime.date(2026, 10, 1),
            end_date=datetime.date(2026, 10, 15),
            payment_date=datetime.date(2026, 10, 15),
            days_paid=Decimal("15.00")
        )
        period = await payroll_service.create_payroll_period(db, tenant_id, period_data)
        period = await payroll_service.calculate_payroll_period(db, tenant_id, period.id)

        # Timbrado en lote
        stamp_res = await payroll_service.batch_stamp_payroll_period(db, tenant_id, period.id)
        assert stamp_res.total_receipts == 1
        assert stamp_res.stamped_count == 1
        assert stamp_res.errors_count == 0
        assert len(stamp_res.stamped_uuids) == 1

        # Verificar recibo individual
        stmt_rec = select(PayrollReceipt).where(PayrollReceipt.payroll_period_id == period.id)
        res_rec = await db.execute(stmt_rec)
        receipt = res_rec.scalar_one()

        assert receipt.status == "TIMBRADO"
        assert receipt.cfdi_uuid is not None
        assert "nomina12:Nomina" in receipt.xml_cfdi
        assert "cfdi:Comprobante" in receipt.xml_cfdi
        assert "tfd:TimbreFiscalDigital" in receipt.xml_cfdi
        assert receipt.sello_digital is not None
        assert receipt.sello_sat is not None


@pytest.mark.asyncio
async def test_payroll_incident_faltas_decreases_paid_days_and_salary():
    """
    Test 4: Verifica que las faltas registradas en la prenómina descuentan exactamente
    los días pagados y reducen proporcionalmente la base del sueldo y las retenciones.
    """
    # 15 días normales: Sueldo $7,500.00
    calc_sin_faltas = calculate_employee_payroll(
        daily_salary=Decimal("500.00"),
        integrated_daily_salary=Decimal("524.50"),
        period_days=Decimal("15.00"),
        incidents=[]
    )
    assert calc_sin_faltas["days_paid"] == Decimal("15.00")
    assert calc_sin_faltas["base_salary"] == Decimal("7500.00")

    # 15 días con 3 faltas injustificadas: Días pagados = 12 días
    # Sueldo = 12 * 500 = $6,000.00
    calc_con_faltas = calculate_employee_payroll(
        daily_salary=Decimal("500.00"),
        integrated_daily_salary=Decimal("524.50"),
        period_days=Decimal("15.00"),
        incidents=[{"incident_type": "FALTA_INJUSTIFICADA", "quantity": Decimal("3.00"), "amount": 0}]
    )
    assert calc_con_faltas["days_paid"] == Decimal("12.00")
    assert calc_con_faltas["base_salary"] == Decimal("6000.00")
    assert calc_con_faltas["total_perceptions"] == Decimal("6000.00")
    # Al disminuir el ingreso de 7500 a 6000, la retención de ISR disminuye automáticamente
    assert calc_con_faltas["isr_retention"] < calc_sin_faltas["isr_retention"]

