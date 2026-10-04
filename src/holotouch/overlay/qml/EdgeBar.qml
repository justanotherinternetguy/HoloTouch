import QtQuick
import "../../ui"

// At a side edge of the screen, beside the hand: a bar that fills while a held window waits there
// to cross to the next workspace, and where it is going.
Item {
    id: root
    property var fx
    property real s: 1
    property real handY: height / 2
    readonly property int side: fx.edgeSide
    readonly property real progress: fx.edgeProgress
    readonly property real span: 240 * s
    // The last side, place and target are kept while the bar leaves.
    property int at: 1
    property real mid: height / 2
    property int target: -1
    property real shown: 0
    property bool sent: false
    onFxChanged: {
        // Read from fx itself: the bindings above may not have caught up with it yet.
        if (fx.edgeSide !== 0) {
            leave.stop()
            drain.stop()
            at = fx.edgeSide
            mid = Math.min(Math.max(handY, span / 2 + 12 * s), height - span / 2 - 12 * s)
            target = fx.edgeTarget
            sent = false
            shown = fx.edgeProgress
            bar.opacity = 1
        } else if (shown >= 0.93) {
            sent = true  // the window went: mint for a moment
            shown = 1
            leave.restart()
        } else if (shown > 0 && !drain.running) {
            drain.restart()  // pulled back from the edge
        }
    }
    SequentialAnimation {
        id: leave
        PauseAnimation { duration: 200 }
        NumberAnimation { target: bar; property: "opacity"; to: 0; duration: 160 }
        PropertyAction { target: root; property: "shown"; value: 0 }
    }
    SequentialAnimation {
        id: drain
        NumberAnimation { target: root; property: "shown"; to: 0; duration: 150 }
    }

    Item {
        id: bar
        visible: root.side !== 0 || root.shown > 0
        // Half its rounded end hangs off the screen, so it reads as part of the edge.
        x: root.at > 0 ? root.width - 18 * root.s : -9 * root.s
        y: root.mid - root.span / 2
        width: 27 * root.s
        height: root.span

        Rectangle {
            anchors.fill: parent
            anchors.margins: -2 * root.s
            radius: width / 2
            color: theme.cream
        }
        Rectangle {
            anchors.fill: parent
            radius: width / 2
            color: theme.ink
        }
        Rectangle {
            // Fills outward from the middle, at a constant speed.
            anchors.centerIn: parent
            width: parent.width
            height: Math.max(parent.height * root.shown, root.shown > 0 ? width : 0)
            radius: width / 2
            color: root.sent ? theme.mint : theme.butter
        }

        Item {
            id: note
            visible: root.target >= 0
            width: row.width + 26 * root.s
            height: 40 * root.s
            x: root.at > 0 ? bar.width - 9 * root.s - width - 12 * root.s : 9 * root.s + 12 * root.s
            y: -height - 14 * root.s
            Rectangle {
                anchors.fill: parent
                radius: height / 2
                color: theme.chip
                border.color: theme.keyline
                border.width: 1.5 * root.s
            }
            Row {
                id: row
                x: 5 * root.s
                anchors.verticalCenter: parent.verticalCenter
                spacing: 9 * root.s
                Rectangle {
                    width: 30 * root.s; height: width; radius: width / 2
                    color: root.sent ? theme.mint : theme.butter
                    Icon {
                        anchors.centerIn: parent
                        name: root.sent ? "check" : root.at > 0 ? "right" : "left"
                        size: 18 * root.s
                        stroke: 3
                    }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Workspace " + (root.target + 1)
                    color: theme.cream
                    font.family: theme.display
                    font.pixelSize: 17 * root.s
                    font.weight: Font.DemiBold
                }
            }
        }
    }
}
