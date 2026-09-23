"""Run identical network scenarios across all ABR algorithms (section 19/22).

Usage:
    python scripts/run_comparison.py --profile experiments/fluctuating.json \
        --segments 18 --db database/streaming.db
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running as a plain script from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from client.client import run_session                      # noqa: E402
from client.metrics.qoe import QoEConfig                   # noqa: E402

ALGORITHMS = [
    ("rate", False),      # Rate-Based ABR (baseline)
    ("buffer", False),    # Buffer-Based ABR (BBA-0)
    ("bola", False),      # BOLA
    ("bola", True),       # BOLA + Hysteresis  (section 13)
    ("mpc", False),       # MPC (section 14)
]


def main() -> None:
    parser = argparse.ArgumentParser(description="ABR comparison runner")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--profile", default="experiments/fluctuating.json")
    parser.add_argument("--segments", type=int, default=18)
    parser.add_argument("--db", default="database/streaming.db")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--beta", type=float, default=4.5)
    parser.add_argument("--gamma", type=float, default=1.0)
    args = parser.parse_args()

    cfg = QoEConfig(args.alpha, args.beta, args.gamma)
    results = []
    for abr, hysteresis in ALGORITHMS:
        label = f"{abr}+hysteresis" if hysteresis else abr
        print(f"--- running {label} on {Path(args.profile).name} "
              f"({args.segments} segments) ---")
        summary = run_session(
            host=args.host, port=args.port,
            abr_name=abr, use_hysteresis=hysteresis,
            profile_path=args.profile,
            segment_count=args.segments,
            db_path=args.db,
            client_id=f"c-{abr}{'-h' if hysteresis else ''}",
            playback_speed=args.speed,
            qoe_cfg=cfg,
            verbose=False,
        )
        results.append(summary)

    header = (f"{'abr':<22} {'avg kbps':>9} {'quality':>8} {'rebuffer':>9} "
              f"{'switches':>9} {'QoE':>9}")
    print("\n" + header)
    print("-" * len(header))
    for r in results:
        print(f"{r['abr']:<22} {r['avg_bitrate_bps'] / 1000:>9.0f} "
              f"{r['avg_quality']:>8.3f} {r['rebuffer_seconds']:>8.2f}s "
              f"{r['n_switches']:>9} {r['qoe']:>9.3f}")

    out = Path(args.db).parent / "last_comparison.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2))
    print(f"\nresults written to {out}")


if __name__ == "__main__":
    main()
