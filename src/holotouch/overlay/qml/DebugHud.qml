import QtQuick

// Tracking diagnostics: timings, poses, and the hands and face as the camera sees them.
Item {
    id: root
    property var info
    property real s: 1
    visible: !!info.visible
    x: 24 * s
    y: 60 * s

    readonly property var bones: [
        [0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9], [9, 10], [10, 11], [11, 12],
        [9, 13], [13, 14], [14, 15], [15, 16], [13, 17], [17, 18], [18, 19], [19, 20], [0, 17]
    ]

    Rectangle {
        width: 420 * root.s
        height: column.height + 24 * root.s
        radius: 18 * root.s
        color: theme.chip
        border.color: theme.keyline
        border.width: 1.5 * root.s

        Column {
            id: column
            x: 12 * root.s
            y: 12 * root.s
            spacing: 8 * root.s
            Text {
                text: root.info.text || ""
                color: theme.cream
                font.family: theme.mono
                font.pixelSize: 13 * root.s
            }
            Canvas {
                id: canvas
                width: 396 * root.s
                height: width * 9 / 16
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    ctx.strokeStyle = theme.inkSoft
                    ctx.lineWidth = 1
                    ctx.strokeRect(0.5, 0.5, width - 1, height - 1)
                    var box = root.info.box
                    if (box) {
                        ctx.strokeStyle = theme.butter
                        ctx.setLineDash([6, 4])
                        ctx.strokeRect(box[0] * width, box[1] * height, box[2] * width, box[3] * height)
                        ctx.setLineDash([])
                    }
                    var face = root.info.face || []
                    if (face.length) {
                        ctx.strokeStyle = theme.lilac
                        ctx.lineWidth = 1
                        ctx.beginPath()
                        for (var f = 0; f <= face.length; f++) {
                            var point = face[f % face.length]
                            if (f === 0)
                                ctx.moveTo(point[0] * width, point[1] * height)
                            else
                                ctx.lineTo(point[0] * width, point[1] * height)
                        }
                        ctx.stroke()
                        // The circle a fist has to reach into to touch the chin.
                        var chin = root.info.chin
                        ctx.strokeStyle = theme.mint
                        ctx.beginPath()
                        ctx.arc(chin[0] * width, chin[1] * height, chin[2] * height, 0, 2 * Math.PI)
                        ctx.stroke()
                    }
                    // The hands left out as being in the background are drawn faint, after the ones followed.
                    var followed = root.info.hands || []
                    var hands = followed.concat(root.info.ignored || [])
                    for (var h = 0; h < hands.length; h++) {
                        var points = hands[h]
                        ctx.strokeStyle = h < followed.length ? theme.cream : theme.inkSoft
                        ctx.lineWidth = 1.5
                        ctx.beginPath()
                        for (var b = 0; b < root.bones.length; b++) {
                            var from = points[root.bones[b][0]], to = points[root.bones[b][1]]
                            ctx.moveTo(from[0] * width, from[1] * height)
                            ctx.lineTo(to[0] * width, to[1] * height)
                        }
                        ctx.stroke()
                    }
                }
                Connections {
                    target: bridge
                    function onDebugChanged() { canvas.requestPaint() }
                }
            }
        }
    }
}
