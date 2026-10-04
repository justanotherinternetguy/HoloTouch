"""Pie menu model and marking-mode selection logic (after Fly-Pie). No drawing here."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from holotouch.config import PieConfig

BACK = -1
MENU_TYPES = ("submenu", "running_windows")
ITEM_TYPES = (
    "app",  # data: desktop file id
    "command",  # data: shell command
    "submenu",
    "window_action",  # data: close | minimize | maximize | tile_left | tile_right
    "workspace",  # data: workspace index to switch to
    "send_to_workspace",  # data: workspace index for the target window
    "running_windows",  # expands to the windows on the current workspace
    "activate_window",  # data: window id
    "track",  # data: next | previous, the way to skip in whatever is playing music
    "key",  # data: a key pressed in whatever has the keyboard, as "Escape" or "ctrl+t"
)


@dataclass
class MenuItem:
    name: str
    type: str = "submenu"
    data: object = None
    icon: str = ""
    children: list["MenuItem"] = field(default_factory=list)

    @property
    def is_menu(self) -> bool:
        return self.type in MENU_TYPES


def item_from_dict(d: dict) -> MenuItem:
    item_type = d.get("type", "submenu" if "children" in d else "command")
    if item_type not in ITEM_TYPES:
        raise ValueError(f"unknown menu item type {item_type!r} for {d.get('name')!r}")
    if item_type == "track" and d.get("data") not in ("next", "previous"):
        raise ValueError(f"menu item {d.get('name')!r}: a track item's data is \"next\" or \"previous\"")
    if item_type == "key" and not (isinstance(d.get("data"), str) and d["data"]):
        raise ValueError(f"menu item {d.get('name')!r}: a key item's data is the key, as \"Escape\" or \"ctrl+t\"")
    return MenuItem(
        name=str(d.get("name", "?")),
        type=item_type,
        data=d.get("data"),
        icon=str(d.get("icon", "")),
        children=[item_from_dict(c) for c in d.get("children", [])],
    )


def track_direction(item: MenuItem) -> int:
    """Which way a "track" item skips: 1 to the next track, -1 to the one before."""
    return -1 if item.data == "previous" else 1


def layout_angles(count: int, back_angle: float | None) -> list[float]:
    """Item directions in degrees, 0 = up, clockwise. A submenu keeps one slot for 'back'."""
    if count == 0:
        return []
    if back_angle is None:
        return [i * 360.0 / count for i in range(count)]
    wedge = 360.0 / (count + 1)
    return [(back_angle + (i + 1) * wedge) % 360.0 for i in range(count)]


def _angle_gap(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


@dataclass
class _Level:
    menu: MenuItem
    cx: float
    cy: float
    back_angle: float | None
    angles: list[float]


class PieSession:
    """One open menu. Feed it hand positions; release() returns the chosen leaf, if any.

    Only direction matters beyond the dead zone. Moving a full stroke length onto a submenu
    enters it and re-centres the menu at the hand; leaves are only committed on release.
    """

    def __init__(self, root: MenuItem, x: float, y: float, cfg: PieConfig, scale: float, screen: tuple[int, int]):
        self.cfg = cfg
        self.scale = scale
        self.screen = screen
        self.hover: int | None = None
        self.stack: list[_Level] = []
        self._push(root, x, y, None)

    @property
    def dead_zone(self) -> float:
        return self.cfg.dead_zone * self.scale

    @property
    def stroke_length(self) -> float:
        return self.cfg.stroke_length * self.scale

    def _clamp(self, x: float, y: float) -> tuple[float, float]:
        margin = (self.cfg.child_offset + self.cfg.child_size) * self.scale
        w, h = self.screen
        return (min(max(x, margin), max(w - margin, margin)), min(max(y, margin), max(h - margin, margin)))

    def _push(self, menu: MenuItem, x: float, y: float, back_angle: float | None) -> None:
        cx, cy = self._clamp(x, y)
        children = menu.children[: self.cfg.max_items]
        self.stack.append(_Level(menu, cx, cy, back_angle, layout_angles(len(children), back_angle)))
        self.hover = None

    def _items(self) -> list[MenuItem]:
        return self.stack[-1].menu.children[: self.cfg.max_items]

    def update(self, x: float, y: float) -> None:
        level = self.stack[-1]
        dx, dy = x - level.cx, y - level.cy
        dist = math.hypot(dx, dy)
        if dist <= self.dead_zone:
            self.hover = None
            return
        angle = math.degrees(math.atan2(dx, -dy)) % 360.0
        candidates = list(enumerate(level.angles))
        if level.back_angle is not None:
            candidates.append((BACK, level.back_angle))
        if not candidates:
            self.hover = None
            return
        self.hover = min(candidates, key=lambda c: _angle_gap(angle, c[1]))[0]
        if dist < self.stroke_length:
            return
        if self.hover == BACK:
            self.stack.pop()
            parent = self.stack[-1]
            parent.cx, parent.cy = self._clamp(x, y)
            self.hover = None
        else:
            item = self._items()[self.hover]
            if item.is_menu and item.children:
                self._push(item, x, y, (level.angles[self.hover] + 180.0) % 360.0)

    def release(self) -> MenuItem | None:
        if self.hover is None or self.hover == BACK:
            return None
        item = self._items()[self.hover]
        return None if item.is_menu else item

    def view(self) -> dict:
        level = self.stack[-1]
        offset = self.cfg.child_offset * self.scale
        items = []
        for i, (item, angle) in enumerate(zip(self._items(), level.angles)):
            rad = math.radians(angle)
            items.append(
                {
                    "name": item.name,
                    "icon": item.icon,
                    "x": level.cx + math.sin(rad) * offset,
                    "y": level.cy - math.cos(rad) * offset,
                    "hovered": self.hover == i,
                    "menu": item.is_menu,
                    "type": item.type,
                    "data": item.data,
                    "count": len(item.children),
                }
            )
        back = None
        if level.back_angle is not None:
            rad = math.radians(level.back_angle)
            back = {
                "x": level.cx + math.sin(rad) * offset,
                "y": level.cy - math.cos(rad) * offset,
                "hovered": self.hover == BACK,
            }
        if self.hover is None:
            label = level.menu.name
        elif self.hover == BACK:
            label = "Back"
        else:
            label = self._items()[self.hover].name
        return {
            "cx": level.cx,
            "cy": level.cy,
            "label": label,
            "items": items,
            "back": back,
            "trail": [[lv.cx, lv.cy] for lv in self.stack],
        }
