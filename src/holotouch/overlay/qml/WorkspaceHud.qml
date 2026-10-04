import QtQuick
import "../../ui"

// Brief note of the current workspace after a switch.
Item {
    id: root
    property var fx
    property real s: 1
    // Remember the last values so the note does not collapse while it fades out.
    property int current: 0
    property int count: 0
    readonly property bool shown: fx.hudDesktop >= 0
    onFxChanged: if (fx.hudDesktop >= 0) { current = fx.hudDesktop; count = fx.hudCount }

    anchors.horizontalCenter: parent.horizontalCenter
    y: parent.height * 0.8
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
            color: theme.lilac
            Icon { anchors.centerIn: parent; name: "workspaces"; size: 22 * root.s }
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: "Workspace " + (root.current + 1)
            color: theme.cream
            font.family: theme.display
            font.pixelSize: 19 * root.s
            font.weight: Font.DemiBold
        }
        Row {
            anchors.verticalCenter: parent.verticalCenter
            spacing: 6 * root.s
            Repeater {
                model: root.count
                Rectangle {
                    required property int index
                    readonly property bool isCurrent: index === root.current
                    width: (isCurrent ? 26 : 12) * root.s
                    height: 12 * root.s
                    radius: height / 2
                    color: isCurrent ? theme.lilac : "#59FBF3E4"
                    Behavior on width { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
                }
            }
        }
    }
}
