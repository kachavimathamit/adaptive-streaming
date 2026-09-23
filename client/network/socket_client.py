"""TCP socket client: connection setup and message exchange (section 8).

Handles the custom HTTP-like protocol: sends a GET request, parses the
response metadata, then receives exactly SIZE bytes of segment data.
"""

from __future__ import annotations

import socket

from common.protocol import build_request, parse_response_header


class SocketClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 9000,
                 timeout: float = 10.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._buf = b""

    # ------------------------------------------------------------------
    def connect(self) -> None:
        sock = socket.create_connection((self.host, self.port),
                                        timeout=self.timeout)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._sock = sock
        self._buf = b""

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    @property
    def connected(self) -> bool:
        return self._sock is not None

    # ------------------------------------------------------------------
    def fetch(self, representation: str, segment_id: int) -> tuple[dict, bytes]:
        """Send one segment request and receive (header, payload).

        Raises ConnectionError if the socket is closed or truncated.
        """
        if self._sock is None:
            raise ConnectionError("not connected")

        self._sock.sendall(build_request(representation, segment_id))
        header = self._read_header()
        size = header["SIZE"]
        body = self._read_exact(size) if size else b""
        return header, body

    # ------------------------------------------------------------------
    def _recv_more(self) -> bool:
        assert self._sock is not None
        chunk = self._sock.recv(65536)
        if not chunk:
            raise ConnectionError("server closed connection")
        self._buf += chunk
        return True

    def _read_line(self) -> str:
        while b"\r\n" not in self._buf:
            self._recv_more()
        line, self._buf = self._buf.split(b"\r\n", 1)
        return line.decode("utf-8", errors="replace")

    def _read_header(self) -> dict:
        lines: list[str] = []
        while True:
            line = self._read_line()
            lines.append(line)
            if line.strip() == "DATA":
                break
            if len(lines) > 32:
                raise ConnectionError("header too large")
        return parse_response_header("\r\n".join(lines) + "\r\n")

    def _read_exact(self, n: int) -> bytes:
        while len(self._buf) < n:
            self._recv_more()
        data, self._buf = self._buf[:n], self._buf[n:]
        return data
