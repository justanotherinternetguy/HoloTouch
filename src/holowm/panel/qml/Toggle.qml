import QtQuick

// A labelled switch. It does not flip itself: whoever handles toggled() changes `checked`.
Item {
    id: root
    property string label
    property string detail
    property bool checked: false
    property real s: 1
    property color accent
    signal toggled(bool on)

    height: Math.max(words.height, track.height)
    opacity: enabled ? 1 : 0.4
    Behavior on opacity { NumberAnimation { duration: 140 } }

    Column {
        id: words
        width: parent.width - track.width - 14 * root.s
        spacing: 2 * root.s
        Text {
            width: parent.width
            text: root.label
            color: "#e8fbff"
            font.pixelSize: 14 * root.s
            font.weight: Font.Medium
        }
        Text {
            width: parent.width
            text: root.detail
            color: "#8aa4ad"
            font.pixelSize: 11.5 * root.s
            wrapMode: Text.WordWrap
        }
    }
    Rectangle {
        id: track
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: 44 * root.s
        height: 24 * root.s
        radius: height / 2
        color: root.checked ? Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.35) : "#14262e"
        border.color: root.checked ? root.accent : "#3b5560"
        border.width: 1.5 * root.s
        Behavior on color { ColorAnimation { duration: 140 } }
        Rectangle {
            x: (root.checked ? parent.width - width - 4 * root.s : 4 * root.s)
            anchors.verticalCenter: parent.verticalCenter
            width: 16 * root.s; height: width; radius: width / 2
            color: root.checked ? root.accent : "#8aa4ad"
            Behavior on x { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
        }
    }
    HoverHandler { cursorShape: root.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor }
    TapHandler { enabled: root.enabled; onTapped: root.toggled(!root.checked) }
}
