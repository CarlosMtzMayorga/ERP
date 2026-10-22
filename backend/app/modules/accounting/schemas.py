import uuid
from decimal import Decimal
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ==========================================
# CUENTAS CONTABLES
# ==========================================
class AccountBase(BaseModel):
    account_number: str = Field(..., max_length=50, description="Ej: 1105-001")
    name: str = Field(..., max_length=200)
    nature: str = Field(..., description="DEUDORA o ACREEDORA")
    account_type: str = Field(..., description="ACTIVO, PASIVO, CAPITAL, INGRESOS, COSTOS, GASTOS")
    level: int = Field(1, ge=1)
    is_group: bool = Field(False, description="True si es cuenta de mayor no imputable")
    sat_group_code: str = Field(..., max_length=20, description="Código Agrupador SAT (ej: 105.01)")
    parent_id: Optional[uuid.UUID] = None


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    sat_group_code: Optional[str] = None
    is_active: Optional[bool] = None


class AccountResponse(AccountBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    initial_balance: Decimal
    current_balance: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# PARTIDAS Y PÓLIZAS CONTABLES
# ==========================================
class JournalEntryLineCreate(BaseModel):
    account_id: uuid.UUID
    concept: str = Field(..., max_length=250)
    debit: Decimal = Field(Decimal("0.00"), ge=0, description="Cargo")
    credit: Decimal = Field(Decimal("0.00"), ge=0, description="Abono")
    cfdi_uuid: Optional[str] = Field(None, max_length=36, description="UUID CFDI para Contabilidad Electrónica")


class JournalEntryLineResponse(BaseModel):
    id: uuid.UUID
    journal_entry_id: uuid.UUID
    account_id: uuid.UUID
    account_number: Optional[str] = None
    account_name: Optional[str] = None
    line_number: int
    concept: str
    debit: Decimal
    credit: Decimal
    cfdi_uuid: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class JournalEntryCreate(BaseModel):
    entry_type: str = Field(..., description="INGRESO, EGRESO, DIARIO")
    entry_date: date = Field(default_factory=date.today)
    concept: str = Field(..., max_length=300)
    lines: List[JournalEntryLineCreate] = Field(..., min_length=2, description="Partidas contables de la póliza")


class JournalEntryResponse(BaseModel):
    id: uuid.UUID
    folio: str
    entry_type: str
    entry_date: date
    concept: str
    total_debit: Decimal
    total_credit: Decimal
    status: str
    source_module: str
    source_folio: Optional[str] = None
    created_at: datetime
    line_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)


class JournalEntryDetailResponse(JournalEntryResponse):
    lines: List[JournalEntryLineResponse] = []


# ==========================================
# ESTADOS FINANCIEROS (REPORTING ENGINE)
# ==========================================

# 1. Balanza de Comprobación
class TrialBalanceItem(BaseModel):
    account_number: str
    name: str
    nature: str
    account_type: str
    level: int
    is_group: bool
    sat_group_code: str
    initial_debit: Decimal
    initial_credit: Decimal
    period_debit: Decimal
    period_credit: Decimal
    final_debit: Decimal
    final_credit: Decimal


class TrialBalanceReport(BaseModel):
    start_date: date
    end_date: date
    items: List[TrialBalanceItem]
    total_initial_debit: Decimal
    total_initial_credit: Decimal
    total_period_debit: Decimal
    total_period_credit: Decimal
    total_final_debit: Decimal
    total_final_credit: Decimal
    is_balanced: bool


# 2. Estado de Resultados (P&L)
class FinancialStatementLine(BaseModel):
    account_number: str
    name: str
    amount: Decimal


class IncomeStatementReport(BaseModel):
    start_date: date
    end_date: date
    gross_sales: Decimal
    sales_discounts: Decimal
    net_sales: Decimal
    cost_of_goods_sold: Decimal
    gross_profit: Decimal
    gross_margin_percentage: Decimal
    operating_expenses: Decimal
    ebitda_operating_income: Decimal
    net_income: Decimal
    revenue_lines: List[FinancialStatementLine] = []
    cogs_lines: List[FinancialStatementLine] = []
    expense_lines: List[FinancialStatementLine] = []


# 3. Balance General
class BalanceSheetSection(BaseModel):
    section_name: str
    total: Decimal
    lines: List[FinancialStatementLine] = []


class BalanceSheetReport(BaseModel):
    as_of_date: date
    current_assets: BalanceSheetSection
    non_current_assets: BalanceSheetSection
    total_assets: Decimal

    short_term_liabilities: BalanceSheetSection
    long_term_liabilities: BalanceSheetSection
    total_liabilities: Decimal

    equity: BalanceSheetSection
    current_year_net_income: Decimal
    total_equity: Decimal

    total_liabilities_and_equity: Decimal
    is_balanced: bool  # Activo == Pasivo + Capital


# 4. CFO Dashboard
class AccountingDashboardMetrics(BaseModel):
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    monthly_revenue: Decimal
    monthly_net_income: Decimal
    gross_margin_percentage: Decimal
    unbalanced_entries_count: int
    recent_entries: List[JournalEntryResponse] = []

