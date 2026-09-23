"""Moving-average throughput estimator (baseline mentioned in section 11)."""

from __future__ import annotations

from collections import deque


class MovingAverage:
    def __init__(self, window: int = 5):
        if window < 1:
            raise ValueError("window must be >= 1")
        self.window = window
        self._samples: deque[float] = deque(maxlen=window)

    def update(self, throughput_bps: float) -> float:
        self._samples.append(throughput_bps)
        return self.value

    @property
    def value(self) -> float | None:
        if not self._samples:
            return None
        return sum(self._samples) / len(self._samples)
