import QtQuick
import QtQuick.Shapes
import "../../ui"
import "../../ui/Icons.js" as Icons

// Marking-menu launcher: petals around a seed. Geometry comes from Python; this draws and animates it.
// Only the direction of the hand counts, so each petal owns a whole wedge, and the wedge aimed at is shaded.
Item {
    id: root
    property real s: 1
    property string side: "right"  // the hand that opened the menu
    readonly property var menu: bridge.menu
    readonly property var pie: bridge.pie
    readonly property var items: bridge.menuItems
    readonly property color tone: side === "left" ? theme.sky : theme.coral
    readonly property real childSize: pie.childSize * s
    readonly property real orbit: pie.childOffset * s
    readonly property real seed: pie.centerSize * s
    readonly property real reach: orbit + childSize / 2 + 26 * s  // how far out a wedge is shaded
    readonly property bool opened: menu.open
    readonly property int hover: menu.hover
    readonly property bool aiming: hover !== -2
    readonly property int slots: items.length + (menu.back ? 1 : 0)
    readonly property real wedge: slots > 1 ? 360 / slots : 0
    readonly property real aim: hover >= 0 && hover < items.length ? angleOf(items[hover].x, items[hover].y)
                              : hover === -1 && menu.back ? angleOf(menu.back.x, menu.back.y) : 0
    readonly property string hint: hover >= 0 && hover < items.length
                                   ? (items[hover].menu ? "keep going" : "let go to pick")
                                   : hover === -1 ? "keep going" : ""

    // Degrees clockwise from straight up, of a point as seen from the menu's centre.
    function angleOf(px, py) { return Math.atan2(px - menu.cx, -(py - menu.cy)) * 180 / Math.PI }
    function wellOf(kind) {
        return kind === "launch" ? theme.butter : kind === "window" ? theme.mint : kind === "close" ? theme.ink : theme.lilac
    }
    // The outline of a wedge centred on straight up, around the point (c, c).
    function wedgePath(c, half, inner, outer) {
        const sin = Math.sin(half * Math.PI / 180), cos = Math.cos(half * Math.PI / 180)
        return "M " + (c - inner * sin) + " " + (c - inner * cos)
             + " L " + (c - outer * sin) + " " + (c - outer * cos)
             + " A " + outer + " " + outer + " 0 0 1 " + (c + outer * sin) + " " + (c - outer * cos)
             + " L " + (c + inner * sin) + " " + (c - inner * cos)
             + " A " + inner + " " + inner + " 0 0 0 " + (c - inner * sin) + " " + (c - inner * cos) + " Z"
    }

    opacity: menu.open ? 1 : 0
    visible: opacity > 0
    Behavior on opacity { NumberAnimation { duration: 150 } }

    // -- the orbit the petals sit on ----------------------------------------------------------
    Rectangle {
        x: root.menu.cx - width / 2; y: root.menu.cy - height / 2
        width: 2 * root.orbit + 5 * root.s; height: width; radius: width / 2
        color: "transparent"
        border.color: "#471E1B2E"
        border.width: 5 * root.s
    }
    Rectangle {
        x: root.menu.cx - width / 2; y: root.menu.cy - height / 2
        width: 2 * root.orbit + 2 * root.s; height: width; radius: width / 2
        color: "transparent"
        border.color: "#BFFBF3E4"
        border.width: 2 * root.s
    }

    // -- the wedge aimed at: its whole selection region, an arc on the orbit, a stem from the seed --
    Item {
        x: root.menu.cx
        y: root.menu.cy
        rotation: root.aim
        opacity: root.aiming && root.wedge > 0 ? 1 : 0
        Behavior on rotation { RotationAnimation { direction: RotationAnimation.Shortest; duration: 140; easing.type: Easing.OutCubic } }
        Behavior on opacity { NumberAnimation { duration: 90 } }
        Shape {
            id: region
            readonly property real c: root.reach + 8 * root.s
            x: -c; y: -c
            width: 2 * c; height: 2 * c
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: "#661E1B2E"
                strokeWidth: 4 * root.s
                fillColor: Qt.rgba(root.tone.r, root.tone.g, root.tone.b, 0.22)
                joinStyle: ShapePath.RoundJoin
                PathSvg { path: root.wedgePath(region.c, root.wedge / 2, root.seed / 2 + 4 * root.s, root.reach) }
            }
            ShapePath {
                strokeColor: theme.cream
                strokeWidth: 2 * root.s
                fillColor: "transparent"
                joinStyle: ShapePath.RoundJoin
                PathSvg { path: root.wedgePath(region.c, root.wedge / 2, root.seed / 2 + 4 * root.s, root.reach) }
            }
            ShapePath {
                strokeColor: theme.cream
                strokeWidth: 13 * root.s
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                PathAngleArc {
                    centerX: region.c; centerY: region.c
                    radiusX: root.orbit; radiusY: root.orbit
                    startAngle: -90 - root.wedge / 2 + 4; sweepAngle: root.wedge - 8
                }
            }
            ShapePath {
                strokeColor: root.tone
                strokeWidth: 8 * root.s
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                PathAngleArc {
                    centerX: region.c; centerY: region.c
                    radiusX: root.orbit; radiusY: root.orbit
                    startAngle: -90 - root.wedge / 2 + 4; sweepAngle: root.wedge - 8
                }
            }
            ShapePath {
                strokeColor: theme.cream
                strokeWidth: 13 * root.s
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                startX: region.c; startY: region.c - root.seed / 2
                PathLine { x: region.c; y: region.c - root.orbit + root.childSize * 0.5 }
            }
            ShapePath {
                strokeColor: root.tone
                strokeWidth: 8 * root.s
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                startX: region.c; startY: region.c - root.seed / 2
                PathLine { x: region.c; y: region.c - root.orbit + root.childSize * 0.5 }
            }
        }
    }

    // -- centres of the menus already passed through, so the path taken stays visible -----------
    Repeater {
        model: Math.max(root.menu.trail.length - 1, 0)
        Item {
            required property int index
            readonly property var point: root.menu.trail[index]
            x: point[0]
            y: point[1]
            Rectangle { anchors.centerIn: parent; width: 21 * root.s; height: width; radius: width / 2; color: theme.hairline }
            Rectangle { anchors.centerIn: parent; width: 18 * root.s; height: width; radius: width / 2; color: theme.cream }
            Rectangle { anchors.centerIn: parent; width: 14 * root.s; height: width; radius: width / 2; color: theme.lilac }
        }
    }

    // -- the petals ---------------------------------------------------------------------------
    Repeater {
        model: root.items
        Item {
            id: petal
            required property var modelData
            required property int index
            readonly property bool aimed: root.hover === index
            readonly property real angle: root.angleOf(modelData.x, modelData.y) * Math.PI / 180
            readonly property real ux: Math.sin(angle)
            readonly property real uy: -Math.cos(angle)
            readonly property string glyph: Icons.path(modelData.icon)
            readonly property int buds: modelData.menu ? Math.max(Math.min(modelData.count, 3), 1) : 0
            // An aimed petal swells and steps outward.
            property real push: aimed ? 12 * root.s : 0
            property real swell: aimed ? 90 / 76 : 1
            property real bloom: 1
            Behavior on push { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
            Behavior on swell { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
            // Petals open one after another, clockwise from twelve, with a small overshoot.
            SequentialAnimation {
                id: open
                PropertyAction { target: petal; property: "bloom"; value: 0.3 }
                PauseAnimation { duration: 18 * petal.index }
                NumberAnimation { target: petal; property: "bloom"; to: 1; duration: 280; easing.type: Easing.OutBack; easing.overshoot: 1.3 }
            }
            Component.onCompleted: open.start()
            Connections {
                target: root
                function onOpenedChanged() { if (root.opened) open.restart() }
            }

            x: modelData.x + ux * push
            y: modelData.y + uy * push
            z: aimed ? 2 : 0

            // Buds: this petal opens further.
            Repeater {
                model: petal.buds
                Rectangle {
                    required property int index
                    readonly property real across: (index - (petal.buds - 1) / 2) * 17 * root.s
                    readonly property real out: root.childSize * petal.swell / 2 + 12 * root.s - Math.abs(across) * 0.2
                    x: petal.ux * out - petal.uy * across - width / 2
                    y: petal.uy * out + petal.ux * across - height / 2
                    width: 10 * root.s; height: width; radius: width / 2
                    color: theme.lilac
                    border.color: theme.hairline
                    border.width: 1.5 * root.s
                    scale: petal.bloom
                }
            }

            Item {
                scale: petal.swell * petal.bloom
                Rectangle {
                    anchors.centerIn: parent
                    width: root.childSize + (petal.aimed ? 9 : 4) * root.s; height: width; radius: width / 2
                    color: theme.hairline
                }
                Rectangle {
                    visible: petal.aimed
                    anchors.centerIn: parent
                    width: root.childSize + 5.5 * root.s; height: width; radius: width / 2
                    color: theme.cream
                }
                Rectangle {
                    anchors.centerIn: parent
                    width: root.childSize; height: width; radius: width / 2
                    color: petal.aimed ? root.tone : theme.cream
                }
                Rectangle {
                    id: well
                    readonly property bool dark: !petal.aimed && petal.modelData.kind === "close"
                    anchors.centerIn: parent
                    width: root.childSize * 0.68; height: width; radius: width / 2
                    color: petal.aimed ? theme.cream : root.wellOf(petal.modelData.kind)
                }
                Icon {
                    visible: petal.glyph !== ""
                    anchors.centerIn: parent
                    path: petal.glyph
                    size: root.childSize * 0.36
                    stroke: 2.1
                    color: well.dark ? theme.cream : theme.ink
                }
                Image {
                    visible: petal.glyph === "" && petal.modelData.hasIcon
                    anchors.centerIn: parent
                    width: root.childSize * 0.46
                    height: width
                    sourceSize: Qt.size(128, 128)
                    source: visible ? "image://theme/" + petal.modelData.icon : ""
                }
                Text {
                    visible: petal.glyph === "" && !petal.modelData.hasIcon
                    anchors.centerIn: parent
                    text: petal.modelData.name.charAt(0).toUpperCase()
                    color: well.dark ? theme.cream : theme.ink
                    font.family: theme.display
                    font.pixelSize: root.childSize * 0.34
                    font.weight: Font.DemiBold
                }
            }

            // Every petal is named, outside the orbit so nothing covers the seed.
            Chip {
                id: name
                readonly property real edge: root.childSize * petal.swell / 2 + (petal.buds ? 26 : 10) * root.s
                readonly property real wantX: petal.ux > 0.5 ? edge : petal.ux < -0.5 ? -edge - width : -width / 2
                readonly property real wantY: Math.abs(petal.ux) > 0.5 ? -height / 2 : petal.uy < 0 ? -edge - height : edge
                s: root.s
                aimed: petal.aimed
                tone: root.tone
                text: petal.modelData.name
                opacity: Math.max((petal.bloom - 0.6) / 0.4, 0)
                // A label that would cross the screen's edge is pushed back inside it.
                x: Math.min(Math.max(petal.x + wantX, 12 * root.s), root.width - width - 12 * root.s) - petal.x
                y: Math.min(Math.max(petal.y + wantY, 12 * root.s), root.height - height - 12 * root.s) - petal.y
            }
        }
    }

    // -- the way back: one slot of a submenu, where the menu before it was centred ---------------
    Item {
        id: back
        readonly property var at: root.menu.back
        readonly property bool aimed: root.hover === -1
        property real swell: aimed ? 90 / 76 : 1
        Behavior on swell { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
        visible: !!at
        x: at ? at.x : 0
        y: at ? at.y : 0
        z: aimed ? 2 : 0
        Item {
            scale: back.swell
            Rectangle {
                anchors.centerIn: parent
                width: root.childSize + (back.aimed ? 9 : 4) * root.s; height: width; radius: width / 2
                color: theme.hairline
            }
            Rectangle {
                visible: back.aimed
                anchors.centerIn: parent
                width: root.childSize + 5.5 * root.s; height: width; radius: width / 2
                color: theme.cream
            }
            Rectangle {
                anchors.centerIn: parent
                width: root.childSize; height: width; radius: width / 2
                color: back.aimed ? root.tone : theme.cream
            }
            Rectangle {
                anchors.centerIn: parent
                width: root.childSize * 0.68; height: width; radius: width / 2
                color: back.aimed ? theme.cream : theme.sunk
            }
            Icon {
                anchors.centerIn: parent
                name: "back"
                size: root.childSize * 0.36
                stroke: 2.2
            }
        }
        Chip {
            s: root.s
            aimed: back.aimed
            tone: root.tone
            text: "Back"
            x: -width / 2
            y: root.childSize * back.swell / 2 + 10 * root.s
        }
    }

    // -- the seed: the dead zone, and what letting go will do -----------------------------------
    Item {
        x: root.menu.cx
        y: root.menu.cy
        z: 3
        Rectangle {
            anchors.centerIn: parent
            width: root.seed + 4 * root.s; height: width; radius: width / 2
            color: theme.cream
        }
        Rectangle {
            anchors.centerIn: parent
            width: root.seed; height: width; radius: width / 2
            color: theme.ink
            border.color: root.aiming ? root.tone : theme.cream
            border.width: 4 * root.s
        }
        Column {
            anchors.centerIn: parent
            width: root.seed - 22 * root.s
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: root.menu.label
                color: theme.cream
                font.family: theme.display
                font.pixelSize: 19 * root.s
                font.weight: Font.DemiBold
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
                lineHeight: 0.95
            }
            Text {
                visible: root.hint !== ""
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: root.hint
                color: Qt.lighter(root.tone, 1.35)
                font.family: theme.display
                font.pixelSize: 14 * root.s
                font.weight: Font.Medium
            }
        }
    }
}
