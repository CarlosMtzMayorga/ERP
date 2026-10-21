import uuid
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, ForeignKey, Numeric, Text, DateTime, Uuid, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship

from app.core.database import Base, TenantMixin


class ProductWarehouseStock(Base, TenantMixin):
    """
    Existencia Materializada por Almacén y Artículo.
    Mantiene la separación estricta entre Existencia Física y Existencia Disponible (Física - Apartados).
    """
    __tablename__ = "product_warehouse_stocks"

    warehouse_id = Column(Uuid(as_uuid=True), ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Uuid(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)

    # Existencia Física (conteo real en bodega)
    physical_stock = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    # Apartados / Reservas activas (comprometido en pedidos de venta)
    reserved_stock = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    # Existencia Disponible = physical_stock - reserved_stock
    available_stock = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    # Costos ponderados por almacén
    average_cost = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    last_cost = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    total_value = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    warehouse = relationship("app.modules.master_data.models.Warehouse")
    product = relationship("app.modules.master_data.models.Product")

    __table_args__ = (
        UniqueConstraint("tenant_id", "warehouse_id", "product_id", name="uq_tenant_warehouse_product_stock"),
        Index("idx_stocks_available", "tenant_id", "warehouse_id", "available_stock"),
    )


class KardexMovement(Base, TenantMixin):
    """
    Ledger Inmutable de Movimientos de Inventario (Append-Only).
    Ningún registro de esta tabla se actualiza o elimina; representa el rastro
    histórico financiero y físico de cada unidad que entra o sale del almacén.
    """
    __tablename__ = "inventory_kardex_movements"

    warehouse_id = Column(Uuid(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True)
    product_id = Column(Uuid(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)

    # Tipos: ENTRADA_COMPRA, SALIDA_VENTA, TRASPASO_SALIDA, TRASPASO_ENTRADA, AJUSTE_POSITIVO, AJUSTE_NEGATIVO, DEVOLUCION_CLIENTE, DEVOLUCION_PROVEEDOR, INVENTARIO_INICIAL
    movement_type = Column(String(30), nullable=False, index=True)
    # Dirección: IN (Suma existencia) o OUT (Resta existencia)
    direction = Column(String(5), nullable=False)

    quantity = Column(Numeric(14, 4), nullable=False)
    unit_cost = Column(Numeric(14, 4), nullable=False)
    total_cost = Column(Numeric(14, 4), nullable=False)

    # Estados antes y después de la afectación
    previous_stock = Column(Numeric(14, 4), nullable=False)
    new_stock = Column(Numeric(14, 4), nullable=False)
    previous_avg_cost = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    new_avg_cost = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    # Método de costeo aplicado en el movimiento (PROMEDIO, PEPS)
    costing_method = Column(String(20), default="PROMEDIO", nullable=False)

    # Documento de referencia
    reference_type = Column(String(50), nullable=False)  # FACTURA, REMISION, PEDIDO, AJUSTE, TRASPASO, INVENTARIO_INICIAL
    reference_id = Column(Uuid(as_uuid=True), nullable=True)
    reference_folio = Column(String(50), nullable=True, index=True)
    notes = Column(Text, nullable=True)

    # Auditoría de usuario
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relaciones
    product = relationship("app.modules.master_data.models.Product")
    warehouse = relationship("app.modules.master_data.models.Warehouse")
    user = relationship("app.modules.auth.models.User")
    layer_consumptions = relationship("KardexLayerConsumption", back_populates="kardex_movement", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_kardex_query", "tenant_id", "product_id", "warehouse_id", "created_at"),
    )


class CostLayer(Base, TenantMixin):
    """
    Capas de Costo para el Motor PEPS (FIFO / Primeras Entradas Primeras Salidas).
    Cada entrada de mercancía genera una capa. Las salidas consumen secuencialmente
    las capas más antiguas mediante bloqueo 'SELECT ... FOR UPDATE'.
    """
    __tablename__ = "inventory_cost_layers"

    warehouse_id = Column(Uuid(as_uuid=True), ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Uuid(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    kardex_movement_id = Column(Uuid(as_uuid=True), ForeignKey("inventory_kardex_movements.id", ondelete="CASCADE"), nullable=False)

    original_quantity = Column(Numeric(14, 4), nullable=False)
    remaining_quantity = Column(Numeric(14, 4), nullable=False)
    unit_cost = Column(Numeric(14, 4), nullable=False)
    is_exhausted = Column(Boolean, default=False, nullable=False, index=True)

    __table_args__ = (
        Index("idx_cost_layers_fifo", "tenant_id", "warehouse_id", "product_id", "is_exhausted", "created_at"),
    )


class KardexLayerConsumption(Base, TenantMixin):
    """
    Trazabilidad de Consumo de Capas PEPS.
    Vincula un movimiento de salida con cada una de las capas de costo que agotó o consumió parcialmente.
    """
    __tablename__ = "inventory_kardex_layer_consumptions"

    kardex_movement_id = Column(Uuid(as_uuid=True), ForeignKey("inventory_kardex_movements.id", ondelete="CASCADE"), nullable=False, index=True)
    cost_layer_id = Column(Uuid(as_uuid=True), ForeignKey("inventory_cost_layers.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity_consumed = Column(Numeric(14, 4), nullable=False)
    unit_cost = Column(Numeric(14, 4), nullable=False)
    total_cost = Column(Numeric(14, 4), nullable=False)

    kardex_movement = relationship("KardexMovement", back_populates="layer_consumptions")
    cost_layer = relationship("CostLayer")


class InventoryReservation(Base, TenantMixin):
    """
    Apartados y Reservas de Inventario (Soft Allocation).
    Permite comprometer mercancía al confirmar un Pedido de Venta o Cotización
    sin descontar inmediatamente la existencia física, impidiendo la sobreventa.
    """
    __tablename__ = "inventory_reservations"

    warehouse_id = Column(Uuid(as_uuid=True), ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Uuid(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)

    quantity = Column(Numeric(14, 4), nullable=False)
    # Estado: RESERVED (Apartado Activo), FULFILLED (Consolidado en Venta/Remisión), CANCELLED (Liberado)
    status = Column(String(20), default="RESERVED", nullable=False, index=True)

    reference_type = Column(String(50), nullable=False)  # PEDIDO_VENTA, COTIZACION
    reference_id = Column(Uuid(as_uuid=True), nullable=True)
    reference_folio = Column(String(50), nullable=True)

    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    fulfilled_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    product = relationship("app.modules.master_data.models.Product")
    warehouse = relationship("app.modules.master_data.models.Warehouse")

    __table_args__ = (
        Index("idx_reservations_status", "tenant_id", "warehouse_id", "product_id", "status"),
    )
