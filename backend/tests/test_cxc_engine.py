import pytest
import uuid
from decimal import Decimal
from datetime import datetime, timezone, date, timedelta
from xml.etree import ElementTree as ET
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.core.database import Base
from app.modules.auth.models import User
from app.modules.tenants.models import Tenant, Branch, FiscalFoliosSeries, CSDCertificate
from app.modules.master_data.models import Customer, Product, Warehouse, Currency
from app.modules.sales.models import SalesDocument
from app.modules.cxc.models import ReceivableDocument, PaymentReceipt, PaymentReceiptDocRel
from app.modules.cxc.cxc_service import (
    calculate_proportional_taxes_rep,
    check_customer_credit_status,
    create_receivable_from_sales_document,
    get_customer_aging_analysis,
    apply_payment_receipt
)
from tests.test_csd_and_folios import generate_test_csd
from app.modules.fiscal_mexico.csd_service import validate_and_process_csd


async def setup_cxc_test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, session_factory


def test_rep_20_proportional_tax_arithmetic_penny_exact():
    """
    Valida que el motor fiscal SAT REP 2.0 calcule los impuestos proporcionales
    con exactitud matemática al centavo: BaseP + IVAP - RetencionesP = ImpPagado.
    """
    # Caso 1: Factura de $11,600.00 (Base $10,000, IVA 16% $1,600)
    # Pago Parcial: $3,500.00
    res1 = calculate_proportional_taxes_rep(
        original_subtotal=Decimal("10000.0000"),
        original_vat=Decimal("1600.0000"),
        original_ret_vat=Decimal("0.0000"),
        original_ret_isr=Decimal("0.0000"),
        original_total=Decimal("11600.0000"),
        amount_paid=Decimal("3500.0000")
    )
    assert res1["amount_paid"] == Decimal("3500.00")
    assert res1["proportional_base"] == Decimal("3017.24")
    assert res1["proportional_vat"] == Decimal("482.76")
    # Cuadre al centavo exacto
    assert res1["proportional_base"] + res1["proportional_vat"] == Decimal("3500.00")

    # Caso 2: Importe impar que suele generar desajustes de centavos: $1,234.56
    res2 = calculate_proportional_taxes_rep(
        original_subtotal=Decimal("10000.0000"),
        original_vat=Decimal("1600.0000"),
        original_ret_vat=Decimal("0.0000"),
        original_ret_isr=Decimal("0.0000"),
        original_total=Decimal("11600.0000"),
        amount_paid=Decimal("1234.5600")
    )
    assert res2["amount_paid"] == Decimal("1234.56")
    assert res2["proportional_base"] + res2["proportional_vat"] == Decimal("1234.56")

    # Caso 3: Factura con Retenciones de IVA y de ISR
    # Base = $1,000, IVA = $160, RetIVA(4%) = $40, RetISR(10%) = $100 -> Total = $1,020.00
    # Pago del 50%: $510.00
    res3 = calculate_proportional_taxes_rep(
        original_subtotal=Decimal("1000.0000"),
        original_vat=Decimal("1600.0000") / 10,  # 160
        original_ret_vat=Decimal("40.0000"),
        original_ret_isr=Decimal("100.0000"),
        original_total=Decimal("1020.0000"),
        amount_paid=Decimal("510.0000")
    )
    assert res3["amount_paid"] == Decimal("510.00")
    assert res3["proportional_base"] == Decimal("500.00")
    assert res3["proportional_vat"] == Decimal("80.00")
    assert res3["proportional_retention_vat"] == Decimal("20.00")
    assert res3["proportional_retention_isr"] == Decimal("50.00")
    # Base + IVA - RetIVA - RetISR == 510.00
    net = (
        res3["proportional_base"] +
        res3["proportional_vat"] -
        res3["proportional_retention_vat"] -
        res3["proportional_retention_isr"]
    )
    assert net == Decimal("510.00")


@pytest.mark.asyncio
async def test_credit_limit_and_overdue_invoice_rejections():
    """
    Valida el control de crédito y bloqueo en tiempo real:
    1. Si el saldo + nuevo pedido excede el límite de crédito -> Rechazado.
    2. Si tiene facturas vencidas fuera de plazo -> Rechazado automáticamente.
    """
    engine, session_factory = await setup_cxc_test_db()
    async with session_factory() as db:
        tenant_id = uuid.uuid4()
        branch_id = uuid.uuid4()
        customer_id = uuid.uuid4()

        tenant = Tenant(id=tenant_id, rfc="CXC850101XYZ", legal_name="EMPRESA CXC SA", fiscal_regime_code="601", zip_code="06000")
        branch = Branch(id=branch_id, tenant_id=tenant_id, code="SUC1", name="Matriz", zip_code="06000")

        # Cliente con Límite de Crédito de $5,000.00 y 15 días de plazo
        customer = Customer(
            id=customer_id,
            tenant_id=tenant_id,
            code="CLI-CRED",
            rfc="CLI850101XYZ",
            legal_name="CLIENTE CREDITO SA",
            fiscal_regime_code="601",
            zip_code="06000",
            credit_limit=Decimal("5000.00"),
            credit_days=15
        )
        db.add_all([tenant, branch, customer])
        await db.commit()

        # 1. Factura vigente de $3,500.00 (vence en 15 días)
        rec1 = ReceivableDocument(
            tenant_id=tenant_id,
            customer_id=customer_id,
            branch_id=branch_id,
            document_type="FACTURA",
            serie="F",
            folio=1,
            formatted_folio="F-1",
            issue_date=datetime.now(timezone.utc),
            due_date=date.today() + timedelta(days=15),
            credit_days=15,
            original_total=Decimal("3500.0000"),
            original_subtotal=Decimal("3017.2400"),
            original_vat=Decimal("482.7600"),
            current_balance=Decimal("3500.0000"),
            status="PENDIENTE"
        )
        db.add(rec1)
        await db.commit()

        # A) Intento de pedido por $2,000.00 -> Saldo proyectado = 3500 + 2000 = $5,500 > $5,000 límite -> RECHAZADO
        authorized, reason, _ = await check_customer_credit_status(
            db=db,
            tenant_id=tenant_id,
            customer_id=customer_id,
            attempted_amount=Decimal("2000.00")
        )
        assert authorized is False
        assert "Límite de crédito excedido" in reason

        # B) Intento de pedido por $1,000.00 -> Saldo proyectado = 3500 + 1000 = $4,500 <= $5,000 -> AUTORIZADO
        authorized, reason, _ = await check_customer_credit_status(
            db=db,
            tenant_id=tenant_id,
            customer_id=customer_id,
            attempted_amount=Decimal("1000.00")
        )
        assert authorized is True

        # 2. Ahora simulamos que la factura se venció (vencida hace 3 días)
        rec1.due_date = date.today() - timedelta(days=3)
        await db.commit()

        # C) Intento de venta de $100.00 (incluso muy por debajo del límite) -> RECHAZADO por vencimiento
        authorized, reason, overdue = await check_customer_credit_status(
            db=db,
            tenant_id=tenant_id,
            customer_id=customer_id,
            attempted_amount=Decimal("100.00")
        )
        assert authorized is False
        assert "vencido" in reason
        assert len(overdue) == 1
        assert overdue[0]["folio"] == "F-1"
        assert overdue[0]["days_overdue"] == 3


@pytest.mark.asyncio
async def test_rep_20_payment_application_and_cfdi_xml():
    """
    Valida la aplicación de pagos PPD y generación del Complemento de Pago REP 2.0:
    1. Factura original por $1,160.00 (Base: $1,000, IVA: $160).
    2. Aplicación de pago parcial 1 ($600.00):
       - Saldo restante: $560.00 (Estado: PARCIAL).
       - Parcialidad 1.
       - Impuestos proporcionales: Base $517.24, IVA $82.76.
       - Timbrado CFDI 4.0 tipo P con nodo <pago20:Pagos Version="2.0">.
    3. Aplicación de pago 2 ($560.00):
       - Saldo restante: $0.00 (Estado: LIQUIDADO).
       - Parcialidad 2.
    """
    engine, session_factory = await setup_cxc_test_db()
    async with session_factory() as db:
        tenant_id = uuid.uuid4()
        branch_id = uuid.uuid4()
        customer_id = uuid.uuid4()
        user_id = uuid.uuid4()

        tenant = Tenant(id=tenant_id, rfc="REP850101XYZ", legal_name="PAGOS SA DE CV", fiscal_regime_code="601", zip_code="06000")
        branch = Branch(id=branch_id, tenant_id=tenant_id, code="SUC1", name="Matriz", zip_code="06000")
        customer = Customer(id=customer_id, tenant_id=tenant_id, code="CLI1", rfc="CLI850101XYZ", legal_name="CLIENTE DE PRUEBA SA", fiscal_regime_code="601", zip_code="06000")
        user = User(id=user_id, email="cajero@rep.com", hashed_password="xxx", full_name="Cobrador")

        # Folios para Recibo de Pago
        folio_pago = FiscalFoliosSeries(
            tenant_id=tenant_id,
            branch_id=branch_id,
            document_type="PAGO",
            serie="PAGO",
            current_folio=0,
            initial_folio=1,
            final_folio=999999
        )

        # CSD Certificado
        cer_bytes, key_bytes, _ = generate_test_csd(passphrase="TestPass123!", rfc="REP850101XYZ")
        csd_proc = validate_and_process_csd(cer_bytes, key_bytes, "TestPass123!", expected_rfc="REP850101XYZ")
        csd = CSDCertificate(
            tenant_id=tenant_id,
            rfc=csd_proc["rfc"],
            certificate_number=csd_proc["certificate_number"],
            valid_from=csd_proc["valid_from"],
            valid_to=csd_proc["valid_to"],
            certificate_pem=csd_proc["certificate_pem"],
            encrypted_private_key=csd_proc["encrypted_private_key"],
            key_passphrase_hash=csd_proc["encrypted_passphrase"],
            is_active=True
        )

        # Factura original por cobrar
        invoice_uuid = str(uuid.uuid4())
        rec_doc = ReceivableDocument(
            tenant_id=tenant_id,
            customer_id=customer_id,
            branch_id=branch_id,
            document_type="FACTURA",
            serie="A",
            folio=100,
            formatted_folio="A-100",
            cfdi_uuid=invoice_uuid,
            issue_date=datetime.now(timezone.utc),
            due_date=date.today() + timedelta(days=30),
            credit_days=30,
            original_total=Decimal("1160.0000"),
            original_subtotal=Decimal("1000.0000"),
            original_vat=Decimal("160.0000"),
            current_balance=Decimal("1160.0000"),
            status="PENDIENTE"
        )
        db.add_all([tenant, branch, customer, user, folio_pago, csd, rec_doc])
        await db.commit()

        # --- PAGO 1: Abono Parcial de $600.00 ---
        p1 = await apply_payment_receipt(
            db=db,
            tenant_id=tenant_id,
            branch_id=branch_id,
            customer_id=customer_id,
            user_id=user_id,
            payment_form="03",  # Transferencia
            amount=Decimal("600.0000"),
            allocations=[{"receivable_id": rec_doc.id, "amount_paid": Decimal("600.0000")}],
            operation_number="SPEI-998877"
        )
        await db.commit()

        assert p1.status == "TIMBRADO"
        assert p1.formatted_folio == "PAGO-1"
        assert p1.cfdi_uuid is not None

        # Validaciones de la Factura y del DoctoRelacionado
        await db.refresh(rec_doc)
        assert rec_doc.current_balance == Decimal("560.0000")
        assert rec_doc.status == "PARCIAL"

        doc_rel1 = (
            await db.execute(
                select(PaymentReceiptDocRel).where(PaymentReceiptDocRel.payment_receipt_id == p1.id)
            )
        ).scalars().first()
        assert doc_rel1 is not None
        assert doc_rel1.installment_number == 1
        assert doc_rel1.previous_balance == Decimal("1160.0000")
        assert doc_rel1.amount_paid == Decimal("600.0000")
        assert doc_rel1.remaining_balance == Decimal("560.0000")
        assert doc_rel1.proportional_base + doc_rel1.proportional_vat == Decimal("600.0000")

        # Validar Estructura XML del CFDI 4.0 con Complemento de Pagos 2.0
        xml_root = ET.fromstring(p1.cfdi_xml)
        ns = {
            "cfdi": "http://www.sat.gob.mx/cfd/4",
            "pago20": "http://www.sat.gob.mx/Pagos20"
        }
        assert xml_root.attrib["TipoDeComprobante"] == "P"
        assert xml_root.attrib["Total"] == "0"

        pagos_node = xml_root.find(".//pago20:Pagos", ns)
        assert pagos_node is not None
        assert pagos_node.attrib["Version"] == "2.0"

        docto_node = xml_root.find(".//pago20:DoctoRelacionado", ns)
        assert docto_node is not None
        assert docto_node.attrib["IdDocumento"] == invoice_uuid
        assert docto_node.attrib["NumParcialidad"] == "1"
        assert docto_node.attrib["ImpSaldoAnt"] == "1160.00"
        assert docto_node.attrib["ImpPagado"] == "600.00"
        assert docto_node.attrib["ImpSaldoInsoluto"] == "560.00"

        # --- PAGO 2: Liquidación Final de $560.00 ---
        p2 = await apply_payment_receipt(
            db=db,
            tenant_id=tenant_id,
            branch_id=branch_id,
            customer_id=customer_id,
            user_id=user_id,
            payment_form="01",  # Efectivo
            amount=Decimal("560.0000"),
            allocations=[{"receivable_id": rec_doc.id, "amount_paid": Decimal("560.0000")}]
        )
        await db.commit()

        await db.refresh(rec_doc)
        assert rec_doc.current_balance == Decimal("0.0000")
        assert rec_doc.status == "LIQUIDADO"

        doc_rel2 = (
            await db.execute(
                select(PaymentReceiptDocRel).where(PaymentReceiptDocRel.payment_receipt_id == p2.id)
            )
        ).scalars().first()
        assert doc_rel2 is not None
        assert doc_rel2.installment_number == 2
        assert doc_rel2.previous_balance == Decimal("560.0000")
        assert doc_rel2.amount_paid == Decimal("560.0000")
        assert doc_rel2.remaining_balance == Decimal("0.0000")
