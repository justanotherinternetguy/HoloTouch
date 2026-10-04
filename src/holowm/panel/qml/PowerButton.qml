import QtQuick
import QtQuick.Shapes
import "../../ui"

// The dial that starts and stops HoloWM. The ring is the state; the button is always the next thing to do.
Item {
    id: root
    property string mode: "stopped"  // the panel's state: stopped | starting | running | paused | stopping
    property string camera: "ok"  // ok | waiting | missing
    property bool practice: false
    property real s: 1
    signal clicked()
    readonly property bool busy: mode === "starting" || mode === "stopping"
    readonly property bool off: mode === "stopped"
    // What the ring shows: nothing, a sweep, whole, dotted or broken.
    readonly property string ring: off ? "none" : busy || camera === "waiting" ? "sweep"
                                 : mode === "paused" ? "paused" : camera === "missing" ? "broken" : "whole"
    readonly property color tone: ring === "paused" ? theme.butterDeep : ring === "broken" ? theme.coral
                                : practice ? theme.lilac : theme.mint
    readonly property var labels: ({
        "stopped": "Start", "starting": "Starting", "running": "Stop", "paused": "Stop", "stopping": "Stopping"
    })

    width: 164 * s
    height: width

    Shape {
        id: rim
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: root.ring === "whole" ? root.tone : theme.line
            strokeWidth: 9 * root.s
            fillColor: "transparent"
            PathAngleArc {
                centerX: rim.width / 2; centerY: rim.height / 2
                radiusX: 74 * root.s; radiusY: 74 * root.s
                startAngle: 0; sweepAngle: 360
            }
        }
        ShapePath {
            strokeColor: root.ring === "paused" || root.ring === "broken" ? root.tone : "transparent"
            strokeWidth: 9 * root.s
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            strokeStyle: ShapePath.DashLine
            dashPattern: root.ring === "paused" ? [0.5, 1.6] : [2.6, 1.9]
            PathAngleArc {
                centerX: rim.width / 2; centerY: rim.height / 2
                radiusX: 74 * root.s; radiusY: 74 * root.s
                startAngle: -90; sweepAngle: 360
            }
        }
    }
    // An arc that goes round while HoloWM is on its way up or down, or waiting for the camera.
    Shape {
        anchors.fill: parent
        visible: root.ring === "sweep"
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: root.tone
            strokeWidth: 9 * root.s
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc {
                centerX: rim.width / 2; centerY: rim.height / 2
                radiusX: 74 * root.s; radiusY: 74 * root.s
                startAngle: -90; sweepAngle: 90
            }
        }
        RotationAnimation on rotation {
            running: root.ring === "sweep"
            loops: Animation.Infinite
            from: 0; to: 360; duration: 1400
        }
    }

    // The button rests on a ledge and sinks onto it when pressed.
    Rectangle {
        visible: !root.busy
        anchors.horizontalCenter: parent.horizontalCenter
        y: 27 * root.s
        width: 116 * root.s; height: width; radius: width / 2
        color: root.off ? theme.ink : theme.ledge
    }
    Rectangle {
        id: disc
        anchors.horizontalCenter: parent.horizontalCenter
        y: (root.busy ? 24 : tap.pressed ? 26 : 21) * root.s
        width: 116 * root.s; height: width; radius: width / 2
        color: root.busy ? theme.sunk : root.off ? (hover.hovered ? Qt.lighter(theme.mint, 1.08) : theme.mint)
                                                 : (hover.hovered ? theme.inkRaised : theme.ink)
        border.color: root.busy ? theme.muted : theme.ink
        border.width: root.off || root.busy ? 2.5 * root.s : 0
        Behavior on y { NumberAnimation { duration: 70 } }

        Column {
            anchors.centerIn: parent
            spacing: 1 * root.s
            Icon {
                visible: !root.busy
                anchors.horizontalCenter: parent.horizontalCenter
                name: "power"
                size: 32 * root.s
                stroke: 2.3
                color: root.off ? theme.ink : theme.cream
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: root.labels[root.mode] || ""
                color: root.busy ? theme.inkSoft : root.off ? theme.ink : theme.cream
                font.family: theme.display
                font.pixelSize: (root.busy ? 17 : root.off ? 20 : 18) * root.s
                font.weight: Font.DemiBold
            }
        }
        HoverHandler { id: hover; cursorShape: root.busy ? Qt.ArrowCursor : Qt.PointingHandCursor }
        TapHandler { id: tap; enabled: !root.busy; onTapped: root.clicked() }
    }
}
