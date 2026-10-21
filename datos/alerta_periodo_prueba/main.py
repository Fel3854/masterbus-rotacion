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


# ─── Funciones auxiliares ────────────────────────────────────

def fetch_cargo_gerente(supabase_url: str, supabase_key: str) -> Dict[str, str]:
    """Carga el mapeo cargo → email de gerente desde Supabase (tabla gerentes_cargo)."""
    url = f"{supabase_url}/rest/v1/gerentes_cargo?select=cargo,email_gerente"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    mapping = {row["cargo"]: row["email_gerente"] for row in data}
    logger.info("Mapeo cargo→gerente cargado desde Supabase: %d entradas", len(mapping))
    return mapping


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
    intentos = 3
    for intento in range(1, intentos + 1):
        try:
            response = requests.get(api_url, timeout=30)
            response.raise_for_status()
            empleados = response.json()
            logger.info("Empleados obtenidos de la API: %d", len(empleados))
            return empleados
        except requests.RequestException as e:
            logger.warning("Intento %d/%d fallido al consultar la API: %s", intento, intentos, e)
            if intento < intentos:
                import time
                time.sleep(2 ** intento)  # backoff: 2s, 4s
    logger.error("No se pudo conectar a la API tras %d intentos.", intentos)
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


def agrupar_por_gerente(empleados: List[Dict], cargo_gerente: Dict[str, str]) -> Dict[str, List[Dict]]:
    """Agrupa empleados según el gerente responsable de su cargo."""
    grupos: Dict[str, List[Dict]] = defaultdict(list)
    sin_gerente = []

    for emp in empleados:
        cargo = emp.get("cargo", "").strip().upper()
        gerente = cargo_gerente.get(cargo)
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

        <p style="margin-top: 20px; color: #333;">
            Por favor, <strong>contactate con Recursos Humanos</strong> para comunicarle
            la decisión respecto a cada empleado antes de que venza el período de prueba.
        </p>

        <p style="margin-top: 16px; font-size: 12px; color: #888;">
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

    intentos = 3
    for intento in range(1, intentos + 1):
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
            return
        except smtplib.SMTPException as e:
            logger.warning("Intento %d/%d fallido al enviar email a %s: %s", intento, intentos, destinatario, e)
            if intento < intentos:
                import time
                time.sleep(5)
    logger.error("No se pudo enviar email a %s tras %d intentos.", destinatario, intentos)
    raise smtplib.SMTPException(f"Fallo definitivo al enviar a {destinatario}")


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
        SUPABASE_URL, SUPABASE_KEY,
    )

    # 1. Cargar mapeo cargo → gerente desde Supabase
    try:
        cargo_gerente = fetch_cargo_gerente(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        logger.error("No se pudo cargar el mapeo cargo→gerente desde Supabase: %s", e)
        sys.exit(1)

    # 2. Obtener empleados
    empleados = fetch_empleados(api_url)

    # 3. Cargar notificados previos
    notificados = cargar_notificados()
    logger.info("Empleados previamente notificados: %d", len(notificados))

    # 4. Filtrar empleados en mes 5
    alertas = filtrar_empleados_mes5(empleados, notificados, dia_min, dia_max)
    logger.info("Empleados nuevos en mes 5 detectados: %d", len(alertas))

    if not alertas:
        logger.info("No hay empleados nuevos para notificar. Fin de ejecución.")
        return

    # 5. Mostrar en consola
    imprimir_tabla_consola(alertas)

    # 6. Agrupar por gerente responsable
    grupos = agrupar_por_gerente(alertas, cargo_gerente)
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

    emails_ok = len(grupos) > 0 and len(enviados_ok) > 0
    logger.info("Ejecución completada. Emails enviados: %d/%d gerentes.", len(grupos) if emails_ok else 0, len(grupos))

    if grupos and not emails_ok:
        logger.error("No se pudo enviar ningún email. Revisá las credenciales SMTP.")
        sys.exit(1)


if __name__ == "__main__":
    # Heartbeat al dashboard-control (Fase 3): reporta que el batch corrio.
    # Solo en corridas reales (no --dry-run). Best-effort: nunca rompe el batch.
    es_dry = "--dry-run" in sys.argv
    exito = True
    try:
        main()
    except SystemExit as e:
        exito = e.code in (0, None)
        raise
    except Exception:
        exito = False
        raise
    finally:
        if not es_dry:
            try:
                from heartbeat import reportar_heartbeat
                reportar_heartbeat(ok=exito)
            except Exception:
                pass
