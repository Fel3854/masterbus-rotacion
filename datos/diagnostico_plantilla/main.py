#!/usr/bin/env python3
"""
Diagnóstico de Plantilla al Inicio — Grupo Master

Descarga los datos de la API y muestra exactamente qué empleados
componen el número de "Plantilla al inicio" para un período dado.

Uso:
    python main.py --año 2026 --mes 1
    python main.py --año 2025                       # vista anual
    python main.py --año 2026 --mes 1 --lista       # muestra cada empleado
    python main.py --año 2026 --mes 1 --csv p.csv   # exporta a CSV
    python main.py --año 2026 --mes 1 --cargo CONDUCTOR
    python main.py --año 2026 --mes 1 --sector "OPERACION CAMPANA"
"""

import argparse
import sys
import requests
import pandas as pd
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

API_URL = "https://traficonuevo.masterbus.net/api/v1/auto/e"

GRUPO_MASTER = {
    "MASTER BUS S.A",
    "MASTER BUS SA",
    "MASTER BUS TASA",
    "SINTRA",
    "M B M S.A.",
    "MASTER MINING SA",
    "SOLUCIONES IOT S.A.",
    "ENDUROCO LATAM SA",
}

MESES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

FECHAS_INVALIDAS = {"00/00/0000", ""}


def _parse_fecha(s):
    if not s or str(s).strip() in FECHAS_INVALIDAS:
        return None
    try:
        return pd.to_datetime(str(s).strip(), format="%d/%m/%Y").date()
    except ValueError:
        return None


def cargar_datos():
    print("Cargando datos desde la API de MasterBus...")
    resp = requests.get(API_URL, timeout=30)
    resp.raise_for_status()
    df = pd.DataFrame(resp.json())
    print(f"  Total empleados en API: {len(df)}")

    df_master = df[df["empleador"].isin(GRUPO_MASTER)].copy()
    print(f"  Empleados del Grupo Master: {len(df_master)}")

    df_master["fecha_inicio"] = df_master["fechainicio"].apply(_parse_fecha)
    df_master["fecha_fin"] = df_master["fechafin"].apply(_parse_fecha)
    df_master = df_master[df_master["fecha_inicio"].notna()].copy()
    df_master["cargo"] = df_master["cargo"].str.strip().str.upper()
    df_master["str"] = df_master["str"].str.strip()

    return df_master


def calcular_plantilla(df, inicio):
    """Empleados activos el día 1 del período."""
    mask = (
        (df["fecha_inicio"] < inicio)
        & (df["fecha_fin"].isna() | (df["fecha_fin"] >= inicio))
    )
    return df[mask].copy()


def sep(char="─", n=65):
    print(char * n)


def main():
    parser = argparse.ArgumentParser(
        description="Diagnóstico de Plantilla al Inicio — Grupo Master",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--año",    type=int, required=True, help="Año del período")
    parser.add_argument("--mes",    type=int, default=None,  help="Mes 1-12. Omitir para vista anual.")
    parser.add_argument("--cargo",  type=str, default=None,  help="Filtrar cargo (substring, case-insensitive)")
    parser.add_argument("--sector", type=str, default=None,  help="Filtrar sector (substring, case-insensitive)")
    parser.add_argument("--lista",  action="store_true",     help="Mostrar listado completo de empleados en consola")
    parser.add_argument("--csv",    type=str, default=None,  help="Exportar listado completo a este archivo CSV")
    args = parser.parse_args()

    # ── Período ──────────────────────────────────────────────────
    if args.mes:
        inicio = date(args.año, args.mes, 1)
        label = f"{MESES[args.mes]} {args.año}"
    else:
        inicio = date(args.año, 1, 1)
        label = str(args.año)

    print()
    sep("═")
    print(f"  DIAGNÓSTICO DE PLANTILLA AL INICIO — {label}")
    print(f"  Criterio: ingresaron ANTES de {inicio.strftime('%d/%m/%Y')} y no se habían ido aún")
    sep("═")
    print()

    # ── Datos ────────────────────────────────────────────────────
    try:
        df = cargar_datos()
    except Exception as e:
        print(f"\nERROR al cargar datos: {e}", file=sys.stderr)
        sys.exit(1)

    # ── Filtros opcionales ───────────────────────────────────────
    filtros_aplicados = []
    if args.cargo:
        df = df[df["cargo"].str.contains(args.cargo.upper(), na=False)]
        filtros_aplicados.append(f"cargo contiene '{args.cargo.upper()}'")
    if args.sector:
        df = df[df["str"].str.contains(args.sector, case=False, na=False)]
        filtros_aplicados.append(f"sector contiene '{args.sector}'")
    if filtros_aplicados:
        print(f"\n  Filtros activos: {' | '.join(filtros_aplicados)}")

    # ── Calcular plantilla ───────────────────────────────────────
    plantilla = calcular_plantilla(df, inicio)
    total = len(plantilla)

    print()
    sep()
    print(f"  PLANTILLA AL INICIO: {total} empleados")
    sep()
    print()

    if total == 0:
        print("  Sin empleados para los filtros y período seleccionados.")
        return

    # ── Desglose por empresa ─────────────────────────────────────
    print("POR EMPRESA:")
    emp = plantilla["empleador"].value_counts()
    for empresa, n in emp.items():
        pct = n / total * 100
        bar = "█" * max(1, int(pct / 3))
        print(f"  {empresa:<30} {n:>5}  ({pct:5.1f}%)  {bar}")
    print()

    # ── Desglose por cargo (top 20) ──────────────────────────────
    print("POR CARGO (top 20):")
    cargos = plantilla["cargo"].value_counts().head(20)
    for cargo, n in cargos.items():
        pct = n / total * 100
        bar = "█" * max(1, int(pct / 2))
        print(f"  {cargo:<38} {n:>5}  ({pct:5.1f}%)  {bar}")
    if len(plantilla["cargo"].unique()) > 20:
        resto = len(plantilla["cargo"].unique()) - 20
        print(f"  ... y {resto} cargos más")
    print()

    # ── Desglose por sector ──────────────────────────────────────
    print("POR SECTOR:")
    sectores = plantilla["str"].value_counts()
    for sector, n in sectores.items():
        pct = n / total * 100
        bar = "█" * max(1, int(pct / 3))
        print(f"  {sector:<42} {n:>5}  ({pct:5.1f}%)  {bar}")
    print()

    # ── Composición: activos puros vs activos con fin futuro ─────
    sin_fin = plantilla["fecha_fin"].isna().sum()
    con_fin = plantilla["fecha_fin"].notna().sum()
    print("COMPOSICIÓN:")
    print(f"  Sin fecha de baja (siguen activos):         {sin_fin:>5}")
    print(f"  Con fecha de baja posterior al inicio:      {con_fin:>5}   ← se van durante o después del período")
    print(f"  Total plantilla al inicio:                  {total:>5}")
    print()

    # ── Antigüedad promedio ──────────────────────────────────────
    meses_antig = []
    for _, row in plantilla.iterrows():
        if row["fecha_inicio"]:
            delta = relativedelta(inicio, row["fecha_inicio"])
            meses_antig.append(delta.years * 12 + delta.months)
    if meses_antig:
        prom = sum(meses_antig) / len(meses_antig)
        med  = sorted(meses_antig)[len(meses_antig) // 2]
        print(f"ANTIGÜEDAD AL INICIO DEL PERÍODO:")
        print(f"  Promedio: {prom:.1f} meses  ({prom/12:.1f} años)")
        print(f"  Mediana:  {med} meses  ({med/12:.1f} años)")
        print()

    # ── Listado en consola ───────────────────────────────────────
    if args.lista:
        sep()
        print("LISTADO COMPLETO (ordenado por cargo, luego nombre):")
        sep()
        cols_raw = ["legajo", "apenom", "cargo", "empleador", "str", "fechainicio", "fechafin"]
        cols_raw = [c for c in cols_raw if c in plantilla.columns]
        display = (
            plantilla[cols_raw]
            .rename(columns={
                "legajo": "Legajo", "apenom": "Nombre", "cargo": "Cargo",
                "empleador": "Empleador", "str": "Sector",
                "fechainicio": "Ingreso", "fechafin": "Baja",
            })
            .sort_values(["Cargo", "Nombre"])
            .reset_index(drop=True)
        )
        pd.set_option("display.max_rows",    None)
        pd.set_option("display.max_colwidth", 35)
        pd.set_option("display.width",        130)
        print(display.to_string(index=False))
        print()

    # ── Exportar CSV ─────────────────────────────────────────────
    if args.csv:
        cols_raw = ["legajo", "apenom", "cargo", "empleador", "str", "fechainicio", "fechafin"]
        cols_raw = [c for c in cols_raw if c in plantilla.columns]
        export = (
            plantilla[cols_raw]
            .rename(columns={
                "legajo": "Legajo", "apenom": "Nombre", "cargo": "Cargo",
                "empleador": "Empleador", "str": "Sector",
                "fechainicio": "Ingreso", "fechafin": "Baja",
            })
            .sort_values(["Cargo", "Nombre"])
            .reset_index(drop=True)
        )
        export.to_csv(args.csv, index=False, encoding="utf-8-sig")
        print(f"  CSV exportado → {args.csv}  ({len(export)} filas)")
        print()


if __name__ == "__main__":
    main()
