"""Ausentismo amplio: las novedades de MasterBus que hacen faltar al trabajo.

La API de novedades (`/api/v1/auto`) trae todo lo que se carga en el diagrama:
francos, feriados, días trabajados, compensaciones y ausencias. Acá se define
qué cuenta como ausentismo, se pasa cada novedad (un rango desde–hasta) a días
de ausencia y se agrega por período. Sin Streamlit: la página
`pages/10_Ausentismo.py` se encarga del caché y de la pantalla.
"""

import json
from datetime import date

import pandas as pd
import requests

API_NOVEDADES_URL = "https://traficonuevo.masterbus.net/api/v1/auto"

# Antes de 2014 la carga en MasterBus es parcial (y hay fechas basura, como el
# año 0206): una serie que arranque antes mostraría un crecimiento que no fue.
FECHA_MINIMA = date(2014, 1, 1)

SIN_DATO = "Sin dato"

# Lo que no es ausentismo: días que no tocaba trabajar (francos, feriados), días
# que sí se trabajaron, y ajustes o compensaciones de días del diagrama.
NOVEDADES_EXCLUIDAS = frozenset({
    "Franco", "Feriado", "FRANCO/FERIADO",
    "Franco trabajado", "Feriado trabajado",
    "Franco compensatorio", "Adeuda Dia", "Devuelve Dia", "Compensa dia",
    "AJUSTE FRANCOS", "DIA FLEX",
    "Control de ausentismo",
})

# Todo lo demás cuenta. Para el gráfico se agrupa: 33 tipos no se pueden apilar
# con colores que se distingan. El orden es el de la pila, de abajo hacia
# arriba: lo no planificado primero, Vacaciones arriba de todo.
_TIPOS_POR_GRUPO = {
    "Enfermedad y salud": [
        "Enfermedad", "Constancia de Atencion Medica", "Citacion Medica", "CUARENTENA",
        "LICENCIA COVID", "LICENCIA VACUNACION", "ART COVID-19", "Res. puesto trabajo"],
    "Accidentes": ["Accidente Laboral", "Accidente en itinerario"],
    "Ausencias": [
        "Ausencia injustificada", "Ausencia con aviso", "Ausencia sin aviso",
        "AUSENCIA JUSTIFICADA", "Jornada Incompleta"],
    "Suspensiones": ["Suspension", "SUSPENSION X REGISTRO"],
    "Licencias": [
        "Licencia por Fallecimiento", "Licencia por Maternidad", "Licencia por Matrimonio",
        "Licencia por Examen", "Licencia Especial", "Licencia Judicial", "LICENCIA S/GOCE",
        "Permiso Gremial", "Mudanza", "Periodo de Excendencia", "Donacion de sangre",
        "LICENCIA POR REGISTRO", "Renovacion Registro", "Renovacion Examen Periodico",
        "Asistencia a curso"],
    "Vacaciones": ["Vacaciones"],
}
GRUPOS = list(_TIPOS_POR_GRUPO)
TIPO_A_GRUPO = {tipo: grupo for grupo, tipos in _TIPOS_POR_GRUPO.items() for tipo in tipos}
# Un tipo que la API agregue más adelante cuenta igual (la definición es amplia)
# y queda acá hasta que se lo clasifique.
GRUPO_OTRAS = "Otras"

COLUMNAS = ["id_empleado", "legajo", "novedad", "desde", "hasta"]

GRANULARIDADES = ("Mensual", "Semanal", "Diaria")
_FRECUENCIA = {"Mensual": "M", "Semanal": "W-SUN", "Diaria": "D"}  # semanas de lunes a domingo
# Más de un año día por día son cientos de barras que no se leen: pasa a Semanal.
DIAS_MAX_DIARIA = 366


def grupo_de(novedad: str) -> str:
    return TIPO_A_GRUPO.get(novedad, GRUPO_OTRAS)


def normalizar_puesto(cargo) -> str:
    """El cargo del padrón en mayúsculas; «CONDUCTOR» y «CONDUCTORES» son uno solo.

    Misma regla que Seguimiento (`seguimiento._solo_conductores`): todo cargo
    que empieza con CONDUCTOR es de conductor.
    """
    c = str(cargo or "").strip().upper()
    if c.startswith("CONDUCTOR"):
        return "CONDUCTORES"
    return c or SIN_DATO


def parsear_novedades(contenido) -> list:
    """Lee la respuesta de la API quedándose sólo con lo que se usa.

    Son ~47 MB y 320 mil novedades: leídas enteras como diccionarios le suman
    unos 430 MB a la memoria de la app (así, unos 150). Por eso al parsear se
    descarta lo que no es ausentismo (dos de cada tres son francos) y los
    nombres; cada novedad queda como `(id_empleado, legajo, novedad, desde,
    hasta)`, y los textos repetidos (fechas, tipos) se guardan una sola vez.
    """
    compartidos = {}

    def texto(valor):
        s = str(valor or "").strip()
        return compartidos.setdefault(s, s)

    def registro(pares):
        d = dict(pares)
        novedad = texto(d.get("novedad"))
        if novedad in NOVEDADES_EXCLUIDAS:
            return None
        return (texto(d.get("id_empleado")), texto(d.get("legajo")), novedad,
                texto(d.get("desde")), texto(d.get("hasta")))

    datos = json.loads(contenido, object_pairs_hook=registro)
    if not isinstance(datos, list):
        raise ValueError("La API de novedades no devolvió una lista.")
    return [r for r in datos if r is not None]


def descargar_novedades(timeout=(10, 120)) -> list:
    """Baja las novedades de MasterBus (sin credenciales, igual que el padrón)."""
    resp = requests.get(API_NOVEDADES_URL, timeout=timeout)
    resp.raise_for_status()
    return parsear_novedades(resp.content)


def normalizar_novedades(registros, hoy: date) -> pd.DataFrame:
    """Las novedades en un DataFrame limpio, recortadas a [FECHA_MINIMA, hoy].

    Quedan afuera las fechas inválidas o invertidas, los registros sin persona
    o sin tipo y los duplicados exactos. Lo que todavía no pasó (vacaciones
    programadas) no cuenta hasta que pase.
    """
    df = pd.DataFrame.from_records(registros, columns=COLUMNAS)
    for col in ("desde", "hasta"):
        df[col] = pd.to_datetime(df[col], format="%Y-%m-%d", errors="coerce")
    validas = ((df["id_empleado"] != "") & (df["novedad"] != "")
               & df["desde"].notna() & df["hasta"].notna() & (df["desde"] <= df["hasta"]))
    df = df[validas].drop_duplicates().copy()
    df["desde"] = df["desde"].clip(lower=pd.Timestamp(FECHA_MINIMA))
    df["hasta"] = df["hasta"].clip(upper=pd.Timestamp(hoy))
    df = df[df["desde"] <= df["hasta"]].reset_index(drop=True)
    df["grupo"] = df["novedad"].map(grupo_de)
    return df


def cruzar_padron(novedades: pd.DataFrame, padron: pd.DataFrame):
    """Suma sector, puesto y empleador de cada persona, cruzando por `id_empleado`.

    Por legajo no se puede: el mismo legajo existe en más de una empresa del
    grupo. Quedan sólo las personas del padrón que se pasa (el del Grupo
    Master); lo que queda afuera vuelve contado, para avisarlo en la página.
    Sector y puesto son los de hoy: la API no guarda el historial.

    Devuelve `(novedades_cruzadas, {"novedades": n, "personas": n})`.
    """
    personas = pd.DataFrame({
        "id_empleado": padron["id_empleado"].astype(str).str.strip(),
        "sector": padron["str"].fillna("").astype(str).str.strip().replace("", SIN_DATO),
        "puesto": padron["cargo"].map(normalizar_puesto),
        "empleador": padron["empleador"].fillna("").astype(str).str.strip(),
    }).drop_duplicates("id_empleado")
    dentro = novedades["id_empleado"].isin(personas["id_empleado"])
    afuera = {"novedades": int((~dentro).sum()),
              "personas": novedades.loc[~dentro, "id_empleado"].nunique()}
    return novedades.merge(personas, on="id_empleado", how="inner"), afuera


def expandir_a_dias(novedades: pd.DataFrame) -> pd.DataFrame:
    """Una fila por persona, tipo de novedad y día: la base para contar días.

    Un día cargado dos veces con el mismo tipo cuenta una vez; con dos tipos
    distintos cuenta en ambos (pasa en menos del 1% de los días).
    """
    novedades = novedades.reset_index(drop=True)
    atributos = [c for c in novedades.columns if c not in ("legajo", "desde", "hasta")]
    base = novedades[atributos].astype({c: "category" for c in atributos})
    base["desde"] = novedades["desde"]
    largos = ((novedades["hasta"] - novedades["desde"]) // pd.Timedelta(days=1) + 1).to_numpy()
    dias = base.loc[base.index.repeat(largos)]
    corrimiento = pd.to_timedelta(dias.groupby(level=0).cumcount().to_numpy(), unit="D")
    dias = dias.assign(dia=dias["desde"].to_numpy() + corrimiento).drop(columns="desde")
    return dias.drop_duplicates(["id_empleado", "novedad", "dia"]).reset_index(drop=True)


def filtrar(dias: pd.DataFrame, desde: date, hasta: date, sectores=(), puestos=(),
            grupos=(), novedades=()) -> pd.DataFrame:
    """Los días entre `desde` y `hasta` (inclusive) que pasan los filtros.

    Un filtro vacío no filtra, como en los multiselect del Dashboard.
    """
    elegidos = (dias["dia"] >= pd.Timestamp(desde)) & (dias["dia"] <= pd.Timestamp(hasta))
    for columna, valores in (("sector", sectores), ("puesto", puestos),
                             ("grupo", grupos), ("novedad", novedades)):
        if valores:
            elegidos &= dias[columna].isin(list(valores))
    return dias[elegidos]


def granularidad_efectiva(granularidad: str, desde: date, hasta: date):
    """`(granularidad a usar, si hubo que cambiarla)`: Diaria sólo hasta un año."""
    if granularidad == "Diaria" and (hasta - desde).days + 1 > DIAS_MAX_DIARIA:
        return "Semanal", True
    return granularidad, False


def serie(dias: pd.DataFrame, granularidad: str, desde: date, hasta: date) -> pd.DataFrame:
    """Días de ausencia por período (filas) y grupo (columnas), más la columna «Total».

    Las filas son el inicio de cada período que toca [desde, hasta], aunque no
    tenga ausencias. Las columnas son sólo los grupos con algún día, en el
    orden de la pila.
    """
    frecuencia = _FRECUENCIA[granularidad]
    inicios = pd.period_range(pd.Timestamp(desde), pd.Timestamp(hasta), freq=frecuencia).start_time
    if dias.empty:
        tabla = pd.DataFrame(index=inicios)
    else:
        periodo = dias["dia"].dt.to_period(frecuencia).dt.start_time.rename("periodo")
        tabla = dias.groupby([periodo, dias["grupo"].astype(str)]).size().unstack(fill_value=0)
        orden = [g for g in GRUPOS + [GRUPO_OTRAS] if g in tabla.columns]
        tabla = tabla.reindex(index=inicios, columns=orden, fill_value=0)
    tabla["Total"] = tabla.sum(axis=1)
    tabla.index.name = "periodo"
    tabla.columns.name = None
    return tabla.astype(int)


def incompletos(inicios, granularidad: str, desde: date, hasta: date) -> list:
    """Para cada período (por su inicio), si el rango elegido lo deja por la mitad."""
    periodos = pd.DatetimeIndex(inicios).to_period(_FRECUENCIA[granularidad])
    return [p.start_time.date() < desde or p.end_time.date() > hasta for p in periodos]


def resumen_por_tipo(dias: pd.DataFrame) -> pd.DataFrame:
    """Días y personas por tipo de novedad, de mayor a menor, con su % de los días."""
    tabla = (dias.assign(grupo=dias["grupo"].astype(str), novedad=dias["novedad"].astype(str))
             .groupby(["grupo", "novedad"])
             .agg(dias=("dia", "size"), personas=("id_empleado", "nunique"))
             .reset_index())
    total = tabla["dias"].sum()
    tabla["pct"] = (tabla["dias"] / total * 100).round(1) if total else 0.0
    return tabla.sort_values(["dias", "novedad"], ascending=[False, True]).reset_index(drop=True)


def kpis(dias: pd.DataFrame) -> dict:
    """Días de ausencia, personas con al menos uno y días promedio por persona."""
    personas = dias["id_empleado"].nunique()
    return {"dias": len(dias), "personas": personas,
            "promedio": round(len(dias) / personas, 1) if personas else 0.0}
