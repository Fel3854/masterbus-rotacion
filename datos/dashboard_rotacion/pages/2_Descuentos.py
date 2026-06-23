"""Vista: Descuentos — Grupo Master"""

import os
import uuid
import pandas as pd
import streamlit as st
from datetime import date
from dateutil.relativedelta import relativedelta

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import cargar_empleados_activos, get_supabase, slug_empleador, COLOR_PRIMARY, COLOR_SECONDARY
from auth import can_edit

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

[data-testid="stElementToolbar"] {{ display: none; }}
[data-testid="InputInstructions"] {{ display: none !important; }}

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
}}

.kpi-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-bottom: 1rem; }}
.kpi-card {{
    background: #fff; border-radius: 10px;
    border: 1px solid #e8e8e8;
    padding: 1rem 1.1rem;
}}
.kpi-label {{ font-size: 0.72rem; font-weight: 600; color: #888; letter-spacing: 0.8px; text-transform: uppercase; margin-bottom: 0.3rem; }}
.kpi-value {{ font-family: 'Fira Code', monospace; font-size: 1.5rem; font-weight: 600; color: #1a1a1a; }}
.kpi-sub {{ font-size: 0.75rem; color: #aaa; margin-top: 0.15rem; }}

.last-rec {{
    background: #fff; border-radius: 10px;
    border-left: 3px solid {COLOR_PRIMARY};
    border-top: 1px solid #e8e8e8;
    border-right: 1px solid #e8e8e8;
    border-bottom: 1px solid #e8e8e8;
    padding: 0.9rem 1.1rem;
}}
.last-rec-name {{ font-weight: 600; font-size: 0.92rem; color: #1a1a1a; }}
.last-rec-detail {{ font-size: 0.8rem; color: #888; margin-top: 0.2rem; }}

/* ── Badge de tipo ── */
.tipo-badge {{
    display: inline-block;
    background: #f0f4ff; color: #2563eb;
    border-radius: 20px; padding: 0.15rem 0.6rem;
    font-size: 0.75rem; font-weight: 600;
    margin-top: 0.3rem;
}}

div[data-testid="stForm"] {{
    background: #fff; border-radius: 12px;
    border: 1px solid #e0e0e0;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06), 0 4px 12px rgba(0,0,0,0.04);
    padding: 1.5rem 1.75rem;
}}

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

label[data-testid="stWidgetLabel"] p,
.stTextArea label p {{
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    color: #444 !important;
    letter-spacing: 0.2px;
}}

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

div[data-testid="stAlert"] {{
    border-radius: 8px !important;
    border: none !important;
}}

div[data-testid="stDataFrame"] {{
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #e8e8e8;
}}

hr {{ border-color: #e0e0e0 !important; margin: 1.75rem 0 !important; }}

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

TABLA = "descuentos"

# Reemplazar con los tipos reales cuando se indiquen
TIPOS_DESCUENTO = [
    "Préstamo",
    "Anticipo SAC",
    "Infracciones",
    "Vacaciones",
    "LINTI",
    "Cubiertas",
    "Baterías",
    "Indumentaria",
    "Teléfono",
]

COLORES_TIPO = {
    "Préstamo":          "#f0f4ff:#2563eb",
    "Anticipo SAC":      "#fff4ed:#ed5d3b",
    "Infracciones":      "#fff1f2:#dc2626",
    "Vacaciones":        "#f0fdf4:#16a34a",
    "LINTI":             "#faf5ff:#7c3aed",
    "Cubiertas":         "#f0fdfa:#0d9488",
    "Baterías":          "#fefce8:#ca8a04",
    "Indumentaria":      "#fdf2f8:#db2777",
    "Teléfono":          "#eef2ff:#4f46e5",
    "Adelanto de Sueldo":"#ecfdf5:#059669",
}

TIPOS_FILTRO = TIPOS_DESCUENTO + ["Adelanto de Sueldo"]


# ─── Helpers Supabase ─────────────────────────────────────────
def _split_cuotas(total: int, n: int) -> list[int]:
    """Reparte el total en n cuotas enteras; el resto va a las primeras
    (ej: 10000 en 3 → [3334, 3333, 3333])."""
    base, rem = divmod(int(total), n)
    return [base + 1 if i < rem else base for i in range(n)]


def _guardar(legajo, apenom, empleador, tipo, fecha, monto, motivo,
             grupo_id=None, cuota_numero=1, cuotas_total=1, monto_total=None):
    get_supabase().table(TABLA).insert({
        "legajo": legajo, "apenom": apenom, "empleador": empleador,
        "tipo_descuento": tipo,
        "fecha_descuento": fecha.isoformat(),
        "monto": int(monto),
        "motivo": motivo.strip() if motivo else None,
        "grupo_id": grupo_id,
        "cuota_numero": cuota_numero,
        "cuotas_total": cuotas_total,
        "monto_total": int(monto_total) if monto_total is not None else int(monto),
    }).execute()


def _leer(desde: date, hasta: date) -> pd.DataFrame:
    resp = (
        get_supabase().table(TABLA)
        .select("id,legajo,apenom,empleador,tipo_descuento,fecha_descuento,monto,motivo,grupo_id,cuota_numero,cuotas_total,monto_total")
        .gte("fecha_descuento", str(desde))
        .lte("fecha_descuento", str(hasta))
        .order("fecha_descuento", desc=True)
        .execute()
    )
    if not resp.data:
        return pd.DataFrame(columns=["id","legajo","apenom","empleador","tipo_descuento","fecha_descuento","monto","motivo","grupo_id","cuota_numero","cuotas_total","monto_total"])
    df = pd.DataFrame(resp.data)
    df["fecha_descuento"] = pd.to_datetime(df["fecha_descuento"]).dt.date
    return df


def _eliminar(record_id: str, tabla: str = TABLA):
    get_supabase().table(tabla).delete().eq("id", record_id).execute()


def _eliminar_grupo(grupo_id: str):
    get_supabase().table(TABLA).delete().eq("grupo_id", grupo_id).execute()


def _leer_adelantos(desde: date, hasta: date) -> pd.DataFrame:
    cols = ["id","legajo","apenom","empleador","tipo_descuento","fecha_descuento","monto","motivo","grupo_id","cuota_numero","cuotas_total","monto_total"]
    resp = (
        get_supabase().table("adelantos")
        .select("id,legajo,apenom,empleador,fecha_adelanto,monto,motivo")
        .gte("fecha_adelanto", str(desde))
        .lte("fecha_adelanto", str(hasta))
        .order("fecha_adelanto", desc=True)
        .execute()
    )
    if not resp.data:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(resp.data)
    df["fecha_descuento"] = pd.to_datetime(df["fecha_adelanto"]).dt.date
    df["tipo_descuento"] = "Adelanto de Sueldo"
    df["grupo_id"] = None
    df["cuota_numero"] = 1
    df["cuotas_total"] = 1
    df["monto_total"] = df["monto"]
    return df[cols]


def _stats_mes() -> dict:
    hoy = date.today()
    resp = (
        get_supabase().table(TABLA)
        .select("monto,apenom,fecha_descuento,tipo_descuento")
        .gte("fecha_descuento", str(hoy.replace(day=1)))
        .lte("fecha_descuento", str(hoy))
        .order("fecha_descuento", desc=True)
        .execute()
    )
    data = resp.data or []
    total = sum(r["monto"] for r in data)
    return {"count": len(data), "total": total, "ultimo": data[0] if data else None}


def _generar_txt(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    lines = []
    for _, r in df.iterrows():
        legajo = int(str(r["legajo"]).strip())
        monto_str = f"{float(r['monto']):.2f}".replace(".", ",")
        apenom = str(r.get("apenom", "") or "").strip()
        lines.append(f"{legajo:>10} {monto_str:>9}  {apenom}")
    return "\n".join(lines)


# ─── Cargar empleados ─────────────────────────────────────────
try:
    df_emp = cargar_empleados_activos()
except Exception:
    st.error("No se pudieron cargar los empleados desde la API.")
    if st.button("Reintentar"):
        st.cache_data.clear()
        st.rerun()
    st.stop()

# Mapa opción -> fila exacta (legajo+apenom+empleador identifican unívocamente,
# evitando que un legajo repetido en otra empresa traiga al empleado equivocado)
opciones_map = {
    f"{r['legajo']} — {r['apenom']}  ·  {r['empleador']}": r
    for _, r in df_emp.iterrows()
}
opciones_emp = list(opciones_map.keys())

# ─── Header ──────────────────────────────────────────────────
st.markdown("""
<div class="page-title">
  <div class="accent-bar"></div>
  <h1>Descuentos</h1>
</div>
<p class="page-subtitle">Registrá descuentos para empleados activos del Grupo Master.</p>
""", unsafe_allow_html=True)

# ─── Layout principal ─────────────────────────────────────────
col_form, col_stats = st.columns([3, 2], gap="large")

with col_form:
    if not can_edit("descuentos"):
        st.markdown('<p class="section-label">Descuentos</p>', unsafe_allow_html=True)
        st.caption("Modo solo lectura — no tenés permiso para registrar descuentos.")
    else:
        st.markdown('<p class="section-label">Registrar descuento</p>', unsafe_allow_html=True)

        with st.form("form_descuento", clear_on_submit=True):
            empleado_sel = st.selectbox(
                "Empleado",
                options=opciones_emp,
                index=None,
                placeholder="Escribí nombre, apellido o legajo para buscar...",
            )
            tipo = st.selectbox("Tipo de descuento", options=TIPOS_DESCUENTO, index=0)

            col_f, col_m, col_c = st.columns([2, 2, 1])
            with col_f:
                fecha = st.date_input("Fecha del descuento", value=date.today())
            with col_m:
                monto = st.number_input("Monto total ($)", min_value=1, step=500, value=None,
                                        placeholder="Ej: 15000")
            with col_c:
                cuotas = st.number_input("Cuotas", min_value=1, max_value=60, step=1, value=1,
                                         help="Cantidad de cuotas mensuales. El monto total se divide entre ellas.")
            motivo = st.text_area("Motivo", max_chars=300,
                                   placeholder="Opcional — descripción del descuento", height=90)
            submitted = st.form_submit_button("Registrar descuento")

        if submitted:
            if not empleado_sel:
                st.error("Seleccioná un empleado para continuar.")
            elif not monto:
                st.error("Ingresá un monto mayor a cero.")
            elif int(monto) < int(cuotas):
                st.error("El monto no alcanza para esa cantidad de cuotas.")
            else:
                r = opciones_map.get(empleado_sel)
                if r is None:
                    st.error("No se encontró el empleado. Intentá de nuevo.")
                else:
                    try:
                        n = int(cuotas)
                        total = int(monto)
                        if n == 1:
                            _guardar(r["legajo"], r["apenom"], r["empleador"], tipo, fecha, total, motivo)
                        else:
                            grupo_id = str(uuid.uuid4())
                            for i, m in enumerate(_split_cuotas(total, n)):
                                _guardar(
                                    r["legajo"], r["apenom"], r["empleador"], tipo,
                                    fecha + relativedelta(months=i), m, motivo,
                                    grupo_id=grupo_id, cuota_numero=i + 1,
                                    cuotas_total=n, monto_total=total,
                                )
                        monto_fmt = f"$ {total:,.0f}".replace(",",".")
                        detalle = f"en {n} cuotas" if n > 1 else "en 1 pago"
                        st.success(f"✓ Descuento registrado — **{r['apenom']}** · {tipo} · {fecha.strftime('%d/%m/%Y')} · **{monto_fmt}** {detalle}")
                        st.cache_data.clear()
                    except Exception:
                        st.error("No se pudo registrar el descuento. Intentá de nuevo.")

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
            <div class="kpi-label">Descuentos en {mes_actual}</div>
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
            fec_ult = pd.to_datetime(ult["fecha_descuento"]).strftime("%d/%m/%Y")
            monto_ult = f"$ {int(ult['monto']):,.0f}".replace(",",".")
            colors = COLORES_TIPO.get(ult["tipo_descuento"], "#f9f9f9:#666666").split(":")
            st.markdown(f"""
            <p class="section-label" style="margin-top:1rem">Último registrado</p>
            <div class="last-rec">
              <div class="last-rec-name">{ult['apenom']}</div>
              <div class="last-rec-detail">{fec_ult} &nbsp;·&nbsp; {monto_ult}</div>
              <span class="tipo-badge" style="background:{colors[0]};color:{colors[1]}">{ult['tipo_descuento']}</span>
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
empleadores_disp = sorted(df_emp["empleador"].dropna().unique())
col_emp, col_d, col_h, col_tip = st.columns([2, 2, 2, 2], gap="medium")
with col_emp:
    empleador_sel = st.selectbox("Empleador", options=empleadores_disp, index=0, key="empleador_d")
with col_d:
    desde = st.date_input("Desde", value=hoy.replace(day=1), key="desde_d")
with col_h:
    hasta = st.date_input("Hasta", value=hoy, key="hasta_d")
with col_tip:
    tipos_filtro = st.multiselect(
        "Filtrar por tipo",
        options=TIPOS_FILTRO,
        placeholder="Todos los tipos",
        key="tipos_filtro",
    )

try:
    df_desc = _leer(desde, hasta)
    df_adel = _leer_adelantos(desde, hasta)
    df_desc["_tabla"] = TABLA
    df_adel["_tabla"] = "adelantos"
    df_reg = pd.concat([df_desc, df_adel], ignore_index=True).sort_values(
        "fecha_descuento", ascending=False
    ).reset_index(drop=True)
except Exception:
    st.error("No se pudieron cargar los registros. Intentá de nuevo.")
    st.stop()

df_reg = df_reg[df_reg["empleador"] == empleador_sel]

if tipos_filtro:
    df_reg = df_reg[df_reg["tipo_descuento"].isin(tipos_filtro)]

if df_reg.empty:
    st.info("No hay descuentos registrados para el período y filtros seleccionados.")
else:
    total_reg = int(df_reg["monto"].sum())
    total_fmt = f"$ {total_reg:,.0f}".replace(",",".")
    st.markdown(f"""
    <div class="download-meta">
      <span class="pill"><span>{len(df_reg)}</span> registros</span>
      <span class="pill">Total <span>{total_fmt}</span></span>
    </div>
    """, unsafe_allow_html=True)

    df_vista = df_reg.copy()
    df_vista["Cuota"] = df_vista.apply(
        lambda r: f"{int(r['cuota_numero'])}/{int(r['cuotas_total'])}" if int(r["cuotas_total"]) > 1 else "—",
        axis=1,
    )
    df_display = df_vista[[
        "legajo","apenom","empleador","tipo_descuento","fecha_descuento","Cuota","monto","motivo",
    ]].rename(columns={
        "legajo":"Legajo","apenom":"Nombre","empleador":"Empleador",
        "tipo_descuento":"Tipo","fecha_descuento":"Fecha",
        "monto":"Monto ($)","motivo":"Motivo",
    })
    df_display["Monto ($)"] = df_display["Monto ($)"].apply(lambda x: f"$ {int(x):,.0f}".replace(",","."))
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    txt = _generar_txt(df_reg)
    st.download_button(
        "⬇  Descargar TXT",
        data=txt.encode("utf-8"),
        file_name=f"{slug_empleador(empleador_sel)}_{desde.strftime('%d-%m-%Y')}_a_{hasta.strftime('%d-%m-%Y')}.txt",
        mime="text/plain",
    )

# ─── Sección eliminar ─────────────────────────────────────────
if can_edit("descuentos"):
    st.divider()
    if st.session_state.pop("deleted_ok_d", False):
        st.success("Registro eliminado correctamente.")
    with st.expander("Eliminar un registro"):
        if df_reg.empty:
            st.info("No hay registros en el período seleccionado para eliminar.")
        else:
            opciones = {}
            for _, row in df_reg.iterrows():
                ct = int(row.get("cuotas_total") or 1)
                cuota_lbl = f"  —  Cuota {int(row['cuota_numero'])}/{ct}" if ct > 1 else ""
                etiqueta = (
                    f"{row['fecha_descuento'].strftime('%d/%m/%Y')}  —  {row['apenom']}  —  "
                    f"{row['tipo_descuento']}  —  $ {int(row['monto']):,}".replace(",", ".")
                    + cuota_lbl
                )
                opciones[etiqueta] = (row["id"], row["_tabla"], row.get("grupo_id"), ct)
            sel_label = st.selectbox("Seleccionar registro", list(opciones.keys()), key="sel_borrar_d")
            sel_id, sel_tabla, sel_grupo, sel_ct = opciones[sel_label]

            st.markdown('<div class="delete-btn-wrap">', unsafe_allow_html=True)
            if st.button("Eliminar registro", key="btn_del_d"):
                st.session_state["del_id_d"] = sel_id
                st.session_state["del_tabla_d"] = sel_tabla
                st.session_state["del_grupo_d"] = sel_grupo
                st.session_state["del_ct_d"] = sel_ct
                st.session_state["del_label_d"] = sel_label
            st.markdown("</div>", unsafe_allow_html=True)

            if "del_id_d" in st.session_state:
                lbl = st.session_state.get("del_label_d", "este registro")
                es_grupo = bool(st.session_state.get("del_grupo_d")) and int(st.session_state.get("del_ct_d", 1)) > 1
                if es_grupo:
                    st.warning(
                        f"**{lbl}** pertenece a un plan de {int(st.session_state['del_ct_d'])} cuotas. "
                        "Se eliminarán **todas las cuotas** del descuento. Esta acción no se puede deshacer."
                    )
                else:
                    st.warning(f"¿Eliminar **{lbl}**? Esta acción no se puede deshacer.")
                c1, c2 = st.columns([1, 1])
                with c1:
                    if st.button("Sí, eliminar", key="btn_confirm_d"):
                        if es_grupo:
                            _eliminar_grupo(st.session_state["del_grupo_d"])
                        else:
                            _eliminar(st.session_state["del_id_d"], st.session_state["del_tabla_d"])
                        for _k in ("del_id_d", "del_tabla_d", "del_grupo_d", "del_ct_d", "del_label_d"):
                            st.session_state.pop(_k, None)
                        st.session_state["deleted_ok_d"] = True
                        st.rerun()
                with c2:
                    if st.button("Cancelar", key="btn_cancel_d"):
                        for _k in ("del_id_d", "del_tabla_d", "del_grupo_d", "del_ct_d", "del_label_d"):
                            st.session_state.pop(_k, None)
                        st.rerun()
