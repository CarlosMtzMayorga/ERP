import uuid
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, ForeignKey, Numeric, Text, DateTime, Uuid, Index
)
from sqlalchemy.orm import relationship

from app.core.database import Base, TenantMixin


class BankTransaction(Base, TenantMixin):
    """
    Libro Mayor Inmutable de Bancos y Tesorería (Append-Only Ledger).
    Garantiza que ningún saldo bancario sea sobrescrito arbitrariamente.
    Registra cada entrada (Depósito, Cobro a Clientes) y salida (Retiro, Pago a Proveedores),
    materializando el saldo en tiempo real con trazabilidad y soporte de conciliación bancaria.
    """
    __tablename__ = "bank_transactions"

    bank_account_id = Column(Uuid(as_uuid=True), ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    # Tipo: DEPOSITO, RETIRO, TRANSFERENCIA_ENTRADA, TRANSFERENCIA_SALIDA, PAGO_PROVEEDOR, COBRO_CLIENTE
    transaction_type = Column(String(30), nullable=False, index=True)
    # Dirección: IN (Suma saldo) o OUT (Resta saldo)
    direction = Column(String(5), nullable=False)

    amount = Column(Numeric(14, 2), nullable=False)
    previous_balance = Column(Numeric(14, 2), nullable=False)
    new_balance = Column(Numeric(14, 2), nullable=False)

    # Referencia al documento de negocio de origen
    reference_type = Column(String(50), nullable=False)  # PAGO_PROVEEDOR, COBRO_CLIENTE, TRANSFERENCIA, AJUSTE
    reference_id = Column(Uuid(as_uuid=True), nullable=True)
    reference_folio = Column(String(50), nullable=True, index=True)
    operation_number = Column(String(100), nullable=True, index=True)  # Clave de rastreo SPEI / No. Cheque

    transaction_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Conciliación Bancaria
    is_reconciled = Column(Boolean, default=False, nullable=False, index=True)
    reconciled_at = Column(DateTime(timezone=True), nullable=True)

    notes = Column(Text, nullable=True)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relaciones
    bank_account = relationship("app.modules.master_data.models.BankAccount")
    user = relationship("app.modules.auth.models.User")

    __table_args__ = (
        Index("idx_bank_tx_account_date", "tenant_id", "bank_account_id", "transaction_date"),
        Index("idx_bank_tx_reconciliation", "tenant_id", "bank_account_id", "is_reconciled"),
    )

