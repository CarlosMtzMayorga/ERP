import pytest
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.core.database import Base
from app.modules.tenants.models import Tenant
from app.modules.auth.models import User, TenantUser, Role, Permission, UserRole


@pytest.mark.asyncio
async def test_rbac_roles_and_permissions():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    tenant_id = uuid.uuid4()

    async with session_factory() as session:
        # Create tenant
        t = Tenant(
            id=tenant_id,
            rfc="EME200101XYZ",
            legal_name="EMPRESA MODELO",
            fiscal_regime_code="601",
            zip_code="06000",
            status="active"
        )
        session.add(t)

        # Create permissions
        p1 = Permission(module="config", action="read", code="config:read", description="Ver config")
        p2 = Permission(module="config", action="manage", code="config:manage", description="Admin config")
        p3 = Permission(module="sales", action="create", code="sales:create", description="Crear venta")
        session.add_all([p1, p2, p3])
        await session.commit()

        # Create Role with p1 and p3
        role = Role(
            tenant_id=tenant_id,
            code="OPERADOR_VENTAS",
            name="Operador de Ventas",
            is_system=False
        )
        role.permissions.extend([p1, p3])
        session.add(role)

        # Create User
        user = User(
            email="vendedor@erpsaas.com",
            full_name="Vendedor Mostrador",
            hashed_password="hashed_pass_test",
            is_superadmin=False,
            is_active=True
        )
        session.add(user)
        await session.commit()

        # Assign user to tenant and role
        tu = TenantUser(tenant_id=tenant_id, user_id=user.id, is_active=True)
        session.add(tu)
        await session.commit()

        ur = UserRole(tenant_id=tenant_id, tenant_user_id=tu.id, role_id=role.id)
        session.add(ur)
        await session.commit()

        # Query user's effective permissions for this tenant
        query = (
            select(Permission.code)
            .join(Role.permissions)
            .join(UserRole, UserRole.role_id == Role.id)
            .join(TenantUser, TenantUser.id == UserRole.tenant_user_id)
            .where(TenantUser.user_id == user.id, TenantUser.tenant_id == tenant_id)
        )
        res = await session.execute(query)
        granted_codes = set(res.scalars().all())

        assert "config:read" in granted_codes
        assert "sales:create" in granted_codes
        assert "config:manage" not in granted_codes  # Not granted

    await engine.dispose()
