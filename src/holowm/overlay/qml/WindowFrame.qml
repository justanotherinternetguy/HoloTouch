import QtQuick

// Outline around the window the hand is over, holding, resizing or about to close.
Item {
    id: root
    property var frame
    property real s: 1
    property color accent
    property color danger
    readonly property bool closing: frame.mode === "close"
    readonly property bool held: frame.mode === "grab" || frame.mode === "resize"
    readonly property color tone: closing ? danger : accent

    x: frame.x
    y: frame.y
    width: frame.w
    height: frame.h
    opacity: frame.visible ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 120 } }

    // Glide between windows while hovering; follow the hand exactly while holding.
    Behavior on x { enabled: !root.held; NumberAnimation { duration: 90; easing.type: Easing.OutCubic } }
    Behavior on y { enabled: !root.held; NumberAnimation { duration: 90; easing.type: Easing.OutCubic } }
    Behavior on width { enabled: !root.held; NumberAnimation { duration: 90; easing.type: Easing.OutCubic } }
    Behavior on height { enabled: !root.held; NumberAnimation { duration: 90; easing.type: Easing.OutCubic } }

    Rectangle {
        anchors.fill: parent
        anchors.margins: -5 * root.s
        radius: 13 * root.s
        visible: root.held || root.closing
        color: "transparent"
        border.color: Qt.rgba(root.tone.r, root.tone.g, root.tone.b, 0.18)
        border.width: 5 * root.s
    }
    Rectangle {
        anchors.fill: parent
        radius: 8 * root.s
        color: Qt.rgba(root.tone.r, root.tone.g, root.tone.b, root.closing ? 0.16 : root.held ? 0.08 : 0.03)
        border.color: Qt.rgba(root.tone.r, root.tone.g, root.tone.b, root.held || root.closing ? 0.95 : 0.5)
        border.width: (root.held ? 3 : 2) * root.s
    }
    Repeater {
        model: 4
        Item {
            id: corner
            required property int index
            readonly property bool atRight: index % 2 === 1
            readonly property bool atBottom: index >= 2
            width: 28 * root.s
            height: 28 * root.s
            x: atRight ? root.width - width : 0
            y: atBottom ? root.height - height : 0
            Rectangle {
                width: parent.width; height: 4 * root.s; radius: height / 2; color: root.tone
                y: corner.atBottom ? parent.height - height : 0
            }
            Rectangle {
                width: 4 * root.s; height: parent.height; radius: width / 2; color: root.tone
                x: corner.atRight ? parent.width - width : 0
            }
        }
    }
    Rectangle {
        visible: root.frame.label !== ""
        anchors.centerIn: parent
        width: label.width + 36 * root.s
        height: label.height + 18 * root.s
        radius: height / 2
        color: "#d9040c12"
        border.color: root.accent
        border.width: 1.5 * root.s
        Text {
            id: label
            anchors.centerIn: parent
            text: root.frame.label
            color: "#e8fbff"
            font.pixelSize: 22 * root.s
            font.family: "monospace"
        }
    }
}
