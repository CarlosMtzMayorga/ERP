export interface Account {
  id: string;
  account_number: string;
  name: string;
  nature: 'DEUDORA' | 'ACREEDORA';
  account_type: 'ACTIVO' | 'PASIVO' | 'CAPITAL' | 'INGRESOS' | 'COSTOS' | 'GASTOS';
  level: number;
  is_group: boolean;
  sat_group_code: string;
  initial_balance: number;
  current_balance: number;
  is_active: boolean;
}

export interface JournalEntryLine {
  id?: string;
  journal_entry_id?: string;
  account_id: string;
  account_number?: string;
  account_name?: string;
  line_number: number;
  concept: string;
  debit: number;
  credit: number;
  cfdi_uuid?: string;
}

export interface JournalEntry {
  id: string;
  folio: string;
  entry_type: 'INGRESO' | 'EGRESO' | 'DIARIO';
  entry_date: string;
  concept: string;
  total_debit: number;
  total_credit: number;
  status: 'BORRADOR' | 'APLICADA' | 'CANCELADA';
  source_module: string;
  source_folio?: string;
  created_at: string;
  line_count?: number;
  lines?: JournalEntryLine[];
}

export interface TrialBalanceItem {
  account_number: string;
  name: string;
  nature: string;
  account_type: string;
  level: number;
  is_group: boolean;
  sat_group_code: string;
  initial_debit: number;
  initial_credit: number;
  period_debit: number;
  period_credit: number;
  final_debit: number;
  final_credit: number;
}

export interface TrialBalanceReport {
  start_date: string;
  end_date: string;
  items: TrialBalanceItem[];
  total_initial_debit: number;
  total_initial_credit: number;
  total_period_debit: number;
  total_period_credit: number;
  total_final_debit: number;
  total_final_credit: number;
  is_balanced: boolean;
}

export interface FinancialStatementLine {
  account_number: string;
  name: string;
  amount: number;
}

export interface IncomeStatementReport {
  start_date: string;
  end_date: string;
  gross_sales: number;
  sales_discounts: number;
  net_sales: number;
  cost_of_goods_sold: number;
  gross_profit: number;
  gross_margin_percentage: number;
  operating_expenses: number;
  ebitda_operating_income: number;
  net_income: number;
  revenue_lines: FinancialStatementLine[];
  cogs_lines: FinancialStatementLine[];
  expense_lines: FinancialStatementLine[];
}

export interface BalanceSheetSection {
  section_name: string;
  total: number;
  lines: FinancialStatementLine[];
}

export interface BalanceSheetReport {
  as_of_date: string;
  current_assets: BalanceSheetSection;
  non_current_assets: BalanceSheetSection;
  total_assets: number;
  short_term_liabilities: BalanceSheetSection;
  long_term_liabilities: BalanceSheetSection;
  total_liabilities: number;
  equity: BalanceSheetSection;
  current_year_net_income: number;
  total_equity: number;
  total_liabilities_and_equity: number;
  is_balanced: boolean;
}

export interface AccountingDashboardMetrics {
  total_assets: number;
  total_liabilities: number;
  total_equity: number;
  monthly_revenue: number;
  monthly_net_income: number;
  gross_margin_percentage: number;
  unbalanced_entries_count: number;
  recent_entries: JournalEntry[];
}
