"""Playback-deadline segment scheduling (document section 15).

Deadline for a segment = the wall-clock instant by which it must be
downloaded so playback never stalls:

    deadline_k = now + (buffer_level - media_already_scheduled)
                 + sum(duration of segments before k)

Priority combines urgency and buffer state:

    priority = urgency - buffer_bonus

so segments whose deadline is near are fetched first, while a healthy
buffer relaxes the ordering.
"""

from __future__ import annotations

import time

from .priority_queue import ScheduledTask, SegmentScheduler


class DeadlineScheduler(SegmentScheduler):
    def __init__(self, buffer_lookup, segment_duration: float = 2.0,
                 urgency_weight: float = 1.0, buffer_bonus: float = 0.1):
        """buffer_lookup: callable returning current B(t) in seconds."""
        super().__init__()
        self.buffer_lookup = buffer_lookup
        self.segment_duration = segment_duration
        self.urgency_weight = urgency_weight
        self.buffer_bonus = buffer_bonus

    def schedule_upcoming(self, from_segment: int, count: int,
                          now: float | None = None) -> None:
        """Push the next ``count`` segments with computed deadlines."""
        now = time.monotonic() if now is None else now
        buffer_level = float(self.buffer_lookup())
        for offset in range(count):
            seg_id = from_segment + offset
            # Media needed at playback time: buffer covers `offset` segments.
            remaining = buffer_level - offset * self.segment_duration
            slack = max(0.0, remaining)
            deadline = now + slack
            urgency = self.urgency_weight * (offset * self.segment_duration) - slack
            priority = urgency - self.buffer_bonus * buffer_level
            self.push(segment_id=seg_id, priority=priority, deadline=deadline)

    def next_segment(self, from_segment: int, lookahead: int = 3,
                     now: float | None = None) -> int:
        """Return the segment id that should be downloaded next."""
        self.schedule_upcoming(from_segment, lookahead, now=now)
        task: ScheduledTask | None = self.pop()
        # Drop any stale tasks scheduled for earlier rounds.
        while task is not None and task.segment_id < from_segment:
            task = self.pop()
        return from_segment if task is None else task.segment_id
