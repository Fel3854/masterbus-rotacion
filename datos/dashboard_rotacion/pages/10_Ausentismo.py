"""Vista: Ausentismo — ausencias y francos según las novedades de MasterBus.

Ausentismo amplio: toda novedad que hace faltar al trabajo, como porcentaje del
trabajo posible (los días-persona de la gente empleada). Los francos se muestran
aparte, sobre la misma base. Qué cuenta y qué no está en `ausentismo.py`; acá van
el caché, los filtros y la pantalla. La ven todos los usuarios logueados.
"""

import os
import sys
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dateutil.relativedelta import relativedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import ausentismo as aus  # noqa: E402
from utils import (inyectar_css_base, cargar_datos, chart_base, MESES,  # noqa: E402
                   COLOR_PRIMARY, COLOR_TEXT, COLOR_SURFACE)

ZONA = "America/Argentina/Buenos_Aires"

# Un color fijo por grupo: filtrar no repinta a los que quedan. El orden es el de
# la pila y la paleta pasó el validador de daltonismo (skill de dataviz) sobre el
# blanco del gráfico. Tres colores quedan bajo 3:1 de contraste contra ese
# blanco: por eso los números también están en «Ver los datos del gráfico».
COLOR_GRUPO = {
    "Enfermedad y salud": "#2a78d6",
    "Accidentes": "#eb6834",
    "Ausencias": "#1baf7a",
    "Suspensiones": "#eda100",
    "Licencias": "#e87ba4",
    "Vacaciones": "#008300",
    aus.GRUPO_OTRAS: "#8C8987",
}
# Los francos no son ausentismo: van en una línea punteada gris, más oscura que
# «Otras» y más clara que la del total (5,5:1 de contraste sobre el blanco).
COLOR_FRANCOS = "#6B6865"
# Un período que el rango deja por la mitad (el mes en curso, por ejemplo) se ve
# más claro: no se compara de igual a igual con los completos.
OPACIDAD_INCOMPLETO = 0.45


def _num(valor, decimales=0) -> str:
    """12345.6 → «12.345,6»."""
    return f"{valor:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _cuantos(n, singular, plural) -> str:
    return f"{_num(n)} {singular if n == 1 else plural}"


def _etiqueta(inicio, granularidad) -> str:
    if granularidad == "Mensual":
        return f"{MESES[inicio.month][:3]} {inicio.year}"
    if granularidad == "Semanal":
        return f"Sem. {inicio:%d/%m/%y}"
    return f"{inicio:%d/%m/%y}"


# ─── CSS ──────────────────────────────────────────────────────
inyectar_css_base()
st.markdown(f"""
<style>
.kpi-card {{
    background: {COLOR_SURFACE}; border-radius: 12px; border: 1px solid #e3e3e3;
    border-left: 7px solid {COLOR_PRIMARY};
    padding: 0.9rem 1.2rem; box-shadow: 0 1px 5px rgba(0,0,0,0.06);
}}
.kpi-label {{
    font-size: 0.7rem; font-weight: 800; letter-spacing: 0.6px;
    text-transform: uppercase; color: #8C8987; margin-bottom: 0.35rem;
}}
.kpi-value {{
    font-family: 'Fira Code', monospace; font-size: 2.1rem; font-weight: 700;
    line-height: 1; color: {COLOR_TEXT};
}}
.kpi-sub {{ font-size: 0.74rem; color: #777; margin-top: 4px; }}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="page-header">
  <div class="bar"></div>
  <h1>Ausentismo</h1>
</div>
""", unsafe_allow_html=True)
st.caption("Ausencias del personal del Grupo Master según las novedades cargadas en MasterBus "
           "(enfermedad, accidentes, ausencias, suspensiones, licencias y vacaciones) y francos, "
           "como porcentaje del trabajo posible: los días-persona de quienes estaban empleados.")

# El servidor corre en UTC: a la noche su «hoy» ya es mañana.
HOY = pd.Timestamp.now(tz=ZONA).date()


# ─── Datos ────────────────────────────────────────────────────
@st.cache_data(ttl=3600, max_entries=1, show_spinner="Cargando las novedades de MasterBus…")
def _cargar(hoy: date) -> tuple:
    """(ausencias, francos, personas, afuera, cargado).

    Ausencias y francos son un día por fila, ya cruzados con el padrón; personas
    es el padrón con el período de empleo de cada una, para la base de los
    porcentajes. La API son ~47 MB: se baja una vez por hora, o al cambiar el día
    (por eso `hoy` es parte de la clave), y se guarda ya reducida. El padrón sale
    de `cargar_datos()`, que tiene su propio caché.
    """
    novedades = aus.normalizar_novedades(aus.descargar_novedades(), hoy)
    padron, _ = cargar_datos()
    cruzadas, afuera = aus.cruzar_padron(novedades, padron)
    ausencias, francos = aus.separar_francos(cruzadas)
    return (aus.expandir_a_dias(ausencias), aus.expandir_a_dias(francos),
            aus.personas_del_padron(padron), afuera, pd.Timestamp.now(tz=ZONA))


try:
    DIAS, FRANCOS, PERSONAS, AFUERA, CARGADO = _cargar(HOY)
except ValueError:
    # Llegó algo, pero no con la forma de siempre: reintentar no lo arregla.
    st.error("Las novedades llegaron de MasterBus con un formato que esta página no "
             "reconoce, así que no se puede mostrar el ausentismo. Avisale a quien "
             "mantiene el dashboard.")
    st.stop()
except Exception:  # noqa: BLE001 — sin las novedades o sin el padrón no hay nada que mostrar
    st.error("No se pudieron traer las novedades desde la API de MasterBus. "
             "Verificá tu conexión e intentá de nuevo.")
    st.button("Reintentar")  # el clic vuelve a correr la página, y el caché no guarda el error
    st.stop()


# ─── Filtros ──────────────────────────────────────────────────
# Una sola fila arriba de todo: indicadores, gráfico y tablas responden a ella.
grupos_presentes = [g for g in aus.GRUPOS + [aus.GRUPO_OTRAS]
                    if g in set(DIAS["grupo"].astype(str))]

f1, f2, f3, f4 = st.columns([1, 1, 2, 2])
with f1:
    desde = st.date_input("Desde", value=HOY.replace(day=1) - relativedelta(months=12),
                          min_value=aus.FECHA_MINIMA, max_value=HOY,
                          format="DD/MM/YYYY", key="aus_desde")
with f2:
    hasta = st.date_input("Hasta", value=HOY, min_value=aus.FECHA_MINIMA, max_value=HOY,
                          format="DD/MM/YYYY", key="aus_hasta")
with f3:
    sectores = st.multiselect("Sector / Operación",
                              sorted(DIAS["sector"].astype(str).unique()),
                              key="aus_sector", placeholder="Todos los sectores")
with f4:
    puestos = st.multiselect("Puesto", sorted(DIAS["puesto"].astype(str).unique()),
                             key="aus_puesto", placeholder="Todos los puestos",
                             format_func=str.title)

# Más ancha: los seis tipos marcados entran en dos renglones y no en cuatro.
f5, f6, f7 = st.columns([3, 2, 2])
with f5:
    grupos = st.multiselect("Tipo de ausencia", grupos_presentes, default=grupos_presentes,
                            key="aus_grupo", placeholder="Todos los tipos")
opciones_novedad = sorted(
    DIAS.loc[DIAS["grupo"].isin(grupos or grupos_presentes), "novedad"].astype(str).unique())
# Si se saca el tipo de una novedad elegida, esa novedad deja de ser una opción.
if "aus_novedad" in st.session_state:
    st.session_state["aus_novedad"] = [n for n in st.session_state["aus_novedad"]
                                       if n in opciones_novedad]
with f6:
    novedades = st.multiselect("Novedad", opciones_novedad, key="aus_novedad",
                               placeholder="Todas las de esos tipos")
with f7:
    pedida = st.radio("Agrupar por", aus.GRANULARIDADES, horizontal=True, key="aus_gran")

if desde > hasta:
    st.warning("La fecha «Desde» es posterior a «Hasta».")
    st.stop()

granularidad, cambiada = aus.granularidad_efectiva(pedida, desde, hasta)
if cambiada:
    st.info("Día por día se muestra con hasta un año de rango: para este rango se agrupa "
            "por semana.")

dias = aus.filtrar(DIAS, desde, hasta, sectores, puestos, grupos, novedades)
# Los francos y la base dependen sólo de fechas, sector y puesto: elegir tipos de
# ausencia no los cambia.
dias_franco = aus.filtrar(FRANCOS, desde, hasta, sectores, puestos)
posibles = aus.dias_posibles(PERSONAS, granularidad, desde, hasta, sectores, puestos)
base = int(posibles.sum())


# ─── Indicadores ──────────────────────────────────────────────
k = aus.kpis(dias, base)
for col, etiqueta, valor, sub in zip(
        st.columns(4),
        ("Ausentismo", "Días de ausencia", "Personas con ausencias", "Días por persona"),
        (f"{_num(k['pct'], 2)} %", _num(k["dias"]), _num(k["personas"]),
         _num(k["promedio"], 1)),
        (f"sobre {_num(base)} días-persona posibles",
         "días corridos, sumando a todas las personas", "con al menos un día en el período",
         "promedio entre quienes faltaron")):
    col.markdown(f'<div class="kpi-card"><div class="kpi-label">{etiqueta}</div>'
                 f'<div class="kpi-value">{valor}</div><div class="kpi-sub">{sub}</div></div>',
                 unsafe_allow_html=True)

if dias.empty:
    st.info("No hay ausencias para esos filtros.")
    st.stop()


# ─── Evolución ────────────────────────────────────────────────
st.markdown('<div class="section-header"><div class="bar"></div>'
            '<span>Evolución del ausentismo y los francos</span></div>', unsafe_allow_html=True)

tabla = aus.serie(dias, granularidad, desde, hasta)
francos = aus.serie(dias_franco, granularidad, desde, hasta)["Total"]
pct = aus.porcentajes(tabla, posibles)
pct_francos = aus.porcentajes(francos, posibles)
etiquetas = [_etiqueta(inicio, granularidad) for inicio in tabla.index]
cortados = aus.incompletos(tabla.index, granularidad, desde, hasta)
opacidad = [OPACIDAD_INCOMPLETO if c else 1.0 for c in cortados]
aviso = ["<br><i>período incompleto</i>" if c else "" for c in cortados]

# Todo en % del trabajo posible del período; el hover suma los días, y el total la base.
fig = go.Figure()
for grupo in [c for c in tabla.columns if c != "Total"]:
    fig.add_trace(go.Bar(
        x=etiquetas, y=pct[grupo].tolist(), name=grupo, customdata=tabla[grupo].tolist(),
        marker=dict(color=COLOR_GRUPO.get(grupo, COLOR_GRUPO[aus.GRUPO_OTRAS]),
                    opacity=opacidad, line=dict(color=COLOR_SURFACE, width=2)),
        hovertemplate=f"{grupo}: %{{y:.2f}} % (%{{customdata:,}} días)<extra></extra>",
    ))
fig.add_trace(go.Scatter(
    x=etiquetas, y=pct["Total"].tolist(), name="Total ausentismo", mode="lines",
    line=dict(color=COLOR_TEXT, width=2),
    customdata=[list(c) for c in zip(tabla["Total"].tolist(), posibles.tolist(), aviso)],
    hovertemplate=("<b>Total ausentismo: %{y:.2f} %</b> (%{customdata[0]:,} días)"
                   "<br>Base: %{customdata[1]:,} días-persona posibles"
                   "%{customdata[2]}<extra></extra>"),
))
hay_francos = bool(francos.sum())
if hay_francos:
    fig.add_trace(go.Scatter(
        x=etiquetas, y=pct_francos.tolist(), name="Francos", mode="lines",
        line=dict(color=COLOR_FRANCOS, width=2, dash="dot"), customdata=francos.tolist(),
        hovertemplate="Francos: %{y:.2f} % (%{customdata:,} días)<extra></extra>",
    ))
fig.update_layout(**chart_base(
    barmode="stack", bargap=0.3, barcornerradius=4, hovermode="x unified", height=420,
    separators=",.", margin=dict(l=10, r=10, t=40, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
))
fig.update_xaxes(type="category")
fig.update_yaxes(title_text="% de los días-persona posibles", ticksuffix=" %")
# Sin la barra de herramientas de Plotly, como en Postulantes: tapaba la leyenda.
# Los números se bajan desde «Ver los datos del gráfico».
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
if hay_francos:
    st.caption("La línea punteada son los francos, sobre la misma base: no son ausentismo. "
               "MasterBus los tiene sólo para quien trabaja con diagrama (sobre todo "
               "conductores): con todos los puestos, su porcentaje queda diluido.")
else:
    st.caption("No hay francos cargados para estos filtros: MasterBus los tiene sólo para "
               "quien trabaja con diagrama (sobre todo conductores).")
if any(cortados):
    st.caption("Las barras más claras son períodos que el rango elegido deja por la mitad "
               "(por ejemplo, el mes en curso): su porcentaje se calcula sólo sobre los días "
               "que entran en el rango.")

with st.expander("Ver los datos del gráfico"):
    datos = (pct / 100).rename(columns={"Total": "Total ausentismo"})
    datos["Francos"] = pct_francos / 100
    cantidades = {"Días de ausencia": tabla["Total"], "Días de franco": francos,
                  "Días-persona posibles": posibles}
    for nombre, valores in cantidades.items():
        datos[nombre] = valores
    datos.index = pd.Index(etiquetas, name="Período")
    st.dataframe(datos, use_container_width=True, column_config={
        c: st.column_config.NumberColumn(c, format="localized" if c in cantidades else "percent")
        for c in datos.columns})


# ─── Detalle por novedad ──────────────────────────────────────
st.markdown('<div class="section-header"><div class="bar"></div>'
            '<span>Detalle por novedad</span></div>', unsafe_allow_html=True)
resumen = aus.resumen_por_tipo(dias, base)
# «localized» y «percent» los formatea el navegador según el idioma de quien mira
# (11.243 y 47,4 % en uno en castellano), y las columnas se siguen ordenando
# como números.
st.dataframe(
    resumen.assign(pct=resumen["pct"] / 100), hide_index=True, use_container_width=True,
    column_config={
        "grupo": "Tipo de ausencia",
        "novedad": "Novedad",
        "dias": st.column_config.NumberColumn("Días", format="localized"),
        "personas": st.column_config.NumberColumn("Personas", format="localized"),
        "pct": st.column_config.NumberColumn("% del trabajo posible", format="percent"),
    })

with st.expander("¿Qué cuenta como ausentismo?"):
    por_grupo = "\n".join(
        f"- **{g}**: " + ", ".join(t for t, de in aus.TIPO_A_GRUPO.items() if de == g)
        for g in aus.GRUPOS)
    st.markdown(
        "Cuenta toda novedad que hace faltar al trabajo, en **días corridos**: un rango "
        "desde–hasta suma todos sus días, aunque en el medio caiga un franco o un feriado. "
        "Si un mismo día tiene dos novedades distintas, cuenta en las dos.\n\n"
        f"{por_grupo}\n\n"
        "**No cuentan** los días que no tocaba trabajar, los que se trabajaron, los ajustes "
        "del diagrama y el permiso gremial (los delegados de tiempo completo sumarían el año "
        "entero): " + ", ".join(sorted(aus.NOVEDADES_EXCLUIDAS)) + ".\n\n"
        "Los porcentajes son sobre el **trabajo posible**: los días-persona en que cada "
        "persona estaba empleada (de su ingreso a su baja), dentro del rango y de los filtros "
        "de sector y puesto. Quien figura inactivo sin fecha de baja no entra, como en la "
        "dotación del Dashboard. Los **francos** ("
        + ", ".join(sorted(aus.NOVEDADES_FRANCO)) + ") van en la línea punteada, sobre la "
        "misma base, y no suman al ausentismo.\n\n"
        f"Un tipo nuevo que aparezca en MasterBus cuenta en **{aus.GRUPO_OTRAS}** hasta que se "
        f"lo clasifique. Se cuenta desde el {aus.FECHA_MINIMA:%d/%m/%Y}: antes, la carga en "
        "MasterBus es parcial.")

fuera = ""
if AFUERA["novedades"]:
    fuera = (" Sin padrón del Grupo Master o sin fecha de baja (no se cuentan): "
             f"{_cuantos(AFUERA['novedades'], 'novedad', 'novedades')} de "
             f"{_cuantos(AFUERA['personas'], 'persona', 'personas')}, en toda la base.")
st.caption(f"Datos al {CARGADO:%d/%m/%Y %H:%M}. Sector y puesto son los actuales de cada "
           f"persona.{fuera}")
