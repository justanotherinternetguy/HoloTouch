"""The control panel process: a window to start, stop and watch HoloWM from."""

from __future__ import annotations

import logging
import os
import signal
from pathlib import Path

# The panel is sized by [ui] scale, as the overlay is, so Qt must not scale it as well.
os.environ["QT_SCALE_FACTOR"] = "1"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"

from PySide6.QtCore import QPoint, QSize, QUrl  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QIcon  # noqa: E402
from PySide6.QtQuick import QQuickView  # noqa: E402

from holowm.config import LOG_PATH, Config  # noqa: E402
from holowm.panel.controller import Controller  # noqa: E402
from holowm.panel.desktop import APP_ID, ICON  # noqa: E402
from holowm.theme import PALETTE, qml_theme  # noqa: E402

log = logging.getLogger(__name__)

_QML = Path(__file__).parent / "qml" / "Panel.qml"
_SIZE = (960, 660)  # of the window, before the scale is applied
_FIT = 0.92  # how much of the screen the window may take up: on a small one the scale gives way


def run_panel(cfg: Config, config_path: Path | None = None, problem: str = "") -> int:
    """Open the panel. A problem is something to tell the user of straight away."""
    qt = QGuiApplication(["holowm"])
    qt.setDesktopFileName(APP_ID)
    qt.setWindowIcon(QIcon(str(ICON)))
    area = qt.primaryScreen().availableGeometry()
    scale = min(cfg.ui.scale, _FIT * area.width() / _SIZE[0], _FIT * area.height() / _SIZE[1])
    # What the panel remembers between openings sits beside the log.
    controller = Controller(cfg, config_path, scale, problem, state_path=LOG_PATH.with_name("panel.json"))

    view = QQuickView()
    view.setTitle("HoloWM")
    view.setColor(QColor(PALETTE["cream"]))
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.rootContext().setContextProperty("theme", qml_theme())
    view.rootContext().setContextProperty("panel", controller)
    view.setSource(QUrl.fromLocalFile(str(_QML)))
    for error in view.errors():
        log.error("QML: %s", error.toString())
    if view.status() != QQuickView.Status.Ready:
        raise RuntimeError("control panel failed to load")
    size = QSize(round(_SIZE[0] * scale), round(_SIZE[1] * scale))
    view.setMinimumSize(size)
    view.resize(size)
    view.setPosition(area.center() - QPoint(size.width() // 2, size.height() // 2))
    view.show()

    controller.watch()
    signal.signal(signal.SIGINT, lambda *_: qt.quit())
    signal.signal(signal.SIGTERM, lambda *_: qt.quit())
    code = qt.exec()
    view.setSource(QUrl())  # the QML goes before the controller it reads from does
    return code
