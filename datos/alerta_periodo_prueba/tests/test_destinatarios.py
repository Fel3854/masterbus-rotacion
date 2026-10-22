"""A quién se avisa: sólo personal del Grupo Master, y los conductores en plural también."""

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main  # noqa: E402


def _empleado(id_empleado="1", cargo="CONDUCTOR", empleador="MASTER BUS S.A", dias=160):
    """Un empleado activo, sin baja, con `dias` de antigüedad (160 cae en el mes 5)."""
    return {"id_empleado": id_empleado, "cargo": cargo, "empleador": empleador,
            "activo": "1", "fechafin": "00/00/0000",
            "fechainicio": (date.today() - timedelta(days=dias)).strftime("%d/%m/%Y")}


def _ids(empleados):
    return [e["id_empleado"] for e in empleados]


# ─── Conductores ──────────────────────────────────────────────

def test_conductores_en_plural_van_al_mismo_gerente_que_en_singular():
    # Desde 2022 casi todos se cargan como CONDUCTORES; el mapeo sólo tenía CONDUCTOR.
    grupos = main.agrupar_por_gerente([_empleado("1", "CONDUCTOR"), _empleado("2", "CONDUCTORES"),
                                       _empleado("3", " conductores ")])
    assert grupos == {main.CARGO_GERENTE["CONDUCTOR"]: [
        _empleado("1", "CONDUCTOR"), _empleado("2", "CONDUCTORES"), _empleado("3", " conductores ")]}


def test_un_cargo_sin_gerente_sigue_sin_avisarse():
    assert main.agrupar_por_gerente([_empleado("1", "OPERADORES DE PLANTA")]) == {}


def test_los_demas_cargos_no_cambian():
    grupos = main.agrupar_por_gerente([_empleado("1", "MECANICO")])
    assert grupos == {main.CARGO_GERENTE["MECANICO"]: [_empleado("1", "MECANICO")]}


# ─── Sólo Grupo Master ────────────────────────────────────────

def test_solo_avisa_por_el_personal_del_grupo_master():
    empleados = [_empleado("1", empleador="MASTER BUS S.A"), _empleado("2", empleador="SINTRA"),
                 _empleado("3", empleador="PLUSMAR"), _empleado("4", empleador="AUTERI ADRIAN ANGEL")]
    assert _ids(main.filtrar_empleados_mes5(empleados, {}, 150, 180)) == ["1", "2"]


def test_el_empleador_se_compara_sin_espacios():
    empleados = [_empleado("1", empleador=" SINTRA ")]
    assert _ids(main.filtrar_empleados_mes5(empleados, {}, 150, 180)) == ["1"]


def test_las_empresas_son_las_mismas_que_las_del_dashboard():
    assert main.GRUPO_MASTER == {
        "MASTER BUS S.A", "MASTER BUS SA", "MASTER BUS TASA", "SINTRA", "M B M S.A.",
        "MASTER MINING SA", "SOLUCIONES IOT S.A.", "ENDUROCO LATAM SA"}


def test_el_filtro_de_mes_5_sigue_igual():
    empleados = [_empleado("1", dias=149), _empleado("2", dias=150), _empleado("3", dias=180),
                 _empleado("4", dias=181), _empleado("5", dias=160)]
    notificados = {"5": "2026-10-01"}
    assert _ids(main.filtrar_empleados_mes5(empleados, notificados, 150, 180)) == ["2", "3"]
