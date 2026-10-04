import QtQuick
import QtQuick.Shapes
import "../../ui"

// One hand: a ring in the hand's colour that tightens, with a dot that grows, as a pinch closes.
// Sky is the left hand and coral the right; the tag says which in a letter as well. A hand that
// points with its thumb out gets sights round the ring: the thumb coming down will click there.
Item {
    id: root
    property var hand
    property real s: 1
    property bool closing: false  // this hand's fist is closing a window: the cursor is the close mark
    property bool hidden: false  // something else stands where the cursor would be, as a dial does
    readonly property bool isLeft: hand.side === "left"
    readonly property color tone: isLeft ? theme.sky : theme.coral
    readonly property bool aiming: hand.pose === "aim" || hand.pose === "press"
    readonly property bool busy: hand.active || hand.pinch > 0.15 || (hand.pose !== "neutral" && hand.pose !== "open")
    // A relaxed hand that has not moved for a while goes quiet, and so does the outline it would draw.
    property bool idle: false
    readonly property bool quiet: !hand.visible || idle
    property real restX: 0
    property real restY: 0
    onHandChanged: {
        if (!hand.visible)
            return
        if (busy || Math.abs(hand.x - restX) + Math.abs(hand.y - restY) > 28 * s) {
            restX = hand.x
            restY = hand.y
            idle = false
            rest.restart()
        }
    }
    Timer { id: rest; interval: 2000; onTriggered: root.idle = true }

    property real base: idle ? 44 : 56
    Behavior on base { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }
    // The ring's size is the pinch itself, drawn as it is measured: nothing eases it.
    readonly property real d: (base - 8 * hand.pinch * base / 56) * s
    readonly property real line: (idle ? 4 : 5) * s
    readonly property bool held: hand.visible && hand.armed
    // At a side edge the tag swings underneath, so left and right never swap places.
    readonly property bool atEdge: isLeft ? x < 60 * s : x > parent.width - 60 * s

    // Drawn clamped inside the screen.
    x: Math.min(Math.max(hand.x, d / 2 + 5 * s), parent.width - d / 2 - 5 * s)
    y: Math.min(Math.max(hand.y, d / 2 + 5 * s), parent.height - d / 2 - 5 * s)
    opacity: 0

    states: State {
        name: "seen"
        when: root.hand.visible
        PropertyChanges { target: root; opacity: root.idle ? 0.7 : 1 }
    }
    transitions: [
        Transition { to: "seen"; NumberAnimation { property: "opacity"; duration: 140 } },
        // A hand that vanishes leaves its ghost for a moment, then that fades.
        Transition {
            from: "seen"
            SequentialAnimation {
                PauseAnimation { duration: 250 }
                NumberAnimation { property: "opacity"; duration: 400 }
            }
        }
    ]

    Item {
        id: body
        opacity: root.hidden ? 0 : 1
        Behavior on opacity { NumberAnimation { duration: 120 } }

        // -- the ring, once the hand is trusted ----------------------------------------------
        Item {
            visible: root.held && !root.closing
            Rectangle {
                anchors.centerIn: parent
                width: root.d + 7 * root.s; height: width; radius: width / 2
                color: "transparent"
                border.color: theme.hairline
                border.width: 1.5 * root.s
            }
            Rectangle {
                anchors.centerIn: parent
                width: root.d + 4 * root.s; height: width; radius: width / 2
                color: "transparent"
                border.color: theme.cream
                border.width: 2 * root.s
            }
            Rectangle {
                anchors.centerIn: parent
                width: root.d; height: width; radius: width / 2
                color: root.hand.active ? theme.cream : "transparent"
                border.color: root.tone
                border.width: root.line
            }
            Rectangle {
                visible: !root.hand.active
                anchors.centerIn: parent
                width: root.d - 2 * root.line; height: width; radius: width / 2
                color: "transparent"
                border.color: theme.cream
                border.width: 2 * root.s
            }
            Rectangle {
                visible: root.hand.pinch > 0.06 && !root.hand.active
                anchors.centerIn: parent
                width: 26 * root.s * root.hand.pinch + 4 * root.s; height: width; radius: width / 2
                color: theme.cream
            }
            Rectangle {
                visible: root.hand.pinch > 0.06
                anchors.centerIn: parent
                width: 26 * root.s * root.hand.pinch; height: width; radius: width / 2
                color: root.tone
            }
        }

        // -- sights: four ticks that come up in the time it takes for aim to count -----------
        Repeater {
            model: 4
            Item {
                required property int index
                visible: root.held && !root.closing && opacity > 0
                rotation: 90 * index
                opacity: root.aiming ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: root.aiming ? 200 : 100 } }
                Rectangle {
                    x: -width / 2
                    y: -root.d / 2 - 9 * root.s - height
                    width: 9 * root.s; height: 14 * root.s; radius: width / 2
                    color: theme.cream
                    border.color: theme.hairline
                    border.width: 1.5 * root.s
                    Rectangle {
                        anchors.centerIn: parent
                        width: 4 * root.s; height: 9 * root.s; radius: width / 2
                        color: root.tone
                    }
                }
            }
        }

        // -- dashed: seen but not yet trusted (in colour), or lost (colourless and hollow) ----
        Shape {
            id: dashed
            readonly property bool lost: !root.hand.visible
            readonly property real r: (lost ? 24 : 28) * root.s
            visible: !root.held && !root.closing
            x: -r - 4 * root.s
            y: -r - 4 * root.s
            width: 2 * r + 8 * root.s
            height: width
            opacity: lost ? 1 : 0.75
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: theme.hairline
                strokeWidth: (dashed.lost ? 6 : 7) * root.s
                fillColor: dashed.lost ? "#4D1E1B2E" : "transparent"
                PathAngleArc {
                    centerX: dashed.width / 2; centerY: dashed.height / 2
                    radiusX: dashed.r; radiusY: dashed.r
                    startAngle: 0; sweepAngle: 360
                }
            }
            ShapePath {
                strokeColor: dashed.lost ? theme.cream : root.tone
                strokeWidth: (dashed.lost ? 3 : 4) * root.s
                fillColor: "transparent"
                strokeStyle: ShapePath.DashLine
                dashPattern: [2.2, 1.6]
                capStyle: ShapePath.FlatCap
                PathAngleArc {
                    centerX: dashed.width / 2; centerY: dashed.height / 2
                    radiusX: dashed.r; radiusY: dashed.r
                    startAngle: 0; sweepAngle: 360
                }
            }
        }

        // -- a fist that is closing a window: the cursor becomes the close mark ----------------
        Item {
            visible: root.closing && root.hand.visible
            Rectangle {
                anchors.centerIn: parent
                width: 55 * root.s; height: width; radius: width / 2
                color: theme.hairline
            }
            Rectangle {
                anchors.centerIn: parent
                width: 52 * root.s; height: width; radius: width / 2
                color: theme.cream
            }
            Rectangle {
                anchors.centerIn: parent
                width: 48 * root.s; height: width; radius: width / 2
                color: theme.ink
                border.color: root.tone
                border.width: 5 * root.s
            }
            Icon {
                anchors.centerIn: parent
                name: "cross"
                size: 22 * root.s
                stroke: 3
                color: theme.cream
            }
        }

        // -- scroll arrows: dim while the fingers rest, the active one brightens with the speed --
        Column {
            visible: root.hand.pose === "two_finger" && root.hand.visible
            anchors.centerIn: parent
            spacing: root.d + 14 * root.s
            Icon {
                name: "up"
                size: 22 * root.s
                stroke: 3.4
                color: root.tone
                opacity: 0.4 + 0.6 * Math.max(-root.hand.scroll, 0)
            }
            Icon {
                name: "down"
                size: 22 * root.s
                stroke: 3.4
                color: root.tone
                opacity: 0.4 + 0.6 * Math.max(root.hand.scroll, 0)
            }
        }

        HandTag {
            isLeft: root.isLeft
            tone: root.tone
            s: root.s
            fade: root.hand.visible ? 1 : 0.7
            readonly property real reach: (root.closing ? 48 * root.s : root.d) / 2
            x: (root.atEdge ? 0 : (root.isLeft ? -1 : 1) * (reach - 1 * root.s)) - width / 2
            y: (root.atEdge ? reach + 7 * root.s : reach - 4 * root.s) - height / 2
        }
    }

    // Said only when the hand was holding something when it went.
    Chip {
        readonly property bool flip: root.x > root.parent.width - width - 60 * root.s
        visible: !root.hand.visible && root.hand.lost
        s: root.s
        text: root.isLeft ? "Lost your left hand" : "Lost your right hand"
        x: flip ? -width - 40 * root.s : 44 * root.s
        y: -height / 2
    }
}
