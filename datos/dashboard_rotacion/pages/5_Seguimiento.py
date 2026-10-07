"""Vista: Seguimiento del personal ingresante — Grupo Master

Dos cuestionarios, que se eligen arriba de todo:
  · Conductores       → entrevista del 2° mes (`seguimiento.py`).
  · Resto del personal → encuesta de efectivización (`seguimiento_general.py`).
Cada uno tiene su tabla, su formulario y sus indicadores; no comparten estado.
"""

import html
import os
import sys
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import (cargar_datos, cargar_empleados_activos, chart_base,  # noqa: E402
                   delta_html, get_supabase, leer_paginado,
                   COLOR_PRIMARY, COLOR_SECONDARY)
from auth import can_edit, current_user  # noqa: E402
import auditoria
import seguimiento as sg  # noqa: E402
import seguimiento_general as sgen  # noqa: E402

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

/* ── Píldoras de radio (escalas 1-4) ── */
div[data-testid="stRadio"] > div {{
    gap: 0.4rem;
    flex-wrap: wrap;
}}
div[data-testid="stRadio"] label {{
    background: #fff;
    border: 1.5px solid #e0e0e0;
    border-radius: 20px;
    padding: 0.3rem 0.9rem;
    font-size: 0.82rem;
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
div[data-testid="stRadio"] label:has(input:checked) p {{ color: #fff !important; }}

/* ── Enunciado de cada pregunta ── */
.preg {{
    font-size: 0.9rem; font-weight: 500; color: #333;
    margin: 0.9rem 0 0.35rem;
}}
.preg .num {{
    font-family: 'Fira Code', monospace; font-weight: 600;
    color: {COLOR_PRIMARY}; margin-right: 6px;
}}
/* Aclaración entre paréntesis que trae el papel al lado de la pregunta. */
.preg .ayuda {{ color: #888 !important; font-weight: 400; }}
/* Pregunta que quedó sin responder en el último intento de guardar.
   El borde y el fondo son para encontrarla scrolleando; la etiqueta es para
   que se entienda sin depender del color. */
.preg.falta {{
    border-left: 3px solid #D12F19;
    background: #FDF0EE;
    border-radius: 0 6px 6px 0;
    padding: 0.4rem 0.6rem;
    margin-left: -0.6rem;
}}
.preg.falta .num {{ color: #D12F19; }}
.preg .falta-tag {{
    display: inline-block;
    background: #D12F19; color: #fff !important;
    font-size: 0.62rem; font-weight: 700; letter-spacing: 0.6px;
    text-transform: uppercase;
    border-radius: 4px; padding: 0.1rem 0.4rem;
    margin-left: 8px; vertical-align: middle;
}}

/* ── Encabezado de sección ── */
.sec-head {{
    display: flex; align-items: center; gap: 8px;
    margin: 1.6rem 0 0.2rem;
}}
.sec-head .bar {{
    width: 3px; height: 18px; background: {COLOR_PRIMARY}; border-radius: 2px;
}}
.sec-head span {{ font-weight: 700; font-size: 0.95rem; color: #333; }}

/* ── Tarjetas KPI del tab Indicadores ── */
.kpi6 {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 14px; margin: 0.5rem 0 1.2rem; }}
.kpi6-card {{
    background: #FFFFFF; border: 1px solid #CCCCCC; border-radius: 10px;
    padding: 20px 16px 16px; box-shadow: 0 1px 5px rgba(0,0,0,0.04);
}}
.kpi6-label {{
    font-size: 0.72rem; font-weight: 700; color: #8C8987;
    text-transform: uppercase; letter-spacing: 0.09em; margin-bottom: 10px;
}}
.kpi6-value {{
    font-size: 2.1rem; font-weight: 800; color: #333333; line-height: 1;
    letter-spacing: -0.025em; font-family: 'Fira Code', monospace;
}}
.kpi6-sub {{ font-size: 0.75rem; color: #8C8987; margin-top: 8px; }}
@media (max-width: 1200px) {{ .kpi6 {{ grid-template-columns: repeat(3, 1fr); }} }}

/* ── Fila de alerta ── */
.alert-row {{
    background: #fff; border-left: 3px solid #D12F19; border-radius: 6px;
    padding: 10px 14px; margin-bottom: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}}
.alert-row.amber {{ border-left-color: #B45309; }}
.alert-name {{ font-weight: 600; font-size: 0.9rem; color: #1a1a1a; }}
.alert-meta {{ font-size: 0.78rem; color: #888; margin-top: 0.15rem; }}
.alert-quote {{
    font-size: 0.82rem; color: #444; margin-top: 0.4rem;
    padding-left: 10px; border-left: 2px solid #e0e0e0; font-style: italic;
}}

/* ── Detalle de una entrevista ── */
.det-head {{
    background: #fff; border: 1px solid #CCCCCC; border-top: 3px solid {COLOR_PRIMARY};
    border-radius: 10px; padding: 18px 20px; margin-bottom: 14px;
}}
.det-name {{ font-size: 1.15rem; font-weight: 700; color: #1a1a1a; }}
.det-meta {{ font-size: 0.83rem; color: #888; margin-top: 0.25rem; }}
.det-chips {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }}
.det-chip {{
    font-size: 0.78rem; font-weight: 600; padding: 4px 12px; border-radius: 14px;
}}
.det-sec {{
    font-size: 0.7rem; font-weight: 700; color: #888; letter-spacing: 1.2px;
    margin: 1.4rem 0 0.5rem; padding-bottom: 0.35rem; border-bottom: 1px solid #e0e0e0;
}}
.det-item {{
    display: flex; align-items: flex-start; gap: 12px; padding: 8px 0;
    border-bottom: 1px solid #f0f0f0;
}}
.det-num {{
    font-family: 'Fira Code', monospace; font-size: 0.8rem; font-weight: 600;
    color: {COLOR_PRIMARY}; min-width: 22px; padding-top: 2px;
}}
.det-q {{ flex: 1; font-size: 0.86rem; color: #444; line-height: 1.4; }}
.det-a {{
    font-size: 0.8rem; font-weight: 600; padding: 3px 12px; border-radius: 13px;
    white-space: nowrap; align-self: flex-start;
}}
.det-txt {{
    font-size: 0.82rem; color: #555; font-style: italic; margin-top: 0.35rem;
    padding-left: 10px; border-left: 2px solid #e0e0e0;
}}
.det-obs {{
    font-size: 0.82rem; color: #555; margin-top: 0.35rem;
    padding-left: 10px; border-left: 2px solid {COLOR_PRIMARY}66;
}}
.det-obs span {{
    font-weight: 700; color: {COLOR_PRIMARY}; font-size: 0.72rem;
    text-transform: uppercase; letter-spacing: 0.03em; margin-right: 4px;
}}
</style>
""", unsafe_allow_html=True)


# ─── Helpers Supabase ─────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def _leer() -> pd.DataFrame:
    """Todas las entrevistas. Sin parámetros: la tabla entera entra en memoria
    (~85 filas/año), así el caché se invalida con _leer.clear() y nunca hace
    falta el st.cache_data.clear() global (que volaría el caché de la API)."""
    # Paginado: la API entrega como mucho 1000 filas por consulta, sin avisar.
    datos = leer_paginado(lambda: (
        get_supabase().table(sg.TABLA)
        .select(",".join(sg.columnas_db()), count="exact")
        .order("fecha_entrevista", desc=True)
        .order("id")              # desempate: la paginación necesita un orden único
    ))
    if not datos:
        return pd.DataFrame(columns=sg.columnas_db())
    df = pd.DataFrame(datos)
    for col in ("fecha_entrevista", "fecha_ingreso", "fecha_proximo_seguimiento"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
    return df


def _guardar(payload: dict) -> None:
    get_supabase().table(sg.TABLA).insert(payload).execute()
    # Sólo la cabecera: las respuestas del conductor son confidenciales y no
    # pueden filtrarse al log (ver el docstring de auditoria.py).
    auditoria.registrar(
        "seguimiento", "alta",
        f"{payload.get('apenom')} (leg. {payload.get('legajo')}) · "
        f"entrevista del {payload.get('fecha_entrevista')}",
        datos={"legajo": payload.get("legajo"), "base": payload.get("base")},
    )


def _eliminar(record_id: str, detalle: str = "") -> None:
    get_supabase().table(sg.TABLA).delete().eq("id", record_id).execute()
    auditoria.registrar("seguimiento", "baja", detalle, registro_id=record_id)


def _auditar_apertura(fila) -> None:
    """Registra que alguien abrió la vista ampliada de una entrevista.

    Se llama al ABRIR (cuando se setea `ver_id_sg`), no al renderizar: la vista
    se repinta en cada rerun y el log se llenaría de duplicados.

    Sólo cuenta como lectura sensible si el usuario tiene permiso para ver los
    textuales; sin ese permiso la vista muestra puntajes, que ve cualquiera.
    """
    if not PUEDE_EDITAR:
        return
    fecha = fila.get("fecha_entrevista")
    fecha_txt = fecha.strftime("%d/%m/%Y") if pd.notna(fecha) else "—"
    auditoria.registrar(
        "seguimiento", "lectura",
        f"Abrió la entrevista de {fila.get('apenom')} (leg. {fila.get('legajo')}) "
        f"del {fecha_txt} — incluye respuestas textuales",
        registro_id=fila.get("id"),
    )


# ─── Utilidades de render ─────────────────────────────────────
def _sec_head(texto: str) -> None:
    st.markdown(
        f'<div class="sec-head"><div class="bar"></div><span>{texto}</span></div>',
        unsafe_allow_html=True,
    )


def _preg_html(num, texto, falta=False):
    """Enunciado de una pregunta. Con `falta=True` queda marcado en rojo.

    Cada enunciado se dibuja dentro de un st.empty() para poder repintarlo
    después de validar, en la misma pasada: así el error de abajo deja de ser
    una lista de números que hay que ir a buscar contando preguntas.
    """
    clase = "preg falta" if falta else "preg"
    tag = '<span class="falta-tag">Falta</span>' if falta else ""
    # Sin número cuando el enunciado no es una pregunta numerada del papel.
    numero = f'<span class="num">{num}.</span>' if num not in (None, "") else ""
    return f'<div class="{clase}">{numero}{texto}{tag}</div>'


# cod → (número o letra, enunciado), para repintar sin volver a recorrer el catálogo.
MAPA_PREG: dict = {}
for _p in sg.PREGUNTAS:
    MAPA_PREG[_p["cod"]] = (_p["n"], _p["texto"])
for _a in sg.AUTOEVAL:
    MAPA_PREG[_a["cod"]] = (_a["letra"], _a["texto"])


def _fmt(valor, sufijo="", decimales=0):
    if valor is None or pd.isna(valor):
        return "—"
    return f"{valor:,.{decimales}f}{sufijo}".replace(",", ".")


def _bloques_html(secciones):
    """Renderiza una lista de (titulo, items) a HTML."""
    out = []
    for titulo, items in secciones:
        out.append(f'<div class="det-sec">{titulo}</div>')
        for it in items:
            resp = ""
            if it["respuesta"]:
                resp = (f'<div class="det-a" style="background:{it["color"]}18;'
                        f'color:{it["color"]};border:1px solid {it["color"]}40;">'
                        f'{it["respuesta"]}</div>')
            txt = f'<div class="det-txt">"{it["textual"]}"</div>' if it["textual"] else ""
            obs = (f'<div class="det-obs"><span>Obs.</span> {it["observacion"]}</div>'
                   if it.get("observacion") else "")
            num = f'<div class="det-num">{it["etiqueta"]}.</div>' if it["etiqueta"] else ""
            out.append(f'<div class="det-item">{num}'
                       f'<div class="det-q">{it["pregunta"]}{txt}{obs}</div>{resp}</div>')
    return "".join(out)


def _render_detalle(fila, incluir_textos):
    """Vista ampliada de una entrevista: ocupa el ancho completo de la pantalla."""
    fecha_e = fila["fecha_entrevista"].strftime("%d/%m/%Y") \
        if pd.notna(fila["fecha_entrevista"]) else "—"
    fecha_i = fila["fecha_ingreso"].strftime("%d/%m/%Y") \
        if pd.notna(fila.get("fecha_ingreso")) else "—"
    prox = fila.get("fecha_proximo_seguimiento")
    prox_txt = f' · Próximo seguimiento: {prox.strftime("%d/%m/%Y")}' if pd.notna(prox) else ""

    _, color_ind = sg.banda(fila["indice_general"])
    _, color_aut = sg.banda(fila["indice_autopercepcion"])
    etiqueta_ind, _ = sg.banda(fila["indice_general"])
    chips = (
        f'<span class="det-chip" style="background:{color_ind}18;color:{color_ind};'
        f'border:1px solid {color_ind}40;">Índice {_fmt(fila["indice_general"], "", 1)}'
        f' · {etiqueta_ind}</span>'
        f'<span class="det-chip" style="background:{color_aut}18;color:{color_aut};'
        f'border:1px solid {color_aut}40;">Autopercepción '
        f'{_fmt(fila["indice_autopercepcion"], "", 1)}</span>'
    )
    if fila["nivel_alerta"]:
        c = "#D12F19" if fila["nivel_alerta"] == "Roja" else "#B45309"
        chips += (f'<span class="det-chip" style="background:{c}18;color:{c};'
                  f'border:1px solid {c}40;">Alerta {fila["nivel_alerta"]}</span>')

    st.markdown(f"""
    <div class="det-head">
      <div class="det-name">{fila["apenom"]}</div>
      <div class="det-meta">
        Legajo {fila["legajo"]} · {fila["base"] or "Sin base"} · {fila["empleador"]}<br>
        Ingreso: {fecha_i} · Entrevista: {fecha_e} · Entrevistador: {fila["entrevistador"]}{prox_txt}
      </div>
      <div class="det-chips">{chips}</div>
    </div>
    """, unsafe_allow_html=True)

    if fila["motivos_alerta"]:
        st.warning("**Motivos de alerta** — " + " · ".join(fila["motivos_alerta"]))

    secciones = sg.detalle_entrevista(fila, incluir_textos=incluir_textos)
    preguntas = [x for x in secciones if x[0][0] in "123456"]
    cierre = [x for x in secciones if x[0][0] in "78"]

    col_izq, col_der = st.columns([3, 2], gap="large")
    with col_izq:
        st.markdown(_bloques_html(preguntas), unsafe_allow_html=True)
    with col_der:
        st.markdown(_bloques_html(cierre), unsafe_allow_html=True)
        if not incluir_textos:
            st.caption(
                "Las respuestas textuales y la conclusión son confidenciales: "
                "solo las ve quien tiene permiso de carga en esta sección.")


def _kpi_card(label, value, sub="", color=COLOR_PRIMARY, delta=""):
    return (
        f'<div class="kpi6-card" style="border-top:3px solid {color};">'
        f'<div class="kpi6-label">{label}</div>'
        f'<div class="kpi6-value">{value}</div>'
        f'<div class="kpi6-sub">{sub}</div>{delta}</div>'
    )


def _guardia_salida() -> None:
    """Avisa antes de recargar/cerrar la pestaña si el formulario tiene datos
    sin guardar.

    Es la red de contención de B0: recargar la página (Cmd-R, F5, entrar por URL)
    destruye `session_state` y con él 20 minutos de transcripción, sin ningún
    aviso. Streamlit no ejecuta scripts en `st.markdown`, así que la única vía es
    un `components.html` (iframe): desde ahí se instala un `beforeunload` sobre la
    ventana padre. No frena la navegación por el sidebar (es client-side y no
    dispara `beforeunload`); solo la recarga/cierre reales, que es justo cuando
    se pierde el trabajo.

    La detección de "sucio" se hace leyendo el DOM del form en el momento del
    aviso (radios marcados, text_area/text_input con contenido), así que no
    molesta con el form vacío ni después de guardar (el form se limpia por el
    bump del seed). Fecha (default hoy) y Entrevistador (prellenado) se ignoran a
    propósito: solos no son "trabajo perdido".
    """
    components.html(
        """
<script>
(function(){
  var p = window.parent, doc = p.document;
  // El form vive solo mientras existe el marcador (#sg-guard-marker). Todo se
  // ancla a él: en otra página el marcador no está y el aviso no dispara,
  // aunque esa página tenga su propio st.form.
  function elForm(){
    var m = doc.getElementById('sg-guard-marker');
    return m ? m.closest('[data-testid="stForm"]') : null;
  }
  function suciedad(form){
    if(!form) return false;
    if(form.querySelector('input[type=radio]:checked')) return true;
    var tas = form.querySelectorAll('textarea');
    for(var i=0;i<tas.length;i++){ if((tas[i].value||'').trim()) return true; }
    var ins = form.querySelectorAll('input');
    for(var j=0;j<ins.length;j++){
      var el = ins[j];
      if(el.type==='radio' || el.type==='checkbox') continue;
      var al = el.getAttribute('aria-label') || '';
      if(al==='Entrevistador' || /date/i.test(al)) continue;  // defaults, no cuentan
      if((el.value||'').trim()) return true;
    }
    return false;
  }
  // Marca en vivo cualquier interacción dentro del form (cubre el selectbox de
  // Conductor, que no deja su valor en input.value). Se liga una sola vez.
  if(!p.__sgListeners){
    p.__sgListeners = true;
    var marca = function(ev){
      var f = elForm();
      if(f && ev.target.closest && f.contains(ev.target)) p.__sgLive = true;
    };
    doc.addEventListener('input', marca, true);
    doc.addEventListener('change', marca, true);
  }
  p.__sgLive = false;   // se resetea en cada render; escribir lo re-arma
  // Se re-liga en cada render. El aviso solo dispara si el marcador está presente
  // (o sea, estás en esta pantalla) y el form tiene datos sin guardar.
  if(p.__sgUnload) p.removeEventListener('beforeunload', p.__sgUnload);
  p.__sgUnload = function(e){
    var f = elForm();
    if(f && (p.__sgLive || suciedad(f))){
      e.preventDefault(); e.returnValue = ''; return '';
    }
  };
  p.addEventListener('beforeunload', p.__sgUnload);
})();
</script>
        """,
        height=0,
    )


# ══════════════════════════════════════════════════════════════
# Cuestionario «Resto del personal» (no conductores)
# ══════════════════════════════════════════════════════════════
# Las mismas tres pestañas que conductores, con su propio catálogo
# (seguimiento_general.py) y su propia tabla. No comparte estado con el de
# conductores: todas sus keys de session_state llevan `sgg`.
CUEST_CONDUCTORES = "Conductores"
CUEST_GENERAL = "Resto del personal"
SUBTITULOS = {
    CUEST_CONDUCTORES: "Entrevista de seguimiento del 2° mes: registrá las respuestas "
                       "y medí la adaptación de cada conductor nuevo.",
    CUEST_GENERAL: "Encuesta de seguimiento del personal ingresante, previa a la "
                   "efectivización: registrá las respuestas, la evaluación del sector "
                   "y el resultado.",
}
FILTROS_GENERAL = ("desde_sgg", "hasta_sgg", "sector_sgg", "resultado_sgg")


def _txt(valor) -> str:
    """Un valor del padrón o de la base como texto; '' si viene vacío o NaN."""
    if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
        return ""
    return str(valor).strip()


def _esc(valor) -> str:
    """Texto que cargó una persona, listo para ir dentro de un HTML."""
    return html.escape(_txt(valor))


def _fecha_txt(valor) -> str:
    return valor.strftime("%d/%m/%Y") if pd.notna(valor) else "—"


@st.cache_data(ttl=300, show_spinner=False)
def _leer_general() -> pd.DataFrame:
    """Todas las entrevistas del personal no conductor (mismo criterio que `_leer`)."""
    datos = leer_paginado(lambda: (
        get_supabase().table(sgen.TABLA)
        .select(",".join(sgen.columnas_db()), count="exact")
        .order("fecha_entrevista", desc=True)
        .order("id")              # desempate: la paginación necesita un orden único
    ))
    if not datos:
        return pd.DataFrame(columns=sgen.columnas_db())
    df = pd.DataFrame(datos)
    for col in ("fecha_entrevista", "fecha_ingreso"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
    return df


def _guardar_general(payload: dict) -> None:
    get_supabase().table(sgen.TABLA).insert(payload).execute()
    # Sólo la cabecera, igual que en conductores: ni las respuestas ni el
    # resultado de la entrevista van al log.
    auditoria.registrar(
        "seguimiento", "alta",
        f"{payload.get('apenom')} (leg. {payload.get('legajo')}) · "
        f"entrevista de personal ingresante del {payload.get('fecha_entrevista')}",
        datos={"legajo": payload.get("legajo"), "sector": payload.get("sector"),
               "cuestionario": "general"},
    )


def _eliminar_general(record_id: str, detalle: str = "") -> None:
    get_supabase().table(sgen.TABLA).delete().eq("id", record_id).execute()
    auditoria.registrar("seguimiento", "baja",
                        f"{detalle} (personal ingresante)", registro_id=record_id)


def _auditar_apertura_general(fila) -> None:
    """Como `_auditar_apertura`: se llama al ABRIR la entrevista, no al dibujarla.

    Acá toda apertura es una lectura sensible: sólo llega a la entrevista quien
    tiene permiso de carga, y la ve entera."""
    auditoria.registrar(
        "seguimiento", "lectura",
        f"Abrió la entrevista de personal ingresante de {fila.get('apenom')} "
        f"(leg. {fila.get('legajo')}) del {_fecha_txt(fila.get('fecha_entrevista'))} "
        "— incluye observaciones",
        registro_id=fila.get("id"),
    )


def _gen_enunciado(p) -> str:
    """Enunciado de una pregunta, con la aclaración entre paréntesis del papel."""
    if p.get("ayuda"):
        return f'{p["texto"]} <span class="ayuda">({p["ayuda"]})</span>'
    return p["texto"]


def _gen_tab_form(df_emp, df_gen) -> None:
    """Pestaña «Nueva entrevista» del personal no conductor.

    Como el listado y el detalle, sólo se dibuja para quien tiene permiso de
    carga: el corte está en `_vista_general`."""
    st.markdown('<p class="section-label">Registrar entrevista</p>', unsafe_allow_html=True)
    if st.session_state.pop("saved_ok_sgg", False):
        st.success(st.session_state.pop("saved_msg_sgg", "✓ Entrevista registrada."))

    opciones_map = {}
    for _, r in sgen.solo_no_conductores(df_emp).iterrows():
        partes = (f"{r['legajo']} — {r['apenom']}", _txt(r.get("cargo")),
                  _txt(r.get("empleador")))
        opciones_map["  ·  ".join(x for x in partes if x)] = r
    # El sector no viene en el padrón: se ofrece lo ya cargado para que el mismo
    # sector no termine escrito de tres maneras.
    sectores = sorted({_txt(s) for s in df_gen["sector"] if _txt(s)})

    # Mismo esquema que conductores: el seed se bumpea SOLO tras guardar con
    # éxito, y nunca clear_on_submit (borraría todo si falla una validación).
    seed = st.session_state.setdefault("sgg_form_seed", 0)
    nombre_user = (current_user() or {}).get("nombre", "")
    cod_res = sgen.RESULTADO["cod"]

    respuestas, obs = {}, {}
    slots, enunciados = {}, {}     # cod → hueco y (número, texto), para repintar al validar

    def _enunciado(cod, num, texto):
        enunciados[cod] = (num, texto)
        slots[cod] = st.empty()
        slots[cod].markdown(_preg_html(num, texto), unsafe_allow_html=True)

    with st.form("form_seguimiento_general", clear_on_submit=False):
        empleado_sel = st.selectbox(
            "Empleado", options=list(opciones_map), index=None,
            placeholder="Escribí nombre, apellido o legajo para buscar...",
            key=f"sgg_emp_{seed}",
        )
        st.caption("Aparece el personal activo que no es conductor. El puesto y la "
                   "fecha de ingreso se toman del padrón al guardar.")
        c1, c2, c3 = st.columns(3)
        with c1:
            sector = st.selectbox(
                "Sector", options=sectores, index=None, accept_new_options=True,
                placeholder="Elegí o escribí uno nuevo", key=f"sgg_sector_{seed}")
        with c2:
            fecha_entrevista = st.date_input(
                "Fecha de la entrevista", value=date.today(), key=f"sgg_fecha_{seed}")
        with c3:
            entrevistador = st.text_input(
                "Entrevistador", value=nombre_user, key=f"sgg_entrev_{seed}")

        for num_sec, nombre_sec in sgen.SECCIONES.items():
            _sec_head(f"{num_sec}. {nombre_sec}")
            for p in [q for q in sgen.PREGUNTAS if q["seccion"] == num_sec]:
                _enunciado(p["cod"], p["n"], _gen_enunciado(p))
                if p["tipo"] == "abierta":
                    respuestas[p["cod"]] = st.text_area(
                        p["texto"], max_chars=1000, height=80,
                        label_visibility="collapsed", placeholder="Opcional",
                        key=f"sgg_{p['cod']}_{seed}")
                    continue
                respuestas[p["cod"]] = st.radio(
                    p["texto"], options=list(p["opciones"]), index=None,
                    horizontal=True, label_visibility="collapsed",
                    key=f"sgg_{p['cod']}_{seed}",
                )
                if "texto_label" in p:
                    respuestas[p["cod"] + "_texto"] = st.text_input(
                        p["texto_label"], key=f"sgg_{p['cod']}_txt_{seed}",
                        placeholder="Detallar solo si corresponde")
            # En el papel las observaciones son una por sección, no por pregunta.
            obs[sgen.OBS_SECCION[num_sec]] = st.text_area(
                "Observaciones", max_chars=1000, height=70, placeholder="Opcional",
                key=f"sgg_obs_{num_sec}_{seed}")

        _sec_head(f"{sgen.N_SECCION_EVALUACION}. {sgen.TITULO_EVALUACION}")
        st.caption("La completa el sector: cómo evalúa al ingresante.")
        for e in sgen.EVALUACION:
            _enunciado(e["cod"], e["letra"], e["texto"])
            respuestas[e["cod"]] = st.radio(
                e["texto"], options=list(e["opciones"]), index=None,
                horizontal=True, label_visibility="collapsed",
                key=f"sgg_{e['cod']}_{seed}",
            )
        obs[sgen.OBS_EVALUACION] = st.text_area(
            "Observaciones", max_chars=1000, height=70, placeholder="Opcional",
            key=f"sgg_obs_eval_{seed}")

        _sec_head(f"{sgen.N_SECCION_RESULTADO}. {sgen.TITULO_RESULTADO}")
        _enunciado(cod_res, None, "Elegí una sola opción.")
        respuestas[cod_res] = st.radio(
            sgen.TITULO_RESULTADO, options=list(sgen.RESULTADOS), index=None,
            horizontal=True, label_visibility="collapsed", key=f"sgg_resultado_{seed}",
        )
        obs[sgen.OBS_FINALES] = st.text_area(
            "Observaciones finales", max_chars=2000, height=110, placeholder="Opcional",
            key=f"sgg_obs_fin_{seed}")

        # El mismo marcador que usa conductores: ancla la guarda de salida a
        # este formulario (se dibuja uno solo de los dos por vez).
        st.markdown('<span id="sg-guard-marker"></span>', unsafe_allow_html=True)
        st.caption("No cierres la pestaña ni cambies de cuestionario hasta guardar "
                   "la entrevista.")
        submitted = st.form_submit_button("Registrar entrevista")

    _guardia_salida()
    if not submitted:
        return

    # ── Validación (fuera del form, como el resto del dashboard) ──
    faltan_cab, faltan_preg, faltan_eval, faltan_txt = [], [], [], []
    marcar = []     # cods a repintar en rojo arriba
    if not empleado_sel:
        faltan_cab.append("el empleado")
    if not sgen.normalizar_sector(sector):
        faltan_cab.append("el sector")
    if not (entrevistador or "").strip():
        faltan_cab.append("el entrevistador")
    if not fecha_entrevista:
        faltan_cab.append("la fecha de la entrevista")

    for p in sgen.CERRADAS:
        elegido = respuestas.get(p["cod"])
        if elegido is None:
            faltan_preg.append(str(p["n"]))
            marcar.append(p["cod"])
        elif elegido in p.get("texto_si", ()) and \
                not (respuestas.get(p["cod"] + "_texto") or "").strip():
            faltan_txt.append(str(p["n"]))
            marcar.append(p["cod"])
    for e in sgen.EVALUACION:
        if respuestas.get(e["cod"]) is None:
            faltan_eval.append(e["corto"])
            marcar.append(e["cod"])
    falta_resultado = respuestas.get(cod_res) is None
    if falta_resultado:
        marcar.append(cod_res)

    # Un solo error con todo lo que falta, y los enunciados repintados en rojo.
    if faltan_cab or faltan_preg or faltan_eval or faltan_txt or falta_resultado:
        for cod in marcar:
            num, texto = enunciados[cod]
            slots[cod].markdown(_preg_html(num, texto, falta=True), unsafe_allow_html=True)

        partes = []
        if faltan_cab:
            partes.append("Falta completar " + ", ".join(faltan_cab) + ".")
        if faltan_preg:
            partes.append(
                f"Faltan {len(faltan_preg)} respuesta"
                f"{'s' if len(faltan_preg) != 1 else ''} — "
                "quedaron marcadas en rojo más arriba: preguntas "
                + ", ".join(faltan_preg) + ".")
        if faltan_eval:
            partes.append("Falta la evaluación del sector en: " + ", ".join(faltan_eval) + ".")
        if falta_resultado:
            partes.append("Falta elegir el resultado de la entrevista.")
        if faltan_txt:
            partes.append(
                f"Respondiste «Sí» en {' y '.join(faltan_txt)}: falta completar el detalle.")
        st.error(" ".join(partes))
        return

    r = opciones_map.get(empleado_sel)
    if r is None:
        st.error("No se encontró al empleado. Intentá de nuevo.")
        return

    payload = {
        "legajo": str(r["legajo"]).strip(),
        "apenom": r["apenom"],
        "empleador": r["empleador"],
        "base": _txt(r.get("str")) or None,
        "cargo": _txt(r.get("cargo")) or None,
        "sector": sgen.normalizar_sector(sector),
        "fecha_ingreso": r["fecha_inicio"].isoformat()
                         if pd.notna(r.get("fecha_inicio")) else None,
        "fecha_entrevista": fecha_entrevista.isoformat(),
        "entrevistador": entrevistador.strip(),
        "registrado_por": nombre_user,
    }
    # Se guarda el CÓDIGO, nunca la etiqueta del radio (salvo en las categorías).
    for p in sgen.PREGUNTAS:
        payload[p["cod"]] = sgen.codigo(p, respuestas.get(p["cod"]))
        if "texto_label" in p:
            payload[p["cod"] + "_texto"] = \
                (respuestas.get(p["cod"] + "_texto") or "").strip() or None
    for e in sgen.EVALUACION:
        payload[e["cod"]] = sgen.codigo(e, respuestas.get(e["cod"]))
    payload[cod_res] = sgen.codigo(sgen.RESULTADO, respuestas.get(cod_res))
    for col, texto in obs.items():
        payload[col] = (texto or "").strip() or None

    try:
        _guardar_general(payload)
    except Exception as e:
        if "23505" in str(e) or "duplicate key" in str(e).lower():
            st.error(
                "Ya hay una entrevista cargada para esa persona con esa fecha. "
                "Si es una entrevista posterior, cambiá la fecha.")
        else:
            st.error("No se pudo registrar la entrevista. Intentá de nuevo.")
        return

    _leer_general.clear()
    st.session_state["saved_ok_sgg"] = True
    st.session_state["saved_msg_sgg"] = (
        f"✓ Entrevista registrada — **{r['apenom']}** · "
        f"{fecha_entrevista.strftime('%d/%m/%Y')}")
    st.session_state["sgg_form_seed"] = seed + 1
    st.rerun()


def _gen_detalle(fila) -> None:
    """Vista ampliada de una entrevista del personal no conductor."""
    etiqueta_ind, color_ind = sgen.banda(fila["indice_general"])
    _, color_ev = sgen.banda(fila["indice_evaluacion"])

    def _chip(texto, color):
        return (f'<span class="det-chip" style="background:{color}18;color:{color};'
                f'border:1px solid {color}40;">{texto}</span>')

    chips = _chip(f'Índice {_fmt(fila["indice_general"], "", 1)} · {etiqueta_ind}', color_ind)
    chips += _chip(f'Evaluación del sector {_fmt(fila["indice_evaluacion"], "", 1)}', color_ev)
    resultado = _txt(fila.get("resultado"))
    if resultado:
        chips += _chip(_esc(resultado),
                       sgen.COLOR_RESULTADO.get(resultado, sgen.COLOR_BUENO))
    if fila["nivel_alerta"]:
        chips += _chip(f'Alerta {fila["nivel_alerta"]}',
                       "#D12F19" if fila["nivel_alerta"] == "Roja" else "#B45309")

    lugar = " · ".join(x for x in (_esc(fila.get("cargo")), _esc(fila.get("sector")),
                                   _esc(fila.get("base")), _esc(fila.get("empleador"))) if x)
    st.markdown(f"""
    <div class="det-head">
      <div class="det-name">{_esc(fila["apenom"])}</div>
      <div class="det-meta">
        Legajo {_esc(fila["legajo"])} · {lugar}<br>
        Ingreso: {_fecha_txt(fila.get("fecha_ingreso"))} · Entrevista: {_fecha_txt(fila["fecha_entrevista"])} · Entrevistador: {_esc(fila["entrevistador"])}
      </div>
      <div class="det-chips">{chips}</div>
    </div>
    """, unsafe_allow_html=True)

    if fila["motivos_alerta"]:
        st.warning("**Motivos de alerta** — " + " · ".join(fila["motivos_alerta"]))

    # El texto libre lo escribió una persona: se escapa antes de ir al HTML.
    secciones = [
        (titulo, [dict(it, respuesta=_esc(it["respuesta"]), textual=_esc(it["textual"]),
                       observacion=_esc(it["observacion"])) for it in items])
        for titulo, items in sgen.detalle_entrevista(fila, incluir_textos=True)
    ]
    corte = len(sgen.SECCIONES)     # 1-7: lo que dijo el ingresante · 8-9: el cierre
    col_izq, col_der = st.columns([3, 2], gap="large")
    with col_izq:
        st.markdown(_bloques_html(secciones[:corte]), unsafe_allow_html=True)
    with col_der:
        st.markdown(_bloques_html(secciones[corte:]), unsafe_allow_html=True)


def _gen_tab_listado(df_gen, filtrar, rojas_ocultas) -> None:
    """Pestaña «Entrevistas cargadas» del personal no conductor."""
    if df_gen.empty:
        st.info("Todavía no hay entrevistas cargadas.")
        return

    def _aviso_rojas_ocultas(key):
        if not rojas_ocultas:
            return
        c_txt, c_btn = st.columns([9, 3], vertical_alignment="center")
        with c_txt:
            st.caption(_gen_texto_rojas_ocultas(rojas_ocultas))
        with c_btn:
            if st.button("Mostrar todas las rojas", key=key, width="stretch"):
                st.session_state["_abrir_rojas_sgg"] = True
                st.rerun()

    # ══ Vista ampliada de una entrevista ══
    ver_id = st.session_state.get("ver_id_sgg")
    if ver_id is not None and (df_gen["id"] == ver_id).any():
        # Los filtros no se dibujan en esta vista y Streamlit descarta el estado
        # de un widget que no se dibujó: se reasignan para que al volver al
        # listado sigan como estaban.
        for clave in FILTROS_GENERAL:
            st.session_state[clave] = st.session_state[clave]

        fila = df_gen[df_gen["id"] == ver_id].iloc[0]
        c_volver, c_desc = st.columns([1, 3])
        with c_volver:
            if st.button("←  Volver al listado", key="btn_volver_sgg", width="stretch"):
                st.session_state.pop("ver_id_sgg", None)
                # Nueva key para la tabla: si no, la selección vieja volvería a
                # abrir esta misma entrevista al instante.
                st.session_state["tabla_seed_sgg"] = \
                    st.session_state.get("tabla_seed_sgg", 0) + 1
                st.rerun()
        with c_desc:
            if st.download_button(
                "⬇  Descargar esta entrevista (Excel)",
                data=sgen.exportar_excel(fila.to_frame().T, incluir_textos=True),
                file_name=(f"entrevista_ingresante_{fila['legajo']}_"
                           f"{fila['fecha_entrevista'].strftime('%d-%m-%Y')}.xlsx"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_una_sgg",
            ):
                auditoria.registrar(
                    "seguimiento", "export",
                    f"Descargó la entrevista de personal ingresante de {fila['apenom']} "
                    f"(leg. {fila['legajo']}) — con observaciones",
                    registro_id=fila["id"],
                )
        _gen_detalle(fila)
        return

    # ══ Listado ══
    st.session_state.pop("ver_id_sgg", None)
    sectores = ["Todos"] + sorted({_txt(s) for s in df_gen["sector"] if _txt(s)})
    if st.session_state["sector_sgg"] not in sectores:      # se eliminó la última de ese sector
        st.session_state["sector_sgg"] = "Todos"

    f1, f2, f3, f4 = st.columns([2, 2, 2, 2], gap="medium")
    # Sin `value=` / `index=`: el default lo pone session_state más arriba, así
    # el botón «Mostrar todas las rojas» puede reescribirlo.
    with f1:
        desde = st.date_input("Desde", key="desde_sgg")
    with f2:
        hasta = st.date_input("Hasta", key="hasta_sgg")
    with f3:
        sector_sel = st.selectbox("Sector", options=sectores, key="sector_sgg")
    with f4:
        resultado_sel = st.selectbox(
            "Resultado", options=["Todos"] + list(sgen.RESULTADOS), key="resultado_sgg")

    f = filtrar(df_gen).copy()

    if f.empty:
        if desde > hasta:
            st.warning(
                f"El «Desde» ({desde.strftime('%d/%m/%Y')}) es posterior al «Hasta» "
                f"({hasta.strftime('%d/%m/%Y')}): el período está invertido.")
        elif sector_sel != "Todos" or resultado_sel != "Todos":
            activos = " y ".join(
                x for x in (f"sector «{sector_sel}»" if sector_sel != "Todos" else "",
                            f"resultado «{resultado_sel}»" if resultado_sel != "Todos" else "")
                if x)
            st.info(
                f"No hay entrevistas entre el {desde.strftime('%d/%m/%Y')} y el "
                f"{hasta.strftime('%d/%m/%Y')} con {activos}.")
        else:
            st.info(
                f"No hay entrevistas cargadas entre el {desde.strftime('%d/%m/%Y')} "
                f"y el {hasta.strftime('%d/%m/%Y')}.")
        _aviso_rojas_ocultas("btn_rojas_vacio_sgg")
    else:
        # ── Alertas primero ──
        alertas = sgen.detectar_alertas(f)
        st.markdown('<p class="section-label">Alertas</p>', unsafe_allow_html=True)
        _aviso_rojas_ocultas("btn_rojas_listado_sgg")
        if alertas.empty:
            st.success("✓ Ninguna entrevista del período disparó alertas.")
        else:
            def _fila_alerta(a):
                clase = "alert-row" if a["nivel_alerta"] == "Roja" else "alert-row amber"
                quote = ""
                if _txt(a.get(sgen.OBS_FINALES)):
                    quote = f'<div class="alert-quote">{_esc(a.get(sgen.OBS_FINALES))}</div>'
                lugar = " · ".join(x for x in (_esc(a.get("cargo")), _esc(a.get("sector"))) if x)
                c_txt, c_btn = st.columns([9, 2], vertical_alignment="center")
                with c_txt:
                    st.markdown(
                        f'<div class="{clase}">'
                        f'<div class="alert-name">{_esc(a["apenom"])} · Legajo {_esc(a["legajo"])}</div>'
                        f'<div class="alert-meta">{lugar or "Sin sector"} · '
                        f'{_fecha_txt(a["fecha_entrevista"])} · '
                        f'Índice {_fmt(a["indice_general"])} · '
                        f'{_esc(" · ".join(a["motivos_alerta"]))}</div>'
                        f'{quote}</div>',
                        unsafe_allow_html=True,
                    )
                with c_btn:
                    if st.button("Ver entrevista", key=f"ver_al_sgg_{a['id']}", width="stretch"):
                        st.session_state["ver_id_sgg"] = a["id"]
                        _auditar_apertura_general(a)
                        st.rerun()

            # Igual que en conductores: las rojas siempre desplegadas, las de
            # atención plegadas con el número a la vista.
            rojas_f = alertas[alertas["nivel_alerta"] == "Roja"]
            atencion_f = alertas[alertas["nivel_alerta"] != "Roja"]
            if not rojas_f.empty:
                st.caption(
                    f"**{len(rojas_f)}** para revisar ya — no se recomienda la continuidad, "
                    "la persona no quiere continuar o el sector la evaluó insuficiente.")
                for _, a in rojas_f.iterrows():
                    _fila_alerta(a)
            if not atencion_f.empty:
                with st.expander(f"Atención ({len(atencion_f)}) — revisar cuando puedas"):
                    for _, a in atencion_f.iterrows():
                        _fila_alerta(a)
        st.divider()
        st.markdown('<p class="section-label">Entrevistas del período</p>',
                    unsafe_allow_html=True)
        vista = pd.DataFrame({
            "Legajo": f["legajo"],
            "Nombre": f["apenom"],
            "Puesto": f["cargo"].fillna("—"),
            "Sector": f["sector"].fillna("—"),
            "Fecha": f["fecha_entrevista"].apply(_fecha_txt),
            "Índice": pd.to_numeric(f["indice_general"], errors="coerce").round(1),
            "Evaluación": pd.to_numeric(f["indice_evaluacion"], errors="coerce").round(1),
            "Resultado": f["resultado"].fillna("—"),
            "Alerta": f["nivel_alerta"].replace("", "—"),
            "Entrevistador": f["entrevistador"],
        })
        evento = st.dataframe(
            vista, width="stretch", hide_index=True,
            on_select="rerun", selection_mode="single-row",
            key=f"tabla_sgg_{st.session_state.get('tabla_seed_sgg', 0)}",
        )
        st.caption("Hacé clic en una fila para abrir la entrevista completa.")

        filas_sel = list((evento or {}).get("selection", {}).get("rows", []))
        if filas_sel:
            st.session_state["ver_id_sgg"] = f.iloc[filas_sel[0]]["id"]
            _auditar_apertura_general(f.iloc[filas_sel[0]])
            st.rerun()

        if st.download_button(
            "⬇  Descargar entrevistas (Excel)",
            data=sgen.exportar_excel(f, incluir_textos=True),
            file_name=(f"seguimiento_personal_{desde.strftime('%d-%m-%Y')}"
                       f"_a_{hasta.strftime('%d-%m-%Y')}.xlsx"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_todas_sgg",
        ):
            auditoria.registrar(
                "seguimiento", "export",
                f"Descargó {len(f)} entrevista(s) de personal ingresante del "
                f"{desde.strftime('%d/%m/%Y')} al {hasta.strftime('%d/%m/%Y')}"
                " — con observaciones",
                datos={"registros": int(len(f)), "cuestionario": "general"},
            )

    # ── Eliminar ──
    st.divider()
    if st.session_state.pop("deleted_ok_sgg", False):
        st.success("Entrevista eliminada correctamente.")
    with st.expander("Eliminar una entrevista"):
        labels = {
            f"{r['apenom']} · {_fecha_txt(r['fecha_entrevista'])} · Legajo {r['legajo']}": r["id"]
            for _, r in df_gen.iterrows() if pd.notna(r["fecha_entrevista"])
        }
        elegido = st.selectbox("Entrevista", options=list(labels), index=None,
                               placeholder="Seleccioná una entrevista...", key="del_sel_sgg")
        if st.button("Eliminar entrevista", key="btn_del_sgg") and elegido:
            st.session_state["del_id_sgg"] = labels[elegido]
            st.session_state["del_label_sgg"] = elegido
            st.rerun()

        if "del_id_sgg" in st.session_state:
            st.warning(
                f"¿Eliminar **{st.session_state['del_label_sgg']}**? "
                "Esta acción no se puede deshacer.")
            c1, c2 = st.columns([1, 1])
            with c1:
                if st.button("Sí, eliminar", key="btn_confirm_sgg"):
                    try:
                        _eliminar_general(st.session_state["del_id_sgg"],
                                          st.session_state.get("del_label_sgg", ""))
                        st.session_state["deleted_ok_sgg"] = True
                    except Exception:
                        st.error("No se pudo eliminar la entrevista.")
                    st.session_state.pop("del_id_sgg", None)
                    st.session_state.pop("del_label_sgg", None)
                    _leer_general.clear()
                    st.rerun()
            with c2:
                if st.button("Cancelar", key="btn_cancel_sgg"):
                    st.session_state.pop("del_id_sgg", None)
                    st.session_state.pop("del_label_sgg", None)
                    st.rerun()


def _gen_texto_rojas_ocultas(n) -> str:
    plural = "s" if n != 1 else ""
    return (f"{n} alerta{plural} roja{plural} "
            f"queda{'n' if n != 1 else ''} fuera de los filtros actuales.")


def _gen_barras_apiladas(dist):
    """Barras al 100 % por pregunta, con la peor puntuada arriba.

    El color de cada tramo sale de los puntos de esa respuesta (la misma paleta
    del detalle), no de su posición: «Buena» y «Parcialmente» son las dos la
    opción del medio, pero no valen lo mismo.
    """
    orden = dist.drop_duplicates("cod").sort_values("indice", ascending=False)
    fig = go.Figure()
    for valor in sorted(dist["valor"].unique()):
        sub = dist[dist["valor"] == valor].set_index("cod").reindex(orden["cod"])
        fig.add_trace(go.Bar(
            y=list(orden["rotulo"]), x=sub["pct"], orientation="h",
            marker_color=[sgen.color_puntos(p) for p in sub["puntos"]],
            customdata=sub[["n", "etiqueta"]].values,
            hovertemplate="%{y}<br>%{customdata[1]}: %{customdata[0]} (%{x:.0f}%)<extra></extra>",
        ))
    fig.update_layout(**chart_base(
        barmode="stack", height=70 + 34 * len(orden), showlegend=False,
        xaxis=dict(range=[0, 100], ticksuffix="%", showgrid=False,
                   zeroline=False, linecolor="#CCCCCC",
                   tickfont=dict(color="#8C8987")),
        yaxis=dict(showgrid=False, zeroline=False, linecolor="#CCCCCC",
                   tickfont=dict(color="#8C8987", size=11)),
        margin=dict(l=10, r=10, t=10, b=10),
    ))
    return fig


def _gen_barras_frecuencia(frec, colores):
    """Barras horizontales de una categoría, en el orden del catálogo."""
    frec = frec.iloc[::-1]          # Plotly dibuja de abajo hacia arriba
    fig = go.Figure(go.Bar(
        x=frec["n"], y=frec["categoria"], orientation="h",
        marker_color=[colores.get(c, COLOR_PRIMARY) for c in frec["categoria"]],
        text=[f"{n}  ({p:.0f}%)" for n, p in zip(frec["n"], frec["pct"])],
        textposition="outside",
        hovertemplate="%{y}<br>%{x} entrevistas<extra></extra>",
    ))
    fig.update_layout(**chart_base(
        height=80 + 36 * len(frec), showlegend=False,
        xaxis=dict(showgrid=True, gridcolor="#E8E8E8", zeroline=False,
                   linecolor="#CCCCCC", tickfont=dict(color="#8C8987"),
                   range=[0, max(frec["n"]) * 1.35]),
        yaxis=dict(showgrid=False, zeroline=False, linecolor="#CCCCCC",
                   tickfont=dict(color="#8C8987")),
        margin=dict(l=10, r=30, t=10, b=10),
    ))
    return fig


def _gen_tab_indicadores(df_gen) -> None:
    """Pestaña «Indicadores» del personal no conductor (agregado, sin nombres)."""
    if df_gen.empty:
        st.info("Todavía no hay entrevistas cargadas para calcular indicadores.")
        return

    kpis = sgen.resumen_kpis(df_gen)
    etiqueta_banda, color_ind = sgen.banda(kpis["indice_general"])
    _, color_ev = sgen.banda(kpis["evaluacion"])
    st.markdown(
        '<div class="kpi6">'
        + _kpi_card("Entrevistas", _fmt(kpis["entrevistas"]), "cargadas en total")
        + _kpi_card("Índice general", _fmt(kpis["indice_general"], "", 1),
                    etiqueta_banda, color_ind)
        + _kpi_card("Evaluación del sector", _fmt(kpis["evaluacion"], "", 1),
                    "cómo ve el sector al ingresante", color_ev)
        + _kpi_card("Quieren continuar", _fmt(kpis["quieren_continuar"], "%"),
                    "responden que sí", COLOR_SECONDARY)
        + _kpi_card("Continuidad", _fmt(kpis["continuidad"], "%"),
                    "recomendada, con o sin seguimiento", "#15803D")
        + _kpi_card("Con alerta", _fmt(kpis["alertas"]),
                    _fmt(kpis["pct_alertas"], "% del total"), "#D12F19")
        + '</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Índices de 0 a 100. **Sí · Muy buena · Muy conforme = 100 — Buena · Conforme = 67 "
        "— Parcialmente · Tal vez = 50 — Regular · Poco conforme = 33 — No = 0.** "
        "No se comparan con los de conductores: son otras preguntas.")

    st.divider()

    # ── 1. Resultado de las entrevistas ──
    st.markdown('<p class="section-label">Resultado de las entrevistas</p>',
                unsafe_allow_html=True)
    frec = sgen.frecuencia_categoria(df_gen, sgen.RESULTADO["cod"])
    if frec.empty:
        st.info("Todavía no hay resultados cargados.")
    else:
        st.plotly_chart(_gen_barras_frecuencia(frec, sgen.COLOR_RESULTADO),
                        use_container_width=True, key="fig_resultado_sgg")

    st.divider()

    # ── 2. Índice por dimensión ──
    st.markdown('<p class="section-label">Índice por dimensión</p>', unsafe_allow_html=True)
    dims = sgen.resumen_dimensiones(df_gen).dropna(subset=["indice"])
    if dims.empty:
        st.info("Todavía no hay respuestas suficientes para calcular los índices.")
    else:
        dims = dims.sort_values("indice", ascending=False)
        fig = go.Figure(go.Bar(
            x=dims["indice"],
            y=[f"{r['nombre']}  (n={int(r['n_items'])} ítems)" for _, r in dims.iterrows()],
            orientation="h",
            marker_color=[sgen.banda(v)[1] for v in dims["indice"]],
            text=[f"{v:.1f}" for v in dims["indice"]],
            textposition="outside",
            hovertemplate="%{y}<br>Índice: %{x:.1f}<extra></extra>",
        ))
        fig.update_layout(**chart_base(
            height=60 + 46 * len(dims), showlegend=False,
            xaxis=dict(range=[0, 112], showgrid=True, gridcolor="#E8E8E8",
                       zeroline=False, linecolor="#CCCCCC",
                       tickfont=dict(color="#8C8987")),
            yaxis=dict(showgrid=False, zeroline=False, linecolor="#CCCCCC",
                       tickfont=dict(color="#8C8987")),
            margin=dict(l=10, r=40, t=10, b=10),
        ))
        st.plotly_chart(fig, use_container_width=True, key="fig_dims_sgg")
        st.caption(
            "Lo que respondió el ingresante. La evaluación del sector va aparte, más "
            "abajo: es otra voz. Arriba, la dimensión con menor índice.")

    st.divider()

    # ── 3. Respuestas por pregunta ──
    leyenda = ("Verde: la mejor respuesta · celeste: Buena / Conforme · ámbar: "
               "Parcialmente / Tal vez / Regular / Poco conforme · rojo: No / Insuficiente.")
    st.markdown('<p class="section-label">Respuestas por pregunta</p>', unsafe_allow_html=True)
    dist = sgen.distribucion_items(df_gen)
    if dist.empty:
        st.info("Todavía no hay respuestas cerradas cargadas.")
    else:
        st.plotly_chart(_gen_barras_apiladas(dist), use_container_width=True,
                        key="fig_items_sgg")
        st.caption("Ordenado de peor a mejor: arriba, las preguntas con menor índice. "
                   + leyenda)

    st.divider()

    c_eval, c_cat = st.columns(2, gap="large")

    # ── 4. Evaluación del sector ──
    with c_eval:
        st.markdown('<p class="section-label">Evaluación del sector</p>',
                    unsafe_allow_html=True)
        dist_ev = sgen.distribucion_items(df_gen, sgen.EVALUACION)
        if dist_ev.empty:
            st.info("Todavía no hay evaluaciones cargadas.")
        else:
            st.plotly_chart(_gen_barras_apiladas(dist_ev), use_container_width=True,
                            key="fig_eval_sgg")
            st.caption("Cómo evaluó cada sector a sus ingresantes. " + leyenda)

    # ── 5. Las dos preguntas que no puntúan ──
    with c_cat:
        st.markdown('<p class="section-label">Preguntas que no puntúan</p>',
                    unsafe_allow_html=True)
        opciones_cat = {f"{p['n']}. {p['corto']}": p["cod"] for p in sgen.CATEGORIAS}
        cat_label = st.radio("Pregunta", options=list(opciones_cat), horizontal=True,
                             label_visibility="collapsed", key="cat_sgg")
        frec = sgen.frecuencia_categoria(df_gen, opciones_cat[cat_label])
        if frec.empty:
            st.info("Todavía no hay respuestas cargadas para esta pregunta.")
        else:
            st.plotly_chart(_gen_barras_frecuencia(frec, {}), use_container_width=True,
                            key="fig_cat_sgg")
            st.caption("Describen, no evalúan: no entran en ningún índice.")

    st.divider()

    # ── 6. Corte por sector ──
    st.markdown('<p class="section-label">Índice por sector</p>', unsafe_allow_html=True)
    tabla_sector, excluidos = sgen.corte_por_sector(df_gen)
    if tabla_sector.empty:
        st.info(f"Ningún sector llega todavía a {sgen.MIN_N_CORTE} entrevistas.")
    else:
        st.dataframe(pd.DataFrame({
            "Sector": tabla_sector["sector"],
            "Entrevistas": tabla_sector["n"],
            "Índice": tabla_sector["indice"].round(1),
            "Evaluación del sector": tabla_sector["evaluacion"].round(1),
        }), width="stretch", hide_index=True)
    if excluidos:
        st.caption(
            f"Solo se muestran sectores con {sgen.MIN_N_CORTE} o más entrevistas. "
            f"Quedan fuera: {', '.join(excluidos)}.")


def _vista_general(df_emp) -> None:
    """Todo el cuestionario del personal no conductor, debajo del selector."""
    try:
        df_gen = sgen.calcular_indices(_leer_general())
    except Exception:
        st.error("No se pudieron cargar las entrevistas. Revisá la conexión con la base.")
        st.caption("Si este cuestionario todavía no se usó nunca, puede faltar crear su "
                   "tabla en Supabase (`migration_seguimiento_general.sql`).")
        if st.button("Reintentar", key="retry_db_sgg"):
            _leer_general.clear()
            st.rerun()
        return

    # Sin permiso de carga no se ve a nadie en particular: ni el listado, ni las
    # alertas, ni el detalle, ni el Excel. A diferencia de conductores, acá cada
    # entrevista trae el resultado («no recomendar continuidad») y la evaluación
    # que el sector hizo de la persona. Quedan los agregados, y recién cuando hay
    # entrevistas suficientes como para que un promedio no sea una sola persona.
    if not PUEDE_EDITAR:
        st.info(
            "**Modo solo lectura.** Ves los indicadores del conjunto, sin nombres. "
            "Las entrevistas de cada persona las ve solo quien tiene el permiso de "
            "Seguimiento.")
        if len(df_gen) < sgen.MIN_N_CORTE:
            st.caption(
                f"Los indicadores se muestran a partir de {sgen.MIN_N_CORTE} entrevistas "
                "cargadas: con menos, un promedio deja ver lo que respondió una persona.")
        else:
            _gen_tab_indicadores(df_gen)
        return

    # Los defaults de los filtros viven en session_state por lo mismo que en
    # conductores: el banner se dibuja antes que ellos y necesita su recorte.
    hoy = date.today()
    st.session_state.setdefault("desde_sgg", hoy.replace(month=1, day=1))
    st.session_state.setdefault("hasta_sgg", hoy)
    st.session_state.setdefault("sector_sgg", "Todos")
    st.session_state.setdefault("resultado_sgg", "Todos")

    def filtrar(df):
        """El recorte que ve el listado; el banner cuenta sobre exactamente lo mismo."""
        out = df[(df["fecha_entrevista"] >= st.session_state["desde_sgg"]) &
                 (df["fecha_entrevista"] <= st.session_state["hasta_sgg"])]
        if st.session_state["sector_sgg"] != "Todos":
            out = out[out["sector"] == st.session_state["sector_sgg"]]
        if st.session_state["resultado_sgg"] != "Todos":
            out = out[out["resultado"] == st.session_state["resultado_sgg"]]
        return out

    rojas = df_gen[df_gen["nivel_alerta"] == "Roja"] if not df_gen.empty else df_gen

    # El botón «Mostrar todas las rojas» vive junto a los filtros, pero Streamlit
    # no deja escribir la key de un widget ya instanciado: deja pedido el cambio
    # y se aplica acá, antes de que los widgets existan.
    if st.session_state.pop("_abrir_rojas_sgg", False) and len(rojas):
        fechas = rojas["fecha_entrevista"].dropna()
        if not fechas.empty:
            st.session_state["desde_sgg"] = min(fechas.min(), st.session_state["desde_sgg"])
            st.session_state["hasta_sgg"] = max(fechas.max(), st.session_state["hasta_sgg"])
        st.session_state["sector_sgg"] = "Todos"
        st.session_state["resultado_sgg"] = "Todos"

    rojas_ocultas = len(rojas) - len(filtrar(rojas)) if len(rojas) else 0

    # Contenedor fijo: el banner aparece y desaparece con los datos, y suelto
    # arriba de st.tabs haría que Streamlit vuelva a montar las pestañas en la
    # primera justo después de eliminar una entrevista.
    with st.container():
        if len(rojas):
            n = len(rojas)
            st.error(
                f"**{n} entrevista{'s' if n != 1 else ''} con alerta roja** — "
                "revisalas en la pestaña «Entrevistas cargadas»."
                + (f" {_gen_texto_rojas_ocultas(rojas_ocultas)}" if rojas_ocultas else ""))

    tab_form, tab_carga, tab_ind = st.tabs(
        ["Nueva entrevista", "Entrevistas cargadas", "Indicadores"])
    with tab_form:
        _gen_tab_form(df_emp, df_gen)
    with tab_carga:
        _gen_tab_listado(df_gen, filtrar, rojas_ocultas)
    with tab_ind:
        _gen_tab_indicadores(df_gen)


# ─── Header + selector de cuestionario ────────────────────────
# Se define acá y no más abajo porque los dos cuestionarios lo consultan.
PUEDE_EDITAR = can_edit("seguimiento")

st.markdown("""
<div class="page-title">
  <div class="accent-bar"></div>
  <h1>Seguimiento</h1>
</div>
""", unsafe_allow_html=True)

# Cambiar de cuestionario redibuja la pantalla con el otro formulario: lo que
# estuviera a medio cargar en el anterior se descarta (el formulario lo avisa).
CUESTIONARIO = st.radio(
    "Cuestionario", options=[CUEST_CONDUCTORES, CUEST_GENERAL], horizontal=True,
    label_visibility="collapsed", key="cuestionario_sg",
)
st.markdown(f'<p class="page-subtitle">{SUBTITULOS[CUESTIONARIO]}</p>',
            unsafe_allow_html=True)

# ─── Carga del padrón ─────────────────────────────────────────
df_emp = pd.DataFrame(columns=["legajo", "apenom", "empleador", "cargo", "str", "fecha_inicio"])
df_full = pd.DataFrame()
try:
    df_emp = cargar_empleados_activos()
    df_full, _ = cargar_datos()
except Exception:
    st.error("No se pudieron cargar los empleados desde la API.")
    if st.button("Reintentar"):
        st.cache_data.clear()
        st.rerun()
    st.stop()

# El cuestionario del resto del personal termina acá: de este punto para abajo
# todo es el de conductores.
if CUESTIONARIO == CUEST_GENERAL:
    _vista_general(df_emp)
    st.stop()

# ══════════════════════════════════════════════════════════════
# Cuestionario «Conductores» (2° mes)
# ══════════════════════════════════════════════════════════════
# Atrapa las dos grafías reales del padrón: CONDUCTORES y CONDUCTOR.
df_cond = df_emp[df_emp["cargo"].astype(str).str.startswith("CONDUCTOR", na=False)]
opciones_map = {
    f"{r['legajo']} — {r['apenom']}  ·  {r['empleador']}": r
    for _, r in df_cond.iterrows()
}
opciones_cond = list(opciones_map.keys())

try:
    df_seg = sg.calcular_indices(_leer())
except Exception:
    st.error("No se pudieron cargar las entrevistas. Revisá la conexión con la base.")
    if st.button("Reintentar", key="retry_db_sg"):
        _leer.clear()
        st.rerun()
    st.stop()

# ─── Filtros del listado ──────────────────────────────────────
# Los defaults viven en session_state y no en el `value=` del widget, por dos
# razones: el banner de alertas se dibuja ANTES que los filtros y necesita saber
# qué recorte está mirando el listado, y así puede además ampliarlos con un click.
_hoy = date.today()
st.session_state.setdefault("desde_sg", _hoy.replace(month=1, day=1))
st.session_state.setdefault("hasta_sg", _hoy)
st.session_state.setdefault("base_sg", "Todas")
st.session_state.setdefault("empleador_sg", "Todos")


def _filtrar(df):
    """El recorte que ve el listado. Una sola definición, para que el banner
    cuente exactamente sobre lo mismo que la lista de abajo."""
    out = df[(df["fecha_entrevista"] >= st.session_state["desde_sg"]) &
             (df["fecha_entrevista"] <= st.session_state["hasta_sg"])]
    if st.session_state["base_sg"] != "Todas":
        out = out[out["base"] == st.session_state["base_sg"]]
    if st.session_state["empleador_sg"] != "Todos":
        out = out[out["empleador"] == st.session_state["empleador_sg"]]
    return out


def _abrir_filtros(df_objetivo):
    """Amplía los filtros lo justo para que entren todas las filas de `df_objetivo`."""
    fechas = df_objetivo["fecha_entrevista"].dropna()
    if not fechas.empty:
        st.session_state["desde_sg"] = min(fechas.min(), st.session_state["desde_sg"])
        st.session_state["hasta_sg"] = max(fechas.max(), st.session_state["hasta_sg"])
    st.session_state["base_sg"] = "Todas"
    st.session_state["empleador_sg"] = "Todos"


# Alertas rojas de TODO el histórico vs. las que el listado está mostrando.
# El banner promete un número y manda al listado: si no coinciden, se pierde
# una queja de seguridad sin que nadie se entere.
ROJAS = df_seg[df_seg["nivel_alerta"] == "Roja"] if not df_seg.empty else df_seg

# El botón que amplía los filtros vive abajo, al lado de ellos, pero Streamlit no
# deja escribir la key de un widget ya instanciado. Así que el botón solo deja
# pedido el cambio y se aplica acá arriba, antes de que los widgets existan.
if st.session_state.pop("_abrir_rojas_sg", False) and len(ROJAS):
    _abrir_filtros(ROJAS)

ROJAS_OCULTAS = len(ROJAS) - len(_filtrar(ROJAS)) if len(ROJAS) else 0


def _texto_rojas_ocultas():
    plural = "s" if ROJAS_OCULTAS != 1 else ""
    return (f"{ROJAS_OCULTAS} alerta{plural} roja{plural} "
            f"queda{'n' if ROJAS_OCULTAS != 1 else ''} fuera de los filtros actuales.")


def _aviso_rojas_ocultas(key):
    """Avisa que hay rojas fuera de los filtros y ofrece traerlas.

    El botón va solo acá, junto a los filtros que modifica. El banner de arriba
    dice lo mismo sin botón: son la misma pantalla y dos botones idénticos a la
    vez es exactamente el tipo de ruido que este arreglo viene a sacar.
    """
    if not ROJAS_OCULTAS:
        return
    c_txt, c_btn = st.columns([9, 3], vertical_alignment="center")
    with c_txt:
        st.caption(_texto_rojas_ocultas())
    with c_btn:
        if st.button("Mostrar todas las rojas", key=key, width="stretch"):
            st.session_state["_abrir_rojas_sg"] = True
            st.rerun()


# El título y el subtítulo ya se dibujaron arriba, junto al selector de cuestionario.
# Banner de alertas rojas abiertas
if len(ROJAS):
    rojas = len(ROJAS)
    st.error(
        f"**{rojas} entrevista{'s' if rojas != 1 else ''} con alerta roja** — "
        "revisalas en la pestaña «Entrevistas cargadas»."
        + (f" {_texto_rojas_ocultas()}" if ROJAS_OCULTAS else "")
    )

tab_form, tab_carga, tab_ind = st.tabs(
    ["Nueva entrevista", "Entrevistas cargadas", "Indicadores"]
)

# ══════════════════════════════════════════════════════════════
# TAB 1 — Nueva entrevista
# ══════════════════════════════════════════════════════════════
with tab_form:
    # El formulario ocupa todo el ancho (se quitó el panel «Pendientes de
    # entrevista» que iba al costado).
    col_form = st.container()

    with col_form:
        if not PUEDE_EDITAR:
            st.markdown('<p class="section-label">Nueva entrevista</p>', unsafe_allow_html=True)
            st.caption("Modo solo lectura — no tenés permiso para registrar entrevistas.")
        else:
            st.markdown('<p class="section-label">Registrar entrevista</p>', unsafe_allow_html=True)

            if st.session_state.pop("saved_ok_sg", False):
                st.success(st.session_state.pop("saved_msg_sg", "✓ Entrevista registrada."))

            # El seed se bumpea SOLO tras guardar con éxito: cambia todas las keys,
            # los widgets vuelven a su default y el formulario queda limpio.
            # Nunca se usa clear_on_submit=True: borraría 20 minutos de
            # transcripción si falla una validación.
            seed = st.session_state.setdefault("sg_form_seed", 0)
            nombre_user = (current_user() or {}).get("nombre", "")

            with st.form("form_seguimiento", clear_on_submit=False):
                empleado_sel = st.selectbox(
                    "Conductor", options=opciones_cond, index=None,
                    placeholder="Escribí nombre, apellido o legajo para buscar...",
                    key=f"sg_emp_{seed}",
                )
                c1, c2 = st.columns(2)
                with c1:
                    fecha_entrevista = st.date_input(
                        "Fecha de la entrevista", value=date.today(), key=f"sg_fecha_{seed}")
                with c2:
                    entrevistador = st.text_input(
                        "Entrevistador", value=nombre_user, key=f"sg_entrev_{seed}")

                respuestas = {}
                slots = {}          # cod → hueco del enunciado, para repintarlo al validar
                for num_sec, nombre_sec in sg.SECCIONES.items():
                    _sec_head(f"{num_sec}. {nombre_sec}")
                    for p in [q for q in sg.PREGUNTAS if q["seccion"] == num_sec]:
                        slots[p["cod"]] = st.empty()
                        slots[p["cod"]].markdown(
                            _preg_html(p["n"], p["texto"]), unsafe_allow_html=True)
                        if p["tipo"] == "categoria":
                            respuestas[p["cod"]] = st.selectbox(
                                p["texto"], options=list(p["opciones"]), index=None,
                                placeholder="Seleccioná una opción...",
                                label_visibility="collapsed", key=f"sg_{p['cod']}_{seed}",
                            )
                        else:
                            respuestas[p["cod"]] = st.radio(
                                p["texto"], options=list(p["opciones"]), index=None,
                                horizontal=True, label_visibility="collapsed",
                                key=f"sg_{p['cod']}_{seed}",
                            )
                        if "texto_label" in p:
                            # Dentro de un st.form no hay rerun hasta el submit, así que
                            # el detalle se muestra siempre y la obligatoriedad de
                            # P9/P16 se valida al enviar.
                            respuestas[p["cod"] + "_texto"] = st.text_input(
                                p["texto_label"], key=f"sg_{p['cod']}_txt_{seed}",
                                placeholder="Detallar solo si corresponde"
                                if p["tipo"] == "flag" else "Textual de la respuesta",
                            )
                        # Observación del entrevistador, opcional, bajo cada pregunta.
                        respuestas[p["cod"] + "_obs"] = st.text_input(
                            "Observación", key=f"sg_{p['cod']}_obs_{seed}",
                            placeholder="Observación del entrevistador (opcional)",
                        )

                _sec_head("7. Autopercepción del conductor")
                st.caption("El conductor se evalúa a sí mismo en cada área.")
                for a in sg.AUTOEVAL:
                    slots[a["cod"]] = st.empty()
                    slots[a["cod"]].markdown(
                        _preg_html(a["letra"], a["texto"]), unsafe_allow_html=True)
                    respuestas[a["cod"]] = st.radio(
                        a["texto"], options=list(a["opciones"]), index=None,
                        horizontal=True, label_visibility="collapsed",
                        key=f"sg_{a['cod']}_{seed}",
                    )

                _sec_head("8. Conclusión")
                fortalezas = st.text_area(
                    "Fortalezas identificadas", max_chars=1000, height=90,
                    key=f"sg_fort_{seed}")
                aspectos = st.text_area(
                    "Aspectos a mejorar", max_chars=1000, height=90,
                    key=f"sg_asp_{seed}")
                compromisos = st.text_area(
                    "Compromisos / acciones acordadas", max_chars=1000, height=90,
                    key=f"sg_comp_{seed}")
                frases = st.text_area(
                    "Frases destacadas del conductor", max_chars=1000, height=90,
                    placeholder="Opcional — citas textuales que valga la pena conservar",
                    key=f"sg_frases_{seed}")
                fecha_prox = st.date_input(
                    "Fecha de próximo seguimiento", value=None, key=f"sg_prox_{seed}")

                # Marcador que solo existe mientras se muestra ESTE formulario:
                # ancla la guarda de salida a esta pantalla (ver _guardia_salida).
                st.markdown('<span id="sg-guard-marker"></span>', unsafe_allow_html=True)
                st.caption("No cierres la pestaña ni cambies de cuestionario hasta "
                           "guardar la entrevista.")
                submitted = st.form_submit_button("Registrar entrevista")

            # Red de contención de B0: avisa si se recarga/cierra con el form a
            # medio llenar (un reload borra la sesión y toda la transcripción).
            _guardia_salida()

            # ── Validación (fuera del form, como el resto del dashboard) ──
            if submitted:
                faltan_cab, faltan_preg, faltan_auto, faltan_txt = [], [], [], []
                marcar = []     # cods a repintar en rojo arriba
                if not empleado_sel:
                    faltan_cab.append("el conductor")
                if not (entrevistador or "").strip():
                    faltan_cab.append("el entrevistador")
                if not fecha_entrevista:
                    faltan_cab.append("la fecha de la entrevista")

                for p in sg.PREGUNTAS:
                    if respuestas.get(p["cod"]) is None:
                        faltan_preg.append(str(p["n"]))
                        marcar.append(p["cod"])
                for a in sg.AUTOEVAL:
                    if respuestas.get(a["cod"]) is None:
                        faltan_auto.append(a["corto"])
                        marcar.append(a["cod"])
                for p in sg.FLAGS:
                    if respuestas.get(p["cod"]) == "Sí" and \
                            not (respuestas.get(p["cod"] + "_texto") or "").strip():
                        faltan_txt.append(str(p["n"]))
                        marcar.append(p["cod"])

                # Un solo error con todo lo que falta: con 24 respuestas obligatorias,
                # avisar de a una sería un ida y vuelta interminable.
                if faltan_cab or faltan_preg or faltan_auto or faltan_txt:
                    # Repintar los enunciados que faltan, en su hueco original.
                    # El mensaje de abajo dice cuántos son; el color dice dónde están.
                    for cod in marcar:
                        p = MAPA_PREG.get(cod)
                        if p and cod in slots:
                            slots[cod].markdown(
                                _preg_html(p[0], p[1], falta=True), unsafe_allow_html=True)

                    partes = []
                    if faltan_cab:
                        partes.append("Falta completar " + ", ".join(faltan_cab) + ".")
                    if faltan_preg:
                        partes.append(
                            f"Faltan {len(faltan_preg)} respuesta"
                            f"{'s' if len(faltan_preg) != 1 else ''} — "
                            "quedaron marcadas en rojo más arriba: preguntas "
                            + ", ".join(faltan_preg) + ".")
                    if faltan_auto:
                        partes.append("Falta la autopercepción de: " + ", ".join(faltan_auto) + ".")
                    if faltan_txt:
                        plural = len(faltan_txt) != 1
                        partes.append(
                            f"Respondiste «Sí» en {' y '.join(faltan_txt)}: "
                            f"tenés que detallar {'cuáles' if plural else 'cuál'}.")
                    st.error(" ".join(partes))
                else:
                    r = opciones_map.get(empleado_sel)
                    if r is None:
                        st.error("No se encontró el conductor. Intentá de nuevo.")
                    else:
                        payload = {
                            "legajo": str(r["legajo"]).strip(),
                            "apenom": r["apenom"],
                            "empleador": r["empleador"],
                            "base": (r.get("str") or "") or None,
                            "cargo": r.get("cargo"),
                            "fecha_ingreso": r["fecha_inicio"].isoformat()
                                             if pd.notna(r.get("fecha_inicio")) else None,
                            "fecha_entrevista": fecha_entrevista.isoformat(),
                            "entrevistador": entrevistador.strip(),
                            "fecha_proximo_seguimiento": fecha_prox.isoformat() if fecha_prox else None,
                            "registrado_por": nombre_user,
                            "fortalezas": fortalezas.strip() or None,
                            "aspectos_mejorar": aspectos.strip() or None,
                            "compromisos": compromisos.strip() or None,
                            "frases_destacadas": frases.strip() or None,
                        }
                        # Se guarda el CÓDIGO, nunca la etiqueta del radio.
                        for p in sg.PREGUNTAS:
                            payload[p["cod"]] = sg.codigo(p, respuestas.get(p["cod"]))
                            if "texto_label" in p:
                                txt = (respuestas.get(p["cod"] + "_texto") or "").strip()
                                payload[p["cod"] + "_texto"] = txt or None
                            obs = (respuestas.get(p["cod"] + "_obs") or "").strip()
                            payload[p["cod"] + "_obs"] = obs or None
                        for a in sg.AUTOEVAL:
                            payload[a["cod"]] = sg.codigo(a, respuestas.get(a["cod"]))

                        try:
                            _guardar(payload)
                        except Exception as e:
                            if "23505" in str(e) or "duplicate key" in str(e).lower():
                                st.error(
                                    "Ya hay una entrevista cargada para ese conductor con esa fecha. "
                                    "Si es un seguimiento posterior, cambiá la fecha de la entrevista.")
                            else:
                                st.error("No se pudo registrar la entrevista. Intentá de nuevo.")
                        else:
                            _leer.clear()
                            st.session_state["saved_ok_sg"] = True
                            st.session_state["saved_msg_sg"] = (
                                f"✓ Entrevista registrada — **{r['apenom']}** · "
                                f"{fecha_entrevista.strftime('%d/%m/%Y')}")
                            st.session_state["sg_form_seed"] = seed + 1
                            st.rerun()

# ══════════════════════════════════════════════════════════════
# TAB 2 — Entrevistas cargadas
# ══════════════════════════════════════════════════════════════
with tab_carga:
    if df_seg.empty:
        st.info("Todavía no hay entrevistas cargadas.")

    # ══ Vista ampliada de una entrevista ══
    elif st.session_state.get("ver_id_sg") is not None and \
            (df_seg["id"] == st.session_state["ver_id_sg"]).any():
        fila = df_seg[df_seg["id"] == st.session_state["ver_id_sg"]].iloc[0]

        c_volver, c_desc = st.columns([1, 3])
        with c_volver:
            if st.button("←  Volver al listado", key="btn_volver_sg",
                         width="stretch"):
                st.session_state.pop("ver_id_sg", None)
                # Nueva key para el dataframe: si no, la selección vieja
                # volvería a abrir esta misma entrevista al instante.
                st.session_state["tabla_seed_sg"] = \
                    st.session_state.get("tabla_seed_sg", 0) + 1
                st.rerun()
        with c_desc:
            if st.download_button(
                "⬇  Descargar esta entrevista (Excel)",
                data=sg.exportar_excel(fila.to_frame().T, incluir_textos=PUEDE_EDITAR),
                file_name=(f"entrevista_{fila['legajo']}_"
                           f"{fila['fecha_entrevista'].strftime('%d-%m-%Y')}.xlsx"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_una_sg",
            ):
                auditoria.registrar(
                    "seguimiento", "export",
                    f"Descargó la entrevista de {fila['apenom']} (leg. {fila['legajo']})"
                    + (" — con textuales" if PUEDE_EDITAR else " — sin textuales"),
                    registro_id=fila["id"],
                )

        _render_detalle(fila, incluir_textos=PUEDE_EDITAR)

    # ══ Listado ══
    else:
        st.session_state.pop("ver_id_sg", None)
        f1, f2, f3, f4 = st.columns([2, 2, 2, 2], gap="medium")
        # Sin `value=` / `index=`: el default lo pone session_state más arriba,
        # así el botón «Mostrar todas las rojas» puede reescribirlo.
        with f1:
            desde = st.date_input("Desde", key="desde_sg")
        with f2:
            hasta = st.date_input("Hasta", key="hasta_sg")
        with f3:
            bases = ["Todas"] + sorted(
                b for b in df_seg["base"].dropna().unique() if str(b).strip())
            base_sel = st.selectbox("Base", options=bases, key="base_sg")
        with f4:
            emps = ["Todos"] + sorted(df_seg["empleador"].dropna().unique())
            emp_sel = st.selectbox("Empleador", options=emps, key="empleador_sg")

        f = _filtrar(df_seg).copy()

        if f.empty:
            # Un listado vacío tiene tres causas muy distintas y antes las tres
            # daban el mismo mensaje. Si no se distinguen, Lu no sabe si el
            # período está vacío de verdad o si se equivocó tipeando una fecha.
            if desde > hasta:
                st.warning(
                    f"El «Desde» ({desde.strftime('%d/%m/%Y')}) es posterior al «Hasta» "
                    f"({hasta.strftime('%d/%m/%Y')}): el período está invertido."
                )
            elif base_sel != "Todas" or emp_sel != "Todos":
                activos = " y ".join(
                    x for x in (f"base «{base_sel}»" if base_sel != "Todas" else "",
                                f"empleador «{emp_sel}»" if emp_sel != "Todos" else "") if x)
                st.info(
                    f"No hay entrevistas entre el {desde.strftime('%d/%m/%Y')} y el "
                    f"{hasta.strftime('%d/%m/%Y')} con {activos}."
                )
            else:
                st.info(
                    f"No hay entrevistas cargadas entre el {desde.strftime('%d/%m/%Y')} "
                    f"y el {hasta.strftime('%d/%m/%Y')}."
                )
            _aviso_rojas_ocultas("btn_rojas_vacio")
        else:
            # ── Alertas primero: con este volumen, son el producto ──
            alertas = sg.detectar_alertas(f)
            st.markdown('<p class="section-label">Alertas</p>', unsafe_allow_html=True)
            _aviso_rojas_ocultas("btn_rojas_listado")
            if alertas.empty:
                st.success("✓ Ninguna entrevista del período disparó alertas.")
            else:
                def _fila_alerta(a):
                    clase = "alert-row" if a["nivel_alerta"] == "Roja" else "alert-row amber"
                    fecha_txt = a["fecha_entrevista"].strftime("%d/%m/%Y") \
                        if pd.notna(a["fecha_entrevista"]) else "—"
                    motivos = " · ".join(a["motivos_alerta"])
                    quote = ""
                    if PUEDE_EDITAR:
                        textos = [t for t in (a.get("p09_texto"), a.get("p16_texto"))
                                  if t and str(t).strip()]
                        if textos:
                            quote = ('<div class="alert-quote">"'
                                     + '" · "'.join(str(t).strip() for t in textos) + '"</div>')
                    c_txt, c_btn = st.columns([9, 2], vertical_alignment="center")
                    with c_txt:
                        st.markdown(
                            f'<div class="{clase}">'
                            f'<div class="alert-name">{a["apenom"]} · Legajo {a["legajo"]}</div>'
                            f'<div class="alert-meta">{a["base"] or "Sin base"} · {fecha_txt} · '
                            f'Índice {_fmt(a["indice_general"])} · {motivos}</div>'
                            f'{quote}</div>',
                            unsafe_allow_html=True,
                        )
                    with c_btn:
                        if st.button("Ver entrevista", key=f"ver_al_{a['id']}",
                                     width="stretch"):
                            st.session_state["ver_id_sg"] = a["id"]
                            _auditar_apertura(a)
                            st.rerun()

                # Rojas y atención no son lo mismo y antes se mezclaban en una
                # sola tira. Las rojas van siempre desplegadas —esconder una es
                # exactamente el bug C1—; las de atención van plegadas, con el
                # número en el título para que se sepa que están.
                rojas_f = alertas[alertas["nivel_alerta"] == "Roja"]
                atencion_f = alertas[alertas["nivel_alerta"] != "Roja"]

                if not rojas_f.empty:
                    st.caption(
                        f"**{len(rojas_f)}** para revisar ya "
                        "— seguridad, capacitación o el conductor no recomendaría la empresa."
                    )
                    for _, a in rojas_f.iterrows():
                        _fila_alerta(a)

                if not atencion_f.empty:
                    with st.expander(
                            f"Atención ({len(atencion_f)}) — revisar cuando puedas"):
                        for _, a in atencion_f.iterrows():
                            _fila_alerta(a)

                if not PUEDE_EDITAR:
                    st.caption(
                        "Las respuestas textuales son confidenciales y solo las ve "
                        "quien tiene permiso de carga en esta sección.")

            st.divider()
            st.markdown('<p class="section-label">Entrevistas del período</p>', unsafe_allow_html=True)

            vista = pd.DataFrame({
                "Legajo": f["legajo"],
                "Nombre": f["apenom"],
                "Base": f["base"].fillna("—"),
                "Fecha": f["fecha_entrevista"].apply(
                    lambda d: d.strftime("%d/%m/%Y") if pd.notna(d) else "—"),
                "Índice": pd.to_numeric(f["indice_general"], errors="coerce").round(1),
                "Autopercepción": pd.to_numeric(f["indice_autopercepcion"], errors="coerce").round(1),
                "Alerta": f["nivel_alerta"].replace("", "—"),
                "Entrevistador": f["entrevistador"],
            })
            evento = st.dataframe(
                vista, width="stretch", hide_index=True,
                on_select="rerun", selection_mode="single-row",
                key=f"tabla_sg_{st.session_state.get('tabla_seed_sg', 0)}",
            )
            st.caption("Hacé clic en una fila para abrir la entrevista completa.")

            # DataframeState es un TypedDict: el acceso por clave es el tipo real,
            # el .selection por atributo depende del wrapper que agrega Streamlit.
            filas_sel = list((evento or {}).get("selection", {}).get("rows", []))
            if filas_sel:
                st.session_state["ver_id_sg"] = f.iloc[filas_sel[0]]["id"]
                _auditar_apertura(f.iloc[filas_sel[0]])
                st.rerun()

            if st.download_button(
                "⬇  Descargar entrevistas (Excel)",
                data=sg.exportar_excel(f, incluir_textos=PUEDE_EDITAR),
                file_name=(f"seguimiento_conductores_{desde.strftime('%d-%m-%Y')}"
                           f"_a_{hasta.strftime('%d-%m-%Y')}.xlsx"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ):
                auditoria.registrar(
                    "seguimiento", "export",
                    f"Descargó {len(f)} entrevista(s) del "
                    f"{desde.strftime('%d/%m/%Y')} al {hasta.strftime('%d/%m/%Y')}"
                    + (" — con textuales" if PUEDE_EDITAR else " — sin textuales"),
                    datos={"registros": int(len(f))},
                )

        # ── Eliminar ──
        if PUEDE_EDITAR:
            st.divider()
            if st.session_state.pop("deleted_ok_sg", False):
                st.success("Entrevista eliminada correctamente.")
            with st.expander("Eliminar una entrevista"):
                labels = {
                    f"{r['apenom']} · {r['fecha_entrevista'].strftime('%d/%m/%Y')} "
                    f"· Legajo {r['legajo']}": r["id"]
                    for _, r in df_seg.iterrows() if pd.notna(r["fecha_entrevista"])
                }
                if not labels:
                    st.caption("No hay entrevistas para eliminar.")
                else:
                    elegido = st.selectbox("Entrevista", options=list(labels.keys()),
                                           index=None, placeholder="Seleccioná una entrevista...",
                                           key="del_sel_sg")
                    if st.button("Eliminar entrevista", key="btn_del_sg") and elegido:
                        st.session_state["del_id_sg"] = labels[elegido]
                        st.session_state["del_label_sg"] = elegido
                        st.rerun()

                    if "del_id_sg" in st.session_state:
                        st.warning(
                            f"¿Eliminar **{st.session_state['del_label_sg']}**? "
                            "Esta acción no se puede deshacer.")
                        c1, c2 = st.columns([1, 1])
                        with c1:
                            if st.button("Sí, eliminar", key="btn_confirm_sg"):
                                try:
                                    _eliminar(st.session_state["del_id_sg"],
                                              st.session_state.get("del_label_sg", ""))
                                    st.session_state["deleted_ok_sg"] = True
                                except Exception:
                                    st.error("No se pudo eliminar la entrevista.")
                                st.session_state.pop("del_id_sg", None)
                                st.session_state.pop("del_label_sg", None)
                                _leer.clear()
                                st.rerun()
                        with c2:
                            if st.button("Cancelar", key="btn_cancel_sg"):
                                st.session_state.pop("del_id_sg", None)
                                st.session_state.pop("del_label_sg", None)
                                st.rerun()

# ══════════════════════════════════════════════════════════════
# TAB 3 — Indicadores (agregado, sin nombres)
# ══════════════════════════════════════════════════════════════
with tab_ind:
    if df_seg.empty:
        st.info("Todavía no hay entrevistas cargadas para calcular indicadores.")
    else:
        kpis = sg.resumen_kpis(df_seg, df_full)
        _, color_ind = sg.banda(kpis["indice_general"])
        _, color_auto = sg.banda(kpis["autopercepcion"])
        etiqueta_banda, _ = sg.banda(kpis["indice_general"])

        st.markdown(
            '<div class="kpi6">'
            + _kpi_card("Entrevistas", _fmt(kpis["entrevistas"]), "cargadas en total")
            + _kpi_card("Cobertura", _fmt(kpis["cobertura"], "%"),
                        f"últimos {sg.MESES_COHORTE} meses", COLOR_SECONDARY)
            + _kpi_card("Índice general", _fmt(kpis["indice_general"], "", 1),
                        etiqueta_banda, color_ind)
            + _kpi_card("Autopercepción", _fmt(kpis["autopercepcion"], "", 1),
                        "cómo se ve el conductor", color_auto)
            + _kpi_card("Recomendarían", _fmt(kpis["recomiendan"], "%"),
                        "responden que sí", COLOR_SECONDARY)
            + _kpi_card("Con alerta", _fmt(kpis["alertas"]),
                        _fmt(kpis["pct_alertas"], "% del total"), "#D12F19")
            + '</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Índices de 0 a 100 sobre la escala 1–4 del formulario "
            "(Mala=1 · Regular=2 · Buena=3 · Muy buena=4). "
            f"**{sg.REFERENCIA_BUENA:.0f} equivale a responder «Buena» en todo.**")

        st.divider()

        # ── 1. Índice por dimensión ──
        st.markdown('<p class="section-label">Índice por dimensión</p>', unsafe_allow_html=True)
        dims = sg.resumen_dimensiones(df_seg).dropna(subset=["indice"])
        if dims.empty:
            st.info("Todavía no hay respuestas suficientes para calcular los índices.")
        else:
            dims = dims.sort_values("indice")
            etiquetas = [
                f"{r['nombre']}  (n={int(r['n_items'])} ítem{'s' if r['n_items'] > 1 else ''})"
                for _, r in dims.iterrows()
            ]
            colores = [sg.banda(v)[1] for v in dims["indice"]]
            fig = go.Figure(go.Bar(
                x=dims["indice"], y=etiquetas, orientation="h",
                marker_color=colores,
                text=[f"{v:.1f}" for v in dims["indice"]],
                textposition="outside",
                hovertemplate="%{y}<br>Índice: %{x:.1f}<extra></extra>",
            ))
            fig.add_vline(
                x=sg.REFERENCIA_BUENA, line_dash="dot", line_color="#8C8987",
                annotation_text="Referencia: todo «Buena»",
                annotation_position="top",
                annotation_font=dict(size=11, color="#8C8987"),
            )
            fig.update_layout(**chart_base(
                height=60 + 46 * len(dims), showlegend=False,
                xaxis=dict(range=[0, 112], showgrid=True, gridcolor="#E8E8E8",
                           zeroline=False, linecolor="#CCCCCC",
                           tickfont=dict(color="#8C8987")),
                yaxis=dict(showgrid=False, zeroline=False, linecolor="#CCCCCC",
                           tickfont=dict(color="#8C8987")),
                margin=dict(l=10, r=40, t=30, b=10),
            ))
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                "Las dos últimas filas son ítems sueltos, no índices: un promedio "
                "de una sola pregunta es la pregunta con decimales.")

        st.divider()

        # ── 2. Distribución por ítem (ranking + distribución en un solo gráfico) ──
        st.markdown('<p class="section-label">Respuestas por pregunta</p>', unsafe_allow_html=True)
        dist = sg.distribucion_items(df_seg)
        if dist.empty:
            st.info("Todavía no hay respuestas cerradas cargadas.")
        else:
            orden = dist.drop_duplicates("cod").sort_values("media", ascending=False)
            y_orden = [f"{sg.POR_COD[c]['n']}. {sg.POR_COD[c]['corto']}" for c in orden["cod"]]
            colores_valor = {1: "#D12F19", 2: "#B45309", 3: COLOR_SECONDARY, 4: "#15803D"}
            fig = go.Figure()
            for valor in (1, 2, 3, 4):
                sub = dist[dist["valor"] == valor].set_index("cod").reindex(orden["cod"])
                fig.add_trace(go.Bar(
                    y=y_orden, x=sub["pct"], orientation="h",
                    name=f"{valor} · {'Muy buena' if valor == 4 else 'Buena' if valor == 3 else 'Regular' if valor == 2 else 'Mala'}",
                    marker_color=colores_valor[valor],
                    customdata=sub[["n", "etiqueta"]].values,
                    hovertemplate="%{y}<br>%{customdata[1]}: %{customdata[0]} (%{x:.0f}%)<extra></extra>",
                ))
            fig.update_layout(**chart_base(
                barmode="stack", height=90 + 34 * len(y_orden),
                xaxis=dict(range=[0, 100], ticksuffix="%", showgrid=False,
                           zeroline=False, linecolor="#CCCCCC",
                           tickfont=dict(color="#8C8987")),
                yaxis=dict(showgrid=False, zeroline=False, linecolor="#CCCCCC",
                           tickfont=dict(color="#8C8987", size=11)),
                legend=dict(orientation="h", yanchor="bottom", y=-0.12,
                            xanchor="center", x=0.5),
                margin=dict(l=10, r=10, t=10, b=10),
            ))
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Ordenado de peor a mejor: arriba, las preguntas con menor promedio.")

        st.divider()

        # ── 3. Categorías ──
        st.markdown('<p class="section-label">Qué dicen los conductores</p>', unsafe_allow_html=True)
        opciones_cat = {f"{p['n']}. {p['corto']}": p["cod"] for p in sg.CATEGORIAS}
        cat_label = st.radio("Pregunta", options=list(opciones_cat.keys()),
                             horizontal=True, label_visibility="collapsed", key="cat_sg")
        frec = sg.frecuencia_categoria(df_seg, opciones_cat[cat_label])
        if frec.empty:
            st.info("Todavía no hay respuestas cargadas para esta pregunta.")
        else:
            fig = go.Figure(go.Bar(
                x=frec["n"], y=frec["categoria"], orientation="h",
                marker_color=COLOR_PRIMARY,
                text=[f"{n}  ({p:.0f}%)" for n, p in zip(frec["n"], frec["pct"])],
                textposition="outside",
                hovertemplate="%{y}<br>%{x} respuestas<extra></extra>",
            ))
            fig.update_layout(**chart_base(
                height=80 + 32 * len(frec), showlegend=False,
                xaxis=dict(showgrid=True, gridcolor="#E8E8E8", zeroline=False,
                           linecolor="#CCCCCC", tickfont=dict(color="#8C8987"),
                           range=[0, max(frec["n"]) * 1.35]),
                yaxis=dict(showgrid=False, zeroline=False, linecolor="#CCCCCC",
                           tickfont=dict(color="#8C8987")),
                margin=dict(l=10, r=30, t=10, b=10),
            ))
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                "«Lo que menos gusta» y «qué cambiaría» miden lo mismo desde ángulos "
                "distintos: lo interesante es dónde no coinciden.")

        st.divider()

        # ── 4. Corte por base y cobertura por cohorte ──
        c_base, c_coh = st.columns(2, gap="large")

        with c_base:
            st.markdown('<p class="section-label">Índice por base</p>', unsafe_allow_html=True)
            tabla_base, excluidas = sg.corte_por_base(df_seg)
            if tabla_base.empty:
                st.info(
                    f"Ninguna base llega todavía a {sg.MIN_N_CORTE} entrevistas.")
            else:
                vista_base = pd.DataFrame({
                    "Base": tabla_base["base"],
                    "Entrevistas": tabla_base["n"],
                    "Índice": tabla_base["indice"].round(1),
                })
                st.dataframe(vista_base, width="stretch", hide_index=True)
            if excluidas:
                st.caption(
                    f"Solo se muestran bases con {sg.MIN_N_CORTE} o más entrevistas. "
                    f"Quedan fuera: {', '.join(excluidas)}.")

        with c_coh:
            st.markdown('<p class="section-label">Cobertura por mes de ingreso</p>',
                        unsafe_allow_html=True)
            cob = sg.cobertura_cohorte(df_full, df_seg)
            if cob.empty:
                st.info("Todavía no hay cohortes con antigüedad suficiente.")
            else:
                vista_cob = pd.DataFrame({
                    "Mes": cob["mes"],
                    "Ingresos": cob["ingresos"],
                    "Entrevistados": cob["entrevistados"],
                    "Cobertura": cob["cobertura"].round(0),
                    "Índice": cob["indice"].round(1),
                })
                st.dataframe(
                    vista_cob, width="stretch", hide_index=True,
                    column_config={"Cobertura": st.column_config.NumberColumn(
                        "Cobertura", format="%d%%")},
                )
                st.caption(
                    "El denominador incluye a quienes ya se dieron de baja: si no, "
                    "un conductor que renunció sin entrevista inflaría la cobertura.")
