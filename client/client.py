"""Main streaming client: ties the whole stack together (sections 8-19).

    socket -> downloader -> EWMA -> ABR -> scheduler -> buffer
              -> playback thread -> metrics collector -> SQLite -> QoE

Usage:
    python -m client.client --abr bola --hysteresis \
        --profile experiments/stable.json --host 127.0.0.1 --port 9000
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from common.config import (
    DEFAULT_EWMA_ALPHA,
    DEFAULT_LADDER,
    DEFAULT_MAX_BUFFER_SECONDS,
    DEFAULT_SEGMENT_COUNT,
    DEFAULT_SEGMENT_DURATION,
)
from .abr import (
    ABRState,
    BOLA,
    MPC,
    BaseABR,
    BufferBasedABR,
    HysteresisABR,
    RateBasedABR,
)
from .buffer import BufferManager, BufferedSegment
from .metrics import MetricsCollector, QoEConfig, compute_qoe
from .network import Downloader, NetworkShaper, SocketClient
from .playback import PlaybackController
from .scheduler import DeadlineScheduler
from .throughput import EWMA


def make_abr(name: str, use_hysteresis: bool = False,
             qoe_cfg: QoEConfig | None = None) -> BaseABR:
    """Factory so experiments can switch controllers via configuration."""
    qoe_cfg = qoe_cfg or QoEConfig()
    name = name.lower()
    if name in ("rate", "rate_based"):
        abr: BaseABR = RateBasedABR()
    elif name in ("buffer", "buffer_based", "bba"):
        abr = BufferBasedABR()
    elif name == "bola":
        abr = BOLA()
    elif name == "mpc":
        abr = MPC(alpha=qoe_cfg.alpha, beta=qoe_cfg.beta, gamma=qoe_cfg.gamma)
    else:
        raise ValueError(f"unknown ABR algorithm: {name}")

    if use_hysteresis:
        abr = HysteresisABR(abr, ladder=DEFAULT_LADDER)
    return abr


def run_session(
    host: str = "127.0.0.1",
    port: int = 9000,
    abr_name: str = "rate",
    use_hysteresis: bool = False,
    profile_path: str | None = None,
    segment_count: int = DEFAULT_SEGMENT_COUNT,
    db_path: str = "database/streaming.db",
    client_id: str = "client-1",
    playback_speed: float = 1.0,
    qoe_cfg: QoEConfig | None = None,
    timeout: float = 15.0,
    verbose: bool = True,
) -> dict:
    qoe_cfg = qoe_cfg or QoEConfig()
    abr = make_abr(abr_name, use_hysteresis, qoe_cfg)
    profile_name = Path(profile_path).stem if profile_path else "none"

    shaper = NetworkShaper.from_file(profile_path) if profile_path else None

    client = SocketClient(host, port, timeout=timeout)
    client.connect()
    downloader = Downloader(client, shaper)

    buffer_manager = BufferManager(max_seconds=DEFAULT_MAX_BUFFER_SECONDS)
    ewma = EWMA(alpha=DEFAULT_EWMA_ALPHA)
    scheduler = DeadlineScheduler(
        buffer_lookup=lambda: buffer_manager.level,
        segment_duration=DEFAULT_SEGMENT_DURATION,
    )

    collector = MetricsCollector(db_path)
    session_id = collector.start_session(
        client_id=client_id, abr=abr.name, profile=profile_name,
        alpha=qoe_cfg.alpha, beta=qoe_cfg.beta, gamma=qoe_cfg.gamma,
        segment_count=segment_count,
    )

    session_start = time.monotonic()
    playback = PlaybackController(
        buffer_manager, total_segments=segment_count,
        speed=playback_speed, session_start=session_start,
    )
    playback.start()

    qualities: list[float] = []
    n_switches = 0
    current_index = 0
    buffer_before = 0.0

    try:
        for i in range(segment_count):
            seg_id = scheduler.next_segment(from_segment=i + 1, lookahead=3)

            state = ABRState(
                buffer_level=buffer_manager.level,
                throughput_bps=ewma.estimate or float(DEFAULT_LADDER[0][1]),
                segment_id=seg_id,
                current_index=current_index,
                segments_downloaded=len(qualities),
            )
            index = abr.select(state)
            representation, bitrate = DEFAULT_LADDER[index]

            buffer_before = buffer_manager.level
            result = downloader.download(representation, seg_id)
            if result.status != 200:
                raise ConnectionError(
                    f"server returned {result.status} for "
                    f"{representation}/segment_{seg_id:03d}"
                )

            buffer_after = buffer_manager.level
            instant = result.throughput
            ewma_value = ewma.update(instant)

            switch = index != current_index
            if switch:
                n_switches += 1
                collector.record_switch(seg_id, abr.bitrate(current_index), bitrate)
                current_index = index

            buffer_manager.put(
                BufferedSegment(
                    segment_id=seg_id,
                    representation=representation,
                    bitrate=bitrate,
                    duration=result.duration or 2.0,
                    size=result.size,
                )
            )
            buffer_after = buffer_manager.level   # capture before DB write
            qualities.append(abr.quality(index))

            collector.record_segment(
                timestamp=time.time(),
                segment_id=seg_id,
                representation=representation,
                bitrate=bitrate,
                size=result.size,
                download_time=result.download_time,
                instant_throughput=instant,
                ewma_throughput=ewma_value,
                buffer_before=buffer_before,
                buffer_after=buffer_after,
                quality_switch=switch,
                rebuffer_event=False,
                rebuffer_duration=0.0,
                network_profile=profile_name,
                abr=abr.name,
            )
            if verbose:
                print(
                    f"[{abr.name}] seg {seg_id:03d} {representation:>5} "
                    f"{bitrate // 1000:>5} kbps  "
                    f"dl={result.download_time * 1000:6.1f} ms  "
                    f"tput={instant / 1e6:5.2f} Mbps  "
                    f"buf={buffer_after:5.1f}s"
                )
    finally:
        report = playback.join_session(timeout=segment_count * 10 + 60)
        client.close()

    # --- rebuffer events -> SQLite -------------------------------------
    for offset, duration, seg_id in report.rebuffer_events:
        collector.record_rebuffer(offset, duration, seg_id)

    avg_bitrate = (
        sum(q * DEFAULT_LADDER[-1][1] for q in qualities) / len(qualities)
        if qualities else 0.0
    )
    qoe = compute_qoe(qualities, report.rebuffer_seconds, n_switches, qoe_cfg)
    collector.record_qoe(qoe["avg_quality"], avg_bitrate,
                         report.rebuffer_seconds, n_switches, qoe["qoe"])

    summary = {
        "session_id": session_id,
        "abr": abr.name,
        "profile": profile_name,
        "segments": len(qualities),
        "avg_bitrate_bps": avg_bitrate,
        "avg_quality": qoe["avg_quality"],
        "n_switches": n_switches,
        "rebuffer_seconds": report.rebuffer_seconds,
        "startup_delay": report.startup_delay,
        "qoe": qoe["qoe"],
        "wall_time": time.monotonic() - session_start,
    }
    collector.close()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Adaptive streaming client")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--abr", default="rate",
                        choices=["rate", "buffer", "bola", "mpc"])
    parser.add_argument("--hysteresis", action="store_true",
                        help="wrap the ABR in the hysteresis controller")
    parser.add_argument("--profile", default=None,
                        help="experiment profile JSON (client-side shaping)")
    parser.add_argument("--segments", type=int, default=DEFAULT_SEGMENT_COUNT)
    parser.add_argument("--db", default="database/streaming.db")
    parser.add_argument("--client-id", default="client-1")
    parser.add_argument("--speed", type=float, default=4.0,
                        help="playback speed multiplier (4 = 4x fast)")
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--beta", type=float, default=4.5)
    parser.add_argument("--gamma", type=float, default=1.0)
    args = parser.parse_args()

    summary = run_session(
        host=args.host,
        port=args.port,
        abr_name=args.abr,
        use_hysteresis=args.hysteresis,
        profile_path=args.profile,
        segment_count=args.segments,
        db_path=args.db,
        client_id=args.client_id,
        playback_speed=args.speed,
        qoe_cfg=QoEConfig(args.alpha, args.beta, args.gamma),
    )
    print("\n=== Session summary ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
