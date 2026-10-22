import uuid
from decimal import Decimal
from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class PurchaseItemCreate(BaseModel):
    product_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0, description="Cantidad a ordenar o facturar")
    unit_cost: Decimal = Field(..., ge=0, description="Costo unitario")
    discount_rate: Decimal = Field(default=Decimal("0.0000"), ge=0, le=1)
    freight_prorated: Decimal = Field(default=Decimal("0.0000"), ge=0)
    sat_clave_prod_serv: Optional[str] = "01010101"
    sat_clave_unidad: Optional[str] = "H87"
    vat_rate: Decimal = Field(default=Decimal("0.1600"), ge=0)
    ieps_rate: Decimal = Field(default=Decimal("0.0000"), ge=0)
    source_item_id: Optional[uuid.UUID] = None


class PurchaseOrderCreate(BaseModel):
    branch_id: uuid.UUID
    warehouse_id: uuid.UUID
    supplier_id: uuid.UUID
    currency_id: uuid.UUID
    expected_date: Optional[date] = None
    source_document_id: Optional[uuid.UUID] = None  # Requisición si aplica
    freight_total: Decimal = Field(default=Decimal("0.0000"), ge=0)
    notes: Optional[str] = None
    items: List[PurchaseItemCreate] = Field(..., min_length=1)


class GoodsReceptionItemCreate(BaseModel):
    product_id: uuid.UUID
    quantity_received: Decimal = Field(..., gt=0, description="Cantidad física recibida en almacén")
    unit_cost: Optional[Decimal] = Field(default=None, ge=0, description="Costo unitario si difiere del pactado en OC")
    freight_prorated: Optional[Decimal] = Field(default=Decimal("0.0000"), ge=0)
    source_item_id: Optional[uuid.UUID] = Field(default=None, description="ID de la partida en la Orden de Compra")


class GoodsReceptionCreate(BaseModel):
    branch_id: uuid.UUID
    warehouse_id: uuid.UUID
    supplier_id: uuid.UUID
    currency_id: uuid.UUID
    purchase_order_id: Optional[uuid.UUID] = Field(default=None, description="Orden de Compra a surtir")
    freight_total: Decimal = Field(default=Decimal("0.0000"), ge=0, description="Flete a prorratear en el costo de los ítems")
    notes: Optional[str] = None
    items: List[GoodsReceptionItemCreate] = Field(..., min_length=1)


class SupplierInvoiceCreate(BaseModel):
    branch_id: uuid.UUID
    warehouse_id: uuid.UUID
    supplier_id: uuid.UUID
    currency_id: uuid.UUID
    source_document_id: Optional[uuid.UUID] = Field(default=None, description="Recepción u Orden de Compra previa")
    cfdi_uuid: Optional[str] = None
    serie: Optional[str] = None
    folio: Optional[int] = None
    issue_date: Optional[datetime] = None
    credit_days: Optional[int] = None
    freight_total: Decimal = Field(default=Decimal("0.0000"), ge=0)
    notes: Optional[str] = None
    items: List[PurchaseItemCreate] = Field(..., min_length=1)


class PurchaseDocumentItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    line_number: int
    sku: str
    description: str
    quantity_ordered: Decimal
    quantity_received: Decimal
    unit_cost: Decimal
    discount_amount: Decimal
    freight_prorated: Decimal
    effective_unit_cost: Decimal
    subtotal: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    total: Decimal
    source_item_id: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)


class PurchaseDocumentResponse(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    warehouse_id: uuid.UUID
    supplier_id: uuid.UUID
    currency_id: uuid.UUID
    document_type: str
    status: str
    serie: str
    folio: int
    formatted_folio: str
    issue_date: datetime
    expected_date: Optional[date] = None
    source_document_id: Optional[uuid.UUID] = None
    source_document_type: Optional[str] = None
    cfdi_uuid: Optional[str] = None
    subtotal: Decimal
    discount_total: Decimal
    freight_total: Decimal
    tax_iva_total: Decimal
    total: Decimal
    notes: Optional[str] = None
    items: List[PurchaseDocumentItemResponse] = []
    supplier_name: Optional[str] = None
    supplier_rfc: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PayableDocumentResponse(BaseModel):
    id: uuid.UUID
    supplier_id: uuid.UUID
    branch_id: uuid.UUID
    purchase_document_id: Optional[uuid.UUID] = None
    document_type: str
    serie: Optional[str] = None
    folio: Optional[int] = None
    formatted_folio: str
    cfdi_uuid: Optional[str] = None
    issue_date: datetime
    due_date: date
    credit_days: int
    original_total: Decimal
    original_subtotal: Decimal
    original_vat: Decimal
    current_balance: Decimal
    currency_code: str
    status: str
    supplier_name: Optional[str] = None
    supplier_rfc: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TopSupplierMetric(BaseModel):
    supplier_id: uuid.UUID
    legal_name: str
    rfc: str
    total_purchased: Decimal
    orders_count: int


class PurchasesDashboardMetrics(BaseModel):
    monthly_purchases_total: Decimal
    pending_purchase_orders_count: int
    unpaid_invoices_balance: Decimal
    active_suppliers_count: int
    top_suppliers: List[TopSupplierMetric] = []


class XMLConceptPreview(BaseModel):
    clave_prod_serv: str
    no_identificacion: Optional[str] = None
    cantidad: Decimal
    clave_unidad: str
    unidad: Optional[str] = None
    descripcion: str
    valor_unitario: Decimal
    importe: Decimal
    descuento: Decimal = Decimal("0.0000")
    objeto_imp: str = "02"
    iva_importe: Decimal = Decimal("0.0000")
    iva_tasa: Decimal = Decimal("0.1600")
    matched_product_id: Optional[uuid.UUID] = None
    matched_sku: Optional[str] = None


class XMLInvoicePreview(BaseModel):
    uuid: str
    serie: Optional[str] = None
    folio: Optional[str] = None
    fecha: str
    forma_pago: Optional[str] = None
    metodo_pago: Optional[str] = None
    moneda: str = "MXN"
    tipo_cambio: Decimal = Decimal("1.0000")
    subtotal: Decimal
    descuento: Decimal = Decimal("0.0000")
    total_iva: Decimal = Decimal("0.0000")
    total_retenciones: Decimal = Decimal("0.0000")
    total: Decimal
    emisor_rfc: str
    emisor_nombre: str
    emisor_regimen: Optional[str] = None
    receptor_rfc: str
    supplier_exists: bool = False
    supplier_id: Optional[uuid.UUID] = None
    supplier_credit_days: int = 0
    concepts: List[XMLConceptPreview] = []


class ConfirmXMLImportRequest(BaseModel):
    branch_id: uuid.UUID
    warehouse_id: uuid.UUID
    currency_id: uuid.UUID
    invoices: List[XMLInvoicePreview]
