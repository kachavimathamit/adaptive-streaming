"""Playback controller (document section 9).

Consumer thread of the producer-consumer pair:

    downloader thread -> buffer_manager.put(segment)
    playback thread   -> buffer_manager.get() -> consume

When the buffer is empty while playback is active the waiting time is
recorded as rebuffering.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from ..buffer.buffer_manager import BufferManager, BufferedSegment


@dataclass
class PlaybackReport:
    segments_played: int = 0
    startup_delay: float = 0.0          # time until first frame
    rebuffer_seconds: float = 0.0       # stalls after playback started
    rebuffer_events: list[tuple[float, float, int]] = field(default_factory=list)
    # each event: (start_offset_from_session, duration, segment_id)
    last_segment: int = 0


class PlaybackController(threading.Thread):
    def __init__(self, buffer_manager: BufferManager, total_segments: int,
                 speed: float = 1.0, session_start: float | None = None,
                 name: str = "playback"):
        super().__init__(name=name, daemon=True)
        self.buffer_manager = buffer_manager
        self.total_segments = total_segments
        self.speed = max(speed, 1e-6)
        self.session_start = time.monotonic() if session_start is None else session_start
        self.report = PlaybackReport()
        self._finished = threading.Event()

    # ------------------------------------------------------------------
    def run(self) -> None:
        # --- startup: wait for the first segment -----------------------
        t0 = time.monotonic()
        first = self._wait_for_segment(timeout=600.0)
        if first is None:
            return
        self.report.startup_delay = time.monotonic() - t0
        self._consume(first)

        # --- steady state ---------------------------------------------
        while self.report.segments_played < self.total_segments:
            seg = self.buffer_manager.get(timeout=0.05)
            if seg is None:
                # Buffer is empty while playback should be running:
                # this waiting time is rebuffering.
                stall_start = time.monotonic()
                seg = self._wait_for_segment(timeout=600.0)
                if seg is None:
                    break
                stall = time.monotonic() - stall_start
                if stall > 0.02:
                    self.report.rebuffer_seconds += stall
                    self.report.rebuffer_events.append(
                        (stall_start - self.session_start, stall, seg.segment_id)
                    )
                self._consume(seg)
                continue
            self._consume(seg)
        self._finished.set()

    # ------------------------------------------------------------------
    def _wait_for_segment(self, timeout: float) -> BufferedSegment | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            seg = self.buffer_manager.get(timeout=0.1)
            if seg is not None:
                return seg
        return None

    def _consume(self, segment: BufferedSegment) -> None:
        self.report.segments_played += 1
        self.report.last_segment = segment.segment_id
        # Simulated real-time playback of this segment's duration.
        time.sleep(segment.duration / self.speed)

    # ------------------------------------------------------------------
    def join_session(self, timeout: float | None = None) -> PlaybackReport:
        self.join(timeout=timeout)
        return self.report
