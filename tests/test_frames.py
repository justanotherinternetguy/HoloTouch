import json
import threading
import time

import cv2
import numpy as np
import pytest

from holowm.cli import main
from holowm.config import Config
from holowm.tracker import frames
from holowm.tracker.frames import FrameWriter, frame_name
from holowm.tracker.process import pump
from holowm.tracker.source import RecordingSource, TrackerSource
from holowm.tracker.types import FrameSample


def picture(seed: int = 0) -> np.ndarray:
    """A smooth RGB frame that is red on the left and blue on the right."""
    ramp = np.linspace(0.0, 1.0, 160)
    rgb = np.zeros((90, 160, 3))
    rgb[..., 0] = 255 * (1 - ramp)
    rgb[..., 1] = (40 * seed) % 255
    rgb[..., 2] = 255 * ramp
    return rgb.astype(np.uint8)


def test_frames_are_saved_as_the_landmarker_saw_them(tmp_path):
    writer = FrameWriter(tmp_path / "session.frames")
    times = [1234.5 + i / 30.0 for i in range(5)]
    for i, t in enumerate(times):
        writer.save(picture(i), t)
    writer.close()
    saved = sorted(p.name for p in writer.directory.iterdir())
    assert saved == [frame_name(t) for t in times]  # in order, and nothing half-written left behind
    back = cv2.cvtColor(cv2.imread(str(writer.directory / frame_name(times[3]))), cv2.COLOR_BGR2RGB)
    assert np.abs(back.astype(int) - picture(3)).mean() < 3  # same colours, same way round


def test_a_recording_names_the_picture_of_each_of_its_frames():
    # The time goes through JSON on its way to whoever matches landmarks to pictures.
    t = 73125.03370475
    assert frame_name(FrameSample.from_dict(FrameSample(1, t, t + 0.02).to_dict()).t_capture) == frame_name(t)
    assert frame_name(t) == "000073125033705.jpg"
    assert frame_name(t) < frame_name(t + 1 / 30.0) < frame_name(t + 1000.0)


def test_frames_are_dropped_rather_than_stalling_the_camera(tmp_path, monkeypatch):
    started, release = threading.Event(), threading.Event()
    encode = cv2.imencode

    def slow_encode(*args):
        started.set()
        release.wait()
        return encode(*args)

    monkeypatch.setattr(frames.cv2, "imencode", slow_encode)
    writer = FrameWriter(tmp_path)
    writer.save(picture(), 0.0)
    assert started.wait(5.0)  # the disk is now "busy" with the first frame
    begun = time.monotonic()
    for i in range(1, frames._BACKLOG + 11):
        writer.save(picture(), i / 30.0)
    assert time.monotonic() - begun < 1.0
    assert writer.dropped == 10
    release.set()
    writer.close()
    assert len(list(tmp_path.glob("*.jpg"))) == frames._BACKLOG + 1


class StubCamera:
    def __init__(self, count: int, alive: list[bool]):
        self.frames = [(picture(i), 500.0 + i / 30.0) for i in range(count)]
        self.alive = alive
        self.index = 0

    def read(self):
        if self.index == len(self.frames):
            self.alive[0] = False
            return None
        self.index += 1
        return self.frames[self.index - 1]


class StubLandmarker:
    def __init__(self):
        self.times = []

    def submit(self, rgb, captured_at, face=False):
        self.times.append(captured_at)


def test_every_camera_frame_is_saved_even_those_not_tracked(tmp_path):
    alive = [True]
    camera, landmarker, writer = StubCamera(8, alive), StubLandmarker(), FrameWriter(tmp_path)
    idle_since = [time.monotonic() - 60.0]  # no hands for a minute: only every second frame is tracked
    assert pump(camera, landmarker, Config(), alive, idle_since, writer) is None
    writer.close()
    assert len(landmarker.times) == 4
    assert sorted(p.name for p in tmp_path.iterdir()) == [frame_name(t) for _, t in camera.frames]


def test_tracking_without_saving_frames(tmp_path):
    alive = [True]
    camera, landmarker = StubCamera(4, alive), StubLandmarker()
    assert pump(camera, landmarker, Config(), alive, [time.monotonic()]) is None
    assert landmarker.times == [t for _, t in camera.frames]


class StubSource:
    """Stands in for the tracker process, so these tests never open the camera."""

    made: list = []

    def __init__(self, cfg=None, frames_dir=None):
        self.error = None
        self.frames_dir = frames_dir
        self.waiting = [FrameSample(seq, 40.0 + seq / 30.0, 40.02 + seq / 30.0) for seq in range(3)]
        self.stopped = False
        StubSource.made.append(self)

    def drain(self):
        frames, self.waiting = self.waiting, []
        return frames

    def stop(self):
        self.stopped = True


@pytest.fixture
def holowm(monkeypatch, tmp_path):
    monkeypatch.setattr(StubSource, "made", [])
    monkeypatch.setattr("holowm.tracker.source.TrackerSource", StubSource)
    return lambda *args: main(["--config", str(tmp_path / "none.toml"), *args])


@pytest.fixture
def record(holowm):
    return lambda *args: holowm("record", *args, "--seconds", "0.01")


def test_recording_source_writes_what_it_passes_on(tmp_path):
    inner = StubSource()
    source = RecordingSource(inner, tmp_path / "new" / "session.jsonl")
    passed = source.drain() + source.drain()
    inner.error = "camera unplugged"
    assert source.error == "camera unplugged"
    source.stop()
    written = [FrameSample.from_dict(json.loads(line)) for line in (tmp_path / "new" / "session.jsonl").read_text().splitlines()]
    assert [f.t_capture for f in written] == [f.t_capture for f in passed] == [40.0 + seq / 30.0 for seq in range(3)]
    assert source.count == 3 and inner.stopped


def test_record_writes_the_samples_it_is_sent(record, tmp_path, capsys):
    assert record(str(tmp_path / "session.jsonl")) == 0
    assert len((tmp_path / "session.jsonl").read_text().splitlines()) == 3
    assert "wrote 3 frames" in capsys.readouterr().out and StubSource.made[0].stopped


def test_run_refuses_recordings_it_cannot_make(holowm, tmp_path, capsys):
    assert holowm("run", "--replay", str(tmp_path / "old.jsonl"), "--record", str(tmp_path / "new.jsonl")) == 2
    assert holowm("run", "--dry-run", "--frames") == 2
    (tmp_path / "session.frames").mkdir()
    (tmp_path / "session.frames" / frame_name(1.0)).write_bytes(b"")
    assert holowm("run", "--dry-run", "--record", str(tmp_path / "session.jsonl"), "--frames") == 2
    assert StubSource.made == [] and list(tmp_path.glob("*.jsonl")) == []


def test_record_saves_frames_beside_the_recording_only_when_asked(record, tmp_path):
    assert record(str(tmp_path / "plain.jsonl")) == 0
    assert record(str(tmp_path / "session.jsonl"), "--frames") == 0
    assert [source.frames_dir for source in StubSource.made] == [None, tmp_path / "session.frames"]


def test_record_makes_the_directory_it_is_told_to_write_in(record, tmp_path):
    assert record(str(tmp_path / "recordings" / "new" / "session.jsonl"), "--frames") == 0
    assert (tmp_path / "recordings" / "new" / "session.jsonl").exists()


def test_record_will_not_mix_frames_into_an_earlier_recording(record, tmp_path, capsys):
    earlier = tmp_path / "session.frames"
    earlier.mkdir()
    (earlier / frame_name(1.0)).write_bytes(b"")
    assert record(str(tmp_path / "session.jsonl"), "--frames") == 2
    assert "already holds frames" in capsys.readouterr().err
    assert StubSource.made == [] and not (tmp_path / "session.jsonl").exists()


class CountingSource(TrackerSource):
    """A tracker source that only counts how often its process would be started and stopped."""

    def __init__(self):
        self.starts = self.stops = 0
        super().__init__(Config())

    def _start(self):
        self.starts += 1
        self._process = self._conn = None
        self._started = self._last_message = float("-inf")  # long enough ago to be restarted at once

    def _stop_process(self):
        self.stops += 1


def test_suspended_tracker_lets_go_of_the_camera_and_is_not_restarted():
    source = CountingSource()
    source.drain()
    assert source.starts == 2  # a tracker that has died is started again
    source.suspend()
    source.suspend()
    assert source.stops == 2  # once to restart it, once to suspend it
    for _ in range(3):
        assert source.drain() == []
    assert source.starts == 2
    source.resume()
    source.resume()
    assert source.starts == 3
