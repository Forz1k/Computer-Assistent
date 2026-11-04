// Общие стили из темы (привязаны к context-объекту `theme` из Python).
pragma Singleton
import QtQuick

Item {
    id: themeData

    property QtObject t: theme   // CoreBridge ThemeBridge

    // цвета с фолбэками — если тема не загрузилась, UI живёт
    property color bgVoid:       t.colors.bg_void       || "#05080E"
    property color bgBase:       t.colors.bg_base       || "#080D16"
    property color glass:        t.colors.surface_glass || "#0E1622"
    property real    glassAlpha: t.colors.surface_glass_alpha !== undefined ? t.colors.surface_glass_alpha : 0.62
    property color raise:        t.colors.surface_raise  || "#141F2E"
    property color hair:         t.colors.stroke_hair    || "#1E2C40"
    property color accent:       t.colors.accent_primary || "#38E1FF"
    property color accentWarm:   t.colors.accent_second  || "#FFB65C"
    property color textPrimary:  t.colors.text_primary   || "#E8F3FF"
    property color textSecondary: t.colors.text_secondary || "#93A9C6"
    property color textMuted:    t.colors.text_muted     || "#5B6E8A"
    property color ok:           t.colors.ok             || "#3DDC97"
    property color warn:         t.colors.warn           || "#FFC857"
    property color danger:       t.colors.danger         || "#FF5C6C"

    property real rS: t.radii.s
    property real rM: t.radii.m
    property real rL: t.radii.l

    property string fontMain: t.fontFamily
    property string fontMono: t.fontMono

    property int glowRadius: t.glow.radius
    property real glowOpacity: t.glow.opacity
    property int particles: t.particleCount
    property bool plasma: t.plasmaEnabled

    property bool reducedMotion: false
    property real uiScale: 1.0

    function ease() { return reducedMotion ? Easing.Linear : Easing.InOutCubic; }
    function dur(ms) { return reducedMotion ? Math.min(80, ms / 4) : ms; }

    // синхронизация с Python-мостом
    function refresh() {
        reducedMotion = core.reducedMotion;
        uiScale = (core.settingsObj.ui_scale || 100) / 100.0;
    }
    readonly property real uiScalePct: (core.settingsObj.ui_scale || 100)
    Connections {
        target: theme
        function onThemeChanged() { refresh(); }
    }
    Connections {
        target: core
        function onSettingsChanged() { refresh(); }
    }
    Component.onCompleted: refresh()
}
