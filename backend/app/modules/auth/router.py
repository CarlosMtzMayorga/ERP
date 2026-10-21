from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.auth.schemas import LoginRequest, SwitchTenantRequest, TokenResponse, UserResponse
from app.modules.auth.service import authenticate_user, build_token_response, get_user_tenants_info

router = APIRouter(prefix="/auth", tags=["Autenticación y Sesión"])


@router.post("/login", response_model=TokenResponse, summary="Iniciar sesión en el ERP")
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    user = await authenticate_user(payload.email, payload.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo electrónico o contraseña incorrectos."
        )
    return await build_token_response(user, None, None, db)


@router.post("/switch-tenant", response_model=TokenResponse, summary="Cambiar de empresa o sucursal activa")
async def switch_tenant(
    payload: SwitchTenantRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db)
):
    if not current_user.is_superadmin:
        membership = next((m for m in current_user.tenants if m.tenant_id == payload.tenant_id and m.is_active), None)
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene acceso asignado a esta empresa."
            )
        branch_id = payload.branch_id or membership.default_branch_id
    else:
        branch_id = payload.branch_id

    return await build_token_response(current_user, payload.tenant_id, branch_id, db)


@router.get("/me", response_model=UserResponse, summary="Obtener perfil y empresas del usuario actual")
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db)
):
    tenants = await get_user_tenants_info(current_user, db)
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_superadmin=current_user.is_superadmin,
        is_active=current_user.is_active,
        tenants=tenants
    )
