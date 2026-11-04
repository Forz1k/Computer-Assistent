// Поле ввода команды: glass-подложка, hairline, glow при фокусе.
import "theme"
import QtQuick
import QtQuick.Controls.Basic

Rectangle {
    id: wrap
    property alias field: tf
    height: 48
    radius: Theme.rS
    color: Qt.rgba(Theme.raise.r, Theme.raise.g, Theme.raise.b, 0.5)
    border.color: tf.activeFocus ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.6) : Theme.hair
    border.width: 1
    Behavior on border.color { ColorAnimation { duration: Theme.dur(200); easing.type: Theme.ease() } }

    signal submitted(string text)

    Row {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 6
        spacing: 6
        Icon {
            name: "bolt"
            width: 18; height: 18
            anchors.verticalCenter: parent.verticalCenter
            fg: tf.activeFocus ? Theme.accent : Theme.textMuted
        }
        TextField {
            id: tf
            width: parent.width - 70
            anchors.verticalCenter: parent.verticalCenter
            placeholderText: "Команда или вопрос… (Ctrl+K — палитра)"
            color: Theme.textPrimary
            font.family: Theme.fontMain
            font.pixelSize: 14 * Theme.uiScale
            background: Rectangle { color: "transparent" }
            selectByMouse: true
            onAccepted: wrap.submitted(text)
        }
        HudButton {
            iconName: "send"
            width: 40; height: 36
            anchors.verticalCenter: parent.verticalCenter
            active: tf.text.length > 0
            onClicked: wrap.submitted(tf.text)
        }
    }
}
