import QtQuick
import "../../ui"

// Brief note that a gesture pressed a key, and what that did.
Item {
    id: root
    property var fx
    property real s: 1
    // Remember the last key so the note does not change while it fades out.
    property string key: "Enter"
    readonly property bool shown: fx.key !== ""
    onFxChanged: if (fx.key !== "") key = fx.key

    anchors.horizontalCenter: parent.horizontalCenter
    y: parent.height * 0.8 - height - 14 * s  // where the track note goes
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
            width: 38 * root.s; height: width; radius: 10 * root.s
            color: theme.mint
            Icon {
                anchors.centerIn: parent
                name: root.key === "Enter" ? "enter" : "plus"
                size: 22 * root.s
                stroke: 2.4
            }
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.key
            color: theme.cream
            font.family: theme.display
            font.pixelSize: 19 * root.s
            font.weight: Font.DemiBold
        }
    }
}
