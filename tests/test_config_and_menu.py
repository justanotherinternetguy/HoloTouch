import json
import math
from pathlib import Path

import pytest

from holowm.config import Config, PieConfig, load_config
from holowm.core.actions import WindowInfo
from holowm.launcher.launch import Launcher, load_menu
from holowm.launcher.menu import MenuItem, PieSession, item_from_dict
from holowm.tracker.types import FrameSample
from holowm.x11.fake import FakeBackend
from synth import make_hand

REPO = Path(__file__).parent.parent


def test_config_overrides_and_rejects_unknown_keys(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[pose]\npinch_enter = 0.2\n[ui]\nscale = 2\ndebug = true\n')
    cfg = load_config(path)
    assert cfg.pose.pinch_enter == 0.2 and cfg.ui.scale == 2.0 and cfg.ui.debug is True
    assert cfg.pose.pinch_exit == Config().pose.pinch_exit
    path.write_text("[pose]\npinch_entr = 0.2\n")
    with pytest.raises(ValueError, match="pose.pinch_entr"):
        load_config(path)
    path.write_text('[ui]\nscale = "big"\n')
    with pytest.raises(ValueError, match="ui.scale"):
        load_config(path)


def test_example_menu_loads():
    root = load_menu(4, REPO / "contrib/menu.example.toml")
    assert [i.name for i in root.children] == ["Terminal", "Browser", "Editor", "Windows", "Escape", "Window", "Music"]
    assert root.children[5].children[5].type == "send_to_workspace"


def test_default_menu_fits_one_ring():
    root = load_menu(4, Path("/nonexistent/menu.toml"))
    assert 3 <= len(root.children) <= 12
    assert all(len(c.children) <= 12 for c in root.children)


def test_default_menu_skips_tracks_to_the_right_and_back_to_the_left():
    root = load_menu(4, Path("/nonexistent/menu.toml"))
    assert "Apps" not in [i.name for i in root.children]
    session = PieSession(root, 1000, 1000, PieConfig(), 1.0, (2880, 1800))
    music = next(n for n, i in enumerate(root.children) if i.name == "Music")
    angle = math.radians(session.stack[-1].angles[music])
    session.update(1000 + 200 * math.sin(angle), 1000 - 200 * math.cos(angle))  # a full stroke onto Music enters it
    level = session.stack[-1]
    assert level.menu.name == "Music"
    ways = {item.data: math.sin(math.radians(a)) for item, a in zip(level.menu.children, level.angles)}
    assert ways["next"] > 0.5 and ways["previous"] < -0.5  # how far to the right each lies, of 1


def test_track_items_skip_a_track():
    backend = FakeBackend()
    launcher = Launcher(backend, MenuItem("Root"))
    launcher.activate(MenuItem("Next track", "track", "next"), None)
    launcher.activate(MenuItem("Previous track", "track", "previous"), None)
    assert backend.commands == [("skip_track", 1), ("skip_track", -1)]
    with pytest.raises(ValueError, match="next"):
        item_from_dict({"name": "Skip", "type": "track", "data": "forward"})


def test_the_default_menu_has_the_escape_key_and_a_key_item_presses_its_key():
    backend = FakeBackend()
    launcher = Launcher(backend, load_menu(4, Path("/nonexistent/menu.toml")))
    escape = next(item for item in launcher.build().children if item.name == "Escape")
    launcher.activate(escape, None)
    launcher.activate(item_from_dict({"name": "New tab", "type": "key", "data": "ctrl+t"}), None)
    assert backend.commands == [("press_key", "Escape"), ("press_key", "ctrl+t")]
    with pytest.raises(ValueError, match="a key item's data is the key"):
        item_from_dict({"name": "Nothing", "type": "key"})


def test_window_actions():
    backend = FakeBackend((2000, 1000))
    win = backend.add_window(WindowInfo(7, 100, 100, 500, 400))
    launcher = Launcher(backend, MenuItem("Root"))
    launcher.activate(MenuItem("Tile", "window_action", "tile_right"), win)
    assert (win.x, win.y, win.w, win.h) == (1000, 0, 1000, 1000)
    launcher.activate(MenuItem("Send", "send_to_workspace", 3), win)
    assert win.desktop == 3
    launcher.activate(MenuItem("Max", "window_action", "maximize"), win)
    assert win.maximized
    launcher.activate(MenuItem("Close", "window_action", "close"), None)  # no target: ignored
    assert backend.get(7) is not None


def test_running_windows_expand_to_current_workspace():
    backend = FakeBackend()
    backend.add_window(WindowInfo(1, 0, 0, 10, 10, desktop=0, title="here"))
    backend.add_window(WindowInfo(2, 0, 0, 10, 10, desktop=1, title="elsewhere"))
    launcher = Launcher(backend, MenuItem("Root", children=[MenuItem("Windows", "running_windows")]))
    assert [c.name for c in launcher.build().children[0].children] == ["here"]


def test_frame_sample_round_trips_through_json():
    cfg = Config()
    frame = FrameSample(3, 1.5, 1.52, [make_hand(cfg, (1920, 1080), "pinch_index", 400, 300, "Left")])
    restored = FrameSample.from_dict(json.loads(json.dumps(frame.to_dict())))
    assert restored.seq == 3 and restored.hands[0].handedness == "Left"
    assert restored.hands[0].world == pytest.approx(frame.hands[0].world, abs=1e-4)
