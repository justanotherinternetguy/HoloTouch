import QtQuick

// One live figure in a bubble, and what it counts.
Rectangle {
    id: root
    property string value
    property string caption
    property string tone: "steady"  // steady | active | empty | problem
    property real s: 1

    width: 76 * s
    height: width
    radius: width / 2
    color: tone === "active" ? theme.butter : tone === "problem" ? theme.coralTint : tone === "empty" ? "transparent" : theme.paper
    border.color: tone === "active" || tone === "problem" ? theme.ink : tone === "empty" ? "transparent" : theme.line
    border.width: 1.5 * s

    // Nothing to show: a dashed rim.
    Canvas {
        anchors.fill: parent
        visible: root.tone === "empty"
        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            ctx.strokeStyle = theme.muted
            ctx.lineWidth = 1.5 * root.s
            ctx.setLineDash([4, 3])
            ctx.beginPath()
            ctx.arc(width / 2, height / 2, width / 2 - root.s, 0, 2 * Math.PI)
            ctx.stroke()
        }
    }
    Column {
        anchors.centerIn: parent
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            width: root.width - 12 * root.s
            horizontalAlignment: Text.AlignHCenter
            text: root.value
            color: root.tone === "empty" ? theme.inkSoft : theme.ink
            font.family: theme.display
            font.pixelSize: (root.value.length > 3 ? 18 : 23) * root.s
            font.weight: Font.DemiBold
            fontSizeMode: Text.HorizontalFit
            minimumPixelSize: 12 * root.s
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.caption
            color: root.tone === "active" || root.tone === "problem" ? theme.inkMid : theme.inkSoft
            font.family: theme.body
            font.pixelSize: 12.5 * root.s
        }
    }
}
