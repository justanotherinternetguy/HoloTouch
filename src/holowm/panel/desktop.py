"""The applications-menu entry that opens the control panel."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_ID = "holowm"
ICON = Path(__file__).parent / "holowm.svg"


def _quoted(path: str) -> str:
    """A path as one argument of a desktop entry's Exec line."""
    for char in '\\"`$':
        path = path.replace(char, "\\" + char)
    return f'"{path}"'.replace("%", "%%")


def desktop_entry() -> str:
    # Named by its interpreter, so the entry works with holowm installed in a virtual environment
    # and not on the PATH.
    return "\n".join(
        [
            "[Desktop Entry]",
            "Type=Application",
            "Name=HoloWM",
            "Comment=Hand-gesture window control",
            f"Exec={_quoted(sys.executable)} -m holowm.cli panel",
            f"Icon={ICON}",
            "Terminal=false",
            "Categories=Utility;",
            "Keywords=gesture;hand;camera;window;",
            "",
        ]
    )


def install_launcher() -> Path:
    """Add HoloWM to the applications menu of this user. Returns the file written."""
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = data_home / "applications" / f"{APP_ID}.desktop"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(desktop_entry())
    return path
