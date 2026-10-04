import QtQuick
import "../../ui"

// A button. One ink one per view, for the thing to do next; the rest are paper with an ink line.
// Each rests on a ledge and sinks onto it when pressed.
Item {
    id: root
    property string text
    property string icon  // a name from Icons.js, or none
    property string kind: "plain"  // plain | main | quiet
    property real s: 1
    signal clicked()
    readonly property bool main: kind === "main"
    readonly property bool quiet: kind === "quiet"
    readonly property real ledge: enabled && !quiet ? 4 * s : 0

    implicitWidth: row.width + 40 * s
    height: 44 * s + 4 * s

    Rectangle {
        visible: root.ledge > 0
        y: 4 * root.s
        width: parent.width
        height: 44 * root.s
        radius: height / 2
        color: root.main ? theme.ledge : theme.ink
    }
    Rectangle {
        id: face
        y: tap.pressed ? root.ledge : 0
        width: parent.width
        height: 44 * root.s
        radius: height / 2
        color: !root.enabled ? theme.sunk : root.quiet ? (hover.hovered ? theme.sunk : "transparent")
             : root.main ? (hover.hovered ? theme.inkRaised : theme.ink) : (hover.hovered ? theme.cream : theme.paper)
        border.color: !root.enabled ? theme.muted : theme.ink
        border.width: root.main || root.quiet ? 0 : 2 * root.s
        Behavior on y { NumberAnimation { duration: 60 } }

        Row {
            id: row
            anchors.centerIn: parent
            spacing: 9 * root.s
            Icon {
                visible: root.icon !== ""
                anchors.verticalCenter: parent.verticalCenter
                name: root.icon
                size: 18 * root.s
                stroke: 3
                color: label.color
            }
            Text {
                id: label
                text: root.text
                color: !root.enabled ? theme.inkSoft : root.main ? theme.cream : theme.ink
                font.family: theme.display
                font.pixelSize: 16 * root.s
                font.weight: Font.DemiBold
                font.underline: root.quiet
            }
        }
    }
    HoverHandler { id: hover; cursorShape: root.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor }
    TapHandler { id: tap; enabled: root.enabled; onTapped: root.clicked() }
}
