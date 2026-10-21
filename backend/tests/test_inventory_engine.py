import pytest
import uuid
import asyncio
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.core.database import Base
from app.modules.tenants.models import Tenant
from app.modules.auth.models import User
from app.modules.master_data.models import Product, Warehouse
from app.modules.inventories.models import (
    ProductWarehouseStock,
    KardexMovement,
    CostLayer,
    KardexLayerConsumption,
    InventoryReservation
)
from app.modules.inventories.inventory_service import (
    record_entry,
    record_exit,
    create_reservation,
    cancel_reservation
)


async def setup_test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, session_factory


@pytest.mark.asyncio
async def test_weighted_average_costing():
    """
    Valida el cálculo matemático dinámico del Costo Promedio Ponderado:
    1. Entrada de 10 unidades @ $100.00 -> Costo Promedio = $100.00
    2. Entrada de 20 unidades @ $130.00 -> Costo Promedio = (10*100 + 20*130) / 30 = 3600 / 30 = $120.00
    3. Salida de 15 unidades -> Evaluada a $120.00 c/u, Stock restante = 15 unidades @ $120.00
    """
    engine, async_db = await setup_test_db()
    tenant_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    product_id = uuid.uuid4()

    async with async_db() as session:
        t = Tenant(id=tenant_id, rfc="EME200101XYZ", legal_name="EMPRESA MODELO", fiscal_regime_code="601", zip_code="06000")
        w = Warehouse(id=warehouse_id, tenant_id=tenant_id, code="ALM-01", name="Almacén Matriz")
        p = Product(
            id=product_id,
            tenant_id=tenant_id,
            sku="PROD-AVG",
            name="Artículo Costo Promedio",
            costing_method="PROMEDIO"
        )
        session.add_all([t, w, p])
        await session.commit()

    # Paso 1: Entrada 10 @ $100
    async with async_db() as session:
        mov1, stock1 = await record_entry(
            db=session,
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity=Decimal("10.0000"),
            unit_cost=Decimal("100.0000"),
            movement_type="ENTRADA_COMPRA"
        )
        await session.commit()
        assert stock1.physical_stock == Decimal("10.0000")
        assert stock1.average_cost == Decimal("100.0000")

    # Paso 2: Entrada 20 @ $130
    async with async_db() as session:
        mov2, stock2 = await record_entry(
            db=session,
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity=Decimal("20.0000"),
            unit_cost=Decimal("130.0000"),
            movement_type="ENTRADA_COMPRA"
        )
        await session.commit()
        assert stock2.physical_stock == Decimal("30.0000")
        assert stock2.average_cost == Decimal("120.0000")
        assert stock2.total_value == Decimal("3600.0000")

    # Paso 3: Salida 15 unidades
    async with async_db() as session:
        mov3, stock3, _ = await record_exit(
            db=session,
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity=Decimal("15.0000"),
            movement_type="SALIDA_VENTA"
        )
        await session.commit()
        assert stock3.physical_stock == Decimal("15.0000")
        assert mov3.unit_cost == Decimal("120.0000")
        assert mov3.total_cost == Decimal("1800.0000")
        assert stock3.average_cost == Decimal("120.0000")

    await engine.dispose()


@pytest.mark.asyncio
async def test_peps_fifo_cost_layers():
    """
    Valida el motor de Capas de Costo PEPS (FIFO):
    - Capa 1: 5 unidades @ $50.00
    - Capa 2: 10 unidades @ $70.00
    - Salida de 8 unidades:
        Consume 5 unidades de la Capa 1 (@ $50 = $250) -> Agota Capa 1
        Consume 3 unidades de la Capa 2 (@ $70 = $210) -> Capa 2 queda con 7 restantes
        Costo total de venta (COGS) = $250 + $210 = $460.00
    """
    engine, async_db = await setup_test_db()
    tenant_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    product_id = uuid.uuid4()

    async with async_db() as session:
        t = Tenant(id=tenant_id, rfc="EME200101XYZ", legal_name="EMPRESA MODELO", fiscal_regime_code="601", zip_code="06000")
        w = Warehouse(id=warehouse_id, tenant_id=tenant_id, code="ALM-01", name="Almacén Matriz")
        p = Product(
            id=product_id,
            tenant_id=tenant_id,
            sku="PROD-PEPS",
            name="Artículo PEPS",
            costing_method="PEPS"
        )
        session.add_all([t, w, p])
        await session.commit()

    # Capa 1
    async with async_db() as session:
        await record_entry(
            db=session,
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity=Decimal("5.0000"),
            unit_cost=Decimal("50.0000")
        )
        await session.commit()

    # Capa 2
    async with async_db() as session:
        await record_entry(
            db=session,
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity=Decimal("10.0000"),
            unit_cost=Decimal("70.0000")
        )
        await session.commit()

    # Salida 8 unidades
    async with async_db() as session:
        mov, stock, consumptions = await record_exit(
            db=session,
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity=Decimal("8.0000")
        )
        await session.commit()

        assert stock.physical_stock == Decimal("7.0000")
        assert mov.total_cost == Decimal("460.0000")
        assert len(consumptions) == 2
        assert consumptions[0]["quantity_consumed"] == Decimal("5.0000")
        assert consumptions[0]["unit_cost"] == Decimal("50.0000")
        assert consumptions[1]["quantity_consumed"] == Decimal("3.0000")
        assert consumptions[1]["unit_cost"] == Decimal("70.0000")

        # Verificar capas en base de datos
        layers_res = await session.execute(
            select(CostLayer)
            .where(CostLayer.tenant_id == tenant_id, CostLayer.product_id == product_id)
            .order_by(CostLayer.created_at.asc())
        )
        layers = layers_res.scalars().all()
        assert layers[0].is_exhausted == True
        assert layers[0].remaining_quantity == Decimal("0.0000")
        assert layers[1].is_exhausted == False
        assert layers[1].remaining_quantity == Decimal("7.0000")

    await engine.dispose()


@pytest.mark.asyncio
async def test_soft_allocation_reservations():
    """
    Valida la separación entre Existencia Física y Existencia Disponible:
    1. Entrada física = 10 unidades
    2. Apartado de 6 unidades para Pedido
       -> Física = 10, Apartada = 6, Disponible = 4
    3. Intento de apartar 5 unidades -> Debe ser rechazado (4 < 5)
    4. Cancelar apartado -> Disponible vuelve a 10
    """
    engine, async_db = await setup_test_db()
    tenant_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    product_id = uuid.uuid4()

    async with async_db() as session:
        t = Tenant(id=tenant_id, rfc="EME200101XYZ", legal_name="EMPRESA MODELO", fiscal_regime_code="601", zip_code="06000")
        w = Warehouse(id=warehouse_id, tenant_id=tenant_id, code="ALM-01", name="Almacén Matriz")
        p = Product(id=product_id, tenant_id=tenant_id, sku="PROD-RESERVE", name="Artículo Reservas", costing_method="PROMEDIO")
        session.add_all([t, w, p])
        await session.commit()

        # Entrada 10
        await record_entry(session, tenant_id, warehouse_id, product_id, Decimal("10.0000"), Decimal("100.0000"))
        await session.commit()

    # Apartar 6
    async with async_db() as session:
        res = await create_reservation(session, tenant_id, warehouse_id, product_id, Decimal("6.0000"), reference_folio="PED-001")
        await session.commit()
        res_id = res.id

        # Verificar stock
        stock = await session.execute(select(ProductWarehouseStock).where(ProductWarehouseStock.product_id == product_id))
        s = stock.scalar_one()
        assert s.physical_stock == Decimal("10.0000")
        assert s.reserved_stock == Decimal("6.0000")
        assert s.available_stock == Decimal("4.0000")

    # Intentar apartar 5 (debe fallar por falta de disponible)
    async with async_db() as session:
        with pytest.raises(Exception) as exc:
            await create_reservation(session, tenant_id, warehouse_id, product_id, Decimal("5.0000"))
        assert "disponible" in str(exc.value).lower()
        assert exc.value.status_code == 409

    # Cancelar apartado
    async with async_db() as session:
        await cancel_reservation(session, tenant_id, res_id)
        await session.commit()

        stock = await session.execute(select(ProductWarehouseStock).where(ProductWarehouseStock.product_id == product_id))
        s = stock.scalar_one()
        assert s.reserved_stock == Decimal("0.0000")
        assert s.available_stock == Decimal("10.0000")

    await engine.dispose()


@pytest.mark.asyncio
async def test_peps_concurrent_salidas():
    """
    Prueba de Concurrencia PEPS:
    Verifica que salidas simultáneas procesadas en transacciones concurrentes
    respetan la serialización del bloqueo de capas de costo y no generan existencias negativas.
    """
    engine, async_db = await setup_test_db()
    tenant_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    product_id = uuid.uuid4()

    async with async_db() as session:
        t = Tenant(id=tenant_id, rfc="EME200101XYZ", legal_name="EMPRESA MODELO", fiscal_regime_code="601", zip_code="06000")
        w = Warehouse(id=warehouse_id, tenant_id=tenant_id, code="ALM-01", name="Almacén Matriz")
        p = Product(id=product_id, tenant_id=tenant_id, sku="PROD-CONCURRENT", name="Artículo Concurrente", costing_method="PEPS")
        session.add_all([t, w, p])
        await session.commit()

        # Entrada de 20 unidades
        await record_entry(session, tenant_id, warehouse_id, product_id, Decimal("20.0000"), Decimal("10.0000"))
        await session.commit()

    async def execute_exit(qty: Decimal):
        async with async_db() as session:
            try:
                await record_exit(session, tenant_id, warehouse_id, product_id, qty)
                await session.commit()
                return True
            except Exception:
                await session.rollback()
                return False

    # Ejecutar 4 salidas de 6 unidades (Total solicitada = 24 > 20 disponible)
    # Exactamente 3 deben tener éxito (3 * 6 = 18 unidades) y la 4ta debe ser rechazada limpiamente por falta de stock
    results = [
        await execute_exit(Decimal("6.0000")),
        await execute_exit(Decimal("6.0000")),
        await execute_exit(Decimal("6.0000")),
        await execute_exit(Decimal("6.0000"))
    ]

    success_count = sum(1 for r in results if r is True)
    failure_count = sum(1 for r in results if r is False)

    assert success_count == 3
    assert failure_count == 1

    # Verificar que el stock final es exactamente 2 unidades
    async with async_db() as session:
        stock = (await session.execute(select(ProductWarehouseStock).where(ProductWarehouseStock.product_id == product_id))).scalar_one()
        assert stock.physical_stock == Decimal("2.0000")
        assert stock.available_stock == Decimal("2.0000")

    await engine.dispose()
