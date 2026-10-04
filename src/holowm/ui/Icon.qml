import QtQuick
import QtQuick.Shapes
import "Icons.js" as Icons

// One line icon from Icons.js, or any SVG path on a 24-unit grid.
Item {
    id: root
    property string name
    property string path: Icons.path(name)
    property color color: theme.ink
    property color fill: "transparent"
    property real stroke: 2  // in grid units
    property real size: 24

    width: size
    height: size

    Shape {
        width: 24
        height: 24
        scale: root.size / 24
        transformOrigin: Item.TopLeft
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: root.color
            strokeWidth: root.stroke
            fillColor: root.fill
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: root.path }
        }
    }
}
