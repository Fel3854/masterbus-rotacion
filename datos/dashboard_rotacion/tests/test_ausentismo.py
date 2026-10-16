"""Tests de ausentismo.py y de la página Ausentismo. Sin red: la API se simula."""

import base64
import json
import os
import re
import sys
from datetime import date

import numpy as np
import pandas as pd
import pytest
import requests
import streamlit as st
from streamlit.testing.v1 import AppTest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ausentismo as aus  # noqa: E402
import utils  # noqa: E402

HOY = date(2026, 10, 15)

# Relevados de la API real el 15/10/2026.
NO_SON_AUSENCIA = [
    "Franco", "Feriado", "FRANCO/FERIADO", "Franco trabajado", "Feriado trabajado",
    "Franco compensatorio", "Adeuda Dia", "Devuelve Dia", "Compensa dia",
    "AJUSTE FRANCOS", "DIA FLEX", "Control de ausentismo",
]
SON_AUSENCIA = [
    "Vacaciones", "Enfermedad", "Ausencia injustificada", "Jornada Incompleta",
    "Suspension", "Ausencia con aviso", "Constancia de Atencion Medica",
    "Accidente Laboral", "CUARENTENA", "Licencia por Fallecimiento", "Permiso Gremial",
    "LICENCIA COVID", "SUSPENSION X REGISTRO", "Licencia por Examen",
    "LICENCIA VACUNACION", "Licencia por Maternidad", "Licencia Especial",
    "Ausencia sin aviso", "Licencia Judicial", "Renovacion Examen Periodico",
    "Licencia por Matrimonio", "Donacion de sangre", "Renovacion Registro",
    "ART COVID-19", "Asistencia a curso", "Citacion Medica", "LICENCIA S/GOCE",
    "Res. puesto trabajo", "LICENCIA POR REGISTRO", "Mudanza", "AUSENCIA JUSTIFICADA",
    "Accidente en itinerario", "Periodo de Excendencia",
]


def _json(*registros):
    """La respuesta cruda de la API, con todos los campos que trae."""
    return json.dumps([
        {"desde": desde, "hasta": hasta, "novedad": novedad, "apellido": "PEREZ",
         "nombre": "JUAN", "legajo": legajo, "id_empleado": id_empleado}
        for id_empleado, legajo, novedad, desde, hasta in registros
    ]).encode()


def _respuesta(status, contenido=b"[]"):
    r = requests.Response()
    r.status_code = status
    r._content = contenido
    r.url = aus.API_NOVEDADES_URL
    return r


def _norm(*registros, hoy=HOY):
    return aus.normalizar_novedades(list(registros), hoy)


def _padron(*filas):
    """Padrón como lo devuelve utils.cargar_datos() (columnas del cruce y vecinas)."""
    columnas = ["id_empleado", "legajo", "apenom", "empleador", "cargo", "str",
                "activo", "fechainicio", "fechafin"]
    return pd.DataFrame([dict(zip(columnas, f + ("01/01/2015", "00/00/0000")))
                         for f in filas])


def _padron_de(registros):
    """Un padrón donde está cada persona de las novedades, todos conductores en Campana."""
    ids = sorted({r[0] for r in registros})
    return _padron(*[(i, "1", "X", "MASTER BUS S.A", "CONDUCTORES", "Operacion Campana", "1")
                     for i in ids])


def _dias(*registros, padron=None):
    cruzado, _ = aus.cruzar_padron(_norm(*registros),
                                   _padron_de(registros) if padron is None else padron)
    return aus.expandir_a_dias(cruzado)


def _fechas(serie_de_fechas):
    return [d.date() for d in serie_de_fechas]


# ─── Parseo de la API ─────────────────────────────────────────

def test_parseo_deja_las_ausencias_sin_nombres():
    crudo = _json(("1", "10", "Franco", "2024-01-06", "2024-01-06"),
                  ("1", "10", "Enfermedad", "2024-01-08", "2024-01-09"),
                  ("2", "20", "Vacaciones", "2024-02-01", "2024-02-14"))
    assert aus.parsear_novedades(crudo) == [
        ("1", "10", "Enfermedad", "2024-01-08", "2024-01-09"),
        ("2", "20", "Vacaciones", "2024-02-01", "2024-02-14"),
    ]


def test_parseo_descarta_cada_novedad_que_no_es_ausentismo():
    crudo = _json(*[("1", "10", t, "2024-01-01", "2024-01-01") for t in NO_SON_AUSENCIA])
    assert aus.parsear_novedades(crudo) == []


def test_parseo_limpia_espacios():
    crudo = _json((" 7 ", " 70 ", "Periodo de Excendencia ", "2024-03-01", "2024-03-31"))
    assert aus.parsear_novedades(crudo) == [
        ("7", "70", "Periodo de Excendencia", "2024-03-01", "2024-03-31")]


def test_parseo_rechaza_una_respuesta_que_no_es_lista():
    with pytest.raises(ValueError):
        aus.parsear_novedades(b'{"error": "mantenimiento"}')


def test_descarga_pide_la_api_de_novedades_y_parsea(monkeypatch):
    pedidos = []

    def get(url, timeout):
        pedidos.append(url)
        return _respuesta(200, _json(("1", "10", "Enfermedad", "2024-01-08", "2024-01-09")))

    monkeypatch.setattr(aus.requests, "get", get)
    assert aus.descargar_novedades() == [("1", "10", "Enfermedad", "2024-01-08", "2024-01-09")]
    assert pedidos == ["https://traficonuevo.masterbus.net/api/v1/auto"]


def test_descarga_falla_si_la_api_responde_error(monkeypatch):
    monkeypatch.setattr(aus.requests, "get", lambda url, timeout: _respuesta(503))
    with pytest.raises(requests.HTTPError):
        aus.descargar_novedades()


# ─── Definición: grupos y puestos ─────────────────────────────

def test_cada_tipo_de_ausencia_conocido_tiene_su_grupo():
    assert [t for t in SON_AUSENCIA if aus.grupo_de(t) == aus.GRUPO_OTRAS] == []


@pytest.mark.parametrize("novedad, grupo", [
    ("Enfermedad", "Enfermedad y salud"),
    ("CUARENTENA", "Enfermedad y salud"),
    ("Res. puesto trabajo", "Enfermedad y salud"),
    ("Accidente en itinerario", "Accidentes"),
    ("Ausencia injustificada", "Ausencias"),
    ("Jornada Incompleta", "Ausencias"),
    ("SUSPENSION X REGISTRO", "Suspensiones"),
    ("Permiso Gremial", "Licencias"),
    ("Asistencia a curso", "Licencias"),
    ("Vacaciones", "Vacaciones"),
    ("Algo que la API agregue mañana", "Otras"),
])
def test_grupo_de(novedad, grupo):
    assert aus.grupo_de(novedad) == grupo


def test_ninguna_novedad_excluida_tiene_grupo():
    assert set(aus.NOVEDADES_EXCLUIDAS) & set(aus.TIPO_A_GRUPO) == set()


@pytest.mark.parametrize("cargo, puesto", [
    ("CONDUCTORES", "CONDUCTORES"),
    ("CONDUCTOR", "CONDUCTORES"),
    (" conductor ", "CONDUCTORES"),
    ("Mecanico", "MECANICO"),
    ("", "Sin dato"),
    (None, "Sin dato"),
])
def test_normalizar_puesto(cargo, puesto):
    assert aus.normalizar_puesto(cargo) == puesto


# ─── Limpieza ─────────────────────────────────────────────────

def test_descarta_fechas_invalidas_e_invertidas():
    df = _norm(("1", "10", "Enfermedad", "2024-01-08", "2024-01-09"),
               ("2", "20", "Enfermedad", "00/00/0000", "2024-01-09"),
               ("3", "30", "Enfermedad", "2024-01-09", ""),
               ("4", "40", "Enfermedad", "2024-01-10", "2024-01-08"),
               ("5", "50", "Enfermedad", "0206-03-11", "0206-05-25"))
    assert list(df["id_empleado"]) == ["1"]


def test_descarta_registros_sin_persona_o_sin_novedad():
    assert _norm(("", "10", "Enfermedad", "2024-01-08", "2024-01-09"),
                 ("2", "20", "", "2024-01-08", "2024-01-09")).empty


def test_un_registro_repetido_cuenta_una_vez():
    r = ("1", "10", "Vacaciones", "2024-02-01", "2024-02-14")
    assert len(_norm(r, r)) == 1


def test_recorta_al_rango_entre_2014_y_hoy():
    df = _norm(("1", "10", "Enfermedad", "2013-12-30", "2014-01-02"),   # empieza antes de 2014
               ("2", "20", "Vacaciones", "2026-10-10", "2026-10-25"),   # termina después de hoy
               ("3", "30", "Vacaciones", "2026-12-01", "2026-12-15"),   # todavía no ocurrió
               ("4", "40", "Enfermedad", "2012-05-01", "2012-05-03"))   # todo antes de 2014
    rangos = {r.id_empleado: (r.desde.date(), r.hasta.date()) for r in df.itertuples()}
    assert rangos == {"1": (date(2014, 1, 1), date(2014, 1, 2)),
                      "2": (date(2026, 10, 10), date(2026, 10, 15))}


def test_cada_novedad_queda_con_su_grupo():
    df = _norm(("1", "10", "Accidente Laboral", "2024-01-08", "2024-01-09"))
    assert list(df["grupo"]) == ["Accidentes"]


# ─── Cruce con el padrón ──────────────────────────────────────

def test_cruza_por_id_empleado_aunque_el_legajo_se_repita_entre_empresas():
    novedades = _norm(("2", "100", "Enfermedad", "2024-01-08", "2024-01-09"))
    padron = _padron(("1", "100", "GOMEZ ANA", "SINTRA", "MECANICO", "Operacion Bragado", "1"),
                     ("2", "100", "PAZ LUIS", "MASTER BUS S.A", "CONDUCTOR", "Operacion Campana", "1"))
    cruzado, _ = aus.cruzar_padron(novedades, padron)
    fila = cruzado.iloc[0]
    assert (fila.sector, fila.puesto, fila.empleador) == (
        "Operacion Campana", "CONDUCTORES", "MASTER BUS S.A")


def test_lo_que_no_esta_en_el_padron_queda_afuera_y_se_informa():
    novedades = _norm(("1", "10", "Enfermedad", "2024-01-08", "2024-01-09"),
                      ("9", "90", "Enfermedad", "2024-01-08", "2024-01-09"),
                      ("9", "90", "Vacaciones", "2024-03-01", "2024-03-10"))
    padron = _padron(("1", "10", "PAZ LUIS", "MASTER BUS S.A", "MECANICO", "Operacion Sur", "1"))
    cruzado, afuera = aus.cruzar_padron(novedades, padron)
    assert list(cruzado["id_empleado"]) == ["1"]
    assert afuera == {"novedades": 2, "personas": 1}


def test_sector_vacio_queda_como_sin_dato():
    novedades = _norm(("1", "10", "Enfermedad", "2024-01-08", "2024-01-09"))
    padron = _padron(("1", "10", "PAZ LUIS", "MASTER BUS S.A", "MECANICO", " ", "1"))
    cruzado, _ = aus.cruzar_padron(novedades, padron)
    assert cruzado.iloc[0].sector == "Sin dato"


# ─── Expansión a días ─────────────────────────────────────────

def test_un_rango_se_convierte_en_un_dia_por_fecha():
    dias = _dias(("1", "10", "Enfermedad", "2024-01-30", "2024-02-02"))
    assert _fechas(dias["dia"]) == [date(2024, 1, 30), date(2024, 1, 31),
                                    date(2024, 2, 1), date(2024, 2, 2)]


def test_dos_registros_del_mismo_tipo_que_se_pisan_cuentan_cada_dia_una_vez():
    dias = _dias(("1", "10", "Enfermedad", "2024-01-01", "2024-01-03"),
                 ("1", "10", "Enfermedad", "2024-01-02", "2024-01-04"))
    assert _fechas(dias["dia"]) == [date(2024, 1, 1), date(2024, 1, 2),
                                    date(2024, 1, 3), date(2024, 1, 4)]


def test_un_dia_con_dos_tipos_distintos_cuenta_en_ambos():
    dias = _dias(("1", "10", "Enfermedad", "2024-01-01", "2024-01-01"),
                 ("1", "10", "Constancia de Atencion Medica", "2024-01-01", "2024-01-01"))
    assert sorted(dias["novedad"].astype(str)) == ["Constancia de Atencion Medica", "Enfermedad"]


def test_cada_dia_lleva_el_sector_y_el_puesto_de_la_persona():
    padron = _padron(("1", "10", "PAZ LUIS", "SINTRA", "CONDUCTOR", "Operacion Bragado", "1"))
    dias = _dias(("1", "10", "Enfermedad", "2024-01-01", "2024-01-02"), padron=padron)
    assert dias[["sector", "puesto"]].astype(str).drop_duplicates().values.tolist() == [
        ["Operacion Bragado", "CONDUCTORES"]]


# ─── Filtros ──────────────────────────────────────────────────

def _tres_personas():
    """Un conductor y un mecánico de Campana, y un conductor de Bragado: 9 días en total."""
    padron = _padron(("1", "10", "A", "MASTER BUS S.A", "CONDUCTOR", "Operacion Campana", "1"),
                     ("2", "20", "B", "MASTER BUS S.A", "MECANICO", "Operacion Campana", "1"),
                     ("3", "30", "C", "SINTRA", "CONDUCTORES", "Operacion Bragado", "1"))
    return _dias(("1", "10", "Enfermedad", "2024-01-10", "2024-01-11"),
                 ("2", "20", "Vacaciones", "2024-01-15", "2024-01-19"),
                 ("3", "30", "Ausencia injustificada", "2024-02-05", "2024-02-05"),
                 ("3", "30", "Ausencia con aviso", "2024-02-20", "2024-02-20"),
                 padron=padron)


def _personas(dias):
    return sorted(set(dias["id_empleado"].astype(str)))


def _novedades(dias):
    return sorted(set(dias["novedad"].astype(str)))


TODO_2024 = (date(2024, 1, 1), date(2024, 12, 31))


def test_sin_filtros_queda_todo_el_rango():
    assert len(aus.filtrar(_tres_personas(), *TODO_2024)) == 9


def test_filtra_por_fechas_incluyendo_los_extremos():
    f = aus.filtrar(_tres_personas(), date(2024, 1, 11), date(2024, 1, 15))
    assert _fechas(f["dia"]) == [date(2024, 1, 11), date(2024, 1, 15)]


def test_filtra_conductores_de_un_sector():
    f = aus.filtrar(_tres_personas(), *TODO_2024,
                    sectores=["Operacion Campana"], puestos=["CONDUCTORES"])
    assert _personas(f) == ["1"]


def test_filtra_conductores_de_todos_los_sectores():
    assert _personas(aus.filtrar(_tres_personas(), *TODO_2024, puestos=["CONDUCTORES"])) == ["1", "3"]


def test_filtra_por_grupo():
    f = aus.filtrar(_tres_personas(), *TODO_2024, grupos=["Ausencias"])
    assert _novedades(f) == ["Ausencia con aviso", "Ausencia injustificada"]


def test_filtra_por_novedad_dentro_del_grupo():
    f = aus.filtrar(_tres_personas(), *TODO_2024, grupos=["Ausencias"],
                    novedades=["Ausencia injustificada"])
    assert _novedades(f) == ["Ausencia injustificada"]


# ─── Serie por período ────────────────────────────────────────

def test_serie_mensual_reparte_un_rango_entre_meses():
    dias = _dias(("1", "10", "Enfermedad", "2024-01-30", "2024-02-02"))
    s = aus.serie(dias, "Mensual", date(2024, 1, 1), date(2024, 2, 29))
    assert _fechas(s.index) == [date(2024, 1, 1), date(2024, 2, 1)]
    assert s["Enfermedad y salud"].tolist() == [2, 2]


def test_serie_incluye_los_periodos_sin_ausencias_en_cero():
    dias = _dias(("1", "10", "Enfermedad", "2024-01-10", "2024-01-10"))
    s = aus.serie(dias, "Mensual", date(2024, 1, 1), date(2024, 3, 31))
    assert s["Total"].tolist() == [1, 0, 0]


def test_serie_sin_datos_tiene_todos_los_periodos_en_cero():
    vacio = aus.filtrar(_tres_personas(), date(2030, 1, 1), date(2030, 1, 2))
    s = aus.serie(vacio, "Mensual", date(2024, 1, 1), date(2024, 2, 29))
    assert list(s.columns) == ["Total"]
    assert s["Total"].tolist() == [0, 0]


def test_las_semanas_van_de_lunes_a_domingo():
    # El 7/1/2024 es domingo y el 8/1/2024 lunes: caen en semanas distintas.
    dias = _dias(("1", "10", "Enfermedad", "2024-01-07", "2024-01-08"))
    s = aus.serie(dias, "Semanal", date(2024, 1, 1), date(2024, 1, 14))
    assert _fechas(s.index) == [date(2024, 1, 1), date(2024, 1, 8)]
    assert s["Total"].tolist() == [1, 1]


def test_serie_diaria():
    dias = _dias(("1", "10", "Enfermedad", "2024-01-30", "2024-02-01"))
    s = aus.serie(dias, "Diaria", date(2024, 1, 29), date(2024, 2, 2))
    assert s["Total"].tolist() == [0, 1, 1, 1, 0]


def test_columnas_en_el_orden_de_la_pila_con_el_total_al_final():
    dias = _dias(("1", "10", "Vacaciones", "2024-01-02", "2024-01-03"),
                 ("1", "10", "Accidente Laboral", "2024-01-10", "2024-01-10"),
                 ("1", "10", "Enfermedad", "2024-01-20", "2024-01-20"),
                 ("1", "10", "Algo nuevo", "2024-01-25", "2024-01-25"))
    s = aus.serie(dias, "Mensual", date(2024, 1, 1), date(2024, 1, 31))
    assert list(s.columns) == ["Enfermedad y salud", "Accidentes", "Vacaciones", "Otras", "Total"]
    assert s.iloc[0].tolist() == [1, 1, 2, 1, 5]


def test_serie_filtrada_no_trae_columnas_de_grupos_sin_dias():
    f = aus.filtrar(_tres_personas(), *TODO_2024, grupos=["Vacaciones"])
    s = aus.serie(f, "Mensual", date(2024, 1, 1), date(2024, 2, 29))
    assert list(s.columns) == ["Vacaciones", "Total"]


def test_marca_los_periodos_que_el_rango_deja_por_la_mitad():
    inicios = pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"])
    assert aus.incompletos(inicios, "Mensual", date(2024, 1, 15), date(2024, 3, 10)) == [
        True, False, True]


def test_periodos_completos_no_se_marcan():
    inicios = pd.to_datetime(["2024-01-01", "2024-01-08"])
    assert aus.incompletos(inicios, "Semanal", date(2024, 1, 1), date(2024, 1, 14)) == [
        False, False]


@pytest.mark.parametrize("pedida, desde, hasta, esperada", [
    ("Diaria", date(2024, 1, 1), date(2024, 12, 31), ("Diaria", False)),   # 366 días: entra
    ("Diaria", date(2024, 1, 1), date(2025, 1, 1), ("Semanal", True)),     # 367 días: no
    ("Mensual", date(2014, 1, 1), date(2026, 10, 15), ("Mensual", False)),
])
def test_granularidad_efectiva(pedida, desde, hasta, esperada):
    assert aus.granularidad_efectiva(pedida, desde, hasta) == esperada


# ─── Resumen y KPIs ───────────────────────────────────────────

def _dos_tipos():
    return _dias(("1", "10", "Enfermedad", "2024-01-01", "2024-01-03"),   # 3 días
                 ("2", "20", "Enfermedad", "2024-01-01", "2024-01-01"),   # 1 día
                 ("1", "10", "Vacaciones", "2024-02-01", "2024-02-06"))   # 6 días


def test_resumen_por_tipo_de_mayor_a_menor_con_su_parte_del_total():
    assert aus.resumen_por_tipo(_dos_tipos()).to_dict("records") == [
        {"grupo": "Vacaciones", "novedad": "Vacaciones", "dias": 6, "personas": 1, "pct": 60.0},
        {"grupo": "Enfermedad y salud", "novedad": "Enfermedad", "dias": 4, "personas": 2,
         "pct": 40.0},
    ]


def test_resumen_no_lista_tipos_que_el_filtro_dejo_sin_dias():
    f = aus.filtrar(_dos_tipos(), *TODO_2024, grupos=["Vacaciones"])
    assert aus.resumen_por_tipo(f)["novedad"].tolist() == ["Vacaciones"]


def test_kpis():
    assert aus.kpis(_dos_tipos()) == {"dias": 10, "personas": 2, "promedio": 5.0}


def test_kpis_sin_datos():
    vacio = aus.filtrar(_dos_tipos(), date(2030, 1, 1), date(2030, 1, 2))
    assert aus.kpis(vacio) == {"dias": 0, "personas": 0, "promedio": 0.0}


# ─── Página (AppTest; la API se simula con respuestas reales de requests) ─────

PAGINA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "pages", "10_Ausentismo.py")

PADRON_PAGINA = [
    ("1", "10", "PAZ LUIS", "MASTER BUS S.A", "CONDUCTOR", "Operacion Campana", "1"),
    ("2", "20", "GOMEZ ANA", "MASTER BUS S.A", "MECANICO", "Operacion Campana", "1"),
    ("3", "30", "SOSA EVA", "SINTRA", "CONDUCTORES", "Operacion Bragado", "1"),
]
NOVEDADES_PAGINA = [
    ("1", "10", "Enfermedad", "2024-01-10", "2024-01-11"),              # conductor de Campana: 2 días
    ("2", "20", "Vacaciones", "2024-01-15", "2024-01-19"),              # mecánica de Campana: 5 días
    ("3", "30", "Ausencia injustificada", "2024-02-05", "2024-02-05"),  # conductora de Bragado: 1 día
    ("3", "30", "Franco", "2024-02-06", "2024-02-06"),                  # no es ausentismo
    ("9", "90", "Enfermedad", "2024-01-10", "2024-01-12"),              # no está en el padrón
]


def _json_padron(*filas):
    """El padrón (/auto/e) con todos los campos que trae la API."""
    return json.dumps([
        {"activo": activo, "apenom": apenom, "banco": "", "cargo": cargo, "cbu": "",
         "ciudad": "Zárate", "cuil": "", "domicilio": "", "email": "", "empleador": empleador,
         "fechafin": "00/00/0000", "fechainicio": "01/01/2015", "fechanac": "01/01/1980",
         "id_empleado": id_empleado, "legajo": legajo, "nrodoc": "", "str": sector,
         "telefono": ""}
        for id_empleado, legajo, apenom, empleador, cargo, sector, activo in filas
    ]).encode()


def _api(novedades, padron, falla):
    def get(url, timeout):
        if falla:
            raise requests.ConnectionError("sin conexión")
        if url == aus.API_NOVEDADES_URL:
            return _respuesta(200, _json(*novedades))
        if url == utils.API_URL:
            return _respuesta(200, _json_padron(*padron))
        raise AssertionError(f"pedido inesperado a {url}")
    return get


def _pagina(monkeypatch, novedades=NOVEDADES_PAGINA, padron=PADRON_PAGINA, falla=False):
    """La página sobre la API simulada, con el rango en el primer trimestre de 2024."""
    st.cache_data.clear()
    monkeypatch.setattr(requests, "get", _api(novedades, padron, falla))
    at = AppTest.from_file(PAGINA, default_timeout=30).run()
    if not at.error:
        at.date_input(key="aus_desde").set_value(date(2024, 1, 1))
        at.date_input(key="aus_hasta").set_value(date(2024, 3, 31))
        at.run()
    return at


def _kpi(at, etiqueta):
    for md in at.markdown:
        m = re.search(rf'kpi-label">{etiqueta}</div><div class="kpi-value">([^<]*)<', md.value)
        if m:
            return m.group(1)
    raise AssertionError(f"no está el KPI «{etiqueta}»")


def _figura(at):
    graficos = at.get("plotly_chart")
    assert len(graficos) == 1
    return json.loads(graficos[0].proto.spec)


def _valores(v):
    """Plotly 6 manda los arrays de numpy en base64; las listas quedan como listas."""
    if isinstance(v, dict) and "bdata" in v:
        return np.frombuffer(base64.b64decode(v["bdata"]), dtype=np.dtype(v["dtype"])).tolist()
    return list(v)


def _barras(at):
    return {t["name"]: _valores(t["y"]) for t in _figura(at)["data"] if t["type"] == "bar"}


def _colores(at):
    return {t["name"]: t["marker"]["color"] for t in _figura(at)["data"] if t["type"] == "bar"}


def test_pagina_cuenta_las_ausencias_del_grupo_master_en_el_rango(monkeypatch):
    at = _pagina(monkeypatch)
    assert not at.exception
    assert _kpi(at, "Días de ausencia") == "8"
    assert _kpi(at, "Personas con ausencias") == "3"
    assert _kpi(at, "Días por persona") == "2,7"
    assert _barras(at) == {"Enfermedad y salud": [2, 0, 0], "Ausencias": [0, 1, 0],
                           "Vacaciones": [5, 0, 0]}


def test_las_barras_se_apilan_en_el_orden_de_la_definicion(monkeypatch):
    barras = [t["name"] for t in _figura(_pagina(monkeypatch))["data"] if t["type"] == "bar"]
    assert barras == ["Enfermedad y salud", "Ausencias", "Vacaciones"]


def test_filtro_de_puesto_deja_solo_conductores(monkeypatch):
    at = _pagina(monkeypatch)
    at.multiselect(key="aus_puesto").set_value(["CONDUCTORES"]).run()
    assert _kpi(at, "Personas con ausencias") == "2"
    assert _barras(at) == {"Enfermedad y salud": [2, 0, 0], "Ausencias": [0, 1, 0]}


def test_filtro_de_sector(monkeypatch):
    at = _pagina(monkeypatch)
    at.multiselect(key="aus_sector").set_value(["Operacion Bragado"]).run()
    assert _barras(at) == {"Ausencias": [0, 1, 0]}


def test_sacar_vacaciones_de_los_tipos(monkeypatch):
    at = _pagina(monkeypatch)
    at.multiselect(key="aus_grupo").set_value(["Enfermedad y salud", "Ausencias"]).run()
    assert _kpi(at, "Días de ausencia") == "3"


def test_filtrar_grupos_no_cambia_el_color_de_los_que_quedan(monkeypatch):
    at = _pagina(monkeypatch)
    antes = _colores(at)["Ausencias"]
    at.multiselect(key="aus_grupo").set_value(["Ausencias"]).run()
    assert _colores(at) == {"Ausencias": antes}


def test_por_semana(monkeypatch):
    at = _pagina(monkeypatch)
    at.radio(key="aus_gran").set_value("Semanal").run()
    assert len(_figura(at)["data"][0]["x"]) == 13   # del lunes 1/1 al domingo 31/3/2024
    assert sum(sum(v) for v in _barras(at).values()) == 8


def test_dia_por_dia_con_mas_de_un_anio_agrupa_por_semana_y_avisa(monkeypatch):
    at = _pagina(monkeypatch)
    at.date_input(key="aus_desde").set_value(date(2023, 1, 1))
    at.radio(key="aus_gran").set_value("Diaria").run()
    assert len(at.info) == 1
    assert len(_figura(at)["data"][0]["x"]) == 66   # semanas del 26/12/2022 al 31/3/2024


def test_una_novedad_elegida_cuyo_tipo_se_saca_no_rompe_la_pagina(monkeypatch):
    at = _pagina(monkeypatch)
    at.multiselect(key="aus_novedad").set_value(["Ausencia injustificada"]).run()
    at.multiselect(key="aus_grupo").set_value(["Vacaciones"]).run()
    assert not at.exception
    assert at.multiselect(key="aus_novedad").value == []
    assert _barras(at) == {"Vacaciones": [5, 0, 0]}


def test_los_periodos_que_el_rango_corta_se_ven_mas_claros(monkeypatch):
    at = _pagina(monkeypatch)
    at.date_input(key="aus_desde").set_value(date(2024, 1, 15)).run()
    opacidad = _valores(_figura(at)["data"][0]["marker"]["opacity"])
    assert opacidad[0] < 1 and opacidad[1:] == [1, 1]


def test_sin_ausencias_para_los_filtros_avisa_y_no_grafica(monkeypatch):
    at = _pagina(monkeypatch)
    at.multiselect(key="aus_sector").set_value(["Operacion Bragado"])
    at.multiselect(key="aus_grupo").set_value(["Vacaciones"]).run()
    assert not at.exception
    assert any("No hay ausencias" in i.value for i in at.info)
    assert at.get("plotly_chart") == []


def test_avisa_lo_que_queda_fuera_del_padron(monkeypatch):
    at = _pagina(monkeypatch)
    assert any("1 novedad de 1 persona" in c.value for c in at.caption)


def test_si_la_api_no_responde_muestra_un_error(monkeypatch):
    at = _pagina(monkeypatch, falla=True)
    assert not at.exception
    assert len(at.error) == 1
