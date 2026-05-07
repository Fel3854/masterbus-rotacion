"""Vista: Vencimientos — Período de Prueba · Grupo Master"""

import os
import sys
from datetime import date

import pandas as pd
import streamlit as st
from dateutil.relativedelta import relativedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import cargar_datos, COLOR_PRIMARY, COLOR_DANGER

MASTER_BUS_EMPRESAS = {"MASTER BUS S.A", "MASTER BUS SA", "MASTER BUS TASA"}

COLOR_VENCIDO = "#D12F19"
COLOR_CERCANO = "#ED5D3B"
COLOR_LEJANO  = "#22C55E"

CAT_VENCIDO = "Vencidos"
CAT_CERCANO = "Vencimientos Cercanos"
CAT_LEJANO  = "Vencimientos Lejanos"
CATEGORIAS  = [CAT_VENCIDO, CAT_CERCANO, CAT_LEJANO]

# ─── CSS ──────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fira+Sans:wght@300;400;500;600;700&family=Fira+Code:wght@400;500;600&display=swap');

html, body, [class*="css"], p, span, div, label, td, th, li {{
    font-family: 'Fira Sans', sans-serif !important;
    color: #333333;
}}
.stApp {{ background-color: #EDEDED !important; }}
[data-testid="stElementToolbar"] {{ display: none; }}
[data-testid="stSidebar"] {{ background-color: #1e1e2e !important; }}
[data-testid="stSidebar"] * {{ color: #e0e0e0 !important; }}
[data-testid="stSidebarNavLink"][aria-selected="true"] {{
    background-color: rgba(237,93,59,0.25) !important;
}}

/* ── Header ── */
.page-title {{
    display: flex; align-items: center; gap: 12px;
    padding: 0.5rem 0 0.25rem;
}}
.page-title .accent-bar {{
    width: 5px; height: 36px; background: {COLOR_PRIMARY};
    border-radius: 3px; flex-shrink: 0;
}}
.page-title h1 {{
    font-size: 1.75rem; font-weight: 700; color: #1a1a1a;
    margin: 0; letter-spacing: -0.5px;
}}
.page-subtitle {{
    color: #666; font-size: 0.9rem; margin: 0 0 1.5rem 17px;
}}

/* ── Section label ── */
.section-label {{
    font-size: 0.68rem; font-weight: 700; letter-spacing: 1.4px;
    text-transform: uppercase; color: #999; margin: 1.5rem 0 0.75rem;
}}

/* ── KPI cards ── */
.kpi-card {{
    background: #fff;
    border-radius: 12px;
    border: 1px solid #e0e0e0;
    border-top: 4px solid var(--card-color, #ccc);
    padding: 1.25rem 1.5rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}}
.kpi-label {{
    font-size: 0.68rem; font-weight: 700; letter-spacing: 1px;
    text-transform: uppercase; color: #999; margin-bottom: 0.5rem;
}}
.kpi-value {{
    font-family: 'Fira Code', monospace;
    font-size: 2.4rem; font-weight: 700;
    line-height: 1; margin-bottom: 0.35rem;
}}
.kpi-desc {{
    font-size: 0.78rem; color: #888;
}}

/* ── Categoría tab pills ── */
div[data-testid="stRadio"] > div {{
    gap: 0.5rem;
    flex-wrap: wrap;
}}
div[data-testid="stRadio"] label {{
    background: #fff;
    border: 1.5px solid #e0e0e0;
    border-radius: 20px;
    padding: 0.35rem 1rem;
    font-size: 0.85rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
    color: #555 !important;
}}
div[data-testid="stRadio"] label:has(input:checked) {{
    background: {COLOR_PRIMARY};
    border-color: {COLOR_PRIMARY};
    color: #fff !important;
}}

/* ── Botón ── */
.stButton > button {{
    background: #fff;
    color: #333 !important;
    border: 1.5px solid #d0d0d0;
    border-radius: 8px;
    font-family: 'Fira Sans', sans-serif;
    font-weight: 600;
    font-size: 0.88rem;
    padding: 0.5rem 1.2rem;
    transition: all 0.2s;
}}
.stButton > button:hover {{
    background: {COLOR_PRIMARY} !important;
    color: #fff !important;
    border-color: {COLOR_PRIMARY} !important;
}}

/* ── Caption ── */
[data-testid="stCaptionContainer"] p {{ color: #aaa !important; font-size: 0.78rem !important; }}

/* ── Dataframe ── */
[data-testid="stDataFrame"] {{
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #e0e0e0;
}}
</style>
""", unsafe_allow_html=True)


# ─── Lógica ───────────────────────────────────────────────────

def _periodo_meses(empleador: str) -> int:
    return 6 if empleador in MASTER_BUS_EMPRESAS else 8


def _calcular_vencimientos(df: pd.DataFrame) -> pd.DataFrame:
    hoy = date.today()
    activos = df[(df["activo"] == "1") & df["fecha_fin"].isna()].copy()
    activos["periodo_meses"] = activos["empleador"].apply(_periodo_meses)
    activos["fecha_vencimiento"] = activos.apply(
        lambda r: r["fecha_inicio"] + relativedelta(months=r["periodo_meses"]), axis=1
    )
    activos["dias_diferencial"] = activos["fecha_vencimiento"].apply(
        lambda fv: (fv - hoy).days
    )

    def _cat(d):
        if d < 0:   return CAT_VENCIDO
        if d <= 45: return CAT_CERCANO
        return CAT_LEJANO

    activos["categoria"] = activos["dias_diferencial"].apply(_cat)
    return activos


# ─── Render ───────────────────────────────────────────────────

st.markdown("""
<div class="page-title">
    <div class="accent-bar"></div>
    <h1>Vencimientos — Período de Prueba</h1>
</div>
<p class="page-subtitle">
    Empleados activos según el estado de su período de prueba
    &nbsp;·&nbsp; 6 meses Master Bus &nbsp;·&nbsp; 8 meses resto
</p>
""", unsafe_allow_html=True)

df_raw, ts = cargar_datos()
df = _calcular_vencimientos(df_raw)

if df.empty:
    st.info("No se encontraron empleados activos con período de prueba calculable.")
    st.stop()

n_vencido = int((df["categoria"] == CAT_VENCIDO).sum())
n_cercano = int((df["categoria"] == CAT_CERCANO).sum())
n_lejano  = int((df["categoria"] == CAT_LEJANO).sum())

col_btn, col_cap = st.columns([1.5, 6])
with col_btn:
    if st.button("↺  Actualizar datos"):
        st.cache_data.clear()
        st.rerun()
with col_cap:
    st.caption(f"Datos al {ts.strftime('%d/%m/%Y %H:%M')}")

# ── KPI cards ────────────────────────────────────────────────
st.markdown('<div class="section-label">Resumen</div>', unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
cards = [
    (c1, CAT_VENCIDO,  n_vencido, "Vencimiento &lt; hoy — revisar",  COLOR_VENCIDO),
    (c2, CAT_CERCANO,  n_cercano, "1 – 45 días para vencer",          COLOR_CERCANO),
    (c3, CAT_LEJANO,   n_lejano,  "&gt; 45 días para vencer",         COLOR_LEJANO),
]
for col, label, count, desc, color in cards:
    with col:
        st.markdown(f"""
        <div class="kpi-card" style="--card-color:{color};">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value" style="color:{color};">{count}</div>
            <div class="kpi-desc">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

# ── Selector de categoría ─────────────────────────────────────
st.markdown('<div class="section-label">Detalle por categoría</div>', unsafe_allow_html=True)

cat_sel = st.radio(
    label="Categoría",
    options=CATEGORIAS,
    horizontal=True,
    label_visibility="collapsed",
)

color_cat = {CAT_VENCIDO: COLOR_VENCIDO, CAT_CERCANO: COLOR_CERCANO, CAT_LEJANO: COLOR_LEJANO}
color_sel = color_cat[cat_sel]

df_sel = df[df["categoria"] == cat_sel].copy()
df_sel = df_sel.sort_values("dias_diferencial", key=lambda s: s.abs()).reset_index(drop=True)

st.markdown(
    f'<div style="border-left:4px solid {color_sel}; padding-left:0.75rem; margin:0.75rem 0 0.5rem;">'
    f'<strong style="color:{color_sel}; font-size:1rem;">{cat_sel}</strong>'
    f'<span style="color:#888; font-size:0.85rem;"> &nbsp;—&nbsp; {len(df_sel)} empleado{"s" if len(df_sel) != 1 else ""}</span>'
    f'</div>',
    unsafe_allow_html=True,
)

if df_sel.empty:
    st.info("No hay empleados en esta categoría.")
    st.stop()

df_display = pd.DataFrame({
    "Legajo":      df_sel["legajo"].astype(str).str.strip(),
    "Nombre":      df_sel["apenom"].str.strip().str.title(),
    "Empresa":     df_sel["empleador"],
    "Cargo":       df_sel["cargo"].str.title(),
    "Sector":      df_sel["str"],
    "Ingreso":     df_sel["fecha_inicio"].apply(lambda d: d.strftime("%d/%m/%Y") if d else ""),
    "Período":     df_sel["periodo_meses"].apply(lambda m: f"{m} m"),
    "Vencimiento": df_sel["fecha_vencimiento"].apply(lambda d: d.strftime("%d/%m/%Y")),
    "Días":        df_sel["dias_diferencial"],
})

st.dataframe(
    df_display,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Días": st.column_config.NumberColumn(
            "Días",
            help="Negativo = ya venció · Positivo = días restantes",
            format="%+d",
        ),
    },
)
