"""Window switcher: a fist touched to the chin lays every window out as a card; a pinch picks one."""

from __future__ import annotations

import math
from dataclasses import dataclass

from holotouch.config import SwitcherConfig
from holotouch.core.actions import ALL_DESKTOPS, WindowInfo
from holotouch.core.hands import Hand
from holotouch.core.interactions.base import Interaction
from holotouch.core.overlay_state import FrameView, OverlayState
from holotouch.core.poses import Pose

# Pixel sizes before ui.scale is applied.
_SCREEN_MARGIN = 24.0
_CAPTION = 46.0
# How far into a neighbouring card (in card widths) the hand must go before the highlight moves.
_STICK = 0.12
# A hand starts pointing once it has slowed to this speed (screen heights/s) and then moved this
# far (screen heights), so a hand that merely happens to be over a card does not pick it.
_SETTLE_SPEED = 0.3
_POINT_TRAVEL = 0.06
# A hand coming off the chin starts slowly; it is not taken to have come to rest for this long.
_OFF_CHIN_S = 0.25


@dataclass(slots=True)
class Grid:
    """Where the panel and its cards sit, in screen pixels."""

    u: float  # ui scale, reduced if the cards would not fit the screen otherwise
    x: float
    y: float
    w: float
    h: float
    card_w: float
    card_h: float
    gap: float
    cards: list[tuple[float, float]]  # top-left corner of each card

    def _distance(self, index: int, px: float, py: float) -> float:
        """How far a point lies outside a card; 0 inside it."""
        x, y = self.cards[index]
        dx = max(x - px, 0.0, px - (x + self.card_w))
        dy = max(y - py, 0.0, py - (y + self.card_h))
        return math.hypot(dx, dy)

    def card_at(self, px: float, py: float) -> int | None:
        """The card nearest a point inside the panel; None for a point outside it."""
        if not (self.x <= px < self.x + self.w and self.y <= py < self.y + self.h):
            return None
        return min(range(len(self.cards)), key=lambda i: self._distance(i, px, py))

    def sticks(self, index: int, px: float, py: float) -> bool:
        """Whether a point is still close enough to a card to keep it highlighted."""
        return self._distance(index, px, py) < self.gap + _STICK * self.card_w


def build_grid(count: int, screen: tuple[int, int], cfg: SwitcherConfig, scale: float) -> Grid:
    """Centred rows of cards in a panel in the middle of the screen."""
    screen_w, screen_h = screen
    card_w, card_h, gap = cfg.card_w, cfg.card_h, cfg.gap  # in units of the ui scale
    pad = 1.5 * gap
    usable_w = screen_w / scale - 2 * _SCREEN_MARGIN
    usable_h = screen_h / scale - 2 * _SCREEN_MARGIN
    fitting = int((usable_w - 2 * pad + gap) // (card_w + gap))
    columns = max(min(cfg.columns, fitting), 1)
    rows = math.ceil(count / columns)
    columns = math.ceil(count / rows)  # even out the rows
    w = columns * card_w + (columns - 1) * gap + 2 * pad
    h = rows * card_h + (rows - 1) * gap + 2 * pad + _CAPTION
    u = scale * min(1.0, usable_w / w, usable_h / h)
    x, y = (screen_w - w * u) / 2, (screen_h - h * u) / 2
    cards = []
    for i in range(count):
        row, column = divmod(i, columns)
        in_row = min(columns, count - row * columns)
        indent = (columns - in_row) * (card_w + gap) / 2
        cards.append((x + (pad + indent + column * (card_w + gap)) * u, y + (pad + row * (card_h + gap)) * u))
    return Grid(u, x, y, w * u, h * u, card_w * u, card_h * u, gap * u, cards)


def _title(win: WindowInfo) -> str:
    return win.title or win.wm_class or "Window"


class SwitcherInteraction(Interaction):
    """Stays open until a pinch picks a card, the chin is touched again, or the hands leave."""

    def __init__(self, engine, windows: list[WindowInfo], now: float):
        super().__init__(engine)
        self.windows = windows
        self.grid = build_grid(len(windows), engine.screen, self.cfg.switcher, self.cfg.ui.scale)
        # Like Alt+Tab, start on the window that was in use before the current one.
        active = self.backend.active_window()
        self.selected: int | None = next(
            (i for i, w in enumerate(windows) if active is None or w.id != active.id), 0
        )
        self._pointer: int | None = None  # the hand whose position set the highlight
        self._rest: dict[int, tuple[float, float]] = {}  # where each hand came to rest
        self._pointing: set[int] = set()  # hands that have since moved on purpose
        self._chin_at = {hand_id: now for hand_id in engine.on_chin}  # when each hand was last on the chin
        self._last_hand = now

    def _points(self, hand: Hand, now: float) -> bool:
        if hand.id in self._pointing:
            return True
        rest = self._rest.get(hand.id)
        if rest is None:
            if hand.speed < _SETTLE_SPEED and now - self._chin_at.get(hand.id, -math.inf) > _OFF_CHIN_S:
                self._rest[hand.id] = (hand.x, hand.y)
        elif math.hypot(hand.x - rest[0], hand.y - rest[1]) > _POINT_TRAVEL * self.engine.screen[1]:
            self._pointing.add(hand.id)
            return True
        return False

    def _point(self, hands: list[Hand], now: float) -> None:
        """Highlight the card under the first pointing hand; none of them over the panel clears it."""
        hands = [h for h in hands if self._points(h, now)]
        if not hands:
            return
        for hand in hands:
            hit = self.grid.card_at(hand.x, hand.y)
            if hit is None:
                continue
            held = self._pointer == hand.id and self.selected is not None
            if not (held and self.grid.sticks(self.selected, hand.x, hand.y)):
                self.selected = hit
            self._pointer = hand.id
            return
        self.selected = self._pointer = None

    def update(self, now: float) -> bool:
        tracked = sorted(self.engine.tracker.hands.values(), key=lambda h: h.id)
        if tracked:
            self._last_hand = now
        elif (now - self._last_hand) * 1000.0 > self.cfg.switcher.idle_close_ms:
            return False
        if self.engine.detect_chin_touch(now):
            return False
        # A hand on the chin is not pointing at anything; it starts afresh once it comes away.
        for hand_id in self.engine.on_chin:
            self._rest.pop(hand_id, None)
            self._pointing.discard(hand_id)
            self._chin_at[hand_id] = now
        hands = [h for h in tracked if h.armed and h.id not in self.engine.on_chin]
        self._point(hands, now)
        for hand in hands:
            if hand.consumed or hand.pose in (Pose.OPEN, Pose.NEUTRAL):
                continue
            hand.consumed = True  # other gestures do nothing while the switcher is open
            if hand.pose is Pose.PINCH_INDEX:
                self._point([hand], now)
                if self.selected is not None:
                    self._switch_to(self.windows[self.selected], now)
                return False
        return True

    def _switch_to(self, win: WindowInfo, now: float) -> None:
        if self.backend.get(win.id) is None:
            return
        # Go to the window rather than letting the window manager bring it here.
        if win.desktop not in (self.backend.current_desktop(), ALL_DESKTOPS):
            self.engine.switch_desktop(win.desktop, now)
        self.backend.activate(win.id)

    def decorate(self, overlay: OverlayState) -> None:
        grid = self.grid
        current = self.backend.current_desktop()
        chosen = self.windows[self.selected] if self.selected is not None else None
        overlay.switcher = {
            "x": grid.x,
            "y": grid.y,
            "w": grid.w,
            "h": grid.h,
            "u": grid.u,
            "card_w": grid.card_w,
            "card_h": grid.card_h,
            "selected": -1 if self.selected is None else self.selected,
            "label": _title(chosen) if chosen is not None else "",
            # The hand that is pointing, for the colour of the highlight.
            "side": self.engine.side(self.engine.tracker.get(self._pointer)) if self._pointer is not None else "",
            "items": [
                {
                    "id": win.id,
                    "title": _title(win),
                    "wm_class": win.wm_class,
                    "x": x,
                    "y": y,
                    "minimized": win.minimized,
                    # 1-based workspace number for a window that is somewhere else, otherwise 0.
                    "desktop": 0 if win.desktop in (current, ALL_DESKTOPS) else win.desktop + 1,
                }
                for win, (x, y) in zip(self.windows, grid.cards)
            ],
        }
        if chosen is not None and not chosen.minimized and chosen.desktop in (current, ALL_DESKTOPS):
            overlay.frame = FrameView(chosen.x, chosen.y, chosen.w, chosen.h, "hover")
