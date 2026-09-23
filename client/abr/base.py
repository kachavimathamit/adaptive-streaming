"""Common ABR interface (document section 12).

Every algorithm implements ``select(state) -> ladder index`` so the same
experiment can be replayed with different controllers via configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from common.config import DEFAULT_LADDER, DEFAULT_SEGMENT_DURATION

__all__ = ["ABRState", "BaseABR", "DEFAULT_LADDER", "bitrate_of", "quality_of"]


def bitrate_of(index: int, ladder=DEFAULT_LADDER) -> int:
    return ladder[index][1]


def quality_of(index: int, ladder=DEFAULT_LADDER) -> float:
    """Normalized quality in [0, 1]."""
    max_br = ladder[-1][1]
    return ladder[index][1] / max_br


@dataclass
class ABRState:
    """Snapshot of client state handed to the ABR engine before each decision."""

    buffer_level: float                 # B(t): seconds of playable media buffered
    throughput_bps: float               # smoothed estimate (EWMA)
    segment_id: int                     # next segment to download (1-based)
    current_index: int = 0              # representation currently being played
    segments_downloaded: int = 0
    last_download_time: float = 0.0
    extra: dict = field(default_factory=dict)


class BaseABR:
    """Interface shared by RateBased, BufferBased, BOLA, Hysteresis, MPC."""

    name = "base"

    def __init__(self, ladder=DEFAULT_LADDER,
                 segment_duration: float = DEFAULT_SEGMENT_DURATION):
        self.ladder = list(ladder)
        self.segment_duration = segment_duration

    # -- helpers -------------------------------------------------------
    @property
    def n_levels(self) -> int:
        return len(self.ladder)

    def bitrate(self, index: int) -> int:
        return self.ladder[index][1]

    def quality(self, index: int) -> float:
        return quality_of(index, self.ladder)

    def clamp(self, index: int) -> int:
        return max(0, min(self.n_levels - 1, index))

    def highest_fitting(self, throughput_bps: float, safety: float = 1.0) -> int:
        """Highest ladder index whose bitrate fits within ``throughput``."""
        limit = throughput_bps * safety
        idx = 0
        for i, (_, br) in enumerate(self.ladder):
            if br <= limit:
                idx = i
            else:
                break
        return idx

    # -- interface -----------------------------------------------------
    def select(self, state: ABRState) -> int:
        raise NotImplementedError
