"""Custom HTTP-like application protocol (document section 5).

Request:
    GET /video/720p/segment_001.m4s\r\n

Response metadata (one key/value per line, terminated by the DATA line,
followed by exactly SIZE raw bytes):

    STATUS 200\r\n
    SIZE 524288\r\n
    BITRATE 2500000\r\n
    DURATION 2\r\n
    REPRESENTATION 720p\r\n
    SEGMENT 1\r\n
    DATA\r\n
    <SIZE raw bytes>
"""

from __future__ import annotations

import re

DATA_LINE = "DATA"
LINE_SEP = "\r\n"

_REQUEST_RE = re.compile(r"^GET\s+/video/([A-Za-z0-9p]+)/segment_(\d+)\.m4s$")


class ProtocolError(Exception):
    """Malformed protocol message."""


def build_request(representation: str, segment_id: int) -> bytes:
    path = f"/video/{representation}/segment_{segment_id:03d}.m4s"
    return f"GET {path}{LINE_SEP}".encode("utf-8")


def parse_request(line: str) -> tuple[str, int]:
    """Parse a request line, returning (representation, segment_id)."""
    line = line.strip()
    m = _REQUEST_RE.match(line)
    if not m:
        raise ProtocolError(f"bad request line: {line!r}")
    representation, seg = m.group(1), int(m.group(2))
    if seg < 1:
        raise ProtocolError(f"bad segment id: {seg}")
    return representation, seg


def build_response_header(
    status: int,
    size: int,
    bitrate: int = 0,
    duration: float = 0.0,
    representation: str = "",
    segment_id: int = 0,
) -> bytes:
    lines = [
        f"STATUS {status}",
        f"SIZE {size}",
        f"BITRATE {bitrate}",
        f"DURATION {duration:g}",
        f"REPRESENTATION {representation}",
        f"SEGMENT {segment_id}",
        DATA_LINE,
    ]
    return (LINE_SEP.join(lines) + LINE_SEP).encode("utf-8")


def parse_response_header(raw: str) -> dict:
    """Parse header text (everything up to and including the DATA line)."""
    header: dict = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line == DATA_LINE:
            header["data_follows"] = True
            break
        parts = line.split(None, 1)
        if len(parts) == 1:
            # Key with empty value (e.g. "REPRESENTATION " on error replies).
            header[parts[0]] = ""
            continue
        if len(parts) != 2:
            raise ProtocolError(f"bad header line: {line!r}")
        key, value = parts
        header[key] = value
    if "STATUS" not in header or "SIZE" not in header:
        raise ProtocolError("header missing STATUS or SIZE")
    header["STATUS"] = int(header["STATUS"])
    header["SIZE"] = int(header["SIZE"])
    header["BITRATE"] = int(header.get("BITRATE", 0))
    header["DURATION"] = float(header.get("DURATION", 0))
    if header["SIZE"] < 0:
        raise ProtocolError("negative SIZE")
    return header
