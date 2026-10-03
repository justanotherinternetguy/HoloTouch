import QtQuick

// Glow on the screen edge that fills while a held window is pushed toward the next workspace.
Item {
    id: root
    property var fx
    property real s: 1
    property color accent
    readonly property int side: fx.edgeSide
    readonly property real progress: fx.edgeProgress

    Rectangle {
        visible: root.side !== 0
        width: 60 * root.s
        height: parent.height
        x: root.side > 0 ? parent.width - width : 0
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop {
                position: root.side > 0 ? 1.0 : 0.0
                color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.2 + 0.6 * root.progress)
            }
            GradientStop { position: root.side > 0 ? 0.0 : 1.0; color: "transparent" }
        }
    }
    Rectangle {
        visible: root.side !== 0
        width: 6 * root.s
        height: parent.height * root.progress
        x: root.side > 0 ? parent.width - width : 0
        y: (parent.height - height) / 2
        radius: width / 2
        color: root.accent
    }
}
