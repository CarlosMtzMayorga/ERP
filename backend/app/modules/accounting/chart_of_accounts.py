import uuid
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounting.models import Account


DEFAULT_CHART_OF_ACCOUNTS: List[Dict[str, Any]] = [
    # ==========================================
    # 1. ACTIVO (1000)
    # ==========================================
    {"number": "1000", "name": "ACTIVO", "nature": "DEUDORA", "type": "ACTIVO", "level": 1, "is_group": True, "sat": "100", "parent": None},
    
    # 1100 - Activo Circulante
    {"number": "1100", "name": "Activo Circulante", "nature": "DEUDORA", "type": "ACTIVO", "level": 2, "is_group": True, "sat": "100.01", "parent": "1000"},
    {"number": "1101", "name": "Caja y Efectivo", "nature": "DEUDORA", "type": "ACTIVO", "level": 3, "is_group": False, "sat": "101.01", "parent": "1100"},
    {"number": "1102", "name": "Bancos Nacionales", "nature": "DEUDORA", "type": "ACTIVO", "level": 3, "is_group": False, "sat": "102.01", "parent": "1100"},
    {"number": "1105", "name": "Clientes Nacionales", "nature": "DEUDORA", "type": "ACTIVO", "level": 3, "is_group": False, "sat": "105.01", "parent": "1100"},
    {"number": "1115", "name": "Inventario de Mercancías", "nature": "DEUDORA", "type": "ACTIVO", "level": 3, "is_group": False, "sat": "115.01", "parent": "1100"},
    {"number": "1118", "name": "IVA Acreditable Pagado", "nature": "DEUDORA", "type": "ACTIVO", "level": 3, "is_group": False, "sat": "118.01", "parent": "1100"},
    {"number": "1119", "name": "IVA Acreditable Pendiente de Pago", "nature": "DEUDORA", "type": "ACTIVO", "level": 3, "is_group": False, "sat": "119.01", "parent": "1100"},

    # 1200 - Activo No Circulante (Fijo)
    {"number": "1200", "name": "Activo No Circulante (Fijo)", "nature": "DEUDORA", "type": "ACTIVO", "level": 2, "is_group": True, "sat": "150", "parent": "1000"},
    {"number": "1201", "name": "Mobiliario y Equipo de Oficina", "nature": "DEUDORA", "type": "ACTIVO", "level": 3, "is_group": False, "sat": "151.01", "parent": "1200"},
    {"number": "1202", "name": "Equipo de Cómputo", "nature": "DEUDORA", "type": "ACTIVO", "level": 3, "is_group": False, "sat": "153.01", "parent": "1200"},

    # ==========================================
    # 2. PASIVO (2000)
    # ==========================================
    {"number": "2000", "name": "PASIVO", "nature": "ACREEDORA", "type": "PASIVO", "level": 1, "is_group": True, "sat": "200", "parent": None},
    
    # 2100 - Pasivo a Corto Plazo
    {"number": "2100", "name": "Pasivo a Corto Plazo", "nature": "ACREEDORA", "type": "PASIVO", "level": 2, "is_group": True, "sat": "200.01", "parent": "2000"},
    {"number": "2101", "name": "Proveedores Nacionales", "nature": "ACREEDORA", "type": "PASIVO", "level": 3, "is_group": False, "sat": "201.01", "parent": "2100"},
    {"number": "2108", "name": "IVA Trasladado Cobrado", "nature": "ACREEDORA", "type": "PASIVO", "level": 3, "is_group": False, "sat": "208.01", "parent": "2100"},
    {"number": "2109", "name": "IVA Trasladado No Cobrado (Pendiente)", "nature": "ACREEDORA", "type": "PASIVO", "level": 3, "is_group": False, "sat": "209.01", "parent": "2100"},
    {"number": "2111", "name": "Cuotas IMSS e Infonavit por Pagar", "nature": "ACREEDORA", "type": "PASIVO", "level": 3, "is_group": False, "sat": "211.01", "parent": "2100"},
    {"number": "2116", "name": "Retenciones de ISR por Sueldos y Salarios", "nature": "ACREEDORA", "type": "PASIVO", "level": 3, "is_group": False, "sat": "216.01", "parent": "2100"},
    {"number": "2117", "name": "Retenciones de IVA por Pagar", "nature": "ACREEDORA", "type": "PASIVO", "level": 3, "is_group": False, "sat": "216.03", "parent": "2100"},
    {"number": "2118", "name": "Retenciones de ISR por Servicios/Fletes", "nature": "ACREEDORA", "type": "PASIVO", "level": 3, "is_group": False, "sat": "216.04", "parent": "2100"},

    # 2200 - Pasivo a Largo Plazo
    {"number": "2200", "name": "Pasivo a Largo Plazo", "nature": "ACREEDORA", "type": "PASIVO", "level": 2, "is_group": True, "sat": "250", "parent": "2000"},
    {"number": "2201", "name": "Acreedores Bancarios a Largo Plazo", "nature": "ACREEDORA", "type": "PASIVO", "level": 3, "is_group": False, "sat": "251.01", "parent": "2200"},

    # ==========================================
    # 3. CAPITAL CONTABLE (3000)
    # ==========================================
    {"number": "3000", "name": "CAPITAL CONTABLE", "nature": "ACREEDORA", "type": "CAPITAL", "level": 1, "is_group": True, "sat": "300", "parent": None},
    {"number": "3101", "name": "Capital Social Fijo", "nature": "ACREEDORA", "type": "CAPITAL", "level": 2, "is_group": False, "sat": "301.01", "parent": "3000"},
    {"number": "3201", "name": "Utilidades Acumuladas de Ejercicios Anteriores", "nature": "ACREEDORA", "type": "CAPITAL", "level": 2, "is_group": False, "sat": "304.01", "parent": "3000"},
    {"number": "3301", "name": "Utilidad o Pérdida del Ejercicio", "nature": "ACREEDORA", "type": "CAPITAL", "level": 2, "is_group": False, "sat": "305.01", "parent": "3000"},

    # ==========================================
    # 4. INGRESOS (4000)
    # ==========================================
    {"number": "4000", "name": "INGRESOS", "nature": "ACREEDORA", "type": "INGRESOS", "level": 1, "is_group": True, "sat": "400", "parent": None},
    {"number": "4101", "name": "Ventas y Servicios Gravados al 16%", "nature": "ACREEDORA", "type": "INGRESOS", "level": 2, "is_group": False, "sat": "401.01", "parent": "4000"},
    {"number": "4102", "name": "Ventas Tasa 0% o Exentas", "nature": "ACREEDORA", "type": "INGRESOS", "level": 2, "is_group": False, "sat": "401.02", "parent": "4000"},

    # ==========================================
    # 5. COSTOS (5000)
    # ==========================================
    {"number": "5000", "name": "COSTOS", "nature": "DEUDORA", "type": "COSTOS", "level": 1, "is_group": True, "sat": "500", "parent": None},
    {"number": "5101", "name": "Costo de Ventas de Mercancías", "nature": "DEUDORA", "type": "COSTOS", "level": 2, "is_group": False, "sat": "501.01", "parent": "5000"},

    # ==========================================
    # 6. GASTOS DE OPERACIÓN (6000)
    # ==========================================
    {"number": "6000", "name": "GASTOS DE OPERACIÓN", "nature": "DEUDORA", "type": "GASTOS", "level": 1, "is_group": True, "sat": "600", "parent": None},
    {"number": "6101", "name": "Sueldos, Salarios y Prestaciones de Administración", "nature": "DEUDORA", "type": "GASTOS", "level": 2, "is_group": False, "sat": "601.01", "parent": "6000"},
    {"number": "6102", "name": "Cuotas Patronales IMSS e Infonavit", "nature": "DEUDORA", "type": "GASTOS", "level": 2, "is_group": False, "sat": "601.03", "parent": "6000"},
    {"number": "6103", "name": "Arrendamiento de Oficinas", "nature": "DEUDORA", "type": "GASTOS", "level": 2, "is_group": False, "sat": "601.05", "parent": "6000"},
    {"number": "6104", "name": "Servicios Generales y Operativos", "nature": "DEUDORA", "type": "GASTOS", "level": 2, "is_group": False, "sat": "601.84", "parent": "6000"},
    {"number": "6201", "name": "Gastos de Venta y Comisiones Mercantiles", "nature": "DEUDORA", "type": "GASTOS", "level": 2, "is_group": False, "sat": "602.01", "parent": "6000"},
]


async def seed_default_chart_of_accounts(db: AsyncSession, tenant_id: uuid.UUID) -> Dict[str, Account]:
    """
    Siembra el Catálogo de Cuentas estándar mexicano (Anexo 24 SAT) para una empresa.
    Retorna un diccionario {account_number: Account} para resolución rápida de pólizas.
    """
    stmt = select(Account).where(Account.tenant_id == tenant_id)
    res = await db.execute(stmt)
    existing = {acc.account_number: acc for acc in res.scalars().all()}
    if existing:
        return existing

    # Crear cuentas respetando la jerarquía
    created_map: Dict[str, Account] = {}

    for item in DEFAULT_CHART_OF_ACCOUNTS:
        parent_obj = created_map.get(item["parent"]) if item["parent"] else None
        parent_id = parent_obj.id if parent_obj else None

        acc = Account(
            tenant_id=tenant_id,
            parent_id=parent_id,
            account_number=item["number"],
            name=item["name"],
            nature=item["nature"],
            account_type=item["type"],
            level=item["level"],
            is_group=item["is_group"],
            sat_group_code=item["sat"],
            initial_balance=Decimal("0.00"),
            current_balance=Decimal("0.00"),
            is_active=True
        )
        db.add(acc)
        await db.flush()  # Para obtener el ID que puedan referenciar subcuentas
        created_map[item["number"]] = acc

    await db.commit()
    return created_map
