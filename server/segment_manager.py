"""Video segment store (document sections 3 and 6).

Resolves requested segments from the media directory. If a real FFmpeg-
prepared segment file exists it is served from disk; otherwise a
deterministic synthetic segment of the correct size is generated so the
stack can be exercised without a video corpus.
"""

from __future__ import annotations

import json
import random
import threading
from dataclasses import dataclass
from pathlib import Path

from common.config import (
    DEFAULT_LADDER,
    DEFAULT_SEGMENT_COUNT,
    DEFAULT_SEGMENT_DURATION,
    LADDER_BY_REP,
)


@dataclass(frozen=True)
class Segment:
    representation: str
    segment_id: int
    bitrate: int
    duration: float
    data: bytes


class SegmentManager:
    def __init__(self, media_dir: str | Path, manifest: dict | None = None):
        self.media_dir = Path(media_dir)
        self._lock = threading.Lock()
        self._file_cache: dict[tuple[str, int], bytes] = {}
        self.manifest = manifest or self._load_manifest()
        self.segment_count = int(self.manifest.get("segment_count", DEFAULT_SEGMENT_COUNT))
        self.segment_duration = float(
            self.manifest.get("segment_duration", DEFAULT_SEGMENT_DURATION)
        )
        reps = self.manifest.get("representations")
        if not reps:
            reps = {name: {"bitrate": br} for name, br in DEFAULT_LADDER}
        self.representations: dict[str, int] = {
            name: int(info["bitrate"]) for name, info in reps.items()
        }

    def _load_manifest(self) -> dict:
        path = self.media_dir / "manifest.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        return {}

    # ------------------------------------------------------------------
    def resolve(self, representation: str, segment_id: int) -> Segment | None:
        """Locate a segment, returning None if it does not exist."""
        if representation not in self.representations or segment_id < 1:
            return None
        if segment_id > self.segment_count:
            return None

        bitrate = self.representations[representation]
        data = self._load_bytes(representation, segment_id, bitrate)
        return Segment(
            representation=representation,
            segment_id=segment_id,
            bitrate=bitrate,
            duration=self.segment_duration,
            data=data,
        )

    def _load_bytes(self, representation: str, segment_id: int, bitrate: int) -> bytes:
        key = (representation, segment_id)
        with self._lock:
            if key in self._file_cache:
                return self._file_cache[key]

        path = (
            self.media_dir
            / representation
            / f"segment_{segment_id:03d}.m4s"
        )
        if path.exists():
            data = path.read_bytes()
        else:
            data = self._synthetic(representation, segment_id, bitrate)

        with self._lock:
            self._file_cache[key] = data
        return data

    @staticmethod
    def _synthetic(representation: str, segment_id: int, bitrate: int) -> bytes:
        """Deterministic pseudo-random bytes of approximately the right size.

        size = bitrate * duration / 8, with +/-10% segment-to-segment
        variation to mimic real encoded segment sizes.
        """
        from common.config import DEFAULT_SEGMENT_DURATION

        base = int(bitrate * DEFAULT_SEGMENT_DURATION / 8)
        rng = random.Random(f"{representation}:{segment_id}")
        jitter = int(base * 0.10)
        size = base + rng.randint(-jitter, jitter)
        return rng.randbytes(max(size, 1))
