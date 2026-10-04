import QtQuick

// One gesture of the guide: a small looping demonstration, what it does, the hand shape, and how.
Rectangle {
    id: root
    property string gesture  // which demonstration to play
    property string title
    property string pose
    property string how
    property string kind: "windows"  // windows | pointer | system
    property bool lit: false  // HoloTouch is seeing this gesture right now
    property real s: 1

    height: column.height + 22 * s
    radius: 20 * s
    color: theme.paper
    border.color: lit ? theme.ink : theme.line
    border.width: (lit ? 2.5 : 1.5) * s

    Column {
        id: column
        x: 10 * root.s
        y: 10 * root.s
        width: parent.width - 20 * root.s
        spacing: 3 * root.s
        GestureStage {
            gesture: root.gesture
            u: parent.width / 170
            color: root.lit ? theme.butter : theme.sunk
        }
        Item { width: 1; height: 3 * root.s }
        Text {
            width: parent.width
            text: root.title
            color: theme.ink
            font.family: theme.display
            font.pixelSize: 16.5 * root.s
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }
        Row {
            spacing: 6 * root.s
            // The marker's shape says the family as well as its colour does.
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 10 * root.s; height: width
                radius: root.kind === "windows" ? width / 2 : 2.5 * root.s
                rotation: root.kind === "system" ? 45 : 0
                color: root.kind === "windows" ? theme.lilac : root.kind === "pointer" ? theme.butter : theme.mint
                border.color: theme.ink
                border.width: 1.5 * root.s
            }
            Text {
                text: root.pose
                color: theme.inkMid
                font.family: theme.body
                font.pixelSize: 12.5 * root.s
                font.weight: Font.Bold
            }
        }
        Text {
            width: parent.width
            text: root.how
            color: theme.inkMid
            font.family: theme.body
            font.pixelSize: 13 * root.s
            lineHeight: 1.12
            wrapMode: Text.WordWrap
        }
    }
}
