"""Offline QoE analysis across experiment sessions (section 19/24).

Usage:
    python -m analysis.analyze --db database/streaming.db
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def load_sessions(db_path: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    sessions = [dict(r) for r in conn.execute(
        "SELECT s.id, s.client_id, s.abr, s.profile, s.alpha, s.beta, s.gamma,"
        " q.avg_quality, q.avg_bitrate, q.rebuffer_seconds, q.n_switches, q.qoe"
        " FROM sessions s LEFT JOIN qoe_results q ON q.session_id = s.id"
        " ORDER BY s.id"
    )]
    conn.close()
    return sessions


def segment_frame(db_path: str):
    """Per-segment metrics as a pandas DataFrame (or list of dicts)."""
    conn = sqlite3.connect(db_path)
    try:
        import pandas as pd
        df = pd.read_sql_query("SELECT * FROM segment_metrics ORDER BY session_id, segment_id", conn)
    except ImportError:
        rows = conn.execute("SELECT * FROM segment_metrics ORDER BY session_id, segment_id").fetchall()
        cols = [d[0] for d in conn.execute("SELECT * FROM segment_metrics LIMIT 0").description]
        df = [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze streaming experiments")
    parser.add_argument("--db", default="database/streaming.db")
    parser.add_argument("--csv", default=None, help="optional CSV export path")
    args = parser.parse_args()

    if not Path(args.db).exists():
        raise SystemExit(f"database not found: {args.db}")

    sessions = load_sessions(args.db)
    if not sessions:
        raise SystemExit("no sessions recorded yet")

    header = (f"{'id':>3} {'abr':<22} {'profile':<14} {'avg kbps':>9} "
              f"{'quality':>8} {'rebuffer':>9} {'switches':>9} {'QoE':>9}")
    print(header)
    print("-" * len(header))
    for s in sessions:
        print(f"{s['id']:>3} {s['abr']:<22} {s['profile']:<14} "
              f"{(s['avg_bitrate'] or 0) / 1000:>9.0f} "
              f"{(s['avg_quality'] or 0):>8.3f} "
              f"{(s['rebuffer_seconds'] or 0):>8.2f}s "
              f"{(s['n_switches'] or 0):>9} "
              f"{(s['qoe'] or 0):>9.3f}")

    if args.csv:
        df = segment_frame(args.db)
        try:
            df.to_csv(args.csv, index=False)
            print(f"\nsegment metrics exported to {args.csv}")
        except AttributeError:
            import csv
            with open(args.csv, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=df[0].keys())
                writer.writeheader()
                writer.writerows(df)
            print(f"\nsegment metrics exported to {args.csv}")


if __name__ == "__main__":
    main()
