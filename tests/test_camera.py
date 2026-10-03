"""Taking a photo in a camera app that was just started, against the fake window backend."""

from holowm.config import Config
from holowm.core.actions import WindowInfo
from holowm.launcher.camera import Shutter, camera_command
from holowm.x11.fake import FakeBackend

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


def test_camera_command_prefers_what_is_configured():
    cfg = Config()
    cfg.gesture.camera_command = "my-camera --selfie"
    assert camera_command(cfg) == "my-camera --selfie"
