"""Configuración central de NEXUS SYSTEM AI."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

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
