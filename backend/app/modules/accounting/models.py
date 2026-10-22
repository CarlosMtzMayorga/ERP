import uuid
from decimal import Decimal
from datetime import datetime, timezone, date
from sqlalchemy import (
    Column, String, Boolean, ForeignKey, Numeric, Text, DateTime, Date, Integer, Uuid, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship

from app.core.database import Base, TenantMixin


class Account(Base, TenantMixin):
    """
    Catálogo de Cuentas Contables con Jerarquía Recursiva y Mapeo al SAT (Anexo 24).
    """
    __tablename__ = "accounting_accounts"

    parent_id = Column(Uuid(as_uuid=True), ForeignKey("accounting_accounts.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Identificación Contable
    account_number = Column(String(50), nullable=False, index=True)  # Ej: 1105-001
    name = Column(String(200), nullable=False)
    
    # Naturaleza y Clasificación
    nature = Column(String(10), nullable=False)  # DEUDORA o ACREEDORA
    account_type = Column(String(20), nullable=False)  # ACTIVO, PASIVO, CAPITAL, INGRESOS, COSTOS, GASTOS
    level = Column(Integer, default=1, nullable=False)
    is_group = Column(Boolean, default=False, nullable=False)  # True = Cuenta de Mayor / Agrupadora (no imputable)

    # Contabilidad Electrónica SAT (Código Agrupador)
    sat_group_code = Column(String(20), nullable=False, index=True)  # Ej: 105.01

    # Saldos
    initial_balance = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    current_balance = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relación Recursiva
    parent = relationship("Account", remote_side="Account.id", backref="subaccounts")

    __table_args__ = (
        UniqueConstraint("tenant_id", "account_number", name="uq_accounting_account_number_per_tenant"),
    )


class JournalEntry(Base, TenantMixin):
    """
    Póliza Contable Transaccional de Partida Doble (Ingresos, Egresos, Diario).
    Garantiza que sum(debit) == sum(credit).
    """
    __tablename__ = "accounting_journal_entries"

    folio = Column(String(30), nullable=False, index=True)  # Ej: POL-ING-2026-0001
    entry_type = Column(String(15), nullable=False, index=True)  # INGRESO, EGRESO, DIARIO
    entry_date = Column(Date, nullable=False, index=True)
    concept = Column(String(300), nullable=False)

    # Totales Cuadrados
    total_debit = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    total_credit = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)

    # Estado: BORRADOR, APLICADA, CANCELADA
    status = Column(String(20), default="APLICADA", nullable=False, index=True)

    # Trazabilidad con el origen de la operación (Venta, Compra, Bancos, Nómina, etc.)
    source_module = Column(String(20), default="MANUAL", nullable=False, index=True)
    source_id = Column(Uuid(as_uuid=True), nullable=True, index=True)
    source_folio = Column(String(50), nullable=True)
    user_id = Column(Uuid(as_uuid=True), nullable=True)

    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    lines = relationship("JournalEntryLine", back_populates="journal_entry", cascade="all, delete-orphan", order_by="JournalEntryLine.line_number")

    __table_args__ = (
        UniqueConstraint("tenant_id", "folio", name="uq_accounting_entry_folio_per_tenant"),
    )


class JournalEntryLine(Base):
    """
    Partida individual de una póliza (Cargo o Abono) vinculada a una cuenta contable.
    Permite asociar el UUID del CFDI para cumplimiento fiscal SAT.
    """
    __tablename__ = "accounting_journal_entry_lines"

    journal_entry_id = Column(Uuid(as_uuid=True), ForeignKey("accounting_journal_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(Uuid(as_uuid=True), ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    line_number = Column(Integer, nullable=False)
    concept = Column(String(250), nullable=False)

    debit = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)   # Cargo
    credit = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)  # Abono

    # Trazabilidad de Contabilidad Electrónica SAT
    cfdi_uuid = Column(String(36), nullable=True, index=True)

    # Relaciones
    journal_entry = relationship("JournalEntry", back_populates="lines")
    account = relationship("Account")
