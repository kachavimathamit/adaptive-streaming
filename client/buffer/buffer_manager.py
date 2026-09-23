"""Thread-safe FIFO playback buffer (document sections 9-10).

    collections.deque + threading.Lock + threading.Condition

Producer (downloader thread)  -> put()
Consumer (playback thread)    -> get()

Buffer occupancy:  B(t) = sum of duration(C_i) over buffered segments.

``put`` blocks while the buffer would exceed ``max_seconds`` (buffer-full
condition); ``get`` blocks while the buffer is empty (buffer-empty
condition).
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BufferedSegment:
    segment_id: int
    representation: str
    bitrate: int
    duration: float
    size: int
    received_at: float = field(default_factory=time.time)


class BufferManager:
    def __init__(self, max_seconds: float = 60.0):
        if max_seconds <= 0:
            raise ValueError("max_seconds must be positive")
        self.max_seconds = max_seconds
        self._deque: deque[BufferedSegment] = deque()
        self._level = 0.0          # seconds buffered
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._not_full = threading.Condition(self._lock)
        self.dropped = 0

    # -- producer side --------------------------------------------------
    def put(self, segment: BufferedSegment, timeout: float | None = None) -> bool:
        """Add a segment; block while the buffer is full.

        Returns False if the timeout elapsed before space was available.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._not_full:
            while self._level + segment.duration > self.max_seconds:
                remaining = None
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        self.dropped += 1
                        return False
                self._not_full.wait(remaining)
            self._deque.append(segment)
            self._level += segment.duration
            self._not_empty.notify()
        return True

    # -- consumer side --------------------------------------------------
    def get(self, timeout: float | None = None) -> BufferedSegment | None:
        """Remove the oldest segment; return None on timeout if empty."""
        with self._not_empty:
            if not self._deque:
                self._not_empty.wait(timeout)
                if not self._deque:
                    return None
            segment = self._deque.popleft()
            self._level -= segment.duration
            if self._level < 0:
                self._level = 0.0
            self._not_full.notify()
            return segment

    # -- inspection -----------------------------------------------------
    @property
    def level(self) -> float:
        """B(t): total playable duration currently held by the client."""
        with self._lock:
            return self._level

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._deque)

    @property
    def empty(self) -> bool:
        with self._lock:
            return not self._deque

    def snapshot(self) -> list[BufferedSegment]:
        with self._lock:
            return list(self._deque)
