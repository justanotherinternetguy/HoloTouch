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
        ("pinch_pinky", Pose.PINCH_PINKY),
        ("fist", Pose.FIST),
        ("two_finger", Pose.TWO_FINGER),
        ("point", Pose.NEUTRAL),
        ("aim", Pose.AIM),
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


def test_thumb_of_a_pointing_hand_presses_only_from_held_out():
    tracker = PoseTracker(PoseConfig())
    # Pointing with the thumb tucked in from the start is only pointing, however long it lasts.
    assert settle(tracker, "point", frames=30) is Pose.NEUTRAL
    # The thumb held out takes aim, and from there it comes down to press and lifts to let go.
    assert settle(tracker, "aim", start=2.0) is Pose.AIM
    assert settle(tracker, "press", start=3.0) is Pose.PRESS
    assert settle(tracker, "aim", start=4.0) is Pose.AIM
    assert settle(tracker, "open", start=5.0) is Pose.OPEN


def test_press_is_measured_to_the_middle_finger_wherever_the_thumb_lands_on_it():
    assert features("point").thumb_tuck < 0.15 < 0.5 < features("aim").thumb_tuck
    # The thumb halfway down is neither: the hand goes on aiming, and one pressing goes on pressing.
    halfway = replace(features("aim"), thumb_tuck=0.33)
    tracker = PoseTracker(PoseConfig())
    settle(tracker, "aim")
    for i in range(6):
        assert tracker.update(halfway, 1.0 + i / 30.0) is Pose.AIM
    settle(tracker, "press", start=2.0)
    for i in range(6):
        assert tracker.update(halfway, 3.0 + i / 30.0) is Pose.PRESS


def test_pointing_hand_turned_from_the_camera_does_not_take_aim():
    turned = extract_features(make_hand(Config(), SCREEN, "aim", 1000, 900, yaw=60.0))
    assert classify(turned) is Pose.NEUTRAL
    # A hand already aiming may turn: where its thumb is was settled while it could be seen.
    tracker = PoseTracker(PoseConfig())
    settle(tracker, "aim")
    for i in range(6):
        assert tracker.update(turned, 1.0 + i / 30.0) is Pose.AIM


def test_letter_y_takes_thumb_and_pinky_out_and_a_moment_to_count():
    tracker = PoseTracker(PoseConfig())
    assert settle(tracker, "y_sign", frames=8) is Pose.NEUTRAL  # a quarter of a second is not yet long enough
    assert settle(tracker, "y_sign", start=8 / 30.0, frames=4) is Pose.Y_SIGN
    assert settle(tracker, "open", start=2.0) is Pose.OPEN
    # The pinky out alone, the thumb folded over the other fingers, is the letter I: no gesture.
    letter_i = replace(features("y_sign"), thumb_tuck=0.1)
    assert classify(letter_i) is Pose.NEUTRAL
    for i in range(12):
        pose = tracker.update(letter_i, 3.0 + i / 30.0)
    assert pose is Pose.NEUTRAL
    # Once the sign is made, the thumb may drift in: the pinky keeps it.
    settle(tracker, "y_sign", start=4.0, frames=12)
    for i in range(6):
        assert tracker.update(letter_i, 5.0 + i / 30.0) is Pose.Y_SIGN


def test_letter_y_is_not_taken_for_a_fist_by_its_short_pinky():
    # A pinky held out, but short: its tip is no further from its knuckle than a curled finger's.
    y = features("y_sign")
    short = replace(y, curl=(*y.curl[:3], 0.5))
    assert all(c < PoseConfig().fist_enter for c in short.curl)
    tracker = PoseTracker(PoseConfig())
    for i in range(12):
        pose = tracker.update(short, i / 30.0)
    assert pose is Pose.Y_SIGN
    # Coming out of a real fist, too, where a fist is let go of later than it is made.
    tracker = PoseTracker(PoseConfig())
    settle(tracker, "fist")
    for i in range(12):
        pose = tracker.update(short, 1.0 + i / 30.0)
    assert pose is Pose.Y_SIGN


def test_letter_y_turned_from_the_camera_is_not_read():
    turned = extract_features(make_hand(Config(), SCREEN, "y_sign", 1000, 900, yaw=60.0))
    tracker = PoseTracker(PoseConfig())
    for i in range(12):
        pose = tracker.update(turned, i / 30.0)
    assert pose is not Pose.Y_SIGN


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
