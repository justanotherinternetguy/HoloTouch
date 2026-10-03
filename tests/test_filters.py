import math

import numpy as np

from holowm.config import FilterConfig
from holowm.core.filters import MotionTrack, OneEuro


def test_one_euro_removes_jitter_at_rest():
    rng = np.random.default_rng(1)
    f = OneEuro(1.5, 12.0)
    noisy = 0.5 + rng.normal(0, 0.002, size=(120, 2))
    out = np.array([f(p, i / 30.0) for i, p in enumerate(noisy)])
    assert out[30:].std() < noisy[30:].std() * 0.5


def test_one_euro_keeps_up_with_fast_motion():
    f = OneEuro(1.5, 12.0)
    speed = 1.0  # screen heights per second
    out = None
    for i in range(60):
        t = i / 30.0
        out = f(np.array([speed * t, 0.0]), t)
    lag = speed * (59 / 30.0) - out[0]
    assert 0 <= lag < 0.03  # under 30 ms behind at full speed


def test_one_euro_is_the_published_algorithm():
    """Sample by sample against the 1€ filter as Casiez's reference code computes it."""
    rng = np.random.default_rng(7)
    t = 100.0 + np.cumsum(rng.uniform(0.02, 0.07, 400))  # a camera that drops and delays frames
    x = np.sin(t * 1.3) * 0.4 + np.where(t % 6 > 3, 2.0 * (t % 3), 0.0) + rng.normal(0, 0.01, t.size)
    min_cutoff, beta, d_cutoff = 1.5, 12.0, 1.0

    def alpha(cutoff, dt):
        return 1.0 / (1.0 + (1.0 / (2 * math.pi * cutoff)) / dt)

    expected, x_hat, dx_hat = [x[0]], x[0], 0.0
    for i in range(1, t.size):
        dt = t[i] - t[i - 1]
        dx_hat = alpha(d_cutoff, dt) * ((x[i] - x_hat) / dt) + (1 - alpha(d_cutoff, dt)) * dx_hat
        a = alpha(min_cutoff + beta * abs(dx_hat), dt)
        x_hat = a * x[i] + (1 - a) * x_hat
        expected.append(x_hat)
    f = OneEuro(min_cutoff, beta, d_cutoff)
    assert np.allclose([float(f(v, ts)) for v, ts in zip(x, t)], expected, rtol=0, atol=1e-12)


def test_one_euro_filters_each_point_at_its_own_speed():
    rng = np.random.default_rng(2)
    jitter = rng.normal(0, 0.002, size=(120, 2, 3))
    travel = np.zeros((120, 2, 3))
    travel[:, 1, 0] = 0.5 * np.arange(120) / 30.0  # the second point moves at 0.5 m/s
    both, alone = OneEuro(4.0, 60.0), OneEuro(4.0, 60.0)
    out = np.array([both(jitter[i] + travel[i], i / 30.0) for i in range(120)])
    still = np.array([alone(jitter[i, 0], i / 30.0) for i in range(120)])
    # The still point is smoothed exactly as if the moving one were not there...
    assert np.array_equal(out[:, 0], still)
    assert out[30:, 0].std() < jitter[30:, 0].std() * 0.7
    # ...while the moving one is followed closely.
    assert abs(out[-1, 1, 0] - travel[-1, 1, 0]) < 0.004


def test_one_euro_ignores_a_sample_that_is_not_newer():
    f = OneEuro(1.0, 0.5)
    f(0.0, 1.0)
    first = float(f(1.0, 1.1))
    assert float(f(5.0, 1.1)) == first  # the same camera frame seen again
    again = OneEuro(1.0, 0.5)
    again(0.0, 1.0), again(1.0, 1.1)
    assert float(f(2.0, 1.2)) == float(again(2.0, 1.2))


def test_prediction_compensates_latency():
    cfg = FilterConfig()
    track = MotionTrack(cfg)
    speed, latency = 0.8, 0.03
    for i in range(45):
        t = i / 30.0
        track.update(np.array([speed * t, 0.5]), t)
    now = 44 / 30.0 + latency
    truth = speed * now
    unpredicted_error = abs(truth - speed * (44 / 30.0))
    assert abs(track.predict(now)[0] - truth) < unpredicted_error * 0.6


def test_prediction_is_bounded_when_samples_stop():
    cfg = FilterConfig()
    track = MotionTrack(cfg)
    for i in range(30):
        track.update(np.array([i / 30.0, 0.5]), i / 30.0)
    last = 29 / 30.0
    soon, later = track.predict(last + 0.2), track.predict(last + 2.0)
    assert np.allclose(soon, later)


def test_step_is_continuous_across_samples():
    cfg = FilterConfig()
    track = MotionTrack(cfg)
    positions = []
    t = 0.0
    for tick in range(240):
        t = tick / 120.0
        if tick % 4 == 0:
            track.update(np.array([0.5 * t, 0.5]), t - 0.03)
        if tick >= 8:
            positions.append(track.step(t)[0])
    steps = np.diff(positions)
    assert steps.min() > 0
    assert steps[60:].max() < 2.0 * steps[60:].mean()
