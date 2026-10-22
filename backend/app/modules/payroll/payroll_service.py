import uuid
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta, date
from typing import List, Optional, Tuple, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy import select, and_, func, desc, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.tenants.models import Tenant, Branch, FiscalFoliosSeries, CSDCertificate
from app.modules.tenants.folios_service import consume_next_folio
from app.modules.master_data.models import BankAccount
from app.modules.banking.banking_service import record_bank_transaction
from app.modules.fiscal_mexico.cfdi_builder import stamp_with_mock_pac
from app.modules.payroll.models import (
    Employee,
    PayrollPeriod,
    PayrollIncident,
    PayrollReceipt,
    PayrollReceiptItem
)
from app.modules.payroll.fiscal_engine import (
    quantize_2,
    calculate_employee_payroll,
    calculate_isr_retention,
    calculate_imss_employee_retention
)
from app.modules.payroll.cfdi_payroll_builder import generate_payroll_cfdi_xml
from app.modules.payroll.schemas import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeResponse,
    PayrollPeriodCreate,
    PayrollIncidentCreate,
    PrenominaRow,
    BulkPrenominaSaveRequest,
    DisbursePayrollRequest,
    BatchStampResponse,
    PayrollDashboardMetrics
)


async def ensure_payroll_folio_series(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    branch_id: Optional[uuid.UUID] = None,
    doc_type: str = "NOMINA",
    serie: str = "NOM",
    initial_folio: int = 1
):
    """Garantiza la existencia de la serie de folios atómicos para periodos o recibos de nómina."""
    stmt = select(FiscalFoliosSeries).where(
        FiscalFoliosSeries.tenant_id == tenant_id,
        FiscalFoliosSeries.document_type == doc_type
    )
    res = await db.execute(stmt)
    existing = res.scalars().first()
    if not existing:
        new_serie = FiscalFoliosSeries(
            tenant_id=tenant_id,
            branch_id=branch_id,
            document_type=doc_type,
            serie=serie,
            initial_folio=initial_folio,
            current_folio=0,
            is_default=True
        )
        db.add(new_serie)
        await db.flush()


# ==========================================
# GESTIÓN DE EMPLEADOS
# ==========================================
async def get_employees(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    status_filter: Optional[str] = None,
    search: Optional[str] = None
) -> List[Employee]:
    stmt = select(Employee).where(Employee.tenant_id == tenant_id)
    if status_filter:
        stmt = stmt.where(Employee.status == status_filter.upper())
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            (Employee.code.ilike(term)) |
            (Employee.first_name.ilike(term)) |
            (Employee.last_name.ilike(term)) |
            (Employee.rfc.ilike(term)) |
            (Employee.curp.ilike(term))
        )
    stmt = stmt.order_by(Employee.code.asc())
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def get_employee_by_id(db: AsyncSession, tenant_id: uuid.UUID, employee_id: uuid.UUID) -> Optional[Employee]:
    stmt = select(Employee).where(Employee.tenant_id == tenant_id, Employee.id == employee_id)
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


async def create_employee(db: AsyncSession, tenant_id: uuid.UUID, data: EmployeeCreate) -> Employee:
    # Validar duplicados de código o CURP en la misma empresa
    stmt = select(Employee).where(
        Employee.tenant_id == tenant_id,
        (Employee.code == data.code) | (Employee.curp == data.curp)
    )
    res = await db.execute(stmt)
    if res.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un empleado con la clave '{data.code}' o la CURP '{data.curp}' en la empresa."
        )

    emp = Employee(
        tenant_id=tenant_id,
        code=data.code.strip().upper(),
        first_name=data.first_name.strip(),
        last_name=data.last_name.strip(),
        email=data.email,
        phone=data.phone,
        rfc=data.rfc.strip().upper(),
        curp=data.curp.strip().upper(),
        nss=data.nss.strip(),
        zip_code=data.zip_code.strip(),
        hire_date=data.hire_date,
        daily_salary=data.daily_salary,
        integrated_daily_salary=data.integrated_daily_salary,
        contract_type=data.contract_type,
        work_shift_type=data.work_shift_type,
        regime_type=data.regime_type,
        risk_class=data.risk_class,
        periodicity=data.periodicity,
        department=data.department,
        job_title=data.job_title,
        bank_name=data.bank_name,
        bank_account_number=data.bank_account_number,
        status=data.status.upper(),
        is_active=True
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return emp


async def update_employee(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    employee_id: uuid.UUID,
    data: EmployeeUpdate
) -> Employee:
    emp = await get_employee_by_id(db, tenant_id, employee_id)
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empleado no encontrado.")

    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(emp, field, val)

    await db.commit()
    await db.refresh(emp)
    return emp


# ==========================================
# PERIODOS DE NÓMINA
# ==========================================
async def get_payroll_periods(db: AsyncSession, tenant_id: uuid.UUID) -> List[PayrollPeriod]:
    stmt = (
        select(PayrollPeriod)
        .where(PayrollPeriod.tenant_id == tenant_id)
        .options(selectinload(PayrollPeriod.receipts))
        .order_by(desc(PayrollPeriod.start_date))
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def get_payroll_period_by_id(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    period_id: uuid.UUID
) -> Optional[PayrollPeriod]:
    stmt = (
        select(PayrollPeriod)
        .where(PayrollPeriod.tenant_id == tenant_id, PayrollPeriod.id == period_id)
        .options(
            selectinload(PayrollPeriod.receipts).selectinload(PayrollReceipt.employee),
            selectinload(PayrollPeriod.receipts).selectinload(PayrollReceipt.items),
            selectinload(PayrollPeriod.incidents).selectinload(PayrollIncident.employee),
        )
    )
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


async def create_payroll_period(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: PayrollPeriodCreate,
    user_id: Optional[uuid.UUID] = None
) -> PayrollPeriod:
    await ensure_payroll_folio_series(db, tenant_id, doc_type="NOMINA", serie="NOM")
    
    # Consumir folio atómico (retorna serie, folio, serie_id)
    serie, next_folio, _ = await consume_next_folio(db, tenant_id, "NOMINA")
    folio_code = f"{serie}-{next_folio:04d}"

    period = PayrollPeriod(
        tenant_id=tenant_id,
        folio=folio_code,
        name=data.name.strip(),
        payroll_type=data.payroll_type,
        periodicity=data.periodicity,
        start_date=data.start_date,
        end_date=data.end_date,
        payment_date=data.payment_date,
        days_paid=data.days_paid,
        status="BORRADOR"
    )
    db.add(period)
    await db.commit()
    await db.refresh(period)
    return period


# ==========================================
# PRENÓMINA E INCIDENCIAS (CAPTURA RÁPIDA EN GRID)
# ==========================================
async def record_payroll_incident(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: PayrollIncidentCreate
) -> PayrollIncident:
    period = await get_payroll_period_by_id(db, tenant_id, data.payroll_period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Periodo de nómina no encontrado.")
    if period.status in ("AUTORIZADA", "DISPERSADA", "TIMBRADA"):
        raise HTTPException(status_code=400, detail="No se pueden registrar incidencias en un periodo cerrado o dispersado.")

    incident = PayrollIncident(
        tenant_id=tenant_id,
        payroll_period_id=data.payroll_period_id,
        employee_id=data.employee_id,
        incident_type=data.incident_type.upper(),
        quantity=data.quantity,
        amount=data.amount,
        notes=data.notes
    )
    db.add(incident)
    await db.commit()
    await db.refresh(incident)
    return incident


async def bulk_save_prenomina(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: BulkPrenominaSaveRequest
) -> Dict[str, Any]:
    """
    Guarda en lote la matriz de incidencias de la prenómina (Excel Grid).
    Limpia incidencias previas del periodo y persiste las nuevas capturas.
    """
    period = await get_payroll_period_by_id(db, tenant_id, data.payroll_period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Periodo no encontrado.")
    if period.status in ("DISPERSADA", "TIMBRADA"):
        raise HTTPException(status_code=400, detail="El periodo ya fue dispersado o timbrado.")

    # Eliminar incidencias previas para este periodo
    await db.execute(
        delete(PayrollIncident).where(
            PayrollIncident.tenant_id == tenant_id,
            PayrollIncident.payroll_period_id == data.payroll_period_id
        )
    )

    created_count = 0
    for row in data.rows:
        emp_id = row.employee_id
        if row.faltas_dias > 0:
            db.add(PayrollIncident(
                tenant_id=tenant_id,
                payroll_period_id=data.payroll_period_id,
                employee_id=emp_id,
                incident_type="FALTA_INJUSTIFICADA",
                quantity=row.faltas_dias,
                amount=Decimal("0.00"),
                notes="Captura en matriz prenómina"
            ))
            created_count += 1
        if row.incapacidades_dias > 0:
            db.add(PayrollIncident(
                tenant_id=tenant_id,
                payroll_period_id=data.payroll_period_id,
                employee_id=emp_id,
                incident_type="INCAPACIDAD",
                quantity=row.incapacidades_dias,
                amount=Decimal("0.00"),
                notes="Incapacidad médica"
            ))
            created_count += 1
        if row.horas_dobles > 0:
            db.add(PayrollIncident(
                tenant_id=tenant_id,
                payroll_period_id=data.payroll_period_id,
                employee_id=emp_id,
                incident_type="HORAS_EXTRAS_DOBLES",
                quantity=row.horas_dobles,
                amount=Decimal("0.00"),
                notes="Horas extras dobles"
            ))
            created_count += 1
        if row.horas_triples > 0:
            db.add(PayrollIncident(
                tenant_id=tenant_id,
                payroll_period_id=data.payroll_period_id,
                employee_id=emp_id,
                incident_type="HORAS_EXTRAS_TRIPLES",
                quantity=row.horas_triples,
                amount=Decimal("0.00"),
                notes="Horas extras triples"
            ))
            created_count += 1
        if row.bonos > 0:
            db.add(PayrollIncident(
                tenant_id=tenant_id,
                payroll_period_id=data.payroll_period_id,
                employee_id=emp_id,
                incident_type="BONO",
                quantity=Decimal("1.00"),
                amount=row.bonos,
                notes="Bono de productividad"
            ))
            created_count += 1
        if row.comisiones > 0:
            db.add(PayrollIncident(
                tenant_id=tenant_id,
                payroll_period_id=data.payroll_period_id,
                employee_id=emp_id,
                incident_type="COMISION",
                quantity=Decimal("1.00"),
                amount=row.comisiones,
                notes="Comisiones devengadas"
            ))
            created_count += 1

    await db.commit()
    return {"message": "Incidencias de prenómina guardadas correctamente", "incidents_created": created_count}


# ==========================================
# MOTOR DE CÁLCULO MASIVO DE NÓMINA
# ==========================================
async def calculate_payroll_period(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    period_id: uuid.UUID
) -> PayrollPeriod:
    """
    Ejecuta el cálculo masivo de nómina para todos los trabajadores activos.
    Determina sueldos, percepciones, retención de ISR (Art. 96) y cuota obrera IMSS.
    Genera los recibos individuales y consolida los totales patronales.
    """
    period = await get_payroll_period_by_id(db, tenant_id, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Periodo no encontrado.")
    if period.status in ("DISPERSADA", "TIMBRADA"):
        raise HTTPException(status_code=400, detail="No se puede recalcular una nómina dispersada o timbrada.")

    # 1. Obtener empleados activos
    employees = await get_employees(db, tenant_id, status_filter="ACTIVO")
    if not employees:
        raise HTTPException(status_code=400, detail="No hay empleados activos para procesar en este periodo.")

    # 2. Obtener incidencias del periodo
    stmt_inc = select(PayrollIncident).where(
        PayrollIncident.tenant_id == tenant_id,
        PayrollIncident.payroll_period_id == period_id
    )
    res_inc = await db.execute(stmt_inc)
    incidents_list = list(res_inc.scalars().all())

    # Agrupar incidencias por empleado
    emp_incidents: Dict[uuid.UUID, List[Dict[str, Any]]] = {}
    for inc in incidents_list:
        emp_incidents.setdefault(inc.employee_id, []).append({
            "incident_type": inc.incident_type,
            "quantity": inc.quantity,
            "amount": inc.amount,
        })

    # 3. Eliminar recibos previos si existían en borrador
    await db.execute(
        delete(PayrollReceipt).where(
            PayrollReceipt.tenant_id == tenant_id,
            PayrollReceipt.payroll_period_id == period_id
        )
    )

    tot_perceptions = Decimal("0.00")
    tot_deductions = Decimal("0.00")
    tot_net = Decimal("0.00")
    tot_isr = Decimal("0.00")
    tot_imss_emp = Decimal("0.00")
    tot_imss_pat = Decimal("0.00")

    receipt_counter = 1
    for emp in employees:
        incidents = emp_incidents.get(emp.id, [])
        calc = calculate_employee_payroll(
            daily_salary=emp.daily_salary,
            integrated_daily_salary=emp.integrated_daily_salary,
            period_days=period.days_paid,
            incidents=incidents,
            risk_class=emp.risk_class
        )

        receipt_folio = f"{period.folio}-R{receipt_counter:03d}"
        receipt = PayrollReceipt(
            tenant_id=tenant_id,
            payroll_period_id=period_id,
            period=period,
            employee_id=emp.id,
            folio=receipt_folio,
            days_worked=calc["days_worked"],
            days_paid=calc["days_paid"],
            daily_salary=emp.daily_salary,
            integrated_daily_salary=emp.integrated_daily_salary,
            base_salary=calc["base_salary"],
            total_perceptions=calc["total_perceptions"],
            total_deductions=calc["total_deductions"],
            total_net=calc["total_net"],
            isr_retention=calc["isr_retention"],
            imss_employee_retention=calc["imss_employee_retention"],
            imss_employer_cost=calc["imss_employer_cost"],
            status="CALCULADO"
        )
        db.add(receipt)
        await db.flush()

        # Partidas del recibo
        for item in calc["items"]:
            rec_item = PayrollReceiptItem(
                payroll_receipt_id=receipt.id,
                item_type=item["item_type"],
                sat_code=item["sat_code"],
                concept_key=item["concept_key"],
                description=item["description"],
                taxed_amount=item["taxed_amount"],
                exempt_amount=item["exempt_amount"],
                total_amount=item["total_amount"]
            )
            db.add(rec_item)

        tot_perceptions += calc["total_perceptions"]
        tot_deductions += calc["total_deductions"]
        tot_net += calc["total_net"]
        tot_isr += calc["isr_retention"]
        tot_imss_emp += calc["imss_employee_retention"]
        tot_imss_pat += calc["imss_employer_cost"]
        receipt_counter += 1

    # Actualizar totales consolidados del periodo
    period.total_perceptions = quantize_2(tot_perceptions)
    period.total_deductions = quantize_2(tot_deductions)
    period.total_net = quantize_2(tot_net)
    period.total_isr_retention = quantize_2(tot_isr)
    period.total_imss_employee = quantize_2(tot_imss_emp)
    period.total_imss_employer = quantize_2(tot_imss_pat)
    period.status = "CALCULADA"

    await db.commit()
    return await get_payroll_period_by_id(db, tenant_id, period_id)


# ==========================================
# DISPERSIÓN BANCARIA (INTEGRACIÓN FASE 8)
# ==========================================
async def disburse_payroll(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    period_id: uuid.UUID,
    bank_account_id: uuid.UUID,
    notes: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None
) -> Dict[str, Any]:
    """
    Dispersa la nómina patronal debitando el total neto de la cuenta bancaria seleccionada.
    
    INTEGRACIÓN CON EL MÓDULO DE BANCOS (Fase 8):
    1. Bloqueo 'SELECT ... FOR UPDATE' en la cuenta bancaria.
    2. Control de sobregiro: valida fondos disponibles vs. 'period.total_net'.
    3. Registra la transacción de salida inmutable en 'BankTransaction'.
    4. Actualiza el periodo a 'DISPERSADA' y autoriza los recibos.
    """
    period = await get_payroll_period_by_id(db, tenant_id, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Periodo de nómina no encontrado.")
    if period.status == "DISPERSADA":
        raise HTTPException(status_code=400, detail="Este periodo de nómina ya ha sido dispersado previamente.")
    if period.status not in ("CALCULADA", "AUTORIZADA", "TIMBRADA"):
        raise HTTPException(status_code=400, detail="El periodo debe ser calculado antes de proceder a la dispersión.")
    if period.total_net <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="El monto neto a dispersar debe ser mayor a cero.")

    # Transacción bancaria de retiro patronal
    bank_tx, bank_acc = await record_bank_transaction(
        db=db,
        tenant_id=tenant_id,
        bank_account_id=bank_account_id,
        amount=period.total_net,
        direction="OUT",
        transaction_type="RETIRO",
        reference_type="PAYROLL_PERIOD",
        reference_id=period.id,
        reference_folio=period.folio,
        notes=notes or f"Dispersión de Nómina - Periodo {period.folio} ({period.name})",
        user_id=user_id,
        for_update=True
    )

    # Actualizar estado del periodo
    period.bank_account_id = bank_account_id
    period.disbursed_at = datetime.now(timezone.utc)
    if period.status != "TIMBRADA":
        period.status = "DISPERSADA"

    # Marcar recibos como autorizados/pagados
    for rec in period.receipts:
        if rec.status == "CALCULADO":
            rec.status = "AUTORIZADO"

    await db.commit()

    return {
        "message": "Nómina dispersada con éxito",
        "period_folio": period.folio,
        "disbursed_net_amount": period.total_net,
        "bank_account_id": str(bank_acc.id),
        "bank_new_balance": bank_acc.current_balance,
        "bank_transaction_id": str(bank_tx.id)
    }


# ==========================================
# TIMBRADO EN LOTE (CFDI 4.0 + NÓMINA 1.2 SAT)
# ==========================================
async def batch_stamp_payroll_period(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    period_id: uuid.UUID
) -> BatchStampResponse:
    """
    Timbrado Masivo de los recibos de un periodo de nómina.
    Genera el CFDI 4.0 con Complemento de Nómina 1.2, sella en memoria con CSD
    y timbra a través del Mock PAC SAT.
    """
    period = await get_payroll_period_by_id(db, tenant_id, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Periodo no encontrado.")
    if not period.receipts:
        raise HTTPException(status_code=400, detail="El periodo no cuenta con recibos calculados.")

    # 1. Obtener CSD vigente
    stmt_csd = select(CSDCertificate).where(
        CSDCertificate.tenant_id == tenant_id,
        CSDCertificate.is_active == True
    )
    res_csd = await db.execute(stmt_csd)
    csd = res_csd.scalars().first()
    if not csd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se encontró un Certificado CSD activo en la empresa para timbrar la nómina."
        )

    # 2. Obtener datos de la empresa (Tenant)
    stmt_tenant = select(Tenant).where(Tenant.id == tenant_id)
    res_tenant = await db.execute(stmt_tenant)
    tenant = res_tenant.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")

    # Código postal sucursal matriz
    stmt_branch = select(Branch).where(Branch.tenant_id == tenant_id)
    res_branch = await db.execute(stmt_branch)
    branch = res_branch.scalars().first()
    branch_zip = branch.zip_code if branch else "06000"

    stamped_count = 0
    errors_count = 0
    stamped_uuids: List[str] = []
    error_details: List[str] = []

    for receipt in period.receipts:
        if receipt.status == "TIMBRADO" and receipt.cfdi_uuid:
            stamped_uuids.append(receipt.cfdi_uuid)
            stamped_count += 1
            continue

        try:
            # Generar XML y Sellado Digital CSD
            xml_str, cadena, sello = generate_payroll_cfdi_xml(
                receipt=receipt,
                period=period,
                employee=receipt.employee,
                tenant=tenant,
                csd=csd,
                branch_zip=branch_zip
            )

            # Timbrado con Mock PAC SAT
            pac_result = stamp_with_mock_pac(xml_str, sello)

            receipt.cfdi_uuid = pac_result["uuid"]
            receipt.stamped_at = datetime.now(timezone.utc)
            receipt.xml_cfdi = pac_result["stamped_xml"]
            receipt.cadena_original = cadena
            receipt.sello_digital = sello
            receipt.sello_sat = pac_result["sello_sat"]
            receipt.status = "TIMBRADO"

            stamped_uuids.append(pac_result["uuid"])
            stamped_count += 1
        except Exception as e:
            errors_count += 1
            error_details.append(f"Error al timbrar empleado {receipt.employee.code}: {str(e)}")

    if stamped_count > 0 and errors_count == 0:
        period.status = "TIMBRADA"

    await db.commit()

    return BatchStampResponse(
        period_id=period.id,
        total_receipts=len(period.receipts),
        stamped_count=stamped_count,
        errors_count=errors_count,
        stamped_uuids=stamped_uuids,
        error_details=error_details
    )


# ==========================================
# DASHBOARD RRHH Y ANALÍTICA
# ==========================================
async def get_payroll_dashboard_metrics(
    db: AsyncSession,
    tenant_id: uuid.UUID
) -> PayrollDashboardMetrics:
    # Empleados activos
    stmt_emp = select(func.count(Employee.id)).where(
        Employee.tenant_id == tenant_id,
        Employee.status == "ACTIVO"
    )
    res_emp = await db.execute(stmt_emp)
    active_emp_count = res_emp.scalar() or 0

    # Periodos del mes actual o recientes
    periods = await get_payroll_periods(db, tenant_id)
    
    total_cost = Decimal("0.00")
    total_net = Decimal("0.00")
    total_imss = Decimal("0.00")

    for p in periods:
        if p.status in ("CALCULADA", "AUTORIZADA", "DISPERSADA", "TIMBRADA"):
            total_cost += p.total_perceptions + p.total_imss_employer
            total_net += p.total_net
            total_imss += p.total_imss_employee + p.total_imss_employer

    social_burden_pct = Decimal("0.00")
    if total_net > Decimal("0.00"):
        social_burden_pct = quantize_2((total_imss / total_net) * Decimal("100.00"))

    recent_summary = []
    for p in periods[:5]:
        recent_summary.append(
            {
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
                "receipt_count": len(p.receipts),
                "created_at": p.created_at,
                "updated_at": p.updated_at
            }
        )

    return PayrollDashboardMetrics(
        total_payroll_cost_month=quantize_2(total_cost),
        total_active_employees=active_emp_count,
        total_social_security_imss=quantize_2(total_imss),
        total_net_salary_disbursed=quantize_2(total_net),
        active_periods_count=len(periods),
        social_burden_percentage=social_burden_pct,
        recent_periods=recent_summary
    )
