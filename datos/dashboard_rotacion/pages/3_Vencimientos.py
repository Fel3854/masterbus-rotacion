"""Vista: Vencimientos — Período de Prueba · Grupo Master"""

import os
import sys
from datetime import date

import pandas as pd
import streamlit as st
from dateutil.relativedelta import relativedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import (
    cargar_datos,
    inyectar_css_base,
    COLOR_PRIMARY,
    COLOR_SECONDARY,
    COLOR_DANGER,
    COLOR_SURFACE,
    COLOR_BORDER,
    COLOR_TEXT,
    COLOR_MUTED,
)

# ─── Constantes ───────────────────────────────────────────────
MASTER_BUS_EMPRESAS = {"MASTER BUS S.A", "MASTER BUS SA", "MASTER BUS TASA"}

COLOR_VENCIDO  = "#D12F19"
COLOR_CERCANO  = "#ED5D3B"
COLOR_LEJANO   = "#2ECC71"

CAT_VENCIDO  = "Vencidos"
CAT_CERCANO  = "Vencimientos Cercanos"
CAT_LEJANO   = "Vencimientos Lejanos"

CATEGORIAS = [CAT_VENCIDO, CAT_CERCANO, CAT_LEJANO]


# ─── Lógica ───────────────────────────────────────────────────

def _periodo_meses(empleador: str) -> int:
    return 6 if empleador in MASTER_BUS_EMPRESAS else 8


def _calcular_vencimientos(df: pd.DataFrame) -> pd.DataFrame:
    hoy = date.today()

    activos = df[
        (df["activo"] == "1") & df["fecha_fin"].isna()
    ].copy()

    activos["periodo_meses"] = activos["empleador"].apply(_periodo_meses)
    activos["fecha_vencimiento"] = activos.apply(
        lambda r: r["fecha_inicio"] + relativedelta(months=r["periodo_meses"]),
        axis=1,
    )
    activos["dias_diferencial"] = activos["fecha_vencimiento"].apply(
        lambda fv: (fv - hoy).days
    )

    def _categoria(d):
        if d < 0:
            return CAT_VENCIDO
        if d <= 45:
            return CAT_CERCANO
        return CAT_LEJANO

    activos["categoria"] = activos["dias_diferencial"].apply(_categoria)
    return activos


def _card_html(label: str, count: int, condicion: str, color: str) -> str:
    return f"""
    <div style="
        background:{COLOR_SURFACE};
        border-left: 5px solid {color};
        border-top: 1px solid {COLOR_BORDER};
        border-right: 1px solid {COLOR_BORDER};
        border-bottom: 1px solid {COLOR_BORDER};
        border-radius: 10px;
        padding: 1.25rem 1.5rem;
        cursor: pointer;
    ">
        <div style="font-size:0.7rem;font-weight:700;letter-spacing:1px;
                    text-transform:uppercase;color:{COLOR_MUTED};margin-bottom:0.4rem;">
            {label}
        </div>
        <div style="font-family:'Fira Code',monospace;font-size:2.25rem;
                    font-weight:700;color:{color};line-height:1;">
            {count}
        </div>
        <div style="font-size:0.78rem;color:{COLOR_MUTED};margin-top:0.35rem;">
            {condicion}
        </div>
    </div>
    """


# ─── CSS adicional ────────────────────────────────────────────

EXTRA_CSS = f"""
<style>
[data-testid="stElementToolbar"] {{ display: none; }}

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
    color: #666; font-size: 0.9rem; margin: 0 0 1.75rem 17px;
}}
.section-label {{
    font-size: 0.7rem; font-weight: 700; letter-spacing: 1.2px;
    text-transform: uppercase; color: #888; margin-bottom: 0.75rem;
    margin-top: 1.5rem;
}}

/* Radio horizontal */
div[data-testid="stHorizontalBlock"] div[data-testid="stRadio"] > div {{
    flex-direction: row; gap: 1rem;
}}

/* Tabla sin índice visible */
.dataframe {{ font-family: 'Fira Code', monospace; font-size: 0.82rem; }}
</style>
"""


# ─── Render ───────────────────────────────────────────────────

def render():
    inyectar_css_base()
    st.markdown(EXTRA_CSS, unsafe_allow_html=True)

    # Header
    st.markdown("""
    <div class="page-title">
        <div class="accent-bar"></div>
        <h1>Vencimientos — Período de Prueba</h1>
    </div>
    <p class="page-subtitle">
        Empleados activos agrupados según el estado de su período de prueba
        (6 meses Master Bus · 8 meses resto)
    </p>
    """, unsafe_allow_html=True)

    # Carga de datos
    df_raw, ts = cargar_datos()
    df = _calcular_vencimientos(df_raw)

    if df.empty:
        st.info("No se encontraron empleados activos con período de prueba calculable.")
        return

    n_vencido = int((df["categoria"] == CAT_VENCIDO).sum())
    n_cercano = int((df["categoria"] == CAT_CERCANO).sum())
    n_lejano  = int((df["categoria"] == CAT_LEJANO).sum())

    # Refresh
    col_ref, _ = st.columns([1, 5])
    with col_ref:
        if st.button("↺ Actualizar datos"):
            st.cache_data.clear()
            st.rerun()
    st.caption(f"Datos al {ts.strftime('%d/%m/%Y %H:%M')}")

    # ── Matriz resumen ────────────────────────────────────────
    st.markdown('<div class="section-label">Resumen</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(_card_html(
            CAT_VENCIDO, n_vencido,
            "Vencimiento &lt; hoy — a revisar",
            COLOR_VENCIDO,
        ), unsafe_allow_html=True)
    with c2:
        st.markdown(_card_html(
            CAT_CERCANO, n_cercano,
            "1 – 45 días para vencer",
            COLOR_CERCANO,
        ), unsafe_allow_html=True)
    with c3:
        st.markdown(_card_html(
            CAT_LEJANO, n_lejano,
            "&gt; 45 días para vencer",
            COLOR_LEJANO,
        ), unsafe_allow_html=True)

    # ── Selector de categoría ─────────────────────────────────
    st.markdown('<div class="section-label">Apertura de detalle</div>', unsafe_allow_html=True)

    cat_sel = st.radio(
        label="Categoría",
        options=CATEGORIAS,
        horizontal=True,
        label_visibility="collapsed",
    )

    # ── Tabla de detalle ──────────────────────────────────────
    df_sel = df[df["categoria"] == cat_sel].copy()
    df_sel = df_sel.sort_values("dias_diferencial", key=lambda s: s.abs()).reset_index(drop=True)

    color_cat = {CAT_VENCIDO: COLOR_VENCIDO, CAT_CERCANO: COLOR_CERCANO, CAT_LEJANO: COLOR_LEJANO}

    st.markdown(
        f'<div style="border-left:4px solid {color_cat[cat_sel]};'
        f'padding-left:0.75rem;margin:0.75rem 0 0.5rem;">'
        f'<strong style="color:{color_cat[cat_sel]};">{cat_sel}</strong>'
        f' — {len(df_sel)} empleado{"s" if len(df_sel) != 1 else ""}'
        f'</div>',
        unsafe_allow_html=True,
    )

    if df_sel.empty:
        st.info("No hay empleados en esta categoría.")
        return

    # Formatear para display
    df_display = pd.DataFrame({
        "Legajo":       df_sel["legajo"].astype(str).str.strip(),
        "Nombre":       df_sel["apenom"].str.strip().str.title(),
        "Empresa":      df_sel["empleador"],
        "Cargo":        df_sel["cargo"].str.title(),
        "Sector":       df_sel["str"],
        "Ingreso":      df_sel["fecha_inicio"].apply(lambda d: d.strftime("%d/%m/%Y") if d else ""),
        "Período (m)":  df_sel["periodo_meses"],
        "Vencimiento":  df_sel["fecha_vencimiento"].apply(lambda d: d.strftime("%d/%m/%Y")),
        "Diferencial":  df_sel["dias_diferencial"],
    })

    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Diferencial": st.column_config.NumberColumn(
                "Diferencial (días)",
                help="Negativo = ya venció · Positivo = días restantes",
                format="%+d",
            ),
            "Período (m)": st.column_config.NumberColumn(
                "Período (m)",
                help="Meses de período de prueba según empresa",
                format="%d m",
            ),
        },
    )


render()
