"""What the QML layer is told about the window switcher. Needs no display."""

from holowm.config import Config
from holowm.core.overlay_state import OverlayState
from holowm.overlay.bridge import Bridge


class StubImages:
    def __init__(self, have):
        self.have = set(have)
        self.calls = []

    def refresh(self, windows, thumb, badge, large):
        self.calls.append((windows, thumb, badge, large))

    def get(self, kind, win):
        return object() if (kind, win) in self.have else None


def view(selected=1):
    items = [
        {"id": 10, "title": "one", "wm_class": "One", "x": 100.0, "y": 200.0, "minimized": False, "desktop": 0},
        {"id": 20, "title": "two", "wm_class": "Two", "x": 500.0, "y": 200.0, "minimized": True, "desktop": 3},
    ]
    return {
        "x": 60.0, "y": 160.0, "w": 800.0, "h": 400.0, "u": 2.0, "card_w": 300.0, "card_h": 250.0,
        "selected": selected, "label": "two" if selected == 1 else "", "items": items,
    }  # fmt: skip


def test_switcher_items_carry_picture_urls_only_for_pictures_that_exist():
    images = StubImages({("thumb", 10), ("icon", 10), ("icon", 20)})
    bridge = Bridge(Config(), images)
    bridge.apply(OverlayState(switcher=view()))
    one, two = bridge.switcherItems
    assert one["thumb"] == "image://window/thumb/10/1" and one["icon"] == "image://window/icon/10/1"
    assert two["thumb"] == "" and two["icon"] == "image://window/icon/20/1"
    assert (two["minimized"], two["desktop"]) == (True, 3)
    state = bridge.switcher
    assert state["open"] and state["selected"] == 1 and state["label"] == "two"
    # Pictures are requested once, sized to the part of the card they fill.
    windows, thumb, badge, large = images.calls[0]
    assert windows == [(10, "One"), (20, "Two")]
    assert thumb[0] < 300 * 1.1 and thumb[1] < 250 * 1.1 and badge < large
    assert thumb == (round((300 - state["inset"] * 2) * 1.1), round((250 - state["inset"] - state["titleH"]) * 1.1))


def test_switcher_only_reloads_pictures_when_it_reopens():
    images = StubImages({("icon", 10)})
    bridge = Bridge(Config(), images)
    changes = []
    bridge.switcherItemsChanged.connect(lambda: changes.append("items"))
    bridge.switcherChanged.connect(lambda: changes.append("state"))
    bridge.apply(OverlayState(switcher=view()))
    bridge.apply(OverlayState(switcher=view()))  # nothing changed: no signals, no reload
    assert changes == ["items", "state"] and len(images.calls) == 1
    bridge.apply(OverlayState(switcher=view(selected=-1)))  # only the highlight moved
    assert changes == ["items", "state", "state"] and len(images.calls) == 1
    bridge.apply(OverlayState())
    # Closed, but the geometry stays so the panel can fade out where it was.
    assert not bridge.switcher["open"] and bridge.switcher["w"] == 800.0 and len(bridge.switcherItems) == 2
    bridge.apply(OverlayState(switcher=view()))
    assert len(images.calls) == 2
    assert bridge.switcherItems[0]["icon"] == "image://window/icon/10/2"
