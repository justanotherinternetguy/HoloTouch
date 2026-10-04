import QtQuick

// The petal that names a hand: L or R, pointed toward the cursor it hangs from.
Item {
    id: root
    property bool isLeft: false
    property color tone: theme.coral
    property real s: 1
    property real fade: 1  // dimmed on a hand that is lost

    width: 22 * s
    height: 22 * s

    Repeater {
        // Ink hairline, cream line, then the colour: the same shape three times, shrinking.
        model: [
            { grow: 3.5, colour: theme.hairline, fade: 1 },
            { grow: 2, colour: theme.cream, fade: 1 },
            { grow: 0, colour: String(root.tone), fade: root.fade }
        ]
        Rectangle {
            required property var modelData
            anchors.fill: parent
            anchors.margins: -modelData.grow * root.s
            radius: height / 2
            topLeftRadius: root.isLeft ? radius : (4 + modelData.grow) * root.s
            topRightRadius: root.isLeft ? (4 + modelData.grow) * root.s : radius
            color: modelData.colour
            opacity: modelData.fade
        }
    }
    Text {
        anchors.centerIn: parent
        text: root.isLeft ? "L" : "R"
        color: theme.ink
        font.family: theme.display
        font.pixelSize: 13 * root.s
        font.weight: Font.Bold
    }
}
