import uuid
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, ForeignKey, Numeric, Text, DateTime, Integer, Uuid, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship

from app.core.database import Base, TenantMixin


class SalesDocument(Base, TenantMixin):
    """
    Documento Comercial y Fiscal de Ventas.
    Soporta el flujo encadenado: Cotización -> Pedido -> Remisión -> Factura (CFDI 4.0).
    """
    __tablename__ = "sales_documents"

    branch_id = Column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True)
    warehouse_id = Column(Uuid(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_id = Column(Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True)
    price_list_id = Column(Uuid(as_uuid=True), ForeignKey("price_lists.id", ondelete="SET NULL"), nullable=True)
    currency_id = Column(Uuid(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False)

    # Tipo: COTIZACION, PEDIDO, REMISION, FACTURA
    document_type = Column(String(20), nullable=False, index=True)
    # Estado: BORRADOR, PENDIENTE, APROBADO, PARCIALMENTE_SURTIDO, SURTIDO, TIMBRADO, CANCELADO
    status = Column(String(30), default="BORRADOR", nullable=False, index=True)

    serie = Column(String(10), nullable=False)
    folio = Column(Integer, nullable=False)
    formatted_folio = Column(String(30), nullable=False, index=True)

    # Encadenamiento y Trazabilidad Documental
    source_document_id = Column(Uuid(as_uuid=True), nullable=True, index=True)
    source_document_type = Column(String(20), nullable=True)

    # Importes y Totales Financieros (Precisión interna 4 decimales)
    exchange_rate = Column(Numeric(14, 4), default=Decimal("1.0000"), nullable=False)
    subtotal = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    discount_total = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    tax_iva_total = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    tax_ieps_total = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    retention_iva_total = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    retention_isr_total = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    total = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    # Costo de Ventas (COGS - Cost of Goods Sold evaluado en el Kardex)
    total_cost_cogs = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    # Datos Fiscales SAT CFDI 4.0
    payment_form = Column(String(5), default="03", nullable=False)   # c_FormaPago (01 Efectivo, 03 Transferencia)
    payment_method = Column(String(5), default="PUE", nullable=False) # c_MetodoPago (PUE, PPD)
    cfdi_use = Column(String(5), default="G03", nullable=False)       # c_UsoCFDI (G01, G03, CP01)
    
    # Timbrado Fiscal SAT
    cfdi_uuid = Column(String(36), nullable=True, index=True)         # Folio Fiscal UUID
    cfdi_xml = Column(Text, nullable=True)                            # XML timbrado con TFD
    cfdi_stamped_at = Column(DateTime(timezone=True), nullable=True)
    cfdi_sello = Column(Text, nullable=True)
    cfdi_cadena_original = Column(Text, nullable=True)

    # Cancelación Fiscal SAT
    cancellation_reason = Column(String(5), nullable=True)            # 01, 02, 03, 04
    cancellation_uuid_replacement = Column(String(36), nullable=True)

    notes = Column(Text, nullable=True)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relaciones
    customer = relationship("app.modules.master_data.models.Customer")
    warehouse = relationship("app.modules.master_data.models.Warehouse")
    branch = relationship("app.modules.tenants.models.Branch")
    currency = relationship("app.modules.master_data.models.Currency")
    user = relationship("app.modules.auth.models.User")
    items = relationship("SalesDocumentItem", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "document_type", "serie", "folio", name="uq_sales_doc_folio"),
        Index("idx_sales_tenant_date", "tenant_id", "document_type", "created_at"),
    )


class SalesDocumentItem(Base, TenantMixin):
    """
    Partida / Línea de Documento de Venta con desglose fiscal SAT.
    """
    __tablename__ = "sales_document_items"

    sales_document_id = Column(Uuid(as_uuid=True), ForeignKey("sales_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Uuid(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)

    line_number = Column(Integer, default=1, nullable=False)
    sku = Column(String(50), nullable=False)
    description = Column(String(255), nullable=False)

    quantity = Column(Numeric(14, 4), nullable=False)
    unit_price = Column(Numeric(14, 4), nullable=False)
    discount_rate = Column(Numeric(5, 4), default=Decimal("0.0000"), nullable=False)
    discount_amount = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    subtotal = Column(Numeric(14, 4), nullable=False)  # (quantity * unit_price) - discount_amount

    # Claves Fiscales SAT
    sat_clave_prod_serv = Column(String(10), default="01010101", nullable=False)
    sat_clave_unidad = Column(String(10), default="H87", nullable=False)
    unit_name = Column(String(20), default="PZA", nullable=False)
    sat_objeto_imp = Column(String(5), default="02", nullable=False)  # 02 = Sí objeto de impuesto

    # Impuestos Trasladados y Retenidos por Partida
    vat_rate = Column(Numeric(5, 4), default=Decimal("0.1600"), nullable=False)
    vat_amount = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    
    ieps_rate = Column(Numeric(5, 4), default=Decimal("0.0000"), nullable=False)
    ieps_amount = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    retention_vat_rate = Column(Numeric(5, 4), default=Decimal("0.0000"), nullable=False)
    retention_vat_amount = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    retention_isr_rate = Column(Numeric(5, 4), default=Decimal("0.0000"), nullable=False)
    retention_isr_amount = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    total = Column(Numeric(14, 4), nullable=False)

    # Costo de Venta asignado a la partida
    unit_cost = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    total_cost = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    document = relationship("SalesDocument", back_populates="items")
    product = relationship("app.modules.master_data.models.Product")

