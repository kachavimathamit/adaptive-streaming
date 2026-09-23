"""Request parsing for the video server (document section 6)."""

from __future__ import annotations

from common.protocol import ProtocolError, parse_request
from common.config import LADDER_BY_REP, DEFAULT_SEGMENT_COUNT


class RequestError(Exception):
    """Invalid or unsupported client request."""


class NotFoundError(RequestError):
    """Valid request line, but the requested resource does not exist."""


def parse_segment_request(line: str, segment_count: int = DEFAULT_SEGMENT_COUNT) -> tuple[str, int]:
    """Validate a request line and return (representation, segment_id)."""
    try:
        representation, segment_id = parse_request(line)
    except ProtocolError as exc:
        raise RequestError(str(exc)) from exc
    if representation not in LADDER_BY_REP:
        raise NotFoundError(f"unknown representation: {representation}")
    if segment_id > segment_count:
        raise NotFoundError(f"segment out of range: {segment_id}")
    return representation, segment_id


def read_request_line(recv_chunk) -> str:
    """Read a single CRLF-terminated line.

    ``recv_chunk(maxsize) -> bytes`` is a callable backed by the socket.
    """
    buf = b""
    while b"\n" not in buf:
        chunk = recv_chunk(1024)
        if not chunk:
            raise RequestError("connection closed before request line")
        buf += chunk
        if len(buf) > 4096:
            raise RequestError("request line too long")
    return buf.split(b"\n", 1)[0].decode("utf-8", errors="replace").strip()
