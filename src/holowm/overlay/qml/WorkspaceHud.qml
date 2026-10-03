import QtQuick

// Brief indicator of the current workspace after a switch.
Rectangle {
    id: root
    property var fx
    property real s: 1
    property color accent
    // Remember the last values so the pill does not collapse while it fades out.
    property int current: 0
    property int count: 0
    readonly property bool shown: fx.hudDesktop >= 0
    onFxChanged: if (fx.hudDesktop >= 0) { current = fx.hudDesktop; count = fx.hudCount }

    anchors.horizontalCenter: parent.horizontalCenter
    y: parent.height * 0.8
    width: row.width + 48 * s
    height: 64 * s
    radius: height / 2
    color: "#d9040c12"
    border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.5)
    border.width: 1.5 * s
    opacity: shown ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 200 } }

    Row {
        id: row
        anchors.centerIn: parent
        spacing: 14 * root.s
        Repeater {
            model: root.count
            Rectangle {
                required property int index
                readonly property bool isCurrent: index === root.current
                width: (isCurrent ? 48 : 22) * root.s
                height: 22 * root.s
                radius: 6 * root.s
                color: isCurrent ? root.accent : Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.25)
                Behavior on width { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
            }
        }
    }
}
