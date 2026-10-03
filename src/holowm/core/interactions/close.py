"""Close a window by holding a still fist over it until the progress ring completes."""

from __future__ import annotations

from holowm.core.actions import WindowInfo
from holowm.core.hands import Hand
from holowm.core.interactions.base import Interaction
from holowm.core.overlay_state import FrameView, OverlayState
from holowm.core.poses import Pose


class CloseInteraction(Interaction):
    def __init__(self, engine, hand: Hand, win: WindowInfo, now: float):
        super().__init__(engine)
        self.hand_id = hand.id
        self.hand_ids = (hand.id,)
        self.win_id = win.id
        self.started = now
        self.origin = (hand.x, hand.y)
        self.progress = 0.0

    def update(self, now: float) -> bool:
        hand = self.engine.tracker.get(self.hand_id)
        win = self.backend.get(self.win_id)
        if hand is None or win is None or hand.pose is not Pose.FIST:
            return False
        radius = self.cfg.gesture.close_radius * self.engine.screen[1]
        if (hand.x - self.origin[0]) ** 2 + (hand.y - self.origin[1]) ** 2 > radius * radius:
            return False
        self.progress = (now - self.started) * 1000.0 / self.cfg.gesture.close_dwell_ms
        if self.progress >= 1.0:
            self.backend.close(self.win_id)
            return False
        return True

    def decorate(self, overlay: OverlayState) -> None:
        win = self.backend.get(self.win_id)
        hand = self.engine.tracker.get(self.hand_id)
        if win is None or hand is None:
            return
        overlay.frame = FrameView(win.x, win.y, win.w, win.h, "close")
        overlay.close_progress = min(self.progress, 1.0)
        overlay.close_x, overlay.close_y = hand.x, hand.y
