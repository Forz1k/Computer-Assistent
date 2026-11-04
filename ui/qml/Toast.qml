// Тост-уведомление: появляется снизу, 3 с, fade+slide.
import QtQuick
import QtQuick.Controls.Basic

Rectangle {
    id: toast
    width: lbl.implicitWidth + 28
    height: 34
    radius: 17
    color: Qt.rgba(Theme.raise.r, Theme.raise.g, Theme.raise.b, 0.92)
    border.color: level === "error" ? Theme.danger : level === "warn" ? Theme.warn : Theme.hair
    border.width: 1
    opacity: 0
    property string level: "info"

    function show(msg, lvl) {
        lbl.text = msg; level = lvl || "info";
        animIn.restart();
        hideTimer.restart();
    }

    Label {
        id: lbl
        anchors.centerIn: parent
        color: Theme.textPrimary
        font.family: Theme.fontMain
        font.pixelSize: 12 * Theme.uiScale
    }

    NumberAnimation { id: animIn; target: toast; property: "opacity"; to: 1; duration: Theme.dur(140); easing.type: Theme.ease() }
    Timer { id: hideTimer; interval: 3000; onTriggered: animOut.start() }
    NumberAnimation { id: animOut; target: toast; property: "opacity"; to: 0; duration: Theme.dur(220)
                      easing.type: Theme.ease() }
}
