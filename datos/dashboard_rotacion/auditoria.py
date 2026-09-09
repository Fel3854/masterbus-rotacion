"""Auditoría — registro de quién hizo qué en el dashboard.

Cada movimiento que cambia datos (alta, baja, cambio) y cada acceso a
información sensible queda con una fila acá: usuario, momento, módulo, acción y
un detalle legible. Es el rastro de control, así que tiene dos reglas duras:

1. **Nunca frena al usuario.** Si falla el registro del log, la acción del
   usuario ya se hizo y no se deshace: se traga el error. Un log caído no puede
   impedir que RRHH cargue un adelanto.

2. **No guarda el contenido confidencial.** Del Seguimiento se registra QUE
   alguien abrió o exportó una entrevista, nunca lo que el conductor dijo. Si el
   textual se copiara al log, el permiso que lo protege no serviría de nada:
   bastaría con mirar la auditoría.

La tabla es append-only a nivel base (ver la migración): la anon key puede
insertar y leer, pero NO borrar ni modificar. Un log que el auditado puede
editar no es un control.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

import pandas as pd
import streamlit as st

from utils import get_supabase

TABLA = "auditoria"

# ─── Catálogo de acciones ────────────────────────────────────
# La etiqueta es lo que se ve en la pantalla de auditoría; el color agrupa por
# gravedad para poder barrer la lista de un vistazo.
ACCIONES = {
    "alta":          {"label": "Alta",              "color": "#15803D"},
    "baja":          {"label": "Baja",              "color": "#D12F19"},
    "cambio":        {"label": "Cambio",            "color": "#B45309"},
    "export":        {"label": "Exportación",       "color": "#46BCD2"},
    "lectura":       {"label": "Lectura sensible",  "color": "#46BCD2"},
    "login":         {"label": "Ingreso",           "color": "#8C8987"},
    "logout":        {"label": "Salida",            "color": "#8C8987"},
    "login_fallido": {"label": "Login fallido",     "color": "#D12F19"},
}

MODULOS = {
    "adelantos":   "Adelantos de Sueldo",
    "descuentos":  "Descuentos",
    "seguimiento": "Seguimiento",
    "minutas":     "Minutas",
    "sesion":      "Sesión",
}

# Acciones que cambian datos. El filtro por defecto de la pantalla usa esto:
# los ingresos y salidas son ruido cuando lo que se busca es "quién tocó qué".
ACCIONES_ESCRITURA = ("alta", "baja", "cambio")

COLUMNAS = ["id", "fecha", "usuario", "nombre", "modulo", "accion",
            "detalle", "registro_id", "datos"]


def registrar(modulo, accion, detalle="", registro_id=None, datos=None):
    """Deja una fila en la auditoría. Nunca lanza excepción.

    Se llama DESPUÉS de que la acción se completó: si la acción falló no hay
    nada que auditar, y si el log falla la acción ya está hecha igual.

    `datos` es para el contexto que no entra en el detalle (montos, cantidad de
    cuotas, legajo). No mandar textuales de entrevistas: ver el docstring del
    módulo.
    """
    try:
        # Import perezoso: auth importa este módulo para loguear el login, así
        # que importarlo arriba sería una dependencia circular.
        from auth import current_user

        u = current_user() or {}
        usuario = st.session_state.get("auth_user") or "?"
        fila = {
            "fecha": datetime.now(timezone.utc).isoformat(),
            "usuario": usuario,
            "nombre": u.get("name") or usuario,
            "modulo": modulo,
            "accion": accion,
            "detalle": (detalle or "")[:500],
            "registro_id": str(registro_id) if registro_id else None,
            "datos": datos or None,
        }
        get_supabase().table(TABLA).insert(fila).execute()
    except Exception:  # noqa: BLE001 — ver regla 1 del docstring
        pass


def registrar_login(usuario, ok):
    """Ingreso o intento fallido.

    Va aparte de `registrar()` porque en el intento fallido todavía no hay
    sesión: el usuario tecleado no es un usuario logueado, es sólo un dato.
    """
    try:
        fila = {
            "fecha": datetime.now(timezone.utc).isoformat(),
            "usuario": (usuario or "?")[:60],
            "nombre": None,
            "modulo": "sesion",
            "accion": "login" if ok else "login_fallido",
            "detalle": "Ingreso correcto" if ok else "Usuario o contraseña incorrectos",
        }
        get_supabase().table(TABLA).insert(fila).execute()
    except Exception:  # noqa: BLE001
        pass


# ─── Lectura y formato (lógica pura, testeable) ──────────────
def normalizar(df):
    """Deja el DataFrame de la auditoría listo para filtrar y mostrar.

    Agrega las columnas derivadas que usa la pantalla: fecha local, etiquetas
    legibles de módulo y acción, y el flag de escritura.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=COLUMNAS + [
            "fecha_local", "dia", "modulo_label", "accion_label", "es_escritura"])

    out = df.copy()
    # Las fechas se guardan en UTC; se muestran en hora de Argentina.
    fechas = pd.to_datetime(out["fecha"], errors="coerce", utc=True)
    out["fecha_local"] = fechas.dt.tz_convert("America/Argentina/Buenos_Aires")
    out["dia"] = out["fecha_local"].dt.date
    out["modulo_label"] = out["modulo"].map(MODULOS).fillna(out["modulo"])
    out["accion_label"] = out["accion"].map(
        {k: v["label"] for k, v in ACCIONES.items()}).fillna(out["accion"])
    out["es_escritura"] = out["accion"].isin(ACCIONES_ESCRITURA)
    out["nombre"] = out["nombre"].fillna(out["usuario"])
    return out.sort_values("fecha_local", ascending=False).reset_index(drop=True)


def resumen_por_usuario(df):
    """Movimientos por usuario: total, escrituras y último movimiento."""
    if df.empty:
        return pd.DataFrame(columns=["usuario", "nombre", "movimientos",
                                     "escrituras", "ultimo"])
    g = df.groupby(["usuario", "nombre"], dropna=False)
    out = g.agg(movimientos=("id", "count"),
                escrituras=("es_escritura", "sum"),
                ultimo=("fecha_local", "max")).reset_index()
    return out.sort_values("movimientos", ascending=False).reset_index(drop=True)


def resumen_por_modulo(df):
    """Movimientos por módulo y acción, para ver dónde se concentró la actividad."""
    if df.empty:
        return pd.DataFrame(columns=["modulo_label", "accion_label", "n"])
    out = (df.groupby(["modulo_label", "accion_label"])
             .size().reset_index(name="n"))
    return out.sort_values("n", ascending=False).reset_index(drop=True)


def filtrar(df, usuarios=None, modulos=None, acciones=None,
            desde=None, hasta=None, texto=None):
    """Aplica los filtros de la pantalla. Cada uno es opcional."""
    out = df
    if usuarios:
        out = out[out["usuario"].isin(usuarios)]
    if modulos:
        out = out[out["modulo"].isin(modulos)]
    if acciones:
        out = out[out["accion"].isin(acciones)]
    if desde is not None:
        out = out[out["dia"] >= desde]
    if hasta is not None:
        out = out[out["dia"] <= hasta]
    if texto:
        t = texto.strip().lower()
        if t:
            out = out[out["detalle"].fillna("").str.lower().str.contains(t, regex=False)]
    return out.reset_index(drop=True)


def preparar_export(df):
    """Tabla plana para el Excel de auditoría."""
    if df.empty:
        return pd.DataFrame(columns=["Fecha", "Usuario", "Módulo", "Acción", "Detalle"])
    out = pd.DataFrame({
        "Fecha":   df["fecha_local"].dt.strftime("%d/%m/%Y %H:%M"),
        "Usuario": df["nombre"],
        "Módulo":  df["modulo_label"],
        "Acción":  df["accion_label"],
        "Detalle": df["detalle"].fillna(""),
    })
    return out


def exportar_excel(df):
    """Bytes de un .xlsx con una hoja 'Auditoria'."""
    datos = preparar_export(df)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        if datos.empty:
            pd.DataFrame({"Sin datos": []}).to_excel(
                writer, sheet_name="Auditoria", index=False)
        else:
            datos.to_excel(writer, sheet_name="Auditoria", index=False)
    return buffer.getvalue()
