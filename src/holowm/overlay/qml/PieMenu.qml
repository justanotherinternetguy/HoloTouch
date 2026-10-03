import QtQuick

// Marking-menu launcher. Geometry comes from Python; this only draws and animates it.
Item {
    id: root
    property real s: 1
    property color accent
    readonly property var menu: bridge.menu
    readonly property var pie: bridge.pie
    readonly property real childSize: pie.childSize * s

    opacity: menu.open ? 1 : 0
    visible: opacity > 0
    Behavior on opacity { NumberAnimation { duration: 140 } }

    Rectangle {
        readonly property real r: (root.pie.childOffset + root.pie.childSize * 1.15) * root.s
        x: root.menu.cx - r
        y: root.menu.cy - r
        width: 2 * r; height: 2 * r; radius: r
        color: "#b3040c12"
        border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.25)
        border.width: 1.5 * root.s
    }

    // Centres of the parent menus, so the path taken stays visible.
    Repeater {
        model: Math.max(root.menu.trail.length - 1, 0)
        Rectangle {
            required property int index
            readonly property var point: root.menu.trail[index]
            width: 16 * root.s; height: width; radius: width / 2
            x: point[0] - width / 2
            y: point[1] - height / 2
            color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.55)
        }
    }

    Rectangle {
        readonly property real r: root.pie.centerSize * root.s / 2
        x: root.menu.cx - r
        y: root.menu.cy - r
        width: 2 * r; height: 2 * r; radius: r
        color: "#e6071a24"
        border.color: root.accent
        border.width: 2 * root.s
        Text {
            anchors.centerIn: parent
            width: parent.width - 20 * root.s
            text: root.menu.label
            color: "#e8fbff"
            font.pixelSize: 15 * root.s
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            maximumLineCount: 3
            elide: Text.ElideRight
        }
    }

    Repeater {
        model: bridge.menuItems
        Item {
            id: item
            required property var modelData
            required property int index
            readonly property bool hovered: root.menu.hover === index
            x: modelData.x - root.childSize / 2
            y: modelData.y - root.childSize / 2
            width: root.childSize
            height: root.childSize
            z: hovered ? 1 : 0
            scale: hovered ? 1.3 : 1.0
            Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }

            Rectangle {
                anchors.fill: parent
                radius: width / 2
                color: item.hovered ? root.accent : "#e60a2230"
                border.color: root.accent
                border.width: (item.hovered ? 3 : 1.5) * root.s
            }
            Image {
                visible: item.modelData.hasIcon
                anchors.centerIn: parent
                width: parent.width * 0.58
                height: width
                sourceSize: Qt.size(128, 128)
                source: item.modelData.hasIcon ? "image://theme/" + item.modelData.icon : ""
            }
            Text {
                visible: !item.modelData.hasIcon
                anchors.centerIn: parent
                text: item.modelData.name.charAt(0).toUpperCase()
                color: item.hovered ? "#04141c" : "#e8fbff"
                font.pixelSize: root.childSize * 0.42
                font.bold: true
            }
            Rectangle {
                // Marks an item that opens a submenu.
                visible: item.modelData.menu
                width: 13 * root.s; height: width; radius: width / 2
                anchors.right: parent.right
                anchors.top: parent.top
                color: root.accent
                border.color: "#04141c"
                border.width: 1.5 * root.s
            }
        }
    }

    Rectangle {
        readonly property var back: root.menu.back
        readonly property bool hovered: root.menu.hover === -1
        visible: !!back
        x: (back ? back.x : 0) - width / 2
        y: (back ? back.y : 0) - height / 2
        width: root.childSize * 0.8; height: width; radius: width / 2
        scale: hovered ? 1.3 : 1.0
        Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
        color: hovered ? root.accent : "#e60a2230"
        border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.7)
        border.width: 1.5 * root.s
        Text {
            anchors.centerIn: parent
            text: "‹"
            color: parent.hovered ? "#04141c" : "#e8fbff"
            font.pixelSize: parent.height * 0.7
        }
    }
}
