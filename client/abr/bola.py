"""BOLA - Buffer-Oriented Adaptive bitrate logic (sections 12-13).

Simplified educational BOLA-basic: each representation gets an
"energy" score V * utility and the current buffer level acts as the
cost barrier:

    score_i = V * u_i - B(t)

The selected representation is the lowest one whose score is still
non-negative (i.e. its utility covers the buffer cost), clamped by the
classic BOLA saturation regions:

    B <= B_low   -> lowest  bitrate (build buffer quickly)
    B >= B_high  -> highest bitrate (buffer can absorb the risk)

This yields a monotone buffer->quality curve with the familiar BOLA
reserve/cap behaviour while remaining a transparent, non-ML rule.

Chain per section 13:  BOLA -> candidate -> Hysteresis -> final.
"""

from __future__ import annotations

from .base import ABRState, BaseABR


class BOLA(BaseABR):
    name = "bola"

    def __init__(self, b_low: float = 6.0, b_high: float = 36.0,
                 gamma: float = 1.0, **kwargs):
        super().__init__(**kwargs)
        if b_high <= b_low:
            raise ValueError("b_high must exceed b_low")
        self.b_low = b_low
        self.b_high = b_high
        self.gamma = gamma  # price/padding term, kept for interface fidelity

        # Utilities: normalized quality scaled to the buffer range so the
        # score crosses zero inside [b_low, b_high].
        max_q = self.quality(self.n_levels - 1)
        self.V = (self.b_high - self.b_low) / max_q if max_q > 0 else 1.0
        # u_i shifted so the lowest level is exactly affordable at B == b_low
        min_q = self.quality(0)
        self.utilities = [
            self.quality(i) - min_q + (self.b_low / self.V)
            for i in range(self.n_levels)
        ]

    def score(self, index: int, buffer_level: float) -> float:
        return self.V * self.utilities[index] - buffer_level

    def select(self, state: ABRState) -> int:
        buffer_level = state.buffer_level
        if buffer_level <= self.b_low:
            return 0
        if buffer_level >= self.b_high:
            return self.n_levels - 1

        # Lowest representation whose utility still covers the buffer cost;
        # if the buffer exceeds every score (top band below B_high), fall
        # back to the highest representation.
        chosen = self.n_levels - 1
        for i in range(self.n_levels):
            if self.score(i, buffer_level) >= 0:
                chosen = i
                break
        return self.clamp(chosen)
