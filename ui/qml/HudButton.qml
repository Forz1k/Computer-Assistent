// HUD-кнопка: hairline-обводка, glow по наведению/нажатию, press-scale 0.96.
import QtQuick
import QtQuick.Controls.Basic

Button {
    id: btn
    property string iconName: ""
    property string text2: ""
    property color accent: Theme.accent
    property bool danger: false
    property bool active: false
    implicitHeight: 40
    implicitWidth: Math.max(40, (btn.text2.length ? lbl.implicitWidth + 34 : 44))
    padding: 8
    enabled: true
    background: Rectangle {
        radius: Theme.rS
        color: btn.active ? Qt.rgba(btn.accent.r, btn.accent.g, btn.accent.b, 0.14)
                          : (btn.hovered ? Qt.rgba(1, 1, 1, 0.05) : "transparent")
        border.color: btn.danger ? Theme.danger
                                 : (btn.active ? btn.accent : Theme.hair)
        border.width: 1
        opacity: btn.enabled ? 1 : 0.4
        Behavior on color { ColorAnimation { duration: Theme.dur(160); easing.type: Theme.ease() } }
        Behavior on border.color { ColorAnimation { duration: Theme.dur(160); easing.type: Theme.ease() } }
    }
    contentItem: Row {
        spacing: 7
        Icon {
            visible: btn.iconName.length > 0
            name: btn.iconName
            width: 18; height: 18
            anchors.verticalCenter: parent.verticalCenter
            fg: btn.danger ? Theme.danger
                : (btn.active || btn.hovered) ? btn.accent : Theme.textSecondary
        }
        Label {
            id: lbl
            visible: btn.text2.length > 0
            text: btn.text2
            color: btn.danger ? Theme.danger : Theme.textPrimary
            font.family: Theme.fontMain
            font.pixelSize: 13 * Theme.uiScale
            anchors.verticalCenter: parent.verticalCenter
        }
    }
    scale: Theme.reducedMotion ? 1 : (down ? 0.96 : 1.0)
    Behavior on scale {
        NumberAnimation { duration: Theme.dur(140); easing.type: Theme.ease() }
    }
}
