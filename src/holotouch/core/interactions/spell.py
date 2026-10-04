"""Spell: the sign for "I love you" opens the launcher, and the letters the hand then makes pick what it opens.

A hand spelling R holds up two fingers, which scroll, and one spelling S makes a fist, which
closes a window. So letters are only read here, between the sign that begins spelling and its
end, and nothing else starts meanwhile.

Only the letters that carry on toward some macro or app are looked for. A letter is taken once
the hand has kept it up for a while. A macro is spelt in full, and an app by its name until no
other begins the same way. What has been picked is opened at once if it can be nothing longer,
and otherwise after a short wait for more letters.
"""

from __future__ import annotations

import math

import numpy as np

from holotouch.core.hands import Hand
from holotouch.core.interactions.base import Interaction
from holotouch.core.letters import REST, letter_features
from holotouch.core.overlay_state import OverlayState
from holotouch.core.poses import Pose
from holotouch.launcher.apps import covered, spelling
from holotouch.launcher.macros import Macro

_SMOOTH_S = 0.08  # readings are averaged over about this long, so that one odd frame changes nothing
_SURE = 0.5  # the hand is shown as a letter when it looks at least this much like it
_LET_GO_S = 0.4  # the sign that began it has been let go of once the hand has been something else for this long
_SHOWN = 6  # how many macros and apps the launcher lists at most


class SpellInteraction(Interaction):
    def __init__(self, engine, hand: Hand, now: float):
        super().__init__(engine)
        self.hand_id = hand.id
        self.hand_ids = (hand.id,)
        self.spelt = ""
        self.guess = ""  # the letter the hand most looks like now, if it clearly looks like one
        self.holding = ""  # the letter being held, of those that would carry on toward a macro or app
        self.progress = 0.0  # how far it has got toward counting
        self.opening = 0.0  # how far the wait for more letters has got, before what was picked is opened
        self._holding_since = now
        self._last = now  # when the last letter was taken, or spelling began
        self._frame = hand.last_seen  # the newest camera frame read
        self._shares: np.ndarray | None = None  # how much the hand looks like each letter, smoothed
        self._off_sign_since: float | None = None
        self._let_go = False  # of the sign that began this: made a second time, it takes it all back
        # The last letter cannot be taken again until the hand has been something else for a while.
        self._elsewhere_since: float | None = None
        self._again = True
        self._narrow()

    def update(self, now: float) -> bool:
        hand = self.engine.tracker.get(self.hand_id)
        if hand is None:
            return self._end(now, None)
        if hand.last_seen != self._frame:
            dt, self._frame = hand.last_seen - self._frame, hand.last_seen
            if hand.pose is Pose.ILY:
                if self._let_go:
                    return self._end(now, hand, run=False)
                self._off_sign_since = None
                self.holding, self.guess, self.progress = "", "", 0.0
            else:
                if self._off_sign_since is None:
                    self._off_sign_since = hand.last_seen
                self._let_go = self._let_go or hand.last_seen - self._off_sign_since >= _LET_GO_S
                if self._read(hand, dt):
                    self._last = now
                    self._narrow()
                    if not self._wanted:
                        return self._end(now, hand)
        cfg = self.cfg.spell
        waited = (now - self._last) * 1000.0
        self.opening = min(waited / cfg.settle_ms, 1.0) if self._chosen is not None else 0.0
        if self.progress > 0.0:
            return True  # a letter is on its way
        if waited >= (cfg.settle_ms if self._chosen is not None else cfg.timeout_ms):
            return self._end(now, hand)
        return True

    def _narrow(self) -> None:
        """Work out what the letters taken so far leave within reach. It changes only when one is taken."""
        macros, count = self.engine.macros, len(self.spelt)
        self._wanted = macros.next_letters(self.spelt)
        self._chosen = macros.chosen(self.spelt)  # what would be opened if no more letters came
        within = sorted(macros.toward(self.spelt), key=lambda macro: macro is not self._chosen)
        self._options = [self._option(macro, count, macro is self._chosen) for macro in within[:_SHOWN]]
        self._more = len(within) - len(self._options)

    @staticmethod
    def _option(macro: Macro, count: int, chosen: bool) -> dict:
        """A row of the launcher: a name, and how much of it has been spelt, or of its letters where those are no name."""
        named = spelling(macro.name) == macro.letters
        return {
            "name": macro.name,
            "icon": macro.icon,
            "code": "" if named else macro.letters.upper(),
            "done": covered(macro.name, count) if named else count,
            "chosen": chosen,
        }

    def _read(self, hand: Hand, dt: float) -> bool:
        """Read the hand in its newest frame. True if a letter was taken."""
        cfg = self.cfg.spell
        model, t = self.engine.letters, hand.last_seen
        shares = model.probabilities(letter_features(hand.landmarks, self.cfg.camera.width / self.cfg.camera.height))
        if self._shares is None:
            self._shares = shares
        else:
            self._shares = self._shares + (1.0 - math.exp(-max(dt, 0.0) / _SMOOTH_S)) * (shares - self._shares)
        looks = dict(zip(model.classes, self._shares.tolist()))
        top = max(looks, key=looks.get)
        self.guess = top if looks[top] >= _SURE and top != REST else ""

        last = self.spelt[-1:]
        if self.guess != last:
            if self._elsewhere_since is None:
                self._elsewhere_since = t
            self._again = self._again or (t - self._elsewhere_since) * 1000.0 >= cfg.repeat_ms
        else:
            self._elsewhere_since = None

        wanted = {letter for letter in self._wanted if self._again or letter != last}
        holding = max(wanted, key=lambda letter: looks.get(letter, 0.0), default="")
        if holding and looks.get(holding, 0.0) < cfg.min_confidence:
            holding = ""
        if holding != self.holding:
            self.holding, self._holding_since = holding, t
        held = (t - self._holding_since) * 1000.0
        self.progress = min(held / cfg.hold_ms, 1.0) if holding else 0.0
        if not holding or held < cfg.hold_ms:
            return False
        self.spelt += holding
        self.holding, self.progress = "", 0.0
        self._again, self._elsewhere_since = False, None
        return True

    def _end(self, now: float, hand: Hand | None, run: bool = True) -> bool:
        if hand is not None:
            # Whatever the hand is left as, its last letter or the sign, starts nothing by itself.
            hand.consumed = True
            hand.quiet_until = now + self.cfg.spell.rest_ms / 1000.0
        self.engine.spelling_over(now, self.spelt, self._chosen if run else None)
        return False

    def decorate(self, overlay: OverlayState) -> None:
        overlay.spell = "spelling"
        overlay.spell_letters = self.spelt.upper()
        overlay.spell_guess = self.guess.upper()
        overlay.spell_holding = self.holding.upper()
        overlay.spell_hold = self.progress
        overlay.spell_options = self._options
        overlay.spell_more = self._more
        overlay.spell_opening = self.opening
