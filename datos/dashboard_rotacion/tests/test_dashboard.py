"""Tests de la página Dashboard (rotación). Sin red: el padrón se simula."""

import json
import os
import re

import pytest
import requests
import streamlit as st
from streamlit.testing.v1 import AppTest

PAGINA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "_dashboard.py")
API_URL = "https://traficonuevo.masterbus.net/api/v1/auto/e"

# (id, legajo, cargo, activo, ingreso, baja). Marzo de 2024 es un mes ya cerrado.
PADRON = [
    ("1", "10", "CONDUCTOR", "1", "01/01/2021", "00/00/0000"),   # sigue
    ("2", "20", "MECANICO", "1", "01/01/2021", "00/00/0000"),    # sigue
    ("3", "30", "CONDUCTOR", "0", "01/01/2021", "15/03/2024"),   # baja fechada en marzo
    ("4", "40", "LAVADOR", "0", "01/01/2021", "00/00/0000"),     # se fue sin fecha de baja
]


def _respuesta(contenido):
    r = requests.Response()
    r.status_code = 200
    r._content = contenido
    r.url = API_URL
    return r


def _json(filas):
    return json.dumps([
        {"id_empleado": i, "legajo": legajo, "apenom": f"PERSONA {i}", "cargo": cargo,
         "activo": activo, "fechainicio": ingreso, "fechafin": baja,
         "empleador": "MASTER BUS S.A", "str": "Operacion Campana", "fechanac": "01/01/1980",
         "nrodoc": "", "cuil": "", "domicilio": "", "ciudad": "", "telefono": "",
         "cbu": "", "banco": "", "email": ""}
        for i, legajo, cargo, activo, ingreso, baja in filas
    ]).encode()


def _pagina(monkeypatch, año=2024, mes=3, padron=PADRON):
    st.cache_data.clear()

    def get(url, timeout):
        assert url == API_URL, f"pedido inesperado a {url}"
        return _respuesta(_json(padron))

    monkeypatch.setattr(requests, "get", get)
    at = AppTest.from_file(PAGINA, default_timeout=30).run()
    [s for s in at.selectbox if s.label == "Año"][0].set_value(año).run()
    [s for s in at.selectbox if s.label == "Mes"][0].set_value(mes).run()
    assert not at.exception
    return at


def _plantilla(at):
    for md in at.markdown:
        m = re.search(r"Plantilla al inicio\s*</div>\s*<div[^>]*>\s*([\d,.]+)", md.value)
        if m:
            return int(m.group(1).replace(",", "").replace(".", ""))
    raise AssertionError("no está el KPI «Plantilla al inicio»")


def test_un_inactivo_sin_fecha_de_baja_no_infla_la_plantilla_de_un_mes_pasado(monkeypatch):
    # Antes, en los meses cerrados se lo contaba como presente para siempre.
    assert _plantilla(_pagina(monkeypatch)) == 3


def test_una_baja_fechada_sale_de_la_plantilla_del_mes_siguiente(monkeypatch):
    at = _pagina(monkeypatch, mes=4)
    assert _plantilla(at) == 2   # la baja de marzo ya no está; el que no tiene fecha, tampoco


def test_avisa_cuantos_inactivos_no_tienen_fecha_de_baja(monkeypatch):
    at = _pagina(monkeypatch)
    assert any("1 empleados inactivos sin fecha de baja" in w.value for w in at.warning)
    assert any("Bajas sin fecha registrada — 1 empleados" in e.label for e in at.expander)


def test_sin_inactivos_sin_fecha_no_hay_aviso(monkeypatch):
    at = _pagina(monkeypatch, padron=PADRON[:3])
    assert not any("sin fecha de baja" in w.value for w in at.warning)
    assert not any("Bajas sin fecha registrada" in e.label for e in at.expander)


@pytest.mark.parametrize("mes, bajas", [(3, 1), (4, 0)])
def test_el_fantasma_no_cuenta_como_baja(monkeypatch, mes, bajas):
    at = _pagina(monkeypatch, mes=mes)
    texto = " ".join(md.value for md in at.markdown)
    m = re.search(r"Bajas del período\s*</div>\s*<div[^>]*>\s*([\d,.]+)", texto)
    assert m and int(m.group(1)) == bajas
