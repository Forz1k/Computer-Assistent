// Палитра команд (Ctrl+K): fuzzy-поиск по командам/темам/настройкам.
import QtQuick
import QtQuick.Controls.Basic

Rectangle {
    id: palette
    anchors.fill: parent
    visible: false
    color: "#99040710"
    signal runCommand(string cmd)

    property var results: core.fuzzySearch("")

    Timer {
        id: debounce
        interval: 90
        onTriggered: palette.results = core.fuzzySearch(palInput.text)
    }

    GlassPanel {
        width: Math.min(520, parent.width - 60)
        height: 380
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 90
        radius: Theme.rM
        glowBorder: true
        opacity: 0
        states: State { name: "shown"; when: palette.visible
                        PropertyChanges { target: paletteCard; opacity: 1 } }
        transitions: Transition { NumberAnimation { property: "opacity"; duration: Theme.dur(180); easing.type: Theme.ease() } }
        id: paletteCard

        Column {
            anchors.fill: parent
            anchors.margins: 14
            spacing: 8

            Row {
                spacing: 8
                width: parent.width
                Icon { name: "search"; width: 18; height: 18; anchors.verticalCenter: parent.verticalCenter; fg: Theme.accent }
                TextField {
                    id: palInput
                    width: parent.width - 30
                    placeholderText: "Поиск команды / темы / режима…"
                    color: Theme.textPrimary
                    font.family: Theme.fontMain
                    font.pixelSize: 14 * Theme.uiScale
                    background: Rectangle { color: "transparent"; border.color: Theme.hair; radius: 6; border.width: 1 }
                    selectByMouse: true
                    onTextChanged: debounce.restart()
                    Keys.onEscapePressed: palette.visible = false
                    Component.onCompleted: forceActiveFocus()
                }
            }

            ListView {
                id: list
                width: parent.width
                height: 280
                clip: true
                model: palette.results
                boundsBehavior: Flickable.StopAtBounds
                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    width: list.width
                    height: 36
                    radius: Theme.rS
                    color: hl.hovered ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.12) : "transparent"
                    HoverHandler { id: hl }
                    TapHandler {
                        onTapped: { palette.visible = false; palette.runCommand(modelData.cmd); }
                    }
                    Label {
                        anchors.left: parent.left
                        anchors.leftMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.label
                        color: Theme.textPrimary
                        font.family: Theme.fontMain
                        font.pixelSize: 13 * Theme.uiScale
                    }
                    Label {
                        anchors.right: parent.right
                        anchors.rightMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.cmd
                        color: Theme.textMuted
                        font.family: Theme.fontMono
                        font.pixelSize: 10 * Theme.uiScale
                    }
                }
            }
            Label {
                text: "Enter — выполнить · Esc — закрыть"
                color: Theme.textMuted
                font.family: Theme.fontMono
                font.pixelSize: 10 * Theme.uiScale
            }
        }
    }

    MouseArea { anchors.fill: parent; onClicked: palette.visible = false; z: -1 }
}
