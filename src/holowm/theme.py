"""HoloWM's colours and typefaces, shared by the overlay and the control panel.

Cream and ink carry the interface. Colour marks what a hand is doing: sky is the left hand, coral
the right, butter is progress, mint is done and running, lilac opens further.
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

_FONTS = Path(__file__).parent / "fonts"
# The role each bundled typeface plays, and what stands in for it if it cannot be loaded.
_FACES = {
    "display": (("Fredoka.ttf",), "sans-serif"),
    "body": (("Figtree.ttf",), "sans-serif"),
    "mono": (("DMMono-Regular.ttf", "DMMono-Medium.ttf"), "monospace"),
}

PALETTE = {
    "cream": "#FBF3E4",
    "paper": "#FFFCF5",
    "sunk": "#F2E6CF",
    "line": "#E6D8BD",
    "muted": "#B8AC96",
    "ink": "#1E1B2E",
    "inkRaised": "#2C2842",
    "inkMid": "#3A3552",
    "inkSoft": "#5A5470",
    "ledge": "#0E0C18",
    "coral": "#FF6B5C",
    "sky": "#4AA8FF",
    "mint": "#3DD6A3",
    "butter": "#FFD35A",
    "lilac": "#B69CFF",
    "coralTint": "#FFE9E5",
    "butterTint": "#FFF6D8",
    "butterDeep": "#C99A1E",
    # Over the desktop every shape pairs cream with ink, so it reads on light and dark windows.
    "keyline": "#D9FBF3E4",  # cream, 85%
    "hairline": "#CC1E1B2E",  # ink, 80%
    "chip": "#EB1E1B2E",  # ink, 92%
    "track": "#991E1B2E",  # ink, 60%
    "scrim": "#941E1B2E",  # ink, 58%
}


def hand_colour(side: str) -> str:
    return PALETTE["sky"] if side == "left" else PALETTE["coral"]


def load_fonts() -> dict[str, str]:
    """Register the bundled typefaces with Qt. Needs a QGuiApplication. Returns role -> family."""
    from PySide6.QtGui import QFontDatabase

    families = {}
    for role, (files, fallback) in _FACES.items():
        family = ""
        for name in files:
            font_id = QFontDatabase.addApplicationFont(str(_FONTS / name))
            loaded = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
            family = family or (loaded[0] if loaded else "")
        if not family:
            log.warning("typeface %s could not be loaded; using %s", files[0], fallback)
        families[role] = family or fallback
    return families


def qml_theme() -> dict[str, str]:
    """What QML sees as `theme`: every colour by name, and the three font families."""
    return {**PALETTE, **load_fonts()}
