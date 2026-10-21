"""Tests unitarios para el script de alertas de período de prueba."""

import sys
import os
from datetime import date, timedelta

# Agregar el directorio padre al path para importar main
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import (
    parse_fecha,
    fechafin_vacia,
    filtrar_empleados_mes5,
    agrupar_por_gerente,
)


# ─── parse_fecha ─────────────────────────────────────────────

def test_parse_fecha_valida():
    assert parse_fecha("15/03/2023") == date(2023, 3, 15)


def test_parse_fecha_invalida_ceros():
    assert parse_fecha("00/00/0000") is None


def test_parse_fecha_vacia():
    assert parse_fecha("") is None


def test_parse_fecha_none():
    assert parse_fecha(None) is None


def test_parse_fecha_formato_incorrecto():
    assert parse_fecha("2023-03-15") is None


# ─── fechafin_vacia ──────────────────────────────────────────

def test_fechafin_vacia_con_none():
    assert fechafin_vacia({"fechafin": None}) is True


def test_fechafin_vacia_con_ceros():
    assert fechafin_vacia({"fechafin": "00/00/0000"}) is True


def test_fechafin_vacia_con_string_vacio():
    assert fechafin_vacia({"fechafin": ""}) is True


def test_fechafin_vacia_con_fecha_real():
    assert fechafin_vacia({"fechafin": "01/01/2024"}) is False


def test_fechafin_vacia_sin_campo():
    assert fechafin_vacia({}) is True


# ─── filtrar_empleados_mes5 ──────────────────────────────────

def _emp(dias_desde_hoy: int, activo: str = "1", id_emp: str = "EMP001") -> dict:
    """Helper: crea un empleado con fecha de ingreso hace N días."""
    fecha_inicio = (date.today() - timedelta(days=dias_desde_hoy)).strftime("%d/%m/%Y")
    return {
        "id_empleado": id_emp,
        "activo": activo,
        "fechainicio": fecha_inicio,
        "fechafin": None,
        "cargo": "CONDUCTOR",
        "apenom": "TEST EMPLEADO",
        "legajo": "12345",
        "empleador": "MASTER BUS S.A",
    }


def test_filtrar_detecta_empleado_en_mes5():
    emp = _emp(dias_desde_hoy=160)
    resultado = filtrar_empleados_mes5([emp], {}, 150, 180)
    assert len(resultado) == 1
    assert resultado[0]["_dias_en_empresa"] == 160


def test_filtrar_ignora_empleado_fuera_de_rango():
    emp_temprano = _emp(dias_desde_hoy=100, id_emp="E1")
    emp_tarde = _emp(dias_desde_hoy=200, id_emp="E2")
    resultado = filtrar_empleados_mes5([emp_temprano, emp_tarde], {}, 150, 180)
    assert len(resultado) == 0


def test_filtrar_ignora_inactivos():
    emp = _emp(dias_desde_hoy=160, activo="0")
    resultado = filtrar_empleados_mes5([emp], {}, 150, 180)
    assert len(resultado) == 0


def test_filtrar_ignora_ya_notificados():
    emp = _emp(dias_desde_hoy=160)
    notificados = {"EMP001": {"fecha_notificacion": "01/01/2026"}}
    resultado = filtrar_empleados_mes5([emp], notificados, 150, 180)
    assert len(resultado) == 0


def test_filtrar_ignora_empleado_con_fecha_fin():
    emp = _emp(dias_desde_hoy=160)
    emp["fechafin"] = "01/06/2026"
    resultado = filtrar_empleados_mes5([emp], {}, 150, 180)
    assert len(resultado) == 0


# ─── agrupar_por_gerente ─────────────────────────────────────

def test_agrupar_asigna_gerente_correcto():
    emp = _emp(dias_desde_hoy=160)
    mapping = {"CONDUCTOR": "gerente@empresa.com"}
    grupos = agrupar_por_gerente([emp], mapping)
    assert "gerente@empresa.com" in grupos
    assert len(grupos["gerente@empresa.com"]) == 1


def test_agrupar_ignora_cargo_sin_gerente():
    emp = _emp(dias_desde_hoy=160)
    emp["cargo"] = "CARGO_INEXISTENTE"
    grupos = agrupar_por_gerente([emp], {})
    assert len(grupos) == 0


def test_agrupar_multiples_empleados_mismo_gerente():
    emp1 = _emp(dias_desde_hoy=155, id_emp="E1")
    emp2 = _emp(dias_desde_hoy=170, id_emp="E2")
    mapping = {"CONDUCTOR": "gerente@empresa.com"}
    grupos = agrupar_por_gerente([emp1, emp2], mapping)
    assert len(grupos["gerente@empresa.com"]) == 2


def test_agrupar_distribuye_a_distintos_gerentes():
    emp1 = _emp(dias_desde_hoy=160, id_emp="E1")
    emp2 = _emp(dias_desde_hoy=160, id_emp="E2")
    emp2["cargo"] = "ADMINISTRATIVO"
    mapping = {"CONDUCTOR": "g1@empresa.com", "ADMINISTRATIVO": "g2@empresa.com"}
    grupos = agrupar_por_gerente([emp1, emp2], mapping)
    assert len(grupos) == 2
    assert "g1@empresa.com" in grupos
    assert "g2@empresa.com" in grupos
