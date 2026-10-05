"""Integration tests for the GNOME backend against a private, headless GNOME Shell running the extension."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

from holotouch.gnome.install import SOURCE, UUID

pytestmark = pytest.mark.skipif(
    not all(shutil.which(tool) for tool in ("gnome-shell", "dbus-daemon", "gsettings")),
    reason="needs gnome-shell, dbus-daemon and gsettings",
)

SCREEN = (1280, 800)
WINDOW = Path(__file__).with_name("wayland_window.py")
# A session bus that can start no services: no portals and no gvfs, so nothing is mounted in the
# directory this is run from, and nothing of the real session's is touched.
BUS_CONFIG = """<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>session</type>
  <keep_umask/>
  <listen>unix:path={socket}</listen>
  <auth>EXTERNAL</auth>
  <policy context="default">
    <allow send_destination="*" eavesdrop="true"/>
    <allow eavesdrop="true"/>
    <allow own="*"/>
  </policy>
</busconfig>
"""


def wait_for(condition, timeout=5.0, step=0.02):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = condition()
        if result:
            return result
        time.sleep(step)
    raise AssertionError("condition not met in time")


class Client:
    """A window of our own, and what it has said was done to it."""

    def __init__(self, env, title, *args):
        self.process = subprocess.Popen(
            [sys.executable, str(WINDOW), title, *args], env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )  # fmt: skip
        self.events: list[dict] = []
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.process.stdout:
            if line.startswith("{"):
                self.events.append(json.loads(line))

    def said(self, event):
        return [e for e in self.events if e["event"] == event]


@pytest.fixture(scope="module")
def session():
    # Sockets go here, and a socket's path has to be short.
    base = Path(tempfile.mkdtemp(prefix="holotouch-test-", dir=os.environ.get("XDG_RUNTIME_DIR") or "/tmp"))
    for name in ("data", "config", "cache", "run"):
        (base / name).mkdir(mode=0o700)
    shutil.copytree(SOURCE, base / "data" / "gnome-shell" / "extensions" / UUID)
    (base / "bus.conf").write_text(BUS_CONFIG.format(socket=base / "bus"))
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "SESSION_MANAGER")
    }
    env.update(
        DBUS_SESSION_BUS_ADDRESS=f"unix:path={base / 'bus'}",
        GSETTINGS_BACKEND="keyfile",  # settings in a file of our own, with no service to keep them
        XDG_DATA_HOME=str(base / "data"),
        XDG_CONFIG_HOME=str(base / "config"),
        XDG_CACHE_HOME=str(base / "cache"),
        XDG_RUNTIME_DIR=str(base / "run"),
        XDG_SESSION_TYPE="wayland",
        XDG_CURRENT_DESKTOP="GNOME",
        WAYLAND_DISPLAY="holotouch-test",
        QT_QPA_PLATFORM="wayland",
    )
    quiet = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    processes = [subprocess.Popen(["dbus-daemon", f"--config-file={base / 'bus.conf'}", "--nofork"], env=env, **quiet)]
    clients = []
    saved = {key: os.environ.get(key) for key in env}
    try:
        wait_for((base / "bus").exists)
        for key, value in (("enabled-extensions", f"['{UUID}']"), ("welcome-dialog-last-shown-version", "'999'")):
            subprocess.run(["gsettings", "set", "org.gnome.shell", key, value], env=env, check=True, **quiet)
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.interface", "enable-animations", "false"], env=env, check=True, **quiet
        )
        processes.append(
            subprocess.Popen(
                ["gnome-shell", "--headless", "--virtual-monitor", f"{SCREEN[0]}x{SCREEN[1]}", "--wayland-display", env["WAYLAND_DISPLAY"]],
                env=env, **quiet,
            )  # fmt: skip
        )
        os.environ.update(env)  # the backend finds the bus, and GNOME, by these
        from holotouch.gnome.backend import GnomeBackend, ShellMissing

        def connect():
            try:
                return GnomeBackend()
            except ShellMissing:
                return None

        try:
            backend = wait_for(connect, timeout=30.0, step=0.25)
        except AssertionError:
            pytest.skip("GNOME Shell did not start here")
        clients += [Client(env, "alpha"), Client(env, "beta", "editable")]

        def poll(condition, timeout=5.0):
            def check():
                backend.poll()
                return condition()

            return wait_for(check, timeout)

        def by_title(title):
            return next((w for w in backend.all_windows() if w.title == title), None)

        poll(lambda: by_title("alpha") and by_title("beta"), timeout=20.0)
        # GNOME Shell starts in its overview, with the pointer in the corner that opens it.
        # Picking a window out closes the overview; the pointer is taken somewhere harmless.
        time.sleep(1.0)
        backend.warp_pointer(SCREEN[0] // 2, SCREEN[1] - 50)
        time.sleep(0.3)
        backend.warp_pointer(SCREEN[0] // 2, SCREEN[1] - 40)
        backend.activate(by_title("alpha").id)
        time.sleep(1.0)
        yield backend, poll, by_title, {client.process.args[2]: client for client in clients}
        backend.close_backend()
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        for process in [client.process for client in clients] + processes[::-1]:
            process.terminate()
        for process in [client.process for client in clients] + processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        shutil.rmtree(base, ignore_errors=True)


def place(session, title, x, y, w, h):
    backend, poll, by_title, _ = session
    backend.move_resize(by_title(title).id, x, y, w, h)
    return poll(lambda: (win := by_title(title)) and (win.x, win.y, win.w, win.h) == (x, y, w, h) and win)


def test_lists_windows_and_the_desktop(session):
    backend, _, by_title, _ = session
    assert backend.screen_size() == SCREEN
    x, y, w, h = backend.workarea()
    assert (x, w) == (0, SCREEN[0]) and y > 0 and y + h == SCREEN[1]  # below the top bar
    assert {w.title for w in backend.windows()} == {"alpha", "beta"}
    assert backend.desktop_count() >= 1 and backend.current_desktop() == 0
    assert by_title("alpha").min_w >= 1


def test_moves_and_resizes_to_the_frame_asked_for(session):
    backend, _, _, _ = session
    win = place(session, "alpha", 100, 120, 500, 360)
    assert backend.window_at(110, 130).id == win.id
    assert backend.window_at(90, 130) is None or backend.window_at(90, 130).id != win.id


def test_activate_raises_and_focuses(session):
    backend, poll, by_title, _ = session
    place(session, "alpha", 100, 120, 500, 360)
    place(session, "beta", 300, 200, 500, 360)
    for title in ("alpha", "beta"):
        backend.activate(by_title(title).id)
        poll(lambda: backend.active_window() and backend.active_window().title == title)
        assert backend.windows()[0].title == title
        assert backend.window_at(350, 250).title == title  # where the two overlap


def test_maximize_stays_maximized_until_the_old_size_is_back(session):
    backend, poll, by_title, _ = session
    placed = place(session, "alpha", 100, 120, 500, 360)
    backend.set_maximized(placed.id, True)
    poll(lambda: by_title("alpha").maximized and by_title("alpha").w == SCREEN[0])
    backend.set_maximized(placed.id, False)
    # Whenever it is seen out of maximize, it has the size it had before.
    win = poll(lambda: not by_title("alpha").maximized and by_title("alpha"))
    assert (win.w, win.h) == (500, 360)


def test_minimize_hides_and_activate_restores(session):
    backend, poll, by_title, _ = session
    alpha = by_title("alpha")
    backend.minimize(alpha.id)
    poll(lambda: by_title("alpha").minimized)
    assert "alpha" not in {w.title for w in backend.windows()}
    assert "alpha" in {w.title for w in backend.all_windows()}
    backend.activate(alpha.id)
    poll(lambda: not by_title("alpha").minimized)


def test_workspaces(session):
    backend, poll, by_title, _ = session
    beta = by_title("beta")
    backend.set_window_desktop(beta.id, 1)
    poll(lambda: by_title("beta").desktop == 1)
    assert {w.title for w in backend.windows()} == {"alpha"}
    backend.switch_desktop(1)
    poll(lambda: backend.current_desktop() == 1 and {w.title for w in backend.windows()} == {"beta"})
    backend.set_window_desktop(beta.id, 0)
    backend.switch_desktop(0)
    poll(lambda: backend.current_desktop() == 0 and len(backend.windows()) == 2)


def test_pointer_clicks_and_scrolls_the_window_under_it(session):
    backend, poll, by_title, clients = session
    alpha = place(session, "alpha", 100, 120, 500, 360)
    backend.activate(alpha.id)
    poll(lambda: backend.active_window() and backend.active_window().id == alpha.id)
    backend.warp_pointer(350, 400)
    poll(lambda: backend.pointer_pos() == (350, 400))
    backend.button_down(360, 410)
    backend.pointer_to(362, 412)
    backend.button_up()
    press = wait_for(lambda: clients["alpha"].said("press"))[-1]
    # Inside the window, to the right of and below its corner by where the pointer was.
    assert 240 <= press["x"] <= 260 and 240 <= press["y"] <= 290
    backend.scroll(0.5)
    backend.scroll(-1.0)
    wheel = wait_for(lambda: len(clients["alpha"].said("wheel")) >= 2 and clients["alpha"].said("wheel"))
    assert [w["angle"] for w in wheel[-2:]] == [60, -120]  # a notch is 120, and up is positive


def test_keys_go_to_the_window_with_the_keyboard(session):
    backend, poll, by_title, clients = session
    alpha = by_title("alpha")
    backend.activate(alpha.id)
    poll(lambda: backend.active_window() and backend.active_window().id == alpha.id)
    time.sleep(0.3)  # the window learns that it has the keyboard a moment after GNOME says so
    backend.press_key("a")
    backend.press_key("ctrl+shift+t")
    backend.press_key("Escape")
    backend.press_key("no such key")
    keys = wait_for(lambda: len(clients["alpha"].said("key")) >= 5 and clients["alpha"].said("key"))
    control, shift = 0x04000000, 0x02000000
    assert (keys[0]["key"], keys[0]["modifiers"]) == (ord("A"), 0)
    assert (keys[3]["key"], keys[3]["modifiers"]) == (ord("T"), control | shift)
    assert keys[4]["key"] == 0x01000000  # Qt's Escape


def test_text_is_typed_whatever_the_keyboard_layout_has(session):
    backend, poll, by_title, clients = session
    beta = by_title("beta")
    backend.activate(beta.id)
    poll(lambda: backend.active_window() and backend.active_window().id == beta.id)
    time.sleep(0.5)
    backend.type_text("Hello, wörld — 123 ")
    wait_for(lambda: any(e["text"] == "Hello, wörld — 123 " for e in clients["beta"].said("text")))


def test_clipboard_is_read_and_tells_a_new_copy(session):
    backend, _, _, _ = session
    backend.set_clipboard("https://example.com/one")
    text, stamp = wait_for(lambda: (read := backend.clipboard())[0] == "https://example.com/one" and read)
    backend.set_clipboard("https://example.com/one")  # the same again is still a new copy
    wait_for(lambda: backend.clipboard() == (text, str(int(stamp) + 1)))


def test_thumbnails_fit_the_size_asked_for(session):
    backend, _, by_title, _ = session
    alpha = place(session, "alpha", 100, 120, 500, 360)
    thumbs = backend.window_thumbnails([alpha.id, 999], 250, 250)
    assert set(thumbs) == {alpha.id}
    picture = thumbs[alpha.id]
    assert (picture.w, picture.h) == (250, 180) and len(picture.data) == 250 * 180 * 4


def test_close_asks_the_window_to_go(session):
    backend, poll, by_title, _ = session
    backend.close(by_title("beta").id)
    poll(lambda: by_title("beta") is None)
    assert [w.title for w in backend.all_windows()] == ["alpha"]
