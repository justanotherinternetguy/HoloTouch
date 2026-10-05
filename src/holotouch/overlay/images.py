"""Pictures for the window switcher: each window's icon and a snapshot of its contents."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtQuick import QQuickImageProvider

from holotouch.core.actions import Pixels
from holotouch.launcher.launch import icon_name


def _pixmap(pixels: Pixels, side: int = 0) -> QPixmap:
    """A pixmap of the pixels, smoothly scaled to fit side x side if given."""
    # A QImage built on a buffer only borrows it, so it has to be copied before the bytes go away.
    image = QImage(pixels.data, pixels.w, pixels.h, pixels.w * 4, QImage.Format.Format_ARGB32)
    if side:
        image = image.scaled(
            side, side, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
    return QPixmap.fromImage(image.copy())


class WindowImages:
    """Loaded from the backend each time the switcher opens, then served to QML."""

    def __init__(self, backend, thumbnails: bool = True):
        # Only the real backends have pictures; the dry-run backend falls back to theme icons.
        self._icon_source = getattr(backend, "window_icon", None)
        self._thumb_source = getattr(backend, "window_thumbnails", None) if thumbnails else None
        self._pixmaps: dict[tuple[str, int], QPixmap] = {}

    def refresh(self, windows: list[tuple[int, str]], thumb: tuple[int, int], badge: int, large: int) -> None:
        """Load pictures for these (window id, class name) pairs and forget every other window.

        Pictures are made at the size they are shown: snapshots within `thumb`, icons `badge`
        pixels wide beside a snapshot and `large` pixels wide when there is none.
        """
        ids = [win for win, _ in windows]
        fresh = self._thumb_source(ids, *thumb) if self._thumb_source else {}
        pixmaps = {}
        for win, wm_class in windows:
            # A window that cannot be captured right now (minimized, or on another workspace)
            # keeps the snapshot from the last time it could.
            snapshot = _pixmap(fresh[win]) if win in fresh else self._pixmaps.get(("thumb", win))
            if snapshot is not None:
                pixmaps["thumb", win] = snapshot
            icon = self._icon(win, wm_class, large if snapshot is None else badge)
            if icon is not None:
                pixmaps["icon", win] = icon
        self._pixmaps = pixmaps

    def _icon(self, win: int, wm_class: str, side: int) -> QPixmap | None:
        pixels = self._icon_source(win, side) if self._icon_source else None
        if pixels is not None:
            return _pixmap(pixels, side)
        name = icon_name(wm_class)
        if name and QIcon.hasThemeIcon(name):
            return QIcon.fromTheme(name).pixmap(side, side)
        return None

    def get(self, kind: str, win: int) -> QPixmap | None:
        return self._pixmaps.get((kind, win))


class WindowImageProvider(QQuickImageProvider):
    """Serves image://window/<icon or thumb>/<window id>/<serial>."""

    def __init__(self, images: WindowImages):
        super().__init__(QQuickImageProvider.ImageType.Pixmap)
        self._images = images

    def requestPixmap(self, image_id: str, size: QSize, requested: QSize) -> QPixmap:
        kind, win = image_id.split("/")[:2]
        pixmap = self._images.get(kind, int(win))
        if pixmap is None:
            pixmap = QPixmap(1, 1)
            pixmap.fill(Qt.GlobalColor.transparent)
        return pixmap
