import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from sqlalchemy import Column, DateTime, String, text, Uuid
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, declared_attr

from app.core.config import settings
from app.core.tenant_context import get_current_tenant_id


# PostgreSQL Async Engine with pool settings optimized for AWS RDS Free Tier (db.t3.micro / db.t4g.micro)
engine = create_async_engine(
    settings.get_database_url(),
    echo=(settings.ENVIRONMENT == "development"),
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models with standard audit columns."""
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )


class TenantMixin:
    """
    Mixin for all multi-tenant models.
    Enforces a mandatory tenant_id with an index on every table.
    """
    @declared_attr
    def tenant_id(cls):
        return Column(Uuid(as_uuid=True), nullable=False, index=True)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that yields an async database session.
    If a tenant is set in context, it sets PostgreSQL session variable for Row-Level Security (RLS).
    """
    async with AsyncSessionLocal() as session:
        tenant_id = get_current_tenant_id()
        if tenant_id:
            # Set PostgreSQL session config for Row-Level Security
            await session.execute(text(f"SET LOCAL app.current_tenant_id = '{str(tenant_id)}'"))
        try:
            yield session
        finally:
            await session.close()

