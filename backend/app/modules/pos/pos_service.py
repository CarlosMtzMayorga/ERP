import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.pos.models import (
    CashRegister,
    CashSession,
    CashMovement,
    POSTicket,
    POSTicketItem
)
from app.modules.tenants.models import Tenant, Branch
from app.modules.master_data.models import Customer, Product
from app.modules.tenants.folios_service import consume_next_folio
from app.modules.inventories.inventory_service import record_exit
from app.modules.fiscal_mexico.tax_engine import quantize_2


async def open_cash_session(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    cash_register_id: uuid.UUID,
    user_id: uuid.UUID,
    initial_cash: Decimal,
    notes: Optional[str] = None
) -> CashSession:
    """
    Abre un nuevo turno de caja declarando el fondo inicial.
    Impide abrir si la caja ya cuenta con un turno activo.
    """
    if initial_cash < Decimal("0.0000"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El fondo de apertura no puede ser negativo.")

    # Verificar caja
    reg_res = await db.execute(
        select(CashRegister).where(CashRegister.id == cash_register_id, CashRegister.tenant_id == tenant_id)
    )
    register = reg_res.scalar_one_or_none()
    if not register or not register.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Caja registradora no encontrada o inactiva.")

    # Verificar turno activo previo
    active_res = await db.execute(
        select(CashSession).where(
            CashSession.cash_register_id == cash_register_id,
            CashSession.status == "OPEN"
        )
    )
    if active_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La caja ya cuenta con un turno abierto. Debe realizar el Corte Z antes de iniciar uno nuevo."
        )

    session = CashSession(
        tenant_id=tenant_id,
        cash_register_id=cash_register_id,
        user_id=user_id,
        status="OPEN",
        opened_at=datetime.now(timezone.utc),
        initial_cash=initial_cash,
        expected_cash=initial_cash,
        expected_card=Decimal("0.0000"),
        total_sales=Decimal("0.0000"),
        tickets_count=0,
        notes=notes
    )
    db.add(session)
    await db.flush()
    return session


async def record_cash_movement(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    movement_type: str,  # ENTRY, WITHDRAWAL
    amount: Decimal,
    reason: str
) -> CashMovement:
    """
    Registra entrada de cambio o retiro de efectivo durante el turno.
    """
    if amount <= Decimal("0.0000"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El monto debe ser mayor a cero.")

    session_res = await db.execute(
        select(CashSession).where(CashSession.id == session_id, CashSession.tenant_id == tenant_id).with_for_update()
    )
    session = session_res.scalar_one_or_none()
    if not session or session.status != "OPEN":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El turno de caja no está abierto.")

    mov_type_clean = movement_type.upper()
    if mov_type_clean == "WITHDRAWAL" and session.expected_cash < amount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Efectivo en caja insuficiente para el retiro.")

    movement = CashMovement(
        tenant_id=tenant_id,
        cash_session_id=session.id,
        user_id=user_id,
        movement_type=mov_type_clean,
        amount=amount,
        reason=reason
    )
    db.add(movement)

    # Actualizar esperado
    if mov_type_clean == "ENTRY":
        session.expected_cash += amount
    else:
        session.expected_cash -= amount

    await db.flush()
    return movement


async def get_corte_x(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID
) -> Dict[str, Any]:
    """
    Corte X (Lectura Parcial):
    Audita las ventas por método de pago, ingresos/retiros y efectivo esperado sin cerrar el turno.
    """
    session_res = await db.execute(
        select(CashSession)
        .options(
            selectinload(CashSession.cash_register),
            selectinload(CashSession.user)
        )
        .where(CashSession.id == session_id, CashSession.tenant_id == tenant_id)
    )
    session = session_res.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turno de caja no encontrado.")

    # Ventas desglosadas
    sales_res = await db.execute(
        select(
            func.coalesce(func.sum(POSTicket.amount_cash), Decimal("0.0000")),
            func.coalesce(func.sum(POSTicket.amount_card), Decimal("0.0000")),
            func.coalesce(func.sum(POSTicket.amount_transfer), Decimal("0.0000")),
            func.coalesce(func.sum(POSTicket.total), Decimal("0.0000")),
            func.count(POSTicket.id)
        ).where(
            POSTicket.cash_session_id == session.id,
            POSTicket.status == "PAID"
        )
    )
    cash_sales, card_sales, trans_sales, total_sales, tickets_count = sales_res.one()

    # Movimientos de efectivo (Entradas y Retiros)
    mov_res = await db.execute(
        select(
            CashMovement.movement_type,
            func.sum(CashMovement.amount)
        ).where(CashMovement.cash_session_id == session.id).group_by(CashMovement.movement_type)
    )
    mov_map = dict(mov_res.all())
    cash_in = mov_map.get("ENTRY", Decimal("0.0000"))
    cash_out = mov_map.get("WITHDRAWAL", Decimal("0.0000"))

    expected_cash = session.initial_cash + cash_sales + cash_in - cash_out
    expected_card = card_sales

    return {
        "session_id": session.id,
        "cash_register_name": session.cash_register.name if session.cash_register else "Caja",
        "cashier_name": session.user.full_name if session.user else "Cajero",
        "opened_at": session.opened_at,
        "initial_cash": session.initial_cash,
        "cash_sales": cash_sales,
        "card_sales": card_sales,
        "transfer_sales": trans_sales,
        "total_sales": total_sales,
        "tickets_count": tickets_count,
        "cash_entries": cash_in,
        "cash_withdrawals": cash_out,
        "expected_cash": expected_cash,
        "expected_card": expected_card
    }


async def close_corte_z(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    declared_cash: Decimal,
    declared_card: Decimal,
    notes: Optional[str] = None
) -> CashSession:
    """
    Corte Z (Cierre Definitivo):
    El cajero declara su conteo físico a ciegas (Blind Checkout).
    El sistema calcula y almacena obligatoriamente cualquier Sobrante (+) o Faltante (-).
    """
    session_res = await db.execute(
        select(CashSession).where(CashSession.id == session_id, CashSession.tenant_id == tenant_id).with_for_update()
    )
    session = session_res.scalar_one_or_none()
    if not session or session.status != "OPEN":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El turno ya está cerrado o no es válido.")

    # Obtener valores esperados
    corte_data = await get_corte_x(db, tenant_id, session.id)

    expected_cash = corte_data["expected_cash"]
    expected_card = corte_data["expected_card"]

    diff_cash = declared_cash - expected_cash
    diff_card = declared_card - expected_card

    session.status = "CLOSED"
    session.closed_at = datetime.now(timezone.utc)
    session.expected_cash = expected_cash
    session.declared_cash = declared_cash
    session.difference_cash = diff_cash
    session.expected_card = expected_card
    session.declared_card = declared_card
    session.difference_card = diff_card
    session.total_sales = corte_data["total_sales"]
    session.tickets_count = corte_data["tickets_count"]
    if notes:
        session.notes = f"{session.notes or ''}\n[Corte Z]: {notes}".strip()

    await db.flush()
    return session


async def create_pos_ticket(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    items_input: List[Dict[str, Any]],
    payment_method: str = "EFECTIVO",
    amount_paid: Decimal = Decimal("0.0000"),
    amount_cash: Optional[Decimal] = None,
    amount_card: Optional[Decimal] = None,
    amount_transfer: Optional[Decimal] = None,
    customer_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None
) -> POSTicket:
    """
    Genera un Ticket de Venta en Punto de Venta.
    1. Valida que el turno de caja esté ABIERTO (Regla crítica de negocio).
    2. Consume folio consecutivo atómico (TICK o POS).
    3. Descarga inmediatamente el inventario en Kardex (KardexMovement SALIDA_VENTA).
    4. Evalúa costo de venta (PEPS / Promedio).
    5. Actualiza efectivo esperado y métricas de la caja.
    """
    # 1. VALIDACIÓN CRÍTICA: Caja abierta
    session_res = await db.execute(
        select(CashSession)
        .options(selectinload(CashSession.cash_register))
        .where(CashSession.id == session_id, CashSession.tenant_id == tenant_id)
        .with_for_update()
    )
    session = session_res.scalar_one_or_none()
    if not session or session.status != "OPEN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pueden emitir tickets: La caja registradora está cerrada o no cuenta con turno abierto."
        )

    if not items_input:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El ticket debe incluir al menos un artículo.")

    register = session.cash_register

    # 2. Consumir Folio Atómico
    serie_code, folio_num, _ = await consume_next_folio(
        db=db,
        tenant_id=tenant_id,
        document_type="TICK",
        branch_id=register.branch_id
    )
    formatted_folio = f"{serie_code}-{folio_num}"

    # Si no se envía cliente, asignar o buscar cliente mostrador
    if not customer_id:
        cust_res = await db.execute(
            select(Customer).where(Customer.tenant_id == tenant_id).limit(1)
        )
        customer = cust_res.scalar_one_or_none()
        if customer:
            customer_id = customer.id
        else:
            # Crear cliente mostrador
            customer = Customer(
                tenant_id=tenant_id,
                code="PUBLICO",
                rfc="XAXX010101000",
                legal_name="PUBLICO EN GENERAL",
                fiscal_regime_code="616",
                zip_code="06000"
            )
            db.add(customer)
            await db.flush()
            customer_id = customer.id

    # 3. Procesar partidas, descargar inventario y calcular totales
    ticket_items = []
    subtotal_sum = Decimal("0.0000")
    vat_sum = Decimal("0.0000")
    total_cogs = Decimal("0.0000")

    for idx, it in enumerate(items_input, start=1):
        prod_res = await db.execute(
            select(Product).where(Product.id == it["product_id"], Product.tenant_id == tenant_id)
        )
        product = prod_res.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Artículo no encontrado.")

        qty = Decimal(str(it["quantity"]))
        gross_price = Decimal(str(it["unit_price"]))  # Precio público (con IVA incluido típicamente en POS)
        
        # Desglosar IVA 16% hacia atrás
        base_unit_price = quantize_2(gross_price / Decimal("1.16"))
        vat_unit = gross_price - base_unit_price
        
        line_subtotal = base_unit_price * qty
        line_vat = vat_unit * qty
        line_total = gross_price * qty

        # Descarga inmediata en Kardex
        if product.product_type == "PRODUCTO":
            mov, _, _ = await record_exit(
                db=db,
                tenant_id=tenant_id,
                warehouse_id=register.warehouse_id,
                product_id=product.id,
                quantity=qty,
                movement_type="SALIDA_VENTA",
                reference_type="TICKET_POS",
                reference_folio=formatted_folio,
                notes=f"Ticket {formatted_folio} en {register.name}",
                user_id=user_id or session.user_id
            )
            unit_cost = mov.unit_cost
            item_cogs = mov.total_cost
        else:
            unit_cost = Decimal("0.0000")
            item_cogs = Decimal("0.0000")

        total_cogs += item_cogs
        subtotal_sum += line_subtotal
        vat_sum += line_vat

        ticket_item = POSTicketItem(
            tenant_id=tenant_id,
            product_id=product.id,
            line_number=idx,
            sku=product.sku,
            description=it.get("description", product.name),
            quantity=qty,
            unit_price=gross_price,
            discount_amount=Decimal("0.0000"),
            subtotal=line_subtotal,
            vat_rate=Decimal("0.1600"),
            vat_amount=line_vat,
            total=line_total,
            unit_cost=unit_cost,
            total_cost=item_cogs
        )
        ticket_items.append(ticket_item)

    ticket_total = subtotal_sum + vat_sum

    # Determinar importes por método de pago
    pay_mode = payment_method.upper()
    cash_val = Decimal("0.0000")
    card_val = Decimal("0.0000")
    trans_val = Decimal("0.0000")
    change_val = Decimal("0.0000")

    if pay_mode == "EFECTIVO":
        cash_val = ticket_total
        if amount_paid > ticket_total:
            change_val = amount_paid - ticket_total
        else:
            amount_paid = ticket_total
    elif pay_mode == "TARJETA":
        card_val = ticket_total
        amount_paid = ticket_total
    elif pay_mode == "TRANSFERENCIA":
        trans_val = ticket_total
        amount_paid = ticket_total
    elif pay_mode == "MIXTO":
        cash_val = Decimal(str(amount_cash or 0))
        card_val = Decimal(str(amount_card or 0))
        trans_val = Decimal(str(amount_transfer or 0))
        change_val = max(Decimal("0.0000"), (amount_paid or cash_val) - cash_val)

    ticket = POSTicket(
        tenant_id=tenant_id,
        cash_session_id=session.id,
        cash_register_id=register.id,
        branch_id=register.branch_id,
        warehouse_id=register.warehouse_id,
        customer_id=customer_id,
        user_id=user_id or session.user_id,
        serie=serie_code,
        folio=folio_num,
        formatted_folio=formatted_folio,
        status="PAID",
        subtotal=subtotal_sum,
        discount_total=Decimal("0.0000"),
        tax_iva_total=vat_sum,
        total=ticket_total,
        total_cost_cogs=total_cogs,
        payment_method=pay_mode,
        amount_cash=cash_val,
        amount_card=card_val,
        amount_transfer=trans_val,
        amount_paid=amount_paid,
        change_returned=change_val,
        is_globally_invoiced=False
    )

    for item in ticket_items:
        ticket.items.append(item)

    # Actualizar sesión de caja
    session.expected_cash += cash_val
    session.expected_card += card_val
    session.total_sales += ticket_total
    session.tickets_count += 1

    db.add(ticket)
    await db.flush()
    return ticket
