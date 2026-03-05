from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass
class QueuedTask:
    action: str
    payload: dict[str, Any]


class InMemoryRequestQueue:
    """Thread-safe in-memory FIFO queue for deferred client calls."""

    def __init__(self) -> None:
        self._items: deque[QueuedTask] = deque()
        self._lock = Lock()

    def enqueue(self, task: QueuedTask) -> int:
        with self._lock:
            self._items.append(task)
            return len(self._items)

    def dequeue(self) -> QueuedTask | None:
        with self._lock:
            if not self._items:
                return None
            return self._items.popleft()

    def size(self) -> int:
        with self._lock:
            return len(self._items)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
