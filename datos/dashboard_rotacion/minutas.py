"""Minutas de reunión (RRHH) — estados, vencimientos y resumen.

Módulo de lógica pura: NO importa Streamlit, así que se puede testear con pytest
sin levantar la app (mismo criterio que `seguimiento.py`).

Cada fila es un ítem de acción salido de una reunión: un tema con responsable,
fecha límite y un estado que avanza en el tiempo (Pendiente → En curso →
Completa). El estado "Vencida" NO es un estado propio: se deriva de la fecha
límite, igual que los índices de Seguimiento se calculan y no se guardan, para
que la regla viva en un solo lugar y no queden filas viejas con un valor de otra
época.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from io import BytesIO

import pandas as pd

TABLA = "minutas_reunion"

# ─── Estados ─────────────────────────────────────────────────
ESTADO_PENDIENTE = "Pendiente"
ESTADO_EN_CURSO  = "En curso"
ESTADO_COMPLETA  = "Completa"

# Orden de progresión: así se listan en los selectores y en el resumen.
ESTADOS = (ESTADO_PENDIENTE, ESTADO_EN_CURSO, ESTADO_COMPLETA)

# ─── Colores de estado ───────────────────────────────────────
# Elegidos para dar contraste >=4.5:1 con texto blanco en los chips (el celeste
# de marca #46BCD2 no llega, así que En curso usa un teal más oscuro derivado).
COLOR_PENDIENTE = "#B45309"   # ámbar
COLOR_EN_CURSO  = "#0E7490"   # teal (variante legible del celeste de marca)
COLOR_COMPLETA  = "#166534"   # verde
COLOR_VENCIDA   = "#B91C1C"   # rojo
COLOR_MUTED     = "#8C8987"

COLOR_ESTADO = {
    ESTADO_PENDIENTE: COLOR_PENDIENTE,
    ESTADO_EN_CURSO:  COLOR_EN_CURSO,
    ESTADO_COMPLETA:  COLOR_COMPLETA,
}

# Tintes claros (fondos de tarjetas y chips). Cada estado tiene una familia de
# color bien distinta de un vistazo: ámbar / celeste / verde / rojo.
COLOR_PENDIENTE_BG = "#FEF3C7"
COLOR_EN_CURSO_BG  = "#CFFAFE"
COLOR_COMPLETA_BG  = "#DCFCE7"
COLOR_VENCIDA_BG   = "#FEE2E2"

COLOR_ESTADO_BG = {
    ESTADO_PENDIENTE: COLOR_PENDIENTE_BG,
    ESTADO_EN_CURSO:  COLOR_EN_CURSO_BG,
    ESTADO_COMPLETA:  COLOR_COMPLETA_BG,
}

COLUMNAS_DB = [
    "id", "fecha", "tema", "descripcion", "responsable", "fecha_limite",
    "estado", "registrado_por", "fecha_registro", "fecha_actualizacion",
]


def columnas_db():
    """Columnas de la tabla, para el `.select(...)` de Supabase."""
    return list(COLUMNAS_DB)


def estado_valido(estado) -> bool:
    """True si `estado` es uno de los tres estados del catálogo."""
    return estado in ESTADOS


# ─── Fechas ──────────────────────────────────────────────────
def to_date(v):
    """Coerciona str / date / datetime / Timestamp a `date`, o None si no se puede.

    OJO: `pd.NaT` ES instancia de `datetime`/`date`, así que un simple
    `isinstance(v, date)` NO alcanza para descartar una fecha vacía —hay que
    chequear `pd.isna` primero—. Por eso todo el código (acá y en la página)
    pasa las fechas por esta función en vez de confiar en `isinstance`.
    """
    if v is None:
        return None
    # NaT / NaN (llegan de pandas cuando la fecha viene vacía).
    if not isinstance(v, str) and pd.isna(v):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    ts = pd.to_datetime(v, errors="coerce")
    return None if pd.isna(ts) else ts.date()


# ─── Vencimiento (derivado, no se guarda) ────────────────────
def es_vencida(fila, hoy=None) -> bool:
    """True si el ítem tiene fecha límite pasada y todavía no está Completa.

    `fila` puede ser un dict o una Series de pandas.
    """
    if fila.get("estado") == ESTADO_COMPLETA:
        return False
    fl = to_date(fila.get("fecha_limite"))
    if fl is None:
        return False
    hoy = hoy or date.today()
    return fl < hoy


def marcar_vencidas(df, hoy=None):
    """Agrega la columna booleana `vencida` a un frame de minutas."""
    out = df.copy()
    if out.empty:
        out["vencida"] = pd.Series(dtype="bool")
        return out
    hoy = hoy or date.today()
    out["vencida"] = out.apply(lambda f: es_vencida(f, hoy), axis=1)
    return out


def color_estado(estado, vencida=False) -> str:
    """Color fuerte del estado (texto, bordes, número). `vencida=True` → rojo."""
    if vencida:
        return COLOR_VENCIDA
    return COLOR_ESTADO.get(estado, COLOR_MUTED)


def color_estado_bg(estado, vencida=False) -> str:
    """Tinte claro de fondo del estado (tarjetas y chips)."""
    if vencida:
        return COLOR_VENCIDA_BG
    return COLOR_ESTADO_BG.get(estado, "#F1F1F1")


# ─── Resumen para el banner "estado general" ─────────────────
def resumen_estado(df, hoy=None):
    """Los números del banner de arriba.

    Devuelve dict con: total, por_estado (dict por cada estado), vencidas y
    pct_completas (0-100, NaN si no hay ítems).
    """
    d = df if "vencida" in df.columns else marcar_vencidas(df, hoy)
    total = int(len(d))
    por_estado = {
        e: int((d["estado"] == e).sum()) if ("estado" in d.columns and total) else 0
        for e in ESTADOS
    }
    vencidas = int(d["vencida"].sum()) if ("vencida" in d.columns and total) else 0
    completas = por_estado.get(ESTADO_COMPLETA, 0)
    pct = (completas / total * 100.0) if total else float("nan")
    return {
        "total": total,
        "por_estado": por_estado,
        "vencidas": vencidas,
        "pct_completas": pct,
    }


# ─── Orden del listado ───────────────────────────────────────
def ordenar(df, hoy=None):
    """Ordena para mostrar: primero las vencidas, después por fecha límite más
    próxima, y las que no tienen fecha límite al final."""
    if df.empty:
        return df
    d = df if "vencida" in df.columns else marcar_vencidas(df, hoy)
    d = d.copy()
    d["_fl"] = pd.to_datetime(d["fecha_limite"], errors="coerce")
    # Las Completa van al final aunque tengan fecha próxima; las sin fecha límite
    # también, para que arriba queden las que exigen acción.
    d["_completa"] = (d["estado"] == ESTADO_COMPLETA).astype(int)
    d["_sin_fl"] = d["_fl"].isna().astype(int)
    d = d.sort_values(
        by=["_completa", "vencida", "_sin_fl", "_fl", "fecha"],
        ascending=[True, False, True, True, False],
    )
    return d.drop(columns=["_fl", "_completa", "_sin_fl"])


# ─── Construcción del payload de insert ──────────────────────
def construir_payload(*, fecha, tema, descripcion, responsable,
                      fecha_limite, estado, registrado_por):
    """Arma el dict del insert a Supabase, con fechas en ISO y textos limpios.

    Deja `descripcion` / `responsable` / `fecha_limite` en None cuando están
    vacíos, así la base guarda NULL y no cadenas vacías.
    """
    return {
        "fecha": fecha.isoformat() if fecha else None,
        "tema": (tema or "").strip(),
        "descripcion": ((descripcion or "").strip() or None),
        "responsable": ((responsable or "").strip() or None),
        "fecha_limite": fecha_limite.isoformat() if fecha_limite else None,
        "estado": estado,
        "registrado_por": registrado_por,
    }


# ─── Exportación ─────────────────────────────────────────────
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _limpiar_celda(v):
    """Saca caracteres de control: texto pegado de Word/WhatsApp rompe openpyxl."""
    if isinstance(v, str):
        return _CTRL.sub("", v)
    return v


ETIQUETAS_EXPORT = {
    "fecha": "Fecha", "tema": "Tema o acción", "descripcion": "Descripción",
    "responsable": "Responsable", "fecha_limite": "Fecha límite",
    "estado": "Estado", "vencida": "Vencida", "registrado_por": "Registrado por",
}


def preparar_export(df, hoy=None):
    """Frame legible para Excel: encabezados en castellano y 'vencida' como Sí/No."""
    if df.empty:
        return pd.DataFrame()
    d = df if "vencida" in df.columns else marcar_vencidas(df, hoy)
    orden = ["fecha", "tema", "descripcion", "responsable", "fecha_limite",
             "estado", "vencida", "registrado_por"]
    out = pd.DataFrame(index=d.index)
    for col in orden:
        if col not in d.columns:
            continue
        if col == "vencida":
            out[ETIQUETAS_EXPORT[col]] = d[col].map({True: "Sí", False: "No"})
        else:
            out[ETIQUETAS_EXPORT.get(col, col)] = d[col]
    return out.apply(lambda col: col.map(_limpiar_celda))


def exportar_excel(df, hoy=None):
    """Bytes de un .xlsx con una hoja 'Minutas'."""
    datos = preparar_export(df, hoy)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        if datos.empty:
            pd.DataFrame({"Sin datos": []}).to_excel(
                writer, sheet_name="Minutas", index=False)
        else:
            datos.to_excel(writer, sheet_name="Minutas", index=False)
    return buffer.getvalue()
