#!/usr/bin/env python3
"""Dashboard de Rotación de Personal — Grupo Master"""

import statistics
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import requests
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

pio.templates.default = "plotly_dark"

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


def periodo_anterior(vista, año, mes):
    """Devuelve (inicio, fin) del período inmediatamente anterior."""
    if vista == "Mensual":
        primer_dia = date(año, mes, 1)
        fin_ant = primer_dia - timedelta(days=1)
        inicio_ant = date(fin_ant.year, fin_ant.month, 1)
        return inicio_ant, fin_ant
    else:
        return date(año - 1, 1, 1), date(año - 1, 12, 31)


def antigüedad_media_bajas(df_bajas):
    """Antigüedad media en meses de los empleados que se fueron."""
    if df_bajas.empty:
        return None
    meses = []
    for _, row in df_bajas.iterrows():
        if row["fecha_inicio"] and row["fecha_fin"]:
            delta = relativedelta(row["fecha_fin"], row["fecha_inicio"])
            meses.append(delta.years * 12 + delta.months)
    return round(statistics.mean(meses), 1) if meses else None


def detectar_anomalia(tasa_actual, serie_historica):
    """True si la tasa actual supera media + 2σ del histórico."""
    valores = [v for v in serie_historica if v > 0]
    if len(valores) < 3:
        return False, 0.0, 0.0
    media = statistics.mean(valores)
    stdev = statistics.stdev(valores)
    umbral = media + 2 * stdev
    return tasa_actual > umbral, round(media, 2), round(umbral, 2)


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


def calcular_heatmap_data(df):
    """Matriz mes × año con tasa de rotación para el mapa de calor."""
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


def calcular_serie_por_empresa(df, vista):
    """Serie temporal de tasa de rotación por empresa del grupo."""
    resultados = {}
    for empresa in sorted(df["empleador"].dropna().unique()):
        df_emp = df[df["empleador"] == empresa]
        if len(df_emp) >= 5:
            resultados[empresa] = calcular_serie(df_emp, vista)
    return resultados


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

st.subheader(f"Período: {label_periodo}")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Plantilla al inicio", f"{n_plantilla:,}",
            delta=f"{delta_plantilla:+,}" if delta_plantilla is not None else None)
col2.metric("Bajas del período", f"{n_bajas:,}",
            delta=f"{delta_bajas:+,}", delta_color="inverse")
col3.metric("Altas del período", f"{n_altas:,}",
            delta=f"{delta_altas:+,}")

_tasa_color = "#e74c3c" if anomalia else "#f39c12" if (tasa > media_hist and media_hist > 0) else "#27ae60"
_tasa_estado = "🔴 Elevada" if anomalia else "🟡 Por encima del promedio" if (tasa > media_hist and media_hist > 0) else "🟢 Normal"
with col4:
    st.metric("Tasa de Rotación", f"{tasa:.1f}%",
              delta=f"{delta_tasa:+.1f}pp" if delta_tasa is not None else None,
              delta_color="inverse")
    st.markdown(
        f'<span style="color:{_tasa_color};font-size:0.8rem;font-weight:600">{_tasa_estado}</span>',
        unsafe_allow_html=True,
    )

col5.metric("Antigüedad media bajas", f"{antiguedad} m" if antiguedad is not None else "—")

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
st.subheader("Evolución de la Rotación")

df_serie = df_serie_alertas

tab_tasa, tab_volumen = st.tabs(["Tasa de Rotación (%)", "Altas y Bajas"])

with tab_tasa:
    fig_linea = go.Figure()
    fig_linea.add_trace(go.Scatter(
        x=df_serie["periodo_dt"],
        y=df_serie["tasa"],
        mode="lines+markers",
        name="Tasa",
        line=dict(color=COLOR_MASTER, width=2.5),
        marker=dict(size=7),
        hovertemplate="%{y:.1f}%<extra></extra>",
    ))
    if media_hist > 0:
        fig_linea.add_hline(
            y=media_hist,
            line_dash="dot",
            line_color="#888",
            annotation_text=f"Media {media_hist:.1f}%",
            annotation_position="bottom right",
            annotation_bgcolor="rgba(30,30,30,0.85)",
            annotation_font_color="#aaa",
        )
        fig_linea.add_hline(
            y=umbral_hist,
            line_dash="dash",
            line_color="#e74c3c",
            annotation_text=f"Umbral {umbral_hist:.1f}%",
            annotation_position="top right",
            annotation_bgcolor="rgba(30,30,30,0.85)",
            annotation_font_color="#ff6b6b",
        )
    fig_linea.update_layout(
        hovermode="x unified",
        yaxis_ticksuffix="%",
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="#333", rangemode="tozero"),
        height=350,
        showlegend=False,
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
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="#333"),
        height=380,
        margin=dict(b=60),
        legend=dict(
            orientation="h",
            yanchor="top", y=-0.18,
            xanchor="center", x=0.5,
        ),
    )
    st.plotly_chart(fig_barras, use_container_width=True)

# ─── Mapa de calor ───────────────────────────────────────────
st.divider()
st.subheader("Mapa de Calor — Tasa de Rotación por Mes y Año")
st.caption("Cada celda muestra la tasa de rotación (%). Verde = baja, amarillo = moderada, rojo = elevada.")

df_heat = calcular_heatmap_data(df)
años_heat = df_heat.columns.tolist()
meses_heat = df_heat.index.tolist()
z_heat = df_heat.values.tolist()

fig_heat = go.Figure(go.Heatmap(
    z=z_heat,
    x=años_heat,
    y=meses_heat,
    colorscale=[[0, "#27ae60"], [0.5, "#f39c12"], [1, "#e74c3c"]],
    text=[[f"{v:.1f}%" if pd.notna(v) else "" for v in fila] for fila in z_heat],
    texttemplate="%{text}",
    textfont={"size": 11, "color": "white"},
    hovertemplate="%{y} %{x}: %{z:.1f}%<extra></extra>",
    showscale=True,
    colorbar=dict(title="Tasa %", ticksuffix="%"),
))
fig_heat.update_layout(
    height=420,
    xaxis=dict(side="top", tickmode="linear"),
    yaxis=dict(autorange="reversed"),
    margin=dict(l=10, r=80, t=40, b=10),
)
st.plotly_chart(fig_heat, use_container_width=True)

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
            yaxis=dict(autorange="reversed"),
            xaxis=dict(showgrid=True, gridcolor="#333"),
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
            yaxis=dict(autorange="reversed"),
            xaxis=dict(showgrid=True, gridcolor="#333"),
            height=max(250, len(bs) * 32),
            margin=dict(l=0, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin bajas en este período.")

# ─── Evolución por empresa ───────────────────────────────────
st.divider()
st.subheader("Evolución por Empresa del Grupo")

series_emp = calcular_serie_por_empresa(df, vista)

if series_emp:
    fig_emp = go.Figure()
    colores = px.colors.qualitative.Set2
    for i, (empresa, serie) in enumerate(series_emp.items()):
        fig_emp.add_trace(go.Scatter(
            x=serie["periodo_dt"],
            y=serie["tasa"],
            mode="lines+markers",
            name=empresa,
            line=dict(color=colores[i % len(colores)], width=2),
            marker=dict(size=5),
            hovertemplate=f"{empresa}<br>%{{y:.1f}}%<extra></extra>",
        ))
    if media_hist > 0:
        fig_emp.add_hline(
            y=media_hist,
            line_dash="dot",
            line_color="#888",
            annotation_text=f"Media global {media_hist:.1f}%",
            annotation_position="bottom right",
            annotation_bgcolor="rgba(30,30,30,0.85)",
            annotation_font_color="#aaa",
        )
    fig_emp.update_layout(
        hovermode="x unified",
        yaxis_ticksuffix="%",
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="#333", rangemode="tozero"),
        height=430,
        margin=dict(b=80),
        legend=dict(
            orientation="h",
            yanchor="top", y=-0.18,
            xanchor="center", x=0.5,
        ),
    )
    st.plotly_chart(fig_emp, use_container_width=True)
else:
    st.info("No hay suficientes datos por empresa para mostrar este gráfico con los filtros actuales.")

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
