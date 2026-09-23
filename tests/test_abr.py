import pytest

from client.abr import (
    ABRState,
    BOLA,
    MPC,
    BufferBasedABR,
    HysteresisABR,
    RateBasedABR,
)

LADDER = [("360p", 500_000), ("480p", 1_000_000),
          ("720p", 2_500_000), ("1080p", 5_000_000)]


def state(buffer_level=20.0, throughput=10e6, current=0, seg=1):
    return ABRState(buffer_level=buffer_level, throughput_bps=throughput,
                    segment_id=seg, current_index=current)


def test_rate_based_scales_with_throughput():
    abr = RateBasedABR(safety=1.0)
    assert abr.select(state(throughput=400_000)) == 0
    assert abr.select(state(throughput=900_000)) == 0   # 500k fits, 1M doesn't
    assert abr.select(state(throughput=1_200_000)) == 1
    assert abr.select(state(throughput=3_000_000)) == 2
    assert abr.select(state(throughput=6_000_000)) == 3


def test_rate_based_respects_safety_margin():
    # 1.1 Mbps raw would fit 1 Mbps, but safety 0.85 rules it out.
    assert RateBasedABR(safety=0.85).select(state(throughput=1_100_000)) == 0
    assert RateBasedABR(safety=1.0).select(state(throughput=1_100_000)) == 1


def test_buffer_based_monotone_in_buffer():
    abr = BufferBasedABR(reserve=8.0, buffer_cap=45.0)
    indices = [abr.select(state(buffer_level=b))
               for b in [0, 8, 15, 22, 30, 38, 45, 60]]
    assert indices == sorted(indices), "quality must not decrease as buffer grows"
    assert indices[0] == 0
    assert indices[-1] == 3


def test_buffer_based_clamps():
    abr = BufferBasedABR(reserve=8.0, buffer_cap=45.0)
    assert abr.select(state(buffer_level=0)) == 0
    assert abr.select(state(buffer_level=1000)) == 3


def test_bola_saturation_regions():
    abr = BOLA(b_low=8.0, b_high=45.0)
    assert abr.select(state(buffer_level=2.0)) == 0    # B <= B_low
    assert abr.select(state(buffer_level=60.0)) == 3   # B >= B_high


def test_bola_monotone_in_buffer():
    abr = BOLA(b_low=8.0, b_high=45.0)
    indices = [abr.select(state(buffer_level=b)) for b in range(0, 50, 4)]
    assert indices == sorted(indices)


def test_hysteresis_blocks_premature_upswitch():
    inner = RateBasedABR(safety=1.0)
    abr = HysteresisABR(inner, up_ratio=1.5, stable=2,
                        min_buffer_for_up=12.0, deep_buffer=30.0)
    # Low buffer: candidate is much higher but buffer is unhealthy -> hold.
    assert abr.select(state(buffer_level=5.0, current=0, throughput=6e6)) == 0
    # Candidate close to current (within up_ratio) and shallow buffer -> hold.
    assert abr.select(state(buffer_level=15.0, current=2, throughput=3e6)) == 2


def test_hysteresis_allows_upswitch_when_stable():
    inner = RateBasedABR(safety=1.0)
    abr = HysteresisABR(inner, up_ratio=1.5, stable=2,
                        min_buffer_for_up=12.0, deep_buffer=30.0)
    s = state(buffer_level=35.0, current=0, throughput=6e6)
    assert abr.select(s) == 0      # first observation: hold
    assert abr.select(s) == 3      # second consecutive: switch


def test_hysteresis_downswitch_immediate():
    inner = RateBasedABR(safety=1.0)
    abr = HysteresisABR(inner, stable=3)
    # Throughput collapses: immediate downswitch regardless of hold count.
    assert abr.select(state(buffer_level=40.0, current=3, throughput=400_000)) == 0


def test_mpc_returns_valid_index():
    abr = MPC(horizon=3)
    for buf in [0.0, 5.0, 20.0, 50.0]:
        idx = abr.select(state(buffer_level=buf, throughput=4e6))
        assert 0 <= idx < len(LADDER)


def test_mpc_prefers_high_quality_when_rich_throughput():
    abr = MPC(horizon=3, alpha=1.0, beta=4.5, gamma=1.0)
    # Plenty of throughput and buffer -> 1080p is affordable and rewarding.
    assert abr.select(state(buffer_level=40.0, throughput=20e6)) == 3


def test_mpc_downshifts_when_throughput_collapses():
    abr = MPC(horizon=3, alpha=1.0, beta=4.5, gamma=1.0)
    # 400 kbps cannot sustain 500 kbps without heavy rebuffering penalty.
    assert abr.select(state(buffer_level=3.0, throughput=400_000)) == 0


def test_common_interface():
    for abr in [RateBasedABR(), BufferBasedABR(), BOLA(), MPC()]:
        assert abr.select(state()) in range(len(LADDER))
        assert abr.bitrate(0) == 500_000
        assert 0 <= abr.quality(0) < abr.quality(3) <= 1.0
