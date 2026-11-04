// Стеклянная панель: полупрозрачная подложка + волосяная обводка + мягкая тень.
import QtQuick
import QtQuick.Effects

Rectangle {
    id: panel
    property real radius: Theme.rM
    property color tint: Theme.glass
    property real alpha: Theme.glassAlpha
    property bool hairline: true
    property bool glowBorder: false
    color: Qt.rgba(tint.r, tint.g, tint.b, alpha)
    border.color: glowBorder ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.35)
                             : Theme.hair
    border.width: hairline ? 1 : 0
    radius: Theme.rM

    // верхний блик стекла
    Rectangle {
        anchors.left: parent.left; anchors.right: parent.right
        anchors.top: parent.top
        height: parent.height * 0.4
        radius: parent.radius
        color: Qt.rgba(1, 1, 1, 0.025)
    }
    MultiEffect {
        source: panel
        anchors.fill: panel
        shadowEnabled: true
        shadowColor: "#000000"
        shadowBlur: 0.35
        shadowVerticalOffset: 6
        shadowHorizontalOffset: 0
        shadowOpacity: 0.35
        z: -1
    }
}
