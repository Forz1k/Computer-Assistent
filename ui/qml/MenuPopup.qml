// Меню смены сетевого режима (щит в статус-баре).
import "theme"
import QtQuick
import QtQuick.Controls.Basic

Rectangle {
    id: netMenu
    visible: false
    width: 200
    height: col.implicitHeight + 16
    radius: Theme.rS
    color: Qt.rgba(Theme.raise.r, Theme.raise.g, Theme.raise.b, 0.97)
    border.color: Theme.accent
    border.width: 1
    z: 200

    function popupAt(p) { x = p.x - width / 2; y = Math.max(4, p.y); visible = true; }
    function choose(mode) { core.setNetworkMode(mode); netMenu.visible = false; }

    Column {
        id: col
        anchors.left: parent.left; anchors.right: parent.right
        anchors.top: parent.top; anchors.margins: 8
        spacing: 2
        Repeater {
            model: [ ["offline", "OFFLINE — только loopback"],
                     ["hybrid", "HYBRID — локально + явные инструменты"],
                     ["online", "ONLINE — внешний LLM/поиск"] ]
            delegate: Rectangle {
                required property var modelData
                width: col.width; height: 30; radius: 6
                color: hl.hovered ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.12) : "transparent"
                HoverHandler { id: hl }
                TapHandler { onTapped: netMenu.choose(modelData[0]) }
                Label {
                    anchors.left: parent.left; anchors.leftMargin: 8; anchors.verticalCenter: parent.verticalCenter
                    text: modelData[1]
                    color: core.statusInfo.network === modelData[0] ? Theme.accent : Theme.textSecondary
                    font.family: Theme.fontMono; font.pixelSize: 10 * Theme.uiScale
                }
            }
        }
    }
    MouseArea { anchors.fill: parent; hoverEnabled: true; onExited: netMenu.visible = false }
}
