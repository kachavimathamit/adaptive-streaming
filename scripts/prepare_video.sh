#!/usr/bin/env bash
# Offline video preparation with FFmpeg (document section 16).
# Generates 4 representations split into 2-second segments.
#
# Usage: ./scripts/prepare_video.sh input.mp4 server/media
set -euo pipefail

INPUT="${1:-sample.mp4}"
OUT="${2:-server/media}"
DURATION=2

mkdir -p "$OUT"

# HLS-style output produces playlist + segment files per rendition.
declare -A LADDER=( [360p]=640:360:500k [480p]=854:480:1000k [720p]=1280:720:2500k [1080p]=1920:1080:5000k )

for rep in "${!LADDER[@]}"; do
  IFS=: read -r w h rate <<< "${LADDER[$rep]}"
  mkdir -p "$OUT/$rep"
  ffmpeg -y -i "$INPUT" \
    -vf "scale=${w}:${h}" -b:v "$rate" -c:v libx264 -profile:v main \
    -g 48 -keyint_min 48 -sc_threshold 0 \
    -f hls -hls_time "$DURATION" -hls_playlist_type vod \
    -hls_segment_filename "$OUT/$rep/segment_%03d.m4s" \
    "$OUT/$rep/index.m3u8"
done

# Build the manifest consumed by the server.
python - "$OUT" <<'PY'
import json, sys, pathlib
out = pathlib.Path(sys.argv[1])
ladder = {"360p": 500_000, "480p": 1_000_000, "720p": 2_500_000, "1080p": 5_000_000}
counts = {}
for rep in ladder:
    segs = sorted((out / rep).glob("segment_*.m4s"))
    counts[rep] = len(segs)
n = min(counts.values()) if counts else 0
manifest = {
    "segment_duration": 2,
    "segment_count": n,
    "representations": {rep: {"bitrate": br} for rep, br in ladder.items()},
}
(out / "manifest.json").write_text(json.dumps(manifest, indent=2))
print(f"wrote {out/'manifest.json'} with {n} segments per representation")
PY
