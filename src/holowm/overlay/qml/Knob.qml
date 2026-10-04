import QtQuick
import QtQuick.Shapes
import "../../ui"

// The dial a claw is turning: an arc that fills with the volume (the right hand, coral) or the
// brightness (the left hand, sky), an icon, and the number.
Item {
    id: root
    property var fx
    property real s: 1
    readonly property bool shown: fx.knob >= 0
    // Keep the last level and name so the dial does not empty while it fades out.
    property real level: 0
    property string name: ""
    onFxChanged: if (fx.knob >= 0) {
        level = fx.knob
        name = fx.knobName
        // Kept whole on the screen, however near an edge the hand is.
        x = Math.min(Math.max(fx.knobX, r + 12 * s), parent.width - r - 12 * s)
        y = Math.min(Math.max(fx.knobY, r + 12 * s), parent.height - r - 12 * s)
    }
    readonly property bool isLeft: name === "Brightness"
    readonly property color tone: isLeft ? theme.sky : theme.coral
    readonly property real r: 66 * s
    readonly property real arc: 54 * s
    readonly property real end: (135 + 270 * level) * Math.PI / 180

    opacity: 0
    states: State {
        name: "turning"
        when: root.shown
        PropertyChanges { target: root; opacity: 1 }
    }
    transitions: [
        Transition { to: "turning"; NumberAnimation { property: "opacity"; duration: 120 } },
        // It stays a moment once let go of, so the number it ended on can be read.
        Transition {
            from: "turning"
            SequentialAnimation {
                PauseAnimation { duration: 400 }
                NumberAnimation { property: "opacity"; duration: 160 }
            }
        }
    ]

    Shape {
        x: -root.r
        y: -root.r
        width: 2 * root.r
        height: 2 * root.r
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: theme.track
            strokeWidth: 14 * root.s
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc { centerX: root.r; centerY: root.r; radiusX: root.arc; radiusY: root.arc; startAngle: 135; sweepAngle: 270 }
        }
        ShapePath {
            strokeColor: theme.cream
            strokeWidth: 10 * root.s
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc { centerX: root.r; centerY: root.r; radiusX: root.arc; radiusY: root.arc; startAngle: 135; sweepAngle: 270 }
        }
        ShapePath {
            strokeColor: root.tone
            strokeWidth: 10 * root.s
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc {
                centerX: root.r; centerY: root.r
                radiusX: root.arc; radiusY: root.arc
                startAngle: 135; sweepAngle: Math.max(270 * root.level, 0.5)
            }
        }
    }

    // A bead at the end of the arc: the hand's turn, made visible.
    Item {
        x: root.arc * Math.cos(root.end)
        y: root.arc * Math.sin(root.end)
        Rectangle { anchors.centerIn: parent; width: 25 * root.s; height: width; radius: width / 2; color: theme.hairline }
        Rectangle { anchors.centerIn: parent; width: 22 * root.s; height: width; radius: width / 2; color: theme.cream }
        Rectangle { anchors.centerIn: parent; width: 18 * root.s; height: width; radius: width / 2; color: root.tone }
    }

    Rectangle {
        anchors.centerIn: parent
        width: 84 * root.s; height: width; radius: width / 2
        color: theme.hairline
    }
    Rectangle {
        anchors.centerIn: parent
        width: 80 * root.s; height: width; radius: width / 2
        color: theme.cream
    }
    Column {
        anchors.centerIn: parent
        Icon {
            anchors.horizontalCenter: parent.horizontalCenter
            name: root.isLeft ? "sun" : "speaker"
            size: 24 * root.s
            stroke: 2.2
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: Math.round(root.level * 100) + "%"
            color: theme.ink
            font.family: theme.display
            font.pixelSize: 24 * root.s
            font.weight: Font.DemiBold
            lineHeight: 0.95
        }
    }
    HandTag {
        isLeft: root.isLeft
        tone: root.tone
        s: root.s
        x: (root.isLeft ? -1 : 1) * 53 * root.s - width / 2
        y: 53 * root.s - height / 2
    }
}
