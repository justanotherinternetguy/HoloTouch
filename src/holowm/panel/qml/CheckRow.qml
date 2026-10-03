import QtQuick

// One of the doctor's checks: how it went, what was checked, and what was found.
Item {
    id: root
    property var check
    property real s: 1
    property color accent
    property color danger
    readonly property color tone: check.mark === "ok" ? accent : check.mark === "warn" ? "#ffc857" : danger

    height: Math.max(words.height, badge.height) + 14 * s

    Rectangle {
        id: badge
        y: 7 * root.s
        width: 20 * root.s; height: width; radius: width / 2
        color: Qt.rgba(root.tone.r, root.tone.g, root.tone.b, 0.14)
        border.color: root.tone
        border.width: 1.5 * root.s
        Text {
            anchors.centerIn: parent
            text: root.check.mark === "ok" ? "✓" : root.check.mark === "warn" ? "!" : "✕"
            color: root.tone
            font.pixelSize: 11 * root.s
            font.bold: true
        }
    }
    Column {
        id: words
        x: badge.width + 12 * root.s
        y: 7 * root.s
        width: parent.width - x
        spacing: 1 * root.s
        Text {
            width: parent.width
            text: root.check.label
            color: "#e8fbff"
            font.pixelSize: 13.5 * root.s
            wrapMode: Text.WordWrap
        }
        Text {
            width: parent.width
            visible: text !== ""
            text: root.check.detail
            color: root.check.mark === "ok" ? "#8aa4ad" : root.tone
            font.pixelSize: 11.5 * root.s
            wrapMode: Text.Wrap
        }
    }
}
