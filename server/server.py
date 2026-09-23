"""Multi-threaded TCP video server (document sections 6-7).

Usage:
    python -m server.server --host 127.0.0.1 --port 9000 --media server/media
"""

from __future__ import annotations

import argparse
import socket
import threading

from .connection_handler import ConnectionHandler
from .segment_manager import SegmentManager


class VideoServer:
    """TCP server: one thread per connected client."""

    def __init__(self, host: str = "127.0.0.1", port: int = 9000,
                 media_dir: str = "server/media", backlog: int = 16):
        self.host = host
        self.port = port
        self.segment_manager = SegmentManager(media_dir)
        self.backlog = backlog
        self.stats: dict = {}
        self.stats_lock = threading.Lock()
        self._sock: socket.socket | None = None
        self._accepting = False
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    def start(self) -> None:
        """Bind, listen, and start the accept loop in a background thread."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(self.backlog)
        sock.settimeout(0.5)
        self._sock = sock
        # Pick up the OS-assigned port when port=0 was requested.
        self.port = sock.getsockname()[1]
        self._accepting = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def _accept_loop(self) -> None:
        assert self._sock is not None
        while self._accepting:
            try:
                conn, addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            handler = ConnectionHandler(
                conn, addr, self.segment_manager, self.stats, self.stats_lock
            )
            handler.start()

    def serve_forever(self) -> None:
        self.start()
        try:
            while self._accepting:
                threading.Event().wait(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        self._accepting = False
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None


def main() -> None:
    parser = argparse.ArgumentParser(description="Adaptive streaming TCP server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--media", default="server/media",
                        help="directory with media/manifest.json and segments")
    args = parser.parse_args()

    server = VideoServer(args.host, args.port, args.media)
    print(f"Serving {server.segment_manager.segment_count} segments "
          f"x {len(server.segment_manager.representations)} representations "
          f"on {args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
