import pytest

from common.protocol import (
    ProtocolError,
    build_request,
    build_response_header,
    parse_request,
    parse_response_header,
)
from server.request_parser import NotFoundError, RequestError, parse_segment_request


def test_build_and_parse_request():
    raw = build_request("720p", 1)
    assert raw == b"GET /video/720p/segment_001.m4s\r\n"
    rep, seg = parse_request(raw.decode().strip())
    assert rep == "720p" and seg == 1


def test_parse_request_rejects_garbage():
    with pytest.raises(ProtocolError):
        parse_request("POST /video/720p/segment_001.m4s")
    with pytest.raises(ProtocolError):
        parse_request("GET /video/720p/segment_0.m4s")  # ids start at 1


def test_response_header_roundtrip():
    raw = build_response_header(
        status=200, size=524288, bitrate=2_500_000, duration=2,
        representation="720p", segment_id=1,
    )
    header = parse_response_header(raw.decode())
    assert header["STATUS"] == 200
    assert header["SIZE"] == 524288
    assert header["BITRATE"] == 2_500_000
    assert header["DURATION"] == 2.0
    assert header["REPRESENTATION"] == "720p"
    assert header["data_follows"] is True


def test_server_request_validation():
    assert parse_segment_request("GET /video/720p/segment_007.m4s") == ("720p", 7)
    with pytest.raises(NotFoundError):
        parse_segment_request("GET /video/4321p/segment_001.m4s")
    with pytest.raises(NotFoundError):
        parse_segment_request("GET /video/720p/segment_999.m4s")
    with pytest.raises(RequestError):  # malformed line is a 400, not 404
        parse_segment_request("GARBAGE")
