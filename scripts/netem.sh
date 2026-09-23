#!/usr/bin/env bash
# Network emulation profiles with tc + netem (document section 17).
# Linux only. Run as root on the interface carrying server traffic.
#
# Usage:
#   sudo ./scripts/netem.sh stable
#   sudo ./scripts/netem.sh sudden_drop     # applies 10 Mbps, re-run at 30s/60s
#   sudo ./scripts/netem.sh reset
set -euo pipefail

IFACE="${IFACE:-lo}"
ACTION="${1:-stable}"

reset() {
  tc qdisc del dev "$IFACE" root 2>/dev/null || true
  echo "cleared qdisc on $IFACE"
}

case "$ACTION" in
  stable)
    reset
    tc qdisc add dev "$IFACE" root tbf rate 10mbit burst 32kbit latency 40ms
    tc qdisc add dev "$IFACE" parent 1:1 handle 10: netem delay 20ms
    echo "stable: 10 Mbps, 20 ms, 0% loss"
    ;;
  sudden_drop)
    reset
    tc qdisc add dev "$IFACE" root tbf rate 10mbit burst 32kbit latency 40ms
    echo "sudden_drop stage 1: 10 Mbps (then run again with 2 / 8 at t=30s/60s)"
    ;;
  fluctuating)
    reset
    tc qdisc add dev "$IFACE" root tbf rate 5mbit burst 32kbit latency 40ms
    tc qdisc add dev "$IFACE" parent 1:1 handle 10: netem delay 40ms 0% loss
    echo "fluctuating: 5 Mbps mid-point; alternate rates manually"
    ;;
  high_latency)
    reset
    tc qdisc add dev "$IFACE" root tbf rate 5mbit burst 32kbit latency 300ms
    tc qdisc add dev "$IFACE" parent 1:1 handle 10: netem delay 150ms
    echo "high_latency: 5 Mbps, 150 ms"
    ;;
  drop2)
    reset
    tc qdisc add dev "$IFACE" root tbf rate 2mbit burst 32kbit latency 60ms
    tc qdisc add dev "$IFACE" parent 1:1 handle 10: netem delay 50ms
    echo "sudden_drop stage 2: 2 Mbps, 50 ms"
    ;;
  rise8)
    reset
    tc qdisc add dev "$IFACE" root tbf rate 8mbit burst 32kbit latency 40ms
    tc qdisc add dev "$IFACE" parent 1:1 handle 10: netem delay 20ms
    echo "sudden_drop stage 3: 8 Mbps, 20 ms"
    ;;
  reset)
    reset
    ;;
  *)
    echo "unknown profile: $ACTION" >&2
    exit 1
    ;;
esac

tc qdisc show dev "$IFACE"
