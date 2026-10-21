import asyncio
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Import all models to register with Base.metadata
from app.core.config import settings
from app.core.database import Base
from app.core.security import get_password_hash
from app.modules.tenants.models import Tenant, Branch, FiscalFoliosSeries, CSDCertificate
from app.modules.auth.models import User, TenantUser, Role, Permission, UserRole, AuditLog
from app.modules.master_data.models import (
    Currency, Warehouse, ProductCategory, Product, PriceList, ProductPrice,
    Customer, CustomerAddress, Supplier, BankAccount
)

# Standard initial permissions across all 10 ERP modules
INITIAL_PERMISSIONS = [
    # Configurador
    ("config", "read", "config:read", "Ver configuraciones y catálogo de empresas"),
    ("config", "manage", "config:manage", "Administrar empresas, sucursales y certificados CSD"),
    ("users", "manage", "users:manage", "Crear y gestionar usuarios y permisos"),
    
    # Inventarios
    ("inventory", "read", "inventory:read", "Consultar existencias y almacenes"),
    ("inventory", "adjust", "inventory:adjust", "Realizar ajustes y traspasos de inventario"),
    ("inventory", "costing", "inventory:costing", "Ver y modificar costos y métodos (PEPS/Promedio)"),
    
    # Ventas
    ("sales", "read", "sales:read", "Consultar cotizaciones, pedidos y remisiones"),
    ("sales", "create", "sales:create", "Crear cotizaciones, pedidos y remisiones"),
    ("sales", "invoice", "sales:invoice", "Facturar y timbrar CFDI 4.0 de ventas"),
    ("sales", "cancel", "sales:cancel", "Cancelar facturas y documentos de venta"),

    # Punto de Venta (POS)
    ("pos", "operate", "pos:operate", "Operar terminal de punto de venta y cobro"),
    ("pos", "cash_cut", "pos:cash_cut", "Apertura, cierre de caja y corte X/Z"),
    ("pos", "global_invoice", "pos:global_invoice", "Generar factura global del día"),

    # Cuentas por Cobrar (CxC)
    ("cxc", "read", "cxc:read", "Consultar antigüedad de saldos y créditos"),
    ("cxc", "apply_payment", "cxc:apply_payment", "Aplicar cobranza y emitir complementos REP 2.0"),

    # Compras
    ("purchases", "read", "purchases:read", "Consultar órdenes de compra y requisiciones"),
    ("purchases", "create", "purchases:create", "Crear órdenes de compra y recibir mercancía"),
    ("purchases", "xml_import", "purchases:xml_import", "Importar y conciliar XML del SAT"),

    # Cuentas por Pagar (CxP)
    ("cxp", "read", "cxp:read", "Consultar facturas de proveedores y vencimientos"),
    ("cxp", "schedule_payment", "cxp:schedule_payment", "Programar y emitir pagos a proveedores"),

    # Bancos
    ("banking", "read", "banking:read", "Consultar saldos y movimientos bancarios"),
    ("banking", "reconcile", "banking:reconcile", "Realizar conciliación bancaria"),

    # Nómina
    ("payroll", "read", "payroll:read", "Consultar empleados y periodos de nómina"),
    ("payroll", "calculate", "payroll:calculate", "Calcular percepciones, deducciones, ISR e IMSS"),
    ("payroll", "stamp", "payroll:stamp", "Timbrar recibos de nómina CFDI 1.2"),

    # Contabilidad
    ("accounting", "read", "accounting:read", "Consultar catálogo de cuentas y pólizas"),
    ("accounting", "create_policy", "accounting:create_policy", "Crear y autorizar pólizas contables"),
    ("accounting", "financial_reports", "accounting:financial_reports", "Generar Balanza, Balance General y Edo. Resultados"),
]


async def init_database():
    """Initializes tables, seeds permissions, admin user and demo tenant."""
    print(f"[*] Conectando a la base de datos: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}...")
    
    engine = create_async_engine(settings.get_database_url(), echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        print("[*] Creando extensiones de PostgreSQL...")
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto";'))
        
        print("[*] Generando tablas del esquema en PostgreSQL...")
        await conn.run_sync(Base.metadata.create_all)
        print("[+] Tablas creadas con éxito.")

    async with session_maker() as session:
        # 1. Seed Permissions
        print("[*] Sembrando permisos del sistema...")
        existing_permissions = (await session.execute(select(Permission))).scalars().all()
        perm_map = {p.code: p for p in existing_permissions}

        for module, action, code, desc in INITIAL_PERMISSIONS:
            if code not in perm_map:
                perm = Permission(module=module, action=action, code=code, description=desc)
                session.add(perm)
                perm_map[code] = perm
        
        await session.commit()
        print(f"[+] {len(perm_map)} permisos del sistema listos.")

        # 2. Check or create SuperAdmin User
        admin_email = "admin@erpsaas.com"
        admin_res = await session.execute(select(User).where(User.email == admin_email))
        admin_user = admin_res.scalar_one_or_none()

        if not admin_user:
            print(f"[*] Creando usuario Superadministrador ({admin_email})...")
            admin_user = User(
                email=admin_email,
                hashed_password=get_password_hash("Admin123!*"),
                full_name="Administrador Principal ERP",
                is_superadmin=True,
                is_active=True
            )
            session.add(admin_user)
            await session.commit()
            await session.refresh(admin_user)
            print("[+] Usuario Superadministrador creado.")
        else:
            print("[i] Usuario Superadministrador ya existe.")

        # 3. Check or create Default Enterprise Tenant (Empresa Modelo)
        demo_rfc = "EME200101XYZ"
        tenant_res = await session.execute(select(Tenant).where(Tenant.rfc == demo_rfc))
        demo_tenant = tenant_res.scalar_one_or_none()

        if not demo_tenant:
            print("[*] Creando empresa modelo inicial (Tenant)...")
            demo_tenant = Tenant(
                rfc=demo_rfc,
                legal_name="EMPRESA MODELO DE MEXICO S.A. DE C.V.",
                trade_name="Empresa Modelo ERP",
                fiscal_regime_code="601",  # General de Ley Personas Morales
                zip_code="06000",          # Centro Cuauhtémoc, CDMX
                email="contacto@empresamodelo.com",
                phone="555-123-4567",
                status="active",
                plan="enterprise"
            )
            session.add(demo_tenant)
            await session.commit()
            await session.refresh(demo_tenant)

            # Sucursal Matriz
            matrix_branch = Branch(
                tenant_id=demo_tenant.id,
                code="SUC-01",
                name="Sucursal Matriz CDMX",
                address="Av. Paseo de la Reforma 222",
                zip_code="06000",
                is_matrix=True,
                is_active=True
            )
            session.add(matrix_branch)
            await session.commit()
            await session.refresh(matrix_branch)

            # Folios iniciales por serie
            series_list = [
                ("FAC", "A", 1, "Facturación Electrónica"),
                ("COT", "COT", 1, "Cotizaciones"),
                ("PED", "PED", 1, "Pedidos"),
                ("REM", "R", 1, "Remisiones"),
                ("REP", "P", 1, "Complementos de Pago"),
                ("NOM", "NOM", 1, "Recibos de Nómina"),
            ]
            for doc_type, serie, folio, _ in series_list:
                folio_serie = FiscalFoliosSeries(
                    tenant_id=demo_tenant.id,
                    branch_id=matrix_branch.id,
                    document_type=doc_type,
                    serie=serie,
                    current_folio=0,
                    initial_folio=folio,
                    is_default=True
                )
                session.add(folio_serie)

            # Rol Administrador para el Tenant
            admin_role = Role(
                tenant_id=demo_tenant.id,
                code="ADMIN",
                name="Administrador de Empresa",
                description="Acceso total a todos los módulos y operaciones",
                is_system=True
            )
            # Asignar todos los permisos al rol de Admin
            all_perms = (await session.execute(select(Permission))).scalars().all()
            admin_role.permissions.extend(all_perms)
            session.add(admin_role)
            await session.commit()
            await session.refresh(admin_role)

            # Asignar usuario a Tenant
            tenant_user = TenantUser(
                tenant_id=demo_tenant.id,
                user_id=admin_user.id,
                default_branch_id=matrix_branch.id,
                is_active=True
            )
            session.add(tenant_user)
            await session.commit()
            await session.refresh(tenant_user)

            user_role = UserRole(
                tenant_id=demo_tenant.id,
                tenant_user_id=tenant_user.id,
                role_id=admin_role.id
            )
            session.add(user_role)

            # Catálogos maestros iniciales
            # Monedas
            mxn = Currency(
                tenant_id=demo_tenant.id,
                code="MXN",
                name="Peso Mexicano",
                symbol="$",
                exchange_rate=Decimal("1.0000"),
                is_base=True,
                is_active=True
            )
            usd = Currency(
                tenant_id=demo_tenant.id,
                code="USD",
                name="Dólar Estadounidense",
                symbol="US$",
                exchange_rate=Decimal("18.5000"),
                is_base=False,
                is_active=True
            )
            session.add_all([mxn, usd])
            await session.commit()
            await session.refresh(mxn)

            # Almacén General
            general_warehouse = Warehouse(
                tenant_id=demo_tenant.id,
                branch_id=matrix_branch.id,
                code="ALM-01",
                name="Almacén General Matriz",
                is_active=True
            )
            session.add(general_warehouse)

            # Lista de Precios General
            general_price_list = PriceList(
                tenant_id=demo_tenant.id,
                code="LISTA-01",
                name="Lista General de Precios",
                currency_id=mxn.id,
                is_default=True,
                is_active=True
            )
            session.add(general_price_list)

            # Familia de Productos General
            general_category = ProductCategory(
                tenant_id=demo_tenant.id,
                code="GEN",
                name="Artículos Generales",
                is_active=True
            )
            session.add(general_category)

            await session.commit()
            print("[+] Empresa modelo y catálogos maestros iniciales configurados exitosamente.")
        else:
            print("[i] Empresa modelo ya existe.")

    await engine.dispose()
    print("\n[SUCCESS] Inicialización completada exitosamente.")
    print("=" * 65)
    print("Credenciales de Acceso Inicial:")
    print("  Email:    admin@erpsaas.com")
    print("  Password: Admin123!*")
    print(f"  RFC Demo: {demo_rfc}")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(init_database())
