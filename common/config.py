"""Shared configuration constants for server and client.

Single source of truth for the bitrate ladder and segment timing so the
server (segment store) and the client (ABR engine) always agree.
"""

# Representation name -> bitrate in bits per second.
# 120 s video / 2 s segments = 60 segments per representation.
DEFAULT_LADDER: list[tuple[str, int]] = [
    ("360p", 500_000),
    ("480p", 1_000_000),
    ("720p", 2_500_000),
    ("1080p", 5_000_000),
]

LADDER_BY_REP: dict[str, int] = dict(DEFAULT_LADDER)

DEFAULT_SEGMENT_DURATION = 2.0          # seconds per segment
DEFAULT_SEGMENT_COUNT = 60              # 60 * 2 s = 120 s video

# Highest bitrate in the ladder (used for normalized quality Q in [0, 1]).
MAX_BITRATE = DEFAULT_LADDER[-1][1]

# Network / buffer defaults
DEFAULT_MAX_BUFFER_SECONDS = 60.0       # playback buffer cap B_max
DEFAULT_EWMA_ALPHA = 0.3                # throughput smoothing factor
