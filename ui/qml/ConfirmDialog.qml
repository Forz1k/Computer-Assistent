// Оверлей подтверждений опасных действий. Блокирующий, с таймаутом 30 с.
import "theme"
import QtQuick
import QtQuick.Controls.Basic

Rectangle {
    id: dlg
    anchors.fill: parent
    visible: false
    color: "#80040710"   // тонированный затемняющий слой
    property string reqId: ""
    property int remaining: 30
    signal answered(string reqId, bool accept)

    Timer {
        id: ttl
        interval: 1000; running: dlg.visible; repeat: true
        onTriggered: {
            dlg.remaining -= 1;
            if (dlg.remaining <= 0) dlg.reject();
        }
    }
    function show(payload) {
        reqId = payload.request_id;
        title2.text = payload.title || "Подтвердите действие";
        toolName.text = payload.tool || "";
        argsLbl.text = JSON.stringify(payload.args || {}, null, 1);
        riskLbl.text = (payload.risk === "high") ? "ВЫСОКИЙ РИСК" : "СРЕДНИЙ РИСК";
        riskLbl.color = (payload.risk === "high") ? Theme.danger : Theme.warn;
        remaining = 30;
        visible = true;
    }
    function accept() { visible = false; dlg.answered(reqId, true); }
    function reject() { visible = false; dlg.answered(reqId, false); }

    GlassPanel {
        id: card
        width: Math.min(460, parent.width - 40)
        height: col.implicitHeight + 36
        anchors.centerIn: parent
        radius: Theme.rM
        glowBorder: true
        opacity: 0
        scale: Theme.reducedMotion ? 1 : 0.95
        states: State {
            name: "shown"; when: dlg.visible
            PropertyChanges { target: card; opacity: 1; scale: 1 }
        }
        transitions: Transition {
            NumberAnimation { properties: "opacity,scale"; duration: Theme.dur(220); easing.type: Theme.ease() }
        }

        Column {
            id: col
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: 18
            spacing: 12

            Row {
                spacing: 10
                Icon { name: "shield"; width: 22; height: 22; fg: Theme.warn }
                Label {
                    id: title2
                    text: "Подтвердите действие"
                    color: Theme.textPrimary
                    font.family: Theme.fontMain
                    font.pixelSize: 16 * Theme.uiScale
                    font.bold: true
                }
            }
            Row {
                spacing: 8
                Label {
                    id: toolName
                    text: ""
                    color: Theme.accent
                    font.family: Theme.fontMono
                    font.pixelSize: 12 * Theme.uiScale
                }
                Label {
                    id: riskLbl
                    text: ""
                    color: Theme.warn
                    font.family: Theme.fontMono
                    font.pixelSize: 11 * Theme.uiScale
                }
            }
            Rectangle {
                width: col.width
                height: argsLbl.implicitHeight + 16
                radius: Theme.rS
                color: Qt.rgba(0, 0, 0, 0.35)
                border.color: Theme.hair
                border.width: 1
                Text {
                    id: argsLbl
                    anchors.fill: parent
                    anchors.margins: 8
                    text: "{}"
                    color: Theme.textSecondary
                    font.family: Theme.fontMono
                    font.pixelSize: 11 * Theme.uiScale
                    wrapMode: Text.WrapAnywhere
                    maximumLineCount: 8
                    elide: Text.ElideRight
                }
            }

            Row {
                spacing: 10
                HudButton { iconName: "check"; text2: "Разрешить (" + dlg.remaining + ")"; active: true
                            accent: Theme.ok; onClicked: card.parent.accept() }
                HudButton { iconName: "close"; text2: "Отклонить"; danger: true
                            onClicked: card.parent.reject() }
            }
            Label {
                text: "Автоотклонение через " + dlg.remaining + " с. Действие попадёт в журнал аудита."
                color: Theme.textMuted
                font.family: Theme.fontMain
                font.pixelSize: 11 * Theme.uiScale
            }
        }
    }
}
