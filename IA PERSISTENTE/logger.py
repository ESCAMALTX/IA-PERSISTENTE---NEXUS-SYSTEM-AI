"""Utilidades de registro: escribe en SQLite y emite el log al bus en vivo."""
from __future__ import annotations

import logging
import sys
from typing import Any

import database
from events import bus

_console = logging.getLogger("nexus")
if not _console.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s",
                                           "%H:%M:%S"))
    _console.addHandler(handler)
    _console.setLevel(logging.INFO)


def log(level: str, source: str, message: str) -> dict[str, Any]:
    entry = database.add_log(level, source, message)
    _console.info("[%s] %s", source, message)
    bus.publish({"type": "log", "data": entry})
    return entry


def info(source: str, message: str) -> dict[str, Any]:
    return log("INFO", source, message)


def warn(source: str, message: str) -> dict[str, Any]:
    return log("WARNING", source, message)


def error(source: str, message: str) -> dict[str, Any]:
    return log("ERROR", source, message)
