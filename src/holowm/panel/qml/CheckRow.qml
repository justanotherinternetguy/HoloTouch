import QtQuick
import "../../ui"

// One of the doctor's checks. Fine: one quiet line. Not fine: a card that says what is lost and
// what to do, with the doctor's own line underneath.
Item {
    id: root
    property var check
    property real s: 1
    readonly property bool fine: check.mark === "ok"
    readonly property bool failed: check.mark === "fail"

    height: fine ? 30 * s : card.height

    // -- fine ---------------------------------------------------------------------------------
    Row {
        visible: root.fine
        anchors.verticalCenter: parent.verticalCenter
        spacing: 10 * root.s
        Rectangle {
            width: 24 * root.s; height: width; radius: width / 2
            color: theme.mint
            Icon { anchors.centerIn: parent; name: "check"; size: 15 * root.s; stroke: 3.4 }
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            width: root.width - 34 * root.s
            text: root.check.title
            color: theme.ink
            font.family: theme.body
            font.pixelSize: 14.5 * root.s
            elide: Text.ElideRight
        }
    }

    // -- worth a look (butter disc), or stopping HoloWM from working (coral diamond) ----------
    Rectangle {
        id: card
        visible: !root.fine
        width: parent.width
        height: words.height + 28 * root.s
        radius: 20 * root.s
        color: root.failed ? theme.coralTint : theme.butterTint
        border.color: theme.ink
        border.width: 1.5 * root.s

        Item {
            x: 14 * root.s
            y: 14 * root.s
            width: 34 * root.s
            height: width
            Rectangle {
                anchors.centerIn: parent
                width: (root.failed ? 27 : 32) * root.s
                height: width
                radius: root.failed ? 6 * root.s : width / 2
                rotation: root.failed ? 45 : 0
                color: root.failed ? theme.coral : theme.butter
                border.color: theme.ink
                border.width: 1.5 * root.s
            }
            Icon { anchors.centerIn: parent; name: "bang"; size: 18 * root.s; stroke: 3.4 }
        }
        Column {
            id: words
            x: 60 * root.s
            y: 14 * root.s
            width: parent.width - x - 16 * root.s
            spacing: 5 * root.s
            Text {
                width: parent.width
                text: root.check.title
                color: theme.ink
                font.family: theme.display
                font.pixelSize: 18 * root.s
                font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
            }
            Rectangle {
                visible: root.check.fix !== ""
                width: parent.width
                height: fix.height + 18 * root.s
                radius: 13 * root.s
                color: theme.paper
                border.color: theme.line
                border.width: 1.5 * root.s
                Icon { x: 10 * root.s; y: 10 * root.s; name: "wrench"; size: 18 * root.s }
                Text {
                    id: fix
                    x: 38 * root.s
                    y: 9 * root.s
                    width: parent.width - x - 12 * root.s
                    text: root.check.fix
                    color: theme.ink
                    font.family: theme.body
                    font.pixelSize: 14 * root.s
                    lineHeight: 1.12
                    wrapMode: Text.WordWrap
                }
            }
            Text {
                width: parent.width
                text: root.check.raw
                color: theme.inkMid
                font.family: theme.mono
                font.pixelSize: 12 * root.s
                wrapMode: Text.Wrap
            }
        }
    }
}
