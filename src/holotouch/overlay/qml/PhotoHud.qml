import QtQuick

// The photo just taken: the screen flashes as it is, and the picture is shown for a moment as a print.
Item {
    id: root
    property var fx
    property real s: 1
    // Remember the last photo so the print does not go blank while it fades out.
    property string photo: ""
    readonly property bool shown: fx.photo !== ""
    onFxChanged: if (fx.photo !== "" && fx.photo !== photo) { photo = fx.photo; flash.restart() }

    anchors.fill: parent

    Rectangle {
        id: white
        anchors.fill: parent
        color: theme.paper
        opacity: 0
        NumberAnimation { id: flash; target: white; property: "opacity"; from: 0.85; to: 0; duration: 380; easing.type: Easing.OutQuad }
    }
    Rectangle {
        id: card
        x: parent.width - width - 48 * root.s
        y: parent.height - height - 48 * root.s
        width: 340 * root.s
        height: picture.height + 62 * root.s
        radius: 12 * root.s
        color: theme.paper
        border.color: theme.ink
        border.width: 2.5 * root.s
        rotation: -3
        opacity: root.shown ? 1 : 0
        scale: root.shown ? 1 : 0.9
        Behavior on opacity { NumberAnimation { duration: 220 } }
        Behavior on scale { NumberAnimation { duration: 260; easing.type: Easing.OutBack } }

        Image {
            id: picture
            x: 12 * root.s
            y: 12 * root.s
            width: parent.width - 24 * root.s
            height: width * 9 / 16
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            cache: false
            sourceSize.width: 720
            source: root.photo
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            y: picture.y + picture.height + 12 * root.s
            text: "Saved to Pictures"
            color: theme.ink
            font.family: theme.display
            font.pixelSize: 19 * root.s
            font.weight: Font.DemiBold
        }
    }
}
