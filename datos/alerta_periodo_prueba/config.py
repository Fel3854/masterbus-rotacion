import os
import sys
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Cargar .env global desde la raíz de automatizaciones
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)


def get_env(key: str, default: Optional[str] = None, required: bool = True) -> str:
    """Obtiene una variable de entorno con validación."""
    value = os.getenv(key, default)
    if required and value is None:
        print(f"[ERROR] Variable de entorno requerida no encontrada: {key}")
        print(f"        Asegúrate de que exista en tu archivo .env")
        sys.exit(1)
    return value


# --- API ---
MASTERBUS_API_URL = get_env(
    "MASTERBUS_API_URL",
    default="https://traficonuevo.masterbus.net/api/v1/auto/e",
    required=False,
)

# --- SMTP ---
SMTP_HOST = get_env("SMTP_HOST")
SMTP_PORT = int(get_env("SMTP_PORT", default="587", required=False))
SMTP_USER = get_env("SMTP_USER")
SMTP_PASSWORD = get_env("SMTP_PASSWORD")
SMTP_USE_TLS = get_env("SMTP_USE_TLS", default="true", required=False).lower() == "true"

# --- Destinatario ---
RRHH_EMAIL = get_env("RRHH_EMAIL")

# --- Detección ---
# Rango en días para considerar "mes 5" del período de prueba
ALERTA_DIA_MIN = int(get_env("ALERTA_DIA_MIN", default="150", required=False))
ALERTA_DIA_MAX = int(get_env("ALERTA_DIA_MAX", default="180", required=False))
