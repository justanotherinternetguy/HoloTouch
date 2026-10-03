"""Grab a window anywhere on its surface and move it; a second pinching hand resizes it."""

from __future__ import annotations

import logging
from collections import deque

from holowm.core.actions import WindowInfo
from holowm.core.hands import Hand
from holowm.core.interactions.base import Interaction
from holowm.core.overlay_state import FrameView, OverlayState
from holowm.core.poses import Pose

log = logging.getLogger(__name__)

_UNMAXIMIZE_TIMEOUT_S = 0.4
_FLICK_REWIND_S = 0.12
_RECT_HISTORY_S = 0.5


class MoveInteraction(Interaction):
    def __init__(self, engine, hand: Hand, win: WindowInfo, now: float):
        super().__init__(engine)
        self.win_id = win.id
        self.primary = hand.id
        self.secondary: int | None = None
        self.hand_ids = (hand.id,)
        self.min_size = (
            max(win.min_w, self.cfg.gesture.min_window_w),
            max(win.min_h, self.cfg.gesture.min_window_h),
        )
        self.rect = [float(win.x), float(win.y), float(win.w), float(win.h)]
        self._sent: tuple[int, int, int, int] = (win.x, win.y, win.w, win.h)
        self._last_resize = 0.0
        self._rects: deque[tuple[float, tuple[float, float, float, float]]] = deque()
        self._edge_side = 0
        self._edge_since = 0.0
        self._edge_block_until = 0.0
        self._edge_progress = 0.0
        self._started = now
        self._grab_point = (hand.x, hand.y)
        self._dragged = False  # the hand has moved or resized the window, so this is not a tap
        # A hand waved about is misread as pinching for a moment often enough. Until the pinch has
        # lasted, the window is left alone; what is kept here puts it back if the grab is undone.
        self._confirmed = False
        self._origin = (win.x, win.y, win.w, win.h)
        self._was_maximized = win.maximized
        focused = self.backend.active_window()
        self._focus_before = focused.id if focused is not None else None

        # A maximized window ignores geometry requests. It stays put until the hand drags it, is
        # then restored, and is re-anchored under the hand once its restored size is known.
        self._held_maximized = win.maximized
        self._unmaximizing = False
        log.debug("grab %r%s", win.title, " (maximized, held until dragged)" if win.maximized else "")
        self._unmax_deadline = 0.0
        if win.maximized:
            self._grab_rel = ((hand.x - win.x) / max(win.w, 1), (hand.y - win.y) / max(win.h, 1))
            self._offset = (0.0, 0.0)
        else:
            self._offset = (win.x - hand.x, win.y - hand.y)
        self._resize_start: tuple[float, float, float, float, float, float, float, float] | None = None

    # -- helpers -----------------------------------------------------------------------------

    def _pinching(self, hand_id: int | None) -> Hand | None:
        hand = self.engine.tracker.get(hand_id)
        return hand if hand is not None and hand.pose is Pose.PINCH_INDEX else None

    def _free_pinch(self, primary: Hand) -> Hand | None:
        """Another hand that has just pinched and is not doing anything else."""
        for hand in self.engine.tracker.hands.values():
            if hand.id != primary.id and hand.pose is Pose.PINCH_INDEX and hand.armed and not hand.consumed:
                return hand
        return None

    def _anchor_move(self, hand: Hand) -> None:
        self._offset = (self.rect[0] - hand.x, self.rect[1] - hand.y)
        self._resize_start = None
        self.secondary = None
        self.hand_ids = (self.primary,)

    def _begin_resize(self, primary: Hand, secondary: Hand) -> None:
        self.secondary = secondary.id
        self.hand_ids = (primary.id, secondary.id)
        secondary.consumed = True
        self._dragged = True
        x, y, w, h = self.rect
        self._resize_start = (
            abs(secondary.x - primary.x),
            abs(secondary.y - primary.y),
            (primary.x + secondary.x) / 2,
            (primary.y + secondary.y) / 2,
            x + w / 2,
            y + h / 2,
            w,
            h,
        )

    def _send(self, now: float, force: bool = False) -> None:
        x, y, w, h = (round(v) for v in self.rect)
        target = (x, y, w, h)
        if target == self._sent:
            return
        if (w, h) != self._sent[2:] and not force:
            # Apps redraw on every resize, so size changes are rate limited; pure moves are not.
            if now - self._last_resize < 1.0 / self.cfg.gesture.resize_hz:
                return
            self._last_resize = now
        self.backend.move_resize(self.win_id, *target)
        self._sent = target

    def _clamp_position(self) -> None:
        """Keep a strip of the window reachable, as the window manager would."""
        screen_w, screen_h = self.engine.screen
        _, work_y, _, _ = self.backend.workarea()
        keep = 80.0
        self.rect[0] = min(max(self.rect[0], keep - self.rect[2]), screen_w - keep)
        self.rect[1] = min(max(self.rect[1], float(work_y)), screen_h - keep)

    # -- main loop ---------------------------------------------------------------------------

    def update(self, now: float) -> bool:
        win = self.backend.get(self.win_id)
        if win is None:
            return False
        primary = self._pinching(self.primary)
        if primary is not None and not self._dragged:
            radius = self.cfg.gesture.tap_radius * self.engine.screen[1]
            dx, dy = primary.x - self._grab_point[0], primary.y - self._grab_point[1]
            self._dragged = dx * dx + dy * dy > radius * radius
        if not self._confirmed:
            if primary is None:
                self._release(now)
                return False
            if (now - self._started) * 1000.0 < self.cfg.gesture.grab_confirm_ms:
                return True
            # The window now catches up with wherever the hand has got to since the pinch began.
            self._confirmed = True
            self.backend.activate(self.win_id)
        if self._held_maximized:
            if primary is None:
                self._release(now)
                return False
            if win.maximized and not self._dragged and self._free_pinch(primary) is None:
                return True
            self._held_maximized, self._unmaximizing = False, True
            self._unmax_deadline = now + _UNMAXIMIZE_TIMEOUT_S
            log.debug("pulling %r out of maximize", win.title)
            if win.maximized:
                self.backend.set_maximized(self.win_id, False)
            return True
        if self._unmaximizing:
            if win.maximized and now < self._unmax_deadline:
                return primary is not None
            hand = self.engine.tracker.get(self.primary)
            if hand is None:
                return False
            self._unmaximizing = False
            _, work_y, _, _ = self.backend.workarea()
            x = hand.x - self._grab_rel[0] * win.w
            y = max(hand.y - self._grab_rel[1] * win.h, work_y)
            self.rect = [x, y, float(win.w), float(win.h)]
            self._sent = self._origin = (win.x, win.y, win.w, win.h)
            self._anchor_move(hand)

        secondary = self._pinching(self.secondary)
        if primary is None and secondary is not None:
            # The first hand let go mid-resize; the other hand carries on moving the window.
            self.primary, primary, secondary = secondary.id, secondary, None
            self._anchor_move(primary)
        elif primary is None:
            self._release(now)
            return False
        elif self.secondary is not None and secondary is None:
            self._send(now, force=True)
            self._anchor_move(primary)

        if self.secondary is None:
            secondary = self._free_pinch(primary)
            if secondary is not None:
                self._begin_resize(primary, secondary)

        if secondary is not None and self._resize_start is not None:
            dx0, dy0, mx0, my0, cx0, cy0, w0, h0 = self._resize_start
            gain = self.cfg.gesture.resize_gain
            screen_w, screen_h = self.engine.screen
            w = w0 + (abs(secondary.x - primary.x) - dx0) * gain
            h = h0 + (abs(secondary.y - primary.y) - dy0) * gain
            w = min(max(w, self.min_size[0]), screen_w)
            h = min(max(h, self.min_size[1]), screen_h)
            cx = cx0 + (primary.x + secondary.x) / 2 - mx0
            cy = cy0 + (primary.y + secondary.y) / 2 - my0
            self.rect = [cx - w / 2, cy - h / 2, w, h]
            self._edge_side, self._edge_progress = 0, 0.0
        else:
            self.rect[0] = primary.x + self._offset[0]
            self.rect[1] = primary.y + self._offset[1]
            self._edge_carry(primary, now)
        self._clamp_position()

        self._rects.append((now, tuple(self.rect)))
        while self._rects and now - self._rects[0][0] > _RECT_HISTORY_S:
            self._rects.popleft()
        self._send(now)
        return True

    def _edge_carry(self, hand: Hand, now: float) -> None:
        g = self.cfg.gesture
        screen_w = self.engine.screen[0]
        margin = g.edge_margin * screen_w
        side = -1 if hand.x <= margin else 1 if hand.x >= screen_w - 1 - margin else 0
        if side == 0 or now < self._edge_block_until or self.engine.desktop_target(side) is None:
            self._edge_side, self._edge_progress = 0, 0.0
            return
        if side != self._edge_side:
            self._edge_side, self._edge_since = side, now
        self._edge_progress = min((now - self._edge_since) * 1000.0 / g.edge_dwell_ms, 1.0)
        if self._edge_progress >= 1.0:
            target = self.engine.desktop_target(side)
            self.backend.set_window_desktop(self.win_id, target)
            self.engine.switch_desktop(target, now)
            self.backend.activate(self.win_id)
            self._dragged = True
            self._edge_block_until = now + g.edge_cooldown_ms / 1000.0
            self._edge_side, self._edge_progress = 0, 0.0

    def _release(self, now: float) -> None:
        self._send(now, force=True)
        hand = self.engine.tracker.get(self.primary)
        g = self.cfg.gesture
        held_ms = (now - self._started) * 1000.0
        one_hand = hand is not None and self.secondary is None
        # A quick pinch that went nowhere is a tap, which only picks the window out. A pinch
        # lost while the hand is already travelling is not: that is a drag about to resume.
        if one_hand and not self._dragged and held_ms <= g.tap_ms and hand.speed <= g.tap_speed:
            log.debug("tap")
            if self._confirmed:
                self._put_back(now)  # the window may have crept after the hand; a tap moves nothing
            else:
                self.backend.activate(self.win_id)  # a tap picks the window out, however short it was
            return
        if held_ms <= g.grab_undo_ms:
            self._undo(now)
            return
        if not one_hand or not self._dragged:
            return
        (vx, vy), t_peak = hand.peak_velocity(now, g.flick_window_ms / 1000.0)
        screen_h = self.engine.screen[1]
        if abs(vy) / screen_h < g.flick_speed or abs(vy) < g.flick_ratio * abs(vx):
            return
        # Put the window back where it was before the flick carried it along.
        rewind = t_peak - _FLICK_REWIND_S
        rect = next((r for t, r in reversed(self._rects) if t <= rewind), self._rects[0][1] if self._rects else None)
        if rect is not None:
            self.rect = list(rect)
            self._send(now, force=True)
        log.debug("flick %s", "down: minimize" if vy > 0 else "up: maximize")
        if vy > 0:
            self.backend.minimize(self.win_id)
        else:
            self.backend.set_maximized(self.win_id, True)

    def _undo(self, now: float) -> None:
        """Leave the window as the grab found it: a pinch this short was more likely misread than meant."""
        if not self._confirmed:
            return  # nothing was done to it
        log.debug("grab undone: it lasted %.0f ms", (now - self._started) * 1000.0)
        self._put_back(now)
        if self._focus_before not in (None, self.win_id) and self.backend.get(self._focus_before) is not None:
            self.backend.activate(self._focus_before)

    def _put_back(self, now: float) -> None:
        """Give the window the place and size the grab found it with, maximized if it was."""
        pulled_free = self._was_maximized and not self._held_maximized
        if pulled_free or not self._was_maximized:
            self.rect = [float(v) for v in self._origin]
            self._send(now, force=True)
        if pulled_free:
            self.backend.set_maximized(self.win_id, True)

    def decorate(self, overlay: OverlayState) -> None:
        x, y, w, h = self.rect
        resizing = self.secondary is not None
        overlay.frame = FrameView(
            x, y, w, h, "resize" if resizing else "grab", f"{round(w)} × {round(h)}" if resizing else ""
        )
        overlay.edge_side = self._edge_side
        overlay.edge_progress = self._edge_progress
