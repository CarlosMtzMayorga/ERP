import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, List, Optional, Union
from fastapi import HTTPException, status


def _clean_tag(tag: str) -> str:
    """Removes XML namespace prefix like {http://www.sat.gob.mx/cfd/4}Tag."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _to_decimal(val: Optional[str], default: Decimal = Decimal("0.0000")) -> Decimal:
    if val is None or val.strip() == "":
        return default
    try:
        return Decimal(val.strip())
    except (InvalidOperation, ValueError):
        return default


def parse_cfdi_40_xml(xml_content: Union[str, bytes]) -> Dict[str, Any]:
    """
    Parsea de forma estricta y segura un archivo XML de CFDI 4.0 emitido por un proveedor.
    Extrae la metadata fiscal, datos del emisor/receptor, conceptos e impuestos desglosados.
    """
    try:
        if isinstance(xml_content, str):
            xml_bytes = xml_content.encode("utf-8")
        else:
            xml_bytes = xml_content
        root = ET.fromstring(xml_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Estructura XML inválida o corrupta: {str(e)}"
        )

    root_tag = _clean_tag(root.tag)
    if root_tag != "Comprobante":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El archivo XML no corresponde a un CFDI válido (raíz: {root_tag})."
        )

    # Atributos generales del Comprobante
    version = root.attrib.get("Version", "4.0")
    serie = root.attrib.get("Serie")
    folio = root.attrib.get("Folio")
    fecha = root.attrib.get("Fecha", "")
    forma_pago = root.attrib.get("FormaPago")
    metodo_pago = root.attrib.get("MetodoPago")
    moneda = root.attrib.get("Moneda", "MXN")
    tipo_cambio = _to_decimal(root.attrib.get("TipoCambio"), Decimal("1.0000"))
    subtotal = _to_decimal(root.attrib.get("SubTotal"))
    descuento = _to_decimal(root.attrib.get("Descuento"))
    total = _to_decimal(root.attrib.get("Total"))
    tipo_comprobante = root.attrib.get("TipoDeComprobante", "I")

    emisor_data = {"rfc": "", "nombre": "", "regimen": ""}
    receptor_data = {"rfc": "", "nombre": "", "uso_cfdi": ""}
    uuid_timbre: Optional[str] = None
    fecha_timbrado: Optional[str] = None

    concepts: List[Dict[str, Any]] = []

    total_iva = Decimal("0.0000")
    total_ieps = Decimal("0.0000")
    total_ret_iva = Decimal("0.0000")
    total_ret_isr = Decimal("0.0000")

    for child in root:
        child_tag = _clean_tag(child.tag)

        if child_tag == "Emisor":
            emisor_data["rfc"] = child.attrib.get("Rfc", "").strip().upper()
            emisor_data["nombre"] = child.attrib.get("Nombre", "").strip()
            emisor_data["regimen"] = child.attrib.get("RegimenFiscal", "").strip()

        elif child_tag == "Receptor":
            receptor_data["rfc"] = child.attrib.get("Rfc", "").strip().upper()
            receptor_data["nombre"] = child.attrib.get("Nombre", "").strip()
            receptor_data["uso_cfdi"] = child.attrib.get("UsoCFDI", "").strip()

        elif child_tag == "Conceptos":
            for concepto in child:
                if _clean_tag(concepto.tag) == "Concepto":
                    c_clave_prod = concepto.attrib.get("ClaveProdServ", "")
                    c_no_ident = concepto.attrib.get("NoIdentificacion")
                    c_cantidad = _to_decimal(concepto.attrib.get("Cantidad"), Decimal("1.0000"))
                    c_clave_unidad = concepto.attrib.get("ClaveUnidad", "H87")
                    c_unidad = concepto.attrib.get("Unidad")
                    c_descripcion = concepto.attrib.get("Descripcion", "")
                    c_valor_unit = _to_decimal(concepto.attrib.get("ValorUnitario"))
                    c_importe = _to_decimal(concepto.attrib.get("Importe"))
                    c_descuento = _to_decimal(concepto.attrib.get("Descuento"))
                    c_objeto_imp = concepto.attrib.get("ObjetoImp", "02")

                    c_iva_importe = Decimal("0.0000")
                    c_iva_tasa = Decimal("0.1600")
                    c_ieps_importe = Decimal("0.0000")
                    c_ret_iva = Decimal("0.0000")
                    c_ret_isr = Decimal("0.0000")

                    # Impuestos por concepto
                    for c_sub in concepto:
                        if _clean_tag(c_sub.tag) == "Impuestos":
                            for imp_group in c_sub:
                                group_tag = _clean_tag(imp_group.tag)
                                if group_tag == "Traslados":
                                    for tras in imp_group:
                                        if _clean_tag(tras.tag) == "Traslado":
                                            imp_tipo = tras.attrib.get("Impuesto", "002")
                                            tasa = _to_decimal(tras.attrib.get("TasaOCuota"), Decimal("0.1600"))
                                            imp_val = _to_decimal(tras.attrib.get("Importe"))
                                            if imp_tipo == "002":  # IVA
                                                c_iva_importe += imp_val
                                                c_iva_tasa = tasa
                                            elif imp_tipo == "003":  # IEPS
                                                c_ieps_importe += imp_val

                                elif group_tag == "Retenciones":
                                    for ret in imp_group:
                                        if _clean_tag(ret.tag) == "Retencion":
                                            imp_tipo = ret.attrib.get("Impuesto", "002")
                                            imp_val = _to_decimal(ret.attrib.get("Importe"))
                                            if imp_tipo == "002":  # Retención IVA
                                                c_ret_iva += imp_val
                                            elif imp_tipo == "001":  # Retención ISR
                                                c_ret_isr += imp_val

                    total_iva += c_iva_importe
                    total_ieps += c_ieps_importe
                    total_ret_iva += c_ret_iva
                    total_ret_isr += c_ret_isr

                    concepts.append({
                        "clave_prod_serv": c_clave_prod,
                        "no_identificacion": c_no_ident,
                        "cantidad": c_cantidad,
                        "clave_unidad": c_clave_unidad,
                        "unidad": c_unidad,
                        "descripcion": c_descripcion,
                        "valor_unitario": c_valor_unit,
                        "importe": c_importe,
                        "descuento": c_descuento,
                        "objeto_imp": c_objeto_imp,
                        "iva_importe": c_iva_importe,
                        "iva_tasa": c_iva_tasa,
                        "ieps_importe": c_ieps_importe,
                        "retencion_iva": c_ret_iva,
                        "retencion_isr": c_ret_isr,
                    })

        elif child_tag == "Impuestos":
            # Si el XML tiene totales globales explícitos de impuestos
            total_tras = _to_decimal(child.attrib.get("TotalImpuestosTrasladados"))
            total_ret = _to_decimal(child.attrib.get("TotalImpuestosRetenidos"))
            if total_tras > 0:
                total_iva = total_tras
            if total_ret > 0:
                total_ret_iva = total_ret

        elif child_tag == "Complemento":
            for comp_child in child:
                if _clean_tag(comp_child.tag) == "TimbreFiscalDigital":
                    uuid_timbre = comp_child.attrib.get("UUID")
                    fecha_timbrado = comp_child.attrib.get("FechaTimbrado")

    if not uuid_timbre:
        # Algunos archivos XML sin timbrar o borradores
        uuid_timbre = ""

    return {
        "version": version,
        "uuid": uuid_timbre,
        "serie": serie,
        "folio": folio,
        "fecha": fecha,
        "fecha_timbrado": fecha_timbrado,
        "forma_pago": forma_pago,
        "metodo_pago": metodo_pago,
        "moneda": moneda,
        "tipo_cambio": tipo_cambio,
        "subtotal": subtotal,
        "descuento": descuento,
        "total": total,
        "tipo_comprobante": tipo_comprobante,
        "emisor_rfc": emisor_data["rfc"],
        "emisor_nombre": emisor_data["nombre"],
        "emisor_regimen": emisor_data["regimen"],
        "receptor_rfc": receptor_data["rfc"],
        "receptor_nombre": receptor_data["nombre"],
        "total_iva": total_iva,
        "total_ieps": total_ieps,
        "total_ret_iva": total_ret_iva,
        "total_ret_isr": total_ret_isr,
        "total_retenciones": total_ret_iva + total_ret_isr,
        "concepts": concepts,
    }

