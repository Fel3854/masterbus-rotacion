"""Vista: Minutas de Reunión — seguimiento de temas y acciones de RRHH."""

import html
import os
import sys
from datetime import date

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from auth import can_edit, current_user  # noqa: E402
from utils import inyectar_css_base, get_supabase  # noqa: E402
import minutas as mn  # noqa: E402

_esc = html.escape


# ─── CSS ──────────────────────────────────────────────────────
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
    font-family: 'Fira Code', monospace; font-size: 2.3rem; font-weight: 700;
    line-height: 1; color: var(--card-color, #333);
}

.estado-chip {
    display: inline-block; font-size: 0.76rem; font-weight: 800;
    padding: 3px 12px; border-radius: 12px; margin-left: 8px; vertical-align: middle;
    background: var(--chip-bg, #eee); color: var(--chip-fg, #333);
    border: 1.5px solid var(--chip-fg, #ccc);
}
.venc-badge {
    display: inline-block; background: #B91C1C; color: #fff; font-size: 0.66rem;
    font-weight: 700; padding: 2px 9px; border-radius: 12px; margin-left: 6px;
    vertical-align: middle; text-transform: uppercase; letter-spacing: 0.5px;
}
.minuta-head { border-left: 4px solid var(--accent, #ccc); padding-left: 12px; }
.minuta-top { display: flex; align-items: center; flex-wrap: wrap; gap: 2px; }
.minuta-tema { font-size: 1.02rem; font-weight: 700; color: #1a1a1a; }
.minuta-meta { font-size: 0.82rem; color: #666; margin-top: 4px; }
.minuta-desc { font-size: 0.88rem; color: #444; margin-top: 8px; white-space: pre-wrap; }
</style>
""", unsafe_allow_html=True)


# ─── Helpers Supabase (caché por-función, como en Seguimiento) ─
@st.cache_data(ttl=300, show_spinner=False)
def _leer() -> pd.DataFrame:
    """Todas las minutas. La tabla entera entra en memoria, así el caché se
    invalida con `_leer.clear()` sin volar el caché de la API de empleados."""
    resp = (
        get_supabase().table(mn.TABLA)
        .select(",".join(mn.columnas_db()))
        .order("fecha_limite", desc=False)
        .execute()
    )
    if not resp.data:
        return pd.DataFrame(columns=mn.columnas_db())
    df = pd.DataFrame(resp.data)
    for col in ("fecha", "fecha_limite"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
    return df


def _guardar(payload: dict) -> None:
    get_supabase().table(mn.TABLA).insert(payload).execute()


def _actualizar(record_id: str, cambios: dict) -> None:
    get_supabase().table(mn.TABLA).update(cambios).eq("id", record_id).execute()


def _eliminar(record_id: str) -> None:
    get_supabase().table(mn.TABLA).delete().eq("id", record_id).execute()


# ─── Utilidades de formato ────────────────────────────────────
# pd.NaT (fecha vacía) es instancia de date, así que NO alcanza con isinstance:
# hay que pasar por mn.to_date, o NaT.strftime() revienta.
def _fmt(d) -> str:
    f = mn.to_date(d)
    return f.strftime("%d/%m/%Y") if f else "—"


def _as_date(d, default=None):
    return mn.to_date(d) or default


# ─── Callbacks de edición ─────────────────────────────────────
def _cambiar_estado(rid: str) -> None:
    nuevo = st.session_state.get(f"est_{rid}")
    if not nuevo:
        return
    try:
        _actualizar(rid, {"estado": nuevo})
        _leer.clear()
        st.toast(f"Estado → {nuevo}", icon="✅")
    except Exception as e:  # noqa: BLE001
        st.toast(f"No se pudo actualizar: {e}", icon="⚠️")


# ─── Render de una minuta ─────────────────────────────────────
def _render_item(fila, puede_editar: bool) -> None:
    rid = str(fila["id"])
    estado = fila["estado"] if fila.get("estado") in mn.ESTADOS else mn.ESTADO_PENDIENTE
    venc = bool(fila.get("vencida"))
    accent = mn.COLOR_VENCIDA if venc else mn.color_estado(estado)

    fecha = mn.to_date(fila.get("fecha"))
    fecha_limite = mn.to_date(fila.get("fecha_limite"))
    tema = _esc(str(fila.get("tema") or "").strip() or "(sin tema)")
    resp = _esc(str(fila.get("responsable") or "").strip() or "—")
    desc = str(fila.get("descripcion") or "").strip()
    lim_txt = _fmt(fecha_limite) if fecha_limite else "sin fecha límite"

    chip = (f'<span class="estado-chip" '
            f'style="--chip-bg:{mn.color_estado_bg(estado)}; --chip-fg:{mn.color_estado(estado)};">'
            f'{estado}</span>')
    badge = '<span class="venc-badge">Vencida</span>' if venc else ""
    desc_html = f'<div class="minuta-desc">{_esc(desc)}</div>' if desc else ""

    with st.container(border=True):
        st.markdown(f"""
        <div class="minuta-head" style="--accent:{accent};">
          <div class="minuta-top"><span class="minuta-tema">{tema}</span>{chip}{badge}</div>
          <div class="minuta-meta">Reunión: {_fmt(fecha)} &nbsp;·&nbsp; Responsable: {resp} &nbsp;·&nbsp; Límite: {lim_txt}</div>
          {desc_html}
        </div>
        """, unsafe_allow_html=True)

        if not puede_editar:
            return

        c_est, _ = st.columns([1.3, 3], vertical_alignment="center")
        with c_est:
            st.selectbox(
                "Estado", mn.ESTADOS, index=mn.ESTADOS.index(estado),
                key=f"est_{rid}", on_change=_cambiar_estado, args=(rid,),
                label_visibility="collapsed",
            )

        with st.expander("Editar detalle / eliminar"):
            with st.form(f"edit_{rid}"):
                e1, e2 = st.columns(2)
                with e1:
                    e_fecha = st.date_input("Fecha de la reunión",
                                            value=_as_date(fecha, date.today()),
                                            format="DD/MM/YYYY", key=f"ef_{rid}")
                    e_resp = st.text_input("Responsable",
                                           value=str(fila.get("responsable") or ""),
                                           key=f"er_{rid}")
                with e2:
                    e_lim = st.date_input("Fecha límite (opcional)",
                                          value=_as_date(fecha_limite),
                                          format="DD/MM/YYYY", key=f"el_{rid}")
                e_tema = st.text_input("Tema o acción *",
                                       value=str(fila.get("tema") or ""), key=f"et_{rid}")
                e_desc = st.text_area("Descripción / detalle",
                                      value=str(fila.get("descripcion") or ""),
                                      key=f"ed_{rid}")
                guardar_edit = st.form_submit_button("Guardar cambios")

            if guardar_edit:
                if not e_tema.strip():
                    st.error("El **tema o acción** no puede quedar vacío.")
                else:
                    try:
                        _actualizar(rid, {
                            "fecha": e_fecha.isoformat() if e_fecha else None,
                            "tema": e_tema.strip(),
                            "descripcion": (e_desc.strip() or None),
                            "responsable": (e_resp.strip() or None),
                            "fecha_limite": e_lim.isoformat() if e_lim else None,
                        })
                        _leer.clear()
                        st.toast("Minuta actualizada.", icon="✅")
                        st.rerun()
                    except Exception as e:  # noqa: BLE001
                        st.error(f"No se pudo guardar: {e}")

            st.divider()
            del_key = f"confirm_del_{rid}"
            if st.session_state.get(del_key):
                st.warning("¿Eliminar esta minuta? No se puede deshacer.")
                d1, d2 = st.columns(2)
                if d1.button("Sí, eliminar", key=f"yes_{rid}", use_container_width=True):
                    try:
                        _eliminar(rid)
                        _leer.clear()
                        st.session_state.pop(del_key, None)
                        st.toast("Minuta eliminada.", icon="🗑️")
                        st.rerun()
                    except Exception as e:  # noqa: BLE001
                        st.error(f"No se pudo eliminar: {e}")
                if d2.button("Cancelar", key=f"no_{rid}", use_container_width=True):
                    st.session_state.pop(del_key, None)
                    st.rerun()
            else:
                if st.button("🗑 Eliminar minuta", key=f"del_{rid}"):
                    st.session_state[del_key] = True
                    st.rerun()


# ─── Formulario de alta ───────────────────────────────────────
def _render_form() -> None:
    # Sin clear_on_submit: si la validación falla (tema vacío) no queremos borrar
    # lo que el usuario ya escribió. Tras un alta exitosa, el st.rerun() de abajo
    # re-renderiza el form limpio igual (los inputs no tienen key, así que se
    # resetean a su valor por defecto en cada corrida).
    with st.form("form_minuta_nueva"):
        a, b = st.columns(2)
        with a:
            f_fecha = st.date_input("Fecha de la reunión", value=date.today(),
                                    format="DD/MM/YYYY")
            f_resp = st.text_input("Responsable",
                                   placeholder="Quién lo tiene a cargo")
        with b:
            f_estado = st.selectbox("Estado", mn.ESTADOS, index=0)
            f_lim = st.date_input("Fecha límite (opcional)", value=None,
                                  format="DD/MM/YYYY")
        f_tema = st.text_input("Tema o acción *",
                               placeholder="Título corto del tema o acción")
        f_desc = st.text_area("Descripción / detalle",
                              placeholder="Describí el tema o la acción a seguir")
        enviado = st.form_submit_button("Guardar minuta", use_container_width=True)

    if enviado:
        if not f_tema.strip():
            st.error("El **tema o acción** es obligatorio.")
            return
        payload = mn.construir_payload(
            fecha=f_fecha, tema=f_tema, descripcion=f_desc, responsable=f_resp,
            fecha_limite=f_lim, estado=f_estado,
            registrado_por=(current_user() or {}).get("name", ""),
        )
        try:
            _guardar(payload)
            _leer.clear()
            st.toast("Minuta guardada.", icon="✅")
            st.rerun()
        except Exception as e:  # noqa: BLE001
            st.error(f"No se pudo guardar la minuta: {e}")


# ─── Listado ──────────────────────────────────────────────────
def _render_lista(df, puede_editar: bool) -> None:
    if df.empty:
        st.info("Todavía no hay minutas cargadas.")
        return

    f1, f2, f3 = st.columns([2, 2, 1.4], vertical_alignment="bottom")
    with f1:
        estado_sel = st.selectbox("Estado", ["Todos", *mn.ESTADOS, "Vencidas"],
                                  key="filtro_estado_mn")
    with f2:
        responsables = sorted(
            {str(r).strip() for r in df["responsable"].dropna() if str(r).strip()}
        )
        opciones_resp = ["Todos", *responsables]
        # Si el responsable filtrado dejó de existir (se borró su última minuta),
        # el valor guardado ya no está en las opciones y el selectbox reventaría.
        if st.session_state.get("filtro_resp_mn") not in opciones_resp:
            st.session_state["filtro_resp_mn"] = "Todos"
        resp_sel = st.selectbox("Responsable", opciones_resp, key="filtro_resp_mn")
    with f3:
        st.download_button(
            "Exportar Excel", data=mn.exportar_excel(df),
            file_name=f"minutas_{date.today():%Y%m%d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    d = df
    if estado_sel == "Vencidas":
        d = d[d["vencida"]]
    elif estado_sel != "Todos":
        d = d[d["estado"] == estado_sel]
    if resp_sel != "Todos":
        d = d[d["responsable"] == resp_sel]

    d = mn.ordenar(d)
    st.caption(f"{len(d)} minuta{'s' if len(d) != 1 else ''}")
    for _, fila in d.iterrows():
        _render_item(fila, puede_editar)


# ══════════════════════════════════════════════════════════════
# Render principal
# ══════════════════════════════════════════════════════════════
st.markdown("""
<div class="page-header">
  <div class="bar"></div>
  <h1>Minutas de Reunión</h1>
</div>
""", unsafe_allow_html=True)
st.caption("Seguimiento de temas y acciones de las reuniones de RRHH.")

c_btn, c_cap = st.columns([1.5, 6], vertical_alignment="center")
with c_btn:
    if st.button("↺  Actualizar"):
        _leer.clear()
        st.rerun()

try:
    df = mn.marcar_vencidas(_leer())
except Exception:  # noqa: BLE001
    st.error("No se pudieron cargar las minutas. Revisá la conexión con la base.")
    if st.button("Reintentar"):
        _leer.clear()
        st.rerun()
    st.stop()

PUEDE_EDITAR = can_edit("minutas")

# ── Banner: estado general ────────────────────────────────────
r = mn.resumen_estado(df)
st.markdown('<div class="section-header"><div class="bar"></div><span>Estado general</span></div>',
            unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
tarjetas = [
    (k1, "Pendientes", r["por_estado"][mn.ESTADO_PENDIENTE], mn.COLOR_PENDIENTE, mn.COLOR_PENDIENTE_BG),
    (k2, "En curso",   r["por_estado"][mn.ESTADO_EN_CURSO],  mn.COLOR_EN_CURSO,  mn.COLOR_EN_CURSO_BG),
    (k3, "Completas",  r["por_estado"][mn.ESTADO_COMPLETA],  mn.COLOR_COMPLETA,  mn.COLOR_COMPLETA_BG),
    (k4, "Vencidas",   r["vencidas"],                        mn.COLOR_VENCIDA,   mn.COLOR_VENCIDA_BG),
]
for col, label, count, color, bg in tarjetas:
    with col:
        st.markdown(f"""
        <div class="kpi-card" style="--card-color:{color}; --card-bg:{bg};">
          <div class="kpi-label">{label}</div>
          <div class="kpi-value">{count}</div>
        </div>
        """, unsafe_allow_html=True)

if r["total"]:
    pct = 0.0 if pd.isna(r["pct_completas"]) else r["pct_completas"] / 100.0
    st.progress(
        pct,
        text=f"{r['por_estado'][mn.ESTADO_COMPLETA]} de {r['total']} completas "
             f"({pct * 100:.0f}%)",
    )
if r["vencidas"]:
    n = r["vencidas"]
    st.warning(
        f"⚠️ **{n} minuta{'s' if n != 1 else ''} vencida{'s' if n != 1 else ''}** "
        "sin completar — filtralas con «Vencidas» en la lista de abajo."
    )

# ── Alta (solo con permiso) ───────────────────────────────────
if PUEDE_EDITAR:
    with st.expander("➕  Cargar nueva minuta"):
        _render_form()
else:
    st.caption("Tenés acceso de solo lectura: podés ver las minutas pero no editarlas.")

# ── Listado ───────────────────────────────────────────────────
st.markdown('<div class="section-header"><div class="bar"></div><span>Minutas cargadas</span></div>',
            unsafe_allow_html=True)
_render_lista(df, PUEDE_EDITAR)
