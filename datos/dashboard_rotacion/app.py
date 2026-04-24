#!/usr/bin/env python3
"""Dashboard de Rotación de Personal — Grupo Master"""

import statistics
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import requests
from datetime import date, timedelta, datetime
from dateutil.relativedelta import relativedelta

pio.templates.default = "plotly_white"

# ─── Página ─────────────────────────────────────────────────
st.set_page_config(
    page_title="Rotación — Grupo Master",
    page_icon="📊",
    layout="wide",
)

# ─── Constantes ─────────────────────────────────────────────
API_URL = "https://traficonuevo.masterbus.net/api/v1/auto/e"
AÑO_INICIO = 2020

# Branding MasterBus (extraído de traficonuevo.masterbus.net)
COLOR_PRIMARY   = "#ED5D3B"   # naranja-rojo principal
COLOR_SECONDARY = "#46BCD2"   # teal secundario
COLOR_ACCENT    = "#8C8987"   # gris acento
COLOR_DANGER    = "#D12F19"   # rojo enlaces / peligro
COLOR_BG        = "#EDEDED"   # fondo general
COLOR_SURFACE   = "#FFFFFF"   # tarjetas
COLOR_TEXT      = "#333333"   # texto principal
COLOR_MUTED     = "#8C8987"   # texto secundario
COLOR_BORDER    = "#CCCCCC"   # bordes

GRUPO_MASTER = {
    "MASTER BUS S.A",
    "MASTER BUS SA",
    "MASTER BUS TASA",
    "SINTRA",
    "M B M S.A.",
    "MASTER MINING SA",
    "SOLUCIONES IOT S.A.",
    "ENDUROCO LATAM SA",
}

FECHAS_INVALIDAS = {"00/00/0000", ""}

MESES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

# ─── Helper de layout de gráficos ────────────────────────────
def _chart_base(**overrides):
    """Tokens de diseño compartidos — branding MasterBus light mode."""
    base = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=COLOR_SURFACE,
        font=dict(
            family="'Helvetica Neue', Helvetica, Arial, Verdana, sans-serif",
            color=COLOR_MUTED,
            size=12,
        ),
        xaxis=dict(
            showgrid=False, showline=True, zeroline=False,
            linecolor=COLOR_BORDER, tickfont=dict(color=COLOR_MUTED),
        ),
        yaxis=dict(
            showgrid=True, gridcolor="#E8E8E8", zeroline=False,
            linecolor=COLOR_BORDER, tickfont=dict(color=COLOR_MUTED),
            rangemode="tozero",
        ),
        hoverlabel=dict(
            bgcolor=COLOR_SURFACE,
            bordercolor=COLOR_BORDER,
            font=dict(
                family="'Helvetica Neue', Helvetica, Arial, sans-serif",
                color=COLOR_TEXT,
                size=12,
            ),
        ),
        margin=dict(l=10, r=10, t=20, b=10),
    )
    base.update(overrides)
    return base


# ─── Datos ───────────────────────────────────────────────────

def _parse_fecha(s):
    if not s or str(s).strip() in FECHAS_INVALIDAS:
        return None
    try:
        return pd.to_datetime(str(s).strip(), format="%d/%m/%Y").date()
    except ValueError:
        return None


@st.cache_data(ttl=3600, show_spinner="Cargando datos de empleados...")
def cargar_datos():
    resp = requests.get(API_URL, timeout=30)
    resp.raise_for_status()

    df = pd.DataFrame(resp.json())
    df = df[df["empleador"].isin(GRUPO_MASTER)].copy()

    df["fecha_inicio"] = df["fechainicio"].apply(_parse_fecha)
    df["fecha_fin"] = df["fechafin"].apply(_parse_fecha)
    df = df[df["fecha_inicio"].notna()].copy()

    df["cargo"] = df["cargo"].str.strip().str.upper()
    df["str"] = df["str"].str.strip()

    return df, datetime.now()


def calcular_rotacion(df, inicio, fin):
    """Plantilla al inicio del período + bajas + altas + tasa."""
    plantilla = df[
        (df["fecha_inicio"] < inicio)
        & (df["fecha_fin"].isna() | (df["fecha_fin"] >= inicio))
    ]
    bajas = df[
        df["fecha_fin"].notna()
        & (df["fecha_fin"] >= inicio)
        & (df["fecha_fin"] <= fin)
    ]
    altas = df[
        (df["fecha_inicio"] >= inicio)
        & (df["fecha_inicio"] <= fin)
    ]

    n_p = len(plantilla)
    n_b = len(bajas)
    n_a = len(altas)
    tasa = round(n_b / n_p * 100, 2) if n_p > 0 else 0.0

    return n_p, n_b, n_a, tasa, bajas


def periodo_anterior(vista, año, mes):
    if vista == "Mensual":
        primer_dia = date(año, mes, 1)
        fin_ant = primer_dia - timedelta(days=1)
        inicio_ant = date(fin_ant.year, fin_ant.month, 1)
        return inicio_ant, fin_ant
    else:
        return date(año - 1, 1, 1), date(año - 1, 12, 31)


def antigüedad_media_bajas(df_bajas):
    if df_bajas.empty:
        return None
    meses = []
    for _, row in df_bajas.iterrows():
        if row["fecha_inicio"] and row["fecha_fin"]:
            delta = relativedelta(row["fecha_fin"], row["fecha_inicio"])
            meses.append(delta.years * 12 + delta.months)
    return round(statistics.mean(meses), 1) if meses else None


def detectar_anomalia(tasa_actual, serie_historica):
    valores = [v for v in serie_historica if v > 0]
    if len(valores) < 3:
        return False, 0.0, 0.0
    media = statistics.mean(valores)
    stdev = statistics.stdev(valores)
    umbral = media + 2 * stdev
    return tasa_actual > umbral, round(media, 2), round(umbral, 2)


@st.cache_data(ttl=3600)
def calcular_serie(df, vista):
    hoy = date.today()
    filas = []

    if vista == "Mensual":
        cursor = date(AÑO_INICIO, 1, 1)
        while cursor <= hoy:
            fin = (cursor + relativedelta(months=1)) - timedelta(days=1)
            n_p, n_b, n_a, tasa, _ = calcular_rotacion(df, cursor, min(fin, hoy))
            filas.append({
                "periodo": cursor.strftime("%m/%Y"),
                "periodo_dt": cursor,
                "plantilla": n_p,
                "bajas": n_b,
                "altas": n_a,
                "tasa": tasa,
            })
            cursor += relativedelta(months=1)
    else:
        for año in range(AÑO_INICIO, hoy.year + 1):
            inicio = date(año, 1, 1)
            fin = date(año, 12, 31)
            n_p, n_b, n_a, tasa, _ = calcular_rotacion(df, inicio, min(fin, hoy))
            filas.append({
                "periodo": str(año),
                "periodo_dt": inicio,
                "plantilla": n_p,
                "bajas": n_b,
                "altas": n_a,
                "tasa": tasa,
            })

    return pd.DataFrame(filas)


def calcular_heatmap_data(df):
    hoy = date.today()
    años = list(range(AÑO_INICIO, hoy.year + 1))
    filas = []
    for mes in range(1, 13):
        fila = {"mes": MESES[mes]}
        for año in años:
            if año == hoy.year and mes > hoy.month:
                fila[str(año)] = None
            else:
                inicio = date(año, mes, 1)
                fin = (inicio + relativedelta(months=1)) - timedelta(days=1)
                _, _, _, tasa, _ = calcular_rotacion(df, inicio, min(fin, hoy))
                fila[str(año)] = tasa
        filas.append(fila)
    return pd.DataFrame(filas).set_index("mes")


@st.cache_data(ttl=3600)
def calcular_serie_por_empresa(df, vista):
    resultados = {}
    for empresa in sorted(df["empleador"].dropna().unique()):
        df_emp = df[df["empleador"] == empresa]
        if len(df_emp) >= 5:
            resultados[empresa] = calcular_serie(df_emp, vista)
    return resultados


# ─── Estilos — Branding MasterBus ────────────────────────────
st.markdown(f"""
<style>
/* Typography: sistema MasterBus — Arial / Helvetica Neue */
html, body, [class*="st-"], p, span, label, div, button, input, select {{
    font-family: 'Helvetica Neue', Helvetica, Arial, Verdana, sans-serif !important;
    font-size: 13px;
    color: {COLOR_TEXT};
}}

/* Fondo general */
.stApp {{
    background-color: {COLOR_BG} !important;
}}
[data-testid="stAppViewContainer"] > .main {{
    background-color: {COLOR_BG};
}}
[data-testid="stHeader"] {{
    background-color: {COLOR_BG} !important;
}}

/* Metric cards */
[data-testid="metric-container"] {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-top: 3px solid {COLOR_PRIMARY};
    border-radius: 4px;
    padding: 16px 14px 14px;
    transition: box-shadow 0.15s ease;
}}
[data-testid="metric-container"]:hover {{
    box-shadow: 0 2px 8px rgba(237,93,59,0.15);
}}
[data-testid="stMetricValue"] {{
    font-size: 1.9rem !important;
    font-weight: 700 !important;
    color: {COLOR_TEXT} !important;
    letter-spacing: -0.01em;
}}
[data-testid="stMetricLabel"] {{
    color: {COLOR_MUTED} !important;
    font-size: 0.72rem !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
}}
[data-testid="stMetricDelta"] svg {{ display: none; }}

/* Sidebar */
[data-testid="stSidebar"] {{
    background: {COLOR_SURFACE} !important;
    border-right: 1px solid {COLOR_BORDER} !important;
}}
[data-testid="stSidebarContent"] {{ padding-top: 1rem; }}

/* Botones */
.stButton > button {{
    background-color: {COLOR_ACCENT} !important;
    color: #FFFFFF !important;
    border: 1px solid #474747 !important;
    border-radius: 4px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    transition: background-color 0.15s ease !important;
}}
.stButton > button:hover {{
    background-color: {COLOR_PRIMARY} !important;
    border-color: {COLOR_PRIMARY} !important;
}}

/* Download button */
.stDownloadButton > button {{
    background-color: {COLOR_SURFACE} !important;
    color: {COLOR_TEXT} !important;
    border: 1px solid {COLOR_BORDER} !important;
    border-radius: 4px !important;
    font-size: 13px !important;
}}
.stDownloadButton > button:hover {{
    border-color: {COLOR_PRIMARY} !important;
    color: {COLOR_PRIMARY} !important;
}}

/* Dividers */
hr {{
    border: none !important;
    border-top: 1px solid {COLOR_BORDER} !important;
    margin: 0.5rem 0 !important;
    opacity: 1 !important;
}}

/* Alerts */
[data-testid="stAlert"] {{
    border-radius: 4px !important;
    font-size: 13px;
    border-left-width: 4px;
}}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{
    gap: 6px;
    background: {COLOR_SURFACE};
    border-radius: 8px;
    padding: 5px 6px;
    border: 1px solid {COLOR_BORDER};
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 6px;
    color: {COLOR_MUTED};
    font-size: 13px;
    font-weight: 600;
    padding: 8px 20px !important;
    min-height: 36px !important;
}}
.stTabs [aria-selected="true"] {{
    background: {COLOR_PRIMARY} !important;
    color: #FFFFFF !important;
}}
.stTabs [data-baseweb="tab"]:hover:not([aria-selected="true"]) {{
    background: {COLOR_BG} !important;
    color: {COLOR_TEXT} !important;
}}

/* Inputs / selectbox */
[data-testid="stTextInput"] input,
[data-baseweb="select"] {{
    background-color: #FBFBFB !important;
    border-color: {COLOR_BORDER} !important;
    border-radius: 4px !important;
    color: {COLOR_TEXT} !important;
    font-size: 13px !important;
}}

/* Captions */
.stCaption, [data-testid="stCaptionContainer"] {{
    color: {COLOR_MUTED} !important;
    font-size: 12px !important;
}}

/* Dataframe */
[data-testid="stDataFrameContainer"] {{
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
}}

/* Scrollbar */
::-webkit-scrollbar {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: {COLOR_BG}; }}
::-webkit-scrollbar-thumb {{ background: {COLOR_BORDER}; border-radius: 2px; }}
::-webkit-scrollbar-thumb:hover {{ background: {COLOR_PRIMARY}; }}
</style>
""", unsafe_allow_html=True)


# ─── Session state para filtros ──────────────────────────────
if "cargos_sel" not in st.session_state:
    st.session_state.cargos_sel = []
if "sectores_sel" not in st.session_state:
    st.session_state.sectores_sel = []

def _borrar_filtros():
    st.session_state.cargos_sel = []
    st.session_state.sectores_sel = []

# ─── Cargar datos ────────────────────────────────────────────
try:
    df_raw, timestamp_carga = cargar_datos()
except Exception:
    st.error(
        "No se pudieron cargar los datos desde la API de MasterBus. "
        "Verificá tu conexión e intentá de nuevo."
    )
    if st.button("Reintentar"):
        st.cache_data.clear()
        st.rerun()
    st.stop()

# ─── Sidebar ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:1rem;">
      <div style="width:3px;height:20px;background:{COLOR_PRIMARY};border-radius:2px;"></div>
      <span style="font-weight:700;font-size:13px;color:{COLOR_TEXT};">Período</span>
    </div>
    """, unsafe_allow_html=True)

    vista = st.radio("Vista", ["Mensual", "Anual"], horizontal=True)

    hoy = date.today()
    años = list(range(AÑO_INICIO, hoy.year + 1))
    año_sel = st.selectbox("Año", años, index=len(años) - 1)

    if vista == "Mensual":
        meses_disp = list(range(1, 13)) if año_sel < hoy.year else list(range(1, hoy.month + 1))
        mes_sel = st.selectbox(
            "Mes", meses_disp, index=len(meses_disp) - 1,
            format_func=lambda m: MESES[m],
        )
    else:
        mes_sel = None

    st.divider()
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:0.75rem;">
      <div style="width:3px;height:20px;background:{COLOR_SECONDARY};border-radius:2px;"></div>
      <span style="font-weight:700;font-size:13px;color:{COLOR_TEXT};">Filtros</span>
    </div>
    """, unsafe_allow_html=True)

    cargos_disp = sorted(df_raw["cargo"].dropna().unique())
    cargos_sel = st.multiselect(
        "Cargo / Puesto", cargos_disp,
        key="cargos_sel",
        placeholder="Todos los cargos",
        format_func=lambda x: x.title(),
    )

    sectores_disp = sorted(df_raw["str"].dropna().unique())
    sectores_sel = st.multiselect(
        "Sector / Operación", sectores_disp,
        key="sectores_sel",
        placeholder="Todos los sectores",
    )

    col_borrar, col_act = st.columns(2)
    with col_borrar:
        st.button("Borrar filtros", on_click=_borrar_filtros, use_container_width=True)
    with col_act:
        if st.button("Actualizar datos", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    st.caption(f"Total empleados Grupo Master: {len(df_raw):,}")
    st.caption(f"Datos al: {timestamp_carga:%d/%m/%Y %H:%M}")

# ─── Aplicar filtros ─────────────────────────────────────────
df = df_raw.copy()
if cargos_sel:
    df = df[df["cargo"].isin(cargos_sel)]
if sectores_sel:
    df = df[df["str"].isin(sectores_sel)]

# ─── Período activo ──────────────────────────────────────────
if vista == "Mensual":
    inicio_periodo = date(año_sel, mes_sel, 1)
    fin_periodo = (inicio_periodo + relativedelta(months=1)) - timedelta(days=1)
    label_periodo = f"{MESES[mes_sel]} {año_sel}"
else:
    inicio_periodo = date(año_sel, 1, 1)
    fin_periodo = date(año_sel, 12, 31)
    label_periodo = str(año_sel)

fin_periodo = min(fin_periodo, hoy)

# ─── KPIs ────────────────────────────────────────────────────
n_plantilla, n_bajas, n_altas, tasa, df_bajas = calcular_rotacion(df, inicio_periodo, fin_periodo)

inicio_ant, fin_ant = periodo_anterior(vista, año_sel, mes_sel if mes_sel else 1)
n_p_ant, n_b_ant, n_a_ant, tasa_ant, _ = calcular_rotacion(df, inicio_ant, min(fin_ant, hoy))

delta_plantilla = n_plantilla - n_p_ant if n_p_ant else None
delta_bajas = n_bajas - n_b_ant
delta_altas = n_altas - n_a_ant
delta_tasa = round(tasa - tasa_ant, 2) if tasa_ant else None

antiguedad = antigüedad_media_bajas(df_bajas)

df_serie_alertas = calcular_serie(df, vista)
tasas_hist = df_serie_alertas["tasa"].tolist()[:-1]
anomalia, media_hist, umbral_hist = detectar_anomalia(tasa, tasas_hist)

_tasa_color = COLOR_DANGER if anomalia else "#B45309" if (tasa > media_hist and media_hist > 0) else "#15803D"
_tasa_estado = "Elevada" if anomalia else "Por encima del promedio" if (tasa > media_hist and media_hist > 0) else "Normal"


def _delta_html(val, inverse=False, suffix="", decimals=0):
    if val is None:
        return ""
    if inverse:
        color = "#D12F19" if val > 0 else "#15803D" if val < 0 else COLOR_MUTED
    else:
        color = "#15803D" if val > 0 else "#D12F19" if val < 0 else COLOR_MUTED
    sign = "+" if val > 0 else ""
    arrow = "▲" if val > 0 else "▼" if val < 0 else "—"
    fmt = f".{decimals}f" if decimals else ","
    val_str = f"{val:{fmt}}" if not suffix else f"{val:{fmt}}{suffix}"
    return (
        f'<div style="font-size:0.76rem;font-weight:600;color:{color};'
        f'margin-top:8px;letter-spacing:0.01em;">'
        f'{arrow} {sign}{val_str} vs período ant.</div>'
    )


_umbral_hint = (
    f'<div style="font-size:0.65rem;color:{COLOR_MUTED};margin-top:6px;line-height:1.3;">'
    f'Umbral: {umbral_hist:.1f}% &nbsp;·&nbsp; Media: {media_hist:.1f}%</div>'
) if media_hist > 0 else ""

_tasa_badge = (
    f'<div style="margin-top:10px;">'
    f'<span style="display:inline-block;background:{_tasa_color}18;color:{_tasa_color};'
    f'font-size:0.66rem;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;'
    f'padding:3px 8px;border-radius:4px;border:1px solid {_tasa_color}40;">'
    f'{_tasa_estado}</span></div>'
)

st.markdown(f"""
<div style="background:{COLOR_SURFACE};border-left:5px solid {COLOR_PRIMARY};
            padding:22px 28px 20px;border-radius:0 12px 12px 0;
            box-shadow:0 2px 12px rgba(0,0,0,0.07);margin-bottom:24px;
            display:flex;align-items:center;justify-content:space-between;
            gap:16px;flex-wrap:wrap;">
  <div>
    <div style="font-size:0.63rem;font-weight:700;color:{COLOR_MUTED};text-transform:uppercase;
                letter-spacing:0.12em;margin-bottom:6px;">Grupo Master — Dashboard RRHH</div>
    <h1 style="margin:0 0 5px;font-size:2.1rem;font-weight:800;color:{COLOR_TEXT};
               font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;
               letter-spacing:-0.025em;line-height:1.1;">
      Rotación de Personal
    </h1>
    <p style="margin:0;color:{COLOR_MUTED};font-size:0.76rem;">
      Datos actualizados cada hora desde la API de MasterBus
      &nbsp;·&nbsp; Fórmula: Bajas / Plantilla al inicio del período
    </p>
  </div>
  <div style="background:{COLOR_BG};border:1px solid {COLOR_BORDER};border-radius:12px;
              padding:14px 24px;text-align:center;flex-shrink:0;">
    <div style="font-size:0.6rem;font-weight:700;color:{COLOR_MUTED};
                text-transform:uppercase;letter-spacing:0.12em;margin-bottom:4px;">Período activo</div>
    <div style="font-size:1.5rem;font-weight:800;color:{COLOR_PRIMARY};
                font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;letter-spacing:-0.01em;">
      {label_periodo}
    </div>
  </div>
</div>

<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:8px;">

  <div style="background:{COLOR_SURFACE};border:1px solid {COLOR_BORDER};
              border-top:3px solid {COLOR_PRIMARY};border-radius:10px;
              padding:22px 18px 18px;box-shadow:0 1px 5px rgba(0,0,0,0.04);">
    <div style="font-size:0.62rem;font-weight:700;color:{COLOR_MUTED};
                text-transform:uppercase;letter-spacing:0.09em;margin-bottom:10px;">
      Plantilla al inicio
    </div>
    <div style="font-size:2.6rem;font-weight:800;color:{COLOR_TEXT};
                line-height:1;letter-spacing:-0.025em;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
      {n_plantilla:,}
    </div>
    {_delta_html(delta_plantilla)}
  </div>

  <div style="background:{COLOR_SURFACE};border:1px solid {COLOR_BORDER};
              border-top:3px solid {COLOR_PRIMARY};border-radius:10px;
              padding:22px 18px 18px;box-shadow:0 1px 5px rgba(0,0,0,0.04);">
    <div style="font-size:0.62rem;font-weight:700;color:{COLOR_MUTED};
                text-transform:uppercase;letter-spacing:0.09em;margin-bottom:10px;">
      Bajas del período
    </div>
    <div style="font-size:2.6rem;font-weight:800;color:{COLOR_TEXT};
                line-height:1;letter-spacing:-0.025em;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
      {n_bajas:,}
    </div>
    {_delta_html(delta_bajas, inverse=True)}
  </div>

  <div style="background:{COLOR_SURFACE};border:1px solid {COLOR_BORDER};
              border-top:3px solid {COLOR_PRIMARY};border-radius:10px;
              padding:22px 18px 18px;box-shadow:0 1px 5px rgba(0,0,0,0.04);">
    <div style="font-size:0.62rem;font-weight:700;color:{COLOR_MUTED};
                text-transform:uppercase;letter-spacing:0.09em;margin-bottom:10px;">
      Altas del período
    </div>
    <div style="font-size:2.6rem;font-weight:800;color:{COLOR_TEXT};
                line-height:1;letter-spacing:-0.025em;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
      {n_altas:,}
    </div>
    {_delta_html(delta_altas)}
  </div>

  <div style="background:{COLOR_SURFACE};border:1px solid {COLOR_BORDER};
              border-top:3px solid {_tasa_color};border-radius:10px;
              padding:22px 18px 18px;box-shadow:0 1px 5px rgba(0,0,0,0.04);">
    <div style="font-size:0.62rem;font-weight:700;color:{COLOR_MUTED};
                text-transform:uppercase;letter-spacing:0.09em;margin-bottom:10px;">
      Tasa de Rotación
    </div>
    <div style="font-size:2.6rem;font-weight:800;color:{COLOR_TEXT};
                line-height:1;letter-spacing:-0.025em;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
      {tasa:.1f}%
    </div>
    {_delta_html(delta_tasa, inverse=True, suffix="pp", decimals=1)}{_tasa_badge}
    {_umbral_hint}
  </div>

  <div style="background:{COLOR_SURFACE};border:1px solid {COLOR_BORDER};
              border-top:3px solid {COLOR_SECONDARY};border-radius:10px;
              padding:22px 18px 18px;box-shadow:0 1px 5px rgba(0,0,0,0.04);">
    <div style="font-size:0.62rem;font-weight:700;color:{COLOR_MUTED};
                text-transform:uppercase;letter-spacing:0.09em;margin-bottom:10px;">
      Antigüedad media bajas
    </div>
    <div style="font-size:2.6rem;font-weight:800;color:{COLOR_TEXT};
                line-height:1;letter-spacing:-0.025em;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
      {f"{antiguedad}" if antiguedad is not None else "—"}
    </div>
    <div style="font-size:0.76rem;color:{COLOR_MUTED};margin-top:6px;">meses promedio</div>
  </div>

</div>
""", unsafe_allow_html=True)

st.divider()

# ─── Alertas ─────────────────────────────────────────────────
if anomalia:
    st.error(
        f"**Alerta de rotación elevada** — La tasa del período ({tasa:.1f}%) supera "
        f"el umbral histórico de {umbral_hist:.1f}% (media {media_hist:.1f}% + 2σ)."
    )
elif tasa > media_hist and media_hist > 0:
    st.warning(
        f"**Rotación por encima del promedio** — {tasa:.1f}% vs media histórica {media_hist:.1f}%."
    )

# ─── Evolución temporal ──────────────────────────────────────
st.markdown(f"""
<div style="display:flex;align-items:center;gap:8px;margin:12px 0 8px;">
  <div style="width:3px;height:18px;background:{COLOR_PRIMARY};border-radius:2px;"></div>
  <span style="font-weight:700;font-size:1rem;color:{COLOR_TEXT};">Evolución de la Rotación</span>
</div>
""", unsafe_allow_html=True)

df_serie = df_serie_alertas

_ann = dict(
    annotation_bgcolor="rgba(255,255,255,0.92)",
    annotation_font_color=COLOR_MUTED,
)

tab_tasa, tab_volumen = st.tabs(["Tasa de Rotación (%)", "Altas y Bajas"])

with tab_tasa:
    fig_linea = go.Figure()
    fig_linea.add_trace(go.Scatter(
        x=df_serie["periodo_dt"],
        y=df_serie["tasa"],
        mode="lines+markers",
        name="Tasa",
        line=dict(color=COLOR_PRIMARY, width=2.5),
        fill="tozeroy",
        fillcolor="rgba(237,93,59,0.07)",
        marker=dict(size=6, color=COLOR_PRIMARY, line=dict(color=COLOR_SURFACE, width=1.5)),
        hovertemplate="%{y:.1f}%<extra></extra>",
    ))
    if media_hist > 0:
        fig_linea.add_hline(
            y=media_hist,
            line_dash="dot",
            line_color=COLOR_ACCENT,
            annotation_text=f"Media {media_hist:.1f}%",
            annotation_position="bottom right",
            **_ann,
        )
        fig_linea.add_hline(
            y=umbral_hist,
            line_dash="dash",
            line_color=COLOR_DANGER,
            annotation_text=f"Umbral {umbral_hist:.1f}%",
            annotation_position="top right",
            annotation_bgcolor="rgba(255,255,255,0.92)",
            annotation_font_color=COLOR_DANGER,
        )
    fig_linea.update_layout(
        **_chart_base(
            hovermode="x unified",
            yaxis_ticksuffix="%",
            height=360,
            showlegend=False,
        )
    )
    st.plotly_chart(fig_linea, use_container_width=True)

with tab_volumen:
    fig_barras = px.bar(
        df_serie,
        x="periodo_dt",
        y=["altas", "bajas"],
        barmode="group",
        labels={"value": "Empleados", "periodo_dt": "", "variable": ""},
        color_discrete_map={"altas": COLOR_SECONDARY, "bajas": COLOR_PRIMARY},
    )
    fig_barras.update_layout(
        **_chart_base(
            hovermode="x unified",
            height=390,
            margin=dict(l=10, r=10, t=20, b=70),
            legend=dict(
                orientation="h",
                yanchor="top", y=-0.14,
                xanchor="center", x=0.5,
                font=dict(color=COLOR_MUTED, size=12),
            ),
        )
    )
    st.plotly_chart(fig_barras, use_container_width=True)

# ─── Mapa de calor ───────────────────────────────────────────
st.divider()
st.markdown(f"""
<div style="display:flex;align-items:center;gap:8px;margin:12px 0 4px;">
  <div style="width:3px;height:18px;background:{COLOR_SECONDARY};border-radius:2px;"></div>
  <span style="font-weight:700;font-size:1rem;color:{COLOR_TEXT};">Mapa de Calor — Tasa de Rotación por Mes y Año</span>
</div>
""", unsafe_allow_html=True)
st.caption("Cada celda muestra la tasa de rotación (%). Verde = baja, amarillo = moderada, rojo = elevada.")

df_heat = calcular_heatmap_data(df)
años_heat = df_heat.columns.tolist()
meses_heat = df_heat.index.tolist()
z_heat = df_heat.values.tolist()

fig_heat = go.Figure(go.Heatmap(
    z=z_heat,
    x=años_heat,
    y=meses_heat,
    colorscale=[[0, "#22C55E"], [0.5, "#F59E0B"], [1, COLOR_DANGER]],
    text=[[f"{v:.1f}%" if pd.notna(v) else "" for v in fila] for fila in z_heat],
    texttemplate="%{text}",
    textfont={
        "size": 11,
        "color": COLOR_TEXT,
        "family": "Helvetica Neue, Helvetica, Arial, sans-serif",
    },
    hovertemplate="%{y} %{x}: %{z:.1f}%<extra></extra>",
    showscale=True,
    colorbar=dict(
        title=dict(
            text="Tasa %",
            font=dict(color=COLOR_MUTED, family="Helvetica Neue, Arial, sans-serif"),
        ),
        ticksuffix="%",
        tickfont=dict(color=COLOR_MUTED, family="Helvetica Neue, Arial, sans-serif"),
        bgcolor="rgba(0,0,0,0)",
        bordercolor=COLOR_BORDER,
    ),
))
fig_heat.update_layout(
    **_chart_base(
        height=430,
        xaxis=dict(
            side="top", tickmode="linear", showgrid=False,
            color=COLOR_MUTED, showline=False,
        ),
        yaxis=dict(
            autorange="reversed", showgrid=False,
            color=COLOR_MUTED, showline=False,
        ),
        margin=dict(l=10, r=80, t=40, b=10),
    )
)
st.plotly_chart(fig_heat, use_container_width=True)

# ─── Desgloses ───────────────────────────────────────────────
st.divider()
st.markdown(f"""
<div style="display:flex;align-items:center;gap:8px;margin:12px 0 8px;">
  <div style="width:3px;height:18px;background:{COLOR_PRIMARY};border-radius:2px;"></div>
  <span style="font-weight:700;font-size:1rem;color:{COLOR_TEXT};">Desglose de Bajas — {label_periodo}</span>
</div>
""", unsafe_allow_html=True)

col_izq, col_der = st.columns(2)

with col_izq:
    st.markdown(f'<p style="font-weight:600;font-size:13px;color:{COLOR_TEXT};margin-bottom:4px;">Por Cargo</p>', unsafe_allow_html=True)
    if not df_bajas.empty:
        bc = df_bajas["cargo"].value_counts().reset_index()
        bc.columns = ["cargo", "bajas"]
        fig = px.bar(
            bc, x="bajas", y="cargo", orientation="h",
            color_discrete_sequence=[COLOR_PRIMARY],
            labels={"bajas": "Bajas", "cargo": ""},
        )
        fig.update_layout(
            **_chart_base(
                yaxis=dict(autorange="reversed", showgrid=False, color=COLOR_MUTED, showline=False),
                xaxis=dict(showgrid=True, gridcolor="#E8E8E8", color=COLOR_MUTED, showline=False),
                height=max(260, len(bc) * 34),
                margin=dict(l=0, r=10, t=10, b=10),
            )
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin bajas en este período.")

with col_der:
    st.markdown(f'<p style="font-weight:600;font-size:13px;color:{COLOR_TEXT};margin-bottom:4px;">Por Sector</p>', unsafe_allow_html=True)
    if not df_bajas.empty:
        bs = df_bajas["str"].value_counts().reset_index()
        bs.columns = ["sector", "bajas"]
        fig = px.bar(
            bs, x="bajas", y="sector", orientation="h",
            color_discrete_sequence=[COLOR_SECONDARY],
            labels={"bajas": "Bajas", "sector": ""},
        )
        fig.update_layout(
            **_chart_base(
                yaxis=dict(autorange="reversed", showgrid=False, color=COLOR_MUTED, showline=False),
                xaxis=dict(showgrid=True, gridcolor="#E8E8E8", color=COLOR_MUTED, showline=False),
                height=max(260, len(bs) * 34),
                margin=dict(l=0, r=10, t=10, b=10),
            )
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin bajas en este período.")

# ─── Evolución por empresa ───────────────────────────────────
st.divider()
st.markdown(f"""
<div style="display:flex;align-items:center;gap:8px;margin:12px 0 8px;">
  <div style="width:3px;height:18px;background:{COLOR_ACCENT};border-radius:2px;"></div>
  <span style="font-weight:700;font-size:1rem;color:{COLOR_TEXT};">Evolución por Empresa del Grupo</span>
</div>
""", unsafe_allow_html=True)
st.caption("Solo se muestran empresas con 5 o más empleados en el período seleccionado.")

series_emp = calcular_serie_por_empresa(df, vista)

# Paleta coherente con el branding MasterBus
COLORES_EMP = [
    COLOR_PRIMARY,   # #ED5D3B naranja-rojo
    COLOR_SECONDARY, # #46BCD2 teal
    "#8C8987",       # gris acento
    "#D12F19",       # rojo
    "#2E86AB",       # azul
    "#6B4E9E",       # violeta
    "#F4A261",       # ámbar
    "#52B788",       # verde
]

if series_emp:
    fig_emp = go.Figure()
    for i, (empresa, serie) in enumerate(series_emp.items()):
        color = COLORES_EMP[i % len(COLORES_EMP)]
        fig_emp.add_trace(go.Scatter(
            x=serie["periodo_dt"],
            y=serie["tasa"],
            mode="lines+markers",
            name=empresa,
            line=dict(color=color, width=2),
            marker=dict(size=5, color=color),
            hovertemplate=f"{empresa}<br>%{{y:.1f}}%<extra></extra>",
        ))
    if media_hist > 0:
        fig_emp.add_hline(
            y=media_hist,
            line_dash="dot",
            line_color=COLOR_ACCENT,
            annotation_text=f"Media global {media_hist:.1f}%",
            annotation_position="bottom right",
            **_ann,
        )
    fig_emp.update_layout(
        **_chart_base(
            hovermode="x unified",
            yaxis_ticksuffix="%",
            height=440,
            margin=dict(l=10, r=10, t=20, b=90),
            legend=dict(
                orientation="h",
                yanchor="top", y=-0.18,
                xanchor="center", x=0.5,
                font=dict(color=COLOR_MUTED, size=11),
            ),
        )
    )
    st.plotly_chart(fig_emp, use_container_width=True)
else:
    st.info("No hay suficientes datos por empresa para mostrar este gráfico con los filtros actuales.")

# ─── Tabla de detalle ────────────────────────────────────────
st.divider()
st.markdown(f"""
<div style="display:flex;align-items:center;gap:8px;margin:12px 0 8px;">
  <div style="width:3px;height:18px;background:{COLOR_SECONDARY};border-radius:2px;"></div>
  <span style="font-weight:700;font-size:1rem;color:{COLOR_TEXT};">Detalle de Bajas — {label_periodo}</span>
</div>
""", unsafe_allow_html=True)

COLS = {
    "legajo": "Legajo",
    "apenom": "Nombre",
    "cargo": "Cargo",
    "empleador": "Empleador",
    "str": "Sector",
    "fechainicio": "Ingreso",
    "fechafin": "Baja",
}

if not df_bajas.empty:
    tabla = (
        df_bajas[list(COLS.keys())]
        .rename(columns=COLS)
        .sort_values("Baja", ascending=False)
        .reset_index(drop=True)
    )
    st.dataframe(tabla, use_container_width=True, hide_index=True)
    st.download_button(
        f"Descargar CSV — {label_periodo}",
        data=tabla.to_csv(index=False).encode("utf-8"),
        file_name=f"bajas_{label_periodo.replace(' ', '_')}.csv",
        mime="text/csv",
    )
else:
    st.info("No hubo bajas en este período para los filtros seleccionados.")
