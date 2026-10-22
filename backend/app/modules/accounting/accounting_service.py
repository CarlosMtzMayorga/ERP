import uuid
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta, date
from typing import List, Optional, Tuple, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.tenants.models import FiscalFoliosSeries
from app.modules.tenants.folios_service import consume_next_folio
from app.modules.accounting.models import Account, JournalEntry, JournalEntryLine
from app.modules.accounting.chart_of_accounts import seed_default_chart_of_accounts
from app.modules.accounting.schemas import (
    AccountCreate,
    AccountUpdate,
    JournalEntryCreate,
    JournalEntryLineCreate,
    TrialBalanceReport,
    TrialBalanceItem,
    IncomeStatementReport,
    BalanceSheetReport,
    BalanceSheetSection,
    FinancialStatementLine,
    AccountingDashboardMetrics,
    JournalEntryResponse,
    JournalEntryLineResponse
)


def _round_2(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def ensure_accounting_folio_series(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    entry_type: str = "DIARIO"
) -> str:
    """Garantiza la existencia de la serie de folios para pólizas según su tipo."""
    doc_type_map = {
        "DIARIO": ("POL_DI", "PD"),
        "INGRESO": ("POL_ING", "PI"),
        "EGRESO": ("POL_EG", "PE"),
    }
    doc_type, serie = doc_type_map.get(entry_type.upper(), ("POL_DI", "PD"))

    stmt = select(FiscalFoliosSeries).where(
        FiscalFoliosSeries.tenant_id == tenant_id,
        FiscalFoliosSeries.document_type == doc_type
    )
    res = await db.execute(stmt)
    existing = res.scalars().first()
    if not existing:
        new_serie = FiscalFoliosSeries(
            tenant_id=tenant_id,
            document_type=doc_type,
            serie=serie,
            initial_folio=1,
            current_folio=0,
            is_default=True
        )
        db.add(new_serie)
        await db.flush()

    return doc_type


# ==========================================
# GESTIÓN DE CUENTAS CONTABLES
# ==========================================
async def get_accounts(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    account_type: Optional[str] = None
) -> List[Account]:
    """Obtiene el catálogo de cuentas de la empresa ordenado por número de cuenta."""
    # Asegurar catálogo estándar sembrado
    await seed_default_chart_of_accounts(db, tenant_id)

    stmt = select(Account).where(Account.tenant_id == tenant_id)
    if account_type:
        stmt = stmt.where(Account.account_type == account_type.upper())
    stmt = stmt.order_by(Account.account_number.asc())
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def get_account_by_number(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    account_number: str
) -> Optional[Account]:
    stmt = select(Account).where(
        Account.tenant_id == tenant_id,
        Account.account_number == account_number.strip()
    )
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


async def create_account(db: AsyncSession, tenant_id: uuid.UUID, data: AccountCreate) -> Account:
    existing = await get_account_by_number(db, tenant_id, data.account_number)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe una cuenta con el número '{data.account_number}'."
        )

    acc = Account(
        tenant_id=tenant_id,
        parent_id=data.parent_id,
        account_number=data.account_number.strip(),
        name=data.name.strip(),
        nature=data.nature.upper(),
        account_type=data.account_type.upper(),
        level=data.level,
        is_group=data.is_group,
        sat_group_code=data.sat_group_code.strip(),
        initial_balance=Decimal("0.00"),
        current_balance=Decimal("0.00"),
        is_active=True
    )
    db.add(acc)
    await db.commit()
    await db.refresh(acc)
    return acc


# ==========================================
# MOTOR DE PARTIDA DOBLE (PÓLIZAS)
# ==========================================
async def create_journal_entry(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: JournalEntryCreate,
    source_module: str = "MANUAL",
    source_id: Optional[uuid.UUID] = None,
    source_folio: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None
) -> JournalEntry:
    """
    Registra y aplica una póliza contable con estricto principio de partida doble.
    
    REGLA MATEMÁTICA INQUEBRANTABLE:
    La suma de los Cargos (debit) debe ser exactamente igual a la suma de los Abonos (credit).
    Si sum(debit) != sum(credit), rechaza la operación con HTTP 400.
    """
    if not data.lines or len(data.lines) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Una póliza contable debe contener al menos dos partidas (un cargo y un abono)."
        )

    total_debit = _round_2(sum(Decimal(str(line.debit)) for line in data.lines))
    total_credit = _round_2(sum(Decimal(str(line.credit)) for line in data.lines))
    diff = abs(total_debit - total_credit)

    # Validación de Cuadre Inquebrantable
    if diff > Decimal("0.001"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Póliza descuadrada: La suma de Cargos (${total_debit:,.2f}) "
                f"no coincide con la suma de Abonos (${total_credit:,.2f}). "
                f"Diferencia: ${diff:,.2f}."
            )
        )

    if total_debit <= Decimal("0.00"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El importe total de la póliza debe ser mayor a cero."
        )

    # 1. Consumir Folio Atómico
    doc_type = await ensure_accounting_folio_series(db, tenant_id, data.entry_type)
    serie, next_num, _ = await consume_next_folio(db, tenant_id, doc_type)
    formatted_folio = f"{serie}-{next_num:05d}"

    # 2. Crear encabezado de póliza
    entry = JournalEntry(
        tenant_id=tenant_id,
        folio=formatted_folio,
        entry_type=data.entry_type.upper(),
        entry_date=data.entry_date,
        concept=data.concept.strip(),
        total_debit=total_debit,
        total_credit=total_credit,
        status="APLICADA",
        source_module=source_module.upper(),
        source_id=source_id,
        source_folio=source_folio,
        user_id=user_id
    )
    db.add(entry)
    await db.flush()

    # 3. Procesar partidas y actualizar saldos de cuentas de forma atómica
    for idx, l in enumerate(data.lines, start=1):
        # Bloquear cuenta contable con for_update para consistencia
        stmt_acc = select(Account).where(
            Account.id == l.account_id,
            Account.tenant_id == tenant_id
        ).with_for_update()
        res_acc = await db.execute(stmt_acc)
        account = res_acc.scalar_one_or_none()

        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cuenta contable ID {l.account_id} no encontrada."
            )
        if account.is_group:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La cuenta '{account.account_number} - {account.name}' es de mayor/grupo y no admite imputaciones directas."
            )

        line_debit = _round_2(Decimal(str(l.debit)))
        line_credit = _round_2(Decimal(str(l.credit)))

        # Actualizar saldo de la cuenta según su naturaleza contable
        # DEUDORA: Aumenta con Cargos, Disminuye con Abonos
        # ACREEDORA: Aumenta con Abonos, Disminuye con Cargos
        if account.nature == "DEUDORA":
            account.current_balance += (line_debit - line_credit)
        else:
            account.current_balance += (line_credit - line_debit)

        line_obj = JournalEntryLine(
            journal_entry_id=entry.id,
            account_id=account.id,
            line_number=idx,
            concept=l.concept.strip(),
            debit=line_debit,
            credit=line_credit,
            cfdi_uuid=l.cfdi_uuid
        )
        db.add(line_obj)

    await db.commit()
    return await get_journal_entry_by_id(db, tenant_id, entry.id)


async def get_journal_entries(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    entry_type: Optional[str] = None,
    source_module: Optional[str] = None
) -> List[JournalEntry]:
    stmt = (
        select(JournalEntry)
        .where(JournalEntry.tenant_id == tenant_id)
        .options(selectinload(JournalEntry.lines))
    )
    if entry_type:
        stmt = stmt.where(JournalEntry.entry_type == entry_type.upper())
    if source_module:
        stmt = stmt.where(JournalEntry.source_module == source_module.upper())
    stmt = stmt.order_by(desc(JournalEntry.entry_date), desc(JournalEntry.created_at))
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def get_journal_entry_by_id(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    entry_id: uuid.UUID
) -> Optional[JournalEntry]:
    stmt = (
        select(JournalEntry)
        .where(JournalEntry.tenant_id == tenant_id, JournalEntry.id == entry_id)
        .options(
            selectinload(JournalEntry.lines).selectinload(JournalEntryLine.account)
        )
    )
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


# ==========================================
# MOTOR DE PÓLIZAS AUTOMÁTICAS (INTEGRACIÓN ERP)
# ==========================================
async def get_or_seed_account_map(db: AsyncSession, tenant_id: uuid.UUID) -> Dict[str, Account]:
    """Retorna el mapa {account_number: Account} de la empresa para contabilización automática."""
    accounts = await get_accounts(db, tenant_id)
    return {acc.account_number: acc for acc in accounts}


async def create_automatic_sales_journal_entry(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    sales_doc: Any
) -> Optional[JournalEntry]:
    """
    Póliza Automática por Factura de Venta (Fases 4 y 5):
    1. Cargo a Clientes (1105) o Bancos (1102) si es de contado -> Total Facturado
    2. Abono a Ventas Gravadas (4101) -> Subtotal
    3. Abono a IVA Trasladado (2108 / 2109) -> IVA Total
    4. Cargo a Costo de Ventas (5101) -> Costo de lo vendido (COGS evaluado en inventarios)
    5. Abono a Inventario de Mercancías (1115) -> Costo de lo vendido (descarga de almacén)
    """
    if getattr(sales_doc, "document_type", "").upper() != "FACTURA":
        return None

    acc_map = await get_or_seed_account_map(db, tenant_id)

    # Determinar si es crédito o contado
    is_credit = getattr(sales_doc, "payment_method", "PUE") == "PPD"
    charge_acc = acc_map.get("1105") if is_credit else acc_map.get("1102")  # Clientes o Bancos
    sales_acc = acc_map.get("4101")  # Ventas Gravadas 16%
    vat_acc = acc_map.get("2109") if is_credit else acc_map.get("2108")  # IVA No Cobrado o Cobrado
    cogs_acc = acc_map.get("5101")  # Costo de Ventas
    inventory_acc = acc_map.get("1115")  # Inventarios

    if not all([charge_acc, sales_acc, vat_acc, cogs_acc, inventory_acc]):
        return None

    total = _round_2(sales_doc.total)
    subtotal = _round_2(sales_doc.subtotal)
    vat = _round_2(sales_doc.tax_iva_total)
    cogs = _round_2(getattr(sales_doc, "total_cost_cogs", Decimal("0.00")))
    cfdi_uuid = getattr(sales_doc, "cfdi_uuid", None)
    folio = getattr(sales_doc, "formatted_folio", "FAC")

    lines: List[JournalEntryLineCreate] = []

    # 1. Cargo a Clientes o Bancos
    lines.append(JournalEntryLineCreate(
        account_id=charge_acc.id,
        concept=f"Venta en Factura {folio}",
        debit=total,
        credit=Decimal("0.00"),
        cfdi_uuid=cfdi_uuid
    ))

    # 2. Abono a Ventas
    lines.append(JournalEntryLineCreate(
        account_id=sales_acc.id,
        concept=f"Ingreso por venta Factura {folio}",
        debit=Decimal("0.00"),
        credit=subtotal,
        cfdi_uuid=cfdi_uuid
    ))

    # 3. Abono a IVA
    if vat > Decimal("0.00"):
        lines.append(JournalEntryLineCreate(
            account_id=vat_acc.id,
            concept=f"IVA Trasladado Factura {folio}",
            debit=Decimal("0.00"),
            credit=vat,
            cfdi_uuid=cfdi_uuid
        ))

    # 4 & 5. Costo de Ventas e Inventarios (Partida doble exacta de costo)
    if cogs > Decimal("0.00"):
        lines.append(JournalEntryLineCreate(
            account_id=cogs_acc.id,
            concept=f"Costo de lo vendido Factura {folio}",
            debit=cogs,
            credit=Decimal("0.00"),
            cfdi_uuid=cfdi_uuid
        ))
        lines.append(JournalEntryLineCreate(
            account_id=inventory_acc.id,
            concept=f"Descarga de inventario Factura {folio}",
            debit=Decimal("0.00"),
            credit=cogs,
            cfdi_uuid=cfdi_uuid
        ))

    entry_data = JournalEntryCreate(
        entry_type="INGRESO" if not is_credit else "DIARIO",
        entry_date=date.today(),
        concept=f"Registro contable automático Factura de Venta {folio}",
        lines=lines
    )

    return await create_journal_entry(
        db=db,
        tenant_id=tenant_id,
        data=entry_data,
        source_module="SALES",
        source_id=sales_doc.id,
        source_folio=folio
    )


async def create_automatic_purchase_journal_entry(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    purchase_doc: Any
) -> Optional[JournalEntry]:
    """
    Póliza Automática por Compra a Proveedor (Fase 7):
    1. Cargo a Inventarios (1115) -> Subtotal
    2. Cargo a IVA Acreditable Pendiente (1119) -> IVA Total
    3. Abono a Proveedores Nacionales (2101) -> Total Pasivo
    """
    acc_map = await get_or_seed_account_map(db, tenant_id)
    inv_acc = acc_map.get("1115")
    vat_pend_acc = acc_map.get("1119")
    prov_acc = acc_map.get("2101")

    if not all([inv_acc, vat_pend_acc, prov_acc]):
        return None

    total = _round_2(purchase_doc.total)
    subtotal = _round_2(purchase_doc.subtotal)
    vat = _round_2(purchase_doc.tax_iva_total)
    folio = getattr(purchase_doc, "formatted_folio", "COMPRA")
    cfdi_uuid = getattr(purchase_doc, "cfdi_uuid", None)

    lines: List[JournalEntryLineCreate] = [
        JournalEntryLineCreate(
            account_id=inv_acc.id,
            concept=f"Entrada de mercancías compra {folio}",
            debit=subtotal,
            credit=Decimal("0.00"),
            cfdi_uuid=cfdi_uuid
        ),
        JournalEntryLineCreate(
            account_id=vat_pend_acc.id,
            concept=f"IVA Acreditable pendiente compra {folio}",
            debit=vat,
            credit=Decimal("0.00"),
            cfdi_uuid=cfdi_uuid
        ),
        JournalEntryLineCreate(
            account_id=prov_acc.id,
            concept=f"Pasivo generado compra {folio}",
            debit=Decimal("0.00"),
            credit=total,
            cfdi_uuid=cfdi_uuid
        )
    ]

    entry_data = JournalEntryCreate(
        entry_type="DIARIO",
        entry_date=date.today(),
        concept=f"Registro contable automático Compra a Proveedor {folio}",
        lines=lines
    )

    return await create_journal_entry(
        db=db,
        tenant_id=tenant_id,
        data=entry_data,
        source_module="PURCHASES",
        source_id=purchase_doc.id,
        source_folio=folio
    )


async def create_automatic_supplier_payment_journal_entry(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    payment: Any
) -> Optional[JournalEntry]:
    """
    Póliza Automática de Pago a Proveedor (Fase 8 / CxP):
    1. Cargo a Proveedores Nacionales (2101) -> Monto Pagado
    2. Abono a Bancos Nacionales (1102) -> Salida de efectivo
    """
    acc_map = await get_or_seed_account_map(db, tenant_id)
    prov_acc = acc_map.get("2101")
    bank_acc = acc_map.get("1102")

    if not prov_acc or not bank_acc:
        return None

    amount = _round_2(payment.amount)
    folio = getattr(payment, "formatted_folio", "PAGO")

    lines: List[JournalEntryLineCreate] = [
        JournalEntryLineCreate(
            account_id=prov_acc.id,
            concept=f"Liquidación a proveedor pago {folio}",
            debit=amount,
            credit=Decimal("0.00")
        ),
        JournalEntryLineCreate(
            account_id=bank_acc.id,
            concept=f"Salida de tesorería pago {folio}",
            debit=Decimal("0.00"),
            credit=amount
        )
    ]

    entry_data = JournalEntryCreate(
        entry_type="EGRESO",
        entry_date=date.today(),
        concept=f"Póliza de egreso automático pago a proveedor {folio}",
        lines=lines
    )

    return await create_journal_entry(
        db=db,
        tenant_id=tenant_id,
        data=entry_data,
        source_module="CXP",
        source_id=payment.id,
        source_folio=folio
    )


async def create_automatic_payroll_journal_entry(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    period: Any
) -> Optional[JournalEntry]:
    """
    Póliza Automática de Nómina Patronal (Fase 9):
    1. Cargo a Sueldos y Salarios (6101) -> Total Percepciones
    2. Cargo a Cuotas Patronales IMSS (6102) -> Costo Patronal IMSS
    3. Abono a Bancos (1102) -> Neto pagado
    4. Abono a Retención de ISR (2116) -> ISR Retenido Art. 96
    5. Abono a Cuotas IMSS por Pagar (2111) -> IMSS Obrero + IMSS Patronal
    """
    acc_map = await get_or_seed_account_map(db, tenant_id)
    salaries_acc = acc_map.get("6101")
    imss_pat_acc = acc_map.get("6102")
    bank_acc = acc_map.get("1102")
    isr_ret_acc = acc_map.get("2116")
    imss_pay_acc = acc_map.get("2111")

    if not all([salaries_acc, imss_pat_acc, bank_acc, isr_ret_acc, imss_pay_acc]):
        return None

    perceptions = _round_2(period.total_perceptions)
    imss_employer = _round_2(period.total_imss_employer)
    net_salary = _round_2(period.total_net)
    isr_retention = _round_2(period.total_isr_retention)
    imss_total_payable = _round_2(period.total_imss_employee + period.total_imss_employer)
    folio = getattr(period, "folio", "NOMINA")

    lines: List[JournalEntryLineCreate] = [
        # Cargos (Gastos)
        JournalEntryLineCreate(
            account_id=salaries_acc.id,
            concept=f"Gasto por Sueldos y Salarios Nómina {folio}",
            debit=perceptions,
            credit=Decimal("0.00")
        ),
        JournalEntryLineCreate(
            account_id=imss_pat_acc.id,
            concept=f"Gasto Carga Patronal IMSS Nómina {folio}",
            debit=imss_employer,
            credit=Decimal("0.00")
        ),
        # Abonos (Bancos + Pasivos retenidos)
        JournalEntryLineCreate(
            account_id=bank_acc.id,
            concept=f"Dispersión neta de salarios Nómina {folio}",
            debit=Decimal("0.00"),
            credit=net_salary
        ),
        JournalEntryLineCreate(
            account_id=isr_ret_acc.id,
            concept=f"Retención ISR Art. 96 Nómina {folio}",
            debit=Decimal("0.00"),
            credit=isr_retention
        ),
        JournalEntryLineCreate(
            account_id=imss_pay_acc.id,
            concept=f"Cuotas IMSS obrero-patronal por pagar Nómina {folio}",
            debit=Decimal("0.00"),
            credit=imss_total_payable
        )
    ]

    entry_data = JournalEntryCreate(
        entry_type="EGRESO",
        entry_date=date.today(),
        concept=f"Contabilización automática dispersión de Nómina {folio}",
        lines=lines
    )

    return await create_journal_entry(
        db=db,
        tenant_id=tenant_id,
        data=entry_data,
        source_module="PAYROLL",
        source_id=period.id,
        source_folio=folio
    )


# ==========================================
# GENERADOR DE ESTADOS FINANCIEROS (REPORTING)
# ==========================================
async def get_trial_balance(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    start_date: date,
    end_date: date
) -> TrialBalanceReport:
    """
    1. Balanza de Comprobación (Anexo 24 SAT):
    Saldos Iniciales, Movimientos (Cargos/Abonos) del periodo y Saldos Finales.
    Verifica sumas iguales.
    """
    accounts = await get_accounts(db, tenant_id)
    account_ids = [acc.id for acc in accounts]

    # Movimientos del periodo
    stmt_lines = (
        select(
            JournalEntryLine.account_id,
            func.coalesce(func.sum(JournalEntryLine.debit), Decimal("0.00")).label("period_debit"),
            func.coalesce(func.sum(JournalEntryLine.credit), Decimal("0.00")).label("period_credit")
        )
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.status == "APLICADA",
            JournalEntry.entry_date >= start_date,
            JournalEntry.entry_date <= end_date
        )
        .group_by(JournalEntryLine.account_id)
    )
    res_lines = await db.execute(stmt_lines)
    period_movs = {row.account_id: (row.period_debit, row.period_credit) for row in res_lines.all()}

    items: List[TrialBalanceItem] = []
    tot_init_deb = Decimal("0.00")
    tot_init_cred = Decimal("0.00")
    tot_per_deb = Decimal("0.00")
    tot_per_cred = Decimal("0.00")
    tot_fin_deb = Decimal("0.00")
    tot_fin_cred = Decimal("0.00")

    for acc in accounts:
        # Solo mostrar cuentas con saldo o movimientos
        p_deb, p_cred = period_movs.get(acc.id, (Decimal("0.00"), Decimal("0.00")))
        
        # Saldo inicial según naturaleza
        init_bal = acc.initial_balance
        init_deb = init_bal if acc.nature == "DEUDORA" and init_bal > 0 else Decimal("0.00")
        init_cred = abs(init_bal) if acc.nature == "ACREEDORA" and init_bal > 0 else Decimal("0.00")

        # Saldo final
        if acc.nature == "DEUDORA":
            net_bal = (init_deb - init_cred) + (p_deb - p_cred)
            fin_deb = max(Decimal("0.00"), net_bal)
            fin_cred = max(Decimal("0.00"), -net_bal)
        else:
            net_bal = (init_cred - init_deb) + (p_cred - p_deb)
            fin_cred = max(Decimal("0.00"), net_bal)
            fin_deb = max(Decimal("0.00"), -net_bal)

        items.append(TrialBalanceItem(
            account_number=acc.account_number,
            name=acc.name,
            nature=acc.nature,
            account_type=acc.account_type,
            level=acc.level,
            is_group=acc.is_group,
            sat_group_code=acc.sat_group_code,
            initial_debit=_round_2(init_deb),
            initial_credit=_round_2(init_cred),
            period_debit=_round_2(p_deb),
            period_credit=_round_2(p_cred),
            final_debit=_round_2(fin_deb),
            final_credit=_round_2(fin_cred)
        ))

        if not acc.is_group:
            tot_init_deb += init_deb
            tot_init_cred += init_cred
            tot_per_deb += p_deb
            tot_per_cred += p_cred
            tot_fin_deb += fin_deb
            tot_fin_cred += fin_cred

    is_balanced = abs(tot_per_deb - tot_per_cred) <= Decimal("0.01") and abs(tot_fin_deb - tot_fin_cred) <= Decimal("0.01")

    return TrialBalanceReport(
        start_date=start_date,
        end_date=end_date,
        items=items,
        total_initial_debit=_round_2(tot_init_deb),
        total_initial_credit=_round_2(tot_init_cred),
        total_period_debit=_round_2(tot_per_deb),
        total_period_credit=_round_2(tot_per_cred),
        total_final_debit=_round_2(tot_fin_deb),
        total_final_credit=_round_2(tot_fin_cred),
        is_balanced=is_balanced
    )


async def get_income_statement(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    start_date: date,
    end_date: date
) -> IncomeStatementReport:
    """
    2. Estado de Resultados (P&L):
    Ventas Netas - Costo de Ventas = Utilidad Bruta
    Utilidad Bruta - Gastos Operativos = EBITDA / Utilidad Neta.
    """
    accounts = await get_accounts(db, tenant_id)

    # Movimientos en el rango de fechas
    stmt_lines = (
        select(
            JournalEntryLine.account_id,
            func.coalesce(func.sum(JournalEntryLine.debit), Decimal("0.00")).label("deb"),
            func.coalesce(func.sum(JournalEntryLine.credit), Decimal("0.00")).label("cred")
        )
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.status == "APLICADA",
            JournalEntry.entry_date >= start_date,
            JournalEntry.entry_date <= end_date
        )
        .group_by(JournalEntryLine.account_id)
    )
    res_lines = await db.execute(stmt_lines)
    movs = {row.account_id: (row.deb, row.cred) for row in res_lines.all()}

    gross_sales = Decimal("0.00")
    sales_discounts = Decimal("0.00")
    cogs_total = Decimal("0.00")
    expenses_total = Decimal("0.00")

    revenue_lines: List[FinancialStatementLine] = []
    cogs_lines: List[FinancialStatementLine] = []
    expense_lines: List[FinancialStatementLine] = []

    for acc in accounts:
        if acc.is_group:
            continue
        deb, cred = movs.get(acc.id, (Decimal("0.00"), Decimal("0.00")))

        if acc.account_type == "INGRESOS":
            # Cuentas de ingresos son acreedoras (cred - deb)
            amt = _round_2(cred - deb)
            if amt != Decimal("0.00"):
                gross_sales += amt
                revenue_lines.append(FinancialStatementLine(
                    account_number=acc.account_number,
                    name=acc.name,
                    amount=amt
                ))
        elif acc.account_type == "COSTOS":
            # Costos son deudores (deb - cred)
            amt = _round_2(deb - cred)
            if amt != Decimal("0.00"):
                cogs_total += amt
                cogs_lines.append(FinancialStatementLine(
                    account_number=acc.account_number,
                    name=acc.name,
                    amount=amt
                ))
        elif acc.account_type == "GASTOS":
            # Gastos son deudores (deb - cred)
            amt = _round_2(deb - cred)
            if amt != Decimal("0.00"):
                expenses_total += amt
                expense_lines.append(FinancialStatementLine(
                    account_number=acc.account_number,
                    name=acc.name,
                    amount=amt
                ))

    net_sales = _round_2(gross_sales - sales_discounts)
    gross_profit = _round_2(net_sales - cogs_total)
    ebitda = _round_2(gross_profit - expenses_total)
    net_income = ebitda

    margin_pct = Decimal("0.00")
    if net_sales > Decimal("0.00"):
        margin_pct = _round_2((gross_profit / net_sales) * Decimal("100.00"))

    return IncomeStatementReport(
        start_date=start_date,
        end_date=end_date,
        gross_sales=gross_sales,
        sales_discounts=sales_discounts,
        net_sales=net_sales,
        cost_of_goods_sold=cogs_total,
        gross_profit=gross_profit,
        gross_margin_percentage=margin_pct,
        operating_expenses=expenses_total,
        ebitda_operating_income=ebitda,
        net_income=net_income,
        revenue_lines=revenue_lines,
        cogs_lines=cogs_lines,
        expense_lines=expense_lines
    )


async def get_balance_sheet(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    as_of_date: date
) -> BalanceSheetReport:
    """
    3. Balance General (Estado de Situación Financiera):
    Total Activos = Total Pasivos + Total Capital Contable.
    """
    accounts = await get_accounts(db, tenant_id)

    # Movimientos acumulados hasta la fecha de corte
    stmt_lines = (
        select(
            JournalEntryLine.account_id,
            func.coalesce(func.sum(JournalEntryLine.debit), Decimal("0.00")).label("deb"),
            func.coalesce(func.sum(JournalEntryLine.credit), Decimal("0.00")).label("cred")
        )
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.status == "APLICADA",
            JournalEntry.entry_date <= as_of_date
        )
        .group_by(JournalEntryLine.account_id)
    )
    res_lines = await db.execute(stmt_lines)
    movs = {row.account_id: (row.deb, row.cred) for row in res_lines.all()}

    cur_assets_lines: List[FinancialStatementLine] = []
    non_cur_assets_lines: List[FinancialStatementLine] = []
    short_liab_lines: List[FinancialStatementLine] = []
    long_liab_lines: List[FinancialStatementLine] = []
    equity_lines: List[FinancialStatementLine] = []

    cur_assets_tot = Decimal("0.00")
    non_cur_assets_tot = Decimal("0.00")
    short_liab_tot = Decimal("0.00")
    long_liab_tot = Decimal("0.00")
    equity_tot = Decimal("0.00")

    # Ingresos, Costos y Gastos para determinar la Utilidad Neta del Ejercicio
    revenue_tot = Decimal("0.00")
    costs_tot = Decimal("0.00")
    expenses_tot = Decimal("0.00")

    for acc in accounts:
        if acc.is_group:
            continue
        deb, cred = movs.get(acc.id, (Decimal("0.00"), Decimal("0.00")))
        
        # Saldo según naturaleza
        if acc.nature == "DEUDORA":
            balance = _round_2(acc.initial_balance + (deb - cred))
        else:
            balance = _round_2(acc.initial_balance + (cred - deb))

        if acc.account_type == "ACTIVO":
            line = FinancialStatementLine(account_number=acc.account_number, name=acc.name, amount=balance)
            if acc.account_number.startswith("11"):  # Circulante
                cur_assets_lines.append(line)
                cur_assets_tot += balance
            else:  # Fijo / No Circulante
                non_cur_assets_lines.append(line)
                non_cur_assets_tot += balance

        elif acc.account_type == "PASIVO":
            line = FinancialStatementLine(account_number=acc.account_number, name=acc.name, amount=balance)
            if acc.account_number.startswith("21"):  # Corto plazo
                short_liab_lines.append(line)
                short_liab_tot += balance
            else:  # Largo plazo
                long_liab_lines.append(line)
                long_liab_tot += balance

        elif acc.account_type == "CAPITAL":
            line = FinancialStatementLine(account_number=acc.account_number, name=acc.name, amount=balance)
            equity_lines.append(line)
            equity_tot += balance

        elif acc.account_type == "INGRESOS":
            revenue_tot += _round_2(cred - deb)
        elif acc.account_type == "COSTOS":
            costs_tot += _round_2(deb - cred)
        elif acc.account_type == "GASTOS":
            expenses_tot += _round_2(deb - cred)

    # Utilidad neta del ejercicio calculada
    year_net_income = _round_2(revenue_tot - costs_tot - expenses_tot)
    total_assets = _round_2(cur_assets_tot + non_cur_assets_tot)
    total_liabilities = _round_2(short_liab_tot + long_liab_tot)
    total_equity = _round_2(equity_tot + year_net_income)

    total_liab_equity = _round_2(total_liabilities + total_equity)
    is_balanced = abs(total_assets - total_liab_equity) <= Decimal("0.01")

    return BalanceSheetReport(
        as_of_date=as_of_date,
        current_assets=BalanceSheetSection(section_name="Activo Circulante", total=cur_assets_tot, lines=cur_assets_lines),
        non_current_assets=BalanceSheetSection(section_name="Activo No Circulante (Fijo)", total=non_cur_assets_tot, lines=non_cur_assets_lines),
        total_assets=total_assets,
        short_term_liabilities=BalanceSheetSection(section_name="Pasivo a Corto Plazo", total=short_liab_tot, lines=short_liab_lines),
        long_term_liabilities=BalanceSheetSection(section_name="Pasivo a Largo Plazo", total=long_liab_tot, lines=long_liab_lines),
        total_liabilities=total_liabilities,
        equity=BalanceSheetSection(section_name="Capital Contable", total=equity_tot, lines=equity_lines),
        current_year_net_income=year_net_income,
        total_equity=total_equity,
        total_liabilities_and_equity=total_liab_equity,
        is_balanced=is_balanced
    )


# ==========================================
# CFO DASHBOARD METRICS
# ==========================================
async def get_accounting_dashboard(
    db: AsyncSession,
    tenant_id: uuid.UUID
) -> AccountingDashboardMetrics:
    today = date.today()
    start_of_month = date(today.year, today.month, 1)

    bs = await get_balance_sheet(db, tenant_id, as_of_date=today)
    pnl = await get_income_statement(db, tenant_id, start_date=start_of_month, end_date=today)
    recent = await get_journal_entries(db, tenant_id)

    recent_summary = [
        JournalEntryResponse(
            id=e.id,
            folio=e.folio,
            entry_type=e.entry_type,
            entry_date=e.entry_date,
            concept=e.concept,
            total_debit=e.total_debit,
            total_credit=e.total_credit,
            status=e.status,
            source_module=e.source_module,
            source_folio=e.source_folio,
            created_at=e.created_at,
            line_count=len(e.lines) if e.lines else 0
        )
        for e in recent[:10]
    ]

    return AccountingDashboardMetrics(
        total_assets=bs.total_assets,
        total_liabilities=bs.total_liabilities,
        total_equity=bs.total_equity,
        monthly_revenue=pnl.net_sales,
        monthly_net_income=pnl.net_income,
        gross_margin_percentage=pnl.gross_margin_percentage,
        unbalanced_entries_count=0,
        recent_entries=recent_summary
    )

