import uuid
from decimal import Decimal
from datetime import datetime, timezone, date
from sqlalchemy import (
    Column, String, Boolean, ForeignKey, Numeric, Text, DateTime, Date, Integer, Uuid, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship

from app.core.database import Base, TenantMixin


class ReceivableDocument(Base, TenantMixin):
    """
    Documento por Cobrar (Cargo en Cuenta del Cliente).
    Registra cada factura, remisión a crédito o saldo inicial pendiente de pago.
    """
    __tablename__ = "cxc_receivable_documents"

    customer_id = Column(Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True)
    branch_id = Column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True)
    sales_document_id = Column(Uuid(as_uuid=True), ForeignKey("sales_documents.id", ondelete="SET NULL"), nullable=True, index=True)

    # Identificación
    document_type = Column(String(20), default="FACTURA", nullable=False)  # FACTURA, REMISION, SALDO_INICIAL
    serie = Column(String(10), nullable=False)
    folio = Column(Integer, nullable=False)
    formatted_folio = Column(String(30), nullable=False, index=True)
    cfdi_uuid = Column(String(36), nullable=True, index=True)

    # Fechas
    issue_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    due_date = Column(Date, nullable=False, index=True)  # Fecha de Vencimiento
    credit_days = Column(Integer, default=0, nullable=False)

    # Importes Originales del Documento
    original_total = Column(Numeric(14, 4), nullable=False)
    original_subtotal = Column(Numeric(14, 4), nullable=False)
    original_vat = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    original_retention_vat = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    original_retention_isr = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    # Saldo Insoluto Actual
    current_balance = Column(Numeric(14, 4), nullable=False)
    currency_code = Column(String(3), default="MXN", nullable=False)

    # Estado: PENDIENTE (sin pagos), PARCIAL (con abonos), LIQUIDADO (saldo 0), CANCELADO
    status = Column(String(20), default="PENDIENTE", nullable=False, index=True)

    # Relaciones
    customer = relationship("app.modules.master_data.models.Customer")
    branch = relationship("app.modules.tenants.models.Branch")
    sales_document = relationship("app.modules.sales.models.SalesDocument")
    installments = relationship("PaymentReceiptDocRel", back_populates="receivable_document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_cxc_cust_status_due", "tenant_id", "customer_id", "status", "due_date"),
    )


class PaymentReceipt(Base, TenantMixin):
    """
    Recibo de Pago / Complemento de Recepción de Pagos SAT (REP 2.0 / CFDI 4.0 tipo P).
    """
    __tablename__ = "cxc_payment_receipts"

    customer_id = Column(Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True)
    branch_id = Column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    # Identificación
    serie = Column(String(10), default="PAGO", nullable=False)
    folio = Column(Integer, nullable=False)
    formatted_folio = Column(String(30), nullable=False, index=True)

    # Datos Bancarios del Pago (Nodo Pago SAT)
    payment_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    payment_form = Column(String(5), default="03", nullable=False)  # 01 Efectivo, 03 Transferencia, 02 Cheque
    currency_code = Column(String(3), default="MXN", nullable=False)
    exchange_rate = Column(Numeric(10, 4), default=Decimal("1.0000"), nullable=False)
    amount = Column(Numeric(14, 4), nullable=False)  # Monto total del pago
    operation_number = Column(String(100), nullable=True)  # NumOperacion

    # Cuentas Bancarias
    sender_rfc = Column(String(13), nullable=True)
    sender_bank = Column(String(100), nullable=True)
    sender_account = Column(String(50), nullable=True)
    receiver_rfc = Column(String(13), nullable=True)
    receiver_account = Column(String(50), nullable=True)

    # Timbrado Fiscal SAT CFDI 4.0 (Tipo Comprobante: P)
    cfdi_uuid = Column(String(36), nullable=True, index=True)
    cfdi_xml = Column(Text, nullable=True)
    cfdi_stamped_at = Column(DateTime(timezone=True), nullable=True)
    cfdi_sello = Column(Text, nullable=True)
    cfdi_cadena_original = Column(Text, nullable=True)

    # Estado: TIMBRADO, CANCELADO
    status = Column(String(20), default="TIMBRADO", nullable=False, index=True)
    notes = Column(Text, nullable=True)

    customer = relationship("app.modules.master_data.models.Customer")
    branch = relationship("app.modules.tenants.models.Branch")
    user = relationship("app.modules.auth.models.User")
    related_docs = relationship("PaymentReceiptDocRel", back_populates="payment_receipt", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "serie", "folio", name="uq_cxc_receipt_folio"),
    )


class PaymentReceiptDocRel(Base, TenantMixin):
    """
    Documento Relacionado (DoctoRelacionado) en el Complemento de Pago REP 2.0.
    Contiene la trazabilidad matemática de la parcialidad y el desglose de impuestos proporcionales.
    """
    __tablename__ = "cxc_payment_doc_rels"

    payment_receipt_id = Column(Uuid(as_uuid=True), ForeignKey("cxc_payment_receipts.id", ondelete="CASCADE"), nullable=False, index=True)
    receivable_document_id = Column(Uuid(as_uuid=True), ForeignKey("cxc_receivable_documents.id", ondelete="RESTRICT"), nullable=False, index=True)

    document_uuid = Column(String(36), nullable=False, index=True)  # IdDocumento (UUID factura origen)
    serie = Column(String(10), nullable=True)
    folio = Column(String(30), nullable=True)
    currency_dr = Column(String(3), default="MXN", nullable=False)  # MonedaDR
    equivalence_dr = Column(Numeric(10, 4), default=Decimal("1.0000"), nullable=False) # EquivalenciaDR

    installment_number = Column(Integer, default=1, nullable=False) # NumParcialidad
    previous_balance = Column(Numeric(14, 4), nullable=False)       # ImpSaldoAnt
    amount_paid = Column(Numeric(14, 4), nullable=False)            # ImpPagado
    remaining_balance = Column(Numeric(14, 4), nullable=False)      # ImpSaldoInsoluto

    # Desglose Fiscal Proporcional REP 2.0 (Regla de Oro SAT):
    # BaseP + ImporteP - RetencionesP = ImpPagado
    proportional_base = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    proportional_vat = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    vat_rate = Column(Numeric(5, 4), default=Decimal("0.1600"), nullable=False)
    proportional_retention_vat = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    proportional_retention_isr = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    payment_receipt = relationship("PaymentReceipt", back_populates="related_docs")
    receivable_document = relationship("ReceivableDocument", back_populates="installments")

