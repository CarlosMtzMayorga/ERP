import uuid
from decimal import Decimal
from datetime import datetime, timezone, date
from sqlalchemy import (
    Column, String, Boolean, ForeignKey, Numeric, Text, DateTime, Date, Integer, Uuid, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship

from app.core.database import Base, TenantMixin


class PurchaseDocument(Base, TenantMixin):
    """
    Documento Comercial y de Aprovisionamiento de Compras.
    Soporta el flujo de trazabilidad completo:
    Requisición -> Orden de Compra (OC) -> Recepción de Mercancía -> Factura de Proveedor.
    """
    __tablename__ = "purchase_documents"

    branch_id = Column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True)
    warehouse_id = Column(Uuid(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True)
    supplier_id = Column(Uuid(as_uuid=True), ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True)
    currency_id = Column(Uuid(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False)

    # Tipo: REQUISICION, ORDEN_COMPRA, RECEPCION, FACTURA_PROVEEDOR
    document_type = Column(String(25), nullable=False, index=True)
    # Estado: BORRADOR, AUTORIZADA, PARCIALMENTE_RECIBIDA, RECIBIDA, FACTURADA, CANCELADA
    status = Column(String(30), default="BORRADOR", nullable=False, index=True)

    serie = Column(String(10), nullable=False)
    folio = Column(Integer, nullable=False)
    formatted_folio = Column(String(30), nullable=False, index=True)

    issue_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expected_date = Column(Date, nullable=True)

    # Trazabilidad y referencias cruzadas (Backorders)
    source_document_id = Column(Uuid(as_uuid=True), ForeignKey("purchase_documents.id", ondelete="SET NULL"), nullable=True, index=True)
    source_document_type = Column(String(25), nullable=True)

    # Identificación Fiscal CFDI 4.0 del Proveedor (si es factura)
    cfdi_uuid = Column(String(36), nullable=True, index=True)

    # Importes Financieros y Prorrateos
    exchange_rate = Column(Numeric(14, 4), default=Decimal("1.0000"), nullable=False)
    subtotal = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    discount_total = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    freight_total = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)  # Gastos de flete para prorrateo
    tax_iva_total = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    tax_ieps_total = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    retention_iva_total = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    retention_isr_total = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    total = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    notes = Column(Text, nullable=True)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relaciones
    supplier = relationship("app.modules.master_data.models.Supplier")
    branch = relationship("app.modules.tenants.models.Branch")
    warehouse = relationship("app.modules.master_data.models.Warehouse")
    currency = relationship("app.modules.master_data.models.Currency")
    user = relationship("app.modules.auth.models.User")
    items = relationship("PurchaseDocumentItem", back_populates="document", cascade="all, delete-orphan")
    source_document = relationship("PurchaseDocument", remote_side="PurchaseDocument.id", foreign_keys=[source_document_id])

    __table_args__ = (
        UniqueConstraint("tenant_id", "document_type", "serie", "folio", name="uq_purchase_doc_folio"),
        Index("idx_purchases_tenant_date", "tenant_id", "document_type", "issue_date"),
    )


class PurchaseDocumentItem(Base, TenantMixin):
    """
    Partida / Línea de Documento de Compra.
    Controla cantidades pedidas vs recibidas (Backorders) y el prorrateo de costos/fletes.
    """
    __tablename__ = "purchase_document_items"

    purchase_document_id = Column(Uuid(as_uuid=True), ForeignKey("purchase_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Uuid(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)

    line_number = Column(Integer, default=1, nullable=False)
    sku = Column(String(50), nullable=False)
    description = Column(String(255), nullable=False)

    # Cantidad del documento y control de backorders
    quantity_ordered = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    quantity_received = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    unit_cost = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    discount_rate = Column(Numeric(5, 4), default=Decimal("0.0000"), nullable=False)
    discount_amount = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    # Flete prorrateado y Costo Unitario Efectivo para valuación en Kardex
    freight_prorated = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    effective_unit_cost = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    subtotal = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    # Catálogos SAT
    sat_clave_prod_serv = Column(String(10), default="01010101", nullable=False)
    sat_clave_unidad = Column(String(10), default="H87", nullable=False)
    unit_name = Column(String(20), default="PZA", nullable=False)

    # Impuestos
    vat_rate = Column(Numeric(5, 4), default=Decimal("0.1600"), nullable=False)
    vat_amount = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    ieps_rate = Column(Numeric(5, 4), default=Decimal("0.0000"), nullable=False)
    ieps_amount = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    retention_vat_rate = Column(Numeric(5, 4), default=Decimal("0.0000"), nullable=False)
    retention_vat_amount = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    retention_isr_rate = Column(Numeric(5, 4), default=Decimal("0.0000"), nullable=False)
    retention_isr_amount = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    total = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    # Enlace a partida de origen (para rastreo de surtido de ítems)
    source_item_id = Column(Uuid(as_uuid=True), nullable=True)

    document = relationship("PurchaseDocument", back_populates="items")
    product = relationship("app.modules.master_data.models.Product")


class PayableDocument(Base, TenantMixin):
    """
    Documento por Pagar (Pasivo con Proveedores - Cuentas por Pagar / CxP).
    Se genera automáticamente al aprobar una Factura de Proveedor (manual o XML CFDI 4.0),
    calculando la fecha de vencimiento según los días de crédito del proveedor.
    """
    __tablename__ = "cxp_payable_documents"

    supplier_id = Column(Uuid(as_uuid=True), ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True)
    branch_id = Column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True)
    purchase_document_id = Column(Uuid(as_uuid=True), ForeignKey("purchase_documents.id", ondelete="SET NULL"), nullable=True, index=True)

    # Identificación
    document_type = Column(String(25), default="FACTURA_PROVEEDOR", nullable=False)
    serie = Column(String(10), nullable=True)
    folio = Column(Integer, nullable=True)
    formatted_folio = Column(String(30), nullable=False, index=True)
    cfdi_uuid = Column(String(36), nullable=True, index=True)

    # Fechas
    issue_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    due_date = Column(Date, nullable=False, index=True)  # Vencimiento según credit_days
    credit_days = Column(Integer, default=0, nullable=False)

    # Importes Originales del Pasivo
    original_total = Column(Numeric(14, 4), nullable=False)
    original_subtotal = Column(Numeric(14, 4), nullable=False)
    original_vat = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    original_retention_vat = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    original_retention_isr = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    # Saldo Pendiente Actual
    current_balance = Column(Numeric(14, 4), nullable=False)
    currency_code = Column(String(3), default="MXN", nullable=False)

    # Estado: PENDIENTE (sin pagos), PARCIAL (con abonos), LIQUIDADO (saldo 0), CANCELADO
    status = Column(String(20), default="PENDIENTE", nullable=False, index=True)

    # Relaciones
    supplier = relationship("app.modules.master_data.models.Supplier")
    branch = relationship("app.modules.tenants.models.Branch")
    purchase_document = relationship("PurchaseDocument")

    __table_args__ = (
        Index("idx_cxp_supplier_due", "tenant_id", "supplier_id", "due_date", "status"),
    )
