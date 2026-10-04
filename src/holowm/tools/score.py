"""Measures HoloWM against prompted recordings: what each asked-for pose was read as, and what it set off.

A recording made by `holowm collect` says which pose was being held when. Here its landmarks are
read the way the running program reads them, and the two are compared.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from holowm.config import Config
from holowm.core.actions import WindowInfo
from holowm.core.engine import Engine
from holowm.core.hands import HandTracker
from holowm.launcher.launch import Launcher
from holowm.launcher.menu import MenuItem
from holowm.tracker.types import FrameSample
from holowm.x11.fake import FakeBackend

_REACT_S = 0.6  # the start of each hold is left out: the hand is still getting there
_EARLY_S = 1.0  # a pose is often made, and its gesture set off, while the prompt still says "get ready"
_TICK_S = 1.0 / 120.0
_SCREEN = (2880, 1800)

# For each prompted label: the poses that count as read right, and the gesture that should run.
EXPECTED: dict[str, tuple[set[str] | None, str | None]] = {
    "open": ({"open"}, None),
    "relaxed": ({"neutral", "open"}, None),
    "pinch": ({"pinch_index"}, "move"),
    "pinch_side": ({"pinch_index"}, "move"),
    "middle_pinch": ({"neutral", "open"}, None),  # this was the click once; it is no gesture now
    "pinky_pinch": ({"pinch_pinky"}, "menu"),
    "fist": ({"fist"}, "close"),
    "two_up": ({"two_finger"}, "scroll"),
    "two_down": ({"two_finger"}, "scroll"),
    "two_back": ({"two_finger"}, "scroll"),
    "claw": ({"claw"}, "knob"),
    "claw_turn": ({"claw"}, "knob"),
    "aim": ({"aim"}, None),
    "aim_press": ({"press"}, "click"),
    "y_sign": ({"y_sign"}, "dictate"),
    "point": ({"neutral", "open"}, None),  # the thumb tucked in from the start: only pointing
    "other": ({"neutral", "open"}, None),
    "chin": (None, "switcher"),  # read from the face and the hand together, not from a pose
}
POSES = ["open", "neutral", "pinch_index", "pinch_pinky", "fist", "two_finger", "claw", "aim", "press", "y_sign", "no hand"]
_SHORT = {"pinch_index": "pinch", "pinch_pinky": "pinky", "two_finger": "two", "y_sign": "y", "no hand": "none"}
_CARRIES_ON = {"two_down", "two_back", "claw_turn", "aim_press"}  # these are asked for as a continuation of the pose before them


@dataclass
class Session:
    name: str
    person: str
    frames: list[FrameSample]
    steps: list[dict]  # each with "label", "start" and "end", on the frames' clock


@dataclass
class Report:
    poses: dict[str, Counter] = field(default_factory=dict)  # prompted label -> how its frames were read
    holds: Counter = field(default_factory=Counter)  # prompted label -> how many times it was held
    ran: Counter = field(default_factory=Counter)  # ... in how many of those the right gesture ran at all
    kept: Counter = field(default_factory=Counter)  # ... and the share of each hold it ran for, summed
    strays: dict[str, Counter] = field(default_factory=dict)  # prompted label -> other gestures, by holds
    people: dict[str, list[int]] = field(default_factory=dict)  # person -> [frames read right, frames]

    def right(self, label: str) -> float | None:
        """The share of a label's frames that were read as a pose it accepts."""
        accepted = EXPECTED.get(label, (None, None))[0]
        total = sum(self.poses.get(label, Counter()).values())
        if accepted is None or not total:
            return None
        return sum(n for pose, n in self.poses[label].items() if pose in accepted) / total


def load_session(recording: Path) -> Session:
    labels_path = recording.with_suffix(".labels.json")
    if not labels_path.exists():
        raise ValueError(f"{labels_path} not found; `holowm collect` makes a recording with labels")
    labels = json.loads(labels_path.read_text())
    frames = [FrameSample.from_dict(json.loads(line)) for line in recording.read_text().splitlines() if line]
    return Session(recording.stem, labels.get("person", ""), frames, labels["steps"])


def read_poses(session: Session, cfg: Config) -> list[tuple[float, str]]:
    """The pose the rules give the hand at each camera frame."""
    tracker = HandTracker(cfg, _SCREEN)
    out = []
    for frame in session.frames:
        tracker.update(frame)
        tracker.step(frame.t_capture)
        hand = min(tracker.hands.values(), key=lambda h: h.id, default=None)
        out.append((frame.t_capture, hand.pose.value if hand is not None and frame.hands else "no hand"))
    return out


def _name(gesture) -> str:
    return type(gesture).__name__.removesuffix("Interaction").lower()


def read_gestures(session: Session, cfg: Config) -> list[tuple[float, str | None]]:
    """The gesture running at each tick when the recording is played through the engine.

    A stand-in window fills the screen, so that a pinch or a fist always has something under it.
    """
    backend = FakeBackend(_SCREEN)
    # The pie menu is given nothing to offer, so a pinky pinch opens it and can launch nothing.
    engine = Engine(cfg, backend, Launcher(backend, MenuItem("Root", children=[])))
    out: list[tuple[float, str | None]] = []
    frames = session.frames
    if not frames:
        return out
    # Each pose is judged afresh: a gesture still going when the next prompt appears (a switcher
    # left open, say) is ended there, unless that prompt carries on from it or asks for the same gesture.
    afresh = [
        (prior["end"], EXPECTED.get(step["label"], (None, None))[1])
        for prior, step in zip(session.steps, session.steps[1:])
        if step["label"] not in _CARRIES_ON
    ]
    t, sent = frames[0].t_result, 0
    while t < frames[-1].t_result + 0.3:
        if afresh and t >= afresh[0][0]:
            wanted = afresh.pop(0)[1]
            if engine.active is not None and _name(engine.active) != wanted:
                engine.cancel_active()
        if engine.active is None:  # put back whatever the last gesture did to the window
            backend.replace_windows(WindowInfo(1, 0, 0, *_SCREEN, title="stand-in"))
        while sent < len(frames) and frames[sent].t_result <= t:
            engine.on_frame(frames[sent])
            sent += 1
        engine.tick(t)
        out.append((t, _name(engine.active) if engine.active is not None else None))
        t += _TICK_S
    return out


def score(sessions: list[Session], cfg: Config) -> Report:
    report = Report()
    for session in sessions:
        poses, gestures = read_poses(session, cfg), read_gestures(session, cfg)
        tally = report.people.setdefault(session.person, [0, 0])
        for step in session.steps:
            label, begin, end = step["label"], step["start"] + _REACT_S, step["end"]
            accepted, expected = EXPECTED.get(label, (None, None))
            read = Counter(pose for t, pose in poses if begin <= t < end)
            report.poses.setdefault(label, Counter()).update(read)
            if accepted is not None:
                tally[0] += sum(n for pose, n in read.items() if pose in accepted)
                tally[1] += sum(read.values())
            settled = [gesture for t, gesture in gestures if begin <= t < end]
            report.holds[label] += 1
            if expected is None:
                report.ran[label] += all(gesture is None for gesture in settled)
            else:
                report.ran[label] += any(gesture == expected for t, gesture in gestures if step["start"] - _EARLY_S <= t < end)
                report.kept[label] += settled.count(expected) / max(len(settled), 1)
            for stray in {gesture for gesture in settled if gesture is not None and gesture != expected}:
                report.strays.setdefault(label, Counter())[stray] += 1
    return report


def format_report(report: Report) -> str:
    def share(n: int, total: int) -> str:
        return f"{round(100 * n / total):3d}%" if n else "   ."

    labels = [label for label in EXPECTED if label in report.holds] + sorted(set(report.holds) - set(EXPECTED))
    lines = ["Poses: what the frames of each prompted hold were read as", ""]
    lines.append(f"{'prompted':<12} {'holds':>5} {'frames':>6}  " + " ".join(f"{_SHORT.get(p, p):>7}" for p in POSES) + "    right")
    for label in labels:
        read = report.poses.get(label, Counter())
        total = sum(read.values())
        right = report.right(label)
        cells = " ".join(f"{share(read[p], total):>7}" for p in POSES) if total else ""
        lines.append(
            f"{label:<12} {report.holds[label]:>5} {total:>6}  {cells}"
            + ("" if right is None else f"    {round(100 * right):4d}%")
        )
    lines += ["", "Gestures: what ran when each hold was played through HoloWM over a stand-in window", ""]
    lines.append(f"{'prompted':<12} {'holds':>5}  {'should run':<10}  {'did':>5}  {'kept up':>7}  other gestures (in how many holds)")
    for label in labels:
        expected = EXPECTED.get(label, (None, None))[1]
        strays = ", ".join(f"{name} in {n}" for name, n in sorted(report.strays.get(label, Counter()).items())) or "-"
        did = f"{report.ran[label]}/{report.holds[label]}"
        # A close is over in under a second, so how long it lasted says nothing.
        kept = "-" if expected in (None, "close") else f"{round(100 * report.kept[label] / report.holds[label])}%"
        lines.append(f"{label:<12} {report.holds[label]:>5}  {expected or 'nothing':<10}  {did:>5}  {kept:>7}  {strays}")
    right, frames = (sum(v[i] for v in report.people.values()) for i in (0, 1))
    lines.append("")
    if frames:
        lines.append(f"Poses read right: {100 * right / frames:.0f}% of {frames} frames.")
    lines.append(f"Right gesture, or rightly none: {sum(report.ran.values())} of {sum(report.holds.values())} holds.")
    if len(report.people) > 1:
        each = ", ".join(f"{person or 'unnamed'} {100 * r / max(n, 1):.0f}%" for person, (r, n) in sorted(report.people.items()))
        lines.append(f"Poses read right, by person: {each}.")
    return "\n".join(lines)


def run_score(recordings: list[Path], cfg: Config) -> int:
    print(format_report(score([load_session(path) for path in recordings], cfg)))
    return 0
