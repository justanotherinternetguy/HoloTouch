import QtQuick
import QtQuick.Shapes

// The knob a claw is turning: an arc that fills with the volume or the brightness, around the hand.
Item {
    id: root
    property var fx
    property real s: 1
    property color accent
    readonly property bool shown: fx.knob >= 0
    // Keep the last level and name so the knob does not empty while it fades out.
    property real level: 0
    property string name: ""
    onFxChanged: if (fx.knob >= 0) { level = fx.knob; name = fx.knobName; x = fx.knobX - r; y = fx.knobY - r }
    readonly property real r: 78 * s

    width: 2 * r
    height: 2 * r
    opacity: shown ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 200 } }

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.25)
            strokeWidth: 9 * root.s
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc {
                centerX: root.r; centerY: root.r
                radiusX: root.r - 6 * root.s; radiusY: root.r - 6 * root.s
                startAngle: 135; sweepAngle: 270
            }
        }
        ShapePath {
            strokeColor: root.accent
            strokeWidth: 9 * root.s
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc {
                centerX: root.r; centerY: root.r
                radiusX: root.r - 6 * root.s; radiusY: root.r - 6 * root.s
                startAngle: 135; sweepAngle: 270 * root.level
            }
        }
    }
    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.bottom
        anchors.topMargin: 4 * root.s
        text: root.name + " " + Math.round(root.level * 100) + "%"
        color: root.accent
        font.pixelSize: 20 * root.s
        font.bold: true
    }
}
