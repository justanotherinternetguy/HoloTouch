import json
from collections import Counter

import pytest

from holotouch.config import Config
from holotouch.core.overlay_state import OverlayState
from holotouch.overlay.bridge import Bridge
from holotouch.tools.prompts import FOLLOW_S, HOLD_S, READY_S, SCRIPT, Prompter


def run(prompter, start=50.0, until=None):
    """Tick the prompter at 120 Hz. Returns every view it showed, with the time."""
    shown, t = [], start
    while not prompter.finished and (until is None or t < until):
        view = prompter.step(t)
        if view is not None:
            shown.append((t, view))
        t += 1 / 120
    return shown


def test_each_pose_is_announced_then_held_and_the_hold_is_what_gets_labelled():
    prompter = Prompter(rounds=1)
    shown = run(prompter)
    first = prompter.plan[0][0]
    assert (shown[0][1]["caption"], shown[0][1]["text"], shown[0][1]["holding"]) == ("Get ready", first.text, False)
    assert prompter.step(1e9) is None and prompter.finished
    script = [step for group in SCRIPT for step in group]
    assert Counter(hold["label"] for hold in prompter.done) == Counter(step.label for step in script)
    for hold in prompter.done:
        assert hold["end"] - hold["start"] == pytest.approx(HOLD_S)
        # "Hold it" was on screen for exactly the labelled time, and the bar filled as it went.
        during = [view for t, view in shown if hold["start"] <= t < hold["end"]]
        assert all(view["holding"] and view["caption"].startswith("Hold it") and view["text"] == hold["text"] for view in during)
        assert abs(len(during) - HOLD_S * 120) <= 1 and during[0]["progress"] < 0.01 and during[-1]["progress"] > 0.99
    gaps = [later["start"] - earlier["end"] for earlier, later in zip(prompter.done, prompter.done[1:])]
    assert set(round(gap, 6) for gap in gaps) == {READY_S, FOLLOW_S}
    assert prompter.done[0]["start"] > 50.0 + READY_S  # extra time before the first pose


def test_a_tilt_always_follows_straight_on_from_two_fingers_up():
    prompter = Prompter(rounds=4, seed=3)
    labels = [step.label for step, _ in prompter.plan]
    for index, label in enumerate(labels):
        if label in ("two_down", "two_back"):
            assert labels[index - 1] == "two_up" and prompter.plan[index][1] == FOLLOW_S
        if label == "claw_turn":  # likewise the knob is gripped before it is turned
            assert labels[index - 1] == "claw" and prompter.plan[index][1] == FOLLOW_S


def test_every_round_covers_every_pose_in_a_different_order():
    prompter = Prompter(rounds=3)
    per_round = len(prompter.plan) // 3
    rounds = [[step.label for step, _ in prompter.plan[i * per_round : (i + 1) * per_round]] for i in range(3)]
    assert all(Counter(labels) == Counter(rounds[0]) for labels in rounds)
    assert rounds[0] != rounds[1] != rounds[2]
    assert [step.label for step, _ in Prompter(rounds=3).plan] == sum(rounds, [])  # and the same every time


def test_a_recording_can_ask_for_just_some_poses():
    prompter = Prompter(rounds=3, only={"claw"})
    assert [step.label for step, _ in prompter.plan] == ["claw", "claw_turn"] * 3  # with what follows on from it
    assert {step.label for step, _ in Prompter(rounds=1, only={"fist", "pinch"}).plan} == {"fist", "pinch"}
    with pytest.raises(ValueError, match="no such pose: clew"):
        Prompter(only={"clew"})
    shown = run(prompter)
    assert {view["caption"] for _, view in shown} == {"Get ready", "Hold it"}  # and nothing about moving the hand


def test_a_recording_stopped_early_keeps_the_poses_finished_so_far(tmp_path):
    prompter = Prompter(rounds=1)
    run(prompter, until=50.0 + 3.0 + READY_S + HOLD_S + 1.0)  # into the second pose
    prompter.save(tmp_path / "session.labels.json", "ada")
    saved = json.loads((tmp_path / "session.labels.json").read_text())
    assert saved["person"] == "ada" and [hold["label"] for hold in saved["steps"]] == [prompter.plan[0][0].label]
    assert saved["steps"][0]["end"] - saved["steps"][0]["start"] == HOLD_S


def test_the_overlay_is_told_the_prompt_and_keeps_its_text_while_it_fades():
    bridge = Bridge(Config())
    changes = []
    bridge.promptChanged.connect(lambda: changes.append(dict(bridge.prompt)))
    view = Prompter(rounds=1).step(10.0)
    bridge.apply(OverlayState(), None, view)
    bridge.apply(OverlayState(), None, view)  # nothing new, nothing sent
    bridge.apply(OverlayState())
    assert changes == [view, {**view, "visible": False}]
