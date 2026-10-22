import pytest
import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta, date
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import Base
from app.modules.tenants.models import Tenant, Branch, FiscalFoliosSeries
from app.modules.auth.models import User
from app.modules.master_data.models import Currency, Warehouse, Product, Supplier
from app.modules.inventories.models import ProductWarehouseStock, KardexMovement, CostLayer
from app.modules.purchases.models import PurchaseDocument, PurchaseDocumentItem, PayableDocument
from app.modules.purchases.schemas import (
    PurchaseOrderCreate,
    PurchaseItemCreate,
    GoodsReceptionCreate,
    GoodsReceptionItemCreate,
    SupplierInvoiceCreate,
)
from app.modules.purchases import purchases_service
from app.modules.purchases.xml_parser import parse_cfdi_40_xml


async def setup_purchases_test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, session_factory


@pytest.mark.asyncio
async def test_reception_creates_peps_cost_layer_and_updates_average_cost():
    """
    Test 1: Verifica que una recepción de mercancía:
    1. Genera un movimiento ENTRADA_COMPRA en el Kardex inmutable.
    2. Recalcula con precisión el Costo Promedio Ponderado.
    3. Si el producto tiene costeo PEPS, genera una Capa de Costo (CostLayer) exacta.
    4. Prorratea el flete en el costo unitario efectivo del artículo.
    """
    engine, session_factory = await setup_purchases_test_db()
    async with session_factory() as db:
        tenant_id = uuid.uuid4()
        branch_id = uuid.uuid4()
        warehouse_id = uuid.uuid4()

        # Base setup
        branch = Branch(id=branch_id, tenant_id=tenant_id, code="SUC-01", name="Matriz", zip_code="06000")
        warehouse = Warehouse(id=warehouse_id, tenant_id=tenant_id, branch_id=branch_id, code="ALM-01", name="Almacén Central")
        currency = Currency(id=uuid.uuid4(), tenant_id=tenant_id, code="MXN", name="Peso Mexicano", exchange_rate=Decimal("1.0000"), is_base=True)
        supplier = Supplier(id=uuid.uuid4(), tenant_id=tenant_id, code="PRV-01", rfc="PROV010101XYZ", legal_name="PROVEEDOR INDUSTRIAL S.A.", zip_code="06000", credit_days=30)
        
        # Producto con método de costeo PEPS y existencia inicial existente
        product_peps = Product(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            sku="ART-PEPS-01",
            name="Taladro Industrial 800W",
            product_type="PRODUCTO",
            costing_method="PEPS",
            average_cost=Decimal("100.0000"),
            last_cost=Decimal("100.0000"),
            vat_rate=Decimal("0.1600")
        )
        # Existencia previa: 10 piezas a $100.00 = $1,000.00
        initial_stock = ProductWarehouseStock(
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            product_id=product_peps.id,
            physical_stock=Decimal("10.0000"),
            available_stock=Decimal("10.0000"),
            reserved_stock=Decimal("0.0000"),
            average_cost=Decimal("100.0000"),
            last_cost=Decimal("100.0000"),
            total_value=Decimal("1000.0000")
        )

        db.add_all([branch, warehouse, currency, supplier, product_peps, initial_stock])
        await db.commit()

        # Recepción de 20 piezas a $160.00 c/u con flete total de $200.00
        # Subtotal items: 20 * 160 = $3,200.00
        # Flete prorrateado: $200.00
        # Costo unitario efectivo = (3200 + 200) / 20 = $170.00
        # Nueva existencia física = 10 + 20 = 30 piezas
        # Nuevo costo promedio ponderado:
        # (10 * 100 + 20 * 170) / 30 = (1000 + 3400) / 30 = 4400 / 30 = 146.6667
        reception_data = GoodsReceptionCreate(
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            supplier_id=supplier.id,
            currency_id=currency.id,
            purchase_order_id=None,
            freight_total=Decimal("200.0000"),
            items=[
                GoodsReceptionItemCreate(
                    product_id=product_peps.id,
                    quantity_received=Decimal("20.0000"),
                    unit_cost=Decimal("160.0000")
                )
            ]
        )

        reception = await purchases_service.receive_merchandise(
            db=db,
            tenant_id=tenant_id,
            data=reception_data,
            user_id=None
        )
        await db.commit()

        assert reception.document_type == "RECEPCION"
        assert reception.status == "RECIBIDA"
        assert len(reception.items) == 1
        assert reception.items[0].effective_unit_cost == Decimal("170.0000")

        # Verificar stock en almacén
        stock_res = await db.execute(
            select(ProductWarehouseStock).where(
                ProductWarehouseStock.tenant_id == tenant_id,
                ProductWarehouseStock.warehouse_id == warehouse_id,
                ProductWarehouseStock.product_id == product_peps.id
            )
        )
        stock = stock_res.scalar_one()
        assert stock.physical_stock == Decimal("30.0000")
        assert stock.available_stock == Decimal("30.0000")
        assert round(stock.average_cost, 4) == Decimal("146.6667")
        assert stock.last_cost == Decimal("170.0000")

        # Verificar movimiento en Kardex inmutable (Append-Only)
        kardex_res = await db.execute(
            select(KardexMovement).where(
                KardexMovement.tenant_id == tenant_id,
                KardexMovement.reference_id == reception.id
            )
        )
        kardex = kardex_res.scalar_one()
        assert kardex.movement_type == "ENTRADA_COMPRA"
        assert kardex.direction == "IN"
        assert kardex.quantity == Decimal("20.0000")
        assert kardex.unit_cost == Decimal("170.0000")
        assert kardex.previous_stock == Decimal("10.0000")
        assert kardex.new_stock == Decimal("30.0000")

        # Verificar generación de Capa de Costo PEPS (FIFO)
        layer_res = await db.execute(
            select(CostLayer).where(
                CostLayer.tenant_id == tenant_id,
                CostLayer.kardex_movement_id == kardex.id
            )
        )
        layer = layer_res.scalar_one()
        assert layer.original_quantity == Decimal("20.0000")
        assert layer.remaining_quantity == Decimal("20.0000")
        assert layer.unit_cost == Decimal("170.0000")
        assert layer.is_exhausted is False

    await engine.dispose()


def test_cfdi_40_xml_parser():
    """
    Test 2: Valida que el parser XML CFDI 4.0 extraiga con exactitud matemática:
    - UUID del SAT del TimbreFiscalDigital
    - Emisor (RFC, Nombre, Régimen)
    - Receptor (RFC, Nombre, UsoCFDI)
    - Subtotal, Descuento, Total
    - Conceptos con importes e impuestos desglosados (IVA)
    """
    sample_cfdi_xml = """<?xml version="1.0" encoding="utf-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" Version="4.0" Serie="FAC" Folio="9945" Fecha="2026-10-15T10:30:00" FormaPago="03" MetodoPago="PPD" Moneda="MXN" TipoCambio="1" SubTotal="5000.00" Descuento="200.00" Total="5568.00" TipoDeComprobante="I" Exportacion="01" LugarExpedicion="06000">
    <cfdi:Emisor Rfc="TEC990101XYZ" Nombre="TECNOLOGIA INDUSTRIAL Y DISTRIBUCION SA DE CV" RegimenFiscal="601"/>
    <cfdi:Receptor Rfc="EME200101XYZ" Nombre="EMPRESA MODELO DE MEXICO SA DE CV" DomicilioFiscalReceptor="06000" RegimenFiscalReceptor="601" UsoCFDI="G03"/>
    <cfdi:Conceptos>
        <cfdi:Concepto ClaveProdServ="43211500" NoIdentificacion="LAP-DELL-5520" Cantidad="2.00" ClaveUnidad="H87" Unidad="Pieza" Descripcion="Computadora Portatil Dell Latitude 5520 Core i7" ValorUnitario="2500.00" Importe="5000.00" Descuento="200.00" ObjetoImp="02">
            <cfdi:Impuestos>
                <cfdi:Traslados>
                    <cfdi:Traslado Base="4800.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="768.00"/>
                </cfdi:Traslados>
            </cfdi:Impuestos>
        </cfdi:Concepto>
    </cfdi:Conceptos>
    <cfdi:Impuestos TotalImpuestosTrasladados="768.00">
        <cfdi:Traslados>
            <cfdi:Traslado Base="4800.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="768.00"/>
        </cfdi:Traslados>
    </cfdi:Impuestos>
    <cfdi:Complemento>
        <tfd:TimbreFiscalDigital Version="1.1" UUID="A1B2C3D4-E5F6-7890-ABCD-EF1234567890" FechaTimbrado="2026-10-15T10:32:15" RfcProvCertif="SAT970701NN3" SelloCFD="mock_sello" NoCertificadoSAT="00001000000504465028"/>
    </cfdi:Complemento>
</cfdi:Comprobante>
"""
    parsed = parse_cfdi_40_xml(sample_cfdi_xml)

    assert parsed["uuid"] == "A1B2C3D4-E5F6-7890-ABCD-EF1234567890"
    assert parsed["serie"] == "FAC"
    assert parsed["folio"] == "9945"
    assert parsed["subtotal"] == Decimal("5000.0000")
    assert parsed["descuento"] == Decimal("200.0000")
    assert parsed["total_iva"] == Decimal("768.0000")
    assert parsed["total"] == Decimal("5568.0000")
    assert parsed["emisor_rfc"] == "TEC990101XYZ"
    assert parsed["emisor_nombre"] == "TECNOLOGIA INDUSTRIAL Y DISTRIBUCION SA DE CV"
    assert parsed["receptor_rfc"] == "EME200101XYZ"
    assert len(parsed["concepts"]) == 1

    concept = parsed["concepts"][0]
    assert concept["clave_prod_serv"] == "43211500"
    assert concept["no_identificacion"] == "LAP-DELL-5520"
    assert concept["cantidad"] == Decimal("2.0000")
    assert concept["valor_unitario"] == Decimal("2500.0000")
    assert concept["descuento"] == Decimal("200.0000")
    assert concept["iva_importe"] == Decimal("768.0000")


@pytest.mark.asyncio
async def test_purchase_order_backorders_and_status_transitions():
    """
    Test 3: Valida el ciclo de vida y trazabilidad documental (Requisición/OC -> Recepción parcial -> Recepción total).
    Verifica que la OC transite de AUTORIZADA -> PARCIALMENTE_RECIBIDA -> RECIBIDA.
    """
    engine, session_factory = await setup_purchases_test_db()
    async with session_factory() as db:
        tenant_id = uuid.uuid4()
        branch_id = uuid.uuid4()
        warehouse_id = uuid.uuid4()

        branch = Branch(id=branch_id, tenant_id=tenant_id, code="SUC-01", name="Matriz", zip_code="06000")
        warehouse = Warehouse(id=warehouse_id, tenant_id=tenant_id, branch_id=branch_id, code="ALM-01", name="Almacén Central")
        currency = Currency(id=uuid.uuid4(), tenant_id=tenant_id, code="MXN", name="Peso Mexicano", exchange_rate=Decimal("1.0000"), is_base=True)
        supplier = Supplier(id=uuid.uuid4(), tenant_id=tenant_id, code="PRV-02", rfc="MAT800101ABC", legal_name="MATERIALES DEL CENTRO", zip_code="06000", credit_days=15)
        
        prod = Product(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            sku="CEMENTO-50KG",
            name="Bulto de Cemento Gris 50kg",
            product_type="PRODUCTO",
            costing_method="PROMEDIO",
            average_cost=Decimal("200.0000"),
            vat_rate=Decimal("0.1600")
        )
        db.add_all([branch, warehouse, currency, supplier, prod])
        await db.commit()

        # 1. Crear Orden de Compra por 100 bultos
        po_data = PurchaseOrderCreate(
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            supplier_id=supplier.id,
            currency_id=currency.id,
            items=[
                PurchaseItemCreate(
                    product_id=prod.id,
                    quantity=Decimal("100.0000"),
                    unit_cost=Decimal("220.0000")
                )
            ]
        )
        po = await purchases_service.create_purchase_order(db, tenant_id, po_data)
        await db.commit()
        assert po.status == "BORRADOR"

        # 2. Autorizar OC
        po = await purchases_service.authorize_purchase_order(db, tenant_id, po.id)
        await db.commit()
        assert po.status == "AUTORIZADA"
        po_item_id = po.items[0].id

        # 3. Primera recepción parcial (Backorder): Recibir 40 bultos de 100
        rec_data_1 = GoodsReceptionCreate(
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            supplier_id=supplier.id,
            currency_id=currency.id,
            purchase_order_id=po.id,
            items=[
                GoodsReceptionItemCreate(
                    product_id=prod.id,
                    quantity_received=Decimal("40.0000"),
                    source_item_id=po_item_id
                )
            ]
        )
        rec1 = await purchases_service.receive_merchandise(db, tenant_id, rec_data_1)
        await db.commit()

        po_res = await db.execute(
            select(PurchaseDocument).options(selectinload(PurchaseDocument.items)).where(PurchaseDocument.id == po.id)
        )
        po = po_res.scalar_one()
        assert po.status == "PARCIALMENTE_RECIBIDA"
        assert po.items[0].quantity_received == Decimal("40.0000")

        # 4. Segunda recepción: Recibir los 60 bultos restantes
        rec_data_2 = GoodsReceptionCreate(
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            supplier_id=supplier.id,
            currency_id=currency.id,
            purchase_order_id=po.id,
            items=[
                GoodsReceptionItemCreate(
                    product_id=prod.id,
                    quantity_received=Decimal("60.0000"),
                    source_item_id=po_item_id
                )
            ]
        )
        rec2 = await purchases_service.receive_merchandise(db, tenant_id, rec_data_2)
        await db.commit()

        po_res2 = await db.execute(
            select(PurchaseDocument).options(selectinload(PurchaseDocument.items)).where(PurchaseDocument.id == po.id)
        )
        po = po_res2.scalar_one()
        assert po.status == "RECIBIDA"
        assert po.items[0].quantity_received == Decimal("100.0000")

    await engine.dispose()


@pytest.mark.asyncio
async def test_supplier_invoice_generates_payable_document_liability():
    """
    Test 4: Valida que al aprobar una Factura de Proveedor se genere de forma atómica
    el pasivo en Cuentas por Pagar (PayableDocument) con fecha de vencimiento según los días de crédito.
    """
    engine, session_factory = await setup_purchases_test_db()
    async with session_factory() as db:
        tenant_id = uuid.uuid4()
        branch_id = uuid.uuid4()
        warehouse_id = uuid.uuid4()

        branch = Branch(id=branch_id, tenant_id=tenant_id, code="SUC-01", name="Matriz", zip_code="06000")
        warehouse = Warehouse(id=warehouse_id, tenant_id=tenant_id, branch_id=branch_id, code="ALM-01", name="Almacén Central")
        currency = Currency(id=uuid.uuid4(), tenant_id=tenant_id, code="MXN", name="Peso Mexicano", exchange_rate=Decimal("1.0000"), is_base=True)
        
        # Proveedor con 45 días de crédito
        supplier = Supplier(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            code="PRV-CREDIT45",
            rfc="PROV450101AAA",
            legal_name="PROVEEDOR CON CREDITO SA",
            zip_code="06000",
            credit_days=45
        )
        prod = Product(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            sku="SERV-MANT",
            name="Mantenimiento Industrial",
            product_type="SERVICIO",
            costing_method="PROMEDIO",
            vat_rate=Decimal("0.1600")
        )
        db.add_all([branch, warehouse, currency, supplier, prod])
        await db.commit()

        issue_date = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)

        invoice_data = SupplierInvoiceCreate(
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            supplier_id=supplier.id,
            currency_id=currency.id,
            cfdi_uuid="B5C6D7E8-1111-2222-3333-444455556666",
            serie="FAC",
            folio=1234,
            issue_date=issue_date,
            credit_days=45,
            items=[
                PurchaseItemCreate(
                    product_id=prod.id,
                    quantity=Decimal("1.0000"),
                    unit_cost=Decimal("10000.0000"),
                    vat_rate=Decimal("0.1600")
                )
            ]
        )

        invoice, payable = await purchases_service.create_supplier_invoice(db, tenant_id, invoice_data)
        await db.commit()

        assert invoice.document_type == "FACTURA_PROVEEDOR"
        assert invoice.status == "FACTURADA"
        assert invoice.total == Decimal("11600.0000")  # 10000 + 16% IVA

        # Validar pasivo en CxP
        assert payable is not None
        assert payable.supplier_id == supplier.id
        assert payable.original_total == Decimal("11600.0000")
        assert payable.current_balance == Decimal("11600.0000")
        assert payable.status == "PENDIENTE"
        assert payable.credit_days == 45
        # Fecha de vencimiento esperada: 2026-10-20 + 45 días = 2026-12-04
        expected_due = date(2026, 12, 4)
        assert payable.due_date == expected_due

    await engine.dispose()
