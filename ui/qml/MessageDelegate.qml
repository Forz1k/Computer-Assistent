// Сообщение ленты: user — тонкая реплика, assistant — glass-карточка.
// Во время стриминга НЕ пересоздаём layout: текст дописывается в тот же Text.
import QtQuick
import QtQuick.Controls.Basic

Item {
    id: msg
    property string role: "user"          // user | assistant | system
    property string content: ""
    property string timeStr: ""
    property bool demo: false
    property bool streaming: false
    property var meta: ({})
    width: parent ? parent.width : 400
    height: col.implicitHeight + 14

    Column {
        id: col
        width: parent.width
        spacing: 4

        // --- строка служебной инфы ---
        Row {
            spacing: 8
            visible: true
            Label {
                text: msg.role === "user" ? "ВЫ" : (msg.role === "system" ? "СИСТЕМА" : "АССИСТЕНТ")
                color: msg.role === "user" ? Theme.accentWarm : Theme.accent
                font.family: Theme.fontMono
                font.pixelSize: 10 * Theme.uiScale
                font.letterSpacing: 1.5
            }
            Label {
                text: msg.timeStr
                color: Theme.textMuted
                font.family: Theme.fontMono
                font.pixelSize: 10 * Theme.uiScale
            }
            Rectangle {
                visible: msg.demo
                height: 16; width: demoLbl.implicitWidth + 12
                radius: 4
                color: Qt.rgba(Theme.warn.r, Theme.warn.g, Theme.warn.b, 0.15)
                border.color: Theme.warn
                border.width: 1
                anchors.verticalCenter: parent.verticalCenter
                Label {
                    id: demoLbl
                    anchors.centerIn: parent
                    text: "DEMO"
                    color: Theme.warn
                    font.family: Theme.fontMono
                    font.pixelSize: 9 * Theme.uiScale
                    font.letterSpacing: 1
                }
            }
        }

        // --- тело ---
        GlassPanel {
            width: parent.width
            visible: msg.role !== "user"
            radius: Theme.rS
            alpha: msg.role === "system" ? 0.35 : Theme.glassAlpha
            glowBorder: msg.streaming
            topPadding: 10; bottomPadding: msg.meta && msg.meta.ttft_ms ? 6 : 10

            Text {
                id: body
                anchors.fill: parent
                anchors.margins: 10
                text: msg.content + (msg.streaming ? "▌" : "")
                textFormat: msg.role === "assistant" ? Text.MarkdownText : Text.PlainText
                wrapMode: Text.Wrap
                color: msg.role === "system" ? Theme.textSecondary : Theme.textPrimary
                font.family: Theme.fontMain
                font.pixelSize: 14 * Theme.uiScale
                lineHeight: 1.3
                onLinkActivated: (link) => Qt.openUrlExternally(link)
            }
        }

        // user — простая реплика без карточки
        Text {
            visible: msg.role === "user"
            width: parent.width
            text: msg.content
            wrapMode: Text.Wrap
            color: Theme.textPrimary
            font.family: Theme.fontMain
            font.pixelSize: 14 * Theme.uiScale
            leftPadding: 2
        }

        // --- метрики ответа ---
        Row {
            visible: msg.role === "assistant" && msg.meta && msg.meta.ttft_ms !== undefined && msg.meta.ttft_ms !== null
            spacing: 10
            Label {
                visible: msg.meta && msg.meta.ttft_ms > 0
                text: "TTFT " + (msg.meta ? msg.meta.ttft_ms : 0) + " мс"
                color: Theme.textMuted; font.family: Theme.fontMono; font.pixelSize: 10 * Theme.uiScale
            }
            Label {
                visible: msg.meta && msg.meta.tps > 0
                text: (msg.meta ? msg.meta.tps : 0) + " ток/с"
                color: Theme.textMuted; font.family: Theme.fontMono; font.pixelSize: 10 * Theme.uiScale
            }
        }
    }
}
