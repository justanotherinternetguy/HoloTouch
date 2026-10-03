"""Smoothing of the finger landmarks inside a tracked hand."""

from dataclasses import replace

import numpy as np

from holowm.config import Config
from holowm.core.hands import HandTracker
from holowm.core.poses import Pose, PoseTracker, extract_features
from holowm.tracker.types import THUMB_TIP, FrameSample
from synth import make_hand, world_landmarks

SCREEN = (2880, 1800)
JITTER = (0.0015, 0.0015, 0.004)  # metres; depth is the least certain
HZ = 30.0


def hand_with(world):
    return replace(make_hand(Config(), SCREEN, "open", 1000, 900), world=world.astype(np.float32))


def track(samples, cfg=None):
    """Feed one hand per camera frame; yields the tracked hand after each frame."""
    tracker = HandTracker(cfg or Config(), SCREEN)
    for i, sample in enumerate(samples):
        t = 50.0 + i / HZ
        tracker.update(FrameSample(i, t, t, [sample]))
        (hand,) = tracker.hands.values()
        yield hand


def test_finger_jitter_is_smoothed_before_the_pose_is_read():
    rng = np.random.default_rng(3)
    still = world_landmarks("two_finger", 20)
    samples = [hand_with(still + rng.normal(0, JITTER, still.shape)) for _ in range(150)]
    raw = [extract_features(s) for s in samples][30:]
    smoothed = [hand.features for hand in track(samples)][30:]
    for name in ("pinch_others", "pinch_pinky", "finger_tilt"):  # each read from the metric landmarks alone
        before = np.std([getattr(f, name) for f in raw])
        after = np.std([getattr(f, name) for f in smoothed])
        assert after < 0.75 * before, name
    # Smoothing settles on the same hand shape, not a different one.
    assert abs(np.mean([f.finger_tilt for f in smoothed]) - 20.0) < 1.0


def pinch_frames(phase):
    """A relaxed hand that pinches within 100 ms, holds, and lets go as fast."""
    pinched = world_landmarks("pinch_index")
    apart = pinched.copy()
    apart[THUMB_TIP] += (-0.03, 0.012, -0.01)  # thumb tip 3.5 cm off the index fingertip

    def closed(t):
        if t < 1.5:
            f = (t - 0.5 - phase) / 0.1
        else:
            f = 1.0 - (t - 1.5 - phase) / 0.1
        f = min(max(f, 0.0), 1.0)
        return f * f * (3 - 2 * f)

    return [hand_with(apart + (pinched - apart) * closed(i / HZ)) for i in range(int(2.5 * HZ))]


def pinch_span(poses):
    pinching = [i for i, pose in enumerate(poses) if pose is Pose.PINCH_INDEX]
    return pinching[0], pinching[-1]


def test_smoothing_does_not_hold_back_a_quick_pinch():
    for phase in (0.0, 0.008, 0.017, 0.025):  # where the movement starts between two frames
        samples = pinch_frames(phase)
        unsmoothed = PoseTracker(Config().pose)
        expected = pinch_span([unsmoothed.update(extract_features(s), i / HZ) for i, s in enumerate(samples)])
        got = pinch_span([hand.pose for hand in track(samples)])
        # Never more than one camera frame late to grab or to let go.
        assert 0 <= got[0] - expected[0] <= 1, phase
        assert 0 <= got[1] - expected[1] <= 1, phase
