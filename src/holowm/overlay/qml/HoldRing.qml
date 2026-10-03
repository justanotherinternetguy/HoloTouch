import QtQuick
import QtQuick.Shapes

// Ring between two hands held in a sign, which completes when what it names is about to open.
Item {
    id: root
    property var fx
    property real s: 1
    property color accent
    readonly property real progress: fx.holdProgress
    readonly property real r: 64 * s

    visible: progress > 0
    x: fx.holdX - r
    y: fx.holdY - r
    width: 2 * r
    height: 2 * r

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.25)
            strokeWidth: 7 * root.s
            fillColor: "transparent"
            PathAngleArc {
                centerX: root.r; centerY: root.r
                radiusX: root.r - 5 * root.s; radiusY: root.r - 5 * root.s
                startAngle: 0
                sweepAngle: 360
            }
        }
        ShapePath {
            strokeColor: root.accent
            strokeWidth: 7 * root.s
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc {
                centerX: root.r; centerY: root.r
                radiusX: root.r - 5 * root.s; radiusY: root.r - 5 * root.s
                startAngle: -90
                sweepAngle: 360 * root.progress
            }
        }
    }
    Text {
        anchors.centerIn: parent
        text: root.fx.holdName
        color: root.accent
        font.pixelSize: 18 * root.s
        font.bold: true
    }
}
