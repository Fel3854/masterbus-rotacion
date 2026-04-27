#!/usr/bin/env python3
"""
Alerta de Período de Prueba — Empleados en Mes 5

Consume la API de empleados de MasterBus, detecta los que están
cumpliendo su 5° mes de período de prueba y envía una alerta
al gerente responsable según el cargo del empleado.

Uso:
    python main.py              # Ejecuta y envía emails
    python main.py --dry-run    # Solo muestra resultados, no envía
"""

import argparse
import json
import logging
import smtplib
import sys
from collections import defaultdict
from datetime import datetime, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, List, Optional

import requests

# ─── Logging ────────────────────────────────────────────────
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "alerta_periodo_prueba.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ─── Constantes ─────────────────────────────────────────────
NOTIFICADOS_FILE = Path(__file__).resolve().parent / "notificados.json"
FECHAS_INVALIDAS = {"00/00/0000", "", None}

# ─── Mapeo cargo → gerente responsable ──────────────────────
CARGO_GERENTE = {
    "ACTIVADOR":                                     "jcabral@masterbus.net",
    "ADMINISTRADOR DE COORDINACION IT":              "icarvajal@masterbus.net",
    "ADMINISTRATIVO":                                "dscirocco@masterbus.net",
    "ASISTENTE ADM DE INTENDENCIA":                  "ellanos@masterbus.net",
    "ASISTENTE ADM. DE RRHH":                        "ffillopski@masterbus.net",
    "ASISTENTE ADMINISTRATIVO DE PAÃOL":             "jcabral@masterbus.net",
    "ASISTENTE ADMINISTRATIVO DE SEGURIDAD VIAL":    "jcigna@masterbus.net",
    "ASISTENTE ADMINISTRATIVO DE TALLER":            "asalvetti@masterbus.net",
    "ASISTENTE BALANCE Y DOCUMENTACION DE BANCOS":   "dscirocco@masterbus.net",
    "ASISTENTE CONTABLE":                            "dscirocco@masterbus.net",
    "ASISTENTE DE ABASTECIMIENTO":                   "jcabral@masterbus.net",
    "ASISTENTE DE GESTION":                          "dscirocco@masterbus.net",
    "ASISTENTE DE LICITACIONES":                     "dscirocco@masterbus.net",
    "ASISTENTE DE NORMAS ISO":                       "talcantara@masterbus.net",
    "ASISTENTE DE SEGURIDAD INDUSTRIAL Y AMBIENTE":  "talcantara@masterbus.net",
    "ASISTENTE OPERATIVO":                           "mdepeon@masterbus.net",
    "ASISTENTE OPERATIVO DE SEGURIDAD VIAL":         "jcigna@masterbus.net",
    "BRIGADISTA":                                    "talcantara@masterbus.net",
    "CADETE":                                        "dscirocco@masterbus.net",
    "CELADOR":                                       "mdepeon@masterbus.net",
    "CHAPISTA":                                      "asalvetti@masterbus.net",
    "CHAPISTA (SALTA/CAT)":                          "asalvetti@masterbus.net",
    "CONDUCTOR":                                     "mdepeon@masterbus.net",
    "CONTRATISTAS":                                  "mdepeon@masterbus.net",
    "COORDINADOR DE BASES":                          "asalvetti@masterbus.net",
    "COORDINADOR DE IT FLOTA":                       "icarvajal@masterbus.net",
    "DESPACHANTE DE COMBUSTIBLE":                    "ellanos@masterbus.net",
    "DIAGRAMADOR DE TRAFICO":                        "mdepeon@masterbus.net",
    "ELECTRICISTA":                                  "asalvetti@masterbus.net",
    "ELECTRICISTA (SALTA/CAT)":                      "asalvetti@masterbus.net",
    "EMPLEADO PANIOL":                               "jcabral@masterbus.net",
    "ENCARGADO DE CUENTAS A PAGAR":                  "dscirocco@masterbus.net",
    "ENCARGADO DE FACTURACION":                      "dscirocco@masterbus.net",
    "ENCARGADO DE TESORERIA":                        "dscirocco@masterbus.net",
    "ENCARGADO IMPOSITIVO":                          "dscirocco@masterbus.net",
    "FORMADORES":                                    "jcigna@masterbus.net",
    "LAVADOR":                                       "ellanos@masterbus.net",
    "LIDER DE PAÃOL":                                "jcabral@masterbus.net",
    "LIQUIDADOR DE SUELDOS - GESTION DOC. EMPRESAS": "ffillopski@masterbus.net",
    "MAESTRANZA":                                    "ellanos@masterbus.net",
    "MAESTRANZA OLAV":                               "ellanos@masterbus.net",
    "MECANICO":                                      "asalvetti@masterbus.net",
    "MECANICO (SALTA/CAT)":                          "asalvetti@masterbus.net",
    "OPERADOR":                                      "mdepeon@masterbus.net",
    "PAÃOLERO":                                      "jcabral@masterbus.net",
    "PROGRAMADOR OPERATIVO":                         "mdepeon@masterbus.net",
    "PROGRAMADOR/DESARROLLO":                        "mdepeon@masterbus.net",
    "RECEPCION":                                     "dscirocco@masterbus.net",
    "SEGURIDAD VIAL Y CAPACITACIONES":               "jcigna@masterbus.net",
    "SOPORTE ON SITE IT FLOTA":                      "icarvajal@masterbus.net",
    "SUPERVISOR ADM DE CARROCERIA":                  "asalvetti@masterbus.net",
    "SUPERVISOR DE CHAPA Y PINTURA":                 "asalvetti@masterbus.net",
    "SUPERVISOR DE ELECTRICISTAS":                   "asalvetti@masterbus.net",
    "SUPERVISOR DE OPERACIONES DE TALLER":           "asalvetti@masterbus.net",
    "SUPERVISOR DE PLANTA":                          "mdepeon@masterbus.net",
    "SUPERVISOR DE PLAYA":                           "ellanos@masterbus.net",
    "SUPERVISOR DE SUPERVISORES":                    "mdepeon@masterbus.net",
    "SUPERVISOR DE TALLER":                          "asalvetti@masterbus.net",
    "SUPERVISOR GENERAL":                            "asalvetti@masterbus.net",
    "SUPERVISOR OPERATIVO":                          "mdepeon@masterbus.net",
    "TALLER OLAV":                                   "asalvetti@masterbus.net",
}


# ─── Funciones auxiliares ────────────────────────────────────

def parse_fecha(fecha_str: str) -> Optional[date]:
    if not fecha_str or fecha_str.strip() in FECHAS_INVALIDAS:
        return None
    try:
        return datetime.strptime(fecha_str.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def cargar_notificados() -> dict:
    if NOTIFICADOS_FILE.exists():
        try:
            with open(NOTIFICADOS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("Error leyendo notificados.json, se reinicia: %s", e)
    return {}


def guardar_notificados(notificados: dict) -> None:
    with open(NOTIFICADOS_FILE, "w", encoding="utf-8") as f:
        json.dump(notificados, f, ensure_ascii=False, indent=2)
    logger.info("Registro de notificados actualizado (%d entradas)", len(notificados))


def fechafin_vacia(empleado: dict) -> bool:
    fechafin = empleado.get("fechafin")
    if fechafin is None:
        return True
    return fechafin.strip() in ("", "00/00/0000")


def fetch_empleados(api_url: str) -> List[Dict]:
    logger.info("Consultando API: %s", api_url)
    try:
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        empleados = response.json()
        logger.info("Empleados obtenidos de la API: %d", len(empleados))
        return empleados
    except requests.RequestException as e:
        logger.error("Error al consultar la API: %s", e)
        sys.exit(1)


def filtrar_empleados_mes5(
    empleados: List[Dict],
    notificados: Dict,
    dia_min: int,
    dia_max: int,
) -> List[Dict]:
    hoy = date.today()
    resultado = []

    for emp in empleados:
        if emp.get("activo") != "1":
            continue
        if not fechafin_vacia(emp):
            continue
        fechainicio = parse_fecha(emp.get("fechainicio", ""))
        if fechainicio is None:
            continue
        dias = (hoy - fechainicio).days
        if dias < dia_min or dias > dia_max:
            continue
        id_emp = emp.get("id_empleado", "")
        if id_emp in notificados:
            logger.debug("Empleado %s ya notificado, se omite", id_emp)
            continue
        emp["_dias_en_empresa"] = dias
        resultado.append(emp)

    return resultado


def agrupar_por_gerente(empleados: List[Dict]) -> Dict[str, List[Dict]]:
    """Agrupa empleados según el gerente responsable de su cargo."""
    grupos: Dict[str, List[Dict]] = defaultdict(list)
    sin_gerente = []

    for emp in empleados:
        cargo = emp.get("cargo", "").strip().upper()
        gerente = CARGO_GERENTE.get(cargo)
        if gerente:
            grupos[gerente].append(emp)
        else:
            logger.warning("Cargo sin gerente asignado: '%s' (empleado %s)", cargo, emp.get("id_empleado"))
            sin_gerente.append(emp)

    if sin_gerente:
        logger.warning("%d empleado(s) sin gerente asignado, no serán notificados.", len(sin_gerente))

    return dict(grupos)


def construir_email_html(empleados: List[Dict]) -> str:
    filas = ""
    for emp in empleados:
        filas += f"""
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd;">{emp.get('legajo', '-')}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{emp.get('apenom', '-')}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{emp.get('cargo', '-')}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{emp.get('empleador', '-')}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{emp.get('str', '-')}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{emp.get('fechainicio', '-')}</td>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{emp.get('_dias_en_empresa', '-')}</td>
        </tr>"""

    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #d35400;">⚠️ Alerta de Período de Prueba</h2>
        <p>Los siguientes <strong>{len(empleados)}</strong> empleado(s) a tu cargo están cumpliendo su
        <strong>5° mes</strong> de período de prueba y deben ser evaluados antes de que
        finalice el período de 6 meses:</p>

        <table style="border-collapse: collapse; width: 100%; font-size: 14px;">
            <thead>
                <tr style="background-color: #d35400; color: white;">
                    <th style="padding: 10px; border: 1px solid #ddd;">Legajo</th>
                    <th style="padding: 10px; border: 1px solid #ddd;">Nombre</th>
                    <th style="padding: 10px; border: 1px solid #ddd;">Cargo</th>
                    <th style="padding: 10px; border: 1px solid #ddd;">Empleador</th>
                    <th style="padding: 10px; border: 1px solid #ddd;">Operación</th>
                    <th style="padding: 10px; border: 1px solid #ddd;">Fecha Ingreso</th>
                    <th style="padding: 10px; border: 1px solid #ddd;">Días en Empresa</th>
                </tr>
            </thead>
            <tbody>
                {filas}
            </tbody>
        </table>

        <p style="margin-top: 20px; font-size: 12px; color: #888;">
            Este es un mensaje automático generado por el sistema de alertas de RRHH.<br>
            Fecha de ejecución: {datetime.now().strftime('%d/%m/%Y %H:%M')}
        </p>
    </body>
    </html>
    """


def enviar_email(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    smtp_use_tls: bool,
    destinatario: str,
    empleados: List[Dict],
) -> None:
    asunto = f"⚠️ Alerta Período de Prueba — {len(empleados)} empleado(s) a tu cargo en mes 5"
    cuerpo = construir_email_html(empleados)

    msg = MIMEMultipart("alternative")
    msg["From"]    = smtp_user
    msg["To"]      = destinatario
    msg["Subject"] = asunto
    msg.attach(MIMEText(cuerpo, "html", "utf-8"))

    try:
        if smtp_use_tls:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)

        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, [destinatario], msg.as_string())
        server.quit()
        logger.info("Email enviado a %s (%d empleados)", destinatario, len(empleados))
    except smtplib.SMTPException as e:
        logger.error("Error al enviar email a %s: %s", destinatario, e)
        raise


def imprimir_tabla_consola(empleados: List[Dict]) -> None:
    if not empleados:
        return
    print("\n" + "=" * 100)
    print(f"{'Legajo':<10} {'Nombre':<35} {'Cargo':<18} {'Empleador':<25} {'Ingreso':<12} {'Días':<5}")
    print("-" * 100)
    for emp in empleados:
        print(
            f"{emp.get('legajo', '-'):<10} "
            f"{emp.get('apenom', '-')[:34]:<35} "
            f"{emp.get('cargo', '-')[:17]:<18} "
            f"{emp.get('empleador', '-')[:24]:<25} "
            f"{emp.get('fechainicio', '-'):<12} "
            f"{emp.get('_dias_en_empresa', '-'):<5}"
        )
    print("=" * 100 + "\n")


# ─── Main ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Alerta de Período de Prueba — Detecta empleados en mes 5"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo muestra los empleados detectados, no envía email")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Inicio de ejecución — Alerta Período de Prueba")
    logger.info("Modo: %s", "DRY-RUN (sin envío de email)" if args.dry_run else "PRODUCCIÓN")

    from config import (
        MASTERBUS_API_URL as api_url,
        SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_USE_TLS,
        ALERTA_DIA_MIN as dia_min,
        ALERTA_DIA_MAX as dia_max,
    )

    # 1. Obtener empleados
    empleados = fetch_empleados(api_url)

    # 2. Cargar notificados previos
    notificados = cargar_notificados()
    logger.info("Empleados previamente notificados: %d", len(notificados))

    # 3. Filtrar empleados en mes 5
    alertas = filtrar_empleados_mes5(empleados, notificados, dia_min, dia_max)
    logger.info("Empleados nuevos en mes 5 detectados: %d", len(alertas))

    if not alertas:
        logger.info("No hay empleados nuevos para notificar. Fin de ejecución.")
        return

    # 4. Mostrar en consola
    imprimir_tabla_consola(alertas)

    # 5. Agrupar por gerente responsable
    grupos = agrupar_por_gerente(alertas)
    logger.info("Gerentes a notificar: %d", len(grupos))

    if args.dry_run:
        for gerente, emps in sorted(grupos.items()):
            logger.info("  [DRY-RUN] -> %s | %d empleado(s)", gerente, len(emps))
        logger.info("Modo DRY-RUN: no se envían emails ni se actualiza el registro.")
        return

    # 6. Enviar un email por gerente
    enviados_ok = []
    for gerente, emps in grupos.items():
        try:
            enviar_email(
                smtp_host=SMTP_HOST,
                smtp_port=SMTP_PORT,
                smtp_user=SMTP_USER,
                smtp_password=SMTP_PASSWORD,
                smtp_use_tls=SMTP_USE_TLS,
                destinatario=gerente,
                empleados=emps,
            )
            enviados_ok.extend(emps)
        except Exception:
            logger.error("Fallo el envío a %s. Sus empleados no se marcarán como notificados.", gerente)

    # 7. Registrar notificados solo de los emails exitosos
    if enviados_ok:
        fecha_hoy = datetime.now().strftime("%d/%m/%Y %H:%M")
        for emp in enviados_ok:
            notificados[emp["id_empleado"]] = {
                "apenom": emp.get("apenom", ""),
                "fechainicio": emp.get("fechainicio", ""),
                "fecha_notificacion": fecha_hoy,
            }
        guardar_notificados(notificados)

    logger.info("Ejecución completada. Emails enviados: %d/%d gerentes.", len(enviados_ok and grupos), len(grupos))


if __name__ == "__main__":
    main()
