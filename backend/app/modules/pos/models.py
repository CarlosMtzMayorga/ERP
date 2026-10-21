import uuid
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, ForeignKey, Numeric, Text, DateTime, Integer, Uuid, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship

from app.core.database import Base, TenantMixin


class CashRegister(Base, TenantMixin):
    """
    Caja Registradora / Terminal de Cobro de Punto de Venta.
    """
    __tablename__ = "pos_cash_registers"

    branch_id = Column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    warehouse_id = Column(Uuid(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True)

    code = Column(String(20), nullable=False)   # CAJA-01, CAJA-02
    name = Column(String(100), nullable=False)  # Caja Mostrador Principal
    is_active = Column(Boolean, default=True, nullable=False)

    branch = relationship("app.modules.tenants.models.Branch")
    warehouse = relationship("app.modules.master_data.models.Warehouse")
    sessions = relationship("CashSession", back_populates="cash_register", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_pos_registers_tenant_code"),
    )


class CashSession(Base, TenantMixin):
    """
    Turno / Sesión de Caja.
    Máquina de estados: CLOSED -> OPEN -> CLOSING -> CLOSED.
    Garantiza que ningún cajero opere sin declarar un fondo inicial de apertura.
    """
    __tablename__ = "pos_cash_sessions"

    cash_register_id = Column(Uuid(as_uuid=True), ForeignKey("pos_cash_registers.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    # Estado: OPEN, CLOSING, CLOSED
    status = Column(String(20), default="OPEN", nullable=False, index=True)

    opened_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    # Arqueo de Efectivo
    initial_cash = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)  # Fondo de caja
    expected_cash = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False) # Calculado por el sistema
    declared_cash = Column(Numeric(14, 4), nullable=True)                              # Conteo físico del cajero
    difference_cash = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False) # Sobrante (+) o Faltante (-)

    # Arqueo de Tarjetas / Terminales Bancarias
    expected_card = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    declared_card = Column(Numeric(14, 4), nullable=True)
    difference_card = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    # Métricas del turno
    total_sales = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    tickets_count = Column(Integer, default=0, nullable=False)
    notes = Column(Text, nullable=True)

    cash_register = relationship("CashRegister", back_populates="sessions")
    user = relationship("app.modules.auth.models.User")
    movements = relationship("CashMovement", back_populates="session", cascade="all, delete-orphan")
    tickets = relationship("POSTicket", back_populates="session")


class CashMovement(Base, TenantMixin):
    """
    Movimientos de Efectivo en Caja (Entradas de cambio y Retiros parciales durante el turno).
    """
    __tablename__ = "pos_cash_movements"

    cash_session_id = Column(Uuid(as_uuid=True), ForeignKey("pos_cash_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    # Tipo: ENTRY (Entrada de cambio), WITHDRAWAL (Retiro de seguridad / corte parcial)
    movement_type = Column(String(20), nullable=False)
    amount = Column(Numeric(14, 4), nullable=False)
    reason = Column(String(255), nullable=False)

    session = relationship("CashSession", back_populates="movements")
    user = relationship("app.modules.auth.models.User")


class POSTicket(Base, TenantMixin):
    """
    Ticket de Venta en Punto de Venta.
    Transacción de alta velocidad con descarga inmediata en Kardex y afectación de caja.
    """
    __tablename__ = "pos_tickets"

    cash_session_id = Column(Uuid(as_uuid=True), ForeignKey("pos_cash_sessions.id", ondelete="RESTRICT"), nullable=False, index=True)
    cash_register_id = Column(Uuid(as_uuid=True), ForeignKey("pos_cash_registers.id", ondelete="RESTRICT"), nullable=False, index=True)
    branch_id = Column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True)
    warehouse_id = Column(Uuid(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_id = Column(Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    serie = Column(String(10), nullable=False)
    folio = Column(Integer, nullable=False)
    formatted_folio = Column(String(30), nullable=False, index=True)

    # Estado: PAID, CANCELLED
    status = Column(String(20), default="PAID", nullable=False, index=True)

    subtotal = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    discount_total = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    tax_iva_total = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    total = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    total_cost_cogs = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    # Desglose de Forma de Pago
    payment_method = Column(String(20), default="EFECTIVO", nullable=False)  # EFECTIVO, TARJETA, TRANSFERENCIA, MIXTO
    amount_cash = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    amount_card = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    amount_transfer = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    amount_paid = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)   # Lo recibido del cliente
    change_returned = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False) # Cambio entregado

    # Facturación Global CFDI 4.0
    is_globally_invoiced = Column(Boolean, default=False, nullable=False, index=True)
    global_invoice_id = Column(Uuid(as_uuid=True), ForeignKey("sales_documents.id", ondelete="SET NULL"), nullable=True)

    session = relationship("CashSession", back_populates="tickets")
    cash_register = relationship("CashRegister")
    user = relationship("app.modules.auth.models.User")
    customer = relationship("app.modules.master_data.models.Customer")
    warehouse = relationship("app.modules.master_data.models.Warehouse")
    items = relationship("POSTicketItem", back_populates="ticket", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "serie", "folio", name="uq_pos_tickets_folio"),
        Index("idx_pos_tickets_session", "tenant_id", "cash_session_id", "status"),
    )


class POSTicketItem(Base, TenantMixin):
    """
    Partida / Línea de Ticket de Venta.
    """
    __tablename__ = "pos_ticket_items"

    ticket_id = Column(Uuid(as_uuid=True), ForeignKey("pos_tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Uuid(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)

    line_number = Column(Integer, default=1, nullable=False)
    sku = Column(String(50), nullable=False)
    description = Column(String(255), nullable=False)

    quantity = Column(Numeric(14, 4), nullable=False)
    unit_price = Column(Numeric(14, 4), nullable=False)
    discount_amount = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    subtotal = Column(Numeric(14, 4), nullable=False)
    vat_rate = Column(Numeric(5, 4), default=Decimal("0.1600"), nullable=False)
    vat_amount = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    total = Column(Numeric(14, 4), nullable=False)

    # Costo de Venta asignado (PEPS / Promedio)
    unit_cost = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    total_cost = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    ticket = relationship("POSTicket", back_populates="items")
    product = relationship("app.modules.master_data.models.Product")

