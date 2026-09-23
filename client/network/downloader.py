"""Segment downloader (document sections 8 and 11).

Requests one segment, measures request-to-last-byte download time, and
computes instantaneous throughput T_i = S_i / dt_i.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .socket_client import SocketClient
from .shaper import NetworkShaper


@dataclass
class SegmentDownload:
    representation: str
    segment_id: int
    bitrate: int
    duration: float
    size: int                # bytes
    download_time: float     # seconds (request sent -> last byte received)
    throughput: float        # bits per second
    data: bytes
    status: int = 200


class Downloader:
    def __init__(self, client: SocketClient, shaper: NetworkShaper | None = None):
        self.client = client
        self.shaper = shaper

    def download(self, representation: str, segment_id: int) -> SegmentDownload:
        if self.shaper is not None:
            self.shaper.start()
            self.shaper.apply_request_latency()

        t0 = time.perf_counter()
        header, data = self.client.fetch(representation, segment_id)
        elapsed = time.perf_counter() - t0

        if self.shaper is not None and header["STATUS"] == 200:
            elapsed += self.shaper.apply_download_delay(len(data), elapsed)

        throughput = (len(data) * 8) / elapsed if elapsed > 0 else 0.0
        return SegmentDownload(
            representation=representation,
            segment_id=segment_id,
            bitrate=header["BITRATE"],
            duration=header["DURATION"],
            size=len(data),
            download_time=elapsed,
            throughput=throughput,
            data=data,
            status=header["STATUS"],
        )
