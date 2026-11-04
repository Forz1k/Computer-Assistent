// Диагностический экран: список компонентов с реальным статусом + «что сделать»,
// кнопка копирования отчёта. Данные приходят из Python (diagnostics/checks.py).
import "theme"
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Rectangle {
    id: sheet
    anchors.fill: parent
    visible: false
    opacity: 0
    color: Qt.rgba(Theme.bgVoid.r, Theme.bgVoid.g, Theme.bgVoid.b, 0.72)
    z: 56

    property string reportText: ""
    property var items: []

    function openNow() { visible = true; core.openDiagnostics(); }
    function closeNow() { visible = false; }
    function showReport(text) { reportText = text; }
    // модель приходит как список dict{name,status,detail,action,latency_ms,version}
    function setItems(list) {
        items = (list || []).map(function (s) {
            return {"name": s.name, "status": s.status,
                    "detail": (s.detail || "") + (s.latency_ms ? ("  (" + s.latency_ms + " мс)") : ""),
                    "hint": s.action || ""};
        });
    }

    Connections {
        target: core
        function onBootStatusesChanged() { sheet.setItems(core.bootStatuses); }
    }
    Component.onCompleted: sheet.setItems(core.bootStatuses)

    SequentialAnimation on opacity {
        id: animIn
        running: false
        NumberAnimation { to: 1; duration: Theme.dur(220); easing.type: Theme.ease() }
    }
    ParallelAnimation {
        id: animOut
        running: false
        NumberAnimation { target: sheet; property: "opacity"; to: 0; duration: Theme.dur(180) }
        ScriptAction { script: sheet.visible = false }
    }

    MouseArea { anchors.fill: parent; onClicked: sheet.closeNow() }

    GlassPanel {
        anchors.centerIn: parent
        width: Math.min(760, parent.width - 48)
        height: Math.min(620, parent.height - 48)
        radius: Theme.rM

        Column {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 16

            Row {
                spacing: 12
                Icon { name: "shield"; width: 22; height: 22; fg: Theme.accent }
                Text {
                    text: "Диагностика системы"
                    color: Theme.textPrimary
                    font.family: Theme.fontMain
                    font.pixelSize: 18 * Theme.uiScale
                    font.bold: true
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            Rectangle { width: parent.width; height: 1; color: Theme.hair }

            ListView {
                id: list
                width: parent.width
                height: parent.height - 190
                clip: true
                spacing: 10
                model: sheet.items.length > 0 ? sheet.items : [
                    {"name": "Нет данных", "status": "warn", "detail": "Нажмите «Обновить»", "hint": "Откройте экран ещё раз после загрузки"}
                ]
                delegate: RowLayout {
                    required property var modelData
                    width: list.width
                    spacing: 12
                    property color sc: modelData.status === "ok" ? Theme.ok
                                     : modelData.status === "warn" ? Theme.warn : Theme.danger
                    Rectangle {
                        width: 10; height: 10; radius: 5
                        color: sc
                        border.color: Qt.rgba(sc.r, sc.g, sc.b, 0.4); border.width: 3
                    }
                    Column {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            text: modelData.name + "  —  " + modelData.status.toUpperCase()
                            color: Theme.textPrimary
                            font.family: Theme.fontMain
                            font.pixelSize: 14 * Theme.uiScale
                        }
                        Text {
                            text: modelData.detail || ""
                            color: Theme.textSecondary
                            font.family: Theme.fontMono
                            font.pixelSize: 11 * Theme.uiScale
                            wrapMode: Text.WordWrap
                            width: list.width - 120
                        }
                        Text {
                            visible: (modelData.hint || "").length > 0
                            text: "→ " + (modelData.hint || "")
                            color: Theme.textMuted
                            font.family: Theme.fontMain
                            font.pixelSize: 11 * Theme.uiScale
                            wrapMode: Text.WordWrap
                            width: list.width - 120
                        }
                    }
                }
            }

            Flickable {
                visible: sheet.reportText.length > 0 && list.count === 0
                width: parent.width; height: 160
                contentHeight: reportCol.height
                Text {
                    id: reportCol
                    width: parent.width
                    text: sheet.reportText
                    color: Theme.textSecondary
                    font.family: Theme.fontMono
                    font.pixelSize: 11 * Theme.uiScale
                    wrapMode: Text.WrapAnywhere
                }
            }

            Row {
                spacing: 10
                HudButton {
                    iconName: "bolt"; text2: "Обновить"
                    onClicked: { core.openDiagnostics(); }
                }
                HudButton {
                    iconName: "copy"; text2: "Скопировать отчёт"
                    onClicked: core.copyReport(sheet.reportText)
                }
                HudButton {
                    iconName: "close"; text2: "Закрыть"; danger: true
                    onClicked: sheet.closeNow()
                }
            }
        }
    }
}
