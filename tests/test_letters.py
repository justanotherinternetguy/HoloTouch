"""The letter model: what it is told of a hand, the one HoloTouch comes with, and training one of your own."""

import json
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

from holotouch.config import Config
from holotouch.core.letters import BUNDLED_PATH, LETTERS, REST, LetterModel, letter_features, model_path, train, varied
from holotouch.tools.letters import examples, run_train_letters, spelt_by
from holotouch.tools.prompts import LETTER_SCRIPT, Prompter
from holotouch.tools.score import Session
from holotouch.tracker.types import FrameSample
from synth import make_hand

SCREEN = (2880, 1800)
ASPECT = 16 / 9
REAL = json.loads((Path(__file__).parent / "fixtures/letter_hands.json").read_text())
# Made-up hands that stand in for letters: (the pose synth makes, the letter it is taken to be).
STAND_INS = {"s": "fist", "v": "two_finger", "y": "y_sign", "l": "aim", "b": "open"}


def hand(pose, x=1400, y=900, **how):
    return make_hand(Config(), SCREEN, pose, x, y, **how)


def test_features_do_not_change_with_where_the_hand_is_or_how_near_but_do_with_which_way_it_points():
    here = letter_features(hand("aim").image, ASPECT)
    assert here.shape == (165,)
    assert np.allclose(here, letter_features(hand("aim", 600, 400).image, ASPECT), atol=1e-4)
    image = hand("aim").image
    nearer = image[0] + 1.6 * (image - image[0])  # nearer the camera, every landmark is further from the wrist
    assert np.allclose(here, letter_features(nearer, ASPECT), atol=1e-4)
    assert not np.allclose(here, letter_features(hand("aim", roll=90.0).image, ASPECT), atol=0.2)
    both = letter_features(np.stack([hand("aim").image, hand("fist").image]), ASPECT)  # several at once
    assert both.shape == (2, 165) and np.allclose(both[0], here)


@pytest.mark.parametrize("case", REAL, ids=[case["what"] for case in REAL])
def test_the_model_holotouch_comes_with_reads_real_hands_of_either_side(case):
    """Landmarks from webcam sessions of prompted poses that are, near enough, letters."""
    model = LetterModel.load(BUNDLED_PATH)
    assert model.classes == LETTERS
    looks = model.read(np.array(case["image"]), ASPECT)
    assert max(looks, key=looks.get) == case["letter"] and sum(looks.values()) == pytest.approx(1.0)


def stand_ins(rng, each=30):
    hands, labels = [], []
    classes = "".join(sorted(STAND_INS))
    for letter, pose in STAND_INS.items():
        for _ in range(each):
            image = hand(pose, roll=rng.uniform(-8, 8)).image.astype(np.float64)
            hands.append(image + rng.normal(0, 0.002, image.shape))
            labels.append(classes.index(letter))
    return np.array(hands) * (ASPECT, 1.0, ASPECT), np.array(labels), classes


def test_a_trained_model_reads_the_other_hand_too_and_comes_back_from_its_file(tmp_path):
    hands, labels, classes = stand_ins(np.random.default_rng(0))
    model = train(hands, labels, classes, epochs=150, copies=6)
    for letter, pose in STAND_INS.items():
        for mirrored in (False, True):
            image = hand(pose, 800, 1000).image.copy()
            if mirrored:  # the left hand: the same shape, the other way round
                image[:, 0] = 1.0 - image[:, 0]
            looks = model.read(image, ASPECT)
            assert max(looks, key=looks.get) == letter, (letter, mirrored)
    path = tmp_path / "mine.model"
    model.save(path)
    assert path.exists()  # under the name it was given
    again = LetterModel.load(path)
    assert again.classes == classes
    assert np.allclose(again.read(hand("aim").image, ASPECT)["l"], model.read(hand("aim").image, ASPECT)["l"], atol=1e-4)


def test_varied_hands_keep_their_order_and_about_half_are_mirrored():
    hands, labels, _ = stand_ins(np.random.default_rng(1), each=10)
    out = varied(hands, 4, np.random.default_rng(2))
    assert out.shape == (4 * len(hands), 21, 3) and np.allclose(out[:, 0], 0.0, atol=0.02)  # each centred on its wrist

    def way_round(h):  # which way round the knuckles go, seen from the wrist
        return np.sign(h[:, 5, 0] * h[:, 17, 1] - h[:, 5, 1] * h[:, 17, 0])

    flipped = way_round(out) != np.tile(way_round(hands - hands[:, :1]), 4)
    assert 0.3 < flipped.mean() < 0.7


def test_your_own_model_is_used_once_there_is_one(tmp_path, monkeypatch):
    monkeypatch.setattr("holotouch.core.letters.OWN_PATH", tmp_path / "letters.npz")
    assert model_path() == BUNDLED_PATH
    (tmp_path / "letters.npz").write_bytes(b"")
    assert model_path() == tmp_path / "letters.npz"
    assert model_path("~/elsewhere.npz") == Path.home() / "elsewhere.npz"  # what the config names comes first


def test_the_letters_script_asks_for_every_letter_that_can_be_read_and_a_resting_hand():
    prompter = Prompter(rounds=2, script=LETTER_SCRIPT)
    spelt = Counter(spelt_by(step.label) for step, _ in prompter.plan)
    assert spelt == Counter({**{letter: 2 for letter in LETTERS}, REST: 4})
    assert spelt_by("fist") is None and spelt_by("letter_j") is None
    only = Prompter(rounds=1, script=LETTER_SCRIPT, only={"letter_r", "letter_s"})
    assert {step.label for step, _ in only.plan} == {"letter_r", "letter_s"}
    with pytest.raises(ValueError, match="no such pose: letter_j"):
        Prompter(script=LETTER_SCRIPT, only={"letter_j"})
    assert all(step.text.startswith(f"{step.label[-1].upper()}: ") for step, _ in only.plan)


def recording(holds_each=2) -> Session:
    """A session in which each stand-in letter, and a resting hand, is held in turn, with nothing shown between."""
    cfg, frames, steps, t = Config(), [], [], 10.0
    shown = {**{f"letter_{letter}": pose for letter, pose in STAND_INS.items()}, "rest": "neutral"}
    for _ in range(holds_each):
        for label, pose in shown.items():
            steps.append({"label": label, "start": t, "end": t + 2.0})
            for n in range(60):
                at = t + n / 30.0
                frames.append(FrameSample(len(frames), at, at + 0.02, [make_hand(cfg, SCREEN, pose, 1400 + n, 900, roll=n / 10)]))
            t += 3.0
    return Session("made-up", "ada", frames, steps)


def test_training_on_your_own_recordings_reports_and_saves_a_model(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("holotouch.tools.letters._EPOCHS", 80)
    session = recording()
    hands, spelt, hold_of = examples([session], Config())
    assert Counter(spelt) == Counter({c: 84 for c in [*STAND_INS, REST]})  # the first 0.6 s of each hold is left out
    assert set(hold_of) == {0, 1}
    monkeypatch.setattr("holotouch.tools.letters.load_session", lambda path: session)
    out = tmp_path / "letters.npz"
    assert run_train_letters([Path("made-up.jsonl")], Config(), out) == 0
    said = capsys.readouterr().out
    assert "Letters read right: yours 100%" in said and "Not recorded: A, C, D" in said and f'model = "{out}"' in said
    model = LetterModel.load(out)
    assert model.classes == LETTERS + REST  # the letters not recorded are known from the public hands
    for letter, pose in [*STAND_INS.items(), (REST, "neutral")]:
        looks = model.read(hand(pose).image, ASPECT)
        assert max(looks, key=looks.get) == letter


def test_one_hold_of_each_letter_is_trained_on_untested_and_no_letter_is_too_few(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("holotouch.tools.letters._EPOCHS", 20)
    session = recording(holds_each=1)
    monkeypatch.setattr("holotouch.tools.letters.load_session", lambda path: session)
    assert run_train_letters([Path("made-up.jsonl")], Config(), tmp_path / "letters.npz") == 0
    assert "One hold of each letter is not enough" in capsys.readouterr().out
    session.steps = [step for step in session.steps if step["label"] == "rest"]
    with pytest.raises(ValueError, match="hold no letters"):
        run_train_letters([Path("made-up.jsonl")], Config(), tmp_path / "letters.npz")
