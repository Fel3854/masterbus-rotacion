"""Seguimiento de conductores (2° mes) — catálogo de preguntas y métricas.

Módulo de lógica pura: NO importa Streamlit, así que se puede testear con pytest
sin levantar la app.

El catálogo `PREGUNTAS` es la única fuente de verdad: renderiza el formulario,
arma el dict del insert y define las métricas. Cambiar una pregunta acá se
propaga a los tres lugares.

Escala 1-4 (la misma que trae la validación del xlsx original):
    Mala/Malo = 1 · Regular = 2 · Buena/Bueno = 3 · Muy buena/Muy bueno = 4
Las opciones se listan SIEMPRE de mejor a peor, así `valor = 4 - índice`.
"""

from __future__ import annotations

import re
from datetime import date
from io import BytesIO

import pandas as pd

TABLA = "seguimiento_conductores"

# ─── Parámetros de negocio ───────────────────────────────────
DIAS_OBJETIVO_MIN = 45      # a partir de acá el conductor entra en la cola
DIAS_VENCIDO      = 120     # pasado esto, la entrevista está vencida
MIN_N_CORTE       = 5       # mínimo de entrevistas para mostrar un corte por base
REFERENCIA_BUENA  = 66.7    # índice equivalente a responder "Buena" en todo
MESES_COHORTE     = 12

# ─── Colores (mismos tokens que utils.py / _dashboard.py) ────
COLOR_CRITICO   = "#D12F19"
COLOR_MEJORAR   = "#B45309"
COLOR_BUENO     = "#8C8987"
COLOR_MUY_BUENO = "#15803D"
COLOR_SECUNDARIO = "#46BCD2"

# Escala textual literal de la data-validation del xlsx (sección 7 y preguntas 6/13/14)
ESCALA_XLSX = ("Muy buena", "Buena", "Regular", "Mala")

# ─── Dimensiones analíticas ──────────────────────────────────
# OJO: `dimension` NO es lo mismo que `seccion`. La sección (1-6) ordena el
# formulario tal como está en papel. La dimensión agrupa para los índices:
#   · P5 ("relación con Tráfico y los operadores") pregunta por un vínculo, no
#     por la operación: indexa en 'vinculos' aunque se muestre en la sección 2.
#   · P7 y P18 quedan sin dimensión: un índice de un solo ítem es la pregunta
#     disfrazada con decimales. Se reportan como ítems sueltos.
#
# `cod` (p01…p20) es el nombre de la columna en Postgres y NO se renumera al
# sacar preguntas: `n` es lo único que ve el usuario y va corrido 1..N.
DIMENSIONES = {
    "adaptacion":  "Adaptación e inducción",
    "operacion":   "Operación y unidades",
    "condiciones": "Condiciones de trabajo",
    "vinculos":    "Vínculos y clima",
}

SECCIONES = {
    1: "Adaptación al puesto",
    2: "Operación y unidades",
    3: "Seguridad y conducción",
    4: "Condiciones de trabajo",
    5: "Relación y clima laboral",
    6: "Expectativas y propuestas",
}

PREGUNTAS = [
    # ── Sección 1 · Adaptación al puesto ─────────────────────────────────
    {"cod": "p01", "seccion": 1, "dimension": "adaptacion", "tipo": "escala",
     "texto": "¿Cómo te sentís en estos primeros meses trabajando con nosotros?",
     "corto": "Cómo se siente",
     "opciones": ("Muy bien", "Bien", "Más o menos", "Mal")},

    {"cod": "p02", "seccion": 1, "dimension": None, "tipo": "categoria",
     "texto": "¿Qué fue lo que más te costó durante estos primeros meses?",
     "corto": "Lo que más costó",
     "opciones": ("Aprender los recorridos", "Manejar las unidades",
                  "Uso de la PAD / tablet",
                  "Horarios y francos", "Ritmo / carga de trabajo",
                  "Trámites y documentación", "Trato con pasajeros",
                  "Relación con supervisores", "Adaptarme al grupo",
                  "Nada en particular", "Otro"),
     "texto_label": "Detalle / textual"},

    {"cod": "p03", "seccion": 1, "dimension": "adaptacion", "tipo": "escala",
     "texto": "¿Sentís que recibiste la capacitación necesaria para realizar correctamente tu trabajo?",
     "corto": "Capacitación del puesto",
     "opciones": ("Sí, completa", "Sí, en parte", "Fue escasa", "No recibí")},

    # ── Sección 2 · Operación y unidades ─────────────────────────────────
    {"cod": "p05", "seccion": 2, "dimension": "operacion", "tipo": "escala",
     "texto": "¿Conocés el funcionamiento básico de las diferentes unidades que te asignaron?",
     "corto": "Conocimiento de unidades",
     "opciones": ("Sí, todas", "Casi todas", "Solo algunas", "No")},

    # Se muestra en la sección 2 (forma en papel) pero indexa en 'vinculos':
    # pregunta por un vínculo, y en 'operacion' contaminaría el índice.
    {"cod": "p06", "seccion": 2, "dimension": "vinculos", "tipo": "escala",
     "texto": "¿Cómo es tu relación con Tráfico y los operadores?",
     "corto": "Relación con Tráfico",
     "opciones": ESCALA_XLSX},

    {"cod": "p07", "seccion": 2, "dimension": "operacion", "tipo": "escala",
     "texto": "¿Sabés a quién recurrir y cómo actuar?",
     "corto": "Sabe a quién recurrir",
     "opciones": ("Siempre", "Casi siempre", "A veces", "Nunca")},

    # ── Sección 3 · Seguridad y conducción ───────────────────────────────
    # dimension=None a propósito: un solo ítem no es un índice. Se reporta suelto.
    {"cod": "p08", "seccion": 3, "dimension": None, "tipo": "escala",
     "texto": "¿Considerás que la capacitación recibida en Seguridad Vial fue suficiente?",
     "corto": "Capacitación Seguridad Vial",
     "opciones": ("Sí, suficiente", "En general sí", "Insuficiente", "No la recibí")},

    {"cod": "p09", "seccion": 3, "dimension": None, "tipo": "flag",
     "texto": "¿Hay alguna norma o procedimiento de seguridad que te resulte difícil de cumplir en la práctica?",
     "corto": "Norma difícil de cumplir",
     "opciones": ("No", "Sí"), "alerta_si": True,
     "texto_label": "¿Cuál? (obligatorio si respondió Sí)"},

    {"cod": "p10", "seccion": 3, "dimension": None, "tipo": "categoria",
     "texto": "¿Qué creés que podríamos mejorar para que puedas realizar tu trabajo de manera más segura?",
     "corto": "Mejora de seguridad",
     "opciones": ("Más capacitación", "Estado de las unidades",
                  "Tiempos de recorrido / diagramación", "Descansos y francos",
                  "Estado de rutas y paradas", "Comunicación con Tráfico",
                  "Elementos de seguridad (EPP)", "Instalaciones de la base",
                  "Nada, está bien así", "Otro"),
     "texto_label": "Detalle / textual"},

    # ── Sección 4 · Condiciones de trabajo ───────────────────────────────
    {"cod": "p11", "seccion": 4, "dimension": "condiciones", "tipo": "escala",
     "texto": "¿Cómo te resulta el esquema de horarios y francos?",
     "corto": "Horarios y francos",
     "opciones": ("Muy bueno", "Bueno", "Regular", "Malo")},

    {"cod": "p12", "seccion": 4, "dimension": "condiciones", "tipo": "escala",
     "texto": "¿Cómo evaluás las condiciones generales de trabajo?",
     "corto": "Condiciones generales",
     "opciones": ("Muy buenas", "Buenas", "Regulares", "Malas")},

    # ── Sección 5 · Relación y clima laboral ─────────────────────────────
    {"cod": "p13", "seccion": 5, "dimension": "vinculos", "tipo": "escala",
     "texto": "¿Cómo es tu relación con tus compañeros?",
     "corto": "Relación con compañeros",
     "opciones": ESCALA_XLSX},

    {"cod": "p15", "seccion": 5, "dimension": "vinculos", "tipo": "escala",
     "texto": "¿Sentís que cuando tenés un problema o una duda podés plantearlo y recibir ayuda?",
     "corto": "Puede pedir ayuda",
     "opciones": ("Siempre", "Casi siempre", "A veces", "Nunca")},

    {"cod": "p16", "seccion": 5, "dimension": None, "tipo": "flag",
     "texto": "¿Hay alguna situación o aspecto del ambiente laboral que te esté incomodando?",
     "corto": "Situación incomodando",
     "opciones": ("No", "Sí"), "alerta_si": True,
     "texto_label": "¿Cuál? (obligatorio si respondió Sí)"},

    # ── Sección 6 · Expectativas y propuestas ────────────────────────────
    # P17 / P18 / P19 comparten vocabulario a propósito: permite cruzar
    # atractor vs. detractor sobre los mismos ejes.
    {"cod": "p17", "seccion": 6, "dimension": None, "tipo": "categoria",
     "texto": "¿Qué es lo que más te gusta de trabajar acá?",
     "corto": "Lo que más gusta",
     "opciones": ("El sueldo / cobrar en fecha", "Los compañeros",
                  "La estabilidad del trabajo", "Las unidades / la flota",
                  "Los horarios y francos", "El trato de los jefes",
                  "El recorrido / la operación", "La empresa y su prestigio",
                  "Otro"),
     "texto_label": "Detalle / textual"},

    {"cod": "p18", "seccion": 6, "dimension": None, "tipo": "categoria",
     "texto": "¿Qué es lo que menos te gusta?",
     "corto": "Lo que menos gusta",
     "opciones": ("Los horarios y francos", "El sueldo",
                  "El estado de las unidades", "El trato de los jefes",
                  "La carga de trabajo", "La comunicación interna",
                  "Las instalaciones / la base", "Los tiempos de recorrido",
                  "Nada en particular", "Otro"),
     "texto_label": "Detalle / textual"},

    {"cod": "p19", "seccion": 6, "dimension": None, "tipo": "categoria",
     "texto": "Si pudieras cambiar una sola cosa de la empresa o de la operación, ¿qué cambiarías?",
     "corto": "Qué cambiaría",
     "opciones": ("Horarios y francos", "Sueldo y adicionales",
                  "Estado de las unidades", "Comunicación y trato",
                  "Diagramación de servicios", "Capacitación",
                  "Instalaciones y comodidades", "Nada", "Otro"),
     "texto_label": "Detalle / textual"},

    {"cod": "p20", "seccion": 6, "dimension": None, "tipo": "escala",
     "texto": "Si tuvieras que recomendarle a un conocido trabajar como conductor en nuestra empresa, ¿qué le dirías?",
     "corto": "Recomendaría la empresa",
     "opciones": ("Sí, sin dudas", "Sí, con reparos", "Lo dudaría", "No")},
]

# Sección 7 — AUTOPERCEPCIÓN: el conductor se evalúa a sí mismo.
# Etiquetas textuales de la data-validation del xlsx: "Muy buena,Buena,Regular,Mala"
AUTOEVAL = [
    {"cod": "auto_operaciones", "tipo": "escala", "letra": "A", "corto": "Operaciones",
     "texto": "Operaciones (responsabilidad, compromiso, predisposición)",
     "opciones": ESCALA_XLSX},
    {"cod": "auto_seguridad_vial", "tipo": "escala", "letra": "B", "corto": "Seguridad Vial",
     "texto": "Seguridad Vial (siniestros, infracciones, manejo imprudente)",
     "opciones": ESCALA_XLSX},
    {"cod": "auto_rrhh", "tipo": "escala", "letra": "C", "corto": "RRHH",
     "texto": "RRHH (código de convivencia)",
     "opciones": ESCALA_XLSX},
    {"cod": "auto_mantenimiento", "tipo": "escala", "letra": "D", "corto": "Mantenimiento",
     "texto": "Mantenimiento (manejo de unidades)",
     "opciones": ESCALA_XLSX},
]

# `n` es el número que ve el conductor en el formulario: se calcula por posición
# y queda siempre corrido 1..N. Si mañana se saca una pregunta del catálogo, el
# `cod` (columna de Postgres) no se toca pero la numeración no queda con huecos.
for _i, _p in enumerate(PREGUNTAS, start=1):
    _p["n"] = _i

# ─── Vistas derivadas del catálogo ───────────────────────────
ESCALAS      = [p for p in PREGUNTAS if p["tipo"] == "escala"]
FLAGS        = [p for p in PREGUNTAS if p["tipo"] == "flag"]
CATEGORIAS   = [p for p in PREGUNTAS if p["tipo"] == "categoria"]
COD_ESCALAS  = [p["cod"] for p in ESCALAS]
COD_AUTO     = [a["cod"] for a in AUTOEVAL]
POR_COD      = {p["cod"]: p for p in PREGUNTAS}

# Textuales: los de las categorías + los de los flags, más los de conclusión.
COD_TEXTOS = [p["cod"] + "_texto" for p in PREGUNTAS if "texto_label" in p]
COLUMNAS_TEXTO = COD_TEXTOS + [
    "frases_destacadas", "fortalezas", "aspectos_mejorar", "compromisos",
]

# Observación del entrevistador, una por cada pregunta numerada del catálogo. Es una
# nota interna del entrevistador (distinta del textual, que es la voz del
# conductor); se trata como confidencial igual que los textuales.
COD_OBS = [p["cod"] + "_obs" for p in PREGUNTAS]

COLUMNAS_CABECERA = [
    "id", "legajo", "apenom", "empleador", "base", "cargo",
    "fecha_ingreso", "fecha_entrevista", "entrevistador",
    "fecha_proximo_seguimiento", "registrado_por", "fecha_registro",
]


def columnas_db():
    """Lista completa de columnas de la tabla, derivada del catálogo.

    Alimenta el `.select(...)` de Supabase y el orden de columnas del Excel,
    así el catálogo y el esquema no se desincronizan sin que un test lo note.
    """
    cols = list(COLUMNAS_CABECERA)
    cols += [p["cod"] for p in PREGUNTAS]
    cols += COD_AUTO
    cols += COLUMNAS_TEXTO
    cols += COD_OBS
    return cols


def dimension_de(cod):
    """Dimensión analítica de una pregunta, o None si es un ítem suelto."""
    p = POR_COD.get(cod)
    return p["dimension"] if p else None


def codigos_de_dimension(dim):
    """Códigos de las escalas que componen una dimensión."""
    return [p["cod"] for p in ESCALAS if p["dimension"] == dim]


# ─── Codificación de respuestas ──────────────────────────────
def codigo(preg, label):
    """Convierte la etiqueta elegida en el formulario al valor numérico.

    Las opciones van de mejor a peor, así que la primera vale 4 y la última 1.
    Para los flags devuelve un bool (True = 'Sí' = hay problema).
    """
    if label is None:
        return None
    opciones = preg["opciones"]
    if label not in opciones:
        return None
    if preg["tipo"] == "flag":
        return label == "Sí"
    if preg["tipo"] == "categoria":
        return label
    return 4 - opciones.index(label)


def etiqueta(preg, valor):
    """Inverso de `codigo`: del valor guardado a la etiqueta legible."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    if preg["tipo"] == "flag":
        return "Sí" if valor else "No"
    if preg["tipo"] == "categoria":
        return str(valor)
    try:
        return preg["opciones"][4 - int(valor)]
    except (IndexError, ValueError, TypeError):
        return ""


# ─── Índices ─────────────────────────────────────────────────
def normalizar(media):
    """Media en escala 1-4 → índice 0-100.

    Con escala 1-4 no hay punto medio: 0 = todo "Mala", 100 = todo "Muy buena",
    y 66.7 = todo "Buena" (la referencia que se dibuja en los gráficos).
    """
    if media is None or pd.isna(media):
        return float("nan")
    return (float(media) - 1.0) / 3.0 * 100.0


def banda(indice):
    """Etiqueta y color según el índice 0-100."""
    if indice is None or pd.isna(indice):
        return ("Sin datos", COLOR_BUENO)
    if indice < 50:
        return ("Crítico", COLOR_CRITICO)
    if indice < 67:
        return ("A mejorar", COLOR_MEJORAR)
    if indice < 84:
        return ("Bueno", COLOR_BUENO)
    return ("Muy bueno", COLOR_MUY_BUENO)


def _media_normalizada(df, cols):
    """Media por fila de `cols` (saltando NaN), normalizada a 0-100."""
    presentes = [c for c in cols if c in df.columns]
    if not presentes:
        return pd.Series([float("nan")] * len(df), index=df.index)
    numerico = df[presentes].apply(pd.to_numeric, errors="coerce")
    return numerico.mean(axis=1, skipna=True).apply(normalizar)


def calcular_indices(df):
    """Agrega los índices y las banderas de alerta a un frame de entrevistas.

    No se guardan en la base: se recalculan siempre, así la fórmula vive en un
    solo lugar y cambiarla no deja filas viejas con valores de otra época.
    """
    out = df.copy()
    if out.empty:
        for col in ["indice_general", "indice_autopercepcion", "n_items_1a2"]:
            out[col] = pd.Series(dtype="float64")
        for dim in DIMENSIONES:
            out["indice_" + dim] = pd.Series(dtype="float64")
        out["es_alerta"] = pd.Series(dtype="bool")
        out["motivos_alerta"] = pd.Series(dtype="object")
        out["nivel_alerta"] = pd.Series(dtype="object")
        return out

    out["indice_general"] = _media_normalizada(out, COD_ESCALAS)
    for dim in DIMENSIONES:
        out["indice_" + dim] = _media_normalizada(out, codigos_de_dimension(dim))
    out["indice_autopercepcion"] = _media_normalizada(out, COD_AUTO)

    escalas_presentes = [c for c in COD_ESCALAS if c in out.columns]
    if escalas_presentes:
        numerico = out[escalas_presentes].apply(pd.to_numeric, errors="coerce")
        out["n_items_1a2"] = (numerico <= 2).sum(axis=1)
    else:
        out["n_items_1a2"] = 0

    motivos = out.apply(_motivos_fila, axis=1)
    out["motivos_alerta"] = motivos
    out["es_alerta"] = motivos.apply(bool)
    out["nivel_alerta"] = out.apply(_nivel_fila, axis=1)
    return out


def _val(fila, col):
    v = fila.get(col)
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    return v


# (columna, test, motivo, nivel)
_REGLAS_ALERTA = [
    ("p09", lambda v: v is True or v == 1,
     "Norma de seguridad difícil de cumplir", "Roja"),
    ("p16", lambda v: v is True or v == 1,
     "Situación del ambiente laboral incomodando", "Roja"),
    ("p20", lambda v: v is not None and float(v) == 1,
     "No recomendaría la empresa", "Roja"),
    ("p08", lambda v: v is not None and float(v) == 1,
     "No recibió capacitación de Seguridad Vial", "Roja"),
]


def _motivos_fila(fila):
    motivos = []
    for col, test, motivo, _nivel in _REGLAS_ALERTA:
        v = _val(fila, col)
        try:
            if v is not None and test(v):
                motivos.append(motivo)
        except (TypeError, ValueError):
            continue

    ig = fila.get("indice_general")
    if ig is not None and not pd.isna(ig) and ig < 50:
        motivos.append("Índice general por debajo de 50")

    n12 = fila.get("n_items_1a2")
    if n12 is not None and not pd.isna(n12) and n12 >= 3:
        motivos.append("3 o más ítems respondidos Regular o Mala")

    return motivos


def _nivel_fila(fila):
    motivos = fila.get("motivos_alerta") or []
    rojas = {m for _c, _t, m, n in _REGLAS_ALERTA if n == "Roja"}
    if any(m in rojas for m in motivos):
        return "Roja"
    if motivos:
        return "Atención"
    return ""


def detectar_alertas(df):
    """Solo las filas con alguna alerta, ordenadas por gravedad."""
    if df.empty or "es_alerta" not in df.columns:
        return df.iloc[0:0]
    alertas = df[df["es_alerta"]].copy()
    if alertas.empty:
        return alertas
    orden = {"Roja": 0, "Atención": 1, "": 2}
    alertas["_orden"] = alertas["nivel_alerta"].map(orden).fillna(2)
    alertas = alertas.sort_values(["_orden", "indice_general"], ascending=[True, True])
    return alertas.drop(columns="_orden")


# ─── Agregados para los gráficos ─────────────────────────────
def distribucion_items(df):
    """Frame largo con la distribución 1-4 de cada escala.

    Columnas: cod, corto, texto, valor, etiqueta, n, pct, media, orden.
    Ordenado por media ascendente: los ítems peor puntuados primero.
    """
    filas = []
    for p in ESCALAS:
        cod = p["cod"]
        if cod not in df.columns:
            continue
        serie = pd.to_numeric(df[cod], errors="coerce").dropna()
        if serie.empty:
            continue
        total = len(serie)
        media = serie.mean()
        for valor in (1, 2, 3, 4):
            n = int((serie == valor).sum())
            filas.append({
                "cod": cod,
                "corto": p["corto"],
                "texto": p["texto"],
                "valor": valor,
                "etiqueta": p["opciones"][4 - valor],
                "n": n,
                "pct": (n / total * 100.0) if total else 0.0,
                "media": media,
                "indice": normalizar(media),
                "total": total,
            })
    out = pd.DataFrame(filas)
    if not out.empty:
        out = out.sort_values(["media", "cod", "valor"])
    return out


def resumen_dimensiones(df):
    """Índice por dimensión + los dos ítems sueltos, con el n de ítems y de casos."""
    filas = []
    for dim, nombre in DIMENSIONES.items():
        cols = codigos_de_dimension(dim)
        col = "indice_" + dim
        serie = pd.to_numeric(df[col], errors="coerce").dropna() if col in df.columns else pd.Series(dtype="float64")
        filas.append({
            "clave": dim,
            "nombre": nombre,
            "tipo": "dimension",
            "n_items": len(cols),
            "n_casos": int(len(serie)),
            "indice": float(serie.mean()) if len(serie) else float("nan"),
        })
    for cod, nombre in (("p08", "Capacitación en Seguridad Vial"),
                        ("p20", "Recomendaría la empresa")):
        serie = pd.to_numeric(df[cod], errors="coerce").dropna() if cod in df.columns else pd.Series(dtype="float64")
        filas.append({
            "clave": cod,
            "nombre": nombre,
            "tipo": "item",
            "n_items": 1,
            "n_casos": int(len(serie)),
            "indice": normalizar(serie.mean()) if len(serie) else float("nan"),
        })
    return pd.DataFrame(filas)


def frecuencia_categoria(df, cod):
    """Frecuencia de las opciones de una pregunta de categoría."""
    p = POR_COD.get(cod)
    if p is None or p["tipo"] != "categoria" or cod not in df.columns:
        return pd.DataFrame(columns=["categoria", "n", "pct"])
    serie = df[cod].dropna()
    serie = serie[serie.astype(str).str.strip() != ""]
    if serie.empty:
        return pd.DataFrame(columns=["categoria", "n", "pct"])
    conteo = serie.value_counts()
    total = int(conteo.sum())
    out = pd.DataFrame({
        "categoria": conteo.index.astype(str),
        "n": conteo.values,
    })
    out["pct"] = out["n"] / total * 100.0
    return out.sort_values("n", ascending=True).reset_index(drop=True)


def corte_por_base(df, min_n=MIN_N_CORTE):
    """Índice general por base. Devuelve (tabla, bases excluidas por bajo n)."""
    if df.empty or "base" not in df.columns:
        return pd.DataFrame(columns=["base", "n", "indice"]), []
    tmp = df.copy()
    tmp["base"] = tmp["base"].fillna("").astype(str).str.strip().replace("", "Sin base")
    agrupado = tmp.groupby("base").agg(
        n=("indice_general", "size"),
        indice=("indice_general", "mean"),
    ).reset_index()
    excluidas = agrupado[agrupado["n"] < min_n]["base"].tolist()
    incluidas = agrupado[agrupado["n"] >= min_n].sort_values("indice")
    return incluidas.reset_index(drop=True), sorted(excluidas)


# ─── Cobertura y cola de pendientes ──────────────────────────
def _clave(df, col_legajo="legajo", col_empleador="empleador"):
    """Clave de join normalizada. El legajo NO es único entre empresas."""
    return (df[col_legajo].astype(str).str.strip() + "|"
            + df[col_empleador].astype(str).str.strip())


def _solo_conductores(df):
    if "cargo" not in df.columns:
        return df.iloc[0:0]
    return df[df["cargo"].astype(str).str.startswith("CONDUCTOR", na=False)]


def cohorte_pendientes(df_activos, df_seg, hoy=None):
    """Conductores activos en ventana de entrevista que todavía no la tienen.

    `df_activos` viene de `cargar_empleados_activos()` (necesita cargo, str y
    fecha_inicio). Devuelve columnas: legajo, apenom, empleador, base,
    fecha_ingreso, dias, estado ('A tiempo' | 'Vencido').
    """
    cols = ["legajo", "apenom", "empleador", "base", "fecha_ingreso", "dias", "estado"]
    if df_activos is None or df_activos.empty:
        return pd.DataFrame(columns=cols)

    hoy = hoy or date.today()
    cond = _solo_conductores(df_activos).copy()
    if cond.empty or "fecha_inicio" not in cond.columns:
        return pd.DataFrame(columns=cols)

    inicio = pd.to_datetime(cond["fecha_inicio"], errors="coerce")
    cond["dias"] = (pd.Timestamp(hoy) - inicio).dt.days
    cond = cond[cond["dias"].notna()]
    cond = cond[(cond["dias"] >= DIAS_OBJETIVO_MIN) & (cond["dias"] <= DIAS_VENCIDO)]
    if cond.empty:
        return pd.DataFrame(columns=cols)

    if df_seg is not None and not df_seg.empty:
        ya = set(_clave(df_seg))
        cond = cond[~_clave(cond).isin(ya)]
    if cond.empty:
        return pd.DataFrame(columns=cols)

    cond["base"] = cond["str"].fillna("") if "str" in cond.columns else ""
    cond["fecha_ingreso"] = cond["fecha_inicio"]
    cond["estado"] = cond["dias"].apply(
        lambda d: "Vencido" if d > 90 else "A tiempo"
    )
    cond["dias"] = cond["dias"].astype(int)
    return cond[cols].sort_values("dias", ascending=False).reset_index(drop=True)


def cobertura_cohorte(df_full, df_seg, meses=MESES_COHORTE, hoy=None):
    """Cobertura por mes de ingreso, sobre el padrón COMPLETO (incluye bajas).

    Usar el padrón de activos acá inflaría la cobertura justo en el peor caso:
    un conductor que renunció al día 40 sin entrevista desaparecería del
    denominador.
    """
    cols = ["mes", "ingresos", "entrevistados", "cobertura", "indice"]
    if df_full is None or df_full.empty:
        return pd.DataFrame(columns=cols)

    hoy = hoy or date.today()
    cond = _solo_conductores(df_full).copy()
    if cond.empty or "fecha_inicio" not in cond.columns:
        return pd.DataFrame(columns=cols)

    inicio = pd.to_datetime(cond["fecha_inicio"], errors="coerce")
    cond = cond[inicio.notna()].copy()
    inicio = inicio[inicio.notna()]
    # Solo cohortes que ya tuvieron tiempo de ser entrevistadas.
    limite_sup = pd.Timestamp(hoy) - pd.Timedelta(days=DIAS_OBJETIVO_MIN)
    limite_inf = pd.Timestamp(hoy) - pd.DateOffset(months=meses)
    mask = (inicio <= limite_sup) & (inicio >= limite_inf)
    cond = cond[mask].copy()
    if cond.empty:
        return pd.DataFrame(columns=cols)

    cond["mes"] = pd.to_datetime(cond["fecha_inicio"]).dt.to_period("M").astype(str)
    cond["_k"] = _clave(cond)

    if df_seg is not None and not df_seg.empty:
        seg = df_seg.copy()
        seg["_k"] = _clave(seg)
        indice_por_k = seg.set_index("_k")["indice_general"] if "indice_general" in seg.columns else None
        entrevistados = set(seg["_k"])
    else:
        indice_por_k, entrevistados = None, set()

    cond["entrevistado"] = cond["_k"].isin(entrevistados)
    if indice_por_k is not None:
        cond["indice"] = cond["_k"].map(indice_por_k)
    else:
        cond["indice"] = float("nan")

    out = cond.groupby("mes").agg(
        ingresos=("_k", "size"),
        entrevistados=("entrevistado", "sum"),
        indice=("indice", "mean"),
    ).reset_index()
    out["entrevistados"] = out["entrevistados"].astype(int)
    out["cobertura"] = out["entrevistados"] / out["ingresos"] * 100.0
    return out[cols].sort_values("mes", ascending=False).reset_index(drop=True)


def resumen_kpis(df_seg, df_full=None, hoy=None):
    """Los 6 números de las tarjetas KPI."""
    n = int(len(df_seg))
    kpis = {
        "entrevistas": n,
        "cobertura": float("nan"),
        "indice_general": float("nan"),
        "autopercepcion": float("nan"),
        "recomiendan": float("nan"),
        "alertas": 0,
        "pct_alertas": float("nan"),
    }
    if n == 0:
        return kpis

    if "indice_general" in df_seg.columns:
        serie = pd.to_numeric(df_seg["indice_general"], errors="coerce").dropna()
        kpis["indice_general"] = float(serie.mean()) if len(serie) else float("nan")
    if "indice_autopercepcion" in df_seg.columns:
        serie = pd.to_numeric(df_seg["indice_autopercepcion"], errors="coerce").dropna()
        kpis["autopercepcion"] = float(serie.mean()) if len(serie) else float("nan")
    if "p20" in df_seg.columns:
        serie = pd.to_numeric(df_seg["p20"], errors="coerce").dropna()
        if len(serie):
            kpis["recomiendan"] = float((serie >= 3).sum()) / len(serie) * 100.0
    if "es_alerta" in df_seg.columns:
        kpis["alertas"] = int(df_seg["es_alerta"].sum())
        kpis["pct_alertas"] = kpis["alertas"] / n * 100.0

    if df_full is not None and not df_full.empty:
        cob = cobertura_cohorte(df_full, df_seg, hoy=hoy)
        if not cob.empty:
            total_ing = int(cob["ingresos"].sum())
            total_ent = int(cob["entrevistados"].sum())
            kpis["cobertura"] = (total_ent / total_ing * 100.0) if total_ing else float("nan")
    return kpis


# ─── Detalle de una entrevista ───────────────────────────────
COLOR_VALOR = {4: COLOR_MUY_BUENO, 3: COLOR_SECUNDARIO, 2: COLOR_MEJORAR, 1: COLOR_CRITICO}


def color_respuesta(preg, valor):
    """Color del chip de una respuesta, según qué tan buena es."""
    if valor is None or (not isinstance(valor, (str, bool)) and pd.isna(valor)):
        return COLOR_BUENO
    if preg["tipo"] == "flag":
        # En los flags "Sí" significa que hay un problema.
        return COLOR_CRITICO if valor else COLOR_MUY_BUENO
    if preg["tipo"] == "categoria":
        return COLOR_BUENO
    try:
        return COLOR_VALOR.get(int(valor), COLOR_BUENO)
    except (TypeError, ValueError):
        return COLOR_BUENO


def detalle_entrevista(fila, incluir_textos=True):
    """Estructura una entrevista para mostrarla en pantalla.

    Devuelve [(titulo_seccion, [item, ...])], donde cada item es un dict con
    etiqueta, respuesta ya legible, color y (si corresponde) el textual.
    `incluir_textos=False` omite los textuales — es la puerta de
    confidencialidad para quien no tiene permiso de carga.
    """
    secciones = []

    for num, nombre in SECCIONES.items():
        items = []
        for preg in [q for q in PREGUNTAS if q["seccion"] == num]:
            valor = fila.get(preg["cod"])
            if valor is not None and not isinstance(valor, (str, bool)) and pd.isna(valor):
                valor = None
            texto = ""
            if incluir_textos and "texto_label" in preg:
                texto = fila.get(preg["cod"] + "_texto") or ""
            obs = ""
            if incluir_textos:
                obs = fila.get(preg["cod"] + "_obs") or ""
            items.append({
                "etiqueta": str(preg["n"]),
                "pregunta": preg["texto"],
                "respuesta": etiqueta(preg, valor) or "Sin responder",
                "color": color_respuesta(preg, valor),
                "textual": str(texto).strip(),
                "observacion": str(obs).strip(),
            })
        secciones.append((f"{num}. {nombre.upper()}", items))

    items = []
    for a in AUTOEVAL:
        valor = fila.get(a["cod"])
        if valor is not None and not isinstance(valor, (str, bool)) and pd.isna(valor):
            valor = None
        items.append({
            "etiqueta": a["letra"],
            "pregunta": a["texto"],
            "respuesta": etiqueta(a, valor) or "Sin responder",
            "color": color_respuesta(a, valor),
            "textual": "",
            "observacion": "",
        })
    secciones.append(("7. AUTOPERCEPCIÓN DEL CONDUCTOR", items))

    if incluir_textos:
        items = []
        for campo, nombre in (("fortalezas", "Fortalezas identificadas"),
                              ("aspectos_mejorar", "Aspectos a mejorar"),
                              ("compromisos", "Compromisos / acciones acordadas"),
                              ("frases_destacadas", "Frases destacadas")):
            valor = fila.get(campo)
            if valor and str(valor).strip():
                items.append({
                    "etiqueta": "", "pregunta": nombre,
                    "respuesta": "", "color": COLOR_BUENO,
                    "textual": str(valor).strip(), "observacion": "",
                })
        if items:
            secciones.append(("8. CONCLUSIÓN", items))

    return secciones


# ─── Exportación ─────────────────────────────────────────────
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _limpiar_celda(v):
    """Saca caracteres de control: texto pegado de Word/WhatsApp rompe openpyxl."""
    if isinstance(v, str):
        return _CTRL.sub("", v)
    return v


ETIQUETAS_EXPORT = {
    "legajo": "Legajo", "apenom": "Nombre", "empleador": "Empleador",
    "base": "Base", "cargo": "Cargo", "fecha_ingreso": "Fecha de ingreso",
    "fecha_entrevista": "Fecha de entrevista", "entrevistador": "Entrevistador",
    "fecha_proximo_seguimiento": "Próximo seguimiento",
    "registrado_por": "Registrado por",
    "indice_general": "Índice general", "indice_autopercepcion": "Autopercepción",
    "nivel_alerta": "Alerta", "motivos_alerta": "Motivos de alerta",
    "frases_destacadas": "Frases destacadas", "fortalezas": "Fortalezas",
    "aspectos_mejorar": "Aspectos a mejorar", "compromisos": "Compromisos",
}


def preparar_export(df, incluir_textos):
    """Frame legible para Excel: etiquetas en vez de códigos.

    `incluir_textos=False` deja fuera todas las columnas textuales — es la
    puerta de confidencialidad para quien no tiene permiso de edición.
    """
    if df.empty:
        return pd.DataFrame()

    out = pd.DataFrame(index=df.index)
    for col in ["legajo", "apenom", "empleador", "base", "fecha_ingreso",
                "fecha_entrevista", "entrevistador", "fecha_proximo_seguimiento",
                "registrado_por"]:
        if col in df.columns:
            out[ETIQUETAS_EXPORT.get(col, col)] = df[col]

    for col in ["indice_general", "indice_autopercepcion"]:
        if col in df.columns:
            out[ETIQUETAS_EXPORT[col]] = pd.to_numeric(df[col], errors="coerce").round(1)
    if "nivel_alerta" in df.columns:
        out["Alerta"] = df["nivel_alerta"]
    if "motivos_alerta" in df.columns:
        out["Motivos de alerta"] = df["motivos_alerta"].apply(
            lambda m: " · ".join(m) if isinstance(m, list) else ""
        )

    for p in PREGUNTAS:
        cod = p["cod"]
        if cod not in df.columns:
            continue
        out[f"{p['n']}. {p['corto']}"] = df[cod].apply(lambda v, p=p: etiqueta(p, v))
        if p["tipo"] == "escala":
            out[f"{p['n']}. {p['corto']} (cód.)"] = pd.to_numeric(df[cod], errors="coerce")

    for a in AUTOEVAL:
        if a["cod"] in df.columns:
            out[f"Autopercepción {a['letra']}. {a['corto']}"] = df[a["cod"]].apply(
                lambda v, a=a: etiqueta(a, v)
            )

    if incluir_textos:
        for col in COLUMNAS_TEXTO:
            if col not in df.columns:
                continue
            if col.endswith("_texto"):
                p = POR_COD.get(col[:-6])
                nombre = f"{p['n']}. {p['corto']} — textual" if p else col
            else:
                nombre = ETIQUETAS_EXPORT.get(col, col)
            out[nombre] = df[col]
        # Observación del entrevistador por pregunta (también confidencial).
        for p in PREGUNTAS:
            col = p["cod"] + "_obs"
            if col in df.columns:
                out[f"{p['n']}. {p['corto']} — observación"] = df[col]

    # .map sobre DataFrame reemplaza al applymap deprecado en pandas 2.x
    return out.apply(lambda col: col.map(_limpiar_celda))


def exportar_excel(df, incluir_textos):
    """Bytes de un .xlsx con una hoja 'Entrevistas'."""
    datos = preparar_export(df, incluir_textos)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        if datos.empty:
            pd.DataFrame({"Sin datos": []}).to_excel(writer, sheet_name="Entrevistas", index=False)
        else:
            datos.to_excel(writer, sheet_name="Entrevistas", index=False)
    return buffer.getvalue()
