import math

import pytest

from client.throughput import EWMA, MovingAverage


def test_ewma_first_sample_sets_value():
    ewma = EWMA(alpha=0.3)
    assert ewma.estimate is None
    ewma.update(1000.0)
    assert ewma.estimate == 1000.0


def test_ewma_recursion():
    ewma = EWMA(alpha=0.5, initial=100.0)
    ewma.update(200.0)
    assert ewma.value == pytest.approx(0.5 * 200 + 0.5 * 100)
    ewma.update(300.0)
    assert ewma.value == pytest.approx(0.5 * 300 + 0.5 * 150)


def test_ewma_rejects_bad_alpha():
    with pytest.raises(ValueError):
        EWMA(alpha=0.0)


def test_moving_average_window():
    ma = MovingAverage(window=3)
    ma.update(10)
    ma.update(20)
    ma.update(30)
    assert ma.value == pytest.approx(20)
    ma.update(40)  # 10 leaves the window
    assert ma.value == pytest.approx(30)


def test_moving_average_empty():
    assert MovingAverage().value is None
