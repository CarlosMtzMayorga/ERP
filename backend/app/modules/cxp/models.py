import uuid
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, ForeignKey, Numeric, Text, DateTime, Integer, Uuid, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship

from app.core.database import Base, TenantMixin
from app.modules.purchases.models import PayableDocument


class SupplierPayment(Base, TenantMixin):
    """
    Comprobante de Egreso / Pago a Proveedores.
    Registra la liquidación o abono a una o varias facturas de compra (PayableDocuments),
    extrayendo fondos de forma atómica de la cuenta bancaria de la empresa.
    """
    __tablename__ = "cxp_supplier_payments"

    supplier_id = Column(Uuid(as_uuid=True), ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True)
    branch_id = Column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True)
    bank_account_id = Column(Uuid(as_uuid=True), ForeignKey("bank_accounts.id", ondelete="RESTRICT"), nullable=False, index=True)

    serie = Column(String(10), default="PP", nullable=False)
    folio = Column(Integer, nullable=False)
    formatted_folio = Column(String(30), nullable=False, index=True)

    payment_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    payment_method = Column(String(10), default="03", nullable=False)  # 03 = Transferencia, 02 = Cheque, 01 = Efectivo
    amount = Column(Numeric(14, 2), nullable=False)
    operation_number = Column(String(100), nullable=True)  # Clave de rastreo SPEI / Referencia bancaria

    notes = Column(Text, nullable=True)
    status = Column(String(20), default="APLICADO", nullable=False, index=True)  # APLICADO, CANCELADO
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relaciones
    supplier = relationship("app.modules.master_data.models.Supplier")
    branch = relationship("app.modules.tenants.models.Branch")
    bank_account = relationship("app.modules.master_data.models.BankAccount")
    user = relationship("app.modules.auth.models.User")
    related_docs = relationship("SupplierPaymentDocRel", back_populates="payment", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "serie", "folio", name="uq_cxp_payments_folio"),
        Index("idx_cxp_payments_supplier_date", "tenant_id", "supplier_id", "payment_date"),
    )


class SupplierPaymentDocRel(Base, TenantMixin):
    """
    Detalle de Documentos Liquidados en el Pago a Proveedores.
    Guarda la trazabilidad de la parcialidad y el desglose de retenciones proporcionales reales (IVA / ISR)
    efectuadas en el pago para la contabilidad financiera.
    """
    __tablename__ = "cxp_supplier_payment_doc_rels"

    supplier_payment_id = Column(Uuid(as_uuid=True), ForeignKey("cxp_supplier_payments.id", ondelete="CASCADE"), nullable=False, index=True)
    payable_document_id = Column(Uuid(as_uuid=True), ForeignKey("cxp_payable_documents.id", ondelete="RESTRICT"), nullable=False, index=True)

    installment_number = Column(Integer, default=1, nullable=False)
    previous_balance = Column(Numeric(14, 2), nullable=False)
    amount_paid = Column(Numeric(14, 2), nullable=False)
    remaining_balance = Column(Numeric(14, 2), nullable=False)

    # Desglose Proporcional para Contabilidad y Auditoría Fiscal
    proportional_subtotal = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    proportional_vat = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    proportional_retention_vat = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    proportional_retention_isr = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)

    payment = relationship("SupplierPayment", back_populates="related_docs")
    payable_document = relationship("app.modules.purchases.models.PayableDocument")

