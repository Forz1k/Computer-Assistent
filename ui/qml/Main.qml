// Корневой файл HUD: frameless-окно, кастомный титлбар, Boot → главный экран,
// мини-режим, палитра команд, подтверждения, статус-бар. Логика — в Python (core).
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window
import "theme"

ApplicationWindow {
    id: win
    visible: true
    width: 1280
    height: 800
    minimumWidth: 940
    minimumHeight: 620
    color: Theme.bgVoid
    title: "Computer Assistant"
    flags: Qt.Window | Qt.FramelessWindowHint

    property bool booted: false
    property bool mini: false
    property real lastW: 1280
    property real lastH: 800
    property point dragOff: Qt.point(0, 0)

    // геометрия окна сохраняется через настройки Python
    Component.onCompleted: {
        Theme.reducedMotion = core.reducedMotion || win.screen === null;
        var g = core.windowGeometry();
        if (g && g.w > 0) { win.width = g.w; win.height = g.h; win.x = g.x; win.y = g.y; }
    }
    onWidthChanged: if (!mini) { lastW = width; }
    Component.onDestruction: core.saveWindowGeometry(Math.round(x), Math.round(y), Math.round(lastW), Math.round(lastH))

    Connections {
        target: core
        function onStateChanged(s) { /* визуальные реакции — внутри ArcCore/состояний */ }
        function onMiniToggled(m) { enterMini(m); }
        function onReportReady(text) { diagSheet.showReport(text); }
        function onToast(msg, level) { toast.show(msg, level); }
    }
    Connections {
        target: theme
        function onThemeChanged() { Theme.refresh(); }
    }

    function enterMini(on) {
        mini = on;
        if (on) {
            win.lastW = win.width; win.lastH = win.height;
            win.visibility = Window.AutoHide;
            win.width = 230; win.height = 260;
            win.minimumWidth = 230; win.minimumHeight = 260;
        } else {
            win.minimumWidth = 940; win.minimumHeight = 620;
            win.width = win.lastW; win.height = win.lastH;
            win.visibility = Window.Windowed;
        }
    }

    // ================= фон и рамка =================
    Rectangle {
        anchors.fill: parent
        radius: Theme.rM
        color: Theme.bgVoid
        border.color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.35)
        border.width: 1

        // мягкая внутренняя подсветка «космоса»
        Rectangle {
            anchors.centerIn: parent
            width: parent.width * 0.9; height: parent.height * 0.9
            radius: Theme.rL
            color: "transparent"
            gradient: Gradient {
                orientation: Gradient.Vertical
                GradientStop { position: 0.0; color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.04) }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }
    }

    // ================= BOOT =================
    BootScreen {
        id: bootScreen
        anchors.fill: parent
        visible: !win.booted
        z: 30
        statuses: core.bootStatuses
        MouseArea { anchors.fill: parent; onClicked: win.booted = true }   // клик — пропуск
        onEnterHud: win.booted = true
        Timer {
            id: bootAuto
            interval: 4200; running: bootScreen.finished
            onTriggered: win.booted = true
        }
    }

    // ================= HUD =================
    Item {
        id: hud
        anchors.fill: parent
        anchors.margins: 2
        visible: win.booted && !win.mini
        opacity: visible ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.dur(420); easing.type: Theme.ease() } }

        // ---- титлбар ----
        Rectangle {
            id: titlebar
            anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
            height: 44
            color: "transparent"

            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton
                property point p0
                onPressed: p0 = mouse
                onPositionChanged: {
                    if (pressed && Math.abs(mouseX - p0.x) + Math.abs(mouseY - p0.y) > 4) {
                        win.x += mouse.x - p0.x; win.y += mouse.y - p0.y;
                    }
                }
                onDoubleClicked: win.visibility = win.visibility === Window.Maximized ? Window.Windowed : Window.Maximized
            }

            Row {
                anchors.left: parent.left; anchors.leftMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8
                Icon { name: "bolt"; width: 18; height: 18; fg: Theme.accent
                       anchors.verticalCenter: parent.verticalCenter }
                Label {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "COMPUTER ASSISTANT"
                    color: Theme.textPrimary
                    font.family: Theme.fontMono
                    font.pixelSize: 11 * Theme.uiScale
                    font.letterSpacing: 3
                }
                Rectangle {   // DEMO-бейдж — всегда виден в демо
                    visible: core.demoMode
                    width: demoLbl.implicitWidth + 14; height: 18
                    radius: 9
                    anchors.verticalCenter: parent.verticalCenter
                    color: Qt.rgba(Theme.warn.r, Theme.warn.g, Theme.warn.b, 0.15)
                    border.color: Theme.warn; border.width: 1
                    Label { id: demoLbl; anchors.centerIn: parent; text: "DEMO — НЕ РЕАЛЬНАЯ МОДЕЛЬ"
                            color: Theme.warn; font.family: Theme.fontMono; font.pixelSize: 9 * Theme.uiScale }
                }
            }

            Row {
                anchors.right: parent.right; anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4
                HudButton { iconName: "settings"; width: 34; height: 30; onClicked: settingsDrawer.openNow() }
                HudButton { iconName: "minimize"; width: 34; height: 30; onClicked: win.showMinimized() }
                HudButton { iconName: "chevron-down"; width: 34; height: 30; text2: ""
                            active: false; onClicked: core.toggleMini() }
                HudButton { iconName: "close"; width: 34; height: 30; danger: true; onClicked: closeAnim.start() }
                NumberAnimation {
                    id: closeAnim
                    target: hud; property: "opacity"; from: 1; to: 0; duration: Theme.dur(180)
                    onFinished: Qt.quit()
                }
            }
        }

        // ---- ядро слева по центру ----
        Item {
            id: coreArea
            anchors.left: parent.left; anchors.right: chatPanel.left
            anchors.top: titlebar.bottom; anchors.bottom: statusStrip.top
            anchors.margins: 16

            ArcCore {
                id: arc
                anchors.centerIn: parent
                width: Math.min(parent.width * 0.72, parent.height * 0.72, 420)
                height: width
                st: core.state
                rmsLevel: core.rms
                spectrum: core.spectrum
                reducedMotion: Theme.reducedMotion
                particles: Theme.particles
                plasmaOn: Theme.plasma
                accent: Theme.accent
                accentWarm: Theme.accentWarm
                strokeColor: Theme.hair
            }

            // живая строка распознанной речи под ядром
            Label {
                anchors.horizontalCenter: arc.horizontalCenter
                anchors.top: arc.bottom; anchors.topMargin: 18
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: core.interimText.length > 0 ? "«" + core.interimText + "»…" : stateCaption(core.state)
                color: core.interimText.length > 0 ? Theme.textPrimary : Theme.textMuted
                font.family: Theme.fontMain
                font.pixelSize: 14 * Theme.uiScale
                elide: Text.ElideMiddle
                Behavior on color { ColorAnimation { duration: Theme.dur(220) } }
            }

            // PTT-кнопка (дублирует глобальную горячую клавишу)
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 4
                width: 150; height: 40; radius: 20
                visible: core.micAvailable && !core.demoMode
                color: pttMa.pressed ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.25)
                                     : Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.08)
                border.color: Theme.accent; border.width: 1
                Label {
                    anchors.centerIn: parent
                    text: pttMa.pressed ? "СЛУШАЮ…" : "УДЕРЖИВАЙТЕ ДЛЯ ГОЛОСА"
                    color: Theme.accent; font.family: Theme.fontMono; font.pixelSize: 10 * Theme.uiScale
                }
                MouseArea {
                    id: pttMa
                    anchors.fill: parent
                    onPressed: core.pttDown()
                    onReleased: core.pttUp()
                }
            }
        }

        // ---- лента диалога справа ----
        ChatPanel {
            id: chatPanel
            anchors.right: parent.right; anchors.rightMargin: 16
            anchors.top: titlebar.bottom; anchors.bottom: statusStrip.top
            width: win.mini ? 0 : Math.max(340, Math.min(430, parent.width * 0.34))
            micAvailable: core.micAvailable
            onSendText: (t) => core.sendText(t)
        }

        // ---- нижняя строка состояния ----
        Rectangle {
            id: statusStrip
            anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
            height: 34
            color: Qt.rgba(Theme.raise.r, Theme.raise.g, Theme.raise.b, 0.6)
            border.color: Theme.hair; border.width: 1

            Row {
                anchors.left: parent.left; anchors.leftMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                spacing: 14
                // щит сетевого режима с анимацией смены
                Row {
                    spacing: 5
                    Icon { name: "shield"; width: 14; height: 14
                           fg: core.statusInfo.network === "offline" ? Theme.ok
                               : (core.statusInfo.network === "online" ? Theme.warn : Theme.accent)
                           anchors.verticalCenter: parent.verticalCenter
                           Behavior on fg { ColorAnimation { duration: Theme.dur(420) } } }
                    Label {
                        anchors.verticalCenter: parent.verticalCenter
                        text: core.statusInfo.network.toUpperCase()
                        color: Theme.textSecondary; font.family: Theme.fontMono; font.pixelSize: 10 * Theme.uiScale
                    }
                    MouseArea {
                        anchors.fill: parent; hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: netMenu.popupAt(mapToItem(win.contentItem, mouseX, mouseY))
                        Tooltip.visible: containsMouse; Tooltip.delay: 400
                        Tooltip.text: "Сетевой режим: нажмите чтобы сменить"
                    }
                }
                MenuPopup { id: netMenu }
                Label {
                    anchors.verticalCenter: parent.verticalCenter
                    text: core.statusInfo.model || "модель не выбрана"
                    color: Theme.textMuted; font.family: Theme.fontMono; font.pixelSize: 10 * Theme.uiScale
                }
                Label {
                    anchors.verticalCenter: parent.verticalCenter
                    text: core.statusInfo.ttft_ms !== undefined && core.statusInfo.ttft_ms !== null
                          ? "TTFT " + core.statusInfo.ttft_ms + " мс" : "TTFT —"
                    color: Theme.textMuted; font.family: Theme.fontMono; font.pixelSize: 10 * Theme.uiScale
                }
                Label {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "FPS " + (core.statusInfo.fps || 0)
                    color: (core.statusInfo.fps || 0) >= 50 ? Theme.textMuted : Theme.warn
                    font.family: Theme.fontMono; font.pixelSize: 10 * Theme.uiScale
                }
            }
            Row {
                anchors.right: parent.right; anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                spacing: 6
                HudButton { iconName: "mic-off"; width: 30; height: 26; active: core.state === "MUTED"
                            onClicked: core.setMuted(core.state !== "MUTED") }
                HudButton { iconName: "stop"; width: 30; height: 26; danger: core.busy
                            onClicked: core.stop() }
                HudButton { iconName: "search"; width: 30; height: 26
                            onClicked: palette.visible = true }
                HudButton { iconName: "shield"; width: 30; height: 26
                            onClicked: diagSheet.openNow() }
            }
        }

        // ---- палитра / подтверждения ----
        CommandPalette {
            id: palette
            z: 60
            onRunCommand: (cmd) => core.runPaletteCommand(cmd)
        }
        ConfirmDialog {
            id: confirmDlg
            z: 70
            visible: Object.keys(core.pendingConfirm).length > 0
            property var pc: core.pendingConfirm
            onPcChanged: if (visible && pc.request_id) show(pc)
            onAnswered: (reqId, accept) => core.answerConfirm(reqId, accept)
        }
        SettingsDrawer { id: settingsDrawer; z: 55 }
        DiagnosticsSheet { id: diagSheet; z: 56 }
    }

    // ================= MINI =================
    Item {
        id: miniView
        anchors.fill: parent
        visible: win.booted && win.mini
        opacity: visible ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.dur(220) } }

        MouseArea {   // перетаскивание мини-окна; клик — разворот
            anchors.fill: parent
            property point p0
            onPressed: p0 = mouse
            onPositionChanged: if (pressed && Math.abs(mouse.x - p0.x) + Math.abs(mouse.y - p0.y) > 6) {
                win.x += mouse.x - p0.x; win.y += mouse.y - p0.y; p0 = mouse;
            }
            onClicked: (mouse) => { if (!dragged) core.toggleMini(); }
            property bool dragged: false
        }
        ArcCore {
            id: miniArc
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top; anchors.topMargin: 14
            width: 170; height: 170
            st: core.state
            rmsLevel: core.rms
            spectrum: core.spectrum
            reducedMotion: Theme.reducedMotion
            particles: Theme.reducedMotion ? 0 : 30
            plasmaOn: Theme.plasma && !Theme.reducedMotion
            accent: Theme.accent
            accentWarm: Theme.accentWarm
            strokeColor: Theme.hair
        }
        Rectangle {   // полоска состояния
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: miniArc.bottom; anchors.topMargin: 8
            width: 150; height: 4; radius: 2
            color: Theme.hair
            Rectangle {
                width: parent.width * frac(); height: parent.height; radius: 2
                color: core.state === "LISTENING" ? Theme.accent
                       : core.state === "THINKING" ? Theme.accentWarm
                       : core.state === "ERROR" ? Theme.danger : Theme.ok
                function frac() {
                    return core.state === "LISTENING" ? 0.6 :
                           (core.state === "THINKING" || core.state === "STREAMING" || core.state === "SPEAKING") ? 1.0 : 0.15;
                }
                Behavior on width { NumberAnimation { duration: Theme.dur(220); easing.type: Theme.ease() } }
            }
        }
        Label {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom; anchors.bottomMargin: 8
            text: core.state + (core.interimText.length ? " · «" + core.interimText + "»" : "")
            color: Theme.textMuted; font.family: Theme.fontMono; font.pixelSize: 9 * Theme.uiScale
            elide: Text.ElideRight; width: parent.width - 20
            horizontalAlignment: Text.AlignHCenter
        }
    }

    // ================= тосты =================
    Toast { id: toast; z: 90; anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom
            anchors.bottomMargin: 48 }

    // ================= хоткеи =================
    Shortcut { sequence: "Ctrl+K"; onActivated: palette.visible = !palette.visible }
    Shortcut { sequence: "Escape"; onActivated: { palette.visible = false; settingsDrawer.closeNow(); diagSheet.closeNow(); } }
    Shortcut { sequence: "Ctrl+M"; onActivated: core.setMuted(core.state !== "MUTED") }
    Shortcut { sequence: "Ctrl+Shift+Space"; onActivated: core.toggleMini() }
    Shortcut { sequence: "Space"; enabled: !palette.visible && win.mini; onActivated: core.toggleMini() }

    function stateCaption(s) {
        switch (s) {
            case "BOOT": return "Инициализация…";
            case "IDLE": return core.micAvailable ? "Ожидание. Скажите «Компьютер» или печатайте." : "Голосовой ввод недоступен — работает текстовый чат.";
            case "WAKE": return "Да, сэр?";
            case "LISTENING": return "Слушаю команду…";
            case "THINKING": return "Обрабатываю запрос…";
            case "STREAMING": return "Формирую ответ…";
            case "SPEAKING": return "Говорю (микрофон на паузе)…";
            case "ERROR": return "Ошибка. См. журнал.";
            case "MUTED": return "Микрофон выключен.";
            default: return "";
        }
    }
}
