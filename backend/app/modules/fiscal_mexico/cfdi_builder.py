import uuid
import base64
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, List, Tuple
from xml.etree import ElementTree as ET
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from app.modules.fiscal_mexico.csd_service import get_decrypted_private_key
from app.modules.fiscal_mexico.tax_engine import quantize_2


def build_cadena_original_40(
    version: str,
    serie: str,
    folio: str,
    fecha: str,
    forma_pago: str,
    subtotal: str,
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
    conceptos: List[Dict[str, Any]],
    impuestos: Dict[str, Any]
) -> str:
    """
    Construye la Cadena Original para CFDI 4.0 conforme a la secuencia normativa del SAT.
    Formato: ||Version|Serie|Folio|Fecha|...||
    """
    parts = [
        version,
        serie,
        folio,
        fecha,
        forma_pago,
        subtotal,
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
    ]

    # Conceptos
    for c in conceptos:
        parts.extend([
            c["ClaveProdServ"],
            c["Cantidad"],
            c["ClaveUnidad"],
            c["Descripcion"],
            c["ValorUnitario"],
            c["Importe"],
            c["ObjetoImp"]
        ])

    # Cierre con doble pipe conforme a SAT Anexo 20
    cadena = "||" + "|".join(parts) + "||"
    return cadena


def sign_cadena_original(cadena_original: str, encrypted_private_key: str) -> str:
    """
    Genera el Sello Digital del Emisor utilizando SHA-256 with RSA (PKCS#1 v1.5).
    """
    private_key = get_decrypted_private_key(encrypted_private_key)
    signature = private_key.sign(
        cadena_original.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    return base64.b64encode(signature).decode("utf-8")


def generate_cfdi_xml(
    document: Any,
    tenant: Any,
    customer: Any,
    csd: Any
) -> Tuple[str, str, str]:
    """
    Genera el archivo XML CFDI 4.0 sellado criptográficamente en memoria.
    Retorna: (xml_str, cadena_original, sello)
    """
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    # Extraer base64 del certificado público CSD limpio
    cert_clean = "".join([
        line.strip() for line in csd.certificate_pem.splitlines()
        if not line.startswith("-----")
    ])

    conceptos_data = []
    for item in document.items:
        conceptos_data.append({
            "ClaveProdServ": item.sat_clave_prod_serv,
            "Cantidad": f"{item.quantity:.2f}",
            "ClaveUnidad": item.sat_clave_unidad,
            "Descripcion": item.description,
            "ValorUnitario": f"{item.unit_price:.2f}",
            "Importe": f"{item.subtotal:.2f}",
            "ObjetoImp": item.sat_objeto_imp,
        })

    # Cadena Original
    cadena = build_cadena_original_40(
        version="4.0",
        serie=document.serie,
        folio=str(document.folio),
        fecha=now_str,
        forma_pago=document.payment_form,
        subtotal=f"{quantize_2(document.subtotal):.2f}",
        moneda=document.currency.code if document.currency else "MXN",
        total=f"{quantize_2(document.total):.2f}",
        tipo_comprobante="I",  # Ingreso
        exportacion="01",       # No aplica
        metodo_pago=document.payment_method,
        lugar_expedicion=tenant.zip_code,
        emisor_rfc=tenant.rfc,
        emisor_nombre=tenant.legal_name,
        emisor_regimen=tenant.fiscal_regime_code,
        receptor_rfc=customer.rfc,
        receptor_nombre=customer.legal_name,
        receptor_domicilio=customer.zip_code,
        receptor_regimen=customer.fiscal_regime_code,
        receptor_uso_cfdi=document.cfdi_use,
        conceptos=conceptos_data,
        impuestos={}
    )

    # Firma con CSD
    sello = sign_cadena_original(cadena, csd.encrypted_private_key)

    # Construir Árbol XML CFDI 4.0
    ns_cfdi = "http://www.sat.gob.mx/cfd/4"
    ns_xsi = "http://www.w3.org/2001/XMLSchema-instance"
    
    ET.register_namespace("cfdi", ns_cfdi)
    ET.register_namespace("xsi", ns_xsi)

    root = ET.Element(
        f"{{{ns_cfdi}}}Comprobante",
        {
            f"{{{ns_xsi}}}schemaLocation": "http://www.sat.gob.mx/cfd/4 http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd",
            "Version": "4.0",
            "Serie": document.serie,
            "Folio": str(document.folio),
            "Fecha": now_str,
            "Sello": sello,
            "FormaPago": document.payment_form,
            "NoCertificado": csd.certificate_number,
            "Certificado": cert_clean,
            "SubTotal": f"{quantize_2(document.subtotal):.2f}",
            "Moneda": document.currency.code if document.currency else "MXN",
            "Total": f"{quantize_2(document.total):.2f}",
            "TipoDeComprobante": "I",
            "Exportacion": "01",
            "MetodoPago": document.payment_method,
            "LugarExpedicion": tenant.zip_code
        }
    )

    # Emisor
    ET.SubElement(
        root,
        f"{{{ns_cfdi}}}Emisor",
        {
            "Rfc": tenant.rfc,
            "Nombre": tenant.legal_name,
            "RegimenFiscal": tenant.fiscal_regime_code
        }
    )

    # Receptor
    ET.SubElement(
        root,
        f"{{{ns_cfdi}}}Receptor",
        {
            "Rfc": customer.rfc,
            "Nombre": customer.legal_name,
            "DomicilioFiscalReceptor": customer.zip_code,
            "RegimenFiscalReceptor": customer.fiscal_regime_code,
            "UsoCFDI": document.cfdi_use
        }
    )

    # Conceptos
    conceptos_el = ET.SubElement(root, f"{{{ns_cfdi}}}Conceptos")
    for item in document.items:
        c_el = ET.SubElement(
            conceptos_el,
            f"{{{ns_cfdi}}}Concepto",
            {
                "ClaveProdServ": item.sat_clave_prod_serv,
                "Cantidad": f"{item.quantity:.2f}",
                "ClaveUnidad": item.sat_clave_unidad,
                "Unidad": item.unit_name,
                "Descripcion": item.description,
                "ValorUnitario": f"{item.unit_price:.2f}",
                "Importe": f"{quantize_2(item.subtotal):.2f}",
                "ObjetoImp": item.sat_objeto_imp
            }
        )
        if item.sat_objeto_imp == "02":
            imp_c = ET.SubElement(c_el, f"{{{ns_cfdi}}}Impuestos")
            tras_c = ET.SubElement(imp_c, f"{{{ns_cfdi}}}Traslados")
            ET.SubElement(
                tras_c,
                f"{{{ns_cfdi}}}Traslado",
                {
                    "Base": f"{quantize_2(item.subtotal):.2f}",
                    "Impuesto": "002",  # 002 = IVA
                    "TipoFactor": "Tasa",
                    "TasaOCuota": f"{item.vat_rate:.6f}",
                    "Importe": f"{quantize_2(item.vat_amount):.2f}"
                }
            )

    # Impuestos Globales
    if document.tax_iva_total > 0:
        imp_global = ET.SubElement(
            root,
            f"{{{ns_cfdi}}}Impuestos",
            {"TotalImpuestosTrasladados": f"{quantize_2(document.tax_iva_total):.2f}"}
        )
        tras_global = ET.SubElement(imp_global, f"{{{ns_cfdi}}}Traslados")
        ET.SubElement(
            tras_global,
            f"{{{ns_cfdi}}}Traslado",
            {
                "Base": f"{quantize_2(document.subtotal):.2f}",
                "Impuesto": "002",
                "TipoFactor": "Tasa",
                "TasaOCuota": "0.160000",
                "Importe": f"{quantize_2(document.tax_iva_total):.2f}"
            }
        )

    xml_str = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
    return xml_str, cadena, sello


def stamp_with_mock_pac(xml_cfdi_str: str, sello_cfd: str) -> Dict[str, Any]:
    """
    Simulación de Timbrado PAC (Proveedor Autorizado de Certificación SAT).
    Añade el TimbreFiscalDigital (TFD 1.1) al XML y devuelve el UUID oficial ficticio.
    """
    fiscal_uuid = str(uuid.uuid4()).upper()
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    no_certificado_sat = "30001000000500003416"
    sello_sat = base64.b64encode(f"MOCK_SAT_STAMP_{fiscal_uuid}".encode()).decode()

    # Parsear XML original para insertar cfdi:Complemento
    ns_cfdi = "http://www.sat.gob.mx/cfd/4"
    ns_tfd = "http://www.sat.gob.mx/TimbreFiscalDigital"
    ET.register_namespace("tfd", ns_tfd)

    root = ET.fromstring(xml_cfdi_str)
    complemento = ET.SubElement(root, f"{{{ns_cfdi}}}Complemento")

    ET.SubElement(
        complemento,
        f"{{{ns_tfd}}}TimbreFiscalDigital",
        {
            f"{{http://www.w3.org/2001/XMLSchema-instance}}schemaLocation": "http://www.sat.gob.mx/TimbreFiscalDigital http://www.sat.gob.mx/sitio_internet/cfd/TimbreFiscalDigital/TimbreFiscalDigitalv11.xsd",
            "Version": "1.1",
            "UUID": fiscal_uuid,
            "FechaTimbrado": now_utc,
            "RfcProvCertif": "FIN1203015JA",  # RFC PAC Autorizado
            "SelloCFD": sello_cfd,
            "NoCertificadoSAT": no_certificado_sat,
            "SelloSAT": sello_sat
        }
    )

    stamped_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")

    return {
        "uuid": fiscal_uuid,
        "stamped_at": now_utc,
        "no_certificado_sat": no_certificado_sat,
        "sello_sat": sello_sat,
        "stamped_xml": stamped_xml
    }
