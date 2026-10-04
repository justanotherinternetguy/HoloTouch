import QtQuick
import QtQuick.Shapes

// An illustrated hand in one pose: a palm and five capsule fingers on a 96-unit grid. Coral is
// the right hand and sky the left, as on the overlay; fingertips that touch get a cream dot.
Item {
    id: root
    property string pose: "open"  // open | index | aim | press | pinky | fist | two | claw | peace | y
    property string side: "right"
    property real size: 64
    property bool plain: false  // cream instead of the hand's colour, for use on a coloured ground
    readonly property color tone: plain ? theme.cream : side === "left" ? theme.sky : theme.coral
    // Each finger from its knuckle to its tip, then the thumb.
    readonly property var fingers: ({
        "open": "M37 52 L33 18 M46 52 L45 12 M55 52 L57 17 M63 54 L68 28 M35 68 L15 50",
        "index": "M37 52 L31 30 L21 38 M46 52 L45 12 M55 52 L57 17 M63 54 L68 28 M35 68 L19 43",
        "aim": "M37 52 L33 18 M46 52 L46 40 M55 52 L55 42 M63 54 L63 45 M35 68 L15 50",
        "press": "M37 52 L33 18 M46 52 L46 40 M55 52 L55 42 M63 54 L63 45 M35 68 L44 55",
        "pinky": "M37 52 L33 18 M46 52 L45 12 M55 52 L57 17 M63 54 L64 38 L47 43 M35 68 L43 49",
        "fist": "M37 52 L37 42 M46 52 L46 40 M55 52 L55 42 M63 54 L63 45 M35 68 L48 60",
        "two": "M37 52 L31 18 M46 52 L49 13 M55 52 L55 42 M63 54 L63 45 M35 68 L47 61",
        "claw": "M37 52 L30 33 M46 52 L45 28 M55 52 L60 32 M63 54 L72 41 M35 68 L19 58",
        "peace": "M37 52 L27 20 M46 52 L53 15 M55 52 L55 42 M63 54 L63 45 M35 68 L47 61",
        "y": "M37 52 L37 42 M46 52 L46 40 M55 52 L55 42 M63 54 L76 32 M35 68 L15 50"
    })
    readonly property var touches: ({ "index": [20, 40], "press": [46, 50], "pinky": [45, 45] })
    readonly property var touch: touches[pose] || null

    width: size
    height: size

    Item {
        width: 96
        height: 96
        scale: root.size / 96
        transformOrigin: Item.TopLeft
        // The left hand is the right one mirrored.
        transform: Scale { origin.x: 48; xScale: root.side === "left" ? -1 : 1 }

        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: theme.ink
                strokeWidth: 14
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                PathSvg { path: root.fingers[root.pose] || root.fingers.open }
            }
            ShapePath {
                strokeColor: theme.ink
                strokeWidth: 5
                fillColor: theme.ink
                PathRectangle { x: 31; y: 46; width: 36; height: 36; radius: 15 }
            }
            ShapePath {
                strokeColor: root.tone
                strokeWidth: 9
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                PathSvg { path: root.fingers[root.pose] || root.fingers.open }
            }
            ShapePath {
                strokeColor: "transparent"
                fillColor: root.tone
                PathRectangle { x: 31; y: 46; width: 36; height: 36; radius: 15 }
            }
        }
        Rectangle {
            visible: root.touch !== null
            x: (root.touch ? root.touch[0] : 0) - width / 2
            y: (root.touch ? root.touch[1] : 0) - height / 2
            width: 13.5; height: width; radius: width / 2
            color: theme.cream
            border.color: theme.ink
            border.width: 2.5
        }
    }
}
