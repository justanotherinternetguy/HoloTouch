import QtQuick

// A short label over the desktop. Ink with a cream line at rest; in a hand's colour when aimed at.
Item {
    id: root
    property string text
    property real s: 1
    property bool aimed: false
    property color tone: theme.coral

    width: label.implicitWidth + (aimed ? 30 : 26) * s
    height: label.implicitHeight + (aimed ? 12 : 10) * s

    Rectangle {
        visible: root.aimed
        anchors.fill: parent
        anchors.margins: -3.5 * root.s
        radius: height / 2
        color: theme.hairline
    }
    Rectangle {
        visible: root.aimed
        anchors.fill: parent
        anchors.margins: -2 * root.s
        radius: height / 2
        color: theme.cream
    }
    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: root.aimed ? root.tone : theme.chip
        border.color: theme.keyline
        border.width: root.aimed ? 0 : 1.5 * root.s
    }
    Text {
        id: label
        anchors.centerIn: parent
        text: root.text
        color: root.aimed ? theme.ink : theme.cream
        font.family: theme.display
        font.pixelSize: (root.aimed ? 19 : 16) * root.s
        font.weight: root.aimed ? Font.DemiBold : Font.Medium
    }
}
