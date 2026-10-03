import QtQuick

// Brief note that a track was skipped, and which way.
Rectangle {
    id: root
    property var fx
    property real s: 1
    property color accent
    // Remember the last direction so the pill does not change while it fades out.
    property int direction: 1
    readonly property bool shown: fx.track !== 0
    onFxChanged: if (fx.track !== 0) direction = fx.track

    anchors.horizontalCenter: parent.horizontalCenter
    y: parent.height * 0.8 - height - 16 * s  // just above the workspace pill
    width: label.width + 56 * s
    height: 64 * s
    radius: height / 2
    color: "#d9040c12"
    border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.5)
    border.width: 1.5 * s
    opacity: shown ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 200 } }

    Text {
        id: label
        anchors.centerIn: parent
        text: root.direction > 0 ? "Next track  ▶▶" : "◀◀  Previous track"
        color: root.accent
        font.pixelSize: 24 * root.s
        font.bold: true
    }
}
