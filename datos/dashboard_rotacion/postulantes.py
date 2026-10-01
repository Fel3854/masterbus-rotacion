"""Postulantes — consulta del registro de entrevistas a postulantes (FORM 045 02).

Módulo de lógica pura: NO importa Streamlit, así que se testea con pytest sin
levantar la app (mismo criterio que `minutas.py` y `seguimiento.py`). Las dos
funciones que tocan la base reciben el cliente de Supabase por parámetro.

El registro se sigue cargando en Access; acá sólo se consulta. La tabla guarda
cada dato TAL CUAL viene, con sus errores de tipeo, y todo lo que ordena la
consulta —familia de puesto, sector, entrevistador unificado, veces que se
presentó— se deriva en pandas y no se guarda. Así las reglas viven en un solo
lugar y corregir una no deja filas viejas con un valor de otra época.

Sobre la casilla «Apto para ingresar»: sólo dice algo cuando está tildada. Desde
2023 casi no se usa (en 2025 se tildó el 2 % de las entrevistas, aunque buena
parte dice «OK PREOCU» en las notas), así que una casilla sin tildar significa
"sin marcar", NO "rechazado". Por eso este módulo nunca produce un "No apto" ni
una tasa de rechazo: serían números falsos con cara de dato.
"""

from __future__ import annotations

import difflib
import os
import re
import tempfile
import types
import unicodedata
from datetime import date, datetime, timezone
from io import BytesIO

import pandas as pd

from paginado import leer_paginado

TABLA = "entrevistas_postulantes"

# (columna interna, encabezado original de Access). El orden es el del
# formulario: es el que se usa para leer el archivo y para exportar.
CAMPOS = [
    ("entrevistador",  "Entrevistador"),
    ("fecha",          "Fecha"),
    ("numero_orden",   "Número de orden"),
    ("apellido",       "Apellido"),
    ("nombres",        "Nombres"),
    ("dni",            "DNI"),
    ("puesto",         "Puesto al que se postula"),
    ("sector",         "Sector"),
    ("apto",           "Apto para ingresar"),
    ("motivo_rechazo", "Motivos del rechazo"),
    ("observaciones",  "Observaciones del entrevistador"),
]
COLUMNAS_FORM = [c for c, _e in CAMPOS]
ENCABEZADO = dict(CAMPOS)
COLUMNAS_TEXTO = ["entrevistador", "apellido", "nombres", "puesto", "sector",
                  "motivo_rechazo", "observaciones"]
# Lo que se compara para saber si una entrevista cambió en Access.
COLUMNAS_DATO = [c for c in COLUMNAS_FORM if c != "numero_orden"]

COLUMNAS_DB = [
    "numero_orden", "entrevistador", "fecha", "apellido", "nombres", "dni",
    "puesto", "sector", "apto", "motivo_rechazo", "observaciones",
    "importado_por", "fecha_importacion", "fecha_actualizacion",
]

EXTENSIONES = ("mdb", "xlsx", "csv")

# PostgREST corta cada respuesta en 1000 filas: la lectura va paginada.
PAGINA_LECTURA = 1000
LOTE_UPSERT = 500

# Si una actualización pisa más que esta proporción de lo ya cargado, lo más
# probable es que el archivo esté mal leído o no sea la base correcta.
UMBRAL_CAMBIO_MASIVO = 0.20


class ArchivoInvalido(Exception):
    """El archivo subido no sirve para actualizar. El mensaje va a la pantalla."""


# ─── Texto ───────────────────────────────────────────────────
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_ENIE = "\x00"


def _vacio(v) -> bool:
    """True para None, NaN, NaT y cadenas vacías o de sólo espacios."""
    if v is None:
        return True
    if isinstance(v, str):
        return not v.strip()
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def norm(s, conservar_enie=False) -> str:
    """Mayúsculas, sin tildes y con los espacios colapsados.

    Es la forma en que se comparan los textos: «Tráfico», «TRAFICO» y
    « trafico » son lo mismo. Por defecto la Ñ pasa a N, para que buscar
    «nunez» encuentre «NUÑEZ»; `conservar_enie` la deja, para lo que se muestra.
    """
    if _vacio(s):
        return ""
    t = str(s).upper()
    if conservar_enie:
        t = t.replace("Ñ", _ENIE)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    if conservar_enie:
        t = t.replace(_ENIE, "Ñ")
    return re.sub(r"\s+", " ", t).strip()


# ─── Familias de puesto ──────────────────────────────────────
# El puesto es texto libre: hay 161 formas de escribirlo y sólo para «conductor»
# conviven CHOFER, CONDUCTOR, CONDUCTORA, CONDCUTOR, CONUCTOR, CHOFER JUJUY…
# La familia agrupa esas variantes para poder filtrar. Es una ayuda para buscar,
# no una clasificación oficial: en pantalla siempre se ve el puesto original.
GRUPO_CONDUCTOR   = "Conductor"
GRUPO_SUPERVISION = "Supervisión y operación"
GRUPO_ADMIN       = "Administración"
GRUPO_TALLER      = "Taller"
GRUPO_MAESTRANZA  = "Maestranza y lavadero"
GRUPO_CELADORA    = "Celadora"
GRUPO_SISTEMAS    = "Sistemas / IoT"
GRUPO_PASANTIA    = "Pasantías"
GRUPO_OTROS       = "Otros"
GRUPO_SIN_DATO    = "Sin dato"

# El orden importa: gana la primera regla que coincide. Supervisión va antes que
# Taller y Maestranza para que «SUP MECANICO» o «SUP LAVADERO» caigan en
# supervisión; Administración va antes que Taller por «ADM TALLER».
_PATRONES_PUESTO = [
    (GRUPO_CONDUCTOR,   r"CHOFER|CONDUC|CONDCU|CONCUT|CONUCT"),
    (GRUPO_SUPERVISION, r"^SUP|JEFE|COOR|RESP|LIDER|OPERADOR|OPERATIVO|^OP DE|^TRAFICO$"),
    (GRUPO_ADMIN,       r"^ADM|RECEP|LIQ|CUENTAS|COMPRAS|RRHH|^ASIST|^AUX|VENTA|"
                        r"VENDEDOR|RADIO|RECLAMOS|PROMOTOR|ANALISTA|GESTORIA|"
                        r"SEG VIAL|SEG E HIG"),
    (GRUPO_TALLER,      r"MECANIC|ELECTR|CHAP|CARROCER|PANOL|ALMACEN|OFICIAL|"
                        r"^M OF |^TALLER$"),
    (GRUPO_MAESTRANZA,  r"MAESTRAN|MAESTAN|LAV[AE][DV]|MANTEN|PREDIO|TAREAS GRALES"),
    (GRUPO_CELADORA,    r"CELAD"),
    (GRUPO_SISTEMAS,    r"IOT|\bIT\b|SOPORTE|DESARROLLO|SISTEMA"),
    (GRUPO_PASANTIA,    r"PASANT|PRACTICAS"),
]
_REGLAS_PUESTO = [(g, re.compile(p)) for g, p in _PATRONES_PUESTO]

GRUPOS_PUESTO = [g for g, _p in _REGLAS_PUESTO] + [GRUPO_OTROS, GRUPO_SIN_DATO]


def grupo_puesto(puesto) -> str:
    """Familia del puesto. «Otros» si no coincide ninguna regla."""
    p = norm(puesto)
    if not p:
        return GRUPO_SIN_DATO
    for grupo, patron in _REGLAS_PUESTO:
        if patron.search(p):
            return grupo
    return GRUPO_OTROS


# ─── Sector ──────────────────────────────────────────────────
# Variantes de tipeo del mismo sector o base. Son nombres de áreas y lugares,
# no de personas, así que pueden vivir en el código.
_ALIAS_SECTOR = {
    "A MATANZA": "LA MATANZA",
    "OLAVARIA": "OLAVARRIA",
    "RR.HH": "RRHH",
    "MASTERBUS": "MASTER BUS",
    "COMODORO": "COMODORO RIVADAVIA",
    "COMODORO RIV": "COMODORO RIVADAVIA",
    "PERITO": "PERITO MORENO",
    "PANOL": "PAÑOL",
}


def normalizar_sector(sector) -> str:
    """Sector comparable: «Tráfico», «TRAFICO» y «trafico» → «TRAFICO»."""
    s = norm(sector, conservar_enie=True)
    return _ALIAS_SECTOR.get(s, s)


# ─── Entrevistador ───────────────────────────────────────────
def unificar_entrevistadores(serie, corte=0.8) -> pd.Series:
    """Junta las variantes de tipeo de un mismo entrevistador.

    El campo es texto libre y el mismo nombre aparece con letras de más, con
    una letra cambiada o con el apellido adelante. En vez de una lista de
    nombres propios en el código —que además habría que mantener a mano—, las
    variantes se agrupan por parecido:

      1. Se ordenan las palabras, así «Pérez Juan» y «Juan Pérez» coinciden.
      2. Se recorren de la más usada a la menos usada. Cada una se suma al
         grupo de una ya vista si se le parece lo suficiente; si no, abre grupo.

    Cada grupo se muestra con su grafía más frecuente. Devuelve una Series
    alineada con la de entrada; los vacíos quedan en "".
    """
    crudos = serie.map(lambda v: "" if _vacio(v) else str(v).strip())
    clave = crudos.map(lambda s: " ".join(sorted(norm(s).split())))

    conteo = clave[clave != ""].value_counts()
    # Empates resueltos por orden alfabético: el resultado no depende del
    # orden en que vengan las filas.
    orden = sorted(conteo.index, key=lambda k: (-conteo[k], k))

    lideres: list = []
    destino = {"": ""}
    for k in orden:
        parecidos = difflib.get_close_matches(k, lideres, n=1, cutoff=corte)
        if parecidos:
            destino[k] = parecidos[0]
        else:
            lideres.append(k)
            destino[k] = k
    grupo = clave.map(destino)

    etiqueta = {"": ""}
    usados = pd.DataFrame({"grupo": grupo, "crudo": crudos})
    for g, parte in usados[usados["grupo"] != ""].groupby("grupo"):
        frecuencia = parte["crudo"].value_counts()
        etiqueta[g] = sorted(frecuencia.index, key=lambda c: (-frecuencia[c], c))[0]
    return grupo.map(etiqueta)


# ─── Fechas ──────────────────────────────────────────────────
def to_date(v):
    """Coerciona str / date / datetime / Timestamp a `date`, o None.

    `pd.NaT` es instancia de `date`, así que un `isinstance` solo no alcanza
    para descartar una fecha vacía (ver el mismo aviso en `minutas.to_date`).
    """
    if _vacio(v):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    ts = pd.to_datetime(v, errors="coerce")
    return None if pd.isna(ts) else ts.date()


# ─── Valores canónicos ───────────────────────────────────────
# El archivo de Access y la base se comparan campo por campo para saber qué
# cambió. Para que «11222333.0» y 11222333, o «Tráfico » y «Tráfico», no
# cuenten como cambio, los dos lados pasan por estas mismas funciones.
ANIO_MINIMO = 1990
_VERDADEROS = {"TRUE", "VERDADERO", "SI", "S", "YES", "Y", "1", "-1", "X"}


def canon_texto(v):
    """Texto sin espacios en los bordes ni caracteres de control; None si vacío."""
    if _vacio(v):
        return None
    s = _CTRL.sub("", str(v)).strip()
    return s or None


def canon_dni(v):
    """Entero positivo o None. El 0 de Access es "sin dato", no un DNI."""
    if _vacio(v) or isinstance(v, bool):
        return None
    if isinstance(v, str):
        s = v.strip()
        if re.fullmatch(r"\d+\.0+", s):          # «11222333.0»
            s = s.split(".")[0]
        s = re.sub(r"[.\s]", "", s)              # «11.222.333»
        if not s.isdigit():
            return None
        n = int(s)
    else:
        try:
            n = int(v)
        except (TypeError, ValueError, OverflowError):
            return None
    return n if n > 0 else None


def canon_fecha(v):
    """'AAAA-MM-DD' o None.

    Access guarda la fecha vacía como su fecha cero (30/12/1899), que exportada
    aparece como «1900-01-00»: todo lo anterior a 1990 se toma como vacío.
    """
    if _vacio(v):
        return None
    if isinstance(v, datetime):
        d = v.date()
    elif isinstance(v, date):
        d = v
    else:
        s = str(v).strip()
        # Con barras es el formato regional de Access (día primero).
        dia_primero = bool(re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}", s))
        ts = pd.to_datetime(s, errors="coerce", dayfirst=dia_primero)
        if pd.isna(ts):
            return None
        d = ts.date()
    return d.isoformat() if d.year >= ANIO_MINIMO else None


def canon_apto(v) -> bool:
    """La casilla, venga como venga: True/False, -1/0, «Sí», «VERDADERO»…"""
    if isinstance(v, bool):
        return v
    if _vacio(v):
        return False
    if isinstance(v, (int, float)):
        return v != 0
    return norm(v) in _VERDADEROS


def canon_orden(v):
    """Número de orden como entero positivo, o None."""
    if _vacio(v) or isinstance(v, bool):
        return None
    try:
        n = int(float(str(v).strip()))
    except (TypeError, ValueError, OverflowError):
        return None
    return n if n > 0 else None


_CANON = {
    "numero_orden": canon_orden, "fecha": canon_fecha, "dni": canon_dni,
    "apto": canon_apto,
}
for _c in COLUMNAS_TEXTO:
    _CANON[_c] = canon_texto


def _canonizar(df, origen) -> pd.DataFrame:
    """Frame con COLUMNAS_FORM en valores canónicos (tipos nativos de Python).

    `origen` dice de qué columna de `df` sale cada columna interna. Se arma con
    listas y dtype=object a propósito: si pandas infiere el tipo, un DNI entero
    junto a un None se vuelve float con NaN y deja de comparar igual.
    """
    datos = {c: [_CANON[c](v) for v in df[origen[c]].tolist()] for c in COLUMNAS_FORM}
    return pd.DataFrame(datos, columns=COLUMNAS_FORM, dtype=object)


def canonizar_base(df) -> pd.DataFrame:
    """Lo que hay en la base, en los mismos valores canónicos que el archivo."""
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=COLUMNAS_FORM, dtype=object)
    return _canonizar(df, {c: c for c in COLUMNAS_FORM})


# ─── Lectura del archivo de Access ───────────────────────────
def _columnas_fijas_tolerantes(self, original_record, column, null_table):
    """Corrección 1 a access-parser: una fecha con bytes inválidos es un vacío.

    La librería revienta con ValueError cuando el campo fecha no contiene una
    fecha (pasa con registros a medio cargar). Acá se convierte en None.
    """
    try:
        type(self)._parse_fixed_length_data(self, original_record, column, null_table)
    except (ValueError, OverflowError):
        self.parsed_table[column.col_name_str].append(None)


def _columnas_variables_por_slot(self, original_record, meta, col_map, null_table):
    """Corrección 2 a access-parser: cada texto se lee de SU posición.

    La librería toma la i-ésima posición para la i-ésima columna de texto. Eso
    sólo es cierto si a la tabla nunca se le borró una columna: a ésta sí, y el
    resultado sale con todos los textos corridos un lugar (el apellido en la
    columna Nombres, el sector en Motivos…) y sin las observaciones. Cada
    columna declara cuál es su posición real en `variable_column_number`.
    """
    from access_parser.access_parser import parse_type

    posiciones = meta.variable_length_field_offsets
    for indice in col_map:
        columna = col_map[indice]
        nombre = columna.col_name_str
        tiene_valor = True
        if columna.column_id <= len(null_table):
            tiene_valor = null_table[columna.column_id]
        slot = columna.variable_column_number
        if not tiene_valor or slot >= len(posiciones):
            self.parsed_table[nombre].append(None)
            continue
        inicio = posiciones[slot]
        fin = meta.var_len_count if slot + 1 == len(posiciones) else posiciones[slot + 1]
        if inicio == fin:
            self.parsed_table[nombre].append("")
            continue
        dato = original_record[inicio:fin]
        self.parsed_table[nombre].append(
            parse_type(columna.type, dato, len(dato), version=self.version))


def _leer_mdb(ruta) -> pd.DataFrame:
    """La tabla de entrevistas de un .mdb, con los encabezados de Access.

    Usa `access-parser` (Python puro) con dos correcciones aplicadas sólo al
    objeto de esta tabla, sin tocar la librería. Verificado contra el archivo
    real: 0 diferencias en las 2.835 filas respecto del export de referencia.
    La versión está fijada en requirements.txt porque las correcciones pisan
    métodos internos.
    """
    try:
        import logging

        from access_parser import AccessParser
    except ImportError as e:
        raise ArchivoInvalido(
            "Este servidor no puede leer archivos .mdb. Exportá la tabla a "
            "Excel desde Access y subí ese archivo.") from e

    # La librería avisa por log cada registro que le resulta raro: es ruido.
    logging.getLogger("access_parser").setLevel(logging.CRITICAL)

    try:
        base = AccessParser(ruta)
    except Exception as e:  # noqa: BLE001 — cualquier falla es "no es un Access válido"
        raise ArchivoInvalido(
            "No se pudo abrir el archivo: no parece una base de Access válida.") from e

    if getattr(base, "version", 3) <= 3:
        raise ArchivoInvalido(
            "La base es de una versión de Access muy vieja para leerla directo. "
            "Exportá la tabla a Excel y subí ese archivo.")

    esperados = {norm(e) for _c, e in CAMPOS}
    tabla = None
    for nombre in base.catalog:
        if nombre.startswith("MSys"):
            continue
        candidata = base.get_table(nombre)
        if candidata is None:
            continue
        columnas = {norm(c.col_name_str) for c in candidata.columns.values()}
        if esperados <= columnas:
            tabla = candidata
            break
    if tabla is None:
        raise ArchivoInvalido(
            "La base de Access no tiene la tabla de entrevistas (no se encontró "
            "ninguna con las columnas del FORM 045 02).")

    tabla._parse_fixed_length_data = types.MethodType(_columnas_fijas_tolerantes, tabla)
    tabla._parse_dynamic_length_data = types.MethodType(_columnas_variables_por_slot, tabla)
    try:
        datos = tabla.parse()
    except Exception as e:  # noqa: BLE001
        raise ArchivoInvalido(
            "No se pudo leer la tabla de entrevistas del archivo de Access. "
            "Exportala a Excel y subí ese archivo.") from e

    # Si un registro falla a mitad de camino, las columnas quedan con distinta
    # cantidad de filas: mejor cortar que cargar datos desalineados.
    largos = {len(v) for v in datos.values()}
    if len(largos) != 1:
        raise ArchivoInvalido(
            "El archivo de Access se leyó incompleto (las columnas no tienen la "
            "misma cantidad de filas). Exportá la tabla a Excel y subí ese archivo.")
    return pd.DataFrame(dict(datos))


def _leer_csv(contenido) -> pd.DataFrame:
    # utf-8 primero; cp1252 es lo que escribe Access al exportar texto.
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            return pd.read_csv(BytesIO(contenido), sep=None, engine="python",
                               dtype=str, keep_default_na=False,
                               encoding=codificacion)
        except UnicodeDecodeError:
            continue
        except Exception as e:  # noqa: BLE001
            raise ArchivoInvalido(f"No se pudo leer el CSV: {e}") from e
    raise ArchivoInvalido("No se pudo leer el CSV: codificación desconocida.")


def leer_archivo(nombre, contenido) -> pd.DataFrame:
    """Archivo subido (.mdb, .xlsx o .csv) → tabla cruda con los encabezados originales."""
    extension = (nombre or "").lower().rsplit(".", 1)[-1]
    if extension not in EXTENSIONES:
        raise ArchivoInvalido(
            "Formato no soportado. Subí el .mdb de Access, o la tabla exportada "
            "a Excel (.xlsx) o a CSV.")
    if not contenido:
        raise ArchivoInvalido("El archivo está vacío.")

    if extension == "csv":
        return _leer_csv(contenido)
    if extension == "xlsx":
        try:
            return pd.read_excel(BytesIO(contenido), dtype=object)
        except Exception as e:  # noqa: BLE001
            raise ArchivoInvalido(f"No se pudo leer el Excel: {e}") from e

    # .mdb: la librería sólo abre rutas, así que pasa por un temporal que se
    # borra apenas termina (tiene datos personales).
    ruta = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mdb", delete=False) as tmp:
            tmp.write(contenido)
            ruta = tmp.name
        return _leer_mdb(ruta)
    finally:
        if ruta and os.path.exists(ruta):
            os.unlink(ruta)


def normalizar_archivo(crudo) -> pd.DataFrame:
    """Tabla cruda → COLUMNAS_FORM en valores canónicos, ordenada por número.

    Los encabezados se reconocen sin importar mayúsculas ni tildes. Lanza
    `ArchivoInvalido` si faltan columnas, si hay filas con datos pero sin
    número de orden, o si un número se repite: en los tres casos no hay forma
    segura de saber a qué entrevista corresponde cada fila.
    """
    if crudo is None or len(crudo) == 0:
        raise ArchivoInvalido("El archivo no tiene filas.")

    por_norma = {norm(c): c for c in crudo.columns}
    faltan = [e for _c, e in CAMPOS if norm(e) not in por_norma]
    if faltan:
        raise ArchivoInvalido(
            "Al archivo le faltan columnas: " + ", ".join(faltan) + ". "
            "Tiene que ser la tabla de entrevistas completa, con los "
            "encabezados de Access.")

    out = _canonizar(crudo, {c: por_norma[norm(e)] for c, e in CAMPOS})

    # Filas totalmente vacías (renglones en blanco al final de un Excel).
    con_algo = out[COLUMNAS_TEXTO + ["fecha", "dni", "numero_orden"]].notna().any(axis=1) \
        | out["apto"].map(bool)
    out = out[con_algo]

    sin_numero = int(out["numero_orden"].isna().sum())
    if sin_numero:
        raise ArchivoInvalido(
            f"Hay {sin_numero} fila(s) con datos pero sin «Número de orden»: "
            "no se puede saber a qué entrevista corresponden.")
    if out.empty:
        raise ArchivoInvalido("El archivo no tiene entrevistas.")

    repetidos = out["numero_orden"][out["numero_orden"].duplicated()].tolist()
    if repetidos:
        muestra = ", ".join(str(n) for n in sorted(set(repetidos))[:10])
        raise ArchivoInvalido(
            f"El «Número de orden» se repite en el archivo ({muestra}): "
            "tiene que ser único.")

    return out.sort_values("numero_orden").reset_index(drop=True)


# ─── Qué cambia al actualizar ────────────────────────────────
def plan_de_carga(archivo, base) -> dict:
    """Compara el archivo (ya normalizado) contra lo que hay en la base.

    Devuelve:
      · nuevas       entrevistas que no estaban.
      · modificadas  las que cambiaron en Access; cada una trae `cambios`, una
                     lista de (campo, valor en la base, valor en el archivo).
      · sin_cambios  cuántas están idénticas (no se tocan).
      · faltantes    las que están en la base y NO en el archivo. No se borran:
                     son la señal de que el archivo es una copia vieja.
    Repetir la carga de un mismo archivo da 0 nuevas y 0 modificadas.
    """
    en_archivo = {f["numero_orden"]: f for f in archivo[COLUMNAS_FORM].to_dict("records")}
    en_base = {f["numero_orden"]: f
               for f in canonizar_base(base)[COLUMNAS_FORM].to_dict("records")}

    nuevas, modificadas, sin_cambios = [], [], 0
    for numero, fila in en_archivo.items():
        actual = en_base.get(numero)
        if actual is None:
            nuevas.append(fila)
            continue
        cambios = [(c, actual[c], fila[c]) for c in COLUMNAS_DATO if actual[c] != fila[c]]
        if cambios:
            modificadas.append(dict(fila, cambios=cambios))
        else:
            sin_cambios += 1
    faltantes = [f for n, f in en_base.items() if n not in en_archivo]

    return {
        "nuevas": pd.DataFrame(nuevas, columns=COLUMNAS_FORM, dtype=object),
        "modificadas": pd.DataFrame(modificadas, columns=COLUMNAS_FORM + ["cambios"],
                                    dtype=object),
        "sin_cambios": sin_cambios,
        "faltantes": pd.DataFrame(faltantes, columns=COLUMNAS_FORM, dtype=object),
        "en_base": len(en_base),
        "en_archivo": len(en_archivo),
    }


def advertencias_de_carga(plan) -> list:
    """Motivos para desconfiar del archivo antes de confirmar la carga.

    Lista de textos; vacía si no hay nada raro. La pantalla exige una
    confirmación explícita cuando hay alguna.
    """
    avisos = []
    faltan = len(plan["faltantes"])
    if faltan:
        cuantas = ("le falta 1 entrevista que ya está" if faltan == 1
                   else f"le faltan {faltan} entrevistas que ya están")
        avisos.append(
            f"Al archivo {cuantas} en el dashboard. Suele pasar cuando se sube "
            "una copia vieja de la base: si seguís, las que cambiaron después "
            "vuelven a su versión anterior.")
    modificadas = len(plan["modificadas"])
    if plan["en_base"] and modificadas / plan["en_base"] > UMBRAL_CAMBIO_MASIVO:
        avisos.append(
            f"El archivo cambia {modificadas} de las {plan['en_base']} "
            "entrevistas ya cargadas. Es demasiado para una actualización "
            "normal: puede que el archivo se haya leído mal o que no sea la "
            "base correcta. Revisá la vista previa antes de seguir.")
    return avisos


def describir_cambios(cambios) -> str:
    """«Observaciones: "PREOCU" → "INGRESÓ"» — para la vista previa en pantalla."""
    partes = []
    for campo, antes, despues in cambios or []:
        etiqueta = ENCABEZADO.get(campo, campo)
        if campo == "apto":
            antes, despues = ("Sí" if antes else "—"), ("Sí" if despues else "—")
        a = "(vacío)" if antes is None else str(antes)
        d = "(vacío)" if despues is None else str(despues)
        partes.append(f"{etiqueta}: {a} → {d}")
    return " · ".join(partes)


def a_cargar(plan) -> pd.DataFrame:
    """Las filas que hay que mandar a la base: nuevas + modificadas."""
    partes = [plan["nuevas"][COLUMNAS_FORM], plan["modificadas"][COLUMNAS_FORM]]
    partes = [p for p in partes if len(p)]
    if not partes:
        return pd.DataFrame(columns=COLUMNAS_FORM, dtype=object)
    return pd.concat(partes, ignore_index=True)


def _nativo(v):
    """Tipos de numpy/pandas → tipos de Python que `json` sabe serializar."""
    if _vacio(v):
        return None
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):
        return v.item()
    return v


def registros_para_upsert(df, importado_por, ahora=None) -> list:
    """Filas listas para el upsert.

    Todas con las mismas claves (PostgREST lo exige en una carga por lote) y
    sin `fecha_importacion`: así el alta toma el default de la base y una
    actualización conserva la fecha en que la fila entró por primera vez.
    """
    marca = (ahora or datetime.now(timezone.utc)).isoformat()
    registros = []
    for fila in df[COLUMNAS_FORM].to_dict("records"):
        registro = {c: _nativo(fila[c]) for c in COLUMNAS_FORM}
        registro["numero_orden"] = int(registro["numero_orden"])
        registro["apto"] = bool(registro["apto"])
        registro["importado_por"] = importado_por
        registro["fecha_actualizacion"] = marca
        registros.append(registro)
    return registros


# ─── Acceso a la base (el cliente entra por parámetro) ───────
def leer_todo(client, pagina=PAGINA_LECTURA) -> pd.DataFrame:
    """Todas las entrevistas, pidiéndolas de a páginas.

    PostgREST devuelve como mucho 1000 filas por consulta y no avisa cuando
    corta: sin paginar, la pantalla mostraría las primeras 1000 como si fueran
    todas (ver paginado.py). El orden por la clave hace que las páginas no se
    pisen ni se salteen.
    """
    def consulta():
        return (client.table(TABLA)
                .select(",".join(COLUMNAS_DB), count="exact")
                .order("numero_orden"))

    return pd.DataFrame(leer_paginado(consulta, pagina=pagina), columns=COLUMNAS_DB)


def upsert(client, registros, lote=LOTE_UPSERT) -> int:
    """Inserta o actualiza por número de orden, de a lotes. Devuelve cuántas mandó.

    Nunca borra. Si un lote falla a mitad de camino, repetir la carga la
    completa: las que ya entraron salen "sin cambios" en el próximo plan.
    """
    try:
        from postgrest.types import ReturnMethod
        retorno = ReturnMethod.minimal
    except Exception:  # noqa: BLE001 — sin la librería (tests) da igual
        retorno = "minimal"

    enviados = 0
    for i in range(0, len(registros), lote):
        parte = registros[i:i + lote]
        # `minimal`: no hace falta que la base devuelva las filas cargadas.
        client.table(TABLA).upsert(
            parte, on_conflict="numero_orden", returning=retorno).execute()
        enviados += len(parte)
    return enviados


# ─── Columnas derivadas ──────────────────────────────────────
DERIVADAS = ["apenom", "puesto_grupo", "sector_norm", "entrevistador_norm",
             "dni_valido", "veces", "con_notas", "en_blanco", "_texto"]


def apenom(apellido, nombres) -> str:
    """«APELLIDO, Nombres», o lo que haya de los dos."""
    a, n = (apellido or "").strip(), (nombres or "").strip()
    return f"{a}, {n}" if a and n else (a or n)


def enriquecer(df) -> pd.DataFrame:
    """Deja el frame de la base listo para consultar.

    Normaliza tipos y agrega las columnas derivadas. Devuelve las entrevistas
    de la más nueva a la más vieja por número de orden: es el orden real de
    carga y no depende de la fecha, que tiene años mal tipeados y vacíos.
    """
    out = df.copy()
    if out.empty:
        for c in DERIVADAS:
            out[c] = pd.Series(dtype=object)
        return out

    out["numero_orden"] = pd.to_numeric(out["numero_orden"], errors="coerce").astype(int)
    out["fecha"] = out["fecha"].map(to_date)
    out["dni"] = pd.to_numeric(out["dni"], errors="coerce").astype("Int64")
    out["apto"] = out["apto"].map(canon_apto)
    for c in COLUMNAS_TEXTO:
        out[c] = out[c].map(lambda v: "" if _vacio(v) else str(v).strip())

    out["apenom"] = [apenom(a, n) for a, n in zip(out["apellido"], out["nombres"])]
    out["puesto_grupo"] = out["puesto"].map(grupo_puesto)
    out["sector_norm"] = out["sector"].map(normalizar_sector)
    out["entrevistador_norm"] = unificar_entrevistadores(out["entrevistador"])

    # El DNI 0 o vacío es "sin dato": si agrupara, las 263 entrevistas sin DNI
    # figurarían como una misma persona que se presentó 263 veces.
    out["dni_valido"] = (out["dni"].notna() & (out["dni"] > 0)).fillna(False).astype(bool)
    por_dni = out.loc[out["dni_valido"], "dni"].value_counts()
    out["veces"] = [int(por_dni[d]) if ok else 1
                    for d, ok in zip(out["dni"], out["dni_valido"])]

    out["con_notas"] = (out["motivo_rechazo"] != "") | (out["observaciones"] != "")
    out["en_blanco"] = (out["apellido"] == "") & (out["nombres"] == "") & ~out["dni_valido"]

    dni_txt = out["dni"].map(lambda d: "" if pd.isna(d) else str(int(d)))
    partes = [out["apellido"], out["nombres"], dni_txt, out["puesto"], out["sector"],
              out["sector_norm"], out["entrevistador"], out["entrevistador_norm"],
              out["motivo_rechazo"], out["observaciones"]]
    out["_texto"] = [norm(" ".join(p)) for p in zip(*partes)]

    return out.sort_values("numero_orden", ascending=False).reset_index(drop=True)


# ─── Búsqueda y filtros ──────────────────────────────────────
def _palabras(consulta) -> list:
    q = norm(consulta)
    if not q:
        return []
    # Sólo dígitos, puntos y espacios: es un DNI («11.222.333», «11 222 333»).
    if re.fullmatch(r"[\d.\s]+", q):
        solo = re.sub(r"\D", "", q)
        return [solo] if solo else []
    q = re.sub(r"(?<=\d)\.(?=\d)", "", q)
    return q.split()


def buscar(df, consulta) -> pd.DataFrame:
    """Entrevistas que contienen TODAS las palabras de la consulta.

    Busca en apellido, nombres, DNI, puesto, sector, entrevistador y notas, sin
    importar tildes, mayúsculas ni el orden. Cada palabra tiene que coincidir
    con el COMIENZO de alguna palabra del registro: «paz» encuentra PAZ y
    PAZOS, pero no CAPAZ. Con la consulta vacía devuelve todo.
    """
    palabras = _palabras(consulta)
    if not palabras or df.empty:
        return df
    mascara = pd.Series(True, index=df.index)
    for p in palabras:
        mascara &= df["_texto"].str.contains(
            r"(?:^|[^A-Z0-9])" + re.escape(p), regex=True)
    return df[mascara]


def filtrar(df, grupos=None, sectores=None, entrevistadores=None, desde=None,
            hasta=None, solo_aptos=False, solo_con_notas=False,
            solo_repetidos=False) -> pd.DataFrame:
    """Aplica los filtros de la pantalla. Cada uno es opcional.

    Con «desde» o «hasta» las entrevistas sin fecha quedan afuera: no se sabe
    si caen en el período. Sin ninguno de los dos, entran.
    """
    out = df
    if grupos:
        out = out[out["puesto_grupo"].isin(grupos)]
    if sectores:
        out = out[out["sector_norm"].isin(sectores)]
    if entrevistadores:
        out = out[out["entrevistador_norm"].isin(entrevistadores)]
    if desde is not None:
        out = out[out["fecha"].map(lambda f: f is not None and f >= desde)]
    if hasta is not None:
        out = out[out["fecha"].map(lambda f: f is not None and f <= hasta)]
    if solo_aptos:
        out = out[out["apto"]]
    if solo_con_notas:
        out = out[out["con_notas"]]
    if solo_repetidos:
        out = out[out["veces"] > 1]
    return out


def opciones(df, columna) -> list:
    """Valores de una columna derivada, del más frecuente al menos frecuente."""
    if df.empty or columna not in df.columns:
        return []
    conteo = df.loc[df[columna] != "", columna].value_counts()
    return sorted(conteo.index, key=lambda v: (-conteo[v], v))


# ─── Historial de una persona ────────────────────────────────
def historial(df, numero_orden) -> pd.DataFrame:
    """Las OTRAS entrevistas de la misma persona (mismo DNI), de vieja a nueva.

    Vacío si la entrevista no tiene DNI válido: sin DNI no hay forma confiable
    de saber que dos registros son de la misma persona.
    """
    fila = df[df["numero_orden"] == numero_orden]
    if fila.empty or not bool(fila.iloc[0]["dni_valido"]):
        return df.iloc[0:0]
    dni = fila.iloc[0]["dni"]
    otras = df[df["dni_valido"] & (df["dni"] == dni) & (df["numero_orden"] != numero_orden)]
    return otras.sort_values("numero_orden")


def apellidos_distintos(df, numero_orden) -> bool:
    """True si con el DNI de esa entrevista hay registros con otro apellido.

    Puede ser el mismo apellido mal tipeado o un DNI cargado a la persona
    equivocada: en los dos casos conviene mirar antes de sacar conclusiones.
    """
    fila = df[df["numero_orden"] == numero_orden]
    if fila.empty or not bool(fila.iloc[0]["dni_valido"]):
        return False
    mismos = df[df["dni_valido"] & (df["dni"] == fila.iloc[0]["dni"])]
    return mismos["apellido"].map(norm).replace("", pd.NA).dropna().nunique() > 1


# ─── Resumen ─────────────────────────────────────────────────
def _conteo(serie, etiqueta, tope=None) -> pd.DataFrame:
    limpia = serie[serie != ""]
    out = limpia.value_counts().rename_axis(etiqueta).reset_index(name="Entrevistas")
    out = out.sort_values(["Entrevistas", etiqueta], ascending=[False, True])
    return (out.head(tope) if tope else out).reset_index(drop=True)


def resumen(df, tope=15) -> dict:
    """Los números de la pestaña Resumen, sobre el recorte que se le pase.

    No hay tasa de aptos ni de rechazo a propósito (ver el docstring del
    módulo). `personas` es aproximado: cuenta los DNI distintos y suma una por
    cada entrevista sin DNI, que no se pueden agrupar.
    """
    if df.empty:
        vacio = pd.DataFrame()
        return {"entrevistas": 0, "personas": 0, "sin_dni": 0, "volvieron": 0,
                "aptos": 0, "por_anio": vacio, "por_grupo": vacio,
                "por_sector": vacio, "por_entrevistador": vacio, "motivos": vacio}

    con_dni = df[df["dni_valido"]]
    sin_dni = int((~df["dni_valido"]).sum())
    anios = df["fecha"].map(lambda f: f.year if f is not None else None).dropna().astype(int)
    por_anio = (anios.value_counts().sort_index()
                .rename_axis("Año").reset_index(name="Entrevistas"))
    return {
        "entrevistas": int(len(df)),
        "personas": int(con_dni["dni"].nunique()) + sin_dni,
        "sin_dni": sin_dni,
        # `veces` cuenta sobre todo el registro, no sobre el recorte.
        "volvieron": int(con_dni.loc[con_dni["veces"] > 1, "dni"].nunique()),
        "aptos": int(df["apto"].sum()),
        "por_anio": por_anio,
        "por_grupo": _conteo(df["puesto_grupo"], "Puesto"),
        "por_sector": _conteo(df["sector_norm"], "Sector", tope),
        "por_entrevistador": _conteo(df["entrevistador_norm"], "Entrevistador", tope),
        "motivos": _conteo(df["motivo_rechazo"].map(norm), "Motivo", tope),
    }


def ultima_actualizacion(df):
    """(momento, quién) de la última vez que se actualizó desde Access, o (None, "")."""
    if df.empty or "fecha_actualizacion" not in df.columns:
        return None, ""
    momentos = pd.to_datetime(df["fecha_actualizacion"], errors="coerce", utc=True)
    if momentos.isna().all():
        return None, ""
    i = momentos.idxmax()
    quien = df.loc[i, "importado_por"] if "importado_por" in df.columns else ""
    return momentos[i], ("" if _vacio(quien) else str(quien))


# ─── Exportación ─────────────────────────────────────────────
def _limpiar_celda(v):
    """Saca caracteres de control: texto pegado de Word/WhatsApp rompe openpyxl."""
    if isinstance(v, str):
        return _CTRL.sub("", v)
    return v


def preparar_export(df) -> pd.DataFrame:
    """Frame para Excel con los encabezados y el orden del FORM 045 02.

    «Apto para ingresar» sale como «Sí» o vacío, nunca «No»: la casilla sin
    tildar no es un rechazo. Ese mismo Excel se puede volver a subir para
    actualizar.
    """
    columnas = [e for _c, e in CAMPOS]
    if df.empty:
        return pd.DataFrame(columns=columnas)
    out = pd.DataFrame(index=df.index)
    for col, encabezado in CAMPOS:
        if col == "apto":
            out[encabezado] = df[col].map(lambda v: "Sí" if canon_apto(v) else "")
        elif col == "dni":
            out[encabezado] = df[col].map(lambda v: canon_dni(v))
        elif col == "fecha":
            out[encabezado] = df[col].map(to_date)
        else:
            out[encabezado] = df[col].map(lambda v: "" if _vacio(v) else v)
    return out.apply(lambda c: c.map(_limpiar_celda))


def exportar_excel(df) -> bytes:
    """Bytes de un .xlsx con una hoja 'Postulantes'."""
    datos = preparar_export(df)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        datos.to_excel(writer, sheet_name="Postulantes", index=False)
    return buffer.getvalue()
