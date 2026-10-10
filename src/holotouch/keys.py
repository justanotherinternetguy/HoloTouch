"""Keys by name, as a menu item or a macro gives them: "Escape", "t", "ctrl+shift+Tab"."""

from __future__ import annotations

# X keysyms, which Wayland compositors use as well; a Latin-1 character is its own.
NAMED_KEYS = {
    "space": 0x20, "Return": 0xFF0D, "Escape": 0xFF1B, "Tab": 0xFF09, "BackSpace": 0xFF08, "Delete": 0xFFFF,
    "Home": 0xFF50, "Left": 0xFF51, "Up": 0xFF52, "Right": 0xFF53, "Down": 0xFF54,
    "Page_Up": 0xFF55, "Page_Down": 0xFF56, "End": 0xFF57,
    **{f"F{n}": 0xFFBD + n for n in range(1, 13)},
}  # fmt: skip
MODIFIERS = {"ctrl": 0xFFE3, "shift": 0xFFE1, "alt": 0xFFE9}  # the left one of each


def keysyms(key: str) -> list[int | None]:
    """The keys to hold and then the key to press, in that order: "ctrl+t" is Control, then t.

    One that names no key is None.
    """
    *held, key = key.split("+") if len(key) > 1 else [key]
    return [MODIFIERS.get(name) for name in held] + [NAMED_KEYS.get(key) or (ord(key) if len(key) == 1 else None)]
