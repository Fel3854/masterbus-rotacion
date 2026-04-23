#!/usr/bin/env python3
"""
Alerta de Período de Prueba — Empleados en Mes 5

Consume la API de empleados de MasterBus, detecta los que están
cumpliendo su 5° mes de período de prueba y envía una alerta
única por email a RRHH.

Uso:
    python main.py              # Ejecuta y envía emails
    python main.py --dry-run    # Solo muestra resultados, no envía
"""

import argparse
import json
import logging
import smtplib
import sys
from datetime import datetime, date
from typing import Dict, List, Optional
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

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


# ─── Funciones auxiliares ────────────────────────────────────

def parse_fecha(fecha_str: str) -> Optional[date]:
    """Parsea una fecha en formato dd/mm/yyyy. Retorna None si es inválida."""
    if not fecha_str or fecha_str.strip() in FECHAS_INVALIDAS:
        return None
    try:
        return datetime.strptime(fecha_str.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def cargar_notificados() -> dict:
    """Carga el registro de empleados ya notificados."""
    if NOTIFICADOS_FILE.exists():
        try:
            with open(NOTIFICADOS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("Error leyendo notificados.json, se reinicia: %s", e)
    return {}


def guardar_notificados(notificados: dict) -> None:
    """Guarda el registro de empleados notificados."""
    with open(NOTIFICADOS_FILE, "w", encoding="utf-8") as f:
        json.dump(notificados, f, ensure_ascii=False, indent=2)
    logger.info("Registro de notificados actualizado (%d entradas)", len(notificados))


def fechafin_vacia(empleado: dict) -> bool:
    """Verifica si el empleado no tiene fecha de fin (sigue activo en la empresa)."""
    fechafin = empleado.get("fechafin")
    if fechafin is None:
        return True
    fechafin = fechafin.strip()
    return fechafin in ("", "00/00/0000")


def fetch_empleados(api_url: str) -> List[Dict]:
    """Obtiene la lista de empleados desde la API de MasterBus."""
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
    """
    Filtra empleados que:
    - Están activos (activo == "1")
    - No tienen fecha de fin (siguen en la empresa)
    - Su fechainicio cae en el rango de mes 5 (dia_min a dia_max días)
    - No fueron notificados previamente
    """
    hoy = date.today()
    resultado = []

    for emp in empleados:
        # Filtro 1: activo
        if emp.get("activo") != "1":
            continue

        # Filtro 2: sin fecha de fin
        if not fechafin_vacia(emp):
            continue

        # Filtro 3: fecha de inicio válida
        fechainicio = parse_fecha(emp.get("fechainicio", ""))
        if fechainicio is None:
            continue

        # Filtro 4: rango de días (mes 5)
        dias = (hoy - fechainicio).days
        if dias < dia_min or dias > dia_max:
            continue

        # Filtro 5: no notificado previamente
        id_emp = emp.get("id_empleado", "")
        if id_emp in notificados:
            logger.debug("Empleado %s ya notificado, se omite", id_emp)
            continue

        emp["_dias_en_empresa"] = dias
        resultado.append(emp)

    return resultado


def construir_email_html(empleados: List[Dict]) -> str:
    """Construye el cuerpo HTML del email con la tabla de empleados."""
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

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #d35400;">⚠️ Alerta de Período de Prueba</h2>
        <p>Los siguientes <strong>{len(empleados)}</strong> empleado(s) están cumpliendo su
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
            Este es un mensaje automático generado por el sistema de alertas de RRHH.
            <br>Fecha de ejecución: {datetime.now().strftime('%d/%m/%Y %H:%M')}
        </p>
    </body>
    </html>
    """
    return html


def enviar_email(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    smtp_use_tls: bool,
    destinatario: str,
    asunto: str,
    cuerpo_html: str,
) -> None:
    """Envía un email HTML vía SMTP."""
    msg = MIMEMultipart("alternative")
    msg["From"] = smtp_user
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))

    try:
        if smtp_use_tls:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)

        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, destinatario, msg.as_string())
        server.quit()
        logger.info("Email enviado correctamente a %s", destinatario)
    except smtplib.SMTPException as e:
        logger.error("Error al enviar email: %s", e)
        raise


def imprimir_tabla_consola(empleados: List[Dict]) -> None:
    """Imprime una tabla formateada en consola para modo dry-run."""
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo muestra los empleados detectados, no envía email",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Inicio de ejecución — Alerta Período de Prueba")
    logger.info("Modo: %s", "DRY-RUN (sin envío de email)" if args.dry_run else "PRODUCCIÓN")

    # En modo dry-run no necesitamos las variables SMTP
    if args.dry_run:
        from dotenv import load_dotenv
        _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        load_dotenv(dotenv_path=_env_path)
        import os
        api_url = os.getenv(
            "MASTERBUS_API_URL",
            "https://traficonuevo.masterbus.net/api/v1/auto/e",
        )
        dia_min = int(os.getenv("ALERTA_DIA_MIN", "150"))
        dia_max = int(os.getenv("ALERTA_DIA_MAX", "180"))
    else:
        # Importar config completa (requiere SMTP configurado)
        from config import (
            MASTERBUS_API_URL as api_url,
            SMTP_HOST,
            SMTP_PORT,
            SMTP_USER,
            SMTP_PASSWORD,
            SMTP_USE_TLS,
            RRHH_EMAIL,
            ALERTA_DIA_MIN as dia_min,
            ALERTA_DIA_MAX as dia_max,
        )

    # 1. Obtener empleados de la API
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

    if args.dry_run:
        logger.info("Modo DRY-RUN: no se envía email ni se actualiza el registro.")
        return

    # 5. Construir y enviar email
    asunto = f"⚠️ Alerta Período de Prueba — {len(alertas)} empleado(s) en mes 5"
    cuerpo = construir_email_html(alertas)

    try:
        enviar_email(
            smtp_host=SMTP_HOST,
            smtp_port=SMTP_PORT,
            smtp_user=SMTP_USER,
            smtp_password=SMTP_PASSWORD,
            smtp_use_tls=SMTP_USE_TLS,
            destinatario=RRHH_EMAIL,
            asunto=asunto,
            cuerpo_html=cuerpo,
        )
    except Exception:
        logger.error("Fallo el envío del email. No se actualizan los notificados.")
        sys.exit(1)

    # 6. Registrar como notificados (solo si el email se envió OK)
    fecha_hoy = datetime.now().strftime("%d/%m/%Y %H:%M")
    for emp in alertas:
        notificados[emp["id_empleado"]] = {
            "apenom": emp.get("apenom", ""),
            "fechainicio": emp.get("fechainicio", ""),
            "fecha_notificacion": fecha_hoy,
        }

    guardar_notificados(notificados)
    logger.info("Ejecución completada exitosamente.")


if __name__ == "__main__":
    main()
