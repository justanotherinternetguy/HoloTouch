import QtQuick
import "../../ui"

// Ring between two hands held in a sign, which completes when what it names is about to open.
Item {
    id: root
    property var fx
    property real s: 1
    readonly property real progress: fx.holdProgress

    visible: progress > 0
    x: fx.holdX
    y: fx.holdY

    HoldArc {
        anchors.centerIn: parent
        r: 58 * root.s
        s: root.s
        progress: root.progress
    }
    Rectangle {
        anchors.centerIn: parent
        width: 68 * root.s; height: width; radius: width / 2
        color: theme.cream
    }
    Rectangle {
        anchors.centerIn: parent
        width: 64 * root.s; height: width; radius: width / 2
        color: theme.ink
    }
    Icon {
        anchors.centerIn: parent
        name: "camera"
        size: 34 * root.s
        color: theme.cream
    }
    Chip {
        s: root.s
        text: root.fx.holdName
        x: -width / 2
        y: 78 * root.s
    }
}
