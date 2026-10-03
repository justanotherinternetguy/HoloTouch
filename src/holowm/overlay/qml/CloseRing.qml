import QtQuick
import QtQuick.Shapes

// Ring around a held fist that completes when the window is about to close.
Item {
    id: root
    property var fx
    property real s: 1
    property color danger
    readonly property real progress: fx.closeProgress
    readonly property real r: 52 * s

    visible: progress > 0
    x: fx.closeX - r
    y: fx.closeY - r
    width: 2 * r
    height: 2 * r

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: root.danger
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
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.top
        anchors.bottomMargin: 6 * root.s
        text: "Close"
        color: root.danger
        font.pixelSize: 18 * root.s
        font.bold: true
    }
}
