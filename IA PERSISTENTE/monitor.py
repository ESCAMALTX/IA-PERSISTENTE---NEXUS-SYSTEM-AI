"""Monitor de recursos Windows (CPU, RAM, disco) e historial en memoria."""
from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Any

import psutil

import config
import database
import logger
from events import bus

HISTORY_SIZE = 120  # ~10 minutos con intervalo de 5 s


class Monitor:
    def __init__(self) -> None:
        self.history: deque[dict[str, Any]] = deque(maxlen=HISTORY_SIZE)
        self.current: dict[str, Any] | None = None
        self._last_alert: dict[str, float] = {}
        self._tasks: list[asyncio.Task[Any]] = []
        self._running = False
        psutil.cpu_percent(interval=None)  # primer muestreo de referencia

    # ----------------------------------------------------------- metrics
    def snapshot(self) -> dict[str, Any]:
        mem = psutil.virtual_memory()
        try:
            disk = psutil.disk_usage("C:\\")
        except OSError:
            disk = psutil.disk_usage("/")
        boot = psutil.boot_time()
        net = psutil.net_io_counters()
        data = {
            "ts": time.time(),
            "cpu_percent": round(psutil.cpu_percent(interval=None), 1),
            "cpu_cores": psutil.cpu_count(logical=True),
            "ram_percent": round(mem.percent, 1),
            "ram_used_gb": round(mem.used / 1024**3, 2),
            "ram_total_gb": round(mem.total / 1024**3, 2),
            "disk_percent": round(disk.percent, 1),
            "disk_used_gb": round(disk.used / 1024**3, 2),
            "disk_total_gb": round(disk.total / 1024**3, 2),
            "uptime_hours": round((time.time() - boot) / 3600, 1),
            "processes": len(psutil.pids()),
            "net_sent_mb": round(net.bytes_sent / 1024**2, 1),
            "net_recv_mb": round(net.bytes_recv / 1024**2, 1),
            "platform": psutil.os.name,
        }
        return data

    def top_processes(self, limit: int = 5) -> list[dict[str, Any]]:
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                info = p.info
                name = info["name"] or ""
                if info["pid"] == 0 or name.lower() == "system idle process":
                    continue
                procs.append({
                    "pid": info["pid"],
                    "name": name,
                    "cpu_percent": round(info["cpu_percent"] or 0.0, 1),
                    "memory_percent": round(info["memory_percent"] or 0.0, 1),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        procs.sort(key=lambda x: (x["cpu_percent"], x["memory_percent"]), reverse=True)
        return procs[:limit]

    # ------------------------------------------------------------- loop
    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._tasks.append(asyncio.create_task(self._loop(), name="nexus-monitor"))
        logger.info("MONITOR", f"Monitor iniciado (intervalo {config.MONITOR_INTERVAL}s)")

    async def stop(self) -> None:
        self._running = False
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()

    async def _loop(self) -> None:
        while self._running:
            try:
                snap = self.snapshot()
                self.current = snap
                self.history.append(snap)
                bus.publish({"type": "metrics", "data": snap})
                await self._check_thresholds(snap)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - el monitor nunca debe morir
                logger.error("MONITOR", f"Error en muestreo: {exc}")
            await asyncio.sleep(config.MONITOR_INTERVAL)

    # ---------------------------------------------------------- alerts
    async def _check_thresholds(self, snap: dict[str, Any]) -> None:
        checks = [
            ("cpu", snap["cpu_percent"], config.CPU_ALERT_THRESHOLD,
             f"CPU al {snap['cpu_percent']}%"),
            ("ram", snap["ram_percent"], config.RAM_ALERT_THRESHOLD,
             f"RAM al {snap['ram_percent']}% ({snap['ram_used_gb']}/{snap['ram_total_gb']} GB)"),
            ("disk", snap["disk_percent"], config.DISK_ALERT_THRESHOLD,
             f"Disco al {snap['disk_percent']}% ({snap['disk_used_gb']}/{snap['disk_total_gb']} GB)"),
        ]
        for kind, value, threshold, message in checks:
            # Comparamos contra el umbral con > 0.01 de margen para evitar parpadeos.
            if value >= threshold:
                self._maybe_raise(kind, snap, message)
            else:
                self._clear_incident(kind)

    def _maybe_raise(self, kind: str, snap: dict[str, Any], message: str) -> None:
        """Mantiene un incidente abierto por recurso y evita ráfagas de alertas.

        La comprobación y la inserción son síncronas (mismo tick del event loop), así
        que nunca se crean dos incidentes abiertos para el mismo recurso. Si se cierra
        un incidente y el valor vuelve a subir, se respeta el enfriamiento para no
        llenar el historial con el mismo problema.
        """
        severity = self._severity(kind, snap)
        last = database.last_incident_of(kind)

        if last and last["status"] == "open":
            if last["severity"] != severity:
                database.resolve_incident(last["id"])
                bus.publish({"type": "incident_resolved", "data": {"id": last["id"]}})
            else:
                return

        elapsed = time.time() - self._last_alert.get(kind, 0.0)
        if elapsed < config.ALERT_COOLDOWN:
            return

        incident = database.create_incident(
            kind, severity, message,
            {"metrics": snap, "top_processes": self.top_processes()},
        )
        self._last_alert[kind] = time.time()
        logger.warn("ALERTA", f"[{severity}] {message}")
        bus.publish({"type": "incident", "data": incident})
        asyncio.create_task(self._diagnose(incident), name=f"diag-{incident['id']}")

    @staticmethod
    def _severity(kind: str, snap: dict[str, Any]) -> str:
        if (kind == "cpu" and snap["cpu_percent"] >= 95) \
                or (kind == "ram" and snap["ram_percent"] >= 95) \
                or (kind == "disk" and snap["disk_percent"] >= 97):
            return "critical"
        return "warning"

    def _clear_incident(self, kind: str) -> None:
        last = database.last_incident_of(kind)
        if last and last["status"] == "open":
            database.resolve_incident(last["id"])
            logger.info("ALERTA", f"Incidente #{last['id']} ({kind}) resuelto: valores normalizados")
            bus.publish({"type": "incident_resolved", "data": {"id": last["id"]}})

    async def _diagnose(self, incident: dict[str, Any]) -> None:
        """Pide a DeepSeek un diagnóstico del incidente y lo guarda."""
        import diagnosis
        import deepseek_client

        if not deepseek_client.is_configured():
            note = ("Diagnóstico automático no disponible: configura DEEPSEEK_API_KEY "
                    "en el archivo .env para que NEXUS analice los incidentes con IA.")
            database.set_incident_diagnosis(incident["id"], note)
            return

        try:
            text = await diagnosis.diagnose_incident(incident)
            database.set_incident_diagnosis(incident["id"], text)
            logger.info("IA", f"Diagnóstico generado para el incidente #{incident['id']}")
            bus.publish({"type": "diagnosis",
                         "data": {"id": incident["id"], "diagnosis": text}})
        except Exception as exc:  # noqa: BLE001
            logger.error("IA", f"No se pudo diagnosticar el incidente #{incident['id']}: {exc}")


monitor = Monitor()
