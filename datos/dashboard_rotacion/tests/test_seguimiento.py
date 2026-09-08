"""Tests de la lógica de Seguimiento de conductores (sin Streamlit)."""

import os
import sys
from datetime import date, timedelta

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import seguimiento as sg  # noqa: E402


# ─── Catálogo ────────────────────────────────────────────────
def test_catalogo_tiene_las_20_preguntas_del_formulario():
    assert len(sg.PREGUNTAS) == 20
    assert [p["n"] for p in sg.PREGUNTAS] == list(range(1, 21))
    assert len(sg.ESCALAS) == 13
    assert len(sg.FLAGS) == 2
    assert len(sg.CATEGORIAS) == 5


def test_toda_escala_tiene_exactamente_cuatro_opciones():
    for p in sg.ESCALAS:
        assert len(p["opciones"]) == 4, p["cod"]
    for a in sg.AUTOEVAL:
        assert len(a["opciones"]) == 4, a["cod"]


def test_codigo_hace_roundtrip_en_todas_las_preguntas():
    for p in sg.ESCALAS:
        for i, label in enumerate(p["opciones"]):
            valor = sg.codigo(p, label)
            assert valor == 4 - i, (p["cod"], label)
            assert sg.etiqueta(p, valor) == label
    for a in sg.AUTOEVAL:
        for i, label in enumerate(a["opciones"]):
            assert sg.codigo(a, label) == 4 - i


def test_flags_devuelven_bool_y_categorias_devuelven_texto():
    p09 = sg.POR_COD["p09"]
    assert sg.codigo(p09, "Sí") is True
    assert sg.codigo(p09, "No") is False
    p18 = sg.POR_COD["p18"]
    assert sg.codigo(p18, "El sueldo") == "El sueldo"


def test_codigo_devuelve_none_ante_valor_invalido():
    p01 = sg.POR_COD["p01"]
    assert sg.codigo(p01, None) is None
    assert sg.codigo(p01, "Excelente") is None


def test_p06_indexa_en_vinculos_no_en_operacion():
    # P6 mide lo mismo que P14; en 'operacion' contaminaría el índice.
    assert sg.POR_COD["p06"]["seccion"] == 2
    assert sg.dimension_de("p06") == "vinculos"
    assert "p06" in sg.codigos_de_dimension("vinculos")


def test_p08_y_p20_no_forman_indice_de_un_solo_item():
    assert sg.dimension_de("p08") is None
    assert sg.dimension_de("p20") is None


def test_toda_escala_con_dimension_esta_en_alguna_dimension():
    asignadas = {c for d in sg.DIMENSIONES for c in sg.codigos_de_dimension(d)}
    sueltas = {"p08", "p20"}
    assert asignadas | sueltas == set(sg.COD_ESCALAS)


# ─── Contrato catálogo ↔ esquema ─────────────────────────────
def test_columnas_db_coincide_con_el_ddl():
    """Guarda contra el drift entre PREGUNTAS y migration_seguimiento_conductores.sql."""
    ruta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "migration_seguimiento_conductores.sql")
    with open(ruta, encoding="utf-8") as f:
        sql = f.read()
    cuerpo = sql.split("CREATE TABLE IF NOT EXISTS seguimiento_conductores (", 1)[1]
    cuerpo = cuerpo.split("\n);", 1)[0]

    en_sql = []
    for linea in cuerpo.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith(("--", "CONSTRAINT", "UNIQUE")):
            continue
        col = linea.split()[0]
        if col.isidentifier():
            en_sql.append(col)

    assert sorted(en_sql) == sorted(sg.columnas_db())


# ─── Índices ─────────────────────────────────────────────────
def test_normalizar_mapea_la_escala_1a4_a_0a100():
    assert sg.normalizar(1) == 0.0
    assert sg.normalizar(4) == 100.0
    assert sg.normalizar(3) == pytest.approx(66.67, abs=0.01)
    assert sg.normalizar(3) == pytest.approx(sg.REFERENCIA_BUENA, abs=0.1)


def test_normalizar_tolera_nan():
    assert pd.isna(sg.normalizar(float("nan")))
    assert pd.isna(sg.normalizar(None))


def test_banda_por_tramo():
    assert sg.banda(20)[0] == "Crítico"
    assert sg.banda(55)[0] == "A mejorar"
    assert sg.banda(70)[0] == "Bueno"
    assert sg.banda(90)[0] == "Muy bueno"
    assert sg.banda(float("nan"))[0] == "Sin datos"


def _fila(valor=4, **extra):
    fila = {c: valor for c in sg.COD_ESCALAS}
    fila.update({c: valor for c in sg.COD_AUTO})
    fila.update({"p09": False, "p16": False})
    fila.update(extra)
    return fila


def test_indices_extremos():
    df = pd.DataFrame([_fila(4), _fila(1)])
    out = sg.calcular_indices(df)
    assert out.loc[0, "indice_general"] == 100.0
    assert out.loc[1, "indice_general"] == 0.0
    assert out.loc[0, "indice_autopercepcion"] == 100.0
    for dim in sg.DIMENSIONES:
        assert out.loc[0, "indice_" + dim] == 100.0


def test_un_item_nulo_saltea_ese_item_en_vez_de_anular_el_indice():
    fila = _fila(4)
    fila["p11"] = None
    out = sg.calcular_indices(pd.DataFrame([fila]))
    assert out.loc[0, "indice_general"] == 100.0
    assert not pd.isna(out.loc[0, "indice_condiciones"])


def test_calcular_indices_sobre_frame_vacio_no_rompe():
    out = sg.calcular_indices(pd.DataFrame())
    assert out.empty
    assert "indice_general" in out.columns
    assert "es_alerta" in out.columns


# ─── Alertas ─────────────────────────────────────────────────
@pytest.mark.parametrize("extra,motivo", [
    ({"p09": True}, "Norma de seguridad difícil de cumplir"),
    ({"p16": True}, "Situación del ambiente laboral incomodando"),
    ({"p20": 1}, "No recomendaría la empresa"),
    ({"p08": 1}, "No recibió capacitación de Seguridad Vial"),
])
def test_cada_regla_roja_dispara_por_separado(extra, motivo):
    out = sg.calcular_indices(pd.DataFrame([_fila(4, **extra)]))
    assert out.loc[0, "es_alerta"]
    assert motivo in out.loc[0, "motivos_alerta"]
    assert out.loc[0, "nivel_alerta"] == "Roja"


def test_indice_bajo_dispara_atencion():
    out = sg.calcular_indices(pd.DataFrame([_fila(2)]))
    motivos = out.loc[0, "motivos_alerta"]
    assert "Índice general por debajo de 50" in motivos
    assert "3 o más ítems respondidos Regular o Mala" in motivos
    assert out.loc[0, "nivel_alerta"] == "Atención"


def test_divergencia_p06_p14_marca_calidad_de_dato():
    out = sg.calcular_indices(pd.DataFrame([_fila(4, p06=4, p14=2)]))
    assert "Revisar codificación: P6 y P14 difieren mucho" in out.loc[0, "motivos_alerta"]


def test_entrevista_sin_problemas_no_genera_alerta():
    out = sg.calcular_indices(pd.DataFrame([_fila(4)]))
    assert not out.loc[0, "es_alerta"]
    assert out.loc[0, "motivos_alerta"] == []
    assert sg.detectar_alertas(out).empty


def test_detectar_alertas_ordena_rojas_primero():
    df = pd.DataFrame([_fila(2), _fila(4, p09=True), _fila(4)])
    out = sg.detectar_alertas(sg.calcular_indices(df))
    assert len(out) == 2
    assert out.iloc[0]["nivel_alerta"] == "Roja"


# ─── Agregados ───────────────────────────────────────────────
def test_distribucion_items_ordena_peor_primero_y_suma_100():
    df = sg.calcular_indices(pd.DataFrame([_fila(4, p11=1), _fila(4, p11=1)]))
    dist = sg.distribucion_items(df)
    assert dist.iloc[0]["cod"] == "p11"
    for cod, grupo in dist.groupby("cod"):
        assert grupo["pct"].sum() == pytest.approx(100.0)


def test_resumen_dimensiones_reporta_n_items():
    df = sg.calcular_indices(pd.DataFrame([_fila(4)]))
    res = sg.resumen_dimensiones(df)
    vinculos = res[res["clave"] == "vinculos"].iloc[0]
    assert vinculos["n_items"] == 4
    assert res[res["clave"] == "p08"].iloc[0]["tipo"] == "item"


def test_frecuencia_categoria():
    df = pd.DataFrame({"p18": ["El sueldo", "El sueldo", "Los horarios y francos"]})
    frec = sg.frecuencia_categoria(df, "p18")
    assert frec.iloc[-1]["categoria"] == "El sueldo"
    assert frec.iloc[-1]["n"] == 2
    assert frec["pct"].sum() == pytest.approx(100.0)


def test_corte_por_base_excluye_y_nombra_las_bases_chicas():
    filas = [_fila(4, base="Operacion Campana") for _ in range(5)]
    filas.append(_fila(4, base="Operacion Frias"))
    df = sg.calcular_indices(pd.DataFrame(filas))
    tabla, excluidas = sg.corte_por_base(df, min_n=5)
    assert list(tabla["base"]) == ["Operacion Campana"]
    assert excluidas == ["Operacion Frias"]


# ─── Cobertura y pendientes ──────────────────────────────────
def _padron(dias, legajo="100", empleador="MASTER BUS S.A", cargo="CONDUCTORES"):
    return {
        "legajo": legajo, "apenom": "PEREZ JUAN", "empleador": empleador,
        "cargo": cargo, "str": "Operacion Campana",
        "fecha_inicio": date.today() - timedelta(days=dias),
    }


def test_cohorte_pendientes_filtra_por_ventana_y_cargo():
    activos = pd.DataFrame([
        _padron(60, "1"),                      # en ventana
        _padron(10, "2"),                      # muy nuevo
        _padron(200, "3"),                     # vencido hace rato
        _padron(60, "4", cargo="MECANICO"),    # no es conductor
    ])
    out = sg.cohorte_pendientes(activos, pd.DataFrame())
    assert list(out["legajo"]) == ["1"]


def test_cohorte_pendientes_toma_las_dos_grafias_de_cargo():
    activos = pd.DataFrame([_padron(60, "1", cargo="CONDUCTORES"),
                            _padron(60, "2", cargo="CONDUCTOR")])
    out = sg.cohorte_pendientes(activos, pd.DataFrame())
    assert sorted(out["legajo"]) == ["1", "2"]


def test_cohorte_pendientes_excluye_al_ya_entrevistado():
    activos = pd.DataFrame([_padron(60, "1"), _padron(60, "2")])
    seg = pd.DataFrame([{"legajo": "1", "empleador": "MASTER BUS S.A"}])
    out = sg.cohorte_pendientes(activos, seg)
    assert list(out["legajo"]) == ["2"]


def test_legajo_duplicado_entre_empresas_se_resuelve_por_par():
    """15 conductores activos comparten legajo: el join va por (legajo, empleador)."""
    activos = pd.DataFrame([
        _padron(60, "77", empleador="MASTER BUS S.A"),
        _padron(60, "77", empleador="EFE BUS S.A"),
    ])
    seg = pd.DataFrame([{"legajo": "77", "empleador": "MASTER BUS S.A"}])
    out = sg.cohorte_pendientes(activos, seg)
    assert list(out["empleador"]) == ["EFE BUS S.A"]


def test_cohorte_pendientes_marca_vencidos():
    activos = pd.DataFrame([_padron(60, "1"), _padron(110, "2")])
    out = sg.cohorte_pendientes(activos, pd.DataFrame())
    estados = dict(zip(out["legajo"], out["estado"]))
    assert estados == {"1": "A tiempo", "2": "Vencido"}


def test_cobertura_cohorte_cuenta_las_bajas_en_el_denominador():
    """Un conductor que renunció sin entrevista NO debe inflar la cobertura."""
    padron = pd.DataFrame([_padron(90, "1"), _padron(90, "2")])  # el 2 es una baja
    seg = pd.DataFrame([{"legajo": "1", "empleador": "MASTER BUS S.A",
                         "indice_general": 80.0}])
    cob = sg.cobertura_cohorte(padron, seg)
    assert cob.iloc[0]["ingresos"] == 2
    assert cob.iloc[0]["entrevistados"] == 1
    assert cob.iloc[0]["cobertura"] == pytest.approx(50.0)


def test_cobertura_ignora_cohortes_demasiado_recientes():
    padron = pd.DataFrame([_padron(10, "1")])
    assert sg.cobertura_cohorte(padron, pd.DataFrame()).empty


def test_resumen_kpis():
    df = sg.calcular_indices(pd.DataFrame([_fila(4), _fila(4, p20=1)]))
    kpis = sg.resumen_kpis(df)
    assert kpis["entrevistas"] == 2
    assert kpis["recomiendan"] == pytest.approx(50.0)
    assert kpis["alertas"] == 1


def test_resumen_kpis_sin_datos():
    kpis = sg.resumen_kpis(pd.DataFrame())
    assert kpis["entrevistas"] == 0
    assert pd.isna(kpis["indice_general"])


# ─── Exportación ─────────────────────────────────────────────
def test_export_oculta_los_textuales_sin_permiso():
    df = sg.calcular_indices(pd.DataFrame([
        _fila(4, apenom="PEREZ JUAN", p16=True, p16_texto="Problema con el jefe")
    ]))
    con = sg.preparar_export(df, incluir_textos=True)
    sin = sg.preparar_export(df, incluir_textos=False)
    assert any("textual" in c for c in con.columns)
    assert not any("textual" in c for c in sin.columns)
    assert "Problema con el jefe" not in sin.to_csv()


def test_export_sanitiza_caracteres_de_control():
    df = sg.calcular_indices(pd.DataFrame([_fila(4, p18_texto="malo\x0bmuy malo")]))
    out = sg.preparar_export(df, incluir_textos=True)
    assert "\x0b" not in out.to_csv()


def test_exportar_excel_devuelve_un_xlsx_valido():
    import openpyxl
    from io import BytesIO
    df = sg.calcular_indices(pd.DataFrame([_fila(4, apenom="PEREZ JUAN")]))
    data = sg.exportar_excel(df, incluir_textos=True)
    wb = openpyxl.load_workbook(BytesIO(data))
    assert wb.sheetnames == ["Entrevistas"]


def test_exportar_excel_vacio_no_rompe():
    assert sg.exportar_excel(pd.DataFrame(), incluir_textos=True)


# ─── Detalle de una entrevista ───────────────────────────────
def test_detalle_arma_las_8_secciones_del_formulario():
    fila = _fila(4)
    fila.update({"fortalezas": "Puntual"})
    secs = sg.detalle_entrevista(fila, incluir_textos=True)
    titulos = [t for t, _ in secs]
    assert len(secs) == 8
    assert titulos[0].startswith("1.")
    assert "AUTOPERCEPCIÓN" in titulos[6]
    assert titulos[7].startswith("8.")
    # las 20 preguntas + 4 de autopercepción + 1 de conclusión
    assert sum(len(i) for _, i in secs) == 25


def test_detalle_traduce_los_codigos_a_etiquetas_legibles():
    fila = _fila(4, p11=1, p18="El sueldo")
    secs = dict(sg.detalle_entrevista(fila, incluir_textos=True))
    cond = next(i for i in secs["4. CONDICIONES DE TRABAJO"] if i["etiqueta"] == "11")
    assert cond["respuesta"] == "Malo"
    assert cond["color"] == sg.COLOR_CRITICO
    exp = next(i for i in secs["6. EXPECTATIVAS Y PROPUESTAS"] if i["etiqueta"] == "18")
    assert exp["respuesta"] == "El sueldo"


def test_detalle_marca_sin_responder_lo_que_falta():
    fila = _fila(4)
    fila["p11"] = None
    secs = dict(sg.detalle_entrevista(fila, incluir_textos=True))
    item = next(i for i in secs["4. CONDICIONES DE TRABAJO"] if i["etiqueta"] == "11")
    assert item["respuesta"] == "Sin responder"


def test_detalle_pinta_el_flag_en_si_como_problema():
    secs = dict(sg.detalle_entrevista(_fila(4, p16=True), incluir_textos=True))
    item = next(i for i in secs["5. RELACIÓN Y CLIMA LABORAL"] if i["etiqueta"] == "16")
    assert item["respuesta"] == "Sí"
    assert item["color"] == sg.COLOR_CRITICO


def test_detalle_oculta_textuales_y_conclusion_sin_permiso():
    fila = _fila(4, p16=True, p16_texto="Problema con el jefe",
                 fortalezas="Puntual", compromisos="Capacitación")
    con = sg.detalle_entrevista(fila, incluir_textos=True)
    sin = sg.detalle_entrevista(fila, incluir_textos=False)
    assert any(i["textual"] for _, items in con for i in items)
    assert not any(i["textual"] for _, items in sin for i in items)
    # La conclusión entera es textual: no debe existir como sección
    assert any(t.startswith("8.") for t, _ in con)
    assert not any(t.startswith("8.") for t, _ in sin)
