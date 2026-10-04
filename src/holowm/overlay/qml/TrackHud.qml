import QtQuick
import "../../ui"

// Brief note that a track was skipped, and which way.
Item {
    id: root
    property var fx
    property real s: 1
    // Remember the last direction so the note does not change while it fades out.
    property int direction: 1
    readonly property bool shown: fx.track !== 0
    onFxChanged: if (fx.track !== 0) direction = fx.track

    anchors.horizontalCenter: parent.horizontalCenter
    y: parent.height * 0.8 - height - 14 * s  // just above the workspace note
    width: row.width + 34 * s
    height: 54 * s
    opacity: shown ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 200 } }

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: theme.chip
        border.color: theme.keyline
        border.width: 1.5 * root.s
    }
    Row {
        id: row
        x: 8 * root.s
        anchors.verticalCenter: parent.verticalCenter
        spacing: 11 * root.s
        Rectangle {
            width: 38 * root.s; height: width; radius: width / 2
            color: theme.butter
            Icon {
                anchors.centerIn: parent
                name: root.direction > 0 ? "next" : "previous"
                size: 22 * root.s
                fill: theme.ink
            }
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.direction > 0 ? "Next track" : "Previous track"
            color: theme.cream
            font.family: theme.display
            font.pixelSize: 19 * root.s
            font.weight: Font.DemiBold
        }
    }
}
