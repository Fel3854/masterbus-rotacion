#!/usr/bin/env python3
"""
Test de disparo de emails a gerentes responsables por cargo.

Envía un email individual a cada gerente del mapeo cargo→email,
solicitando que respondan con "OK" para confirmar recepción.
CC: masterbusdev@gmail.com

Uso:
    python test_disparo_gerentes.py              # Envía emails reales
    python test_disparo_gerentes.py --dry-run    # Solo muestra sin enviar
"""

import argparse
import logging
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
import os

# ─── Config ─────────────────────────────────────────────────
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

SMTP_HOST     = os.getenv("SMTP_HOST", "")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS  = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

CC_EMAIL = "talcantara@masterbus.net"

# ─── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ─── Mapeo cargo → email gerente ────────────────────────────
CARGO_GERENTE = {
    "ACTIVADOR":                                    "jcabral@masterbus.net",
    "ADMINISTRADOR DE COORDINACION IT":             "icarvajal@masterbus.net",
    "ADMINISTRATIVO":                               "dscirocco@masterbus.net",
    "ASISTENTE ADM DE INTENDENCIA":                 "ellanos@masterbus.net",
    "ASISTENTE ADM. DE RRHH":                       "ffillopski@masterbus.net",
    "ASISTENTE ADMINISTRATIVO DE PAÃOL":            "jcabral@masterbus.net",
    "ASISTENTE ADMINISTRATIVO DE SEGURIDAD VIAL":   "jcigna@masterbus.net",
    "ASISTENTE ADMINISTRATIVO DE TALLER":           "asalvetti@masterbus.net",
    "ASISTENTE BALANCE Y DOCUMENTACION DE BANCOS":  "dscirocco@masterbus.net",
    "ASISTENTE CONTABLE":                           "dscirocco@masterbus.net",
    "ASISTENTE DE ABASTECIMIENTO":                  "jcabral@masterbus.net",
    "ASISTENTE DE GESTION":                         "dscirocco@masterbus.net",
    "ASISTENTE DE LICITACIONES":                    "dscirocco@masterbus.net",
    "ASISTENTE DE NORMAS ISO":                      "talcantara@masterbus.net",
    "ASISTENTE DE SEGURIDAD INDUSTRIAL Y AMBIENTE": "talcantara@masterbus.net",
    "ASISTENTE OPERATIVO":                          "mdepeon@masterbus.net",
    "ASISTENTE OPERATIVO DE SEGURIDAD VIAL":        "jcigna@masterbus.net",
    "BRIGADISTA":                                   "talcantara@masterbus.net",
    "CADETE":                                       "dscirocco@masterbus.net",
    "CELADOR":                                      "mdepeon@masterbus.net",
    "CHAPISTA":                                     "asalvetti@masterbus.net",
    "CHAPISTA (SALTA/CAT)":                         "asalvetti@masterbus.net",
    "CONDUCTOR":                                    "mdepeon@masterbus.net",
    "CONTRATISTAS":                                 "mdepeon@masterbus.net",
    "COORDINADOR DE BASES":                         "asalvetti@masterbus.net",
    "COORDINADOR DE IT FLOTA":                      "icarvajal@masterbus.net",
    "DESPACHANTE DE COMBUSTIBLE":                   "ellanos@masterbus.net",
    "DIAGRAMADOR DE TRAFICO":                       "mdepeon@masterbus.net",
    "ELECTRICISTA":                                 "asalvetti@masterbus.net",
    "ELECTRICISTA (SALTA/CAT)":                     "asalvetti@masterbus.net",
    "EMPLEADO PANIOL":                              "jcabral@masterbus.net",
    "ENCARGADO DE CUENTAS A PAGAR":                 "dscirocco@masterbus.net",
    "ENCARGADO DE FACTURACION":                     "dscirocco@masterbus.net",
    "ENCARGADO DE TESORERIA":                       "dscirocco@masterbus.net",
    "ENCARGADO IMPOSITIVO":                         "dscirocco@masterbus.net",
    "FORMADORES":                                   "jcigna@masterbus.net",
    "LAVADOR":                                      "ellanos@masterbus.net",
    "LIDER DE PAÃOL":                               "jcabral@masterbus.net",
    "LIQUIDADOR DE SUELDOS - GESTION DOC. EMPRESAS":"ffillopski@masterbus.net",
    "MAESTRANZA":                                   "ellanos@masterbus.net",
    "MAESTRANZA OLAV":                              "ellanos@masterbus.net",
    "MECANICO":                                     "asalvetti@masterbus.net",
    "MECANICO (SALTA/CAT)":                         "asalvetti@masterbus.net",
    "OPERADOR":                                     "mdepeon@masterbus.net",
    "PAÃOLERO":                                     "jcabral@masterbus.net",
    "PROGRAMADOR OPERATIVO":                        "mdepeon@masterbus.net",
    "PROGRAMADOR/DESARROLLO":                       "mdepeon@masterbus.net",
    "RECEPCION":                                    "dscirocco@masterbus.net",
    "SEGURIDAD VIAL Y CAPACITACIONES":              "jcigna@masterbus.net",
    "SOPORTE ON SITE IT FLOTA":                     "icarvajal@masterbus.net",
    "SUPERVISOR ADM DE CARROCERIA":                 "asalvetti@masterbus.net",
    "SUPERVISOR DE CHAPA Y PINTURA":                "asalvetti@masterbus.net",
    "SUPERVISOR DE ELECTRICISTAS":                  "asalvetti@masterbus.net",
    "SUPERVISOR DE OPERACIONES DE TALLER":          "asalvetti@masterbus.net",
    "SUPERVISOR DE PLANTA":                         "mdepeon@masterbus.net",
    "SUPERVISOR DE PLAYA":                          "ellanos@masterbus.net",
    "SUPERVISOR DE SUPERVISORES":                   "mdepeon@masterbus.net",
    "SUPERVISOR DE TALLER":                         "asalvetti@masterbus.net",
    "SUPERVISOR GENERAL":                           "asalvetti@masterbus.net",
    "SUPERVISOR OPERATIVO":                         "mdepeon@masterbus.net",
    "TALLER OLAV":                                  "asalvetti@masterbus.net",
}

# ─── Cargos por gerente (para el cuerpo del email) ──────────
def cargos_por_gerente() -> dict[str, list[str]]:
    agrupado: dict[str, list[str]] = {}
    for cargo, email in CARGO_GERENTE.items():
        agrupado.setdefault(email, []).append(cargo)
    return agrupado


def construir_html(gerente_email: str, cargos: list[str]) -> str:
    filas = "".join(
        f'<tr><td style="padding:6px 12px; border:1px solid #ddd;">{c}</td></tr>'
        for c in sorted(cargos)
    )
    return f"""
<html>
<body style="font-family: Arial, sans-serif; color: #333; font-size: 14px;">
  <p>Hola,</p>
  <p>Este es un <strong>email de prueba</strong> del sistema automático de alertas de RRHH.</p>
  <p>Te llegará aquí cada vez que un empleado de los cargos a tu cargo esté próximo a cumplir
     el período de prueba de 6 meses.</p>
  <p>Los cargos asignados a tu dirección (<strong>{gerente_email}</strong>) son:</p>
  <table style="border-collapse:collapse; font-size:13px;">
    <thead>
      <tr style="background:#1a4a8a; color:white;">
        <th style="padding:8px 12px; border:1px solid #ddd;">Cargo</th>
      </tr>
    </thead>
    <tbody>{filas}</tbody>
  </table>
  <p style="margin-top:20px;">
    <strong>Por favor, respondé este email con la palabra <span style="color:#c0392b;">OK</span>
    para confirmar que lo recibiste correctamente.</strong>
  </p>
  <p style="font-size:12px; color:#888; margin-top:30px;">
    Mensaje automático generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} — Sistema de Alertas RRHH MasterBus
  </p>
</body>
</html>
"""


def enviar_email(destinatario: str, cargos: list[str], dry_run: bool) -> bool:
    asunto = "[TEST] Confirmación de recepción — Sistema de Alertas RRHH"
    cuerpo = construir_html(destinatario, cargos)

    if dry_run:
        logger.info("  [DRY-RUN] Para: %s | Cargos: %d | CC: %s", destinatario, len(cargos), CC_EMAIL)
        return True

    msg = MIMEMultipart("alternative")
    msg["From"]    = SMTP_USER
    msg["To"]      = destinatario
    msg["Cc"]      = CC_EMAIL
    msg["Subject"] = asunto
    msg.attach(MIMEText(cuerpo, "html", "utf-8"))

    todos = [destinatario, CC_EMAIL]
    try:
        if SMTP_USE_TLS:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)

        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, todos, msg.as_string())
        server.quit()
        logger.info("  ✓ Enviado a %s (CC: %s)", destinatario, CC_EMAIL)
        return True
    except smtplib.SMTPException as e:
        logger.error("  ✗ Error enviando a %s: %s", destinatario, e)
        return False


def main():
    parser = argparse.ArgumentParser(description="Disparo de test a gerentes")
    parser.add_argument("--dry-run", action="store_true", help="Simula sin enviar")
    args = parser.parse_args()

    if not args.dry_run:
        faltantes = [v for k, v in [
            ("SMTP_HOST", SMTP_HOST),
            ("SMTP_USER", SMTP_USER),
            ("SMTP_PASSWORD", SMTP_PASSWORD),
        ] if not v]
        if faltantes:
            logger.error("Configurar en .env: SMTP_HOST, SMTP_USER, SMTP_PASSWORD")
            sys.exit(1)

    modo = "DRY-RUN" if args.dry_run else "PRODUCCIÓN"
    logger.info("=" * 60)
    logger.info("Test de disparo a gerentes — Modo: %s", modo)
    logger.info("=" * 60)

    agrupado = cargos_por_gerente()
    ok = err = 0

    for email, cargos in sorted(agrupado.items()):
        if enviar_email(email, cargos, args.dry_run):
            ok += 1
        else:
            err += 1

    logger.info("-" * 60)
    logger.info("Resultado: %d enviados, %d errores (de %d gerentes)", ok, err, ok + err)


if __name__ == "__main__":
    main()
