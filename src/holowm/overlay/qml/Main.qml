import QtQuick

// Root of the overlay. `bridge` is the Python Bridge object and `theme` the colours and typefaces;
// everything here is driven by the two.
Item {
    id: root
    readonly property real s: bridge.scale
    readonly property var hands: [bridge.hand0, bridge.hand1]
    // The hand driving the gesture in progress, and the side of the last one that did.
    readonly property var holder: hands.find(hand => hand.visible && hand.active) || null
    property string side: "right"
    onHolderChanged: if (holder) side = holder.side

    WindowFrame {
        frame: bridge.frame
        hands: root.hands
        s: root.s
        quiet: first.quiet && second.quiet
        visible: !bridge.switcher.open  // there the card is the selection
    }
    EdgeBar { anchors.fill: parent; fx: bridge.fx; s: root.s; handY: root.holder ? root.holder.y : height / 2 }
    PieMenu { anchors.fill: parent; s: root.s; side: root.side }
    WindowSwitcher { anchors.fill: parent }
    CloseRing { fx: bridge.fx; s: root.s; reach: bridge.closeRadius * root.height; title: bridge.frame.label; side: root.side }
    HoldRing { fx: bridge.fx; s: root.s }
    ClickPulse { fx: bridge.fx; s: root.s }
    HandCursor {
        id: first
        hand: bridge.hand0
        s: root.s
        closing: bridge.fx.closeProgress > 0 && bridge.hand0.active
        hidden: bridge.fx.knob >= 0 && bridge.hand0.active
    }
    HandCursor {
        id: second
        hand: bridge.hand1
        s: root.s
        closing: bridge.fx.closeProgress > 0 && bridge.hand1.active
        hidden: bridge.fx.knob >= 0 && bridge.hand1.active
    }
    Knob { fx: bridge.fx; s: root.s }
    WorkspaceHud { fx: bridge.fx; s: root.s }
    TrackHud { fx: bridge.fx; s: root.s }
    DictationHud { fx: bridge.fx; s: root.s }
    KeyHud { fx: bridge.fx; s: root.s }
    DebugHud { info: bridge.debug; s: root.s }
    Prompt { prompt: bridge.prompt; s: root.s }
}
