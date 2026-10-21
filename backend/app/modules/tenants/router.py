import uuid
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_tenant, require_permission
from app.modules.auth.models import User
from app.modules.tenants.models import Tenant, Branch, FiscalFoliosSeries

router = APIRouter(prefix="/tenants", tags=["Configurador - Empresas y Sucursales"])


class BranchResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    address: Optional[str]
    zip_code: str
    phone: Optional[str]
    is_matrix: bool
    is_active: bool

    class Config:
        from_attributes = True


class TenantDetailResponse(BaseModel):
    id: uuid.UUID
    rfc: str
    legal_name: str
    trade_name: Optional[str]
    fiscal_regime_code: str
    zip_code: str
    email: Optional[str]
    phone: Optional[str]
    status: str
    plan: str
    branches: List[BranchResponse] = []

    class Config:
        from_attributes = True


@router.get("/current", response_model=TenantDetailResponse, summary="Obtener detalles de la empresa activa")
async def get_active_company(
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
    db: AsyncSession = Depends(get_db)
):
    branches_res = await db.execute(
        select(Branch).where(Branch.tenant_id == tenant.id, Branch.is_active == True)
    )
    branches = branches_res.scalars().all()
    
    return TenantDetailResponse(
        id=tenant.id,
        rfc=tenant.rfc,
        legal_name=tenant.legal_name,
        trade_name=tenant.trade_name,
        fiscal_regime_code=tenant.fiscal_regime_code,
        zip_code=tenant.zip_code,
        email=tenant.email,
        phone=tenant.phone,
        status=tenant.status,
        plan=tenant.plan,
        branches=[BranchResponse.model_validate(b) for b in branches]
    )


@router.get("/branches", response_model=List[BranchResponse], summary="Listar sucursales de la empresa activa")
async def list_branches(
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(Branch).where(Branch.tenant_id == tenant.id).order_by(Branch.is_matrix.desc(), Branch.code)
    )
    return [BranchResponse.model_validate(b) for b in res.scalars().all()]
