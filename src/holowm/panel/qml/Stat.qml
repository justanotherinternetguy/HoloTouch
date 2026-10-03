import QtQuick

// One live figure and what it counts.
Rectangle {
    id: root
    property string value
    property string caption
    property real s: 1
    property color accent

    height: 58 * s
    radius: 8 * s
    color: Qt.rgba(accent.r, accent.g, accent.b, 0.05)
    border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.18)
    border.width: 1

    Column {
        anchors.centerIn: parent
        spacing: 2 * root.s
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            width: root.width - 12 * root.s
            horizontalAlignment: Text.AlignHCenter
            text: root.value
            color: "#e8fbff"
            font.pixelSize: 20 * root.s
            font.weight: Font.DemiBold
            fontSizeMode: Text.HorizontalFit
            minimumPixelSize: 11 * root.s
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.caption
            color: "#8aa4ad"
            font.pixelSize: 10 * root.s
            font.capitalization: Font.AllUppercase
            font.letterSpacing: 1.2 * root.s
        }
    }
}
