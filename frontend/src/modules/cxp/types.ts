export interface PaymentScheduleItem {
  id: string;
  supplier_id: string;
  supplier_name: string;
  supplier_rfc: string;
  formatted_folio: string;
  cfdi_uuid?: string;
  issue_date: string;
  due_date: string;
  days_until_due: number;
  is_overdue: boolean;
  credit_days: number;
  original_total: number;
  original_retention_vat: number;
  original_retention_isr: number;
  current_balance: number;
  status: 'PENDIENTE' | 'PARCIAL' | 'LIQUIDADO';
}

export interface PaymentScheduleSummary {
  total_debt: number;
  overdue_total: number;
  due_today_total: number;
  due_this_week_total: number;
  due_later_total: number;
  items: PaymentScheduleItem[];
}

export interface CxPDashboardMetrics {
  total_accounts_payable: number;
  overdue_payable: number;
  paid_this_month: number;
  active_creditors_count: number;
  schedule_summary: PaymentScheduleSummary;
}

export interface SupplierPaymentDocRel {
  payable_document_id: string;
  formatted_folio?: string;
  installment_number: number;
  previous_balance: number;
  amount_paid: number;
  remaining_balance: number;
  proportional_subtotal: number;
  proportional_vat: number;
  proportional_retention_vat: number;
  proportional_retention_isr: number;
}

export interface SupplierPayment {
  id: string;
  formatted_folio: string;
  supplier_id: string;
  supplier_name?: string;
  supplier_rfc?: string;
  bank_account_id: string;
  bank_name?: string;
  account_number?: string;
  payment_date: string;
  payment_method: string;
  amount: number;
  operation_number?: string;
  status: string;
  notes?: string;
  related_docs: SupplierPaymentDocRel[];
}
