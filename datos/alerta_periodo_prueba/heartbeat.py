"""
heartbeat.py — reporta la "ultima corrida" de este batch al dashboard-control (Fase 3).

Best-effort: si falta GH_TOKEN o la API falla, SOLO loguea un warning y NO interrumpe el
batch. El dashboard, si no recibe señal en `max_silencio_horas`, marca "Rotacion" como caido.

Token: agrega GH_TOKEN a automatizaciones/.env (un PAT fine-grained con permiso
Contents: Read and write SOLO sobre el repo del dashboard). Nunca se commitea.
"""

import base64
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

# El .env vive en la raiz de automatizaciones (mismo que usa config.py).
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

logger = logging.getLogger(__name__)

REPO = os.getenv("HEARTBEAT_REPO", "Fel3854/dashboard-control")
BRANCH = os.getenv("HEARTBEAT_BRANCH", "main")
API = "https://api.github.com"


def reportar_heartbeat(ok: bool = True, slug: str = "rotacion") -> bool:
    """
    Sube heartbeats/<slug>.json al repo del dashboard via la Contents API.
    Devuelve True si reporto, False si lo omitio o fallo (sin lanzar excepciones).
    """
    token = os.getenv("GH_TOKEN")
    if not token:
        logger.warning("Heartbeat omitido: falta GH_TOKEN en el .env (no se reporta al dashboard).")
        return False

    url = f"{API}/repos/{REPO}/contents/heartbeats/{slug}.json"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    cuerpo = json.dumps(
        {
            "ultima_corrida": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "ok": ok,
        },
        indent=2,
    )

    try:
        # La Contents API exige el `sha` del archivo si ya existe.
        sha = None
        r = requests.get(url, headers=headers, params={"ref": BRANCH}, timeout=15)
        if r.status_code == 200:
            sha = r.json().get("sha")

        payload = {
            "message": f"heartbeat: {slug} {'OK' if ok else 'FAIL'} [skip ci]",
            "content": base64.b64encode(cuerpo.encode()).decode(),
            "branch": BRANCH,
        }
        if sha:
            payload["sha"] = sha

        resp = requests.put(url, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        logger.info("Heartbeat reportado al dashboard (ok=%s).", ok)
        return True
    except Exception as e:  # nunca debe tumbar el batch
        logger.warning("No se pudo reportar el heartbeat (no es critico): %s", e)
        return False
