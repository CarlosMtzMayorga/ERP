import uuid
from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import verify_password, create_access_token
from app.modules.auth.models import User, TenantUser, UserRole, Role, Permission
from app.modules.tenants.models import Tenant, Branch
from app.modules.auth.schemas import TenantBriefResponse, UserResponse, TokenResponse


async def authenticate_user(email: str, password: str, db: AsyncSession) -> Optional[User]:
    query = (
        select(User)
        .options(
            selectinload(User.tenants)
            .selectinload(TenantUser.roles)
            .selectinload(UserRole.role)
            .selectinload(Role.permissions)
        )
        .where(User.email == email.strip().lower())
    )
    res = await db.execute(query)
    user = res.scalar_one_or_none()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def get_user_tenants_info(user: User, db: AsyncSession) -> List[TenantBriefResponse]:
    if user.is_superadmin:
        # Superadmin can access all active tenants
        all_tenants = (await db.execute(select(Tenant).where(Tenant.status == "active"))).scalars().all()
        return [
            TenantBriefResponse(
                id=t.id,
                rfc=t.rfc,
                legal_name=t.legal_name,
                trade_name=t.trade_name,
                roles=["SUPERADMIN"]
            )
            for t in all_tenants
        ]
    
    tenant_ids = [m.tenant_id for m in user.tenants if m.is_active]
    if not tenant_ids:
        return []
    
    tenants_res = await db.execute(select(Tenant).where(Tenant.id.in_(tenant_ids), Tenant.status == "active"))
    tenants_map = {t.id: t for t in tenants_res.scalars().all()}
    
    results = []
    for m in user.tenants:
        if m.is_active and m.tenant_id in tenants_map:
            t = tenants_map[m.tenant_id]
            role_names = [ur.role.name for ur in m.roles if ur.role]
            results.append(
                TenantBriefResponse(
                    id=t.id,
                    rfc=t.rfc,
                    legal_name=t.legal_name,
                    trade_name=t.trade_name,
                    default_branch_id=m.default_branch_id,
                    roles=role_names
                )
            )
    return results


async def get_permissions_for_tenant(user: User, tenant_id: uuid.UUID, db: AsyncSession) -> List[str]:
    if user.is_superadmin:
        all_perms = (await db.execute(select(Permission.code))).scalars().all()
        return list(all_perms)

    query = (
        select(Permission.code)
        .join(Role.permissions)
        .join(UserRole, UserRole.role_id == Role.id)
        .join(TenantUser, TenantUser.id == UserRole.tenant_user_id)
        .where(
            TenantUser.user_id == user.id,
            TenantUser.tenant_id == tenant_id,
            TenantUser.is_active == True
        )
    )
    res = await db.execute(query)
    return list(res.scalars().all())


async def build_token_response(
    user: User,
    active_tenant_id: Optional[uuid.UUID],
    active_branch_id: Optional[uuid.UUID],
    db: AsyncSession
) -> TokenResponse:
    tenants_info = await get_user_tenants_info(user, db)
    
    # Auto-select first tenant if none specified
    if not active_tenant_id and tenants_info:
        active_tenant_id = tenants_info[0].id
        active_branch_id = tenants_info[0].default_branch_id

    permissions = []
    if active_tenant_id:
        permissions = await get_permissions_for_tenant(user, active_tenant_id, db)

    access_token = create_access_token(
        subject=str(user.id),
        tenant_id=str(active_tenant_id) if active_tenant_id else None,
        branch_id=str(active_branch_id) if active_branch_id else None,
        is_superadmin=user.is_superadmin
    )

    user_resp = UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_superadmin=user.is_superadmin,
        is_active=user.is_active,
        tenants=tenants_info
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user=user_resp,
        active_tenant_id=active_tenant_id,
        active_branch_id=active_branch_id,
        permissions=permissions
    )

