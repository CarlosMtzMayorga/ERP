export interface CxCDashboardData {
  total_receivable: number;
  current_receivable: number;
  overdue_total: number;
  overdue_percentage: number;
  buckets: {
    current: number;
    days_1_30: number;
    days_31_60: number;
    days_61_90: number;
    days_over_90: number;
  };
  top_debtors: TopDebtor[];
  total_pending_documents: number;
}

export interface TopDebtor {
  customer_id: string;
  customer_name: string;
  credit_limit: number;
  credit_days: number;
  total_debt: number;
}

export interface PendingReceivable {
  id: string;
  customer_id: string;
  customer_name: string;
  folio: string;
  cfdi_uuid?: string;
  issue_date: string;
  due_date: string;
  is_overdue: boolean;
  days_overdue: number;
  original_total: number;
  current_balance: number;
  status: string;
}

export interface PaymentReceiptSummary {
  id: string;
  folio: string;
  cfdi_uuid?: string;
  customer_name: string;
  payment_date: string;
  payment_form: string;
  amount: number;
  status: string;
  stamped_at?: string;
  docs_count: number;
}

export interface CustomerStatement {
  customer: {
    id: string;
    code: string;
    legal_name: string;
    rfc: string;
    credit_limit: number;
    credit_days: number;
    current_balance: number;
  };
  transactions: {
    type: 'CARGO' | 'ABONO';
    date: string;
    due_date?: string | null;
    folio: string;
    concept: string;
    amount: number;
    balance: number;
    status: string;
  }[];
}
