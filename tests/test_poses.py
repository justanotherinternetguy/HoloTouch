from dataclasses import replace

import pytest

from holowm.config import Config, PoseConfig
from holowm.core.poses import Pose, PoseTracker, extract_features
from holowm.launcher.menu import BACK, MenuItem, PieSession, layout_angles
from holowm.config import PieConfig
from synth import make_hand

SCREEN = (2880, 1800)


def features(pose):
    return extract_features(make_hand(Config(), SCREEN, pose, 1000, 900))


def settle(tracker, pose, start=0.0, frames=6):
    result = None
    for i in range(frames):
        result = tracker.update(features(pose), start + i / 30.0)
    return result


@pytest.mark.parametrize(
    "name,expected",
    [
        ("open", Pose.OPEN),
        ("neutral", Pose.NEUTRAL),
        ("pinch_index", Pose.PINCH_INDEX),
        ("pinch_middle", Pose.PINCH_MIDDLE),
        ("pinch_pinky", Pose.PINCH_PINKY),
        ("fist", Pose.FIST),
        ("two_finger", Pose.TWO_FINGER),
        ("point", Pose.NEUTRAL),
    ],
)
def test_each_pose_is_recognised(name, expected):
    assert settle(PoseTracker(PoseConfig()), name) is expected


@pytest.mark.parametrize("tilt", [-30, 0, 25, 60, 90])
def test_finger_tilt_is_measured_and_keeps_the_two_finger_pose(tilt):
    hand = extract_features(make_hand(Config(), SCREEN, "two_finger", 1000, 900, tilt=tilt))
    assert hand.finger_tilt == pytest.approx(tilt, abs=0.5)
    tracker = PoseTracker(PoseConfig())
    for i in range(6):
        pose = tracker.update(hand, i / 30.0)
    assert pose is Pose.TWO_FINGER


def test_palm_anchor_does_not_move_when_pinching():
    assert features("open").palm == pytest.approx(features("pinch_index").palm)


def test_pinch_needs_more_than_one_frame():
    tracker = PoseTracker(PoseConfig())
    settle(tracker, "open")
    assert tracker.update(features("pinch_index"), 1.0) is Pose.OPEN
    assert tracker.update(features("pinch_index"), 1.0 + 1 / 30) is Pose.PINCH_INDEX


def test_single_dropped_frame_does_not_release_pinch():
    tracker = PoseTracker(PoseConfig())
    settle(tracker, "pinch_index")
    assert tracker.update(features("open"), 1.0) is Pose.PINCH_INDEX
    assert tracker.update(features("pinch_index"), 1.0 + 1 / 30) is Pose.PINCH_INDEX
    # A sustained open hand does release it.
    assert settle(tracker, "open", start=2.0) is Pose.OPEN


def test_pinch_type_is_locked_until_release():
    tracker = PoseTracker(PoseConfig())
    settle(tracker, "pinch_index")
    # The pinky closing in during an index pinch does not turn it into a pinky pinch.
    both = replace(features("pinch_index"), pinch_pinky=0.05)
    for i in range(6):
        assert tracker.update(both, 1.0 + i / 30.0) is Pose.PINCH_INDEX
    settle(tracker, "open", start=2.0)
    assert settle(tracker, "pinch_pinky", start=3.0) is Pose.PINCH_PINKY


def classify(hand_features):
    tracker = PoseTracker(PoseConfig())
    for i in range(6):
        pose = tracker.update(hand_features, i / 30.0)
    return pose


def test_pinky_pinch_has_to_beat_every_other_finger():
    # Scroll pose with the thumb folded over ring and pinky: both fingertips are at the thumb.
    folded = replace(features("two_finger"), pinch_pinky=0.15, pinch_others=0.17)
    assert classify(folded) is Pose.TWO_FINGER
    # Thumb on the pinky alone, the other fingers clear of it.
    assert classify(replace(features("two_finger"), pinch_pinky=0.15, pinch_others=0.9)) is Pose.PINCH_PINKY
    # Thumb meeting the middle finger is no gesture any more.
    assert classify(replace(features("open"), pinch_others=0.1)) is Pose.OPEN
    # Index and pinky both at the thumb: the index pinch is the default.
    assert classify(replace(features("pinch_index"), pinch_pinky=0.1)) is Pose.PINCH_INDEX


def test_layout_angles():
    assert layout_angles(4, None) == [0, 90, 180, 270]
    assert layout_angles(3, 180.0) == [270, 0, 90]
    assert layout_angles(0, None) == []


def pie(children):
    return PieSession(MenuItem("Root", children=children), 1000, 900, PieConfig(), 1.0, SCREEN)


def test_pie_direction_picks_item_and_dead_zone_cancels():
    items = [MenuItem(n, "command", n) for n in ("up", "right", "down", "left")]
    session = pie(items)
    session.update(1000, 900 - 30)
    assert session.release() is None  # inside the dead zone
    session.update(1000 + 400, 900 + 20)
    assert session.release().name == "right"
    session.update(1000 - 60, 900 - 10)
    assert session.release().name == "left"


def test_pie_submenu_enter_and_back():
    sub = MenuItem("More", children=[MenuItem("a", "command", "a"), MenuItem("b", "command", "b")])
    session = pie([MenuItem("top", "command", "top"), sub])
    # Item 1 points down (180 degrees). Hovering inside the stroke length does not enter it.
    session.update(1000, 900 + 100)
    assert len(session.stack) == 1 and session.release() is None
    session.update(1000, 900 + 160)
    assert len(session.stack) == 2
    level = session.stack[-1]
    assert (level.cx, level.cy) == (1000, 1060)
    assert level.back_angle == 0.0  # back is toward where we came from
    assert level.angles == [120.0, 240.0]
    # Straight back up past the stroke length returns to the parent.
    session.update(1000, 1060 - 100)
    assert session.hover == BACK and session.release() is None
    session.update(1000, 1060 - 160)
    assert len(session.stack) == 1


def test_pie_is_clamped_on_screen():
    session = PieSession(MenuItem("Root", children=[MenuItem("a", "command", "a")]), 5, 5, PieConfig(), 2.0, SCREEN)
    view = session.view()
    assert view["cx"] > 200 and view["cy"] > 200
