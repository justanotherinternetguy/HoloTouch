"""Smoothing of the finger landmarks inside a tracked hand, and which hands are tracked at all."""

from dataclasses import replace
from itertools import count

import numpy as np

from holotouch.config import Config
from holotouch.core.hands import HandTracker
from holotouch.core.poses import Pose, PoseTracker, extract_features
from holotouch.tracker.types import THUMB_TIP, FrameSample
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


# -- hands in the background ------------------------------------------------------------------

FACE = 2.1  # the scale of the picture at the face synth.make_face draws: a hand of nearness 1.0 is level with it
_frames = count()


def hand_at(x, nearness, handedness="Right"):
    return make_hand(Config(), SCREEN, "open", x, 900, handedness, 0.0, nearness)


def feed(tracker, *hands, face=0.0, frames=5):
    """Show the tracker the same hands for some camera frames, and the face if its scale is given."""
    for _ in range(frames):
        i = next(_frames)
        t = 50.0 + i / HZ
        tracker.update(FrameSample(i, t, t, list(hands)), face)
        tracker.step(t)


def follows(tracker, sample):
    return any(hand.landmarks is sample.image for hand in tracker.hands.values())


def test_a_hand_far_from_the_camera_is_not_followed():
    tracker = HandTracker(Config(), SCREEN)
    mine, far = hand_at(1000, 1.0), hand_at(2000, 0.3)
    feed(tracker, far, mine)
    assert follows(tracker, mine) and not follows(tracker, far)
    assert len(tracker.ignored) == 1 and tracker.ignored[0] is far
    cfg = Config()
    cfg.tracker.min_hand_scale = 0.0
    tracker = HandTracker(cfg, SCREEN)
    feed(tracker, far, mine)
    assert follows(tracker, far) and not tracker.ignored


def test_a_hand_well_behind_the_face_is_someone_elses():
    behind = hand_at(2000, 0.6)
    tracker = HandTracker(Config(), SCREEN)
    feed(tracker, behind)  # with no face to hold it against, it may be the user's own, sat further back
    assert follows(tracker, behind)
    tracker = HandTracker(Config(), SCREEN)
    feed(tracker, behind, face=FACE)
    assert not tracker.hands
    level = hand_at(2000, 1.0)
    feed(tracker, behind, level, face=FACE)
    assert follows(tracker, level) and len(tracker.hands) == 1


def test_a_hand_being_followed_is_kept_a_little_past_the_limit():
    drawn_back = hand_at(1000, 0.7)
    tracker = HandTracker(Config(), SCREEN)
    feed(tracker, drawn_back, face=FACE)
    assert not tracker.hands  # too far back to be taken up
    feed(tracker, hand_at(1000, 0.8), face=FACE)
    feed(tracker, drawn_back, face=FACE, frames=15)
    assert follows(tracker, drawn_back)
    feed(tracker, hand_at(1000, 0.6), face=FACE, frames=15)
    assert not tracker.hands


def test_a_nearer_hand_takes_the_place_of_one_in_the_background():
    # Two people behind the user are seen first, and with no face in view they pass for users.
    tracker = HandTracker(Config(), SCREEN)
    behind = [hand_at(600, 0.5), hand_at(2200, 0.5, "Left")]
    feed(tracker, *behind)
    assert all(follows(tracker, hand) for hand in behind)
    mine = hand_at(1400, 1.0)
    feed(tracker, *behind, mine)
    assert follows(tracker, mine) and sum(follows(tracker, hand) for hand in behind) == 1
    other = hand_at(1000, 0.9, "Left")
    feed(tracker, *behind, mine, other)
    assert follows(tracker, mine) and follows(tracker, other)
    assert len(tracker.ignored) == 2


def test_a_third_hand_about_as_near_takes_no_place():
    tracker = HandTracker(Config(), SCREEN)
    two = [hand_at(600, 1.0), hand_at(2200, 1.0, "Left")]
    feed(tracker, *two)
    ids = sorted(tracker.hands)
    third = hand_at(1400, 1.2)
    feed(tracker, third, *two)
    assert sorted(tracker.hands) == ids and not follows(tracker, third)
