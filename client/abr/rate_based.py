"""Rate-Based ABR (baseline): pick the highest bitrate the smoothed
throughput estimate can support with a safety margin (section 12)."""

from __future__ import annotations

from .base import ABRState, BaseABR


class RateBasedABR(BaseABR):
    name = "rate_based"

    def __init__(self, safety: float = 0.85, **kwargs):
        super().__init__(**kwargs)
        self.safety = safety

    def select(self, state: ABRState) -> int:
        throughput = state.throughput_bps or self.bitrate(0)
        return self.highest_fitting(throughput, safety=self.safety)
