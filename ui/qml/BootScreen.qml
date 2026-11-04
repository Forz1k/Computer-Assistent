// Boot-экран: реальные статусы компонентов + чек-лист установки.
// Никакого фейкового прогресса: полоса = число завершённых проверок из Python.
import QtQuick
import QtQuick.Controls.Basic

Rectangle {
    id: boot
    color: Theme.bgVoid
    property var statuses: []          // [{name,status,detail,action}]
    property bool finished: statuses.length >= 6
    onStatusesChanged: if (statuses.length >= 6) finished = true
    signal enterHud()

    // фон: сетка + виньетка
    Canvas {
        anchors.fill: parent
        onPaint: {
            var ctx = getContext("2d"); ctx.reset();
            ctx.strokeStyle = Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.05);
            ctx.lineWidth = 1;
            for (var x = 0; x < width; x += 48) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, height); ctx.stroke(); }
            for (var y = 0; y < height; y += 48) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke(); }
        }
    }

    Column {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -20
        spacing: 18
        width: Math.min(620, parent.width - 60)

        Item {
            width: 120; height: 120
            anchors.horizontalCenter: parent.horizontalCenter
            ArcCore {
                anchors.fill: parent
                st: boot.finished ? "IDLE" : "BOOT"
                rmsLevel: 0.15
                particles: 30
                plasmaOn: Theme.plasma
                accent: Theme.accent
                accentWarm: Theme.accentWarm
                reducedMotion: Theme.reducedMotion
            }
        }

        Label {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "COMPUTER ASSISTANT"
            color: Theme.textPrimary
            font.family: Theme.fontMono
            font.pixelSize: 22 * Theme.uiScale
            font.letterSpacing: 6
        }
        Label {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Инициализация подсистем…"
            color: Theme.textMuted
            font.family: Theme.fontMain
            font.pixelSize: 13 * Theme.uiScale
            visible: !boot.finished
        }

        // прогресс = реально выполненные проверки
        Rectangle {
            width: parent.width; height: 3
            radius: 2
            color: Theme.hair
            Rectangle {
                width: parent.width * (boot.statuses.length ? boot.statuses.length / 6 : 0.05)
                height: 3
                radius: 2
                color: boot.finished ? Theme.ok : Theme.accent
                Behavior on width { NumberAnimation { duration: Theme.dur(400); easing.type: Theme.ease() } }
            }
        }

        Repeater {
            model: boot.statuses
            delegate: Row {
                required property var modelData
                required property int index
                spacing: 10
                width: parent ? parent.width : 0
                Icon {
                    name: modelData.status === "ok" ? "check" : (modelData.status === "warn" ? "dot-ok" : "close")
                    width: 16; height: 16
                    anchors.verticalCenter: parent.verticalCenter
                    fg: modelData.status === "ok" ? Theme.ok
                        : modelData.status === "warn" ? Theme.warn : Theme.danger
                }
                Column {
                    width: parent.width - 30
                    spacing: 2
                    Row {
                        spacing: 8
                        Label {
                            text: modelData.name.toUpperCase()
                            color: Theme.textSecondary
                            font.family: Theme.fontMono
                            font.pixelSize: 11 * Theme.uiScale
                            font.letterSpacing: 1
                        }
                        Label {
                            visible: modelData.latency_ms !== null && modelData.latency_ms !== undefined
                            text: modelData.latency_ms + " мс"
                            color: Theme.textMuted
                            font.family: Theme.fontMono
                            font.pixelSize: 10 * Theme.uiScale
                        }
                    }
                    Label {
                        text: modelData.detail
                        color: Theme.textMuted
                        font.family: Theme.fontMain
                        font.pixelSize: 11 * Theme.uiScale
                        elide: Label.ElideRight
                        width: parent.width
                    }
                    Label {
                        visible: modelData.action && modelData.status !== "ok"
                        text: "→ " + modelData.action
                        color: Theme.warn
                        font.family: Theme.fontMain
                        font.pixelSize: 11 * Theme.uiScale
                        wrapMode: Text.Wrap
                        width: parent.width
                    }
                }
                Item { width: 1; height: 40 }
            }
        }

        Item { width: 1; height: 6 }

        HudButton {
            anchors.horizontalCenter: parent.horizontalCenter
            iconName: "chevron-down"
            text2: boot.finished ? "Войти в HUD" : "Пропустить проверку и войти"
            active: true
            onClicked: boot.enterHud()
        }
    }

    transitions: Transition {
        NumberAnimation { property: "opacity"; to: 0; duration: Theme.dur(700); easing.type: Theme.ease() }
    }
}
