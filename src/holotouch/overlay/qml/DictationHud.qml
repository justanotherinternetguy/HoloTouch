import QtQuick
import "../../ui"

// Says that the microphone is being recorded, then that what was said is being written out.
Item {
    id: root
    property var fx
    property real s: 1
    // Remember the last state so the note does not change while it fades out.
    property string state_: "listening"
    readonly property bool shown: fx.dictation !== ""
    onFxChanged: if (fx.dictation !== "") state_ = fx.dictation
    readonly property bool listening: state_ === "listening"
    readonly property bool failed: state_ === "failed"

    anchors.horizontalCenter: parent.horizontalCenter
    y: parent.height * 0.8 - height - 14 * s  // where the track note goes
    width: row.width + 34 * s
    height: 54 * s
    opacity: shown ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 200 } }

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: theme.chip
        border.color: theme.keyline
        border.width: 1.5 * root.s
    }
    Row {
        id: row
        x: 8 * root.s
        anchors.verticalCenter: parent.verticalCenter
        spacing: 11 * root.s
        Rectangle {
            id: badge
            width: 38 * root.s; height: width; radius: width / 2
            color: root.failed ? theme.cream : root.listening ? theme.coral : theme.butter
            Icon {
                anchors.centerIn: parent
                name: root.failed ? "bang" : "mic"
                size: 22 * root.s
                stroke: 2.2
            }
            // The badge breathes for as long as the microphone is open.
            SequentialAnimation on scale {
                running: root.shown && root.listening
                loops: Animation.Infinite
                alwaysRunToEnd: true
                NumberAnimation { to: 1.12; duration: 600; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1; duration: 600; easing.type: Easing.InOutSine }
            }
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.failed ? "Could not dictate" : root.listening ? "Listening" : "Writing"
            color: theme.cream
            font.family: theme.display
            font.pixelSize: 19 * root.s
            font.weight: Font.DemiBold
        }
    }
}
