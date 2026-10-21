import pytest
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.core.database import Base
from app.modules.tenants.models import Tenant, Branch, FiscalFoliosSeries
from app.modules.tenants.folios_service import consume_next_folio


@pytest.mark.asyncio
async def test_atomic_folio_consumption():
    # In-memory async SQLite engine for quick integration testing
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    tenant_id = uuid.uuid4()
    branch_id = uuid.uuid4()

    async with session_factory() as session:
        # Create test tenant
        t = Tenant(
            id=tenant_id,
            rfc="EME200101XYZ",
            legal_name="EMPRESA MODELO",
            fiscal_regime_code="601",
            zip_code="06000",
            status="active",
            plan="enterprise"
        )
        session.add(t)

        # Create test series
        serie = FiscalFoliosSeries(
            tenant_id=tenant_id,
            branch_id=branch_id,
            document_type="FAC",
            serie="F",
            current_folio=99,
            initial_folio=1,
            final_folio=500,
            is_default=True
        )
        session.add(serie)
        await session.commit()

    # Consume folio 1
    async with session_factory() as session:
        s, next_folio, _ = await consume_next_folio(
            db=session,
            tenant_id=tenant_id,
            document_type="FAC",
            branch_id=branch_id
        )
        await session.commit()
        assert s == "F"
        assert next_folio == 100

    # Consume folio 2
    async with session_factory() as session:
        s2, next_folio2, _ = await consume_next_folio(
            db=session,
            tenant_id=tenant_id,
            document_type="FAC",
            branch_id=branch_id
        )
        await session.commit()
        assert s2 == "F"
        assert next_folio2 == 101

    await engine.dispose()

