import QtQuick
import QtQuick.Shapes
import "../../ui"

// A small looping demonstration of one gesture: an illustrated hand, and what it acts on.
// Drawn on a 170 by 104 unit stage and scaled by `u`. With `playing` off, the hand holds its pose.
Rectangle {
    id: root
    property string gesture: "move"
    property real u: 1
    property bool playing: true

    width: 170 * u
    height: 104 * u
    radius: 14 * u
    color: theme.sunk
    clip: true

    component Pane: Rectangle {
        width: 56; height: 38; radius: 8
        color: theme.paper
        border.color: theme.ink
        border.width: 2.5
    }
    // Swings a property back and forth for as long as the stage is playing.
    component Sway: SequentialAnimation {
        id: sway
        property real from: 0
        property real to: 1
        property int time: 1400
        property int rest: 200
        running: root.playing
        loops: Animation.Infinite
        NumberAnimation { to: sway.to; duration: sway.time; easing.type: Easing.InOutSine }
        PauseAnimation { duration: sway.rest }
        NumberAnimation { to: sway.from; duration: sway.time; easing.type: Easing.InOutSine }
        PauseAnimation { duration: sway.rest }
    }

    Loader {
        width: 170
        height: 104
        scale: root.u
        transformOrigin: Item.TopLeft
        sourceComponent: ({
            "grab": grab, "move": move, "resize": resize, "flick": flick, "edge": edge, "click": click,
            "menu": menu, "close": close, "scroll": scroll, "knob": knob, "swipe": swipe,
            "switcher": switcher, "camera": camera, "dictate": dictate, "clap": clap
        })[root.gesture] || palm
    }

    Component {
        id: palm
        Item { HandFigure { x: 49; y: 16; size: 72; pose: "open" } }
    }
    Component {
        id: grab
        Item {
            Pane { x: 52; y: 34; width: 62; height: 42 }
            // Open, then pinched, over the window.
            HandFigure {
                x: 70; y: 27; size: 66; pose: "open"
                SequentialAnimation on opacity {
                    running: root.playing; loops: Animation.Infinite
                    PauseAnimation { duration: 900 }
                    NumberAnimation { to: 0; duration: 120 }
                    PauseAnimation { duration: 1300 }
                    NumberAnimation { to: 1; duration: 120 }
                }
            }
            HandFigure {
                x: 70; y: 27; size: 66; pose: "index"; opacity: 0
                SequentialAnimation on opacity {
                    running: root.playing; loops: Animation.Infinite
                    PauseAnimation { duration: 900 }
                    NumberAnimation { to: 1; duration: 120 }
                    PauseAnimation { duration: 1300 }
                    NumberAnimation { to: 0; duration: 120 }
                }
            }
        }
    }
    Component {
        id: move
        Item {
            Item {
                x: -18
                Sway on x { from: -18; to: 18 }
                Pane { x: 44; y: 36 }
                HandFigure { x: 59; y: 28; size: 64; pose: "index" }
            }
        }
    }
    Component {
        id: resize
        Item {
            Pane {
                x: 56; y: 34; width: 62; height: 40
                Sway on scale { from: 1; to: 1.26 }
            }
            HandFigure {
                x: 17; y: 48; size: 52; pose: "index"; side: "left"
                Sway on x { from: 17; to: 8 }
                Sway on y { from: 48; to: 55 }
            }
            HandFigure {
                x: 105; y: 10; size: 52; pose: "index"
                Sway on x { from: 105; to: 114 }
                Sway on y { from: 10; to: 3 }
            }
        }
    }
    Component {
        id: flick
        Item {
            Rectangle { x: 18; y: 7; width: 134; height: 3; radius: 1.5; color: theme.ink; opacity: 0.35 }
            Item {
                y: 12
                SequentialAnimation on y {
                    running: root.playing; loops: Animation.Infinite
                    PauseAnimation { duration: 1300 }
                    NumberAnimation { to: -22; duration: 220; easing.type: Easing.OutCubic }
                    PauseAnimation { duration: 700 }
                    NumberAnimation { to: 12; duration: 400; easing.type: Easing.InOutSine }
                }
                Pane { x: 50; y: 40; width: 50; height: 34 }
                HandFigure { x: 63; y: 33; size: 58; pose: "index" }
            }
        }
    }
    Component {
        id: edge
        Item {
            Rectangle { x: 160; y: 18; width: 20; height: 68; radius: 10; color: theme.ink }
            Rectangle {
                id: fill
                x: 160; width: 20; radius: 10; color: theme.butter
                height: 0
                y: 52 - height / 2
                SequentialAnimation on height {
                    running: root.playing; loops: Animation.Infinite
                    PauseAnimation { duration: 1500 }
                    NumberAnimation { to: 68; duration: 1300 }
                    PauseAnimation { duration: 300 }
                    PropertyAction { value: 0 }
                    PauseAnimation { duration: 500 }
                }
            }
            Item {
                x: -34
                SequentialAnimation on x {
                    running: root.playing; loops: Animation.Infinite
                    PauseAnimation { duration: 300 }
                    NumberAnimation { to: 0; duration: 1100; easing.type: Easing.InOutSine }
                    PauseAnimation { duration: 1700 }
                    NumberAnimation { to: -34; duration: 500; easing.type: Easing.InOutSine }
                }
                Pane { x: 84; y: 36 }
                HandFigure { x: 106; y: 30; size: 58; pose: "index" }
            }
        }
    }
    Component {
        id: click
        Item {
            id: clicking
            // The thumb is held out to take aim, then comes down: the ripple leaves as it lands.
            property bool down: true
            Rectangle {
                id: ring
                x: 70; y: 39; width: 28; height: 28; radius: 14
                color: "transparent"
                border.color: theme.ink
                border.width: 3
                opacity: 0
            }
            SequentialAnimation {
                running: root.playing; loops: Animation.Infinite
                PropertyAction { target: clicking; property: "down"; value: false }
                PauseAnimation { duration: 800 }
                PropertyAction { target: clicking; property: "down"; value: true }
                ParallelAnimation {
                    NumberAnimation { target: ring; property: "scale"; from: 0.4; to: 2; duration: 900; easing.type: Easing.OutCubic }
                    NumberAnimation { target: ring; property: "opacity"; from: 1; to: 0; duration: 900 }
                }
            }
            HandFigure { x: 53; y: 20; size: 64; pose: clicking.down ? "press" : "aim" }
        }
    }
    Component {
        id: menu
        Item {
            HandFigure { x: 55; y: 30; size: 60; pose: "pinky" }
            Repeater {
                model: [
                    { x: 75, y: 14, colour: theme.butter }, { x: 109, y: 38, colour: theme.lilac },
                    { x: 97, y: 78, colour: theme.mint }, { x: 53, y: 78, colour: theme.butter },
                    { x: 41, y: 38, colour: theme.lilac }
                ]
                Rectangle {
                    id: bud
                    required property var modelData
                    required property int index
                    x: modelData.x; y: modelData.y
                    width: 16; height: 16; radius: 8
                    color: modelData.colour
                    border.color: theme.ink
                    border.width: 2
                    SequentialAnimation on scale {
                        running: root.playing; loops: Animation.Infinite
                        PropertyAction { value: 0 }
                        PauseAnimation { duration: 500 + 60 * bud.index }
                        NumberAnimation { to: 1; duration: 280; easing.type: Easing.OutBack }
                        PauseAnimation { duration: 1700 - 60 * bud.index }
                        NumberAnimation { to: 0; duration: 160 }
                    }
                }
            }
        }
    }
    Component {
        id: close
        Item {
            Shape {
                x: 43; y: 10; width: 84; height: 84
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    strokeColor: "#331E1B2E"; strokeWidth: 9; fillColor: "transparent"
                    PathAngleArc { centerX: 42; centerY: 42; radiusX: 36; radiusY: 36; startAngle: 0; sweepAngle: 360 }
                }
                ShapePath {
                    strokeColor: theme.butter; strokeWidth: 7; fillColor: "transparent"; capStyle: ShapePath.RoundCap
                    PathAngleArc {
                        id: arc
                        centerX: 42; centerY: 42; radiusX: 36; radiusY: 36; startAngle: -90; sweepAngle: 1
                        SequentialAnimation on sweepAngle {
                            running: root.playing; loops: Animation.Infinite
                            PauseAnimation { duration: 400 }
                            NumberAnimation { to: 360; duration: 2000 }
                            PauseAnimation { duration: 500 }
                            PropertyAction { value: 1 }
                        }
                    }
                }
            }
            HandFigure { x: 55; y: 16; size: 60; pose: "fist" }
        }
    }
    Component {
        id: scroll
        Item {
            HandFigure {
                x: 53; y: 20; size: 64; pose: "two"
                transformOrigin: Item.Bottom
                Sway on rotation { from: 0; to: 18; time: 1000 }
            }
        }
    }
    Component {
        id: knob
        Item {
            HandFigure {
                x: 53; y: 20; size: 64; pose: "claw"
                rotation: -18
                Sway on rotation { from: -18; to: 24; time: 1200 }
            }
        }
    }
    Component {
        id: swipe
        Item {
            // The open hand is swept to the right, and the Enter key goes down as it gets there.
            Rectangle {
                id: keycap
                x: 14; y: 60; width: 34; height: 30; radius: 8
                color: theme.paper
                border.color: theme.ink
                border.width: 2.5
                Icon { anchors.centerIn: parent; name: "enter"; size: 18; stroke: 2.6 }
                SequentialAnimation on scale {
                    running: root.playing; loops: Animation.Infinite
                    PauseAnimation { duration: 1150 }
                    NumberAnimation { to: 0.8; duration: 90 }
                    NumberAnimation { to: 1; duration: 220; easing.type: Easing.OutBack }
                    PauseAnimation { duration: 1260 }
                }
            }
            HandFigure {
                x: 30; y: 12; size: 62; pose: "open"
                SequentialAnimation on x {
                    running: root.playing; loops: Animation.Infinite
                    PauseAnimation { duration: 900 }
                    NumberAnimation { to: 100; duration: 320; easing.type: Easing.OutCubic }
                    PauseAnimation { duration: 900 }
                    NumberAnimation { to: 30; duration: 600; easing.type: Easing.InOutSine }
                }
            }
        }
    }
    Component {
        id: switcher
        Item {
            // A chin, and a fist coming up to it.
            Shape {
                x: 45; y: -34; width: 80; height: 60
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    strokeColor: theme.ink; strokeWidth: 3.5; fillColor: theme.paper; capStyle: ShapePath.RoundCap
                    PathAngleArc { centerX: 40; centerY: 20; radiusX: 34; radiusY: 34; startAngle: 0; sweepAngle: 180 }
                }
            }
            HandFigure {
                x: 55; y: 44; size: 60; pose: "fist"
                SequentialAnimation on y {
                    running: root.playing; loops: Animation.Infinite
                    PauseAnimation { duration: 700 }
                    NumberAnimation { to: 6; duration: 600; easing.type: Easing.OutCubic }
                    PauseAnimation { duration: 1100 }
                    NumberAnimation { to: 44; duration: 500; easing.type: Easing.InOutSine }
                }
            }
        }
    }
    Component {
        id: camera
        Item {
            HandFigure { x: 2; y: 24; size: 62; pose: "peace"; side: "left" }
            HandFigure { x: 106; y: 24; size: 62; pose: "peace" }
            Shape {
                x: 63; y: 30; width: 44; height: 44
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    strokeColor: "#331E1B2E"; strokeWidth: 7; fillColor: "transparent"
                    PathAngleArc { centerX: 22; centerY: 22; radiusX: 17; radiusY: 17; startAngle: 0; sweepAngle: 360 }
                }
                ShapePath {
                    strokeColor: theme.butter; strokeWidth: 6; fillColor: "transparent"; capStyle: ShapePath.RoundCap
                    PathAngleArc {
                        centerX: 22; centerY: 22; radiusX: 17; radiusY: 17; startAngle: -90; sweepAngle: 1
                        SequentialAnimation on sweepAngle {
                            running: root.playing; loops: Animation.Infinite
                            PauseAnimation { duration: 400 }
                            NumberAnimation { to: 360; duration: 2400 }
                            PauseAnimation { duration: 500 }
                            PropertyAction { value: 1 }
                        }
                    }
                }
            }
        }
    }
    Component {
        id: dictate
        Item {
            id: saying
            // The sign is held and words come; it is dropped, and they are in the text box.
            property real said: 1
            SequentialAnimation on said {
                running: root.playing; loops: Animation.Infinite
                PropertyAction { value: 0 }
                PauseAnimation { duration: 500 }
                NumberAnimation { to: 1; duration: 1500 }
                PauseAnimation { duration: 1200 }
            }
            HandFigure { x: 4; y: 22; size: 62; pose: "y" }
            Pane {
                x: 72; y: 34; width: 88; height: 36
                Row {
                    x: 10
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 4
                    Repeater {
                        model: [14, 9, 17, 11]
                        Rectangle {
                            required property int modelData
                            required property int index
                            width: modelData; height: 6; radius: 3
                            color: theme.ink
                            visible: saying.said * 4 > index + 0.5
                        }
                    }
                    Rectangle { width: 2.5; height: 16; y: -5; color: theme.coral }
                }
            }
        }
    }
    Component {
        id: clap
        Item {
            id: clapping
            // The hands meet twice, and a tab is added to the row of them.
            property real apart: 1
            property bool opened: true
            SequentialAnimation {
                running: root.playing; loops: Animation.Infinite
                PropertyAction { target: clapping; property: "opened"; value: false }
                PauseAnimation { duration: 500 }
                NumberAnimation { target: clapping; property: "apart"; to: 0; duration: 130; easing.type: Easing.InQuad }
                NumberAnimation { target: clapping; property: "apart"; to: 1; duration: 190; easing.type: Easing.OutQuad }
                NumberAnimation { target: clapping; property: "apart"; to: 0; duration: 130; easing.type: Easing.InQuad }
                PropertyAction { target: clapping; property: "opened"; value: true }
                NumberAnimation { target: clapping; property: "apart"; to: 1; duration: 190; easing.type: Easing.OutQuad }
                PauseAnimation { duration: 1500 }
            }
            Row {
                x: 43; y: 8; spacing: 4
                Repeater {
                    model: 3
                    Rectangle {
                        required property int index
                        visible: index < 2 || clapping.opened
                        width: 26; height: 14; radius: 5
                        color: index === 2 ? theme.mint : theme.paper
                        border.color: theme.ink
                        border.width: 2.5
                    }
                }
            }
            // A left hand is drawn its own width short of 96 units to the right of where it is put.
            HandFigure { x: -8 - 22 * clapping.apart; y: 34; size: 60; pose: "open"; side: "left" }
            HandFigure { x: 82 + 22 * clapping.apart; y: 34; size: 60; pose: "open" }
        }
    }
}
