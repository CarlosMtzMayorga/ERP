# ERP SaaS Enterprise (Cloud-Native & Multi-Empresa)

> Sistema de Planificación de Recursos Empresariales (ERP) Web nativo de la nube, multiempresa (multi-tenant), inspirado en la arquitectura modular de **Microsip**, diseñado con un panel administrativo moderno estilo **Rubick / Shadcn UI**, y preparado para la fiscalidad mexicana (**SAT CFDI 4.0**).

---

## 1. Stack Tecnológico

- **Backend:** Python 3.11+ / FastAPI con SQLAlchemy 2.0 (AsyncIO) y Pydantic v2.
- **Frontend:** React 18 con TypeScript, Vite, Tailwind CSS y Lucide Icons.
- **Base de Datos:** PostgreSQL 16 con Row-Level Security (RLS) y aislamiento `tenant_id`.
- **Despliegue Objetivo:** AWS Free Tier (Amazon RDS PostgreSQL `db.t3.micro` / `db.t4g.micro`, AWS App Runner / EC2, Amazon S3 + CloudFront).

---

## 2. Aislamiento Multi-Tenant & Seguridad

El sistema implementa una arquitectura híbrida de alta eficiencia optimizada para **AWS RDS Free Tier**:
1. **Columna `tenant_id` indexada** en todas las entidades maestras y transaccionales.
2. **PostgreSQL Row-Level Security (RLS):** Se activa la política `tenant_isolation_policy` en todas las tablas, vinculada a la variable de sesión `app.current_tenant_id`.
3. **Filtro a nivel aplicación:** ContextVars asíncronos en FastAPI y Middleware que extraen el tenant del JWT o del header `X-Tenant-ID`.
4. **Catálogos SAT Compartidos:** Catálogos del SAT (claves de producto, unidades, formas de pago) sin duplicación innecesaria.
5. **Encriptación CSD:** Llaves privadas de Certificados de Sello Digital encriptadas en reposo con AES-256 (Fernet/GCM).

---

## 3. Módulos del Sistema (Arquitectura Modular Microsip)

1. **Configurador:** Empresas, sucursales, usuarios, roles y permisos RBAC, series/folios, CSD SAT.
2. **Inventarios:** Multialmacén, existencias en tiempo real, costeo Promedio y PEPS, traspasos y ajustes.
3. **Ventas:** Cotizaciones, pedidos, remisiones y facturas CFDI 4.0.
4. **Punto de Venta (POS):** Venta rápida en mostrador, corte X y Z, arqueo y factura global.
5. **Cuentas por Cobrar:** Créditos, límites, antigüedad de saldos y complementos de recepción de pagos (REP 2.0).
6. **Compras:** Requisiciones, órdenes de compra, recepción de mercancía y conciliación XML SAT.
7. **Cuentas por Pagar:** Programación de pagos a proveedores, vencimientos y transferencias.
8. **Bancos:** Chequeras multimoneda, conciliación bancaria y flujo de efectivo.
9. **Nómina:** Empleados, incidencias, ISR, IMSS y timbrado de recibos CFDI 1.2.
10. **Contabilidad:** Pólizas manuales y automáticas generadas por los 9 módulos, catálogo SAT y balanza.

---

## 4. Inicialización Rápida

### Prerrequisitos
- Python 3.11+
- Node.js 18+ (para el frontend)
- PostgreSQL 14+ o Docker

### Paso 1: Configurar Variables de Entorno
```bash
cp .env.example .env
```

### Paso 2: Inicializar la Base de Datos y Sembrar Datos Demo
```bash
cd backend
pip install -r requirements.txt
python scripts/init_db.py
```

### Credenciales por Defecto (Sembradas en `init_db.py`):
- **Email:** `admin@erpsaas.com`
- **Contraseña:** `Admin123!*`
- **Empresa Demo:** EMPRESA MODELO DE MEXICO S.A. DE C.V. (RFC: `EME200101XYZ`)
