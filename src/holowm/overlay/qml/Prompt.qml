import QtQuick

// One instruction at a time, top centre: the pose a prompted recording is asking for, or the
// step practice mode is on. The bar shows how long is left, or how far along it is.
Item {
    id: root
    property var prompt
    property real s: 1
    readonly property bool holding: !!prompt.holding
    readonly property color tone: holding ? theme.mint : theme.butter

    anchors.horizontalCenter: parent.horizontalCenter
    y: parent.height * 0.1
    width: Math.max(column.width + 80 * s, 520 * s)
    height: column.height + 44 * s
    opacity: prompt.visible ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 200 } }

    Rectangle {
        anchors.fill: parent
        anchors.margins: -2 * root.s
        radius: 30 * root.s
        color: theme.keyline
    }
    Rectangle {
        anchors.fill: parent
        radius: 28 * root.s
        color: theme.ink
    }
    Column {
        id: column
        anchors.centerIn: parent
        spacing: 10 * root.s
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: caption.text !== ""
            width: caption.width + 24 * root.s
            height: caption.height + 8 * root.s
            radius: height / 2
            color: root.tone
            Text {
                id: caption
                anchors.centerIn: parent
                text: root.prompt.caption || ""
                color: theme.ink
                font.family: theme.display
                font.pixelSize: 16 * root.s
                font.weight: Font.DemiBold
            }
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.prompt.text || ""
            color: theme.cream
            font.family: theme.display
            font.pixelSize: 36 * root.s
            font.weight: Font.DemiBold
        }
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 400 * root.s
            height: 10 * root.s
            radius: height / 2
            color: "#40FBF3E4"
            Rectangle {
                width: Math.max(parent.width * (root.prompt.progress || 0), root.prompt.progress > 0 ? height : 0)
                height: parent.height
                radius: height / 2
                color: root.tone
            }
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: text !== ""
            text: root.prompt.detail || ""
            color: "#E3DACB"
            font.family: theme.body
            font.pixelSize: 16 * root.s
        }
    }
}
