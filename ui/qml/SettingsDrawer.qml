// Панель настроек: вкладки. Логика применения — в Python (core.setSetting).
import "theme"
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Rectangle {
    id: drawer
    anchors.fill: parent
    visible: false
    color: "#66040710"
    z: 55

    function openNow() { visible = true; }
    function closeNow() { visible = false; }

    MouseArea { anchors.fill: parent; onClicked: drawer.closeNow() }

    GlassPanel {
        id: card
        width: Math.min(560, parent.width - 80)
        height: Math.min(520, parent.height - 90)
        anchors.centerIn: parent
        radius: Theme.rM
        glowBorder: true
        opacity: drawer.visible ? 1 : 0
        scale: drawer.visible || Theme.reducedMotion ? 1 : 0.96
        Behavior on opacity { NumberAnimation { duration: Theme.dur(220); easing.type: Theme.ease() } }
        Behavior on scale { NumberAnimation { duration: Theme.dur(220); easing.type: Easing.OutBack } }

        Column {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 12

            Row {
                width: parent.width
                Label { text: "НАСТРОЙКИ"; color: Theme.accent; font.family: Theme.fontMono
                        font.pixelSize: 12 * Theme.uiScale; font.letterSpacing: 3
                        anchors.verticalCenter: parent.verticalCenter }
                Item { width: parent.width - 220; height: 1 }
                HudButton { iconName: "close"; width: 30; height: 28; onClicked: drawer.closeNow() }
            }

            // вкладки
            Row {
                id: tabs
                property int currentIndex: 0
                spacing: 4
                Repeater {
                    model: ["Внешний вид", "Голос и микрофон", "Активация", "Сеть", "Безопасность"]
                    delegate: Rectangle {
                        required property int index
                        required property var modelData
                        width: tabLbl.implicitWidth + 18; height: 28
                        radius: 14
                        color: tabs.currentIndex === index ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18) : "transparent"
                        border.color: tabs.currentIndex === index ? Theme.accent : Theme.hair
                        border.width: 1
                        TapHandler { onTapped: tabs.currentIndex = index }
                        Label { id: tabLbl; anchors.centerIn: parent; text: modelData
                                color: tabs.currentIndex === index ? Theme.accent : Theme.textSecondary
                                font.family: Theme.fontMain; font.pixelSize: 11 * Theme.uiScale }
                    }
                }
            }

            Flickable {
                width: parent.width
                height: parent.height - 120
                contentHeight: stack.childrenRect.height
                clip: true
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                StackLayout {
                    id: stack
                    width: parent.width
                    currentIndex: tabs.currentIndex >= 0 ? tabs.currentIndex : 0

                    // ---------- Внешний вид ----------
                    Column {
                        spacing: 10
                        Section { title: "Тема" }
                        Row {
                            spacing: 8
                            Repeater {
                                model: theme.listThemes("")
                                delegate: Rectangle {
                                    required property var modelData
                                    width: thLbl.implicitWidth + 20; height: 30; radius: 15
                                    color: theme.name === modelData ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.2) : "transparent"
                                    border.color: theme.name === modelData ? Theme.accent : Theme.hair; border.width: 1
                                    TapHandler { onTapped: core.selectTheme(modelData) }
                                    Label { id: thLbl; anchors.centerIn: parent; text: modelData.replace("_", " ")
                                            color: Theme.textPrimary; font.family: Theme.fontMain; font.pixelSize: 11 * Theme.uiScale }
                                }
                            }
                        }
                        Section { title: "Анимация" }
                        SwitchRow { label: "Уменьшить анимацию"; checked: core.reducedMotion
                                    onToggled: (v) => core.setSetting("reduced_motion", JSON.stringify(v)) }
                        Section { title: "Масштаб интерфейса" }
                        Row {
                            spacing: 8
                            Repeater {
                                model: [100, 125, 150]
                                delegate: Rectangle {
                                    required property var modelData
                                    width: 54; height: 28; radius: 14
                                    color: Theme.uiScalePct === modelData ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.2) : "transparent"
                                    border.color: Theme.uiScalePct === modelData ? Theme.accent : Theme.hair; border.width: 1
                                    TapHandler { onTapped: core.setSetting("ui_scale", JSON.stringify(modelData)) }
                                    Label { anchors.centerIn: parent; text: modelData + "%"; color: Theme.textPrimary
                                            font.family: Theme.fontMono; font.pixelSize: 11 * Theme.uiScale }
                                }
                            }
                        }
                        Section { title: "Звуки интерфейса" }
                        SwitchRow { label: "Блипы (wake/confirm/error)"; checked: sSounds.checked
                                    property alias inner: sSounds
                                    Switch { id: sSounds; checked: true; onToggled: core.setSetting("sounds.enabled", JSON.stringify(checked)) } }
                    }

                    // ---------- Голос и микрофон ----------
                    Column {
                        spacing: 10
                        Section { title: "Озвучка (Piper)" }
                        PathField { key: "voice.piper_bin"; placeholder: "C:\\…\\piper.exe (не обязательно)" }
                        PathField { key: "voice.piper_model"; placeholder: "C:\\…\\ru_RU-*.onnx" }
                        Label { visible: !core.ttsAvailable; text: "Piper не найден — озвучка выключена. Приложение работает без неё."
                                color: Theme.warn; font.family: Theme.fontMain; font.pixelSize: 11 * Theme.uiScale }
                        SliderRow { label: "Скорость речи"; from: 0.6; to: 1.6; value: 1.0
                                    onMoved: core.setSetting("voice.rate", JSON.stringify(value)) }
                        SliderRow { label: "Громкость речи"; from: 0; to: 1; value: 1.0
                                    onMoved: core.setSetting("voice.volume", JSON.stringify(value)) }
                        HudButton { text2: "Проверить голос"; iconName: "bolt"; onClicked: core.sendText("тест голоса") }
                        Section { title: "Микрофон" }
                        Label { text: core.micAvailable ? "Устройство захвата обнаружено." :
                                                       "Микрофон недоступен — голосовой ввод выключен, текстовый чат работает."
                                color: core.micAvailable ? Theme.ok : Theme.warn
                                font.family: Theme.fontMain; font.pixelSize: 11 * Theme.uiScale }
                        PathField { key: "stt.model_path"; placeholder: "C:\\…\\vosk-model-small-ru-0.22" }
                    }

                    // ---------- Активация ----------
                    Column {
                        spacing: 10
                        Section { title: "Ключевое слово" }
                        LineField { key: "wake.word"; def: "компьютер"; label: "Слово активации" }
                        LineField { key: "wake.aliases"; def: "джарвис"; label: "Синонимы (через запятую)" }
                        Section { title: "Строгость детекта" }
                        Row {
                            spacing: 8
                            Repeater {
                                model: [["strict", "строгая"], ["medium", "средняя"], ["fuzzy", "нечёткая"]]
                                delegate: Rectangle {
                                    required property var modelData
                                    width: stLbl.implicitWidth + 18; height: 28; radius: 14
                                    color: hl.hovered ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.12) : "transparent"
                                    border.color: Theme.hair; border.width: 1
                                    HoverHandler { id: hl }
                                    TapHandler { onTapped: core.setSetting("wake.strictness", JSON.stringify(modelData[0])) }
                                    Label { id: stLbl; anchors.centerIn: parent; text: modelData[1]
                                            color: Theme.textSecondary; font.family: Theme.fontMain; font.pixelSize: 11 * Theme.uiScale }
                                }
                            }
                        }
                        Section { title: "Прочее" }
                        SwitchRow { label: "Постоянное прослушивание wake-word"; checked: true
                                    onToggled: (v) => core.setSetting("wake.always_on", JSON.stringify(v)) }
                        Label {
                            wrapMode: Text.Wrap; width: parent.width
                            text: "Детект построен на Vosk с ограниченной грамматикой — это НЕ специализированная wake-word модель: возможны ложные срабатывания; точность не измерялась."
                            color: Theme.textMuted; font.family: Theme.fontMain; font.pixelSize: 10 * Theme.uiScale
                        }
                    }

                    // ---------- Сеть ----------
                    Column {
                        spacing: 10
                        Section { title: "Режим (по умолчанию OFFLINE)" }
                        Row {
                            spacing: 8
                            Repeater {
                                model: ["offline", "hybrid", "online"]
                                delegate: Rectangle {
                                    required property var modelData
                                    width: nmLbl.implicitWidth + 20; height: 28; radius: 14
                                    color: core.statusInfo.network === modelData ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.2) : "transparent"
                                    border.color: core.statusInfo.network === modelData ? Theme.accent : Theme.hair; border.width: 1
                                    TapHandler { onTapped: core.setNetworkMode(modelData) }
                                    Label { id: nmLbl; anchors.centerIn: parent; text: modelData.toUpperCase()
                                            color: Theme.textPrimary; font.family: Theme.fontMono; font.pixelSize: 11 * Theme.uiScale }
                                }
                            }
                        }
                        Label { wrapMode: Text.Wrap; width: parent.width
                                text: "OFFLINE: исходящие запросы разрешены только к 127.0.0.1 (Ollama). Любой внешний адрес блокируется шлюзом и пишется в аудит."
                                color: Theme.textMuted; font.family: Theme.fontMain; font.pixelSize: 10 * Theme.uiScale }
                        Section { title: "Ollama (loopback)" }
                        PathField { key: "ollama.base_url"; placeholder: "http://127.0.0.1:11434" }
                        LineField { key: "ollama.model"; def: ""; label: "Модель (из ollama list)" }
                        SliderRow { label: "num_ctx"; from: 2048; to: 8192; value: 4096; step: 2048
                                    onMoved: core.setSetting("ollama.num_ctx", JSON.stringify(Math.round(value))) }
                        Section { title: "Персона" }
                        Row {
                            spacing: 8
                            Repeater {
                                model: ["jarvis", "computer", "neutral"]
                                delegate: Rectangle {
                                    required property var modelData
                                    width: pLbl.implicitWidth + 18; height: 28; radius: 14
                                    color: Theme.hair; border.width: 1; border.color: Theme.hair
                                    TapHandler { onTapped: core.setSetting("persona", JSON.stringify(modelData)) }
                                    Label { id: pLbl; anchors.centerIn: parent; text: modelData
                                            color: Theme.textSecondary; font.family: Theme.fontMain; font.pixelSize: 11 * Theme.uiScale }
                                }
                            }
                        }
                    }

                    // ---------- Безопасность ----------
                    Column {
                        spacing: 10
                        Section { title: "Инструменты" }
                        SwitchRow { label: "Подтверждать опасные действия"; checked: true
                                    onToggled: (v) => core.setSetting("security.confirm_dangerous", JSON.stringify(v)) }
                        SwitchRow { label: "Журнал аудита"; checked: true
                                    onToggled: (v) => core.setSetting("security.audit_enabled", JSON.stringify(v)) }
                        Section { title: "Рабочая папка" }
                        PathField { key: "workspace.root"; placeholder: "%USERPROFILE%\\JarvisWorkspace" }
                        Label { wrapMode: Text.Wrap; width: parent.width
                                text: "Рабочая папка — НЕ песочница. Модель не может удалять файлы вне подтверждённых операций; все пути проверяются на выходе за корни."
                                color: Theme.textMuted; font.family: Theme.fontMain; font.pixelSize: 10 * Theme.uiScale }
                        Section { title: "API-ключи" }
                        Label { text: "Ключи хранятся в Windows Credential Manager (keyring), никогда в config.json/логах."
                                color: Theme.textMuted; font.family: Theme.fontMain; font.pixelSize: 10 * Theme.uiScale }
                    }
                }
            }
        }
    }

    component Section : Label {
        text: title; color: Theme.accent; font.family: Theme.fontMono
        font.pixelSize: 10 * Theme.uiScale; font.letterSpacing: 2
        property string title: ""
    }
    component SwitchRow : Row {
        property alias checked: sw.checked
        property alias label: lbl2.text
        signal toggled(bool v)
        spacing: 10
        Label { id: lbl2; anchors.verticalCenter: parent.verticalCenter; color: Theme.textSecondary
                font.family: Theme.fontMain; font.pixelSize: 12 * Theme.uiScale }
        Switch {
            id: sw
            anchors.verticalCenter: parent.verticalCenter
            onToggled: parent.toggled(checked)
            contentItem: Rectangle { width: 34; height: 18; radius: 9
                color: sw.checked ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.4) : Theme.hair
                Rectangle { width: 12; height: 12; radius: 6; y: 3; color: Theme.textPrimary
                    x: sw.checked ? 19 : 3
                    Behavior on x { NumberAnimation { duration: Theme.dur(140) } } } }
        }
    }
    component SliderRow : Column {
        property string label: ""
        property real from: 0; property real to: 1; property real value: 0.5
        property int step: 0
        signal moved()
        width: parent ? parent.width : 300
        spacing: 2
        Label { text: parent.label + ": " + parent.value.toFixed(parent.step > 0 ? 0 : 2)
                color: Theme.textSecondary; font.family: Theme.fontMain; font.pixelSize: 11 * Theme.uiScale }
        Slider {
            width: parent.width; from: parent.from; to: parent.to; value: parent.value
            stepSize: parent.step
            onMoved: parent.moved()
        }
    }
    component PathField : Column {
        property string key: ""
        property string placeholder: ""
        width: parent ? parent.width : 300
        spacing: 2
        TextField {
            width: parent.width
            placeholderText: parent.placeholder
            text: String((JSON.parse(core.settingsJson)[parent.key.split(".")[0]] || {})[parent.key.split(".")[1]] ?? "")
            color: Theme.textPrimary; font.family: Theme.fontMono; font.pixelSize: 11 * Theme.uiScale
            background: Rectangle { color: "transparent"; border.color: Theme.hair; border.width: 1; radius: 6 }
            onEditingFinished: core.setSetting(parent.key, JSON.stringify(text))
        }
    }
    component LineField : Column {
        property string key: ""; property string def: ""; property string label: ""
        width: parent ? parent.width : 300
        spacing: 2
        Label { text: parent.label; color: Theme.textSecondary; font.family: Theme.fontMain; font.pixelSize: 11 * Theme.uiScale }
        TextField {
            width: parent.width
            placeholderText: parent.def
            color: Theme.textPrimary; font.family: Theme.fontMain; font.pixelSize: 12 * Theme.uiScale
            background: Rectangle { color: "transparent"; border.color: Theme.hair; border.width: 1; radius: 6 }
            onEditingFinished: core.setSetting(parent.key, JSON.stringify(text))
        }
    }
}
