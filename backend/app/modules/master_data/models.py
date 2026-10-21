import uuid
from decimal import Decimal
from sqlalchemy import (
    Column, String, Boolean, ForeignKey, Numeric, Text, JSON, Uuid, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.core.database import Base, TenantMixin


class Currency(Base, TenantMixin):
    """
    Catálogo de Monedas del Sistema.
    Compatible con catálogo SAT c_Moneda.
    """
    __tablename__ = "currencies"

    code = Column(String(3), nullable=False)  # MXN, USD, EUR
    name = Column(String(50), nullable=False)
    symbol = Column(String(5), default="$", nullable=False)
    exchange_rate = Column(Numeric(14, 4), default=Decimal("1.0000"), nullable=False)  # Respecto a moneda base
    is_base = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_currencies_tenant_code"),
    )


class Warehouse(Base, TenantMixin):
    """
    Catálogo de Almacenes (Multialmacén).
    """
    __tablename__ = "warehouses"

    branch_id = Column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    code = Column(String(20), nullable=False)  # ALM-01
    name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_warehouses_tenant_code"),
    )


class ProductCategory(Base, TenantMixin):
    """
    Líneas / Familias de Artículos.
    """
    __tablename__ = "product_categories"

    code = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    parent_id = Column(Uuid(as_uuid=True), ForeignKey("product_categories.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_categories_tenant_code"),
    )


class Product(Base, TenantMixin):
    """
    Catálogo Maestro de Artículos y Servicios.
    Soporta multialmacén, control de costos (Promedio y PEPS) y normativas SAT CFDI 4.0.
    """
    __tablename__ = "products"

    sku = Column(String(50), nullable=False, index=True)
    barcode = Column(String(50), nullable=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Tipo: PRODUCTO, SERVICIO, KIT
    product_type = Column(String(20), default="PRODUCTO", nullable=False)
    # Método de Costeo: PROMEDIO, PEPS
    costing_method = Column(String(20), default="PROMEDIO", nullable=False)

    category_id = Column(Uuid(as_uuid=True), ForeignKey("product_categories.id", ondelete="SET NULL"), nullable=True)
    
    # Claves SAT obligatorias CFDI 4.0
    sat_clave_prod_serv = Column(String(10), default="01010101", nullable=False)
    sat_clave_unidad = Column(String(10), default="H87", nullable=False)  # H87 = Pieza, E48 = Servicio
    unit_name = Column(String(20), default="PZA", nullable=False)
    sat_objeto_imp = Column(String(5), default="02", nullable=False)  # 02 = Sí objeto de impuesto

    # Impuestos por defecto
    vat_rate = Column(Numeric(5, 4), default=Decimal("0.1600"), nullable=False)  # 16% IVA
    ieps_rate = Column(Numeric(5, 4), default=Decimal("0.0000"), nullable=False)

    # Costos actuales de referencia
    last_cost = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    average_cost = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    base_price = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "sku", name="uq_products_tenant_sku"),
    )


class PriceList(Base, TenantMixin):
    """
    Listas de Precios (General, Mayoreo, VIP, etc.).
    """
    __tablename__ = "price_lists"

    code = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    currency_id = Column(Uuid(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_price_lists_tenant_code"),
    )


class ProductPrice(Base, TenantMixin):
    """
    Precio asignado a un producto en una lista de precios específica.
    """
    __tablename__ = "product_prices"

    product_id = Column(Uuid(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    price_list_id = Column(Uuid(as_uuid=True), ForeignKey("price_lists.id", ondelete="CASCADE"), nullable=False)
    price = Column(Numeric(14, 4), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "product_id", "price_list_id", name="uq_product_price_list"),
    )


class Customer(Base, TenantMixin):
    """
    Catálogo Maestro de Clientes.
    Integra datos comerciales y fiscales (SAT CFDI 4.0).
    """
    __tablename__ = "customers"

    code = Column(String(20), nullable=False, index=True)
    rfc = Column(String(13), nullable=False, index=True)
    legal_name = Column(String(255), nullable=False)  # Razón Social
    trade_name = Column(String(255), nullable=True)   # Nombre Comercial
    email = Column(String(120), nullable=True)
    phone = Column(String(30), nullable=True)

    # Datos Fiscales SAT CFDI 4.0
    fiscal_regime_code = Column(String(10), nullable=False)  # ej: 601, 612
    zip_code = Column(String(10), nullable=False)            # Domicilio Fiscal
    default_uso_cfdi = Column(String(10), default="G03", nullable=False)
    default_forma_pago = Column(String(5), default="03", nullable=False)  # 03 = Transferencia, 01 = Efectivo
    default_metodo_pago = Column(String(5), default="PPD", nullable=False) # PUE o PPD

    # Crédito y Cobranza
    credit_days = Column(Integer, default=0, nullable=False)
    credit_limit = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    price_list_id = Column(Uuid(as_uuid=True), ForeignKey("price_lists.id", ondelete="SET NULL"), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)

    addresses = relationship("CustomerAddress", back_populates="customer", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_customers_tenant_code"),
    )


class CustomerAddress(Base, TenantMixin):
    """
    Direcciones múltiples por cliente (Fiscal, Entrega, Sucursales del cliente).
    """
    __tablename__ = "customer_addresses"

    customer_id = Column(Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    address_type = Column(String(20), default="FISCAL", nullable=False)  # FISCAL, ENTREGA
    street = Column(String(150), nullable=False)
    exterior_no = Column(String(20), nullable=False)
    interior_no = Column(String(20), nullable=True)
    neighborhood = Column(String(100), nullable=False)  # Colonia
    municipality = Column(String(100), nullable=False)  # Municipio / Alcaldía
    state = Column(String(100), nullable=False)         # Estado
    country = Column(String(50), default="MEX", nullable=False)
    zip_code = Column(String(10), nullable=False)

    customer = relationship("Customer", back_populates="addresses")


class Supplier(Base, TenantMixin):
    """
    Catálogo Maestro de Proveedores (Compras y Cuentas por Pagar).
    """
    __tablename__ = "suppliers"

    code = Column(String(20), nullable=False, index=True)
    rfc = Column(String(13), nullable=False, index=True)
    legal_name = Column(String(255), nullable=False)
    trade_name = Column(String(255), nullable=True)
    email = Column(String(120), nullable=True)
    phone = Column(String(30), nullable=True)
    zip_code = Column(String(10), nullable=False)
    fiscal_regime_code = Column(String(10), nullable=True)

    credit_days = Column(Integer, default=0, nullable=False)
    credit_limit = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_suppliers_tenant_code"),
    )


class BankAccount(Base, TenantMixin):
    """
    Cuentas Bancarias / Chequeras de la Empresa.
    """
    __tablename__ = "bank_accounts"

    bank_name = Column(String(100), nullable=False)      # BBVA, Santander, Banorte
    account_number = Column(String(30), nullable=False)
    clabe = Column(String(18), nullable=False)
    currency_id = Column(Uuid(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False)
    sat_banco_code = Column(String(10), nullable=True)   # Clave SAT de institución bancaria
    current_balance = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "account_number", name="uq_bank_accounts_number"),
    )
