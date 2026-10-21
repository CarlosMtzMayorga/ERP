import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_tenant, require_permission
from app.modules.auth.models import User
from app.modules.tenants.models import Tenant, Branch
from app.modules.master_data.models import Warehouse, Product, Customer
from app.modules.pos.models import CashRegister, CashSession, CashMovement, POSTicket, POSTicketItem
from app.modules.pos.pos_service import (
    open_cash_session,
    record_cash_movement,
    get_corte_x,
    close_corte_z,
    create_pos_ticket
)
from app.modules.pos.global_invoice_service import generate_global_invoice

router = APIRouter(prefix="/pos", tags=["Módulo 4: Punto de Venta (POS) & Facturación Global"])


# --- Schemas ---

class CashRegisterCreateRequest(BaseModel):
    branch_id: uuid.UUID
    warehouse_id: uuid.UUID
    code: str = Field(..., max_length=20, example="CAJA-01")
    name: str = Field(..., max_length=100, example="Caja Principal Mostrador")


class CashRegisterResponse(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    warehouse_id: uuid.UUID
    code: str
    name: str
    is_active: bool
    branch_name: Optional[str] = None
    warehouse_name: Optional[str] = None
    active_session_id: Optional[uuid.UUID] = None

    class Config:
        from_attributes = True


class OpenSessionRequest(BaseModel):
    cash_register_id: uuid.UUID
    initial_cash: Decimal = Field(..., ge=0, example="1000.00")
    notes: Optional[str] = None


class CashMovementRequest(BaseModel):
    movement_type: str = Field(..., description="ENTRY o WITHDRAWAL")
    amount: Decimal = Field(..., gt=0)
    reason: str = Field(..., min_length=3, max_length=255)


class CorteZRequest(BaseModel):
    declared_cash: Decimal = Field(..., ge=0)
    declared_card: Decimal = Field(Decimal("0.00"), ge=0)
    notes: Optional[str] = None


class TicketItemInput(BaseModel):
    product_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., gt=0)
    description: Optional[str] = None


class TicketCreateRequest(BaseModel):
    session_id: uuid.UUID
    items: List[TicketItemInput]
    payment_method: str = Field("EFECTIVO", description="EFECTIVO, TARJETA, TRANSFERENCIA, MIXTO")
    amount_paid: Decimal = Field(Decimal("0.00"), ge=0)
    amount_cash: Optional[Decimal] = None
    amount_card: Optional[Decimal] = None
    amount_transfer: Optional[Decimal] = None
    customer_id: Optional[uuid.UUID] = None


class GlobalInvoiceRequest(BaseModel):
    branch_id: uuid.UUID
    periodicity: str = Field("01", description="01=Diaria, 02=Semanal, 04=Mensual")
    months: Optional[str] = None
    year: Optional[int] = None
    ticket_ids: Optional[List[uuid.UUID]] = None


# --- Endpoints: Cajas Registradoras ---

@router.get("/products")
async def list_pos_products(
    q: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user)
):
    """
    Catálogo de artículos optimizado para POS y lector de código de barras.
    """
    query = (
        select(Product)
        .where(Product.tenant_id == tenant.id, Product.is_active == True)
        .order_by(Product.name.asc())
        .limit(limit)
    )
    if q:
        search_pattern = f"%{q}%"
        query = query.where(
            (Product.name.ilike(search_pattern)) |
            (Product.sku.ilike(search_pattern)) |
            (Product.barcode == q)
        )

    res = await db.execute(query)
    prods = res.scalars().all()

    return [
        {
            "id": p.id,
            "sku": p.sku,
            "barcode": p.barcode or p.sku,
            "name": p.name,
            "product_type": p.product_type,
            "unit_name": p.unit_name,
            "base_price": p.base_price,
            "vat_rate": p.vat_rate,
            "average_cost": p.average_cost
        }
        for p in prods
    ]


@router.get("/registers", response_model=List[CashRegisterResponse])
async def list_cash_registers(
    branch_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user)
):
    """Lista las cajas registradoras del tenant con su estado y turno activo."""
    query = (
        select(CashRegister)
        .options(
            selectinload(CashRegister.branch),
            selectinload(CashRegister.warehouse),
            selectinload(CashRegister.sessions)
        )
        .where(CashRegister.tenant_id == tenant.id)
    )
    if branch_id:
        query = query.where(CashRegister.branch_id == branch_id)

    res = await db.execute(query)
    registers = res.scalars().all()

    result = []
    for r in registers:
        # Encontrar sesión abierta activa
        active_sess = next((s for s in r.sessions if s.status == "OPEN"), None)
        result.append(CashRegisterResponse(
            id=r.id,
            branch_id=r.branch_id,
            warehouse_id=r.warehouse_id,
            code=r.code,
            name=r.name,
            is_active=r.is_active,
            branch_name=r.branch.name if r.branch else None,
            warehouse_name=r.warehouse.name if r.warehouse else None,
            active_session_id=active_sess.id if active_sess else None
        ))
    return result


@router.post("/registers", response_model=CashRegisterResponse, status_code=status.HTTP_201_CREATED)
async def create_cash_register(
    req: CashRegisterCreateRequest,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user)
):
    """Registra una nueva caja registradora o terminal de cobro."""
    # Verificar unicidad de código
    existing = await db.execute(
        select(CashRegister).where(CashRegister.tenant_id == tenant.id, CashRegister.code == req.code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"El código de caja '{req.code}' ya existe.")

    register = CashRegister(
        tenant_id=tenant.id,
        branch_id=req.branch_id,
        warehouse_id=req.warehouse_id,
        code=req.code.upper(),
        name=req.name,
        is_active=True
    )
    db.add(register)
    await db.commit()
    await db.refresh(register)

    return CashRegisterResponse(
        id=register.id,
        branch_id=register.branch_id,
        warehouse_id=register.warehouse_id,
        code=register.code,
        name=register.name,
        is_active=register.is_active,
        branch_name=None,
        warehouse_name=None,
        active_session_id=None
    )


# --- Endpoints: Sesiones y Cortes de Caja ---

@router.post("/sessions/open")
async def open_session_endpoint(
    req: OpenSessionRequest,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user)
):
    """
    Abre un nuevo turno de caja registrando el fondo inicial de efectivo.
    """
    session = await open_cash_session(
        db=db,
        tenant_id=tenant.id,
        cash_register_id=req.cash_register_id,
        user_id=user.id,
        initial_cash=req.initial_cash,
        notes=req.notes
    )
    await db.commit()
    return {
        "message": "Turno de caja abierto correctamente.",
        "session_id": session.id,
        "status": session.status,
        "initial_cash": session.initial_cash,
        "opened_at": session.opened_at
    }


@router.get("/sessions/active")
async def get_active_session_endpoint(
    cash_register_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user)
):
    """
    Consulta la sesión abierta activa para una caja específica.
    """
    res = await db.execute(
        select(CashSession)
        .options(
            selectinload(CashSession.cash_register),
            selectinload(CashSession.user)
        )
        .where(
            CashSession.tenant_id == tenant.id,
            CashSession.cash_register_id == cash_register_id,
            CashSession.status == "OPEN"
        )
    )
    session = res.scalar_one_or_none()
    if not session:
        return {"has_active_session": False, "session": None}

    return {
        "has_active_session": True,
        "session": {
            "id": session.id,
            "cash_register_id": session.cash_register_id,
            "cash_register_name": session.cash_register.name if session.cash_register else None,
            "cashier_name": session.user.full_name if session.user else None,
            "status": session.status,
            "opened_at": session.opened_at,
            "initial_cash": session.initial_cash,
            "expected_cash": session.expected_cash,
            "total_sales": session.total_sales,
            "tickets_count": session.tickets_count
        }
    }


@router.post("/sessions/{session_id}/movement")
async def cash_movement_endpoint(
    session_id: uuid.UUID,
    req: CashMovementRequest,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user)
):
    """
    Registra entrada o retiro de efectivo en la caja.
    """
    mov = await record_cash_movement(
        db=db,
        tenant_id=tenant.id,
        session_id=session_id,
        user_id=user.id,
        movement_type=req.movement_type,
        amount=req.amount,
        reason=req.reason
    )
    await db.commit()
    return {
        "message": f"Movimiento de efectivo ({mov.movement_type}) registrado.",
        "movement_id": mov.id,
        "amount": mov.amount,
        "reason": mov.reason
    }


@router.get("/sessions/{session_id}/corte-x")
async def corte_x_endpoint(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user)
):
    """
    Corte X (Lectura Parcial): Audita ingresos por método de pago y efectivo esperado sin cerrar el turno.
    """
    data = await get_corte_x(db, tenant.id, session_id)
    return data


@router.post("/sessions/{session_id}/corte-z")
async def corte_z_endpoint(
    session_id: uuid.UUID,
    req: CorteZRequest,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user)
):
    """
    Corte Z (Cierre Definitivo):
    El cajero declara su conteo físico a ciegas y el sistema audita sobrantes/faltantes.
    """
    closed_session = await close_corte_z(
        db=db,
        tenant_id=tenant.id,
        session_id=session_id,
        user_id=user.id,
        declared_cash=req.declared_cash,
        declared_card=req.declared_card,
        notes=req.notes
    )
    await db.commit()
    return {
        "message": "Corte Z completado exitosamente. Turno cerrado.",
        "session_id": closed_session.id,
        "status": closed_session.status,
        "expected_cash": closed_session.expected_cash,
        "declared_cash": closed_session.declared_cash,
        "difference_cash": closed_session.difference_cash,
        "expected_card": closed_session.expected_card,
        "declared_card": closed_session.declared_card,
        "difference_card": closed_session.difference_card,
        "total_sales": closed_session.total_sales,
        "tickets_count": closed_session.tickets_count,
        "closed_at": closed_session.closed_at
    }


# --- Endpoints: Tickets de Venta ---

@router.post("/tickets", status_code=status.HTTP_201_CREATED)
async def create_ticket_endpoint(
    req: TicketCreateRequest,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user)
):
    """
    Genera un ticket de venta en POS con descarga inmediata de inventario Kardex y cálculo de cambio.
    """
    items_raw = [
        {
            "product_id": it.product_id,
            "quantity": it.quantity,
            "unit_price": it.unit_price,
            "description": it.description
        }
        for it in req.items
    ]

    ticket = await create_pos_ticket(
        db=db,
        tenant_id=tenant.id,
        session_id=req.session_id,
        items_input=items_raw,
        payment_method=req.payment_method,
        amount_paid=req.amount_paid,
        amount_cash=req.amount_cash,
        amount_card=req.amount_card,
        amount_transfer=req.amount_transfer,
        customer_id=req.customer_id,
        user_id=user.id
    )
    await db.commit()

    return {
        "id": ticket.id,
        "folio": ticket.formatted_folio,
        "serie": ticket.serie,
        "folio_number": ticket.folio,
        "status": ticket.status,
        "subtotal": ticket.subtotal,
        "tax_iva_total": ticket.tax_iva_total,
        "total": ticket.total,
        "payment_method": ticket.payment_method,
        "amount_paid": ticket.amount_paid,
        "change_returned": ticket.change_returned,
        "created_at": ticket.created_at
    }


@router.get("/tickets")
async def list_tickets_endpoint(
    session_id: Optional[uuid.UUID] = None,
    is_globally_invoiced: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user)
):
    """
    Lista los tickets de venta emitidos para la sesión o tenant.
    """
    query = (
        select(POSTicket)
        .options(
            selectinload(POSTicket.customer),
            selectinload(POSTicket.cash_register)
        )
        .where(POSTicket.tenant_id == tenant.id)
        .order_by(POSTicket.created_at.desc())
        .limit(limit)
    )
    if session_id:
        query = query.where(POSTicket.cash_session_id == session_id)
    if is_globally_invoiced is not None:
        query = query.where(POSTicket.is_globally_invoiced == is_globally_invoiced)

    res = await db.execute(query)
    tickets = res.scalars().all()

    return [
        {
            "id": t.id,
            "folio": t.formatted_folio,
            "total": t.total,
            "subtotal": t.subtotal,
            "tax_iva_total": t.tax_iva_total,
            "payment_method": t.payment_method,
            "amount_paid": t.amount_paid,
            "change_returned": t.change_returned,
            "status": t.status,
            "is_globally_invoiced": t.is_globally_invoiced,
            "cash_register_name": t.cash_register.name if t.cash_register else None,
            "customer_name": t.customer.legal_name if t.customer else "Público en General",
            "created_at": t.created_at
        }
        for t in tickets
    ]


@router.get("/tickets/{ticket_id}")
async def get_ticket_detail_endpoint(
    ticket_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user)
):
    """
    Obtiene el detalle completo de un ticket con sus partidas descargadas.
    """
    res = await db.execute(
        select(POSTicket)
        .options(
            selectinload(POSTicket.items),
            selectinload(POSTicket.customer),
            selectinload(POSTicket.cash_register),
            selectinload(POSTicket.user)
        )
        .where(POSTicket.id == ticket_id, POSTicket.tenant_id == tenant.id)
    )
    ticket = res.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado.")

    return {
        "id": ticket.id,
        "folio": ticket.formatted_folio,
        "serie": ticket.serie,
        "folio_number": ticket.folio,
        "created_at": ticket.created_at,
        "cash_register": ticket.cash_register.name if ticket.cash_register else None,
        "cashier": ticket.user.full_name if ticket.user else None,
        "customer": ticket.customer.legal_name if ticket.customer else "Público en General",
        "payment_method": ticket.payment_method,
        "amount_paid": ticket.amount_paid,
        "change_returned": ticket.change_returned,
        "subtotal": ticket.subtotal,
        "tax_iva_total": ticket.tax_iva_total,
        "total": ticket.total,
        "total_cost_cogs": ticket.total_cost_cogs,
        "is_globally_invoiced": ticket.is_globally_invoiced,
        "items": [
            {
                "id": it.id,
                "sku": it.sku,
                "description": it.description,
                "quantity": it.quantity,
                "unit_price": it.unit_price,
                "subtotal": it.subtotal,
                "vat_amount": it.vat_amount,
                "total": it.total,
                "unit_cost": it.unit_cost,
                "total_cost": it.total_cost
            }
            for it in ticket.items
        ]
    }


# --- Endpoints: Facturación Global CFDI 4.0 ---

@router.get("/global-invoice/pending-tickets")
async def list_pending_global_tickets(
    branch_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user)
):
    """
    Lista todos los tickets de venta no facturados aún, listos para incluirse en el CFDI Global.
    """
    query = (
        select(POSTicket)
        .where(
            POSTicket.tenant_id == tenant.id,
            POSTicket.status == "PAID",
            POSTicket.is_globally_invoiced == False
        )
        .order_by(POSTicket.created_at.asc())
    )
    if branch_id:
        query = query.where(POSTicket.branch_id == branch_id)

    res = await db.execute(query)
    tickets = res.scalars().all()

    total_gross = sum(t.total for t in tickets)
    return {
        "pending_count": len(tickets),
        "total_amount": total_gross,
        "tickets": [
            {
                "id": t.id,
                "folio": t.formatted_folio,
                "total": t.total,
                "payment_method": t.payment_method,
                "created_at": t.created_at
            }
            for t in tickets
        ]
    }


@router.post("/global-invoice/generate", status_code=status.HTTP_201_CREATED)
async def generate_global_invoice_endpoint(
    req: GlobalInvoiceRequest,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user)
):
    """
    Genera y timbra la Factura Global CFDI 4.0 con el nodo obligatorio InformacionGlobal.
    """
    global_inv = await generate_global_invoice(
        db=db,
        tenant_id=tenant.id,
        branch_id=req.branch_id,
        periodicity=req.periodicity,
        months=req.months,
        year=req.year,
        ticket_ids=req.ticket_ids
    )
    await db.commit()

    return {
        "message": "Factura Global CFDI 4.0 generada y timbrada exitosamente.",
        "document_id": global_inv.id,
        "folio": global_inv.formatted_folio,
        "uuid": global_inv.cfdi_uuid,
        "stamped_at": global_inv.cfdi_stamped_at,
        "total": global_inv.total,
        "subtotal": global_inv.subtotal,
        "tax_iva_total": global_inv.tax_iva_total,
        "status": global_inv.status
    }
