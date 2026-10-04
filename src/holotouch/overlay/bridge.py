"""Exposes the engine's overlay state to QML as a handful of properties.

Each property only notifies when its value actually changed, so an idle overlay does not repaint.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal
from PySide6.QtGui import QIcon

from holotouch.config import Config
from holotouch.core.overlay_state import OverlayState
from holotouch.overlay.images import WindowImages

_HIDDEN_HAND = {
    "visible": False, "x": 0.0, "y": 0.0, "pinch": 0.0, "pose": "neutral", "active": False, "armed": False,
    "scroll": 0.0, "side": "right", "lost": False,
}  # fmt: skip
_HIDDEN_FRAME = {
    "visible": False, "x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0, "mode": "hover", "label": "", "side": "",
    "ghost": [], "lost": False,
}  # fmt: skip
_CLOSED_MENU = {"open": False, "cx": 0.0, "cy": 0.0, "label": "", "hover": -2, "back": None, "trail": []}
_CLOSED_SWITCHER = {
    "open": False, "x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0, "u": 1.0, "cardW": 0.0, "cardH": 0.0,
    "inset": 0.0, "titleH": 0.0, "badge": 0.0, "largeIcon": 0.0, "selected": -1, "label": "", "side": "",
}  # fmt: skip
# Switcher card layout, in pixels before the ui scale: the margin around the picture, the strip
# kept for the title, and the icon size beside a snapshot and in place of one.
_CARD_INSET = 12.0
_CARD_TITLE = 42.0
_CARD_BADGE = 44.0
_CARD_ICON = 88.0
# Pictures are made slightly larger than shown, so the enlarged selected card stays sharp.
_PICTURE_SCALE = 1.1


def _kind(item: dict) -> str:
    """What a menu item does, which decides the colour of its petal."""
    kind = item.get("type", "")
    if item.get("menu") or kind == "workspace":
        return "more"
    if kind == "window_action" and item.get("data") == "close":
        return "close"
    if kind in ("window_action", "send_to_workspace", "activate_window"):
        return "window"
    return "launch"


def _has_icon(name: str) -> bool:
    if not name:
        return False
    return Path(name).is_file() if name.startswith("/") else QIcon.hasThemeIcon(name)


class Bridge(QObject):
    handsChanged = Signal()
    frameChanged = Signal()
    fxChanged = Signal()
    menuChanged = Signal()
    menuItemsChanged = Signal()
    switcherChanged = Signal()
    switcherItemsChanged = Signal()
    spellOptionsChanged = Signal()
    debugChanged = Signal()
    promptChanged = Signal()

    def __init__(self, cfg: Config, images: WindowImages | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._cfg = cfg
        self._images = images
        self._slots: dict[int, int] = {}  # hand id -> cursor slot, stable while the hand lives
        self._hands = [dict(_HIDDEN_HAND), dict(_HIDDEN_HAND)]
        self._frame = dict(_HIDDEN_FRAME)
        self._fx: dict = self._fx_of(OverlayState())
        self._menu = dict(_CLOSED_MENU)
        self._menu_items: list = []
        self._menu_key: tuple = ()
        self._switcher = dict(_CLOSED_SWITCHER)
        self._switcher_items: list = []
        self._switcher_key: tuple | None = None
        self._switcher_serial = 0
        self._spell_options: list = []
        self._spell_seen: list = []
        self._debug: dict = {"visible": False}
        self._prompt: dict = {"visible": False}

    # -- constants ---------------------------------------------------------------------------

    @Property(float, constant=True)
    def scale(self) -> float:
        return self._cfg.ui.scale

    @Property("QVariantMap", constant=True)
    def pie(self) -> dict:
        p = self._cfg.pie
        return {"deadZone": p.dead_zone, "childOffset": p.child_offset, "childSize": p.child_size, "centerSize": p.center_size}

    @Property(float, constant=True)
    def closeRadius(self) -> float:
        """How far a closing fist may drift, as a fraction of the screen's height."""
        return self._cfg.gesture.close_radius

    # -- live state --------------------------------------------------------------------------

    @Property("QVariantMap", notify=handsChanged)
    def hand0(self) -> dict:
        return self._hands[0]

    @Property("QVariantMap", notify=handsChanged)
    def hand1(self) -> dict:
        return self._hands[1]

    @Property("QVariantMap", notify=frameChanged)
    def frame(self) -> dict:
        return self._frame

    @Property("QVariantMap", notify=fxChanged)
    def fx(self) -> dict:
        return self._fx

    @Property("QVariantMap", notify=menuChanged)
    def menu(self) -> dict:
        return self._menu

    @Property("QVariantList", notify=menuItemsChanged)
    def menuItems(self) -> list:
        return self._menu_items

    @Property("QVariantMap", notify=switcherChanged)
    def switcher(self) -> dict:
        return self._switcher

    @Property("QVariantList", notify=switcherItemsChanged)
    def switcherItems(self) -> list:
        return self._switcher_items

    @Property("QVariantList", notify=spellOptionsChanged)
    def spellOptions(self) -> list:
        return self._spell_options

    @Property("QVariantMap", notify=debugChanged)
    def debug(self) -> dict:
        return self._debug

    @Property("QVariantMap", notify=promptChanged)
    def prompt(self) -> dict:
        return self._prompt

    def apply(self, state: OverlayState, debug: dict | None = None, prompt: dict | None = None) -> None:
        live = {h.id for h in state.hands}
        self._slots = {i: s for i, s in self._slots.items() if i in live}
        # A hand that disappears keeps its last position so its cursor fades out in place. One that
        # was driving a gesture when it went is marked lost, so the overlay can say so.
        hands = [
            {**h, "visible": False, "active": False, "scroll": 0.0, "lost": h["active"] if h["visible"] else h["lost"]}
            for h in self._hands
        ]
        for hand in state.hands:
            slot = self._slots.get(hand.id)
            if slot is None:
                free = [s for s in (0, 1) if s not in self._slots.values()]
                if not free:
                    continue
                slot = self._slots[hand.id] = free[0]
            hands[slot] = {
                "visible": True, "x": hand.x, "y": hand.y, "pinch": hand.pinch,
                "pose": hand.pose, "active": hand.active, "armed": hand.armed, "scroll": hand.scroll,
                "side": hand.side, "lost": False,
            }  # fmt: skip
        holder_lost = any(h["lost"] and was["visible"] for h, was in zip(hands, self._hands))
        if hands != self._hands:
            self._hands = hands
            self.handsChanged.emit()

        f = state.frame
        if f is not None:
            frame = {
                "visible": True, "x": f.x, "y": f.y, "w": f.w, "h": f.h, "mode": f.mode, "label": f.label,
                "side": f.side, "ghost": list(f.ghost) if f.ghost is not None else [], "lost": False,
            }  # fmt: skip
        else:
            # The last outline is kept while it fades. If the hand holding the window vanished, it
            # fades as an outline that was let down, not one that was let go of.
            if self._frame["visible"]:
                lost = holder_lost and self._frame["mode"] in ("grab", "resize")
            else:
                lost = self._frame["lost"]
            frame = {**self._frame, "visible": False, "lost": lost}
        if frame != self._frame:
            self._frame = frame
            self.frameChanged.emit()

        fx = self._fx_of(state)
        if fx != self._fx:
            self._fx = fx
            self.fxChanged.emit()

        self._apply_menu(state.menu)
        self._apply_switcher(state.switcher)
        # The last rows are kept once spelling is over, so that the launcher fades out as it was.
        if state.spell == "spelling" and state.spell_options != self._spell_seen:
            self._spell_seen = state.spell_options
            self._spell_options = [{**option, "hasIcon": _has_icon(option["icon"])} for option in state.spell_options]
            self.spellOptionsChanged.emit()

        debug = debug or {"visible": False}
        if debug != self._debug:
            self._debug = debug
            self.debugChanged.emit()

        # The last prompt is kept while it fades out, as the menu is.
        prompt = prompt or {**self._prompt, "visible": False}
        if prompt != self._prompt:
            self._prompt = prompt
            self.promptChanged.emit()

    @staticmethod
    def _fx_of(state: OverlayState) -> dict:
        return {
            "edgeSide": state.edge_side,
            "edgeProgress": state.edge_progress,
            "edgeTarget": state.edge_target,
            "closeProgress": state.close_progress,
            "closeX": state.close_x,
            "closeY": state.close_y,
            "hudDesktop": state.hud_desktop,
            "hudCount": state.hud_count,
            "scrolling": state.scrolling,
            "knob": state.knob,
            "knobX": state.knob_x,
            "knobY": state.knob_y,
            "knobName": state.knob_name,
            "holdProgress": state.hold_progress,
            "holdX": state.hold_x,
            "holdY": state.hold_y,
            "holdName": state.hold_name,
            "click": state.click,
            "clickX": state.click_x,
            "clickY": state.click_y,
            "track": state.track,
            "photo": QUrl.fromLocalFile(state.photo).toString() if state.photo else "",
            "key": state.key,
            "dictation": state.dictation,
            "spell": state.spell,
            "spellLetters": state.spell_letters,
            "spellGuess": state.spell_guess,
            "spellHolding": state.spell_holding,
            "spellHold": state.spell_hold,
            "spellMore": state.spell_more,
            "spellOpening": state.spell_opening,
            "spellName": state.spell_name,
            "paused": state.paused,
        }

    def _apply_menu(self, view: dict | None) -> None:
        if view is None:
            if self._menu["open"]:
                # Keep the last geometry so the menu can fade out in place.
                self._menu = {**self._menu, "open": False}
                self.menuChanged.emit()
            return
        key = tuple((i["name"], round(i["x"]), round(i["y"])) for i in view["items"])
        if key != self._menu_key:
            self._menu_key = key
            self._menu_items = [
                {
                    "name": i["name"], "icon": i["icon"], "hasIcon": _has_icon(i["icon"]), "x": i["x"], "y": i["y"],
                    "menu": i["menu"], "kind": _kind(i), "count": i.get("count", 0),
                }  # fmt: skip
                for i in view["items"]
            ]
            self.menuItemsChanged.emit()
        hover = next((n for n, i in enumerate(view["items"]) if i["hovered"]), -2)
        if view["back"] is not None and view["back"]["hovered"]:
            hover = -1
        menu = {
            "open": True,
            "cx": view["cx"],
            "cy": view["cy"],
            "label": view["label"],
            "hover": hover,
            "back": view["back"],
            "trail": view["trail"],
        }
        if menu != self._menu:
            self._menu = menu
            self.menuChanged.emit()

    def _image_url(self, kind: str, win: int) -> str:
        if self._images is None or self._images.get(kind, win) is None:
            return ""
        # The serial makes QML load the picture again each time the switcher opens.
        return f"image://window/{kind}/{win}/{self._switcher_serial}"

    def _apply_switcher(self, view: dict | None) -> None:
        if view is None:
            if self._switcher["open"]:
                # Keep the last geometry so the panel can fade out in place.
                self._switcher = {**self._switcher, "open": False}
                self._switcher_key = None
                self.switcherChanged.emit()
            return
        key = tuple((i["id"], round(i["x"]), round(i["y"])) for i in view["items"])
        u = view["u"]
        if key != self._switcher_key:
            self._switcher_key = key
            self._switcher_serial += 1
            if self._images is not None:
                self._images.refresh(
                    [(i["id"], i["wm_class"]) for i in view["items"]],
                    thumb=(
                        round((view["card_w"] - 2 * _CARD_INSET * u) * _PICTURE_SCALE),
                        round((view["card_h"] - (_CARD_INSET + _CARD_TITLE) * u) * _PICTURE_SCALE),
                    ),
                    badge=round(_CARD_BADGE * u * _PICTURE_SCALE),
                    large=round(_CARD_ICON * u * _PICTURE_SCALE),
                )
            self._switcher_items = [
                {
                    "title": i["title"], "x": i["x"], "y": i["y"], "minimized": i["minimized"], "desktop": i["desktop"],
                    "icon": self._image_url("icon", i["id"]), "thumb": self._image_url("thumb", i["id"]),
                }  # fmt: skip
                for i in view["items"]
            ]
            self.switcherItemsChanged.emit()
        switcher = {
            "open": True, "x": view["x"], "y": view["y"], "w": view["w"], "h": view["h"], "u": u,
            "cardW": view["card_w"], "cardH": view["card_h"], "inset": _CARD_INSET * u, "titleH": _CARD_TITLE * u,
            "badge": _CARD_BADGE * u, "largeIcon": _CARD_ICON * u, "selected": view["selected"], "label": view["label"],
            "side": view.get("side", ""),
        }  # fmt: skip
        if switcher != self._switcher:
            self._switcher = switcher
            self.switcherChanged.emit()
