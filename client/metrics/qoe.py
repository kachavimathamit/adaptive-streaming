"""QoE evaluation (document section 19).

    QoE = alpha * mean_quality - beta * T_rebuffer - gamma * N_switch
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QoEConfig:
    alpha: float = 1.0     # weight on average quality
    beta: float = 4.5      # penalty per second of rebuffering
    gamma: float = 1.0     # penalty per quality switch


def compute_qoe(qualities: list[float], rebuffer_seconds: float,
                n_switches: int, config: QoEConfig | None = None) -> dict:
    """Return the QoE breakdown.

    ``qualities`` are normalized per-segment qualities in [0, 1]
    (bitrate / max_bitrate of the ladder).
    """
    cfg = config or QoEConfig()
    avg_quality = sum(qualities) / len(qualities) if qualities else 0.0
    qoe = (cfg.alpha * avg_quality
           - cfg.beta * rebuffer_seconds
           - cfg.gamma * n_switches)
    return {
        "avg_quality": avg_quality,
        "rebuffer_seconds": rebuffer_seconds,
        "n_switches": n_switches,
        "qoe": qoe,
    }
