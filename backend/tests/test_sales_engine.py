import pytest
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.core.database import Base
from app.modules.auth.models import User
from app.modules.tenants.models import Tenant, Branch, FiscalFoliosSeries, CSDCertificate
from app.modules.master_data.models import Customer, Product, Warehouse, Currency
from app.modules.inventories.models import ProductWarehouseStock, KardexMovement, InventoryReservation
from app.modules.inventories.inventory_service import record_entry
from app.modules.sales.models import SalesDocument, SalesDocumentItem
from app.modules.sales.sales_service import (
    create_sales_document,
    convert_order_to_invoice,
    stamp_invoice_cfdi
)
from app.modules.fiscal_mexico.tax_engine import calculate_item_taxes, calculate_document_totals
from tests.test_csd_and_folios import generate_test_csd
from app.core.security import encrypt_csd_key


async def setup_sales_test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, session_factory


def test_complex_tax_arithmetic():
    """
    Valida el cálculo aritmético exacto de impuestos múltiples:
    - Base: $1,000.00
    - IVA Trasladado (16%): $160.00
    - IEPS Trasladado (8%): $80.00
    - Retención IVA (4%): -$40.00
    - Retención ISR (10%): -$100.00
    - Total Partida = 1000 + 160 + 80 - 40 - 100 = $1,100.00
    """
    item1 = calculate_item_taxes(
        quantity=Decimal("2.0000"),
        unit_price=Decimal("500.0000"),  # Gross = 1000
        discount_rate=Decimal("0.0000"),
        vat_rate=Decimal("0.1600"),
        ieps_rate=Decimal("0.0800"),
        retention_vat_rate=Decimal("0.0400"),
        retention_isr_rate=Decimal("0.1000"),
        sat_objeto_imp="02"
    )

    assert item1["subtotal"] == Decimal("1000.0000")
    assert item1["vat_amount"] == Decimal("160.0000")
    assert item1["ieps_amount"] == Decimal("80.0000")
    assert item1["retention_vat_amount"] == Decimal("40.0000")
    assert item1["retention_isr_amount"] == Decimal("100.0000")
    assert item1["total"] == Decimal("1100.0000")

    # Partida 2: Objeto Impuesto 01 (No objeto)
    item2 = calculate_item_taxes(
        quantity=Decimal("1.0000"),
        unit_price=Decimal("500.0000"),
        sat_objeto_imp="01"
    )
    assert item2["subtotal"] == Decimal("500.0000")
    assert item2["vat_amount"] == Decimal("0.0000")
    assert item2["total"] == Decimal("500.0000")

    totals = calculate_document_totals([item1, item2])
    assert totals["subtotal"] == Decimal("1500.00")
    assert totals["tax_iva_total"] == Decimal("160.00")
    assert totals["tax_ieps_total"] == Decimal("80.00")
    assert totals["retention_iva_total"] == Decimal("40.00")
    assert totals["retention_isr_total"] == Decimal("100.00")
    assert totals["total"] == Decimal("1600.00")


@pytest.mark.asyncio
async def test_order_to_invoice_inventory_flow():
    """
    Prueba de integración:
    1. Entrada a almacén de 50 unidades @ $100.00.
    2. Creación de Pedido por 20 unidades -> Genera reserva (Soft Allocation).
       Existencia física: 50, Apartada: 20, Disponible: 30.
    3. Conversión de Pedido a Factura:
       - Libera la reserva (Apartada = 0).
       - Descarga el inventario físico oficial en Kardex (Física = 30, Disponible = 30).
       - Evalúa el costo de lo vendido (COGS = 20 * 100 = $2,000.00).
       - Pedido cambia a estado 'SURTIDO'.
    """
    engine, async_db = await setup_sales_test_db()
    tenant_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    currency_id = uuid.uuid4()
    product_id = uuid.uuid4()

    async with async_db() as session:
        t = Tenant(id=tenant_id, rfc="EME200101XYZ", legal_name="EMPRESA MODELO", fiscal_regime_code="601", zip_code="06000")
        b = Branch(id=branch_id, tenant_id=tenant_id, code="SUC-01", name="Matriz", zip_code="06000")
        w = Warehouse(id=warehouse_id, tenant_id=tenant_id, code="ALM-01", name="Almacén Matriz")
        c = Customer(id=customer_id, tenant_id=tenant_id, code="CLI-01", rfc="XAXX010101000", legal_name="CLIENTE GENERAL", fiscal_regime_code="616", zip_code="06000")
        curr = Currency(id=currency_id, tenant_id=tenant_id, code="MXN", name="Peso Mexicano")
        p = Product(id=product_id, tenant_id=tenant_id, sku="SKU-VENTA", name="Producto para Venta", costing_method="PROMEDIO")

        # Series de Pedido y Factura
        f_ped = FiscalFoliosSeries(tenant_id=tenant_id, branch_id=branch_id, document_type="PEDIDO", serie="PED", current_folio=0, initial_folio=1)
        f_fac = FiscalFoliosSeries(tenant_id=tenant_id, branch_id=branch_id, document_type="FAC", serie="F", current_folio=0, initial_folio=1)

        session.add_all([t, b, w, c, curr, p, f_ped, f_fac])
        await session.commit()

        # Entrada inicial: 50 unidades @ $100.00
        await record_entry(session, tenant_id, warehouse_id, product_id, Decimal("50.0000"), Decimal("100.0000"))
        await session.commit()

    # Paso 2: Crear Pedido por 20 unidades
    async with async_db() as session:
        order = await create_sales_document(
            db=session,
            tenant_id=tenant_id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            customer_id=customer_id,
            currency_id=currency_id,
            document_type="PEDIDO",
            items_input=[{
                "product_id": product_id,
                "quantity": Decimal("20.0000"),
                "unit_price": Decimal("250.0000"),
                "vat_rate": Decimal("0.1600")
            }],
            approve_immediately=True
        )
        await session.commit()
        order_id = order.id
        assert order.status == "APROBADO"
        assert order.formatted_folio == "PED-1"

        # Verificar inventario: física=50, apartada=20, disponible=30
        stock = (await session.execute(select(ProductWarehouseStock).where(ProductWarehouseStock.product_id == product_id))).scalar_one()
        assert stock.physical_stock == Decimal("50.0000")
        assert stock.reserved_stock == Decimal("20.0000")
        assert stock.available_stock == Decimal("30.0000")

    # Paso 3: Convertir Pedido a Factura
    async with async_db() as session:
        invoice = await convert_order_to_invoice(
            db=session,
            tenant_id=tenant_id,
            order_id=order_id
        )
        await session.commit()

        assert invoice.document_type == "FACTURA"
        assert invoice.formatted_folio == "F-1"
        assert invoice.total_cost_cogs == Decimal("2000.0000")  # 20 * $100
        assert invoice.source_document_id == order_id

        # Verificar que el pedido cambió a SURTIDO
        ped = (await session.execute(select(SalesDocument).where(SalesDocument.id == order_id))).scalar_one()
        assert ped.status == "SURTIDO"

        # Verificar que la existencia física se descargó y el apartado se liberó:
        # física=30, apartada=0, disponible=30
        stock = (await session.execute(select(ProductWarehouseStock).where(ProductWarehouseStock.product_id == product_id))).scalar_one()
        assert stock.physical_stock == Decimal("30.0000")
        assert stock.reserved_stock == Decimal("0.0000")
        assert stock.available_stock == Decimal("30.0000")

        # Verificar movimiento en Kardex
        kardex = (await session.execute(select(KardexMovement).where(KardexMovement.product_id == product_id, KardexMovement.direction == "OUT"))).scalar_one()
        assert kardex.movement_type == "SALIDA_VENTA"
        assert kardex.quantity == Decimal("20.0000")
        assert kardex.total_cost == Decimal("2000.0000")

    await engine.dispose()


@pytest.mark.asyncio
async def test_cfdi_40_xml_and_digital_signature():
    """
    Valida la generación de la Cadena Original, el sellado criptográfico con CSD
    y la obtención del Timbre Fiscal Digital (UUID) simulado por el PAC.
    """
    engine, async_db = await setup_sales_test_db()
    tenant_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    currency_id = uuid.uuid4()
    product_id = uuid.uuid4()

    cer_bytes, key_bytes, _ = generate_test_csd(passphrase="TestPass123!", rfc="EME200101XYZ")
    from app.modules.fiscal_mexico.csd_service import validate_and_process_csd
    csd_proc = validate_and_process_csd(cer_bytes, key_bytes, "TestPass123!", expected_rfc="EME200101XYZ")

    async with async_db() as session:
        t = Tenant(id=tenant_id, rfc="EME200101XYZ", legal_name="EMPRESA MODELO SA DE CV", fiscal_regime_code="601", zip_code="06000")
        b = Branch(id=branch_id, tenant_id=tenant_id, code="SUC-01", name="Matriz", zip_code="06000")
        w = Warehouse(id=warehouse_id, tenant_id=tenant_id, code="ALM-01", name="Almacén Matriz")
        c = Customer(id=customer_id, tenant_id=tenant_id, code="CLI-01", rfc="XAXX010101000", legal_name="CLIENTE GENERAL PUBLICO", fiscal_regime_code="616", zip_code="06000")
        curr = Currency(id=currency_id, tenant_id=tenant_id, code="MXN", name="Peso Mexicano")
        p = Product(id=product_id, tenant_id=tenant_id, sku="SKU-TIMBRADO", name="Servicio de Consultoria", costing_method="PROMEDIO", product_type="SERVICIO")
        f_fac = FiscalFoliosSeries(tenant_id=tenant_id, branch_id=branch_id, document_type="FAC", serie="A", current_folio=0, initial_folio=1)

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

        session.add_all([t, b, w, c, curr, p, f_fac, csd])
        await session.commit()

        # Crear Factura directa
        invoice = await create_sales_document(
            db=session,
            tenant_id=tenant_id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            customer_id=customer_id,
            currency_id=currency_id,
            document_type="FACTURA",
            items_input=[{
                "product_id": product_id,
                "quantity": Decimal("1.0000"),
                "unit_price": Decimal("1000.0000"),
                "vat_rate": Decimal("0.1600"),
                "description": "Consultoría Estratégica"
            }]
        )
        await session.commit()
        inv_id = invoice.id

    # Timbrar
    async with async_db() as session:
        stamped_inv = await stamp_invoice_cfdi(session, tenant_id, inv_id)
        await session.commit()

        assert stamped_inv.status == "TIMBRADO"
        assert stamped_inv.cfdi_uuid is not None
        assert len(stamped_inv.cfdi_uuid) == 36
        assert "<cfdi:Comprobante" in stamped_inv.cfdi_xml
        assert "TimbreFiscalDigital" in stamped_inv.cfdi_xml
        assert stamped_inv.cfdi_sello is not None
        assert "||4.0|A|1|" in stamped_inv.cfdi_cadena_original

    await engine.dispose()
