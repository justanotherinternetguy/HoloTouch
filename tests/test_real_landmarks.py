"""Pose classification on landmarks the real model produced for MediaPipe's sample photos."""

import json
from pathlib import Path

import numpy as np
import pytest

from holowm.config import PoseConfig
from holowm.core.poses import Pose, PoseTracker, extract_features
from holowm.tracker.types import HandSample

HANDS = json.loads((Path(__file__).parent / "fixtures/real_hands.json").read_text())


def classify(name: str) -> list[Pose]:
    poses = []
    for d in HANDS[name]:
        sample = HandSample(d["handedness"], d["score"], np.array(d["image"], np.float32), np.array(d["world"], np.float32))
        tracker = PoseTracker(PoseConfig())
        features = extract_features(sample)
        for i in range(6):
            pose = tracker.update(features, i / 30.0)
        poses.append(pose)
    return poses


@pytest.mark.parametrize(
    "photo,expected",
    [
        ("fist", Pose.FIST),
        ("victory", Pose.TWO_FINGER),
        ("right_hands", Pose.OPEN),  # flat open palms facing the camera
        ("woman_hands", Pose.NEUTRAL),  # relaxed hands, thumb resting near the index finger
        ("pointing_up", Pose.NEUTRAL),
        ("thumbs_up", Pose.FIST),
    ],
)
def test_real_photo_pose(photo, expected):
    poses = classify(photo)
    assert poses and all(p is expected for p in poses)


PROMPTED = json.loads((Path(__file__).parent / "fixtures/prompted_hands.json").read_text())


def metric_gap(world: np.ndarray) -> float:
    """Thumb tip to index tip in palm lengths, by the metric landmarks alone."""
    return float(np.linalg.norm(world[4] - world[8]) / np.linalg.norm(world[9] - world[0]))


@pytest.mark.parametrize("case", PROMPTED, ids=[case["what"] for case in PROMPTED])
def test_a_hand_held_to_a_prompt_is_read_as_what_it_was(case):
    """Landmarks from a webcam session in which each pose was asked for and held."""
    sample = HandSample(case["handedness"], 1.0, np.array(case["image"], np.float32), np.array(case["world"], np.float32))
    tracker = PoseTracker(PoseConfig())
    features = extract_features(sample)
    for i in range(6):
        pose = tracker.update(features, i / 30.0)
    assert pose.value == case["pose"]
    if case["pose"] == "pinch_index":
        # The fingertips touch, yet the metric landmarks put them apart; it is the picture that shows them together.
        assert metric_gap(sample.world) > 0.3 and features.pinch_index < 0.2
    elif case["pose"] != "fist":
        assert features.pinch_index > PoseConfig().pinch_enter


def test_fingertips_that_only_line_up_in_the_picture_are_not_a_pinch():
    sample = next(case for case in PROMPTED if case["what"].startswith("open hand"))
    image, world = np.array(sample["image"], np.float32), np.array(sample["world"], np.float32)
    image[4, :2] = image[8, :2]  # the thumb tip drawn exactly on the index tip
    touching, behind = image.copy(), image.copy()
    touching[4, 2] = touching[8, 2]
    behind[4, 2] = behind[8, 2] + 0.2  # ...but a hand's length further from the camera
    assert extract_features(HandSample("Right", 1.0, touching, world)).pinch_index == pytest.approx(0.0, abs=0.01)
    assert extract_features(HandSample("Right", 1.0, behind, world)).pinch_index == pytest.approx(metric_gap(world), rel=0.01)
    # A sideways gap in the picture counts for more in a frame that is wider than it is tall.
    apart = touching.copy()
    apart[4, 0] += 0.02
    wide, square = (extract_features(HandSample("Right", 1.0, apart, world), aspect).pinch_index for aspect in (16 / 9, 1.0))
    assert wide > 1.2 * square
