import QtQuick

// A plain button.
Rectangle {
    id: root
    property string text
    property real s: 1
    property color accent
    signal clicked()

    height: 38 * s
    radius: height / 2
    color: Qt.rgba(accent.r, accent.g, accent.b, hover.hovered && enabled ? 0.18 : 0.07)
    border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.45)
    border.width: 1.5 * s
    opacity: enabled ? 1 : 0.35
    Behavior on opacity { NumberAnimation { duration: 140 } }

    Text {
        anchors.centerIn: parent
        text: root.text
        color: root.accent
        font.pixelSize: 14 * root.s
        font.weight: Font.Medium
    }
    HoverHandler { id: hover; cursorShape: root.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor }
    TapHandler { enabled: root.enabled; onTapped: root.clicked() }
}
