"""Priority-queue segment scheduler using heapq (document section 15).

Tasks are ordered by ``(priority, deadline, sequence, segment_id)``:
lower priority value == more urgent, ties broken by earlier deadline.
"""

from __future__ import annotations

import heapq
import itertools
import threading
from dataclasses import dataclass


@dataclass(order=True)
class ScheduledTask:
    priority: float
    deadline: float
    sequence: int
    segment_id: int


class SegmentScheduler:
    """Thread-safe min-heap over (priority, deadline, segment_id)."""

    def __init__(self):
        self._heap: list[ScheduledTask] = []
        self._lock = threading.Lock()
        self._seq = itertools.count()

    def push(self, segment_id: int, priority: float, deadline: float) -> None:
        task = ScheduledTask(priority, deadline, next(self._seq), segment_id)
        with self._lock:
            heapq.heappush(self._heap, task)

    def pop(self) -> ScheduledTask | None:
        with self._lock:
            if not self._heap:
                return None
            return heapq.heappop(self._heap)

    def peek(self) -> ScheduledTask | None:
        with self._lock:
            return self._heap[0] if self._heap else None

    def __len__(self) -> int:
        with self._lock:
            return len(self._heap)
