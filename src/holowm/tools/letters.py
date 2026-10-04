"""Trains the letter model on your own hand, from recordings made by `holowm collect --letters`.

Your hands are added to the public ones that the model HoloWM comes with was trained on, so a
letter you held only one way is still known held another. It says how the model does on holds it
was not trained on, beside the model HoloWM comes with read on the same frames, and saves it
where spelling looks for it.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

from holowm.config import Config
from holowm.core.letters import BUNDLED_PATH, LETTERS, OWN_PATH, REST, LetterModel, letter_features, public_hands, train
from holowm.tools.prompts import LETTER_PREFIX, REST_LABEL
from holowm.tools.score import _REACT_S, Session, load_session

_FOLDS = 4  # at most: with fewer holds of a letter than this, each hold is a fold of its own
_EPOCHS = 300
_COPIES = 6  # how many times over each hand is varied in training: fewer than for the public hands alone, which are fewer


def spelt_by(label: str) -> str | None:
    """The class a prompted label stands for: a letter, REST, or None for a label that is neither."""
    if label == REST_LABEL:
        return REST
    letter = label.removeprefix(LETTER_PREFIX)
    return letter if label.startswith(LETTER_PREFIX) and letter in LETTERS else None


def examples(sessions: list[Session], cfg: Config) -> tuple[np.ndarray, list[str], np.ndarray]:
    """Every frame inside a hold that shows exactly one hand: the hand, what it spells, and which hold of that it is.

    The hands come with x and depth scaled by the picture's aspect, as letters.train takes them.
    """
    aspect = cfg.camera.width / cfg.camera.height
    hands, spelt, hold_of = [], [], []
    seen: Counter = Counter()
    for session in sessions:
        for step in session.steps:
            what = spelt_by(step["label"])
            if what is None:
                continue
            for frame in session.frames:
                if step["start"] + _REACT_S <= frame.t_capture < step["end"] and len(frame.hands) == 1:
                    hands.append(frame.hands[0].image)
                    spelt.append(what)
                    hold_of.append(seen[what])
            seen[what] += 1
    return np.array(hands, dtype=np.float64).reshape(-1, 21, 3) * (aspect, 1.0, aspect), spelt, np.array(hold_of, dtype=int)


def fit(hands: np.ndarray, labels: np.ndarray, classes: str) -> LetterModel:
    """A model of your hands and the public ones together: for each letter, yours count as much as theirs."""
    theirs, their_labels = public_hands()
    their_labels = np.array([classes.index(LETTERS[index]) for index in their_labels])
    both, both_labels = np.concatenate([hands, theirs]), np.concatenate([labels, their_labels])
    mine = np.arange(len(both)) < len(hands)
    weights = np.zeros(len(both))
    for index in range(len(classes)):
        for side in (mine, ~mine):
            of_it = side & (both_labels == index)
            weights[of_it] = 1.0 / max(int(of_it.sum()), 1)
    return train(both, both_labels, classes, epochs=_EPOCHS, copies=_COPIES, weights=weights)


def held_out(hands: np.ndarray, labels: np.ndarray, hold_of: np.ndarray, classes: str) -> np.ndarray | None:
    """What each frame was read as by a model trained on other holds than its own; None with one hold of each."""
    holds = min(int(hold_of[labels == index].max()) + 1 for index in set(labels.tolist()))
    folds = min(holds, _FOLDS)
    if folds < 2:
        return None
    read = np.zeros(len(hands), dtype=int)
    for fold in range(folds):
        test = hold_of % folds == fold
        model = fit(hands[~test], labels[~test], classes)
        read[test] = model.probabilities(letter_features(hands[test], 1.0)).argmax(axis=1)
    return read


def format_report(classes: str, labels: np.ndarray, hold_of: np.ndarray, read: np.ndarray, bundled: np.ndarray) -> str:
    """read and bundled are the class each frame was read as, by index into classes; -1 for one that is not among them."""

    def share(right: np.ndarray) -> str:
        return f"{round(100 * right.mean()):3d}%" if len(right) else "   -"

    lines = [f"{'letter':<7} {'holds':>5} {'frames':>6}  {'yours':>5}  {'HoloWM':>6}  yours most often took it for"]
    for index, letter in enumerate(classes):
        mine = labels == index
        if not mine.any():
            continue
        wrong = Counter(classes[r] for r in read[mine] if r != index).most_common(2)
        taken = ", ".join(f"{'rest' if other == REST else other.upper()} ({n})" for other, n in wrong) or "-"
        name = "rest" if letter == REST else letter.upper()
        theirs = share(bundled[mine] == index) if letter != REST else "   -"
        lines.append(
            f"{name:<7} {int(hold_of[mine].max()) + 1:>5} {int(mine.sum()):>6}  {share(read[mine] == index):>5}  {theirs:>6}  {taken}"
        )
    return "\n".join(lines)


def run_train_letters(recordings: list[Path], cfg: Config, out: Path = OWN_PATH) -> int:
    sessions = [load_session(path) for path in recordings]
    hands, spelt, hold_of = examples(sessions, cfg)
    if not set(spelt) - {REST}:
        raise ValueError("these recordings hold no letters; `holowm collect --letters` records them")
    classes = LETTERS + (REST if REST in spelt else "")
    labels = np.array([classes.index(c) for c in spelt])

    theirs = LetterModel.load(BUNDLED_PATH)
    bundled = np.array([classes.find(theirs.classes[i]) for i in theirs.probabilities(letter_features(hands, 1.0)).argmax(axis=1)])
    letters = labels != classes.find(REST)
    print(f"Training on {len(hands)} frames of yours and the {len(public_hands()[0])} public hands; this takes a minute or so.\n")
    read = held_out(hands, labels, hold_of, classes)
    if read is None:
        print("One hold of each letter is not enough to test a model on holds it has not seen; training on them anyway.")
        print(f"The model HoloWM comes with reads {100 * (bundled == labels)[letters].mean():.0f}% of these frames right.")
    else:
        print("Each hold read by a model that was not trained on it, and by the model HoloWM comes with\n")
        print(format_report(classes, labels, hold_of, read, bundled))
        print(
            f"\nLetters read right: yours {100 * (read == labels)[letters].mean():.0f}%, "
            f"HoloWM's {100 * (bundled == labels)[letters].mean():.0f}%, of {int(letters.sum())} frames."
        )
    missing = [letter.upper() for letter in LETTERS if letter not in spelt]
    if missing:
        print(f"\nNot recorded: {', '.join(missing)}. Those are read from the public hands alone.")
    if REST not in classes:
        print("\nNo resting hand was recorded, so this model takes every hand for some letter.")
    fit(hands, labels, classes).save(out)
    print(f"\nSaved to {out}.")
    if out == OWN_PATH:
        print("HoloWM spells with it from now on. Remove the file to go back to the model HoloWM comes with.")
    else:
        print(f'To use it, put this in ~/.config/holowm/config.toml:\n\n[spell]\nmodel = "{out}"')
    return 0
