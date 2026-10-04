import QtQuick
import "../../ui"

// Diagnostics and the log, out of the way at the bottom: closed unless asked for, or unless
// something has gone wrong, which is when the log matters.
Rectangle {
    id: root
    property bool open: false
    property real s: 1
    readonly property real closedHeight: 44 * s
    readonly property real openHeight: 214 * s
    signal toggled(bool on)

    height: open ? openHeight : closedHeight
    color: theme.cream
    clip: true
    Behavior on height { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

    Rectangle { width: parent.width; height: 1.5 * root.s; color: theme.line }

    Item {
        id: bar
        x: 24 * root.s
        width: parent.width - 48 * root.s
        height: root.open ? 48 * root.s : root.closedHeight
        Row {
            anchors.verticalCenter: parent.verticalCenter
            spacing: 10 * root.s
            Icon { anchors.verticalCenter: parent.verticalCenter; name: root.open ? "down" : "up"; size: 18 * root.s; stroke: 2.6 }
            Text {
                text: "Diagnostics and log"
                color: theme.ink
                font.family: theme.display
                font.pixelSize: 15 * root.s
                font.weight: Font.DemiBold
            }
        }
        Text {
            visible: !root.open
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: panel.debug ? "Tracking view is on" : "Tracking view is off"
            color: theme.inkSoft
            font.family: theme.body
            font.pixelSize: 13 * root.s
        }
        HoverHandler { cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: root.toggled(!root.open) }

        Row {
            visible: root.open
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            spacing: 14 * root.s
            Toggle {
                anchors.verticalCenter: parent.verticalCenter
                width: 190 * root.s
                s: root.s
                compact: true
                label: "Tracking view"
                checked: panel.debug
                onToggled: on => panel.setDebug(on)
            }
            PillButton {
                anchors.verticalCenter: parent.verticalCenter
                s: root.s * 0.86
                text: "Copy log"
                width: implicitWidth
                enabled: panel.log !== ""
                onClicked: panel.copyLog()
            }
        }
    }

    Rectangle {
        x: 24 * root.s
        y: 50 * root.s
        width: parent.width - 48 * root.s
        height: root.openHeight - y - 16 * root.s
        radius: 16 * root.s
        color: theme.ink
        Text {
            anchors.centerIn: parent
            visible: panel.log === ""
            text: "What HoloWM reports while it runs shows up here."
            color: theme.muted
            font.family: theme.mono
            font.pixelSize: 13 * root.s
        }
        Flickable {
            id: view
            // Follows the newest lines until it is scrolled back from them.
            property bool following: true
            anchors.fill: parent
            anchors.margins: 12 * root.s
            clip: true
            contentHeight: text.height
            boundsBehavior: Flickable.StopAtBounds
            onContentYChanged: following = contentY >= contentHeight - height - 4
            onContentHeightChanged: if (following) contentY = Math.max(contentHeight - height, 0)
            Text {
                id: text
                width: view.width
                text: panel.log
                color: "#E3DACB"
                font.family: theme.mono
                font.pixelSize: 12.5 * root.s
                lineHeight: 1.25
                wrapMode: Text.Wrap
                textFormat: Text.PlainText
            }
        }
    }
}
