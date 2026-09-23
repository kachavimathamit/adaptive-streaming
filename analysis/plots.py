"""Plot bitrate, buffer occupancy, throughput and QoE comparisons (section 24).

Usage:
    python -m analysis.plots --db database/streaming.db --out analysis/output
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def _load(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    segments = [dict(r) for r in conn.execute(
        "SELECT * FROM segment_metrics ORDER BY session_id, segment_id"
    )]
    sessions = [dict(r) for r in conn.execute(
        "SELECT s.id, s.abr, s.profile, q.qoe, q.rebuffer_seconds, q.n_switches"
        " FROM sessions s LEFT JOIN qoe_results q ON q.session_id = s.id ORDER BY s.id"
    )]
    conn.close()
    return sessions, segments


def plot_session(ax_time, ax_buffer, rows: list[dict]) -> None:
    ids = [r["segment_id"] for r in rows]
    kbps = [r["bitrate"] / 1000 for r in rows]
    tput = [r["instant_throughput"] / 1e6 for r in rows]
    ewma = [r["ewma_throughput"] / 1e6 for r in rows]
    buf = [r["buffer_after"] for r in rows]

    ax_time.plot(ids, kbps, marker=".", label="bitrate (kbps)")
    ax_time.plot(ids, tput, linestyle=":", alpha=0.6, label="instant tput (Mbps)")
    ax_time.plot(ids, ewma, label="EWMA tput (Mbps)")
    ax_time.set_xlabel("segment")
    ax_time.set_ylabel("kbps / Mbps")
    ax_time.legend(loc="upper left", fontsize=8)

    ax_buffer.plot(ids, buf, color="green", label="buffer B(t) (s)")
    ax_buffer.set_xlabel("segment")
    ax_buffer.set_ylabel("seconds")
    ax_buffer.legend(loc="upper left", fontsize=8)


def plot_qoe(ax, sessions: list[dict]) -> None:
    labels = [f"{s['id']}: {s['abr']}\n({s['profile']})" for s in sessions]
    values = [s["qoe"] or 0 for s in sessions]
    ax.bar(range(len(values)), values)
    ax.set_xticks(range(len(values)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("QoE")
    ax.set_title("QoE by session")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate experiment plots")
    parser.add_argument("--db", default="database/streaming.db")
    parser.add_argument("--out", default="analysis/output")
    args = parser.parse_args()

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        raise SystemExit("matplotlib is required: pip install matplotlib")

    sessions, segments = _load(args.db)
    if not sessions:
        raise SystemExit("no sessions recorded yet")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    by_session: dict[int, list[dict]] = {}
    for row in segments:
        by_session.setdefault(row["session_id"], []).append(row)

    for session in sessions:
        rows = by_session.get(session["id"], [])
        if not rows:
            continue
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
        plot_session(ax1, ax2, rows)
        fig.suptitle(f"Session {session['id']}: {session['abr']} / {session['profile']}")
        fig.tight_layout()
        path = out / f"session_{session['id']}_{session['abr']}_{session['profile']}.png"
        fig.savefig(path, dpi=120)
        plt.close(fig)
        print(f"wrote {path}")

    fig, ax = plt.subplots(figsize=(9, 5))
    plot_qoe(ax, sessions)
    fig.tight_layout()
    path = out / "qoe_comparison.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
