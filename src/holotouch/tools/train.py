"""Trains the pose model on prompted recordings, and says how it does on hands it has not seen."""

from __future__ import annotations

import copy
import tempfile
from pathlib import Path

import numpy as np

from holotouch.config import Config
from holotouch.core.pose_model import CLASSES, PoseModel, landmark_features, train
from holotouch.core.poses import Pose
from holotouch.tools.score import _REACT_S, Report, Session, format_report, load_session, score

# The pose each prompted label should be read as.
TARGET = {
    "open": Pose.OPEN,
    "relaxed": Pose.NEUTRAL,
    "point": Pose.NEUTRAL,
    "other": Pose.NEUTRAL,
    "pinch": Pose.PINCH_INDEX,
    "pinch_side": Pose.PINCH_INDEX,
    "pinky_pinch": Pose.PINCH_PINKY,
    "fist": Pose.FIST,
    "chin": Pose.FIST,
    "two_up": Pose.TWO_FINGER,
    "two_down": Pose.TWO_FINGER,
    "two_back": Pose.TWO_FINGER,
    # "claw" and "claw_turn" have no class in the model, which predates them, and are left out.
}


def examples(session: Session, cfg: Config) -> tuple[np.ndarray, np.ndarray]:
    """A row of features and a class for every frame inside a hold that shows exactly one hand."""
    aspect = cfg.camera.width / cfg.camera.height
    rows, classes = [], []
    for step in session.steps:
        target = TARGET.get(step["label"])
        if target is None:
            continue
        for frame in session.frames:
            if step["start"] + _REACT_S <= frame.t_capture < step["end"] and len(frame.hands) == 1:
                rows.append(landmark_features(frame.hands[0], aspect))
                classes.append(CLASSES.index(target))
    return np.array(rows), np.array(classes, dtype=int)


def _merge(into: Report, other: Report) -> None:
    for label, read in other.poses.items():
        into.poses.setdefault(label, type(read)()).update(read)
    for label, strays in other.strays.items():
        into.strays.setdefault(label, type(strays)()).update(strays)
    into.holds.update(other.holds)
    into.ran.update(other.ran)
    into.kept.update(other.kept)
    for person, (right, frames) in other.people.items():
        tally = into.people.setdefault(person, [0, 0])
        tally[0], tally[1] = tally[0] + right, tally[1] + frames


def held_out(sessions: list[Session], cfg: Config) -> Report:
    """Each session scored with a model trained on all the others, so on a recording it never saw."""
    data = [examples(session, cfg) for session in sessions]
    report = Report()
    with tempfile.TemporaryDirectory() as scratch:
        for index, session in enumerate(sessions):
            x = np.concatenate([d[0] for i, d in enumerate(data) if i != index])
            y = np.concatenate([d[1] for i, d in enumerate(data) if i != index])
            path = Path(scratch) / f"{index}.npz"
            train(x, y).save(path)
            with_model = copy.deepcopy(cfg)
            with_model.pose.model = str(path)
            _merge(report, score([session], with_model))
    return report


def run_train(recordings: list[Path], cfg: Config, out: Path) -> int:
    sessions = [load_session(path) for path in recordings]
    cfg = copy.deepcopy(cfg)
    cfg.pose.model = ""  # the comparison below is against the rules, whatever is configured
    if len(sessions) > 1:
        print("== The rules ==\n")
        print(format_report(score(sessions, cfg)))
        print("\n== The model: each recording read by a model trained on the others ==\n")
        print(format_report(held_out(sessions, cfg)))
    else:
        print("One recording is not enough to test a model on hands it has not seen; training on it anyway.")
    data = [examples(session, cfg) for session in sessions]
    x, y = np.concatenate([d[0] for d in data]), np.concatenate([d[1] for d in data])
    train(x, y).save(out)
    print(f"\nTrained on {len(x)} frames from {len(sessions)} recordings and saved to {out}.")
    print(f'To use it, put this in ~/.config/holotouch/config.toml:\n\n[pose]\nmodel = "{out}"')
    return 0
