"""Hysteresis controller - quality-switch stabilization (section 13).

Wraps any ABR (commonly BOLA):

    BOLA -> candidate -> Hysteresis -> final bitrate

Rules:
  * switch down  : applied immediately (protects against rebuffering)
  * switch up    : only when the candidate is far enough above the current
                   bitrate (up_ratio) AND the buffer is healthy, or when the
                   buffer is already deep; the candidate must also be
                   observed for ``stable`` consecutive decisions.
"""

from __future__ import annotations

from .base import ABRState, BaseABR


class HysteresisABR(BaseABR):
    name = "hysteresis"

    def __init__(self, inner: BaseABR, up_ratio: float = 1.5,
                 stable: int = 2, min_buffer_for_up: float = 12.0,
                 deep_buffer: float = 30.0, **kwargs):
        super().__init__(**kwargs)
        self.inner = inner
        self.up_ratio = up_ratio
        self.stable = max(1, stable)
        self.min_buffer_for_up = min_buffer_for_up
        self.deep_buffer = deep_buffer
        self._candidate: int | None = None
        self._hold_count = 0
        # Present the wrapped algorithm's name (e.g. "bola+hysteresis").
        self.name = f"{inner.name}+hysteresis"

    def select(self, state: ABRState) -> int:
        candidate = self.clamp(self.inner.select(state))
        current = self.clamp(state.current_index)

        if candidate <= current:
            # Downswitch (or hold) always allowed; reset the hold counter.
            self._candidate = None
            self._hold_count = 0
            return candidate

        # Candidate is an up-switch request.
        up_allowed = (
            state.buffer_level >= self.deep_buffer
            or (
                state.buffer_level >= self.min_buffer_for_up
                and self.bitrate(candidate) >= self.bitrate(current) * self.up_ratio
            )
        )
        if not up_allowed:
            self._candidate = None
            self._hold_count = 0
            return current

        if candidate == self._candidate:
            self._hold_count += 1
        else:
            self._candidate = candidate
            self._hold_count = 1

        if self._hold_count >= self.stable:
            self._candidate = None
            self._hold_count = 0
            return candidate
        return current
