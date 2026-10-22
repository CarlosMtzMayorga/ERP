import base64
import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Dict, Any, List, Tuple
from xml.etree import ElementTree as ET

from app.modules.fiscal_mexico.cfdi_builder import sign_cadena_original, stamp_with_mock_pac
from app.modules.payroll.models import PayrollReceipt, PayrollPeriod, Employee, PayrollReceiptItem


def calculate_seniority_weeks(hire_date: date, current_date: date = None) -> str:
    """
    Calcula la antigüedad del trabajador en formato SAT Anexo 20 (ej: P52W).
    """
    if current_date is None:
        current_date = date.today()
    delta_days = (current_date - hire_date).days
    weeks = max(1, delta_days // 7)
    return f"P{weeks}W"


def build_cadena_original_nomina_12(
    version: str,
    serie: str,
    folio: str,
    fecha: str,
    forma_pago: str,
    subtotal: str,
    descuento: str,
    moneda: str,
    total: str,
    tipo_comprobante: str,
    exportacion: str,
    metodo_pago: str,
    lugar_expedicion: str,
    emisor_rfc: str,
    emisor_nombre: str,
    emisor_regimen: str,
    receptor_rfc: str,
    receptor_nombre: str,
    receptor_domicilio: str,
    receptor_regimen: str,
    receptor_uso_cfdi: str,
    nomina_version: str,
    tipo_nomina: str,
    fecha_pago: str,
    fecha_inicial: str,
    fecha_final: str,
    num_dias_pagados: str,
    total_percepciones: str,
    total_deducciones: str,
    curp: str,
    nss: str
) -> str:
    """
    Construye la Cadena Original para CFDI 4.0 con Complemento Nómina 1.2 conforme al Anexo 20.
    """
    parts = [
        version,
        serie,
        folio,
        fecha,
        forma_pago,
        subtotal,
        descuento,
        moneda,
        total,
        tipo_comprobante,
        exportacion,
        metodo_pago,
        lugar_expedicion,
        emisor_rfc,
        emisor_nombre,
        emisor_regimen,
        receptor_rfc,
        receptor_nombre,
        receptor_domicilio,
        receptor_regimen,
        receptor_uso_cfdi,
        # Complemento Nómina 1.2
        nomina_version,
        tipo_nomina,
        fecha_pago,
        fecha_inicial,
        fecha_final,
        num_dias_pagados,
        total_percepciones,
        total_deducciones,
        curp,
        nss
    ]
    return "||" + "|".join(parts) + "||"


def generate_payroll_cfdi_xml(
    receipt: PayrollReceipt,
    period: PayrollPeriod,
    employee: Employee,
    tenant: Any,
    csd: Any,
    branch_zip: str = "06000"
) -> Tuple[str, str, str]:
    """
    Genera el comprobante fiscal CFDI 4.0 con Complemento Nómina versión 1.2 sellado criptográficamente en memoria.
    Retorna: (xml_str, cadena_original, sello_digital)
    """
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    # Extraer base64 del certificado CSD limpio
    cert_clean = "".join([
        line.strip() for line in csd.certificate_pem.splitlines()
        if not line.startswith("-----")
    ])

    ns_cfdi = "http://www.sat.gob.mx/cfd/4"
    ns_xsi = "http://www.w3.org/2001/XMLSchema-instance"
    ns_nomina12 = "http://www.sat.gob.mx/nomina12"

    ET.register_namespace("cfdi", ns_cfdi)
    ET.register_namespace("xsi", ns_xsi)
    ET.register_namespace("nomina12", ns_nomina12)

    serie = "NOM"
    folio = receipt.folio or str(receipt.id)[:8].upper()

    subtotal_str = f"{receipt.total_perceptions:.2f}"
    descuento_str = f"{receipt.total_deductions:.2f}"
    total_str = f"{receipt.total_net:.2f}"

    # 1. Comprobante Raíz CFDI 4.0
    root = ET.Element(
        f"{{{ns_cfdi}}}Comprobante",
        {
            f"{{{ns_xsi}}}schemaLocation": (
                "http://www.sat.gob.mx/cfd/4 http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd "
                "http://www.sat.gob.mx/nomina12 http://www.sat.gob.mx/sitio_internet/cfd/nomina/nomina12.xsd"
            ),
            "Version": "4.0",
            "Serie": serie,
            "Folio": folio,
            "Fecha": now_utc,
            "FormaPago": "99",  # Por definir
            "NoCertificado": csd.certificate_number,
            "Certificado": cert_clean,
            "SubTotal": subtotal_str,
            "Descuento": descuento_str,
            "Moneda": "MXN",
            "Total": total_str,
            "TipoDeComprobante": "N",  # N = Nómina
            "Exportacion": "01",  # No aplica
            "MetodoPago": "PUE",  # Pago en una sola exhibición
            "LugarExpedicion": branch_zip or "06000",
            "Sello": ""  # Se completará tras firmar
        }
    )

    # 2. Emisor
    ET.SubElement(
        root,
        f"{{{ns_cfdi}}}Emisor",
        {
            "Rfc": tenant.rfc,
            "Nombre": tenant.legal_name,
            "RegimenFiscal": getattr(tenant, "fiscal_regime_code", "601") or "601"
        }
    )

    # 3. Receptor (Trabajador)
    ET.SubElement(
        root,
        f"{{{ns_cfdi}}}Receptor",
        {
            "Rfc": employee.rfc,
            "Nombre": f"{employee.first_name} {employee.last_name}",
            "DomicilioFiscalReceptor": employee.zip_code or branch_zip or "06000",
            "RegimenFiscalReceptor": "605",  # Sueldos y Salarios
            "UsoCFDI": "CN01"  # Nómina
        }
    )

    # 4. Conceptos (Línea estándar Anexo 20 de Nómina)
    conceptos_el = ET.SubElement(root, f"{{{ns_cfdi}}}Conceptos")
    ET.SubElement(
        conceptos_el,
        f"{{{ns_cfdi}}}Concepto",
        {
            "ClaveProdServ": "84111505",  # Servicios de contabilidad de sueldos
            "Cantidad": "1",
            "ClaveUnidad": "ACT",
            "Descripcion": "Pago de nómina",
            "ValorUnitario": subtotal_str,
            "Importe": subtotal_str,
            "Descuento": descuento_str,
            "ObjetoImp": "01"  # No objeto de impuesto
        }
    )

    # 5. Complemento Nómina 1.2
    complemento_el = ET.SubElement(root, f"{{{ns_cfdi}}}Complemento")

    seniority_str = calculate_seniority_weeks(employee.hire_date, period.end_date)
    nomina_attrs = {
        "Version": "1.2",
        "TipoNomina": period.payroll_type or "O",
        "FechaPago": period.payment_date.strftime("%Y-%m-%d"),
        "FechaInicialPago": period.start_date.strftime("%Y-%m-%d"),
        "FechaFinalPago": period.end_date.strftime("%Y-%m-%d"),
        "NumDiasPagados": f"{receipt.days_paid:.3f}",
        "TotalPercepciones": subtotal_str,
        "TotalDeducciones": descuento_str
    }

    nomina_el = ET.SubElement(complemento_el, f"{{{ns_nomina12}}}Nomina", nomina_attrs)

    # Emisor Nómina (Registro Patronal)
    ET.SubElement(
        nomina_el,
        f"{{{ns_nomina12}}}Emisor",
        {"RegistroPatronal": "Y1234567890"}
    )

    # Receptor Nómina (Datos del empleado)
    receptor_nom_attrs = {
        "Curp": employee.curp,
        "NumSeguridadSocial": employee.nss,
        "FechaInicioRelLaboral": employee.hire_date.strftime("%Y-%m-%d"),
        "Antiguedad": seniority_str,
        "TipoContrato": employee.contract_type or "01",
        "TipoJornada": employee.work_shift_type or "01",
        "TipoRegimen": employee.regime_type or "02",
        "NumEmpleado": employee.code,
        "Departamento": employee.department or "General",
        "Puesto": employee.job_title or "Operativo",
        "RiesgoPuesto": employee.risk_class or "1",
        "PeriodicidadPago": period.periodicity or "04",
        "SalarioBaseCotApor": f"{receipt.daily_salary:.2f}",
        "SalarioDiarioIntegrado": f"{receipt.integrated_daily_salary:.2f}",
        "ClaveEntFed": "CMX"
    }
    if employee.bank_account_number:
        receptor_nom_attrs["Banco"] = "012"  # BBVA / Clave bancaria
        receptor_nom_attrs["CuentaBancaria"] = employee.bank_account_number

    ET.SubElement(nomina_el, f"{{{ns_nomina12}}}Receptor", receptor_nom_attrs)

    # Separar Percepciones y Deducciones de los items
    perceptions = [item for item in receipt.items if item.item_type == "PERCEPCION"]
    deductions = [item for item in receipt.items if item.item_type == "DEDUCCION"]

    # Percepciones Nómina
    if perceptions:
        total_gravado = sum(p.taxed_amount for p in perceptions)
        total_exento = sum(p.exempt_amount for p in perceptions)
        percep_el = ET.SubElement(
            nomina_el,
            f"{{{ns_nomina12}}}Percepciones",
            {
                "TotalSueldos": f"{total_gravado + total_exento:.2f}",
                "TotalGravado": f"{total_gravado:.2f}",
                "TotalExento": f"{total_exento:.2f}"
            }
        )
        for p in perceptions:
            ET.SubElement(
                percep_el,
                f"{{{ns_nomina12}}}Percepcion",
                {
                    "TipoPercepcion": p.sat_code,
                    "Clave": p.concept_key,
                    "Concepto": p.description,
                    "ImporteGravado": f"{p.taxed_amount:.2f}",
                    "ImporteExento": f"{p.exempt_amount:.2f}"
                }
            )

    # Deducciones Nómina
    if deductions:
        isr_items = [d for d in deductions if d.sat_code == "002"]
        other_deductions = [d for d in deductions if d.sat_code != "002"]

        total_isr = sum(d.total_amount for d in isr_items)
        total_otras = sum(d.total_amount for d in other_deductions)

        deduc_attrs = {}
        if total_otras > 0:
            deduc_attrs["TotalOtrasDeducciones"] = f"{total_otras:.2f}"
        if total_isr > 0:
            deduc_attrs["TotalImpuestosRetenidos"] = f"{total_isr:.2f}"

        deduc_el = ET.SubElement(nomina_el, f"{{{ns_nomina12}}}Deducciones", deduc_attrs)
        for d in deductions:
            ET.SubElement(
                deduc_el,
                f"{{{ns_nomina12}}}Deduccion",
                {
                    "TipoDeduccion": d.sat_code,
                    "Clave": d.concept_key,
                    "Concepto": d.description,
                    "Importe": f"{d.total_amount:.2f}"
                }
            )

    # 6. Construir Cadena Original y Firma Criptográfica
    cadena = build_cadena_original_nomina_12(
        version="4.0",
        serie=serie,
        folio=folio,
        fecha=now_utc,
        forma_pago="99",
        subtotal=subtotal_str,
        descuento=descuento_str,
        moneda="MXN",
        total=total_str,
        tipo_comprobante="N",
        exportacion="01",
        metodo_pago="PUE",
        lugar_expedicion=branch_zip or "06000",
        emisor_rfc=tenant.rfc,
        emisor_nombre=tenant.legal_name,
        emisor_regimen=getattr(tenant, "fiscal_regime_code", "601") or "601",
        receptor_rfc=employee.rfc,
        receptor_nombre=f"{employee.first_name} {employee.last_name}",
        receptor_domicilio=employee.zip_code or branch_zip or "06000",
        receptor_regimen="605",
        receptor_uso_cfdi="CN01",
        nomina_version="1.2",
        tipo_nomina=period.payroll_type or "O",
        fecha_pago=period.payment_date.strftime("%Y-%m-%d"),
        fecha_inicial=period.start_date.strftime("%Y-%m-%d"),
        fecha_final=period.end_date.strftime("%Y-%m-%d"),
        num_dias_pagados=f"{receipt.days_paid:.3f}",
        total_percepciones=subtotal_str,
        total_deducciones=descuento_str,
        curp=employee.curp,
        nss=employee.nss
    )

    sello = sign_cadena_original(cadena, csd.encrypted_private_key)
    root.set("Sello", sello)

    xml_str = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
    return xml_str, cadena, sello

