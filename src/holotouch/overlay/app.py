"""The core process: Qt event loop, overlay window, engine tick, tray icon and control socket."""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import time
from pathlib import Path

# The overlay draws in real pixels to line up with window geometry, so Qt must not scale it.
os.environ["QT_SCALE_FACTOR"] = "1"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
from holotouch.session import gnome_wayland  # noqa: E402

# The overlay is an X11 window, under Wayland too: only there can a window sit above all the
# others, unmanaged and let clicks through. XWayland shows it.
if gnome_wayland():
    os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from PySide6.QtCore import QSize, Qt, QTimer, QUrl  # noqa: E402
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QSurfaceFormat  # noqa: E402
from PySide6.QtNetwork import QLocalServer  # noqa: E402
from PySide6.QtQuick import QQuickImageProvider, QQuickView  # noqa: E402
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon  # noqa: E402

from holotouch.config import LOG_ENV, SOCKET_PATH, Config  # noqa: E402
from holotouch.core.engine import Engine  # noqa: E402
from holotouch.core.hands import image_scale  # noqa: E402
from holotouch.launcher.camera import Photographer, Shutter, camera_command  # noqa: E402
from holotouch.launcher.dictate import Dictation  # noqa: E402
from holotouch.launcher.phone import PhoneLink  # noqa: E402
from holotouch.overlay.bridge import Bridge  # noqa: E402
from holotouch.overlay.images import WindowImageProvider, WindowImages  # noqa: E402
from holotouch.theme import PALETTE, qml_theme  # noqa: E402
from holotouch.x11.fake import FakeBackend  # noqa: E402

log = logging.getLogger(__name__)

_QML = Path(__file__).parent / "qml" / "Main.qml"

# The overlay window needs an alpha channel to be see-through.
_format = QSurfaceFormat()
_format.setAlphaBufferSize(8)
_format.setSwapInterval(1)
QSurfaceFormat.setDefaultFormat(_format)
_RAISE_INTERVAL_MS = 2000
# GNOME takes a window that covers a whole monitor for one shown fullscreen, and hides its top
# bar for as long as the window is there. The overlay is kept this many pixels short of that: one
# of GNOME's units, which is at most as many pixels.
_GNOME_SHORT = 4


class ThemeIconProvider(QQuickImageProvider):
    """Serves image://theme/<icon name or absolute path> to the pie menu."""

    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Pixmap)

    def requestPixmap(self, icon_id: str, size: QSize, requested: QSize) -> QPixmap:
        side = requested.width() if requested.width() > 0 else 96
        icon = QIcon(icon_id) if icon_id.startswith("/") else QIcon.fromTheme(icon_id)
        pixmap = icon.pixmap(side, side)
        if pixmap.isNull():
            pixmap = QPixmap(1, 1)
            pixmap.fill(Qt.GlobalColor.transparent)
        return pixmap


def _use_desktop_icon_theme() -> None:
    if gnome_wayland():
        command = ["gsettings", "get", "org.gnome.desktop.interface", "icon-theme"]
    else:
        command = ["xfconf-query", "-c", "xsettings", "-p", "/Net/IconThemeName"]
    try:
        name = subprocess.run(command, capture_output=True, text=True, timeout=2).stdout.strip().strip("'")
    except (OSError, subprocess.SubprocessError):
        name = ""
    QIcon.setThemeName(name or "Adwaita")
    QIcon.setFallbackThemeName("hicolor")


def _tray_pixmap(paused: bool) -> QPixmap:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    tone = QColor(PALETTE["muted" if paused else "mint"])
    painter.setPen(QPen(tone, 6))
    painter.drawEllipse(8, 8, 48, 48)
    painter.setBrush(tone)
    painter.drawEllipse(24, 24, 16, 16)
    painter.end()
    return pixmap


class App:
    def __init__(self, cfg: Config, backend, source, exit_when_done: bool = False, prompter=None):
        """With a prompter, hands are tracked and shown but start no gestures, and the app ends with its script."""
        self.cfg = cfg
        self.backend = backend
        self.source = source
        self.exit_when_done = exit_when_done
        self.prompter = prompter
        self.qt = QApplication.instance() or QApplication(["holotouch"])
        self.qt.setQuitOnLastWindowClosed(False)
        _use_desktop_icon_theme()
        self.engine = Engine(cfg, backend)
        self.engine.acting = prompter is None
        self.images = WindowImages(backend, cfg.switcher.thumbnails)
        self.bridge = Bridge(cfg, self.images)
        self.debug = cfg.ui.debug
        self._frame_times: list[float] = []
        self._latency_ms = 0.0
        self._last_frame = None
        self._camera_app: subprocess.Popen | None = None  # the camera app, while it has the webcam
        self._lent = False  # tracking is paused only because the camera app has the webcam
        self._shutter: Shutter | None = None  # at work until the camera app has taken its photo
        self._photographer = Photographer(cfg, source)
        self._dictation = Dictation(cfg, backend)
        self._phone = PhoneLink(cfg, backend)
        self._said: dict | None = None  # an instruction the control panel asked to have shown
        self._view = self._make_view()
        self._tray = self._make_tray()
        self._server = self._make_server()

        refresh = self.qt.primaryScreen().refreshRate() or 60.0
        hz = cfg.ui.tick_hz or refresh
        self._tick_timer = QTimer()
        self._tick_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(max(round(1000.0 / hz), 1))
        self._raise_timer = QTimer()
        self._raise_timer.timeout.connect(lambda: self._view.isVisible() and self._view.raise_())
        self._raise_timer.start(_RAISE_INTERVAL_MS)
        signal.signal(signal.SIGINT, lambda *_: self.qt.quit())
        signal.signal(signal.SIGTERM, lambda *_: self.qt.quit())

    # -- setup -------------------------------------------------------------------------------

    def _make_view(self) -> QQuickView:
        view = QQuickView()
        view.setFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.BypassWindowManagerHint  # override-redirect: above everything, unmanaged
            | Qt.WindowType.WindowTransparentForInput  # empty input shape: clicks pass through
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.Tool
        )
        view.setColor(QColor(0, 0, 0, 0))
        view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
        view.engine().addImageProvider("theme", ThemeIconProvider())
        view.engine().addImageProvider("window", WindowImageProvider(self.images))
        view.rootContext().setContextProperty("theme", qml_theme())
        view.rootContext().setContextProperty("bridge", self.bridge)
        view.setSource(QUrl.fromLocalFile(str(_QML)))
        for error in view.errors():
            log.error("QML: %s", error.toString())
        if view.status() != QQuickView.Status.Ready:
            raise RuntimeError("overlay failed to load")
        geometry = self.qt.primaryScreen().geometry()
        if gnome_wayland():
            geometry.setHeight(geometry.height() - _GNOME_SHORT)
        view.setGeometry(geometry)
        view.show()
        return view

    def _make_tray(self) -> QSystemTrayIcon | None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        tray = QSystemTrayIcon(QIcon(_tray_pixmap(False)))
        menu = QMenu()
        self._pause_action = menu.addAction("Pause tracking")
        self._pause_action.triggered.connect(lambda: self.command("toggle"))
        debug_action = menu.addAction("Debug overlay")
        debug_action.setCheckable(True)
        debug_action.setChecked(self.debug)
        debug_action.triggered.connect(lambda: self.command("debug"))
        menu.addSeparator()
        menu.addAction("Quit HoloTouch").triggered.connect(self.qt.quit)
        tray.setContextMenu(menu)
        tray.setToolTip("HoloTouch")
        tray.activated.connect(
            lambda reason: reason == QSystemTrayIcon.ActivationReason.Trigger and self.command("toggle")
        )
        tray.show()
        self._tray_menu = menu
        return tray

    def _make_server(self) -> QLocalServer:
        QLocalServer.removeServer(str(SOCKET_PATH))
        server = QLocalServer()
        server.newConnection.connect(self._on_connection)
        if not server.listen(str(SOCKET_PATH)):
            log.warning("control socket unavailable: %s", server.errorString())
        return server

    # -- control -----------------------------------------------------------------------------

    def _on_connection(self) -> None:
        socket = self._server.nextPendingConnection()

        def respond():
            reply = self.command(bytes(socket.readAll()).decode().strip())
            socket.write((reply + "\n").encode())
            socket.flush()
            socket.disconnectFromServer()

        socket.readyRead.connect(respond)

    def command(self, name: str) -> str:
        if name in ("pause", "resume", "toggle"):
            paused = {"pause": True, "resume": False, "toggle": not self.engine.paused}[name]
            self._lent = False  # asked for by hand: closing the camera app no longer decides it
            if not paused:
                self.source.resume()
            self.engine.set_paused(paused)
            # Hiding the window lets the compositor stop compositing fullscreen apps while paused.
            self._view.setVisible(not paused)
            if self._tray is not None:
                self._tray.setIcon(QIcon(_tray_pixmap(paused)))
                self._pause_action.setText("Resume tracking" if paused else "Pause tracking")
            return "paused" if paused else "running"
        if name == "debug":
            self.debug = not self.debug
            return f"debug {'on' if self.debug else 'off'}"
        if name == "status":
            state = "paused" if self.engine.paused else "running"
            return f"{state}; {self._tracker_fps():.0f} fps; {len(self.engine.tracker.hands)} hands"
        if name == "info":
            return json.dumps(self._info())
        if name == "say" or name.startswith("say "):
            # `say {...}` shows one instruction on the desktop, as practice mode does; `say` takes it away.
            try:
                said = json.loads(name[4:]) if name[4:].strip() else None
            except ValueError:
                return "say: not JSON"
            self._said = {**said, "visible": True} if isinstance(said, dict) else None
            return "said" if self._said else "unsaid"
        if name == "phone":
            # What tossing an open palm upward does, for when there is no hand to toss.
            return "sending" if self._phone.send(time.monotonic()) else "not sent: no web browser has the keyboard, or a page is on its way already"
        if name == "quit":
            QTimer.singleShot(0, self.qt.quit)
            return "bye"
        return f"unknown command: {name}"

    def _info(self) -> dict:
        """What the control panel shows of a running instance."""
        active = self.engine.active
        frame = self.engine.overlay.frame
        return {
            "pid": os.getpid(),
            "paused": self.engine.paused,
            "lent": self._lent,
            "fps": round(self._tracker_fps()),
            "hands": len(self.engine.tracker.hands),
            # The gesture in progress, named after its class: "move", "scroll", "knob"...
            "gesture": type(active).__name__.removesuffix("Interaction").lower() if active is not None else "",
            # The window a hand is on: how it is held, and where it is. Practice mode watches these.
            "frame": [frame.mode, round(frame.x), round(frame.y), round(frame.w), round(frame.h)] if frame else [],
            "screen": list(self.engine.screen),
            "debug": self.debug,
            "practice": isinstance(self.backend, FakeBackend),
            "error": self.source.error or "",
            "log": os.environ.get(LOG_ENV, ""),
        }

    # -- camera app --------------------------------------------------------------------------

    def _open_camera(self) -> None:
        """Lend the webcam to the camera app: tracking stops, and starts again once the app is closed."""
        command = camera_command(self.cfg)
        if not command:
            log.warning("no camera app found; name one with camera_command under [gesture]")
            return
        # Only one program can use the webcam at a time, so it is given up before the app starts.
        self.source.suspend()
        shutter = Shutter(self.backend, self.cfg, time.monotonic())
        try:
            self._camera_app = subprocess.Popen(
                command, shell=True, start_new_session=True,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )  # fmt: skip
        except OSError as exc:
            log.error("could not open the camera app %r: %s", command, exc)
            self.source.resume()
            return
        log.info("opened the camera app (%s); tracking is paused until it is closed", command)
        self.command("pause")
        self._lent = True
        self._shutter = shutter

    def _watch_camera(self) -> None:
        if self.engine.camera_wanted:
            self.engine.camera_wanted = False
            if not camera_command(self.cfg):
                self._photographer.take(time.monotonic())  # at once, from the camera the hands are watched with
            elif self._camera_app is None:
                self._open_camera()
        if self._shutter is not None and not self._shutter.step(time.monotonic()):
            self._shutter = None
        if self._camera_app is not None and self._camera_app.poll() is not None:
            self._camera_app = self._shutter = None
            if self._lent:
                log.info("the camera app was closed; tracking again")
                self.command("resume")

    # -- loop --------------------------------------------------------------------------------

    def _tracker_fps(self) -> float:
        now = time.monotonic()
        self._frame_times = [t for t in self._frame_times if now - t <= 1.0]
        return float(len(self._frame_times))

    def _tick(self) -> None:
        now = time.monotonic()
        for frame in self.source.drain():
            self.engine.on_frame(frame)
            self._frame_times.append(now)
            self._latency_ms += 0.1 * ((now - frame.t_capture) * 1000.0 - self._latency_ms)
            self._last_frame = frame
        state = self.engine.tick(now)
        self._watch_camera()
        state.dictation = self._dictation.step(self.engine.dictating, now)
        if self.engine.phone_wanted:
            self.engine.phone_wanted = False
            self._phone.send(now)
        state.photo, no_photo = self._photographer.step(now)
        state.key = self._phone.step(now) or no_photo or state.key
        prompt = self.prompter.step(now) if self.prompter is not None else self._said
        self.bridge.apply(state, self._debug_info() if self.debug else None, prompt)
        if self.exit_when_done and getattr(self.source, "finished", False):
            self.qt.quit()
        if self.prompter is not None and self.prompter.finished:
            self.qt.quit()

    def _debug_info(self) -> dict:
        engine = self.engine
        aspect = self.cfg.camera.width / self.cfg.camera.height
        lines = [
            f"tracker {self._tracker_fps():4.0f} fps   capture-to-tick {self._latency_ms:5.1f} ms",
            f"state   {'PAUSED' if engine.paused else type(engine.active).__name__ if engine.active else 'idle'}",
        ]
        if self.source.error:
            lines.append(f"error   {self.source.error}")
        for hand in sorted(engine.tracker.hands.values(), key=lambda h: h.id):
            f = hand.features
            lines.append(
                f"hand {hand.id} {hand.handedness[:1]} {hand.pose.value:<12} "
                f"i={f.pinch_index:.2f} p={f.pinch_pinky:.2f} th={f.thumb_tuck:.2f} t={f.finger_tilt:+4.0f} "
                f"{'armed' if hand.armed else '-'}"
            )
        # How large each hand is in the picture, which is how near the camera it is; the size a
        # new hand has to be (tracker.min_hand_scale, or tracker.behind_face of the face's); and
        # the sizes of the hands left out as being in the background.
        tracker = engine.tracker
        ignored = tracker.ignored
        sizes = [f"{h.id}: {h.image_scale:.2f}" for h in sorted(tracker.hands.values(), key=lambda h: h.id)]
        sizes.append(f"least {tracker.smallest:.2f}")
        if ignored:
            sizes.append("ignored " + " ".join(f"{image_scale(h, aspect):.2f}" for h in ignored))
        lines.append("size    " + "   ".join(sizes))
        face = engine.face
        seen = face.visible(time.monotonic())
        if seen:
            # Per hand: how far it is from the chin (c, in face heights) and how much nearer the
            # camera than the face (z). A fist on the chin needs c under chin_reach and z under chin_depth.
            measures = [f"{h.id}: c={face.reach(h):.2f} z={face.closeness(h):.2f}" for h in engine.tracker.hands.values()]
            lines.append("face    " + ("   ".join(measures) or "seen"))
        else:
            lines.append("face    not seen")
        m = self.cfg.mapping
        return {
            "visible": True,
            "text": "\n".join(lines),
            "box": [m.box_x, m.box_y, m.box_w, m.box_h],
            "hands": [h.landmarks[:, :2].round(3).tolist() for h in engine.tracker.hands.values()],
            "ignored": [h.image[:, :2].round(3).tolist() for h in ignored],
            "face": face.outline.round(3).tolist() if seen else [],
            # The chin, and how far from it a fist may be, as fractions of the frame's width and height.
            "chin": [float(face.chin[0]) / aspect, float(face.chin[1]), face.size * self.cfg.gesture.chin_reach] if seen else [],
        }

    def run(self) -> int:
        code = self.qt.exec()
        self._tick_timer.stop()
        self._view.setSource(QUrl())  # the QML goes before the bridge it reads from does
        self.engine.cancel_active()
        self._dictation.close()
        self._phone.close()
        self.source.stop()
        self._server.close()
        if hasattr(self.backend, "close_backend"):
            self.backend.flush()
            self.backend.close_backend()
        return code
