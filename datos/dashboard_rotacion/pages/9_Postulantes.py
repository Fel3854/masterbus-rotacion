"""Vista: Postulantes — registro de entrevistas (FORM 045 02).

Consulta para quien tiene `ver_postulantes`; alta, edición, anulación e
importación para quien además tiene `edit_postulantes`.
"""

import html
import os
import sys
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from auth import puede_ver_postulantes, can_edit, current_user  # noqa: E402
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
SOLO_ANULADAS = "Anuladas"

LEYENDA_APTO = (
    "«Apto ✓» significa que la casilla «Apto para ingresar» está tildada. **Sin "
    "tilde no quiere decir rechazado**: desde 2023 la casilla casi no se usa y el "
    "resultado de la entrevista está en las notas.")

ZONA = "America/Argentina/Buenos_Aires"
FECHA_MINIMA = date(pt.ANIO_MINIMO, 1, 1)

# Un guardado en lote que toca más entrevistas que esto pide tildar una
# confirmación, como las importaciones que cambian demasiado.
UMBRAL_LOTE = 50
# Columnas que se pueden llenar de una con un mismo valor. Apellido, nombres,
# DNI y las dos notas quedan afuera: son de cada persona, y pisarlas en lote
# casi siempre sería un error. Se siguen editando celda por celda.
CAMPOS_LOTE = ["entrevistador", "puesto", "sector", "fecha", "apto"]
# Las dos notas van al final: son anchas, y adelante dejarían fuera de la
# pantalla a las columnas cortas, que son las que más se corrigen.
ORDEN_GRILLA = ["numero_orden", "fecha", "apellido", "nombres", "dni", "puesto",
                "sector", "entrevistador", "apto", "motivo_rechazo", "observaciones"]
ROTULO_GRILLA = {
    "numero_orden": "Nº", "fecha": "Fecha", "apellido": "Apellido",
    "nombres": "Nombres", "dni": "DNI", "puesto": "Puesto", "sector": "Sector",
    "apto": "Apto", "motivo_rechazo": "Motivos del rechazo",
    "observaciones": "Observaciones", "entrevistador": "Entrevistador",
}


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

# Ver y cargar van por separado: sin este permiso la página es sólo de consulta.
PUEDE_EDITAR = can_edit("postulantes")
QUIEN = (current_user() or {}).get("nombre", "") or st.session_state.get("auth_user", "")
# El servidor corre en UTC: a la noche su «hoy» ya es mañana.
HOY = pd.Timestamp.now(tz=ZONA).date()


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


@st.cache_data(ttl=600, max_entries=2, show_spinner=False)
def _opciones_carga(version: str) -> dict:
    """Entrevistadores, puestos y sectores ya usados, para elegir al cargar.

    Son texto libre: ofrecer lo que ya está escrito es lo que evita sumar otra
    forma más de escribir «CONDUCTOR». `version` las renueva cuando cambia el
    registro.
    """
    df, _legajos_ok = _leer()
    vigentes = df[~df["en_blanco"] & ~df["anulada"]]
    return {"entrevistador": pt.sugerencias(vigentes, "entrevistador_norm"),
            "puesto": pt.sugerencias(vigentes, "puesto"),
            "sector": pt.sugerencias(vigentes, "sector")}


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


def _avisar(mensaje="", aviso="") -> None:
    """Deja un mensaje para mostrar arriba después del rerun que sigue a un guardado."""
    if mensaje:
        st.session_state["_pt_carga_ok"] = True
        st.session_state["_pt_carga_msg"] = mensaje
    if aviso:
        st.session_state["_pt_carga_aviso"] = aviso


def _texto_conflictos(conflictos) -> str:
    """El aviso de lo que NO se guardó porque otra persona lo cambió antes."""
    if not conflictos:
        return ""
    numeros = sorted({n for n, _campo in conflictos})
    cuales = ", ".join(str(n) for n in numeros[:15]) + ("…" if len(numeros) > 15 else "")
    quedo = "cambio no se guardó" if len(conflictos) == 1 else "cambios no se guardaron"
    return (f"{_miles(len(conflictos))} {quedo}: otra persona modificó eso mismo "
            f"mientras editabas. Revisá cómo quedó (Nº {cuales}).")


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
        width="small", help="✓ = casilla tildada. Vacío = sin marcar, no rechazado."),
    "Motivo": st.column_config.TextColumn(width="medium"),
    "Observaciones": st.column_config.TextColumn(width="medium"),
    "Veces": st.column_config.TextColumn(
        width="small", help="Cuántas entrevistas tiene esa persona (mismo DNI)."),
}


# La grilla de «Editar en lote». El DNI va como texto para que «11.222.333» no
# se lea como un decimal. Sin tope de fecha: la configuración es parte de la
# identidad del widget, y un «hasta hoy» lo reiniciaría a medianoche con todo lo
# editado adentro. La fecha futura se frena al guardar.
CONFIG_GRILLA = {
    "numero_orden": st.column_config.NumberColumn("Nº", format="%d", width="small"),
    "fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY", width="small",
                                         min_value=FECHA_MINIMA),
    "apellido": st.column_config.TextColumn("Apellido"),
    "nombres": st.column_config.TextColumn("Nombres"),
    "dni": st.column_config.TextColumn("DNI", width="small", max_chars=12,
                                       validate=r"^[\d.\s]*$",
                                       help="Sólo números, con o sin puntos."),
    "puesto": st.column_config.TextColumn("Puesto"),
    "sector": st.column_config.TextColumn("Sector"),
    "apto": st.column_config.CheckboxColumn(
        "Apto", width="small", help="Tildado = apto. Sin tildar = sin marcar, no rechazado."),
    "motivo_rechazo": st.column_config.TextColumn("Motivos del rechazo", width="medium"),
    "observaciones": st.column_config.TextColumn("Observaciones", width="large"),
    "entrevistador": st.column_config.TextColumn("Entrevistador"),
}


def _grilla(f: pd.DataFrame) -> pd.DataFrame:
    """Un recorte del registro con la forma de la grilla: sólo los campos del formulario."""
    return pd.DataFrame({
        "numero_orden": f["numero_orden"].astype(int),
        "fecha": pd.to_datetime(f["fecha"], errors="coerce"),
        "apellido": f["apellido"],
        "nombres": f["nombres"],
        "dni": f["dni"].map(lambda d: "" if pd.isna(d) else str(int(d))),
        "puesto": f["puesto"],
        "sector": f["sector"],
        "apto": f["apto"].astype(bool),
        "motivo_rechazo": f["motivo_rechazo"],
        "observaciones": f["observaciones"],
        "entrevistador": f["entrevistador"],
    }).reset_index(drop=True)


# ─── Formulario de una entrevista (alta y edición) ────────────
def _campos_entrevista(clave: str, valores: dict, con_dni: bool) -> dict:
    """Dibuja los campos del FORM 045 02 dentro del formulario abierto.

    `valores` es con qué arrancan. Devuelve lo cargado tal cual, sin validar. En
    el alta el DNI se pide afuera del formulario (así se ven al instante las
    entrevistas anteriores de esa persona), por eso es opcional acá.
    """
    def _elegir(campo):
        actual = str(valores.get(campo) or "")
        lista = OPCIONES_CARGA[campo]
        if actual and actual not in lista:
            lista = [actual, *lista]              # una grafía rara no se pierde por editar
        return st.selectbox(
            pt.ENCABEZADO[campo], lista, index=lista.index(actual) if actual else None,
            accept_new_options=True, placeholder="Elegí o escribí uno nuevo",
            key=f"{clave}_{campo}")

    cargado = {}
    inicial = pt.to_date(valores.get("fecha"))
    c1, c2, c3 = st.columns([1.2, 3, 1.4], vertical_alignment="bottom")
    with c1:
        # Los topes se corren si la fecha guardada ya está afuera (un año mal
        # tipeado): si no, el widget no dejaría ni abrir la entrevista.
        cargado["fecha"] = st.date_input(
            "Fecha", value=inicial, format="DD/MM/YYYY",
            min_value=min(FECHA_MINIMA, inicial or FECHA_MINIMA),
            max_value=max(HOY, inicial or HOY), key=f"{clave}_fecha")
    with c2:
        cargado["entrevistador"] = _elegir("entrevistador")
    with c3:
        cargado["apto"] = st.checkbox(pt.ENCABEZADO["apto"], value=bool(valores.get("apto")),
                                      key=f"{clave}_apto")

    persona = st.columns([2, 2, 1.2] if con_dni else 2)
    with persona[0]:
        cargado["apellido"] = st.text_input("Apellido *", value=str(valores.get("apellido") or ""),
                                            key=f"{clave}_apellido")
    with persona[1]:
        cargado["nombres"] = st.text_input("Nombres", value=str(valores.get("nombres") or ""),
                                           key=f"{clave}_nombres")
    if con_dni:
        with persona[2]:
            cargado["dni"] = st.text_input("DNI", value=str(valores.get("dni") or ""),
                                           placeholder="Con o sin puntos", key=f"{clave}_dni")

    p1, p2 = st.columns(2)
    with p1:
        cargado["puesto"] = _elegir("puesto")
    with p2:
        cargado["sector"] = _elegir("sector")

    cargado["motivo_rechazo"] = st.text_area(
        pt.ENCABEZADO["motivo_rechazo"], value=str(valores.get("motivo_rechazo") or ""),
        height=80, key=f"{clave}_motivo",
        help="También se usa para anotar avances, como «SE ENVIA PROPUESTA».")
    cargado["observaciones"] = st.text_area(
        pt.ENCABEZADO["observaciones"], value=str(valores.get("observaciones") or ""),
        height=140, key=f"{clave}_observaciones")
    return cargado


def _guardar(modificadas: pd.DataFrame):
    """Escribe una edición. Devuelve el resultado, o None si falló (ya avisó)."""
    try:
        resultado = pt.guardar_edicion(get_supabase(), modificadas, QUIEN)
    except Exception:  # noqa: BLE001
        # Puede haber entrado una parte: que lo próximo que se lea sea lo real.
        _leer.clear()
        st.error("No se pudieron guardar todos los cambios. Volvé a guardar: lo "
                 "que ya entró no se repite.")
        return None
    _leer.clear()
    return resultado


def _anular(numero: int, anulada: bool) -> None:
    """Anula o restaura una entrevista y vuelve a dibujar."""
    try:
        pt.marcar_anulada(get_supabase(), numero, anulada, QUIEN)
    except Exception:  # noqa: BLE001
        st.error("No se pudo guardar. Probá de nuevo.")
        return
    auditoria.registrar(
        "postulantes", "baja" if anulada else "cambio",
        f"{'Anuló' if anulada else 'Restauró'} la entrevista Nº {numero}",
        registro_id=numero)
    _leer.clear()
    st.session_state.pop(f"pt_anular_{numero}", None)
    _avisar(f"Entrevista Nº {numero} anulada. Se puede restaurar desde «Mostrar solo → "
            f"{SOLO_ANULADAS}»." if anulada else f"Entrevista Nº {numero} restaurada.")
    st.rerun()


def _render_edicion(df: pd.DataFrame, fila) -> None:
    """Editar, anular o restaurar la entrevista de la ficha."""
    numero = int(fila["numero_orden"])
    with st.expander("Editar esta entrevista"):
        # La versión de la fila va en la key: si la entrevista cambia en la
        # base, el formulario se vuelve a llenar con lo nuevo en vez de seguir
        # mostrando lo que había quedado tipeado.
        clave = f"pt_ed_{numero}_{fila['fecha_actualizacion']}"
        actuales = {c: fila[c] for c in pt.COLUMNAS_TEXTO}
        actuales.update(fecha=fila["fecha"], apto=bool(fila["apto"]),
                        dni="" if pd.isna(fila["dni"]) else str(int(fila["dni"])))
        with st.form(f"form_{clave}", enter_to_submit=False):
            cargado = _campos_entrevista(clave, actuales, con_dni=True)
            enviar = st.form_submit_button("Guardar cambios", type="primary")

        if enviar:
            dni, error_dni = pt.leer_dni(cargado["dni"])
            editado = pd.DataFrame(
                [{"numero_orden": numero, **pt.canonizar_fila({**cargado, "dni": dni})}])
            modificadas = pt.plan_de_edicion(df[df["numero_orden"] == numero], editado)
            campos = ([c for c, _a, _d in modificadas.iloc[0]["cambios"]]
                      if len(modificadas) else [])
            errores = [error_dni] if error_dni else []
            if campos:
                errores += pt.validar_entrevista(dict(modificadas.iloc[0]),
                                                 campos=campos, hoy=HOY)
            if errores:
                st.error("\n\n".join(f"- {e}" for e in errores))
            elif not campos:
                st.info("No cambiaste nada.")
            else:
                resultado = _guardar(modificadas)
                if resultado is not None:
                    if resultado["guardadas"]:
                        # Qué campos, nunca con qué valor.
                        nombres = ", ".join(pt.ENCABEZADO[c] for c in resultado["por_campo"])
                        auditoria.registrar(
                            "postulantes", "cambio",
                            f"Editó la entrevista Nº {numero} — {nombres}",
                            registro_id=numero,
                            datos={"campos": list(resultado["por_campo"])})
                    _avisar(f"Entrevista Nº {numero} actualizada."
                            if resultado["guardadas"] else "",
                            _texto_conflictos(resultado["conflictos"]))
                    st.rerun()

        st.divider()
        pide_anular = f"pt_anular_{numero}"
        if bool(fila["anulada"]):
            st.caption("Está anulada: no aparece en la lista ni cuenta en el historial "
                       "de la persona.")
            if st.button("Restaurar entrevista", key=f"pt_restaurar_{numero}"):
                _anular(numero, False)
        elif st.session_state.get(pide_anular):
            st.warning("¿Anular esta entrevista? Deja de verse en la lista y de contar "
                       "en el historial de la persona. No se borra: se puede restaurar.")
            s1, s2 = st.columns(2)
            if s1.button("Sí, anular", key=f"pt_anular_si_{numero}", width="stretch"):
                _anular(numero, True)
            if s2.button("Cancelar", key=f"pt_anular_no_{numero}", width="stretch"):
                st.session_state.pop(pide_anular, None)
                st.rerun()
        elif st.button("Anular entrevista", key=f"pt_anular_btn_{numero}",
                       help="Para una entrevista cargada por error o duplicada."):
            st.session_state[pide_anular] = True
            st.rerun()


# ─── Ficha de una entrevista ──────────────────────────────────
def _render_ficha(df: pd.DataFrame, numero: int) -> None:
    fila = df[df["numero_orden"] == numero].iloc[0]

    chips = ""
    if bool(fila["anulada"]):
        chips += (f'<span class="ficha-chip" style="--chip-bg:{COLOR_ALERTA_BG}; '
                  f'--chip-fg:{COLOR_ALERTA};">Anulada</span>')
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
        entrada = (f"Ingresó el {ingreso:%d/%m/%Y}" if ingreso
                   else "Ingresó (sin fecha en el padrón)")
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

        editada = pd.to_datetime(fila["fecha_edicion"], errors="coerce", utc=True)
        if not pd.isna(editada):
            st.caption(f"Cargada o editada en el dashboard por {fila['editado_por'] or '—'} "
                       f"el {editada.tz_convert(ZONA):%d/%m/%Y %H:%M}.")
        if PUEDE_EDITAR:
            _render_edicion(df, fila)


# ══════════════════════════════════════════════════════════════
# Carga
# ══════════════════════════════════════════════════════════════
c_btn, c_estado = st.columns([1.5, 6], vertical_alignment="center")
with c_btn:
    if st.button("↺  Actualizar"):
        _leer.clear()
        cargar_empleados_cruce.clear()
        st.rerun()

# Lugares fijos para lo que aparece y desaparece de una corrida a otra: el
# spinner de la lectura (sólo cuando no hay caché) y los avisos de un guardado.
# Sueltos, correrían un lugar todo lo que viene después, y con eso Streamlit
# vuelve a armar `st.tabs` en la primera pestaña: a quien está cargando en
# «Nueva entrevista» lo devolvería a «Entrevistas» en el medio de la carga.
zona_lectura = st.container()
zona_avisos = st.container()

try:
    with zona_lectura:
        df, LEGAJOS_OK = _leer()
except Exception:  # noqa: BLE001
    st.error("No se pudo cargar el registro de postulantes. Revisá la conexión con la base.")
    if st.button("Reintentar"):
        _leer.clear()
        st.rerun()
    st.stop()

with zona_avisos:
    # Además del cartel, un toast: el formulario queda lejos del tope de la
    # página y sin él no se vería que la entrevista se guardó.
    if st.session_state.pop("_pt_carga_ok", None):
        hecho = st.session_state.pop("_pt_carga_msg", "Registro actualizado.")
        st.success(hecho)
        st.toast(hecho, icon="✅")
    if st.session_state.get("_pt_carga_aviso"):
        pendiente = st.session_state.pop("_pt_carga_aviso")
        st.warning(pendiente)
        st.toast(pendiente, icon="⚠️")

HAY_DATOS = not df.empty
# Fuera de la consulta quedan los números de orden tomados en Access sin nada
# cargado (son parte del registro, pero acá son renglones vacíos) y las
# entrevistas anuladas.
visibles = df[~df["en_blanco"] & ~df["anulada"]] if HAY_DATOS else df

momento, quien = pt.ultima_actualizacion(df)
# Identifica el estado del registro: cambia con cada alta, edición o importación.
VERSION = f"{len(df)}|{momento}|{LEGAJOS_OK}"
OPCIONES_CARGA = _opciones_carga(VERSION) if PUEDE_EDITAR else {}

with c_estado:
    if HAY_DATOS:
        partes = [_plural(len(visibles), "entrevista")]
        if not visibles.empty:
            ultima = visibles.iloc[0]             # viene ordenado de nueva a vieja
            partes.append(f"última: Nº {int(ultima['numero_orden'])} "
                          f"({_fecha(ultima['fecha'])})")
        if momento is not None:
            local = momento.tz_convert(ZONA)
            partes.append(f"último cambio el {local.strftime('%d/%m/%Y %H:%M')}"
                          + (f" por {quien}" if quien else ""))
        st.caption(" · ".join(partes))

if HAY_DATOS and not LEGAJOS_OK:
    zona_avisos.warning("No se pudo consultar el padrón de empleados: la columna "
                        "**Legajo** está vacía por ahora. Probá con «↺ Actualizar» "
                        "en un rato.")


# ══════════════════════════════════════════════════════════════
# Búsqueda y filtros (valen para Entrevistas y para Resumen)
# ══════════════════════════════════════════════════════════════
FILTROS_DEFECTO = {"pt_q": "", "pt_grupos": [], "pt_sectores": [], "pt_entrev": [],
                   "pt_desde": None, "pt_hasta": None, "pt_solo": []}
# Las de legajo sólo tienen sentido con el padrón a la vista.
OPCIONES_SOLO = [SOLO_APTOS, SOLO_NOTAS, SOLO_REPETIDOS]
if LEGAJOS_OK:
    OPCIONES_SOLO += [SOLO_LEGAJO, SOLO_REVISAR]
# Las anuladas sólo se muestran a quien las puede restaurar.
if PUEDE_EDITAR and HAY_DATOS and bool(df["anulada"].any()):
    OPCIONES_SOLO.append(SOLO_ANULADAS)


def _limpiar_filtros() -> None:
    for clave, valor in FILTROS_DEFECTO.items():
        st.session_state[clave] = valor


f = universo = visibles
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

    # «Anuladas» no achica la lista de siempre: la cambia por la de anuladas.
    if SOLO_ANULADAS in solo:
        universo = df[df["anulada"]]
    f = pt.filtrar(
        pt.buscar(universo, consulta),
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


# Las tres de carga sólo existen para quien puede editar.
pestanas = st.tabs(["Entrevistas", "Resumen"] + (
    ["Nueva entrevista", "Editar en lote", "Importar archivo"] if PUEDE_EDITAR else []))
tab_lista, tab_resumen = pestanas[0], pestanas[1]

# ══════════════════════════════════════════════════════════════
# TAB 1 — Entrevistas
# ══════════════════════════════════════════════════════════════
with tab_lista:
    if not HAY_DATOS:
        st.info("Todavía no hay entrevistas cargadas."
                + (" Cargá la primera en «Nueva entrevista» o traé el registro "
                   "desde «Importar archivo»." if PUEDE_EDITAR else ""))
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
        total = (f" de {_miles(len(universo))}" if HAY_FILTROS else "")
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
                 f"de {_miles(len(universo))} del registro" if HAY_FILTROS
                 else "todo el registro")
        _tarjeta(k2, "Personas", _miles(r["personas"]),
                 f"{_miles(r['sin_dni'])} sin DNI, contadas de a una" if r["sin_dni"]
                 else "por DNI")
        _tarjeta(k3, "Volvieron a presentarse", _miles(r["volvieron"]),
                 "personas con más de una entrevista")
        _tarjeta(k4, "Marcadas aptas", _miles(r["aptos"]),
                 "casilla «Apto» tildada")
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

# Hasta acá, la consulta. Lo que sigue carga y modifica el registro.
if not PUEDE_EDITAR:
    st.stop()
tab_alta, tab_lote, tab_carga = pestanas[2:]

# ══════════════════════════════════════════════════════════════
# TAB 3 — Nueva entrevista
# ══════════════════════════════════════════════════════════════
with tab_alta:
    # Semilla en las keys: al guardar cambia y el formulario vuelve vacío.
    semilla_alta = st.session_state.get("pt_alta_seed", 0)
    st.markdown("Cargá acá cada entrevista nueva. El **Nº de orden** se asigna "
                "solo al guardar.")

    c_dni, c_previas = st.columns([1.3, 4.7], vertical_alignment="bottom")
    with c_dni:
        dni_txt = st.text_input("DNI", key=f"pt_alta_dni_{semilla_alta}",
                                placeholder="Con o sin puntos")
    dni_nuevo, error_dni = pt.leer_dni(dni_txt)
    previas = (visibles[visibles["dni_valido"] & (visibles["dni"] == dni_nuevo)]
               if dni_nuevo is not None else visibles.iloc[0:0])
    with c_previas:
        if error_dni:
            st.error(error_dni)
        elif dni_nuevo is None:
            st.caption("Empezá por el DNI: si la persona ya se presentó, sus "
                       "entrevistas aparecen acá abajo. Sin DNI no se puede armar el "
                       "historial ni cruzar el legajo.")
        elif previas.empty:
            st.caption("Es la primera entrevista registrada con este DNI.")
        else:
            st.caption(f"**Esta persona ya tiene {_plural(len(previas), 'entrevista')} "
                       "en el registro.** Miralas antes de cargar la nueva.")
    # En un contenedor que está siempre: si la tabla apareciera suelta, el
    # formulario de abajo cambiaría de lugar al tipear el DNI.
    with st.container():
        if not previas.empty:
            vista_previas = _tabla(previas)
            st.dataframe(vista_previas, hide_index=True, width="stretch",
                         column_config=_config(vista_previas))

    # (dni, fecha) del posible duplicado que frenó el guardado anterior. Sólo
    # vale mientras siga siendo ese DNI y la otra entrevista siga ahí.
    repetida = st.session_state.get("pt_alta_dup")
    ya_cargada = (pt.posibles_duplicados(visibles, *repetida) if repetida
                  else visibles.iloc[0:0])
    if repetida and (repetida[0] != dni_nuevo or ya_cargada.empty):
        st.session_state.pop("pt_alta_dup")
        repetida = None

    with st.form(f"pt_alta_{semilla_alta}", enter_to_submit=False):
        cargado = _campos_entrevista(f"pt_alta_{semilla_alta}", {"fecha": HOY},
                                     con_dni=False)
        confirma_repetida = False
        if repetida:
            st.warning(
                f"Ya hay una entrevista de este DNI con esa misma fecha (Nº "
                f"{', '.join(str(n) for n in ya_cargada['numero_orden'])}). Si es la "
                "misma, no la cargues de nuevo.")
            confirma_repetida = st.checkbox(
                "Es otra entrevista: guardarla igual",
                key=f"pt_alta_dup_ok_{semilla_alta}")
        enviar_alta = st.form_submit_button("Guardar entrevista", type="primary")

    if enviar_alta:
        fila_nueva = pt.canonizar_fila({**cargado, "dni": dni_nuevo})
        errores = [error_dni] if error_dni else []
        errores += pt.validar_entrevista(fila_nueva, alta=True, hoy=HOY)
        clave_repetida = (fila_nueva["dni"], fila_nueva["fecha"])
        hay_repetida = not pt.posibles_duplicados(visibles, *clave_repetida).empty
        if errores:
            st.error("\n\n".join(f"- {e}" for e in errores))
        elif hay_repetida and not (confirma_repetida and repetida == clave_repetida):
            # Se vuelve a dibujar con el aviso y el tilde adentro del formulario;
            # lo que ya se tipeó queda, porque las keys no cambian.
            st.session_state["pt_alta_dup"] = clave_repetida
            st.rerun()
        else:
            try:
                numero_nuevo = pt.insertar(get_supabase(), fila_nueva, QUIEN)
            except Exception:  # noqa: BLE001
                st.error("No se pudo guardar la entrevista. Probá de nuevo: no "
                         "quedó nada a medias.")
            else:
                # El número, nunca el nombre ni las notas.
                auditoria.registrar("postulantes", "alta",
                                    f"Cargó la entrevista Nº {numero_nuevo}",
                                    registro_id=numero_nuevo)
                _leer.clear()
                _avisar(f"Entrevista Nº {numero_nuevo} cargada: "
                        f"{pt.apenom(fila_nueva['apellido'], fila_nueva['nombres'])}.")
                st.session_state["pt_alta_seed"] = semilla_alta + 1
                st.session_state.pop("pt_alta_dup", None)
                st.rerun()

# ══════════════════════════════════════════════════════════════
# TAB 4 — Editar en lote
# ══════════════════════════════════════════════════════════════
CLAVES_LOTE = ("pt_lote_base", "pt_lote_trabajo", "pt_lote_rev")


def _salir_del_lote() -> None:
    for clave in CLAVES_LOTE:
        st.session_state.pop(clave, None)


with tab_lote:
    if "pt_lote_base" not in st.session_state:
        st.markdown(
            "Para corregir varias entrevistas a la vez, como en una planilla. Se "
            "editan **las que dejan pasar la búsqueda y los filtros de arriba**: "
            "achicá el resultado a lo que querés tocar y entrá.")
        if f.empty:
            st.info("No hay entrevistas en el resultado: aflojá los filtros para "
                    "elegir qué editar.")
        elif st.button(f"Editar {_plural(len(f), 'entrevista')} del resultado",
                       type="primary"):
            # El recorte se congela: el `data_editor` descarta lo editado si le
            # cambian los datos de abajo, y el registro se relee cada 10 minutos
            # o cuando otra persona guarda.
            inicial = _grilla(f)
            st.session_state["pt_lote_base"] = inicial
            st.session_state["pt_lote_trabajo"] = inicial.copy()
            st.session_state["pt_lote_rev"] = 0
            st.rerun()
    else:
        lote_base = st.session_state["pt_lote_base"]
        lote_rev = st.session_state["pt_lote_rev"]
        n_lote = len(lote_base)
        st.markdown(
            f"Editando **{_plural(n_lote, 'entrevista')}** (las del resultado cuando "
            "entraste). Cambiá las celdas que haga falta: nada se guarda hasta que "
            "toques **Guardar**.")

        zona_valor = st.container()
        # La key cambia con cada «Aplicar»: la grilla arranca de la tabla ya
        # modificada en vez de superponerle ediciones viejas.
        editado = st.data_editor(
            st.session_state["pt_lote_trabajo"], key=f"pt_lote_editor_{lote_rev}",
            hide_index=True, num_rows="fixed", disabled=["numero_orden"],
            column_order=ORDEN_GRILLA, column_config=CONFIG_GRILLA,
            # Justo para las filas que hay, hasta un tope: sin renglones vacíos.
            height=min(440, 38 + 35 * n_lote))

        # Va arriba de la grilla pero se dibuja después: necesita lo que la
        # grilla tiene editado para no perderlo al aplicar.
        with zona_valor.expander("Aplicar un mismo valor a toda una columna"):
            v1, v2, v3 = st.columns([1.5, 3, 1.9], vertical_alignment="bottom")
            with v1:
                campo_lote = st.selectbox("Columna", CAMPOS_LOTE, key="pt_lote_campo",
                                          format_func=lambda c: ROTULO_GRILLA[c])
            with v2:
                if campo_lote == "fecha":
                    valor_lote = st.date_input(
                        "Valor", value=None, format="DD/MM/YYYY", key="pt_lote_valor_fecha",
                        min_value=FECHA_MINIMA, max_value=HOY)
                elif campo_lote == "apto":
                    valor_lote = st.radio("Valor", ["Tildado", "Sin tildar"], horizontal=True,
                                          key="pt_lote_valor_apto") == "Tildado"
                else:
                    valor_lote = st.selectbox(
                        "Valor", OPCIONES_CARGA[campo_lote], index=None,
                        accept_new_options=True, placeholder="Elegí o escribí uno nuevo",
                        key=f"pt_lote_valor_{campo_lote}")
            sin_valor = valor_lote is None or not str(valor_lote).strip()
            with v3:
                if st.button(f"Aplicar a las {_miles(n_lote)} filas", disabled=sin_valor,
                             width="stretch"):
                    aplicado = editado.copy()
                    aplicado[campo_lote] = (pd.Timestamp(valor_lote).as_unit("ns")
                                            if campo_lote == "fecha" else valor_lote)
                    st.session_state["pt_lote_trabajo"] = aplicado
                    st.session_state["pt_lote_rev"] = lote_rev + 1
                    st.rerun()
            st.caption(
                "Pone ese valor en todas las filas de la grilla. Abajo vas a ver cuáles "
                "cambian, antes de guardar. Apellido, nombres, DNI y las notas no se "
                "llenan en lote: son de cada persona.")

        modificadas = pt.plan_de_edicion(lote_base, editado)
        n_mod = len(modificadas)
        puede_guardar = False
        if not n_mod:
            st.caption("Todavía no cambiaste nada.")
        else:
            cuenta: dict = {}
            for cambios in modificadas["cambios"]:
                for campo, _antes, _despues in cambios:
                    cuenta[campo] = cuenta.get(campo, 0) + 1
            _seccion(f"Qué se va a guardar: {_plural(n_mod, 'entrevista')}")
            st.caption(" · ".join(f"{ROTULO_GRILLA[c]}: {_miles(k)}" for c, k in cuenta.items()))
            st.dataframe(pd.DataFrame({
                "Nº": modificadas["numero_orden"],
                "Apellido y nombre": [pt.apenom(a, n) for a, n in
                                      zip(modificadas["apellido"], modificadas["nombres"])],
                "Qué cambió (antes → ahora)": modificadas["cambios"].map(pt.describir_cambios),
            }), hide_index=True, width="stretch", height=min(38 * (n_mod + 1) + 3, 300),
                column_config={"Nº": COLUMNAS_TABLA["Nº"]})

            errores_lote = []
            vaciadas = 0
            for registro in modificadas.to_dict("records"):
                tocados = [c for c, _a, _d in registro["cambios"]]
                errores_lote += [f"Nº {registro['numero_orden']}: {e}"
                                 for e in pt.validar_entrevista(registro, campos=tocados, hoy=HOY)]
                if ({"apellido", "nombres", "dni"} & set(tocados)
                        and not (registro["apellido"] or registro["nombres"] or registro["dni"])):
                    vaciadas += 1
            if errores_lote:
                resto = len(errores_lote) - 20
                st.error("Corregí esto antes de guardar:\n\n"
                         + "\n\n".join(f"- {e}" for e in errores_lote[:20])
                         + (f"\n\n…y {resto} más." if resto > 0 else ""))
            if vaciadas:
                st.warning(
                    f"{_plural(vaciadas, 'entrevista queda', 'entrevistas quedan')} sin "
                    "apellido, nombre ni DNI: van a dejar de verse en la lista. Si la "
                    "idea es sacarlas, conviene anularlas desde su ficha.")
            confirmado_lote = True
            if n_mod > UMBRAL_LOTE:
                confirmado_lote = st.checkbox(
                    f"Revisé la lista y quiero cambiar {_plural(n_mod, 'entrevista')}",
                    key=f"pt_lote_confirma_{lote_rev}")
            puede_guardar = confirmado_lote and not errores_lote

        b1, b2, _b3 = st.columns([2.2, 1.8, 4])
        with b1:
            guardar_lote = st.button(
                f"Guardar cambios en {_plural(n_mod, 'entrevista')}" if n_mod else "Guardar",
                type="primary", disabled=not puede_guardar, width="stretch")
        with b2:
            if st.button("Salir sin guardar", width="stretch"):
                _salir_del_lote()
                st.rerun()

        if guardar_lote:
            resultado = _guardar(modificadas)
            # Si falló no se sale: la grilla queda como está para reintentar.
            if resultado is not None:
                guardadas = resultado["guardadas"]
                if guardadas:
                    # Qué entrevistas y qué campos, nunca los valores.
                    auditoria.registrar(
                        "postulantes", "cambio",
                        f"Editó {_plural(guardadas, 'entrevista')} en lote — "
                        + " · ".join(f"{ROTULO_GRILLA[c]}: {k}"
                                     for c, k in resultado["por_campo"].items()),
                        datos={"registros": guardadas, "campos": resultado["por_campo"],
                               "numeros": resultado["numeros"],
                               "conflictos": len(resultado["conflictos"])})
                _salir_del_lote()
                _avisar(f"Se guardaron los cambios en {_plural(guardadas, 'entrevista')}."
                        if guardadas else "",
                        _texto_conflictos(resultado["conflictos"]))
                st.rerun()

# ══════════════════════════════════════════════════════════════
# TAB 5 — Importar archivo
# ══════════════════════════════════════════════════════════════
with tab_carga:
    st.markdown(
        "El registro se carga y se corrige acá. Esta pestaña queda para traer un "
        "archivo entero: **la base de Access (.mdb)**, o un Excel con las columnas "
        "del formulario (por ejemplo, el que se descarga desde «Entrevistas»). Se "
        "agregan las entrevistas que no estaban y se actualizan las que cambiaron. "
        "**Nunca se borra nada**, y lo que se cargó o editó en el dashboard no se pisa.")
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
        "Archivo de Access (.mdb), o la tabla en Excel (.xlsx) o CSV",
        type=list(pt.EXTENSIONES), key=f"pt_archivo_{semilla}")

    if subido is not None:
        try:
            nuevo = _leer_subido(subido.name, subido.getvalue())
        except pt.ArchivoInvalido as e:
            st.error(str(e))
            nuevo = None

        if nuevo is not None:
            plan = pt.plan_de_carga(nuevo, df, proteger_editadas=True)
            n_nuevas, n_modif = len(plan["nuevas"]), len(plan["modificadas"])
            n_faltan, n_prot = len(plan["faltantes"]), len(plan["protegidas"])

            _seccion(f"Qué trae «{subido.name}»")
            tarjetas = st.columns(5 if n_prot else 4)
            _tarjeta(tarjetas[0], "Nuevas", _miles(n_nuevas), "se agregan",
                     COLOR_OK if n_nuevas else COLOR_NEUTRO,
                     COLOR_OK_BG if n_nuevas else COLOR_NEUTRO_BG)
            _tarjeta(tarjetas[1], "Modificadas", _miles(n_modif), "se actualizan",
                     COLOR_AVISO if n_modif else COLOR_NEUTRO,
                     COLOR_AVISO_BG if n_modif else COLOR_NEUTRO_BG)
            _tarjeta(tarjetas[2], "Sin cambios", _miles(plan["sin_cambios"]), "no se tocan")
            _tarjeta(tarjetas[3], "No están en el archivo", _miles(n_faltan),
                     "quedan como están",
                     COLOR_ALERTA if n_faltan else COLOR_NEUTRO,
                     COLOR_ALERTA_BG if n_faltan else COLOR_NEUTRO_BG)
            if n_prot:
                _tarjeta(tarjetas[4], "Editadas acá", _miles(n_prot), "no se pisan",
                         COLOR_ALERTA, COLOR_ALERTA_BG)
            st.write("")

            pisar = False
            if n_prot:
                with st.expander(f"Cargadas o editadas en el dashboard ({_miles(n_prot)})",
                                 expanded=n_prot <= 30):
                    st.markdown(
                        "El archivo las trae distintas de como están acá. **No se "
                        "pisan**: lo más probable es que el archivo sea anterior a esas "
                        "correcciones, o que en Access ese número de orden sea de otra "
                        "persona.")
                    prot = plan["protegidas"]
                    aca = dict(zip(df["numero_orden"], df["apenom"]))
                    st.dataframe(pd.DataFrame({
                        "Nº": prot["numero_orden"],
                        "Como está acá": [aca.get(n, "") for n in prot["numero_orden"]],
                        "Qué cambiaría (acá → archivo)": prot["cambios"].map(
                            pt.describir_cambios),
                    }), hide_index=True, width="stretch",
                        column_config={"Nº": COLUMNAS_TABLA["Nº"]})
                    cuales = ("esta entrevista" if n_prot == 1
                              else f"estas {_miles(n_prot)} entrevistas")
                    pisar = st.checkbox(
                        f"Pisar también {cuales} con lo que trae el archivo",
                        key=f"pt_pisar_{semilla}")
            n_pisadas = n_prot if pisar else 0

            if not (n_nuevas or n_modif or n_pisadas):
                if n_prot:
                    st.info("Lo único distinto en este archivo son entrevistas cargadas "
                            "o editadas en el dashboard, que no se pisan. No hay nada "
                            "para actualizar.")
                elif n_faltan:
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

                que_entra = (f"{_plural(n_nuevas, 'nueva')}, {_plural(n_modif, 'modificada')}"
                             + (f", {_plural(n_pisadas, 'pisada')}" if n_pisadas else ""))
                if st.button(f"Confirmar importación ({que_entra})",
                             type="primary", disabled=not confirmado):
                    try:
                        pt.upsert(get_supabase(), pt.registros_para_upsert(
                            pt.a_cargar(plan, pisar_protegidas=pisar), QUIEN))
                    except Exception:  # noqa: BLE001
                        st.error(
                            "No se pudo completar la importación. Volvé a subir "
                            "el archivo y confirmá de nuevo: lo que ya entró no se "
                            "duplica.")
                    else:
                        # Cantidades y nombre de archivo, nunca el contenido.
                        auditoria.registrar(
                            "postulantes", "cambio",
                            f"Importó un archivo: {que_entra} — archivo «{subido.name}»",
                            datos={"nuevas": n_nuevas, "modificadas": n_modif,
                                   "sin_cambios": plan["sin_cambios"],
                                   "faltantes": n_faltan, "protegidas": n_prot,
                                   "pisadas": n_pisadas, "archivo": subido.name},
                        )
                        _leer.clear()
                        _avisar(
                            f"Registro actualizado: {_plural(n_nuevas, 'entrevista nueva', 'entrevistas nuevas')} "
                            f"y {_plural(n_modif + n_pisadas, 'modificada')}.")
                        # Semilla nueva: el uploader vuelve vacío tras la carga.
                        st.session_state["pt_archivo_seed"] = semilla + 1
                        st.rerun()
