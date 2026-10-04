import QtQuick
import QtQuick.Shapes
import "../../ui"

// HoloTouch's state in a badge, a word and a sentence. The badge changes shape as well as colour:
// a disc while things are well, a rounded square while paused, a ring while off, a diamond for trouble.
Column {
    id: root
    property string kind: "stopped"  // running | paused | lent | stopped | starting | missing | failed | practising
    property string word
    property string sentence
    property real s: 1
    readonly property bool trouble: kind === "missing" || kind === "failed"
    readonly property bool hollow: kind === "stopped" || kind === "starting"
    readonly property color tone: trouble ? theme.coral : kind === "practising" ? theme.lilac
                                : kind === "paused" || kind === "lent" ? theme.butter : theme.mint

    spacing: 3 * s

    Row {
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 10 * root.s
        Item {
            anchors.verticalCenter: parent.verticalCenter
            width: 34 * root.s
            height: width
            Rectangle {
                visible: !root.hollow
                anchors.centerIn: parent
                width: (root.trouble ? 26 : 30) * root.s
                height: width
                radius: root.trouble ? 6 * root.s : root.kind === "paused" || root.kind === "lent" ? 9 * root.s : width / 2
                rotation: root.trouble ? 45 : 0
                color: root.tone
                border.color: theme.ink
                border.width: 2 * root.s
            }
            Rectangle {
                visible: root.kind === "stopped"
                anchors.centerIn: parent
                width: 30 * root.s; height: width; radius: width / 2
                color: "transparent"
                border.color: theme.ink
                border.width: 3 * root.s
            }
            Shape {
                visible: root.kind === "starting"
                anchors.fill: parent
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    strokeColor: theme.ink
                    strokeWidth: 3 * root.s
                    fillColor: "transparent"
                    strokeStyle: ShapePath.DashLine
                    dashPattern: [1.6, 1.5]
                    PathAngleArc {
                        centerX: 17 * root.s; centerY: 17 * root.s
                        radiusX: 13.5 * root.s; radiusY: 13.5 * root.s
                        startAngle: 0; sweepAngle: 360
                    }
                }
            }
            Icon {
                visible: root.kind !== "starting"
                anchors.centerIn: parent
                name: ({
                    "running": "play", "paused": "pause", "lent": "camera", "stopped": "stop",
                    "missing": "bang", "failed": "bang", "practising": "windows"
                })[root.kind] || "play"
                size: (root.kind === "stopped" ? 20 : 17) * root.s
                stroke: root.kind === "paused" || root.trouble ? 3.6 : 2.4
                fill: root.kind === "running" || root.kind === "stopped" ? theme.ink : "transparent"
            }
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.word
            color: theme.ink
            font.family: theme.display
            font.pixelSize: 26 * root.s
            font.weight: Font.DemiBold
        }
    }
    Text {
        width: root.width
        horizontalAlignment: Text.AlignHCenter
        text: root.sentence
        color: theme.inkMid
        font.family: theme.body
        font.pixelSize: 14.5 * root.s
        wrapMode: Text.WordWrap
        maximumLineCount: 3
        elide: Text.ElideRight
    }
}
