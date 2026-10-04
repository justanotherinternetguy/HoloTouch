"""Train the letter model HoloTouch comes with, on public landmarks of the American manual alphabet.

    .venv/bin/python research/letters_public.py [--check recordings/me-right-1.jsonl ...]

The landmarks are ASLNow!'s (https://huggingface.co/datasets/sid220/asl-now-fingerspelling, MIT
licence): about two thousand hands, of several people, as MediaPipe's hand landmarker saw them.
They are fetched once with git, to ~/.cache/holotouch/letters/asl-now. The model is written to
src/holotouch/core/letters.npz, and the hands themselves beside it, to letters_public.npz, for
`holotouch train-letters` to add your own to.

Before that it is tested on hands it has not seen: the data is split five ways, and each fifth is
read by a model trained on the rest. The fifths are drawn at random, and nothing says whose hand
each one is, so a person's hands are on both sides of every split: on somebody new it will do
worse than this says. --check reads recordings made by `holotouch collect` with it, which shows how
it does on this camera. Their poses are no letters, but some are near enough to one: the letter
Y is Y, taking aim is L, two fingers up is V or U.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from holotouch.config import CACHE_DIR
from holotouch.core.letters import BUNDLED_PATH, LETTERS, PUBLIC_PATH, LetterModel, letter_features, train

DATA_URL = "https://huggingface.co/datasets/sid220/asl-now-fingerspelling"
DATA_REVISION = "9b3c96ae0adb7744a2c9fc72692842e6b3e25e33"
DATA_DIR = CACHE_DIR / "letters" / "asl-now"
# The pictures were a web page's view of a webcam, whose shape was not written down. Taken as
# 4:3 the palms come out as wide for their length as they do in recordings made here.
ASPECT = 4 / 3


def load_public() -> tuple[np.ndarray, np.ndarray]:
    """Every hand, its x and depth scaled by the picture's aspect, and the index into LETTERS of what it spells."""
    if not DATA_DIR.exists():
        DATA_DIR.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--quiet", DATA_URL, str(DATA_DIR)], check=True)
        subprocess.run(["git", "-C", str(DATA_DIR), "checkout", "--quiet", DATA_REVISION], check=True)
    hands, labels = [], []
    for index, letter in enumerate(LETTERS):
        for path in sorted((DATA_DIR / letter.upper()).glob("*.json")):
            points = json.loads(path.read_text())
            if len(points) == 21:
                hands.append([[p["x"], p["y"], p["z"]] for p in points])
                labels.append(index)
    return np.array(hands) * (ASPECT, 1.0, ASPECT), np.array(labels)


def held_out(hands: np.ndarray, labels: np.ndarray, folds: int = 5) -> np.ndarray:
    """What each hand was read as by a model trained on the other four fifths of them."""
    order = np.random.default_rng(1).permutation(len(hands))
    read = np.zeros(len(hands), dtype=int)
    for fold in range(folds):
        test = order[fold::folds]
        rest = np.setdiff1d(order, test)
        model = train(hands[rest], labels[rest], LETTERS)
        read[test] = model.probabilities(letter_features(hands[test], 1.0)).argmax(axis=1)
    return read


def report(read: np.ndarray, labels: np.ndarray) -> None:
    print(f"Read right: {100 * (read == labels).mean():.1f}% of {len(labels)} hands not trained on.\n")
    print("letter  hands  right  most often taken for")
    for index, letter in enumerate(LETTERS):
        mine = read[labels == index]
        wrong = Counter(LETTERS[r] for r in mine if r != index).most_common(2)
        taken = ", ".join(f"{other.upper()} ({n})" for other, n in wrong) or "-"
        print(f"{letter.upper():<6} {len(mine):>6}  {100 * (mine == index).mean():4.0f}%  {taken}")


def check(model: LetterModel, recordings: list[Path]) -> None:
    from holotouch.config import Config
    from holotouch.tools.score import _REACT_S, load_session

    aspect = Config().camera.width / Config().camera.height
    for recording in recordings:
        session = load_session(recording)
        print(f"\n{recording.name}: what the frames of each prompted hold were read as")
        for label in sorted({step["label"] for step in session.steps}):
            holds = [step for step in session.steps if step["label"] == label]
            hands = [
                frame.hands[0].image
                for step in holds
                for frame in session.frames
                if step["start"] + _REACT_S <= frame.t_capture < step["end"] and len(frame.hands) == 1
            ]
            if not hands:
                continue
            p = model.probabilities(letter_features(np.array(hands), aspect))
            top = Counter(model.classes[i] for i in p.argmax(axis=1)).most_common(3)
            said = ", ".join(f"{letter.upper()} {100 * n / len(hands):.0f}%" for letter, n in top)
            print(f"  {label:<12} {len(hands):>4} frames   {said}   (median confidence {np.median(p.max(axis=1)):.2f})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=BUNDLED_PATH, help="where to save the model")
    parser.add_argument("--check", type=Path, nargs="*", default=[], help="recordings made by `holotouch collect` to read with it")
    args = parser.parse_args()
    hands, labels = load_public()
    report(held_out(hands, labels), labels)
    model = train(hands, labels, LETTERS)
    model.save(args.out)
    print(f"\nTrained on all {len(hands)} hands and saved to {args.out} ({args.out.stat().st_size / 1000:.0f} kB).")
    if args.out == BUNDLED_PATH:
        # Kept from the wrist, where a quarter of a thousandth of the picture's height is detail enough.
        with open(PUBLIC_PATH, "wb") as out:
            np.savez_compressed(out, hands=(hands - hands[:, :1]).astype(np.float16), labels=labels.astype(np.uint8))
        print(f"The hands are in {PUBLIC_PATH} ({PUBLIC_PATH.stat().st_size / 1000:.0f} kB).")
    check(model, args.check)
    return 0


if __name__ == "__main__":
    sys.exit(main())
