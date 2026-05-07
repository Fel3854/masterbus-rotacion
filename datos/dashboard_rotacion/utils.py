"""Utilidades compartidas entre las páginas del dashboard."""

import requests
import pandas as pd
import streamlit as st
from datetime import datetime
from supabase import create_client, Client

API_URL = "https://traficonuevo.masterbus.net/api/v1/auto/e"

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

COLOR_PRIMARY   = "#ED5D3B"
COLOR_SECONDARY = "#46BCD2"
COLOR_ACCENT    = "#8C8987"
COLOR_DANGER    = "#D12F19"
COLOR_BG        = "#EDEDED"
COLOR_SURFACE   = "#FFFFFF"
COLOR_TEXT      = "#333333"
COLOR_MUTED     = "#8C8987"
COLOR_BORDER    = "#CCCCCC"

def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


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
    df["fecha_fin"]    = df["fechafin"].apply(_parse_fecha)
    df = df[df["fecha_inicio"].notna()].copy()

    df["cargo"]  = df["cargo"].str.strip().str.upper()
    df["str"]    = df["str"].str.strip()
    df["activo"] = df["activo"].astype(str)

    return df, datetime.now()


def cargar_empleados_activos():
    """Devuelve DataFrame con empleados activos del Grupo Master."""
    df, _ = cargar_datos()
    activos = df[df["activo"] == "1"][["legajo", "apenom", "empleador"]].copy()
    activos["legajo"] = activos["legajo"].astype(str).str.strip()
    activos["apenom"] = activos["apenom"].str.strip().str.upper()
    activos = activos.sort_values("apenom").reset_index(drop=True)
    return activos


def inyectar_css_base():
    """CSS compartido con el branding MasterBus."""
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fira+Sans:wght@400;500;600;700&family=Fira+Code:wght@400;500&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Fira Sans', sans-serif;
        color: {COLOR_TEXT};
    }}

    /* Forzar texto oscuro en todos los elementos de texto de Streamlit */
    p, span, li, td, th, label, div, h1, h2, h3, h4, h5, h6 {{
        color: {COLOR_TEXT};
    }}
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] span,
    [data-testid="stText"],
    [data-testid="stCaptionContainer"] p,
    [data-testid="stWidgetLabel"] p {{
        color: {COLOR_TEXT} !important;
    }}
    /* Dataframe */
    [data-testid="stDataFrame"] td,
    [data-testid="stDataFrame"] th,
    [data-testid="stDataFrame"] span {{
        color: {COLOR_TEXT} !important;
    }}

    .stApp {{ background-color: {COLOR_BG}; }}

    .stButton > button {{
        background: #3a3a3a;
        color: #fff;
        border: none;
        border-radius: 6px;
        font-family: 'Fira Sans', sans-serif;
        font-weight: 600;
        padding: 0.45rem 1.2rem;
        transition: background 0.2s;
    }}
    .stButton > button:hover {{ background: {COLOR_PRIMARY}; }}

    .stDownloadButton > button {{
        background: {COLOR_PRIMARY};
        color: #fff;
        border: none;
        border-radius: 6px;
        font-family: 'Fira Sans', sans-serif;
        font-weight: 600;
        padding: 0.45rem 1.2rem;
        transition: background 0.2s;
    }}
    .stDownloadButton > button:hover {{ background: {COLOR_DANGER}; }}

    div[data-testid="stForm"] {{
        background: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER};
        border-radius: 10px;
        padding: 1.5rem;
    }}

    .stTextInput input, .stSelectbox select, .stNumberInput input, .stTextArea textarea {{
        background: #f7f7f7;
        border: 1px solid {COLOR_BORDER};
        border-radius: 6px;
        font-family: 'Fira Sans', sans-serif;
    }}

    .page-header {{
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 0.25rem;
    }}
    .page-header .bar {{
        width: 4px;
        height: 28px;
        background: {COLOR_PRIMARY};
        border-radius: 2px;
        flex-shrink: 0;
    }}
    .page-header h1 {{
        font-size: 1.6rem;
        font-weight: 700;
        color: {COLOR_TEXT};
        margin: 0;
    }}

    .section-header {{
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 1.5rem 0 0.75rem;
    }}
    .section-header .bar {{
        width: 3px;
        height: 18px;
        background: {COLOR_SECONDARY};
        border-radius: 2px;
        flex-shrink: 0;
    }}
    .section-header span {{
        font-weight: 700;
        font-size: 1rem;
        color: {COLOR_TEXT};
    }}
    </style>
    """, unsafe_allow_html=True)
