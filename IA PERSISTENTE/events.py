"""Bus de eventos en memoria para WebSockets (logs en vivo y métricas)."""
from __future__ import annotations

import asyncio
from collections import deque
from typing import Any


class EventBus:
    def __init__(self, max_queue: int = 500) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._max = max_queue
        self._recent: deque[dict[str, Any]] = deque(maxlen=200)

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self._max)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(q)

    def publish(self, event: dict[str, Any]) -> None:
        self._recent.append(event)
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # el cliente está saturado; descartamos el evento

    @property
    def recent(self) -> list[dict[str, Any]]:
        return list(self._recent)


bus = EventBus()
