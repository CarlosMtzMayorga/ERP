from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Tuple


# UMA (Unidad de Medida y Actualización) de Referencia Nacional
UMA_VALUE = Decimal("108.57")

# Tabla Oficial de ISR Art. 96 LISR (Tarifa Quincenal Oficial)
# Formato: (Límite Inferior, Límite Superior, Cuota Fija, Porcentaje sobre Excedente)
ISR_QUINCENAL_TABLE: List[Tuple[Decimal, Decimal, Decimal, Decimal]] = [
    (Decimal("0.01"), Decimal("373.20"), Decimal("0.00"), Decimal("0.0192")),
    (Decimal("373.21"), Decimal("3167.70"), Decimal("7.17"), Decimal("0.0640")),
    (Decimal("3167.71"), Decimal("5567.10"), Decimal("186.02"), Decimal("0.1088")),
    (Decimal("5567.11"), Decimal("6471.45"), Decimal("447.11"), Decimal("0.1600")),
    (Decimal("6471.46"), Decimal("7748.55"), Decimal("591.79"), Decimal("0.1792")),
    (Decimal("7748.56"), Decimal("15627.15"), Decimal("820.73"), Decimal("0.2136")),
    (Decimal("15627.16"), Decimal("24629.70"), Decimal("2503.73"), Decimal("0.2352")),
    (Decimal("24629.71"), Decimal("47025.45"), Decimal("4621.13"), Decimal("0.3000")),
    (Decimal("47025.46"), Decimal("62700.60"), Decimal("11339.85"), Decimal("0.3200")),
    (Decimal("62700.61"), Decimal("188101.80"), Decimal("16355.90"), Decimal("0.3400")),
    (Decimal("188101.81"), Decimal("999999999.99"), Decimal("58992.31"), Decimal("0.3500")),
]


def quantize_2(val: Decimal) -> Decimal:
    """Redondeo canónico a 2 decimales para moneda nacional y CFDI."""
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_isr_retention(taxable_base: Decimal, days: Decimal = Decimal("15.00")) -> Decimal:
    """
    Cálculo de retención de ISR conforme al Artículo 96 de la Ley del Impuesto Sobre la Renta (LISR).
    Normaliza la base gravable a 15 días para aplicar la tarifa quincenal y escala el impuesto de forma proporcional.
    """
    if taxable_base <= Decimal("0.00"):
        return Decimal("0.00")

    days_dec = Decimal(str(days))
    if days_dec <= Decimal("0.00"):
        days_dec = Decimal("15.00")

    # Escalamiento de la base gravable a escala quincenal estándar (15 días)
    scaling_factor = Decimal("15.00") / days_dec
    normalized_base = taxable_base * scaling_factor

    cuota_fija = Decimal("0.00")
    porcentaje = Decimal("0.00")
    limite_inferior = Decimal("0.00")

    matched = False
    for inf, sup, cuota, pct in ISR_QUINCENAL_TABLE:
        if inf <= normalized_base <= sup:
            limite_inferior = inf
            cuota_fija = cuota
            porcentaje = pct
            matched = True
            break

    if not matched:
        # En caso de superar el rango máximo
        inf, sup, cuota, pct = ISR_QUINCENAL_TABLE[-1]
        limite_inferior = inf
        cuota_fija = cuota
        porcentaje = pct

    excedente = normalized_base - limite_inferior
    impuesto_marginal = excedente * porcentaje
    isr_quincenal = cuota_fija + impuesto_marginal

    # Escalar de vuelta a los días reales trabajados
    isr_real = isr_quincenal / scaling_factor
    return quantize_2(max(Decimal("0.00"), isr_real))


def calculate_imss_employee_retention(integrated_daily_salary: Decimal, days: Decimal = Decimal("15.00")) -> Decimal:
    """
    Cálculo de la Cuota Obrera del IMSS conforme a la Ley del Seguro Social (LSS):
    Ramas obreras:
    - Prestaciones en dinero: 0.25%
    - Gastos médicos pensionados: 0.375%
    - Invalidez y vida: 0.625%
    - Cesantía en edad avanzada y vejez: 1.125%
      Suma tasa fija: 2.375% sobre SDI (topado a 25 UMAs).
    - Excedente de 3 UMA: 0.40% sobre el excedente (SDI - 3*UMA) si SDI > 3*UMA.
    """
    sdi = Decimal(str(integrated_daily_salary))
    days_dec = Decimal(str(days))
    if sdi <= Decimal("0.00") or days_dec <= Decimal("0.00"):
        return Decimal("0.00")

    # Tope máximo de cotización: 25 veces la UMA vigente
    max_cap = Decimal("25") * UMA_VALUE
    sdi_capped = min(sdi, max_cap)

    # 1. Tasa fija de ramas ordinarias (2.375%)
    fixed_rate = Decimal("0.02375")
    cuota_fija_diaria = sdi_capped * fixed_rate

    # 2. Excedente de 3 UMAs
    threshold_3_uma = Decimal("3") * UMA_VALUE
    cuota_excedente_diaria = Decimal("0.0000")
    if sdi_capped > threshold_3_uma:
        excedente = sdi_capped - threshold_3_uma
        cuota_excedente_diaria = excedente * Decimal("0.0040")  # 0.40%

    cuota_diaria_total = cuota_fija_diaria + cuota_excedente_diaria
    cuota_periodo = cuota_diaria_total * days_dec

    return quantize_2(cuota_periodo)


def calculate_imss_employer_cost(integrated_daily_salary: Decimal, days: Decimal = Decimal("15.00"), risk_class: str = "1") -> Decimal:
    """
    Cálculo aproximado de la Carga Social Patronal IMSS/Infonavit para análisis de costos en RRHH.
    Abarca Cuota Fija (20.40% UMA), Excedente patronal, Prestaciones en dinero, Invalidez, Guardería, Riesgo de Trabajo y Retiro/Cesantía.
    """
    sdi = Decimal(str(integrated_daily_salary))
    days_dec = Decimal(str(days))
    if sdi <= Decimal("0.00") or days_dec <= Decimal("0.00"):
        return Decimal("0.00")

    max_cap = Decimal("25") * UMA_VALUE
    sdi_capped = min(sdi, max_cap)

    # Factores patronales base (~24.5% + Cuota fija)
    cuota_fija_diaria = UMA_VALUE * Decimal("0.2040")
    
    # Riesgo de trabajo según clase
    risk_rates = {
        "1": Decimal("0.0054355"),
        "2": Decimal("0.0113065"),
        "3": Decimal("0.0259840"),
        "4": Decimal("0.0465325"),
        "5": Decimal("0.0758875"),
    }
    risk_rate = risk_rates.get(str(risk_class), Decimal("0.0054355"))

    # Ramas patronales sobre SDI (Dinero: 0.70%, Pensionados: 1.05%, Invalidez: 1.75%, Guarderías: 1.00%, Retiro: 2.00%, Cesantía: 3.15%, Infonavit: 5.00%)
    percentage_branches = Decimal("0.0070") + Decimal("0.0105") + Decimal("0.0175") + Decimal("0.0100") + Decimal("0.0200") + Decimal("0.0315") + Decimal("0.0500") + risk_rate
    ramas_diarias = sdi_capped * percentage_branches

    # Excedente patronal (1.10%)
    threshold_3_uma = Decimal("3") * UMA_VALUE
    excedente_patronal = Decimal("0.0000")
    if sdi_capped > threshold_3_uma:
        excedente_patronal = (sdi_capped - threshold_3_uma) * Decimal("0.0110")

    costo_diario = cuota_fija_diaria + ramas_diarias + excedente_patronal
    return quantize_2(costo_diario * days_dec)


def calculate_employee_payroll(
    daily_salary: Decimal,
    integrated_daily_salary: Decimal,
    period_days: Decimal = Decimal("15.00"),
    incidents: List[Dict[str, Any]] = None,
    risk_class: str = "1"
) -> Dict[str, Any]:
    """
    Ejecuta la liquidación de percepciones, deducciones estatutarias y neto a pagar
    para un empleado en un periodo de nómina específico.
    """
    if incidents is None:
        incidents = []

    ds = Decimal(str(daily_salary))
    sdi = Decimal(str(integrated_daily_salary))
    total_days = Decimal(str(period_days))

    # 1. Procesamiento de Incidencias
    faltas_dias = Decimal("0.00")
    incapacidad_dias = Decimal("0.00")
    horas_dobles = Decimal("0.00")
    horas_triples = Decimal("0.00")
    bonos_total = Decimal("0.00")
    comisiones_total = Decimal("0.00")

    for inc in incidents:
        itype = inc.get("incident_type", "").upper()
        qty = Decimal(str(inc.get("quantity", 0)))
        amt = Decimal(str(inc.get("amount", 0)))

        if itype == "FALTA_INJUSTIFICADA":
            faltas_dias += qty
        elif itype in ("INCAPACIDAD", "INCAPACIDAD_ENFERMEDAD", "INCAPACIDAD_RIESGO_TRABAJO"):
            incapacidad_dias += qty
        elif itype == "PERMISO_SIN_GOCE":
            faltas_dias += qty
        elif itype == "HORAS_EXTRAS_DOBLES":
            horas_dobles += qty
        elif itype == "HORAS_EXTRAS_TRIPLES":
            horas_triples += qty
        elif itype == "BONO":
            bonos_total += amt
        elif itype == "COMISION":
            comisiones_total += amt

    # Días efectivamente trabajados y pagados
    dias_no_laborados = faltas_dias + incapacidad_dias
    dias_pagados = max(Decimal("0.00"), total_days - dias_no_laborados)
    dias_cotizados_imss = max(Decimal("0.00"), total_days - faltas_dias)  # Incapacidades descuentan cuotas pero con rama especial; aquí días cotizados reales

    # 2. Percepciones
    # Sueldo Base Ordinario (SAT: 001)
    sueldo_base = quantize_2(dias_pagados * ds)

    perceptions_items: List[Dict[str, Any]] = []
    if sueldo_base > Decimal("0.00"):
        perceptions_items.append({
            "item_type": "PERCEPCION",
            "sat_code": "001",
            "concept_key": "P001",
            "description": "Sueldo Ordinario",
            "taxed_amount": sueldo_base,
            "exempt_amount": Decimal("0.00"),
            "total_amount": sueldo_base
        })

    # Horas Extras Dobles (SAT: 019)
    # LFT: Primeras 9 horas semanales pagadas al 200%. 50% exento hasta 5 UMAs quincenal.
    horas_dobles_monto = Decimal("0.00")
    if horas_dobles > Decimal("0.00"):
        valor_hora_base = ds / Decimal("8.00")
        horas_dobles_monto = quantize_2(valor_hora_base * Decimal("2.00") * horas_dobles)
        # Exención 50% topada a 5 UMAs
        tope_exento = Decimal("5") * UMA_VALUE
        mitad = quantize_2(horas_dobles_monto / Decimal("2.00"))
        exento = min(mitad, tope_exento)
        gravado = horas_dobles_monto - exento
        perceptions_items.append({
            "item_type": "PERCEPCION",
            "sat_code": "019",
            "concept_key": "P019_2",
            "description": f"Horas Extras Dobles ({horas_dobles} hrs)",
            "taxed_amount": gravado,
            "exempt_amount": exento,
            "total_amount": horas_dobles_monto
        })

    # Horas Extras Triples (SAT: 019)
    # 100% gravadas
    horas_triples_monto = Decimal("0.00")
    if horas_triples > Decimal("0.00"):
        valor_hora_base = ds / Decimal("8.00")
        horas_triples_monto = quantize_2(valor_hora_base * Decimal("3.00") * horas_triples)
        perceptions_items.append({
            "item_type": "PERCEPCION",
            "sat_code": "019",
            "concept_key": "P019_3",
            "description": f"Horas Extras Triples ({horas_triples} hrs)",
            "taxed_amount": horas_triples_monto,
            "exempt_amount": Decimal("0.00"),
            "total_amount": horas_triples_monto
        })

    # Bonos e Incentivos (SAT: 038)
    if bonos_total > Decimal("0.00"):
        perceptions_items.append({
            "item_type": "PERCEPCION",
            "sat_code": "038",
            "concept_key": "P038",
            "description": "Bono por Productividad y Asistencia",
            "taxed_amount": quantize_2(bonos_total),
            "exempt_amount": Decimal("0.00"),
            "total_amount": quantize_2(bonos_total)
        })

    # Comisiones (SAT: 028)
    if comisiones_total > Decimal("0.00"):
        perceptions_items.append({
            "item_type": "PERCEPCION",
            "sat_code": "028",
            "concept_key": "P028",
            "description": "Comisiones sobre Ventas",
            "taxed_amount": quantize_2(comisiones_total),
            "exempt_amount": Decimal("0.00"),
            "total_amount": quantize_2(comisiones_total)
        })

    # Totales de Percepciones
    total_gravado = sum(p["taxed_amount"] for p in perceptions_items)
    total_exento = sum(p["exempt_amount"] for p in perceptions_items)
    total_perceptions = quantize_2(total_gravado + total_exento)

    # 3. Deducciones Estatutarias
    deductions_items: List[Dict[str, Any]] = []

    # A) Retención de ISR (SAT: 002)
    isr_retention = calculate_isr_retention(total_gravado, days=dias_pagados)
    if isr_retention > Decimal("0.00"):
        deductions_items.append({
            "item_type": "DEDUCCION",
            "sat_code": "002",
            "concept_key": "D002",
            "description": "ISR Retenido Art. 96 LISR",
            "taxed_amount": Decimal("0.00"),
            "exempt_amount": Decimal("0.00"),
            "total_amount": isr_retention
        })

    # B) Seguridad Social IMSS Cuota Obrera (SAT: 001)
    imss_employee = calculate_imss_employee_retention(sdi, days=dias_cotizados_imss)
    if imss_employee > Decimal("0.00"):
        deductions_items.append({
            "item_type": "DEDUCCION",
            "sat_code": "001",
            "concept_key": "D001",
            "description": "Seguridad Social IMSS (Cuota Obrera)",
            "taxed_amount": Decimal("0.00"),
            "exempt_amount": Decimal("0.00"),
            "total_amount": imss_employee
        })

    total_deductions = quantize_2(sum(d["total_amount"] for d in deductions_items))

    # 4. Neto a Pagar
    total_net = quantize_2(max(Decimal("0.00"), total_perceptions - total_deductions))

    # Carga Patronal (Informativa para RRHH)
    imss_employer = calculate_imss_employer_cost(sdi, days=dias_cotizados_imss, risk_class=risk_class)

    return {
        "days_worked": dias_pagados,
        "days_paid": dias_pagados,
        "base_salary": sueldo_base,
        "total_perceptions": total_perceptions,
        "total_deductions": total_deductions,
        "total_net": total_net,
        "total_taxed": total_gravado,
        "total_exempt": total_exento,
        "isr_retention": isr_retention,
        "imss_employee_retention": imss_employee,
        "imss_employer_cost": imss_employer,
        "items": perceptions_items + deductions_items
    }
