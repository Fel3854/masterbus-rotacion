"""Tests de auditoria.py — lógica pura, sin Streamlit ni red."""

import os
import sys
from datetime import date

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auditoria as au  # noqa: E402


def _fila(usuario="lu", nombre="Lu", modulo="adelantos", accion="alta",
          detalle="X", fecha="2026-09-08T14:30:00+00:00", **extra):
    f = {"id": f"id-{usuario}-{accion}-{fecha}", "fecha": fecha, "usuario": usuario,
         "nombre": nombre, "modulo": modulo, "accion": accion, "detalle": detalle,
         "registro_id": None, "datos": None}
    f.update(extra)
    return f


def _df(*filas):
    return au.normalizar(pd.DataFrame(list(filas), columns=au.COLUMNAS))


# ─── normalizar ───────────────────────────────────────────────
def test_normalizar_vacio_devuelve_columnas_y_no_revienta():
    out = au.normalizar(pd.DataFrame(columns=au.COLUMNAS))
    assert out.empty
    for col in ("fecha_local", "dia", "modulo_label", "accion_label", "es_escritura"):
        assert col in out.columns


def test_normalizar_convierte_utc_a_hora_argentina():
    # 02:30 UTC del 9 es todavía el 8 a las 23:30 en Argentina (UTC-3).
    out = _df(_fila(fecha="2026-09-09T02:30:00+00:00"))
    assert out.loc[0, "fecha_local"].hour == 23
    assert out.loc[0, "dia"] == date(2026, 9, 8)


def test_normalizar_traduce_modulo_y_accion():
    out = _df(_fila(modulo="seguimiento", accion="lectura"))
    assert out.loc[0, "modulo_label"] == "Seguimiento"
    assert out.loc[0, "accion_label"] == "Lectura sensible"


def test_modulo_desconocido_se_muestra_crudo_en_vez_de_quedar_vacio():
    out = _df(_fila(modulo="modulo_nuevo", accion="accion_nueva"))
    assert out.loc[0, "modulo_label"] == "modulo_nuevo"
    assert out.loc[0, "accion_label"] == "accion_nueva"


def test_solo_alta_baja_y_cambio_cuentan_como_escritura():
    out = _df(_fila(accion="alta"), _fila(accion="baja"), _fila(accion="cambio"),
              _fila(accion="login"), _fila(accion="export"), _fila(accion="lectura"))
    assert out["es_escritura"].sum() == 3


def test_login_fallido_sin_nombre_cae_al_usuario_tecleado():
    out = _df(_fila(usuario="pepe", nombre=None, accion="login_fallido", modulo="sesion"))
    assert out.loc[0, "nombre"] == "pepe"


def test_ordena_del_mas_reciente_al_mas_viejo():
    out = _df(_fila(fecha="2026-09-01T10:00:00+00:00", detalle="vieja"),
              _fila(fecha="2026-09-08T10:00:00+00:00", detalle="nueva"))
    assert out.loc[0, "detalle"] == "nueva"


# ─── filtrar ──────────────────────────────────────────────────
def test_filtrar_sin_criterios_devuelve_todo():
    df = _df(_fila(), _fila(usuario="flor"))
    assert len(au.filtrar(df)) == 2


def test_filtrar_por_usuario_y_modulo():
    df = _df(_fila(usuario="lu", modulo="adelantos"),
             _fila(usuario="flor", modulo="adelantos"),
             _fila(usuario="lu", modulo="minutas"))
    assert len(au.filtrar(df, usuarios=["lu"])) == 2
    assert len(au.filtrar(df, usuarios=["lu"], modulos=["minutas"])) == 1


def test_busqueda_de_texto_es_case_insensitive_y_literal():
    df = _df(_fila(detalle="MARTINEZ JUAN · $ 50.000"))
    assert len(au.filtrar(df, texto="martinez")) == 1
    # el punto no debe interpretarse como comodín de regex
    assert len(au.filtrar(df, texto="50x000")) == 0


def test_filtrar_por_rango_de_dias_incluye_los_extremos():
    df = _df(_fila(fecha="2026-09-01T12:00:00+00:00"),
             _fila(fecha="2026-09-05T12:00:00+00:00"),
             _fila(fecha="2026-09-10T12:00:00+00:00"))
    out = au.filtrar(df, desde=date(2026, 9, 1), hasta=date(2026, 9, 5))
    assert len(out) == 2


# ─── resúmenes ────────────────────────────────────────────────
def test_resumen_por_usuario_separa_movimientos_de_escrituras():
    df = _df(_fila(usuario="lu", accion="alta"),
             _fila(usuario="lu", accion="login"),
             _fila(usuario="flor", accion="baja"))
    res = au.resumen_por_usuario(df)
    lu = res[res["usuario"] == "lu"].iloc[0]
    assert lu["movimientos"] == 2
    assert lu["escrituras"] == 1


def test_resumenes_vacios_no_revientan():
    vacio = au.normalizar(pd.DataFrame(columns=au.COLUMNAS))
    assert au.resumen_por_usuario(vacio).empty
    assert au.resumen_por_modulo(vacio).empty
    assert au.preparar_export(vacio).empty


def test_resumen_por_modulo_agrupa_modulo_y_accion():
    df = _df(_fila(modulo="minutas", accion="alta"),
             _fila(modulo="minutas", accion="alta"),
             _fila(modulo="minutas", accion="baja"))
    res = au.resumen_por_modulo(df)
    top = res.iloc[0]
    assert top["accion_label"] == "Alta" and top["n"] == 2


# ─── export ───────────────────────────────────────────────────
def test_export_usa_encabezados_legibles_y_hora_local():
    df = _df(_fila(fecha="2026-09-08T14:30:00+00:00"))
    out = au.preparar_export(df)
    assert list(out.columns) == ["Fecha", "Usuario", "Módulo", "Acción", "Detalle"]
    assert out.loc[0, "Fecha"] == "08/09/2026 11:30"


def test_exportar_excel_devuelve_un_xlsx():
    df = _df(_fila())
    b = au.exportar_excel(df)
    assert b[:2] == b"PK"  # los .xlsx son zips


# ─── catálogo ─────────────────────────────────────────────────
def test_toda_accion_del_catalogo_tiene_etiqueta_y_color():
    for cod, meta in au.ACCIONES.items():
        assert meta["label"] and meta["color"].startswith("#"), cod


def test_las_acciones_de_escritura_estan_en_el_catalogo():
    for a in au.ACCIONES_ESCRITURA:
        assert a in au.ACCIONES


def test_columnas_coinciden_con_el_ddl():
    """El módulo y la tabla no pueden desincronizarse sin que un test lo note."""
    ruta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "migration_auditoria.sql")
    with open(ruta, encoding="utf-8") as fh:
        sql = fh.read()
    cuerpo = sql.split("CREATE TABLE IF NOT EXISTS auditoria (", 1)[1].split("\n);", 1)[0]
    cols = []
    for linea in cuerpo.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith(("--", "CONSTRAINT", "UNIQUE")):
            continue
        cols.append(linea.split()[0])
    assert cols == au.COLUMNAS


def test_el_ddl_no_habilita_borrar_ni_editar_la_auditoria():
    """El log es append-only: si alguien agrega una policy de DELETE, salta acá."""
    ruta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "migration_auditoria.sql")
    with open(ruta, encoding="utf-8") as fh:
        # Sin los comentarios: el texto que explica por qué NO hay FOR ALL
        # contiene esa misma frase y daría un falso positivo.
        sql = "\n".join(l for l in fh.read().splitlines()
                        if not l.strip().startswith("--")).upper()
    assert "FOR INSERT" in sql and "FOR SELECT" in sql
    assert "FOR DELETE" not in sql
    assert "FOR UPDATE" not in sql
    assert "FOR ALL" not in sql
