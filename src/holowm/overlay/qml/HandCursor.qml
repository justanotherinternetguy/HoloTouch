import QtQuick

// One hand: an outer ring, and an inner ring that closes as the pinch closes.
Item {
    id: root
    property var hand
    property real s: 1
    property color accent
    property color danger
    readonly property real size: 64 * s
    readonly property color tone: hand.pose === "fist" ? danger : accent

    x: hand.x - size / 2
    y: hand.y - size / 2
    width: size
    height: size
    opacity: hand.visible ? (hand.armed ? 1.0 : 0.4) : 0
    Behavior on opacity { NumberAnimation { duration: 140 } }

    Rectangle {
        anchors.centerIn: parent
        width: root.size; height: width; radius: width / 2
        color: "#33040c12"
        border.width: 2 * root.s
        border.color: Qt.rgba(root.tone.r, root.tone.g, root.tone.b, 0.55)
    }
    Rectangle {
        anchors.centerIn: parent
        width: root.size - (root.size - 20 * root.s) * root.hand.pinch
        height: width; radius: width / 2
        color: root.hand.active ? Qt.rgba(root.tone.r, root.tone.g, root.tone.b, 0.4) : "transparent"
        border.width: (root.hand.active ? 4 : 3) * root.s
        border.color: root.tone
    }
    Rectangle {
        anchors.centerIn: parent
        width: 8 * root.s; height: width; radius: width / 2
        color: root.tone
    }
    // Scroll arrows: dim while the fingers are at rest, the active one brightens with the speed.
    Column {
        visible: root.hand.pose === "two_finger"
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.verticalCenter: parent.verticalCenter
        spacing: root.size * 0.95
        Text {
            text: "▲"; color: root.accent; font.pixelSize: 16 * root.s
            opacity: 0.35 + 0.65 * Math.max(-root.hand.scroll, 0)
        }
        Text {
            text: "▼"; color: root.accent; font.pixelSize: 16 * root.s
            opacity: 0.35 + 0.65 * Math.max(root.hand.scroll, 0)
        }
    }
}
