"""MPC - Model Predictive Control ABR (section 14).

Non-ML predictive controller:

  1. Read current buffer and recent (EWMA) throughput.
  2. Enumerate candidate bitrate sequences over a short horizon (default 3).
  3. Simulate future buffer evolution for each sequence:
         download_time = bitrate * duration / throughput
         buffer -= download_time  (rebuffering if it would drop below 0)
         buffer += duration
  4. Score each sequence with a QoE objective
         sum( alpha*quality - beta*rebuffer - gamma*switch_cost )
  5. Apply only the first decision and repeat next segment.
"""

from __future__ import annotations

from itertools import product

from .base import ABRState, BaseABR


class MPC(BaseABR):
    name = "mpc"

    def __init__(self, horizon: int = 3, alpha: float = 1.0,
                 beta: float = 4.5, gamma: float = 1.0,
                 rebuffer_risk: float = 0.5, **kwargs):
        super().__init__(**kwargs)
        self.horizon = max(1, horizon)
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.rebuffer_risk = rebuffer_risk  # extra weight on near-empty buffer

    # ------------------------------------------------------------------
    def _simulate(self, sequence: tuple[int, ...], buffer_level: float,
                  throughput: float, previous_index: int) -> float:
        b = buffer_level
        prev = previous_index
        score = 0.0
        for idx in sequence:
            bitrate = self.bitrate(idx)
            download_time = bitrate * self.segment_duration / max(throughput, 1.0)
            rebuffer = max(0.0, download_time - b)
            b = max(0.0, b - download_time) + self.segment_duration

            score += self.alpha * self.quality(idx)
            score -= self.beta * rebuffer
            score -= self.gamma * abs(self.quality(idx) - self.quality(prev))
            # Penalise operating with a nearly-empty buffer (rebuffer risk).
            if b < 2.0:
                score -= self.rebuffer_risk
            prev = idx
        return score

    def select(self, state: ABRState) -> int:
        throughput = state.throughput_bps or self.bitrate(0)
        best_score = float("-inf")
        best_first = self.clamp(state.current_index)

        for sequence in product(range(self.n_levels), repeat=self.horizon):
            score = self._simulate(
                sequence, state.buffer_level, throughput, state.current_index
            )
            if score > best_score:
                best_score = score
                best_first = sequence[0]
        return best_first
