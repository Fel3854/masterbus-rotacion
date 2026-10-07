"""Seguimiento del personal ingresante que NO es conductor — catálogo y métricas.

Segundo cuestionario del ítem Seguimiento: la «Encuesta de seguimiento –
personal ingresante» (la de efectivización) que se le toma al resto del
personal. Los conductores tienen el suyo en `seguimiento.py`.

Módulo de lógica pura: NO importa Streamlit, así que se puede testear con pytest
sin levantar la app.

Va en un módulo y una tabla aparte, y no como un caso más de `seguimiento.py`,
porque los dos formularios no comparten ni preguntas ni forma:
  · acá casi todas las respuestas son de 3 opciones, allá de 4;
  · acá hay una evaluación que hace el sector y un resultado de la entrevista,
    allá una autopercepción del conductor y una conclusión;
  · acá las observaciones son una por sección, allá una por pregunta.
Los índices de uno y otro se leen igual (0 a 100, mismas bandas) pero NO se
comparan entre sí: miden preguntas distintas.

El catálogo `PREGUNTAS` es la única fuente de verdad: renderiza el formulario,
arma el dict del insert y define las métricas.
"""

from __future__ import annotations

import unicodedata
from io import BytesIO

import pandas as pd

from seguimiento import (COLOR_BUENO, COLOR_CRITICO, COLOR_MEJORAR,  # noqa: F401
                         COLOR_MUY_BUENO, COLOR_SECUNDARIO, MIN_N_CORTE,
                         _limpiar_celda, banda)

TABLA = "seguimiento_general"

# ─── Escalas ─────────────────────────────────────────────────
# Las opciones se listan SIEMPRE de mejor a peor. En la base se guarda la
# posición (`valor = cantidad de opciones − índice`: la mejor vale el número más
# alto y la peor vale 1), igual que en conductores. Los puntos viven sólo acá,
# así cambiar la fórmula no deja filas viejas con valores de otra época.
#
# Los puntos siguen a las palabras, no a la posición: «Buena» vale 67 y
# «Regular» 33, lo mismo que en la escala de 4 de conductores (Muy buena · Buena
# · Regular · Mala = 100 · 67 · 33 · 0). Este formulario no ofrece «Mala», así
# que su opción más baja en esas preguntas vale 33 y no 0: «Regular» no es el
# piso, es que el papel no deja contestar algo peor.
_TERCIO = 100.0 / 3.0

SI_PARCIAL_NO = ("Sí", "Parcialmente", "No")
SI_TALVEZ_NO  = ("Sí", "Tal vez", "No")
PUNTOS_SI_NO  = (100.0, 50.0, 0.0)
PUNTOS_BUENA  = (100.0, 2 * _TERCIO, _TERCIO)

ESCALA_EVAL   = ("Muy bueno", "Bueno", "Regular", "Insuficiente")
ESCALA_EVAL_F = ("Muy buena", "Buena", "Regular", "Insuficiente")
PUNTOS_EVAL   = (100.0, 2 * _TERCIO, _TERCIO, 0.0)

REFERENCIA_BUENA = 2 * _TERCIO   # índice de quien responde «Buena» / «Conforme»
PUNTOS_BAJO      = 34.0          # hasta acá la respuesta es la más baja: No · Regular · Poco conforme

# ─── Secciones y dimensiones ─────────────────────────────────
# El papel repite el «2» (Adaptación y Puesto de trabajo): acá van corridas.
SECCIONES = {
    1: "Inducción",
    2: "Adaptación",
    3: "Puesto de trabajo",
    4: "Capacitación",
    5: "Equipo y ambiente laboral",
    6: "Motivación",
    7: "Expectativas",
}
N_SECCION_EVALUACION = len(SECCIONES) + 1
N_SECCION_RESULTADO  = len(SECCIONES) + 2
TITULO_EVALUACION = "Evaluación general del sector"
TITULO_RESULTADO  = "Resultado de la entrevista"

# Las dimensiones son las secciones, salvo Motivación y Expectativas, que van
# juntas: Motivación tiene una sola pregunta que puntúa, y un índice de un solo
# ítem es la pregunta disfrazada con decimales.
DIMENSIONES = {
    "induccion":    "Inducción",
    "adaptacion":   "Adaptación",
    "puesto":       "Puesto de trabajo",
    "capacitacion": "Capacitación",
    "equipo":       "Equipo y ambiente laboral",
    "motivacion":   "Motivación y expectativas",
}

# Tipos de pregunta:
#   · escala    → puntúa (lleva `puntos`) y entra en los índices.
#   · categoria → respuesta cerrada que describe y no puntúa: que algo le haya
#                 resultado difícil a un ingresante no es una mala nota.
#   · abierta   → texto libre, sin respuesta cerrada.
#
# `cod` (g01…g16) es el nombre de la columna en Postgres y NO se renumera al
# sacar preguntas: `n` es lo único que ve el usuario y va corrido 1..N. La «g»
# es para que no se confundan con las `pNN` de la tabla de conductores.
PREGUNTAS = [
    # ── Sección 1 · Inducción ────────────────────────────────────────────
    {"cod": "g01", "seccion": 1, "dimension": "induccion", "tipo": "escala",
     "texto": "¿Recibiste la inducción necesaria sobre la empresa?",
     "ayuda": "Sectores, contactos, bases, qué hace cada persona, etc.",
     "corto": "Inducción sobre la empresa",
     "opciones": SI_PARCIAL_NO, "puntos": PUNTOS_SI_NO},

    {"cod": "g02", "seccion": 1, "dimension": "induccion", "tipo": "escala",
     "texto": "¿Recibiste la inducción necesaria sobre tu sector?",
     "ayuda": "Organigrama, perfiles, contactos, horarios, costumbres del área, etc.",
     "corto": "Inducción sobre el sector",
     "opciones": SI_PARCIAL_NO, "puntos": PUNTOS_SI_NO},

    # ── Sección 2 · Adaptación ───────────────────────────────────────────
    {"cod": "g03", "seccion": 2, "dimension": "adaptacion", "tipo": "escala",
     "texto": "¿Cómo fue tu adaptación a la empresa y al puesto?",
     "corto": "Adaptación a la empresa y al puesto",
     "opciones": ("Muy buena", "Buena", "Regular"), "puntos": PUNTOS_BUENA},

    {"cod": "g04", "seccion": 2, "dimension": "adaptacion", "tipo": "escala",
     "texto": "¿Tus compañeros te ayudaron en la adaptación?",
     "corto": "Ayuda de los compañeros",
     "opciones": SI_PARCIAL_NO, "puntos": PUNTOS_SI_NO},

    {"cod": "g05", "seccion": 2, "dimension": None, "tipo": "categoria",
     "texto": "¿Hay algo que te haya resultado difícil?",
     "corto": "Algo le resultó difícil",
     "opciones": SI_PARCIAL_NO,
     "texto_label": "¿Qué? (obligatorio si respondió Sí)", "texto_si": ("Sí",)},

    # ── Sección 3 · Puesto de trabajo ────────────────────────────────────
    {"cod": "g06", "seccion": 3, "dimension": "puesto", "tipo": "escala",
     "texto": "¿Tenés claras cuáles son las tareas y responsabilidades de tu puesto?",
     "corto": "Tareas y responsabilidades claras",
     "opciones": SI_PARCIAL_NO, "puntos": PUNTOS_SI_NO},

    {"cod": "g07", "seccion": 3, "dimension": "puesto", "tipo": "escala",
     "texto": "¿El esquema de horarios y francos te parece correcto?",
     "corto": "Horarios y francos",
     "opciones": SI_PARCIAL_NO, "puntos": PUNTOS_SI_NO},

    # ── Sección 4 · Capacitación ─────────────────────────────────────────
    {"cod": "g08", "seccion": 4, "dimension": "capacitacion", "tipo": "escala",
     "texto": "¿Considerás que recibiste la capacitación necesaria para realizar tu trabajo?",
     "corto": "Capacitación necesaria",
     "opciones": SI_PARCIAL_NO, "puntos": PUNTOS_SI_NO},

    {"cod": "g09", "seccion": 4, "dimension": "capacitacion", "tipo": "escala",
     "texto": "¿Te facilitaron los procedimientos escritos sobre tus tareas?",
     "corto": "Procedimientos escritos",
     "opciones": SI_PARCIAL_NO, "puntos": PUNTOS_SI_NO},

    {"cod": "g10", "seccion": 4, "dimension": None, "tipo": "abierta",
     "texto": "¿Qué otra capacitación considerás que te sería útil para mejorar "
              "en tu puesto de trabajo?",
     "corto": "Otra capacitación útil"},

    # ── Sección 5 · Equipo y ambiente laboral ────────────────────────────
    {"cod": "g11", "seccion": 5, "dimension": "equipo", "tipo": "escala",
     "texto": "¿Cómo es la relación con tus compañeros y superiores?",
     "corto": "Relación con compañeros y superiores",
     "opciones": ("Muy buena", "Buena", "Regular"), "puntos": PUNTOS_BUENA},

    {"cod": "g12", "seccion": 5, "dimension": "equipo", "tipo": "escala",
     "texto": "¿Cómo evaluás el ambiente de trabajo?",
     "corto": "Ambiente de trabajo",
     "opciones": ("Muy bueno", "Bueno", "Regular"), "puntos": PUNTOS_BUENA},

    # ── Sección 6 · Motivación ───────────────────────────────────────────
    {"cod": "g13", "seccion": 6, "dimension": "motivacion", "tipo": "escala",
     "texto": "¿Cómo te sentís trabajando en la empresa?",
     "corto": "Conformidad con la empresa",
     "opciones": ("Muy conforme", "Conforme", "Poco conforme"), "puntos": PUNTOS_BUENA},

    {"cod": "g14", "seccion": 6, "dimension": None, "tipo": "categoria",
     "texto": "¿Creés que la empresa podría mejorar la experiencia del empleado?",
     "corto": "La empresa podría mejorar la experiencia",
     "opciones": SI_TALVEZ_NO,
     "texto_label": "¿Cómo? (obligatorio si respondió Sí)", "texto_si": ("Sí",)},

    # ── Sección 7 · Expectativas ─────────────────────────────────────────
    {"cod": "g15", "seccion": 7, "dimension": "motivacion", "tipo": "escala",
     "texto": "¿Te gustaría continuar trabajando en la empresa?",
     "corto": "Quiere continuar en la empresa",
     "opciones": SI_TALVEZ_NO, "puntos": PUNTOS_SI_NO},

    {"cod": "g16", "seccion": 7, "dimension": "motivacion", "tipo": "escala",
     "texto": "¿Creés que hay posibilidades de crecimiento en el área donde "
              "ingresaste o en otro sector?",
     "corto": "Posibilidades de crecimiento",
     "opciones": SI_TALVEZ_NO, "puntos": PUNTOS_SI_NO},
]

# Preguntas que las reglas de alerta nombran. Un test cuida que sigan
# apuntando a lo que dicen.
COD_CONFORMIDAD = "g13"
COD_CONTINUAR   = "g15"

# Sección 8 — EVALUACIÓN DEL SECTOR: acá no habla el ingresante, lo evalúa su
# sector. Por eso tiene índice propio y no entra en el índice general.
EVALUACION = [
    {"cod": "ev_desempeno", "tipo": "escala", "letra": "A", "corto": "Desempeño",
     "texto": "Desempeño",
     "opciones": ESCALA_EVAL, "puntos": PUNTOS_EVAL},
    {"cod": "ev_compromiso", "tipo": "escala", "letra": "B",
     "corto": "Compromiso y responsabilidad",
     "texto": "Compromiso y responsabilidad",
     "opciones": ESCALA_EVAL, "puntos": PUNTOS_EVAL},
    {"cod": "ev_adaptacion", "tipo": "escala", "letra": "C", "corto": "Adaptación",
     "texto": "Adaptación",
     "opciones": ESCALA_EVAL_F, "puntos": PUNTOS_EVAL},
]

# Sección 9 — RESULTADO: una sola opción, de la más favorable a la menos.
RESULTADOS = (
    "Recomendar continuidad",
    "Recomendar continuidad con seguimiento",
    "Requiere plan de mejora/capacitación",
    "No recomendar continuidad",
)
RESULTADO = {"cod": "resultado", "tipo": "categoria", "corto": "Resultado",
             "texto": TITULO_RESULTADO, "opciones": RESULTADOS}
RESULTADO_NO_CONTINUAR = RESULTADOS[3]
RESULTADO_PLAN_MEJORA  = RESULTADOS[2]
RESULTADOS_CONTINUIDAD = RESULTADOS[:2]
COLOR_RESULTADO = dict(zip(
    RESULTADOS, (COLOR_MUY_BUENO, COLOR_SECUNDARIO, COLOR_MEJORAR, COLOR_CRITICO)))

# `n` es el número que se ve en pantalla: va por posición, siempre corrido.
for _i, _p in enumerate(PREGUNTAS, start=1):
    _p["n"] = _i

# ─── Vistas derivadas del catálogo ───────────────────────────
ESCALAS     = [p for p in PREGUNTAS if p["tipo"] == "escala"]
CATEGORIAS  = [p for p in PREGUNTAS if p["tipo"] == "categoria"]
ABIERTAS    = [p for p in PREGUNTAS if p["tipo"] == "abierta"]
CERRADAS    = [p for p in PREGUNTAS if p["tipo"] != "abierta"]
COD_ESCALAS = [p["cod"] for p in ESCALAS]
COD_EVAL    = [e["cod"] for e in EVALUACION]
POR_COD     = {p["cod"]: p for p in PREGUNTAS + EVALUACION + [RESULTADO]}

# Observaciones: una por sección, como en el papel.
OBS_SECCION = {
    1: "obs_induccion",
    2: "obs_adaptacion",
    3: "obs_puesto",
    4: "obs_capacitacion",
    5: "obs_equipo",
    6: "obs_motivacion",
    7: "obs_expectativas",
}
OBS_EVALUACION = "obs_evaluacion"
OBS_FINALES    = "observaciones_finales"

# Todo lo que es texto libre. Es confidencial: sólo lo ve quien tiene permiso
# de carga, igual que los textuales de conductores.
COD_TEXTOS = [p["cod"] + "_texto" for p in PREGUNTAS if "texto_label" in p]
COLUMNAS_TEXTO = ([p["cod"] for p in ABIERTAS] + COD_TEXTOS
                  + list(OBS_SECCION.values()) + [OBS_EVALUACION, OBS_FINALES])

# `base` y `cargo` salen del padrón, con los mismos nombres que en la tabla de
# conductores. `sector` lo carga el entrevistador: el padrón no lo trae.
COLUMNAS_CABECERA = [
    "id", "legajo", "apenom", "empleador", "base", "cargo", "sector",
    "fecha_ingreso", "fecha_entrevista", "entrevistador",
    "registrado_por", "fecha_registro",
]


def columnas_db():
    """Lista completa de columnas de la tabla, derivada del catálogo.

    Alimenta el `.select(...)` de Supabase; un test la compara contra el DDL
    para que el catálogo y el esquema no se desincronicen sin que nadie lo note.
    """
    cols = list(COLUMNAS_CABECERA)
    cols += [p["cod"] for p in CERRADAS]
    cols += COD_EVAL
    cols += [RESULTADO["cod"]]
    cols += COLUMNAS_TEXTO
    return cols


def codigos_de_dimension(dim):
    """Códigos de las escalas que componen una dimensión."""
    return [p["cod"] for p in ESCALAS if p["dimension"] == dim]


# ─── Padrón ──────────────────────────────────────────────────
def solo_no_conductores(df):
    """El padrón sin los conductores, que tienen su propio cuestionario.

    Mismo criterio que usa conductores para quedarse con ellos (el cargo
    empieza con CONDUCTOR), así nadie queda en los dos ni en ninguno.
    """
    if df is None or "cargo" not in df.columns:
        return df
    es_conductor = df["cargo"].astype(str).str.strip().str.upper() \
        .str.startswith("CONDUCTOR", na=False)
    return df[~es_conductor]


def normalizar_sector(texto):
    """El sector tal como se guarda: mayúsculas, sin tildes ni espacios de más.

    Lo tipea el entrevistador, así que «Administración», «administracion » y
    «ADMINISTRACION» tienen que terminar siendo el mismo sector o el corte por
    sector se parte en tres. Queda con la grafía del padrón (MECANICO, PAÑOLERO):
    se van las tildes y la diéresis, la Ñ se conserva.
    """
    limpio = unicodedata.normalize("NFC", " ".join(str(texto or "").split())).upper()
    # Se parte por la Ñ para que su virgulilla no se vaya con las tildes.
    return "Ñ".join(
        "".join(c for c in unicodedata.normalize("NFD", parte)
                if unicodedata.category(c) != "Mn")
        for parte in limpio.split("Ñ"))


# ─── Codificación de respuestas ──────────────────────────────
def _vacio(valor):
    return valor is None or (not isinstance(valor, (str, bool)) and pd.isna(valor))


def codigo(preg, label):
    """Convierte lo elegido en el formulario al valor que se guarda.

    Escalas: la primera opción (la mejor) vale la cantidad de opciones y la
    última vale 1. Categorías: se guarda la etiqueta. Abiertas: el texto.
    """
    if preg["tipo"] == "abierta":
        return (label or "").strip() or None
    if label is None or label not in preg["opciones"]:
        return None
    if preg["tipo"] == "categoria":
        return label
    return len(preg["opciones"]) - preg["opciones"].index(label)


def etiqueta(preg, valor):
    """Inverso de `codigo`: del valor guardado a la etiqueta legible."""
    if _vacio(valor):
        return ""
    if preg["tipo"] != "escala":
        return str(valor)
    try:
        indice = len(preg["opciones"]) - int(valor)
        if indice < 0:
            return ""
        return preg["opciones"][indice]
    except (IndexError, ValueError, TypeError):
        return ""


def puntos(preg, valor):
    """Puntos (0-100) de una respuesta de escala. NaN si no hay respuesta."""
    if preg["tipo"] != "escala" or _vacio(valor):
        return float("nan")
    try:
        indice = len(preg["opciones"]) - int(valor)
        if indice < 0:
            return float("nan")
        return float(preg["puntos"][indice])
    except (IndexError, ValueError, TypeError):
        return float("nan")


# ─── Índices ─────────────────────────────────────────────────
def _puntajes(df, pregs):
    """Frame con los puntos de cada pregunta de `pregs`; NaN donde no hay respuesta."""
    out = pd.DataFrame(index=df.index)
    for p in pregs:
        if p["cod"] in df.columns:
            out[p["cod"]] = df[p["cod"]].apply(lambda v, p=p: puntos(p, v))
    return out


def _media(pts, cols):
    presentes = [c for c in cols if c in pts.columns]
    if not presentes:
        return pd.Series([float("nan")] * len(pts), index=pts.index)
    return pts[presentes].mean(axis=1, skipna=True)


def calcular_indices(df):
    """Agrega los índices y las alertas a un frame de entrevistas.

    No se guardan en la base: se recalculan siempre, así la fórmula vive en un
    solo lugar.

      · `indice_general`    — lo que dijo el ingresante (las escalas 1-7).
      · `indice_<dimensión>`
      · `indice_evaluacion` — cómo lo evaluó el sector (sección 8). Va aparte:
        es otra voz, y la distancia entre los dos es justamente lo que interesa.
    """
    out = df.copy()
    if out.empty:
        for col in ["indice_general", "indice_evaluacion", "n_items_bajos"]:
            out[col] = pd.Series(dtype="float64")
        for dim in DIMENSIONES:
            out["indice_" + dim] = pd.Series(dtype="float64")
        out["es_alerta"] = pd.Series(dtype="bool")
        out["motivos_alerta"] = pd.Series(dtype="object")
        out["nivel_alerta"] = pd.Series(dtype="object")
        return out

    pts = _puntajes(out, ESCALAS)
    out["indice_general"] = _media(pts, COD_ESCALAS)
    for dim in DIMENSIONES:
        out["indice_" + dim] = _media(pts, codigos_de_dimension(dim))
    out["indice_evaluacion"] = _media(_puntajes(out, EVALUACION), COD_EVAL)
    out["n_items_bajos"] = (pts <= PUNTOS_BAJO).sum(axis=1) if len(pts.columns) else 0

    alertas = [_alertas_fila(fila) for _, fila in out.iterrows()]
    out["motivos_alerta"] = pd.Series(
        [[motivo for motivo, _nivel in a] for a in alertas],
        index=out.index, dtype="object")
    out["es_alerta"] = [bool(a) for a in alertas]
    out["nivel_alerta"] = [
        "Roja" if any(nivel == "Roja" for _m, nivel in a) else "Atención" if a else ""
        for a in alertas
    ]
    return out


def _val(fila, col):
    v = fila.get(col)
    return None if _vacio(v) else v


def _num(fila, col):
    v = _val(fila, col)
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _alertas_fila(fila):
    """[(motivo, nivel)] de una entrevista que ya tiene los índices calculados.

    Rojas: lo que pone en duda la continuidad. Atención: lo que pide una acción
    pero no la frena.
    """
    alertas = []
    resultado = _val(fila, RESULTADO["cod"])

    if resultado == RESULTADO_NO_CONTINUAR:
        alertas.append(("No se recomienda la continuidad", "Roja"))
    if _num(fila, COD_CONTINUAR) == 1:
        alertas.append(("No quiere continuar en la empresa", "Roja"))
    insuficientes = [e["corto"] for e in EVALUACION if _num(fila, e["cod"]) == 1]
    if insuficientes:
        alertas.append(("Evaluación del sector insuficiente: "
                        + ", ".join(insuficientes), "Roja"))

    if resultado == RESULTADO_PLAN_MEJORA:
        alertas.append(("Requiere plan de mejora o capacitación", "Atención"))
    if _num(fila, COD_CONFORMIDAD) == 1:
        alertas.append(("Poco conforme trabajando en la empresa", "Atención"))
    indice = _num(fila, "indice_general")
    if indice is not None and indice < 50:
        alertas.append(("Índice general por debajo de 50", "Atención"))
    bajos = _num(fila, "n_items_bajos")
    if bajos is not None and bajos >= 3:
        alertas.append(("3 o más respuestas en la opción más baja", "Atención"))
    return alertas


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
def distribucion_items(df, pregs=None):
    """Frame largo con la distribución de respuestas de cada escala.

    Columnas: cod, rotulo, corto, texto, valor, etiqueta, puntos, n, pct,
    indice, total. Ordenado por índice ascendente: lo peor puntuado primero.
    `pregs` es ESCALAS por defecto; con EVALUACION da la del sector.
    """
    pregs = ESCALAS if pregs is None else pregs
    filas = []
    for p in pregs:
        cod = p["cod"]
        if cod not in df.columns:
            continue
        serie = pd.to_numeric(df[cod], errors="coerce").dropna()
        if serie.empty:
            continue
        total = len(serie)
        indice = serie.apply(lambda v, p=p: puntos(p, v)).mean()
        cantidad = len(p["opciones"])
        for valor in range(1, cantidad + 1):
            n = int((serie == valor).sum())
            filas.append({
                "cod": cod,
                "rotulo": f"{p.get('n') or p.get('letra')}. {p['corto']}",
                "corto": p["corto"],
                "texto": p["texto"],
                "valor": valor,
                "etiqueta": p["opciones"][cantidad - valor],
                "puntos": float(p["puntos"][cantidad - valor]),
                "n": n,
                "pct": (n / total * 100.0) if total else 0.0,
                "indice": indice,
                "total": total,
            })
    out = pd.DataFrame(filas)
    if not out.empty:
        out = out.sort_values(["indice", "cod", "valor"])
    return out


def resumen_dimensiones(df):
    """Índice por dimensión, con el n de ítems y de casos."""
    filas = []
    for dim, nombre in DIMENSIONES.items():
        col = "indice_" + dim
        serie = (pd.to_numeric(df[col], errors="coerce").dropna()
                 if col in df.columns else pd.Series(dtype="float64"))
        filas.append({
            "clave": dim,
            "nombre": nombre,
            "n_items": len(codigos_de_dimension(dim)),
            "n_casos": int(len(serie)),
            "indice": float(serie.mean()) if len(serie) else float("nan"),
        })
    return pd.DataFrame(filas)


def frecuencia_categoria(df, cod):
    """Frecuencia de las opciones de una categoría, en el orden del catálogo.

    A diferencia de conductores no se ordena por cantidad: acá las opciones
    tienen un orden propio (Sí · Parcialmente · No, o de continuar a no
    continuar) y mezclarlas lo esconde. Las que nadie eligió salen en 0.
    """
    p = POR_COD.get(cod)
    vacio = pd.DataFrame(columns=["categoria", "n", "pct"])
    if p is None or p["tipo"] != "categoria" or cod not in df.columns:
        return vacio
    serie = df[cod].dropna().astype(str).str.strip()
    serie = serie[serie.isin(p["opciones"])]
    if serie.empty:
        return vacio
    total = len(serie)
    conteo = serie.value_counts()
    out = pd.DataFrame({
        "categoria": list(p["opciones"]),
        "n": [int(conteo.get(o, 0)) for o in p["opciones"]],
    })
    out["pct"] = out["n"] / total * 100.0
    return out


def corte_por_sector(df, min_n=MIN_N_CORTE):
    """Índice general y evaluación por sector. Devuelve (tabla, sectores
    excluidos por tener menos de `min_n` entrevistas)."""
    cols = ["sector", "n", "indice", "evaluacion"]
    if df.empty or "sector" not in df.columns:
        return pd.DataFrame(columns=cols), []
    tmp = df.copy()
    tmp["sector"] = tmp["sector"].fillna("").astype(str).str.strip().replace("", "Sin sector")
    for col in ("indice_general", "indice_evaluacion"):
        if col not in tmp.columns:
            tmp[col] = float("nan")
    agrupado = tmp.groupby("sector").agg(
        n=("sector", "size"),
        indice=("indice_general", "mean"),
        evaluacion=("indice_evaluacion", "mean"),
    ).reset_index()
    excluidos = agrupado[agrupado["n"] < min_n]["sector"].tolist()
    incluidos = agrupado[agrupado["n"] >= min_n].sort_values("indice")
    return incluidos[cols].reset_index(drop=True), sorted(excluidos)


def resumen_kpis(df):
    """Los 6 números de las tarjetas KPI."""
    n = int(len(df))
    kpis = {
        "entrevistas": n,
        "indice_general": float("nan"),
        "evaluacion": float("nan"),
        "quieren_continuar": float("nan"),
        "continuidad": float("nan"),
        "alertas": 0,
        "pct_alertas": float("nan"),
    }
    if n == 0:
        return kpis

    for clave, col in (("indice_general", "indice_general"),
                       ("evaluacion", "indice_evaluacion")):
        if col in df.columns:
            serie = pd.to_numeric(df[col], errors="coerce").dropna()
            kpis[clave] = float(serie.mean()) if len(serie) else float("nan")

    if COD_CONTINUAR in df.columns:
        serie = pd.to_numeric(df[COD_CONTINUAR], errors="coerce").dropna()
        if len(serie):
            mejor = len(POR_COD[COD_CONTINUAR]["opciones"])     # «Sí»
            kpis["quieren_continuar"] = float((serie == mejor).sum()) / len(serie) * 100.0

    if RESULTADO["cod"] in df.columns:
        serie = df[RESULTADO["cod"]].dropna()
        serie = serie[serie.isin(RESULTADOS)]
        if len(serie):
            kpis["continuidad"] = (float(serie.isin(RESULTADOS_CONTINUIDAD).sum())
                                   / len(serie) * 100.0)

    if "es_alerta" in df.columns:
        kpis["alertas"] = int(df["es_alerta"].sum())
        kpis["pct_alertas"] = kpis["alertas"] / n * 100.0
    return kpis


# ─── Detalle de una entrevista ───────────────────────────────
def color_puntos(pts):
    """Color de una respuesta según sus puntos: la misma paleta de 4 niveles de
    conductores (100 verde · 67 celeste · 33 a 50 ámbar · 0 rojo)."""
    if pts is None or pd.isna(pts):
        return COLOR_BUENO
    if pts >= 99:
        return COLOR_MUY_BUENO
    if pts >= 60:
        return COLOR_SECUNDARIO
    if pts >= 30:
        return COLOR_MEJORAR
    return COLOR_CRITICO


def color_respuesta(preg, valor):
    """Color del chip de una respuesta."""
    if _vacio(valor):
        return COLOR_BUENO
    if preg["cod"] == RESULTADO["cod"]:
        return COLOR_RESULTADO.get(str(valor), COLOR_BUENO)
    if preg["tipo"] != "escala":
        return COLOR_BUENO          # las categorías describen, no puntúan
    return color_puntos(puntos(preg, valor))


def _item(etiqueta_item, pregunta, respuesta="", color=COLOR_BUENO,
          textual="", observacion=""):
    return {"etiqueta": etiqueta_item, "pregunta": pregunta, "respuesta": respuesta,
            "color": color, "textual": textual, "observacion": observacion}


def _texto(fila, col):
    v = _val(fila, col)
    return str(v).strip() if v is not None else ""


def detalle_entrevista(fila, incluir_textos=True):
    """Estructura una entrevista para mostrarla en pantalla.

    Devuelve [(titulo_seccion, [item, ...])] con la misma forma de ítem que usa
    conductores, así la pantalla los dibuja igual. `incluir_textos=False` omite
    todo el texto libre — es la puerta de confidencialidad para quien no tiene
    permiso de carga.
    """
    secciones = []

    for num, nombre in SECCIONES.items():
        items = []
        for preg in [q for q in PREGUNTAS if q["seccion"] == num]:
            valor = _val(fila, preg["cod"])
            if preg["tipo"] == "abierta":
                # Con permiso se lee la respuesta; sin permiso se sabe si
                # contestó, no qué.
                texto = _texto(fila, preg["cod"])
                if incluir_textos and texto:
                    items.append(_item(str(preg["n"]), preg["texto"], textual=texto))
                else:
                    items.append(_item(
                        str(preg["n"]), preg["texto"],
                        respuesta="Respondida" if texto else "Sin responder"))
                continue
            textual = ""
            if incluir_textos and "texto_label" in preg:
                textual = _texto(fila, preg["cod"] + "_texto")
            items.append(_item(
                str(preg["n"]), preg["texto"],
                respuesta=etiqueta(preg, valor) or "Sin responder",
                color=color_respuesta(preg, valor), textual=textual))
        if incluir_textos:
            obs = _texto(fila, OBS_SECCION[num])
            if obs:
                items.append(_item("", "", observacion=obs))
        secciones.append((f"{num}. {nombre.upper()}", items))

    items = []
    for e in EVALUACION:
        valor = _val(fila, e["cod"])
        items.append(_item(e["letra"], e["texto"],
                           respuesta=etiqueta(e, valor) or "Sin responder",
                           color=color_respuesta(e, valor)))
    if incluir_textos:
        obs = _texto(fila, OBS_EVALUACION)
        if obs:
            items.append(_item("", "", observacion=obs))
    secciones.append((f"{N_SECCION_EVALUACION}. {TITULO_EVALUACION.upper()}", items))

    resultado = _val(fila, RESULTADO["cod"])
    items = [_item("", "Resultado",
                   respuesta=etiqueta(RESULTADO, resultado) or "Sin responder",
                   color=color_respuesta(RESULTADO, resultado))]
    if incluir_textos:
        obs = _texto(fila, OBS_FINALES)
        if obs:
            items.append(_item("", "Observaciones finales", observacion=obs))
    secciones.append((f"{N_SECCION_RESULTADO}. {TITULO_RESULTADO.upper()}", items))

    return secciones


# ─── Exportación ─────────────────────────────────────────────
ETIQUETAS_EXPORT = {
    "legajo": "Legajo", "apenom": "Nombre", "empleador": "Empleador",
    "base": "Base", "cargo": "Puesto", "sector": "Sector",
    "fecha_ingreso": "Fecha de ingreso", "fecha_entrevista": "Fecha de entrevista",
    "entrevistador": "Entrevistador", "registrado_por": "Registrado por",
    "indice_general": "Índice general",
    "indice_evaluacion": "Evaluación del sector (índice)",
    OBS_EVALUACION: f"{N_SECCION_EVALUACION}. {TITULO_EVALUACION} — observaciones",
    OBS_FINALES: "Observaciones finales",
}


def preparar_export(df, incluir_textos):
    """Frame legible para Excel: etiquetas en vez de códigos.

    `incluir_textos=False` deja fuera todas las columnas de texto libre — es la
    puerta de confidencialidad para quien no tiene permiso de carga.
    """
    if df.empty:
        return pd.DataFrame()

    out = pd.DataFrame(index=df.index)
    for col in ["legajo", "apenom", "empleador", "base", "cargo", "sector",
                "fecha_ingreso", "fecha_entrevista", "entrevistador", "registrado_por"]:
        if col in df.columns:
            out[ETIQUETAS_EXPORT[col]] = df[col]

    for col in ["indice_general", "indice_evaluacion"]:
        if col in df.columns:
            out[ETIQUETAS_EXPORT[col]] = pd.to_numeric(df[col], errors="coerce").round(1)
    if RESULTADO["cod"] in df.columns:
        out["Resultado"] = df[RESULTADO["cod"]]
    if "nivel_alerta" in df.columns:
        out["Alerta"] = df["nivel_alerta"]
    if "motivos_alerta" in df.columns:
        out["Motivos de alerta"] = df["motivos_alerta"].apply(
            lambda m: " · ".join(m) if isinstance(m, list) else "")

    for p in CERRADAS:
        cod = p["cod"]
        if cod not in df.columns:
            continue
        out[f"{p['n']}. {p['corto']}"] = df[cod].apply(lambda v, p=p: etiqueta(p, v))
        if p["tipo"] == "escala":
            out[f"{p['n']}. {p['corto']} (pts.)"] = df[cod].apply(
                lambda v, p=p: puntos(p, v)).round(1)

    for e in EVALUACION:
        if e["cod"] in df.columns:
            out[f"Evaluación del sector {e['letra']}. {e['corto']}"] = df[e["cod"]].apply(
                lambda v, e=e: etiqueta(e, v))

    if incluir_textos:
        for p in PREGUNTAS:
            if p["tipo"] == "abierta" and p["cod"] in df.columns:
                out[f"{p['n']}. {p['corto']}"] = df[p["cod"]]
            col = p["cod"] + "_texto"
            if "texto_label" in p and col in df.columns:
                out[f"{p['n']}. {p['corto']} — detalle"] = df[col]
        for num, col in OBS_SECCION.items():
            if col in df.columns:
                out[f"{num}. {SECCIONES[num]} — observaciones"] = df[col]
        for col in (OBS_EVALUACION, OBS_FINALES):
            if col in df.columns:
                out[ETIQUETAS_EXPORT[col]] = df[col]

    return out.apply(lambda col: col.map(_limpiar_celda))


def exportar_excel(df, incluir_textos):
    """Bytes de un .xlsx con una hoja 'Entrevistas'."""
    datos = preparar_export(df, incluir_textos)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        if datos.empty:
            pd.DataFrame({"Sin datos": []}).to_excel(
                writer, sheet_name="Entrevistas", index=False)
        else:
            datos.to_excel(writer, sheet_name="Entrevistas", index=False)
    return buffer.getvalue()
