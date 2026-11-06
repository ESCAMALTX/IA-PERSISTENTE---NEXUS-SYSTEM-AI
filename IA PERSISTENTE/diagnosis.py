"""Diagnóstico inteligente de incidentes mediante DeepSeek."""
from __future__ import annotations

import json
from typing import Any

import deepseek_client

DIAGNOSIS_PROMPT = (
    "Eres un ingeniero de sistemas experto en Windows. Recibes un incidente "
    "detectado automáticamente con sus métricas y procesos. Responde en español, "
    "en este formato exacto y sin nada más:\n"
    "CAUSA PROBABLE: <una frase>\n"
    "IMPACTO: <bajo|medio|alto>\n"
    "ACCIONES:\n1. <paso concreto>\n2. <paso concreto>\n3. <paso concreto>"
)


async def diagnose_incident(incident: dict[str, Any]) -> str:
    payload = json.dumps(
        {
            "tipo": incident["kind"],
            "severidad": incident["severity"],
            "mensaje": incident["message"],
            "detalles": incident.get("details"),
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )
    messages = [{"role": "user", "content": f"Diagnostica este incidente:\n\n{payload}"}]
    return await deepseek_client.chat(
        messages, temperature=0.2, system=DIAGNOSIS_PROMPT
    )


async def analyze_now() -> str:
    """Diagnóstico bajo demanda del estado actual del equipo."""
    import monitor as monitor_module
    snap = monitor_module.monitor.snapshot()
    tops = monitor_module.monitor.top_processes(8)
    payload = json.dumps(
        {"metricas_actuales": snap, "procesos_principales": tops},
        ensure_ascii=False, indent=2,
    )
    messages = [{"role": "user",
                 "content": f"Analiza el estado actual de este equipo:\n\n{payload}"}]
    return await deepseek_client.chat(messages, temperature=0.3)
