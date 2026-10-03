"""Pie launcher: opened with a thumb+pinky pinch, steered by hand direction, committed on release."""

from __future__ import annotations

from holowm.core.hands import Hand
from holowm.core.interactions.base import Interaction
from holowm.core.overlay_state import OverlayState
from holowm.core.poses import Pose
from holowm.launcher.menu import PieSession, track_direction


class MenuInteraction(Interaction):
    def __init__(self, engine, hand: Hand, now: float):
        super().__init__(engine)
        self.hand_id = hand.id
        self.hand_ids = (hand.id,)
        # Window actions in the menu apply to whatever was under the hand when it opened.
        self.target = self.backend.window_at(hand.x, hand.y) or self.backend.active_window()
        self.session = PieSession(
            engine.launcher.build(), hand.x, hand.y, self.cfg.pie, self.cfg.ui.scale, engine.screen
        )

    def update(self, now: float) -> bool:
        hand = self.engine.tracker.get(self.hand_id)
        if hand is None:
            return False
        if hand.pose is not Pose.PINCH_PINKY:
            item = self.session.release()
            if item is not None:
                target = self.backend.get(self.target.id) if self.target else None
                self.engine.launcher.activate(item, target)
                if item.type == "workspace":
                    self.engine.show_hud(now, int(item.data))
                elif item.type == "track":
                    self.engine.show_track(now, track_direction(item))
            return False
        self.session.update(hand.x, hand.y)
        return True

    def decorate(self, overlay: OverlayState) -> None:
        overlay.menu = self.session.view()
