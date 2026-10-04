"""The benchmark, run on recordings synthesised to a known script."""

import json

import pytest

from holowm.config import Config
from holowm.core.actions import WindowInfo
from holowm.tools.prompts import Prompter
from holowm.tools.score import Session, format_report, load_session, score
from holowm.tracker.types import FrameSample
from synth import Sim, make_face, make_hand, screen_point

SCREEN = (2880, 1800)
AT = (1400, 900)
# The hand a careful person would show for each prompt: (pose, tilt of the two fingers).
SHOWN = {
    "open": ("open", 0), "relaxed": ("point", 0), "pinch": ("pinch_index", 0), "pinky_pinch": ("pinch_pinky", 0),
    "fist": ("fist", 0), "two_up": ("two_finger", 0), "two_down": ("two_finger", 100), "two_back": ("two_finger", -25),
    "aim": ("aim", 0), "aim_press": ("press", 0),
}  # fmt: skip
# The prompts that carry straight on from the one before, and the pose the hand is still in as they appear.
FOLLOWS = {"two_down": "two_finger", "two_back": "two_finger", "aim_press": "aim"}


def session(steps, shown=SHOWN, person="ada", react=0.3) -> Session:
    """A recording in which each prompted pose is made `react` seconds into its hold, with an open hand between."""
    cfg, frames, t, holds = Config(), [], 20.0, []
    for label in steps:
        t += 1.5 if label not in FOLLOWS else 0.0
        holds.append({"label": label, "start": t, "end": t + 3.0})
        t += 3.0
    for seq in range(round((t + 1.0 - 19.0) * 30)):
        now = 19.0 + seq / 30.0
        hold = next((h for h in holds if h["start"] + react <= now < h["end"] + react), None)
        follows = next((h for h in holds if h["label"] in FOLLOWS and h["start"] <= now < h["start"] + react), None)
        pose, tilt = shown[hold["label"]] if hold else (FOLLOWS[follows["label"]], 0) if follows else ("open", 0)
        frames.append(FrameSample(seq, now, now + 0.02, [make_hand(cfg, SCREEN, pose, *AT, "Right", tilt)]))
    return Session("made-up", person, frames, holds)


ALL = ["open", "relaxed", "fist", "pinch", "pinky_pinch", "two_up", "two_down", "two_up", "two_back"]


def test_a_hand_that_does_as_asked_scores_full_marks():
    report = score([session(ALL)], Config())
    assert all(report.right(label) == 1.0 for label in set(ALL))
    assert report.holds == {"open": 1, "relaxed": 1, "pinch": 1, "pinky_pinch": 1, "fist": 1, "two_up": 2, "two_down": 1, "two_back": 1}
    assert report.ran == report.holds and not report.strays
    assert report.kept["pinch"] == pytest.approx(1.0) and report.kept["two_down"] == pytest.approx(1.0)
    assert report.people == {"ada": [sum(sum(c.values()) for c in report.poses.values())] * 2}
    text = format_report(report)
    assert "Poses read right: 100% of" in text and "Right gesture, or rightly none: 9 of 9 holds." in text


def test_the_thumb_coming_down_on_a_hand_taking_aim_is_scored_as_a_click():
    report = score([session(["aim", "aim_press", "relaxed"])], Config())
    assert report.right("aim") == 1.0 and report.right("aim_press") == 1.0
    assert report.ran == report.holds and not report.strays  # taking aim runs nothing by itself
    assert report.kept["aim_press"] == pytest.approx(1.0)
    # With no aim taken before it, the same hand is only pointing, and that shows as a click that never ran.
    report = score([session(["open", "aim_press"])], Config())
    assert report.ran["aim_press"] == 0 and report.right("aim_press") == 0.0


def test_misreadings_show_up_against_the_pose_that_was_asked_for():
    # Asked for a fist, the hand pinches; asked to relax, it makes a fist; a pinch comes out as an open hand.
    wrong = {**SHOWN, "fist": ("pinch_index", 0), "relaxed": ("fist", 0), "pinch": ("open", 0)}
    report = score([session(["fist", "relaxed", "pinch", "open"], wrong)], Config())
    assert report.right("fist") == 0.0 and report.poses["fist"]["pinch_index"] == sum(report.poses["fist"].values())
    assert report.right("relaxed") == 0.0 and report.right("pinch") == 0.0 and report.right("open") == 1.0
    assert (report.ran["fist"], report.ran["relaxed"], report.ran["pinch"], report.ran["open"]) == (0, 0, 0, 1)
    assert report.strays == {"fist": {"move": 1}, "relaxed": {"close": 1}}
    text = format_report(report)
    assert "fist             1  close         0/1        -  move in 1" in text
    assert "relaxed          1  nothing       0/1        -  close in 1" in text


def test_each_pose_is_judged_afresh_whatever_the_one_before_left_running():
    cfg = Config()
    made = session(["fist", "pinch", "two_up", "two_down"])
    chin, pinch = made.steps[0], made.steps[1]
    for frame in made.frames:  # the fist is on the chin, which opens the switcher; that stays open until dismissed
        frame.face = make_face(cfg, (0.5, 0.5))
        if chin["start"] <= frame.t_capture < chin["end"]:
            frame.hands = [make_hand(cfg, SCREEN, "fist", *screen_point(cfg, SCREEN, 0.5, 0.56))]
    chin["label"] = "chin"
    report = score([made], cfg)
    assert report.ran["chin"] == 1 and report.ran["pinch"] == 1 and report.kept["pinch"] == pytest.approx(1.0)
    assert not report.strays
    # A tilt carries on from the two fingers before it, so the scroll begun there is what should be running.
    assert report.ran["two_down"] == 1 and report.kept["two_down"] == pytest.approx(1.0)


def test_a_pose_kept_up_from_one_prompt_into_the_next_keeps_its_gesture():
    # The same pinch held through two prompts that both ask for it: one grab, right for both.
    made = session(["pinch", "pinch"])
    for frame in made.frames:
        if made.steps[0]["start"] + 0.3 <= frame.t_capture < made.steps[1]["end"]:
            frame.hands = [make_hand(Config(), SCREEN, "pinch_index", *AT)]
    report = score([made], Config())
    assert report.ran["pinch"] == 2 and report.kept["pinch"] == pytest.approx(2.0)


def test_a_gesture_that_drops_out_is_counted_as_run_but_not_kept_up():
    cfg = Config()
    made = session(["pinch"])
    hold = made.steps[0]
    for frame in made.frames:  # the pinch opens for the last second of the hold
        if hold["end"] - 0.7 <= frame.t_capture < hold["end"] + 0.3:
            frame.hands = [make_hand(cfg, SCREEN, "open", *AT)]
    report = score([made], cfg)
    assert report.ran["pinch"] == 1 and 0.55 < report.kept["pinch"] < 0.8
    assert 0.55 < report.right("pinch") < 0.8


def test_a_fist_made_while_still_getting_ready_has_done_its_closing_before_the_hold():
    report = score([session(["fist"], react=-0.85)], Config())
    assert report.ran["fist"] == 1


def test_frames_with_no_hand_are_counted_as_such():
    made = session(["open"])
    for frame in made.frames:  # the hand leaves just before the part of the hold that is scored
        if frame.t_capture >= made.steps[0]["start"] + 0.5:
            frame.hands = []
    report = score([made], Config())
    assert report.poses["open"] == {"no hand": sum(report.poses["open"].values())} and report.right("open") == 0.0


def test_sessions_from_several_people_are_scored_together_and_apart():
    wrong = {**SHOWN, "fist": ("open", 0)}
    report = score([session(["fist", "open"]), session(["fist", "open"], wrong, person="ben")], Config())
    assert report.holds == {"fist": 2, "open": 2} and report.right("fist") == 0.5
    assert report.people["ada"][0] == report.people["ada"][1] and report.people["ben"][0] * 2 == report.people["ben"][1]
    assert "Poses read right, by person: ada 100%, ben 50%." in format_report(report)


def test_a_session_is_loaded_from_a_recording_and_the_labels_beside_it(tmp_path):
    made = session(["open", "fist"])
    path = tmp_path / "ada-1.jsonl"
    path.write_text("".join(json.dumps(frame.to_dict()) + "\n" for frame in made.frames))
    with pytest.raises(ValueError, match="holowm collect"):
        load_session(path)
    prompter = Prompter(rounds=1)
    prompter.done = made.steps
    prompter.save(path.with_suffix(".labels.json"), "ada")
    loaded = load_session(path)
    assert (loaded.name, loaded.person, loaded.steps) == ("ada-1", "ada", made.steps)
    assert score([loaded], Config()).right("fist") == 1.0


def test_with_gestures_off_hands_are_tracked_but_start_nothing():
    sim = Sim()
    sim.backend.add_window(WindowInfo(1, 500, 400, 800, 600, title="one"))
    sim.engine.acting = False
    sim.hold(0.4, ("open", 900, 700))
    sim.hold(0.6, ("pinch_index", 900, 700))
    sim.hold(1.0, ("fist", 900, 700))
    assert sim.engine.active is None and not sim.backend.commands
    assert [hand.pose for hand in sim.engine.overlay.hands] == ["fist"]
