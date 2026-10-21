import uuid
from typing import Annotated, List, Optional
from fastapi import Depends, HTTPException, Header, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.tenant_context import set_tenant_context, get_current_tenant_id
from app.modules.auth.models import User, TenantUser, UserRole, Role, Permission
from app.modules.tenants.models import Tenant

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)


async def get_current_user(
    token: Annotated[Optional[str], Depends(oauth2_scheme)],
    x_tenant_id: Annotated[Optional[str], Header(alias="X-Tenant-ID")] = None,
    x_branch_id: Annotated[Optional[str], Header(alias="X-Branch-ID")] = None,
    db: AsyncSession = Depends(get_db)
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales no proporcionadas o sesión expirada.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        payload = decode_access_token(token)
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token alterado o expirado.")

    result = await db.execute(
        select(User)
        .options(selectinload(User.tenants))
        .where(User.id == user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado o inactivo.")

    # Determine Active Tenant from Token or Header
    active_tenant_id: Optional[uuid.UUID] = None
    if x_tenant_id:
        try:
            active_tenant_id = uuid.UUID(x_tenant_id)
        except ValueError:
            pass
    elif payload.get("tenant_id"):
        active_tenant_id = uuid.UUID(payload.get("tenant_id"))

    # Determine Active Branch
    active_branch_id: Optional[uuid.UUID] = None
    if x_branch_id:
        try:
            active_branch_id = uuid.UUID(x_branch_id)
        except ValueError:
            pass
    elif payload.get("branch_id"):
        active_branch_id = uuid.UUID(payload.get("branch_id"))

    # Validate tenant membership if user is not superadmin
    if active_tenant_id and not user.is_superadmin:
        membership = next((m for m in user.tenants if m.tenant_id == active_tenant_id and m.is_active), None)
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene acceso a la empresa seleccionada."
            )
        if not active_branch_id:
            active_branch_id = membership.default_branch_id

    # Set context variables for this async request & session
    set_tenant_context(active_tenant_id, active_branch_id, user.id)

    return user


async def get_current_tenant(
    user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db)
) -> Tenant:
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe seleccionar una empresa activa para realizar esta operación."
        )

    res = await db.execute(select(Tenant).where(Tenant.id == tenant_id, Tenant.status == "active"))
    tenant = res.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no encontrada o suspendida.")

    return tenant


def require_permission(permission_code: str):
    """Dependency factory checking if current user has permission in active tenant."""
    async def permission_checker(
        user: Annotated[User, Depends(get_current_user)],
        db: AsyncSession = Depends(get_db)
    ):
        if user.is_superadmin:
            return True

        tenant_id = get_current_tenant_id()
        if not tenant_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Empresa no especificada.")

        # Query user roles and permissions for this tenant
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
        granted_codes = set(res.scalars().all())

        if permission_code not in granted_codes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso denegado: se requiere la facultad '{permission_code}'."
            )
        return True

    return permission_checker
