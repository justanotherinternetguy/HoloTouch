import json
import math
from pathlib import Path

import pytest

from holotouch.config import Config, PieConfig, load_config
from holotouch.core.actions import WindowInfo
from holotouch.launcher.launch import Launcher, load_menu
from holotouch.launcher.menu import MenuItem, PieSession, item_from_dict
from holotouch.tracker.types import FrameSample
from holotouch.x11.fake import FakeBackend
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
    assert [i.name for i in root.children] == ["Terminal", "Browser", "Editor", "Windows", "This app", "Window", "Music"]
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
    # Pausing lies between them, straight on down from where Music was.
    assert [item.name for item in level.menu.children] == ["Next track", "Play / pause", "Previous track"]
    assert level.angles == pytest.approx([90, 180, 270])


def test_track_items_skip_a_track():
    backend = FakeBackend()
    launcher = Launcher(backend, MenuItem("Root"))
    launcher.activate(MenuItem("Next track", "track", "next"), None)
    launcher.activate(MenuItem("Previous track", "track", "previous"), None)
    launcher.activate(item_from_dict({"name": "Pause", "type": "track", "data": "play_pause"}), None)
    assert backend.commands == [("skip_track", 1), ("skip_track", -1), ("play_pause",)]
    with pytest.raises(ValueError, match="next"):
        item_from_dict({"name": "Skip", "type": "track", "data": "forward"})


def test_a_key_item_presses_its_key():
    backend = FakeBackend()
    launcher = Launcher(backend, MenuItem("Root"))
    launcher.activate(item_from_dict({"name": "New tab", "type": "key", "data": "ctrl+t"}), None)
    assert backend.commands == [("press_key", "ctrl+t")]
    with pytest.raises(ValueError, match="a key item's data is the key"):
        item_from_dict({"name": "Nothing", "type": "key"})


def app_menu(wm_class, root=None, **given):
    """The menu's item for the app in use, as it is with a window of this class having the keyboard: none, if None."""
    backend = FakeBackend()
    if wm_class is not None:
        backend.add_window(WindowInfo(1, 0, 0, 800, 600, title="in use", wm_class=wm_class))
        backend.activate(1)
    built = Launcher(backend, root or load_menu(4, Path("/nonexistent/menu.toml")), **given).build()
    return next(item for item in built.children if item.type == "app_actions")


def keys(menu):
    return {item.name: item.data for item in menu.children}


def test_the_default_menu_has_no_escape_key_but_the_keys_of_the_app_in_use():
    root = load_menu(4, Path("/nonexistent/menu.toml"))
    assert "Escape" not in [item.name for item in root.children] and len(root.children) == 8
    page = app_menu("Google-chrome")
    assert page.name == "This page" and page.is_menu
    assert keys(page) == {
        "Send to phone": None, "Close tab": "ctrl+w", "Go forward": "alt+Right", "Next tab": "ctrl+Tab",
        "Reload": "F5", "Escape": "Escape", "Previous tab": "ctrl+shift+Tab", "Go back": "alt+Left",
    }  # fmt: skip


@pytest.mark.parametrize(
    "wm_class, name, has",
    [
        ("firefox", "This page", {"Go back": "alt+Left"}),
        ("Xfce4-terminal", "This terminal", {"Copy": "ctrl+shift+c", "Interrupt": "ctrl+c"}),
        ("com.mitchellh.ghostty", "This terminal", {"Paste": "ctrl+shift+v"}),
        ("Thunar", "This folder", {"Parent folder": "alt+Up", "Go back": "alt+Left"}),
        ("org.gnome.Nautilus", "This folder", {"Open": "Return"}),
        ("mpv", "This video", {"Play / pause": "space", "Forward": "Right"}),
        ("vlc", "This video", {"Play / pause": "space", "Forward": "alt+Right"}),
        ("Evince", "This document", {"Next page": "n", "Previous page": "p"}),
        ("Mousepad", "This app", {"Copy": "ctrl+c", "Undo": "ctrl+z", "Escape": "Escape"}),
        ("", "This app", {"Paste": "ctrl+v"}),
        (None, "This app", {"Escape": "Escape"}),  # the desktop has the keyboard
    ],
)
def test_the_menu_offers_the_keys_of_the_kind_of_app_in_use(wm_class, name, has):
    menu = app_menu(wm_class)
    assert menu.name == name
    assert has.items() <= keys(menu).items()


def entered(wm_class):
    """The items for the app in use and the way each lies, once its item in the built-in menu has been entered."""
    backend = FakeBackend()
    backend.add_window(WindowInfo(1, 0, 0, 800, 600, wm_class=wm_class))
    backend.activate(1)
    root = Launcher(backend, load_menu(4, Path("/nonexistent/menu.toml"))).build()
    at = next(n for n, item in enumerate(root.children) if item.type == "app_actions")
    session = PieSession(root, 1000, 1000, PieConfig(), 1.0, (2880, 1800))
    angle = math.radians(session.stack[-1].angles[at])
    session.update(1000 + 200 * math.sin(angle), 1000 - 200 * math.cos(angle))
    level = session.stack[-1]
    return {item.name: way for item, way in zip(level.menu.children, level.angles)}


@pytest.mark.parametrize("wm_class", ["Xfce4-terminal", "Thunar", "mpv", "vlc", "Evince", "Mousepad"])
def test_the_seven_items_of_a_kind_of_app_lie_on_the_compass(wm_class):
    assert list(entered(wm_class).values()) == pytest.approx([0, 45, 90, 135, 180, 225, 270])


def test_a_web_browser_has_escape_too_and_going_forward_and_back_still_lie_right_and_left():
    ways = entered("firefox")
    assert list(ways) == ["Send to phone", "Close tab", "Go forward", "Next tab", "Reload", "Escape", "Previous tab", "Go back"]
    across = {name: math.sin(math.radians(way)) for name, way in ways.items()}  # how far to the right each lies, of 1
    assert across["Go forward"] > 0.9 and across["Go back"] < -0.9
    assert across["Next tab"] > 0.8 and across["Previous tab"] < -0.8
    assert math.cos(math.radians(ways["Send to phone"])) > 0.99  # straight up, as the toss is
    assert math.cos(math.radians(ways["Escape"])) < -0.9  # and Escape at the bottom
    # The folders' two lie across from each other exactly.
    folder = entered("Thunar")
    assert (folder["Go forward"], folder["Go back"]) == (90, 270)


def test_the_browsers_of_the_configuration_are_the_ones_given_a_page(tmp_path):
    assert app_menu("Nyxt").name == "This app"
    assert app_menu("Nyxt", browsers="nyxt, chrome").name == "This page"
    # A menu of one's own may hold the item too, wherever it likes, and its name gives way.
    path = tmp_path / "menu.toml"
    path.write_text('[[item]]\nname = "Keys"\ntype = "app_actions"\n\n[[item]]\nname = "To phone"\ntype = "phone"\n')
    root = load_menu(4, path)
    assert [item.type for item in root.children] == ["app_actions", "phone"]
    assert app_menu("Thunar", root).name == "This folder"


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
