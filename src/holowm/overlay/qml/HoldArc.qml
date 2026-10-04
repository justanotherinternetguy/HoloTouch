import QtQuick
import QtQuick.Shapes

// A ring that fills clockwise from twelve: butter while it fills, mint once it is complete.
Shape {
    id: root
    property real r: 54  // radius of the arc, in pixels
    property real progress: 0
    property bool done: false
    property real s: 1

    width: 2 * r + 14 * s
    height: width
    preferredRendererType: Shape.CurveRenderer

    ShapePath {
        strokeColor: theme.track
        strokeWidth: 13 * root.s
        fillColor: "transparent"
        PathAngleArc { centerX: root.width / 2; centerY: root.height / 2; radiusX: root.r; radiusY: root.r; startAngle: 0; sweepAngle: 360 }
    }
    ShapePath {
        strokeColor: "#8CFBF3E4"
        strokeWidth: 9 * root.s
        fillColor: "transparent"
        PathAngleArc { centerX: root.width / 2; centerY: root.height / 2; radiusX: root.r; radiusY: root.r; startAngle: 0; sweepAngle: 360 }
    }
    ShapePath {
        strokeColor: root.done ? theme.mint : theme.butter
        strokeWidth: 9 * root.s
        fillColor: "transparent"
        capStyle: ShapePath.RoundCap
        PathAngleArc {
            centerX: root.width / 2; centerY: root.height / 2
            radiusX: root.r; radiusY: root.r
            startAngle: -90
            sweepAngle: 360 * Math.max(root.progress, 0.001)
        }
    }
}
