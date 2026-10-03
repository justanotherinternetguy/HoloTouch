import gzip
import json
import math
from pathlib import Path

import numpy as np
import pytest

from holowm.config import Config
from holowm.core.actions import WindowInfo
from holowm.core.interactions import CameraInteraction, ClickInteraction, MoveInteraction, ScrollInteraction
from holowm.launcher.menu import MenuItem
from holowm.tracker.types import FrameSample
from synth import Sim, make_face, screen_point

WIN = dict(x=500, y=400, w=800, h=600)
CENTRE = (900, 700)


@pytest.fixture
def sim():
    s = Sim()
    s.backend.add_window(WindowInfo(1, **WIN, title="one"))
    return s


def arm(sim, at=CENTRE, pose="open"):
    sim.hold(0.4, (pose, *at))


def test_hover_outlines_window_under_hand(sim):
    arm(sim)
    frame = sim.engine.overlay.frame
    assert frame is not None and frame.mode == "hover" and (frame.x, frame.y) == (500, 400)
    assert not sim.backend.commands


def test_pinch_grabs_and_moves_window_relative_to_hand(sim):
    arm(sim)
    sim.hold(0.2, ("pinch_index", *CENTRE))
    assert sim.commands("activate") == [("activate", 1)]
    win = sim.backend.get(1)
    assert abs(win.x - 500) <= 3 and abs(win.y - 400) <= 3  # no jump on grab
    sim.glide(1.0, "pinch_index", CENTRE, (1500, 900))
    sim.hold(0.3, ("pinch_index", 1500, 900))
    sim.hold(0.3, ("open", 1500, 900))
    assert abs(win.x - 1100) <= 4 and abs(win.y - 600) <= 4
    assert (win.w, win.h) == (800, 600)
    assert sim.engine.active is None
    assert not sim.commands("minimize") and not sim.commands("set_maximized")


def test_hand_that_enters_already_pinched_does_not_grab(sim):
    sim.hold(0.6, ("pinch_index", *CENTRE))
    sim.glide(0.5, "pinch_index", CENTRE, (1400, 900))
    assert not sim.backend.commands


def test_pinch_over_empty_desktop_does_not_grab_later(sim):
    arm(sim, at=(2500, 1500))
    sim.hold(0.2, ("pinch_index", 2500, 1500))
    sim.glide(0.6, "pinch_index", (2500, 1500), CENTRE)
    sim.hold(0.2, ("pinch_index", *CENTRE))
    assert not sim.backend.commands


def test_fast_reach_does_not_grab(sim):
    sim.hold(0.3, ("open", 2400, 1500))
    sim.glide(0.15, "open", (2400, 1500), (1100, 800))
    sim.glide(0.1, "pinch_index", (1100, 800), CENTRE)
    assert not sim.commands("activate")


def turned(pose, x, y, yaw=60.0):
    """A hand turned `yaw` degrees away from facing the camera."""
    return (pose, x, y, "Right", 0.0, 1.0, 0.0, yaw)


def pinch_on_the_move(sim, yaw):
    """An open hand crosses the window at about a screen height a second and pinches halfway over."""
    sim.hold(0.4, turned("open", 600, 700, yaw))
    sim.run(0.4, lambda f: [turned("open" if f < 0.5 else "pinch_index", 600 + 700 * f, 700, yaw)])


def test_hand_turned_from_the_camera_has_to_be_slow_to_grab(sim):
    pinch_on_the_move(sim, yaw=60.0)
    assert sim.engine.active is None and not sim.backend.commands


def test_hand_facing_the_camera_grabs_on_the_move(sim):
    pinch_on_the_move(sim, yaw=0.0)
    assert isinstance(sim.engine.active, MoveInteraction)


def test_side_on_pinch_made_in_place_grabs(sim):
    sim.hold(0.4, turned("open", *CENTRE))
    sim.hold(0.3, turned("pinch_index", *CENTRE))
    assert sim.commands("activate") == [("activate", 1)]


def test_window_stays_put_until_the_pinch_has_lasted(sim):
    arm(sim)
    sim.run(0.12, lambda f: [("pinch_index", CENTRE[0] + 240 * f, CENTRE[1])])
    assert sim.engine.active is not None and not sim.backend.commands
    sim.hold(0.3, ("pinch_index", CENTRE[0] + 240, CENTRE[1]))
    assert abs(sim.backend.get(1).x - 740) <= 4  # it has caught up with the hand


def short_grab(sim, dx=0, dy=0, at=CENTRE):
    """A pinch that is over a quarter of a second after it began, the hand travelling as it ends."""
    sim.hold(0.1, ("pinch_index", *at))
    sim.run(0.12, lambda f: [("pinch_index", at[0] + dx * f, at[1] + dy * f)])
    sim.hold(0.3, ("open", at[0] + dx, at[1] + dy))


def test_grab_that_is_over_at_once_puts_the_window_back(sim):
    sim.backend.add_window(WindowInfo(2, 1900, 400, 600, 600, title="two"))
    sim.backend.activate(2)
    arm(sim)
    short_grab(sim, dx=300)
    win = sim.backend.get(1)
    assert sim.commands("move_resize")  # it had begun to follow the hand
    assert (win.x, win.y, win.w, win.h) == (500, 400, 800, 600)
    assert sim.backend.active_window().id == 2  # and the window in use before is in use again


def test_grab_that_is_over_at_once_cannot_flick_the_window_away(sim):
    arm(sim)
    short_grab(sim, dy=700)
    assert not sim.commands("minimize") and sim.backend.get(1).y == 400


def test_maximized_window_pulled_free_by_a_grab_that_is_over_at_once_is_maximized_again(sim):
    win = sim.backend.get(1)
    sim.backend.set_maximized(1, True)
    arm(sim, at=(1440, 300))
    short_grab(sim, dx=300, at=(1440, 300))
    assert sim.commands("set_maximized")[1:] == [("set_maximized", 1, False), ("set_maximized", 1, True)]
    sim.backend.set_maximized(1, False)
    assert win.maximized is False and (win.x, win.y, win.w, win.h) == (500, 400, 800, 600)


def test_brief_tracking_dropout_keeps_the_grab(sim):
    arm(sim)
    sim.hold(0.2, ("pinch_index", *CENTRE))
    sim.run(0.15)  # no hands reported
    assert sim.engine.active is not None
    sim.glide(0.5, "pinch_index", CENTRE, (1200, 700))
    sim.hold(0.2, ("pinch_index", 1200, 700))
    assert abs(sim.backend.get(1).x - 800) <= 4


def test_lost_hand_drops_window_in_place(sim):
    arm(sim)
    sim.hold(0.2, ("pinch_index", *CENTRE))
    sim.run(0.6)
    assert sim.engine.active is None
    assert not sim.commands("minimize") and not sim.commands("close")


def test_maximized_window_is_pulled_free_by_dragging(sim):
    win = sim.backend.get(1)
    sim.backend.set_maximized(1, True)
    sim.backend.commands.clear()
    arm(sim, at=(1440, 300))
    sim.hold(0.6, ("pinch_index", 1440, 300))
    assert win.maximized and not sim.commands("set_maximized")  # holding it still leaves it alone
    sim.glide(0.6, "pinch_index", (1440, 300), (1640, 500))
    sim.hold(0.2, ("pinch_index", 1640, 500))
    assert sim.commands("set_maximized") == [("set_maximized", 1, False)]
    assert not win.maximized and (win.w, win.h) == (800, 600)
    # The hand stays at the same relative spot of the restored window.
    assert abs((1640 - win.x) / win.w - 0.5) < 0.02
    sim.glide(0.4, "pinch_index", (1640, 500), (1300, 700))
    sim.hold(0.2, ("pinch_index", 1300, 700))
    assert abs((1300 - win.x) / win.w - 0.5) < 0.02


def test_second_hand_pulls_a_maximized_window_free_to_resize(sim):
    win = sim.backend.get(1)
    sim.backend.set_maximized(1, True)
    left, right = (900, 700), (1900, 700)
    sim.hold(0.4, ("open", *left, "Left"), ("open", *right, "Right"))
    sim.hold(0.2, ("pinch_index", *left, "Left"), ("open", *right, "Right"))
    assert win.maximized
    sim.hold(0.4, ("pinch_index", *left, "Left"), ("pinch_index", *right, "Right"))
    assert not win.maximized and sim.engine.overlay.frame.mode == "resize"


def tap(sim, at=CENTRE):
    sim.hold(0.15, ("pinch_index", *at))
    sim.hold(0.15, ("open", *at))


def test_quick_pinch_only_brings_the_window_to_the_front(sim):
    win = sim.backend.get(1)
    arm(sim)
    tap(sim)
    assert sim.backend.commands == [("activate", 1)]
    tap(sim)  # a second one is no more than that: nothing is clicked, nothing maximized
    assert sim.backend.commands == [("activate", 1)] * 2
    assert (win.x, win.y, win.w, win.h) == (500, 400, 800, 600) and not win.maximized


def test_tap_leaves_the_window_exactly_where_it_was(sim):
    win = sim.backend.get(1)
    arm(sim)
    sim.hold(0.1, ("pinch_index", *CENTRE))
    sim.glide(0.2, "pinch_index", CENTRE, (CENTRE[0] + 40, CENTRE[1]))  # a slow drift, inside a tap
    sim.hold(0.15, ("open", CENTRE[0] + 40, CENTRE[1]))
    assert (win.x, win.y) == (500, 400)


def test_maximized_window_stays_maximized_under_a_tap(sim):
    win = sim.backend.get(1)
    sim.backend.set_maximized(1, True)
    sim.backend.commands.clear()
    at = (1440, 600)
    arm(sim, at=at)
    tap(sim, at=at)
    assert win.maximized and not sim.commands("set_maximized")


def test_pinch_that_drops_out_at_the_start_of_a_drag_grabs_again(sim):
    win = sim.backend.get(1)
    sim.backend.set_maximized(1, True)
    sim.backend.commands.clear()
    start = (1440, 600)
    arm(sim, at=start)
    sim.hold(0.15, ("pinch_index", *start))
    # The hand sets off and tracking loses the pinch for a moment, as it does with motion blur.
    sim.run(0.12, lambda f: [("open", 1440 + 150 * f * f, 600)])
    sim.run(0.4, lambda f: [("pinch_index", 1590 + 600 * f, 600)])
    sim.hold(0.2, ("pinch_index", 2190, 600))
    # It is still a drag: the window comes out of maximize and follows the hand.
    assert sim.engine.active is not None
    assert sim.commands("set_maximized") == [("set_maximized", 1, False)]
    assert not win.maximized and win.x < 2190 < win.x + win.w
    sim.glide(0.4, "pinch_index", (2190, 600), (1500, 900))
    sim.hold(0.2, ("pinch_index", 1500, 900))
    assert win.x < 1500 < win.x + win.w and win.y < 900 < win.y + win.h


def test_fullscreen_window_is_not_grabbable(sim):
    sim.backend.get(1).fullscreen = True
    arm(sim)
    sim.hold(0.3, ("pinch_index", *CENTRE))
    assert not sim.backend.commands


def test_two_handed_resize(sim):
    left, right = (700, 700), (1100, 700)
    sim.hold(0.4, ("open", *left, "Left"), ("open", *right, "Right"))
    sim.hold(0.2, ("pinch_index", *left, "Left"), ("open", *right, "Right"))
    sim.hold(0.2, ("pinch_index", *left, "Left"), ("pinch_index", *right, "Right"))
    assert sim.engine.overlay.frame.mode == "resize"

    def spread(frac):
        return [("pinch_index", 700 - 200 * frac, 700, "Left"), ("pinch_index", 1100 + 200 * frac, 700 + 100 * frac, "Right")]

    sim.run(0.8, spread)
    sim.run(0.3, lambda _: spread(1.0))
    win = sim.backend.get(1)
    assert abs(win.w - 1200) <= 6 and abs(win.h - 700) <= 6
    assert abs((win.x + win.w / 2) - 900) <= 6  # centre follows the midpoint of the hands
    assert "×" in sim.engine.overlay.frame.label
    # Releasing the second hand returns to a plain move without a jump.
    sim.hold(0.3, ("pinch_index", 500, 700, "Left"), ("open", 1300, 800, "Right"))
    assert sim.engine.overlay.frame.mode == "grab"
    assert abs(win.w - 1200) <= 6


def test_resize_respects_minimum_size(sim):
    sim.backend.get(1).min_w = 400
    sim.hold(0.4, ("open", 600, 700, "Left"), ("open", 1200, 700, "Right"))
    sim.hold(0.2, ("pinch_index", 600, 700, "Left"), ("open", 1200, 700, "Right"))
    sim.hold(0.2, ("pinch_index", 600, 700, "Left"), ("pinch_index", 1200, 700, "Right"))
    sim.run(0.6, lambda f: [("pinch_index", 600 + 290 * f, 700, "Left"), ("pinch_index", 1200 - 290 * f, 700, "Right")])
    sim.hold(0.2, ("pinch_index", 890, 700, "Left"), ("pinch_index", 910, 700, "Right"))
    assert sim.backend.get(1).w == 400


def flick(sim, dy):
    arm(sim)
    sim.hold(0.3, ("pinch_index", *CENTRE))
    end = (CENTRE[0], CENTRE[1] + dy)
    sim.run(0.12, lambda f: [("pinch_index", CENTRE[0], CENTRE[1] + dy * f)])
    sim.hold(0.3, ("open", *end))


def test_flick_down_minimizes_and_restores_position(sim):
    flick(sim, 700)
    assert sim.commands("minimize") == [("minimize", 1)]
    last_move = sim.commands("move_resize")[-1]
    assert abs(last_move[3] - 400) < 150  # rewound to roughly where it was before the flick


def test_flick_up_maximizes(sim):
    flick(sim, -500)
    assert sim.commands("set_maximized") == [("set_maximized", 1, True)]
    assert not sim.commands("minimize")


def test_follow_through_after_a_flick_is_not_a_swipe(sim):
    sim.backend.add_window(WindowInfo(2, 300, 900, 1200, 800, title="low"))
    arm(sim, at=(900, 1500))
    sim.hold(0.3, ("pinch_index", 900, 1500))
    sim.run(0.12, lambda f: [("pinch_index", 900, 1500 - 500 * f)])
    # The hand opens and keeps travelling upward before it stops.
    sim.run(0.2, lambda f: [("open", 900, 1000 - 750 * f)])
    sim.hold(0.4, ("open", 900, 250))
    assert sim.commands("set_maximized") == [("set_maximized", 2, True)]
    assert sim.engine.overlay.switcher is None


def test_slow_release_is_a_plain_drop(sim):
    arm(sim)
    sim.hold(0.2, ("pinch_index", *CENTRE))
    sim.glide(1.2, "pinch_index", CENTRE, (900, 1100))
    sim.hold(0.3, ("open", 900, 1100))
    assert not sim.commands("minimize") and not sim.commands("set_maximized")


def test_edge_carry_moves_window_to_next_workspace(sim):
    arm(sim, at=(1200, 700))
    sim.hold(0.2, ("pinch_index", 1200, 700))
    sim.glide(0.5, "pinch_index", (1200, 700), (2879, 700))
    sim.hold(0.2, ("pinch_index", 2879, 700))
    assert sim.engine.overlay.edge_side == 1 and 0 < sim.engine.overlay.edge_progress < 1
    sim.hold(0.4, ("pinch_index", 2879, 700))
    assert sim.commands("set_window_desktop") == [("set_window_desktop", 1, 1)]
    assert sim.backend.current_desktop() == 1
    assert sim.engine.active is not None  # still holding the window
    assert sim.engine.overlay.hud_desktop == 1
    # Leaving the edge before the cooldown ends does not carry again.
    sim.glide(0.4, "pinch_index", (2879, 700), (1500, 700))
    assert len(sim.commands("set_window_desktop")) == 1


def test_edge_carry_stops_at_last_workspace(sim):
    arm(sim, at=(1200, 700))
    sim.hold(0.2, ("pinch_index", 1200, 700))
    sim.glide(0.4, "pinch_index", (1200, 700), (0, 700))
    sim.hold(0.8, ("pinch_index", 0, 700))
    assert not sim.commands("set_window_desktop")


def test_fist_hold_closes_window(sim):
    arm(sim)
    sim.hold(0.4, ("fist", *CENTRE))
    overlay = sim.engine.overlay
    assert overlay.frame.mode == "close" and 0 < overlay.close_progress < 1
    assert not sim.commands("close")
    sim.hold(0.6, ("fist", *CENTRE))
    assert sim.commands("close") == [("close", 1)]


def test_opening_the_hand_cancels_close(sim):
    arm(sim)
    sim.hold(0.45, ("fist", *CENTRE))
    sim.hold(0.6, ("open", *CENTRE))
    assert not sim.commands("close")


def test_moving_fist_does_not_close(sim):
    arm(sim)
    sim.glide(1.2, "fist", CENTRE, (1200, 900))
    assert not sim.commands("close")


def test_open_palm_swipe_switches_workspace_once(sim):
    arm(sim, at=(2000, 900))
    sim.glide(0.25, "open", (2000, 900), (700, 900))
    assert sim.commands("switch_desktop") == [("switch_desktop", 1)]
    # The return stroke must not undo it.
    sim.glide(0.25, "open", (700, 900), (2000, 900))
    sim.hold(0.3, ("open", 2000, 900))
    assert sim.commands("switch_desktop") == [("switch_desktop", 1)]
    assert sim.engine.overlay.hud_desktop == 1


def test_slow_or_relaxed_hand_motion_is_not_a_swipe(sim):
    arm(sim, at=(2000, 900))
    sim.glide(1.5, "open", (2000, 900), (700, 900))
    sim.hold(0.3, ("neutral", 700, 900))
    sim.glide(0.25, "neutral", (700, 900), (2000, 900))
    assert not sim.commands("switch_desktop")


def fingers(tilt, at=CENTRE):
    """Index and middle fingers extended, leaning `tilt` degrees toward the camera."""
    return ("two_finger", *at, "Right", tilt)


def lean(sim, start, end, seconds=0.3, at=CENTRE):
    sim.run(seconds, lambda f: [fingers(start + (end - start) * f, at)])


def top_speed_fraction(sim, tilt):
    g = sim.cfg.gesture
    return (abs(tilt) - g.scroll_dead_deg) / (g.scroll_full_deg - g.scroll_dead_deg)


def test_tilting_two_fingers_scrolls_while_the_hand_stays_still(sim):
    sim.backend.warp_pointer(50, 60)
    sim.backend.commands.clear()
    arm(sim)
    sim.hold(0.6, fingers(0))
    assert sim.engine.overlay.scrolling and sim.backend.scrolled == 0
    assert sim.commands("warp_pointer")[0][1:] == pytest.approx(CENTRE, abs=3)
    # Tip the fingers forward and hold them there: it keeps scrolling down at a steady rate.
    lean(sim, 0, 30)
    sim.hold(0.4, fingers(30))
    before = sim.backend.scrolled
    sim.hold(1.0, fingers(30))
    expected = top_speed_fraction(sim, 30) * sim.cfg.gesture.scroll_speed
    assert sim.backend.scrolled - before == pytest.approx(-expected, rel=0.03)
    assert sim.engine.overlay.hands[0].scroll == pytest.approx(top_speed_fraction(sim, 30), abs=0.03)
    # Back where they started, it stops.
    lean(sim, 30, 0)
    sim.hold(0.4, fingers(0))
    stopped = sim.backend.scrolled
    sim.hold(0.5, fingers(0))
    assert sim.backend.scrolled == stopped and sim.engine.overlay.hands[0].scroll == 0
    # Leaning them back scrolls up.
    lean(sim, 0, -25)
    sim.hold(0.6, fingers(-25))
    assert sim.backend.scrolled > stopped + 2
    # Opening the hand ends it at once and puts the pointer back.
    sim.hold(0.2, ("open", *CENTRE))
    assert not sim.engine.overlay.scrolling
    sim.hold(0.1, ("open", *CENTRE))
    ended = sim.backend.scrolled
    sim.hold(0.5, ("open", *CENTRE))
    assert sim.backend.scrolled == ended and not sim.engine.overlay.scrolling
    assert sim.backend.pointer_pos() == (50, 60)
    assert not sim.commands("move_resize")


def test_scroll_speed_follows_the_tilt_up_to_a_limit(sim):
    arm(sim)
    sim.hold(0.5, fingers(0))
    rates = []
    for tilt in (20, 40, 70):
        lean(sim, rates and rates[-1][0] or 0, tilt)
        sim.hold(0.4, fingers(tilt))
        before = sim.backend.scrolled
        sim.hold(0.5, fingers(tilt))
        rates.append((tilt, (before - sim.backend.scrolled) / 0.5))
    top = sim.cfg.gesture.scroll_speed
    assert rates[0][1] == pytest.approx(top_speed_fraction(sim, 20) * top, rel=0.05)
    assert rates[1][1] == pytest.approx(top, rel=0.05)
    assert rates[2][1] == pytest.approx(top, rel=0.05)  # no faster beyond the full tilt


def test_moving_the_hand_or_a_small_wobble_does_not_scroll(sim):
    arm(sim)
    sim.hold(0.5, fingers(0))
    sim.run(0.6, lambda f: [fingers(5 * math.sin(f * 12), (900, 700 - 300 * f))])
    sim.hold(0.3, fingers(0, (900, 400)))
    assert sim.backend.scrolled == 0 and sim.engine.overlay.scrolling


def test_scrolling_starts_from_however_the_fingers_were_held(sim):
    arm(sim)
    sim.hold(0.6, fingers(40))  # like a real hand, already leaning toward the camera
    assert sim.backend.scrolled == 0
    lean(sim, 40, 70)
    sim.hold(0.5, fingers(70))
    assert sim.backend.scrolled < -3


def test_unclear_pose_pauses_scrolling_without_losing_the_resting_tilt(sim):
    arm(sim)
    sim.hold(0.5, fingers(0))
    lean(sim, 0, 30)
    sim.hold(0.4, fingers(30))
    gesture = sim.engine.active
    # The middle finger is misread as bent for a few frames.
    sim.hold(0.13, ("point", *CENTRE))
    paused = sim.backend.scrolled
    sim.hold(0.07, ("point", *CENTRE))
    assert sim.backend.scrolled == paused and sim.engine.active is gesture
    sim.hold(0.15, fingers(30))
    assert sim.engine.active is gesture
    sim.hold(0.5, fingers(30))
    assert sim.backend.scrolled < paused - 3  # still scrolling: 30 degrees is still a tilt
    # Staying unclear for longer ends it.
    sim.hold(0.8, ("point", *CENTRE))
    assert sim.engine.active is None


def scroll_rates(sim, seconds, hands):
    """The scroll speed shown on the hand (-1..1 of the top speed) at every tick."""
    rates, end = [], sim.t + seconds
    while sim.t < end:
        sim.run(1 / Sim.TICK_HZ, hands)
        rates.append(sim.engine.overlay.hands[0].scroll)
    return rates


def test_shaky_tilt_reading_still_scrolls_at_a_steady_speed(sim):
    rng = np.random.default_rng(5)

    def shaky(tilt):  # the camera reads the tilt a few degrees off, differently every frame
        return lambda _: [fingers(tilt + rng.normal(0, 3.0))]

    arm(sim)
    sim.run(1.5, shaky(0))
    assert sim.backend.scrolled == 0  # jitter around the resting tilt does not creep
    sim.run(0.3, lambda f: [fingers(30 * f + rng.normal(0, 3.0))])
    sim.run(0.6, shaky(30))
    rates = scroll_rates(sim, 1.5, shaky(30))
    assert np.mean(rates) == pytest.approx(top_speed_fraction(sim, 30), abs=0.08)
    assert np.std(rates) < 0.035  # 3 degrees of jitter alone would be 0.09


def test_scroll_speed_keeps_up_with_a_quick_tilt(sim):
    arm(sim)
    sim.hold(0.6, fingers(0))
    lean(sim, 0, 30, seconds=0.2)
    sim.hold(0.1, fingers(30))  # a tenth of a second after the fingers arrive
    assert sim.engine.overlay.hands[0].scroll == pytest.approx(top_speed_fraction(sim, 30), abs=0.08)
    lean(sim, 30, 0, seconds=0.2)
    sim.hold(0.1, fingers(0))
    stopped = sim.backend.scrolled
    sim.hold(0.5, fingers(0))
    assert sim.backend.scrolled == stopped


def test_scroll_direction_can_be_inverted(sim):
    sim.cfg.gesture.scroll_invert = True
    arm(sim)
    sim.hold(0.5, fingers(0))
    lean(sim, 0, 30)
    sim.hold(0.5, fingers(30))
    assert sim.backend.scrolled > 3


def test_the_reading_climbing_as_the_pose_is_made_is_not_a_tilt(sim):
    arm(sim)
    # For a third of a second after the two fingers go up, a real hand's tilt reads low and climbs.
    sim.hold(0.2, fingers(0))
    lean(sim, 0, 27, seconds=0.2)
    sim.hold(1.0, fingers(27))
    assert sim.engine.overlay.scrolling and sim.backend.scrolled == 0


def test_a_steep_tilt_keeps_scrolling_whatever_the_hand_is_read_as(sim):
    arm(sim)
    sim.hold(0.6, fingers(0))
    lean(sim, 0, 100)
    gesture = sim.engine.active
    # Fingers pointing at the camera or lower lie over the rest of the hand, which then reads as
    # neutral or as a pinch. Each of these still has the two fingers reading steep. (A tilt read
    # as a fist is in the recorded test below; the made-up fist here is curled like a real one.)
    for misread, tilt in (("point", 100), ("pinch_index", 120)):
        before = sim.backend.scrolled
        sim.hold(1.0, (misread, *CENTRE, "Right", tilt))
        assert sim.engine.active is gesture
        assert sim.backend.scrolled - before == pytest.approx(-sim.cfg.gesture.scroll_speed, rel=0.05)
    # With the fingers back up it is the same gesture still, at rest where it was before.
    sim.hold(0.1, fingers(100))
    lean(sim, 100, 0)
    sim.hold(0.4, fingers(0))
    stopped = sim.backend.scrolled
    sim.hold(0.5, fingers(0))
    assert sim.engine.active is gesture and sim.backend.scrolled == stopped
    assert not [c for c in sim.backend.commands if c[0] != "warp_pointer"]  # no window was touched


def test_a_real_fist_ends_the_scroll_even_though_it_reads_as_a_steep_tilt(sim):
    arm(sim)
    sim.hold(0.6, fingers(0))
    lean(sim, 0, 100)
    sim.hold(0.5, fingers(100))
    sim.hold(0.5, ("fist", *CENTRE))  # reads as tilted 140 degrees, with the index finger curled right up
    stopped = sim.backend.scrolled
    sim.hold(1.5, ("fist", *CENTRE))
    assert sim.engine.active is None and sim.backend.scrolled == stopped
    assert not sim.commands("close")  # and the fist the scroll ended on closes nothing
    # Made afresh, it closes the window as a fist always does.
    sim.hold(0.3, ("open", *CENTRE))
    sim.hold(1.2, ("fist", *CENTRE))
    assert sim.commands("close") == [("close", 1)]


def test_fingers_tipped_past_straight_down_still_scroll_down(sim):
    arm(sim)
    sim.hold(0.6, fingers(0))
    lean(sim, 0, 200, seconds=0.6)
    before = sim.backend.scrolled
    sim.hold(1.0, fingers(200))
    assert sim.backend.scrolled - before == pytest.approx(-sim.cfg.gesture.scroll_speed, rel=0.05)


def test_a_pinch_read_as_scrolling_ends_grabs_nothing(sim):
    arm(sim)
    sim.hold(0.6, fingers(0))
    sim.hold(0.2, ("pinch_index", *CENTRE))
    assert sim.engine.overlay.scrolling  # it may be a misreading, so the scroll waits a moment
    sim.hold(0.6, ("pinch_index", *CENTRE))
    assert sim.engine.active is None and not sim.commands("activate")
    # Made afresh, the pinch grabs as it always does.
    sim.hold(0.3, ("open", *CENTRE))
    sim.hold(0.3, ("pinch_index", *CENTRE))
    assert isinstance(sim.engine.active, MoveInteraction)


def recorded_tilt(name: str) -> list[FrameSample]:
    """Hand landmarks MediaPipe produced for a real two-finger scroll with a steep tilt in it."""
    data = json.loads(gzip.decompress((Path(__file__).parent / "fixtures" / "scroll_tilts.json.gz").read_bytes()))
    return [FrameSample.from_dict({**frame, "seq": seq}) for seq, frame in enumerate(data[name])]


@pytest.mark.parametrize("name", ["read_as_a_pinch", "read_as_a_fist"])
def test_a_real_steep_tilt_scrolls_all_the_way_and_touches_no_window(name):
    sim = Sim()
    sim.backend.add_window(WindowInfo(1, 0, 0, *sim.screen, title="under the hand wherever it goes"))
    frames = recorded_tilt(name)
    started, held_still, previous = [], None, None
    t, sent = frames[0].t_result, 0
    while t < frames[-1].t_result + 0.3:
        while sent < len(frames) and frames[sent].t_result <= t:
            sim.engine.on_frame(frames[sent])
            sent += 1
        sim.engine.tick(t)
        if sim.engine.active is not None and sim.engine.active is not previous:
            started.append(type(sim.engine.active).__name__)
        previous = sim.engine.active
        if held_still is None and t >= 1.1:  # the fingers are up and still; the tilt begins after this
            held_still = sim.backend.scrolled
        t += 1 / 120
    assert started == ["ScrollInteraction"]  # one scroll, and neither a grab nor a close
    assert abs(held_still) < 0.5
    assert sim.backend.scrolled < -18  # about a second at the top speed of 20 notches a second
    assert not [c for c in sim.backend.commands if c[0] != "warp_pointer"]
    assert sim.engine.active is None  # the hand opening at the end stopped it


def claw(roll=0.0, at=CENTRE, hand="right"):
    """Every finger bent as if round a knob, the hand turned `roll` degrees clockwise.

    In the mirrored frame the tracker calls the user's right hand "Left" and the left hand "Right".
    """
    return ("claw", *at, "Left" if hand == "right" else "Right", 0.0, 1.0, roll)


def turn(sim, start, end, seconds=0.5, at=CENTRE):
    sim.run(seconds, lambda f: [claw(start + (end - start) * f, at)])


def test_turning_a_claw_like_a_knob_changes_the_volume(sim):
    arm(sim)
    sim.hold(1.0, claw())
    assert sim.engine.overlay.knob == 0.5 and sim.engine.overlay.knob_name == "Volume"
    assert not sim.backend.commands  # gripped, not yet turned
    turn(sim, 0, 44)
    sim.hold(0.5, claw(44))
    g = sim.cfg.gesture
    assert sim.backend.dials["volume"] == pytest.approx(0.5 + (44 - g.knob_dead_deg) / g.knob_full_deg, abs=0.02)
    assert sim.engine.overlay.knob == sim.backend.dials["volume"]
    turn(sim, 44, -40, seconds=0.8)
    sim.hold(0.5, claw(-40))
    assert sim.backend.dials["volume"] == pytest.approx(0.5 - (40 - g.knob_dead_deg) / g.knob_full_deg, abs=0.02)
    # Opening the hand lets go of the knob, and the volume stays where it was turned to.
    left_at = sim.backend.dials["volume"]
    sim.hold(0.5, ("open", *CENTRE))
    assert sim.engine.active is None and sim.engine.overlay.knob == -1 and sim.backend.dials["volume"] == left_at
    assert {c[0] for c in sim.backend.commands} == {"set_volume"}  # and no window was touched


def test_a_claw_held_or_moved_without_turning_leaves_the_volume_alone(sim):
    arm(sim)
    sim.hold(0.8, claw())
    sim.run(1.0, lambda f: [claw(5 * math.sin(f * 12), (900 + 500 * f, 700 - 200 * f))])
    assert sim.engine.overlay.knob == 0.5 and not sim.commands("set_volume")


def test_the_volume_stops_at_silent_and_at_full(sim):
    arm(sim)
    sim.hold(0.8, claw())
    turn(sim, 0, 100, seconds=0.8)
    sim.hold(0.4, claw(100))
    assert sim.backend.dials["volume"] == 1.0
    turn(sim, 100, -150, seconds=1.5)
    sim.hold(0.4, claw(-150))
    assert sim.backend.dials["volume"] == 0.0


def test_the_knob_starts_from_however_the_hand_has_come_to_rest(sim):
    arm(sim)
    turn(sim, 0, 40)  # still turning into place as the claw is first made out
    sim.hold(0.8, claw(40))
    assert sim.engine.overlay.knob == 0.5 and not sim.commands("set_volume")


@pytest.mark.parametrize("held", [60, 150, 240, 330])
def test_however_the_hand_is_held_the_knob_turns_just_the_same(sim, held):
    # From one of these the turn carries the line of the knuckles across where its angle wraps round.
    arm(sim)
    sim.hold(1.0, claw(held))
    turn(sim, held, held + 44)
    sim.hold(0.5, claw(held + 44))
    assert sim.backend.dials["volume"] == pytest.approx(0.8, abs=0.02)


def test_the_knob_can_be_made_to_turn_the_other_way(sim):
    sim.cfg.gesture.knob_invert = True
    arm(sim)
    sim.hold(0.8, claw())
    turn(sim, 0, 44)
    sim.hold(0.5, claw(44))
    assert sim.backend.dials["volume"] == pytest.approx(0.2, abs=0.02)


def test_the_left_hand_turns_the_brightness_and_never_all_the_way_down(sim):
    arm(sim)
    sim.hold(1.0, claw(hand="left"))
    assert sim.engine.overlay.knob == 0.5 and sim.engine.overlay.knob_name == "Brightness"
    sim.run(0.5, lambda f: [claw(44 * f, hand="left")])
    sim.hold(0.5, claw(44, hand="left"))
    assert sim.backend.dials["brightness"] == pytest.approx(0.8, abs=0.02) and sim.backend.dials["volume"] == 0.5
    assert {c[0] for c in sim.backend.commands} == {"set_brightness"}
    sim.run(1.5, lambda f: [claw(44 - 190 * f, hand="left")])
    sim.hold(0.4, claw(-146, hand="left"))
    assert sim.backend.dials["brightness"] == 0.05  # dim, but still to be seen


def test_which_hand_is_which_follows_whether_the_camera_is_mirrored(sim):
    sim.cfg.camera.mirror = False  # unmirrored, the tracker names each hand as it is
    arm(sim)
    sim.hold(1.0, claw(hand="left"))
    assert sim.engine.overlay.knob_name == "Volume"


def test_a_claw_does_nothing_when_the_volume_cannot_be_read(sim):
    sim.backend.dials["volume"] = None
    arm(sim)
    sim.hold(0.8, claw())
    turn(sim, 0, 60)
    assert sim.engine.active is None and not sim.backend.commands


def test_a_relaxed_hand_is_not_a_claw(sim):
    arm(sim)
    sim.run(1.5, lambda f: [("neutral", *CENTRE, "Right", 0.0, 1.0, 50 * f)])  # fingers a little curled, turning
    assert sim.engine.active is None and not sim.backend.commands


def menu_sim():
    window = MenuItem("Window", children=[MenuItem("Close", "window_action", "close"), MenuItem("Min", "window_action", "minimize")])
    root = MenuItem(
        "Root",
        children=[
            MenuItem("Terminal", "command", "term"),
            MenuItem("Two", "workspace", 2),
            window,
            MenuItem("Windows", "running_windows"),
        ],
    )
    s = Sim(menu=root)
    s.backend.add_window(WindowInfo(1, **WIN, title="one"))
    return s


def test_menu_opens_and_launches_on_release():
    sim = menu_sim()
    arm(sim, at=(1500, 900))
    sim.hold(0.2, ("pinch_pinky", 1500, 900))
    menu = sim.engine.overlay.menu
    assert menu is not None and [i["name"] for i in menu["items"]] == ["Terminal", "Two", "Window", "Windows"]
    sim.glide(0.4, "pinch_pinky", (1500, 900), (1500, 720))
    sim.hold(0.2, ("pinch_pinky", 1500, 720))
    assert sim.engine.overlay.menu["label"] == "Terminal"
    sim.hold(0.3, ("open", 1500, 720))
    assert [i.name for i in sim.launcher.activated] == ["Terminal"]
    assert sim.engine.overlay.menu is None


def test_menu_track_item_skips_a_track_and_says_so():
    sim = Sim(menu=MenuItem("Root", children=[MenuItem("Next track", "track", "next"), MenuItem("Previous track", "track", "previous")]))
    arm(sim, at=(1500, 900))
    sim.hold(0.2, ("pinch_pinky", 1500, 900))
    sim.glide(0.4, "pinch_pinky", (1500, 900), (1500, 1080))  # the second of two items lies straight down
    sim.hold(0.2, ("pinch_pinky", 1500, 1080))
    sim.hold(0.3, ("open", 1500, 1080))
    assert sim.backend.commands == [("skip_track", -1)] and sim.engine.overlay.track == -1
    sim.hold(1.5, ("open", 1500, 1080))
    assert sim.engine.overlay.track == 0  # the note goes away again


def test_menu_release_in_dead_zone_cancels():
    sim = menu_sim()
    arm(sim, at=(1500, 900))
    sim.hold(0.3, ("pinch_pinky", 1500, 900))
    sim.hold(0.3, ("open", 1500, 900))
    assert not sim.launcher.activated and not sim.backend.commands


def test_menu_window_action_targets_window_under_hand():
    sim = menu_sim()
    arm(sim)
    sim.hold(0.2, ("pinch_pinky", *CENTRE))
    # "Window" is the third of four items: straight down. Enter it, then pick Close.
    sim.glide(0.4, "pinch_pinky", CENTRE, (900, 1000))
    sim.hold(0.2, ("pinch_pinky", 900, 1000))
    view = sim.engine.overlay.menu
    assert [i["name"] for i in view["items"]] == ["Close", "Min"] and view["back"] is not None
    close = view["items"][0]
    sim.glide(0.4, "pinch_pinky", (900, 1000), (close["x"], close["y"]))
    sim.hold(0.2, ("pinch_pinky", close["x"], close["y"]))
    sim.hold(0.3, ("open", close["x"], close["y"]))
    assert sim.commands("close") == [("close", 1)]


def test_menu_lists_running_windows_and_switches_workspace():
    sim = menu_sim()
    arm(sim, at=(1500, 900))
    sim.hold(0.2, ("pinch_pinky", 1500, 900))
    sim.glide(0.4, "pinch_pinky", (1500, 900), (1200, 900))  # "Windows" points left
    sim.hold(0.2, ("pinch_pinky", 1200, 900))
    assert [i["name"] for i in sim.engine.overlay.menu["items"]] == ["one"]
    sim.hold(0.3, ("open", 1200, 900))

    sim.hold(0.4, ("open", 1500, 900))
    sim.hold(0.2, ("pinch_pinky", 1500, 900))
    sim.glide(0.4, "pinch_pinky", (1500, 900), (1680, 900))  # "Two" points right
    sim.hold(0.3, ("open", 1680, 900))
    assert sim.commands("switch_desktop") == [("switch_desktop", 2)]


def switcher_sim():
    sim = Sim()
    sim.backend.add_window(WindowInfo(1, 100, 100, 800, 600, title="one"))
    sim.backend.add_window(WindowInfo(2, 300, 200, 800, 600, title="two"))
    sim.backend.add_window(WindowInfo(3, 500, 300, 800, 600, desktop=2, title="three"))
    sim.backend.add_window(WindowInfo(4, 700, 400, 800, 600, title="four", minimized=True))
    sim.backend.activate(2)
    sim.run(0.05)
    sim.backend.activate(1)
    sim.backend.commands.clear()
    return sim


TOP = (1440, 450)  # where the hand comes to rest after opening the switcher, above its panel
CHIN = (0.5, 0.5)  # where the chin is in the camera frame
AT_CHIN = screen_point(Config(), (2880, 1800), 0.5, 0.56)  # a hand placed here has its knuckles on the chin


def on_chin(pose="fist", nearness=1.0):
    return (pose, *AT_CHIN, "Right", 0.0, nearness)


def open_switcher(sim):
    """Touch a fist to the chin, then take the hand away and let it rest, open, above the panel."""
    sim.face = make_face(sim.cfg, CHIN)
    sim.hold(0.5, on_chin())
    sim.glide(0.3, "open", AT_CHIN, TOP)
    sim.hold(0.2, ("open", *TOP))


def card_centre(sim, title):
    view = sim.engine.overlay.switcher
    item = next(i for i in view["items"] if i["title"] == title)
    return (item["x"] + view["card_w"] / 2, item["y"] + view["card_h"] / 2)


def test_fist_on_the_chin_opens_switcher_with_recent_windows_first():
    sim = switcher_sim()
    open_switcher(sim)
    view = sim.engine.overlay.switcher
    assert view is not None and not sim.backend.commands
    # Most recently used first, then the rest; windows on other workspaces and minimized ones too.
    assert [i["title"] for i in view["items"]] == ["one", "two", "four", "three"]
    assert [i["desktop"] for i in view["items"]] == [0, 0, 0, 3]
    assert [i["minimized"] for i in view["items"]] == [False, False, True, False]
    # Like Alt+Tab, the window used before the current one starts highlighted.
    assert view["selected"] == 1 and view["label"] == "two"
    frame = sim.engine.overlay.frame
    assert frame is not None and (frame.x, frame.y) == (300, 200)
    # Every card is on screen and inside the panel.
    for item in view["items"]:
        assert view["x"] < item["x"] and item["x"] + view["card_w"] < view["x"] + view["w"]
        assert view["y"] < item["y"] and item["y"] + view["card_h"] < view["y"] + view["h"]
    assert view["x"] > 0 and view["x"] + view["w"] < 2880


def test_switcher_pinch_right_away_goes_to_previous_window():
    sim = switcher_sim()
    open_switcher(sim)
    sim.hold(0.2, ("pinch_index", *TOP))
    assert sim.backend.commands == [("activate", 2)]
    assert sim.engine.overlay.switcher is None and sim.engine.active is None
    # The pinch that picked the window does not also grab it.
    sim.glide(0.3, "pinch_index", TOP, (1000, 600))
    assert sim.backend.commands == [("activate", 2)]


def test_hand_coming_off_the_chin_does_not_pick_the_card_it_lands_on():
    sim = switcher_sim()
    sim.face = make_face(sim.cfg, CHIN)
    sim.hold(0.5, on_chin())
    middle = (1440, 880)  # over the third card
    sim.glide(0.3, "open", AT_CHIN, middle)
    sim.hold(0.3, ("open", *middle))
    view = sim.engine.overlay.switcher
    assert view["x"] < middle[0] < view["x"] + view["w"] and view["y"] < middle[1] < view["y"] + view["h"]
    assert view["selected"] == 1
    sim.hold(0.2, ("pinch_index", *middle))
    assert sim.backend.commands == [("activate", 2)]


def test_switcher_pinch_on_a_card_switches_workspace_and_activates():
    sim = switcher_sim()
    open_switcher(sim)
    target = card_centre(sim, "three")
    sim.glide(0.5, "open", TOP, target)
    sim.hold(0.2, ("open", *target))
    view = sim.engine.overlay.switcher
    assert view["items"][view["selected"]]["title"] == "three" and view["label"] == "three"
    assert sim.engine.overlay.frame is None  # it is on another workspace, so nothing to outline
    sim.hold(0.2, ("pinch_index", *target))
    assert sim.backend.commands == [("switch_desktop", 2), ("activate", 3)]
    assert sim.engine.overlay.hud_desktop == 2


def test_switcher_restores_a_minimized_window():
    sim = switcher_sim()
    open_switcher(sim)
    target = card_centre(sim, "four")
    sim.glide(0.5, "open", TOP, target)
    sim.hold(0.2, ("pinch_index", *target))
    assert sim.backend.commands == [("activate", 4)]
    assert not sim.backend.get(4).minimized


def test_switcher_highlight_does_not_flicker_between_cards():
    sim = switcher_sim()
    open_switcher(sim)
    view = sim.engine.overlay.switcher
    one, two = card_centre(sim, "one"), card_centre(sim, "two")
    sim.glide(0.4, "open", TOP, one)
    sim.hold(0.2, ("open", *one))
    assert sim.engine.overlay.switcher["selected"] == 0
    # Just past the midpoint toward the next card is not enough to move the highlight.
    edge = ((one[0] + two[0]) / 2 + 0.05 * view["card_w"], one[1])
    sim.glide(0.3, "open", one, edge)
    sim.hold(0.2, ("open", *edge))
    assert sim.engine.overlay.switcher["selected"] == 0
    sim.glide(0.3, "open", edge, two)
    sim.hold(0.2, ("open", *two))
    assert sim.engine.overlay.switcher["selected"] == 1


def test_switcher_pinch_off_the_panel_dismisses():
    sim = switcher_sim()
    open_switcher(sim)
    inside = card_centre(sim, "one")
    sim.glide(0.4, "open", TOP, inside)
    sim.glide(0.4, "open", inside, (300, 300))
    sim.hold(0.2, ("open", 300, 300))
    assert sim.engine.overlay.switcher["selected"] == -1
    sim.hold(0.2, ("pinch_index", 300, 300))
    assert sim.engine.overlay.switcher is None and not sim.backend.commands


def test_touching_the_chin_again_puts_the_switcher_away():
    sim = switcher_sim()
    open_switcher(sim)
    sim.hold(0.5, ("open", *TOP))
    assert sim.engine.overlay.switcher is not None
    sim.glide(0.3, "open", TOP, AT_CHIN)
    sim.hold(0.5, on_chin())
    assert sim.engine.overlay.switcher is None and not sim.backend.commands
    # It stays away while the fist rests there, and the next touch brings it back.
    sim.hold(1.5, on_chin())
    assert sim.engine.overlay.switcher is None
    sim.glide(0.3, "open", AT_CHIN, TOP)
    sim.glide(0.3, "open", TOP, AT_CHIN)
    sim.hold(0.5, on_chin())
    assert sim.engine.overlay.switcher is not None and not sim.backend.commands


def test_switcher_closes_when_hands_leave():
    sim = switcher_sim()
    open_switcher(sim)
    sim.run(1.0)
    assert sim.engine.overlay.switcher is not None
    sim.run(1.2)
    assert sim.engine.overlay.switcher is None and not sim.backend.commands


def test_switcher_blocks_other_gestures_while_open():
    sim = switcher_sim()
    open_switcher(sim)
    over_window = (700, 300)  # over window "two", outside the panel
    sim.glide(0.4, "open", TOP, over_window)
    sim.hold(1.0, ("fist", *over_window))
    assert sim.engine.overlay.switcher is not None and not sim.backend.commands
    # The fist that was ignored does not start closing the window once the switcher goes away.
    sim.engine.cancel_active()
    sim.hold(1.0, ("fist", *over_window))
    assert not sim.commands("close")


def test_vertical_swipes_do_nothing(sim):
    arm(sim, at=(1440, 1350))
    sim.glide(0.25, "open", (1440, 1350), TOP)
    sim.hold(0.6, ("open", *TOP))
    sim.glide(0.25, "open", TOP, (1440, 1350))
    sim.hold(0.3, ("open", 1440, 1350))
    assert sim.engine.overlay.switcher is None and not sim.backend.commands


def chin_sim():
    """Windows to switch between, one of them where a hand on the chin points, and a face in view."""
    sim = switcher_sim()
    sim.backend.add_window(WindowInfo(9, 1000, 800, 900, 600, title="under the chin"))
    sim.backend.commands.clear()
    sim.face = make_face(sim.cfg, CHIN)
    return sim


def test_fist_has_to_stay_on_the_chin_a_moment_and_opens_the_switcher_once():
    sim = chin_sim()
    sim.hold(0.15, on_chin())
    sim.glide(0.3, "open", AT_CHIN, TOP)
    sim.hold(0.3, ("open", *TOP))
    assert sim.engine.overlay.switcher is None  # only brushed past
    sim.glide(0.3, "open", TOP, AT_CHIN)
    sim.hold(0.5, on_chin())
    switcher = sim.engine.active
    assert sim.engine.overlay.switcher is not None
    # Resting there neither puts it away again nor closes the window the hand is over.
    sim.hold(2.5, on_chin())
    assert sim.engine.active is switcher and not sim.backend.commands


def test_fist_held_out_in_front_of_the_face_closes_a_window_as_before():
    sim = chin_sim()
    arm(sim, at=TOP)
    sim.hold(1.2, on_chin(nearness=2.0))  # over the chin in the picture, but much nearer the camera
    assert sim.backend.commands == [("close", 9)] and sim.engine.overlay.switcher is None


def test_fist_that_may_or_may_not_be_on_the_chin_does_neither():
    sim = chin_sim()
    arm(sim, at=TOP)
    sim.hold(1.5, on_chin(nearness=1.65))
    assert sim.engine.overlay.switcher is None and not sim.backend.commands


@pytest.mark.parametrize("pose", ["open", "neutral", "two_finger", "point"])
def test_hand_that_is_not_closed_does_not_touch_the_chin(pose):
    sim = chin_sim()
    sim.hold(1.0, on_chin(pose))
    assert sim.engine.overlay.switcher is None and not sim.commands("close")


def test_fist_on_the_chin_read_as_a_pinch_opens_the_switcher_and_grabs_nothing():
    sim = chin_sim()
    arm(sim, at=TOP)  # an armed hand: a pinch from it would grab
    sim.glide(0.3, "open", TOP, AT_CHIN)
    sim.hold(0.6, on_chin("loose_fist"))
    assert sim.engine.overlay.switcher is not None and not sim.backend.commands
    # Still read as a pinch while it comes away, it does not pick a window either.
    sim.glide(0.4, "loose_fist", AT_CHIN, (1500, 1500))
    sim.hold(0.3, ("loose_fist", 1500, 1500))
    assert sim.engine.overlay.switcher is not None and not sim.backend.commands


def test_hand_lost_against_the_face_does_not_count_as_touching_again():
    sim = chin_sim()
    sim.hold(0.5, on_chin())
    assert sim.engine.overlay.switcher is not None
    for _ in range(3):  # tracking drops the fist and finds it again, as a new hand each time
        sim.run(0.6)
        sim.hold(0.6, on_chin())
    assert sim.engine.overlay.switcher is not None and not sim.backend.commands


def test_face_hidden_behind_the_hand_is_remembered_for_a_moment():
    sim = chin_sim()
    sim.hold(0.3, ("open", *TOP))
    sim.face = None  # the fist covers too much of the face for it to be found
    sim.glide(0.3, "open", TOP, AT_CHIN)
    sim.hold(0.5, on_chin())
    assert sim.engine.overlay.switcher is not None


def test_without_a_face_in_view_a_fist_closes_the_window():
    sim = chin_sim()
    sim.face = None
    arm(sim, at=TOP)
    sim.hold(1.2, on_chin())
    assert sim.backend.commands == [("close", 9)] and sim.engine.overlay.switcher is None


def test_fist_away_from_the_chin_closes_the_window_with_a_face_in_view():
    sim = chin_sim()
    arm(sim, at=(700, 300))
    sim.hold(1.2, ("fist", 700, 300))  # over window "one", level with the face but nowhere near the chin
    assert sim.backend.commands == [("close", 1)] and sim.engine.overlay.switcher is None


def test_switcher_can_be_limited_to_the_current_workspace():
    sim = switcher_sim()
    sim.cfg.switcher.all_workspaces = False
    open_switcher(sim)
    assert [i["title"] for i in sim.engine.overlay.switcher["items"]] == ["one", "two", "four"]


def click(sim, at=CENTRE, held=0.15):
    sim.hold(held, ("pinch_middle", *at))
    sim.hold(0.15, ("open", *at))


def test_thumb_to_middle_finger_holds_the_mouse_button_down_where_the_cursor_is(sim):
    arm(sim)
    sim.hold(0.2, ("pinch_middle", *CENTRE))
    assert sim.backend.commands == [("button_down", *CENTRE)]
    assert isinstance(sim.engine.active, ClickInteraction)
    sim.hold(1.0, ("pinch_middle", *CENTRE))  # held for as long as the pinch is
    assert sim.backend.commands == [("button_down", *CENTRE)]
    sim.hold(0.15, ("open", *CENTRE))
    assert sim.backend.commands == [("button_down", *CENTRE), ("button_up",)]
    assert sim.engine.active is None


def test_click_touches_no_window(sim):
    win = sim.backend.get(1)
    arm(sim)
    click(sim)
    sim.hold(0.2, ("pinch_middle", *CENTRE))
    sim.glide(0.4, "pinch_middle", CENTRE, (1500, 1000))
    sim.hold(0.2, ("open", 1500, 1000))
    assert (win.x, win.y, win.w, win.h) == (500, 400, 800, 600)
    assert {c[0] for c in sim.backend.commands} == {"button_down", "pointer_to", "button_up"}


def test_index_pinch_never_presses_the_mouse_button(sim):
    arm(sim)
    tap(sim)
    tap(sim)
    sim.hold(0.2, ("pinch_index", *CENTRE))
    sim.glide(0.4, "pinch_index", CENTRE, (1300, 900))
    sim.hold(0.2, ("open", 1300, 900))
    assert not sim.commands("button_down")


def test_pointer_stays_put_while_a_held_hand_wanders(sim):
    arm(sim)
    sim.hold(0.1, ("pinch_middle", *CENTRE))
    sim.glide(0.3, "pinch_middle", CENTRE, (CENTRE[0] + 30, CENTRE[1] - 20))
    sim.hold(0.15, ("open", CENTRE[0] + 30, CENTRE[1] - 20))
    assert sim.backend.commands == [("button_down", *CENTRE), ("button_up",)]


def test_pinch_carried_somewhere_drags_the_pointer_there(sim):
    arm(sim)
    sim.hold(0.1, ("pinch_middle", *CENTRE))
    sim.glide(0.4, "pinch_middle", CENTRE, (1500, 1000))
    sim.hold(0.2, ("pinch_middle", 1500, 1000))
    moves = sim.commands("pointer_to")
    assert sim.backend.commands[0] == ("button_down", *CENTRE) and len(moves) > 5
    assert abs(moves[-1][1] - 1500) <= 5 and abs(moves[-1][2] - 1000) <= 5 and not sim.commands("button_up")
    sim.hold(0.15, ("open", 1500, 1000))
    assert sim.backend.commands[-1] == ("button_up",)


def test_second_click_in_the_same_place_lands_on_the_first(sim):
    arm(sim)
    click(sim)
    nearby = (CENTRE[0] + 25, CENTRE[1] + 15)  # as near as a hand gets to the same place twice
    click(sim, at=nearby)
    assert sim.commands("button_down") == [("button_down", *CENTRE)] * 2


def test_click_somewhere_else_or_later_lands_under_the_cursor(sim):
    arm(sim)
    click(sim)
    there = (CENTRE[0] + 200, CENTRE[1])
    sim.glide(0.2, "open", CENTRE, there)
    sim.hold(0.3, ("open", *there))
    click(sim, at=there)  # soon after, but not at the same place
    sim.hold(1.2, ("open", *there))
    nearby = (there[0] + 25, there[1])
    sim.glide(0.2, "open", there, nearby)
    sim.hold(0.3, ("open", *nearby))
    click(sim, at=nearby)  # at the same place, but not soon after
    assert sim.commands("button_down") == [("button_down", *at) for at in (CENTRE, there, nearby)]


def test_click_works_off_any_window_and_on_a_fullscreen_one(sim):
    there = (2400, 300)  # bare desktop
    arm(sim, at=there)
    click(sim, at=there)
    assert sim.backend.commands == [("button_down", *there), ("button_up",)]
    sim.backend.commands.clear()
    sim.backend.get(1).fullscreen = True
    sim.hold(0.4)
    arm(sim)
    click(sim)
    assert sim.backend.commands == [("button_down", *CENTRE), ("button_up",)]


def test_mouse_button_is_let_go_when_the_hand_is_lost_or_holowm_paused(sim):
    arm(sim)
    sim.hold(0.2, ("pinch_middle", *CENTRE))
    sim.hold(0.5)
    assert sim.backend.commands == [("button_down", *CENTRE), ("button_up",)]
    sim.hold(0.4, ("open", *CENTRE))
    sim.hold(0.2, ("pinch_middle", *CENTRE))
    sim.engine.set_paused(True)
    assert sim.commands("button_up") == [("button_up",)] * 2 and sim.engine.active is None


def test_click_says_where_it_went_for_a_moment(sim):
    arm(sim)
    sim.hold(0.1, ("pinch_middle", *CENTRE))
    overlay = sim.engine.overlay
    assert overlay.click and abs(overlay.click_x - CENTRE[0]) < 1 and abs(overlay.click_y - CENTRE[1]) < 1
    sim.hold(0.5, ("pinch_middle", *CENTRE))
    assert not sim.engine.overlay.click  # the note goes away again


def test_hand_that_enters_with_the_middle_finger_pinched_does_not_click(sim):
    sim.hold(0.6, ("pinch_middle", *CENTRE))
    assert not sim.backend.commands


def test_hand_turned_from_the_camera_does_not_click(sim):
    side_on = ("Right", 0.0, 1.0, 0.0, 60.0)
    sim.hold(0.4, ("open", *CENTRE, *side_on))
    sim.hold(0.4, ("pinch_middle", *CENTRE, *side_on))
    assert not sim.backend.commands


def test_pointing_with_one_finger_does_not_click(sim):
    arm(sim)
    sim.hold(0.6, ("point", *CENTRE))
    assert not sim.backend.commands


LEFT_V, RIGHT_V = ("two_finger", 900, 900, "Left"), ("two_finger", 2000, 900, "Right")


def raise_both(sim):
    """Both hands in view and open, then each holding up two fingers."""
    sim.hold(0.4, ("open", 900, 900, "Left"), ("open", 2000, 900, "Right"))
    sim.hold(0.3, LEFT_V, RIGHT_V)


def test_peace_sign_held_with_both_hands_opens_the_camera(sim):
    raise_both(sim)
    assert isinstance(sim.engine.active, CameraInteraction) and not sim.engine.camera_wanted
    sim.hold(1.2, LEFT_V, RIGHT_V)
    overlay = sim.engine.overlay
    assert 0.3 < overlay.hold_progress < 0.7 and overlay.hold_name == "Camera"
    assert abs(overlay.hold_x - 1450) <= 4 and abs(overlay.hold_y - 900) <= 4  # the ring sits between the hands
    sim.hold(1.7, LEFT_V, RIGHT_V)
    assert sim.engine.camera_wanted and sim.engine.active is None
    assert not sim.backend.scrolled and not sim.commands("activate")
    # Held on, the sign neither asks again nor starts to scroll.
    sim.engine.camera_wanted = False
    sim.hold(4.0, LEFT_V, RIGHT_V)
    assert not sim.engine.camera_wanted and sim.engine.active is None


def test_peace_sign_let_go_early_opens_nothing(sim):
    raise_both(sim)
    sim.hold(2.0, LEFT_V, RIGHT_V)
    sim.hold(0.3, LEFT_V, ("open", 2000, 900, "Right"))
    assert sim.engine.active is None and sim.engine.overlay.hold_progress == 0
    sim.hold(3.0, LEFT_V, ("open", 2000, 900, "Right"))  # the hand still held up does not go on to scroll
    assert not sim.engine.camera_wanted and sim.engine.active is None


def test_one_hand_holding_up_two_fingers_scrolls_as_before(sim):
    sim.hold(0.4, ("open", 900, 900, "Left"), ("open", 2000, 900, "Right"))
    sim.hold(4.0, LEFT_V, ("open", 2000, 900, "Right"))
    assert isinstance(sim.engine.active, ScrollInteraction) and not sim.engine.camera_wanted


def test_second_hand_joining_turns_a_scroll_into_the_peace_sign(sim):
    sim.hold(0.4, ("open", 900, 900, "Left"), ("open", 2000, 900, "Right"))
    sim.hold(0.6, LEFT_V, ("open", 2000, 900, "Right"))
    assert isinstance(sim.engine.active, ScrollInteraction)
    sim.hold(0.3, LEFT_V, RIGHT_V)
    assert isinstance(sim.engine.active, CameraInteraction)
    assert sim.backend.pointer_pos() == (0, 0)  # the scroll put the pointer back as it gave way
    sim.hold(3.0, LEFT_V, RIGHT_V)
    assert sim.engine.camera_wanted


def test_peace_sign_misread_for_a_moment_carries_on(sim):
    raise_both(sim)
    sim.hold(1.5, LEFT_V, RIGHT_V)
    sim.hold(0.15, LEFT_V, ("neutral", 2000, 900, "Right"))
    sim.hold(1.5, LEFT_V, RIGHT_V)
    assert sim.engine.camera_wanted


def test_how_long_the_peace_sign_is_held_can_be_set(sim):
    sim.cfg.gesture.camera_hold_ms = 1000
    raise_both(sim)
    sim.hold(1.0, LEFT_V, RIGHT_V)
    assert sim.engine.camera_wanted


def test_hands_keep_identity_when_they_cross(sim):
    sim.hold(0.4, ("open", 600, 1300, "Left"), ("open", 2200, 1300, "Right"))
    ids = {h.handedness: h.id for h in sim.engine.tracker.hands.values()}

    def cross(frac):
        return [("open", 600 + 1600 * frac, 1300, "Left"), ("open", 2200 - 1600 * frac, 1500, "Right")]

    sim.run(1.5, cross)
    after = {h.handedness: (h.id, h.x) for h in sim.engine.tracker.hands.values()}
    assert after["Left"][0] == ids["Left"] and after["Right"][0] == ids["Right"]
    assert after["Left"][1] > after["Right"][1]


def test_pause_cancels_and_ignores_hands(sim):
    arm(sim)
    sim.hold(0.2, ("pinch_index", *CENTRE))
    assert sim.engine.active is not None
    sim.engine.set_paused(True)
    sim.glide(0.5, "pinch_index", CENTRE, (1500, 900))
    assert sim.engine.active is None and not sim.engine.overlay.hands
    assert abs(sim.backend.get(1).x - 500) <= 3
