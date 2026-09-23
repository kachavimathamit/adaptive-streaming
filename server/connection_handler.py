"""Per-connection handler for the multi-threaded TCP server (sections 6-7)."""

from __future__ import annotations

import socket
import threading
import time

from common.protocol import build_response_header
from .request_parser import (
    NotFoundError,
    RequestError,
    parse_segment_request,
    read_request_line,
)
from .segment_manager import SegmentManager


class ConnectionHandler(threading.Thread):
    """Serves one connected client in its own thread."""

    def __init__(
        self,
        conn: socket.socket,
        addr,
        segment_manager: SegmentManager,
        stats: dict | None = None,
        stats_lock: threading.Lock | None = None,
        timeout: float = 30.0,
    ):
        super().__init__(daemon=True)
        self.conn = conn
        self.addr = addr
        self.segment_manager = segment_manager
        self.stats = stats if stats is not None else {}
        self.stats_lock = stats_lock or threading.Lock()
        self.timeout = timeout

    def run(self) -> None:
        self.conn.settimeout(self.timeout)
        try:
            # Serve requests until the client disconnects (HTTP-like
            # request/response loop over one persistent TCP connection).
            while True:
                try:
                    line = read_request_line(self.conn.recv)
                except RequestError:
                    break  # clean disconnect or malformed request line

                try:
                    representation, segment_id = parse_segment_request(
                        line, self.segment_manager.segment_count
                    )
                except NotFoundError:
                    self._send_header(404, 0)
                    continue
                except RequestError:
                    self._send_header(400, 0)
                    break

                segment = self.segment_manager.resolve(representation, segment_id)
                if segment is None:
                    self._send_header(404, 0)
                    continue

                header = build_response_header(
                    status=200,
                    size=len(segment.data),
                    bitrate=segment.bitrate,
                    duration=segment.duration,
                    representation=segment.representation,
                    segment_id=segment.segment_id,
                )
                self.conn.sendall(header)
                self.conn.sendall(segment.data)

                with self.stats_lock:
                    self.stats["segments_sent"] = self.stats.get("segments_sent", 0) + 1
                    self.stats["bytes_sent"] = (
                        self.stats.get("bytes_sent", 0) + len(segment.data)
                    )
        except (ConnectionError, socket.timeout, OSError):
            pass
        finally:
            try:
                self.conn.close()
            except OSError:
                pass

    def _send_header(self, status: int, size: int) -> None:
        self.conn.sendall(build_response_header(status=status, size=size))
