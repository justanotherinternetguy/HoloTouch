import QtQuick

// The pose a prompted recording is asking for, and how long is left to get ready or to hold it.
Rectangle {
    id: root
    property var prompt
    property real s: 1
    property color accent
    readonly property bool holding: !!prompt.holding
    readonly property color tone: holding ? accent : "#8aa4ad"

    anchors.horizontalCenter: parent.horizontalCenter
    y: parent.height * 0.14
    width: Math.max(column.width + 96 * s, 620 * s)
    height: column.height + 56 * s
    radius: 16 * s
    color: "#e6040c12"
    border.color: Qt.rgba(tone.r, tone.g, tone.b, holding ? 0.9 : 0.4)
    border.width: (holding ? 3 : 1.5) * s
    opacity: prompt.visible ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 200 } }

    Column {
        id: column
        anchors.centerIn: parent
        spacing: 14 * root.s
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.prompt.caption || ""
            color: root.tone
            font.pixelSize: 18 * root.s
            font.capitalization: Font.AllUppercase
            font.letterSpacing: 2 * root.s
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.prompt.text || ""
            color: "#e8fbff"
            font.pixelSize: 40 * root.s
            font.weight: Font.DemiBold
        }
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 460 * root.s
            height: 8 * root.s
            radius: height / 2
            color: Qt.rgba(root.tone.r, root.tone.g, root.tone.b, 0.2)
            Rectangle {
                width: parent.width * (root.prompt.progress || 0)
                height: parent.height
                radius: height / 2
                color: root.tone
            }
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.prompt.detail || ""
            color: "#8aa4ad"
            font.pixelSize: 15 * root.s
        }
    }
}
