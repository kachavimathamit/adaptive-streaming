"""Network shaping fallback (document section 17).

The document recommends Linux ``tc`` + ``netem`` for realistic network
emulation.  When that is unavailable (e.g. Windows), this class applies
an equivalent client-side model: per-request latency plus a bandwidth
cap taken from an experiment profile JSON.

Profile format (experiments/*.json):

    {
      "name": "stable",
      "latency_ms": 20,
      "packet_loss": 0.0,
      "timeline": [{"t": 0, "mbps": 10}]
    }
"""

from __future__ import annotations

import json
import time
from pathlib import Path


class NetworkShaper:
    def __init__(self, profile: dict, clock=time.monotonic, sleeper=time.sleep):
        self.name = profile.get("name", "custom")
        self.latency_s = float(profile.get("latency_ms", 0)) / 1000.0
        self.packet_loss = float(profile.get("packet_loss", 0.0))
        timeline = profile.get("timeline", [{"t": 0, "mbps": 10}])
        # (start_time_seconds, bits_per_second), sorted by time
        self.timeline = sorted(
            ((float(step["t"]), float(step["mbps"]) * 1_000_000)
             for step in timeline),
            key=lambda s: s[0],
        )
        self._clock = clock
        self._sleep = sleeper
        self._start: float | None = None

    # ------------------------------------------------------------------
    @classmethod
    def from_file(cls, path: str | Path) -> "NetworkShaper":
        profile = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(profile)

    def start(self) -> None:
        """Anchor the profile timeline (idempotent: first call wins)."""
        if self._start is None:
            self._start = self._clock()

    def current_cap_bps(self) -> float | None:
        """Bandwidth cap in bits/s at the current session time."""
        if self._start is None:
            self.start()
        assert self._start is not None
        elapsed = self._clock() - self._start
        cap = self.timeline[0][1]
        for t, bps in self.timeline:
            if elapsed >= t:
                cap = bps
            else:
                break
        return cap

    # ------------------------------------------------------------------
    def apply_request_latency(self) -> None:
        """Impose configured one-way latency before a request goes out."""
        if self.latency_s > 0:
            self._sleep(self.latency_s)

    def apply_download_delay(self, num_bytes: int, elapsed: float) -> float:
        """Sleep so the observed throughput matches the profile cap.

        Returns the extra time slept.
        """
        cap = self.current_cap_bps()
        if not cap or cap <= 0:
            return 0.0
        required = (num_bytes * 8) / cap
        if elapsed < required:
            extra = required - elapsed
            self._sleep(extra)
            return extra
        return 0.0
