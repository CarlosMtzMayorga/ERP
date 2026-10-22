import uuid
from decimal import Decimal
from datetime import datetime, timezone, date
from sqlalchemy import (
    Column, String, Boolean, ForeignKey, Numeric, Text, DateTime, Date, Integer, Uuid, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship

from app.core.database import Base, TenantMixin


class Employee(Base, TenantMixin):
    """
    Expediente Maestro del Trabajador conforme a la normativa laboral (LFT) y fiscal (SAT).
    """
    __tablename__ = "payroll_employees"

    branch_id = Column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Identificación del Empleado
    code = Column(String(30), nullable=False, index=True)  # Clave interna ej: "EMP-001"
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(150), nullable=True)
    phone = Column(String(50), nullable=True)

    # Identificadores Fiscales y de Seguridad Social Obligatorios
    rfc = Column(String(13), nullable=False, index=True)
    curp = Column(String(18), nullable=False, index=True)
    nss = Column(String(11), nullable=False, index=True)  # 11 dígitos IMSS
    zip_code = Column(String(10), default="06000", nullable=False)  # Domicilio Fiscal SAT

    # Salarios y Prestaciones
    hire_date = Column(Date, nullable=False, default=date.today)
    daily_salary = Column(Numeric(12, 4), nullable=False, default=Decimal("0.0000"))  # Salario Diario (SD)
    integrated_daily_salary = Column(Numeric(12, 4), nullable=False, default=Decimal("0.0000"))  # Salario Diario Integrado (SDI)

    # Catálogos Normativos SAT
    contract_type = Column(String(10), default="01", nullable=False)  # 01 - Tiempo indeterminado, 02 - Determinado, etc.
    work_shift_type = Column(String(10), default="01", nullable=False)  # 01 - Diurna, 02 - Nocturna, 03 - Mixta
    regime_type = Column(String(10), default="02", nullable=False)  # 02 - Sueldos y salarios
    risk_class = Column(String(10), default="1", nullable=False)  # 1 a 5 (Riesgo de puesto IMSS)
    periodicity = Column(String(10), default="04", nullable=False)  # 04 - Quincenal, 02 - Semanal, 05 - Mensual

    # Estructura Organizacional
    department = Column(String(100), default="General", nullable=False)
    job_title = Column(String(100), default="Operativo", nullable=False)

    # Datos Bancarios para Dispersión
    bank_name = Column(String(100), nullable=True)
    bank_account_number = Column(String(50), nullable=True)  # CLABE o Cuenta

    # Estado
    status = Column(String(20), default="ACTIVO", nullable=False, index=True)  # ACTIVO, BAJA, SUSPENDIDO
    is_active = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_payroll_employee_code_per_tenant"),
        UniqueConstraint("tenant_id", "curp", name="uq_payroll_employee_curp_per_tenant"),
    )


class PayrollPeriod(Base, TenantMixin):
    """
    Periodo de Nómina (Semanal, Quincenal, Mensual).
    Agrupa los recibos, almacena los acumulados y gestiona la máquina de estados.
    """
    __tablename__ = "payroll_periods"

    folio = Column(String(30), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    payroll_type = Column(String(5), default="O", nullable=False)  # O: Ordinaria, E: Extraordinaria
    periodicity = Column(String(5), default="04", nullable=False)  # 04: Quincenal, 02: Semanal, 05: Mensual

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    payment_date = Column(Date, nullable=False)
    days_paid = Column(Numeric(5, 2), default=Decimal("15.00"), nullable=False)

    # Estados: BORRADOR, CALCULADA, AUTORIZADA, DISPERSADA, TIMBRADA, CANCELADA
    status = Column(String(20), default="BORRADOR", nullable=False, index=True)

    # Acumulados Financieros y Fiscales
    total_perceptions = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    total_deductions = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    total_net = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    total_isr_retention = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    total_imss_employee = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    total_imss_employer = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)

    # Integración con Bancos (Dispersión)
    bank_account_id = Column(Uuid(as_uuid=True), ForeignKey("bank_accounts.id", ondelete="SET NULL"), nullable=True)
    disbursed_at = Column(DateTime(timezone=True), nullable=True)

    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    receipts = relationship("PayrollReceipt", back_populates="period", cascade="all, delete-orphan")
    incidents = relationship("PayrollIncident", back_populates="period", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "folio", name="uq_payroll_period_folio_per_tenant"),
    )


class PayrollIncident(Base, TenantMixin):
    """
    Incidencias de nómina (Faltas, Incapacidades, Permisos, Horas Extras, Bonos).
    Afectan los días trabajados y/o las percepciones del empleado en el periodo.
    """
    __tablename__ = "payroll_incidents"

    payroll_period_id = Column(Uuid(as_uuid=True), ForeignKey("payroll_periods.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Uuid(as_uuid=True), ForeignKey("payroll_employees.id", ondelete="CASCADE"), nullable=False, index=True)

    # Tipos: FALTA_INJUSTIFICADA, INCAPACIDAD, PERMISO_SIN_GOCE, HORAS_EXTRAS_DOBLES, HORAS_EXTRAS_TRIPLES, BONO, COMISION
    incident_type = Column(String(50), nullable=False)
    quantity = Column(Numeric(8, 2), default=Decimal("1.00"), nullable=False)  # Días u Horas
    amount = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)  # Importe directo o calculado
    notes = Column(Text, nullable=True)

    # Relaciones
    period = relationship("PayrollPeriod", back_populates="incidents")
    employee = relationship("Employee")


class PayrollReceipt(Base, TenantMixin):
    """
    Recibo de Nómina Individual emitido por trabajador.
    Contiene el desglose final, estado de timbrado CFDI 1.2 y sellos digitales.
    """
    __tablename__ = "payroll_receipts"

    payroll_period_id = Column(Uuid(as_uuid=True), ForeignKey("payroll_periods.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Uuid(as_uuid=True), ForeignKey("payroll_employees.id", ondelete="RESTRICT"), nullable=False, index=True)

    folio = Column(String(30), nullable=False, index=True)
    days_worked = Column(Numeric(5, 2), nullable=False)
    days_paid = Column(Numeric(5, 2), nullable=False)
    
    daily_salary = Column(Numeric(12, 4), nullable=False)
    integrated_daily_salary = Column(Numeric(12, 4), nullable=False)

    base_salary = Column(Numeric(12, 2), nullable=False)
    total_perceptions = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total_deductions = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total_net = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)

    isr_retention = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    imss_employee_retention = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    imss_employer_cost = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)

    # Estados: CALCULADO, AUTORIZADO, TIMBRADO, CANCELADO
    status = Column(String(20), default="CALCULADO", nullable=False, index=True)

    # Timbrado Fiscal SAT (CFDI 4.0 + Complemento Nómina 1.2)
    cfdi_uuid = Column(String(36), nullable=True, index=True)
    stamped_at = Column(DateTime(timezone=True), nullable=True)
    xml_cfdi = Column(Text, nullable=True)
    cadena_original = Column(Text, nullable=True)
    sello_digital = Column(Text, nullable=True)
    sello_sat = Column(Text, nullable=True)

    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    period = relationship("PayrollPeriod", back_populates="receipts")
    employee = relationship("Employee")
    items = relationship("PayrollReceiptItem", back_populates="receipt", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "payroll_period_id", "employee_id", name="uq_payroll_receipt_employee_period"),
    )


class PayrollReceiptItem(Base):
    """
    Partida individual de Percepción, Deducción u Otro Pago del recibo de nómina (SAT).
    """
    __tablename__ = "payroll_receipt_items"

    payroll_receipt_id = Column(Uuid(as_uuid=True), ForeignKey("payroll_receipts.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # PERCEPCION, DEDUCCION, OTRO_PAGO
    item_type = Column(String(20), nullable=False)
    sat_code = Column(String(10), nullable=False)  # Clave catálogo SAT (ej: 001 - Sueldos, 002 - ISR)
    concept_key = Column(String(20), nullable=False)
    description = Column(String(200), nullable=False)

    taxed_amount = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    exempt_amount = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)

    receipt = relationship("PayrollReceipt", back_populates="items")

