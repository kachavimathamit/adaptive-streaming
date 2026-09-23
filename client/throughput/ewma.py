"""EWMA throughput estimation (document section 11).

    T_i     = S_i / dt_i                       (instantaneous throughput)
    T_hat_i = alpha * T_i + (1-alpha) * T_hat_{i-1}
"""

from __future__ import annotations


class EWMA:
    def __init__(self, alpha: float = 0.3, initial: float | None = None):
        if not 0 < alpha <= 1:
            raise ValueError("alpha must be in (0, 1]")
        self.alpha = alpha
        self.value: float | None = initial
        self.samples = 0

    def update(self, throughput_bps: float) -> float:
        if self.value is None:
            self.value = throughput_bps
        else:
            self.value = self.alpha * throughput_bps + (1 - self.alpha) * self.value
        self.samples += 1
        return self.value

    @property
    def estimate(self) -> float | None:
        return self.value

    def reset(self) -> None:
        self.value = None
        self.samples = 0
