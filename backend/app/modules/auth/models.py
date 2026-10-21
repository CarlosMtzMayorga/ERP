import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey, Table, Text, JSON, Uuid
from sqlalchemy.orm import relationship

from app.core.database import Base, TenantMixin


# Association Table between Role and Permission
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Uuid(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    """
    Usuario del Sistema.
    Puede tener acceso a múltiples empresas (tenants).
    """
    __tablename__ = "users"

    email = Column(String(150), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(150), nullable=False)
    phone = Column(String(30), nullable=True)
    is_superadmin = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    tenants = relationship("TenantUser", back_populates="user", cascade="all, delete-orphan")


class TenantUser(Base, TenantMixin):
    """
    Membresía de usuario en una empresa específica con sucursal por defecto.
    """
    __tablename__ = "tenant_users"

    tenant_id = Column(Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    default_branch_id = Column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="tenants")
    roles = relationship("UserRole", back_populates="tenant_user", cascade="all, delete-orphan")


class Role(Base, TenantMixin):
    """
    Rol de seguridad. Puede ser global del sistema (tenant_id null) o custom por empresa.
    """
    __tablename__ = "roles"

    tenant_id = Column(Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    code = Column(String(50), nullable=False)  # ADMIN, CAJERO, VENDEDOR, CONTADOR
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    is_system = Column(Boolean, default=False, nullable=False)

    permissions = relationship("Permission", secondary=role_permissions, backref="roles")


class Permission(Base):
    """
    Permiso granular del sistema.
    Mapea módulos y operaciones precisas.
    """
    __tablename__ = "permissions"

    module = Column(String(50), nullable=False, index=True)  # config, inventory, sales, pos, cxc, purchases, etc.
    action = Column(String(50), nullable=False)              # read, create, update, delete, stamp, cancel, export
    code = Column(String(100), unique=True, nullable=False, index=True)  # sales:create, pos:open_cash
    description = Column(String(255), nullable=True)


class UserRole(Base, TenantMixin):
    """
    Asignación de roles al usuario dentro de un tenant.
    """
    __tablename__ = "user_roles"

    tenant_id = Column(Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_user_id = Column(Uuid(as_uuid=True), ForeignKey("tenant_users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)

    tenant_user = relationship("TenantUser", back_populates="roles")
    role = relationship("Role")


class AuditLog(Base, TenantMixin):
    """
    Bitácora de auditoría inmutable para cumplimiento y seguridad.
    """
    __tablename__ = "audit_logs"

    tenant_id = Column(Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    module = Column(String(50), nullable=False)
    action = Column(String(50), nullable=False)
    entity_name = Column(String(100), nullable=False)
    entity_id = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    details = Column(JSON, nullable=True)

