import QtQuick
import "../../ui"

// Window switcher: every window as a card with its own picture. Geometry comes from Python; this
// only draws it. The desktop is dimmed by one flat scrim, the only time the overlay dims anything.
Item {
    id: root
    readonly property var view: bridge.switcher
    readonly property real u: view.u
    // The hand that is pointing colours the selection; the last one is kept while it fades.
    property color tone: theme.coral
    onViewChanged: if (view.side !== "") tone = view.side === "left" ? theme.sky : theme.coral

    opacity: view.open ? 1 : 0
    visible: opacity > 0
    Behavior on opacity { NumberAnimation { duration: 140 } }

    Rectangle {
        anchors.fill: parent
        color: theme.scrim
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
            scale: selected ? 1.1 : 1.0
            Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }

            Item {
                id: picture
                anchors.fill: parent
                anchors.margins: root.view.inset
                anchors.bottomMargin: root.view.titleH
                opacity: card.modelData.minimized ? 0.55 : 1.0

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
                // A window with no picture: its icon, or its first letter, on a plain card.
                Rectangle {
                    visible: !card.hasThumb
                    anchors.fill: parent
                    radius: 10 * root.u
                    color: theme.sunk
                }
                Image {
                    // Large when it stands in for a missing picture, otherwise a badge in the corner.
                    readonly property real side: card.hasThumb ? root.view.badge : root.view.largeIcon
                    visible: card.hasIcon
                    x: card.hasThumb ? frame.x + frame.width - side + 8 * root.u : (parent.width - side) / 2
                    y: card.hasThumb ? frame.y + frame.height - side + 8 * root.u : (parent.height - side) / 2
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
                    color: theme.ink
                    font.family: theme.display
                    font.pixelSize: 56 * root.u
                    font.weight: Font.DemiBold
                }

                // The frame hugs the picture as it is painted: cream and ink at rest, and a thick
                // band of the pointing hand's colour once selected.
                Item {
                    id: frame
                    readonly property real w: card.hasThumb ? thumb.paintedWidth : parent.width
                    readonly property real h: card.hasThumb ? thumb.paintedHeight : parent.height
                    x: (parent.width - w) / 2
                    y: (parent.height - h) / 2
                    width: w
                    height: h
                    Rectangle {
                        visible: card.selected
                        anchors.fill: parent
                        anchors.margins: -9.5 * root.u
                        radius: 15 * root.u
                        color: "transparent"
                        border.color: theme.hairline
                        border.width: 1.5 * root.u
                    }
                    Rectangle {
                        visible: card.selected
                        anchors.fill: parent
                        anchors.margins: -8 * root.u
                        radius: 13.5 * root.u
                        color: "transparent"
                        border.color: theme.cream
                        border.width: 2 * root.u
                    }
                    Rectangle {
                        visible: card.selected
                        anchors.fill: parent
                        anchors.margins: -6 * root.u
                        radius: 11.5 * root.u
                        color: "transparent"
                        border.color: root.tone
                        border.width: 6 * root.u
                    }
                    Rectangle {
                        visible: !card.selected
                        anchors.fill: parent
                        anchors.margins: -3.5 * root.u
                        radius: 9 * root.u
                        color: "transparent"
                        border.color: theme.hairline
                        border.width: 1.5 * root.u
                    }
                    Rectangle {
                        visible: !card.selected
                        anchors.fill: parent
                        anchors.margins: -2 * root.u
                        radius: 7.5 * root.u
                        color: "transparent"
                        border.color: theme.cream
                        border.width: 2 * root.u
                    }
                }
            }

            // The title, as a chip under the picture.
            Item {
                id: title
                anchors.horizontalCenter: parent.horizontalCenter
                y: parent.height - root.view.titleH + (root.view.titleH - height) / 2 + 3 * root.u
                width: Math.min(name.implicitWidth + 26 * root.u, parent.width - 8 * root.u)
                height: name.implicitHeight + 10 * root.u
                Rectangle {
                    visible: card.selected
                    anchors.fill: parent
                    anchors.margins: -3.5 * root.u
                    radius: height / 2
                    color: theme.hairline
                }
                Rectangle {
                    visible: card.selected
                    anchors.fill: parent
                    anchors.margins: -2 * root.u
                    radius: height / 2
                    color: theme.cream
                }
                Rectangle {
                    anchors.fill: parent
                    radius: height / 2
                    color: card.selected ? root.tone : theme.chip
                    border.color: theme.keyline
                    border.width: card.selected ? 0 : 1.5 * root.u
                }
                Text {
                    id: name
                    anchors.centerIn: parent
                    width: Math.min(implicitWidth, parent.width - 22 * root.u)
                    elide: Text.ElideRight
                    text: card.modelData.title
                    color: card.selected ? theme.ink : theme.cream
                    font.family: theme.display
                    font.pixelSize: 15 * root.u
                    font.weight: card.selected ? Font.DemiBold : Font.Medium
                }
            }

            Rectangle {
                // Workspace number, for a window that is not on the current workspace.
                visible: card.modelData.desktop > 0
                x: 2 * root.u
                y: 2 * root.u
                width: 28 * root.u
                height: width
                radius: width / 2
                color: theme.lilac
                border.color: theme.ink
                border.width: 2 * root.u
                Text {
                    anchors.centerIn: parent
                    text: card.modelData.desktop
                    color: theme.ink
                    font.family: theme.display
                    font.pixelSize: 15 * root.u
                    font.weight: Font.DemiBold
                }
            }
        }
    }

    // What a pinch will do now, under the cards.
    Item {
        readonly property bool chosen: root.view.selected >= 0
        x: root.view.x + (root.view.w - width) / 2
        y: root.view.y + root.view.h - height - 8 * root.u
        width: Math.min(words.implicitWidth + 44 * root.u, root.view.w)
        height: words.implicitHeight + 18 * root.u
        Rectangle {
            anchors.fill: parent
            radius: height / 2
            color: theme.chip
            border.color: theme.keyline
            border.width: 1.5 * root.u
        }
        Text {
            id: words
            anchors.centerIn: parent
            width: Math.min(implicitWidth, parent.width - 40 * root.u)
            elide: Text.ElideMiddle
            textFormat: Text.PlainText
            text: parent.chosen ? "Pinch to go to " + root.view.label + "  ·  touch your chin again to dismiss"
                                : "Point at a window  ·  pinch, or touch your chin again, to dismiss"
            color: theme.cream
            font.family: theme.display
            font.pixelSize: 16 * root.u
            font.weight: Font.Medium
        }
    }
}
