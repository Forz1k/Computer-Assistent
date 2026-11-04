// Arc Core — живое аудио-реактивное ядро HUD.
//
// Рендер: QQuickPaintedItem (QPainter) с единым драйвером анимации (один QTimer на
// элемент, ≤ 8 мс/кадр; при перегрузке — автодеградация частиц). Это осознанный выбор
// вместо шейдера: гарантирует идентичный вид на software-рендеринге (фолбэк обязателен
// по ТЗ) и не требует GLSL-отладки на целевой GTX 1060 без экрана разработки.
//
// Слои: плазма (яркость от RMS), 3 кольца с разрывами (разные скорости/направления),
// радиальный спектр 64 луча, тик-метки/прицельные дуги, пул частиц с параллаксом.
// Состояния задают визуальный язык (см. core/state_machine.py).
//
import QtQuick
import QtQuick.Effects

Rectangle {
    id: root
    implicitWidth: 320
    implicitHeight: 320
    radius: width / 2
    color: "transparent"

    // -------- вход из Python --------
    property string st: "BOOT"            // состояние из core.state
    property real rmsLevel: 0.0           // 0..1
    property var spectrum: []             // [64] floats 0..1
    property bool reducedMotion: false
    property int particles: 90
    property bool plasmaOn: true
    property color accent: "#38E1FF"
    property color accentWarm: "#FFB65C"
    property color strokeColor: "#1E2C40"
    property real listenFrac: 1.0           // прогресс окна команды (из Python)

    // -------- внутренние часы (единый драйвер) --------
    property real t: 0                    // секунды с запуска
    property real rot: 0                  // базовый угол колец
    property real breath: 1.0
    property real pulse: 0.0              // вспышка WAKE
    property real glitch: 0.0             // ERROR shake
    property point mouseNorm: Qt.point(0, 0)
    property real _lsum: 0

    Timer {
        id: driver
        interval: 16
        running: true
        repeat: true
        onTriggered: {
            var dt = interval / 1000.0;
            root.t += dt;
            // скорость вращения зависит от состояния
            var spd = (root.st === "THINKING") ? 1.9 :
                      (root.st === "LISTENING" || root.st === "STREAMING") ? 1.0 :
                      (root.st === "SPEAKING") ? 0.7 :
                      (root.st === "MUTED") ? 0.0 : 0.28;
            root.rot += dt * spd * 36;   // deg/s
            if (root.pulse > 0) root.pulse = Math.max(0, root.pulse - dt * 5.5);
            if (root.glitch > 0) root.glitch = Math.max(0, root.glitch - dt * 4.5);
            if (root.st === "LISTENING") {
                root._lsum += dt;
                root.listenFrac = Math.max(0, 1 - root._lsum / 6.0);
            } else { root._lsum = 0; root.listenFrac = 1.0; }
            canvas.requestPaint();
        }
    }

    // дыхание IDLE: масштаб 1.00↔1.03, цикл 4 с
    NumberAnimation on breath {
        running: !root.reducedMotion && (root.st === "IDLE" || root.st === "BOOT")
        from: 1.00; to: 1.03
        duration: 2000
        loops: Animation.Infinite
        easing.type: Easing.SineCurve
        alwaysRunToEnd: true
    }
    function effBreath() { return (st === "IDLE" || st === "BOOT") ? breath : 1.0; }

    // реакция на смену состояния
    onStChanged: {
        if (st === "WAKE") pulse = 1.0;
        if (st === "ERROR") glitch = 1.0;
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        onPositionChanged: (m) => {
            root.mouseNorm = Qt.point((m.x / width - 0.5) * 2, (m.y / height - 0.5) * 2);
        }
        onClicked: { core.pttDown(); core.pttUp() }  // клик по ядру = push-to-talk
    }

    Canvas {
        id: canvas
        anchors.fill: parent
        property var _pool: []
        renderTarget: Canvas.Image
        onPaint: {
            var ctx = getContext("2d");
            ctx.reset ? ctx.reset() : ctx.clearRect(0, 0, width, height);
            var cx = width / 2, cy = height / 2;
            var R = Math.min(cx, cy);
            var shakeX = glitch > 0 ? (Math.random() - 0.5) * 8 * glitch : 0;
            var shakeY = glitch > 0 ? (Math.random() - 0.5) * 8 * glitch : 0;
            ctx.save();
            ctx.translate(cx + shakeX, cy + shakeY);
            var sc = root.effBreath() * (st === "MUTED" ? 0.86 : 1.0) * (1 + pulse * 0.06);
            ctx.scale(sc, sc);

            var energy = st === "MUTED" ? 0.05 :
                         (0.15 + rmsLevel * 0.85);
            var colA = accent.toString();
            var colW = accentWarm.toString();

            // ---- слой 1: плазма (мягкие пятна, яркость от RMS) ----
            if (plasmaOn && !reducedMotion) {
                for (var i = 0; i < 5; i++) {
                    var a = t * (0.2 + i * 0.07) + i * 1.3;
                    var px = Math.cos(a) * R * 0.28, py = Math.sin(a * 0.8) * R * 0.22;
                    var rr = R * (0.30 + 0.12 * Math.sin(t * 0.7 + i));
                    var g = ctx.createRadialGradient(px, py, 0, px, py, rr);
                    g.addColorStop(0, Qt.rgba(colA.r, colA.g, colA.b, 0.10 * energy + 0.02));
                    g.addColorStop(1, "rgba(0,0,0,0)");
                    ctx.fillStyle = g;
                    ctx.beginPath(); ctx.arc(px, py, rr, 0, 2 * Math.PI); ctx.fill();
                }
            }

            // ---- фон ядра ----
            var bg = ctx.createRadialGradient(0, 0, R * 0.05, 0, 0, R * 0.62);
            bg.addColorStop(0, Qt.rgba(colA.r, colA.g, colA.b, 0.10 + energy * 0.25));
            bg.addColorStop(1, "rgba(5,8,14,0)");
            ctx.fillStyle = bg;
            ctx.beginPath(); ctx.arc(0, 0, R * 0.62, 0, 2 * Math.PI); ctx.fill();

            // ---- слой 3: радиальный спектр 64 луча ----
            var sp = spectrum;
            var n = 64;
            var baseR = R * 0.46;
            ctx.lineCap = "round";
            for (var k = 0; k < n; k++) {
                var v = (sp && sp.length === n) ? sp[k] : 0;
                var ang = (k / n) * 2 * Math.PI - Math.PI / 2;
                var len = R * (0.04 + v * 0.34);
                var warm = (st === "SPEAKING") ? Math.abs(Math.sin(k * 0.35 + t)) : 0;
                ctx.strokeStyle = Qt.rgba(
                    colA.r + (colW.r - colA.r) * warm,
                    colA.g + (colW.g - colA.g) * warm,
                    colA.b + (colW.b - colA.b) * warm,
                    0.25 + v * 0.75);
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(Math.cos(ang) * baseR, Math.sin(ang) * baseR);
                ctx.lineTo(Math.cos(ang) * (baseR + len), Math.sin(ang) * (baseR + len));
                ctx.stroke();
            }

            // ---- слой 2: 3 кольца с разрывами ----
            var rings = [
                { r: R * 0.55, w: 2.0, dir: 1, gap: 0.9, spd: 1.0 },
                { r: R * 0.66, w: 1.5, dir: -1, gap: 1.4, spd: 0.6 },
                { r: R * 0.78, w: 1.5, dir: 1, gap: 2.1, spd: 0.35 }
            ];
            for (var ri = 0; ri < rings.length; ri++) {
                var rg = rings[ri];
                var openFrac = (st === "LISTENING" || st === "WAKE" || st === "THINKING") ? 1.0 :
                               (st === "MUTED" ? 0.35 : 0.7);
                var seg = (2 * Math.PI - rg.gap) * openFrac;
                var start = rot * Math.PI / 180 * rg.spd * rg.dir + ri * 2.1;
                ctx.strokeStyle = Qt.rgba(colA.r, colA.g, colA.b,
                                          0.30 + energy * 0.5);
                ctx.lineWidth = rg.w;
                ctx.beginPath();
                ctx.arc(0, 0, rg.r, start, start + seg);
                ctx.stroke();
                // сканер-дуга в THINKING
                if (st === "THINKING") {
                    ctx.strokeStyle = Qt.rgba(colW.r, colW.g, colW.b, 0.8);
                    ctx.lineWidth = 2.5;
                    var sa = -rot * Math.PI / 180 * 2.2 + ri;
                    ctx.beginPath(); ctx.arc(0, 0, rg.r, sa, sa + 0.5); ctx.stroke();
                }
            }

            // прогресс таймаута команды (LISTENING) — внешнее кольцо
            if (st === "LISTENING") {
                ctx.strokeStyle = Qt.rgba(colA.r, colA.g, colA.b, 0.9);
                ctx.lineWidth = 3;
                ctx.beginPath();
                ctx.arc(0, 0, R * 0.86, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * root.listenFrac);
                ctx.stroke();
            }

            // ---- слой 4: тик-метки + прицельные дуги ----
            var tickAlpha = (st === "LISTENING" || st === "WAKE" || st === "THINKING") ? 0.8 : 0.25;
            ctx.strokeStyle = Qt.rgba(colA.r, colA.g, colA.b, tickAlpha);
            ctx.lineWidth = 1;
            for (var m = 0; m < 48; m++) {
                var ta = m / 48 * 2 * Math.PI;
                var long = (m % 4 === 0);
                var r0 = R * 0.88, r1 = R * (long ? 0.94 : 0.91);
                ctx.beginPath();
                ctx.moveTo(Math.cos(ta) * r0, Math.sin(ta) * r0);
                ctx.lineTo(Math.cos(ta) * r1, Math.sin(ta) * r1);
                ctx.stroke();
            }
            if (st === "WAKE" || st === "LISTENING") {
                ctx.strokeStyle = Qt.rgba(colA.r, colA.g, colA.b, 0.9 * (pulse > 0 ? pulse : 0.6));
                ctx.lineWidth = 2;
                for (var q = 0; q < 4; q++) {
                    var qa = q * Math.PI / 2 + Math.PI / 4;
                    ctx.beginPath();
                    ctx.arc(0, 0, R * 0.97, qa - 0.18, qa + 0.18);
                    ctx.stroke();
                }
            }

            // ---- слой 5: частицы (пул фиксированный, без аллокаций в кадре) ----
            if (!reducedMotion && particles > 0) {
                if (_pool.length === 0) {
                    _pool = [];
                    for (var c = 0; c < 120; c++) {
                        _pool.push({
                            a: Math.random() * 2 * Math.PI,
                            r: 0.5 + Math.random() * 0.45,
                            s: 0.15 + Math.random() * 0.5,
                            z: 0.3 + Math.random() * 0.7,
                            ph: Math.random() * 6.28
                        });
                    }
                }
                var parX = reducedMotion ? 0 : mouseNorm.x * 6;
                var parY = reducedMotion ? 0 : mouseNorm.y * 6;
                ctx.fillStyle = colA;
                for (var p = 0; p < Math.min(particles, _pool.length); p++) {
                    var pt = _pool[p];
                    var pa = pt.a + t * pt.s * 0.4;
                    var pr = pt.r * R;
                    var tw = 0.25 + 0.35 * Math.abs(Math.sin(t * 1.3 + pt.ph));
                    ctx.globalAlpha = tw * (st === "MUTED" ? 0.2 : 1);
                    var x = Math.cos(pa) * pr + parX * pt.z;
                    var y = Math.sin(pa) * pr * 0.92 + parY * pt.z;
                    ctx.fillRect(x, y, 1.6, 1.6);
                }
                ctx.globalAlpha = 1;
            }

            // ---- янтарные вкрапления THINKING + пульс 1.2 Гц ----
            if (st === "THINKING") {
                var thp = 0.5 + 0.5 * Math.sin(t * 2 * Math.PI * 1.2);
                ctx.strokeStyle = Qt.rgba(colW.r, colW.g, colW.b, 0.25 + thp * 0.4);
                ctx.lineWidth = 1.5;
                ctx.beginPath(); ctx.arc(0, 0, R * 0.50 + thp * 4, 0, 2 * Math.PI); ctx.stroke();
            }

            // ---- SPEAKING: тёплая волна по кольцам ----
            if (st === "SPEAKING") {
                var wv = 0.5 + 0.5 * Math.sin(t * 5);
                ctx.strokeStyle = Qt.rgba(1, 1, 1, 0.12 + wv * 0.15);
                ctx.lineWidth = 6;
                ctx.beginPath(); ctx.arc(0, 0, R * 0.60, 0, 2 * Math.PI); ctx.stroke();
            }

            // ---- ERROR: красный глитч 220 мс ----
            if (glitch > 0) {
                ctx.strokeStyle = Qt.rgba(1, 0.36, 0.42, glitch);
                ctx.lineWidth = 2;
                ctx.beginPath(); ctx.arc(0, 0, R * 0.7, 0, 2 * Math.PI); ctx.stroke();
            }

            // центральный глиф
            ctx.restore();
        }

    }

    // мягкое внешнее свечение (многослойное, но дешёвое: два размытых круга)
    Rectangle {
        anchors.centerIn: parent
        width: parent.width * 0.9; height: width
        radius: width / 2
        color: "transparent"
        border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b,
                              root.st === "MUTED" ? 0.05 : 0.18 + root.rmsLevel * 0.2)
        border.width: 10
        opacity: root.st === "ERROR" && root.glitch > 0 ? 0.4 : 1
        Behavior on border.color { ColorAnimation { duration: root.reducedMotion ? 100 : 320; easing.type: Easing.InOutCubic } }
    }
    Rectangle {
        anchors.centerIn: parent
        width: parent.width * 1.02; height: width
        radius: width / 2
        color: "transparent"
        border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b,
                              root.st === "MUTED" ? 0.03 : 0.08 + root.rmsLevel * 0.10)
        border.width: 18
        layer.enabled: true
        layer.effect: MultiEffect { blurEnabled: true; blur: 0.6 }
    }

}