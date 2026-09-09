"""Tests de la lógica de Minutas de reunión (sin Streamlit)."""

import os
import sys
from datetime import date

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import minutas as mn  # noqa: E402


HOY = date(2026, 9, 8)


def _df(filas):
    """Frame de minutas con las columnas de la base."""
    return pd.DataFrame(filas, columns=mn.columnas_db())


# ─── Catálogo de estados ─────────────────────────────────────
def test_hay_tres_estados_en_orden_de_progresion():
    assert mn.ESTADOS == ("Pendiente", "En curso", "Completa")
    assert mn.estado_valido("Pendiente")
    assert mn.estado_valido("Completa")
    assert not mn.estado_valido("cerrada")
    assert not mn.estado_valido(None)


def test_cada_estado_tiene_color():
    for e in mn.ESTADOS:
        assert mn.color_estado(e).startswith("#")
    # Vencida pinta rojo aunque el estado sea otro.
    assert mn.color_estado("Pendiente", vencida=True) == mn.COLOR_VENCIDA


def test_columnas_db_incluye_los_campos_del_formulario():
    cols = mn.columnas_db()
    for c in ("fecha", "tema", "descripcion", "responsable",
              "fecha_limite", "estado"):
        assert c in cols


# ─── Vencimiento ─────────────────────────────────────────────
def test_es_vencida_solo_si_paso_la_fecha_y_no_esta_completa():
    ayer = date(2026, 9, 7)
    manana = date(2026, 9, 9)
    assert mn.es_vencida({"estado": "Pendiente", "fecha_limite": ayer}, HOY)
    assert mn.es_vencida({"estado": "En curso", "fecha_limite": ayer}, HOY)
    # Completa nunca vence.
    assert not mn.es_vencida({"estado": "Completa", "fecha_limite": ayer}, HOY)
    # Con fecha futura no vence.
    assert not mn.es_vencida({"estado": "Pendiente", "fecha_limite": manana}, HOY)
    # Sin fecha límite no puede vencer.
    assert not mn.es_vencida({"estado": "Pendiente", "fecha_limite": None}, HOY)


def test_es_vencida_acepta_fecha_como_texto_iso():
    assert mn.es_vencida({"estado": "Pendiente", "fecha_limite": "2026-09-01"}, HOY)
    assert not mn.es_vencida({"estado": "Pendiente", "fecha_limite": ""}, HOY)
    assert not mn.es_vencida({"estado": "Pendiente", "fecha_limite": "basura"}, HOY)


def test_hoy_mismo_no_esta_vencida():
    # Vence recién a partir del día siguiente al límite.
    assert not mn.es_vencida({"estado": "Pendiente", "fecha_limite": HOY}, HOY)


def test_marcar_vencidas_agrega_columna_booleana():
    df = _df([
        {"estado": "Pendiente", "fecha_limite": date(2026, 9, 1)},
        {"estado": "Completa",  "fecha_limite": date(2026, 9, 1)},
        {"estado": "En curso",  "fecha_limite": None},
    ])
    out = mn.marcar_vencidas(df, HOY)
    assert list(out["vencida"]) == [True, False, False]


def test_marcar_vencidas_en_frame_vacio_no_rompe():
    out = mn.marcar_vencidas(_df([]), HOY)
    assert "vencida" in out.columns
    assert out.empty


# ─── Regresión: NaT (fecha vacía) es instancia de date ───────
# Bug real: una minuta cargada SIN fecha límite llega como pd.NaT; como NaT ES
# instancia de date, un `isinstance(x, date)` la dejaba pasar y NaT.strftime()
# reventaba la página. to_date debe devolver None para NaT.
def test_to_date_descarta_nat_none_y_vacios():
    assert mn.to_date(pd.NaT) is None
    assert mn.to_date(None) is None
    assert mn.to_date("") is None
    assert mn.to_date("basura") is None
    assert mn.to_date("2026-09-09") == date(2026, 9, 9)
    assert mn.to_date(date(2026, 9, 9)) == date(2026, 9, 9)
    assert mn.to_date(pd.Timestamp("2026-09-09")) == date(2026, 9, 9)


def test_es_vencida_con_nat_no_rompe():
    assert mn.es_vencida({"estado": "Pendiente", "fecha_limite": pd.NaT}, HOY) is False


def test_marcar_vencidas_con_fecha_limite_null():
    # Reproduce lo que devuelve _leer() cuando fecha_limite viene NULL de la base.
    df = _df([{"tema": "x", "estado": "Pendiente", "fecha_limite": pd.NaT, "fecha": HOY}])
    out = mn.marcar_vencidas(df, HOY)
    assert list(out["vencida"]) == [False]
    # Y el resumen sigue funcionando.
    r = mn.resumen_estado(out, HOY)
    assert r["vencidas"] == 0 and r["por_estado"]["Pendiente"] == 1


# ─── Resumen del banner ──────────────────────────────────────
def test_resumen_cuenta_por_estado_y_vencidas():
    df = _df([
        {"estado": "Pendiente", "fecha_limite": date(2026, 9, 1)},   # vencida
        {"estado": "Pendiente", "fecha_limite": date(2026, 12, 1)},
        {"estado": "En curso",  "fecha_limite": date(2026, 9, 1)},   # vencida
        {"estado": "Completa",  "fecha_limite": date(2026, 9, 1)},
    ])
    r = mn.resumen_estado(df, HOY)
    assert r["total"] == 4
    assert r["por_estado"]["Pendiente"] == 2
    assert r["por_estado"]["En curso"] == 1
    assert r["por_estado"]["Completa"] == 1
    assert r["vencidas"] == 2
    assert r["pct_completas"] == 25.0


def test_resumen_de_frame_vacio():
    r = mn.resumen_estado(_df([]), HOY)
    assert r["total"] == 0
    assert r["vencidas"] == 0
    assert r["por_estado"] == {"Pendiente": 0, "En curso": 0, "Completa": 0}
    assert pd.isna(r["pct_completas"])


# ─── Orden del listado ───────────────────────────────────────
def test_ordenar_pone_vencidas_arriba_y_completas_al_final():
    df = _df([
        {"tema": "completa",  "estado": "Completa",  "fecha_limite": date(2026, 9, 1)},
        {"tema": "sin_fl",    "estado": "Pendiente", "fecha_limite": None},
        {"tema": "vencida",   "estado": "Pendiente", "fecha_limite": date(2026, 9, 1)},
        {"tema": "futura",    "estado": "En curso",  "fecha_limite": date(2026, 12, 1)},
    ])
    orden = list(mn.ordenar(df, HOY)["tema"])
    assert orden[0] == "vencida"          # vencida primero
    assert orden[-1] == "completa"        # completa al final
    assert orden.index("futura") < orden.index("sin_fl")  # con fecha antes que sin fecha


# ─── Payload de insert ───────────────────────────────────────
def test_construir_payload_normaliza_fechas_y_vacios():
    p = mn.construir_payload(
        fecha=date(2026, 9, 8), tema="  Revisar EPP  ",
        descripcion="   ", responsable="",
        fecha_limite=date(2026, 9, 20), estado="Pendiente",
        registrado_por="lu",
    )
    assert p["fecha"] == "2026-09-08"
    assert p["fecha_limite"] == "2026-09-20"
    assert p["tema"] == "Revisar EPP"        # sin espacios
    assert p["descripcion"] is None          # vacío → NULL
    assert p["responsable"] is None          # vacío → NULL
    assert p["estado"] == "Pendiente"
    assert p["registrado_por"] == "lu"


def test_construir_payload_sin_fecha_limite():
    p = mn.construir_payload(
        fecha=date(2026, 9, 8), tema="X", descripcion="d", responsable="Flor",
        fecha_limite=None, estado="En curso", registrado_por="flor",
    )
    assert p["fecha_limite"] is None
    assert p["responsable"] == "Flor"


# ─── Exportación ─────────────────────────────────────────────
def test_export_tiene_encabezados_legibles_y_vencida_si_no():
    df = _df([
        {"fecha": date(2026, 9, 8), "tema": "T", "descripcion": "d",
         "responsable": "Lu", "fecha_limite": date(2026, 9, 1),
         "estado": "Pendiente", "registrado_por": "lu"},
    ])
    out = mn.preparar_export(df, HOY)
    assert "Tema o acción" in out.columns
    assert "Fecha límite" in out.columns
    assert list(out["Vencida"]) == ["Sí"]


def test_exportar_excel_devuelve_bytes():
    df = _df([
        {"fecha": date(2026, 9, 8), "tema": "T", "descripcion": "d",
         "responsable": "Lu", "fecha_limite": None,
         "estado": "Completa", "registrado_por": "lu"},
    ])
    data = mn.exportar_excel(df, HOY)
    assert isinstance(data, bytes) and len(data) > 0


def test_exportar_excel_vacio_no_rompe():
    data = mn.exportar_excel(_df([]), HOY)
    assert isinstance(data, bytes) and len(data) > 0
