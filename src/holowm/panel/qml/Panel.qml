import QtQuick

// The control panel. `panel` is the Python Controller; everything here is driven by it.
Rectangle {
    id: root
    readonly property real s: panel.scale
    readonly property color accent: panel.accent
    readonly property color danger: panel.danger
    readonly property bool up: panel.state === "running" || panel.state === "paused"
    readonly property real pad: 24 * s
    property int tab: 0
    color: "#040c12"

    readonly property string status: {
        switch (panel.state) {
        case "starting": return "Starting…"
        case "stopping": return "Stopping…"
        case "paused": return panel.lent ? "Paused while the camera app is open" : "Paused"
        case "running": return panel.fps > 0 ? "Tracking" : "Waiting for the camera…"
        }
        return "Not running"
    }
    readonly property int problems: panel.checks.filter(check => check.mark === "fail").length

    readonly property var tabs: ["Gestures", "Checks", "Log"]
    readonly property var gestures: [
        { pose: "Thumb + index", title: "Move a window",
          how: "Pinch over a window and carry it. A quick pinch brings it to the front." },
        { pose: "Second hand pinches too", title: "Resize",
          how: "While one hand holds a window, pinch with the other and pull them apart." },
        { pose: "Flick a held window", title: "Maximize or minimize",
          how: "Flick it up and let go to maximize it, down to minimize it." },
        { pose: "Hold at a screen edge", title: "Send to a workspace",
          how: "Carry a window to the left or right edge of the screen and wait there." },
        { pose: "Thumb + middle", title: "Click",
          how: "One pinch is a click, two a double click. Keep it pinched to drag." },
        { pose: "Thumb + pinky", title: "Pie menu",
          how: "Move toward an item and let go to pick it: apps, windows, music." },
        { pose: "Fist, held still", title: "Close a window",
          how: "Hold a fist over the window until the ring completes." },
        { pose: "Two fingers up", title: "Scroll",
          how: "Tilt the two fingers down or back up: the further, the faster." },
        { pose: "Claw, turned", title: "Volume and brightness",
          how: "Grip a knob in the air and turn it. Right hand: volume. Left: brightness." },
        { pose: "Open palm, swept", title: "Switch workspace",
          how: "Sweep an open hand quickly to the left or to the right." },
        { pose: "Fist to chin", title: "Window switcher",
          how: "Every window becomes a card. Point at one and pinch to go to it." },
        { pose: "Peace sign, both hands", title: "Camera",
          how: "Hold both up until the ring completes to open the camera and take a photo." }
    ]

    // -- left: HoloWM itself -------------------------------------------------------------------

    Item {
        id: side
        x: root.pad
        y: root.pad
        width: 300 * root.s
        height: parent.height - 2 * root.pad

        Column {
            id: controls
            width: parent.width
            spacing: 14 * root.s

            Row {
                spacing: 12 * root.s
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 34 * root.s; height: width; radius: width / 2
                    color: "transparent"
                    border.color: root.accent
                    border.width: 3.5 * root.s
                    Rectangle {
                        anchors.centerIn: parent
                        width: 11 * root.s; height: width; radius: width / 2
                        color: root.accent
                    }
                }
                Column {
                    Text {
                        text: "HoloWM"
                        color: "#e8fbff"
                        font.pixelSize: 24 * root.s
                        font.weight: Font.DemiBold
                    }
                    Text {
                        text: "holographic window manager · " + panel.version
                        color: "#8aa4ad"
                        font.pixelSize: 11.5 * root.s
                    }
                }
            }

            PowerButton {
                anchors.horizontalCenter: parent.horizontalCenter
                mode: panel.state
                s: root.s
                accent: root.accent
                onClicked: panel.state === "stopped" ? panel.start() : panel.stop()
            }

            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 8 * root.s
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 9 * root.s; height: width; radius: width / 2
                    color: panel.state === "running" ? root.accent : panel.state === "stopped" ? "#3b5560" : "#8aa4ad"
                }
                Text {
                    text: root.status
                    color: "#e8fbff"
                    font.pixelSize: 15 * root.s
                }
            }

            Row {
                id: stats
                width: parent.width
                spacing: 8 * root.s
                readonly property real each: (width - 2 * spacing) / 3
                Stat { width: stats.each; s: root.s; accent: root.accent; caption: "fps"; value: root.up ? panel.fps : "–" }
                Stat { width: stats.each; s: root.s; accent: root.accent; caption: "hands"; value: root.up ? panel.hands : "–" }
                Stat { width: stats.each; s: root.s; accent: root.accent; caption: "gesture"; value: root.up ? (panel.gesture || "idle") : "–" }
            }

            PillButton {
                width: parent.width
                s: root.s
                accent: root.accent
                enabled: root.up
                text: panel.state === "paused" ? "Resume tracking" : "Pause tracking"
                onClicked: panel.togglePause()
            }
        }

        // Whatever went wrong, in the space the controls and the switches leave between them.
        Text {
            anchors.top: controls.bottom
            anchors.bottom: switches.top
            anchors.topMargin: 10 * root.s
            anchors.bottomMargin: 10 * root.s
            width: parent.width
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: Text.AlignHCenter
            text: panel.error
            color: root.danger
            font.pixelSize: 12.5 * root.s
            wrapMode: Text.Wrap
            elide: Text.ElideRight
            clip: true
        }

        Column {
            id: switches
            anchors.bottom: parent.bottom
            width: parent.width
            spacing: 14 * root.s

            Toggle {
                width: parent.width
                s: root.s
                accent: root.accent
                label: "Tracking view"
                detail: "Show what the camera makes of your hands and face."
                checked: panel.debug
                onToggled: on => panel.setDebug(on)
            }
            Toggle {
                width: parent.width
                s: root.s
                accent: root.accent
                label: "Practice mode"
                detail: "Try gestures on two stand-in windows. Real windows are left alone."
                checked: panel.practice
                enabled: panel.state === "stopped"  // it is decided when HoloWM starts
                onToggled: on => panel.setPractice(on)
            }
            Rectangle { width: parent.width; height: 1; color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.15) }
            Text {
                width: parent.width
                text: root.up ? "HoloWM keeps running when this window is closed."
                              : "Press Start, then hold a hand up to the camera."
                color: "#5d7680"
                font.pixelSize: 11.5 * root.s
                wrapMode: Text.WordWrap
            }
        }
    }

    Rectangle {
        id: divider
        x: side.x + side.width + root.pad
        y: root.pad
        width: 1
        height: parent.height - 2 * root.pad
        color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.15)
    }

    // -- right: the guide, the checks and the log ----------------------------------------------

    Item {
        id: main
        anchors.left: divider.right
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.margins: root.pad

        Row {
            id: tabBar
            spacing: 26 * root.s
            Repeater {
                model: root.tabs
                Item {
                    id: tabItem
                    required property int index
                    required property string modelData
                    readonly property bool current: root.tab === index
                    width: name.width
                    height: 30 * root.s
                    Text {
                        id: name
                        text: tabItem.modelData + (tabItem.index === 1 && root.problems ? "  ·  " + root.problems : "")
                        color: tabItem.current ? "#e8fbff" : tabHover.hovered ? "#b8d4dc" : "#8aa4ad"
                        font.pixelSize: 15 * root.s
                        font.weight: tabItem.current ? Font.DemiBold : Font.Normal
                    }
                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: 2 * root.s
                        radius: height / 2
                        color: root.accent
                        visible: tabItem.current
                    }
                    HoverHandler { id: tabHover; cursorShape: Qt.PointingHandCursor }
                    TapHandler {
                        onTapped: {
                            root.tab = tabItem.index
                            // The checks are run for whoever comes to look at them.
                            if (tabItem.index === 1 && !panel.checks.length && !panel.checking)
                                panel.runChecks()
                        }
                    }
                }
            }
        }

        Item {
            id: pages
            anchors.top: tabBar.bottom
            anchors.topMargin: 14 * root.s
            anchors.bottom: parent.bottom
            width: parent.width

            Flickable {
                anchors.fill: parent
                visible: root.tab === 0
                clip: true
                contentHeight: guide.height
                boundsBehavior: Flickable.StopAtBounds
                Grid {
                    id: guide
                    width: parent.width
                    columns: 2
                    spacing: 8 * root.s
                    Repeater {
                        model: root.gestures
                        GestureCard {
                            required property var modelData
                            width: (guide.width - guide.spacing) / 2
                            height: 84 * root.s
                            s: root.s
                            accent: root.accent
                            pose: modelData.pose
                            title: modelData.title
                            how: modelData.how
                        }
                    }
                }
            }

            Item {
                anchors.fill: parent
                visible: root.tab === 1
                PillButton {
                    id: checkButton
                    width: 150 * root.s
                    s: root.s
                    accent: root.accent
                    enabled: !panel.checking
                    text: panel.checking ? "Checking…" : "Run checks"
                    onClicked: panel.runChecks()
                }
                Text {
                    anchors.left: checkButton.right
                    anchors.leftMargin: 16 * root.s
                    anchors.right: parent.right
                    anchors.verticalCenter: checkButton.verticalCenter
                    text: panel.checking || !panel.checks.length ? "Whether this machine has what HoloWM needs."
                        : root.problems ? (root.problems === 1 ? "1 problem found." : root.problems + " problems found.")
                        : "All good."
                    color: !panel.checking && root.problems ? root.danger : "#8aa4ad"
                    font.pixelSize: 13 * root.s
                    elide: Text.ElideRight
                }
                Flickable {
                    anchors.top: checkButton.bottom
                    anchors.topMargin: 12 * root.s
                    anchors.bottom: parent.bottom
                    width: parent.width
                    clip: true
                    contentHeight: checkList.height
                    boundsBehavior: Flickable.StopAtBounds
                    Column {
                        id: checkList
                        width: parent.width
                        Repeater {
                            model: panel.checks
                            CheckRow {
                                required property var modelData
                                width: checkList.width
                                check: modelData
                                s: root.s
                                accent: root.accent
                                danger: root.danger
                            }
                        }
                    }
                }
            }

            Rectangle {
                anchors.fill: parent
                visible: root.tab === 2
                radius: 10 * root.s
                color: "#060f16"
                border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.16)
                border.width: 1
                Text {
                    anchors.centerIn: parent
                    visible: panel.log === ""
                    text: "What HoloWM reports while it runs shows up here."
                    color: "#5d7680"
                    font.pixelSize: 13 * root.s
                }
                Flickable {
                    id: logView
                    // Follows the newest lines until it is scrolled back from them.
                    property bool following: true
                    anchors.fill: parent
                    anchors.margins: 12 * root.s
                    clip: true
                    contentHeight: logText.height
                    boundsBehavior: Flickable.StopAtBounds
                    onContentYChanged: following = contentY >= contentHeight - height - 4
                    onContentHeightChanged: if (following) contentY = Math.max(contentHeight - height, 0)
                    Text {
                        id: logText
                        width: logView.width
                        text: panel.log
                        color: "#b8d4dc"
                        font.family: "monospace"
                        font.pixelSize: 11.5 * root.s
                        wrapMode: Text.WrapAnywhere
                        textFormat: Text.PlainText
                    }
                }
            }
        }
    }
}
