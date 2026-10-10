"""The GNOME backend against a stand-in for GNOME Shell: what it makes of the state, and what it asks for."""

import json

import pytest

from holotouch import session
from holotouch.core.actions import ALL_DESKTOPS
from holotouch.gnome import backend as gnome
from holotouch.gnome import install
from holotouch.gnome.backend import GnomeBackend, ShellMissing
from holotouch.launcher.launch import _preferred_apps, icon_name


def window(id, x, y, w, h, **more):
    return {
        "id": id, "x": x, "y": y, "w": w, "h": h, "workspace": 0, "title": f"window {id}", "class": "org.gnome.Nautilus",
        "maximized": False, "fullscreen": False, "minimized": False, "skip": False, "min": [100, 50], "icon": "folder",
        **more,
    }  # fmt: skip


def state(*windows, **more):
    return {
        "version": gnome.VERSION, "size": [2160, 1350], "workarea": [0, 32, 2160, 1318], "workspace": 0,
        "workspaces": 3, "active": windows[-1]["id"] if windows else 0, "windows": list(windows), **more,
    }  # fmt: skip


class Shell:
    """Answers Watch with its state, and keeps every call made."""

    def __init__(self, state):
        self.state = state
        self.calls: list[tuple] = []
        self.signals: list[tuple[str, tuple]] = []
        self.answers = {}

    def ask(self, member, signature="", *args, timeout=1.0):
        self.calls.append((member, *args))
        if member == "Watch":
            return (json.dumps(self.state),) if self.state is not None else None
        return self.answers.get(member)

    def ask_later(self, member, then, signature="", *args):
        self.calls.append((member, *args))

    def send(self, member, signature="", *args):
        self.calls.append((member, *args))

    def poll(self):
        signals, self.signals = self.signals, []
        return signals

    def changed(self, state):
        self.state = state
        self.signals.append(("StateChanged", (json.dumps(state),)))

    def close(self):
        pass


# Under the desktop: GNOME counts 2160 x 1350 on a monitor scaled to 133%, and XWayland shows
# the overlay twice that size.
OVERLAY = (4320, 2700)


def make(*windows, **more):
    shell = Shell(state(*windows, **more))
    backend = GnomeBackend(screen=OVERLAY, link=shell)
    shell.calls.clear()
    return backend, shell


def test_windows_are_given_in_the_overlays_pixels_topmost_first():
    backend, _ = make(window(1, 100, 100, 600, 400), window(2, 300, 200, 500, 300))
    assert backend.screen_size() == OVERLAY and backend.workarea() == (0, 64, 4320, 2636)
    top, under = backend.windows()
    assert (top.id, top.x, top.y, top.w, top.h) == (2, 600, 400, 1000, 600)
    assert (under.id, under.min_w, under.min_h) == (1, 200, 100)
    assert backend.window_at(700, 500).id == 2 and backend.window_at(250, 250).id == 1
    assert backend.window_at(4000, 2600) is None
    assert backend.active_window().id == 2 and backend.desktop_count() == 3


def test_requests_go_out_in_gnomes_own_units():
    backend, shell = make(window(1, 100, 100, 600, 400))
    backend.move_resize(1, 801, 400, 1200, 900)
    backend.move_resize(99, 0, 0, 10, 10)  # no such window
    backend.warp_pointer(999, 501)
    backend.button_down(1000, 500)
    backend.button_down(1200, 500)  # down already
    backend.button_up()
    backend.button_up()
    assert shell.calls == [
        ("MoveResize", 1, 400, 200, 600, 450),
        ("WarpPointer", 499.5, 250.5),
        ("WarpPointer", 500.0, 250.0),
        ("Button", True),
        ("Button", False),
    ]


def test_a_state_sent_by_the_shell_replaces_the_last():
    backend, shell = make(window(1, 100, 100, 600, 400))
    shell.changed(state(window(1, 150, 100, 600, 400), window(2, 0, 0, 10, 10), workspace=1))
    backend.poll()
    assert backend.get(1).x == 300 and backend.get(2) is not None and backend.current_desktop() == 1
    shell.signals.append(("StateChanged", ("not json",)))
    backend.poll()  # what cannot be read is left out, and the last state stands
    assert backend.get(1).x == 300


def test_only_windows_on_this_workspace_and_in_view_can_be_pointed_at():
    backend, _ = make(
        window(1, 0, 0, 100, 100, workspace=1),
        window(2, 0, 0, 100, 100, minimized=True),
        window(3, 0, 0, 100, 100, workspace=-1),
        window(4, 0, 0, 100, 100, skip=True),
        active=2,
    )
    assert [w.id for w in backend.windows()] == [4, 3]
    assert backend.get(3).desktop == ALL_DESKTOPS
    assert [w.id for w in backend.all_windows()] == [3, 2, 1]  # the switcher's: not what keeps off the taskbar
    assert backend.active_window() is None  # the keyboard is with a window that is minimized


def test_a_window_let_out_of_maximize_counts_as_maximized_until_it_has_its_size_back(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(gnome.time, "monotonic", lambda: clock[0])
    full = window(1, 0, 32, 2160, 1318, maximized=True)
    backend, shell = make(full)
    backend.set_maximized(1, False)
    assert shell.calls == [("SetMaximized", 1, False)]
    # GNOME says at once that it is out, with the size of the screen still.
    shell.changed(state({**full, "maximized": False}))
    backend.poll()
    assert backend.get(1).maximized
    shell.changed(state(window(1, 200, 200, 800, 600)))
    backend.poll()
    assert not backend.get(1).maximized and backend.get(1).w == 1600
    # One whose own size is the screen's is not waited on for ever.
    backend, shell = make(full)
    backend.set_maximized(1, False)
    clock[0] += 1.0
    shell.changed(state({**full, "maximized": False}))
    backend.poll()
    assert not backend.get(1).maximized


def test_keys_are_sent_as_keysyms_held_in_order():
    backend, shell = make()
    backend.press_key("ctrl+shift+Tab")
    backend.press_key("a")
    backend.press_key("+")
    backend.press_key("ctrl+nonsense")
    backend.type_text("hello")
    assert shell.calls == [("Keys", [0xFFE3, 0xFFE1, 0xFF09]), ("Keys", [ord("a")]), ("Keys", [ord("+")]), ("TypeText", "hello")]


def test_scrolling_and_the_pointers_place():
    backend, shell = make()
    backend.scroll(0.25)
    backend.scroll(0.0)
    assert shell.calls == [("Scroll", 0.25)]
    shell.answers["Pointer"] = (400, 300)
    assert backend.pointer_pos() == (800, 600)
    del shell.answers["Pointer"]  # GNOME Shell does not answer: where it was last known to be
    assert backend.pointer_pos() == (800, 600)


def test_the_clipboard_is_none_when_it_holds_no_text():
    backend, shell = make()
    assert backend.clipboard() == (None, None)  # no answer
    shell.answers["GetClipboard"] = (False, "", 4)
    assert backend.clipboard() == (None, "4")
    shell.answers["GetClipboard"] = (True, "copied", 5)
    assert backend.clipboard() == ("copied", "5")


def test_the_shell_is_asked_again_every_so_often(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(gnome.time, "monotonic", lambda: clock[0])
    backend, shell = make()
    backend.poll()
    assert shell.calls == []
    clock[0] += 3.0
    backend.poll()
    assert shell.calls == [("Watch",)]  # which also has an extension that was turned off and on watch again


def test_an_extension_that_does_not_answer_or_is_another_version_is_said_so():
    with pytest.raises(ShellMissing, match="holotouch gnome"):
        GnomeBackend(link=Shell(None))
    with pytest.raises(ShellMissing, match="version 0"):
        GnomeBackend(link=Shell(state(version=0)))
    assert issubclass(ShellMissing, ValueError)  # which the command line reports in a line


def test_without_a_screen_given_gnomes_units_are_the_pixels():
    backend = GnomeBackend(link=Shell(state(window(1, 100, 100, 600, 400))))
    assert backend.screen_size() == (2160, 1350) and backend.get(1).w == 600


def test_the_session_is_told_from_the_environment(monkeypatch):
    for kind, desktop, gnome_on_wayland in (
        ("wayland", "GNOME", True),
        ("wayland", "ubuntu:GNOME", True),
        ("x11", "GNOME", False),
        ("x11", "XFCE", False),
        ("wayland", "KDE", False),
    ):
        monkeypatch.setenv("XDG_SESSION_TYPE", kind)
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", desktop)
        assert session.gnome_wayland() is gnome_on_wayland
    assert session.pixel_ratio() == 1.0  # anywhere but GNOME on Wayland, a pixel is a pixel


def test_sizes_grow_by_what_xwayland_scales_down(monkeypatch):
    from holotouch.config import Config

    monkeypatch.setattr(session, "gnome_wayland", lambda: True)
    monkeypatch.setattr(session, "_stage_and_scale", lambda: (2160, 4 / 3))
    monkeypatch.setattr(session, "x_screen_size", lambda: (4320, 2700))
    cfg = Config()
    session.adapt(cfg)
    assert cfg.ui.scale == pytest.approx(Config().ui.scale * 1.5)
    monkeypatch.setattr(session, "x_screen_size", lambda: None)  # no XWayland: nothing to go by
    assert session.pixel_ratio() == 1.0


def test_the_extension_is_installed_and_turned_on(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    settings = {install._ENABLED: "['other@example.org']", install._DISABLED: f"['{install.UUID}']"}

    def run(*command):
        if command[:2] == ("gsettings", "get"):
            return True, settings.get(command[2:], "false")
        if command[:2] == ("gsettings", "set"):
            settings[command[2:4]] = command[4]
            return True, ""
        return False, ""

    monkeypatch.setattr(install, "_run", run)
    monkeypatch.setattr(install, "running_version", lambda: None)
    said = []
    assert install.install(said.append) is False  # GNOME Shell has yet to start with it
    assert "log out and back in" in said[-1]
    assert (tmp_path / "gnome-shell" / "extensions" / install.UUID / "extension.js").exists()
    assert install.installed_version() == gnome.VERSION and install.enabled()
    assert settings[install._ENABLED] == f"['other@example.org', '{install.UUID}']"
    assert settings[install._DISABLED] == "[]"
    monkeypatch.setattr(install, "running_version", lambda: gnome.VERSION)
    assert install.install(said.append) is True
    install.uninstall(said.append)
    assert install.installed_version() is None and settings[install._ENABLED] == "['other@example.org']"


def test_a_gnome_shell_newer_than_the_extension_names_is_told_apart(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    version = {"said": "GNOME Shell 51.0"}

    def run(*command):
        if command[0] == "gnome-shell":
            return True, version["said"]
        return (True, "@as []") if command[:2] == ("gsettings", "get") else (True, "")

    monkeypatch.setattr(install, "_run", run)
    monkeypatch.setattr(install, "running_version", lambda: None)
    assert install.shell_version() == 51 and install.too_new() is None
    said = []
    install.install(said.append)
    assert "log out and back in" in said[-1]
    version["said"] = f"GNOME Shell {max(install.made_for()) + 1}.0"
    assert install.too_new() == max(install.made_for()) + 1
    install.install(said.append)
    assert "newer" in said[-1] and "log out" not in said[-1]
    version["said"] = ""
    assert install.shell_version() is None and install.too_new() is None


def test_the_extensions_version_is_the_backends():
    source = (install.SOURCE / "extension.js").read_text()
    metadata = json.loads((install.SOURCE / "metadata.json").read_text())
    assert f"const VERSION = {gnome.VERSION};" in source
    assert metadata["uuid"] == install.UUID and metadata["version"] == gnome.VERSION


def test_an_icon_is_named_after_the_window_class():
    assert icon_name("Thunar") == "thunar"
    assert icon_name("org.gnome.Nautilus") == "org.gnome.Nautilus"


def test_the_menu_opens_what_the_desktop_prefers(monkeypatch):
    from holotouch.launcher import launch

    monkeypatch.setattr(launch.shutil, "which", lambda name: f"/usr/bin/{name}" if name in ("exo-open", "kgx", "xterm") else None)
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "XFCE")
    assert _preferred_apps()[0] == "exo-open --launch TerminalEmulator"
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    terminal, browser, files = _preferred_apps()
    assert terminal == "kgx" and "default-web-browser" in browser and files.startswith("xdg-open")
