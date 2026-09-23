"""End-to-end test: real TCP server + full client session (sections 4-19)."""

import pytest

from client.client import run_session
from client.network import Downloader, SocketClient
from client.metrics.qoe import QoEConfig, compute_qoe
from server import VideoServer


@pytest.fixture()
def server(tmp_path):
    srv = VideoServer(host="127.0.0.1", port=0,
                      media_dir=str(tmp_path / "media"))
    srv.start()
    yield srv
    srv.stop()


def test_single_segment_transfer(server):
    client = SocketClient("127.0.0.1", server.port)
    client.connect()
    try:
        result = Downloader(client).download("360p", 1)
    finally:
        client.close()

    assert result.status == 200
    assert result.bitrate == 500_000
    assert result.duration == 2.0
    assert result.size > 0
    assert len(result.data) == result.size
    assert result.download_time > 0
    assert result.throughput > 0


def test_unknown_representation_returns_404(server):
    client = SocketClient("127.0.0.1", server.port)
    client.connect()
    try:
        header, body = client.fetch("2160p", 1)
    finally:
        client.close()
    assert header["STATUS"] == 404
    assert body == b""


def test_concurrent_clients(server):
    """Multi-threaded server handles several clients at once (section 7)."""
    import threading

    errors = []

    def worker():
        client = SocketClient("127.0.0.1", server.port)
        client.connect()
        try:
            for seg in range(1, 4):
                r = Downloader(client).download("480p", seg)
                assert r.status == 200
        except Exception as exc:  # pragma: no cover
            errors.append(exc)
        finally:
            client.close()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors
    assert server.stats.get("segments_sent", 0) >= 12


def test_full_session_records_metrics(server, tmp_path):
    db = tmp_path / "test.db"
    summary = run_session(
        host="127.0.0.1", port=server.port,
        abr_name="rate", use_hysteresis=True,
        segment_count=6,
        db_path=str(db),
        playback_speed=1000.0,   # instant playback for test speed
        qoe_cfg=QoEConfig(alpha=1.0, beta=4.5, gamma=1.0),
        verbose=False,
    )
    assert summary["segments"] == 6
    assert summary["qoe"] == pytest.approx(
        1.0 * summary["avg_quality"]
        - 4.5 * summary["rebuffer_seconds"]
        - 1.0 * summary["n_switches"]
    )

    import sqlite3
    conn = sqlite3.connect(str(db))
    rows = conn.execute("SELECT COUNT(*) FROM segment_metrics").fetchone()[0]
    sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    qoe_rows = conn.execute("SELECT COUNT(*) FROM qoe_results").fetchone()[0]
    conn.close()
    assert rows == 6
    assert sessions == 1
    assert qoe_rows == 1


def test_qoe_formula():
    result = compute_qoe([0.2, 0.4, 1.0], rebuffer_seconds=2.0,
                         n_switches=3, config=QoEConfig(1.0, 4.5, 1.0))
    assert result["avg_quality"] == pytest.approx(0.53333, abs=1e-4)
    assert result["qoe"] == pytest.approx(0.53333 - 9.0 - 3.0, abs=1e-4)
