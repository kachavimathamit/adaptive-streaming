"""Buffer-Based ABR (BBA-0 style) - section 12.

Maps buffer occupancy B(t) onto the bitrate ladder using evenly spaced
thresholds between a reserve (low buffer) and a cap (high buffer):

    B <= reserve                 -> lowest bitrate
    B >= cap                     -> highest bitrate
    reserve < B < cap            -> first threshold c_i <= B
"""

from __future__ import annotations

from .base import ABRState, BaseABR


class BufferBasedABR(BaseABR):
    name = "buffer_based"

    def __init__(self, reserve: float = 6.0, buffer_cap: float = 30.0, **kwargs):
        super().__init__(**kwargs)
        if buffer_cap <= reserve:
            raise ValueError("buffer_cap must exceed reserve")
        self.reserve = reserve
        self.buffer_cap = buffer_cap
        n = self.n_levels
        # thresholds[i] = buffer level at which we move up to level i
        self.thresholds = [
            reserve + (self.buffer_cap - reserve) * i / (n - 1)
            for i in range(n)
        ]

    def select(self, state: ABRState) -> int:
        buffer_level = state.buffer_level
        if buffer_level <= self.reserve:
            return 0
        if buffer_level >= self.buffer_cap:
            return self.n_levels - 1
        idx = 0
        for i, threshold in enumerate(self.thresholds):
            if buffer_level >= threshold:
                idx = i
            else:
                break
        return idx
