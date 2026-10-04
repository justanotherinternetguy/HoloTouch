"""Taking a photo: by HoloTouch itself, and in a camera app that was just started, against the fake window backend."""

from datetime import datetime
from pathlib import Path

from holotouch.config import Config
from holotouch.core.actions import WindowInfo
from holotouch.launcher import camera
from holotouch.launcher.camera import NO_PHOTO, Photographer, Shutter, camera_command, photo_dir, photo_path
from holotouch.x11.fake import FakeBackend

APP = WindowInfo(7, 200, 100, 800, 640, title="Camera")


def backend_with_editor():
    backend = FakeBackend()
    backend.add_window(WindowInfo(1, 0, 0, 900, 700, title="editor"))
    backend.activate(1)
    backend.commands.clear()
    return backend


def run(shutter, start, seconds, step=0.05):
    """Step the shutter for a while; the time it finished at, or None if it is still at work."""
    t = start
    while t < start + seconds:
        if not shutter.step(t):
            return t
        t += step
    return None


def test_shutter_key_is_pressed_once_the_apps_window_has_had_time_to_start_the_camera():
    backend = backend_with_editor()
    shutter = Shutter(backend, Config(), 100.0)
    assert run(shutter, 100.0, 1.0) is None and not backend.commands  # no window yet: nothing is typed
    backend.add_window(APP)
    assert run(shutter, 101.0, 2.9) is None
    assert backend.commands == [("activate", 7)]  # the app is given the keyboard, and time
    done = run(shutter, 103.9, 1.0)
    assert done is not None and 103.95 <= done <= 104.1
    assert backend.commands == [("activate", 7), ("press_key", "t")]


def test_shutter_key_is_never_typed_into_another_window():
    backend = backend_with_editor()
    shutter = Shutter(backend, Config(), 100.0)
    backend.add_window(APP)
    assert run(shutter, 100.0, 2.0) is None
    backend.activate(1)  # the editor takes the keyboard back, and keeps taking it
    backend.activate = lambda win_id: backend._record("activate", win_id)
    assert run(shutter, 102.0, 10.0) is not None
    assert not [c for c in backend.commands if c[0] == "press_key"]


def test_shutter_takes_the_keyboard_back_for_the_app_before_pressing():
    backend = backend_with_editor()
    shutter = Shutter(backend, Config(), 100.0)
    backend.add_window(APP)
    assert run(shutter, 100.0, 2.0) is None
    backend.activate(1)  # something else was clicked meanwhile
    assert run(shutter, 102.0, 5.0) is not None
    assert backend.commands[-2:] == [("activate", 7), ("press_key", "t")]


def test_no_photo_if_the_app_never_shows_a_window_or_is_closed_first():
    backend = backend_with_editor()
    assert run(Shutter(backend, Config(), 100.0), 100.0, 20.0) is not None and not backend.commands
    shutter = Shutter(backend, Config(), 200.0)
    backend.add_window(APP)
    assert run(shutter, 200.0, 1.0) is None
    backend.close(7)
    assert run(shutter, 201.0, 5.0) is not None
    assert not [c for c in backend.commands if c[0] == "press_key"]


def test_shutter_key_can_be_changed_or_left_out():
    cfg = Config()
    cfg.gesture.camera_shutter_key, cfg.gesture.camera_shutter_ms = "space", 500
    backend = backend_with_editor()
    shutter = Shutter(backend, cfg, 100.0)
    backend.add_window(APP)
    assert run(shutter, 100.0, 2.0) is not None and backend.commands[-1] == ("press_key", "space")
    cfg.gesture.camera_shutter_key = ""
    backend = backend_with_editor()
    shutter = Shutter(backend, cfg, 100.0)
    backend.add_window(APP)
    assert run(shutter, 100.0, 2.0) is not None and not backend.commands


def test_a_camera_app_is_opened_only_where_one_is_named():
    cfg = Config()
    assert camera_command(cfg) == ""  # HoloTouch takes the photo itself, whatever is installed
    cfg.gesture.camera_command = "my-camera --selfie"
    assert camera_command(cfg) == "my-camera --selfie"


class StubSource:
    """Stands in for the tracker: asked for photos, it says later how each went."""

    def __init__(self, camera=True):
        self.camera = camera
        self.asked: list[Path] = []
        self.answers: list[tuple[str, str]] = []

    def snap(self, path):
        if self.camera:
            self.asked.append(path)
        return self.camera

    def photos(self):
        answers, self.answers = self.answers, []
        return answers


def photographer(tmp_path, **source):
    cfg = Config()
    cfg.gesture.camera_dir = str(tmp_path / "photos")
    return Photographer(cfg, StubSource(**source))


def test_a_photo_is_asked_for_at_once_and_shown_for_a_moment_when_it_is_saved(tmp_path):
    taker = photographer(tmp_path)
    assert taker.step(100.0) == ("", "")
    taker.take(100.0)
    (path,) = taker.source.asked
    assert path.parent == tmp_path / "photos" and path.name.startswith("Photo ") and path.suffix == ".jpg"
    assert taker.step(100.02) == ("", "")  # not saved yet
    taker.source.answers.append((str(path), ""))
    assert taker.step(100.05) == (str(path), "")
    assert taker.step(102.0) == (str(path), "")
    assert taker.step(103.0) == ("", "")  # and the print goes away again


def test_with_no_camera_or_one_that_cannot_save_no_photo_is_said_to_be_taken(tmp_path):
    taker = photographer(tmp_path, camera=False)  # a recording played back, or a camera lent out
    taker.take(100.0)
    assert taker.step(100.0) == ("", NO_PHOTO) and taker.step(103.0) == ("", "")
    taker = photographer(tmp_path)
    taker.take(200.0)
    taker.source.answers.append(("", "disk full"))
    assert taker.step(200.1) == ("", NO_PHOTO)
    # A camera that never answers, its process having died, is given up on.
    taker = photographer(tmp_path)
    taker.take(300.0)
    assert taker.step(301.0) == ("", "") and taker.step(302.5) == ("", NO_PHOTO)
    assert taker.step(305.0) == ("", "")


def test_photos_go_to_the_pictures_folder_under_names_that_are_free(tmp_path, monkeypatch):
    when = datetime(2026, 10, 4, 9, 30, 5)
    first = photo_path(tmp_path, when)
    assert first == tmp_path / "Photo 2026-10-04 09-30-05.jpg"
    first.write_bytes(b"taken")
    assert photo_path(tmp_path, when) == tmp_path / "Photo 2026-10-04 09-30-05 (2).jpg"  # two in one second
    cfg = Config()
    said = type("Said", (), {"stdout": f"{tmp_path}/Bilder\n"})
    monkeypatch.setattr(camera.subprocess, "run", lambda *args, **kwargs: said)
    assert photo_dir(cfg) == tmp_path / "Bilder" / "HoloTouch"
    cfg.gesture.camera_dir = "~/selfies"
    assert photo_dir(cfg) == Path.home() / "selfies"
