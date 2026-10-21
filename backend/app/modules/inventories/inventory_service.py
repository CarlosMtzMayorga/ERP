import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.inventories.models import (
    ProductWarehouseStock,
    KardexMovement,
    CostLayer,
    KardexLayerConsumption,
    InventoryReservation,
)
from app.modules.master_data.models import Product, Warehouse


async def get_or_create_stock(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    product_id: uuid.UUID,
    for_update: bool = True
) -> ProductWarehouseStock:
    """
    Obtiene o inicializa el balance de existencia física y apartados para un artículo en un almacén.
    Aplica bloqueo de fila ('FOR UPDATE') si for_update=True para garantizar serialización de movimientos.
    """
    stmt = select(ProductWarehouseStock).where(
        ProductWarehouseStock.tenant_id == tenant_id,
        ProductWarehouseStock.warehouse_id == warehouse_id,
        ProductWarehouseStock.product_id == product_id
    )
    if for_update:
        stmt = stmt.with_for_update()

    res = await db.execute(stmt)
    stock = res.scalar_one_or_none()

    if not stock:
        # Inicializar balance en ceros
        stock = ProductWarehouseStock(
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            physical_stock=Decimal("0.0000"),
            reserved_stock=Decimal("0.0000"),
            available_stock=Decimal("0.0000"),
            average_cost=Decimal("0.0000"),
            last_cost=Decimal("0.0000"),
            total_value=Decimal("0.0000")
        )
        db.add(stock)
        await db.flush()

    return stock


async def record_entry(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    product_id: uuid.UUID,
    quantity: Decimal,
    unit_cost: Decimal,
    movement_type: str = "ENTRADA_COMPRA",
    reference_type: str = "FACTURA_COMPRA",
    reference_id: Optional[uuid.UUID] = None,
    reference_folio: Optional[str] = None,
    notes: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None
) -> Tuple[KardexMovement, ProductWarehouseStock]:
    """
    Registra una entrada de inventario (Append-Only) en el Kardex.
    Actualiza el costo promedio ponderado y genera una capa de costo PEPS si aplica.
    """
    if quantity <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La cantidad a ingresar debe ser mayor a cero.")
    if unit_cost < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El costo unitario no puede ser negativo.")

    # 1. Obtener artículo para conocer su método de costeo
    prod_res = await db.execute(
        select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id)
    )
    product = prod_res.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artículo no encontrado.")

    # 2. Bloquear y obtener registro de existencias
    stock = await get_or_create_stock(db, tenant_id, warehouse_id, product_id, for_update=True)

    previous_stock = stock.physical_stock
    previous_avg_cost = stock.average_cost
    new_stock = previous_stock + quantity

    # 3. Cálculo de Costo Promedio Ponderado Dinámico:
    # (Existencia previa * Costo promedio previo + Cantidad entrante * Costo entrante) / Existencia nueva
    if new_stock > 0:
        total_prev_val = previous_stock * previous_avg_cost
        incoming_val = quantity * unit_cost
        new_avg_cost = (total_prev_val + incoming_val) / new_stock
    else:
        new_avg_cost = unit_cost

    # 4. Actualizar existencia materializada
    stock.physical_stock = new_stock
    stock.available_stock = new_stock - stock.reserved_stock
    stock.average_cost = new_avg_cost
    stock.last_cost = unit_cost
    stock.total_value = new_stock * new_avg_cost

    # Actualizar costos maestros de referencia en el artículo
    product.last_cost = unit_cost
    product.average_cost = new_avg_cost

    total_cost = quantity * unit_cost

    # 5. Insertar movimiento en Kardex inmutable (Append-Only)
    movement = KardexMovement(
        tenant_id=tenant_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        movement_type=movement_type.upper(),
        direction="IN",
        quantity=quantity,
        unit_cost=unit_cost,
        total_cost=total_cost,
        previous_stock=previous_stock,
        new_stock=new_stock,
        previous_avg_cost=previous_avg_cost,
        new_avg_cost=new_avg_cost,
        costing_method=product.costing_method,
        reference_type=reference_type,
        reference_id=reference_id,
        reference_folio=reference_folio,
        notes=notes,
        user_id=user_id
    )
    db.add(movement)
    await db.flush()  # Para obtener el ID del movimiento

    # 6. Si el método de costeo es PEPS (FIFO), generar Capa de Costo
    if product.costing_method.upper() == "PEPS":
        cost_layer = CostLayer(
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            kardex_movement_id=movement.id,
            original_quantity=quantity,
            remaining_quantity=quantity,
            unit_cost=unit_cost,
            is_exhausted=False
        )
        db.add(cost_layer)

    return movement, stock


async def record_exit(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    product_id: uuid.UUID,
    quantity: Decimal,
    movement_type: str = "SALIDA_VENTA",
    reference_type: str = "FACTURA_VENTA",
    reference_id: Optional[uuid.UUID] = None,
    reference_folio: Optional[str] = None,
    notes: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    reservation_id: Optional[uuid.UUID] = None
) -> Tuple[KardexMovement, ProductWarehouseStock, List[Dict[str, Any]]]:
    """
    Registra una salida de inventario (Append-Only) en el Kardex.
    Aplica el motor de costeo (PEPS con bloqueo SELECT FOR UPDATE o Costo Promedio)
    y descuenta el inventario físico y/o apartados.
    """
    if quantity <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La cantidad a descontar debe ser mayor a cero.")

    # 1. Obtener artículo
    prod_res = await db.execute(
        select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id)
    )
    product = prod_res.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artículo no encontrado.")

    # 2. Bloquear y obtener existencia
    stock = await get_or_create_stock(db, tenant_id, warehouse_id, product_id, for_update=True)

    # Validar existencia física real
    if stock.physical_stock < quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Existencia física insuficiente en el almacén. "
                f"Física actual: {stock.physical_stock}, requerida: {quantity}."
            )
        )

    # Si hay una reserva previa (soft allocation) que se está convirtiendo en salida real:
    if reservation_id:
        res_stmt = select(InventoryReservation).where(
            InventoryReservation.id == reservation_id,
            InventoryReservation.tenant_id == tenant_id,
            InventoryReservation.status == "RESERVED"
        ).with_for_update()
        res_record = (await db.execute(res_stmt)).scalar_one_or_none()
        if not res_record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva de inventario no encontrada o ya finalizada.")
        
        # Descontar del apartado
        stock.reserved_stock = max(Decimal("0.0000"), stock.reserved_stock - quantity)
        res_record.status = "FULFILLED"
        res_record.fulfilled_at = datetime.now(timezone.utc)
    else:
        # Si es una salida directa no reservada, validar existencia disponible (Física - Apartados)
        if stock.available_stock < quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Existencia disponible insuficiente por mercancía apartada. "
                    f"Física: {stock.physical_stock}, Apartada: {stock.reserved_stock}, "
                    f"Disponible: {stock.available_stock}, Solicitada: {quantity}."
                )
            )

    previous_stock = stock.physical_stock
    new_stock = previous_stock - quantity
    consumptions_log: List[Dict[str, Any]] = []

    # 3. Determinación de Costo (PEPS vs Promedio)
    if product.costing_method.upper() == "PEPS":
        # Consumir capas de costo en orden FIFO con bloqueo exclusivo SELECT FOR UPDATE
        layer_stmt = (
            select(CostLayer)
            .where(
                CostLayer.tenant_id == tenant_id,
                CostLayer.warehouse_id == warehouse_id,
                CostLayer.product_id == product_id,
                CostLayer.is_exhausted == False,
                CostLayer.remaining_quantity > Decimal("0.0000")
            )
            .order_by(CostLayer.created_at.asc())
            .with_for_update()
        )
        layers_res = await db.execute(layer_stmt)
        layers = layers_res.scalars().all()

        needed_qty = quantity
        total_cogs = Decimal("0.0000")

        for layer in layers:
            available_in_layer = layer.remaining_quantity
            take = min(needed_qty, available_in_layer)

            layer.remaining_quantity -= take
            if layer.remaining_quantity <= Decimal("0.0000"):
                layer.is_exhausted = True

            layer_cost = take * layer.unit_cost
            total_cogs += layer_cost

            consumptions_log.append({
                "cost_layer_id": layer.id,
                "quantity_consumed": take,
                "unit_cost": layer.unit_cost,
                "total_cost": layer_cost
            })

            needed_qty -= take
            if needed_qty <= Decimal("0.0000"):
                break

        # Si aún faltó cantidad por costear en capas PEPS, fallback al costo promedio
        if needed_qty > Decimal("0.0000"):
            fallback_unit_cost = stock.average_cost if stock.average_cost > 0 else stock.last_cost
            fallback_cost = needed_qty * fallback_unit_cost
            total_cogs += fallback_cost

        exit_unit_cost = total_cogs / quantity if quantity > 0 else stock.average_cost
        exit_total_cost = total_cogs
    else:
        # Método Costo Promedio Ponderado
        exit_unit_cost = stock.average_cost
        exit_total_cost = quantity * exit_unit_cost

    # 4. Actualizar existencia materializada
    stock.physical_stock = new_stock
    stock.available_stock = new_stock - stock.reserved_stock
    stock.total_value = new_stock * stock.average_cost

    # 5. Insertar movimiento en Kardex inmutable
    movement = KardexMovement(
        tenant_id=tenant_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        movement_type=movement_type.upper(),
        direction="OUT",
        quantity=quantity,
        unit_cost=exit_unit_cost,
        total_cost=exit_total_cost,
        previous_stock=previous_stock,
        new_stock=new_stock,
        previous_avg_cost=stock.average_cost,
        new_avg_cost=stock.average_cost,
        costing_method=product.costing_method,
        reference_type=reference_type,
        reference_id=reference_id,
        reference_folio=reference_folio,
        notes=notes,
        user_id=user_id
    )
    db.add(movement)
    await db.flush()

    # 6. Registrar auditoría de capas PEPS consumidas
    for c in consumptions_log:
        consumption_record = KardexLayerConsumption(
            tenant_id=tenant_id,
            kardex_movement_id=movement.id,
            cost_layer_id=c["cost_layer_id"],
            quantity_consumed=c["quantity_consumed"],
            unit_cost=c["unit_cost"],
            total_cost=c["total_cost"]
        )
        db.add(consumption_record)

    return movement, stock, consumptions_log


async def record_transfer(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    source_warehouse_id: uuid.UUID,
    target_warehouse_id: uuid.UUID,
    product_id: uuid.UUID,
    quantity: Decimal,
    reference_folio: Optional[str] = None,
    notes: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None
) -> Tuple[KardexMovement, KardexMovement]:
    """
    Traspaso atómico entre dos almacenes de la misma empresa.
    Descuenta de origen (con su método de costeo) y suma en destino con el costo transferido.
    """
    if source_warehouse_id == target_warehouse_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El almacén origen y destino no pueden ser el mismo.")

    transfer_id = uuid.uuid4()
    folio_ref = reference_folio or f"TRASP-{str(transfer_id)[:8].upper()}"

    # 1. Salida en almacén origen
    exit_mov, _, _ = await record_exit(
        db=db,
        tenant_id=tenant_id,
        warehouse_id=source_warehouse_id,
        product_id=product_id,
        quantity=quantity,
        movement_type="TRASPASO_SALIDA",
        reference_type="TRASPASO",
        reference_id=transfer_id,
        reference_folio=folio_ref,
        notes=f"Traspaso hacia almacén destino. {notes or ''}",
        user_id=user_id
    )

    # 2. Entrada en almacén destino con el costo unitario exacto determinado en la salida
    entry_mov, _ = await record_entry(
        db=db,
        tenant_id=tenant_id,
        warehouse_id=target_warehouse_id,
        product_id=product_id,
        quantity=quantity,
        unit_cost=exit_mov.unit_cost,
        movement_type="TRASPASO_ENTRADA",
        reference_type="TRASPASO",
        reference_id=transfer_id,
        reference_folio=folio_ref,
        notes=f"Traspaso desde almacén origen. {notes or ''}",
        user_id=user_id
    )

    return exit_mov, entry_mov


async def create_reservation(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    product_id: uuid.UUID,
    quantity: Decimal,
    reference_type: str = "PEDIDO_VENTA",
    reference_id: Optional[uuid.UUID] = None,
    reference_folio: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None
) -> InventoryReservation:
    """
    Aparta inventario disponible (Soft Allocation).
    Incrementa reserved_stock y reduce available_stock sin tocar physical_stock.
    """
    if quantity <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La cantidad a apartar debe ser mayor a cero.")

    stock = await get_or_create_stock(db, tenant_id, warehouse_id, product_id, for_update=True)

    if stock.available_stock < quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"No hay inventario disponible suficiente para apartar. "
                f"Física: {stock.physical_stock}, Ya apartada: {stock.reserved_stock}, "
                f"Disponible: {stock.available_stock}, Solicitada: {quantity}."
            )
        )

    # Actualizar apartado
    stock.reserved_stock += quantity
    stock.available_stock = stock.physical_stock - stock.reserved_stock

    reservation = InventoryReservation(
        tenant_id=tenant_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        quantity=quantity,
        status="RESERVED",
        reference_type=reference_type,
        reference_id=reference_id,
        reference_folio=reference_folio,
        user_id=user_id
    )
    db.add(reservation)
    await db.flush()
    return reservation


async def cancel_reservation(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    reservation_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None
) -> InventoryReservation:
    """
    Cancela una reserva y libera el inventario apartado de vuelta a disponible.
    """
    stmt = (
        select(InventoryReservation)
        .where(
            InventoryReservation.id == reservation_id,
            InventoryReservation.tenant_id == tenant_id,
            InventoryReservation.status == "RESERVED"
        )
        .with_for_update()
    )
    res = await db.execute(stmt)
    reservation = res.scalar_one_or_none()
    if not reservation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada o ya procesada.")

    stock = await get_or_create_stock(db, tenant_id, reservation.warehouse_id, reservation.product_id, for_update=True)
    stock.reserved_stock = max(Decimal("0.0000"), stock.reserved_stock - reservation.quantity)
    stock.available_stock = stock.physical_stock - stock.reserved_stock

    reservation.status = "CANCELLED"
    reservation.cancelled_at = datetime.now(timezone.utc)
    return reservation

