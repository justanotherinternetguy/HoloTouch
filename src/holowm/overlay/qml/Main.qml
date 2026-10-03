import QtQuick

// Root of the overlay. `bridge` is the Python Bridge object; everything here is driven by it.
Item {
    id: root
    readonly property real s: bridge.scale
    readonly property color accent: bridge.accent
    readonly property color danger: bridge.danger

    WindowFrame { frame: bridge.frame; s: root.s; accent: root.accent; danger: root.danger }
    EdgeGlow { anchors.fill: parent; fx: bridge.fx; s: root.s; accent: root.accent }
    PieMenu { anchors.fill: parent; s: root.s; accent: root.accent }
    WindowSwitcher { anchors.fill: parent; accent: root.accent }
    CloseRing { fx: bridge.fx; s: root.s; danger: root.danger }
    Knob { fx: bridge.fx; s: root.s; accent: root.accent }
    HoldRing { fx: bridge.fx; s: root.s; accent: root.accent }
    ClickPulse { fx: bridge.fx; s: root.s; accent: root.accent }
    HandCursor { hand: bridge.hand0; s: root.s; accent: root.accent; danger: root.danger }
    HandCursor { hand: bridge.hand1; s: root.s; accent: root.accent; danger: root.danger }
    WorkspaceHud { fx: bridge.fx; s: root.s; accent: root.accent }
    TrackHud { fx: bridge.fx; s: root.s; accent: root.accent }
    DebugHud { info: bridge.debug; s: root.s; accent: root.accent }
    Prompt { prompt: bridge.prompt; s: root.s; accent: root.accent }
}
