"""Integration tests for the X11 backend against a private Xvfb display running xfwm4."""

import os
import shutil
import struct
import subprocess
import time

import pytest

pytestmark = pytest.mark.skipif(
    not all(shutil.which(tool) for tool in ("Xvfb", "xfwm4", "xmessage", "dbus-run-session")),
    reason="needs Xvfb, xfwm4, xmessage and dbus-run-session",
)

SCREEN = (1280, 800)


def wait_for(condition, timeout=5.0, step=0.02):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = condition()
        if result:
            return result
        time.sleep(step)
    raise AssertionError("condition not met in time")


@pytest.fixture(scope="module")
def display(tmp_path_factory):
    read_fd, write_fd = os.pipe()
    xvfb = subprocess.Popen(
        ["Xvfb", "-displayfd", str(write_fd), "-screen", "0", f"{SCREEN[0]}x{SCREEN[1]}x24", "-nolisten", "tcp"],
        pass_fds=[write_fd],
        stderr=subprocess.DEVNULL,
    )
    os.close(write_fd)
    name = ":" + os.read(read_fd, 16).decode().strip()
    os.close(read_fd)
    # A private config dir and session bus keep this xfwm4 away from the real desktop's settings.
    env = dict(os.environ, DISPLAY=name, XDG_CONFIG_HOME=str(tmp_path_factory.mktemp("xdg")))
    env.pop("SESSION_MANAGER", None)
    wm = subprocess.Popen(
        ["dbus-run-session", "--", "xfwm4", "--compositor=on", "--sm-client-disable"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    clients = []

    def spawn(title, geometry):
        clients.append(
            subprocess.Popen(
                ["xmessage", "-name", title, "-title", title, "-geometry", geometry, "hello from " + title],
                env=env,
                stderr=subprocess.DEVNULL,
            )
        )

    try:
        yield name, spawn
    finally:
        for proc in [*clients, wm, xvfb]:
            proc.terminate()
        for proc in [*clients, wm, xvfb]:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


@pytest.fixture(scope="module")
def backend(display):
    from holowm.x11.backend import X11Backend

    name, spawn = display
    backend = None

    def connect():
        nonlocal backend
        try:
            backend = X11Backend(scroll_backend="xtest", display=name)
        except Exception:
            return False
        return True

    wait_for(connect)

    def wm_ready():
        backend._root_dirty = True
        return backend.desktop_count() >= 2

    wait_for(wm_ready, timeout=10)
    spawn("alpha", "300x200+100+100")
    spawn("beta", "300x200+250+180")

    def both():
        backend.poll()
        backend._stack_dirty = True
        return len(backend.windows()) == 2

    wait_for(both, timeout=10)
    yield backend
    backend.close_backend()


def by_title(backend, title):
    backend.poll()
    return next((w for w in backend.windows() if w.title == title), None)


def settle(backend, condition, timeout=5.0):
    def check():
        backend.flush()
        backend.poll()
        return condition()

    return wait_for(check, timeout)


def test_reports_screen_and_workspaces(backend):
    assert backend.screen_size() == SCREEN
    assert backend.desktop_count() == 4
    assert backend.current_desktop() == 0


def test_lists_decorated_windows_with_frame_geometry(backend):
    alpha = by_title(backend, "alpha")
    assert alpha is not None and alpha.wm_class
    client = backend._clients[alpha.id]
    assert client.frame[2] > 0  # has a title bar
    assert alpha.w == 300 + client.frame[0] + client.frame[1]
    assert alpha.h == 200 + client.frame[2] + client.frame[3]


def test_move_resize_lands_exactly_where_asked(backend):
    alpha = by_title(backend, "alpha")
    backend.move_resize(alpha.id, 420, 310, 500, 333)
    settle(backend, lambda: (lambda w: (w.x, w.y, w.w, w.h) == (420, 310, 500, 333))(backend.get(alpha.id)))
    backend.move_resize(alpha.id, 100, 100, 320, 240)
    settle(backend, lambda: (lambda w: (w.x, w.y, w.w, w.h) == (100, 100, 320, 240))(backend.get(alpha.id)))


def test_rapid_moves_all_apply(backend):
    alpha = by_title(backend, "alpha")
    for i in range(120):
        backend.move_resize(alpha.id, 100 + i * 3, 100 + i, alpha.w, alpha.h)
        backend.flush()
        backend.poll()
    settle(backend, lambda: (backend.get(alpha.id).x, backend.get(alpha.id).y) == (457, 219))
    backend.move_resize(alpha.id, 100, 100, alpha.w, alpha.h)
    settle(backend, lambda: backend.get(alpha.id).x == 100)


def test_hit_test_follows_stacking_and_activation(backend):
    alpha, beta = by_title(backend, "alpha"), by_title(backend, "beta")
    backend.move_resize(alpha.id, 100, 100, 320, 240)
    backend.move_resize(beta.id, 250, 180, 320, 240)
    settle(backend, lambda: backend.get(beta.id).x == 250 and backend.get(alpha.id).x == 100)
    overlap = (300, 250)
    backend.activate(beta.id)
    settle(backend, lambda: backend.window_at(*overlap).id == beta.id)
    backend.activate(alpha.id)
    settle(backend, lambda: backend.window_at(*overlap).id == alpha.id)
    assert backend.active_window().id == alpha.id
    assert backend.window_at(110, 110).id == alpha.id
    assert backend.window_at(560, 410).id == beta.id
    assert backend.window_at(1200, 700) is None


def test_maximize_and_restore(backend):
    alpha = by_title(backend, "alpha")
    before = (alpha.x, alpha.y, alpha.w, alpha.h)
    backend.set_maximized(alpha.id, True)
    settle(backend, lambda: backend.get(alpha.id).maximized)
    assert backend.get(alpha.id).w >= SCREEN[0] - 2
    backend.set_maximized(alpha.id, False)
    settle(backend, lambda: not backend.get(alpha.id).maximized)
    settle(backend, lambda: (lambda w: (w.x, w.y, w.w, w.h) == before)(backend.get(alpha.id)))


def test_workspace_switch_and_window_transfer(backend):
    beta = by_title(backend, "beta")
    backend.set_window_desktop(beta.id, 2)
    settle(backend, lambda: backend.get(beta.id).desktop == 2)
    assert by_title(backend, "beta") is None  # no longer on this workspace
    assert backend.get(beta.id) is not None
    backend.switch_desktop(2)
    settle(backend, lambda: backend.current_desktop() == 2 and by_title(backend, "beta") is not None)
    assert by_title(backend, "alpha") is None
    backend.set_window_desktop(beta.id, 0)
    backend.switch_desktop(0)
    settle(backend, lambda: backend.current_desktop() == 0 and by_title(backend, "beta") is not None)


def test_minimized_window_is_not_a_target(backend):
    beta = by_title(backend, "beta")
    backend.minimize(beta.id)
    settle(backend, lambda: by_title(backend, "beta") is None)
    backend.activate(beta.id)
    settle(backend, lambda: by_title(backend, "beta") is not None)


def test_all_windows_includes_minimized_and_other_workspaces(backend):
    alpha, beta = by_title(backend, "alpha"), by_title(backend, "beta")

    def listed():
        return {w.title: w for w in backend.all_windows()}

    assert set(listed()) == {"alpha", "beta"}  # no panels, no desktop, not our own helper window
    backend.minimize(beta.id)
    settle(backend, lambda: listed()["beta"].minimized)
    assert by_title(backend, "beta") is None
    backend.activate(beta.id)
    settle(backend, lambda: not listed()["beta"].minimized)
    backend.set_window_desktop(alpha.id, 3)
    settle(backend, lambda: listed()["alpha"].desktop == 3)
    assert by_title(backend, "alpha") is None and not listed()["alpha"].minimized
    backend.set_window_desktop(alpha.id, 0)
    settle(backend, lambda: by_title(backend, "alpha") is not None)


def test_window_icon_is_read_from_the_window(backend):
    import xcffib.xproto as xp

    alpha = by_title(backend, "alpha")
    assert backend.window_icon(alpha.id, 48) is None  # xmessage sets no icon
    small = [2, 2, 0xFF112233, 0xFF112233, 0xFF112233, 0xFF112233]
    large = [64, 64, *([0x80445566] * 64 * 64)]
    data = small + large
    x = backend.x
    x.core.ChangeProperty(
        xp.PropMode.Replace, alpha.id, x.atom("_NET_WM_ICON"), xp.Atom.CARDINAL, 32, len(data),
        struct.pack(f"{len(data)}I", *data),
    )
    # The cached "no icon" answer is dropped when the property changes.
    icon = settle(backend, lambda: backend.window_icon(alpha.id, 48))
    assert (icon.w, icon.h) == (64, 64)
    assert icon.data[:4] == bytes([0x66, 0x55, 0x44, 0x80]) and len(icon.data) == 64 * 64 * 4
    assert backend.window_icon(alpha.id, 2).w == 2


def test_thumbnails_show_window_contents_even_when_covered(backend, display):
    import numpy as np

    proc = subprocess.Popen(
        ["xmessage", "-title", "blue", "-bg", "#2255aa", "-geometry", "400x300+500+300", "blue"],
        env=dict(os.environ, DISPLAY=display[0]), stderr=subprocess.DEVNULL,
    )
    try:
        blue = settle(backend, lambda: by_title(backend, "blue"))
        alpha = by_title(backend, "alpha")
        # Put alpha right on top of it; the picture still shows the blue window itself.
        backend.move_resize(alpha.id, blue.x, blue.y, blue.w, blue.h)
        backend.activate(alpha.id)
        settle(backend, lambda: backend.window_at(blue.x + 50, blue.y + 100).id == alpha.id)

        def capture():
            return backend.window_thumbnails([blue.id, alpha.id, 0x12345], 100, 100).get(blue.id)

        def mostly_blue():
            shot = capture()
            if shot is None:
                return None
            pixels = np.frombuffer(shot.data, np.uint8).reshape(shot.h, shot.w, 4)
            b, g, r, a = (float(pixels[:, :, i].mean()) for i in range(4))
            return shot if (a == 255 and abs(b - 0xAA) < 25 and abs(g - 0x55) < 25 and abs(r - 0x22) < 25) else None

        shot = settle(backend, mostly_blue)
        # Scaled to fit 100x100 with the window's proportions (400x300 client area).
        assert (shot.w, shot.h) == (100, 75)
        backend.minimize(blue.id)
        settle(backend, lambda: by_title(backend, "blue") is None)
        assert capture() is None  # nothing to capture while it is unmapped
    finally:
        proc.terminate()
        proc.wait(timeout=5)
        settle(backend, lambda: all(w.title != "blue" for w in backend.all_windows()))
        backend.move_resize(alpha.id, 100, 100, 320, 240)
        settle(backend, lambda: backend.get(alpha.id).x == 100)


def test_desktop_window_is_never_a_target(backend, display):
    """xfwm4 minimizes even the desktop if asked, which leaves nothing to repaint bare desktop."""
    import xcffib
    import xcffib.xproto as xp

    conn = xcffib.connect(display[0])
    screen = conn.get_setup().roots[0]

    def atom(name):
        return conn.core.InternAtom(False, len(name), name).reply().atom

    desk = conn.generate_id()
    conn.core.CreateWindow(
        screen.root_depth, desk, screen.root, 0, 0, SCREEN[0], SCREEN[1], 0, xp.WindowClass.InputOutput,
        screen.root_visual, xp.CW.BackPixel, [0x224466],
    )
    conn.core.ChangeProperty(
        xp.PropMode.Replace, desk, atom("_NET_WM_WINDOW_TYPE"), xp.Atom.ATOM, 32, 1,
        struct.pack("I", atom("_NET_WM_WINDOW_TYPE_DESKTOP")),
    )
    conn.core.MapWindow(desk)
    conn.flush()
    try:
        settle(backend, lambda: backend.get(desk) is not None)
        assert all(w.id != desk for w in backend.windows() + backend.all_windows())
        assert backend.window_at(SCREEN[0] - 5, SCREEN[1] - 5) is None
        # On an empty workspace xfwm4 gives the desktop the focus; that is not a window to act on.
        backend.switch_desktop(3)
        settle(backend, lambda: backend.current_desktop() == 3 and backend._active == desk)
        assert backend.active_window() is None
        backend.minimize(desk)
        backend.set_maximized(desk, True)
        backend.set_window_desktop(desk, 2)
        backend.move_resize(desk, 50, 50, 300, 200)
        backend.close(desk)
        backend.flush()
        time.sleep(0.5)
        backend.poll()
        assert conn.core.GetWindowAttributes(desk).reply().map_state == xp.MapState.Viewable
        info = backend.get(desk)
        assert (info.w, info.h) == SCREEN and not info.minimized and info.desktop in (0, -1)
    finally:
        conn.core.DestroyWindow(desk)
        conn.flush()
        conn.disconnect()
        backend.switch_desktop(0)
        settle(backend, lambda: backend.get(desk) is None and backend.current_desktop() == 0)
        alpha = settle(backend, lambda: by_title(backend, "alpha"))
        backend.activate(alpha.id)
        settle(backend, lambda: backend.active_window() is not None and backend.active_window().id == alpha.id)


def test_pointer_warp_and_xtest_scroll(backend, display):
    import xcffib
    import xcffib.xproto as xp

    # A window of our own under the pointer, on a second connection, to observe wheel clicks.
    conn = xcffib.connect(display[0])
    screen = conn.get_setup().roots[0]
    probe = conn.generate_id()
    conn.core.CreateWindow(
        screen.root_depth, probe, screen.root, 1100, 600, 100, 100, 0, xp.WindowClass.InputOutput,
        screen.root_visual, xp.CW.OverrideRedirect | xp.CW.EventMask, [1, xp.EventMask.ButtonPress],
    )
    conn.core.MapWindow(probe)
    conn.flush()
    backend.warp_pointer(1150, 650)
    settle(backend, lambda: backend.pointer_pos() == (1150, 650))
    backend.scroll(-0.6)
    backend.scroll(-1.6)  # 2.2 notches down in total -> two wheel-down clicks, 0.2 carried over
    backend.scroll(3.0)  # net 2.8 up -> two wheel-up clicks
    backend.flush()
    seen = []

    def collect():
        while (event := conn.poll_for_event()) is not None:
            if isinstance(event, xp.ButtonPressEvent):
                seen.append(event.detail)
        return len(seen) >= 4

    wait_for(collect)
    conn.disconnect()
    assert seen == [5, 5, 4, 4]


def test_mouse_button_goes_down_where_asked_and_comes_up_where_it_was_taken(backend, display):
    import xcffib
    import xcffib.xproto as xp

    # A window of our own to be clicked, on a second connection.
    conn = xcffib.connect(display[0])
    screen = conn.get_setup().roots[0]
    probe = conn.generate_id()
    conn.core.CreateWindow(
        screen.root_depth, probe, screen.root, 1000, 400, 100, 100, 0, xp.WindowClass.InputOutput,
        screen.root_visual, xp.CW.OverrideRedirect | xp.CW.EventMask,
        [1, xp.EventMask.ButtonPress | xp.EventMask.ButtonRelease],
    )
    conn.core.MapWindow(probe)
    conn.flush()
    backend.warp_pointer(200, 700)
    settle(backend, lambda: backend.pointer_pos() == (200, 700))
    seen = []

    def collect(count):
        while (event := conn.poll_for_event()) is not None:
            if isinstance(event, (xp.ButtonPressEvent, xp.ButtonReleaseEvent)):
                seen.append((type(event).__name__, event.detail, event.root_x, event.root_y))
        return len(seen) >= count

    backend.button_down(1040, 460)
    backend.flush()
    wait_for(lambda: collect(1))
    # The button is still down, and the pointer where it went down, until it is let go.
    assert seen == [("ButtonPressEvent", 1, 1040, 460)] and backend.pointer_pos() == (1040, 460)
    backend.pointer_to(1070, 480)
    backend.button_up()
    backend.flush()
    wait_for(lambda: collect(2))
    conn.core.DestroyWindow(probe)
    conn.disconnect()
    assert seen[1] == ("ButtonReleaseEvent", 1, 1070, 480)
    assert backend.pointer_pos() == (1070, 480)  # the pointer stays where it was let go
    backend.button_up()  # with no button down, this does nothing
    backend.flush()
    assert len(seen) == 2


def test_xtest_key_press_reaches_the_window_with_the_keyboard(backend, display):
    import xcffib
    import xcffib.xproto as xp

    # A window of our own holding the keyboard, on a second connection, to observe key presses.
    conn = xcffib.connect(display[0])
    setup = conn.get_setup()
    screen = setup.roots[0]
    probe = conn.generate_id()
    conn.core.CreateWindow(
        screen.root_depth, probe, screen.root, 1100, 100, 100, 100, 0, xp.WindowClass.InputOutput,
        screen.root_visual, xp.CW.OverrideRedirect | xp.CW.EventMask, [1, xp.EventMask.KeyPress],
    )
    conn.core.MapWindow(probe)
    conn.core.SetInputFocus(xp.InputFocus.PointerRoot, probe, xp.Time.CurrentTime)
    conn.flush()
    wait_for(lambda: conn.core.GetInputFocus().reply().focus == probe)
    for key in ("t", "space", "Return", "Escape"):
        backend.press_key(key)
    backend.press_key("\u20ac")  # not on the keyboard: nothing is pressed
    backend.flush()
    seen = []

    def collect():
        while (event := conn.poll_for_event()) is not None:
            if isinstance(event, xp.KeyPressEvent):
                seen.append(event.detail)
        return len(seen) >= 4

    wait_for(collect)
    first = setup.min_keycode
    mapping = conn.core.GetKeyboardMapping(first, setup.max_keycode - first + 1).reply()
    typed = [mapping.keysyms[(code - first) * mapping.keysyms_per_keycode] for code in seen]
    conn.disconnect()
    assert typed == [ord("t"), 0x20, 0xFF0D, 0xFF1B]


def test_engine_drives_real_window(backend):
    """End to end: synthetic hands grab and move an xfwm4-managed window."""
    from holowm.config import Config
    from holowm.core.engine import Engine
    from holowm.launcher.launch import Launcher
    from holowm.launcher.macros import Macros
    from holowm.launcher.menu import MenuItem
    from holowm.tracker.types import FrameSample
    from synth import make_hand

    alpha = by_title(backend, "alpha")
    backend.move_resize(alpha.id, 100, 100, 320, 240)
    settle(backend, lambda: backend.get(alpha.id).x == 100)
    cfg = Config()
    engine = Engine(cfg, backend, Launcher(backend, MenuItem("Root")), Macros(backend, []))
    start = (200.0, 200.0)

    def script(elapsed):
        if elapsed < 0.4:
            return "open", start
        if elapsed < 0.6:
            return "pinch_index", start
        if elapsed < 1.4:
            f = (elapsed - 0.6) / 0.8
            return "pinch_index", (200 + 500 * f, 200 + 300 * f)
        if elapsed < 1.8:
            return "pinch_index", (700.0, 500.0)
        return "open", (700.0, 500.0)

    t0 = time.monotonic()
    next_frame, seq = t0, 0
    while (now := time.monotonic()) - t0 < 2.2:
        if now >= next_frame:
            pose, (px, py) = script(now - t0)
            engine.on_frame(FrameSample(seq, now, now, [make_hand(cfg, SCREEN, pose, px, py)]))
            seq, next_frame = seq + 1, next_frame + 1 / 30
        engine.tick(now)
        time.sleep(1 / 120)
    win = settle(backend, lambda: backend.get(alpha.id))
    assert abs(win.x - 600) <= 6 and abs(win.y - 400) <= 6
    assert backend.active_window().id == alpha.id


def test_switcher_orders_by_use_and_goes_to_a_window_on_another_workspace(backend):
    from holowm.config import Config
    from holowm.core.engine import Engine
    from holowm.core.interactions import SwitcherInteraction
    from holowm.launcher.launch import Launcher
    from holowm.launcher.macros import Macros
    from holowm.launcher.menu import MenuItem

    alpha, beta = by_title(backend, "alpha"), by_title(backend, "beta")
    engine = Engine(Config(), backend, Launcher(backend, MenuItem("Root")), Macros(backend, []))

    def focus(win):
        backend.activate(win.id)
        settle(backend, lambda: backend.active_window() is not None and backend.active_window().id == win.id)
        engine.tick(time.monotonic())

    focus(beta)
    focus(alpha)
    assert [w.title for w in engine.switcher_windows()] == ["alpha", "beta"]
    focus(beta)
    assert [w.title for w in engine.switcher_windows()] == ["beta", "alpha"]

    backend.set_window_desktop(alpha.id, 2)
    settle(backend, lambda: backend.get(alpha.id).desktop == 2)
    switcher = SwitcherInteraction(engine, engine.switcher_windows(), time.monotonic())
    switcher._switch_to(backend.get(alpha.id), time.monotonic())
    # We go to the window's workspace; the window manager does not bring it over to ours.
    settle(backend, lambda: backend.current_desktop() == 2 and backend.active_window().id == alpha.id)
    assert backend.get(alpha.id).desktop == 2 and by_title(backend, "alpha") is not None
    backend.set_window_desktop(alpha.id, 0)
    backend.switch_desktop(0)
    settle(backend, lambda: backend.current_desktop() == 0 and by_title(backend, "alpha") is not None)


def test_close_removes_window(backend):
    beta = by_title(backend, "beta")
    backend.close(beta.id)
    settle(backend, lambda: backend.get(beta.id) is None)
