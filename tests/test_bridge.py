"""What the QML layer is told about the window switcher. Needs no display."""

from holowm.config import Config
from holowm.core.overlay_state import FrameView, HandView, OverlayState
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


def hand(hand_id, side, active=False):
    return HandView(hand_id, 100.0 * hand_id, 200.0, 1.0 if active else 0.0, "pinch_index" if active else "neutral", active, True, side=side)


def test_each_cursor_knows_which_hand_it_is():
    bridge = Bridge(Config())
    bridge.apply(OverlayState(hands=[hand(1, "left"), hand(2, "right")]))
    assert (bridge.hand0["side"], bridge.hand1["side"]) == ("left", "right")
    assert not bridge.hand0["lost"] and bridge.hand0["visible"]


def test_a_hand_that_vanishes_while_holding_a_window_is_lost_and_so_is_its_frame():
    bridge = Bridge(Config())
    held = OverlayState(hands=[hand(1, "left"), hand(2, "right", active=True)], frame=FrameView(10, 20, 300, 200, "grab", side="right"))
    bridge.apply(held)
    assert bridge.frame["side"] == "right" and not bridge.frame["lost"]
    bridge.apply(OverlayState(hands=[hand(1, "left")]))
    # The cursor stays where the hand was last seen, and says it was holding something.
    assert not bridge.hand1["visible"] and bridge.hand1["lost"] and bridge.hand1["x"] == 200.0
    assert not bridge.frame["visible"] and bridge.frame["lost"]
    bridge.apply(OverlayState(hands=[hand(1, "left")]))
    assert bridge.hand1["lost"] and bridge.frame["lost"]  # still so while they fade
    # A hand that only leaves, holding nothing, is not: nor is a window that was let go of.
    bridge.apply(held)
    bridge.apply(OverlayState(hands=[hand(1, "left"), hand(2, "right")]))
    assert not bridge.frame["lost"]
    bridge.apply(OverlayState(hands=[hand(1, "left")]))
    assert not bridge.hand1["visible"] and not bridge.hand1["lost"]


def test_menu_items_say_what_kind_of_thing_they_do():
    from holowm.launcher.launch import default_menu
    from holowm.launcher.menu import PieSession

    cfg = Config()
    bridge = Bridge(cfg)
    session = PieSession(default_menu(4), 800, 500, cfg.pie, 1.0, (1920, 1080))
    bridge.apply(OverlayState(menu=session.view()))
    kinds = {item["name"]: item["kind"] for item in bridge.menuItems}
    assert kinds["Terminal"] == "launch" and kinds["Window"] == "more" and kinds["Workspaces"] == "more"
    window = next(item for item in session.stack[0].menu.children if item.name == "Window")
    session._push(window, 800, 500, 90.0)
    bridge.apply(OverlayState(menu=session.view()))
    kinds = {item["name"]: item["kind"] for item in bridge.menuItems}
    assert kinds["Close"] == "close" and kinds["Maximize"] == "window"


def test_a_resize_carries_the_outline_it_began_with():
    bridge = Bridge(Config())
    bridge.apply(OverlayState(frame=FrameView(10, 20, 300, 200, "resize", "300 × 200", ghost=(35, 40, 250, 160))))
    assert bridge.frame["ghost"] == [35, 40, 250, 160] and bridge.frame["side"] == ""
