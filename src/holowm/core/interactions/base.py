from __future__ import annotations

from typing import TYPE_CHECKING

from holowm.core.overlay_state import OverlayState

if TYPE_CHECKING:
    from holowm.core.engine import Engine


class Interaction:
    """A gesture in progress. It owns the hands until update() returns False."""

    def __init__(self, engine: "Engine"):
        self.engine = engine
        self.backend = engine.backend
        self.cfg = engine.cfg
        self.hand_ids: tuple[int, ...] = ()

    def update(self, now: float) -> bool:
        raise NotImplementedError

    def cancel(self) -> None:
        """Abandon the gesture without committing anything further."""

    def decorate(self, overlay: OverlayState) -> None:
        """Add this interaction's visuals to the overlay state."""
