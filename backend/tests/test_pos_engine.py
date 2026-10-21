import pytest
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from xml.etree import ElementTree as ET
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.core.database import Base
from app.modules.auth.models import User
from app.modules.tenants.models import Tenant, Branch, FiscalFoliosSeries, CSDCertificate
from app.modules.master_data.models import Customer, Product, Warehouse, Currency
from app.modules.inventories.models import ProductWarehouseStock, KardexMovement
from app.modules.inventories.inventory_service import record_entry, get_or_create_stock
from app.modules.pos.models import CashRegister, CashSession, CashMovement, POSTicket, POSTicketItem
from app.modules.pos.pos_service import (
    open_cash_session,
    record_cash_movement,
    get_corte_x,
    close_corte_z,
    create_pos_ticket
)
from app.modules.pos.global_invoice_service import (
    calculate_global_invoice_breakdown,
    generate_global_invoice
)
from tests.test_csd_and_folios import generate_test_csd
from app.modules.fiscal_mexico.csd_service import validate_and_process_csd


async def setup_pos_test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, session_factory


@pytest.mark.asyncio
async def test_cash_session_lifecycle_and_corte_z():
    """
    Valida el ciclo de vida del turno de caja:
    1. Apertura con fondo inicial de $1,000.00.
    2. Bloqueo de apertura simultánea si ya hay turno abierto.
    3. Movimiento de entrada de cambio (+$200.00).
    4. Movimiento de retiro de seguridad (-$150.00).
    5. Lectura de Corte X (Esperado: $1,050.00).
    6. Corte Z a ciegas: Cajero declara $1,040.00 (Faltante registrado: -$10.00).
    """
    engine, session_factory = await setup_pos_test_db()
    async with session_factory() as db:
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        branch_id = uuid.uuid4()
        warehouse_id = uuid.uuid4()

        # Seed datos básicos
        tenant = Tenant(
            id=tenant_id,
            rfc="POS850101XYZ",
            legal_name="POS SA DE CV",
            fiscal_regime_code="601",
            zip_code="06000"
        )
        branch = Branch(
            id=branch_id,
            tenant_id=tenant_id,
            code="SUC1",
            name="Sucursal Matriz",
            zip_code="06000"
        )
        warehouse = Warehouse(
            id=warehouse_id,
            tenant_id=tenant_id,
            branch_id=branch_id,
            code="ALM1",
            name="Almacén Tienda"
        )
        user = User(
            id=user_id,
            email="cajero@pos.com",
            hashed_password="xxx",
            full_name="Cajero 1"
        )
        cash_register = CashRegister(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            code="CAJA-01",
            name="Caja Principal"
        )
        db.add_all([tenant, branch, warehouse, user, cash_register])
        await db.commit()

        # 1. Apertura con fondo inicial
        session = await open_cash_session(
            db=db,
            tenant_id=tenant_id,
            cash_register_id=cash_register.id,
            user_id=user_id,
            initial_cash=Decimal("1000.0000"),
            notes="Apertura turno matutino"
        )
        await db.commit()

        assert session.status == "OPEN"
        assert session.initial_cash == Decimal("1000.0000")
        assert session.expected_cash == Decimal("1000.0000")

        # 2. Impedir abrir otro turno en la misma caja
        with pytest.raises(HTTPException) as exc_info:
            await open_cash_session(
                db=db,
                tenant_id=tenant_id,
                cash_register_id=cash_register.id,
                user_id=user_id,
                initial_cash=Decimal("500.0000")
            )
        assert exc_info.value.status_code == 400
        assert "turno abierto" in exc_info.value.detail.lower()

        # 3. Movimiento de entrada de cambio (+$200.00)
        mov_in = await record_cash_movement(
            db=db,
            tenant_id=tenant_id,
            session_id=session.id,
            user_id=user_id,
            movement_type="ENTRY",
            amount=Decimal("200.0000"),
            reason="Dotación de monedas de $10 y billetes de $20"
        )
        await db.commit()
        assert mov_in.amount == Decimal("200.0000")
        assert session.expected_cash == Decimal("1200.0000")

        # 4. Movimiento de retiro de seguridad (-$150.00)
        mov_out = await record_cash_movement(
            db=db,
            tenant_id=tenant_id,
            session_id=session.id,
            user_id=user_id,
            movement_type="WITHDRAWAL",
            amount=Decimal("150.0000"),
            reason="Retiro a caja fuerte por límite de efectivo"
        )
        await db.commit()
        assert mov_out.amount == Decimal("150.0000")
        assert session.expected_cash == Decimal("1050.0000")

        # 5. Corte X (Lectura Parcial)
        corte_x = await get_corte_x(db=db, tenant_id=tenant_id, session_id=session.id)
        assert corte_x["initial_cash"] == Decimal("1000.0000")
        assert corte_x["cash_entries"] == Decimal("200.0000")
        assert corte_x["cash_withdrawals"] == Decimal("150.0000")
        assert corte_x["expected_cash"] == Decimal("1050.0000")

        # 6. Corte Z (Cierre definitivo a ciegas)
        # Cajero cuenta y declara $1,040.00 en efectivo (Faltante de $10.00)
        closed_session = await close_corte_z(
            db=db,
            tenant_id=tenant_id,
            session_id=session.id,
            user_id=user_id,
            declared_cash=Decimal("1040.0000"),
            declared_card=Decimal("0.0000"),
            notes="Faltante de $10 pesos por redondeo en cambio"
        )
        await db.commit()

        assert closed_session.status == "CLOSED"
        assert closed_session.expected_cash == Decimal("1050.0000")
        assert closed_session.declared_cash == Decimal("1040.0000")
        assert closed_session.difference_cash == Decimal("-10.0000")  # Faltante auditado


@pytest.mark.asyncio
async def test_pos_ticket_issuance_and_kardex_discharge():
    """
    Valida la emisión de un ticket de alta velocidad:
    1. Falla si la caja no tiene turno abierto.
    2. Con turno abierto: consume folio TICK, descarga existencia Kardex, calcula cambio.
    """
    engine, session_factory = await setup_pos_test_db()
    async with session_factory() as db:
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        branch_id = uuid.uuid4()
        warehouse_id = uuid.uuid4()

        tenant = Tenant(
            id=tenant_id,
            rfc="TICK850101XYZ",
            legal_name="TIENDA POS SA",
            fiscal_regime_code="601",
            zip_code="06000"
        )
        branch = Branch(
            id=branch_id,
            tenant_id=tenant_id,
            code="SUC1",
            name="Sucursal 1",
            zip_code="06000"
        )
        warehouse = Warehouse(
            id=warehouse_id,
            tenant_id=tenant_id,
            branch_id=branch_id,
            code="W01",
            name="Piso Venta"
        )
        user = User(
            id=user_id,
            email="pos@pos.com",
            hashed_password="xxx",
            full_name="Cajero"
        )
        cash_register = CashRegister(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            code="CAJA-01",
            name="Caja Principal"
        )
        # Folio series para tickets
        folio_series = FiscalFoliosSeries(
            tenant_id=tenant_id,
            branch_id=branch_id,
            document_type="TICK",
            serie="TICK",
            current_folio=0,
            initial_folio=1,
            final_folio=999999
        )
        # Producto con stock inicial
        product = Product(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            sku="REFRESCO-600",
            name="Refresco Cola 600ml",
            product_type="PRODUCTO",
            unit_name="PZA",
            sat_clave_unidad="H87",
            sat_clave_prod_serv="50202306",
            costing_method="PROMEDIO"
        )
        db.add_all([tenant, branch, warehouse, user, cash_register, folio_series, product])
        await db.commit()

        # Entrada inicial de 20 piezas @ $15.00 c/u
        await record_entry(
            db=db,
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            product_id=product.id,
            quantity=Decimal("20.0000"),
            unit_cost=Decimal("15.0000"),
            movement_type="ENTRADA_COMPRA",
            reference_folio="FAC-INIT",
            user_id=user_id
        )
        await db.commit()

        # 1. Intentar emitir ticket con sesión cerrada/inexistente -> Debe fallar
        fake_session_id = uuid.uuid4()
        with pytest.raises(HTTPException) as exc_info:
            await create_pos_ticket(
                db=db,
                tenant_id=tenant_id,
                session_id=fake_session_id,
                items_input=[{"product_id": product.id, "quantity": Decimal("2.0000"), "unit_price": Decimal("25.0000")}],
                payment_method="EFECTIVO",
                amount_paid=Decimal("50.0000")
            )
        assert exc_info.value.status_code == 400
        assert "cerrada" in exc_info.value.detail.lower()

        # 2. Abrir turno de caja con $500.00
        session = await open_cash_session(
            db=db,
            tenant_id=tenant_id,
            cash_register_id=cash_register.id,
            user_id=user_id,
            initial_cash=Decimal("500.0000")
        )
        await db.commit()

        # 3. Emitir ticket de 2 refrescos @ $25.00 público = $50.00 total.
        # Cliente paga con billete de $100.00 (Cambio esperado: $50.00).
        ticket = await create_pos_ticket(
            db=db,
            tenant_id=tenant_id,
            session_id=session.id,
            items_input=[{
                "product_id": product.id,
                "quantity": Decimal("2.0000"),
                "unit_price": Decimal("25.0000")
            }],
            payment_method="EFECTIVO",
            amount_paid=Decimal("100.0000"),
            user_id=user_id
        )
        await db.commit()

        # Validaciones del Ticket
        assert ticket.formatted_folio == "TICK-1"
        assert ticket.status == "PAID"
        assert ticket.total == Decimal("50.0000")
        assert ticket.amount_paid == Decimal("100.0000")
        assert ticket.change_returned == Decimal("50.0000")
        assert ticket.total_cost_cogs == Decimal("30.0000")  # 2 piezas * $15.00 costo

        # Validar afectación del Kardex
        stock = await get_or_create_stock(db, tenant_id, warehouse_id, product.id, for_update=False)
        assert stock.physical_stock == Decimal("18.0000")  # 20 - 2 = 18

        # Validar actualización en la sesión de caja
        assert session.expected_cash == Decimal("550.0000")  # $500 inicial + $50 venta
        assert session.total_sales == Decimal("50.0000")
        assert session.tickets_count == 1


@pytest.mark.asyncio
async def test_global_invoice_cfdi_40_generation():
    """
    Valida la generación del CFDI 4.0 Global (Público en General):
    1. Desglose inverso de IVA (Base + IVA = Total).
    2. Nodo <cfdi:InformacionGlobal Periodicidad="01" Meses="10" Año="2026"/>.
    3. Receptor genérico SAT RFC XAXX010101000 con UsoCFDI S01 y Régimen 616.
    4. Sellado criptográfico con CSD y Timbrado Mock PAC.
    """
    engine, session_factory = await setup_pos_test_db()
    async with session_factory() as db:
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        branch_id = uuid.uuid4()
        warehouse_id = uuid.uuid4()

        tenant = Tenant(
            id=tenant_id,
            rfc="GBL850101XYZ",
            legal_name="GLOBAL STORE SA DE CV",
            fiscal_regime_code="601",
            zip_code="06000"
        )
        branch = Branch(
            id=branch_id,
            tenant_id=tenant_id,
            code="SUC1",
            name="Sucursal Matriz",
            zip_code="06000"
        )
        warehouse = Warehouse(
            id=warehouse_id,
            tenant_id=tenant_id,
            branch_id=branch_id,
            code="W01",
            name="Almacén"
        )
        user = User(
            id=user_id,
            email="pos@global.com",
            hashed_password="xxx",
            full_name="Cajero"
        )
        currency = Currency(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            code="MXN",
            name="Peso Mexicano",
            symbol="$",
            is_base=True
        )

        cash_register = CashRegister(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            code="CAJA-01",
            name="Caja Principal"
        )
        # Folio series para Factura
        fac_folio = FiscalFoliosSeries(
            tenant_id=tenant_id,
            branch_id=branch_id,
            document_type="FAC",
            serie="FGLOB",
            current_folio=0,
            initial_folio=1,
            final_folio=999999
        )
        
        # CSD Certificado para timbrado
        cer_bytes, key_bytes, _ = generate_test_csd(passphrase="TestPass123!", rfc="GBL850101XYZ")
        csd_proc = validate_and_process_csd(cer_bytes, key_bytes, "TestPass123!", expected_rfc="GBL850101XYZ")

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

        # Crear sesión y tickets simulados
        session = CashSession(
            tenant_id=tenant_id,
            cash_register_id=cash_register.id,
            user_id=user_id,
            status="OPEN",
            initial_cash=Decimal("500.0000")
        )
        db.add_all([tenant, branch, warehouse, user, currency, cash_register, fac_folio, csd, session])
        await db.commit()

        # Ticket 1: $116.00 (Base: $100.00, IVA: $16.00)
        t1 = POSTicket(
            tenant_id=tenant_id,
            cash_session_id=session.id,
            cash_register_id=cash_register.id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            customer_id=uuid.uuid4(),
            user_id=user_id,
            serie="TICK",
            folio=1,
            formatted_folio="TICK-1",
            status="PAID",
            subtotal=Decimal("100.0000"),
            tax_iva_total=Decimal("16.0000"),
            total=Decimal("116.0000"),
            payment_method="EFECTIVO",
            amount_paid=Decimal("116.0000"),
            is_globally_invoiced=False
        )
        # Ticket 2: $232.00 (Base: $200.00, IVA: $32.00)
        t2 = POSTicket(
            tenant_id=tenant_id,
            cash_session_id=session.id,
            cash_register_id=cash_register.id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            customer_id=uuid.uuid4(),
            user_id=user_id,
            serie="TICK",
            folio=2,
            formatted_folio="TICK-2",
            status="PAID",
            subtotal=Decimal("200.0000"),
            tax_iva_total=Decimal("32.0000"),
            total=Decimal("232.0000"),
            payment_method="TARJETA",
            amount_paid=Decimal("232.0000"),
            is_globally_invoiced=False
        )
        db.add_all([t1, t2])
        await db.commit()

        # 1. Validar función pura de desglose normativo
        breakdown = calculate_global_invoice_breakdown([t1, t2])
        assert breakdown["total"] == Decimal("348.00")
        assert breakdown["subtotal"] == Decimal("300.00")
        assert breakdown["vat"] == Decimal("48.00")
        assert len(breakdown["conceptos"]) == 2

        # 2. Generar Factura Global CFDI 4.0
        global_invoice = await generate_global_invoice(
            db=db,
            tenant_id=tenant_id,
            branch_id=branch_id,
            periodicity="01",  # Diaria
            months="10",
            year=2026,
            ticket_ids=[t1.id, t2.id]
        )
        await db.commit()

        # Validaciones de Factura Global
        assert global_invoice.status == "TIMBRADO"
        assert global_invoice.formatted_folio == "FGLOB-1"
        assert global_invoice.total == Decimal("348.00")
        assert global_invoice.subtotal == Decimal("300.00")
        assert global_invoice.tax_iva_total == Decimal("48.00")
        assert global_invoice.cfdi_uuid is not None

        # Validaciones en el XML timbrado
        xml_root = ET.fromstring(global_invoice.cfdi_xml)
        ns = {"cfdi": "http://www.sat.gob.mx/cfd/4"}

        # Verificar InformacionGlobal
        info_global = xml_root.find("cfdi:InformacionGlobal", ns)
        assert info_global is not None
        assert info_global.attrib["Periodicidad"] == "01"
        assert info_global.attrib["Meses"] == "10"
        assert info_global.attrib["Año"] == "2026"

        # Verificar Receptor Público en General
        receptor = xml_root.find("cfdi:Receptor", ns)
        assert receptor.attrib["Rfc"] == "XAXX010101000"
        assert receptor.attrib["Nombre"] == "PUBLICO EN GENERAL"
        assert receptor.attrib["UsoCFDI"] == "S01"
        assert receptor.attrib["RegimenFiscalReceptor"] == "616"

        # Validar que los tickets quedaron marcados como facturados
        await db.refresh(t1)
        await db.refresh(t2)
        assert t1.is_globally_invoiced is True
        assert t1.global_invoice_id == global_invoice.id
        assert t2.is_globally_invoiced is True
        assert t2.global_invoice_id == global_invoice.id

