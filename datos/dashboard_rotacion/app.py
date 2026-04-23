#!/usr/bin/env python3
"""Dashboard de Rotación de Personal — Grupo Master"""

import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

# ─── Página ─────────────────────────────────────────────────
st.set_page_config(
    page_title="Rotación — Grupo Master",
    page_icon="📊",
    layout="wide",
)

# ─── Constantes ─────────────────────────────────────────────
API_URL = "https://traficonuevo.masterbus.net/api/v1/auto/e"
AÑO_INICIO = 2020
COLOR_MASTER = "#d35400"

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

    return df


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


def calcular_serie(df, vista):
    """Serie temporal completa desde AÑO_INICIO hasta hoy."""
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


# ─── Estilos ─────────────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="metric-container"] {
        background: #fafafa;
        border: 1px solid #eee;
        border-radius: 8px;
        padding: 16px;
    }
    [data-testid="stMetricValue"] { font-size: 2rem !important; }
</style>
""", unsafe_allow_html=True)

# ─── Título ──────────────────────────────────────────────────
st.title("📊 Rotación de Personal — Grupo Master")
st.caption("Datos actualizados cada hora desde la API de MasterBus · Fórmula: Bajas / Plantilla al inicio del período")

# ─── Cargar datos ────────────────────────────────────────────
try:
    df_raw = cargar_datos()
except Exception as e:
    st.error(f"No se pudieron cargar los datos: {e}")
    st.stop()

# ─── Sidebar ─────────────────────────────────────────────────
with st.sidebar:
    st.header("Período")
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
    st.header("Filtros")

    cargos_disp = sorted(df_raw["cargo"].dropna().unique())
    cargos_sel = st.multiselect("Cargo / Puesto", cargos_disp, placeholder="Todos los cargos")

    sectores_disp = sorted(df_raw["str"].dropna().unique())
    sectores_sel = st.multiselect("Sector / Operación", sectores_disp, placeholder="Todos los sectores")

    st.divider()
    if st.button("🔄 Actualizar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption(f"Total empleados Grupo Master en la API: {len(df_raw):,}")

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

st.subheader(f"Período: {label_periodo}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Plantilla al inicio", f"{n_plantilla:,}")
col2.metric("Bajas del período", f"{n_bajas:,}")
col3.metric("Altas del período", f"{n_altas:,}")
col4.metric("Tasa de Rotación", f"{tasa:.1f}%",
            delta=None, delta_color="inverse")

st.divider()

# ─── Evolución temporal ──────────────────────────────────────
st.subheader("Evolución de la Rotación")

df_serie = calcular_serie(df, vista)

tab_tasa, tab_volumen = st.tabs(["Tasa de Rotación (%)", "Altas y Bajas"])

with tab_tasa:
    fig_linea = px.line(
        df_serie,
        x="periodo_dt",
        y="tasa",
        markers=True,
        labels={"tasa": "Tasa (%)", "periodo_dt": ""},
        color_discrete_sequence=[COLOR_MASTER],
    )
    fig_linea.update_traces(line_width=2.5, marker_size=7)
    fig_linea.update_layout(
        hovermode="x unified",
        yaxis_ticksuffix="%",
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="#eee", rangemode="tozero"),
        height=350,
    )
    st.plotly_chart(fig_linea, use_container_width=True)

with tab_volumen:
    fig_barras = px.bar(
        df_serie,
        x="periodo_dt",
        y=["altas", "bajas"],
        barmode="group",
        labels={"value": "Empleados", "periodo_dt": "", "variable": ""},
        color_discrete_map={"altas": "#2ecc71", "bajas": COLOR_MASTER},
    )
    fig_barras.update_layout(
        hovermode="x unified",
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="#eee"),
        height=350,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_barras, use_container_width=True)

# ─── Desgloses ───────────────────────────────────────────────
st.divider()
st.subheader(f"Desglose de Bajas — {label_periodo}")

col_izq, col_der = st.columns(2)

with col_izq:
    st.markdown("**Por Cargo**")
    if not df_bajas.empty:
        bc = df_bajas["cargo"].value_counts().reset_index()
        bc.columns = ["cargo", "bajas"]
        fig = px.bar(
            bc, x="bajas", y="cargo", orientation="h",
            color_discrete_sequence=[COLOR_MASTER],
            labels={"bajas": "Bajas", "cargo": ""},
        )
        fig.update_layout(
            plot_bgcolor="white", paper_bgcolor="white",
            yaxis=dict(autorange="reversed"),
            xaxis=dict(showgrid=True, gridcolor="#eee"),
            height=max(250, len(bc) * 32),
            margin=dict(l=0, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin bajas en este período.")

with col_der:
    st.markdown("**Por Sector**")
    if not df_bajas.empty:
        bs = df_bajas["str"].value_counts().reset_index()
        bs.columns = ["sector", "bajas"]
        fig = px.bar(
            bs, x="bajas", y="sector", orientation="h",
            color_discrete_sequence=[COLOR_MASTER],
            labels={"bajas": "Bajas", "sector": ""},
        )
        fig.update_layout(
            plot_bgcolor="white", paper_bgcolor="white",
            yaxis=dict(autorange="reversed"),
            xaxis=dict(showgrid=True, gridcolor="#eee"),
            height=max(250, len(bs) * 32),
            margin=dict(l=0, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin bajas en este período.")

# ─── Tabla de detalle ────────────────────────────────────────
st.divider()
st.subheader(f"Detalle de Bajas — {label_periodo}")

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
        "⬇️ Descargar CSV",
        data=tabla.to_csv(index=False).encode("utf-8"),
        file_name=f"bajas_{label_periodo.replace(' ', '_')}.csv",
        mime="text/csv",
    )
else:
    st.info("No hubo bajas en este período para los filtros seleccionados.")
