import uuid
from typing import Optional, Tuple
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.modules.tenants.models import FiscalFoliosSeries


async def consume_next_folio(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    document_type: str,
    branch_id: Optional[uuid.UUID] = None,
    preferred_serie: Optional[str] = None
) -> Tuple[str, int, uuid.UUID]:
    """
    Consume atómicamente el siguiente folio consecutivo para un tipo de documento.
    
    GARANTÍA DE CONCURRENCIA:
    Utiliza bloqueo exclusivo de fila en PostgreSQL ('SELECT ... FOR UPDATE').
    Cualquier otra transacción concurrente (facturación simultánea, POS multipunto)
    esperará a que la fila se actualice y libere, impidiendo matemáticamente folios duplicados
    o saltos inconsistentes en la contabilidad y el SAT.
    """
    query = (
        select(FiscalFoliosSeries)
        .where(
            FiscalFoliosSeries.tenant_id == tenant_id,
            FiscalFoliosSeries.document_type == document_type.upper()
        )
    )

    if preferred_serie:
        query = query.where(FiscalFoliosSeries.serie == preferred_serie.upper())
    elif branch_id:
        # Priorizar la serie asignada a la sucursal específica, luego las genéricas
        query = query.where(
            (FiscalFoliosSeries.branch_id == branch_id) | (FiscalFoliosSeries.branch_id.is_(None))
        ).order_by(
            FiscalFoliosSeries.branch_id.desc(),
            FiscalFoliosSeries.is_default.desc()
        )
    else:
        query = query.order_by(FiscalFoliosSeries.is_default.desc())

    # Bloqueo exclusivo a nivel de fila PostgreSQL
    query = query.with_for_update()

    result = await db.execute(query)
    serie_row = result.scalars().first()

    if not serie_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe una serie de folios configurada para el tipo de documento '{document_type}'."
        )

    # Calcular consecutivo
    if serie_row.current_folio < serie_row.initial_folio:
        next_folio = serie_row.initial_folio
    else:
        next_folio = serie_row.current_folio + 1

    # Validar límite superior si está configurado
    if serie_row.final_folio and next_folio > serie_row.final_folio:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Rango de folios agotado para la serie '{serie_row.serie}' "
                f"(Límite máximo: {serie_row.final_folio}). Configure una nueva serie o aumente el rango."
            )
        )

    # Actualizar estado atómicamente
    serie_row.current_folio = next_folio
    await db.flush()  # Conserva el bloqueo en la transacción actual

    return serie_row.serie, next_folio, serie_row.id

