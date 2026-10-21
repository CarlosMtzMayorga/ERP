import uuid
from datetime import datetime, timezone
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_tenant, require_permission
from app.modules.auth.models import User
from app.modules.tenants.models import Tenant, CSDCertificate
from app.modules.fiscal_mexico.csd_service import validate_and_process_csd, CSDValidationError

router = APIRouter(prefix="/config/csd", tags=["Configurador - Certificados CSD SAT"])


class CSDResponse(BaseModel):
    id: uuid.UUID
    rfc: str
    certificate_number: str
    valid_from: datetime
    valid_to: datetime
    is_active: bool
    status: str            # active (vigente), expiring_soon (por vencer), expired (vencido)
    days_remaining: int

    class Config:
        from_attributes = True


@router.post("/upload", response_model=CSDResponse, summary="Cargar y validar par de certificados CSD (.cer y .key)")
async def upload_csd_certificates(
    cer_file: UploadFile = File(..., description="Archivo de Certificado Público (.cer) del SAT"),
    key_file: UploadFile = File(..., description="Archivo de Llave Privada (.key) del SAT"),
    passphrase: str = Form(..., description="Contraseña de la llave privada del CSD"),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user),
    _has_perm: bool = Depends(require_permission("config:manage")),
    db: AsyncSession = Depends(get_db)
):
    # Validar extensiones
    if not cer_file.filename.lower().endswith(".cer"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo del certificado debe tener extensión .cer"
        )
    if not key_file.filename.lower().endswith(".key"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo de la llave privada debe tener extensión .key"
        )

    # Leer archivos en memoria (streaming seguro sin escribir a disco)
    cer_bytes = await cer_file.read()
    key_bytes = await key_file.read()

    try:
        processed = validate_and_process_csd(
            cer_bytes=cer_bytes,
            key_bytes=key_bytes,
            passphrase=passphrase,
            expected_rfc=tenant.rfc
        )
    except CSDValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

    # Desactivar certificados previos de este tenant para mantener sólo uno vigente
    await db.execute(
        update(CSDCertificate)
        .where(CSDCertificate.tenant_id == tenant.id)
        .values(is_active=False)
    )

    # Crear nuevo registro persistente con datos cifrados
    csd_record = CSDCertificate(
        tenant_id=tenant.id,
        rfc=processed["rfc"],
        certificate_number=processed["certificate_number"],
        valid_from=processed["valid_from"],
        valid_to=processed["valid_to"],
        certificate_pem=processed["certificate_pem"],
        encrypted_private_key=processed["encrypted_private_key"],
        key_passphrase_hash=processed["encrypted_passphrase"],
        is_active=True
    )
    db.add(csd_record)
    await db.commit()
    await db.refresh(csd_record)

    return CSDResponse(
        id=csd_record.id,
        rfc=csd_record.rfc,
        certificate_number=csd_record.certificate_number,
        valid_from=csd_record.valid_from,
        valid_to=csd_record.valid_to,
        is_active=csd_record.is_active,
        status=processed["status"],
        days_remaining=processed["days_remaining"]
    )


@router.get("", response_model=List[CSDResponse], summary="Listar certificados CSD de la empresa activa")
async def list_csd_certificates(
    tenant: Tenant = Depends(get_current_tenant),
    _has_perm: bool = Depends(require_permission("config:read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(CSDCertificate)
        .where(CSDCertificate.tenant_id == tenant.id)
        .order_by(CSDCertificate.is_active.desc(), CSDCertificate.valid_to.desc())
    )
    res = await db.execute(stmt)
    certificates = res.scalars().all()

    now = datetime.now(timezone.utc)
    results = []
    for c in certificates:
        v_to = c.valid_to if c.valid_to.tzinfo else c.valid_to.replace(tzinfo=timezone.utc)
        v_from = c.valid_from if c.valid_from.tzinfo else c.valid_from.replace(tzinfo=timezone.utc)
        
        days_left = (v_to - now).days
        if now > v_to:
            status_label = "expired"
        elif days_left <= 30:
            status_label = "expiring_soon"
        elif now < v_from:
            status_label = "not_yet_valid"
        else:
            status_label = "active"

        results.append(
            CSDResponse(
                id=c.id,
                rfc=c.rfc,
                certificate_number=c.certificate_number,
                valid_from=c.valid_from,
                valid_to=c.valid_to,
                is_active=c.is_active,
                status=status_label,
                days_remaining=days_left
            )
        )
    return results


@router.delete("/{csd_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Desactivar o eliminar certificado CSD")
async def delete_csd_certificate(
    csd_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    _has_perm: bool = Depends(require_permission("config:manage")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(CSDCertificate).where(CSDCertificate.id == csd_id, CSDCertificate.tenant_id == tenant.id)
    res = await db.execute(stmt)
    csd = res.scalar_one_or_none()
    if not csd:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificado CSD no encontrado.")
    
    await db.delete(csd)
    await db.commit()
    return None
