"""The interaction engine: turns tracked hands into window-manager commands and overlay state."""

from __future__ import annotations

import logging
import math
import re

from holowm.config import Config
from holowm.core.actions import ALL_DESKTOPS, WindowBackend, WindowInfo
from holowm.core.claps import Claps, palm_gap
from holowm.core.face import FaceTrack
from holowm.core.hands import Hand, HandTracker
from holowm.core.letters import LetterModel, model_path
from holowm.core.interactions import (
    CameraInteraction,
    ClickInteraction,
    CloseInteraction,
    DictateInteraction,
    Interaction,
    MenuInteraction,
    MoveInteraction,
    ScrollInteraction,
    KnobInteraction,
    SpellInteraction,
    SwitcherInteraction,
)
from holowm.core.overlay_state import FrameView, HandView, OverlayState
from holowm.core.poses import Pose
from holowm.launcher.apps import installed_apps
from holowm.launcher.launch import Launcher
from holowm.launcher.macros import Macro, Macros
from holowm.tracker.types import FrameSample

log = logging.getLogger(__name__)

_SWIPE_REARM_SPEED = 0.3  # screen heights/s; a hand must slow below this before swiping again
_FOCUS_HISTORY = 64
# A hand resting on the chin stays "on the chin" until it is this far past the limits it met. A
# fist as far past the depth limit is not surely on the chin, but too near the face to close a window.
_CHIN_SLACK = 1.2
# How long a hand must be off the chin before it has left: when it is seen elsewhere, and when it
# has dropped out of tracking (which a hand against the face often does).
_CHIN_LEFT_S = 0.2
_CHIN_LOST_S = 1.0
_CLICK_SHOWN_S = 0.3  # how long the overlay marks where the mouse button went down
_CLICK_AGAIN_S = 1.0  # a press this soon after the last, at the same place, lands exactly on it
_CLAP_REACH = 0.35  # metres; hands nearer each other than this are clapping, or about to, not swiping


class Engine:
    def __init__(
        self, cfg: Config, backend: WindowBackend, launcher: Launcher | None = None, macros: Macros | None = None
    ):
        self.cfg = cfg
        self.backend = backend
        self.launcher = launcher or Launcher(backend)
        if macros is None:
            macros = Macros(backend, apps=installed_apps() if cfg.spell.apps else [])
        self.macros = macros  # what the launcher opens: the macros, and the installed apps
        self.letters = self._letter_model() if self.macros else None  # with nothing to spell, nothing is read
        self.screen = backend.screen_size()
        self.tracker = HandTracker(cfg, self.screen)
        self.face = FaceTrack(cfg)
        self.claps = Claps(cfg.gesture)
        self.active: Interaction | None = None
        self.overlay = OverlayState()
        self.paused = False
        self.acting = True  # False: hands are tracked and drawn, but no gesture is started
        # Set when the camera app is asked for. Whoever runs the engine opens it, and clears this.
        self.camera_wanted = False
        self.latency_ms = 0.0
        self._hud_until = 0.0
        self._hud_desktop = -1
        self._track = 0  # the way the last track was skipped, shown until _track_until
        self._track_until = 0.0
        self._swipe_block_until = 0.0
        self._key = ""  # the key last pressed by a gesture, shown until _key_until
        self._key_until = 0.0
        self._spelt = ("", "", "")  # how spelling last ended, what was spelt and what it opened, shown until _spelt_until
        self._spelt_until = 0.0
        self._focus_order: list[int] = []  # window ids, most recently focused first
        self._chin_since: float | None = None  # when a hand not yet acted on came to the chin
        self._chin_held = False  # a hand is still resting there after being acted on
        self._chin_hands: set[int] = set()  # the hands last seen there
        self._chin_seen = 0.0
        self.on_chin: set[int] = set()  # the hands there now
        self._click = (0.0, 0.0)  # where the mouse button last went down, and when
        self._click_time = -math.inf

    # -- input -------------------------------------------------------------------------------

    def on_frame(self, frame: FrameSample) -> None:
        if not self.paused:
            self.tracker.update(frame)
            self.claps.update(list(self.tracker.hands.values()), frame.t_capture)
            if frame.face is not None:
                self.face.update(frame.face, frame.t_capture)

    def set_paused(self, paused: bool) -> None:
        if paused == self.paused:
            return
        self.paused = paused
        if paused:
            self.cancel_active()
            self.tracker.hands.clear()
            self.claps.reset()
        log.info("paused" if paused else "resumed")

    def cancel_active(self) -> None:
        """Abandon any gesture in progress, leaving windows where they are."""
        if self.active is not None:
            self.active.cancel()
            self.active = None

    # -- workspace helpers shared by interactions ---------------------------------------------

    def desktop_target(self, delta: int) -> int | None:
        count = self.backend.desktop_count()
        target = self.backend.current_desktop() + delta
        if self.cfg.gesture.wrap_workspaces and count:
            return target % count
        return target if 0 <= target < count else None

    def switch_desktop(self, index: int, now: float) -> None:
        self.backend.switch_desktop(index)
        self.show_hud(now, index)

    def show_hud(self, now: float, desktop: int) -> None:
        self._hud_desktop = desktop
        self._hud_until = now + self.cfg.ui.hud_ms / 1000.0

    def show_track(self, now: float, direction: int) -> None:
        """Say for a moment that a track was skipped: 1 to the next one, -1 to the one before."""
        self._track = direction
        self._track_until = now + self.cfg.ui.hud_ms / 1000.0

    @property
    def dictating(self) -> bool:
        """Whether the microphone is wanted: whoever runs the engine records it, and types what was said."""
        return isinstance(self.active, DictateInteraction)

    # -- spelling --------------------------------------------------------------------------

    def _letter_model(self) -> LetterModel:
        path = model_path(self.cfg.spell.model)
        try:
            return LetterModel.load(path)
        except Exception as exc:  # missing, or not a model: numpy says so in half a dozen ways
            raise ValueError(f"[spell] model: cannot read {path} ({getattr(exc, 'strerror', None) or exc})") from None

    def spelling_over(self, now: float, spelt: str, macro: Macro | None) -> None:
        """Run the macro that was spelt, or open the app, if one was, and say for a moment how it ended."""
        if macro is not None:
            self.macros.run(macro)
        elif not spelt:
            return  # begun and let go of with nothing spelt: there is nothing to say
        self._spelt = ("done" if macro is not None else "failed", spelt.upper(), macro.name if macro is not None else "")
        self._spelt_until = now + self.cfg.ui.hud_ms / 1000.0

    # -- clicking --------------------------------------------------------------------------

    def click_point(self, hand: Hand, now: float) -> tuple[float, float]:
        """Where a press by this hand lands: under its cursor, or on its last click if it is at that again.

        A double click has to land twice within a few pixels, which a hand cannot do unaided.
        """
        at = self._click
        again = now - self._click_time <= _CLICK_AGAIN_S and math.hypot(hand.x - at[0], hand.y - at[1]) <= self.click_slop
        if not again:
            at = (hand.x, hand.y)
        self._click, self._click_time = at, now
        return at

    @property
    def click_slop(self) -> float:
        return self.cfg.gesture.click_slop * self.screen[1]

    # -- window switcher ---------------------------------------------------------------------

    def _track_focus(self) -> None:
        active = self.backend.active_window()
        if active is not None and self._focus_order[:1] != [active.id]:
            others = [i for i in self._focus_order if i != active.id]
            self._focus_order = [active.id, *others][:_FOCUS_HISTORY]

    def switcher_windows(self) -> list[WindowInfo]:
        """The windows to offer, most recently used first."""
        windows = self.backend.all_windows()
        if not self.cfg.switcher.all_workspaces:
            current = self.backend.current_desktop()
            windows = [w for w in windows if w.desktop in (current, ALL_DESKTOPS)]
        # Windows not focused since HoloWM started keep their stacking order, after the rest.
        rank = {win_id: n for n, win_id in enumerate(self._focus_order)}
        return sorted(windows, key=lambda w: rank.get(w.id, len(rank)))

    def _open_switcher(self, now: float) -> None:
        windows = self.switcher_windows()
        if windows:
            self.active = SwitcherInteraction(self, windows, now)

    # -- fist to chin ------------------------------------------------------------------------

    def _on_chin(self, hand: Hand) -> bool:
        """Whether a closed hand rests on the chin: beside it in the picture, and level with the face."""
        g = self.cfg.gesture
        slack = _CHIN_SLACK if self._chin_held else 1.0
        if self.face.reach(hand) > g.chin_reach * slack:
            return False
        closeness = self.face.closeness(hand)
        # A fist against the face is partly hidden and seldom reads as the fist pose, so the
        # fingers are held to a looser limit here.
        if max(hand.features.curl) <= g.chin_curl * slack and closeness <= g.chin_depth * slack:
            return True
        if hand.pose is Pose.FIST and closeness <= g.chin_depth * _CHIN_SLACK:
            hand.consumed = True  # not surely a touch, but too near the face to close a window
        return False

    def detect_chin_touch(self, now: float) -> bool:
        """True once each time a closed hand comes to rest on the chin."""
        self.on_chin = set()
        if not self.face.visible(now):
            self._chin_since = None
            return False
        touching = [h for h in self.tracker.hands.values() if self._on_chin(h)]
        for hand in touching:
            hand.consumed = True  # whatever pose it reads as there, it starts nothing else
        self.on_chin = {h.id for h in touching}
        if not touching:
            self._chin_since = None
            # A hand that is still tracked has moved away; one that has vanished may only be
            # hidden against the face, and gets longer to come back.
            elsewhere = any(self.tracker.get(hand_id) is not None for hand_id in self._chin_hands)
            if now - self._chin_seen > (_CHIN_LEFT_S if elsewhere else _CHIN_LOST_S):
                self._chin_held = False
            return False
        self._chin_hands = self.on_chin
        self._chin_seen = now
        if self._chin_held:
            return False
        if self._chin_since is None:
            self._chin_since = now
        if (now - self._chin_since) * 1000.0 < self.cfg.gesture.chin_hold_ms:
            return False
        self._chin_held = True
        log.debug("fist to chin")
        return True

    # -- the peace sign with both hands ------------------------------------------------------

    def _peace_hands(self) -> list[Hand] | None:
        """Both hands, if each is holding up two fingers."""
        hands = sorted(self.tracker.hands.values(), key=lambda h: h.id)
        if len(hands) == 2 and all(hand.armed and hand.pose is Pose.TWO_FINGER for hand in hands):
            return hands
        return None

    # -- tick --------------------------------------------------------------------------------

    def tick(self, now: float) -> OverlayState:
        self.backend.poll()
        self._track_focus()
        self.tracker.step(now)
        if not self.paused and self.acting:
            # The first hand to hold up two fingers begins to scroll. The second one doing the same
            # makes it the sign held with both hands, which takes over.
            if isinstance(self.active, ScrollInteraction) and self._peace_hands() is not None:
                self.cancel_active()
            was_active = self.active
            if self.active is not None and not self.active.update(now):
                log.debug("end %s", type(self.active).__name__)
                # The follow-through of a release is not a swipe: those hands must slow down first.
                for hand_id in self.active.hand_ids:
                    hand = self.tracker.get(hand_id)
                    if hand is not None:
                        hand.swipe_ready = False
                self.active = None
            if self.active is None and self.detect_chin_touch(now):
                self._open_switcher(now)
            if self.active is None:
                self._try_begin(now)
            if self.active is None:
                self._on_swipe(now)
            # A clap made while a gesture is going on is no clap: those hands are busy.
            if self.claps.take() and self.active is None:
                self._on_claps(now)
            if self.active is not None and self.active is not was_active:
                log.debug("begin %s", type(self.active).__name__)
        self._build_overlay(now)
        self.backend.flush()
        return self.overlay

    def _try_begin(self, now: float) -> None:
        for hand in self.tracker.hands.values():
            if now < hand.quiet_until:
                hand.consumed = True
        both = self._peace_hands()
        if both is not None and not all(hand.consumed for hand in both):
            for hand in both:
                hand.consumed = True
            self.active = CameraInteraction(self, both, now)
            return
        for hand in sorted(self.tracker.hands.values(), key=lambda h: h.id):
            if not hand.armed or hand.consumed:
                continue
            if hand.pose is Pose.PINCH_INDEX:
                hand.consumed = True
                win = self.backend.window_at(hand.x, hand.y)
                if win is not None and not win.fullscreen:
                    self.active = MoveInteraction(self, hand, win, now)
            elif hand.pose is Pose.PRESS:
                hand.consumed = True
                self.active = ClickInteraction(self, hand, now)
            elif hand.pose is Pose.PINCH_PINKY:
                hand.consumed = True
                self.active = MenuInteraction(self, hand, now)
            elif hand.pose is Pose.FIST:
                hand.consumed = True
                win = self.backend.window_at(hand.x, hand.y)
                if win is not None:
                    self.active = CloseInteraction(self, hand, win, now)
            elif hand.pose is Pose.TWO_FINGER:
                hand.consumed = True
                self.active = ScrollInteraction(self, hand, now)
            elif hand.pose is Pose.CLAW:
                hand.consumed = True
                left = self.side(hand) == "left"
                self.active = KnobInteraction(self, hand, now, "brightness" if left else "volume")
            elif hand.pose is Pose.Y_SIGN:
                hand.consumed = True
                self.active = DictateInteraction(self, hand, now)
            elif hand.pose is Pose.ILY:
                hand.consumed = True
                if self.macros:
                    self.active = SpellInteraction(self, hand, now)
            if self.active is not None:
                return

    def detect_swipe(self, now: float) -> bool:
        """True once for each fast open-palm stroke to the right, as it completes."""
        g = self.cfg.gesture
        # Hands that are near each other, or have just parted, are clapping: each one sweeps
        # sideways as it comes and as it goes.
        hands = list(self.tracker.hands.values())
        if now - self.claps.met_at < g.swipe_cooldown_ms / 1000.0 or (len(hands) == 2 and palm_gap(*hands) < _CLAP_REACH):
            return False
        for hand in hands:
            if not hand.swipe_ready:
                if hand.speed < _SWIPE_REARM_SPEED:
                    hand.swipe_ready, hand.swipe_since = True, now
                continue
            if now < self._swipe_block_until or not hand.armed or hand.pose is not Pose.OPEN:
                continue
            if hand.features.facing < g.swipe_min_facing:
                continue
            # Only motion made with the open palm counts, and it is measured from as far left as
            # the hand went: a hand is often drawn back that way first.
            start = max(now - g.swipe_window_ms / 1000.0, hand.pose_since, hand.swipe_since)
            x0, y0 = min(((x, y) for t, x, y in hand.history if t >= start), default=(hand.ux, hand.uy))
            dx, dy = hand.ux - x0, hand.uy - y0
            if dx < g.swipe_min_travel * self.screen[0] or dx < g.swipe_ratio * abs(dy):
                continue
            hand.swipe_ready = False
            self._swipe_block_until = now + g.swipe_cooldown_ms / 1000.0
            return True
        return False

    def _on_swipe(self, now: float) -> None:
        if self.detect_swipe(now):
            log.debug("swipe to the right: Enter")
            self.backend.press_key("Return")
            self._key, self._key_until = "Enter", now + self.cfg.ui.hud_ms / 1000.0

    def _on_claps(self, now: float) -> None:
        """Two claps: a new tab, if it is a web browser that has the keyboard."""
        win = self.backend.active_window()
        words = set(re.findall(r"[a-z0-9]+", win.wm_class.lower())) if win is not None else set()
        if not words & set(self.cfg.gesture.clap_browsers.lower().replace(",", " ").split()):
            log.debug("two claps, but %r is no web browser", win.wm_class if win is not None else None)
            return
        log.debug("two claps: a new tab in %s", win.wm_class)
        self.backend.press_key("ctrl+t")
        self._key, self._key_until = "New tab", now + self.cfg.ui.hud_ms / 1000.0

    def side(self, hand: Hand | None) -> str:
        """Which of the user's hands this is: "left" or "right"."""
        # The frame is mirrored, which makes the tracker name each hand as the other one.
        return "left" if hand is not None and (hand.handedness == "Right") == self.cfg.camera.mirror else "right"

    # -- overlay -----------------------------------------------------------------------------

    def _build_overlay(self, now: float) -> None:
        overlay = OverlayState(paused=self.paused)
        owners = self.active.hand_ids if self.active is not None else ()
        hover: Hand | None = None
        for hand in sorted(self.tracker.hands.values(), key=lambda h: h.id):
            overlay.hands.append(
                HandView(
                    hand.id, hand.x, hand.y, hand.pinch, hand.pose.value, hand.id in owners, hand.armed,
                    side=self.side(hand),
                )  # fmt: skip
            )
            if hover is None and hand.armed:
                hover = hand
        if self.active is not None:
            self.active.decorate(overlay)
        elif hover is not None:
            win = self.backend.window_at(hover.x, hover.y)
            if win is not None and not win.fullscreen:
                overlay.frame = FrameView(win.x, win.y, win.w, win.h, "hover", side=self.side(hover))
        if now < self._hud_until:
            overlay.hud_desktop = self._hud_desktop
            overlay.hud_count = self.backend.desktop_count()
        if now < self._track_until:
            overlay.track = self._track
        if now < self._key_until:
            overlay.key = self._key
        if not overlay.spell and now < self._spelt_until:
            overlay.spell, overlay.spell_letters, overlay.spell_name = self._spelt
        if now - self._click_time < _CLICK_SHOWN_S:
            overlay.click, (overlay.click_x, overlay.click_y) = True, self._click
        self.overlay = overlay
