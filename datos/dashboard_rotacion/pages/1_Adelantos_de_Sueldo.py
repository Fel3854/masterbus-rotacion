"""Vista: Adelantos de Sueldo — Grupo Master"""

import os
import pandas as pd
import streamlit as st
from datetime import date

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import cargar_empleados_activos, get_supabase, COLOR_PRIMARY, COLOR_SECONDARY

# ─── CSS ─────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fira+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=Fira+Code:wght@400;500;600&display=swap');

html, body, [class*="css"] {{
    font-family: 'Fira Sans', sans-serif;
    color: #333333;
}}
p, span, li, td, th, label, div, h1, h2, h3, h4, h5, h6 {{ color: #333333; }}
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span,
[data-testid="stText"],
[data-testid="stCaptionContainer"] p,
[data-testid="stWidgetLabel"] p {{ color: #333333 !important; }}
[data-testid="stDataFrame"] td,
[data-testid="stDataFrame"] th,
[data-testid="stDataFrame"] span {{ color: #333333 !important; }}
.stApp {{ background-color: #EDEDED; }}

/* ── Ocultar toolbar del dataframe y hint "Press Enter" ── */
[data-testid="stElementToolbar"] {{ display: none; }}
[data-testid="InputInstructions"] {{ display: none !important; }}

/* ── Header de página ── */
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

/* ── Sección header ── */
.section-label {{
    font-size: 0.7rem; font-weight: 700; letter-spacing: 1.2px;
    text-transform: uppercase; color: #888; margin-bottom: 0.75rem;
}}

/* ── Cards ── */
.card {{
    background: #fff; border-radius: 12px;
    border: 1px solid #e0e0e0;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06), 0 4px 12px rgba(0,0,0,0.04);
    padding: 1.5rem;
    margin-bottom: 1rem;
}}

/* ── KPI cards ── */
.kpi-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-bottom: 1rem; }}
.kpi-card {{
    background: #fff; border-radius: 10px;
    border: 1px solid #e8e8e8;
    padding: 1rem 1.1rem;
}}
.kpi-label {{ font-size: 0.72rem; font-weight: 600; color: #888; letter-spacing: 0.8px; text-transform: uppercase; margin-bottom: 0.3rem; }}
.kpi-value {{ font-family: 'Fira Code', monospace; font-size: 1.5rem; font-weight: 600; color: #1a1a1a; }}
.kpi-sub {{ font-size: 0.75rem; color: #aaa; margin-top: 0.15rem; }}

/* ── Último registro card ── */
.last-rec {{
    background: #fff; border-radius: 10px;
    border-left: 3px solid {COLOR_SECONDARY};
    border-top: 1px solid #e8e8e8;
    border-right: 1px solid #e8e8e8;
    border-bottom: 1px solid #e8e8e8;
    padding: 0.9rem 1.1rem;
}}
.last-rec-name {{ font-weight: 600; font-size: 0.92rem; color: #1a1a1a; }}
.last-rec-detail {{ font-size: 0.8rem; color: #888; margin-top: 0.2rem; }}

/* ── Formulario ── */
div[data-testid="stForm"] {{
    background: #fff; border-radius: 12px;
    border: 1px solid #e0e0e0;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06), 0 4px 12px rgba(0,0,0,0.04);
    padding: 1.5rem 1.75rem;
}}

/* ── Inputs ── */
div[data-testid="stSelectbox"] > div > div,
div[data-testid="stSelectbox"] input,
div[data-testid="stDateInput"] input,
div[data-testid="stNumberInput"] input,
.stTextArea textarea {{
    background: #fafafa !important;
    color: #333333 !important;
    border: 1.5px solid #e0e0e0 !important;
    border-radius: 8px !important;
    font-family: 'Fira Sans', sans-serif !important;
    font-size: 0.9rem !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
}}
div[data-testid="stSelectbox"] > div > div:focus-within,
div[data-testid="stDateInput"] input:focus,
div[data-testid="stNumberInput"] input:focus,
.stTextArea textarea:focus {{
    border-color: {COLOR_PRIMARY} !important;
    box-shadow: 0 0 0 3px rgba(237,93,59,0.12) !important;
    outline: none !important;
}}

/* ── Labels ── */
label[data-testid="stWidgetLabel"] p,
.stTextArea label p {{
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    color: #444 !important;
    letter-spacing: 0.2px;
}}

/* ── Botón submit ── */
div[data-testid="stForm"] .stButton > button {{
    width: 100%;
    background: {COLOR_PRIMARY};
    color: #fff;
    border: none;
    border-radius: 8px;
    font-family: 'Fira Sans', sans-serif;
    font-size: 0.92rem;
    font-weight: 600;
    padding: 0.65rem 1.5rem;
    letter-spacing: 0.2px;
    cursor: pointer;
    transition: background 0.2s ease, transform 0.1s ease, box-shadow 0.2s ease;
    box-shadow: 0 2px 8px rgba(237,93,59,0.3);
}}
div[data-testid="stForm"] .stButton > button:hover {{
    background: #d44e2f;
    box-shadow: 0 4px 14px rgba(237,93,59,0.4);
    transform: translateY(-1px);
}}
div[data-testid="stForm"] .stButton > button:active {{
    transform: translateY(0);
    box-shadow: 0 1px 4px rgba(237,93,59,0.3);
}}

/* ── Botón descarga ── */
.stDownloadButton > button {{
    background: {COLOR_PRIMARY} !important;
    color: #fff !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'Fira Sans', sans-serif !important;
    font-size: 0.88rem !important;
    font-weight: 600 !important;
    padding: 0.55rem 1.4rem !important;
    cursor: pointer !important;
    transition: background 0.2s ease, transform 0.1s ease !important;
    box-shadow: 0 2px 8px rgba(237,93,59,0.3) !important;
}}
.stDownloadButton > button:hover {{
    background: #d44e2f !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(237,93,59,0.4) !important;
}}

/* ── Mensajes de éxito/error ── */
div[data-testid="stAlert"] {{
    border-radius: 8px !important;
    border: none !important;
}}

/* ── Dataframe ── */
div[data-testid="stDataFrame"] {{
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #e8e8e8;
}}

/* ── Divider ── */
hr {{ border-color: #e0e0e0 !important; margin: 1.75rem 0 !important; }}

/* ── Métricas descarga ── */
.download-meta {{
    display: flex; gap: 1.5rem; align-items: center;
    margin-bottom: 1rem;
}}
.download-meta .pill {{
    background: #f0f0f0; border-radius: 20px;
    padding: 0.3rem 0.85rem;
    font-size: 0.8rem; font-weight: 600; color: #444;
}}
.download-meta .pill span {{ color: {COLOR_PRIMARY}; }}

/* ── Expander eliminar ── */
div[data-testid="stExpander"] summary p {{
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    color: #888 !important;
}}
.delete-btn-wrap button {{
    background: #fff !important;
    color: #D12F19 !important;
    border: 1.5px solid #D12F19 !important;
    border-radius: 8px !important;
}}
.delete-btn-wrap button:hover {{
    background: #D12F19 !important;
    color: #fff !important;
}}
</style>
""", unsafe_allow_html=True)

TABLA = "adelantos"


# ─── Helpers Supabase ─────────────────────────────────────────
def _guardar(legajo, apenom, empleador, fecha, monto, motivo):
    get_supabase().table(TABLA).insert({
        "legajo": legajo, "apenom": apenom, "empleador": empleador,
        "fecha_adelanto": fecha.isoformat(),
        "monto": int(monto),
        "motivo": motivo.strip() if motivo else None,
    }).execute()


def _leer(desde: date, hasta: date) -> pd.DataFrame:
    resp = (
        get_supabase().table(TABLA)
        .select("id,legajo,apenom,empleador,fecha_adelanto,monto,motivo")
        .gte("fecha_adelanto", str(desde))
        .lte("fecha_adelanto", str(hasta))
        .order("fecha_adelanto", desc=True)
        .execute()
    )
    if not resp.data:
        return pd.DataFrame(columns=["id","legajo","apenom","empleador","fecha_adelanto","monto","motivo"])
    df = pd.DataFrame(resp.data)
    df["fecha_adelanto"] = df["fecha_adelanto"].apply(lambda x: pd.to_datetime(x).date())
    return df


def _eliminar(record_id: str):
    get_supabase().table(TABLA).delete().eq("id", record_id).execute()


def _stats_mes() -> dict:
    hoy = date.today()
    resp = (
        get_supabase().table(TABLA)
        .select("monto,apenom,fecha_adelanto")
        .gte("fecha_adelanto", str(hoy.replace(day=1)))
        .lte("fecha_adelanto", str(hoy))
        .order("fecha_adelanto", desc=True)
        .execute()
    )
    data: list[dict] = resp.data or []  # type: ignore[assignment]
    total_monto = sum(r["monto"] for r in data)
    ultimo = data[0] if data else None
    return {"count": len(data), "total": total_monto, "ultimo": ultimo}


def _generar_txt(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    lines = []
    for _, r in df.iterrows():
        legajo = int(str(r["legajo"]).strip())
        monto_str = f"{float(r['monto']):.2f}".replace(".", ",")
        lines.append(f"{legajo:>10} {monto_str:>9}")
    return "\n".join(lines)


# ─── Cargar empleados ─────────────────────────────────────────
df_emp = pd.DataFrame(columns=["legajo", "apenom", "empleador"])
try:
    df_emp = cargar_empleados_activos()
except Exception:
    st.error("No se pudieron cargar los empleados desde la API.")
    if st.button("Reintentar"):
        st.cache_data.clear()
        st.rerun()
    st.stop()

opciones_emp = [
    f"{r['legajo']} — {r['apenom']}  ·  {r['empleador']}"
    for _, r in df_emp.iterrows()
]

# ─── Header ──────────────────────────────────────────────────
st.markdown("""
<div class="page-title">
  <div class="accent-bar"></div>
  <h1>Adelantos de Sueldo</h1>
</div>
<p class="page-subtitle">Registrá adelantos de sueldo para empleados activos del Grupo Master.</p>
""", unsafe_allow_html=True)

# ─── Layout principal: form (izq) + stats (der) ───────────────
col_form, col_stats = st.columns([3, 2], gap="large")

with col_form:
    st.markdown('<p class="section-label">Registrar adelanto</p>', unsafe_allow_html=True)

    with st.form("form_adelanto", clear_on_submit=True):
        empleado_sel = st.selectbox(
            "Empleado",
            options=opciones_emp,
            index=None,
            placeholder="Escribí nombre, apellido o legajo para buscar...",
        )
        col_f, col_m = st.columns(2)
        with col_f:
            fecha = st.date_input("Fecha del adelanto", value=date.today())
        with col_m:
            monto = st.number_input("Monto ($)", min_value=1, step=500, value=None,
                                    placeholder="Ej: 50000")
        motivo = st.text_area("Motivo", max_chars=300,
                               placeholder="Opcional — razón del adelanto", height=90)
        submitted = st.form_submit_button("Registrar adelanto")

    if submitted:
        if not empleado_sel:
            st.error("Seleccioná un empleado para continuar.")
        elif not monto:
            st.error("Ingresá un monto mayor a cero.")
        else:
            legajo_sel = empleado_sel.split(" — ")[0].strip()
            row = df_emp[df_emp["legajo"] == legajo_sel]
            if row.empty:
                st.error("No se encontró el empleado. Intentá de nuevo.")
            else:
                r = row.iloc[0]
                try:
                    _guardar(r["legajo"], r["apenom"], r["empleador"], fecha, monto, motivo)
                    monto_fmt = f"$ {monto:,.0f}".replace(",",".")
                    st.success(f"✓ Adelanto registrado — **{r['apenom']}** · {fecha.strftime('%d/%m/%Y')} · **{monto_fmt}**")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

with col_stats:
    st.markdown('<p class="section-label">Resumen del mes actual</p>', unsafe_allow_html=True)
    try:
        stats = _stats_mes()
        meses = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
                 7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}
        mes_actual = meses[date.today().month]
        total_fmt = f"$ {stats['total']:,.0f}".replace(",",".")

        st.markdown(f"""
        <div class="kpi-grid">
          <div class="kpi-card">
            <div class="kpi-label">Adelantos en {mes_actual}</div>
            <div class="kpi-value">{stats['count']}</div>
            <div class="kpi-sub">registros</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Monto total</div>
            <div class="kpi-value" style="font-size:1.2rem">{total_fmt}</div>
            <div class="kpi-sub">{mes_actual} {date.today().year}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        if stats["ultimo"]:
            ult = stats["ultimo"]
            fec_ult = pd.to_datetime(ult["fecha_adelanto"]).strftime("%d/%m/%Y")
            monto_ult = f"$ {int(ult['monto']):,.0f}".replace(",",".")
            st.markdown(f"""
            <p class="section-label" style="margin-top:1rem">Último registrado</p>
            <div class="last-rec">
              <div class="last-rec-name">{ult['apenom']}</div>
              <div class="last-rec-detail">{fec_ult} &nbsp;·&nbsp; {monto_ult}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="last-rec"><div class="last-rec-detail">Sin registros este mes.</div></div>', unsafe_allow_html=True)

    except Exception:
        st.info("No se pudieron cargar las estadísticas.")

# ─── Sección descarga ─────────────────────────────────────────
st.divider()
st.markdown('<p class="section-label">Descargar listado</p>', unsafe_allow_html=True)

hoy = date.today()
col_d, col_h, col_btn = st.columns([2, 2, 3], gap="medium")
with col_d:
    desde = st.date_input("Desde", value=hoy.replace(day=1), key="desde_a")
with col_h:
    hasta = st.date_input("Hasta", value=hoy, key="hasta_a")

df_reg = pd.DataFrame(columns=["id","legajo","apenom","empleador","fecha_adelanto","monto","motivo"])
try:
    df_reg = _leer(desde, hasta)
except Exception as e:
    st.error(f"Error al consultar: {e}")
    st.stop()

if df_reg.empty:
    st.info("No hay adelantos registrados para el período seleccionado.")
else:
    total_reg = int(df_reg["monto"].sum())
    total_fmt = f"$ {total_reg:,.0f}".replace(",",".")
    st.markdown(f"""
    <div class="download-meta">
      <span class="pill"><span>{len(df_reg)}</span> registros</span>
      <span class="pill">Total <span>{total_fmt}</span></span>
    </div>
    """, unsafe_allow_html=True)

    df_display = df_reg.rename(columns={
        "legajo":"Legajo","apenom":"Nombre","empleador":"Empleador",
        "fecha_adelanto":"Fecha","monto":"Monto ($)","motivo":"Motivo",
    })
    df_display["Monto ($)"] = df_display["Monto ($)"].apply(lambda x: f"$ {int(x):,.0f}".replace(",","."))
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    txt = _generar_txt(df_reg)
    st.download_button(
        "⬇  Descargar TXT",
        data=txt.encode("utf-8"),
        file_name=f"adelantos_{desde.strftime('%Y%m%d')}_{hasta.strftime('%Y%m%d')}.txt",
        mime="text/plain",
    )

# ─── Sección eliminar ─────────────────────────────────────────
st.divider()
with st.expander("Eliminar un registro"):
    if df_reg.empty:
        st.info("No hay registros en el período seleccionado para eliminar.")
    else:
        opciones = {
            f"{row['fecha_adelanto'].strftime('%d/%m/%Y')}  —  {row['apenom']}  —  $ {int(row['monto']):,}".replace(",", "."): row["id"]
            for _, row in df_reg.iterrows()
        }
        sel_label = st.selectbox("Seleccionar registro", list(opciones.keys()), key="sel_borrar_a")
        sel_id = opciones[sel_label]

        st.markdown('<div class="delete-btn-wrap">', unsafe_allow_html=True)
        if st.button("Eliminar registro", key="btn_del_a"):
            st.session_state["del_id_a"] = sel_id
            st.session_state["del_label_a"] = sel_label
        st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.get("del_id_a") == sel_id:
            st.warning(f"¿Eliminar **{sel_label}**? Esta acción no se puede deshacer.")
            c1, c2 = st.columns([1, 1])
            with c1:
                if st.button("Sí, eliminar", key="btn_confirm_a"):
                    _eliminar(st.session_state["del_id_a"])
                    st.session_state.pop("del_id_a", None)
                    st.session_state.pop("del_label_a", None)
                    st.success("Registro eliminado.")
                    st.rerun()
            with c2:
                if st.button("Cancelar", key="btn_cancel_a"):
                    st.session_state.pop("del_id_a", None)
                    st.session_state.pop("del_label_a", None)
                    st.rerun()
