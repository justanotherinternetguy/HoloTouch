import QtQuick

// Window switcher: every window as a card. Geometry comes from Python; this only draws it.
Item {
    id: root
    property color accent
    readonly property var view: bridge.switcher
    readonly property real u: view.u

    opacity: view.open ? 1 : 0
    visible: opacity > 0
    Behavior on opacity { NumberAnimation { duration: 140 } }

    Rectangle {
        x: root.view.x
        y: root.view.y
        width: root.view.w
        height: root.view.h
        radius: 20 * root.u
        color: "#d9040c12"
        border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.3)
        border.width: 1.5 * root.u

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 20 * root.u
            width: parent.width - 60 * root.u
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideMiddle
            text: root.view.selected >= 0 ? root.view.label : "Pinch, or touch your chin again, to dismiss"
            color: root.view.selected >= 0 ? "#e8fbff" : "#8fb4c0"
            font.pixelSize: 17 * root.u
        }
    }

    Repeater {
        model: bridge.switcherItems
        Item {
            id: card
            required property var modelData
            required property int index
            readonly property bool selected: root.view.selected === index
            readonly property bool hasThumb: modelData.thumb !== ""
            readonly property bool hasIcon: modelData.icon !== ""
            x: modelData.x
            y: modelData.y
            width: root.view.cardW
            height: root.view.cardH
            z: selected ? 1 : 0
            scale: selected ? 1.07 : 1.0
            Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }

            Rectangle {
                anchors.fill: parent
                anchors.margins: -5 * root.u
                radius: 16 * root.u
                visible: card.selected
                color: "transparent"
                border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.2)
                border.width: 5 * root.u
            }
            Rectangle {
                anchors.fill: parent
                radius: 11 * root.u
                color: card.selected ? "#f20d3140" : "#e60a2230"
                border.color: card.selected ? root.accent : Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.3)
                border.width: (card.selected ? 3 : 1.2) * root.u
            }

            Item {
                id: picture
                anchors.fill: parent
                anchors.margins: root.view.inset
                anchors.bottomMargin: root.view.titleH
                opacity: card.modelData.minimized ? 0.45 : 1.0

                // Python makes the pictures at the size they are shown, so plain smoothing is enough.
                Image {
                    id: thumb
                    visible: card.hasThumb
                    anchors.fill: parent
                    fillMode: Image.PreserveAspectFit
                    source: card.modelData.thumb
                    cache: false
                    smooth: true
                }
                Rectangle {
                    visible: card.hasThumb
                    anchors.centerIn: parent
                    width: thumb.paintedWidth
                    height: thumb.paintedHeight
                    color: "transparent"
                    border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.35)
                    border.width: 1
                }
                Image {
                    // Large when it stands in for a missing snapshot, otherwise a badge in the corner.
                    readonly property real side: card.hasThumb ? root.view.badge : root.view.largeIcon
                    visible: card.hasIcon
                    x: card.hasThumb ? parent.width - side + 6 * root.u : (parent.width - side) / 2
                    y: card.hasThumb ? parent.height - side + 6 * root.u : (parent.height - side) / 2
                    width: side
                    height: side
                    source: card.modelData.icon
                    cache: false
                    smooth: true
                }
                Text {
                    visible: !card.hasThumb && !card.hasIcon
                    anchors.centerIn: parent
                    text: card.modelData.title.charAt(0).toUpperCase()
                    color: "#e8fbff"
                    font.pixelSize: 56 * root.u
                    font.bold: true
                }
            }

            Text {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: root.view.inset
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
                text: card.modelData.title
                color: card.selected ? "#ffffff" : "#c9e9f2"
                font.pixelSize: 14 * root.u
            }

            Rectangle {
                // Workspace number, for a window that is not on the current workspace.
                visible: card.modelData.desktop > 0
                x: 8 * root.u
                y: 8 * root.u
                width: 26 * root.u
                height: width
                radius: width / 2
                color: root.accent
                border.color: "#04141c"
                border.width: 1.5 * root.u
                Text {
                    anchors.centerIn: parent
                    text: card.modelData.desktop
                    color: "#04141c"
                    font.pixelSize: 14 * root.u
                    font.bold: true
                }
            }
        }
    }
}
