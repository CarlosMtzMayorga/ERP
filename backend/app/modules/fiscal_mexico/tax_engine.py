from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List


def quantize_2(val: Decimal) -> Decimal:
    """Redondeo canónico a 2 decimales para totales y CFDI XML (SAT Anexo 20)."""
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def quantize_4(val: Decimal) -> Decimal:
    """Precisión a 4 decimales para costos e importes intermedios."""
    return val.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def calculate_item_taxes(
    quantity: Decimal,
    unit_price: Decimal,
    discount_rate: Decimal = Decimal("0.0000"),
    vat_rate: Decimal = Decimal("0.1600"),
    ieps_rate: Decimal = Decimal("0.0000"),
    retention_vat_rate: Decimal = Decimal("0.0000"),
    retention_isr_rate: Decimal = Decimal("0.0000"),
    sat_objeto_imp: str = "02"
) -> Dict[str, Decimal]:
    """
    Motor de Cálculo Fiscal por Partida según lineamientos del SAT (CFDI 4.0).
    Maneja alta precisión interna (hasta 6 decimales) y redondeo conforme a Anexo 20.
    """
    gross_amount = quantity * unit_price
    discount_amount = gross_amount * discount_rate
    base_amount = gross_amount - discount_amount

    vat_amount = Decimal("0.0000")
    ieps_amount = Decimal("0.0000")
    retention_vat_amount = Decimal("0.0000")
    retention_isr_amount = Decimal("0.0000")

    if sat_objeto_imp == "02":  # Sí objeto de impuesto
        if vat_rate > 0:
            vat_amount = base_amount * vat_rate
        if ieps_rate > 0:
            ieps_amount = base_amount * ieps_rate
        if retention_vat_rate > 0:
            retention_vat_amount = base_amount * retention_vat_rate
        if retention_isr_rate > 0:
            retention_isr_amount = base_amount * retention_isr_rate

    line_total = base_amount + vat_amount + ieps_amount - retention_vat_amount - retention_isr_amount

    return {
        "gross_amount": quantize_4(gross_amount),
        "discount_amount": quantize_4(discount_amount),
        "subtotal": quantize_4(base_amount),
        "vat_amount": quantize_4(vat_amount),
        "ieps_amount": quantize_4(ieps_amount),
        "retention_vat_amount": quantize_4(retention_vat_amount),
        "retention_isr_amount": quantize_4(retention_isr_amount),
        "total": quantize_4(line_total)
    }


def calculate_document_totals(items_data: List[Dict[str, Any]]) -> Dict[str, Decimal]:
    """
    Consolida la liquidación impositiva y financiera de un comprobante completo.
    """
    subtotal = Decimal("0.0000")
    discount_total = Decimal("0.0000")
    tax_iva_total = Decimal("0.0000")
    tax_ieps_total = Decimal("0.0000")
    retention_iva_total = Decimal("0.0000")
    retention_isr_total = Decimal("0.0000")

    for item in items_data:
        subtotal += item["subtotal"]
        discount_total += item.get("discount_amount", Decimal("0.0000"))
        tax_iva_total += item.get("vat_amount", Decimal("0.0000"))
        tax_ieps_total += item.get("ieps_amount", Decimal("0.0000"))
        retention_iva_total += item.get("retention_vat_amount", Decimal("0.0000"))
        retention_isr_total += item.get("retention_isr_amount", Decimal("0.0000"))

    total = subtotal + tax_iva_total + tax_ieps_total - retention_iva_total - retention_isr_total

    return {
        "subtotal": quantize_2(subtotal),
        "discount_total": quantize_2(discount_total),
        "tax_iva_total": quantize_2(tax_iva_total),
        "tax_ieps_total": quantize_2(tax_ieps_total),
        "retention_iva_total": quantize_2(retention_iva_total),
        "retention_isr_total": quantize_2(retention_isr_total),
        "total": quantize_2(total)
    }
