export interface CashRegister {
  id: string;
  branch_id: string;
  warehouse_id: string;
  code: string;
  name: string;
  is_active: boolean;
  branch_name?: string;
  warehouse_name?: string;
  active_session_id?: string | null;
}

export interface CashSession {
  id: string;
  cash_register_id: string;
  cash_register_name?: string;
  cashier_name?: string;
  status: 'OPEN' | 'CLOSING' | 'CLOSED';
  opened_at: string;
  closed_at?: string;
  initial_cash: number;
  expected_cash: number;
  declared_cash?: number;
  difference_cash?: number;
  expected_card: number;
  declared_card?: number;
  difference_card?: number;
  total_sales: number;
  tickets_count: number;
  notes?: string;
}

export interface CartItem {
  product_id: string;
  sku: string;
  name: string;
  quantity: number;
  unit_price: number; // Gross price with VAT
  subtotal: number;
  vat_amount: number;
  total: number;
}

export interface POSTicket {
  id: string;
  folio: string;
  serie?: string;
  folio_number?: number;
  total: number;
  subtotal: number;
  tax_iva_total: number;
  payment_method: string;
  amount_paid: number;
  change_returned: number;
  status: string;
  is_globally_invoiced: boolean;
  cash_register_name?: string;
  customer_name?: string;
  created_at: string;
  items?: POSTicketDetailItem[];
}

export interface POSTicketDetailItem {
  id: string;
  sku: string;
  description: string;
  quantity: number;
  unit_price: number;
  subtotal: number;
  vat_amount: number;
  total: number;
  unit_cost: number;
  total_cost: number;
}

export interface CorteXData {
  session_id: string;
  cash_register_name: string;
  cashier_name: string;
  opened_at: string;
  initial_cash: number;
  cash_sales: number;
  card_sales: number;
  transfer_sales: number;
  total_sales: number;
  tickets_count: number;
  cash_entries: number;
  cash_withdrawals: number;
  expected_cash: number;
  expected_card: number;
}

