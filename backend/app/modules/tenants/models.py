import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey, JSON, Uuid
from sqlalchemy.orm import relationship

from app.core.database import Base, TenantMixin


class Tenant(Base):
    """
    Empresa / Organización (Tenant).
    Representa una empresa jurídica en el ERP SaaS.
    """
    __tablename__ = "tenants"

    rfc = Column(String(13), unique=True, nullable=False, index=True)
    legal_name = Column(String(255), nullable=False)  # Razón Social
    trade_name = Column(String(255), nullable=True)   # Nombre Comercial
    fiscal_regime_code = Column(String(10), nullable=False)  # Clave SAT Régimen Fiscal (ej. 601)
    zip_code = Column(String(10), nullable=False)  # Código Postal Fiscal
    
    email = Column(String(120), nullable=True)
    phone = Column(String(30), nullable=True)
    logo_url = Column(String(500), nullable=True)
    
    status = Column(String(20), default="active", nullable=False)  # active, suspended, trial
    plan = Column(String(50), default="enterprise", nullable=False)
    settings = Column(JSON, default=dict, nullable=False)  # Configuraciones personalizadas

    # Relationships
    branches = relationship("Branch", back_populates="tenant", cascade="all, delete-orphan")
    folio_series = relationship("FiscalFoliosSeries", back_populates="tenant", cascade="all, delete-orphan")
    csd_certificates = relationship("CSDCertificate", back_populates="tenant", cascade="all, delete-orphan")


class Branch(Base, TenantMixin):
    """
    Sucursal de la empresa.
    Permite la operación multialmacén, multi-caja y facturación por sucursal.
    """
    __tablename__ = "branches"

    tenant_id = Column(Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(20), nullable=False)  # Ej. SUC-01, MATRIZ
    name = Column(String(150), nullable=False)
    address = Column(String(255), nullable=True)
    zip_code = Column(String(10), nullable=False)
    phone = Column(String(30), nullable=True)
    is_matrix = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    tenant = relationship("Tenant", back_populates="branches")


class FiscalFoliosSeries(Base, TenantMixin):
    """
    Series y Folios por Tipo de Documento y Sucursal.
    Controla el consecutivo transaccional (Ventas, Remisiones, Pagos REP, etc.).
    """
    __tablename__ = "fiscal_folios_series"

    tenant_id = Column(Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    
    document_type = Column(String(20), nullable=False)  # FAC, COT, PED, REM, REP, NOM, TRASP, AJUST
    serie = Column(String(10), nullable=False)          # Ej: 'A', 'B', 'REM', 'POS'
    current_folio = Column(Integer, default=0, nullable=False)
    initial_folio = Column(Integer, default=1, nullable=False)
    final_folio = Column(Integer, nullable=True)
    is_default = Column(Boolean, default=True, nullable=False)

    tenant = relationship("Tenant", back_populates="folio_series")


class CSDCertificate(Base, TenantMixin):
    """
    Certificados de Sello Digital (CSD) del SAT.
    Almacena el certificado público (.cer) y la llave privada encriptada (.key).
    """
    __tablename__ = "sat_csd_certificates"

    tenant_id = Column(Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    rfc = Column(String(13), nullable=False)
    certificate_number = Column(String(30), nullable=False)  # Número de serie de 20 dígitos
    valid_from = Column(DateTime(timezone=True), nullable=False)
    valid_to = Column(DateTime(timezone=True), nullable=False)
    certificate_pem = Column(Text, nullable=False)
    encrypted_private_key = Column(Text, nullable=False)
    key_passphrase_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    tenant = relationship("Tenant", back_populates="csd_certificates")

