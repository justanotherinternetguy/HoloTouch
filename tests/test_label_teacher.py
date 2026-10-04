"""The labelling script, run on a recording made by the real frame writer, with a stand-in teacher."""

import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from holotouch.tracker.frames import FrameWriter, frame_name
from holotouch.tracker.types import FrameSample, HandSample

SCRIPT = Path(__file__).parents[1] / "research" / "label_teacher.py"
TIMES = [9000.25 + i / 30.0 for i in range(6)]
TRACKED = TIMES[:2] + TIMES[3:5]  # the frames MediaPipe was given


class StubTeacher:
    made = 0

    def __init__(self, confidence: float):
        StubTeacher.made += 1
        self.detect_s = self.pose_s = 0.0

    def label(self, rgb: np.ndarray) -> list[dict]:
        shade = round(float(rgb.mean()) / 255.0, 1)  # tells the pictures apart
        return [{"handedness": "Right", "confidence": shade, "box": [0.1, 0.3, 0.4, 0.7],
                 "image": [[0.25, 0.8]] * 21, "world": [[0.0, 0.0, 0.0]] * 21}]  # fmt: skip


@pytest.fixture
def script(monkeypatch):
    spec = importlib.util.spec_from_file_location("label_teacher", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "Teacher", StubTeacher)
    monkeypatch.setattr(StubTeacher, "made", 0)
    return module


@pytest.fixture
def recording(tmp_path) -> Path:
    path = tmp_path / "session.jsonl"
    writer = FrameWriter(path.with_suffix(".frames"))
    for i, t in enumerate(TIMES):
        writer.save(np.full((90, 160, 3), 51 * i, np.uint8), t)  # shades 0.0, 0.2, ... 1.0
    writer.close()
    hand = HandSample("Right", 0.9, np.full((21, 3), (0.75, 0.8, 0.0), np.float32), np.zeros((21, 3), np.float32))
    path.write_text("".join(json.dumps(FrameSample(i, t, t + 0.02, [hand]).to_dict()) + "\n" for i, t in enumerate(TRACKED)))
    return path


def labels(recording: Path) -> list[dict]:
    return [json.loads(line) for line in recording.with_suffix(".teacher.jsonl").read_text().splitlines()]


def test_every_picture_is_labelled_under_its_own_name(script, recording):
    assert script.main([str(recording)]) == 0
    found = labels(recording)
    assert [f"{label['t_us']:015d}.jpg" for label in found] == [frame_name(t) for t in TIMES]
    assert [label["hands"][0]["confidence"] for label in found] == [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]


def test_a_stopped_run_carries_on_where_it_left_off(script, recording):
    script.main([str(recording), "--limit", "2"])
    assert len(labels(recording)) == 2
    with recording.with_suffix(".teacher.jsonl").open("a") as out:
        out.write('{"t_us": 90002833')  # stopped in the middle of writing the third
    script.main([str(recording)])
    assert [label["hands"][0]["confidence"] for label in labels(recording)] == [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    assert StubTeacher.made == 2
    script.main([str(recording)])  # nothing left to do, so the model is not even loaded
    assert StubTeacher.made == 2 and len(labels(recording)) == 6


def test_labelling_only_some_pictures(script, recording):
    script.main([str(recording), "--every", "3"])
    assert [label["hands"][0]["confidence"] for label in labels(recording)] == [0.0, 0.6]


def test_overlay_shows_both_models_on_the_picture(script, recording):
    script.main([str(recording), "--overlay"])
    drawn = sorted(recording.with_suffix(".overlay").iterdir())
    assert [p.name for p in drawn] == [frame_name(t) for t in TIMES]

    def colour(picture: Path, x: float, y: float) -> tuple[int, int, int]:
        blue, green, red = cv2.imread(str(picture))[round(y * 90), round(x * 160)].astype(int)
        return red, green, blue

    red, green, blue = colour(drawn[1], 0.25, 0.8)  # where the teacher put the hand
    assert green > red + 60 and green > blue + 60
    red, green, blue = colour(drawn[1], 0.75, 0.8)  # where the recording has it
    assert red > green + 60 and red > blue + 60
    red, green, blue = colour(drawn[2], 0.75, 0.8)  # a frame MediaPipe was never given
    assert abs(red - green) < 30 and abs(red - blue) < 30


def test_a_recording_without_pictures_is_refused(script, tmp_path, capsys):
    (tmp_path / "bare.jsonl").write_text("")
    assert script.main([str(tmp_path / "bare.jsonl")]) == 2
    assert "holotouch record --frames" in capsys.readouterr().err
    assert StubTeacher.made == 0
