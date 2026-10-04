import QtQuick
import "../../ui"

// Practice mode: one thing to try at a time on the two stand-in windows, a demonstration of it,
// and a clear word when it has been done. `panel` says which step is on and when one is done.
Item {
    id: root
    property real s: 1
    readonly property bool up: panel.state === "running" || panel.state === "paused"
    readonly property bool busy: panel.state === "starting" || panel.state === "stopping"
    readonly property bool practising: up && panel.practice
    readonly property var steps: panel.coach
    readonly property int step: panel.coachStep
    readonly property bool finished: step >= steps.length
    readonly property var now: finished ? null : steps[step]
    readonly property string waiting: {
        if (panel.state === "paused")
            return "Tracking is paused"
        if (panel.hands === 0)
            return "Hold a hand up to the camera"
        return ["Waiting for a pinch over a window", "Waiting for you to carry it and let go",
                "Waiting for both hands to pinch and pull", "Waiting for a thumb-to-pinky pinch"][step] || ""
    }

    // -- before practice: what it is, and the way in ------------------------------------------
    Rectangle {
        visible: !root.practising
        width: parent.width
        height: intro.height + 36 * root.s
        radius: 22 * root.s
        color: theme.paper
        border.color: theme.line
        border.width: 1.5 * root.s
        Row {
            id: intro
            x: 18 * root.s
            y: 18 * root.s
            spacing: 20 * root.s
            GestureStage { gesture: "grab"; u: 1.42 * root.s; playing: root.visible }
            Column {
                width: root.width - 36 * root.s - 170 * 1.42 * root.s - 20 * root.s
                spacing: 8 * root.s
                Text {
                    width: parent.width
                    text: "Try it on stand-in windows"
                    color: theme.ink
                    font.family: theme.display
                    font.pixelSize: 26 * root.s
                    font.weight: Font.DemiBold
                    wrapMode: Text.WordWrap
                    lineHeight: 0.95
                }
                Text {
                    width: parent.width
                    text: "Four short steps: grab a window, move it, resize it with both hands, and open the pie menu. "
                        + "Two stand-in windows take the gestures, so your real ones are left alone."
                    color: theme.inkMid
                    font.family: theme.body
                    font.pixelSize: 15 * root.s
                    lineHeight: 1.15
                    wrapMode: Text.WordWrap
                }
                Item { width: 1; height: 2 * root.s }
                PillButton {
                    s: root.s
                    kind: "main"
                    enabled: !root.busy
                    text: root.busy ? "One moment" : root.up ? "Stop and start practice" : "Start practice"
                    width: implicitWidth
                    onClicked: panel.startPractice()
                }
            }
        }
    }

    // -- practising ---------------------------------------------------------------------------
    Column {
        visible: root.practising
        width: parent.width
        spacing: 14 * root.s

        // The steps: done is a tick, now is a number in a double ring, to come is pale.
        Item {
            width: parent.width
            height: 68 * root.s
            Repeater {
                model: root.steps.length - 1
                Rectangle {
                    required property int index
                    readonly property bool done: index < root.step
                    x: (index + 0.5) * parent.width / root.steps.length + 30 * root.s
                    y: 20 * root.s
                    width: parent.width / root.steps.length - 60 * root.s
                    height: 4 * root.s
                    radius: 2 * root.s
                    color: done ? theme.mint : theme.muted
                    border.color: theme.ink
                    border.width: done ? 1 * root.s : 0
                }
            }
            Repeater {
                model: root.steps
                Item {
                    id: petal
                    required property var modelData
                    required property int index
                    readonly property bool done: index < root.step
                    readonly property bool current: index === root.step
                    x: index * parent.width / root.steps.length
                    width: parent.width / root.steps.length
                    height: parent.height
                    Rectangle {
                        visible: petal.current
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: -6 * root.s
                        width: 56 * root.s; height: width; radius: width / 2
                        color: "transparent"
                        border.color: theme.ink
                        border.width: 2 * root.s
                    }
                    Rectangle {
                        id: disc
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: 44 * root.s; height: width; radius: width / 2
                        color: petal.done ? theme.mint : petal.current ? theme.butter : theme.sunk
                        border.color: petal.done || petal.current ? theme.ink : theme.muted
                        border.width: 2 * root.s
                        // A step that has just been done lands with a small bounce.
                        scale: petal.done ? 1 : 0.92
                        Behavior on scale { NumberAnimation { duration: 320; easing.type: Easing.OutBack; easing.overshoot: 3 } }
                        Icon { visible: petal.done; anchors.centerIn: parent; name: "check"; size: 24 * root.s; stroke: 3.2 }
                        Text {
                            visible: !petal.done
                            anchors.centerIn: parent
                            text: petal.index + 1
                            color: petal.current ? theme.ink : theme.inkSoft
                            font.family: theme.display
                            font.pixelSize: 20 * root.s
                            font.weight: Font.DemiBold
                        }
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 48 * root.s
                        text: petal.modelData.name
                        color: petal.done || petal.current ? theme.ink : theme.inkSoft
                        font.family: theme.display
                        font.pixelSize: 15 * root.s
                        font.weight: Font.DemiBold
                    }
                }
            }
        }

        // What just worked.
        Rectangle {
            visible: panel.coachPraise !== ""
            width: parent.width
            height: 44 * root.s
            radius: height / 2
            color: theme.mint
            border.color: theme.ink
            border.width: 1.5 * root.s
            Rectangle {
                x: 8 * root.s
                anchors.verticalCenter: parent.verticalCenter
                width: 28 * root.s; height: width; radius: width / 2
                color: theme.ink
                Icon { anchors.centerIn: parent; name: "check"; size: 17 * root.s; stroke: 3.4; color: theme.mint }
            }
            Text {
                x: 46 * root.s
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - x - 16 * root.s
                text: panel.coachPraise
                color: theme.ink
                font.family: theme.body
                font.pixelSize: 15 * root.s
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
        }

        // One instruction, and a demonstration of it.
        Rectangle {
            visible: !root.finished
            width: parent.width
            height: lesson.height + 32 * root.s
            radius: 22 * root.s
            color: theme.paper
            border.color: theme.line
            border.width: 1.5 * root.s
            Row {
                id: lesson
                x: 16 * root.s
                y: 16 * root.s
                spacing: 20 * root.s
                GestureStage {
                    gesture: panel.hands === 0 && panel.state === "running" ? "palm" : root.now ? root.now.demo : "palm"
                    u: 1.42 * root.s
                    playing: root.visible
                }
                Column {
                    width: root.width - 32 * root.s - 170 * 1.42 * root.s - 20 * root.s
                    spacing: 7 * root.s
                    Text {
                        text: "Step " + (root.step + 1) + " of " + root.steps.length
                        color: theme.inkMid
                        font.family: theme.body
                        font.pixelSize: 13.5 * root.s
                        font.weight: Font.Bold
                    }
                    Text {
                        width: parent.width
                        text: root.now ? root.now.title : ""
                        color: theme.ink
                        font.family: theme.display
                        font.pixelSize: 28 * root.s
                        font.weight: Font.DemiBold
                        wrapMode: Text.WordWrap
                        lineHeight: 0.95
                    }
                    Text {
                        width: parent.width
                        text: root.now ? root.now.body : ""
                        color: theme.ink
                        font.family: theme.body
                        font.pixelSize: 15.5 * root.s
                        lineHeight: 1.15
                        wrapMode: Text.WordWrap
                    }
                    Rectangle {
                        width: Math.min(wait.implicitWidth + 44 * root.s, parent.width)
                        height: 32 * root.s
                        radius: height / 2
                        color: theme.sunk
                        Rectangle {
                            x: 9 * root.s
                            anchors.verticalCenter: parent.verticalCenter
                            width: 14 * root.s; height: width; radius: width / 2
                            color: "transparent"
                            border.color: theme.ink
                            border.width: 3 * root.s
                        }
                        Text {
                            id: wait
                            x: 31 * root.s
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - x - 10 * root.s
                            text: root.waiting
                            color: theme.ink
                            font.family: theme.body
                            font.pixelSize: 14 * root.s
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                        }
                    }
                }
            }
        }

        // Every step done.
        Rectangle {
            visible: root.finished
            width: parent.width
            height: finish.height + 36 * root.s
            radius: 22 * root.s
            color: theme.paper
            border.color: theme.ink
            border.width: 1.5 * root.s
            Column {
                id: finish
                x: 18 * root.s
                y: 18 * root.s
                width: parent.width - 36 * root.s
                spacing: 8 * root.s
                Text {
                    text: "You're ready"
                    color: theme.ink
                    font.family: theme.display
                    font.pixelSize: 30 * root.s
                    font.weight: Font.DemiBold
                }
                Text {
                    width: parent.width
                    text: "That was every step. Stop practice and start HoloTouch on your real windows?"
                    color: theme.ink
                    font.family: theme.body
                    font.pixelSize: 15.5 * root.s
                    wrapMode: Text.WordWrap
                }
                Row {
                    spacing: 12 * root.s
                    PillButton { s: root.s; kind: "main"; text: "Start for real"; width: implicitWidth; onClicked: panel.startForReal() }
                    PillButton { s: root.s; text: "Go again"; width: implicitWidth; onClicked: panel.coachRestart() }
                }
            }
        }

        Row {
            visible: !root.finished
            spacing: 12 * root.s
            PillButton { s: root.s; text: "Skip this step"; width: implicitWidth; onClicked: panel.coachSkip() }
            PillButton { s: root.s; kind: "quiet"; text: "Start over"; width: implicitWidth; onClicked: panel.coachRestart() }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                width: root.width - 310 * root.s
                horizontalAlignment: Text.AlignRight
                text: "The same line shows on your desktop, above the stand-in windows."
                color: theme.inkMid
                font.family: theme.body
                font.pixelSize: 13 * root.s
                wrapMode: Text.WordWrap
            }
        }
    }
}
