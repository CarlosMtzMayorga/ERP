import uuid
from decimal import Decimal
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class BankTransactionCreate(BaseModel):
    bank_account_id: uuid.UUID
    transaction_type: str = Field(..., description="DEPOSITO, RETIRO")
    amount: Decimal = Field(..., gt=0, description="Monto de la transacción")
    operation_number: Optional[str] = None
    notes: Optional[str] = None


class InterbankTransferCreate(BaseModel):
    source_account_id: uuid.UUID
    target_account_id: uuid.UUID
    amount: Decimal = Field(..., gt=0, description="Monto a transferir")
    operation_number: Optional[str] = None
    notes: Optional[str] = None


class ReconciliationRequest(BaseModel):
    bank_account_id: uuid.UUID
    transaction_ids: List[uuid.UUID] = Field(..., min_length=1)


class BankAccountCreate(BaseModel):
    bank_name: str
    account_number: str
    clabe: str
    currency_id: uuid.UUID
    sat_banco_code: Optional[str] = None
    initial_balance: Decimal = Field(default=Decimal("0.00"), ge=0)


class BankTransactionResponse(BaseModel):
    id: uuid.UUID
    bank_account_id: uuid.UUID
    transaction_type: str
    direction: str
    amount: Decimal
    previous_balance: Decimal
    new_balance: Decimal
    reference_type: str
    reference_id: Optional[uuid.UUID] = None
    reference_folio: Optional[str] = None
    operation_number: Optional[str] = None
    transaction_date: datetime
    is_reconciled: bool
    reconciled_at: Optional[datetime] = None
    notes: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BankAccountResponse(BaseModel):
    id: uuid.UUID
    bank_name: str
    account_number: str
    clabe: str
    currency_id: uuid.UUID
    currency_code: Optional[str] = "MXN"
    current_balance: Decimal
    reconciled_balance: Decimal
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class BankingDashboardMetrics(BaseModel):
    total_book_balance: Decimal
    total_reconciled_balance: Decimal
    monthly_inflow: Decimal
    monthly_outflow: Decimal
    accounts: List[BankAccountResponse] = []
    recent_transactions: List[BankTransactionResponse] = []
