"""Vista: Auditoría — registro de movimientos de los usuarios del dashboard."""

import html
import os
import sys
from datetime import date, timedelta

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from auth import puede_ver_auditoria  # noqa: E402
from utils import inyectar_css_base, get_supabase  # noqa: E402
import auditoria as au  # noqa: E402

_esc = html.escape

DIAS_DEFECTO = 30

inyectar_css_base()
st.markdown("""
<style>
.kpi-card {
    background: var(--card-bg, #f4f4f4); border-radius: 12px;
    border: 1px solid var(--card-color, #ddd);
    border-left: 7px solid var(--card-color, #ccc);
    padding: 0.9rem 1.2rem; box-shadow: 0 1px 5px rgba(0,0,0,0.06);
}
.kpi-label {
    font-size: 0.7rem; font-weight: 800; letter-spacing: 0.6px;
    text-transform: uppercase; color: var(--card-color, #666); margin-bottom: 0.35rem;
}
.kpi-value {
    font-family: 'Fira Code', monospace; font-size: 2.1rem; font-weight: 700;
    line-height: 1; color: var(--card-color, #333);
}
.kpi-sub { font-size: 0.74rem; color: #777; margin-top: 4px; }

.mov-row {
    border-left: 4px solid var(--acc, #ccc); padding: 7px 0 7px 12px;
    margin-bottom: 3px;
}
.mov-top { font-size: 0.9rem; color: #1a1a1a; }
.mov-chip {
    display: inline-block; font-size: 0.66rem; font-weight: 800;
    padding: 2px 9px; border-radius: 11px; margin-right: 7px;
    text-transform: uppercase; letter-spacing: 0.4px;
    background: var(--acc, #eee); color: #fff;
}
.mov-user { font-weight: 700; }
.mov-meta { font-size: 0.76rem; color: #777; margin-top: 2px; }
.dia-head {
    font-size: 0.74rem; font-weight: 800; text-transform: uppercase;
    letter-spacing: 0.7px; color: #999; margin: 18px 0 6px;
    border-bottom: 1px solid #e2e2e2; padding-bottom: 3px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="page-title">
  <div class="accent-bar"></div>
  <h1>Auditoría</h1>
</div>
<p class="page-subtitle">Registro de movimientos: quién cargó, modificó, eliminó, exportó o accedió a información sensible.</p>
""", unsafe_allow_html=True)

# La página está fuera de la navegación para quien no tiene el permiso, pero
# igual se corta acá: una URL directa no puede saltear el control.
if not puede_ver_auditoria():
    st.error("No tenés permiso para ver la auditoría.")
    st.stop()


@st.cache_data(ttl=120, show_spinner=False)
def _leer(desde: date, hasta: date) -> pd.DataFrame:
    """Movimientos del período. Se filtra en la base: el log crece sin techo."""
    resp = (
        get_supabase().table(au.TABLA)
        .select(",".join(au.COLUMNAS))
        .gte("fecha", desde.isoformat())
        # `hasta` es un día completo: el rango va hasta el arranque del siguiente.
        .lt("fecha", (hasta + timedelta(days=1)).isoformat())
        .order("fecha", desc=True)
        .limit(5000)
        .execute()
    )
    return pd.DataFrame(resp.data or [], columns=au.COLUMNAS)


c1, c2 = st.columns([1, 1])
with c1:
    desde = st.date_input("Desde", value=date.today() - timedelta(days=DIAS_DEFECTO),
                          format="DD/MM/YYYY", key="au_desde")
with c2:
    hasta = st.date_input("Hasta", value=date.today(), format="DD/MM/YYYY", key="au_hasta")

if desde > hasta:
    st.error("La fecha «Desde» no puede ser posterior a «Hasta».")
    st.stop()

df = au.normalizar(_leer(desde, hasta))

if df.empty:
    st.info("No hay movimientos registrados en el período seleccionado.")
    st.stop()

# ─── KPIs ─────────────────────────────────────────────────────
escrituras = int(df["es_escritura"].sum())
sensibles = int(df["accion"].isin(("lectura", "export")).sum())
fallidos = int((df["accion"] == "login_fallido").sum())
kpis = [
    ("Movimientos", len(df), "#333333", f"{df['usuario'].nunique()} usuarios"),
    ("Altas, bajas y cambios", escrituras, "#B45309", "modificaron datos"),
    ("Accesos sensibles", sensibles, "#46BCD2", "lecturas y exportaciones"),
    ("Logins fallidos", fallidos, "#D12F19" if fallidos else "#8C8987", "contraseña incorrecta"),
]
for col, (label, val, color, sub) in zip(st.columns(4), kpis):
    with col:
        st.markdown(
            f'<div class="kpi-card" style="--card-color:{color};">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{val}</div>'
            f'<div class="kpi-sub">{sub}</div></div>',
            unsafe_allow_html=True)

st.write("")
tab_mov, tab_usr = st.tabs(["Movimientos", "Por usuario"])

# ══ Movimientos ══
with tab_mov:
    f1, f2, f3 = st.columns([2, 2, 3])
    with f1:
        usuarios = st.multiselect(
            "Usuario", options=sorted(df["usuario"].unique()), key="au_usr")
    with f2:
        modulos = st.multiselect(
            "Módulo", options=sorted(df["modulo"].unique()),
            format_func=lambda m: au.MODULOS.get(m, m), key="au_mod")
    with f3:
        texto = st.text_input("Buscar en el detalle",
                              placeholder="Nombre, legajo, tema...", key="au_txt")

    solo_esc = st.checkbox(
        "Solo movimientos que cambiaron datos (altas, bajas y cambios)",
        value=False, key="au_solo_esc")

    f = au.filtrar(df, usuarios=usuarios, modulos=modulos, texto=texto)
    if solo_esc:
        f = f[f["es_escritura"]].reset_index(drop=True)

    if f.empty:
        st.info("Ningún movimiento coincide con los filtros.")
    else:
        st.caption(f"{len(f)} movimiento(s)")
        dia_actual = None
        for _, r in f.iterrows():
            if r["dia"] != dia_actual:
                dia_actual = r["dia"]
                st.markdown(
                    f'<div class="dia-head">{dia_actual.strftime("%A %d/%m/%Y")}</div>',
                    unsafe_allow_html=True)
            color = au.ACCIONES.get(r["accion"], {}).get("color", "#8C8987")
            st.markdown(
                f'<div class="mov-row" style="--acc:{color};">'
                f'<div class="mov-top">'
                f'<span class="mov-chip">{_esc(str(r["accion_label"]))}</span>'
                f'<span class="mov-user">{_esc(str(r["nombre"]))}</span> — '
                f'{_esc(str(r["detalle"] or "—"))}</div>'
                f'<div class="mov-meta">{r["fecha_local"].strftime("%H:%M")} · '
                f'{_esc(str(r["modulo_label"]))}</div></div>',
                unsafe_allow_html=True)

        st.write("")
        st.download_button(
            "⬇  Descargar auditoría (Excel)",
            data=au.exportar_excel(f),
            file_name=f"auditoria_{desde.strftime('%d-%m-%Y')}_a_{hasta.strftime('%d-%m-%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

# ══ Por usuario ══
with tab_usr:
    res = au.resumen_por_usuario(df)
    st.dataframe(
        pd.DataFrame({
            "Usuario": res["nombre"],
            "Movimientos": res["movimientos"],
            "Cambios de datos": res["escrituras"],
            "Último movimiento": res["ultimo"].dt.strftime("%d/%m/%Y %H:%M"),
        }),
        hide_index=True, width="stretch",
    )

    st.markdown('<p class="section-label">Actividad por módulo</p>',
                unsafe_allow_html=True)
    por_mod = au.resumen_por_modulo(df)
    st.dataframe(
        pd.DataFrame({
            "Módulo": por_mod["modulo_label"],
            "Acción": por_mod["accion_label"],
            "Movimientos": por_mod["n"],
        }),
        hide_index=True, width="stretch",
    )
