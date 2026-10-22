import uuid
from decimal import Decimal
from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class PaymentDistributionItem(BaseModel):
    payable_document_id: uuid.UUID
    amount_to_apply: Decimal = Field(..., gt=0, description="Monto específico a abonar a esta factura")


class ApplySupplierPaymentRequest(BaseModel):
    supplier_id: uuid.UUID
    branch_id: uuid.UUID
    bank_account_id: uuid.UUID
    amount: Decimal = Field(..., gt=0, description="Monto total del pago a transferir")
    payment_method: str = Field(default="03", description="03 = Transferencia, 02 = Cheque, 01 = Efectivo")
    operation_number: Optional[str] = None
    notes: Optional[str] = None
    distributions: Optional[List[PaymentDistributionItem]] = Field(
        default=None,
        description="Distribución específica entre facturas. Si se omite, se distribuye automáticamente de más antigua a más reciente."
    )


class SupplierPaymentDocRelResponse(BaseModel):
    payable_document_id: uuid.UUID
    formatted_folio: Optional[str] = None
    installment_number: int
    previous_balance: Decimal
    amount_paid: Decimal
    remaining_balance: Decimal
    proportional_subtotal: Decimal
    proportional_vat: Decimal
    proportional_retention_vat: Decimal
    proportional_retention_isr: Decimal

    model_config = ConfigDict(from_attributes=True)


class SupplierPaymentResponse(BaseModel):
    id: uuid.UUID
    formatted_folio: str
    supplier_id: uuid.UUID
    supplier_name: Optional[str] = None
    supplier_rfc: Optional[str] = None
    bank_account_id: uuid.UUID
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    payment_date: datetime
    payment_method: str
    amount: Decimal
    operation_number: Optional[str] = None
    status: str
    notes: Optional[str] = None
    related_docs: List[SupplierPaymentDocRelResponse] = []

    model_config = ConfigDict(from_attributes=True)


class PaymentScheduleItem(BaseModel):
    id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str
    supplier_rfc: str
    formatted_folio: str
    cfdi_uuid: Optional[str] = None
    issue_date: datetime
    due_date: date
    days_until_due: int
    is_overdue: bool
    credit_days: int
    original_total: Decimal
    original_retention_vat: Decimal
    original_retention_isr: Decimal
    current_balance: Decimal
    status: str


class PaymentScheduleSummary(BaseModel):
    total_debt: Decimal
    overdue_total: Decimal
    due_today_total: Decimal
    due_this_week_total: Decimal
    due_later_total: Decimal
    items: List[PaymentScheduleItem] = []


class CxPDashboardMetrics(BaseModel):
    total_accounts_payable: Decimal
    overdue_payable: Decimal
    paid_this_month: Decimal
    active_creditors_count: int
    schedule_summary: PaymentScheduleSummary

