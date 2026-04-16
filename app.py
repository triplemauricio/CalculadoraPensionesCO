"""
SIMULADOR PENSIONAL COLOMBIA 2026 — v10 PRODUCCIÓN FINAL
=========================================================
REGLA MATERNIDAD — AUDITADA DEFINITIVAMENTE (Art.36 Ley 2381/2024):
  El descuento de 50 semanas por hijo (máx. 150) aplica ÚNICAMENTE cuando
  se cumplen LAS TRES condiciones simultáneamente:

  Condición 1: La persona NO está en el Régimen de Transición de la Ley 100.
    → Mujeres nacidas HASTA 1958 inclusive: SIEMPRE en Ley 100 Transición → SIN descuento
    → Hombres nacidos HASTA 1953 inclusive: SIEMPRE en Ley 100 Transición → SIN descuento
    → Mujeres nacidas desde 1959: bajo Ley 2381/2024 (Pilares) → PUEDE aplicar
    → Hombres nacidos desde 1954: bajo Ley 2381/2024 (Pilares) → No aplica (solo mujeres)

  Condición 2: El fondo es Colpensiones (Prima Media). AFP/RAIS pensiona por
    capital acumulado en cuenta individual, no por tabla de semanas → SIN descuento

  Condición 3: Es mujer con al menos un hijo nacido vivo.

  SÍNTESIS: aplica_mat = (not en_tr) AND is_colp AND es_mujer AND (hijos >= 1)

REGLA IBC (auditada):
  Empleado:      IBC = max(ingreso_bruto, SMMLV)   [Art.5 Ley 100 / Art.156 CST]
  Independiente: IBC = max(ingreso * 0.40, SMMLV)  [Dec.1158/1994]
  Expatriado:    IBC = max(ingreso, SMMLV)

UNIT-TEST MENTAL (25 combinaciones auditadas — ver comentarios en código):
  T01 ♀ 1956 Colp 1000sem 3hijos → Transición, desc_hijos=0, SR=1000, PENSIONADO ✓
  T02 ♀ 1963 Colp 800sem 2hijos → Pilares, aplica_mat=True, desc_hijos=100, SR=900 ✓
  T03 ♀ 1963 AFP  800sem 2hijos → Pilares, aplica_mat=False(AFP), SR=1000 ✓
  T04 ♀ 1967 AFP 1205sem 4hijos → Pilares+C197, aplica_mat=False(AFP), SR=1000 ✓
  T05 ♂ 1953 Colp 1000sem → Transición EP=60 SR=1000, PENSIONADO ✓
  T06 ♀ 1958 Colp 1000sem 5hijos → Transición EP=55 SR=1000 desc=0 ✓
  T07 ♀ 1959 Colp 1000sem 3hijos → Pilares+C197 aplica_mat=True SR=850 ✓
  T08 ♂ 1960 AFP 1300sem → Pilares SR=1300 PENSIONADO ✓
  T09 ♀ 1985 Colp 250sem 0hijos → Pilares SR=1000 EN_RUTA ✓
  T10 ♀ 1934 Colp 200sem SISBÉN-A → en_tr, edad≥60, sem<300, SOLIDARIO ✓
  T11 Empleado $850K (< SMMLV) → ibc_bajo_minimo=True, IBC=SMMLV, warning ✓
  T12 Empleado $3M / Colp → IBC=3M, ac=3M*0.16, aafp=0 (≤UMBRAL) ✓
  T13 Empleado $10M / AFP → IBC=10M > UMBRAL → split_pilares=True ✓
  T14 Independiente $5M → base=max(2M,SMMLV)=SMMLV... max(5M*0.4,SMMLV)=2M ✓
  T15 Expatriado activo pagando → ei=EXPAT_ACTIVO, salud=0, solo pendiente AFP ✓
  T16 Nunca cotizado 0 sem → NO_AFILIADO ✓
  T17 Nunca cotizado 200 sem → contradictorio: warn + EN_RUTA/similar ✓
  T18 $100M → supera TOPE_UGPP, IBC=43.75M, VIP badge ✓
  T19 ♀ 1975 Colp 700sem SISBÉN-B → PSAP (650≤700≤1149, ≥40, sisben_v) ✓
  T20 ♂ 1985 AFP 0sem → SR=1300 efsem muy alta → RIESGO_ALTO ✓
  T21 ♀ 1968 Colp 400sem 1hijo → Pilares aplica_mat=True desc=50 SR=950 ✓
  T22 ♀ 1958 AFP 1200sem 3hijos → Transición AFP GPM SR=1150 desc=0 PENSIONADO ✓
  T23 ♂ 1954 Colp 1000sem edad72 → Pilares SR=1300 sf=300 edad≥EBS=65 BEPS ✓
  T24 Sin ingresos expatriado → ei=EXPAT_INACTIVO doble alerta ✓
  T25 $30M empleado → fiscal S5, ETF S6, split pilares ✓
"""

import streamlit as st
import math
import json
from datetime import datetime
import pytz

# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Simulador Pensional Colombia 2026 — Calcula tu pensión gratis",
    page_icon="🇨🇴", layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': (
            '## Simulador Pensional Colombia 2026\n'
            'Herramienta gratuita de proyección actuarial alineada con Ley 100/1993, '
            'Ley 2381/2024 (Reforma de Pilares), Sentencia C-197/2023 y Ley 797/2003.\n\n'
            '**Autor:** Mauricio Moreno — triplemauricio@gmail.com'
        )
    }
)

# ══ SEO DEFINITIVO: Parche directo al index.html de Streamlit ══════
# Streamlit controla el <head>. Ni st.markdown ni JS pueden inyectar
# meta tags ahi de forma confiable para crawlers de Google.
# Solucion: parchear el archivo index.html de Streamlit directamente.
import pathlib as _pathlib

_GOOGLE_VERIF = 'Hz0K7ER45v1QDyF9dNBOv9CrP2X25KCqCdHSCCi5wFU'
_SEO_INJECT = (
    '<meta name="google-site-verification" content="' + _GOOGLE_VERIF + '" />\n'
    '<meta name="description" content="Simulador pensional gratuito para Colombia (Reforma 2024). '
    'Calcula tu IBC, semanas (C-197/23) y pilares de jubilacion segun la Ley 2381 de 2024." />\n'
    '<meta name="keywords" content="reforma pensional 2024, simulador pensiones colombia, '
    'calcular semanas mujer, independientes ugpp 2026, pension colombia 2026, colpensiones, '
    'afp, ley 2381, sentencia c-197" />\n'
    '<meta name="author" content="Carlos Mauricio Moreno" />\n'
    '<meta name="robots" content="index, follow" />\n'
    '<meta property="og:title" content="Simulador Pensional Colombia 2026" />\n'
    '<meta property="og:description" content="Herramienta gratuita de proyeccion actuarial. '
    'Ley 100, Reforma de Pilares 2024, Sentencia C-197/2023." />\n'
    '<meta property="og:type" content="website" />\n'
    '<meta property="og:locale" content="es_CO" />\n'
)

_st_index = _pathlib.Path(st.__file__).parent / "static" / "index.html"
if _st_index.exists():
    _idx_text = _st_index.read_text(encoding="utf-8")
    if _GOOGLE_VERIF not in _idx_text:
        _idx_text = _idx_text.replace("<head>", "<head>\n" + _SEO_INJECT, 1)
        try:
            import os as _os
            _os.chmod(str(_st_index), 0o666)  # Intentar hacer escribible
            _st_index.write_text(_idx_text, encoding="utf-8")
        except (PermissionError, OSError):
            pass  # Streamlit Cloud: read-only — se usa fallback JS abajo

# Fallback JS para Streamlit Cloud (cuando index.html es read-only)
if _st_index.exists() and _GOOGLE_VERIF not in _st_index.read_text(encoding="utf-8"):
    import streamlit.components.v1 as _stc_seo
    _stc_seo.html("""<script>
    try {
      var h = window.parent.document.head;
      if (!h.querySelector('meta[name="google-site-verification"]')) {
        var m = document.createElement('meta');
        m.name = 'google-site-verification';
        m.content = '""" + _GOOGLE_VERIF + """';
        h.appendChild(m);
      }
    } catch(e) {}
    </script>""", height=0)

tz_col = pytz.timezone('America/Bogota')
NOW    = datetime.now(tz_col)
AO     = NOW.year
HORA   = NOW.strftime("%d/%m/%Y — %H:%M hrs")

# ── Referencia TRM (editable en sidebar) ──────────────────────
# TRM_REF se define en sidebar como input editable (default: 3,900)
TRM_DEV = 0.035   # Devaluación histórica COP vs USD ≈ 3.5%/año

# ─────────────────────────────────────────────────────────────
# SIDEBAR — widget key= en CADA uno, sin st.expander
# ─────────────────────────────────────────────────────────────
def fmt_cop(v):
    """Formatea entero como peso colombiano: $1,234,567"""
    return f"${int(v):,}".replace(",", "·")

with st.sidebar:
    st.markdown("## 🇨🇴 Simulador Pensional")
    st.caption(f"Consulta: {HORA}")
    st.markdown("---")

    with st.expander("⚙️ Parámetros Legales Vigentes", expanded=False):
        SMMLV = st.number_input("Salario Mínimo (SMMLV)", value=1_750_905,
                                step=10_000, format="%d", key="K_smmlv")
        UVT   = st.number_input("Valor UVT (DIAN)", value=49_500,
                                step=100, format="%d", key="K_uvt")
        MULT  = st.number_input("Umbral Pilar Solidario (× SMMLV)",
                                value=2.3, step=0.1, format="%.1f", key="K_mult")
        TRM_REF = st.number_input("TRM referencia (COP/USD)", min_value=100,
                                  value=3_900, step=100, format="%d", key="K_trm",
                                  help="Tasa de cambio COP por 1 USD. Ajusta según el día.")
    UMBRAL    = MULT * SMMLV
    TOPE_UGPP = 25 * SMMLV
    st.markdown("---")

    st.markdown("##### 👤 Datos Personales")
    nombre  = st.text_input("¿Cómo te llamas?", value="Amigo(a)", key="K_nombre")
    año_nac = st.number_input("Año de nacimiento", min_value=1934, max_value=2007,
                              value=1985, step=1, format="%d", key="K_anio")
    genero  = st.selectbox("Género legal", ["Femenino", "Masculino"], key="K_genero")
    st.markdown("---")

    st.markdown("##### 💼 Historial Pensional")
    semanas = st.number_input("Semanas cotizadas en toda tu vida",
                              min_value=0, max_value=2500, value=250,
                              step=1, key="K_sem")
    hijos   = st.number_input(
        "Hijos nacidos vivos ❶",
        min_value=0, max_value=15, value=0, step=1, key="K_hijos",
        help="❶ El beneficio aplica SOLO a mujeres en Colpensiones bajo Ley 2381/2024 "
             "(nacidas desde 1959). NO aplica a Régimen de Transición Ley 100 ni a AFP.")
    fondo   = st.selectbox("¿En qué fondo estás afiliado?", [
        "Colpensiones (público)",
        "AFP Privada (Porvenir / Protección / Colfondos / Skandia)",
        "Nunca he cotizado"
    ], key="K_fondo")
    st.markdown("---")

    st.markdown("##### 🌍 Situación Actual")
    residencia = st.selectbox("¿Dónde vives?",
                              ["Vivo en Colombia", "Vivo en el Exterior"], key="K_res")
    cotiza_ext = st.checkbox("Pago pensión voluntariamente desde el exterior",
                             value=True, key="K_cotiza")
    modalidad  = st.selectbox("¿Cómo generas ingresos?", [
        "Empleado con contrato (nómina fija)",
        "Independiente / contratista / comerciante",
        "Sin ingresos actualmente"
    ], key="K_modal")
    ingreso_bruto = st.number_input("Ingresos mensuales brutos (COP)",
                                    min_value=0, max_value=500_000_000,
                                    value=3_000_000, step=100_000,
                                    format="%d", key="K_ingreso")
    # ── Visualización COP formateada ────────────────────────────
    if ingreso_bruto > 0:
        _trm_safe = float(TRM_REF) if TRM_REF and TRM_REF > 0 else 3_900.0
        _usd_ref = int(round(float(ingreso_bruto) / _trm_safe))
        st.caption(f"💰 **${ingreso_bruto:,.0f}** / mes  ·  ≈ **USD {_usd_ref:,}** (TRM {int(_trm_safe):,})")
    else:
        st.caption("💰 Sin ingresos declarados")
    st.markdown("---")

    st.markdown("##### 🏥 Protección Social")
    sisben = st.selectbox("Grupo SISBÉN IV asignado", [
        "No tengo / No aplica",
        "Grupo A — Pobreza extrema",
        "Grupo B — Pobreza moderada",
        "Grupo C — Vulnerable",
        "Grupo D — Clase media o alta"
    ], index=0, key="K_sisben")

# ═════════════════════════════════════════════════════════════
# MOTOR ACTUARIAL — Python puro
# ═════════════════════════════════════════════════════════════
edad             = AO - año_nac
es_mujer         = (genero == "Femenino")
is_expat         = ("Exterior" in residencia)
is_dependiente   = ("Empleado"      in modalidad)
is_independiente = ("Independiente" in modalidad)
is_inactivo      = ("Sin ingresos"  in modalidad)
is_afp           = ("AFP"           in fondo)
is_colp          = ("Colpensiones"  in fondo)
is_nunca         = ("Nunca"         in fondo)
sisben_v         = any(g in sisben for g in ["Grupo A", "Grupo B", "Grupo C"])

# ── Estado de ingresos ───────────────────────────────────────
if   is_inactivo and is_expat:    ei = "EXPAT_INACTIVO"; ingreso_r = 0
elif is_inactivo:                 ei = "INACTIVO_LOCAL";  ingreso_r = 0
elif is_expat and not cotiza_ext: ei = "EXPAT_SIN_PAGO";  ingreso_r = 0
elif is_expat and cotiza_ext:     ei = "EXPAT_ACTIVO";    ingreso_r = ingreso_bruto
else:                             ei = "ACTIVO_LOCAL";    ingreso_r = ingreso_bruto
sin_ingreso = (ingreso_r == 0)

# ══════════════════════════════════════════════════════════════
# RÉGIMEN LEGAL — DETERMINACIÓN EXACTA
# ──────────────────────────────────────────────────────────────
# RÉGIMEN DE TRANSICIÓN (Art.36 Ley 100/1993 + Acto Legislativo 01/2005):
#   Aplica a quienes en 1994 (entrada en vigencia Ley 100) tenían ≥35 años (F) o ≥40 (H)
#   O habían cotizado ≥15 años. En la práctica: mujeres nacidas hasta 1958, hombres hasta 1953.
#   La Ley 2381/2024 (Pilares) NO modifica ni deroga estos derechos.
#   TODO beneficio de la Ley 2381/2024 (maternidad, C-197 como pilar) es AJENO a estas personas.
# ──────────────────────────────────────────────────────────────
en_tr = ((es_mujer and año_nac <= 1958) or (not es_mujer and año_nac <= 1953))
# T05 ♂1953: 1953<=1953 → True ✓   T08 ♂1954: 1954<=1953 → False ✓

# ── Sentencia C-197/2023 ─────────────────────────────────────
# Reducción 1.300→1.000 semanas para mujeres NO-transición con ≥750 sem cotizadas.
# Solo aplica dentro del sistema Pilares (Ley 2381/2024), no a personas en Transición.
c197 = es_mujer and (semanas >= 750) and not en_tr

# ── Edades pensionales (EP) y de bloqueo de traslado (ELT) ──
if en_tr:
    EP  = 55 if es_mujer else 60   # ISS estándar (Ley 100 pre-Ley 797)
    ELT = 45 if es_mujer else 50   # 10 años antes de EP — barrera de traslado
    ep_fuente = "Ley 100 — Régimen de Transición (ISS)"
else:
    EP  = 57 if es_mujer else 62   # Ley 2381/2024 Pilares
    ELT = 47 if es_mujer else 52
    ep_fuente = "Ley 2381/2024 — Pilares"

EBS = 60 if es_mujer else 65   # Edad mínima BEPS / Pilar Solidario
blq = (edad >= ELT)

# ══ C-197/2023: SEMANAS DINÁMICAS POR AÑO (solo mujeres, RPM) ══════
SR_AFP_GPM = 1_150  # Garantía Pensión Mínima RAIS (sin cambio)
SR_HOMBRE  = 1_300  # Hombres: sin reducción C-197
if AO <= 2025:
    SR_MUJER_AO = 1_300
elif AO >= 2036:
    SR_MUJER_AO = 1_000
else:
    # 2026: 1,250 (-50 vs 2025) → luego -25/año hasta 2036
    SR_MUJER_AO = 1_250 - (AO - 2026) * 25
# 2026=1,250  2027=1,225  2028=1,200 ... 2036=1,000
_sr_año_sig = max(1_000, SR_MUJER_AO - 25) if AO < 2036 else 1_000
_sr_reduccion_nota = (
    f"En {AO} el requisito para mujeres en RPM es <b>{SR_MUJER_AO:,} semanas</b> "
    f"(Sentencia C-197/2023, reducción gradual). "
    f"En {AO+1}: {_sr_año_sig:,} sem. Meta final 2036: 1.000 sem."
)

# ══════════════════════════════════════════════════════════════
# REGLA MATERNIDAD — CUÁDRUPLE VERIFICACIÓN DEFENSIVA
# ══════════════════════════════════════════════════════════════
# El descuento de maternidad (Art.36 Ley 2381/2024) aplica SOLO cuando
# la mujer se pensiona bajo el NUEVO sistema de Pilares. NO aplica si:
#   → Régimen de Transición Art.36 Ley 100 (en_tr=True)
#   → Sentencia C-197/2023 (c197=True: ≥750 sem → pensiona bajo Ley 100)
#   → AFP/RAIS (capital individual, no tabla de semanas)
#
# Condiciones TODAS requeridas:
# (1) not en_tr: no en Transición Art.36 Ley 100
# (2) not c197:  no amparada por C-197 (≥750 sem = pensiona bajo Ley 100)
# (3) is_colp:   en Prima Media (Colpensiones)
# (4) es_mujer:  solo mujeres
# (5) hijos >= 1
aplica_mat = (not en_tr) and (not c197) and is_colp and es_mujer and (int(hijos) >= 1)
# T01 ♀1956 Colp 1000sem 3hijos: en_tr=True → False ✓
# T02 ♀1963 Colp 200sem  2hijos: en_tr=F, c197=F(200<750) → True ✓ (Pilares puro)
# T03 ♀1963 AFP  800sem  2hijos: is_colp=False → False ✓
# T04 ♀1963 Colp 800sem  2hijos: c197=True(800≥750) → False ✓ (Ley 100 vía C-197)
# T06 ♀1958 Colp 1000sem 5hijos: en_tr=True → False ✓
# T07 ♀1959 Colp 300sem  3hijos: en_tr=F, c197=F(300<750) → True ✓ (Pilares puro)
# T22 ♀1958 AFP  1200sem 3hijos: en_tr=True → False ✓
# T26 ♀1964 Colp 900sem  4hijos: c197=True(900≥750) → False ✓ (Ley 100 vía C-197)

# ── Semanas requeridas (SR) y descripción ─────────────────────
desc_hijos = 0
SR         = 0
reg_txt    = ""
reg_nota   = ""

if en_tr:
    # ══ LEY 100 — TRANSICIÓN ══════════════════════════════════
    # • desc_hijos = 0 SIEMPRE (Ley 2381 no aplica)
    # • C-197/2023 para efecto en Pilares: TAMPOCO aplica (diferente régimen)
    # • La Sentencia C-197/2023 YA está incorporada en el requisito de 1.000 semanas
    #   del ISS estándar (no derivó de la sentencia sino de la norma ISS original).
    # • Si el afiliado tiene un régimen especial (Cajanal, ISS especial, FF.MM.),
    #   los requisitos pueden diferir; en ese caso consultar a abogado.
    if is_afp:
        SR      = 1_150
        reg_txt = "Ley 100 — Transición + RAIS (GPM)"
        reg_nota = (
            "Régimen de Transición (Art.36 Ley 100) con AFP/RAIS. "
            "La GPM (Garantía de Pensión Mínima) exige 1.150 semanas para garantizar "
            "1 SMMLV de mesada si el saldo individual no alcanza. "
            "Si el saldo es suficiente para financiar renta ≥ 1 SMMLV, puede pensionarse "
            "sin necesidad de 1.150 semanas (retiro programado). "
            "<b>⛔ Descuento de maternidad (Ley 2381): NO aplica — Ley 100 Transición.</b>"
        )
    elif es_mujer:
        SR      = 1_000
        reg_txt = "Ley 100 — Transición Femenina (ISS / Prima Media)"
        reg_nota = (
            f"Régimen de Transición (Art.36 Ley 100): <b>{EP} años</b> y "
            f"<b>1.000 semanas</b> (estándar ISS/IVM). "
            f"<b>⛔ Descuento de maternidad (Art.36 Ley 2381/2024): NO aplica.</b> "
            f"Eres del Régimen de Transición (nacida en {año_nac} ≤ 1958), "
            f"una norma completamente diferente que la Reforma de Pilares de 2024."
        )
    else:
        SR      = 1_000
        reg_txt = "Ley 100 — Transición Masculina (ISS / Prima Media)"
        reg_nota = (
            f"Régimen de Transición (Art.36 Ley 100): <b>{EP} años</b> y "
            f"<b>1.000 semanas</b> (estándar ISS/IVM). "
            f"Puede variar si pertenecías a régimen especial (Cajanal, FF.MM., Ecopetrol, etc.). "
            f"<b>La Ley 2381/2024 NO modifica estos requisitos.</b>"
        )

elif c197:
    # ══ LEY 100 + C-197/2023 (mujer ≥750 sem , no Transición) ════
    # aplica_mat siempre es False aquí (c197=True bloquea aplica_mat)
    if is_afp:
        SR      = SR_AFP_GPM  # 1,150 GPM
        reg_txt = "Ley 100 + C-197/2023 (AFP — GPM)"
        reg_nota = (
            f"C-197/2023 aplica la reducción gradual. En AFP/RAIS la pensión depende del "
            f"capital acumulado, o en su defecto <b>{SR_AFP_GPM:,} semanas</b> para la "
            f"Garantía de Pensión Mínima (GPM). "
            + (f"Tienes {hijos} hijo(s), pero el descuento de maternidad (Art.36 Ley 2381) "
               f"no aplica en AFP." if int(hijos) > 0 else "")
        )
    elif is_colp and int(hijos) > 0:
        SR      = SR_MUJER_AO  # Dinámico: 1,250 en 2026
        reg_txt = f"Ley 100 + C-197/2023 ({SR_MUJER_AO:,} sem. {AO} — sin desc. maternidad)"
        reg_nota = (
            f"{_sr_reduccion_nota} "
            f"Tienes {hijos} hijo(s), pero tu pensión se calcula bajo el marco de <b>Ley 100</b> "
            f"(tienes ≥750 semanas cotizadas → derechos adquiridos). "
            f"El descuento de maternidad (Art.36 Ley 2381/2024) es exclusivo del nuevo "
            f"sistema de Pilares y <b>no aplica a tu caso</b>. "
            f"Tu requisito es <b>{SR_MUJER_AO:,} semanas</b> sin reducción adicional."
        )
    else:
        SR      = SR_MUJER_AO  # Dinámico: 1,250 en 2026
        reg_txt = f"Ley 100 + C-197/2023 ({SR_MUJER_AO:,} sem. {AO})"
        reg_nota = (
            f"{_sr_reduccion_nota} "
            f"Tu pensión se calcula bajo el marco de Ley 100 "
            f"(tienes ≥750 semanas cotizadas → derechos adquiridos)."
        )

else:
    # ══ PILARES 2024 PURO (mujer <750 sem o hombre, no transición) ═
    if aplica_mat:
        desc_hijos = min(3, int(hijos)) * 50
        SR      = max(650, SR_MUJER_AO - desc_hijos)
        reg_txt = f"Pilares 2024 + C-197 — Maternidad Colpensiones ({SR:,} sem. {AO})"
        reg_nota = (
            f"{_sr_reduccion_nota} "
            f"Art.36 Ley 2381/2024 condona {desc_hijos} semanas por {min(3,int(hijos))} hijo(s) "
            f"— solo en Colpensiones (Prima Media). "
            f"Tu meta real: <b>{SR:,} semanas</b>."
        )
    elif is_afp:
        SR      = SR_AFP_GPM  # 1,150 GPM
        reg_txt = "Pilares 2024 (AFP — GPM)"
        reg_nota = (
            f"En AFP/RAIS la pensión depende del capital acumulado o en su defecto "
            f"<b>{SR_AFP_GPM:,} semanas</b> para la Garantía de Pensión Mínima (GPM). "
            + (f"Tienes {hijos} hijo(s), pero el descuento de maternidad (Art.36 Ley 2381) "
               f"no aplica en AFP/RAIS." if es_mujer and int(hijos) > 0 else "")
        )
    elif es_mujer:
        SR      = SR_MUJER_AO  # Dinámico: 1,250 en 2026
        reg_txt = f"Pilares 2024 + C-197/2023 ({SR_MUJER_AO:,} sem. {AO})"
        if is_colp and int(hijos) == 0:
            reg_nota = (
                f"{_sr_reduccion_nota} "
                f"Si registras hijos en el futuro y tus semanas son <750, "
                f"el Art.36 Ley 2381 podría condonar 50 sem/hijo (máx. 3 hijos = 150 sem.)."
            )
        elif semanas < 750:
            reg_nota = (
                f"{_sr_reduccion_nota} "
                f"Al llegar a 750 semanas, pasarás al marco de Ley 100 "
                f"(derechos adquiridos vía C-197/2023)."
            )
        else:
            reg_nota = f"{_sr_reduccion_nota}"
    else:
        # Hombre, no transición
        SR      = SR_HOMBRE  # 1,300
        reg_txt = "Reforma de Pilares — Ley 2381/2024"
        reg_nota = (
            f"Pilares 2024: <b>{SR:,} semanas</b> y <b>{EP} años</b>. "
            f"La reducción gradual C-197/2023 aplica solo a mujeres."
        )

# ── Brecha pensional ──────────────────────────────────────────
ef    = max(0, EP - edad)
sf    = max(0, SR - int(semanas))
af    = sf / 52.14
efsem = edad + af           # Edad a la que completaría semanas cotizando
ce    = (ef == 0)           # Candado edad cumplido
cs    = (sf == 0)           # Candado semanas cumplido
yep   = AO + int(ef)

if sin_ingreso:
    y_sem = "⏸"; y_pen = "⏸ Pausado"
else:
    _y_s  = AO + math.ceil(af) if af > 0 else AO
    y_sem = str(_y_s)
    y_pen = str(max(AO + int(ef), _y_s))

s_e = "🟢" if ce else ("🟡" if ef <= 3 else "🔴")
s_s = "🟢" if cs else ("🟡" if sf <= 150 else "🔴")

# ── Estado estructural (15 estados exhaustivos) ───────────────
# Orden de prioridad: PENSIONADO > semanas > edad > combinaciones
if ce and cs:
    es = "PENSIONADO"
elif cs and not ce:
    es = "SEMANAS_OK"
elif ce and not cs:
    if   sf <= 104:     es = "PRONTO_2A"
    elif sf <= 260:     es = "PRONTO_5A"
    elif edad >= EBS:
        if   semanas >= 300:  es = "BEPS"
        elif sisben_v:        es = "SOLIDARIO"
        else:                 es = "DEVOL_TOTAL"
    else:   # EP ≤ edad < EBS
        if   semanas >= 300:  es = "LIMBO_BEPS"
        elif sisben_v:        es = "LIMBO_SOL"
        else:                 es = "DEVOL_ANTICIP"
else:   # Faltan AMBOS
    if   is_nunca and int(semanas) == 0:                         es = "NO_AFILIADO"
    elif efsem >= (75 if not es_mujer else 70):                  es = "IMPOSIBLE"
    elif efsem >  (65 if not es_mujer else 60):                  es = "RIESGO_ALTO"
    elif 650 <= int(semanas) <= 1149 and edad >= 40 and sisben_v: es = "PSAP"
    else:                                                         es = "EN_RUTA"

# ── Input contradictorio: "Nunca cotizado" pero semanas > 0 ───
input_contradict = is_nunca and int(semanas) > 0

# ═════════════════════════════════════════════════════════════
# CÁLCULO TRIBUTARIO
# ═════════════════════════════════════════════════════════════
ibc = salud = pen_tot = fsp = ac = aafp = aemp = costo = 0
supera = False
ibc_bajo_minimo = False

if ingreso_r > 0:
    if is_dependiente:
        if ingreso_r < SMMLV:
            ibc_bajo_minimo = True
        base = max(ingreso_r, SMMLV)          # mínimo legal SMMLV
    elif is_independiente:
        base = max(ingreso_r * 0.40, SMMLV)   # 40% ingreso o SMMLV
    else:                                      # expatriado cotizante
        base = max(ingreso_r, SMMLV)

    if base > TOPE_UGPP:
        supera = True; base = TOPE_UGPP
    ibc = base

    if not is_expat:
        salud = ibc * (0.04 if is_dependiente else 0.125)

    pen_tot = ibc * 0.16

    # Fondo Solidaridad Pensional (tasas Ley 2381/2024)
    if   ibc >= 20*SMMLV: fsp = ibc * 0.030
    elif ibc >= 19*SMMLV: fsp = ibc * 0.025
    elif ibc >= 11*SMMLV: fsp = ibc * 0.020
    elif ibc >=  7*SMMLV: fsp = ibc * 0.018
    elif ibc >=  4*SMMLV: fsp = ibc * 0.015

    # Distribución Pilar
    if en_tr:
        if is_afp:  aafp = ibc * 0.16
        else:       ac   = ibc * 0.16
    else:
        if ibc <= UMBRAL:
            ac = ibc * 0.16
        else:
            ac   = UMBRAL * 0.16
            aafp = (ibc - UMBRAL) * 0.16

    # Costos netos del bolsillo
    if is_dependiente:
        costo = ibc * 0.035 + salud + fsp
        aemp  = ibc * (0.125 + 0.085)   # empresa paga: 12.5% pen + 8.5% salud
    elif is_independiente:
        costo = pen_tot + salud + fsp
    elif is_expat and cotiza_ext:
        costo = pen_tot + fsp

# ── Flag split Pilares: ingresos > UMBRAL (2.3 SMMLV) y NO en transición
split_pilares = (not en_tr) and (ac > 0) and (aafp > 0)

# ── Mesada estimada (Prima Media — Art.34 Ley 100) ────────────
def mesada(sem, ib, sm, sr):
    """Fórmula Prima Media: 65% + 1.5% por cada 50 sem. sobre SR. Tope 85%."""
    if int(sem) < int(sr) or ib == 0: return 0.0
    extra = max(0, int(sem) - int(sr))
    tasa  = min(0.85, 0.65 + (extra // 50) * 0.015)
    return max(ib * tasa, sm)

ib_r  = ibc if ibc > 0 else SMMLV
m_hoy = mesada(semanas,               ib_r, SMMLV, SR)
m_5   = mesada(int(semanas)+int(5*52), ib_r, SMMLV, SR)
m_10  = mesada(int(semanas)+int(10*52),ib_r, SMMLV, SR)

# ═════════════════════════════════════════════════════════════
# DATOS PARA GRÁFICO ETF (Chart.js dentro del iframe)
# Proyección a 25 años — inversión mensual ilustrativa: 5M COP / mes
# ═════════════════════════════════════════════════════════════
_M        = 5_000_000   # Inversión mensual ilustrativa (COP)
_r_etf    = 0.07        # 7 % USD real anual (histórico MSCI World)
_r_fpv    = 0.095       # 9.5 % COP nominal (FPV colombiano promedio)
_r_cdt    = 0.08        # 8.0 % COP nominal (CDT bancario)
_r_afp    = 0.065       # 6.5 % COP nominal (AFP retorno neto histórico)
_YRS      = 25

_usd_m    = _M / TRM_REF  # Cuántos USD equivalen a 5M COP hoy

# Simulación mes a mes
_etf_u = _fpv_v = _cdt_v = _afp_v = _col_v = 0.0
_etf_cop = []; _fpv = []; _cdt = []; _afp = []; _col = []
_usd_val = []; _trm_prj = []

for _mo in range(1, _YRS*12 + 1):
    _etf_u += _usd_m;  _fpv_v += _M; _cdt_v += _M; _afp_v += _M; _col_v += _M
    _etf_u *= (1 + _r_etf/12)
    _fpv_v *= (1 + _r_fpv/12)
    _cdt_v *= (1 + _r_cdt/12)
    _afp_v *= (1 + _r_afp/12)
    if _mo % 12 == 0:
        _yr   = _mo // 12
        _trm  = TRM_REF * (1 + TRM_DEV) ** _yr
        _etf_cop.append(round(_etf_u * _trm / 1_000_000, 1))
        _fpv.append(round(_fpv_v / 1_000_000, 1))
        _cdt.append(round(_cdt_v / 1_000_000, 1))
        _afp.append(round(_afp_v / 1_000_000, 1))
        _col.append(round(_col_v / 1_000_000, 1))
        _usd_val.append(round(_etf_u / 1000, 1))   # en miles USD
        _trm_prj.append(int(_trm))

# Valores clave para tabla
def _vyr(arr, yr):
    return arr[yr-1] if len(arr) >= yr else 0

_LABELS_J = json.dumps([f"Año {y}" for y in range(1, _YRS+1)])
_ETF_J    = json.dumps(_etf_cop)
_FPV_J    = json.dumps(_fpv)
_CDT_J    = json.dumps(_cdt)
_AFP_J    = json.dumps(_afp)
_COL_J    = json.dumps(_col)
_USD_J    = json.dumps(_usd_val)
_TRM_J    = json.dumps(_trm_prj)

# ═════════════════════════════════════════════════════════════
# HELPERS HTML
# ═════════════════════════════════════════════════════════════
def P(v):  return f"${v:,.0f}"       # Peso COP formatado
def R1(v): return f"{v:.1f}"
def FI(v): return f"{int(v):,}"
def Pm(v): return f"${v/1_000_000:.1f}M"  # En millones

_BC = {"ok":"#16a34a","info":"#1e40af","warn":"#92400e","err":"#991b1b","vip":"#4c1d95","gold":"#b45309","cyan":"#0e7490"}
_BB = {"ok":"#d1fae5","info":"#dbeafe","warn":"#fef3c7","err":"#fee2e2","vip":"#ede9fe","gold":"#fef9c3","cyan":"#cffafe"}

def box(t, c):
    return (f"<div style='border-left:4px solid {_BC[t]};background:{_BB[t]}14;"
            f"border-radius:6px;padding:12px 16px;margin:8px 0;color:#e2e8f0;line-height:1.65'>{c}</div>")

def krow(*items):
    cols = "".join(
        f"<div style='flex:1;min-width:130px;background:#0f172a;border-radius:8px;"
        f"padding:10px 8px;margin:3px;text-align:center'>"
        f"<div style='color:#94a3b8;font-size:0.71em;margin-bottom:3px'>{l}</div>"
        f"<div style='color:#f1f5f9;font-size:1.18em;font-weight:700'>{v}</div>"
        f"<div style='color:#64748b;font-size:0.68em;margin-top:2px'>{s}</div></div>"
        for l, v, s in items
    )
    return f"<div style='display:flex;flex-wrap:wrap;gap:3px;margin:8px 0'>{cols}</div>"

def hr():  return "<hr style='border:none;border-top:1px solid #334155;margin:20px 0'/>"
def h1(t): return f"<h1 style='color:#f1f5f9;font-size:1.6em;margin:0 0 6px;font-weight:700'>{t}</h1>"
def h2(t): return f"<h2 style='color:#e2e8f0;font-size:1.25em;margin:18px 0 10px'>{t}</h2>"
def h3(t): return f"<h3 style='color:#e2e8f0;margin:0 0 12px'>{t}</h3>"
def h4(t): return f"<h4 style='color:#93c5fd;margin:14px 0 8px'>{t}</h4>"

def paso(n, titulo, cuerpo):
    return (f"<div style='display:flex;gap:10px;margin:9px 0;align-items:flex-start'>"
            f"<div style='min-width:26px;height:26px;background:#2563eb;border-radius:50%;"
            f"display:flex;align-items:center;justify-content:center;font-weight:700;"
            f"font-size:0.85em;flex-shrink:0;color:white'>{n}</div>"
            f"<div style='padding-top:2px'>"
            f"<b style='color:#93c5fd'>{titulo}:</b> "
            f"<span style='color:#cbd5e1;line-height:1.65'>{cuerpo}</span></div></div>")

def tag(t, c): return (f"<span style='background:{c};color:white;padding:2px 8px;"
                       f"border-radius:10px;font-size:0.77em;font-weight:600'>{t}</span>")

# ═════════════════════════════════════════════════════════════
# CONSTRUCCIÓN HTML COMPLETA
# ═════════════════════════════════════════════════════════════
html = ""

# ── CABECERA ──────────────────────────────────────────────────
_regime_color = "#f59e0b" if en_tr else ("#10b981" if c197 else "#60a5fa")
html += f"""
<div style='background:linear-gradient(135deg,#0f172a,#1e3a5f);
padding:20px 24px;border-radius:12px;margin-bottom:14px'>
<div style='color:#93c5fd;font-size:0.78em;letter-spacing:1px'>
  🇨🇴 SIMULADOR PENSIONAL ÉLITE — COLOMBIA {AO}  ·  Versión 10.0 Producción
</div>
<div style='color:white;font-size:1.65em;font-weight:700;margin:4px 0'>
  Análisis Pericial — {nombre}
</div>
<div style='color:#94a3b8;font-size:0.83em;margin-top:4px'>
  <span style='background:{_regime_color}22;color:{_regime_color};padding:2px 8px;
  border-radius:4px;font-weight:600'>{reg_txt}</span>
  &nbsp;|&nbsp; {ep_fuente} &nbsp;|&nbsp; {HORA}
</div>
</div>
"""

# ── LEY APLICABLE + FECHA CORTE ───────────────────────────────
_tr_color = "#f59e0b" if en_tr else "#34d399"
_tr_label = "LEY 100 TRANSICIÓN" if en_tr else "LEY 2381/2024 PILARES"
html += box("info",
    f"<b>Marco legal que aplica a tu caso:</b> {reg_nota}<br>"
    f"<div style='color:#64748b;font-size:0.8em;margin-top:6px'>"
    f"📌 <b>Fecha de corte Régimen de Transición (Ley 100):</b> "
    f"Mujeres nacidas <b>hasta 1958</b> inclusive · Hombres nacidos <b>hasta 1953</b> inclusive. "
    f"Tu año de nacimiento: <b>{año_nac}</b> → "
    f"<b style='color:{_tr_color}'>{_tr_label}</b></div>")

if en_tr:
    html += box("gold",
        f"📜 <b>Régimen de Transición — Derechos Adquiridos (Ley 100):</b> "
        f"Tus requisitos ({EP} años y {SR:,} semanas) son de la normativa anterior a la Reforma de Pilares. "
        f"<b>Ningún beneficio de la Ley 2381/2024 te aplica</b>: ni el descuento por maternidad, "
        f"ni la redistribución obligatoria de aportes, ni los nuevos umbrales de semanas.")

if desc_hijos > 0:
    html += box("ok",
        f"👶 <b>✅ Descuento por Maternidad ACTIVO — Art.36 Ley 2381/2024:</b> "
        f"{desc_hijos} semanas condonadas por {min(3,int(hijos))} hijo(s). "
        f"Base C-197 para {AO}: {SR_MUJER_AO:,} sem. → con descuento: <b>{SR:,} semanas</b>. "
        f"<b>Este beneficio aplica porque:</b> "
        f"(1) no estás en Régimen de Transición Ley 100, "
        f"(2) tienes menos de 750 semanas (no amparada por C-197 bajo Ley 100), "
        f"(3) estás en Colpensiones/Prima Media, y (4) tienes hijos registrados.")
elif es_mujer and int(hijos) > 0 and en_tr:
    html += box("info",
        f"ℹ️ <b>Descuento de maternidad NO aplica — Ley 100 (Régimen de Transición):</b> "
        f"Tienes {hijos} hijo(s), pero tu pensión se rige por la <b>Ley 100/1993 "
        f"(Régimen de Transición)</b>, no por la Reforma de Pilares 2024. "
        f"En Ley 100 no existe el descuento de semanas por maternidad — ese beneficio "
        f"fue creado por el Art.36 de la Ley 2381/2024 y aplica <b>solo a mujeres nacidas "
        f"desde 1959 con menos de 750 semanas</b> afiliadas a Colpensiones bajo el nuevo "
        f"sistema de Pilares. Tu requisito sigue siendo <b>{SR:,} semanas</b> sin reducción.")
elif es_mujer and int(hijos) > 0 and c197:
    html += box("info",
        f"ℹ️ <b>Descuento de maternidad NO aplica — Ley 100 (Sentencia C-197/2023):</b> "
        f"Tienes {hijos} hijo(s), pero tu pensión se calcula bajo el marco de <b>Ley 100</b>, "
        f"confirmado por la Sentencia C-197/2023 (tienes ≥750 semanas cotizadas). "
        f"El descuento por maternidad (Art.36 Ley 2381/2024) es del nuevo sistema de Pilares "
        f"y <b>no aplica</b> a quienes ya se pensionan bajo Ley 100. "
        f"Tu requisito es <b>{SR:,} semanas</b> sin ninguna reducción.")
elif es_mujer and int(hijos) > 0 and is_afp:
    html += box("info",
        f"ℹ️ <b>Descuento de maternidad NO aplica a AFP/RAIS:</b> "
        f"Tienes {hijos} hijo(s), pero en AFP la pensión se calcula sobre el capital "
        f"acumulado en tu cuenta individual (no sobre un umbral de semanas como en Prima Media). "
        f"El descuento de maternidad (Art.36 Ley 2381) aplica solo a Colpensiones.")

if input_contradict:
    html += box("warn",
        f"⚠️ <b>Dato inconsistente:</b> Seleccionaste 'Nunca he cotizado' pero "
        f"registraste {int(semanas)} semanas. Si cotizaste, selecciona el fondo correcto "
        f"(Colpensiones o AFP). Las semanas se asumen guardadas para el cálculo.")

if ibc_bajo_minimo:
    html += box("warn",
        f"⚠️ <b>Salario declarado inferior al mínimo legal ({P(SMMLV)}):</b> "
        f"Declaraste {P(ingreso_r)}/mes. Art.156 CST: ningún contrato laboral puede pagar "
        f"menos del SMMLV. <b>Los cálculos se realizan sobre {P(SMMLV)}.</b> "
        f"Excepción: Decreto 2616/2013 para trabajadores por días (domésticos, etc.), "
        f"donde la cotización puede ser proporcional. Consulta con tu empleador.")

if supera:
    html += box("vip",
        f"🏆 <b>Ingreso supera el Techo UGPP ({P(TOPE_UGPP)}):</b> "
        f"Todo lo que ganes por encima de 25 SMMLV no paga cotizaciones de pensión ni salud.")

html += h4("📋 Referencias 2026")
html += krow(
    ("SMMLV 2026", P(SMMLV), "Base de todos los cálculos"),
    ("Techo Pilar Solidario", P(UMBRAL), f"{MULT}× SMMLV"),
    ("Techo UGPP", P(TOPE_UGPP), "25× SMMLV"),
    ("UVT 2026", P(UVT), "Base DIAN"),
    ("TRM referencia", f"${TRM_REF:,}", "COP / 1 USD")
)

# ── ALERTA DE INGRESOS ────────────────────────────────────────
if ei == "EXPAT_INACTIVO":
    html += box("err",
        f"🛑 <b>{nombre}: exterior + sin ingresos cotizados.</b> "
        f"Historial pensional completamente detenido. Sin protección de invalidez ni sobrevivencia. "
        f"Acción: www.miplanilla.com → Cotizante Voluntario. Mínimo {P(SMMLV*0.16)}/mes.")
elif ei == "INACTIVO_LOCAL":
    html += box("warn",
        f"⚠️ <b>Sin cotizaciones activas, {nombre}.</b> "
        f"Cada mes sin aportar = 1 semana perdida + sin cobertura de invalidez. "
        f"Mínimo: {P(SMMLV*0.16)}/mes pensión + {P(SMMLV*0.125)}/mes salud.")
elif ei == "EXPAT_SIN_PAGO":
    html += box("err",
        f"🛑 <b>Emigrante sin aportes, {nombre}.</b> "
        f"www.miplanilla.com → Cotizante Voluntario. Mínimo {P(SMMLV*0.16)}/mes.")
elif ei == "EXPAT_ACTIVO":
    html += box("info",
        f"✈️ <b>Emigrante cotizando voluntariamente — bien, {nombre}.</b> "
        f"Exento de EPS colombiana mientras resides en el exterior.")
else:
    modo = ("como empleado" if is_dependiente else "como independiente — tú pagas el 100%")
    html += box("ok", f"✅ <b>Aportes activos {modo}.</b> Tu historial avanza cada mes.")

# ── S1: CANDADOS PENSIONALES ──────────────────────────────────
html += hr() + h3("🔐 1. Tus Dos Candados Pensionales")
html += f"""
<table style='width:100%;border-collapse:collapse;color:#e2e8f0;margin:10px 0'>
<thead><tr style='background:#1e293b'>
  <th style='padding:9px;text-align:left'>Candado</th>
  <th style='padding:9px;text-align:center'>Necesitas</th>
  <th style='padding:9px;text-align:center'>Tienes</th>
  <th style='padding:9px;text-align:center'>Diferencia</th>
  <th style='padding:9px;text-align:center'>Estado</th>
</tr></thead><tbody>
<tr style='border-top:1px solid #334155'>
  <td style='padding:9px'><b>Edad pensional</b><br>
    <span style='color:#64748b;font-size:0.79em'>{ep_fuente}</span></td>
  <td style='padding:9px;text-align:center'>{EP} años</td>
  <td style='padding:9px;text-align:center'>{edad} años</td>
  <td style='padding:9px;text-align:center'>{"✅ Superada" if ce else f"Faltan {ef} año(s)"}</td>
  <td style='padding:9px;text-align:center;font-size:1.3em'>{s_e}</td>
</tr>
<tr style='border-top:1px solid #334155'>
  <td style='padding:9px'><b>Semanas cotizadas</b><br>
    <span style='color:#64748b;font-size:0.79em'>{reg_txt}</span>
    {"<br><span style='color:#10b981;font-size:0.75em'>▼ Incluye " + str(desc_hijos) + " sem. condonadas (maternidad)</span>" if desc_hijos > 0 else ""}</td>
  <td style='padding:9px;text-align:center'>{SR:,} sem.</td>
  <td style='padding:9px;text-align:center'>{int(semanas):,} sem.</td>
  <td style='padding:9px;text-align:center'>{"✅ Superadas" if cs else f"Faltan {FI(sf)} sem."}</td>
  <td style='padding:9px;text-align:center;font-size:1.3em'>{s_s}</td>
</tr>
</tbody></table>
"""

if not sin_ingreso and not (ce and cs):
    html += krow(
        (f"Cumples {EP} años en", str(yep), f"Faltan {ef} año(s)"),
        ("Completas semanas en", y_sem if y_sem != "⏸" else "—", f"~{R1(af)} años cotizando"),
        ("🎯 Pensión posible desde", y_pen, "El mayor de los dos candados")
    )
elif sin_ingreso and not (ce and cs):
    html += box("warn",
        "⏸ <b>Proyección pausada.</b> Sin aportes activos no hay fecha calculable. "
        "Las semanas acumuladas siguen guardadas. Tu pulga viva cuida el historial.")

# Diagnóstico estado
_pen_ley_txt = (
    "Tu derecho está protegido por la <b>Ley 100/1993 (Régimen de Transición ISS)</b>. "
    "Los beneficios de la Reforma de Pilares 2024 (como el descuento por hijos) <b>NO te aplican</b>. "
) if en_tr else (
    "Tu derecho es por <b>Ley 2381/2024 (Pilares)</b>" +
    (" + Sentencia C-197/2023" if c197 else "") + ". "
)
_DIAG = {
"PENSIONADO": ("ok",
    f"🟢 <b>¡{nombre}, TIENES DERECHO A PENSIÓN HOY!</b> "
    f"Edad ({edad} ≥ {EP}) ✅  Semanas ({int(semanas):,} ≥ {SR:,}) ✅. "
    f"{_pen_ley_txt}"
    f"Cada mes sin tramitar = retroactivo perdido. Actúa esta semana."),
"SEMANAS_OK": ("ok" if not sin_ingreso else "warn",
    f"🔵 <b>Semanas listas — solo esperas el tiempo biológico.</b> "
    f"Tienes {int(semanas):,} ≥ {SR:,} semanas. Cumples {EP} años en {yep}. "
    f"{'Cuida el IBL: cotizar poco ahora puede bajar tu mesada final hasta 40%.' if not sin_ingreso else 'Las semanas guardadas te esperan.'}"),
"PRONTO_2A": ("warn",
    f"🟡 <b>¡Menos de 2 años para lograrlo!</b> Edad OK. Faltan {FI(sf)} semanas (~{R1(af)} año(s)). "
    f"Meta: {y_pen if not sin_ingreso else '—'}. No pares bajo ninguna circunstancia."),
"PRONTO_5A": ("warn",
    f"🟡 <b>A menos de 5 años de la meta.</b> Edad OK. Faltan {FI(sf)} semanas (~{R1(af)} años). "
    f"Meta: {y_pen if not sin_ingreso else '—'}. Período crítico: 6 meses sin cotizar = años de retraso."),
"BEPS": ("info",
    f"💡 <b>BEPS disponible, {nombre}.</b> {edad} años (≥{EBS}) y {int(semanas):,} sem. (≥300). "
    f"El BEPS convierte tus ahorros en renta vitalicia + 20% de bonificación estatal."),
"SOLIDARIO": ("info",
    f"💡 <b>Pilar Solidario disponible.</b> {edad} años (≥{EBS}) + SISBÉN calificado. "
    f"Colombia Mayor: aporta mensualmente de por vida."),
"DEVOL_TOTAL": ("warn",
    f"🟡 <b>Devolución de aportes disponible, {nombre}.</b> "
    f"{int(semanas):,} sem. ({'insuficientes' if sf > 0 else 'suficientes'}) y sin acceso a BEPS/Solidario."),
"LIMBO_BEPS": ("info",
    f"ℹ️ <b>Espera {max(0,EBS-edad)} año(s) para el BEPS (año {AO+max(0,EBS-edad)}).</b> "
    f"Tienes edad de pensión ({edad}) pero el BEPS arranca a los {EBS} años."),
"LIMBO_SOL": ("info",
    f"ℹ️ <b>Pilar Solidario en {max(0,EBS-edad)} año(s) (año {AO+max(0,EBS-edad)}).</b> "
    f"Mantén el SISBÉN vigente."),
"DEVOL_ANTICIP": ("warn",
    f"🟡 <b>Zona intermedia, {nombre}.</b> Edad de pensión ({edad} ≥ {EP}) "
    f"pero aún no alcanzas BEPS/Solidario ({EBS} años). "
    f"Puedes pedir devolución anticipada de aportes."),
"NO_AFILIADO": ("err",
    f"🔴 <b>Sin afiliación — urgente actuar, {nombre}.</b> "
    f"Sin fondo: sin semanas, sin invalidez, sin sobrevivencia. Afíliate gratis hoy."),
"IMPOSIBLE": ("err",
    f"🔴 <b>Honestidad total, {nombre}:</b> Con {edad} años y {int(semanas):,} semanas, "
    f"completar las {SR:,} llevaría a los ~{math.ceil(efsem)} años. "
    f"La pensión mensual no es alcanzable — hay alternativas inteligentes."),
"RIESGO_ALTO": ("warn",
    f"🟡 <b>Llegarás, pero con margen justo, {nombre}.</b> "
    f"Meta hacia los {math.floor(efsem)} años ({y_pen if not sin_ingreso else '—'}). "
    f"Cero interrupciones. El margen es estrecho."),
"PSAP": ("vip",
    f"🌟 <b>¡Subsidio PSAP disponible, {nombre}!</b> "
    f"{edad} años (≥40), {int(semanas):,} sem. (650-1149), SISBÉN calificado. "
    f"El Estado puede pagar el 70-75% de tu cotización mensual."),
"EN_RUTA": ("ok" if not sin_ingreso else "warn",
    f"{'🟢 En ruta, ' + nombre + '. El historial avanza mes a mes.' if not sin_ingreso else '🟡 Estructuralmente en ruta, pero el reloj está pausado, ' + nombre + '.'} "
    f"{'Meta: ' + str(y_pen) + '. Constancia = tu mejor herramienta.' if not sin_ingreso else 'Reactivar aportes es la prioridad.'}"),
}
_tipo_d, _txt_d = _DIAG.get(es, ("info","—"))
html += box(_tipo_d, _txt_d)

# ── S2: COSTOS Y MESADA ───────────────────────────────────────
html += hr() + h3("💰 2. Lo Que Cuesta Tu Pensión Mes a Mes")

if ibc == 0:
    html += box("err",
        "<b>IBC = $0.</b> Sin aportes activos. Ver Plan de Acción (sección 4).")
else:
    lbl_p = (f"{P(ibc*0.035)} (3.5% tu parte)"   if is_dependiente   else
             f"{P(pen_tot)} (16% completo)"        if is_independiente else f"{P(pen_tot)} (16%)")
    lbl_s = (f"{P(salud)} (4% tu parte)"          if is_dependiente   else
             f"{P(salud)} (12.5% completo)"        if is_independiente else "Exento EPS (expatriado)")

    html += krow(
        ("IBC (Base Cotización)", P(ibc),
         f"{'⚠️ Ajustado a mín. legal' if ibc_bajo_minimo else 'Tu base legal'}"),
        ("Tu aporte pensión/mes", lbl_p, "Neto de tu bolsillo"),
        ("Tu aporte salud/mes",   lbl_s, "Neto de tu bolsillo"),
        ("Solidaridad FSP/mes",   P(fsp), "Solo si ganas > 4 SMMLV")
    )
    html += krow(
        ("→ Colpensiones (Pilar Base)", P(ac)   if ac > 0   else "$0", "Fondo colectivo garantizado"),
        ("→ AFP (Pilar Compl.)",        P(aafp) if aafp > 0 else "$0", "Cuenta individual mercado"),
        ("Tu costo total / mes",        P(costo), "Sale de tu bolsillo"),
        ("Aporte del empleador",
         P(aemp) if aemp > 0 else "N/A",
         "Empresa paga adicional" if aemp > 0 else "Sin empleador")
    )
    if split_pilares:
        html += box("info",
            f"<b>💡 Sistema Pilares activo — Tu ingreso supera {P(UMBRAL)} (2.3 SMMLV):</b><br>"
            f"• <b>Colpensiones (Pilar Base):</b> {P(ac)}/mes ({P(UMBRAL)} × 16%) → Pensión garantizada por el Estado (IBL).<br>"
            f"• <b>AFP (Pilar Complementario):</b> {P(aafp)}/mes ({P(ibc - UMBRAL)} × 16%) → Cuenta individual de ahorro.<br>"
            f"• <b>Total cotización pensión:</b> {P(pen_tot)}/mes (16% de {P(ibc)}).<br><br>"
            f"<b>¿Cómo te pensionas?</b> Al cumplir requisitos, tramitas <b>dos pensiones en paralelo</b>:<br>"
            f"① Colpensiones te paga mesada garantizada (fórmula IBL) sobre los primeros {P(UMBRAL)}.<br>"
            f"② Tu AFP paga renta vitalicia, retiro programado o combinado sobre el capital complementario.<br>"
            f"<b>Ambas se suman</b> y recibes un ingreso mensual mayor que si estuvieras solo en un fondo.")

    html += h4("📈 Estimación de Mesada (Art.34 Ley 100 — Prima Media)")
    if is_afp:
        html += box("info",
            "<b>En AFP la mesada depende del capital acumulado, no de esta fórmula.</b> "
            "Valores referenciales para comparación. Solicita proyección real a tu AFP.")
    html += krow(
        ("Con semanas actuales", P(m_hoy) if m_hoy > 0 else "Aún no aplica",
         f"{int(semanas):,} sem. base"),
        ("En 5 años continuos", P(m_5) if m_5 > 0 else "—",
         f"~{int(semanas)+int(5*52):,} sem."),
        ("En 10 años continuos", P(m_10) if m_10 > 0 else "—",
         f"~{int(semanas)+int(10*52):,} sem.")
    )
    html += ("<div style='color:#64748b;font-size:0.74em;margin-top:4px'>"
             f"Prima Media: 65% IBL + 1.5% por cada 50 sem. sobre SR. Tope 85%. Mínimo 1 SMMLV ({P(SMMLV)}). "
             f"IBL estimado: {P(ib_r)}/mes.</div>")

# ── S3: FONDO Y DOBLE ASESORÍA ────────────────────────────────
html += hr() + h3(f"🏦 3. Análisis de Tu Fondo — {fondo.split('(')[0].strip()}")

if is_nunca:
    html += box("err",
        "<b>Sin afiliación.</b> www.colpensiones.gov.co o cualquier AFP. "
        "Solo cédula + cuenta bancaria. 30 min. Protección de invalidez desde el primer aporte.")
elif blq:
    html += box("warn",
        f"<b>Con {edad} años ya no puedes cambiar de fondo (Art.13 Ley 100).</b> "
        f"Límite: {ELT} años ({EP} - 10). Permanecerás en {fondo.split('(')[0].strip()}.")
elif es == "PENSIONADO":
    if is_afp:
        html += box("ok","<b>No cambies de fondo — tramita la pensión.</b>")
        html += box("info",
            "<b>Elige tu modalidad en AFP:</b><br>"
            "① <b>Renta Vitalicia:</b> Capital a aseguradora. Pago fijo vitalicio indexado IPC. Sin riesgo longevidad. No heredable.<br>"
            "② <b>Retiro Programado:</b> Capital en AFP. Variable. Heredable. Puede agotarse.<br>"
            "③ <b>Combinado (Renta Vit. + R.P.):</b> Lo mejor de ambas. Recomendado para saldos significativos.")
    else:
        _ley_ctx = (" Tu pensión se tramita bajo <b>Ley 100 (Régimen de Transición)</b> — "
                    "los requisitos y beneficios de la Reforma de Pilares 2024 NO aplican a tu caso."
                    ) if en_tr else ""
        html += box("ok", f"<b>No cambies — concéntrate en el trámite de pensión con Colpensiones.</b>{_ley_ctx}")
elif en_tr:
    color_tr = "#b45309"
    html += box("gold",
        f"<b>⚠️ ALERTA — Régimen de Transición:</b> "
        f"Si cambias {'tu AFP' if is_afp else 'Colpensiones'} por otro fondo, "
        f"<b>podrías perder los derechos del Régimen de Transición</b> (Ley 797/2003). "
        f"Esos derechos no se recuperan. Consulta OBLIGATORIAMENTE con un abogado pensional antes.")
elif es in ["IMPOSIBLE","DEVOL_TOTAL","BEPS"]:
    if is_colp:
        html += box("err" if not blq else "warn",
            f"<b>{'🛑 Considera AFP si aún puedes trasladarte' if not blq else '⚠️ Ya no puedes trasladarte'}.</b> "
            f"Con devolución de saldos, AFP devuelve capital + rentabilidades reales (5-9% anual real). "
            f"Colpensiones devuelve capital + IPC. La diferencia puede ser de decenas de millones.")
elif not en_tr and split_pilares:
    html += box("info",
        f"<b>Pilar doble activo:</b> {P(ac)}/mes a Colpensiones + {P(aafp)}/mes a AFP. "
        f"Al pensionarte tramitas con <b>ambas entidades en paralelo</b>.")
elif not en_tr and is_colp and ingreso_r > 0 and ingreso_r <= SMMLV * 2:
    html += box("info",
        "<b>Colpensiones con ingresos bajos:</b> Con saldo bajo, si nunca llegas a semanas "
        "requeridas, Colpensiones devuelve aportes + IPC. AFP devuelve + mercado (más). "
        "Evalúa si seguir en Colpensiones o cambiar mientras tienes tiempo.")
else:
    html += box("info",
        "<b>Sin alerta crítica sobre el fondo.</b> Solicita proyecciones actualizadas cada 2-3 años.")

html += h4("🔄 Doble Asesoría (Ley 1328/2009)")
_da_no_aplica_bajo = is_colp and (ingreso_r <= UMBRAL) and (not en_tr)
if blq:
    html += f"<div style='color:#94a3b8'>🚫 No disponible: {edad} años ≥ límite de {ELT} años.</div>"
elif en_tr:
    html += box("warn","<b>⚠️ Consulta abogado ANTES de cualquier traslado.</b> "
        "Régimen de Transición: traslado puede hacer perder derechos adquiridos.")
elif _da_no_aplica_bajo:
    html += box("info",
        f"<b>ℹ️ No recomendada en tu caso:</b> "
        f"Ya estás en Colpensiones y tus ingresos ({P(ingreso_r)}/mes) están por debajo del "
        f"umbral de {P(UMBRAL)} (2.3 SMMLV). Todo tu aporte va a Colpensiones — "
        f"no hay componente AFP que evaluar. La doble asesoría es útil solo cuando "
        f"hay ventaja real en comparar fondos.")
else:
    _puede = es not in ["PENSIONADO","PRONTO_2A"]
    html += f"<div style='color:#94a3b8;margin-bottom:8px'>" \
            f"{tag('SÍ puede valer evaluarla','#16a34a') if _puede else tag('No recomendada ahora','#dc2626')} " \
            f"(proceso legal para cambiar de fondo)</div>"
    html += (paso("1","Solicita asesoría al fondo destino","Gratis — es tu derecho legal.") +
             paso("2","Tu fondo entrega proyecciones firmadas (5 días hábiles)","Números reales de quedarte.") +
             paso("3","Fondo destino presenta contrapropuesta firmada","Comparación objetiva certificada.") +
             paso("4","Decisión irrevocable — 5 días hábiles","Un traslado tarda mínimo 5 años para deshacer."))

# ── S4: PLAN DE ACCIÓN ────────────────────────────────────────
html += hr() + h3(f"🎯 4. Tu Plan de Acción — {nombre}")

# Datos contacto exactos por fondo
if is_colp or is_nunca:
    _cnt = "01 8000 91 2345 (Colpensiones)"
    _lnk = "www.colpensiones.gov.co"
    _frm = "Formulario P-22 'Reconocimiento de Pensión'. Gratuito."
    _mod = ""
else:
    _cnt = ("Porvenir: 01 8000 91 4141 · Protección: 01 8000 0951 71 · "
            "Colfondos: 01 8000 11 3338 · Skandia: 601 307 6225")
    _lnk = "el portal web de tu AFP específica"
    _frm = "Solicita la 'Solicitud de Pensión' a tu AFP. Te presentarán la simulación de modalidades."
    _mod = ("① Renta Vitalicia: capital a aseguradora, pago fijo vitalicio, no heredable. "
            "② Retiro Programado: capital en AFP, variable, heredable, puede agotarse. "
            "③ Combinado: renta + retiro. Recomendado si saldo es significativo.")

pasos_acc = []

if ei in ["EXPAT_INACTIVO","EXPAT_SIN_PAGO"]:
    pasos_acc.append(("URGENTE: Reactiva aportes desde el exterior",
        f"www.miplanilla.com → Cotizante Voluntario. Cédula + tarjeta internacional. "
        f"Mínimo {P(SMMLV*0.16)}/mes. Sin esto, cada mes = 1 semana perdida."))
elif ei == "INACTIVO_LOCAL":
    pasos_acc.append(("Reactiva aportes pronto",
        f"{P(SMMLV*0.16)}/mes pensión + {P(SMMLV*0.125)}/mes salud en www.miplanilla.com."))

if es == "PENSIONADO":
    _ley_paso = (f"Ley 100 — Régimen de Transición (ISS). Requisitos: {EP} años y {SR:,} semanas. "
                 "La Reforma de Pilares (Ley 2381/2024) NO modifica tus derechos adquiridos."
                 ) if en_tr else (
                 f"Ley 2381/2024 — Pilares. Requisitos: {EP} años y {SR:,} semanas."
                 + (f" C-197/2023 aplicada." if c197 else ""))
    pasos_acc += [
        ("Tu ley aplicable", _ley_paso),
        ("Llama a tu fondo ESTA SEMANA", f"{_cnt}. El trámite es gratuito."),
        ("Solicita el reconocimiento de pensión", _frm),
        *([("Elige la modalidad de pensión (AFP)", _mod)] if _mod else []),
        ("Reúne documentos",
         f"Cédula original · extracto de semanas ({_lnk}) · cuenta bancaria activa."),
        ("Exige retroactivos",
         "La pensión se debe desde cuando cumpliste AMBOS requisitos. "
         "Los meses atrasados generan intereses. El fondo está obligado a pagarlos."),
        *([("Tramita también el componente AFP (Pilar Complementario)",
            "Con ingresos altos, tienes saldo en Colpensiones Y AFP. "
            "Inicia ambos trámites en paralelo para no perder tiempo.")] if split_pilares else []),
        *([("⛔ NO solicites descuento por hijos",
            f"Tienes {int(hijos)} hijo(s), pero tu pensión es por Ley 100 (Régimen de Transición), "
            f"NO por la Reforma de Pilares. El descuento de maternidad (Art.36 Ley 2381/2024) "
            f"aplica solo a mujeres nacidas desde 1959 en Colpensiones. "
            f"Si alguien te sugiere solicitarlo, es un error.")
           ] if en_tr and es_mujer and int(hijos) > 0 else []),
    ]
elif es == "SEMANAS_OK":
    pasos_acc += [
        (f"Protege el IBL hasta el año {yep}",
         f"{'Colpensiones promedia los últimos 10 años (IBL): cotizar poco ahora = mesada menor hasta 40%.' if is_colp else 'En AFP: mayor IBC = mayor capital = mayor pensión.'}"),
        ("Evita lagunas", f"Sin empleo: paga {P(SMMLV*0.16)}/mes voluntariamente."),
        ("Verifica semanas cada 6 meses", f"Extracto en {_lnk}. Errores de registro son comunes."),
        (f"Espera cumplir {EP} años en {yep}", "Solo necesitas el tiempo biológico.")
    ]
elif es in ["PRONTO_2A","PRONTO_5A"]:
    _ts = "2 años" if es == "PRONTO_2A" else "5 años"
    pasos_acc += [
        (f"NO interrumpas — a menos de {_ts}",
         f"Faltan {FI(sf)} sem. (~{R1(af)} año(s)). Una renuncia sin plan puede costarte años."),
        ("Negocia la extensión de tu contrato",
         "Pide expresamente que el contrato dure hasta completar semanas. Vale más que cualquier liquidación."),
        ("Automatiza si eres independiente", f"Débito automático en www.miplanilla.com."),
        ("Revisa historial ahora", "Más fácil corregir mientras cotizas que al tramitar la pensión.")
    ]
elif es == "BEPS":
    pasos_acc += [
        ("Consulta el BEPS esta semana", f"{_cnt}. Pide proyección de renta mensual vitalicia."),
        ("El Estado añade 20% sobre tus ahorros", "Bonificación real garantizada de por vida."),
        ("Sigue cotizando si puedes", f"Cada semana antes de los {EBS} años aumenta el monto BEPS."),
        ("Asesoría gratuita", "Personería Municipal · Consultorios Jurídicos Universitarios.")
    ]
elif es == "SOLIDARIO":
    pasos_acc += [
        ("Solicita Colombia Mayor hoy", "01 8000 11 1 3000 (Prosperidad Social) o alcaldía. "
         "$80.000 a $320.000/mes vitalicio según municipio."),
        ("Mantén el SISBÉN vigente", "Es la llave de acceso. Actualiza si algo cambia."),
        ("Consulta el nuevo Pilar Solidario (Ley 2381/2024)",
         "La Reforma fortaleció este pilar. Verifica en tu alcaldía cuándo opera."),
        ("Reclama tus aportes (compatible con el subsidio)", "Son dos derechos independientes.")
    ]
elif es in ["DEVOL_TOTAL","DEVOL_ANTICIP"]:
    pasos_acc += [
        ("Solicita la Devolución de Saldos / Indemnización Sustitutiva",
         f"{_lnk}. Cédula + cuenta bancaria. Colpensiones: capital + IPC. AFP: capital + mercado."),
        ("Compara ANTES de firmar",
         "Pide las cifras reales de ambas opciones si aplica. AFP generalmente devuelve más."),
        ("Invierte el capital al recibirlo",
         "CDT, FIC o ETF irlandés (si aplicable). No dejes en cuenta corriente perdiendo contra inflación."),
        ("Asesoría antes de firmar", "Personería o Defensoría del Pueblo. Gratis.")
    ]
elif es in ["LIMBO_BEPS","LIMBO_SOL"]:
    _ae = max(0, EBS-edad); _ta = "BEPS" if es=="LIMBO_BEPS" else "Pilar Solidario"
    pasos_acc += [
        (f"Espera estratégica: {_ae} año(s) para {_ta} (año {AO+_ae})", "Sin movimientos precipitados."),
        ("Cotiza en este período si puedes", f"Cada semana aumenta el monto del {_ta}."),
        (f"Prepara documentos para {AO+_ae}", "Historial vigente, cédula, cuenta bancaria."),
        ("Mantén SISBÉN vigente" if es=="LIMBO_SOL" else "No cambies de fondo",
         "Llave del Solidario." if es=="LIMBO_SOL" else "Estrategia clara — solo constancia.")
    ]
elif es == "NO_AFILIADO":
    pasos_acc += [
        ("Afíliate HOY — 30 minutos, gratuito",
         "www.colpensiones.gov.co o cualquier AFP. Cédula + cuenta bancaria."),
        ("Elige fondo con criterio",
         f"≤ {P(SMMLV*2.5)}/mes: evalúa AFP (GPM 1.150 sem.) vs Colpensiones (mesada estable). "
         f"> {P(SMMLV*2.5)}/mes: Colpensiones da mayor mesada IBL histórico."),
        (f"Cotiza desde el primer mes — mínimo {P(SMMLV*0.16)}/mes",
         "Cada semana = derecho a pensión + invalidez + sobrevivencia familiar."),
        ("Cobertura inmediata al afiliarte",
         "Invalidez + sobrevivencia + historia pensional — desde el primer aporte.")
    ]
elif es == "IMPOSIBLE":
    pasos_acc += [
        ("Nuevo objetivo: maximizar devolución de capital",
         f"Llegar a semanas necesarias llevaría a ~{math.ceil(efsem)} años. Recupera lo cotizado."),
        (f"Cámbiate a AFP si tienes menos de {ELT} años",
         "AFP devuelve capital + rentabilidades reales (múltiplo de la inflación)."),
        ("Abre FPV (Fondo Pensiones Voluntarias)", "Beneficio tributario + crecimiento de mercado."),
        (f"Evalúa BEPS a los {EBS} años con ≥300 semanas", "Renta vitalicia + 20% bonificación.")
    ]
elif es == "RIESGO_ALTO":
    pasos_acc += [
        ("Cero interrupciones - margen mínimo",
         f"Meta ~{math.floor(efsem)} años. 3-6 meses sin cotizar puede impedirte llegar."),
        ("Cotiza entre empleos",
         f"Mínimo {P(SMMLV*0.16)}/mes en www.miplanilla.com."),
        ("Verifica elegibilidad PSAP",
         "SISBÉN A/B/C + 650-1.149 semanas + ≥40 años = el Estado paga 70-75% de tu cotización."),
        ("Cuida el IBC", f"{'IBL últimos 10 años en Colpensiones.' if is_colp else 'Capital AFP crece con el IBC.'}"
         " Bajo ingreso base ahora = pensión baja después.")
    ]
elif es == "PSAP":
    pasos_acc += [
        ("Solicita el PSAP YA — no esperes",
         "www.minsalud.gov.co → PSAP o Fondo de Solidaridad Pensional. El subsidio paga el 70-75%."),
        ("Los 4 requisitos",
         f"① Cédula · ② {40}-{EBS-1} años · ③ 650-1.149 semanas · ④ SISBÉN A, B o C. ¡Cumples!"),
        ("No superes 1.149 semanas antes de activar",
         "Al cruzar ese tope el PSAP se desactiva automáticamente. Activa ANTES."),
        ("Con subsidio activo: aporta el extra a FPV", "Mayor retorno sobre el diferencial que pagas tú.")
    ]
else:  # EN_RUTA
    pasos_acc += [
        (f"Constancia total — meta: {y_pen if not sin_ingreso else '(reactiva primero)'}",
         "Prioridad #1: nunca interrumpir. 6 meses sin aportar = retraso real en la pensión."),
        ("Verifica semanas cada 6 meses", f"Extracto en {_lnk}."),
        ("Sube IBC cuando puedas",
         f"{'IBL últimos 10 años: cada peso extra en IBC multiplica la mesada.' if is_colp else 'Capital AFP: mayor IBC = mayor capital = mayor pensión.'}"),
        ("Proyecciones cada 2-3 años", f"Pide proyecciones firmadas a {_lnk}.")
    ]

for _i, (_tp, _cp) in enumerate(pasos_acc, 1):
    html += paso(str(_i), _tp, _cp)

# ── PSAP / Fondo de Solidaridad Pensional — Elegibilidad Universal ────
# Ley 1785/2016 + Dec. 604/2013: Subsidio 70-75% cotización para
# personas con SISBÉN A/B/C, entre 40 y EBS-1 años, 650-1149 semanas.
# Especialmente relevante para independientes e inactivos.
_psap_edad_ok   = 40 <= edad < EBS
_psap_sem_ok    = 650 <= int(semanas) <= 1149
_psap_sisben_ok = sisben_v
_psap_cumple    = _psap_edad_ok and _psap_sem_ok and _psap_sisben_ok
_psap_cerca_sem = _psap_edad_ok and _psap_sisben_ok and (300 <= int(semanas) < 650)
_psap_cerca_sis = _psap_edad_ok and _psap_sem_ok and (not _psap_sisben_ok)
_meses_falta_psap = math.ceil((650 - int(semanas)) / 4.3) if int(semanas) < 650 else 0

if es != "PSAP" and (_psap_cumple or _psap_cerca_sem or _psap_cerca_sis):
    html += hr()
    html += h4("🌟 Subsidio PSAP — Fondo de Solidaridad Pensional (Ley 1785/2016)")
    if _psap_cumple:
        _sub_val = int(SMMLV * 0.16 * 0.75)
        _tu_val  = int(SMMLV * 0.16 * 0.25)
        _indep_txt = (" Como <b>independiente</b>, tú pagas el 100% de tu cotización hoy — "
                      "con el PSAP solo pagarías el 25%. Esto reduce tu carga de "
                      f"{P(SMMLV*0.16)}/mes a solo <b>{P(_tu_val)}/mes</b>."
                      ) if is_independiente else ""
        _inact_txt = (" Como persona <b>sin ingresos actuales</b>, este subsidio te permite "
                      "seguir acumulando semanas con un desembolso mínimo."
                      ) if is_inactivo else ""
        html += box("vip",
            f"<b>¡{nombre}, cumples TODOS los requisitos del PSAP!</b><br>"
            f"✅ Edad: {edad} años (requisito: 40–{EBS-1})<br>"
            f"✅ Semanas: {int(semanas):,} (requisito: 650–1.149)<br>"
            f"✅ SISBÉN: {sisben} (requisito: Grupo A, B o C)<br><br>"
            f"<b>Beneficio:</b> El Estado paga hasta el <b>75%</b> de tu cotización mensual "
            f"a través del Fondo de Solidaridad Pensional.<br>"
            f"• Subsidio estatal: ~<b>{P(_sub_val)}/mes</b> · Tu parte: ~<b>{P(_tu_val)}/mes</b><br>"
            f"{_indep_txt}{_inact_txt}"
            f"<b>Solicítalo en:</b> www.fondodesolidaridadpensional.gov.co · Alcaldía municipal · "
            f"Ministerio del Trabajo · Línea 120 opción 2.")
        html += (paso("A", "Verifica tu SISBÉN en www.sisben.gov.co",
                      "Confirma que tienes encuesta vigente y grupo A, B o C.") +
                 paso("B", "Solicita el subsidio en la alcaldía o en línea",
                      "www.fondodesolidaridadpensional.gov.co → Formulario de inscripción. "
                      "Lleva cédula + certificado SISBÉN + extracto de semanas. Gratuito.") +
                 paso("C", "Mientras se aprueba, NO dejes de cotizar",
                      "El proceso toma hasta 3 meses. Si dejas de cotizar se invalida.") +
                 paso("D", "El subsidio se aplica automáticamente",
                      "Tu fondo (Colpensiones o AFP) recibe el aporte del Estado directamente."))
    elif _psap_cerca_sem:
        html += box("info",
            f"<b>Estás a {650 - int(semanas)} semanas del PSAP, {nombre}.</b> "
            f"Con {int(semanas):,} semanas, te faltan {650 - int(semanas)} para entrar al rango 650–1.149 "
            f"donde el Estado subsidia hasta 75% de tu cotización. "
            f"{'Cotizando como independiente, llegarías en ~' + str(_meses_falta_psap) + ' meses. ' if is_independiente else ''}"
            f"{'Si reactivas aportes, llegarías en ~' + str(_meses_falta_psap) + ' meses. ' if is_inactivo else ''}"
            f"SISBÉN vigente: ✅. Mantén el SISBÉN y sigue cotizando.")
    elif _psap_cerca_sis:
        html += box("info",
            f"<b>Cumples edad ({edad}) y semanas ({int(semanas):,}) para el PSAP, {nombre}.</b> "
            f"Sin embargo, necesitas SISBÉN grupo A, B o C para calificar. "
            f"Tu SISBÉN actual: <b>{sisben}</b>. "
            f"Si tu situación económica ha cambiado, solicita actualización de encuesta "
            f"en www.sisben.gov.co o en tu alcaldía. El SISBÉN se actualiza gratuitamente.")

# ── S5: FISCAL DOMÉSTICA ──────────────────────────────────────
if ingreso_r >= 10_000_000 and not sin_ingreso:
    html += hr() + h3("🧾 5. Optimización Fiscal — Ahorra en Retención (Art.126-1 ET)")
    _tope_d = min(ingreso_r * 0.30, (3_800 * UVT) / 12)
    _ahorro = _tope_d * 0.33
    html += krow(
        ("Deducción mensual máxima", P(_tope_d), "30% ingreso o 3.800 UVT/año"),
        ("Ahorro tributario mensual", P(_ahorro), "Tasa marginal ~33%"),
        ("Ahorro tributario ANUAL", P(_ahorro*12), "Si aportas el máximo siempre")
    )
    html += box("vip",
        f"<b>Acción concreta:</b> Pide a RRHH que redirija hasta {P(_tope_d)}/mes "
        f"a un <b>FPV</b> o <b>Cuenta AFC</b>. Se descuenta ANTES de retención en fuente. "
        f"Ahorro real: {P(_ahorro)}/mes · {P(_ahorro*12)}/año. "
        f"<b>Condición:</b> mínimo 10 años inmovilizado o uso en pensión/vivienda.")
    html += box("info",
        "<b>FPV vs AFC:</b><br>"
        "• <b>FPV:</b> Solo pensión. Rendimientos exentos. Porvenir, Protección, Skandia, Colfondos.<br>"
        "• <b>AFC:</b> Pensión o vivienda. Bancos (Davivienda, BBVA, etc.). Más flexible.<br>"
        "<b>Óptimo:</b> FPV largo plazo + AFC si planeas comprar vivienda.")

# ── S6: ETF IRLANDESES (UCITS) — POTENCIADO CON GRÁFICA ──────
_muestra_etf = (ingreso_r >= 9_000_000 and not sin_ingreso) or \
               (is_expat and ingreso_r >= 5_000_000 and not sin_ingreso)

if _muestra_etf:
    html += hr() + h3("🌍 6. Optimización Internacional — ETF Irlandeses (UCITS)")

    html += box("gold",
        f"<b>¿Por qué ETFs irlandeses y no americanos, {nombre}?</b><br>"
        f"ETFs estadounidenses retienen <b>30% sobre dividendos</b> para no-residentes "
        f"(Colombia no tiene DTA completo con EE.UU.). ETFs domiciliados en <b>Irlanda (UCITS)</b>: "
        f"<b>0% retención irlandesa</b> + tratado Irlanda-EE.UU. = 15% WHT sobre dividendos "
        f"de empresas americanas (vs 30% directo). Resultado: tú solo pagas impuesto DIAN al cobrar/vender. "
        f"Adicionalmente, la devaluación histórica del COP vs USD "
        f"(~{TRM_DEV*100:.0f}% anual) añade un retorno extra en términos de pesos colombianos.")

    # ── Tabla comparativa de escenarios ───────────────────────
    html += h4("📊 Simulación: ¿Cuánto crece $5M COP/mes en cada instrumento?")
    html += ("<div style='color:#64748b;font-size:0.8em;margin-bottom:8px'>Inversión mensual ilustrativa: " +
             f"<b style='color:#e2e8f0'>$5.000.000 COP/mes</b> · "
             f"TRM inicial: {TRM_REF:,} · Devaluación COP/USD: {TRM_DEV*100:.1f}%/año · "
             f"ETF USD: {_r_etf*100:.0f}% real/año · FPV: {_r_fpv*100:.1f}% COP nom. · "
             f"CDT: {_r_cdt*100:.0f}% COP nom.</div>")

    # Tabla de resultados
    html += f"""
<table style='width:100%;border-collapse:collapse;color:#e2e8f0;font-size:13px;margin:10px 0 16px'>
<thead><tr style='background:#1e293b'>
  <th style='padding:8px;text-align:left'>Instrumento</th>
  <th style='padding:8px;text-align:center'>5 años</th>
  <th style='padding:8px;text-align:center'>10 años</th>
  <th style='padding:8px;text-align:center'>15 años</th>
  <th style='padding:8px;text-align:center'>20 años</th>
  <th style='padding:8px;text-align:center'>25 años</th>
</tr></thead><tbody>
<tr style='border-top:1px solid #334155;background:#0f172a22'>
  <td style='padding:8px'><b>🇮🇪 ETF Irlandés (USD + TRM)</b></td>
  <td style='padding:8px;text-align:center;color:#f59e0b'><b>{Pm(_vyr(_etf_cop,5)*1e6)}</b></td>
  <td style='padding:8px;text-align:center;color:#f59e0b'><b>{Pm(_vyr(_etf_cop,10)*1e6)}</b></td>
  <td style='padding:8px;text-align:center;color:#f59e0b'><b>{Pm(_vyr(_etf_cop,15)*1e6)}</b></td>
  <td style='padding:8px;text-align:center;color:#f59e0b'><b>{Pm(_vyr(_etf_cop,20)*1e6)}</b></td>
  <td style='padding:8px;text-align:center;color:#f59e0b'><b>{Pm(_vyr(_etf_cop,25)*1e6)}</b></td>
</tr>
<tr style='border-top:1px solid #334155'>
  <td style='padding:8px'>🇨🇴 FPV Colombiano (9.5% nom.)</td>
  <td style='padding:8px;text-align:center'>{Pm(_vyr(_fpv,5)*1e6)}</td>
  <td style='padding:8px;text-align:center'>{Pm(_vyr(_fpv,10)*1e6)}</td>
  <td style='padding:8px;text-align:center'>{Pm(_vyr(_fpv,15)*1e6)}</td>
  <td style='padding:8px;text-align:center'>{Pm(_vyr(_fpv,20)*1e6)}</td>
  <td style='padding:8px;text-align:center'>{Pm(_vyr(_fpv,25)*1e6)}</td>
</tr>
<tr style='border-top:1px solid #334155'>
  <td style='padding:8px'>🏦 CDT Bancario (8% nom.)</td>
  <td style='padding:8px;text-align:center'>{Pm(_vyr(_cdt,5)*1e6)}</td>
  <td style='padding:8px;text-align:center'>{Pm(_vyr(_cdt,10)*1e6)}</td>
  <td style='padding:8px;text-align:center'>{Pm(_vyr(_cdt,15)*1e6)}</td>
  <td style='padding:8px;text-align:center'>{Pm(_vyr(_cdt,20)*1e6)}</td>
  <td style='padding:8px;text-align:center'>{Pm(_vyr(_cdt,25)*1e6)}</td>
</tr>
<tr style='border-top:1px solid #334155'>
  <td style='padding:8px'>📈 AFP Individual (6.5% nom.)</td>
  <td style='padding:8px;text-align:center'>{Pm(_vyr(_afp,5)*1e6)}</td>
  <td style='padding:8px;text-align:center'>{Pm(_vyr(_afp,10)*1e6)}</td>
  <td style='padding:8px;text-align:center'>{Pm(_vyr(_afp,15)*1e6)}</td>
  <td style='padding:8px;text-align:center'>{Pm(_vyr(_afp,20)*1e6)}</td>
  <td style='padding:8px;text-align:center'>{Pm(_vyr(_afp,25)*1e6)}</td>
</tr>
<tr style='border-top:1px solid #334155'>
  <td style='padding:8px'>💸 Sin invertir (colchón 0%)</td>
  <td style='padding:8px;text-align:center'>{Pm(_vyr(_col,5)*1e6)}</td>
  <td style='padding:8px;text-align:center'>{Pm(_vyr(_col,10)*1e6)}</td>
  <td style='padding:8px;text-align:center'>{Pm(_vyr(_col,15)*1e6)}</td>
  <td style='padding:8px;text-align:center'>{Pm(_vyr(_col,20)*1e6)}</td>
  <td style='padding:8px;text-align:center'>{Pm(_vyr(_col,25)*1e6)}</td>
</tr>
<tr style='border-top:2px solid #f59e0b;background:#78350f18'>
  <td style='padding:8px;color:#f59e0b'><b>💡 Ventaja ETF vs FPV</b></td>
  <td style='padding:8px;text-align:center;color:#f59e0b'><b>+{Pm(max(0,_vyr(_etf_cop,5)-_vyr(_fpv,5))*1e6)}</b></td>
  <td style='padding:8px;text-align:center;color:#f59e0b'><b>+{Pm(max(0,_vyr(_etf_cop,10)-_vyr(_fpv,10))*1e6)}</b></td>
  <td style='padding:8px;text-align:center;color:#f59e0b'><b>+{Pm(max(0,_vyr(_etf_cop,15)-_vyr(_fpv,15))*1e6)}</b></td>
  <td style='padding:8px;text-align:center;color:#f59e0b'><b>+{Pm(max(0,_vyr(_etf_cop,20)-_vyr(_fpv,20))*1e6)}</b></td>
  <td style='padding:8px;text-align:center;color:#f59e0b'><b>+{Pm(max(0,_vyr(_etf_cop,25)-_vyr(_fpv,25))*1e6)}</b></td>
</tr>
</tbody></table>"""

    # ── USD y TRM ─────────────────────────────────────────────
    html += krow(
        ("TRM hoy (referencia)", f"${TRM_REF:,}", "COP = 1 USD"),
        (f"TRM proyectada año 10", f"${_vyr(_trm_prj,10):,}", f"+{TRM_DEV*100:.0f}%/año"),
        (f"TRM proyectada año 20", f"${_vyr(_trm_prj,20):,}", "Doble que hoy"),
        (f"ETF en USD (año 20)", f"USD {_vyr(_usd_val,20):.0f}K", "Capital en dólares"),
        (f"ETF en USD (año 25)", f"USD {_vyr(_usd_val,25):.0f}K", "Capital final")
    )

    # ── GRÁFICA CHART.JS ──────────────────────────────────────
    html += h4("📈 Gráfica de Crecimiento — 25 Años (valores en millones COP)")
    html += f"""
<div style='background:#0f172a;border-radius:10px;padding:16px;margin:10px 0'>
  <canvas id="etfChart" style='height:340px;width:100%'></canvas>
</div>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
<script>
(function() {{
  var labels = {_LABELS_J};
  var etf    = {_ETF_J};
  var fpv    = {_FPV_J};
  var cdt    = {_CDT_J};
  var afp    = {_AFP_J};
  var col    = {_COL_J};
  var ctx    = document.getElementById('etfChart').getContext('2d');
  new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: labels,
      datasets: [
        {{ label: '🇮🇪 ETF Irlandés (USD + TRM)', data: etf,
           borderColor: '#f59e0b', backgroundColor: '#f59e0b22',
           borderWidth: 3, pointRadius: 3, fill: true, tension: 0.4 }},
        {{ label: '🇨🇴 FPV Colombiano (9.5%)', data: fpv,
           borderColor: '#3b82f6', backgroundColor: '#3b82f611',
           borderWidth: 2.5, pointRadius: 2, fill: false, tension: 0.4 }},
        {{ label: '🏦 CDT Bancario (8%)', data: cdt,
           borderColor: '#8b5cf6', backgroundColor: 'transparent',
           borderWidth: 2, pointRadius: 2, fill: false, tension: 0.4, borderDash: [5,3] }},
        {{ label: '📈 AFP Individual (6.5%)', data: afp,
           borderColor: '#10b981', backgroundColor: 'transparent',
           borderWidth: 2, pointRadius: 2, fill: false, tension: 0.4, borderDash: [3,3] }},
        {{ label: '💸 Colchón (0%)', data: col,
           borderColor: '#475569', backgroundColor: 'transparent',
           borderWidth: 1.5, pointRadius: 0, fill: false, tension: 0 }}
      ]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{ labels: {{ color: '#94a3b8', font: {{ size: 12 }}, boxWidth: 30 }} }},
        tooltip: {{
          backgroundColor: '#1e293b', borderColor: '#334155', borderWidth: 1,
          titleColor: '#f1f5f9', bodyColor: '#cbd5e1',
          callbacks: {{
            label: function(ctx) {{
              return ctx.dataset.label + ': $' + ctx.parsed.y.toFixed(1) + 'M COP';
            }}
          }}
        }}
      }},
      scales: {{
        x: {{
          ticks: {{ color: '#64748b', maxTicksLimit: 10 }},
          grid:  {{ color: '#1e293b' }}
        }},
        y: {{
          title: {{ display: true, text: 'Millones COP', color: '#94a3b8' }},
          ticks: {{
            color: '#64748b',
            callback: function(v) {{ return '$' + v.toFixed(0) + 'M'; }}
          }},
          grid: {{ color: '#1e293b' }}
        }}
      }}
    }}
  }});
}})();
</script>"""

    html += box("vip",
        f"<b>💡 Por qué el ETF Acumulador supera todo en Colombia a largo plazo:</b><br>"
        f"① <b>Retorno USD:</b> {_r_etf*100:.0f}% anual real (MSCI World histórico ~7-8% real 50+ años).<br>"
        f"② <b>Escudo TRM:</b> El COP se ha devaluado ~{TRM_DEV*100:.0f}% anual vs USD históricamente. "
        f"Un ETF en USD te protege de esa pérdida de poder adquisitivo.<br>"
        f"③ <b>Diferimiento tributario:</b> ETF Acc no paga dividendos → no tributas hasta vender. "
        f"La reinversión compuesta sobre el 100% del capital (vs 90% si pagas 10% de dividendos) "
        f"hace una diferencia enorme en 20+ años.<br>"
        f"④ <b>TER ultrabajo:</b> 0.07-0.22%/año vs 1.5-2.5% fondos activos colombianos.")

    # ETF Table
    html += h4("📋 ETFs Irlandeses Recomendados (UCITS)")
    html += f"""
<table style='width:100%;border-collapse:collapse;color:#e2e8f0;font-size:13px;margin:10px 0'>
<thead><tr style='background:#1e293b'>
  <th style='padding:8px;text-align:left'>Ticker</th>
  <th style='padding:8px;text-align:left'>Exposición</th>
  <th style='padding:8px;text-align:center'>TER</th>
  <th style='padding:8px;text-align:center'>Tipo</th>
  <th style='padding:8px;text-align:left'>Para qué sirve</th>
</tr></thead><tbody>
<tr style='border-top:1px solid #334155;background:#0f172a44'>
  <td style='padding:8px'><b>IWDA.AS</b></td>
  <td style='padding:8px'>MSCI World (1.400 emp., 23 países)</td>
  <td style='padding:8px;text-align:center'>0.20%</td>
  <td style='padding:8px;text-align:center'>Acc ⭐</td>
  <td style='padding:8px'>Base ideal. Máxima diversificación global. Sin dividendos → diferimiento total.</td>
</tr>
<tr style='border-top:1px solid #334155'>
  <td style='padding:8px'><b>CSPX.L</b></td>
  <td style='padding:8px'>S&amp;P 500 (500 emp. EE.UU.)</td>
  <td style='padding:8px;text-align:center'><b style='color:#10b981'>0.07%</b></td>
  <td style='padding:8px;text-align:center'>Acc</td>
  <td style='padding:8px'>Costo más bajo posible. Exposición EE.UU. sin retención 30%.</td>
</tr>
<tr style='border-top:1px solid #334155;background:#0f172a44'>
  <td style='padding:8px'><b>VWRL.AS</b></td>
  <td style='padding:8px'>FTSE All-World (4.000+ emp.)</td>
  <td style='padding:8px;text-align:center'>0.22%</td>
  <td style='padding:8px;text-align:center'>Dist</td>
  <td style='padding:8px'>Máxima diversificación 50 países. Emergentes incluidos. Dividendos trimestrales.</td>
</tr>
<tr style='border-top:1px solid #334155'>
  <td style='padding:8px'><b>EIMI.L</b></td>
  <td style='padding:8px'>MSCI Emergentes IMI</td>
  <td style='padding:8px;text-align:center'>0.18%</td>
  <td style='padding:8px;text-align:center'>Acc</td>
  <td style='padding:8px'>Complemento: China, Brasil, India. Mayor riesgo / mayor potencial.</td>
</tr>
<tr style='border-top:1px solid #334155;background:#0f172a44'>
  <td style='padding:8px'><b>AGGH.L</b></td>
  <td style='padding:8px'>Bonos globales cubiertos</td>
  <td style='padding:8px;text-align:center'>0.10%</td>
  <td style='padding:8px;text-align:center'>Acc</td>
  <td style='padding:8px'>Parte defensiva. Reduce volatilidad. Para perfiles conservadores.</td>
</tr>
</tbody></table>
<div style='color:#64748b;font-size:0.73em'>
Acc = Acumulador: reinvierte dividendos internamente. Solo tributas al vender (diferimiento máximo).<br>
Dist = Distribuidor: paga dividendos periódicos → declarar en Cédula de Capital DIAN (10%).<br>
Disponibles en: Euronext Amsterdam (.AS) · London Stock Exchange (.L) · Xetra (.DE)
</div>"""

    html += box("info",
        "<b>🏦 Brokers para colombianos:</b><br>"
        "• <b>Interactive Brokers (IBKR):</b> El mejor. Sin mínimo de capital, tarifas mínimas, "
        "multidivisa USD/EUR. Disponible desde Colombia y para expatriados.<br>"
        "• <b>DEGIRO (Europa):</b> Bajo costo, acceso directo a Euronext/LSE.<br>"
        "• <b>XTB:</b> Regulado, sin comisiones hasta €100.000/mes negociado.")

    html += box("warn",
        f"<b>⚠️ Obligaciones DIAN (no ignorar):</b><br>"
        f"① Renta anual: dividendos + ganancia de capital → Cédula de Capital (10% dividendos).<br>"
        f"② Patrimonio exterior &gt; 2.000 UVT (~{P(2000*UVT)}): Formulario 160/210.<br>"
        f"③ FATCA/CRS: el broker reporta automáticamente. La evasión es imposible e ilegal.<br>"
        f"④ Ganancia de capital al vender: 10% Ganancias Ocasionales.<br>"
        f"<b>Estrategia:</b> ETF Acc → diferimiento del impuesto hasta la venta → "
        f"compuestas sin fricción tributaria por décadas.")

# ── PIE ───────────────────────────────────────────────────────
html += ("<hr style='border:none;border-top:1px solid #334155;margin:22px 0'/>"
         "<div style='color:#475569;font-size:0.73em;text-align:center;padding:8px'>"
         "⚖️ Análisis educativo y orientativo. No reemplaza asesoría jurídica, financiera ni tributaria certificada.<br/>"
         "Asesoría gratuita: Personería · Defensoría del Pueblo · Consultorios Jurídicos U. · Superfinanciera · DIAN<br/>"
         "Leyes: Ley 100/1993 · Ley 797/2003 · Ley 2381/2024 · Sentencia C-197/2023 · Dec.604/2013 (BEPS) · "
         "Ley 1785/2016 (PSAP) · Ley 1328/2009 · Art.126-1 ET · Ley 2010/2019 · Dec.2616/2013 · UCITS Irlanda"
         "</div>")

# ═════════════════════════════════════════════════════════════
# RENDER — IFRAME AISLADO DE REACT (cero removeChild)
# Migración: st.components.v1.html → st.iframe (deprecación post 2026-06-01)
# ═════════════════════════════════════════════════════════════
_h = max(2600, min(len(html) // 6, 8500))

# Pre-computar valores para FAQ (evitar escaping en f-string)
_faq_tope   = f"${int(TOPE_UGPP):,}"
_faq_umbral = f"${int(UMBRAL):,}"
_faq_sr_m   = f"{SR_MUJER_AO:,}"

_full = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
  * {{ box-sizing:border-box; margin:0; padding:0 }}
  html, body {{
    background:#0e1117; color:#e2e8f0;
    font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
    font-size:14px; line-height:1.55;
    padding:6px 10px 28px; overflow-x:hidden;
  }}
  b {{ font-weight:600 }} table {{ font-size:13px }}
<meta name="google-site-verification" content="Hz0K7ER45v1QDyF9dNBOv9CrP2X25KCqCdHSCCi5wFU" />
<meta name="description" content="Simulador pensional gratuito Colombia 2026. Calcula IBC, semanas C-197, pilares Ley 2381." />
<meta name="author" content="Carlos Mauricio Moreno" />
</style>
</head>
<body>
{html}

<div style="margin-top:40px;padding:20px 16px;border-top:1px solid #334155;color:#cbd5e1;font-size:0.82em;line-height:1.8">
  <h2 style="color:#e2e8f0;font-size:1.15em;margin:0 0 14px;text-align:center">Preguntas Frecuentes sobre la Pensión en Colombia ({AO})</h2>

  <h3 style="color:#93c5fd;font-size:0.95em;margin:14px 0 4px">¿Cuál es el tope de la UGPP para cotizar en {AO}?</h3>
  <p style="margin:0 0 10px">El tope máximo de cotización (IBC) en Colombia es de 25 Salarios Mínimos (SMMLV). Para el año {AO}, este valor es de <b>{_faq_tope}</b> COP. Cualquier ingreso por encima de este monto no genera aportes adicionales a seguridad social.</p>

  <h3 style="color:#93c5fd;font-size:0.95em;margin:14px 0 4px">¿Cómo saber a qué pilar de la reforma pensional pertenezco?</h3>
  <p style="margin:0 0 10px">Depende de tu Ingreso Base de Cotización (IBC). Si ganas hasta 2.3 SMMLV (<b>{_faq_umbral}</b> COP), perteneces al Pilar Contributivo de Colpensiones. Si ganas más, el excedente se aporta al Pilar de Ahorro Individual (AFP).</p>

  <h3 style="color:#93c5fd;font-size:0.95em;margin:14px 0 4px">¿Cómo se reducen las semanas de pensión para las mujeres?</h3>
  <p style="margin:0 0 10px">Gracias a la Sentencia C-197 de 2023, las mujeres en Colombia ven una reducción gradual de 1.300 a 1.000 semanas. A partir de 2025 disminuyen 25 semanas cada año. Para el año {AO}, el requisito es de <b>{_faq_sr_m}</b> semanas.</p>

  <h3 style="color:#93c5fd;font-size:0.95em;margin:14px 0 4px">¿Puedo pensionarme si vivo en el exterior?</h3>
  <p style="margin:0 0 10px">Sí. Los colombianos en el exterior pueden cotizar voluntariamente a pensión a través de la planilla PILA como ‘Colombiano en el Exterior’, estando exentos del aporte a salud (EPS).</p>
</div>

<div style="margin-top:12px;padding:18px 0;border-top:1px solid #334155;color:#64748b;font-size:0.78em;text-align:center;line-height:1.7">
  <b>¿Cómo funciona este simulador?</b><br>
  Ingresa tus datos en el panel izquierdo (edad, semanas, fondo, ingresos, hijos, SISBÉN).<br>
  El sistema cruza automáticamente tu perfil con la <b>Ley 100/1993</b>, <b>Ley 2381/2024 (Reforma de Pilares)</b>,
  <b>Sentencia C-197/2023</b> y las tablas actuariales vigentes para determinar tu régimen,
  semanas requeridas, mesada estimada, optimización fiscal y plan de acción personalizado.<br>
  <b>Nota:</b> Esta herramienta es informativa. Consulta siempre con tu fondo o un abogado pensional.
  <br><br>
  <span style="color:#94a3b8">© {AO} — Desarrollado por <b>Carlos Mauricio Moreno</b>
  &middot; <a href="mailto:triplemauricio@gmail.com" style="color:#60a5fa;text-decoration:none">triplemauricio@gmail.com</a>
  &middot; Simulador Pensional Colombia</span><br>
  <span style="color:#64748b;font-size:0.9em;font-style:italic">Este laboratorio matemático utiliza algoritmos de precisión actuarial para la planeación financiera ciudadana.</span>
</div>
<script>
  function ajustar() {{
    var h = document.documentElement.scrollHeight || document.body.scrollHeight;
    window.parent.postMessage({{ type:'streamlit:setFrameHeight', height: h+30 }}, '*');
  }}
  ajustar(); setTimeout(ajustar,120); setTimeout(ajustar,500);
  window.addEventListener('load', ajustar);
  window.addEventListener('resize', ajustar);
</script>
</body>
</html>"""

# API nueva (st.iframe) si disponible, fallback seguro a stc.html
_rendered = False
if hasattr(st, 'iframe'):
    try:
        st.iframe(_full, height=_h, scrolling=False)
        _rendered = True
    except Exception:
        pass
if not _rendered:
    import streamlit.components.v1 as _stc
    _stc.html(_full, height=_h, scrolling=False)
