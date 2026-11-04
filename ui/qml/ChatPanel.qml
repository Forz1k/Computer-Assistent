// Правая панель: лента диалога + чипы-подсказки + поле ввода.
import "theme"
import QtQuick
import QtQuick.Controls.Basic

GlassPanel {
    id: panel
    property bool micAvailable: true
    signal sendText(string text)
    radius: Theme.rM

    Column {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 10

        Row {
            width: parent.width
            spacing: 8
            Label {
                text: "ЖУРНАЛ СВЯЗИ"
                color: Theme.accent
                font.family: Theme.fontMono
                font.pixelSize: 11 * Theme.uiScale
                font.letterSpacing: 3
            }
            Item { width: parent.width - 150; height: 1 }
            Rectangle {
                width: 8; height: 8; radius: 4
                anchors.verticalCenter: parent.verticalCenter
                color: core.state === "MUTED" ? Theme.textMuted :
                       (core.busy ? Theme.warn : Theme.ok)
                SequentialAnimation on opacity {
                    running: core.busy && !Theme.reducedMotion
                    loops: Animation.Infinite
                    NumberAnimation { from: 1; to: 0.3; duration: 600 }
                    NumberAnimation { from: 0.3; to: 1; duration: 600 }
                }
            }
        }

        ListView {
            id: feed
            width: parent.width
            height: parent.height - 210
            clip: true
            spacing: 6
            model: chatModel.messages
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            onCountChanged: positionViewAtIndex(count - 1, ListView.End)
            delegate: MessageDelegate {
                required property var modelData
                width: feed.width
                role: modelData.role
                content: modelData.content
                timeStr: modelData.time
                demo: modelData.demo
                streaming: modelData.streaming
                meta: modelData.meta
            }
            // live-стриминг без пересоздания делегата: обновляем content напрямую
            Connections {
                target: chatModel
                function onStreamChunk(idx, chunk) {
                    var item = feed.itemAtIndex(idx);
                    if (item) item.content += chunk;
                }
                function onStreamEnd(idx) {
                    var item = feed.itemAtIndex(idx);
                    if (item) { item.streaming = false; }
                }
            }
        }

        // interim-распознавание (живой partial со STT)
        Label {
            width: parent.width
            visible: core.interimText.length > 0
            text: "«" + core.interimText + "»…"
            color: Theme.textSecondary
            font.family: Theme.fontMain
            font.pixelSize: 12 * Theme.uiScale
            font.italic: true
            elide: Text.ElideRight
        }

        Flow {
            width: parent.width
            spacing: 6
            Repeater {
                model: ["Который час", "Статус системы", "Открой браузер", "Создай заметку"]
                delegate: Rectangle {
                    id: chipRect
                    width: chipLbl.implicitWidth + 18
                    height: 26
                    radius: 13
                    color: hovered.hovered ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.15) : "transparent"
                    border.color: Theme.hair
                    border.width: 1
                    property string cmd: modelData
                    HoverHandler { id: hovered }
                    TapHandler { onTapped: panel.sendText(chipRect.cmd) }
                    Label {
                        id: chipLbl
                        anchors.centerIn: parent
                        text: chipRect.cmd
                        color: Theme.textSecondary
                        font.family: Theme.fontMain
                        font.pixelSize: 11 * Theme.uiScale
                    }
                }
            }
        }

        CommandField {
            id: input
            width: parent.width
            enabled: !core.busy
            onSubmit: panel.sendText(text)
        }
    }
}
