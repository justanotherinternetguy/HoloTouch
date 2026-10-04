import QtQuick
import "../../ui"

// The launcher: the letters spelt so far, the one the hand is making, and under them the apps and
// macros still within reach. For a moment after, what was opened, or that there was nothing.
Item {
    id: root
    property var fx
    property var options: []
    property real s: 1
    // Remember the last of each so the note does not change while it fades out.
    property string state_: "spelling"
    property string letters: ""
    property string name: ""
    property int more: 0
    readonly property bool shown: fx.spell !== ""
    onFxChanged: if (fx.spell !== "") {
        state_ = fx.spell
        letters = fx.spellLetters
        name = fx.spellName
        more = fx.spellMore
    }
    readonly property bool spelling: state_ === "spelling"
    readonly property bool failed: state_ === "failed"
    readonly property real head: 54 * s

    function plain(text) { return text.replace(/&/g, "&amp;").replace(/</g, "&lt;") }
    // A name or a macro's letters, with what has been spelt of it picked out.
    function marked(text, done) {
        return "<font color=\"" + theme.butter + "\">" + plain(text.slice(0, done)) + "</font>" + plain(text.slice(done))
    }

    anchors.horizontalCenter: parent.horizontalCenter
    y: parent.height * 0.16
    width: Math.max(spelling ? 430 * s : 0, row.width + 34 * s)
    height: head + (spelling ? list.height : 0)
    opacity: shown ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 200 } }
    Behavior on height { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
    Behavior on width { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }

    Rectangle {
        anchors.fill: parent
        radius: root.head / 2
        color: theme.chip
        border.color: theme.keyline
        border.width: 1.5 * root.s
    }
    Row {
        id: row
        x: 8 * root.s
        height: root.head
        spacing: 9 * root.s
        // What the hand looks like now, while spelling; then how it ended.
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: 38 * root.s; height: width; radius: width / 2
            color: root.failed ? theme.cream : root.spelling ? theme.lilac : theme.mint
            Icon {
                anchors.centerIn: parent
                visible: !root.spelling
                name: root.failed ? "bang" : "check"
                size: 22 * root.s
                stroke: 2.4
            }
            Text {
                anchors.centerIn: parent
                visible: root.spelling
                text: root.fx.spellGuess || "·"
                color: theme.ink
                font.family: theme.display
                font.pixelSize: 21 * root.s
                font.weight: Font.DemiBold
            }
        }
        Repeater {
            model: root.letters.length
            Rectangle {
                required property int index
                anchors.verticalCenter: parent.verticalCenter
                width: 32 * root.s; height: 36 * root.s; radius: 9 * root.s
                color: theme.cream
                Text {
                    anchors.centerIn: parent
                    text: root.letters[index]
                    color: theme.ink
                    font.family: theme.display
                    font.pixelSize: 21 * root.s
                    font.weight: Font.DemiBold
                }
            }
        }
        // The letter being held fills up from below until it is taken.
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            visible: root.spelling && root.shown
            width: 32 * root.s; height: 36 * root.s; radius: 9 * root.s
            color: "transparent"
            border.color: theme.keyline
            border.width: 1.5 * root.s
            clip: true
            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: parent.height * root.fx.spellHold
                radius: parent.radius
                color: theme.butter
            }
            Text {
                anchors.centerIn: parent
                text: root.fx.spellHolding
                color: root.fx.spellHold > 0.55 ? theme.ink : theme.cream
                font.family: theme.display
                font.pixelSize: 21 * root.s
                font.weight: Font.DemiBold
            }
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: root.spelling ? (root.letters === "" && root.fx.spellHolding === "" ? "Spell a name" : "") : root.failed ? "No match" : root.name
            color: theme.cream
            font.family: theme.display
            font.pixelSize: 19 * root.s
            font.weight: Font.DemiBold
        }
    }

    // The apps and macros that what has been spelt may yet become. The one that will be opened
    // if no more letters come is first, and fills up while it waits for them.
    Column {
        id: list
        y: root.head
        x: 10 * root.s
        width: root.width - 2 * x
        bottomPadding: 14 * root.s
        spacing: 4 * root.s
        visible: root.spelling
        Repeater {
            model: root.options
            Rectangle {
                id: option
                required property var modelData
                width: list.width
                height: 42 * root.s
                radius: 13 * root.s
                color: modelData.chosen ? theme.inkMid : "transparent"
                Rectangle {
                    visible: option.modelData.chosen
                    width: parent.width * root.fx.spellOpening
                    height: parent.height
                    radius: parent.radius
                    color: theme.butter
                    opacity: 0.3
                }
                Row {
                    x: 8 * root.s
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 11 * root.s
                    // An app has its icon, or failing that its initial. A macro has its letters.
                    Item {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: option.modelData.code === ""
                        width: 30 * root.s; height: width
                        Image {
                            anchors.fill: parent
                            visible: option.modelData.hasIcon
                            sourceSize: Qt.size(2 * width, 2 * height)
                            source: visible ? "image://theme/" + option.modelData.icon : ""
                        }
                        Rectangle {
                            anchors.fill: parent
                            visible: !option.modelData.hasIcon
                            radius: 8 * root.s
                            color: theme.cream
                            Text {
                                anchors.centerIn: parent
                                text: option.modelData.name.slice(0, 1).toUpperCase()
                                color: theme.ink
                                font.family: theme.display
                                font.pixelSize: 18 * root.s
                                font.weight: Font.DemiBold
                            }
                        }
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: option.modelData.code !== ""
                        width: Math.max(implicitWidth, 30 * root.s)
                        horizontalAlignment: Text.AlignHCenter
                        textFormat: Text.StyledText
                        text: root.marked(option.modelData.code, option.modelData.done)
                        color: theme.muted
                        font.family: theme.mono
                        font.pixelSize: 15 * root.s
                        font.weight: Font.Medium
                        font.letterSpacing: 2 * root.s
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        width: Math.min(implicitWidth, option.width - x - 16 * root.s)
                        elide: Text.ElideRight
                        textFormat: Text.StyledText
                        text: option.modelData.code === "" ? root.marked(option.modelData.name, option.modelData.done) : root.plain(option.modelData.name)
                        color: theme.cream
                        font.family: theme.body
                        font.pixelSize: 16 * root.s
                    }
                }
            }
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: root.more > 0
            topPadding: 2 * root.s
            text: "and " + root.more + " more"
            color: theme.muted
            font.family: theme.body
            font.pixelSize: 13 * root.s
        }
    }
}
