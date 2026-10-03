import QtQuick

// The round button that starts and stops HoloWM. Rings spread from it while tracking runs.
Item {
    id: root
    property string mode: "stopped"  // the panel's state: stopped | starting | running | paused | stopping
    property real s: 1
    property color accent
    signal clicked()
    readonly property bool busy: mode === "starting" || mode === "stopping"
    readonly property bool tracking: mode === "running"
    readonly property color tone: mode === "paused" ? "#7a8a90" : accent
    readonly property var labels: ({
        "stopped": "Start", "starting": "Starting", "running": "Stop", "paused": "Stop", "stopping": "Stopping"
    })

    width: 172 * s
    height: width

    Rectangle {
        id: wave
        anchors.centerIn: parent
        width: disc.width; height: width; radius: width / 2
        color: "transparent"
        border.color: root.accent
        border.width: 2 * root.s
        visible: root.tracking
        ParallelAnimation {
            running: root.tracking
            loops: Animation.Infinite
            NumberAnimation { target: wave; property: "scale"; from: 1.0; to: 1.24; duration: 1900; easing.type: Easing.OutCubic }
            NumberAnimation { target: wave; property: "opacity"; from: 0.6; to: 0.0; duration: 1900 }
        }
    }
    Rectangle {
        id: disc
        anchors.centerIn: parent
        width: 136 * root.s; height: width; radius: width / 2
        color: Qt.rgba(root.tone.r, root.tone.g, root.tone.b,
                       (root.tracking ? 0.16 : 0.05) + (hover.hovered && !root.busy ? 0.08 : 0))
        border.color: Qt.rgba(root.tone.r, root.tone.g, root.tone.b, root.mode === "stopped" ? 0.6 : 1.0)
        border.width: 3 * root.s
        Behavior on color { ColorAnimation { duration: 200 } }

        Text {
            id: label
            anchors.centerIn: parent
            text: root.labels[root.mode] || ""
            color: "#e8fbff"
            font.pixelSize: (root.busy ? 20 : 30) * root.s
            font.weight: Font.DemiBold
            // Breathes while HoloWM is on its way up or down.
            SequentialAnimation on opacity {
                running: root.busy
                loops: Animation.Infinite
                NumberAnimation { to: 0.35; duration: 550 }
                NumberAnimation { to: 1.0; duration: 550 }
            }
        }
        HoverHandler { id: hover; cursorShape: root.busy ? Qt.ArrowCursor : Qt.PointingHandCursor }
        TapHandler { enabled: !root.busy; onTapped: root.clicked() }
    }
    onBusyChanged: if (!busy) label.opacity = 1
}
