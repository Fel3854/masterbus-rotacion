"""Vista: Postulantes — consulta del registro de entrevistas (FORM 045 02)."""

import html
import os
import sys
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from auth import puede_ver_postulantes, current_user  # noqa: E402
from utils import (inyectar_css_base, get_supabase, chart_base,  # noqa: E402
                   cargar_empleados_cruce,
                   COLOR_PRIMARY, COLOR_TEXT, COLOR_MUTED, COLOR_BORDER)
import auditoria  # noqa: E402
import postulantes as pt  # noqa: E402

_esc = html.escape

COLOR_NEUTRO, COLOR_NEUTRO_BG = "#333333", "#F4F4F4"
COLOR_OK, COLOR_OK_BG = "#166534", "#DCFCE7"
COLOR_AVISO, COLOR_AVISO_BG = "#B45309", "#FEF3C7"
COLOR_ALERTA, COLOR_ALERTA_BG = "#B91C1C", "#FEE2E2"

MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

SOLO_APTOS = "Marcados aptos"
SOLO_NOTAS = "Con notas"
SOLO_REPETIDOS = "Se presentó más de una vez"
SOLO_LEGAJO = "Ingresó (con legajo)"
SOLO_REVISAR = "DNI a revisar"

LEYENDA_APTO = (
    "«Apto ✓» significa que la casilla estaba tildada en Access. **Sin tilde no "
    "quiere decir rechazado**: desde 2023 la casilla casi no se usa y el "
    "resultado de la entrevista está en las notas.")


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
    font-family: 'Fira Code', monospace; font-size: 2.1rem; font-weight: 700;
    line-height: 1; color: var(--card-color, #333);
}
.kpi-sub { font-size: 0.74rem; color: #777; margin-top: 4px; }

.ficha { border-left: 4px solid var(--accent, #ED5D3B); padding-left: 14px; }
.ficha-nombre { font-size: 1.15rem; font-weight: 700; color: #1a1a1a; }
.ficha-meta { font-size: 0.85rem; color: #555; margin-top: 4px; line-height: 1.5; }
.ficha-chip {
    display: inline-block; font-size: 0.72rem; font-weight: 800;
    padding: 2px 11px; border-radius: 12px; margin-left: 8px; vertical-align: middle;
    background: var(--chip-bg, #eee); color: var(--chip-fg, #333);
    border: 1.5px solid var(--chip-fg, #ccc);
}
.ficha-rotulo {
    font-size: 0.68rem; font-weight: 800; letter-spacing: 0.6px;
    text-transform: uppercase; color: #8C8987; margin-top: 12px;
}
.ficha-texto { font-size: 0.95rem; color: #1a1a1a; white-space: pre-wrap; }
.ficha-vacio { font-size: 0.95rem; color: #999; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="page-header">
  <div class="bar"></div>
  <h1>Postulantes</h1>
</div>
""", unsafe_allow_html=True)
st.caption("Registro de entrevistas a postulantes (FORM 045 02). "
           "Buscá una persona o filtrá el histórico.")

# La página está fuera de la navegación para quien no tiene el permiso, pero
# igual se corta acá, antes de leer nada: una URL directa no puede saltear el
# control.
if not puede_ver_postulantes():
    st.error("No tenés permiso para ver el registro de postulantes.")
    st.stop()


# ─── Datos ────────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner="Cargando el registro de postulantes…")
def _leer() -> tuple:
    """(registro, legajos_ok): todo el registro, enriquecido y cruzado con el padrón.

    Son pocos miles de filas: entran en memoria y se filtran en pandas. El caché
    se invalida con `_leer.clear()` sin volar el de la API de empleados. Sólo se
    llama después del chequeo de permiso de arriba.

    El legajo es un agregado: si la API de empleados no responde, la consulta
    sigue andando con la columna vacía y `legajos_ok` en False.
    """
    registro = pt.enriquecer(pt.leer_todo(get_supabase()))
    try:
        empleados = pt.preparar_empleados(cargar_empleados_cruce())
    except Exception:  # noqa: BLE001 — sin el padrón sólo falta el legajo
        empleados = None
    hay_padron = empleados is not None and not empleados.empty
    return pt.cruzar_legajos(registro, empleados), hay_padron


@st.cache_data(max_entries=2, show_spinner="Leyendo el archivo…")
def _leer_subido(nombre: str, contenido: bytes) -> pd.DataFrame:
    """El archivo subido, ya normalizado. En caché para no releerlo en cada rerun."""
    return pt.normalizar_archivo(pt.leer_archivo(nombre, contenido))


@st.cache_data(ttl=600, max_entries=4, show_spinner=False)
def _excel(numeros: tuple, version: str) -> bytes:
    """El Excel de un recorte. En caché: armarlo en cada rerun frena la búsqueda.

    `version` cambia cuando se actualiza el registro: sin ella, tras una carga
    el botón seguiría bajando el Excel viejo de ese mismo recorte. El
    vencimiento es por el legajo, que puede cambiar en el padrón sin que cambie
    nada del registro.
    """
    df, _legajos_ok = _leer()
    return pt.exportar_excel(df[df["numero_orden"].isin(numeros)])


# ─── Formato ──────────────────────────────────────────────────
def _fecha(d) -> str:
    f = pt.to_date(d)
    return f.strftime("%d/%m/%Y") if f else "sin fecha"


def _miles(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def _plural(n, singular, plural=None) -> str:
    return f"{_miles(n)} {singular if n == 1 else (plural or singular + 's')}"


def _tarjeta(col, label, valor, sub="", color=COLOR_NEUTRO, fondo=COLOR_NEUTRO_BG):
    with col:
        st.markdown(
            f'<div class="kpi-card" style="--card-color:{color}; --card-bg:{fondo};">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{valor}</div>'
            f'<div class="kpi-sub">{sub}</div></div>',
            unsafe_allow_html=True)


def _seccion(texto: str) -> None:
    st.markdown(f'<div class="section-header"><div class="bar"></div>'
                f'<span>{texto}</span></div>', unsafe_allow_html=True)


def _tabla(f: pd.DataFrame, con_persona=True) -> pd.DataFrame:
    """Las columnas que se muestran de una lista de entrevistas."""
    vista = pd.DataFrame({"Nº": f["numero_orden"],
                          "Fecha": pd.to_datetime(f["fecha"], errors="coerce")})
    if con_persona:
        vista["Apellido y nombre"] = f["apenom"]
        vista["DNI"] = f["dni"]
        # Sólo en lo que viene del registro: una vista previa de importación
        # todavía no está cruzada con el padrón.
        if "legajo" in f.columns:
            vista["Legajo"] = f["legajo"]
    vista["Puesto"] = f["puesto"]
    vista["Sector"] = f["sector"]
    vista["Apto"] = f["apto"].map({True: "✓", False: ""})
    vista["Motivo"] = f["motivo_rechazo"]
    vista["Observaciones"] = f["observaciones"]
    vista["Entrevistador"] = f["entrevistador_norm"]
    if con_persona:
        vista["Veces"] = f["veces"].map(lambda v: f"×{v}" if v > 1 else "")
    return vista


def _config(vista: pd.DataFrame) -> dict:
    """La configuración de columnas, sólo para las que la tabla realmente tiene."""
    return {k: v for k, v in COLUMNAS_TABLA.items() if k in vista.columns}


COLUMNAS_TABLA = {
    "Nº": st.column_config.NumberColumn(format="%d", width="small"),
    "Fecha": st.column_config.DateColumn(format="DD/MM/YYYY", width="small"),
    "DNI": st.column_config.NumberColumn(format="%d", width="small"),
    "Legajo": st.column_config.TextColumn(
        width="small",
        help="Legajo en MasterBus si la persona ingresó: mismo DNI y apellido en el "
             "padrón de empleados. Vacío = no figura como empleado, o no tiene DNI."),
    "Apto": st.column_config.TextColumn(
        width="small", help="✓ = casilla tildada en Access. Vacío = sin marcar, no rechazado."),
    "Motivo": st.column_config.TextColumn(width="medium"),
    "Observaciones": st.column_config.TextColumn(width="medium"),
    "Veces": st.column_config.TextColumn(
        width="small", help="Cuántas entrevistas tiene esa persona (mismo DNI)."),
}


# ─── Ficha de una entrevista ──────────────────────────────────
def _render_ficha(df: pd.DataFrame, numero: int) -> None:
    fila = df[df["numero_orden"] == numero].iloc[0]

    chips = ""
    if bool(fila["apto"]):
        chips += (f'<span class="ficha-chip" style="--chip-bg:{COLOR_OK_BG}; '
                  f'--chip-fg:{COLOR_OK};">Apto ✓</span>')
    if int(fila["veces"]) > 1:
        chips += (f'<span class="ficha-chip" style="--chip-bg:{COLOR_AVISO_BG}; '
                  f'--chip-fg:{COLOR_AVISO};">Se presentó {int(fila["veces"])} veces</span>')

    empleo = ""
    if fila["legajo"]:
        if bool(fila["legajo_activo"]):
            situacion, tono, fondo = "Activo", COLOR_OK, COLOR_OK_BG
        else:
            baja = pt.to_date(fila["legajo_baja"])
            situacion = f"Baja {baja:%d/%m/%Y}" if baja else "Baja"
            tono, fondo = COLOR_NEUTRO, COLOR_NEUTRO_BG
        chips += (f'<span class="ficha-chip" style="--chip-bg:{fondo}; --chip-fg:{tono};">'
                  f'Legajo {_esc(str(fila["legajo"]))} · {situacion}</span>')
        # El legajo es de la persona, no de esta entrevista: la fecha de
        # ingreso al lado deja ver si entró por ésta o en otro momento.
        ingreso = pt.to_date(fila["legajo_ingreso"])
        entrevista = pt.to_date(fila["fecha"])
        entrada = f"Ingresó el {ingreso:%d/%m/%Y}" if ingreso else "Ingresó (sin fecha en el padrón)"
        if ingreso and entrevista and ingreso < entrevista:
            entrada += ", antes de esta entrevista"
        empleo = "<br>" + _esc(" · ".join(
            x for x in (entrada, str(fila["legajo_empleador"])) if x))

    dni = "sin DNI" if pd.isna(fila["dni"]) else f"DNI {_miles(fila['dni'])}"
    datos = [f"Nº {int(fila['numero_orden'])}", _fecha(fila["fecha"]), dni]
    lugar = " · ".join(x for x in (fila["puesto"], fila["sector"]) if x)
    entrevisto = fila["entrevistador_norm"] or "sin dato"

    def _bloque(rotulo, texto):
        cuerpo = (f'<div class="ficha-texto">{_esc(texto)}</div>' if texto
                  else '<div class="ficha-vacio">—</div>')
        return f'<div class="ficha-rotulo">{rotulo}</div>{cuerpo}'

    with st.container(border=True):
        st.markdown(
            f'<div class="ficha">'
            f'<div><span class="ficha-nombre">{_esc(fila["apenom"] or "(sin nombre)")}</span>'
            f'{chips}</div>'
            f'<div class="ficha-meta">{_esc(" · ".join(datos))}<br>'
            f'{_esc(lugar or "Sin puesto ni sector cargados")}'
            f' · Entrevistó: {_esc(entrevisto)}{empleo}</div>'
            f'{_bloque(pt.ENCABEZADO["motivo_rechazo"], fila["motivo_rechazo"])}'
            f'{_bloque(pt.ENCABEZADO["observaciones"], fila["observaciones"])}'
            f'</div>', unsafe_allow_html=True)

        if fila["legajo_estado"] == pt.LEGAJO_REVISAR:
            st.warning(
                "Este DNI figura en el padrón de empleados con otro apellido. Lo "
                "más probable es que el DNI esté mal cargado: por eso no se "
                "muestra el legajo.")

        # El historial sale de TODO el registro, no del recorte filtrado: la
        # pregunta es si la persona ya se presentó, no si cumple el filtro.
        otras = pt.historial(df, numero)
        if not bool(fila["dni_valido"]):
            st.caption("Sin DNI cargado: no se puede armar el historial. Buscá "
                       "por apellido para ver si tiene otras entrevistas.")
        elif otras.empty:
            st.caption("Es la única entrevista registrada con este DNI.")
        else:
            st.markdown(f"**Otras entrevistas con el mismo DNI ({len(otras)})**")
            if pt.apellidos_distintos(df, numero):
                st.warning(
                    "Con este DNI hay registros con apellidos distintos. Puede "
                    "ser el mismo apellido mal tipeado o un DNI mal cargado: "
                    "revisá los nombres antes de sacar conclusiones.")
            vista_otras = _tabla(otras)
            st.dataframe(vista_otras, hide_index=True, width="stretch",
                         column_config=_config(vista_otras))


# ══════════════════════════════════════════════════════════════
# Carga
# ══════════════════════════════════════════════════════════════
c_btn, c_estado = st.columns([1.5, 6], vertical_alignment="center")
with c_btn:
    if st.button("↺  Actualizar"):
        _leer.clear()
        cargar_empleados_cruce.clear()
        st.rerun()

try:
    df, LEGAJOS_OK = _leer()
except Exception:  # noqa: BLE001
    st.error("No se pudo cargar el registro de postulantes. Revisá la conexión con la base.")
    if st.button("Reintentar"):
        _leer.clear()
        st.rerun()
    st.stop()

if st.session_state.pop("_pt_carga_ok", None):
    st.success(st.session_state.pop("_pt_carga_msg", "Registro actualizado."))

HAY_DATOS = not df.empty
# Números de orden tomados en Access sin nada cargado: son parte del registro,
# pero en una consulta son renglones vacíos.
visibles = df[~df["en_blanco"]] if HAY_DATOS else df

momento, quien = pt.ultima_actualizacion(df)
# Identifica el estado del registro: cambia con cada actualización desde Access.
VERSION = f"{len(df)}|{momento}|{LEGAJOS_OK}"

with c_estado:
    if HAY_DATOS:
        partes = [_plural(len(visibles), "entrevista")]
        if not visibles.empty:
            ultima = visibles.iloc[0]             # viene ordenado de nueva a vieja
            partes.append(f"última: Nº {int(ultima['numero_orden'])} "
                          f"({_fecha(ultima['fecha'])})")
        if momento is not None:
            local = momento.tz_convert("America/Argentina/Buenos_Aires")
            partes.append(f"actualizado desde Access el {local.strftime('%d/%m/%Y %H:%M')}"
                          + (f" por {quien}" if quien else ""))
        st.caption(" · ".join(partes))

if HAY_DATOS and not LEGAJOS_OK:
    st.warning("No se pudo consultar el padrón de empleados: la columna **Legajo** "
               "está vacía por ahora. Probá con «↺ Actualizar» en un rato.")


# ══════════════════════════════════════════════════════════════
# Búsqueda y filtros (valen para Entrevistas y para Resumen)
# ══════════════════════════════════════════════════════════════
FILTROS_DEFECTO = {"pt_q": "", "pt_grupos": [], "pt_sectores": [], "pt_entrev": [],
                   "pt_desde": None, "pt_hasta": None, "pt_solo": []}
# Las de legajo sólo tienen sentido con el padrón a la vista.
OPCIONES_SOLO = [SOLO_APTOS, SOLO_NOTAS, SOLO_REPETIDOS]
if LEGAJOS_OK:
    OPCIONES_SOLO += [SOLO_LEGAJO, SOLO_REVISAR]


def _limpiar_filtros() -> None:
    for clave, valor in FILTROS_DEFECTO.items():
        st.session_state[clave] = valor


f = visibles
consulta, desde, hasta = "", None, None
grupos, sectores, entrevistadores, solo = [], [], [], []

if HAY_DATOS:
    op_grupos = [g for g in pt.GRUPOS_PUESTO if (visibles["puesto_grupo"] == g).any()]
    op_sectores = pt.opciones(visibles, "sector_norm")
    op_entrev = pt.opciones(visibles, "entrevistador_norm")
    # Tras una actualización una opción puede dejar de existir: si el valor
    # guardado ya no está entre las opciones, el multiselect revienta.
    for clave, validas in (("pt_grupos", op_grupos), ("pt_sectores", op_sectores),
                           ("pt_entrev", op_entrev), ("pt_solo", OPCIONES_SOLO)):
        st.session_state[clave] = [v for v in st.session_state.get(clave, [])
                                   if v in validas]

    consulta = st.text_input(
        "Buscar", key="pt_q", icon=":material/search:",
        placeholder="Apellido, nombre, DNI o texto de las notas (ej.: perez juan · "
                    "30123456 · stand by)")

    fechas = [x for x in visibles["fecha"] if x is not None]
    fecha_min = min(fechas) if fechas else date(2000, 1, 1)
    fecha_max = max(max(fechas), date.today()) if fechas else date.today()

    f1, f2, f3, f4, f5 = st.columns([2.2, 2.2, 2.2, 1.3, 1.3])
    with f1:
        grupos = st.multiselect("Puesto", op_grupos, key="pt_grupos",
                                placeholder="Todos",
                                help="Familias de puesto: «Conductor» junta CHOFER, "
                                     "CONDUCTOR y sus variantes de tipeo.")
    with f2:
        sectores = st.multiselect("Sector / base", op_sectores, key="pt_sectores",
                                  placeholder="Todos")
    with f3:
        entrevistadores = st.multiselect("Entrevistador", op_entrev, key="pt_entrev",
                                         placeholder="Todos")
    with f4:
        desde = st.date_input("Desde", value=None, key="pt_desde", format="DD/MM/YYYY",
                              min_value=fecha_min, max_value=fecha_max)
    with f5:
        hasta = st.date_input("Hasta", value=None, key="pt_hasta", format="DD/MM/YYYY",
                              min_value=fecha_min, max_value=fecha_max)

    p1, p2 = st.columns([6, 1.5], vertical_alignment="bottom")
    with p1:
        solo = st.pills("Mostrar solo", OPCIONES_SOLO,
                        selection_mode="multi", key="pt_solo") or []
    with p2:
        st.button("Limpiar filtros", on_click=_limpiar_filtros, width="stretch")

    f = pt.filtrar(
        pt.buscar(visibles, consulta),
        grupos=grupos, sectores=sectores, entrevistadores=entrevistadores,
        desde=desde, hasta=hasta,
        solo_aptos=SOLO_APTOS in solo, solo_con_notas=SOLO_NOTAS in solo,
        solo_repetidos=SOLO_REPETIDOS in solo,
        solo_con_legajo=SOLO_LEGAJO in solo,
        solo_dni_a_revisar=SOLO_REVISAR in solo,
    )

HAY_OTROS_FILTROS = bool(grupos or sectores or entrevistadores or desde or hasta or solo)
HAY_FILTROS = bool(consulta.strip()) or HAY_OTROS_FILTROS
r = pt.resumen(f)


def _texto_filtros() -> str:
    """Los filtros activos en una línea, para la auditoría de la exportación."""
    partes = []
    if consulta.strip():
        partes.append(f"búsqueda «{consulta.strip()}»")
    if grupos:
        partes.append("puesto: " + ", ".join(grupos))
    if sectores:
        partes.append("sector: " + ", ".join(sectores))
    if entrevistadores:
        partes.append("entrevistador: " + ", ".join(entrevistadores))
    if desde:
        partes.append(f"desde {desde.strftime('%d/%m/%Y')}")
    if hasta:
        partes.append(f"hasta {hasta.strftime('%d/%m/%Y')}")
    partes.extend(s.lower() for s in solo)
    return " · ".join(partes)


tab_lista, tab_resumen, tab_carga = st.tabs(
    ["Entrevistas", "Resumen", "Actualizar desde Access"])

# ══════════════════════════════════════════════════════════════
# TAB 1 — Entrevistas
# ══════════════════════════════════════════════════════════════
with tab_lista:
    if not HAY_DATOS:
        st.info("Todavía no hay entrevistas cargadas. Subí el archivo de Access "
                "en la pestaña «Actualizar desde Access».")
    elif f.empty:
        if desde and hasta and desde > hasta:
            st.warning(f"El «Desde» ({desde.strftime('%d/%m/%Y')}) es posterior al "
                       f"«Hasta» ({hasta.strftime('%d/%m/%Y')}): el período está invertido.")
        elif consulta.strip():
            st.info(f"Ninguna entrevista coincide con «{consulta.strip()}»"
                    + (" y los filtros elegidos" if HAY_OTROS_FILTROS else "")
                    + ". Probá sólo con el apellido o con el DNI.")
        else:
            st.info("Ninguna entrevista coincide con los filtros elegidos.")
    else:
        total = (f" de {_miles(len(visibles))}" if HAY_FILTROS else "")
        st.caption(f"**{_plural(r['entrevistas'], 'entrevista')}**{total} · "
                   f"{_plural(r['personas'], 'persona')}"
                   + (" (aprox.: las que no tienen DNI cuentan de a una)"
                      if r["sin_dni"] else ""))

        # La selección se guarda por posición de fila: si cambia el recorte, la
        # posición vieja apuntaría a otra persona. La key atada al recorte la
        # descarta sola.
        numeros = tuple(f["numero_orden"].tolist())
        vista = _tabla(f)
        evento = st.dataframe(
            vista, hide_index=True, width="stretch", height=430,
            column_config=_config(vista),
            on_select="rerun", selection_mode="single-row",
            key=f"tabla_pt_{hash(numeros)}",
        )
        st.caption("Hacé clic en una fila para ver la ficha completa y el historial "
                   "de esa persona. " + LEYENDA_APTO)

        filas_sel = list((evento or {}).get("selection", {}).get("rows", []))
        if filas_sel and filas_sel[0] < len(f):
            _render_ficha(df, int(f.iloc[filas_sel[0]]["numero_orden"]))

        if st.download_button(
            "⬇  Descargar resultado (Excel)", data=_excel(numeros, VERSION),
            file_name=f"postulantes_{date.today():%Y%m%d}.xlsx", mime=MIME_XLSX,
        ):
            # Cuántas y con qué filtros, nunca el contenido de las notas.
            filtros = _texto_filtros()
            auditoria.registrar(
                "postulantes", "export",
                f"Descargó {_plural(len(f), 'entrevista')} de postulantes"
                + (f" — {filtros}" if filtros else " — registro completo"),
                datos={"registros": int(len(f))},
            )

# ══════════════════════════════════════════════════════════════
# TAB 2 — Resumen del recorte
# ══════════════════════════════════════════════════════════════
with tab_resumen:
    if not HAY_DATOS or f.empty:
        st.info("No hay entrevistas para resumir con los filtros elegidos."
                if HAY_DATOS else "Todavía no hay entrevistas cargadas.")
    else:
        if HAY_FILTROS:
            st.caption(f"Sobre las {_miles(r['entrevistas'])} entrevistas que "
                       "dejan pasar la búsqueda y los filtros de arriba.")
        k1, k2, k3, k4 = st.columns(4)
        _tarjeta(k1, "Entrevistas", _miles(r["entrevistas"]),
                 f"de {_miles(len(visibles))} del registro" if HAY_FILTROS
                 else "todo el registro")
        _tarjeta(k2, "Personas", _miles(r["personas"]),
                 f"{_miles(r['sin_dni'])} sin DNI, contadas de a una" if r["sin_dni"]
                 else "por DNI")
        _tarjeta(k3, "Volvieron a presentarse", _miles(r["volvieron"]),
                 "personas con más de una entrevista")
        _tarjeta(k4, "Marcadas aptas", _miles(r["aptos"]),
                 "casilla tildada en Access")
        st.caption(
            "No hay porcentaje de aptos ni de rechazos a propósito. " + LEYENDA_APTO)

        por_anio = r["por_anio"]
        if len(por_anio) >= 2:
            _seccion("Entrevistas por año")
            maximo = int(por_anio["Entrevistas"].max())
            n_barras = len(por_anio)
            fig = go.Figure(go.Bar(
                x=por_anio["Año"].astype(str), y=por_anio["Entrevistas"],
                # Barra fina (~24 px) aunque haya pocas: que no llene el ancho.
                width=min(0.45, 24 * n_barras / 1000),
                marker=dict(color=COLOR_PRIMARY, cornerradius=4),
                # Sólo se rotula el máximo; el resto lo dan el eje y el hover.
                text=[_miles(v) if v == maximo else "" for v in por_anio["Entrevistas"]],
                textposition="outside", cliponaxis=False,
                textfont=dict(color=COLOR_TEXT, size=12),
                hovertemplate="%{x}: %{y} entrevistas<extra></extra>",
            ))
            fig.update_layout(**chart_base(
                height=280, showlegend=False,
                xaxis=dict(type="category", showgrid=False, showline=True,
                           zeroline=False, linecolor=COLOR_BORDER,
                           tickfont=dict(color=COLOR_MUTED)),
                margin=dict(l=10, r=10, t=28, b=10),
            ))
            st.plotly_chart(fig, use_container_width=True,
                            config={"displayModeBar": False})
            sin_fecha = int(f["fecha"].map(lambda x: x is None).sum())
            if sin_fecha:
                st.caption(f"{_plural(sin_fecha, 'entrevista')} sin fecha no "
                           "entran en este gráfico.")
            with st.expander("Ver como tabla"):
                st.dataframe(por_anio, hide_index=True,
                             column_config={"Año": st.column_config.NumberColumn(format="%d")})

        _seccion("Cómo se reparten")
        t1, t2, t3 = st.columns(3)
        with t1:
            st.dataframe(r["por_grupo"], hide_index=True, width="stretch")
        with t2:
            st.dataframe(r["por_sector"], hide_index=True, width="stretch")
        with t3:
            st.dataframe(r["por_entrevistador"], hide_index=True, width="stretch")
        st.caption("Puesto por familia; sector y entrevistador muestran los 15 "
                   "con más entrevistas.")

        if not r["motivos"].empty:
            _seccion("Motivos más cargados")
            st.dataframe(r["motivos"], hide_index=True, width="stretch")
            st.caption("El texto del campo «Motivos del rechazo» tal como se cargó "
                       "(sin distinguir mayúsculas ni tildes). Ese campo también se "
                       "usa para anotar avances, como «SE ENVIA PROPUESTA».")

# ══════════════════════════════════════════════════════════════
# TAB 3 — Actualizar desde Access
# ══════════════════════════════════════════════════════════════
with tab_carga:
    st.markdown(
        "Las entrevistas se siguen cargando en Access. Para traer las novedades, "
        "subí acá **el archivo de Access (.mdb)** tal cual está. Se agregan las "
        "entrevistas nuevas y se actualizan las que cambiaron. **Nunca se borra "
        "nada.**")
    with st.expander("¿Y si el .mdb no se puede leer?"):
        st.markdown(
            "Exportá la tabla a Excel y subí ese archivo:\n"
            "1. Abrí la base en Access.\n"
            "2. Clic derecho sobre la tabla *FORM 045 02 REGISTRO DE ENTREVISTAS A "
            "POSTULANTES* → **Exportar** → **Excel**.\n"
            "3. Guardalo como `.xlsx` sin cambiar los nombres de las columnas.\n"
            "4. Subilo acá.")

    semilla = st.session_state.get("pt_archivo_seed", 0)
    subido = st.file_uploader(
        "Archivo de Access (.mdb), o la tabla exportada a Excel (.xlsx) o CSV",
        type=list(pt.EXTENSIONES), key=f"pt_archivo_{semilla}")

    if subido is not None:
        try:
            nuevo = _leer_subido(subido.name, subido.getvalue())
        except pt.ArchivoInvalido as e:
            st.error(str(e))
            nuevo = None

        if nuevo is not None:
            plan = pt.plan_de_carga(nuevo, df)
            n_nuevas, n_modif = len(plan["nuevas"]), len(plan["modificadas"])
            n_faltan = len(plan["faltantes"])

            _seccion(f"Qué trae «{subido.name}»")
            a1, a2, a3, a4 = st.columns(4)
            _tarjeta(a1, "Nuevas", _miles(n_nuevas), "se agregan",
                     COLOR_OK if n_nuevas else COLOR_NEUTRO,
                     COLOR_OK_BG if n_nuevas else COLOR_NEUTRO_BG)
            _tarjeta(a2, "Modificadas", _miles(n_modif), "se actualizan",
                     COLOR_AVISO if n_modif else COLOR_NEUTRO,
                     COLOR_AVISO_BG if n_modif else COLOR_NEUTRO_BG)
            _tarjeta(a3, "Sin cambios", _miles(plan["sin_cambios"]), "no se tocan")
            _tarjeta(a4, "No están en el archivo", _miles(n_faltan),
                     "quedan como están",
                     COLOR_ALERTA if n_faltan else COLOR_NEUTRO,
                     COLOR_ALERTA_BG if n_faltan else COLOR_NEUTRO_BG)
            st.write("")

            if not n_nuevas and not n_modif:
                if n_faltan:
                    st.warning(
                        f"Este archivo no trae novedades y le faltan "
                        f"{_plural(n_faltan, 'entrevista')} que ya están en el "
                        "dashboard: parece una copia vieja de la base. No hay "
                        "nada para actualizar.")
                else:
                    st.success("El dashboard ya está al día con este archivo: no "
                               "hay nada para actualizar.")
            else:
                if n_nuevas:
                    with st.expander(f"Nuevas ({_miles(n_nuevas)})", expanded=n_nuevas <= 30):
                        # «Veces» no va: se cuenta sobre todo el registro, y
                        # acá sólo están las nuevas.
                        vista_nuevas = _tabla(pt.enriquecer(plan["nuevas"])) \
                            .drop(columns=["Veces"])
                        st.dataframe(vista_nuevas, hide_index=True, width="stretch",
                                     column_config=_config(vista_nuevas))
                if n_modif:
                    with st.expander(f"Modificadas ({_miles(n_modif)})",
                                     expanded=n_modif <= 30):
                        mod = plan["modificadas"]
                        st.dataframe(pd.DataFrame({
                            "Nº": mod["numero_orden"],
                            "Apellido y nombre": [pt.apenom(a, n) for a, n in
                                                  zip(mod["apellido"], mod["nombres"])],
                            "Qué cambió (antes → ahora)": mod["cambios"].map(
                                pt.describir_cambios),
                        }), hide_index=True, width="stretch",
                            column_config={"Nº": COLUMNAS_TABLA["Nº"]})

                avisos = pt.advertencias_de_carga(plan)
                for aviso in avisos:
                    st.warning(aviso)
                confirmado = True
                if avisos:
                    confirmado = st.checkbox(
                        "Revisé la vista previa y quiero actualizar igual",
                        key=f"pt_confirma_{semilla}")

                if st.button(
                    f"Confirmar actualización ({_plural(n_nuevas, 'nueva')}, "
                    f"{_plural(n_modif, 'modificada')})",
                    type="primary", disabled=not confirmado,
                ):
                    quien = (current_user() or {}).get("nombre", "") \
                        or st.session_state.get("auth_user", "")
                    try:
                        pt.upsert(get_supabase(),
                                  pt.registros_para_upsert(pt.a_cargar(plan), quien))
                    except Exception:  # noqa: BLE001
                        st.error(
                            "No se pudo completar la actualización. Volvé a subir "
                            "el archivo y confirmá de nuevo: lo que ya entró no se "
                            "duplica.")
                    else:
                        # Cantidades y nombre de archivo, nunca el contenido.
                        auditoria.registrar(
                            "postulantes", "cambio",
                            f"Actualizó el registro desde Access: "
                            f"{_plural(n_nuevas, 'nueva')}, "
                            f"{_plural(n_modif, 'modificada')} — archivo «{subido.name}»",
                            datos={"nuevas": n_nuevas, "modificadas": n_modif,
                                   "sin_cambios": plan["sin_cambios"],
                                   "faltantes": n_faltan, "archivo": subido.name},
                        )
                        _leer.clear()
                        st.session_state["_pt_carga_ok"] = True
                        st.session_state["_pt_carga_msg"] = (
                            f"Registro actualizado: {_plural(n_nuevas, 'entrevista nueva', 'entrevistas nuevas')} "
                            f"y {_plural(n_modif, 'modificada')}.")
                        # Semilla nueva: el uploader vuelve vacío tras la carga.
                        st.session_state["pt_archivo_seed"] = semilla + 1
                        st.rerun()
