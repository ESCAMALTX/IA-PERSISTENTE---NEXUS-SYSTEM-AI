"""Configuración central de NEXUS SYSTEM AI."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# python-dotenv es opcional: en Docker las variables llegan por el entorno y la
# app debe arrancar aunque el paquete no esté instalado.
try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - solo en imágenes sin dotenv
    pass
else:
    load_dotenv(BASE_DIR / ".env", override=False)


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


DEEPSEEK_API_KEY = _env("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = _env("DEEPSEEK_MODEL", "deepseek-chat")

HOST = os.getenv("NEXUS_HOST", "127.0.0.1")
PORT = int(os.getenv("NEXUS_PORT", "8000"))

DATA_DIR = Path(os.getenv("NEXUS_DATA_DIR", BASE_DIR / "data"))
DB_PATH = DATA_DIR / "nexus.db"

# Umbrales de monitorización (%).
CPU_ALERT_THRESHOLD = float(os.getenv("CPU_ALERT_THRESHOLD", "85"))
RAM_ALERT_THRESHOLD = float(os.getenv("RAM_ALERT_THRESHOLD", "85"))
DISK_ALERT_THRESHOLD = float(os.getenv("DISK_ALERT_THRESHOLD", "90"))

MONITOR_INTERVAL = float(os.getenv("MONITOR_INTERVAL", "5"))
ALERT_COOLDOWN = float(os.getenv("ALERT_COOLDOWN", "120"))

# Número de mensajes de historial que se envían al modelo.
HISTORY_WINDOW = int(os.getenv("HISTORY_WINDOW", "20"))

SYSTEM_PROMPT = (
    "Eres NEXUS, un asistente de IA que supervisa un computador Windows. "
    "Respondes en español, de forma clara y breve. Cuando se te pasan métricas "
    "del sistema (CPU, RAM, disco) o logs, los analizas y propones acciones "
    "concretas. Si no tienes datos suficientes, lo dices en lugar de inventar."
)

DATA_DIR.mkdir(parents=True, exist_ok=True)
