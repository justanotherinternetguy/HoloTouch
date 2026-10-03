import QtQuick

// One gesture of the guide: the hand shape, what it does, and how it is done.
Rectangle {
    id: root
    property string pose
    property string title
    property string how
    property real s: 1
    property color accent

    radius: 10 * s
    color: Qt.rgba(accent.r, accent.g, accent.b, 0.045)
    border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.16)
    border.width: 1

    Column {
        x: 14 * root.s
        width: parent.width - 2 * x
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2 * root.s
        Text {
            width: parent.width
            text: root.pose
            color: root.accent
            font.pixelSize: 10 * root.s
            font.capitalization: Font.AllUppercase
            font.letterSpacing: 1.2 * root.s
            elide: Text.ElideRight
        }
        Text {
            width: parent.width
            text: root.title
            color: "#e8fbff"
            font.pixelSize: 14.5 * root.s
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }
        Text {
            width: parent.width
            text: root.how
            color: "#8aa4ad"
            font.pixelSize: 11.5 * root.s
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
        }
    }
}
