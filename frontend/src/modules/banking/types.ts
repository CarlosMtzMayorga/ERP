export interface BankAccount {
  id: string;
  bank_name: string;
  account_number: string;
  clabe: string;
  currency_id: string;
  currency_code: string;
  current_balance: number;
  reconciled_balance: number;
  is_active: boolean;
}

export interface BankTransaction {
  id: string;
  bank_account_id: string;
  transaction_type: 'DEPOSITO' | 'RETIRO' | 'TRANSFERENCIA_ENTRADA' | 'TRANSFERENCIA_SALIDA' | 'PAGO_PROVEEDOR' | 'COBRO_CLIENTE';
  direction: 'IN' | 'OUT';
  amount: number;
  previous_balance: number;
  new_balance: number;
  reference_type: string;
  reference_id?: string;
  reference_folio?: string;
  operation_number?: string;
  transaction_date: string;
  is_reconciled: boolean;
  reconciled_at?: string;
  notes?: string;
  bank_name?: string;
  account_number?: string;
}

export interface BankingDashboardMetrics {
  total_book_balance: number;
  total_reconciled_balance: number;
  monthly_inflow: number;
  monthly_outflow: number;
  accounts: BankAccount[];
  recent_transactions: BankTransaction[];
}

