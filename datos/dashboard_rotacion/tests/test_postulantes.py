"""Tests de la lógica de Postulantes (sin Streamlit ni red).

Todos los datos de este archivo son inventados: el registro real tiene nombres,
DNI y notas de postulantes, y nada de eso puede entrar al repositorio.
"""

import json
import os
import sys
from datetime import date, datetime, timezone
from io import BytesIO
from types import SimpleNamespace

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import postulantes as pt  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ─── Constructores ───────────────────────────────────────────
def _fila(numero, **campos):
    """Una entrevista con las columnas de la base; lo que no se pasa queda vacío."""
    fila = {c: None for c in pt.COLUMNAS_DB}
    fila.update({"numero_orden": numero, "apto": False})
    fila.update(campos)
    return fila


def _base(*filas):
    return pd.DataFrame(list(filas), columns=pt.COLUMNAS_DB)


def _enriquecida(*filas):
    return pt.enriquecer(_base(*filas))


def _archivo(*filas):
    """Tabla cruda como sale de Access: encabezados originales."""
    columnas = [e for _c, e in pt.CAMPOS]
    registros = []
    for f in filas:
        registros.append({pt.ENCABEZADO[c]: f.get(c) for c in pt.COLUMNAS_FORM})
    return pd.DataFrame(registros, columns=columnas)


# ─── norm ────────────────────────────────────────────────────
def test_norm_saca_tildes_mayusculas_y_espacios_de_mas():
    assert pt.norm("  Tráfico  ") == "TRAFICO"
    assert pt.norm("la   matanza") == "LA MATANZA"


def test_norm_de_un_vacio_es_cadena_vacia():
    for vacio in (None, "", "   ", float("nan"), pd.NaT, pd.NA):
        assert pt.norm(vacio) == ""


def test_norm_pasa_la_enie_a_n_salvo_que_se_pida_conservarla():
    # Para comparar, Ñ y N son lo mismo: buscar «nunez» tiene que encontrar NUÑEZ.
    assert pt.norm("Ñandú") == "NANDU"
    # Para mostrar, «PANOL» no es una palabra.
    assert pt.norm("Pañol", conservar_enie=True) == "PAÑOL"


# ─── Familias de puesto ──────────────────────────────────────
@pytest.mark.parametrize("puesto, grupo", [
    ("CHOFER", pt.GRUPO_CONDUCTOR),
    ("Conductor", pt.GRUPO_CONDUCTOR),
    ("CONDUCTORA", pt.GRUPO_CONDUCTOR),
    ("CONDCUTOR", pt.GRUPO_CONDUCTOR),          # los typos reales del registro
    ("CONUCTOR", pt.GRUPO_CONDUCTOR),
    ("CONCUTOR", pt.GRUPO_CONDUCTOR),
    ("CHOFER JUJUY", pt.GRUPO_CONDUCTOR),
    ("CONDUCTOR LM", pt.GRUPO_CONDUCTOR),
    ("SUPERVISOR TRAFICO", pt.GRUPO_SUPERVISION),
    ("SUP. TALLER", pt.GRUPO_SUPERVISION),
    ("SUPEVISOR", pt.GRUPO_SUPERVISION),
    ("JEFE DE TALLER", pt.GRUPO_SUPERVISION),
    ("COORD DE BASE", pt.GRUPO_SUPERVISION),
    ("OPERADOR DE PLANTA", pt.GRUPO_SUPERVISION),
    ("RESP. PAÑOL", pt.GRUPO_SUPERVISION),
    ("ADMINISTRATIVA", pt.GRUPO_ADMIN),
    ("ADMNISTRATRATIVA", pt.GRUPO_ADMIN),
    ("RECEPCIONISTA", pt.GRUPO_ADMIN),
    ("LIQ SUELDOS/ RRHH", pt.GRUPO_ADMIN),
    ("ASISTENTE DE COMPRAS", pt.GRUPO_ADMIN),
    ("MECANICO", pt.GRUPO_TALLER),
    ("Mecánico", pt.GRUPO_TALLER),
    ("ELECTROMECÁNICO", pt.GRUPO_TALLER),
    ("PAÑOLERO", pt.GRUPO_TALLER),
    ("M.OFICIAL MECANICO", pt.GRUPO_TALLER),
    ("CHAPISTA", pt.GRUPO_TALLER),
    ("MAESTRANZA", pt.GRUPO_MAESTRANZA),
    ("MAESTANZA", pt.GRUPO_MAESTRANZA),
    ("LAVAVERO", pt.GRUPO_MAESTRANZA),
    ("LAVEDERO", pt.GRUPO_MAESTRANZA),
    ("MANTEN/ LAVADERO", pt.GRUPO_MAESTRANZA),
    ("CELADODA", pt.GRUPO_CELADORA),
    ("SOPORTE IT", pt.GRUPO_SISTEMAS),
    ("DESARROLLO IOT", pt.GRUPO_SISTEMAS),
    ("PASANTIA", pt.GRUPO_PASANTIA),
    ("PRACTICAS PROFESIONALES", pt.GRUPO_PASANTIA),
    ("VARIOS", pt.GRUPO_OTROS),
    ("", pt.GRUPO_SIN_DATO),
    (None, pt.GRUPO_SIN_DATO),
])
def test_grupo_puesto(puesto, grupo):
    assert pt.grupo_puesto(puesto) == grupo


@pytest.mark.parametrize("puesto, grupo", [
    # Supervisión gana sobre el área que supervisa…
    ("SUP MECANICO", pt.GRUPO_SUPERVISION),
    ("SUP LAVADERO", pt.GRUPO_SUPERVISION),
    ("SUPERVISOR MAESTRANZA", pt.GRUPO_SUPERVISION),
    # …y Administración sobre el área donde trabaja.
    ("ADM TALLER", pt.GRUPO_ADMIN),
    ("ADMINISTRATIVO PAÑOL", pt.GRUPO_ADMIN),
])
def test_el_orden_de_las_reglas_resuelve_los_puestos_que_caen_en_dos_familias(puesto, grupo):
    assert pt.grupo_puesto(puesto) == grupo


def test_toda_familia_que_devuelve_la_funcion_esta_en_el_catalogo():
    for puesto in ("CHOFER", "SUPERVISOR", "ADM", "MECANICO", "LAVADERO",
                   "CELADORA", "IOT", "PASANTIA", "COSA RARA", ""):
        assert pt.grupo_puesto(puesto) in pt.GRUPOS_PUESTO


# ─── Sector ──────────────────────────────────────────────────
def test_sector_iguala_mayusculas_tildes_y_espacios():
    assert pt.normalizar_sector("Tráfico") == "TRAFICO"
    assert pt.normalizar_sector("TRAFICO") == "TRAFICO"
    assert pt.normalizar_sector(" trafico ") == "TRAFICO"
    assert pt.normalizar_sector(None) == ""


def test_sector_corrige_los_typos_conocidos():
    assert pt.normalizar_sector("A MATANZA") == "LA MATANZA"
    assert pt.normalizar_sector("Olavaria") == "OLAVARRIA"
    assert pt.normalizar_sector("RR.HH") == pt.normalizar_sector("RRHH") == "RRHH"
    assert pt.normalizar_sector("PANOL") == pt.normalizar_sector("PAÑOL") == "PAÑOL"


# ─── Entrevistador ───────────────────────────────────────────
def test_unifica_variantes_de_tipeo_y_orden_invertido():
    serie = pd.Series(
        ["Ana Demostra"] * 10
        + ["Demostra Ana",          # apellido adelante
           "AnA Demostra",          # mayúsculas
           "Ana Demostraa",         # letra de más
           "Ana Demosta"]           # letra de menos
    )
    assert set(pt.unificar_entrevistadores(serie)) == {"Ana Demostra"}


def test_no_junta_a_dos_personas_distintas_que_comparten_apellido():
    serie = pd.Series(["Ana Demostra"] * 10 + ["Pablo Demostra"] * 3)
    assert set(pt.unificar_entrevistadores(serie)) == {"Ana Demostra", "Pablo Demostra"}


def test_el_grupo_se_muestra_con_la_grafia_mas_frecuente():
    serie = pd.Series(["Demostra Ana"] * 5 + ["Ana Demostra"] * 2)
    assert set(pt.unificar_entrevistadores(serie)) == {"Demostra Ana"}


def test_entrevistador_vacio_queda_vacio():
    out = pt.unificar_entrevistadores(pd.Series(["Ana Demostra", None, "", "  "]))
    assert list(out) == ["Ana Demostra", "", "", ""]


def test_el_resultado_no_depende_del_orden_de_las_filas():
    nombres = ["Ana Demostra"] * 4 + ["Demostra Ana"] * 4 + ["Luis Ejemplo", "Ejemplo Luis"]
    ida = pt.unificar_entrevistadores(pd.Series(nombres))
    vuelta = pt.unificar_entrevistadores(pd.Series(nombres[::-1]))
    assert sorted(set(ida)) == sorted(set(vuelta))


# ─── Valores canónicos ───────────────────────────────────────
@pytest.mark.parametrize("valor", [True, "true", "TRUE", "Verdadero", "Sí", "si", -1, 1, "-1", "x"])
def test_apto_tildado(valor):
    assert pt.canon_apto(valor) is True


@pytest.mark.parametrize("valor", [False, "false", "FALSO", "No", 0, "0", "", None, float("nan")])
def test_apto_sin_tildar(valor):
    assert pt.canon_apto(valor) is False


@pytest.mark.parametrize("valor, esperado", [
    ("2026-09-24", "2026-09-24"),
    ("2026-09-24 00:00:00", "2026-09-24"),       # como lo entrega el .mdb
    ("24/09/2026", "2026-09-24"),                # formato regional de Access
    ("03/04/2026", "2026-04-03"),                # día primero, no mes primero
    (date(2026, 9, 24), "2026-09-24"),
    (datetime(2026, 9, 24, 10, 30), "2026-09-24"),
    (pd.Timestamp("2026-09-24"), "2026-09-24"),
    ("1899-12-30 00:00:00", None),               # fecha cero de Access = vacío
    ("(Invalid Date)", None),
    ("(Empty Date)", None),
    ("basura", None),
    ("", None), (None, None), (pd.NaT, None),
])
def test_canon_fecha(valor, esperado):
    assert pt.canon_fecha(valor) == esperado


@pytest.mark.parametrize("valor, esperado", [
    (11222333, 11222333),
    (11222333.0, 11222333),                      # Excel y el .mdb lo traen como float
    ("11222333", 11222333),
    ("11222333.0", 11222333),
    ("11.222.333", 11222333),
    (0, None), ("0", None), (0.0, None),         # el 0 de Access es "sin dato"
    ("", None), (None, None), (float("nan"), None),
    ("sin dni", None),
    (True, None),
])
def test_canon_dni(valor, esperado):
    assert pt.canon_dni(valor) == esperado


def test_canon_texto_limpia_bordes_y_deja_none_en_los_vacios():
    assert pt.canon_texto("  NO PASO LA PRUEBA ") == "NO PASO LA PRUEBA"
    assert pt.canon_texto("   ") is None
    assert pt.canon_texto(None) is None
    assert pt.canon_texto("con\x07control") == "concontrol"


# ─── enriquecer ──────────────────────────────────────────────
def test_el_dni_cero_o_vacio_nunca_agrupa_personas():
    """Regresión del riesgo principal: 263 entrevistas reales no tienen DNI. Si
    el 0 agrupara, serían "una persona" que se presentó 263 veces."""
    e = _enriquecida(_fila(1, apellido="UNO", dni=0),
                     _fila(2, apellido="DOS", dni=0),
                     _fila(3, apellido="TRES", dni=None),
                     _fila(4, apellido="CUATRO", dni=float("nan")))
    assert not e["dni_valido"].any()
    assert list(e["veces"]) == [1, 1, 1, 1]
    for numero in (1, 2, 3, 4):
        assert pt.historial(e, numero).empty


def test_veces_cuenta_las_entrevistas_del_mismo_dni():
    e = _enriquecida(_fila(1, apellido="ALFA", dni=11222333),
                     _fila(2, apellido="ALFA", dni=11222333),
                     _fila(3, apellido="BETA", dni=44555666))
    veces = dict(zip(e["numero_orden"], e["veces"]))
    assert veces == {1: 2, 2: 2, 3: 1}


def test_enriquecer_ordena_de_la_mas_nueva_a_la_mas_vieja_por_numero():
    # El número de orden es el orden real de carga; la fecha tiene años mal tipeados.
    e = _enriquecida(_fila(5, fecha="2012-12-02"), _fila(9, fecha="2024-12-09"),
                     _fila(7, fecha=None))
    assert list(e["numero_orden"]) == [9, 7, 5]


def test_enriquecer_arma_el_nombre_y_marca_notas_y_registros_en_blanco():
    e = _enriquecida(
        _fila(1, apellido="ALFA", nombres="ANA", observaciones="OK PREOCU"),
        _fila(2, apellido="BETA"),
        _fila(3),                                   # número reservado, sin datos
    ).set_index("numero_orden")
    assert e.loc[1, "apenom"] == "ALFA, ANA"
    assert e.loc[2, "apenom"] == "BETA"
    assert bool(e.loc[1, "con_notas"]) and not bool(e.loc[2, "con_notas"])
    assert bool(e.loc[3, "en_blanco"]) and not bool(e.loc[1, "en_blanco"])


def test_enriquecer_convierte_la_fecha_de_la_base_a_date():
    e = _enriquecida(_fila(1, fecha="2026-09-24"), _fila(2, fecha=None))
    fechas = dict(zip(e["numero_orden"], e["fecha"]))
    assert fechas[1] == date(2026, 9, 24)
    assert fechas[2] is None


def test_enriquecer_de_una_tabla_vacia_no_rompe():
    e = pt.enriquecer(pd.DataFrame(columns=pt.COLUMNAS_DB))
    assert e.empty
    for c in pt.DERIVADAS:
        assert c in e.columns
    assert pt.buscar(e, "algo").empty
    assert pt.filtrar(e, grupos=[pt.GRUPO_CONDUCTOR]).empty
    assert pt.resumen(e)["entrevistas"] == 0
    assert pt.opciones(e, "sector_norm") == []


# ─── buscar ──────────────────────────────────────────────────
def _registro_de_prueba():
    return _enriquecida(
        _fila(1, apellido="ALFA", nombres="ANA MARIA", dni=11222333,
              puesto="CONDUCTOR", sector="SINTRA", observaciones="OK PREOCU"),
        _fila(2, apellido="MUÑOZ", nombres="JOSE", dni=44555666,
              puesto="CHOFER", sector="Tráfico", motivo_rechazo="STAND BY"),
        _fila(3, apellido="PAZ", nombres="LUIS", puesto="MECANICO", sector="Taller"),
        _fila(4, apellido="PAZOS", nombres="LUISA", puesto="ADMINISTRATIVA",
              sector="RR.HH"),
        _fila(5, apellido="CAPAZ", nombres="OMAR", puesto="CHOFER", sector="Tráfico",
              motivo_rechazo="NO PASO LA PRUEBA DE MANEJO"),
    )


def _numeros(df):
    return sorted(df["numero_orden"].tolist())


def test_buscar_sin_texto_devuelve_todo():
    e = _registro_de_prueba()
    assert len(pt.buscar(e, "")) == len(e)
    assert len(pt.buscar(e, "   ")) == len(e)
    assert len(pt.buscar(e, None)) == len(e)


def test_buscar_acepta_las_palabras_en_cualquier_orden():
    e = _registro_de_prueba()
    assert _numeros(pt.buscar(e, "ana alfa")) == [1]
    assert _numeros(pt.buscar(e, "alfa ana")) == [1]


def test_buscar_ignora_tildes_y_mayusculas():
    e = _registro_de_prueba()
    assert _numeros(pt.buscar(e, "munoz")) == [2]
    assert _numeros(pt.buscar(e, "Muñoz")) == [2]
    assert _numeros(pt.buscar(e, "trafico")) == [2, 5]


def test_buscar_exige_todas_las_palabras():
    e = _registro_de_prueba()
    assert _numeros(pt.buscar(e, "chofer trafico")) == [2, 5]
    assert pt.buscar(e, "chofer taller").empty


def test_buscar_coincide_con_el_comienzo_de_la_palabra():
    """«paz» encuentra PAZ y PAZOS, pero no CAPAZ."""
    e = _registro_de_prueba()
    assert _numeros(pt.buscar(e, "paz")) == [3, 4]
    assert _numeros(pt.buscar(e, "luis")) == [3, 4]      # LUIS y LUISA


def test_buscar_por_dni_con_o_sin_puntos():
    e = _registro_de_prueba()
    assert _numeros(pt.buscar(e, "11222333")) == [1]
    assert _numeros(pt.buscar(e, "11.222.333")) == [1]
    assert _numeros(pt.buscar(e, "11 222 333")) == [1]
    assert _numeros(pt.buscar(e, "1122")) == [1]         # también por el comienzo


def test_buscar_entra_en_las_notas():
    e = _registro_de_prueba()
    assert _numeros(pt.buscar(e, "stand by")) == [2]
    assert _numeros(pt.buscar(e, "preocu")) == [1]
    assert _numeros(pt.buscar(e, "prueba manejo")) == [5]


def test_buscar_encuentra_el_sector_por_su_forma_normalizada():
    e = _registro_de_prueba()
    assert _numeros(pt.buscar(e, "rrhh")) == [4]         # cargado como «RR.HH»


def test_buscar_trata_los_simbolos_como_texto_y_no_como_regex():
    e = _registro_de_prueba()
    for consulta in ("(alfa", "al.a", "[", "*", "\\"):
        pt.buscar(e, consulta)                            # no tiene que reventar
    assert pt.buscar(e, "al.a").empty                     # el punto no es comodín


# ─── filtrar ─────────────────────────────────────────────────
def test_filtrar_sin_criterios_devuelve_todo():
    e = _registro_de_prueba()
    assert len(pt.filtrar(e)) == len(e)


def test_filtrar_por_familia_junta_chofer_y_conductor():
    e = _registro_de_prueba()
    assert _numeros(pt.filtrar(e, grupos=[pt.GRUPO_CONDUCTOR])) == [1, 2, 5]


def test_filtrar_por_sector_usa_el_valor_normalizado():
    e = _registro_de_prueba()
    assert _numeros(pt.filtrar(e, sectores=["TRAFICO"])) == [2, 5]
    assert _numeros(pt.filtrar(e, sectores=["RRHH", "TALLER"])) == [3, 4]


def test_filtrar_por_entrevistador_unificado():
    e = _enriquecida(*[_fila(i, entrevistador="Ana Demostra") for i in range(1, 6)],
                     _fila(6, entrevistador="Demostra Ana"),
                     _fila(7, entrevistador="Luis Ejemplo"))
    assert _numeros(pt.filtrar(e, entrevistadores=["Ana Demostra"])) == [1, 2, 3, 4, 5, 6]


def test_las_entrevistas_sin_fecha_solo_quedan_afuera_si_se_filtra_por_fecha():
    e = _enriquecida(_fila(1, fecha="2025-03-10"), _fila(2, fecha="2026-03-10"),
                     _fila(3, fecha=None))
    assert _numeros(pt.filtrar(e)) == [1, 2, 3]
    assert _numeros(pt.filtrar(e, desde=date(2026, 1, 1))) == [2]
    assert _numeros(pt.filtrar(e, hasta=date(2025, 12, 31))) == [1]


def test_el_rango_de_fechas_incluye_los_extremos():
    e = _enriquecida(_fila(1, fecha="2026-03-01"), _fila(2, fecha="2026-03-31"))
    assert _numeros(pt.filtrar(e, desde=date(2026, 3, 1), hasta=date(2026, 3, 31))) == [1, 2]


def test_filtros_de_aptos_notas_y_repetidos():
    e = _enriquecida(
        _fila(1, dni=11222333, apto=True),
        _fila(2, dni=11222333, observaciones="OK"),
        _fila(3, dni=44555666),
    )
    assert _numeros(pt.filtrar(e, solo_aptos=True)) == [1]
    assert _numeros(pt.filtrar(e, solo_con_notas=True)) == [2]
    assert _numeros(pt.filtrar(e, solo_repetidos=True)) == [1, 2]


def test_opciones_van_de_la_mas_frecuente_a_la_menos_y_sin_vacios():
    e = _enriquecida(_fila(1, sector="Taller"), _fila(2, sector="Tráfico"),
                     _fila(3, sector="TRAFICO"), _fila(4, sector=None))
    assert pt.opciones(e, "sector_norm") == ["TRAFICO", "TALLER"]


# ─── historial ───────────────────────────────────────────────
def test_historial_trae_las_otras_entrevistas_del_mismo_dni_de_vieja_a_nueva():
    e = _enriquecida(_fila(10, apellido="ALFA", dni=11222333),
                     _fila(30, apellido="ALFA", dni=11222333),
                     _fila(20, apellido="ALFA", dni=11222333),
                     _fila(40, apellido="BETA", dni=44555666))
    assert pt.historial(e, 30)["numero_orden"].tolist() == [10, 20]
    assert pt.historial(e, 40).empty


def test_historial_de_un_numero_inexistente_es_vacio():
    e = _enriquecida(_fila(1, dni=11222333))
    assert pt.historial(e, 999).empty
    assert pt.apellidos_distintos(e, 999) is False


def test_avisa_cuando_un_mismo_dni_tiene_apellidos_distintos():
    e = _enriquecida(_fila(1, apellido="ALFA", dni=11222333),
                     _fila(2, apellido="BETA", dni=11222333),
                     _fila(3, apellido="GAMA", dni=44555666),
                     _fila(4, apellido="Gama", dni=44555666))
    assert pt.apellidos_distintos(e, 1) is True
    assert pt.apellidos_distintos(e, 3) is False      # mismo apellido, otra grafía


# ─── Legajo ──────────────────────────────────────────────────
def _empleo(nrodoc, apenom, legajo, inicio="01/03/2020", fin=None, activo="1",
            empleador="EMPRESA UNO"):
    """Una fila del padrón tal como la entrega la API."""
    return {"nrodoc": nrodoc, "apenom": apenom, "legajo": legajo, "empleador": empleador,
            "fechainicio": inicio, "fechafin": fin, "activo": activo}


def _padron(*empleos):
    return pt.preparar_empleados(pd.DataFrame(list(empleos)))


def _cruzada(entrevistas, *empleos):
    return pt.cruzar_legajos(_enriquecida(*entrevistas), _padron(*empleos))


def _legajos(df):
    return dict(zip(df["numero_orden"], df["legajo"]))


def test_preparar_empleados_deja_valores_comparables():
    p = _padron(_empleo("11.222.333", "PÉREZ GÓMEZ, Juan Carlos", " 1234 ",
                        inicio="05/03/2020", fin="31/12/2021", activo="0"))
    fila = p.iloc[0]
    assert list(p.columns) == pt.COLUMNAS_EMPLEADOS
    assert fila["dni"] == 11222333 and fila["apellido"] == "PEREZ GOMEZ"
    assert fila["legajo"] == "1234" and fila["empleador"] == "EMPRESA UNO"
    assert fila["ingreso"] == date(2020, 3, 5) and fila["baja"] == date(2021, 12, 31)
    assert bool(fila["activo"]) is False


def test_preparar_empleados_toma_las_fechas_invalidas_como_vacias():
    p = _padron(_empleo("11222333", "ALFA, Ana", "10", inicio="00/00/0000", fin=None))
    assert p.iloc[0]["ingreso"] is None and p.iloc[0]["baja"] is None


def test_preparar_empleados_descarta_a_quien_no_tiene_documento_o_legajo():
    p = _padron(_empleo("", "ALFA, Ana", "10"), _empleo(None, "BETA, Bea", "11"),
                _empleo("11222333", "GAMA, Gus", ""), _empleo("22333444", "DELTA, Dan", "12"))
    assert p["legajo"].tolist() == ["12"]
    assert _padron().empty and pt.preparar_empleados(None).empty


@pytest.mark.parametrize("registro, padron, esperado", [
    ("ALFA", "ALFA", True),
    ("Alfá ", "ALFA", True),                    # tildes, mayúsculas y espacios
    ("ALFA", "ALFA BETA", True),                # apellido compuesto en el padrón
    ("ALFA BETA", "BETA", True),                # o en el registro
    ("GONZALES", "GONZALEZ", True),             # error de tipeo
    ("ALFA-BETA", "ALFA BETA", True),
    ("ALFA", "OMEGA", False),
    ("DE LOS ALFA", "DE LOS OMEGA", False),     # las partículas no cuentan
    ("SAN ALFA", "SAN OMEGA", False),
    ("", "ALFA", False),                        # sin apellido no hay con qué confirmar
    (None, "ALFA", False),
])
def test_apellido_compatible(registro, padron, esperado):
    assert pt.apellido_compatible(registro, padron) is esperado


def test_el_legajo_aparece_cuando_coinciden_dni_y_apellido():
    c = _cruzada([_fila(1, apellido="Alfa", dni=11222333, fecha="2020-02-20"),
                  _fila(2, apellido="BETA", dni=22333444)],
                 _empleo("11.222.333", "ALFA, Ana", "1234", inicio="01/03/2020"))
    uno = c[c["numero_orden"] == 1].iloc[0]
    assert uno["legajo"] == "1234" and uno["legajo_estado"] == pt.LEGAJO_OK
    assert uno["legajo_empleador"] == "EMPRESA UNO"
    assert uno["legajo_ingreso"] == date(2020, 3, 1) and bool(uno["legajo_activo"]) is True
    dos = c[c["numero_orden"] == 2].iloc[0]
    assert dos["legajo"] == "" and dos["legajo_estado"] == ""
    assert dos["legajo_ingreso"] is None and bool(dos["legajo_activo"]) is False


def test_un_dni_que_es_de_otro_apellido_no_muestra_legajo_y_queda_a_revisar():
    """Es la razón de cruzar por DNI + apellido: un DNI mal tipeado puede caer
    justo en el de otro empleado, y le atribuiríamos su legajo."""
    c = _cruzada([_fila(1, apellido="ALFA", dni=11222333)],
                 _empleo("11222333", "OMEGA, Oscar", "1234"))
    assert _legajos(c) == {1: ""}
    assert c.iloc[0]["legajo_estado"] == pt.LEGAJO_REVISAR


def test_una_entrevista_sin_dni_nunca_cruza():
    c = _cruzada([_fila(1, apellido="ALFA", dni=None), _fila(2, apellido="ALFA", dni=0)],
                 _empleo("", "ALFA, Ana", "10"), _empleo("0", "ALFA, Ana", "11"),
                 _empleo("11222333", "ALFA, Ana", "12"))
    assert _legajos(c) == {1: "", 2: ""}
    assert set(c["legajo_estado"]) == {""}


def test_con_varios_empleos_muestra_el_primero_que_empezo_desde_la_entrevista():
    empleos = [_empleo("11222333", "ALFA, Ana", "100", inicio="01/03/2015", fin="01/03/2016", activo="0"),
               _empleo("11222333", "ALFA, Ana", "200", inicio="10/06/2019", fin="01/02/2020", activo="0",
                       empleador="EMPRESA DOS"),
               _empleo("11222333", "ALFA, Ana", "300", inicio="01/09/2023")]
    c = _cruzada([_fila(1, apellido="ALFA", dni=11222333, fecha="2019-05-20")], *empleos)
    fila = c.iloc[0]
    assert fila["legajo"] == "200" and fila["legajo_empleador"] == "EMPRESA DOS"
    assert fila["legajo_baja"] == date(2020, 2, 1) and bool(fila["legajo_activo"]) is False


def test_si_todos_los_empleos_son_anteriores_muestra_el_mas_reciente():
    """Alguien que ya trabajó acá y se vuelve a presentar: el legajo es dato
    de la persona, aunque esta entrevista no haya terminado en ingreso."""
    c = _cruzada([_fila(1, apellido="ALFA", dni=11222333, fecha="2024-05-20")],
                 _empleo("11222333", "ALFA, Ana", "200", inicio="10/06/2019"),
                 _empleo("11222333", "ALFA, Ana", "100", inicio="01/03/2015"))
    assert _legajos(c) == {1: "200"}


def test_una_entrevista_fechada_pocos_dias_despues_del_ingreso_es_la_de_ese_ingreso():
    empleos = [_empleo("11222333", "ALFA, Ana", "200", inicio="10/06/2019"),
               _empleo("11222333", "ALFA, Ana", "300", inicio="01/09/2023")]
    dentro = _cruzada([_fila(1, apellido="ALFA", dni=11222333, fecha="2019-06-17")], *empleos)
    fuera = _cruzada([_fila(1, apellido="ALFA", dni=11222333, fecha="2019-06-18")], *empleos)
    assert _legajos(dentro) == {1: "200"}
    assert _legajos(fuera) == {1: "300"}


def test_sin_fecha_de_entrevista_muestra_el_empleo_mas_reciente():
    c = _cruzada([_fila(1, apellido="ALFA", dni=11222333)],
                 _empleo("11222333", "ALFA, Ana", "300", inicio="01/09/2023"),
                 _empleo("11222333", "ALFA, Ana", "200", inicio="10/06/2019"),
                 _empleo("11222333", "ALFA, Ana", "50", inicio="00/00/0000"))
    assert _legajos(c) == {1: "300"}


def test_si_el_dni_esta_repetido_en_el_padron_gana_el_apellido_que_coincide():
    c = _cruzada([_fila(1, apellido="ALFA", dni=11222333, fecha="2020-01-10")],
                 _empleo("11222333", "OMEGA, Oscar", "900", inicio="01/02/2020"),
                 _empleo("11222333", "ALFA, Ana", "100", inicio="01/03/2015"))
    assert _legajos(c) == {1: "100"}
    assert c.iloc[0]["legajo_estado"] == pt.LEGAJO_OK


@pytest.mark.parametrize("padron", [None, pd.DataFrame(columns=pt.COLUMNAS_EMPLEADOS)])
def test_sin_padron_las_columnas_quedan_vacias_y_la_consulta_sigue(padron):
    """Si la API de empleados no responde, sólo falta el legajo."""
    c = pt.cruzar_legajos(_enriquecida(_fila(1, apellido="ALFA", dni=11222333)), padron)
    assert set(pt.COLUMNAS_LEGAJO) <= set(c.columns)
    assert _legajos(c) == {1: ""}
    assert _numeros(pt.buscar(c, "alfa")) == [1]
    assert pt.filtrar(c, solo_con_legajo=True).empty


def test_cruzar_un_registro_vacio_no_rompe():
    vacio = pt.enriquecer(pd.DataFrame(columns=pt.COLUMNAS_DB))
    c = pt.cruzar_legajos(vacio, _padron(_empleo("11222333", "ALFA, Ana", "10")))
    assert c.empty and set(pt.COLUMNAS_LEGAJO) <= set(c.columns)
    assert pt.filtrar(c, solo_con_legajo=True, solo_dni_a_revisar=True).empty


def test_se_puede_buscar_por_legajo():
    c = _cruzada([_fila(1, apellido="ALFA", dni=11222333), _fila(2, apellido="BETA", dni=22333444)],
                 _empleo("11222333", "ALFA, Ana", "4321"))
    assert _numeros(pt.buscar(c, "4321")) == [1]


def test_filtros_de_legajo():
    c = _cruzada([_fila(1, apellido="ALFA", dni=11222333),
                  _fila(2, apellido="BETA", dni=22333444),
                  _fila(3, apellido="GAMA", dni=33444555)],
                 _empleo("11222333", "ALFA, Ana", "10"),
                 _empleo("22333444", "OMEGA, Oscar", "20"))
    assert _numeros(pt.filtrar(c, solo_con_legajo=True)) == [1]
    assert _numeros(pt.filtrar(c, solo_dni_a_revisar=True)) == [2]
    assert _numeros(pt.filtrar(c)) == [1, 2, 3]


def test_el_cruce_no_cambia_ni_el_orden_ni_las_demas_columnas():
    e = _enriquecida(_fila(1, apellido="ALFA", dni=11222333), _fila(2, apellido="BETA"))
    c = pt.cruzar_legajos(e, _padron(_empleo("11222333", "ALFA, Ana", "10")))
    assert c["numero_orden"].tolist() == e["numero_orden"].tolist()
    assert c["apenom"].tolist() == e["apenom"].tolist()
    assert "legajo" not in e.columns          # no toca el frame que recibe


# ─── resumen ─────────────────────────────────────────────────
def test_resumen_cuenta_personas_y_los_que_volvieron():
    e = _enriquecida(
        _fila(1, dni=11222333, fecha="2025-02-01", puesto="CHOFER", apto=True),
        _fila(2, dni=11222333, fecha="2026-02-01", puesto="CONDUCTOR"),
        _fila(3, dni=44555666, fecha="2026-03-01", puesto="MECANICO"),
        _fila(4, dni=None, fecha=None, puesto="CHOFER"),
    )
    r = pt.resumen(e)
    assert r["entrevistas"] == 4
    assert r["personas"] == 3          # 2 DNI distintos + 1 entrevista sin DNI
    assert r["sin_dni"] == 1
    assert r["volvieron"] == 1
    assert r["aptos"] == 1
    assert dict(zip(r["por_anio"]["Año"], r["por_anio"]["Entrevistas"])) == {2025: 1, 2026: 2}
    por_grupo = dict(zip(r["por_grupo"]["Puesto"], r["por_grupo"]["Entrevistas"]))
    assert por_grupo == {pt.GRUPO_CONDUCTOR: 3, pt.GRUPO_TALLER: 1}


def test_resumen_no_trae_ninguna_tasa_de_rechazo():
    """La casilla sin tildar no es un rechazo: no hay número honesto que dar."""
    r = pt.resumen(_enriquecida(_fila(1, apto=True), _fila(2)))
    assert not [k for k in r if "rechaz" in k or "no_apto" in k or "pct" in k]


def test_motivos_se_agrupan_sin_importar_como_se_tipearon():
    e = _enriquecida(_fila(1, motivo_rechazo="NO PASO LA PRUEBA"),
                     _fila(2, motivo_rechazo="no pasó la prueba"),
                     _fila(3, motivo_rechazo="FALTA EXPERIENCIA"), _fila(4))
    motivos = pt.resumen(e)["motivos"]
    assert motivos.iloc[0].tolist() == ["NO PASO LA PRUEBA", 2]
    assert len(motivos) == 2                              # el vacío no cuenta


def test_ultima_actualizacion_devuelve_el_momento_mas_reciente_y_quien():
    e = _enriquecida(
        _fila(1, fecha_actualizacion="2026-10-01T12:00:00+00:00", importado_por="Uno"),
        _fila(2, fecha_actualizacion="2026-10-05T12:00:00+00:00", importado_por="Dos"),
    )
    momento, quien = pt.ultima_actualizacion(e)
    assert (momento.day, quien) == (5, "Dos")
    assert pt.ultima_actualizacion(pt.enriquecer(pd.DataFrame(columns=pt.COLUMNAS_DB))) == (None, "")


# ─── normalizar_archivo ──────────────────────────────────────
def _fila_archivo(numero, **campos):
    fila = {"numero_orden": numero, "apto": False}
    fila.update(campos)
    return fila


def test_normalizar_archivo_deja_tipos_canonicos():
    n = pt.normalizar_archivo(_archivo(
        _fila_archivo(2, apellido=" ALFA ", dni="11.222.333", fecha="24/09/2026",
                      apto="Sí", sector="Tráfico "),
        _fila_archivo(1, apellido="BETA", dni=0, fecha="1899-12-30", apto=0),
    ))
    assert n["numero_orden"].tolist() == [1, 2]            # ordenado por número
    dos = n[n["numero_orden"] == 2].iloc[0]
    assert (dos["apellido"], dos["dni"], dos["fecha"], dos["apto"], dos["sector"]) == \
        ("ALFA", 11222333, "2026-09-24", True, "Tráfico")
    uno = n[n["numero_orden"] == 1].iloc[0]
    assert uno["dni"] is None and uno["fecha"] is None and uno["apto"] is False


def test_los_encabezados_se_reconocen_sin_tildes_ni_mayusculas():
    crudo = _archivo(_fila_archivo(1, apellido="ALFA"))
    crudo.columns = [pt.norm(c).lower() for c in crudo.columns]   # «numero de orden»
    assert pt.normalizar_archivo(crudo)["apellido"].tolist() == ["ALFA"]


def test_las_columnas_de_mas_se_ignoran():
    crudo = _archivo(_fila_archivo(1, apellido="ALFA"))
    crudo["Columna nueva"] = "x"
    assert list(pt.normalizar_archivo(crudo).columns) == pt.COLUMNAS_FORM


def test_si_falta_una_columna_el_error_dice_cual():
    crudo = _archivo(_fila_archivo(1, apellido="ALFA")).drop(columns=["Sector", "DNI"])
    with pytest.raises(pt.ArchivoInvalido) as error:
        pt.normalizar_archivo(crudo)
    assert "Sector" in str(error.value) and "DNI" in str(error.value)


def test_un_numero_de_orden_repetido_se_rechaza():
    crudo = _archivo(_fila_archivo(7, apellido="ALFA"), _fila_archivo(7, apellido="BETA"))
    with pytest.raises(pt.ArchivoInvalido) as error:
        pt.normalizar_archivo(crudo)
    assert "7" in str(error.value)


def test_una_fila_con_datos_pero_sin_numero_se_rechaza():
    crudo = _archivo(_fila_archivo(1, apellido="ALFA"), _fila_archivo(None, apellido="BETA"))
    with pytest.raises(pt.ArchivoInvalido):
        pt.normalizar_archivo(crudo)


def test_los_renglones_totalmente_en_blanco_se_ignoran():
    crudo = _archivo(_fila_archivo(1, apellido="ALFA"), _fila_archivo(None, apto=None))
    assert pt.normalizar_archivo(crudo)["numero_orden"].tolist() == [1]


def test_un_registro_reservado_sin_datos_se_conserva():
    # En Access hay números de orden tomados sin nada cargado: son parte del registro.
    crudo = _archivo(_fila_archivo(1, apellido="ALFA"), _fila_archivo(2))
    assert pt.normalizar_archivo(crudo)["numero_orden"].tolist() == [1, 2]


@pytest.mark.parametrize("crudo", [None, pd.DataFrame()])
def test_un_archivo_sin_filas_se_rechaza(crudo):
    with pytest.raises(pt.ArchivoInvalido):
        pt.normalizar_archivo(crudo)


# ─── leer_archivo ────────────────────────────────────────────
def _crudo_de_ejemplo():
    return _archivo(
        _fila_archivo(1, entrevistador="Ana Demostra", fecha="2026-09-24",
                      apellido="MUÑOZ", nombres="JOSÉ", dni=11222333,
                      puesto="CONDUCTOR", sector="Tráfico", apto=True,
                      motivo_rechazo="NO, POR AHORA", observaciones="OK PREOCU"),
        _fila_archivo(2, apellido="BETA", dni=0),
    )


def test_lee_un_csv_utf8_separado_por_comas():
    contenido = _crudo_de_ejemplo().to_csv(index=False).encode("utf-8")
    n = pt.normalizar_archivo(pt.leer_archivo("export.csv", contenido))
    assert n["apellido"].tolist() == ["MUÑOZ", "BETA"]
    assert n["motivo_rechazo"].tolist()[0] == "NO, POR AHORA"     # la coma no parte el campo
    assert n["apto"].tolist() == [True, False]


def test_lee_un_csv_de_access_en_cp1252_separado_por_punto_y_coma():
    contenido = _crudo_de_ejemplo().to_csv(index=False, sep=";").encode("cp1252")
    n = pt.normalizar_archivo(pt.leer_archivo("EXPORT.CSV", contenido))
    assert n["apellido"].tolist() == ["MUÑOZ", "BETA"]
    assert n["nombres"].tolist()[0] == "JOSÉ"


def test_lee_un_excel():
    buffer = BytesIO()
    crudo = _crudo_de_ejemplo()
    crudo["Fecha"] = pd.to_datetime(crudo["Fecha"])          # Excel guarda fechas reales
    crudo.to_excel(buffer, index=False)
    n = pt.normalizar_archivo(pt.leer_archivo("tabla.xlsx", buffer.getvalue()))
    assert n["fecha"].tolist() == ["2026-09-24", None]
    assert n["dni"].tolist() == [11222333, None]


@pytest.mark.parametrize("nombre", ["notas.txt", "base.accdb", "sin_extension", "", None])
def test_un_formato_no_soportado_se_rechaza(nombre):
    with pytest.raises(pt.ArchivoInvalido):
        pt.leer_archivo(nombre, b"algo")


def test_un_archivo_vacio_se_rechaza():
    with pytest.raises(pt.ArchivoInvalido):
        pt.leer_archivo("export.csv", b"")


def test_un_mdb_que_no_es_de_access_se_rechaza_con_un_mensaje_claro():
    pytest.importorskip("access_parser")
    with pytest.raises(pt.ArchivoInvalido) as error:
        pt.leer_archivo("base.mdb", b"esto no es una base de access" * 400)
    assert "Access" in str(error.value)


def test_el_excel_que_exporta_el_dashboard_se_puede_volver_a_subir_sin_cambios():
    e = _enriquecida(
        _fila(1, entrevistador="Ana Demostra", fecha="2026-09-24", apellido="MUÑOZ",
              nombres="JOSÉ", dni=11222333, puesto="CONDUCTOR", sector="Tráfico",
              apto=True, motivo_rechazo="x", observaciones="OK PREOCU"),
        _fila(2, apellido="BETA"),
        _fila(3),
    )
    vuelta = pt.normalizar_archivo(pt.leer_archivo("export.xlsx", pt.exportar_excel(e)))
    plan = pt.plan_de_carga(vuelta, e)
    assert (len(plan["nuevas"]), len(plan["modificadas"]), plan["sin_cambios"]) == (0, 0, 3)


# ─── plan_de_carga ───────────────────────────────────────────
def test_plan_separa_nuevas_modificadas_sin_cambios_y_faltantes():
    base = _base(_fila(1, apellido="ALFA", observaciones="PREOCU 28/05"),
                 _fila(2, apellido="BETA"),
                 _fila(3, apellido="GAMA"))
    archivo = pt.normalizar_archivo(_archivo(
        _fila_archivo(1, apellido="ALFA", observaciones="INGRESO"),   # cambió la nota
        _fila_archivo(2, apellido="BETA"),                            # igual
        _fila_archivo(4, apellido="DELTA"),                           # nueva
    ))
    plan = pt.plan_de_carga(archivo, base)
    assert plan["nuevas"]["numero_orden"].tolist() == [4]
    assert plan["modificadas"]["numero_orden"].tolist() == [1]
    assert plan["sin_cambios"] == 1
    assert plan["faltantes"]["numero_orden"].tolist() == [3]
    assert plan["modificadas"].iloc[0]["cambios"] == [
        ("observaciones", "PREOCU 28/05", "INGRESO")]
    assert pt.a_cargar(plan)["numero_orden"].tolist() == [4, 1]


def test_con_la_base_vacia_todo_es_nuevo():
    archivo = pt.normalizar_archivo(_archivo(_fila_archivo(1, apellido="ALFA"),
                                             _fila_archivo(2, apellido="BETA")))
    for vacia in (None, pd.DataFrame(columns=pt.COLUMNAS_DB)):
        plan = pt.plan_de_carga(archivo, vacia)
        assert len(plan["nuevas"]) == 2 and plan["sin_cambios"] == 0
        assert pt.advertencias_de_carga(plan) == []


def test_repetir_la_misma_carga_no_cambia_nada():
    archivo = pt.normalizar_archivo(_archivo(
        _fila_archivo(1, apellido="ALFA", dni=11222333, fecha="2026-09-24", apto=True,
                      sector="Tráfico", observaciones="OK PREOCU"),
        _fila_archivo(2, apellido="BETA"),
    ))
    # Lo que queda en la base después de cargar ese archivo.
    cargado = pd.DataFrame(pt.registros_para_upsert(archivo, "Ana"))
    plan = pt.plan_de_carga(archivo, cargado)
    assert len(plan["nuevas"]) == 0 and len(plan["modificadas"]) == 0
    assert plan["sin_cambios"] == 2
    assert pt.a_cargar(plan).empty


def test_las_diferencias_de_formato_no_cuentan_como_cambio():
    """La base devuelve el DNI como float y la fecha como texto; Access trae
    espacios de más. Nada de eso es un cambio real."""
    base = _base(_fila(1, apellido="ALFA", dni=11222333.0, fecha="2026-09-24",
                       sector="Tráfico", apto=True))
    archivo = pt.normalizar_archivo(_archivo(
        _fila_archivo(1, apellido=" ALFA ", dni="11.222.333",
                      fecha=pd.Timestamp("2026-09-24"), sector="Tráfico ", apto=-1)))
    plan = pt.plan_de_carga(archivo, base)
    assert plan["sin_cambios"] == 1 and len(plan["modificadas"]) == 0


def test_tildar_la_casilla_de_apto_es_un_cambio():
    base = _base(_fila(1, apellido="ALFA", apto=False))
    archivo = pt.normalizar_archivo(_archivo(_fila_archivo(1, apellido="ALFA", apto=True)))
    cambios = pt.plan_de_carga(archivo, base)["modificadas"].iloc[0]["cambios"]
    assert cambios == [("apto", False, True)]
    assert pt.describir_cambios(cambios) == "Apto para ingresar: — → Sí"


def test_describir_cambios_usa_los_nombres_del_formulario():
    texto = pt.describir_cambios([("observaciones", None, "OK"), ("sector", "Taller", None)])
    assert texto == ("Observaciones del entrevistador: (vacío) → OK · "
                     "Sector: Taller → (vacío)")


def test_avisa_si_al_archivo_le_faltan_entrevistas_que_ya_estan_cargadas():
    base = _base(*[_fila(i, apellido="X") for i in range(1, 11)])
    archivo = pt.normalizar_archivo(_archivo(
        *[_fila_archivo(i, apellido="X") for i in range(1, 9)]))     # copia vieja
    avisos = pt.advertencias_de_carga(pt.plan_de_carga(archivo, base))
    assert len(avisos) == 1 and "le faltan 2 entrevistas" in avisos[0]

    casi = pt.normalizar_archivo(_archivo(
        *[_fila_archivo(i, apellido="X") for i in range(1, 10)]))
    assert "le falta 1 entrevista " in pt.advertencias_de_carga(
        pt.plan_de_carga(casi, base))[0]


def test_avisa_si_el_archivo_cambia_demasiadas_entrevistas():
    base = _base(*[_fila(i, apellido="X") for i in range(1, 11)])
    corrido = pt.normalizar_archivo(_archivo(
        *[_fila_archivo(i, nombres="X") for i in range(1, 11)]))     # columnas corridas
    avisos = pt.advertencias_de_carga(pt.plan_de_carga(corrido, base))
    assert len(avisos) == 1 and "10 de las 10" in avisos[0]


def test_una_actualizacion_normal_no_dispara_avisos():
    base = _base(*[_fila(i, apellido="X") for i in range(1, 11)])
    archivo = pt.normalizar_archivo(_archivo(
        *[_fila_archivo(i, apellido="X") for i in range(1, 10)],
        _fila_archivo(10, apellido="X", observaciones="PREOCU"),      # 1 de 10 cambia
        _fila_archivo(11, apellido="NUEVA")))
    assert pt.advertencias_de_carga(pt.plan_de_carga(archivo, base)) == []


# ─── registros_para_upsert ───────────────────────────────────
def test_los_registros_tienen_todos_las_mismas_claves_y_se_pueden_serializar():
    """PostgREST rechaza un lote con claves distintas, y `json` no sabe qué
    hacer con los enteros de numpy ni con NaN."""
    archivo = pt.normalizar_archivo(_archivo(
        _fila_archivo(1, apellido="ALFA", dni=11222333, fecha="2026-09-24", apto=True),
        _fila_archivo(2)))
    registros = pt.registros_para_upsert(
        archivo, "Ana", ahora=datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc))

    assert len({tuple(sorted(r)) for r in registros}) == 1
    json.dumps(registros)
    uno, dos = registros
    assert uno["dni"] == 11222333 and type(uno["dni"]) is int
    assert type(uno["numero_orden"]) is int and uno["apto"] is True
    assert uno["fecha"] == "2026-09-24"
    assert dos["dni"] is None and dos["fecha"] is None and dos["apellido"] is None
    assert dos["apto"] is False
    assert uno["importado_por"] == "Ana"
    assert uno["fecha_actualizacion"] == "2026-10-01T12:00:00+00:00"


def test_el_upsert_no_manda_la_fecha_de_importacion():
    """Si la mandara, cada actualización pisaría la fecha en que la fila entró."""
    archivo = pt.normalizar_archivo(_archivo(_fila_archivo(1, apellido="ALFA")))
    registro = pt.registros_para_upsert(archivo, "Ana")[0]
    assert "fecha_importacion" not in registro
    assert set(registro) <= set(pt.COLUMNAS_DB)


# ─── Acceso a la base (cliente falso) ────────────────────────
class _Consulta:
    def __init__(self, cliente):
        self.cliente = cliente
        self.rango = None
        self.es_upsert = False

    def select(self, columnas, **opciones):
        self.cliente.selects.append(columnas)
        self.cliente.opciones_select.append(opciones)
        return self

    def order(self, columna):
        self.cliente.ordenes.append(columna)
        return self

    def range(self, desde, hasta):
        self.rango = (desde, hasta)
        self.cliente.rangos.append(self.rango)
        return self

    def upsert(self, filas, **opciones):
        self.es_upsert = True
        self.cliente.upserts.append((list(filas), opciones))
        return self

    def execute(self):
        if self.es_upsert:
            return SimpleNamespace(data=None)
        desde, hasta = self.rango
        return SimpleNamespace(data=self.cliente.filas[desde:hasta + 1])


class _Cliente:
    """Imita lo justo de supabase-py, incluido el tope de filas por consulta."""

    def __init__(self, filas=()):
        self.filas = list(filas)
        self.tablas, self.selects, self.ordenes = [], [], []
        self.opciones_select = []
        self.rangos, self.upserts = [], []

    def table(self, nombre):
        self.tablas.append(nombre)
        return _Consulta(self)


def test_leer_todo_pagina_y_trae_mas_de_mil_filas():
    """PostgREST corta en 1000 sin avisar: sin paginar se verían sólo las primeras."""
    cliente = _Cliente(_fila(i, apellido=f"P{i}") for i in range(1, 2501))
    df = pt.leer_todo(cliente)
    assert len(df) == 2500
    assert cliente.rangos == [(0, 999), (1000, 1999), (2000, 2999)]
    assert list(df.columns) == pt.COLUMNAS_DB
    assert set(cliente.tablas) == {pt.TABLA}
    assert set(cliente.ordenes) == {"numero_orden"}       # orden estable entre páginas


def test_leer_todo_cuando_la_ultima_pagina_viene_justo_llena():
    cliente = _Cliente(_fila(i) for i in range(1, 2001))
    assert len(pt.leer_todo(cliente)) == 2000
    assert cliente.rangos == [(0, 999), (1000, 1999), (2000, 2999)]


def test_leer_todo_con_la_tabla_vacia():
    df = pt.leer_todo(_Cliente())
    assert df.empty and list(df.columns) == pt.COLUMNAS_DB


def test_leer_todo_no_pide_columnas_que_no_existen():
    cliente = _Cliente()
    pt.leer_todo(cliente)
    assert cliente.selects == [",".join(pt.COLUMNAS_DB)]


def test_leer_todo_pide_el_conteo_exacto():
    """Con el total a la vista la lectura no depende del tope del servidor."""
    cliente = _Cliente()
    pt.leer_todo(cliente)
    assert cliente.opciones_select == [{"count": "exact"}]


def test_upsert_manda_por_lotes_y_por_numero_de_orden():
    cliente = _Cliente()
    registros = [{"numero_orden": i} for i in range(1, 1201)]
    assert pt.upsert(cliente, registros, lote=500) == 1200
    assert [len(filas) for filas, _o in cliente.upserts] == [500, 500, 200]
    assert all(o["on_conflict"] == "numero_orden" for _f, o in cliente.upserts)
    enviados = [r["numero_orden"] for filas, _o in cliente.upserts for r in filas]
    assert enviados == list(range(1, 1201))


def test_upsert_sin_registros_no_llama_a_la_base():
    cliente = _Cliente()
    assert pt.upsert(cliente, []) == 0
    assert cliente.upserts == []


# ─── Exportación ─────────────────────────────────────────────
def test_el_export_usa_los_encabezados_y_el_orden_del_formulario():
    e = _enriquecida(_fila(1, apellido="ALFA", dni=11222333, fecha="2026-09-24", apto=True),
                     _fila(2, apellido="BETA"))
    out = pt.preparar_export(e)
    assert list(out.columns) == [
        "Entrevistador", "Fecha", "Número de orden", "Apellido", "Nombres", "DNI",
        "Puesto al que se postula", "Sector", "Apto para ingresar",
        "Motivos del rechazo", "Observaciones del entrevistador"]


def test_el_export_nunca_escribe_no_en_la_columna_de_apto():
    e = _enriquecida(_fila(1, apto=True), _fila(2, apto=False))
    aptos = dict(zip(pt.preparar_export(e)["Número de orden"],
                     pt.preparar_export(e)["Apto para ingresar"]))
    assert aptos == {1: "Sí", 2: ""}


def test_el_export_no_lleva_las_columnas_derivadas():
    out = pt.preparar_export(_enriquecida(_fila(1, apellido="ALFA")))
    for derivada in pt.DERIVADAS:
        assert derivada not in out.columns


def test_el_export_suma_el_legajo_al_final_si_el_registro_viene_cruzado():
    c = _cruzada([_fila(1, apellido="ALFA", dni=11222333), _fila(2, apellido="BETA")],
                 _empleo("11222333", "ALFA, Ana", "1234", inicio="01/03/2020"))
    out = pt.preparar_export(c)
    assert list(out.columns)[:11] == [e for _c, e in pt.CAMPOS]
    assert list(out.columns)[11:] == ["Legajo", "Empleador", "Fecha de ingreso"]
    uno = out[out["Número de orden"] == 1].iloc[0]
    assert uno["Legajo"] == 1234 and uno["Empleador"] == "EMPRESA UNO"
    assert uno["Fecha de ingreso"] == date(2020, 3, 1)
    dos = out[out["Número de orden"] == 2].iloc[0]
    assert dos["Legajo"] == "" and dos["Fecha de ingreso"] is None
    vacio = pt.cruzar_legajos(pt.enriquecer(pd.DataFrame(columns=pt.COLUMNAS_DB)), None)
    assert list(pt.preparar_export(vacio).columns)[11:] == ["Legajo", "Empleador", "Fecha de ingreso"]


def test_el_excel_con_legajo_se_puede_volver_a_subir_sin_cambios():
    """Las tres columnas de legajo son de consulta: al subir el Excel se ignoran."""
    base = _base(_fila(1, apellido="ALFA", dni=11222333, fecha="2026-09-24"),
                 _fila(2, apellido="BETA"))
    cruzada = pt.cruzar_legajos(pt.enriquecer(base),
                                _padron(_empleo("11222333", "ALFA, Ana", "1234")))
    archivo = pt.normalizar_archivo(
        pt.leer_archivo("postulantes.xlsx", pt.exportar_excel(cruzada)))
    plan = pt.plan_de_carga(archivo, base)
    assert (len(plan["nuevas"]), len(plan["modificadas"]), plan["sin_cambios"]) == (0, 0, 2)


def test_exportar_excel_devuelve_un_xlsx_incluso_vacio():
    assert pt.exportar_excel(_enriquecida(_fila(1, apellido="ALFA")))[:2] == b"PK"
    vacio = pt.enriquecer(pd.DataFrame(columns=pt.COLUMNAS_DB))
    assert pt.exportar_excel(vacio)[:2] == b"PK"


# ─── Esquema ─────────────────────────────────────────────────
def _ddl():
    with open(os.path.join(RAIZ, "migration_entrevistas_postulantes.sql"),
              encoding="utf-8") as fh:
        return fh.read()


def test_columnas_coinciden_con_el_ddl():
    """El módulo y la tabla no pueden desincronizarse sin que un test lo note."""
    cuerpo = _ddl().split("CREATE TABLE IF NOT EXISTS entrevistas_postulantes (", 1)[1] \
        .split("\n);", 1)[0]
    columnas = []
    for linea in cuerpo.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith(("--", "CONSTRAINT", "UNIQUE")):
            continue
        columnas.append(linea.split()[0])
    assert columnas == pt.COLUMNAS_DB


def test_todo_campo_del_formulario_tiene_columna_en_la_tabla():
    assert set(pt.COLUMNAS_FORM) <= set(pt.COLUMNAS_DB)
    assert len(pt.CAMPOS) == 11


def test_el_ddl_no_habilita_borrar_el_registro():
    """La app agrega y actualiza, nunca borra. Si alguien suma una policy de
    DELETE o un FOR ALL, salta acá."""
    # Sin los comentarios: el texto que explica por qué NO hay FOR ALL contiene
    # esa misma frase y daría un falso positivo.
    sql = "\n".join(l for l in _ddl().splitlines()
                    if not l.strip().startswith("--")).upper()
    assert "FOR SELECT" in sql and "FOR INSERT" in sql and "FOR UPDATE" in sql
    assert "FOR DELETE" not in sql
    assert "FOR ALL" not in sql


def test_el_ddl_agrega_el_permiso_a_usuarios():
    assert "ADD COLUMN IF NOT EXISTS VER_POSTULANTES" in " ".join(_ddl().upper().split())


# ─── Archivo real (sólo en la máquina de quien lo tenga) ─────
@pytest.mark.skipif(
    not (os.environ.get("POSTULANTES_MDB") and os.environ.get("POSTULANTES_CSV")),
    reason="Necesita el .mdb real y su export de referencia, que no están en el repo.")
def test_el_mdb_real_se_lee_igual_que_su_export_de_referencia():
    """La lectura del .mdb pisa dos métodos internos de access-parser. Antes de
    cambiar su versión, correr esto con:
        POSTULANTES_MDB=/ruta/base.mdb POSTULANTES_CSV=/ruta/export.csv pytest
    """
    with open(os.environ["POSTULANTES_MDB"], "rb") as fh:
        mdb = pt.normalizar_archivo(pt.leer_archivo("base.mdb", fh.read()))
    with open(os.environ["POSTULANTES_CSV"], "rb") as fh:
        csv = pt.normalizar_archivo(pt.leer_archivo("export.csv", fh.read()))
    plan = pt.plan_de_carga(mdb, csv)
    assert len(mdb) == len(csv) > 0
    assert (len(plan["nuevas"]), len(plan["modificadas"]), len(plan["faltantes"])) == (0, 0, 0)
