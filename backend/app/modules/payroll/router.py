import uuid
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.tenant_context import get_current_tenant_id
from app.core.dependencies import get_current_user, require_permission
from app.modules.auth.models import User
from app.modules.payroll.models import PayrollReceipt, PayrollReceiptItem
from app.modules.payroll.schemas import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeResponse,
    PayrollPeriodCreate,
    PayrollPeriodResponse,
    PayrollIncidentCreate,
    PayrollIncidentResponse,
    BulkPrenominaSaveRequest,
    PayrollReceiptResponse,
    PayrollReceiptDetailResponse,
    DisbursePayrollRequest,
    BatchStampResponse,
    PayrollDashboardMetrics
)
from app.modules.payroll import payroll_service

router = APIRouter(prefix="/payroll", tags=["Nómina y Recursos Humanos"])


# ==========================================
# DASHBOARD RRHH
# ==========================================
@router.get("/dashboard", response_model=PayrollDashboardMetrics)
async def get_payroll_dashboard(
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("payroll:read"))
):
    """Métricas ejecutivas de nómina: costo total, headcount, carga social IMSS vs neto."""
    return await payroll_service.get_payroll_dashboard_metrics(db, tenant_id)


# ==========================================
# EXPEDIENTE DE EMPLEADOS
# ==========================================
@router.get("/employees", response_model=List[EmployeeResponse])
async def list_employees(
    status: Optional[str] = Query(None, description="Filtrar por estado ACTIVO / BAJA"),
    search: Optional[str] = Query(None, description="Buscar por nombre, clave, RFC o CURP"),
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("payroll:read"))
):
    """Catálogo maestro de trabajadores de la empresa."""
    return await payroll_service.get_employees(db, tenant_id, status_filter=status, search=search)


@router.post("/employees", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_employee(
    data: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("payroll:read"))
):
    """Alta de nuevo trabajador con validación de RFC, CURP, NSS y Salarios."""
    return await payroll_service.create_employee(db, tenant_id, data)


@router.get("/employees/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("payroll:read"))
):
    emp = await payroll_service.get_employee_by_id(db, tenant_id, employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Empleado no encontrado.")
    return emp


@router.put("/employees/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: uuid.UUID,
    data: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("payroll:read"))
):
    return await payroll_service.update_employee(db, tenant_id, employee_id, data)


# ==========================================
# PERIODOS DE NÓMINA
# ==========================================
@router.get("/periods", response_model=List[PayrollPeriodResponse])
async def list_payroll_periods(
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("payroll:read"))
):
    """Listado de periodos de nómina (semanales, quincenales)."""
    periods = await payroll_service.get_payroll_periods(db, tenant_id)
    result = []
    for p in periods:
        result.append(
            PayrollPeriodResponse(
                id=p.id,
                folio=p.folio,
                name=p.name,
                payroll_type=p.payroll_type,
                periodicity=p.periodicity,
                start_date=p.start_date,
                end_date=p.end_date,
                payment_date=p.payment_date,
                days_paid=p.days_paid,
                status=p.status,
                total_perceptions=p.total_perceptions,
                total_deductions=p.total_deductions,
                total_net=p.total_net,
                total_isr_retention=p.total_isr_retention,
                total_imss_employee=p.total_imss_employee,
                total_imss_employer=p.total_imss_employer,
                bank_account_id=p.bank_account_id,
                disbursed_at=p.disbursed_at,
                receipt_count=len(p.receipts) if p.receipts else 0,
                created_at=p.created_at,
                updated_at=p.updated_at
            )
        )
    return result


@router.post("/periods", response_model=PayrollPeriodResponse, status_code=status.HTTP_201_CREATED)
async def create_payroll_period(
    data: PayrollPeriodCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("payroll:calculate"))
):
    """Crea un nuevo periodo de nómina con folio automático."""
    p = await payroll_service.create_payroll_period(db, tenant_id, data, user_id=current_user.id)
    return PayrollPeriodResponse(
        id=p.id,
        folio=p.folio,
        name=p.name,
        payroll_type=p.payroll_type,
        periodicity=p.periodicity,
        start_date=p.start_date,
        end_date=p.end_date,
        payment_date=p.payment_date,
        days_paid=p.days_paid,
        status=p.status,
        total_perceptions=p.total_perceptions,
        total_deductions=p.total_deductions,
        total_net=p.total_net,
        total_isr_retention=p.total_isr_retention,
        total_imss_employee=p.total_imss_employee,
        total_imss_employer=p.total_imss_employer,
        bank_account_id=p.bank_account_id,
        disbursed_at=p.disbursed_at,
        receipt_count=0,
        created_at=p.created_at,
        updated_at=p.updated_at
    )


@router.get("/periods/{period_id}")
async def get_payroll_period(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("payroll:read"))
):
    """Detalle completo del periodo incluyendo todos los recibos e incidencias."""
    p = await payroll_service.get_payroll_period_by_id(db, tenant_id, period_id)
    if not p:
        raise HTTPException(status_code=404, detail="Periodo no encontrado.")
    
    receipts_data = []
    for r in p.receipts:
        receipts_data.append({
            "id": r.id,
            "folio": r.folio,
            "employee_id": r.employee_id,
            "employee_code": r.employee.code if r.employee else "",
            "employee_name": f"{r.employee.first_name} {r.employee.last_name}" if r.employee else "",
            "employee_rfc": r.employee.rfc if r.employee else "",
            "days_worked": r.days_worked,
            "days_paid": r.days_paid,
            "daily_salary": r.daily_salary,
            "integrated_daily_salary": r.integrated_daily_salary,
            "base_salary": r.base_salary,
            "total_perceptions": r.total_perceptions,
            "total_deductions": r.total_deductions,
            "total_net": r.total_net,
            "isr_retention": r.isr_retention,
            "imss_employee_retention": r.imss_employee_retention,
            "imss_employer_cost": r.imss_employer_cost,
            "status": r.status,
            "cfdi_uuid": r.cfdi_uuid,
            "stamped_at": r.stamped_at,
            "created_at": r.created_at,
            "items": [
                {
                    "id": item.id,
                    "item_type": item.item_type,
                    "sat_code": item.sat_code,
                    "concept_key": item.concept_key,
                    "description": item.description,
                    "taxed_amount": item.taxed_amount,
                    "exempt_amount": item.exempt_amount,
                    "total_amount": item.total_amount
                }
                for item in r.items
            ]
        })

    incidents_data = []
    for inc in p.incidents:
        incidents_data.append({
            "id": inc.id,
            "employee_id": inc.employee_id,
            "employee_name": f"{inc.employee.first_name} {inc.employee.last_name}" if inc.employee else "",
            "incident_type": inc.incident_type,
            "quantity": inc.quantity,
            "amount": inc.amount,
            "notes": inc.notes,
            "created_at": inc.created_at
        })

    return {
        "id": p.id,
        "folio": p.folio,
        "name": p.name,
        "payroll_type": p.payroll_type,
        "periodicity": p.periodicity,
        "start_date": p.start_date,
        "end_date": p.end_date,
        "payment_date": p.payment_date,
        "days_paid": p.days_paid,
        "status": p.status,
        "total_perceptions": p.total_perceptions,
        "total_deductions": p.total_deductions,
        "total_net": p.total_net,
        "total_isr_retention": p.total_isr_retention,
        "total_imss_employee": p.total_imss_employee,
        "total_imss_employer": p.total_imss_employer,
        "bank_account_id": p.bank_account_id,
        "disbursed_at": p.disbursed_at,
        "receipts": receipts_data,
        "incidents": incidents_data,
        "created_at": p.created_at,
        "updated_at": p.updated_at
    }


# ==========================================
# CÁLCULO, INCIDENCIAS Y PRENÓMINA
# ==========================================
@router.post("/incidents", response_model=PayrollIncidentResponse, status_code=status.HTTP_201_CREATED)
async def record_incident(
    data: PayrollIncidentCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("payroll:calculate"))
):
    """Registra una falta, incapacidad, horas extra o bono."""
    inc = await payroll_service.record_payroll_incident(db, tenant_id, data)
    return PayrollIncidentResponse(
        id=inc.id,
        payroll_period_id=inc.payroll_period_id,
        employee_id=inc.employee_id,
        incident_type=inc.incident_type,
        quantity=inc.quantity,
        amount=inc.amount,
        notes=inc.notes,
        created_at=inc.created_at
    )


@router.post("/prenomina/bulk")
async def bulk_save_prenomina(
    data: BulkPrenominaSaveRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("payroll:calculate"))
):
    """Guarda masivamente las incidencias desde la matriz interactiva de captura (Excel Grid)."""
    return await payroll_service.bulk_save_prenomina(db, tenant_id, data)


@router.post("/periods/{period_id}/calculate")
async def calculate_payroll(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("payroll:calculate"))
):
    """Ejecuta el cálculo masivo de percepciones, ISR (Art. 96) y Seguro Social IMSS."""
    period = await payroll_service.calculate_payroll_period(db, tenant_id, period_id)
    return {
        "message": "Nómina calculada con éxito",
        "period_id": period.id,
        "status": period.status,
        "total_net": period.total_net,
        "total_perceptions": period.total_perceptions,
        "total_deductions": period.total_deductions,
        "total_isr_retention": period.total_isr_retention,
        "total_imss_employee": period.total_imss_employee,
        "total_imss_employer": period.total_imss_employer,
        "receipts_generated": len(period.receipts)
    }


# ==========================================
# DISPERSIÓN BANCARIA Y TIMBRADO EN LOTE
# ==========================================
@router.post("/periods/{period_id}/disburse")
async def disburse_payroll(
    period_id: uuid.UUID,
    req: DisbursePayrollRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("payroll:calculate"))
):
    """
    Dispersa la nómina descontando atómicamente el neto patronal de la cuenta bancaria.
    Bloquea con 'SELECT FOR UPDATE' y valida fondos suficientes (anti-sobregiro).
    """
    return await payroll_service.disburse_payroll(
        db=db,
        tenant_id=tenant_id,
        period_id=period_id,
        bank_account_id=req.bank_account_id,
        notes=req.notes,
        user_id=current_user.id
    )


@router.post("/periods/{period_id}/stamp-batch", response_model=BatchStampResponse)
async def batch_stamp_payroll(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("payroll:stamp"))
):
    """
    Timbra en lote todos los recibos del periodo emitiendo el CFDI 4.0 con Complemento Nómina 1.2
    sellado en memoria mediante CSD y timbrado con PAC SAT.
    """
    return await payroll_service.batch_stamp_payroll_period(db, tenant_id, period_id)


# ==========================================
# VISOR DE RECIBO INDIVIDUAL (KIOSCO)
# ==========================================
@router.get("/receipts/{receipt_id}", response_model=PayrollReceiptDetailResponse)
async def get_receipt_detail(
    receipt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("payroll:read"))
):
    """Obtiene el detalle completo de un recibo de nómina, incluyendo XML CFDI y sellos."""
    stmt = (
        select(PayrollReceipt)
        .where(PayrollReceipt.tenant_id == tenant_id, PayrollReceipt.id == receipt_id)
        .options(
            selectinload(PayrollReceipt.employee),
            selectinload(PayrollReceipt.items)
        )
    )
    res = await db.execute(stmt)
    receipt = res.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="Recibo de nómina no encontrado.")

    return PayrollReceiptDetailResponse(
        id=receipt.id,
        payroll_period_id=receipt.payroll_period_id,
        employee_id=receipt.employee_id,
        employee_code=receipt.employee.code if receipt.employee else None,
        employee_name=f"{receipt.employee.first_name} {receipt.employee.last_name}" if receipt.employee else None,
        employee_rfc=receipt.employee.rfc if receipt.employee else None,
        folio=receipt.folio,
        days_worked=receipt.days_worked,
        days_paid=receipt.days_paid,
        daily_salary=receipt.daily_salary,
        integrated_daily_salary=receipt.integrated_daily_salary,
        base_salary=receipt.base_salary,
        total_perceptions=receipt.total_perceptions,
        total_deductions=receipt.total_deductions,
        total_net=receipt.total_net,
        isr_retention=receipt.isr_retention,
        imss_employee_retention=receipt.imss_employee_retention,
        imss_employer_cost=receipt.imss_employer_cost,
        status=receipt.status,
        cfdi_uuid=receipt.cfdi_uuid,
        stamped_at=receipt.stamped_at,
        xml_cfdi=receipt.xml_cfdi,
        cadena_original=receipt.cadena_original,
        sello_digital=receipt.sello_digital,
        sello_sat=receipt.sello_sat,
        created_at=receipt.created_at,
        items=[
            {
                "id": it.id,
                "item_type": it.item_type,
                "sat_code": it.sat_code,
                "concept_key": it.concept_key,
                "description": it.description,
                "taxed_amount": it.taxed_amount,
                "exempt_amount": it.exempt_amount,
                "total_amount": it.total_amount
            }
            for it in receipt.items
        ]
    )

