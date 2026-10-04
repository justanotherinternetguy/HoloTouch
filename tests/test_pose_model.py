"""The pose model: what it is given, that it learns, and that a hand's pose comes from it when configured."""

import copy
import json

import numpy as np
import pytest

from holotouch.config import Config
from holotouch.core.hands import HandTracker
from holotouch.core.pose_model import CLASSES, PoseModel, landmark_features, train
from holotouch.core.poses import Pose
from holotouch.tools.prompts import Prompter
from holotouch.tools.score import load_session
from holotouch.tools.train import examples, held_out
from holotouch.tracker.types import FrameSample, HandSample
from synth import make_hand

SCREEN = (2880, 1800)
ASPECT = 16 / 9
SHAPES = {"open": Pose.OPEN, "point": Pose.NEUTRAL, "pinch_index": Pose.PINCH_INDEX, "pinch_pinky": Pose.PINCH_PINKY,
          "fist": Pose.FIST, "two_finger": Pose.TWO_FINGER}  # fmt: skip


def hand(pose, x=1400, y=900, nearness=1.0, jitter=0.0, seed=0):
    made = make_hand(Config(), SCREEN, pose, x, y, "Right", 0.0, nearness)
    noise = np.random.default_rng(seed).normal(0, jitter, (21, 3)).astype(np.float32)
    return HandSample("Right", 0.95, made.image + noise * (1.2, 2.1, 1.0), made.world + noise)


def trained(jitter=0.002):
    x = np.array([landmark_features(hand(p, jitter=jitter, seed=s), ASPECT) for p in SHAPES for s in range(40)])
    y = np.array([CLASSES.index(SHAPES[p]) for p in SHAPES for _ in range(40)])
    return train(x, y, epochs=150)


def test_the_description_of_a_hand_does_not_depend_on_where_how_near_or_which_hand():
    here = landmark_features(hand("pinch_index"), ASPECT)
    assert here.shape == (210,)
    assert np.allclose(here, landmark_features(hand("pinch_index", 600, 400, nearness=1.7), ASPECT), atol=1e-4)
    mirrored = hand("pinch_index")
    mirrored.image[:, 0], mirrored.world[:, 0], mirrored.handedness = 1.0 - mirrored.image[:, 0], -mirrored.world[:, 0], "Left"
    assert np.allclose(here, landmark_features(mirrored, ASPECT), atol=1e-4)
    turned = hand("pinch_index")
    c, s = np.cos(0.6), np.sin(0.6)
    turned.world = turned.world @ np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], np.float32)
    assert np.allclose(here[:105], landmark_features(turned, ASPECT)[:105], atol=1e-4)
    assert not np.allclose(here, landmark_features(hand("fist"), ASPECT), atol=0.05)


def test_a_trained_model_reads_poses_it_was_shown_and_survives_saving(tmp_path):
    model = trained()
    for pose, expected in SHAPES.items():
        assert model.classify(hand(pose, 700, 500, nearness=1.4, jitter=0.002, seed=99), ASPECT) is expected
    model.save(tmp_path / "poses.npz")
    again = PoseModel.load(tmp_path / "poses.npz")
    x = landmark_features(hand("fist"), ASPECT)
    assert np.allclose(model.probabilities(x), again.probabilities(x))


def test_a_model_that_is_not_sure_says_neutral():
    model = trained()
    model.min_confidence = 1.01  # nothing is ever that sure
    assert model.classify(hand("fist"), ASPECT) is Pose.NEUTRAL


def test_a_configured_model_decides_the_pose_and_the_rules_do_otherwise(tmp_path):
    model = trained()
    model.w2[:], model.b2[:] = 0.0, 0.0
    model.b2[CLASSES.index(Pose.TWO_FINGER)] = 9.0  # a model that calls everything two fingers
    model.save(tmp_path / "poses.npz")
    cfg = Config()
    cfg.pose.model = str(tmp_path / "poses.npz")
    poses = {}
    for name, config in (("rules", Config()), ("model", cfg)):
        tracker = HandTracker(config, SCREEN)
        for i in range(12):
            tracker.update(FrameSample(i, 5.0 + i / 30, 5.0 + i / 30, [hand("fist")]))
        (tracked,) = tracker.hands.values()
        poses[name] = tracked.pose
    assert poses == {"rules": Pose.FIST, "model": Pose.TWO_FINGER}
    cfg.pose.model = str(tmp_path / "missing.npz")
    with pytest.raises(ValueError, match="cannot read"):
        HandTracker(cfg, SCREEN)


def labelled(tmp_path, name, order):
    """A recording in which each pose of `order` is held for three seconds, saved with its labels."""
    frames, steps, t = [], [], 30.0
    for pose in order:
        steps.append({"label": pose, "start": t + 1.5, "end": t + 4.5})
        t += 4.5
    lookup = {"relaxed": "point", "pinch": "pinch_index", "two_up": "two_finger"}
    for seq in range(round((t + 1 - 29) * 30)):
        now = 29.0 + seq / 30
        step = next((s for s in steps if s["start"] <= now < s["end"]), None)
        pose = lookup.get(step["label"], step["label"]) if step else "open"
        frames.append(FrameSample(seq, now, now + 0.02, [hand(pose, jitter=0.002, seed=seq)]))
    path = tmp_path / f"{name}.jsonl"
    path.write_text("".join(json.dumps(f.to_dict()) + "\n" for f in frames))
    prompter = Prompter(rounds=1)
    prompter.done = steps
    prompter.save(path.with_suffix(".labels.json"), "ada")
    return load_session(path)


def test_training_examples_come_from_the_holds_and_a_held_out_recording_is_read_right(tmp_path):
    order = ["fist", "relaxed", "pinch", "open", "two_up"]
    sessions = [labelled(tmp_path, "one", order), labelled(tmp_path, "two", order[::-1])]
    x, y = examples(sessions[0], Config())
    assert len(x) == 5 * 72 and sorted(set(y)) == sorted(CLASSES.index(p) for p in (Pose.OPEN, Pose.NEUTRAL, Pose.PINCH_INDEX, Pose.FIST, Pose.TWO_FINGER))
    report = held_out(copy.deepcopy(sessions), Config())
    assert report.holds == {pose: 2 for pose in order}
    assert all(report.right(pose) == 1.0 for pose in order) and report.ran == report.holds
