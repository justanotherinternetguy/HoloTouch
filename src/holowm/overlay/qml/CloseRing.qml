import QtQuick

// The ring a fist holds still inside to close a window. It stays where the fist formed and is as
// wide as the fist may drift, so leaving the ring is what cancels.
Item {
    id: root
    property var fx
    property real s: 1
    property real reach: 54  // how far the fist may drift, in pixels
    property string title
    property string side: "right"
    property real shown: 0  // what is drawn: the progress, or its draining away once cancelled
    property bool done: false
    property string name
    onFxChanged: {
        const progress = fx.closeProgress
        if (progress > 0) {
            leave.stop()
            drain.stop()
            x = fx.closeX
            y = fx.closeY
            name = title.length > 26 ? title.slice(0, 25) + "…" : title
            done = false
            shown = progress
            scale = 1
            opacity = 1
        } else if (shown >= 0.96) {
            done = true  // it ran its course: mint, one pop, gone
            shown = 1
            leave.restart()
        } else if (shown > 0) {
            drain.restart()  // cancelled: the arc empties and nothing is confirmed
        }
    }

    visible: shown > 0

    SequentialAnimation {
        id: leave
        NumberAnimation { target: root; property: "scale"; to: 1.16; duration: 90; easing.type: Easing.OutCubic }
        ParallelAnimation {
            NumberAnimation { target: root; property: "scale"; to: 1; duration: 200 }
            NumberAnimation { target: root; property: "opacity"; to: 0; duration: 200 }
        }
        PropertyAction { target: root; property: "shown"; value: 0 }
    }
    NumberAnimation { id: drain; target: root; property: "shown"; to: 0; duration: 150 }

    HoldArc {
        anchors.centerIn: parent
        r: root.reach
        s: root.s
        progress: root.shown
        done: root.done
    }
    Chip {
        readonly property bool flip: root.x > root.parent.width - root.reach - width - 40 * root.s
        visible: !root.done && root.name !== ""
        s: root.s
        text: "Closing " + root.name
        x: flip ? -root.reach - 20 * root.s - width : root.reach + 20 * root.s
        y: -height / 2
    }
}
