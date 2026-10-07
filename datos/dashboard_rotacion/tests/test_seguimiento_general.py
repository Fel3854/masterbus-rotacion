"""Tests de la lógica de Seguimiento del personal no conductor (sin Streamlit)."""

import os
import re
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import seguimiento as sg  # noqa: E402
import seguimiento_general as sgen  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ddl():
    with open(os.path.join(RAIZ, "migration_seguimiento_general.sql"), encoding="utf-8") as f:
        return f.read()


def _cuerpo_tabla():
    cuerpo = _ddl().split("CREATE TABLE IF NOT EXISTS seguimiento_general (", 1)[1]
    return cuerpo.split("\n);", 1)[0]


# ─── Catálogo ────────────────────────────────────────────────
def test_catalogo_tiene_las_16_preguntas_del_formulario():
    assert len(sgen.PREGUNTAS) == 16
    assert len(sgen.ESCALAS) == 13
    assert len(sgen.CATEGORIAS) == 2
    assert len(sgen.ABIERTAS) == 1
    assert len(sgen.EVALUACION) == 3
    assert len(sgen.RESULTADOS) == 4


def test_numeracion_visible_va_corrida_sin_huecos():
    assert [p["n"] for p in sgen.PREGUNTAS] == list(range(1, len(sgen.PREGUNTAS) + 1))


def test_toda_pregunta_esta_en_una_seccion_del_formulario():
    assert {p["seccion"] for p in sgen.PREGUNTAS} == set(sgen.SECCIONES)
    assert set(sgen.OBS_SECCION) == set(sgen.SECCIONES)


def test_toda_escala_tiene_un_puntaje_por_opcion_de_mejor_a_peor():
    for p in sgen.ESCALAS + sgen.EVALUACION:
        assert len(p["puntos"]) == len(p["opciones"]), p["cod"]
        assert list(p["puntos"]) == sorted(p["puntos"], reverse=True), p["cod"]
        assert p["puntos"][0] == 100.0, p["cod"]


def test_las_mismas_palabras_valen_lo_mismo_que_en_conductores():
    """«Buena» y «Regular» puntúan igual en los dos cuestionarios."""
    g03 = sgen.POR_COD["g03"]
    assert sgen.puntos(g03, sgen.codigo(g03, "Buena")) == pytest.approx(sg.normalizar(3))
    assert sgen.puntos(g03, sgen.codigo(g03, "Regular")) == pytest.approx(sg.normalizar(2))
    ev = sgen.POR_COD["ev_desempeno"]
    for i, label in enumerate(ev["opciones"]):
        assert sgen.puntos(ev, sgen.codigo(ev, label)) == pytest.approx(sg.normalizar(4 - i))


def test_los_codigos_no_se_pisan_con_los_de_conductores():
    propios = {p["cod"] for p in sgen.PREGUNTAS} | set(sgen.COD_EVAL)
    assert not propios & set(sg.columnas_db())


def test_codigo_hace_roundtrip_en_todas_las_escalas():
    for p in sgen.ESCALAS + sgen.EVALUACION:
        cantidad = len(p["opciones"])
        for i, label in enumerate(p["opciones"]):
            valor = sgen.codigo(p, label)
            assert valor == cantidad - i, (p["cod"], label)
            assert sgen.etiqueta(p, valor) == label
            assert sgen.puntos(p, valor) == p["puntos"][i]


def test_categorias_guardan_la_etiqueta_y_la_abierta_el_texto():
    g05 = sgen.POR_COD["g05"]
    assert sgen.codigo(g05, "Parcialmente") == "Parcialmente"
    assert sgen.etiqueta(g05, "Parcialmente") == "Parcialmente"
    g10 = sgen.POR_COD["g10"]
    assert sgen.codigo(g10, "  Excel avanzado ") == "Excel avanzado"
    assert sgen.codigo(g10, "   ") is None
    assert sgen.codigo(sgen.RESULTADO, sgen.RESULTADOS[1]) == sgen.RESULTADOS[1]


def test_codigo_devuelve_none_ante_valor_invalido():
    g01 = sgen.POR_COD["g01"]
    assert sgen.codigo(g01, None) is None
    assert sgen.codigo(g01, "Tal vez") is None
    assert sgen.etiqueta(g01, 9) == ""
    assert pd.isna(sgen.puntos(g01, 9))
    assert pd.isna(sgen.puntos(g01, None))


def test_las_categorias_no_puntuan():
    """Que algo le haya resultado difícil describe, no baja la nota."""
    for p in sgen.CATEGORIAS:
        assert p["dimension"] is None
        assert "puntos" not in p
        assert p["cod"] not in sgen.COD_ESCALAS


def test_toda_escala_esta_en_una_dimension_de_mas_de_un_item():
    asignadas = {c for d in sgen.DIMENSIONES for c in sgen.codigos_de_dimension(d)}
    assert asignadas == set(sgen.COD_ESCALAS)
    for dim in sgen.DIMENSIONES:
        assert len(sgen.codigos_de_dimension(dim)) >= 2, dim


def test_las_reglas_de_alerta_apuntan_a_las_preguntas_correctas():
    assert "continuar" in sgen.POR_COD[sgen.COD_CONTINUAR]["texto"]
    assert "sentís" in sgen.POR_COD[sgen.COD_CONFORMIDAD]["texto"]
    assert sgen.RESULTADO_NO_CONTINUAR == "No recomendar continuidad"
    assert sgen.RESULTADO_PLAN_MEJORA.startswith("Requiere plan de mejora")


# ─── Contrato catálogo ↔ esquema ─────────────────────────────
def test_columnas_db_no_repite_columnas():
    cols = sgen.columnas_db()
    assert len(cols) == len(set(cols))


def test_columnas_db_coincide_con_el_ddl():
    """Guarda contra el drift entre PREGUNTAS y migration_seguimiento_general.sql."""
    en_sql = []
    for linea in _cuerpo_tabla().splitlines():
        linea = linea.strip()
        if not linea or linea.startswith(("--", "CONSTRAINT", "UNIQUE")):
            continue
        col = linea.split()[0]
        if col.isidentifier():
            en_sql.append(col)
    assert sorted(en_sql) == sorted(sgen.columnas_db())


def test_el_check_de_cada_escala_coincide_con_su_cantidad_de_opciones():
    cuerpo = _cuerpo_tabla()
    for p in sgen.ESCALAS + sgen.EVALUACION:
        m = re.search(rf"\b{p['cod']}\s+SMALLINT CHECK \({p['cod']}\s+BETWEEN 1 AND (\d)\)",
                      cuerpo)
        assert m, p["cod"]
        assert int(m.group(1)) == len(p["opciones"]), p["cod"]


def test_la_tabla_solo_permite_lo_que_la_app_hace():
    """Leer, cargar y eliminar. Sin FOR ALL ni UPDATE: las entrevistas no se editan."""
    sql = _ddl()
    assert "ENABLE ROW LEVEL SECURITY" in sql
    comandos = set(re.findall(r"\bFOR (SELECT|INSERT|UPDATE|DELETE|ALL) TO anon", sql))
    assert comandos == {"SELECT", "INSERT", "DELETE"}


def test_la_migracion_no_toca_la_tabla_de_conductores():
    assert "seguimiento_conductores" not in re.sub(r"--.*", "", _ddl())


# ─── Padrón ──────────────────────────────────────────────────
def test_solo_no_conductores_deja_afuera_las_dos_grafias():
    padron = pd.DataFrame({
        "legajo": ["1", "2", "3", "4", "5"],
        "cargo": ["CONDUCTORES", "CONDUCTOR", "MECANICO", None, "ADMINISTRATIVO"],
    })
    assert list(sgen.solo_no_conductores(padron)["legajo"]) == ["3", "4", "5"]


def test_entre_los_dos_cuestionarios_no_queda_nadie_afuera_ni_repetido():
    padron = pd.DataFrame({
        "legajo": ["1", "2", "3"], "cargo": ["CONDUCTOR", "LAVADOR", "CONDUCTORES"]})
    conductores = set(sg._solo_conductores(padron)["legajo"])
    resto = set(sgen.solo_no_conductores(padron)["legajo"])
    assert conductores | resto == set(padron["legajo"])
    assert not conductores & resto


def test_normalizar_sector_unifica_grafias():
    assert sgen.normalizar_sector("  taller   mecánico ") == "TALLER MECANICO"
    assert sgen.normalizar_sector("Administración") == sgen.normalizar_sector("ADMINISTRACION ")
    assert sgen.normalizar_sector("güemes") == "GUEMES"
    assert sgen.normalizar_sector(None) == ""
    assert sgen.normalizar_sector("   ") == ""


def test_normalizar_sector_conserva_la_enie():
    assert sgen.normalizar_sector("pañol") == "PAÑOL"
    assert sgen.normalizar_sector("pañol") == "PAÑOL"       # ñ escrita en dos caracteres


# ─── Índices ─────────────────────────────────────────────────
def _fila(mejor=True, **extra):
    """Entrevista con todo en la mejor opción (o en la más baja)."""
    fila = {p["cod"]: len(p["opciones"]) if mejor else 1 for p in sgen.ESCALAS}
    fila.update({e["cod"]: len(e["opciones"]) if mejor else 1 for e in sgen.EVALUACION})
    fila.update({"g05": "No", "g14": "No", "resultado": sgen.RESULTADOS[0]})
    fila.update(extra)
    return fila


def test_indices_extremos():
    out = sgen.calcular_indices(pd.DataFrame([_fila(True), _fila(False)]))
    assert out.loc[0, "indice_general"] == 100.0
    assert out.loc[0, "indice_evaluacion"] == 100.0
    for dim in sgen.DIMENSIONES:
        assert out.loc[0, "indice_" + dim] == 100.0
    assert out.loc[1, "indice_evaluacion"] == 0.0
    # Abajo no da 0: cuatro preguntas no ofrecen nada peor que «Regular» o «Poco conforme».
    assert 0 < out.loc[1, "indice_general"] < 15
    assert out.loc[1, "n_items_bajos"] == len(sgen.ESCALAS)


def test_las_respuestas_intermedias_valen_segun_sus_palabras():
    fila = _fila(True, g01=2, g03=2)          # «Parcialmente» y «Buena»
    out = sgen.calcular_indices(pd.DataFrame([fila]))
    assert out.loc[0, "indice_induccion"] == pytest.approx(75.0)            # (50 + 100) / 2
    assert out.loc[0, "indice_adaptacion"] == pytest.approx((200 / 3 + 100) / 2)
    assert out.loc[0, "n_items_bajos"] == 0


def test_un_item_nulo_saltea_ese_item_en_vez_de_anular_el_indice():
    fila = _fila(True)
    fila["g07"] = None
    out = sgen.calcular_indices(pd.DataFrame([fila]))
    assert out.loc[0, "indice_general"] == 100.0
    assert out.loc[0, "indice_puesto"] == 100.0


def test_la_evaluacion_del_sector_no_entra_en_el_indice_general():
    out = sgen.calcular_indices(pd.DataFrame([_fila(True, ev_desempeno=2, ev_compromiso=2,
                                                    ev_adaptacion=2)]))
    assert out.loc[0, "indice_general"] == 100.0
    assert out.loc[0, "indice_evaluacion"] == pytest.approx(100 / 3)


def test_calcular_indices_sobre_frame_vacio_no_rompe():
    out = sgen.calcular_indices(pd.DataFrame())
    assert out.empty
    for col in ("indice_general", "indice_evaluacion", "es_alerta", "nivel_alerta"):
        assert col in out.columns


# ─── Alertas ─────────────────────────────────────────────────
@pytest.mark.parametrize("extra,motivo,nivel", [
    ({"resultado": "No recomendar continuidad"}, "No se recomienda la continuidad", "Roja"),
    ({"g15": 1}, "No quiere continuar en la empresa", "Roja"),
    ({"ev_compromiso": 1},
     "Evaluación del sector insuficiente: Compromiso y responsabilidad", "Roja"),
    ({"resultado": "Requiere plan de mejora/capacitación"},
     "Requiere plan de mejora o capacitación", "Atención"),
    ({"g13": 1}, "Poco conforme trabajando en la empresa", "Atención"),
])
def test_cada_regla_dispara_por_separado(extra, motivo, nivel):
    out = sgen.calcular_indices(pd.DataFrame([_fila(True, **extra)]))
    assert out.loc[0, "es_alerta"]
    assert out.loc[0, "motivos_alerta"] == [motivo]
    assert out.loc[0, "nivel_alerta"] == nivel


def test_la_evaluacion_insuficiente_nombra_todas_las_areas():
    out = sgen.calcular_indices(pd.DataFrame([_fila(True, ev_desempeno=1, ev_adaptacion=1)]))
    assert out.loc[0, "motivos_alerta"] == [
        "Evaluación del sector insuficiente: Desempeño, Adaptación"]


def test_tres_respuestas_en_la_opcion_mas_baja_disparan_atencion():
    dos = sgen.calcular_indices(pd.DataFrame([_fila(True, g01=1, g02=1)]))
    assert not dos.loc[0, "es_alerta"]
    tres = sgen.calcular_indices(pd.DataFrame([_fila(True, g01=1, g02=1, g03=1)]))
    assert tres.loc[0, "motivos_alerta"] == ["3 o más respuestas en la opción más baja"]
    assert tres.loc[0, "nivel_alerta"] == "Atención"


def test_indice_bajo_dispara_atencion():
    out = sgen.calcular_indices(pd.DataFrame([_fila(False, g15=2, g13=2,
                                                    ev_desempeno=3, ev_compromiso=3,
                                                    ev_adaptacion=3)]))
    assert "Índice general por debajo de 50" in out.loc[0, "motivos_alerta"]
    assert out.loc[0, "nivel_alerta"] == "Atención"


def test_continuidad_con_seguimiento_no_es_alerta():
    out = sgen.calcular_indices(pd.DataFrame([
        _fila(True, resultado="Recomendar continuidad con seguimiento")]))
    assert not out.loc[0, "es_alerta"]


def test_entrevista_sin_problemas_no_genera_alerta():
    out = sgen.calcular_indices(pd.DataFrame([_fila(True, g05="Sí", g14="Sí")]))
    assert not out.loc[0, "es_alerta"]
    assert out.loc[0, "motivos_alerta"] == []
    assert out.loc[0, "nivel_alerta"] == ""
    assert sgen.detectar_alertas(out).empty


def test_detectar_alertas_ordena_rojas_primero():
    df = pd.DataFrame([_fila(True, g13=1), _fila(True, g15=1), _fila(True)])
    out = sgen.detectar_alertas(sgen.calcular_indices(df))
    assert list(out["nivel_alerta"]) == ["Roja", "Atención"]


# ─── Agregados ───────────────────────────────────────────────
def test_distribucion_items_ordena_peor_primero_y_suma_100():
    df = sgen.calcular_indices(pd.DataFrame([_fila(True, g07=1), _fila(True, g07=1)]))
    dist = sgen.distribucion_items(df)
    assert dist.iloc[0]["cod"] == "g07"
    assert set(dist["cod"]) == set(sgen.COD_ESCALAS)
    for _cod, grupo in dist.groupby("cod"):
        assert grupo["pct"].sum() == pytest.approx(100.0)
        assert len(grupo) == 3


def test_distribucion_de_la_evaluacion_usa_sus_cuatro_opciones():
    df = pd.DataFrame([_fila(True), _fila(True, ev_desempeno=1)])
    dist = sgen.distribucion_items(df, sgen.EVALUACION)
    assert set(dist["cod"]) == set(sgen.COD_EVAL)
    desempeno = dist[dist["cod"] == "ev_desempeno"]
    assert len(desempeno) == 4
    assert desempeno.iloc[0]["rotulo"] == "A. Desempeño"
    assert desempeno.iloc[0]["indice"] == pytest.approx(50.0)


def test_resumen_dimensiones_reporta_n_items():
    res = sgen.resumen_dimensiones(sgen.calcular_indices(pd.DataFrame([_fila(True)])))
    assert list(res["clave"]) == list(sgen.DIMENSIONES)
    motivacion = res[res["clave"] == "motivacion"].iloc[0]
    assert motivacion["n_items"] == 3
    assert motivacion["indice"] == 100.0


def test_frecuencia_categoria_respeta_el_orden_del_catalogo():
    df = pd.DataFrame({"resultado": [sgen.RESULTADOS[3], sgen.RESULTADOS[0],
                                     sgen.RESULTADOS[0], "texto viejo", None]})
    frec = sgen.frecuencia_categoria(df, "resultado")
    assert list(frec["categoria"]) == list(sgen.RESULTADOS)
    assert list(frec["n"]) == [2, 0, 0, 1]
    assert frec["pct"].sum() == pytest.approx(100.0)
    assert sgen.frecuencia_categoria(df, "g01").empty       # no es una categoría


def test_corte_por_sector_excluye_y_nombra_los_sectores_chicos():
    filas = [_fila(True, sector="TALLER") for _ in range(5)]
    filas.append(_fila(True, sector="COMPRAS"))
    df = sgen.calcular_indices(pd.DataFrame(filas))
    tabla, excluidos = sgen.corte_por_sector(df, min_n=5)
    assert list(tabla["sector"]) == ["TALLER"]
    assert tabla.iloc[0]["n"] == 5
    assert excluidos == ["COMPRAS"]


def test_resumen_kpis():
    df = sgen.calcular_indices(pd.DataFrame([
        _fila(True),
        _fila(True, g15=2, resultado="Recomendar continuidad con seguimiento"),
        _fila(True, g15=1, resultado="No recomendar continuidad"),
        _fila(True, resultado="Requiere plan de mejora/capacitación"),
    ]))
    kpis = sgen.resumen_kpis(df)
    assert kpis["entrevistas"] == 4
    assert kpis["quieren_continuar"] == pytest.approx(50.0)     # sólo los que dijeron «Sí»
    assert kpis["continuidad"] == pytest.approx(50.0)
    assert kpis["alertas"] == 2
    assert kpis["evaluacion"] == 100.0


def test_resumen_kpis_sin_datos():
    kpis = sgen.resumen_kpis(pd.DataFrame())
    assert kpis["entrevistas"] == 0
    assert pd.isna(kpis["indice_general"])


# ─── Exportación ─────────────────────────────────────────────
TEXTOS = {
    "g05": "Sí", "g05_texto": "El sistema de carga",
    "g14": "Sí", "g14_texto": "Mejor comunicación",
    "g10": "Excel avanzado",
    "obs_induccion": "Llegó sin inducción formal",
    "obs_evaluacion": "Muy prolijo",
    "observaciones_finales": "Se lo ve cómodo",
}


def test_export_oculta_todo_el_texto_libre_sin_permiso():
    df = sgen.calcular_indices(pd.DataFrame([_fila(True, apenom="PEREZ JUAN", **TEXTOS)]))
    con = sgen.preparar_export(df, incluir_textos=True).to_csv()
    sin = sgen.preparar_export(df, incluir_textos=False).to_csv()
    for col in sgen.COLUMNAS_TEXTO:
        if col in TEXTOS:
            assert TEXTOS[col] in con, col
            assert TEXTOS[col] not in sin, col
    assert "PEREZ JUAN" in sin and "Recomendar continuidad" in sin


def test_export_traduce_los_codigos_y_sanitiza():
    df = sgen.calcular_indices(pd.DataFrame([
        _fila(True, g01=2, cargo="LAVADOR", sector="LAVADERO",
              observaciones_finales="bien\x0bmuy bien")]))
    out = sgen.preparar_export(df, incluir_textos=True)
    assert out.loc[0, "1. Inducción sobre la empresa"] == "Parcialmente"
    assert out.loc[0, "1. Inducción sobre la empresa (pts.)"] == 50.0
    assert out.loc[0, "Puesto"] == "LAVADOR"
    assert out.loc[0, "Evaluación del sector A. Desempeño"] == "Muy bueno"
    assert "\x0b" not in out.to_csv()


def test_exportar_excel_devuelve_un_xlsx_valido():
    import openpyxl
    from io import BytesIO
    df = sgen.calcular_indices(pd.DataFrame([_fila(True, apenom="PEREZ JUAN")]))
    wb = openpyxl.load_workbook(BytesIO(sgen.exportar_excel(df, incluir_textos=True)))
    assert wb.sheetnames == ["Entrevistas"]
    assert sgen.exportar_excel(pd.DataFrame(), incluir_textos=True)


# ─── Detalle de una entrevista ───────────────────────────────
def test_detalle_arma_las_9_secciones_del_formulario():
    secs = sgen.detalle_entrevista(_fila(True), incluir_textos=True)
    titulos = [t for t, _ in secs]
    assert len(secs) == 9
    assert titulos[0] == "1. INDUCCIÓN"
    assert titulos[7] == "8. EVALUACIÓN GENERAL DEL SECTOR"
    assert titulos[8] == "9. RESULTADO DE LA ENTREVISTA"
    # 16 preguntas + 3 de evaluación + el resultado, sin observaciones cargadas
    assert sum(len(i) for _, i in secs) == len(sgen.PREGUNTAS) + 4


def test_detalle_traduce_los_codigos_y_los_colorea_por_puntos():
    fila = _fila(True, g01=2, g03=2, g07=1, resultado="No recomendar continuidad")
    secs = dict(sgen.detalle_entrevista(fila, incluir_textos=True))
    por_n = {i["etiqueta"]: i for _, items in secs.items() for i in items}
    assert por_n["1"]["respuesta"] == "Parcialmente"
    assert por_n["1"]["color"] == sgen.COLOR_MEJORAR
    assert por_n["3"]["respuesta"] == "Buena"
    assert por_n["3"]["color"] == sgen.COLOR_SECUNDARIO
    assert por_n["7"]["respuesta"] == "No"
    assert por_n["7"]["color"] == sgen.COLOR_CRITICO
    assert por_n["2"]["color"] == sgen.COLOR_MUY_BUENO
    resultado = secs["9. RESULTADO DE LA ENTREVISTA"][0]
    assert resultado["respuesta"] == "No recomendar continuidad"
    assert resultado["color"] == sgen.COLOR_CRITICO


def test_detalle_marca_sin_responder_lo_que_falta():
    fila = _fila(True)
    fila["g07"] = None
    secs = dict(sgen.detalle_entrevista(fila, incluir_textos=True))
    item = next(i for i in secs["3. PUESTO DE TRABAJO"] if i["etiqueta"] == "7")
    assert item["respuesta"] == "Sin responder"


def test_detalle_oculta_el_texto_libre_sin_permiso():
    fila = _fila(True, **TEXTOS)
    con = sgen.detalle_entrevista(fila, incluir_textos=True)
    sin = sgen.detalle_entrevista(fila, incluir_textos=False)

    def _textos(secs):
        return [i["textual"] or i["observacion"] for _, items in secs for i in items
                if i["textual"] or i["observacion"]]

    assert sorted(_textos(con)) == sorted(
        v for k, v in TEXTOS.items() if k in sgen.COLUMNAS_TEXTO)
    assert _textos(sin) == []
    # Sin permiso se sabe que contestó la abierta, no qué contestó.
    abierta = next(i for _, items in sin for i in items if i["etiqueta"] == "10")
    assert abierta["respuesta"] == "Respondida"


def test_detalle_avisa_si_la_pregunta_abierta_quedo_vacia():
    for permiso in (True, False):
        secs = sgen.detalle_entrevista(_fila(True), incluir_textos=permiso)
        abierta = next(i for _, items in secs for i in items if i["etiqueta"] == "10")
        assert abierta["respuesta"] == "Sin responder"
        assert abierta["textual"] == ""
