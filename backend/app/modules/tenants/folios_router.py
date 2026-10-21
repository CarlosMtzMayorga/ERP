import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_tenant, require_permission
from app.modules.auth.models import User
from app.modules.tenants.models import Tenant, FiscalFoliosSeries, Branch
from app.modules.tenants.folios_service import consume_next_folio

router = APIRouter(prefix="/config/folios", tags=["Configurador - Series y Folios"])


class FolioSeriesCreate(BaseModel):
    branch_id: Optional[uuid.UUID] = None
    document_type: str = Field(..., description="Tipo de documento: FAC, REM, TICK, COT, PED, REP, NOM, TRASP, AJUST")
    serie: str = Field(..., max_length=10, description="Código de serie, ej. A, F, POS1, MATRIZ")
    initial_folio: int = Field(1, ge=1)
    final_folio: Optional[int] = Field(None, ge=1)
    is_default: bool = True


class FolioSeriesUpdate(BaseModel):
    branch_id: Optional[uuid.UUID] = None
    serie: Optional[str] = Field(None, max_length=10)
    current_folio: Optional[int] = Field(None, ge=0)
    final_folio: Optional[int] = None
    is_default: Optional[bool] = None


class FolioSeriesResponse(BaseModel):
    id: uuid.UUID
    branch_id: Optional[uuid.UUID]
    branch_name: Optional[str] = None
    document_type: str
    serie: str
    current_folio: int
    initial_folio: int
    final_folio: Optional[int]
    is_default: bool

    class Config:
        from_attributes = True


class ConsumeFolioRequest(BaseModel):
    document_type: str
    branch_id: Optional[uuid.UUID] = None
    serie: Optional[str] = None


class ConsumeFolioResponse(BaseModel):
    serie: str
    folio: int
    formatted_folio: str
    series_id: uuid.UUID


@router.get("", response_model=List[FolioSeriesResponse], summary="Listar todas las series y folios de la empresa")
async def list_folios(
    branch_id: Optional[uuid.UUID] = Query(None, description="Filtrar por sucursal"),
    document_type: Optional[str] = Query(None, description="Filtrar por tipo de documento"),
    tenant: Tenant = Depends(get_current_tenant),
    _has_perm: bool = Depends(require_permission("config:read")),
    db: AsyncSession = Depends(get_db)
):
    query = select(FiscalFoliosSeries, Branch.name.label("branch_name")).outerjoin(
        Branch, Branch.id == FiscalFoliosSeries.branch_id
    ).where(FiscalFoliosSeries.tenant_id == tenant.id)

    if branch_id:
        query = query.where(FiscalFoliosSeries.branch_id == branch_id)
    if document_type:
        query = query.where(FiscalFoliosSeries.document_type == document_type.upper())

    query = query.order_by(FiscalFoliosSeries.document_type, FiscalFoliosSeries.serie)
    res = await db.execute(query)

    items = []
    for serie_row, branch_name in res.all():
        resp = FolioSeriesResponse(
            id=serie_row.id,
            branch_id=serie_row.branch_id,
            branch_name=branch_name or "Todas las sucursales",
            document_type=serie_row.document_type,
            serie=serie_row.serie,
            current_folio=serie_row.current_folio,
            initial_folio=serie_row.initial_folio,
            final_folio=serie_row.final_folio,
            is_default=serie_row.is_default
        )
        items.append(resp)
    return items


@router.post("", response_model=FolioSeriesResponse, status_code=status.HTTP_201_CREATED, summary="Crear nueva serie de folios")
async def create_folio_series(
    payload: FolioSeriesCreate,
    tenant: Tenant = Depends(get_current_tenant),
    _has_perm: bool = Depends(require_permission("config:manage")),
    db: AsyncSession = Depends(get_db)
):
    # Validar sucursal si se especifica
    if payload.branch_id:
        branch_check = await db.execute(
            select(Branch).where(Branch.id == payload.branch_id, Branch.tenant_id == tenant.id)
        )
        if not branch_check.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sucursal no encontrada.")

    new_series = FiscalFoliosSeries(
        tenant_id=tenant.id,
        branch_id=payload.branch_id,
        document_type=payload.document_type.upper(),
        serie=payload.serie.strip().upper(),
        current_folio=payload.initial_folio - 1,
        initial_folio=payload.initial_folio,
        final_folio=payload.final_folio,
        is_default=payload.is_default
    )
    db.add(new_series)
    await db.commit()
    await db.refresh(new_series)

    return FolioSeriesResponse.model_validate(new_series)


@router.put("/{serie_id}", response_model=FolioSeriesResponse, summary="Actualizar serie de folios existente")
async def update_folio_series(
    serie_id: uuid.UUID,
    payload: FolioSeriesUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    _has_perm: bool = Depends(require_permission("config:manage")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(FiscalFoliosSeries).where(FiscalFoliosSeries.id == serie_id, FiscalFoliosSeries.tenant_id == tenant.id)
    )
    serie_row = res.scalar_one_or_none()
    if not serie_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Serie de folios no encontrada.")

    if payload.branch_id is not None:
        serie_row.branch_id = payload.branch_id
    if payload.serie is not None:
        serie_row.serie = payload.serie.strip().upper()
    if payload.current_folio is not None:
        serie_row.current_folio = payload.current_folio
    if payload.final_folio is not None:
        serie_row.final_folio = payload.final_folio
    if payload.is_default is not None:
        serie_row.is_default = payload.is_default

    await db.commit()
    await db.refresh(serie_row)
    return FolioSeriesResponse.model_validate(serie_row)


@router.post("/consume", response_model=ConsumeFolioResponse, summary="Consumo atómico de folio (con bloqueo SELECT FOR UPDATE)")
async def test_consume_folio(
    payload: ConsumeFolioRequest,
    tenant: Tenant = Depends(get_current_tenant),
    _has_perm: bool = Depends(require_permission("config:manage")),
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint atómico de consumo transaccional. Bloquea la serie en Postgres
    hasta completar la asignación del folio.
    """
    serie, next_folio, series_id = await consume_next_folio(
        db=db,
        tenant_id=tenant.id,
        document_type=payload.document_type,
        branch_id=payload.branch_id,
        preferred_serie=payload.serie
    )
    await db.commit()

    return ConsumeFolioResponse(
        serie=serie,
        folio=next_folio,
        formatted_folio=f"{serie}-{next_folio}",
        series_id=series_id
    )

