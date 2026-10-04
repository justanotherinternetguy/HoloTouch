import QtQuick
import QtQuick.Shapes

// Outline around the window a hand is over, holding, resizing or about to close. It sits just
// outside the window, so nothing is drawn over what the window shows.
Item {
    id: root
    property var frame
    property var hands: []  // both cursors' hands, to tie a held window to whoever holds it
    property real s: 1
    property bool quiet: false  // every hand in view is idle: a window only hovered over is left bare
    readonly property string mode: frame.mode
    readonly property bool held: mode === "grab" || mode === "resize"
    readonly property bool let_down: !frame.visible && frame.lost  // the hand holding it vanished
    readonly property color tone: frame.side === "left" ? theme.sky : theme.coral
    readonly property real m: 5 * s
    readonly property var holders: hands.filter(hand => hand.visible && hand.active)

    function toneOf(hand) { return hand.side === "left" ? theme.sky : theme.coral }

    x: frame.x - m
    y: frame.y - m
    width: frame.w + 2 * m
    height: frame.h + 2 * m
    opacity: frame.visible && !(mode === "hover" && quiet) ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: root.let_down ? 650 : 120 } }

    // -- under a hand, or closing: a cream line with corner arcs --------------------------------
    Item {
        anchors.fill: parent
        visible: (root.mode === "hover" || root.mode === "close") && !root.let_down
        Rectangle {
            anchors.fill: parent
            anchors.margins: -1.5 * root.s
            radius: 16.5 * root.s
            color: "transparent"
            border.color: "#8C1E1B2E"
            border.width: 1.5 * root.s
        }
        Rectangle {
            anchors.fill: parent
            radius: 15 * root.s
            color: "transparent"
            border.color: theme.keyline
            border.width: 2.5 * root.s
        }
        Rectangle {
            anchors.fill: parent
            anchors.margins: 2.5 * root.s
            radius: 12.5 * root.s
            color: "transparent"
            border.color: "#8C1E1B2E"
            border.width: 1.5 * root.s
        }
        Repeater {
            model: 4
            Shape {
                id: corner
                required property int index
                readonly property real side: 36 * root.s
                readonly property real out: 6 * root.s
                // Butter, the colour of progress, while a fist is closing the window.
                readonly property color colour: root.mode === "close" ? theme.butter : root.tone
                width: side
                height: side
                x: index === 1 || index === 2 ? root.width - side + out : -out
                y: index >= 2 ? root.height - side + out : -out
                rotation: index * 90
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    strokeColor: theme.hairline
                    strokeWidth: 9 * root.s
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    startX: 3 * root.s; startY: corner.side - 3 * root.s
                    PathLine { x: 3 * root.s; y: 20 * root.s }
                    PathQuad { x: 20 * root.s; y: 3 * root.s; controlX: 3 * root.s; controlY: 3 * root.s }
                    PathLine { x: corner.side - 3 * root.s; y: 3 * root.s }
                }
                ShapePath {
                    strokeColor: corner.colour
                    strokeWidth: 6 * root.s
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    startX: 3 * root.s; startY: corner.side - 3 * root.s
                    PathLine { x: 3 * root.s; y: 20 * root.s }
                    PathQuad { x: 20 * root.s; y: 3 * root.s; controlX: 3 * root.s; controlY: 3 * root.s }
                    PathLine { x: corner.side - 3 * root.s; y: 3 * root.s }
                }
            }
        }
    }

    // -- held by one hand: a solid frame in that hand's colour ----------------------------------
    Item {
        anchors.fill: parent
        visible: root.mode === "grab" && !root.let_down
        Rectangle {
            anchors.fill: parent
            anchors.margins: -3.5 * root.s
            radius: 18.5 * root.s
            color: "transparent"
            border.color: theme.hairline
            border.width: 1.5 * root.s
        }
        Rectangle {
            anchors.fill: parent
            anchors.margins: -2 * root.s
            radius: 17 * root.s
            color: "transparent"
            border.color: theme.cream
            border.width: 2 * root.s
        }
        Rectangle {
            anchors.fill: parent
            radius: 15 * root.s
            color: "transparent"
            border.color: root.tone
            border.width: 5 * root.s
        }
        Rectangle {
            anchors.fill: parent
            anchors.margins: 5 * root.s
            radius: 10 * root.s
            color: "transparent"
            border.color: "#991E1B2E"
            border.width: 1.5 * root.s
        }

        // What ties the window to the hand: a bead on the nearest edge, and a leash to the pinch
        // when that is close.
        Item {
            id: tie
            readonly property var hand: root.holders.length ? root.holders[0] : null
            readonly property real hx: hand ? hand.x - root.x : 0
            readonly property real hy: hand ? hand.y - root.y : 0
            readonly property var gaps: [hy, root.width - hx, root.height - hy, hx]  // top, right, bottom, left
            readonly property int edge: gaps.indexOf(Math.min(gaps[0], gaps[1], gaps[2], gaps[3]))
            readonly property bool upright: edge === 0 || edge === 2
            readonly property real inset: 2.5 * root.s
            readonly property real bx: upright ? Math.min(Math.max(hx, 20 * root.s), root.width - 20 * root.s)
                                               : edge === 1 ? root.width - inset : inset
            readonly property real by: upright ? (edge === 0 ? inset : root.height - inset)
                                               : Math.min(Math.max(hy, 20 * root.s), root.height - 20 * root.s)
            readonly property real reach: Math.abs(gaps[edge])
            visible: hand !== null

            Rectangle {
                // The leash stops short of the cursor's ring and is left out when the edge is far off.
                readonly property real gap: tie.reach - 34 * root.s
                visible: gap > 4 * root.s && tie.reach <= 160 * root.s
                width: tie.upright ? 4 * root.s : gap
                height: tie.upright ? gap : 4 * root.s
                x: tie.upright ? tie.bx - width / 2 : (tie.edge === 1 ? tie.bx - 8 * root.s - gap : tie.bx + 8 * root.s)
                y: tie.upright ? (tie.edge === 0 ? tie.by + 8 * root.s : tie.by - 8 * root.s - gap) : tie.by - height / 2
                radius: 2 * root.s
                color: root.tone
                border.color: theme.cream
                border.width: 0
                Rectangle {
                    z: -1
                    anchors.fill: parent
                    anchors.margins: -1.5 * root.s
                    radius: 3.5 * root.s
                    color: theme.cream
                }
            }
            Rectangle {
                x: tie.bx - width / 2; y: tie.by - height / 2
                width: 23 * root.s; height: width; radius: width / 2
                color: theme.hairline
            }
            Rectangle {
                x: tie.bx - width / 2; y: tie.by - height / 2
                width: 20 * root.s; height: width; radius: width / 2
                color: theme.cream
            }
            Rectangle {
                x: tie.bx - width / 2; y: tie.by - height / 2
                width: 16 * root.s; height: width; radius: width / 2
                color: root.tone
            }
        }
    }

    // -- held by both hands: neutral cream, a grip at the corner nearest each hand --------------
    Item {
        anchors.fill: parent
        visible: root.mode === "resize" && !root.let_down
        Rectangle {
            anchors.fill: parent
            anchors.margins: -1.5 * root.s
            radius: 16.5 * root.s
            color: "transparent"
            border.color: theme.hairline
            border.width: 1.5 * root.s
        }
        Rectangle {
            anchors.fill: parent
            radius: 15 * root.s
            color: "transparent"
            border.color: theme.cream
            border.width: 4 * root.s
        }
        Rectangle {
            anchors.fill: parent
            anchors.margins: 4 * root.s
            radius: 11 * root.s
            color: "transparent"
            border.color: theme.hairline
            border.width: 1.5 * root.s
        }

        // The size the resize began with.
        Shape {
            readonly property var ghost: root.frame.ghost
            visible: ghost.length === 4
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: "#99FBF3E4"
                strokeWidth: 2.5 * root.s
                fillColor: "transparent"
                strokeStyle: ShapePath.DashLine
                dashPattern: [3.2, 2.4]
                PathRectangle {
                    x: root.frame.ghost.length === 4 ? root.frame.ghost[0] - root.x : 0
                    y: root.frame.ghost.length === 4 ? root.frame.ghost[1] - root.y : 0
                    width: root.frame.ghost.length === 4 ? root.frame.ghost[2] : 0
                    height: root.frame.ghost.length === 4 ? root.frame.ghost[3] : 0
                    radius: 12 * root.s
                }
            }
        }

        Repeater {
            model: root.mode === "resize" ? root.holders : []
            Item {
                id: grip
                required property var modelData
                required property int index
                readonly property real hx: modelData.x - root.x
                readonly property real hy: modelData.y - root.y
                // The nearest corner; a second hand reaching for the same one takes the corner across.
                readonly property bool lower: hy > root.height / 2
                readonly property bool nearRight: hx > root.width / 2
                readonly property var other: root.holders.length > 1 ? root.holders[1 - index] : null
                readonly property bool clash: other !== null && index === 1
                    && (other.x - root.x > root.width / 2) === nearRight && (other.y - root.y > root.height / 2) === lower
                readonly property bool atRight: clash ? !nearRight : nearRight
                readonly property real cx: atRight ? root.width - 4 * root.s : 4 * root.s
                readonly property real cy: lower ? root.height - 4 * root.s : 4 * root.s
                readonly property color colour: root.toneOf(modelData)
                readonly property real span: Math.hypot(cx - hx, cy - hy)

                Item {
                    // The leash: from just outside the cursor to just short of the grip.
                    x: grip.hx
                    y: grip.hy
                    rotation: Math.atan2(grip.cy - grip.hy, grip.cx - grip.hx) * 180 / Math.PI
                    visible: grip.span > 56 * root.s
                    Rectangle {
                        x: 30 * root.s
                        y: -3.5 * root.s
                        width: grip.span - 48 * root.s
                        height: 7 * root.s
                        radius: height / 2
                        color: theme.cream
                    }
                    Rectangle {
                        x: 31.5 * root.s
                        y: -2 * root.s
                        width: grip.span - 51 * root.s
                        height: 4 * root.s
                        radius: height / 2
                        color: grip.colour
                    }
                }
                Shape {
                    readonly property real side: 60 * root.s
                    readonly property real out: 8 * root.s
                    width: side
                    height: side
                    x: grip.atRight ? root.width - side + out : -out
                    y: grip.lower ? root.height - side + out : -out
                    rotation: grip.atRight ? (grip.lower ? 180 : 90) : (grip.lower ? 270 : 0)
                    preferredRendererType: Shape.CurveRenderer
                    ShapePath {
                        strokeColor: theme.cream
                        strokeWidth: 14 * root.s
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        startX: 7 * root.s; startY: 53 * root.s
                        PathLine { x: 7 * root.s; y: 30 * root.s }
                        PathQuad { x: 30 * root.s; y: 7 * root.s; controlX: 7 * root.s; controlY: 7 * root.s }
                        PathLine { x: 53 * root.s; y: 7 * root.s }
                    }
                    ShapePath {
                        strokeColor: grip.colour
                        strokeWidth: 10 * root.s
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        startX: 7 * root.s; startY: 53 * root.s
                        PathLine { x: 7 * root.s; y: 30 * root.s }
                        PathQuad { x: 30 * root.s; y: 7 * root.s; controlX: 7 * root.s; controlY: 7 * root.s }
                        PathLine { x: 53 * root.s; y: 7 * root.s }
                    }
                }
            }
        }

        // The size, seated on the bottom edge so it covers nothing the window shows.
        Rectangle {
            visible: root.frame.label !== ""
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height - 2 * root.s - height / 2
            width: size.width + 28 * root.s
            height: 38 * root.s
            radius: height / 2
            color: theme.ink
            border.color: theme.cream
            border.width: 2 * root.s
            Row {
                id: size
                anchors.centerIn: parent
                spacing: 9 * root.s
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 12 * root.s; height: width; radius: width / 2
                    color: theme.sky
                }
                Text {
                    text: root.frame.label
                    color: theme.cream
                    font.family: theme.display
                    font.pixelSize: 21 * root.s
                    font.weight: Font.DemiBold
                }
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 12 * root.s; height: width; radius: width / 2
                    color: theme.coral
                }
            }
        }
    }

    // -- the hand that held it was lost: colourless and dashed, where it was left ---------------
    Shape {
        anchors.fill: parent
        visible: root.let_down
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: "#801E1B2E"
            strokeWidth: 6 * root.s
            fillColor: "transparent"
            PathRectangle { width: root.width; height: root.height; radius: 15 * root.s }
        }
        ShapePath {
            strokeColor: theme.cream
            strokeWidth: 3 * root.s
            fillColor: "transparent"
            strokeStyle: ShapePath.DashLine
            dashPattern: [3, 2.2]
            PathRectangle { width: root.width; height: root.height; radius: 15 * root.s }
        }
    }
}
