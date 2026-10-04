"""Prompted recording: asks for one pose after another and notes when each was held.

A recording made this way comes with the truth about what the hand was doing, which is what
`holowm score` measures the pose rules against.
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from pathlib import Path

READY_S = 2.0  # time to read a prompt and get the hand there; nothing is labelled during it
FOLLOW_S = 1.2  # the same, for a step that carries on from the pose before it
HOLD_S = 3.0  # how long each pose is held, and labelled
_INTRO_S = 3.0  # extra time before the very first pose


@dataclass(frozen=True)
class Step:
    label: str  # what the recording's labels call this pose
    text: str  # what the person is asked to do


# One round. Each inner list is done in one go: a pose, then what follows on from it. The tilts
# follow "two fingers up" because that is the only way a hand ever gets into them, and the thumb
# comes down to press from a hand that is taking aim.
SCRIPT = [
    [Step("open", "Open hand, palm to the camera")],
    [Step("relaxed", "Relax your hand")],
    [Step("pinch", "Pinch thumb and index")],
    [Step("pinch_side", "Turn your hand side-on, then pinch thumb and index")],
    [
        Step("aim", "Point up with one finger, thumb out to the side"),
        Step("aim_press", "Now bring the thumb down onto your middle finger"),
    ],
    [Step("pinky_pinch", "Touch thumb to pinky")],
    [Step("fist", "Make a fist")],
    [Step("two_up", "Two fingers up"), Step("two_down", "Now tip them steeply down")],
    [Step("two_up", "Two fingers up"), Step("two_back", "Now lean them back")],
    [Step("claw", "Make a claw, as if gripping a knob"), Step("claw_turn", "Now turn it, like a knob")],
    [Step("y_sign", "Thumb and pinky out, the other fingers folded: the letter Y")],
    [Step("point", "Point up with one finger, thumb tucked in")],
    [Step("other", "Anything else: wave, scratch your head")],
    [Step("chin", "Rest your fist on your chin")],
]


class Prompter:
    """Walks through the script in real time. Call step() every tick with the current time."""

    def __init__(
        self, rounds: int = 2, seed: int = 0, ready_s: float = READY_S, hold_s: float = HOLD_S, only: set[str] | None = None
    ):
        """only limits the script to the poses with these labels, each with whatever follows on from it."""
        self.hold_s = hold_s
        self.plan: list[tuple[Step, float]] = []  # each step with its time to get ready
        script = [group for group in SCRIPT if only is None or any(step.label in only for step in group)]
        known = sorted({step.label for group in SCRIPT for step in group})
        if only is not None and not only <= set(known):
            raise ValueError(f"no such pose: {', '.join(sorted(only - set(known)))} (there are: {', '.join(known)})")
        order = random.Random(seed)
        for _ in range(rounds):
            for group in order.sample(script, len(script)):
                for position, step in enumerate(group):
                    self.plan.append((step, ready_s if position == 0 else min(FOLLOW_S, ready_s)))
        if self.plan:
            self.plan[0] = (self.plan[0][0], self.plan[0][1] + _INTRO_S)
        self.done: list[dict] = []  # the holds completed so far, with when they began and ended
        self._index = 0
        self._began: float | None = None  # when the current step's time to get ready began

    @property
    def finished(self) -> bool:
        return self._index >= len(self.plan)

    def step(self, now: float) -> dict | None:
        """What to show at this moment, or None once the script is over."""
        if self._began is None:
            self._began = now
        while not self.finished:
            step, ready = self.plan[self._index]
            hold_from = self._began + ready
            if now < hold_from:
                return self._view(step, False, (now - self._began) / ready)
            if now < hold_from + self.hold_s:
                return self._view(step, True, (now - hold_from) / self.hold_s)
            self.done.append({"label": step.label, "text": step.text, "start": hold_from, "end": hold_from + self.hold_s})
            self._index += 1
            self._began = hold_from + self.hold_s
        return None

    def _view(self, step: Step, holding: bool, progress: float) -> dict:
        return {
            "visible": True,
            "holding": holding,
            "caption": "Hold it" if holding else "Get ready",
            "text": step.text,
            "progress": min(max(progress, 0.0), 1.0),
            "detail": f"{self._index + 1} of {len(self.plan)}",
        }

    def save(self, path: Path, person: str) -> None:
        """Write the holds completed so far. Times are on the clock the recording's frames use."""
        labels = {"person": person, "recorded": time.strftime("%Y-%m-%dT%H:%M:%S"), "steps": self.done}
        path.write_text(json.dumps(labels, indent=1) + "\n")
