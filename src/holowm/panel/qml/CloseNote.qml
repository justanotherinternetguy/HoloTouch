import QtQuick

// Said once, right under the window's close button: closing the panel does not stop HoloWM.
Item {
    id: root
    property real s: 1
    signal dismissed()

    width: 318 * s
    height: 54 * s

    // The pointer up to the close button.
    Rectangle {
        x: parent.width - 30 * root.s
        y: -6 * root.s
        width: 14 * root.s; height: width
        rotation: 45
        color: theme.ink
    }
    Rectangle {
        anchors.fill: parent
        radius: 18 * root.s
        topRightRadius: 6 * root.s
        color: theme.ink
    }
    Column {
        x: 14 * root.s
        anchors.verticalCenter: parent.verticalCenter
        Text {
            text: "Closing this window won't stop HoloWM."
            color: theme.cream
            font.family: theme.body
            font.pixelSize: 13 * root.s
            font.weight: Font.Bold
        }
        Text {
            text: "Press Stop when you want it off."
            color: "#E3DACB"
            font.family: theme.body
            font.pixelSize: 13 * root.s
        }
    }
    Rectangle {
        anchors.right: parent.right
        anchors.rightMargin: 5 * root.s
        anchors.verticalCenter: parent.verticalCenter
        width: 54 * root.s
        height: 44 * root.s
        radius: height / 2
        color: ok.hovered ? theme.paper : theme.cream
        Text {
            anchors.centerIn: parent
            text: "OK"
            color: theme.ink
            font.family: theme.display
            font.pixelSize: 15 * root.s
            font.weight: Font.DemiBold
        }
        HoverHandler { id: ok; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: root.dismissed() }
    }
}
