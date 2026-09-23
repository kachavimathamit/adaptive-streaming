"""SQLite metrics storage (document section 18).

Records one row per downloaded segment plus sessions, quality-switch
events, rebuffer events and final QoE results.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT,
    abr TEXT NOT NULL,
    profile TEXT NOT NULL,
    alpha REAL, beta REAL, gamma REAL,
    start_time REAL,
    segment_count INTEGER,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS segment_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    timestamp REAL,
    segment_id INTEGER,
    representation TEXT,
    bitrate INTEGER,
    size INTEGER,
    download_time REAL,
    instant_throughput REAL,
    ewma_throughput REAL,
    buffer_before REAL,
    buffer_after REAL,
    quality_switch INTEGER,
    rebuffer_event INTEGER,
    rebuffer_duration REAL,
    network_profile TEXT,
    abr TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS quality_switches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    segment_id INTEGER,
    from_bitrate INTEGER,
    to_bitrate INTEGER
);

CREATE TABLE IF NOT EXISTS rebuffer_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    start_offset REAL,
    duration REAL,
    segment_id INTEGER
);

CREATE TABLE IF NOT EXISTS qoe_results (
    session_id INTEGER PRIMARY KEY,
    avg_quality REAL,
    avg_bitrate REAL,
    rebuffer_seconds REAL,
    n_switches INTEGER,
    qoe REAL
);
"""


class MetricsCollector:
    def __init__(self, db_path: str | Path):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._lock = threading.Lock()
        self.session_id: int | None = None

    # ------------------------------------------------------------------
    def start_session(self, client_id: str, abr: str, profile: str,
                      alpha: float, beta: float, gamma: float,
                      segment_count: int, notes: str = "") -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO sessions (client_id, abr, profile, alpha, beta, gamma,"
                " start_time, segment_count, notes) VALUES (?,?,?,?,?,?,?,?,?)",
                (client_id, abr, profile, alpha, beta, gamma,
                 time.time(), segment_count, notes),
            )
            self._conn.commit()
            self.session_id = cur.lastrowid
            return int(cur.lastrowid)

    # ------------------------------------------------------------------
    def record_segment(self, *, timestamp: float, segment_id: int,
                       representation: str, bitrate: int, size: int,
                       download_time: float, instant_throughput: float,
                       ewma_throughput: float, buffer_before: float,
                       buffer_after: float, quality_switch: bool,
                       rebuffer_event: bool, rebuffer_duration: float,
                       network_profile: str, abr: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO segment_metrics (session_id, timestamp, segment_id,"
                " representation, bitrate, size, download_time, instant_throughput,"
                " ewma_throughput, buffer_before, buffer_after, quality_switch,"
                " rebuffer_event, rebuffer_duration, network_profile, abr)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (self.session_id, timestamp, segment_id, representation, bitrate,
                 size, download_time, instant_throughput, ewma_throughput,
                 buffer_before, buffer_after, int(quality_switch),
                 int(rebuffer_event), rebuffer_duration, network_profile, abr),
            )
            self._conn.commit()

    def record_switch(self, segment_id: int, from_bitrate: int,
                      to_bitrate: int) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO quality_switches (session_id, segment_id, from_bitrate,"
                " to_bitrate) VALUES (?,?,?,?)",
                (self.session_id, segment_id, from_bitrate, to_bitrate),
            )
            self._conn.commit()

    def record_rebuffer(self, start_offset: float, duration: float,
                        segment_id: int) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO rebuffer_events (session_id, start_offset, duration,"
                " segment_id) VALUES (?,?,?,?)",
                (self.session_id, start_offset, duration, segment_id),
            )
            self._conn.commit()

    def record_qoe(self, avg_quality: float, avg_bitrate: float,
                   rebuffer_seconds: float, n_switches: int, qoe: float) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO qoe_results (session_id, avg_quality,"
                " avg_bitrate, rebuffer_seconds, n_switches, qoe)"
                " VALUES (?,?,?,?,?,?)",
                (self.session_id, avg_quality, avg_bitrate, rebuffer_seconds,
                 n_switches, qoe),
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    def query(self, sql: str, params: tuple = ()) -> list[tuple]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
