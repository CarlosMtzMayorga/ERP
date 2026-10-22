export interface Employee {
  id: string;
  code: string;
  first_name: string;
  last_name: string;
  email?: string;
  phone?: string;
  rfc: string;
  curp: string;
  nss: string;
  zip_code: string;
  hire_date: string;
  daily_salary: number;
  integrated_daily_salary: number;
  contract_type: string;
  work_shift_type: string;
  regime_type: string;
  risk_class: string;
  periodicity: string;
  department: string;
  job_title: string;
  bank_name?: string;
  bank_account_number?: string;
  status: 'ACTIVO' | 'BAJA' | 'SUSPENDIDO';
  is_active: boolean;
}

export interface PayrollIncident {
  id: string;
  payroll_period_id: string;
  employee_id: string;
  employee_name?: string;
  incident_type: 'FALTA_INJUSTIFICADA' | 'INCAPACIDAD' | 'HORAS_EXTRAS_DOBLES' | 'HORAS_EXTRAS_TRIPLES' | 'BONO' | 'COMISION';
  quantity: number;
  amount: number;
  notes?: string;
  created_at: string;
}

export interface PrenominaGridRow {
  employee_id: string;
  code: string;
  name: string;
  daily_salary: number;
  integrated_daily_salary: number;
  faltas_dias: number;
  incapacidades_dias: number;
  horas_dobles: number;
  horas_triples: number;
  bonos: number;
  comisiones: number;
  estimated_net?: number;
}

export interface PayrollReceiptItem {
  id: string;
  item_type: 'PERCEPCION' | 'DEDUCCION' | 'OTRO_PAGO';
  sat_code: string;
  concept_key: string;
  description: string;
  taxed_amount: number;
  exempt_amount: number;
  total_amount: number;
}

export interface PayrollReceipt {
  id: string;
  payroll_period_id: string;
  employee_id: string;
  employee_code?: string;
  employee_name?: string;
  employee_rfc?: string;
  folio: string;
  days_worked: number;
  days_paid: number;
  daily_salary: number;
  integrated_daily_salary: number;
  base_salary: number;
  total_perceptions: number;
  total_deductions: number;
  total_net: number;
  isr_retention: number;
  imss_employee_retention: number;
  imss_employer_cost: number;
  status: 'CALCULADO' | 'AUTORIZADO' | 'TIMBRADO' | 'CANCELADO';
  cfdi_uuid?: string;
  stamped_at?: string;
  xml_cfdi?: string;
  cadena_original?: string;
  sello_digital?: string;
  sello_sat?: string;
  items?: PayrollReceiptItem[];
  created_at: string;
}

export interface PayrollPeriod {
  id: string;
  folio: string;
  name: string;
  payroll_type: string;
  periodicity: string;
  start_date: string;
  end_date: string;
  payment_date: string;
  days_paid: number;
  status: 'BORRADOR' | 'CALCULADA' | 'AUTORIZADA' | 'DISPERSADA' | 'TIMBRADA' | 'CANCELADA';
  total_perceptions: number;
  total_deductions: number;
  total_net: number;
  total_isr_retention: number;
  total_imss_employee: number;
  total_imss_employer: number;
  bank_account_id?: string;
  disbursed_at?: string;
  receipt_count?: number;
  receipts?: PayrollReceipt[];
  incidents?: PayrollIncident[];
  created_at: string;
  updated_at: string;
}

export interface PayrollDashboardMetrics {
  total_payroll_cost_month: number;
  total_active_employees: number;
  total_social_security_imss: number;
  total_net_salary_disbursed: number;
  active_periods_count: number;
  social_burden_percentage: number;
  recent_periods: PayrollPeriod[];
}

export interface BankAccount {
  id: string;
  bank_name: string;
  account_number: string;
  clabe: string;
  current_balance: number;
  reconciled_balance: number;
  is_active: boolean;
}

