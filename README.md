# Adaptive Video Streaming & Buffer Management Engine

Team 14 • Theme 03 — Python socket-programming implementation of an
adaptive (ABR) video streaming stack. Non-AI/ML: EWMA, Rate-Based,
Buffer-Based, BOLA, Hysteresis and MPC controllers over a custom
HTTP-like protocol on TCP sockets.

## Architecture

```
FFmpeg -> multi-bitrate segment store -> TCP server (thread per client)
   TCP client -> EWMA estimator -> ABR engine -> deadline scheduler
   -> thread-safe FIFO buffer (deque + Lock/Condition)
   -> playback thread -> SQLite metrics -> QoE analysis / plots
```

## Layout

```
adaptive-streaming/
├── common/            shared config + protocol (request/response format)
├── server/            TCP server: server.py, connection_handler.py,
│                      request_parser.py, segment_manager.py, media/
├── client/
│   ├── client.py      session orchestration (CLI entry point)
│   ├── network/       socket_client.py, downloader.py, shaper.py
│   ├── abr/           base, rate_based, buffer_based, bola, hysteresis, mpc
│   ├── throughput/    ewma.py, moving_average.py
│   ├── buffer/        buffer_manager.py (deque, FIFO, B(t))
│   ├── scheduler/     priority_queue.py (heapq), deadline_scheduler.py
│   ├── playback/      playback_controller.py (consumer thread)
│   └── metrics/       collector.py (SQLite), qoe.py
├── experiments/       network profiles (stable, sudden_drop, ...)
├── analysis/          analyze.py (tables/CSV), plots.py (matplotlib)
├── scripts/           prepare_video.sh (FFmpeg), netem.sh (tc/netem)
├── tests/             pytest unit + end-to-end tests
├── database/          streaming.db (created at runtime)
└── requirements.txt
```

## Quick start

```bash
pip install -r requirements.txt

# terminal 1 — server (synthetic segments are generated automatically
# if no FFmpeg-prepared media exists)
python -m server.server --host 127.0.0.1 --port 9000

# terminal 2 — client
python -m client.client --abr rate --segments 60 --speed 4 \
    --profile experiments/stable.json

# other controllers
python -m client.client --abr buffer --profile experiments/fluctuating.json
python -m client.client --abr bola --hysteresis --profile experiments/sudden_drop.json
python -m client.client --abr mpc --profile experiments/high_latency.json
```

Analysis:

```bash
python -m analysis.analyze --db database/streaming.db --csv analysis/out.csv
python -m analysis.plots    --db database/streaming.db --out analysis/output
```

Tests:

```bash
python -m pytest tests -q
```

## Custom protocol

Request:  `GET /video/720p/segment_001.m4s\r\n`

Response metadata (then exactly `SIZE` bytes):

```
STATUS 200
SIZE 524288
BITRATE 2500000
DURATION 2
REPRESENTATION 720p
SEGMENT 1
DATA
<raw bytes>
```

## Real video (optional)

```bash
./scripts/prepare_video.sh input.mp4 server/media   # requires FFmpeg
```

## Network emulation

Prefer Linux `tc`/`netem` so the TCP transfer itself experiences the
imposed conditions:

```bash
sudo ./scripts/netem.sh stable        # 10 Mbps, 20 ms
sudo ./scripts/netem.sh high_latency  # 5 Mbps, 150 ms
sudo ./scripts/netem.sh reset
```

On machines without `tc` (e.g. Windows) pass `--profile experiments/*.json`;
the client-side shaper applies the same latency/bandwidth timeline before
measurements are recorded.

## QoE

`QoE = α·mean_quality − β·T_rebuffer − γ·N_switch`

Weights are configurable via `--alpha/--beta/--gamma`; the same network
profiles are replayed across all five ABR controllers for comparison.
