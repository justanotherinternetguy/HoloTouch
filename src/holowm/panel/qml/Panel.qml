import QtQuick
import "../../ui"

// The control panel. `panel` is the Python Controller and `theme` the colours and typefaces;
// everything here is driven by the two.
//
// On the left, the station: the dial, the state, what HoloWM sees right now, and the two switches
// worth reaching for. On the right, the guide, practice and the machine checks. Diagnostics and
// the log sit in a drawer underneath.
Rectangle {
    id: root
    readonly property real s: panel.scale
    readonly property bool up: panel.state === "running" || panel.state === "paused"
    readonly property bool busy: panel.state === "starting" || panel.state === "stopping"
    readonly property real pad: 24 * s
    property int tab: 0
    color: theme.cream

    readonly property var failed: panel.checks.filter(check => check.mark === "fail")
    readonly property var lacking: panel.checks.filter(check => check.mark === "warn")
    readonly property var fine: panel.checks.filter(check => check.mark === "ok")
    // Something stops HoloWM working: a check failed, or the camera is not answering.
    readonly property bool alarm: failed.length > 0 || panel.camera === "missing"

    // The state in a badge, a word and a sentence.
    readonly property var status: {
        const hands = ["Hold a hand up to begin.", "Watching one hand.", "Watching both of your hands."]
        switch (panel.state) {
        case "starting": return { kind: "starting", word: "Starting", sentence: "Waking the camera." }
        case "stopping": return { kind: "starting", word: "Stopping", sentence: "Letting go of the camera." }
        case "paused":
            return panel.lent
                ? { kind: "lent", word: "Paused", sentence: "The camera app has the webcam. Close it to carry on." }
                : { kind: "paused", word: "Paused", sentence: "Tracking paused. Your hands do nothing until you resume." }
        case "running":
            if (panel.camera === "missing")
                return { kind: "missing", word: "No camera", sentence: "Running, but it can't see you." }
            if (panel.camera === "waiting")
                return { kind: "starting", word: "Running", sentence: "Waiting for the camera." }
            return panel.practice
                ? { kind: "practising", word: "Practising", sentence: "Your real windows are left alone." }
                : { kind: "running", word: "Running", sentence: hands[Math.min(panel.hands, 2)] }
        }
        return panel.error !== ""
            ? { kind: "failed", word: "Stopped", sentence: panel.error }
            : { kind: "stopped", word: "Stopped", sentence: "Ready when you are." }
    }
    // The gesture in progress, as a word that fits a bubble.
    readonly property var gestureWords: ({
        "move": "Move", "click": "Click", "menu": "Menu", "close": "Close", "scroll": "Scroll",
        "knob": "Dial", "switcher": "Switcher", "camera": "Camera", "dictate": "Dictate", "spell": "Spell"
    })
    readonly property var gestures: [
        { demo: "move", live: "move", kind: "windows", pose: "Thumb + index", title: "Move a window",
          how: "Pinch over a window and carry it. A quick pinch brings it to the front." },
        { demo: "resize", live: "move", kind: "windows", pose: "Second hand pinches too", title: "Resize",
          how: "While one hand holds a window, pinch with the other and pull them apart." },
        { demo: "flick", live: "", kind: "windows", pose: "Flick a held window", title: "Maximize or minimize",
          how: "Flick it up and let go to maximize it, down to minimize it." },
        { demo: "edge", live: "", kind: "windows", pose: "Hold at a screen edge", title: "Send to a workspace",
          how: "Carry a window to the left or right edge of the screen and wait there." },
        { demo: "click", live: "click", kind: "pointer", pose: "Point, thumb down", title: "Click",
          how: "Point up, thumb out, then tap the thumb down onto your middle finger. Twice is a double click; keep it down to drag." },
        { demo: "menu", live: "menu", kind: "system", pose: "Thumb + pinky", title: "Pie menu",
          how: "Move toward an item and let go to pick it: apps, windows, music." },
        { demo: "close", live: "close", kind: "windows", pose: "Fist, held still", title: "Close a window",
          how: "Hold a fist over the window until the ring completes." },
        { demo: "scroll", live: "scroll", kind: "pointer", pose: "Two fingers up", title: "Scroll",
          how: "Tip the two fingers at the screen to scroll down, straighten them up to scroll up: the further, the faster." },
        { demo: "knob", live: "knob", kind: "system", pose: "Claw, turned", title: "Volume and brightness",
          how: "Grip a knob in the air and turn it. Right hand: volume. Left: brightness." },
        { demo: "swipe", live: "", kind: "pointer", pose: "Open palm, swept right", title: "Enter",
          how: "Sweep an open hand quickly to the right to press the Enter key." },
        { demo: "switcher", live: "switcher", kind: "windows", pose: "Fist to chin", title: "Window switcher",
          how: "Every window becomes a card. Point at one and pinch to go to it." },
        { demo: "camera", live: "camera", kind: "system", pose: "Peace sign, both hands", title: "Camera",
          how: "Hold both up until the ring completes to open the camera and take a photo." },
        { demo: "dictate", live: "dictate", kind: "system", pose: "Thumb and pinky out", title: "Dictate",
          how: "Hold up the letter Y and speak. Let go, and what you said is typed where the keyboard is." },
        { demo: "spell", live: "spell", kind: "system", pose: "Thumb, index and pinky out", title: "App launcher",
          how: "Hold up I love you, then fingerspell an app's name until it is the only one left, or a macro's letters: R, S opens Instagram Reels." },
        { demo: "clap", live: "", kind: "system", pose: "Clap twice", title: "New tab",
          how: "With a web browser in front, clap your hands twice to open a new tab in it." }
    ]

    // The checks are run once at the start, so the panel can say how the machine stands.
    Component.onCompleted: panel.runChecks()
    // Trouble brings its own help forward: the checks, and the log.
    property bool troubled: false
    Connections {
        target: panel
        function onChanged() {
            const trouble = panel.camera === "missing" || (panel.state === "stopped" && panel.error !== "")
            if (trouble && !root.troubled) {
                panel.setDrawerOpen(true)
                if (panel.camera === "missing") {
                    root.tab = 2
                    panel.runChecks()
                }
            }
            root.troubled = trouble
        }
    }

    // -- left: the station ---------------------------------------------------------------------

    Item {
        id: station
        x: root.pad
        y: 20 * root.s
        width: 256 * root.s
        height: parent.height - 40 * root.s

        Column {
            width: parent.width
            spacing: 13 * root.s

            Row {
                spacing: 12 * root.s
                Item {
                    // Two rings, one for each hand.
                    anchors.verticalCenter: parent.verticalCenter
                    width: 46 * root.s
                    height: 30 * root.s
                    Rectangle {
                        width: 30 * root.s; height: width; radius: width / 2
                        color: "transparent"
                        border.color: theme.sky
                        border.width: 5 * root.s
                    }
                    Rectangle {
                        x: 16 * root.s
                        width: 30 * root.s; height: width; radius: width / 2
                        color: "transparent"
                        border.color: theme.coral
                        border.width: 5 * root.s
                    }
                }
                Column {
                    Text {
                        text: "HoloWM"
                        color: theme.ink
                        font.family: theme.display
                        font.pixelSize: 22 * root.s
                        font.weight: Font.DemiBold
                    }
                    Text {
                        text: "holographic window manager · " + panel.version
                        color: theme.inkSoft
                        font.family: theme.body
                        font.pixelSize: 12 * root.s
                    }
                }
            }

            PowerButton {
                anchors.horizontalCenter: parent.horizontalCenter
                mode: panel.state
                camera: panel.camera
                practice: panel.practice
                s: root.s
                onClicked: panel.state === "stopped" ? panel.start() : panel.stop()
            }

            StateLine {
                width: parent.width
                s: root.s
                kind: root.status.kind
                word: root.status.word
                sentence: root.status.sentence
            }

            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 10 * root.s
                readonly property bool live: root.up && panel.camera !== "missing"
                Stat {
                    s: root.s
                    caption: panel.hands === 1 ? "hand" : "hands"
                    value: parent.live ? panel.hands : "–"
                    tone: parent.live ? "steady" : "empty"
                }
                Stat {
                    s: root.s
                    caption: "gesture"
                    value: parent.live ? (root.gestureWords[panel.gesture] || "Idle") : "–"
                    tone: !parent.live ? "empty" : panel.gesture !== "" ? "active" : "steady"
                }
                Stat {
                    s: root.s
                    caption: "frames/s"
                    value: root.up ? panel.fps : "–"
                    tone: !root.up ? "empty" : panel.camera === "missing" ? "problem" : "steady"
                }
            }

            PillButton {
                width: parent.width
                s: root.s
                enabled: root.up && panel.camera !== "missing"
                kind: panel.state === "paused" ? "main" : "plain"
                icon: panel.state === "paused" ? "play" : "pause"
                text: panel.state === "paused" ? "Resume tracking" : "Pause tracking"
                onClicked: panel.togglePause()
            }

            Toggle {
                width: parent.width
                s: root.s
                tone: theme.lilac
                label: "Practice mode"
                detail: panel.state === "stopped" ? "Start with two stand-in windows. Your real ones are left alone."
                      : panel.practice ? "On. Stop to go back to real windows." : "Stop first to switch it on."
                checked: panel.practice
                enabled: panel.state === "stopped"  // it is decided when HoloWM starts
                onToggled: on => panel.setPractice(on)
            }
        }

        Row {
            anchors.bottom: parent.bottom
            width: parent.width
            spacing: 8 * root.s
            Icon { name: "info"; size: 17 * root.s; stroke: 2.2 }
            Text {
                width: parent.width - 25 * root.s
                text: root.up ? "HoloWM keeps running if you close this window."
                              : "Press Start, then hold a hand up to the camera."
                color: theme.inkMid
                font.family: theme.body
                font.pixelSize: 13 * root.s
                wrapMode: Text.WordWrap
            }
        }
    }

    Rectangle {
        id: divider
        x: 304 * root.s
        width: 1.5 * root.s
        height: parent.height
        color: theme.line
    }

    // -- right: guide, practice, checks -------------------------------------------------------

    Item {
        id: main
        anchors.left: divider.right
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: drawer.top

        Rectangle {
            id: tabs
            x: root.pad
            y: 10 * root.s
            width: tabRow.width + 8 * root.s
            height: 48 * root.s
            radius: height / 2
            color: theme.sunk
            Row {
                id: tabRow
                x: 4 * root.s
                y: 4 * root.s
                Repeater {
                    model: ["Guide", "Practice", "Checks"]
                    Rectangle {
                        id: tabItem
                        required property int index
                        required property string modelData
                        readonly property bool current: root.tab === index
                        width: tabLabel.width + 40 * root.s
                        height: 40 * root.s
                        radius: height / 2
                        color: current ? theme.ink : tabHover.hovered ? theme.line : "transparent"
                        Row {
                            id: tabLabel
                            anchors.centerIn: parent
                            spacing: 8 * root.s
                            Text {
                                text: tabItem.modelData
                                color: tabItem.current ? theme.cream : theme.ink
                                font.family: theme.display
                                font.pixelSize: 15 * root.s
                                font.weight: Font.DemiBold
                            }
                            // On Checks: a coral diamond when something stops HoloWM working, else a
                            // butter count of the optional extras that are missing.
                            Rectangle {
                                visible: tabItem.index === 2 && root.alarm
                                anchors.verticalCenter: parent.verticalCenter
                                width: 14 * root.s; height: width; radius: 3.5 * root.s
                                rotation: 45
                                color: theme.coral
                                border.color: tabItem.current ? theme.cream : theme.ink
                                border.width: 1.5 * root.s
                            }
                            Rectangle {
                                visible: tabItem.index === 2 && !root.alarm && root.lacking.length > 0
                                anchors.verticalCenter: parent.verticalCenter
                                width: Math.max(count.width + 10 * root.s, 20 * root.s)
                                height: 20 * root.s
                                radius: height / 2
                                color: theme.butter
                                border.color: theme.ink
                                border.width: tabItem.current ? 0 : 1.5 * root.s
                                Text {
                                    id: count
                                    anchors.centerIn: parent
                                    text: root.lacking.length
                                    color: theme.ink
                                    font.family: theme.display
                                    font.pixelSize: 13 * root.s
                                    font.weight: Font.DemiBold
                                }
                            }
                        }
                        HoverHandler { id: tabHover; cursorShape: Qt.PointingHandCursor }
                        TapHandler { onTapped: root.tab = tabItem.index }
                    }
                }
            }
        }

        Item {
            id: pages
            x: root.pad
            y: 68 * root.s
            width: parent.width - 2 * root.pad
            height: parent.height - y

            // -- Guide -----------------------------------------------------------------------
            Flickable {
                id: guidePage
                anchors.fill: parent
                visible: root.tab === 0
                clip: true
                contentHeight: guide.height + 16 * root.s
                boundsBehavior: Flickable.StopAtBounds
                Column {
                    id: guide
                    width: parent.width
                    spacing: 14 * root.s

                    // Start here.
                    Rectangle {
                        width: parent.width
                        height: 204 * root.s
                        radius: 22 * root.s
                        color: theme.paper
                        border.color: theme.line
                        border.width: 1.5 * root.s
                        GestureStage {
                            id: heroStage
                            x: 16 * root.s
                            y: 16 * root.s
                            gesture: "grab"
                            u: (172 / 104) * root.s
                            playing: guidePage.visible
                        }
                        Column {
                            x: heroStage.x + heroStage.width + 18 * root.s
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - x - 18 * root.s
                            spacing: 6 * root.s
                            Rectangle {
                                width: first.width + 20 * root.s
                                height: 22 * root.s
                                radius: height / 2
                                color: theme.butter
                                Text {
                                    id: first
                                    anchors.centerIn: parent
                                    text: "Start here"
                                    color: theme.ink
                                    font.family: theme.body
                                    font.pixelSize: 12.5 * root.s
                                    font.weight: Font.Bold
                                }
                            }
                            Text {
                                text: "Try a pinch"
                                color: theme.ink
                                font.family: theme.display
                                font.pixelSize: 30 * root.s
                                font.weight: Font.DemiBold
                            }
                            Text {
                                width: parent.width
                                text: "Touch your thumb to your index finger over a window, then carry it. Open your fingers to let go."
                                color: theme.inkMid
                                font.family: theme.body
                                font.pixelSize: 15 * root.s
                                lineHeight: 1.15
                                wrapMode: Text.WordWrap
                            }
                            // What HoloWM makes of it, as it happens.
                            Rectangle {
                                readonly property bool seen: root.up && panel.gesture === "move"
                                width: Math.min(live.implicitWidth + 44 * root.s, parent.width)
                                height: 32 * root.s
                                radius: height / 2
                                color: seen ? theme.mint : theme.sunk
                                Rectangle {
                                    x: 5 * root.s
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 22 * root.s; height: width; radius: width / 2
                                    color: parent.seen ? theme.ink : "transparent"
                                    border.color: theme.ink
                                    border.width: parent.seen ? 0 : 3 * root.s
                                    Icon {
                                        visible: parent.parent.seen
                                        anchors.centerIn: parent
                                        name: "check"
                                        size: 14 * root.s
                                        stroke: 3.6
                                        color: theme.mint
                                    }
                                }
                                Text {
                                    id: live
                                    x: 34 * root.s
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: parent.width - x - 10 * root.s
                                    elide: Text.ElideRight
                                    text: parent.seen ? "That's it. You're moving a window."
                                        : panel.state === "stopped" ? "Press Start to try it"
                                        : panel.state === "paused" ? "Tracking is paused"
                                        : root.up && panel.hands === 0 ? "Hold a hand up to the camera"
                                        : "HoloWM is watching for it"
                                    color: theme.ink
                                    font.family: theme.body
                                    font.pixelSize: 14 * root.s
                                    font.weight: Font.DemiBold
                                }
                            }
                        }
                    }

                    // How the machine stands, in one line.
                    Rectangle {
                        visible: panel.checks.length > 0 && !panel.checking
                        width: parent.width
                        height: 66 * root.s
                        radius: 22 * root.s
                        color: root.failed.length ? theme.coralTint : theme.paper
                        border.color: root.failed.length ? theme.ink : theme.line
                        border.width: 1.5 * root.s
                        Item {
                            x: 16 * root.s
                            anchors.verticalCenter: parent.verticalCenter
                            width: 34 * root.s
                            height: width
                            Rectangle {
                                anchors.centerIn: parent
                                width: (root.failed.length ? 27 : 34) * root.s
                                height: width
                                radius: root.failed.length ? 6 * root.s : width / 2
                                rotation: root.failed.length ? 45 : 0
                                color: root.failed.length ? theme.coral : theme.mint
                                border.color: theme.ink
                                border.width: root.failed.length ? 1.5 * root.s : 0
                            }
                            Icon { anchors.centerIn: parent; name: root.failed.length ? "bang" : "check"; size: 20 * root.s; stroke: 3 }
                        }
                        Column {
                            x: 64 * root.s
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - x - 150 * root.s
                            Text {
                                width: parent.width
                                elide: Text.ElideRight
                                text: root.failed.length ? "This machine needs a fix first" : "This machine is ready"
                                color: theme.ink
                                font.family: theme.display
                                font.pixelSize: 17 * root.s
                                font.weight: Font.DemiBold
                            }
                            Text {
                                width: parent.width
                                elide: Text.ElideRight
                                text: root.failed.length ? root.failed[0].title + "."
                                    : root.lacking.length === 1 ? "One optional extra is missing: " + root.lacking[0].title.toLowerCase() + "."
                                    : root.lacking.length ? root.lacking.length + " optional extras are missing."
                                    : "Everything HoloWM needs is here."
                                color: theme.inkMid
                                font.family: theme.body
                                font.pixelSize: 14 * root.s
                            }
                        }
                        PillButton {
                            anchors.right: parent.right
                            anchors.rightMargin: 14 * root.s
                            y: (parent.height - 44 * root.s) / 2 - 2 * root.s
                            s: root.s * 0.92
                            text: "See checks"
                            width: implicitWidth
                            onClicked: root.tab = 2
                        }
                    }

                    Text {
                        text: "All " + root.gestures.length + " gestures"
                        color: theme.ink
                        font.family: theme.display
                        font.pixelSize: 18 * root.s
                        font.weight: Font.DemiBold
                    }
                    Grid {
                        id: cards
                        width: parent.width
                        columns: 3
                        spacing: 12 * root.s
                        Repeater {
                            model: root.gestures
                            GestureCard {
                                required property var modelData
                                width: (cards.width - 2 * cards.spacing) / 3
                                // Every card in a row is as tall as the tallest text needs.
                                height: 248 * root.s
                                s: root.s
                                gesture: modelData.demo
                                kind: modelData.kind
                                pose: modelData.pose
                                title: modelData.title
                                how: modelData.how
                                lit: root.up && modelData.live !== "" && modelData.live === panel.gesture && modelData.demo !== "resize"
                            }
                        }
                    }
                }
            }

            // -- Practice --------------------------------------------------------------------
            Coach {
                anchors.fill: parent
                visible: root.tab === 1
                s: root.s
            }

            // -- Checks ----------------------------------------------------------------------
            Flickable {
                anchors.fill: parent
                visible: root.tab === 2
                clip: true
                contentHeight: checkList.height + 16 * root.s
                boundsBehavior: Flickable.StopAtBounds
                Column {
                    id: checkList
                    width: parent.width
                    spacing: 12 * root.s

                    // The camera is not answering: one problem, what it usually is, what to do.
                    Rectangle {
                        visible: panel.camera === "missing"
                        width: parent.width
                        height: cameraHelp.height + 32 * root.s
                        radius: 22 * root.s
                        color: theme.coralTint
                        border.color: theme.ink
                        border.width: 1.5 * root.s
                        Column {
                            id: cameraHelp
                            x: 18 * root.s
                            y: 16 * root.s
                            width: parent.width - 36 * root.s
                            spacing: 8 * root.s
                            Text {
                                text: "The camera isn't answering"
                                color: theme.ink
                                font.family: theme.display
                                font.pixelSize: 24 * root.s
                                font.weight: Font.DemiBold
                            }
                            Text {
                                width: parent.width
                                text: "HoloWM started, but no pictures are arriving from the camera. Usually it is one of these."
                                color: theme.ink
                                font.family: theme.body
                                font.pixelSize: 15 * root.s
                                wrapMode: Text.WordWrap
                            }
                            Repeater {
                                model: [
                                    ["Another app has it.", "Only one program can use a webcam at a time. Close video calls and camera apps."],
                                    ["It's unplugged or switched off.", "Check the cable, or the camera switch on your laptop."],
                                    ["HoloWM isn't allowed to open it.", "The checks below test the camera and say what to change."]
                                ]
                                Rectangle {
                                    required property var modelData
                                    required property int index
                                    width: cameraHelp.width
                                    height: cause.height + 16 * root.s
                                    radius: 14 * root.s
                                    color: theme.paper
                                    border.color: theme.line
                                    border.width: 1.5 * root.s
                                    Rectangle {
                                        x: 12 * root.s
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 26 * root.s; height: width; radius: width / 2
                                        color: theme.ink
                                        Text {
                                            anchors.centerIn: parent
                                            text: parent.parent.index + 1
                                            color: theme.cream
                                            font.family: theme.display
                                            font.pixelSize: 15 * root.s
                                            font.weight: Font.DemiBold
                                        }
                                    }
                                    Text {
                                        id: cause
                                        x: 50 * root.s
                                        y: 8 * root.s
                                        width: parent.width - x - 12 * root.s
                                        textFormat: Text.StyledText
                                        text: "<b>" + parent.modelData[0] + "</b> " + parent.modelData[1]
                                        color: theme.ink
                                        font.family: theme.body
                                        font.pixelSize: 14 * root.s
                                        lineHeight: 1.12
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }
                            Row {
                                spacing: 12 * root.s
                                PillButton { s: root.s; kind: "main"; text: "Try again"; width: implicitWidth; onClicked: panel.restart() }
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "HoloWM also keeps trying by itself."
                                    color: theme.inkMid
                                    font.family: theme.body
                                    font.pixelSize: 13 * root.s
                                }
                            }
                        }
                    }

                    Item {
                        width: parent.width
                        height: 52 * root.s
                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - again.width - 14 * root.s
                            Text {
                                width: parent.width
                                elide: Text.ElideRight
                                text: panel.checking ? "Checking this machine"
                                    : root.failed.length === 1 ? "One thing stops HoloWM working"
                                    : root.failed.length ? root.failed.length + " things stop HoloWM working"
                                    : panel.camera === "missing" ? "The checks found nothing wrong"
                                    : "This machine is ready"
                                color: theme.ink
                                font.family: theme.display
                                font.pixelSize: 24 * root.s
                                font.weight: Font.DemiBold
                            }
                            Text {
                                width: parent.width
                                elide: Text.ElideRight
                                text: panel.checking ? "Looking at the session, the camera and the extras."
                                    : root.failed.length ? "Each says what to change. Check again when you have."
                                    : panel.camera === "missing" ? "So the camera is most likely in use elsewhere, or unplugged."
                                    : root.lacking.length === 1 ? "Everything HoloWM needs is here. One optional extra is missing."
                                    : root.lacking.length ? "Everything HoloWM needs is here. " + root.lacking.length + " optional extras are missing."
                                    : "Everything HoloWM needs is here, and every extra too."
                                color: theme.inkMid
                                font.family: theme.body
                                font.pixelSize: 15 * root.s
                            }
                        }
                        PillButton {
                            id: again
                            anchors.right: parent.right
                            y: 2 * root.s
                            s: root.s
                            enabled: !panel.checking
                            text: panel.checking ? "Checking" : "Check again"
                            width: implicitWidth
                            onClicked: panel.runChecks()
                        }
                    }

                    Text {
                        visible: root.failed.length > 0
                        text: "Needs fixing"
                        color: theme.ink
                        font.family: theme.display
                        font.pixelSize: 16 * root.s
                        font.weight: Font.DemiBold
                    }
                    Repeater {
                        model: root.failed
                        CheckRow { required property var modelData; width: checkList.width; check: modelData; s: root.s }
                    }
                    Text {
                        visible: root.lacking.length > 0
                        text: "Worth a look"
                        color: theme.ink
                        font.family: theme.display
                        font.pixelSize: 16 * root.s
                        font.weight: Font.DemiBold
                    }
                    Repeater {
                        model: root.lacking
                        CheckRow { required property var modelData; width: checkList.width; check: modelData; s: root.s }
                    }
                    Text {
                        visible: root.fine.length > 0
                        text: "All fine"
                        color: theme.ink
                        font.family: theme.display
                        font.pixelSize: 16 * root.s
                        font.weight: Font.DemiBold
                    }
                    Grid {
                        width: parent.width
                        columns: 2
                        columnSpacing: 16 * root.s
                        rowSpacing: 2 * root.s
                        Repeater {
                            model: root.fine
                            CheckRow {
                                required property var modelData
                                width: (checkList.width - 16 * root.s) / 2
                                check: modelData
                                s: root.s
                            }
                        }
                    }
                }
            }
        }
    }

    Drawer {
        id: drawer
        anchors.left: divider.right
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        s: root.s
        open: panel.drawerOpen
        onToggled: on => panel.setDrawerOpen(on)
    }

    // What the close button does, said once, right under it.
    CloseNote {
        visible: root.up && !panel.closeNoteSeen
        anchors.right: parent.right
        anchors.rightMargin: 10 * root.s
        y: 8 * root.s
        s: root.s
        onDismissed: panel.dismissCloseNote()
    }
}
