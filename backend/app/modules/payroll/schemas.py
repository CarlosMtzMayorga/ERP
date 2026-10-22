import uuid
from decimal import Decimal
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ==========================================
# EMPLEADOS (EXPEDIENTE RRHH)
# ==========================================
class EmployeeBase(BaseModel):
    code: str = Field(..., max_length=30, description="Clave interna del empleado ej: EMP-001")
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    email: Optional[str] = None
    phone: Optional[str] = None

    # Fiscal y Seguridad Social
    rfc: str = Field(..., min_length=12, max_length=13, description="RFC del empleado")
    curp: str = Field(..., min_length=18, max_length=18, description="CURP del empleado")
    nss: str = Field(..., min_length=11, max_length=11, description="Número de Seguridad Social IMSS")
    zip_code: str = Field("06000", max_length=10, description="Código Postal del domicilio fiscal")

    # Salarios
    hire_date: date = Field(default_factory=date.today)
    daily_salary: Decimal = Field(..., ge=0, description="Salario Diario (SD)")
    integrated_daily_salary: Decimal = Field(..., ge=0, description="Salario Diario Integrado (SDI)")

    # Catálogos SAT
    contract_type: str = Field("01", description="SAT c_TipoContrato (01 - Indeterminado)")
    work_shift_type: str = Field("01", description="SAT c_TipoJornada (01 - Diurna)")
    regime_type: str = Field("02", description="SAT c_TipoRegimen (02 - Sueldos y salarios)")
    risk_class: str = Field("1", description="SAT c_RiesgoPuesto (1 a 5)")
    periodicity: str = Field("04", description="SAT c_PeriodicidadPago (04 - Quincenal)")

    # Organización y Banco
    department: str = Field("General", max_length=100)
    job_title: str = Field("Operativo", max_length=100)
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    status: str = Field("ACTIVO", max_length=20)


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    daily_salary: Optional[Decimal] = None
    integrated_daily_salary: Optional[Decimal] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None


class EmployeeResponse(EmployeeBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# INCIDENCIAS DE NÓMINA
# ==========================================
class PayrollIncidentCreate(BaseModel):
    payroll_period_id: uuid.UUID
    employee_id: uuid.UUID
    incident_type: str = Field(..., description="FALTA_INJUSTIFICADA, INCAPACIDAD, HORAS_EXTRAS_DOBLES, HORAS_EXTRAS_TRIPLES, BONO, COMISION")
    quantity: Decimal = Field(Decimal("1.00"), description="Días u horas")
    amount: Decimal = Field(Decimal("0.00"), description="Monto en caso de bono o comisión directa")
    notes: Optional[str] = None


class PayrollIncidentResponse(BaseModel):
    id: uuid.UUID
    payroll_period_id: uuid.UUID
    employee_id: uuid.UUID
    incident_type: str
    quantity: Decimal
    amount: Decimal
    notes: Optional[str]
    created_at: datetime
    employee_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# Matriz de Captura Rápida de Prenómina (Grid)
class PrenominaRow(BaseModel):
    employee_id: uuid.UUID
    faltas_dias: Decimal = Field(Decimal("0.00"), ge=0)
    incapacidades_dias: Decimal = Field(Decimal("0.00"), ge=0)
    horas_dobles: Decimal = Field(Decimal("0.00"), ge=0)
    horas_triples: Decimal = Field(Decimal("0.00"), ge=0)
    bonos: Decimal = Field(Decimal("0.00"), ge=0)
    comisiones: Decimal = Field(Decimal("0.00"), ge=0)


class BulkPrenominaSaveRequest(BaseModel):
    payroll_period_id: uuid.UUID
    rows: List[PrenominaRow]


# ==========================================
# RECIBOS Y PARTIDAS DE NÓMINA
# ==========================================
class PayrollReceiptItemResponse(BaseModel):
    id: uuid.UUID
    item_type: str  # PERCEPCION, DEDUCCION
    sat_code: str
    concept_key: str
    description: str
    taxed_amount: Decimal
    exempt_amount: Decimal
    total_amount: Decimal

    model_config = ConfigDict(from_attributes=True)


class PayrollReceiptResponse(BaseModel):
    id: uuid.UUID
    payroll_period_id: uuid.UUID
    employee_id: uuid.UUID
    employee_code: Optional[str] = None
    employee_name: Optional[str] = None
    employee_rfc: Optional[str] = None
    folio: str
    days_worked: Decimal
    days_paid: Decimal
    daily_salary: Decimal
    integrated_daily_salary: Decimal
    base_salary: Decimal
    total_perceptions: Decimal
    total_deductions: Decimal
    total_net: Decimal
    isr_retention: Decimal
    imss_employee_retention: Decimal
    imss_employer_cost: Decimal
    status: str
    cfdi_uuid: Optional[str] = None
    stamped_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PayrollReceiptDetailResponse(PayrollReceiptResponse):
    xml_cfdi: Optional[str] = None
    cadena_original: Optional[str] = None
    sello_digital: Optional[str] = None
    sello_sat: Optional[str] = None
    items: List[PayrollReceiptItemResponse] = []


# ==========================================
# PERIODOS DE NÓMINA
# ==========================================
class PayrollPeriodCreate(BaseModel):
    name: str = Field(..., max_length=150, description="Nombre descriptivo ej: 1ra Quincena Octubre 2026")
    payroll_type: str = Field("O", max_length=5, description="O: Ordinaria, E: Extraordinaria")
    periodicity: str = Field("04", max_length=5, description="04: Quincenal, 02: Semanal, 05: Mensual")
    start_date: date
    end_date: date
    payment_date: date
    days_paid: Decimal = Field(Decimal("15.00"), ge=1)


class PayrollPeriodResponse(BaseModel):
    id: uuid.UUID
    folio: str
    name: str
    payroll_type: str
    periodicity: str
    start_date: date
    end_date: date
    payment_date: date
    days_paid: Decimal
    status: str
    total_perceptions: Decimal
    total_deductions: Decimal
    total_net: Decimal
    total_isr_retention: Decimal
    total_imss_employee: Decimal
    total_imss_employer: Decimal
    bank_account_id: Optional[uuid.UUID] = None
    disbursed_at: Optional[datetime] = None
    receipt_count: Optional[int] = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Dispersión Bancaria
class DisbursePayrollRequest(BaseModel):
    bank_account_id: uuid.UUID = Field(..., description="ID de la cuenta bancaria patronal a debitar")
    notes: Optional[str] = None


# Timbrado en Lote
class BatchStampResponse(BaseModel):
    period_id: uuid.UUID
    total_receipts: int
    stamped_count: int
    errors_count: int
    stamped_uuids: List[str] = []
    error_details: List[str] = []


# ==========================================
# DASHBOARD RRHH
# ==========================================
class PayrollDashboardMetrics(BaseModel):
    total_payroll_cost_month: Decimal
    total_active_employees: int
    total_social_security_imss: Decimal
    total_net_salary_disbursed: Decimal
    active_periods_count: int
    social_burden_percentage: Decimal
    recent_periods: List[PayrollPeriodResponse] = []
