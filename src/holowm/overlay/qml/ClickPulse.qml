import QtQuick

// Ripple where the mouse button has just gone down.
Item {
    id: root
    property var fx
    property real s: 1
    readonly property bool shown: fx.click
    onShownChanged: if (shown) { x = fx.clickX; y = fx.clickY; pulse.restart() }

    opacity: 0

    Rectangle {
        anchors.centerIn: parent
        width: 70 * root.s; height: width; radius: width / 2
        color: "transparent"
        border.color: theme.hairline
        border.width: 7 * root.s
    }
    Rectangle {
        anchors.centerIn: parent
        width: 67 * root.s; height: width; radius: width / 2
        color: "transparent"
        border.color: theme.cream
        border.width: 4 * root.s
    }

    ParallelAnimation {
        id: pulse
        NumberAnimation { target: root; property: "scale"; from: 0.3; to: 1.3; duration: 350; easing.type: Easing.OutCubic }
        NumberAnimation { target: root; property: "opacity"; from: 1; to: 0; duration: 350 }
    }
}
