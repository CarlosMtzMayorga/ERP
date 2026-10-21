import uuid
from decimal import Decimal
from datetime import datetime, date, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_tenant, require_permission
from app.modules.auth.models import User
from app.modules.tenants.models import Tenant
from app.modules.master_data.models import Product, Warehouse
from app.modules.inventories.models import (
    ProductWarehouseStock,
    KardexMovement,
    CostLayer,
    KardexLayerConsumption,
    InventoryReservation,
)
from app.modules.inventories.inventory_service import (
    record_entry,
    record_exit,
    record_transfer,
    create_reservation,
    cancel_reservation,
)

router = APIRouter(prefix="/inventory", tags=["Módulo 2: Inventarios"])


# --- Schemas ---
class InventoryDashboardResponse(BaseModel):
    total_valuation: Decimal
    total_physical_units: Decimal
    critical_stock_count: int
    reorder_stock_count: int
    movements_today_count: int
    active_reservations_count: int


class ProductStockResponse(BaseModel):
    product_id: uuid.UUID
    sku: str
    product_name: str
    unit_name: str
    costing_method: str
    warehouse_id: uuid.UUID
    warehouse_name: str
    physical_stock: Decimal
    reserved_stock: Decimal
    available_stock: Decimal
    average_cost: Decimal
    last_cost: Decimal
    total_value: Decimal
    min_stock: Decimal
    reorder_point: Decimal
    max_stock: Decimal
    stock_status: str  # CRITICAL (Rojo), REORDER (Amarillo), OPTIMAL (Verde)


class LayerConsumptionResponse(BaseModel):
    cost_layer_id: uuid.UUID
    quantity_consumed: Decimal
    unit_cost: Decimal
    total_cost: Decimal

    class Config:
        from_attributes = True


class KardexMovementResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime
    product_id: uuid.UUID
    sku: str
    product_name: str
    warehouse_id: uuid.UUID
    warehouse_name: str
    movement_type: str
    direction: str
    quantity: Decimal
    unit_cost: Decimal
    total_cost: Decimal
    previous_stock: Decimal
    new_stock: Decimal
    new_avg_cost: Decimal
    costing_method: str
    reference_type: str
    reference_folio: Optional[str]
    notes: Optional[str]
    user_name: Optional[str] = None
    layer_consumptions: List[LayerConsumptionResponse] = []


class EntryMovementRequest(BaseModel):
    warehouse_id: uuid.UUID
    product_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0)
    unit_cost: Decimal = Field(..., ge=0)
    movement_type: str = Field("ENTRADA_COMPRA", description="ENTRADA_COMPRA, AJUSTE_POSITIVO, INVENTARIO_INICIAL")
    reference_folio: Optional[str] = None
    notes: Optional[str] = None


class ExitMovementRequest(BaseModel):
    warehouse_id: uuid.UUID
    product_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0)
    movement_type: str = Field("AJUSTE_NEGATIVO", description="AJUSTE_NEGATIVO, SALIDA_VENTA, MERMA")
    reference_folio: Optional[str] = None
    notes: Optional[str] = None


class TransferMovementRequest(BaseModel):
    source_warehouse_id: uuid.UUID
    target_warehouse_id: uuid.UUID
    product_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0)
    reference_folio: Optional[str] = None
    notes: Optional[str] = None


class ReservationRequest(BaseModel):
    warehouse_id: uuid.UUID
    product_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0)
    reference_type: str = Field("PEDIDO_VENTA")
    reference_id: Optional[uuid.UUID] = None
    reference_folio: Optional[str] = None


# --- Endpoints ---
@router.get("/dashboard", response_model=InventoryDashboardResponse, summary="Métricas ejecutivas de inventario en tiempo real")
async def get_inventory_dashboard(
    tenant: Tenant = Depends(get_current_tenant),
    _has_perm: bool = Depends(require_permission("inventory:read")),
    db: AsyncSession = Depends(get_db)
):
    # Total valorizado y unidades físicas
    stock_agg = await db.execute(
        select(
            func.coalesce(func.sum(ProductWarehouseStock.total_value), Decimal("0.0000")),
            func.coalesce(func.sum(ProductWarehouseStock.physical_stock), Decimal("0.0000"))
        ).where(ProductWarehouseStock.tenant_id == tenant.id)
    )
    total_val, total_units = stock_agg.one()

    # Movimientos de hoy
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    mov_res = await db.execute(
        select(func.count(KardexMovement.id)).where(
            KardexMovement.tenant_id == tenant.id,
            KardexMovement.created_at >= today_start
        )
    )
    mov_today = mov_res.scalar() or 0

    # Reservas activas
    res_count = await db.execute(
        select(func.count(InventoryReservation.id)).where(
            InventoryReservation.tenant_id == tenant.id,
            InventoryReservation.status == "RESERVED"
        )
    )
    active_reservations = res_count.scalar() or 0

    # Contar alertas de stock (Rojo <= min_stock, Amarillo <= reorder_point)
    stocks_query = (
        select(ProductWarehouseStock.physical_stock, Product.min_stock, Product.reorder_point)
        .join(Product, Product.id == ProductWarehouseStock.product_id)
        .where(ProductWarehouseStock.tenant_id == tenant.id, Product.is_active == True)
    )
    stocks_res = await db.execute(stocks_query)
    
    critical_count = 0
    reorder_count = 0
    for phys, min_s, reorder_p in stocks_res.all():
        if phys <= min_s:
            critical_count += 1
        elif phys <= reorder_p:
            reorder_count += 1

    return InventoryDashboardResponse(
        total_valuation=total_val,
        total_physical_units=total_units,
        critical_stock_count=critical_count,
        reorder_stock_count=reorder_count,
        movements_today_count=mov_today,
        active_reservations_count=active_reservations
    )


@router.get("/stocks", response_model=List[ProductStockResponse], summary="Catálogo de existencias por almacén con semáforos de stock")
async def list_product_stocks(
    warehouse_id: Optional[uuid.UUID] = Query(None),
    status_filter: Optional[str] = Query(None, description="CRITICAL, REORDER, OPTIMAL"),
    tenant: Tenant = Depends(get_current_tenant),
    _has_perm: bool = Depends(require_permission("inventory:read")),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(ProductWarehouseStock, Product, Warehouse)
        .join(Product, Product.id == ProductWarehouseStock.product_id)
        .join(Warehouse, Warehouse.id == ProductWarehouseStock.warehouse_id)
        .where(ProductWarehouseStock.tenant_id == tenant.id)
    )

    if warehouse_id:
        query = query.where(ProductWarehouseStock.warehouse_id == warehouse_id)

    query = query.order_by(Product.name, Warehouse.name)
    res = await db.execute(query)

    output = []
    for stock, prod, wh in res.all():
        # Determinar Semáforo
        if stock.physical_stock <= prod.min_stock:
            current_status = "CRITICAL"
        elif stock.physical_stock <= prod.reorder_point:
            current_status = "REORDER"
        else:
            current_status = "OPTIMAL"

        if status_filter and current_status != status_filter.upper():
            continue

        output.append(
            ProductStockResponse(
                product_id=prod.id,
                sku=prod.sku,
                product_name=prod.name,
                unit_name=prod.unit_name,
                costing_method=prod.costing_method,
                warehouse_id=wh.id,
                warehouse_name=wh.name,
                physical_stock=stock.physical_stock,
                reserved_stock=stock.reserved_stock,
                available_stock=stock.available_stock,
                average_cost=stock.average_cost,
                last_cost=stock.last_cost,
                total_value=stock.total_value,
                min_stock=prod.min_stock,
                reorder_point=prod.reorder_point,
                max_stock=prod.max_stock,
                stock_status=current_status
            )
        )
    return output


@router.get("/kardex", response_model=List[KardexMovementResponse], summary="Historial inmutable del Kardex con detalle de capas PEPS")
async def list_kardex_movements(
    product_id: Optional[uuid.UUID] = Query(None),
    warehouse_id: Optional[uuid.UUID] = Query(None),
    movement_type: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    tenant: Tenant = Depends(get_current_tenant),
    _has_perm: bool = Depends(require_permission("inventory:read")),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(KardexMovement)
        .options(
            selectinload(KardexMovement.product),
            selectinload(KardexMovement.warehouse),
            selectinload(KardexMovement.user),
            selectinload(KardexMovement.layer_consumptions)
        )
        .where(KardexMovement.tenant_id == tenant.id)
    )

    if product_id:
        query = query.where(KardexMovement.product_id == product_id)
    if warehouse_id:
        query = query.where(KardexMovement.warehouse_id == warehouse_id)
    if movement_type:
        query = query.where(KardexMovement.movement_type == movement_type.upper())

    query = query.order_by(KardexMovement.created_at.desc()).limit(limit).offset(offset)
    res = await db.execute(query)
    movements = res.scalars().all()

    output = []
    for m in movements:
        consumptions = [
            LayerConsumptionResponse(
                cost_layer_id=c.cost_layer_id,
                quantity_consumed=c.quantity_consumed,
                unit_cost=c.unit_cost,
                total_cost=c.total_cost
            )
            for c in m.layer_consumptions
        ]

        output.append(
            KardexMovementResponse(
                id=m.id,
                created_at=m.created_at,
                product_id=m.product_id,
                sku=m.product.sku if m.product else "N/A",
                product_name=m.product.name if m.product else "N/A",
                warehouse_id=m.warehouse_id,
                warehouse_name=m.warehouse.name if m.warehouse else "N/A",
                movement_type=m.movement_type,
                direction=m.direction,
                quantity=m.quantity,
                unit_cost=m.unit_cost,
                total_cost=m.total_cost,
                previous_stock=m.previous_stock,
                new_stock=m.new_stock,
                new_avg_cost=m.new_avg_cost,
                costing_method=m.costing_method,
                reference_type=m.reference_type,
                reference_folio=m.reference_folio,
                notes=m.notes,
                user_name=m.user.full_name if m.user else "Sistema",
                layer_consumptions=consumptions
            )
        )
    return output


@router.post("/movements/entry", summary="Registrar entrada de mercancía al almacén")
async def api_record_entry(
    payload: EntryMovementRequest,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("inventory:adjust")),
    db: AsyncSession = Depends(get_db)
):
    movement, stock = await record_entry(
        db=db,
        tenant_id=tenant.id,
        warehouse_id=payload.warehouse_id,
        product_id=payload.product_id,
        quantity=payload.quantity,
        unit_cost=payload.unit_cost,
        movement_type=payload.movement_type,
        reference_type="AJUSTE",
        reference_folio=payload.reference_folio,
        notes=payload.notes,
        user_id=user.id
    )
    await db.commit()
    return {
        "message": "Entrada registrada exitosamente en Kardex.",
        "movement_id": movement.id,
        "new_physical_stock": stock.physical_stock,
        "new_average_cost": stock.average_cost
    }


@router.post("/movements/exit", summary="Registrar salida o ajuste negativo de mercancía")
async def api_record_exit(
    payload: ExitMovementRequest,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("inventory:adjust")),
    db: AsyncSession = Depends(get_db)
):
    movement, stock, consumptions = await record_exit(
        db=db,
        tenant_id=tenant.id,
        warehouse_id=payload.warehouse_id,
        product_id=payload.product_id,
        quantity=payload.quantity,
        movement_type=payload.movement_type,
        reference_type="AJUSTE",
        reference_folio=payload.reference_folio,
        notes=payload.notes,
        user_id=user.id
    )
    await db.commit()
    return {
        "message": "Salida registrada exitosamente en Kardex.",
        "movement_id": movement.id,
        "new_physical_stock": stock.physical_stock,
        "unit_cost_applied": movement.unit_cost,
        "total_cost": movement.total_cost,
        "layers_consumed": consumptions
    }


@router.post("/movements/transfer", summary="Traspaso atómico entre dos almacenes")
async def api_record_transfer(
    payload: TransferMovementRequest,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("inventory:adjust")),
    db: AsyncSession = Depends(get_db)
):
    exit_mov, entry_mov = await record_transfer(
        db=db,
        tenant_id=tenant.id,
        source_warehouse_id=payload.source_warehouse_id,
        target_warehouse_id=payload.target_warehouse_id,
        product_id=payload.product_id,
        quantity=payload.quantity,
        reference_folio=payload.reference_folio,
        notes=payload.notes,
        user_id=user.id
    )
    await db.commit()
    return {
        "message": "Traspaso inter-almacenes ejecutado con éxito.",
        "exit_movement_id": exit_mov.id,
        "entry_movement_id": entry_mov.id,
        "transferred_unit_cost": exit_mov.unit_cost
    }


@router.post("/reservations", summary="Apartar inventario (Soft Allocation)")
async def api_create_reservation(
    payload: ReservationRequest,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("inventory:read")),
    db: AsyncSession = Depends(get_db)
):
    reservation = await create_reservation(
        db=db,
        tenant_id=tenant.id,
        warehouse_id=payload.warehouse_id,
        product_id=payload.product_id,
        quantity=payload.quantity,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
        reference_folio=payload.reference_folio,
        user_id=user.id
    )
    await db.commit()
    return {
        "message": "Inventario apartado con éxito.",
        "reservation_id": reservation.id,
        "quantity_reserved": reservation.quantity,
        "status": reservation.status
    }


@router.delete("/reservations/{reservation_id}", summary="Liberar/cancelar apartado de inventario")
async def api_cancel_reservation(
    reservation_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("inventory:adjust")),
    db: AsyncSession = Depends(get_db)
):
    reservation = await cancel_reservation(
        db=db,
        tenant_id=tenant.id,
        reservation_id=reservation_id,
        user_id=user.id
    )
    await db.commit()
    return {
        "message": "Apartado cancelado y existencia liberada a disponible.",
        "reservation_id": reservation.id,
        "status": reservation.status
    }

