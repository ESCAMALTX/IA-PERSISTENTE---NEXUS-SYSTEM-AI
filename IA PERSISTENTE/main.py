"""NEXUS SYSTEM AI - backend FastAPI con WebSockets."""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import config
import database
import deepseek_client
import diagnosis
import logger
import monitor as monitor_module
from events import bus

STATIC_DIR = config.BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    logger.info("NEXUS", "Sistema iniciado")
    if deepseek_client.is_configured():
        logger.info("NEXUS", f"DeepSeek configurado (modelo {config.DEEPSEEK_MODEL})")
    else:
        logger.warn("NEXUS", "DEEPSEEK_API_KEY ausente: la IA responderá en modo degradado")
    await monitor_module.monitor.start()
    try:
        yield
    finally:
        await monitor_module.monitor.stop()
        logger.info("NEXUS", "Sistema detenido")


app = FastAPI(title="NEXUS SYSTEM AI", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ------------------------------------------------------------- models
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: int | None = None


class ChatResponse(BaseModel):
    conversation_id: int
    reply: str


# ------------------------------------------------------------ routes
@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
async def status() -> dict[str, Any]:
    mon = monitor_module.monitor
    snap = mon.current or mon.snapshot()
    agents = [
        {"name": "DeepSeek AI", "state": "online" if deepseek_client.is_configured() else "sin clave",
         "detail": config.DEEPSEEK_MODEL},
        {"name": "Monitor de recursos", "state": "online", "detail": f"cada {config.MONITOR_INTERVAL}s"},
        {"name": "Registro de logs", "state": "online", "detail": "SQLite + WebSocket"},
        {"name": "Memoria persistente", "state": "online", "detail": str(config.DB_PATH.name)},
    ]
    stats = database.memory_stats()
    overall = "ok" if stats["open_incidents"] == 0 else "atencion"
    return {
        "overall": overall,
        "ai_configured": deepseek_client.is_configured(),
        "metrics": snap,
        "agents": agents,
        "memory": stats,
        "thresholds": {
            "cpu": config.CPU_ALERT_THRESHOLD,
            "ram": config.RAM_ALERT_THRESHOLD,
            "disk": config.DISK_ALERT_THRESHOLD,
        },
    }


@app.get("/api/metrics")
async def metrics() -> dict[str, Any]:
    mon = monitor_module.monitor
    return {
        "current": mon.current or mon.snapshot(),
        "history": list(mon.history),
        "top_processes": mon.top_processes(),
    }


@app.get("/api/logs")
async def logs(limit: int = 150) -> list[dict[str, Any]]:
    return database.recent_logs(limit=min(limit, 1000))


@app.get("/api/conversations")
async def conversations() -> dict[str, Any]:
    return {
        "conversations": database.list_conversations(),
        "latest": database.latest_conversation_id(),
    }


@app.get("/api/conversations/{conversation_id}")
async def conversation(conversation_id: int) -> dict[str, Any]:
    try:
        messages = database.get_messages(conversation_id)
    except Exception:  # noqa: BLE001
        messages = []
    if not messages:
        raise HTTPException(404, "Conversación no encontrada")
    return {"conversation_id": conversation_id, "messages": messages}


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int) -> dict[str, str]:
    database.delete_conversation(conversation_id)
    logger.info("MEMORIA", f"Conversación #{conversation_id} eliminada")
    return {"status": "deleted"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    conversation_id = req.conversation_id
    if conversation_id is None:
        conversation_id = database.create_conversation()
    database.add_message(conversation_id, "user", req.message)
    logger.info("CHAT", f"Usuario: {req.message[:120]}")

    history = database.get_messages(conversation_id, limit=config.HISTORY_WINDOW)
    messages = [{"role": m["role"], "content": m["content"]} for m in history]

    try:
        reply = await deepseek_client.chat(messages)
    except deepseek_client.DeepSeekError as exc:
        logger.error("IA", str(exc))
        raise HTTPException(503, str(exc)) from exc

    database.add_message(conversation_id, "assistant", reply)
    logger.info("CHAT", f"NEXUS: {reply[:120]}")
    return ChatResponse(conversation_id=conversation_id, reply=reply)


@app.get("/api/incidents")
async def incidents(limit: int = 100) -> list[dict[str, Any]]:
    return database.list_incidents(limit=min(limit, 500))


@app.post("/api/incidents/{incident_id}/diagnose")
async def diagnose_incident(incident_id: int) -> dict[str, Any]:
    items = {i["id"]: i for i in database.list_incidents(limit=500)}
    incident = items.get(incident_id)
    if incident is None:
        raise HTTPException(404, "Incidente no encontrado")
    try:
        text = await diagnosis.diagnose_incident(incident)
    except deepseek_client.DeepSeekError as exc:
        raise HTTPException(503, str(exc)) from exc
    database.set_incident_diagnosis(incident_id, text)
    logger.info("IA", f"Diagnóstico manual del incidente #{incident_id}")
    return {"id": incident_id, "diagnosis": text}


@app.post("/api/incidents/{incident_id}/resolve")
async def resolve(incident_id: int) -> dict[str, str]:
    database.resolve_incident(incident_id)
    bus.publish({"type": "incident_resolved", "data": {"id": incident_id}})
    return {"status": "resolved"}


@app.post("/api/analyze")
async def analyze() -> dict[str, str]:
    try:
        text = await diagnosis.analyze_now()
    except deepseek_client.DeepSeekError as exc:
        raise HTTPException(503, str(exc)) from exc
    database.create_incident("manual", "info", "Análisis manual del sistema",
                             diagnosis=text)
    logger.info("IA", "Análisis manual del sistema completado")
    return {"analysis": text}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    queue = bus.subscribe()
    mon = monitor_module.monitor
    try:
        await ws.send_text(json.dumps({
            "type": "init",
            "data": {
                "logs": database.recent_logs(80),
                "metrics": mon.current or mon.snapshot(),
                "history": list(mon.history)[-60:],
            },
        }, default=str))

        while True:
            event = await queue.get()
            await ws.send_text(json.dumps(event, default=str))
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.error("WS", f"WebSocket cerrado: {exc}")
    finally:
        bus.unsubscribe(queue)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
