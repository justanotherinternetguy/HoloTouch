import QtQuick

// Ripple where the mouse button has just gone down.
Rectangle {
    id: root
    property var fx
    property real s: 1
    property color accent
    readonly property bool shown: fx.click
    onShownChanged: if (shown) { x = fx.clickX - width / 2; y = fx.clickY - height / 2; pulse.restart() }

    width: 64 * s
    height: width
    radius: width / 2
    color: "transparent"
    border.color: accent
    border.width: 4 * s
    opacity: 0

    ParallelAnimation {
        id: pulse
        NumberAnimation { target: root; property: "scale"; from: 0.3; to: 1.3; duration: 350; easing.type: Easing.OutCubic }
        NumberAnimation { target: root; property: "opacity"; from: 1; to: 0; duration: 350 }
    }
}
