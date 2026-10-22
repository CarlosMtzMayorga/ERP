import uuid
from decimal import Decimal
from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.tenant_context import get_current_tenant_id
from app.core.dependencies import get_current_user, require_permission
from app.modules.auth.models import User
from app.modules.accounting.schemas import (
    AccountCreate,
    AccountUpdate,
    AccountResponse,
    JournalEntryCreate,
    JournalEntryResponse,
    JournalEntryDetailResponse,
    JournalEntryLineResponse,
    TrialBalanceReport,
    IncomeStatementReport,
    BalanceSheetReport,
    AccountingDashboardMetrics
)
from app.modules.accounting import accounting_service

router = APIRouter(prefix="/accounting", tags=["Contabilidad y Estados Financieros"])


# ==========================================
# CFO DASHBOARD
# ==========================================
@router.get("/dashboard", response_model=AccountingDashboardMetrics)
async def get_accounting_dashboard(
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("accounting:read"))
):
    """Métricas ejecutivas para el Director de Finanzas (CFO View): Activos, Pasivos, Margen y Utilidad."""
    return await accounting_service.get_accounting_dashboard(db, tenant_id)


# ==========================================
# CATÁLOGO DE CUENTAS (ANEXO 24 SAT)
# ==========================================
@router.get("/accounts", response_model=List[AccountResponse])
async def list_accounts(
    account_type: Optional[str] = Query(None, description="ACTIVO, PASIVO, CAPITAL, INGRESOS, COSTOS, GASTOS"),
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("accounting:read"))
):
    """Catálogo estructurado de cuentas contables de la empresa con Código Agrupador SAT."""
    return await accounting_service.get_accounts(db, tenant_id, account_type=account_type)


@router.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    data: AccountCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("accounting:read"))
):
    """Crea una nueva cuenta o subcuenta en el catálogo contable."""
    return await accounting_service.create_account(db, tenant_id, data)


# ==========================================
# PÓLIZAS CONTABLES DE PARTIDA DOBLE
# ==========================================
@router.get("/journal-entries", response_model=List[JournalEntryResponse])
async def list_journal_entries(
    entry_type: Optional[str] = Query(None, description="INGRESO, EGRESO, DIARIO"),
    source_module: Optional[str] = Query(None, description="SALES, PURCHASES, BANKING, PAYROLL, MANUAL"),
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("accounting:read"))
):
    """Listado histórico de pólizas contables registradas y aplicadas."""
    entries = await accounting_service.get_journal_entries(db, tenant_id, entry_type=entry_type, source_module=source_module)
    return [
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
        for e in entries
    ]


@router.post("/journal-entries", response_model=JournalEntryDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_journal_entry(
    data: JournalEntryCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("accounting:create_policy"))
):
    """
    Registra una póliza manual validando estrictamente que los Cargos cuadren con los Abonos.
    Rechaza pólizas con descuadre.
    """
    entry = await accounting_service.create_journal_entry(
        db=db,
        tenant_id=tenant_id,
        data=data,
        source_module="MANUAL",
        user_id=current_user.id
    )
    return JournalEntryDetailResponse(
        id=entry.id,
        folio=entry.folio,
        entry_type=entry.entry_type,
        entry_date=entry.entry_date,
        concept=entry.concept,
        total_debit=entry.total_debit,
        total_credit=entry.total_credit,
        status=entry.status,
        source_module=entry.source_module,
        source_folio=entry.source_folio,
        created_at=entry.created_at,
        line_count=len(entry.lines),
        lines=[
            JournalEntryLineResponse(
                id=l.id,
                journal_entry_id=l.journal_entry_id,
                account_id=l.account_id,
                account_number=l.account.account_number if l.account else None,
                account_name=l.account.name if l.account else None,
                line_number=l.line_number,
                concept=l.concept,
                debit=l.debit,
                credit=l.credit,
                cfdi_uuid=l.cfdi_uuid
            )
            for l in entry.lines
        ]
    )


@router.get("/journal-entries/{entry_id}", response_model=JournalEntryDetailResponse)
async def get_journal_entry(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("accounting:read"))
):
    """Detalle completo de una póliza contable con todas sus partidas y UUID CFDI."""
    entry = await accounting_service.get_journal_entry_by_id(db, tenant_id, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Póliza contable no encontrada.")
    return JournalEntryDetailResponse(
        id=entry.id,
        folio=entry.folio,
        entry_type=entry.entry_type,
        entry_date=entry.entry_date,
        concept=entry.concept,
        total_debit=entry.total_debit,
        total_credit=entry.total_credit,
        status=entry.status,
        source_module=entry.source_module,
        source_folio=entry.source_folio,
        created_at=entry.created_at,
        line_count=len(entry.lines),
        lines=[
            JournalEntryLineResponse(
                id=l.id,
                journal_entry_id=l.journal_entry_id,
                account_id=l.account_id,
                account_number=l.account.account_number if l.account else None,
                account_name=l.account.name if l.account else None,
                line_number=l.line_number,
                concept=l.concept,
                debit=l.debit,
                credit=l.credit,
                cfdi_uuid=l.cfdi_uuid
            )
            for l in entry.lines
        ]
    )


# ==========================================
# ESTADOS FINANCIEROS Y REPORTING
# ==========================================
@router.get("/reports/trial-balance", response_model=TrialBalanceReport)
async def get_trial_balance_report(
    start_date: date = Query(default_factory=lambda: date(date.today().year, 1, 1)),
    end_date: date = Query(default_factory=date.today),
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("accounting:financial_reports"))
):
    """Balanza de Comprobación oficial para Contabilidad Electrónica del SAT."""
    return await accounting_service.get_trial_balance(db, tenant_id, start_date=start_date, end_date=end_date)


@router.get("/reports/income-statement", response_model=IncomeStatementReport)
async def get_income_statement_report(
    start_date: date = Query(default_factory=lambda: date(date.today().year, date.today().month, 1)),
    end_date: date = Query(default_factory=date.today),
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("accounting:financial_reports"))
):
    """Estado de Resultados (P&L): Ventas, Costos, Utilidad Bruta, Gastos y Utilidad Neta."""
    return await accounting_service.get_income_statement(db, tenant_id, start_date=start_date, end_date=end_date)


@router.get("/reports/balance-sheet", response_model=BalanceSheetReport)
async def get_balance_sheet_report(
    as_of_date: date = Query(default_factory=date.today),
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("accounting:financial_reports"))
):
    """Balance General (Estado de Situación Financiera): Activo = Pasivo + Capital."""
    return await accounting_service.get_balance_sheet(db, tenant_id, as_of_date=as_of_date)

