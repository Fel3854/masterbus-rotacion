"""Tests de paginado.py — lectura paginada de Supabase. Sin red."""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paginado import PAGINA, leer_paginado  # noqa: E402


class _Servidor:
    """Imita a PostgREST: entrega como mucho `tope` filas por consulta, sin avisar."""

    def __init__(self, n, tope=1000, con_conteo=True):
        self.filas = [{"id": i} for i in range(n)]
        self.tope = tope
        self.con_conteo = con_conteo
        self.rangos = []
        self.consultas_armadas = 0

    def consulta(self):
        self.consultas_armadas += 1
        return _Consulta(self)


class _Consulta:
    def __init__(self, servidor):
        self.servidor = servidor
        self.rango = None

    def range(self, desde, hasta):
        # Como el cliente real: un segundo .range() sobre la misma consulta
        # acumula parámetros, así que cada consulta admite uno solo.
        assert self.rango is None, "la consulta se reutilizó entre páginas"
        self.rango = (desde, hasta)
        self.servidor.rangos.append(self.rango)
        return self

    def execute(self):
        desde, hasta = self.rango
        fin = min(hasta + 1, desde + self.servidor.tope)
        return SimpleNamespace(
            data=self.servidor.filas[desde:fin],
            count=len(self.servidor.filas) if self.servidor.con_conteo else None)


def _ids(filas):
    return [f["id"] for f in filas]


def test_trae_mas_de_mil_filas_sin_repetir_ni_saltear():
    """El caso que motivó el módulo: sin paginar llegaban sólo las primeras 1000."""
    servidor = _Servidor(2500)
    filas = leer_paginado(servidor.consulta)
    assert _ids(filas) == list(range(2500))
    assert servidor.rangos == [(0, 999), (1000, 1999), (2000, 2999)]


def test_con_menos_de_una_pagina_hace_una_sola_consulta():
    servidor = _Servidor(300)
    assert len(leer_paginado(servidor.consulta)) == 300
    assert servidor.rangos == [(0, 999)]


def test_tabla_vacia():
    servidor = _Servidor(0)
    assert leer_paginado(servidor.consulta) == []
    assert servidor.rangos == [(0, 999)]


def test_con_conteo_no_hace_una_consulta_de_mas_cuando_la_ultima_pagina_viene_llena():
    servidor = _Servidor(2000, con_conteo=True)
    assert len(leer_paginado(servidor.consulta)) == 2000
    assert servidor.rangos == [(0, 999), (1000, 1999)]


def test_sin_conteo_una_pagina_llena_obliga_a_pedir_la_siguiente():
    servidor = _Servidor(2000, con_conteo=False)
    assert len(leer_paginado(servidor.consulta)) == 2000
    assert servidor.rangos == [(0, 999), (1000, 1999), (2000, 2999)]


def test_con_conteo_no_depende_del_tope_del_servidor():
    """Si el proyecto entregara menos filas por consulta que las que se piden,
    el conteo exacto igual permite traerlas todas."""
    servidor = _Servidor(1200, tope=500, con_conteo=True)
    assert _ids(leer_paginado(servidor.consulta)) == list(range(1200))
    assert servidor.rangos == [(0, 999), (500, 1499), (1000, 1999)]


def test_cada_pagina_arma_una_consulta_nueva():
    servidor = _Servidor(2500)
    leer_paginado(servidor.consulta)
    assert servidor.consultas_armadas == len(servidor.rangos) == 3


def test_el_tope_corta_y_ajusta_el_tamano_de_la_ultima_pagina():
    servidor = _Servidor(6000)
    filas = leer_paginado(servidor.consulta, tope=2500)
    assert _ids(filas) == list(range(2500))
    assert servidor.rangos == [(0, 999), (1000, 1999), (2000, 2499)]


def test_un_tope_menor_que_la_pagina_pide_solo_eso():
    servidor = _Servidor(6000)
    assert len(leer_paginado(servidor.consulta, tope=10)) == 10
    assert servidor.rangos == [(0, 9)]


def test_pedir_una_de_mas_permite_saber_si_quedo_algo_afuera():
    """Es lo que hace Auditoría para avisar que el período no entra entero."""
    maximo = 1500
    assert len(leer_paginado(_Servidor(1500).consulta, tope=maximo + 1)) == maximo
    assert len(leer_paginado(_Servidor(1501).consulta, tope=maximo + 1)) == maximo + 1


def test_el_tamano_de_pagina_se_puede_cambiar():
    servidor = _Servidor(25, con_conteo=False)
    assert len(leer_paginado(servidor.consulta, pagina=10)) == 25
    assert servidor.rangos == [(0, 9), (10, 19), (20, 29)]


def test_la_pagina_por_defecto_es_el_tope_de_supabase():
    assert PAGINA == 1000
