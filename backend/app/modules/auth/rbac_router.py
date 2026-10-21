import uuid
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_tenant, require_permission
from app.core.security import get_password_hash
from app.modules.auth.models import User, TenantUser, Role, Permission, UserRole, role_permissions
from app.modules.tenants.models import Tenant, Branch

router = APIRouter(prefix="/rbac", tags=["Configurador - Control de Accesos (RBAC)"])


# --- Schemas ---
class PermissionItem(BaseModel):
    id: uuid.UUID
    module: str
    action: str
    code: str
    description: Optional[str]

    class Config:
        from_attributes = True


class RoleCreate(BaseModel):
    code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    permission_ids: List[uuid.UUID] = []


class RoleResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: Optional[str]
    is_system: bool
    permissions: List[PermissionItem] = []

    class Config:
        from_attributes = True


class TenantUserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: Optional[str] = "Temporal123!*"
    phone: Optional[str] = None
    default_branch_id: Optional[uuid.UUID] = None
    role_ids: List[uuid.UUID] = []


class TenantUserUpdateRoles(BaseModel):
    default_branch_id: Optional[uuid.UUID] = None
    role_ids: List[uuid.UUID]


class TenantUserResponse(BaseModel):
    id: uuid.UUID          # User.id
    tenant_user_id: uuid.UUID
    email: str
    full_name: str
    phone: Optional[str]
    is_active: bool
    default_branch_id: Optional[uuid.UUID]
    default_branch_name: Optional[str] = None
    roles: List[str] = []
    role_ids: List[uuid.UUID] = []


# --- Endpoints: Permisos ---
@router.get("/permissions", response_model=Dict[str, List[PermissionItem]], summary="Listar catálogo de permisos agrupados por módulo")
async def list_permissions(
    _has_perm: bool = Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Permission).order_by(Permission.module, Permission.code))
    perms = res.scalars().all()

    grouped: Dict[str, List[PermissionItem]] = {}
    for p in perms:
        item = PermissionItem.model_validate(p)
        grouped.setdefault(p.module, []).append(item)
    return grouped


# --- Endpoints: Roles ---
@router.get("/roles", response_model=List[RoleResponse], summary="Listar roles de la empresa activa")
async def list_roles(
    tenant: Tenant = Depends(get_current_tenant),
    _has_perm: bool = Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Role)
        .options(selectinload(Role.permissions))
        .where((Role.tenant_id == tenant.id) | (Role.tenant_id.is_(None)))
        .order_by(Role.is_system.desc(), Role.name)
    )
    res = await db.execute(stmt)
    roles = res.scalars().all()
    return [RoleResponse.model_validate(r) for r in roles]


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED, summary="Crear nuevo rol para la empresa")
async def create_role(
    payload: RoleCreate,
    tenant: Tenant = Depends(get_current_tenant),
    _has_perm: bool = Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db)
):
    # Verificar código único en el tenant
    existing = await db.execute(
        select(Role).where(Role.tenant_id == tenant.id, Role.code == payload.code.strip().upper())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Ya existe un rol con clave '{payload.code}'.")

    new_role = Role(
        tenant_id=tenant.id,
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        description=payload.description,
        is_system=False
    )

    if payload.permission_ids:
        perm_res = await db.execute(select(Permission).where(Permission.id.in_(payload.permission_ids)))
        new_role.permissions = list(perm_res.scalars().all())

    db.add(new_role)
    await db.commit()
    await db.refresh(new_role)

    # Re-cargar con relaciones
    loaded = await db.execute(
        select(Role).options(selectinload(Role.permissions)).where(Role.id == new_role.id)
    )
    return RoleResponse.model_validate(loaded.scalar_one())


@router.put("/roles/{role_id}", response_model=RoleResponse, summary="Actualizar rol y permisos")
async def update_role(
    role_id: uuid.UUID,
    payload: RoleCreate,
    tenant: Tenant = Depends(get_current_tenant),
    _has_perm: bool = Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id, Role.tenant_id == tenant.id)
    res = await db.execute(stmt)
    role = res.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado o es rol protegido del sistema.")

    role.name = payload.name.strip()
    role.description = payload.description

    if payload.permission_ids is not None:
        perm_res = await db.execute(select(Permission).where(Permission.id.in_(payload.permission_ids)))
        role.permissions = list(perm_res.scalars().all())

    await db.commit()
    await db.refresh(role)
    return RoleResponse.model_validate(role)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar rol personalizado")
async def delete_role(
    role_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    _has_perm: bool = Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Role).where(Role.id == role_id, Role.tenant_id == tenant.id)
    res = await db.execute(stmt)
    role = res.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado.")
    if role.is_system:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se pueden eliminar roles protegidos del sistema.")

    await db.delete(role)
    await db.commit()
    return None


# --- Endpoints: Usuarios de la Empresa ---
@router.get("/users", response_model=List[TenantUserResponse], summary="Listar usuarios asignados a la empresa activa")
async def list_tenant_users(
    tenant: Tenant = Depends(get_current_tenant),
    _has_perm: bool = Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(TenantUser)
        .options(
            selectinload(TenantUser.user),
            selectinload(TenantUser.roles).selectinload(UserRole.role)
        )
        .where(TenantUser.tenant_id == tenant.id)
    )
    res = await db.execute(stmt)
    tenant_users = res.scalars().all()

    # Pre-cargar nombres de sucursales
    branches_res = await db.execute(select(Branch).where(Branch.tenant_id == tenant.id))
    branch_map = {b.id: b.name for b in branches_res.scalars().all()}

    output = []
    for tu in tenant_users:
        role_names = [ur.role.name for ur in tu.roles if ur.role]
        role_ids = [ur.role_id for ur in tu.roles if ur.role]
        output.append(
            TenantUserResponse(
                id=tu.user.id,
                tenant_user_id=tu.id,
                email=tu.user.email,
                full_name=tu.user.full_name,
                phone=tu.user.phone,
                is_active=tu.is_active and tu.user.is_active,
                default_branch_id=tu.default_branch_id,
                default_branch_name=branch_map.get(tu.default_branch_id, "Sin sucursal asignada"),
                roles=role_names,
                role_ids=role_ids
            )
        )
    return output


@router.post("/users", response_model=TenantUserResponse, status_code=status.HTTP_201_CREATED, summary="Registrar o asignar usuario a la empresa activa")
async def create_or_assign_user(
    payload: TenantUserCreate,
    tenant: Tenant = Depends(get_current_tenant),
    _has_perm: bool = Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db)
):
    email_clean = payload.email.strip().lower()

    # Buscar si ya existe el usuario global
    user_res = await db.execute(select(User).where(User.email == email_clean))
    user = user_res.scalar_one_or_none()

    if not user:
        # Crear nuevo usuario en el sistema
        user = User(
            email=email_clean,
            full_name=payload.full_name.strip(),
            phone=payload.phone,
            hashed_password=get_password_hash(payload.password or "Temporal123!*"),
            is_superadmin=False,
            is_active=True
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # Verificar si ya está asignado a este tenant
    tu_res = await db.execute(
        select(TenantUser).where(TenantUser.tenant_id == tenant.id, TenantUser.user_id == user.id)
    )
    tenant_user = tu_res.scalar_one_or_none()

    if tenant_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El usuario '{email_clean}' ya está asignado a esta empresa."
        )

    # Crear membresía de empresa
    tenant_user = TenantUser(
        tenant_id=tenant.id,
        user_id=user.id,
        default_branch_id=payload.default_branch_id,
        is_active=True
    )
    db.add(tenant_user)
    await db.commit()
    await db.refresh(tenant_user)

    # Asignar roles
    assigned_role_names = []
    if payload.role_ids:
        roles_res = await db.execute(
            select(Role).where(Role.id.in_(payload.role_ids), (Role.tenant_id == tenant.id) | (Role.tenant_id.is_(None)))
        )
        valid_roles = roles_res.scalars().all()
        for r in valid_roles:
            ur = UserRole(tenant_id=tenant.id, tenant_user_id=tenant_user.id, role_id=r.id)
            db.add(ur)
            assigned_role_names.append(r.name)
        await db.commit()

    return TenantUserResponse(
        id=user.id,
        tenant_user_id=tenant_user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        is_active=True,
        default_branch_id=tenant_user.default_branch_id,
        roles=assigned_role_names,
        role_ids=payload.role_ids
    )


@router.put("/users/{user_id}/status", summary="Activar o suspender acceso de usuario en la empresa activa")
async def toggle_user_status(
    user_id: uuid.UUID,
    active: bool,
    tenant: Tenant = Depends(get_current_tenant),
    _has_perm: bool = Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(TenantUser).where(TenantUser.tenant_id == tenant.id, TenantUser.user_id == user_id)
    res = await db.execute(stmt)
    tu = res.scalar_one_or_none()
    if not tu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado en esta empresa.")

    tu.is_active = active
    await db.commit()
    return {"message": "Estado actualizado con éxito.", "is_active": active}


@router.put("/users/{user_id}/roles", response_model=TenantUserResponse, summary="Actualizar roles y sucursal de un usuario")
async def update_user_roles(
    user_id: uuid.UUID,
    payload: TenantUserUpdateRoles,
    tenant: Tenant = Depends(get_current_tenant),
    _has_perm: bool = Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(TenantUser).options(selectinload(TenantUser.user)).where(
        TenantUser.tenant_id == tenant.id, TenantUser.user_id == user_id
    )
    res = await db.execute(stmt)
    tu = res.scalar_one_or_none()
    if not tu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado en esta empresa.")

    tu.default_branch_id = payload.default_branch_id

    # Eliminar roles existentes y asignar los nuevos
    await db.execute(delete(UserRole).where(UserRole.tenant_user_id == tu.id))

    assigned_names = []
    if payload.role_ids:
        roles_res = await db.execute(
            select(Role).where(Role.id.in_(payload.role_ids), (Role.tenant_id == tenant.id) | (Role.tenant_id.is_(None)))
        )
        for r in roles_res.scalars().all():
            ur = UserRole(tenant_id=tenant.id, tenant_user_id=tu.id, role_id=r.id)
            db.add(ur)
            assigned_names.append(r.name)

    await db.commit()

    return TenantUserResponse(
        id=tu.user.id,
        tenant_user_id=tu.id,
        email=tu.user.email,
        full_name=tu.user.full_name,
        phone=tu.user.phone,
        is_active=tu.is_active,
        default_branch_id=tu.default_branch_id,
        roles=assigned_names,
        role_ids=payload.role_ids
    )
