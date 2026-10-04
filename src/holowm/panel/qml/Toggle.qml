import QtQuick

// A labelled switch. It does not flip itself: whoever handles toggled() changes `checked`.
// One that cannot change now says why in its detail line, and is drawn pale.
Item {
    id: root
    property string label
    property string detail
    property bool checked: false
    property color tone: theme.mint
    property bool compact: false  // just the label beside the switch, on one line
    property real s: 1
    signal toggled(bool on)

    height: Math.max(words.height, 44 * s)

    Column {
        id: words
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width - track.width - 12 * root.s
        spacing: 1 * root.s
        Text {
            width: parent.width
            horizontalAlignment: root.compact ? Text.AlignRight : Text.AlignLeft
            text: root.label
            color: root.enabled ? theme.ink : theme.inkSoft
            font.family: theme.display
            font.pixelSize: (root.compact ? 14.5 : 16) * root.s
            font.weight: Font.DemiBold
        }
        Text {
            visible: !root.compact && text !== ""
            width: parent.width
            text: root.detail
            color: theme.inkSoft
            font.family: theme.body
            font.pixelSize: 13 * root.s
            wrapMode: Text.WordWrap
        }
    }
    Rectangle {
        id: track
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: 56 * root.s
        height: 32 * root.s
        radius: height / 2
        color: root.checked ? root.tone : theme.sunk
        border.color: root.enabled ? theme.ink : theme.muted
        border.width: 2 * root.s
        Behavior on color { ColorAnimation { duration: 140 } }
        Rectangle {
            // The knob's side says the state as well as the colour does.
            x: root.checked ? parent.width - width - 5 * root.s : 5 * root.s
            anchors.verticalCenter: parent.verticalCenter
            width: 22 * root.s; height: width; radius: width / 2
            color: root.enabled || root.checked ? theme.ink : theme.muted
            Behavior on x { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
        }
    }
    HoverHandler { cursorShape: root.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor }
    TapHandler { enabled: root.enabled; onTapped: root.toggled(!root.checked) }
}
