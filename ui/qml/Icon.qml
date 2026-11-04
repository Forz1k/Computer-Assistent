// Иконки: только векторные Canvas-глифы (никаких растровых ассетов).
import "theme"
import QtQuick

Item {
    id: icon
    property string name: "mic"
    property color fg: Theme.textSecondary
    property real weight: 1.6
    implicitWidth: 20
    implicitHeight: 20

    Canvas {
        anchors.fill: parent
        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();
            var w = width, h = height;
            ctx.strokeStyle = icon.fg.toString();
            ctx.fillStyle = icon.fg.toString();
            ctx.lineWidth = icon.weight;
            ctx.lineCap = "round";
            ctx.lineJoin = "round";
            var cx = w / 2, cy = h / 2;

            switch (icon.name) {
            case "mic": {
                ctx.beginPath();
                ctx.roundRect(cx - 3, cy - 7, 6, 10, 3);
                ctx.stroke();
                ctx.beginPath();
                ctx.arc(cx, cy + 1, 6.5, 0.15 * Math.PI, 0.85 * Math.PI);
                ctx.stroke();
                ctx.beginPath();
                ctx.moveTo(cx, cy + 7.5); ctx.lineTo(cx, cy + 9.5); ctx.stroke();
                break;
            }
            case "mic-off": {
                ctx.globalAlpha = 0.9;
                ctx.beginPath();
                ctx.roundRect(cx - 3, cy - 7, 6, 10, 3); ctx.stroke();
                ctx.beginPath();
                ctx.moveTo(cx - 8, cy - 8); ctx.lineTo(cx + 8, cy + 9); ctx.stroke();
                break;
            }
            case "send": {
                ctx.beginPath();
                ctx.moveTo(cx - 8, cy); ctx.lineTo(cx + 8, cy - 6);
                ctx.lineTo(cx + 2, cy + 7); ctx.lineTo(cx, cy + 1);
                ctx.closePath(); ctx.stroke();
                break;
            }
            case "stop": {
                ctx.beginPath(); ctx.rect(cx - 5, cy - 5, 10, 10); ctx.fill();
                break;
            }
            case "settings": {
                ctx.beginPath(); ctx.arc(cx, cy, 3, 0, 2 * Math.PI); ctx.stroke();
                for (var i = 0; i < 8; i++) {
                    var a = i * Math.PI / 4;
                    ctx.beginPath();
                    ctx.moveTo(cx + Math.cos(a) * 5.5, cy + Math.sin(a) * 5.5);
                    ctx.lineTo(cx + Math.cos(a) * 8, cy + Math.sin(a) * 8);
                    ctx.stroke();
                }
                break;
            }
            case "shield": {
                ctx.beginPath();
                ctx.moveTo(cx, cy - 8);
                ctx.lineTo(cx + 7, cy - 5); ctx.lineTo(cx + 7, cy + 2);
                ctx.quadraticCurveTo(cx + 7, cy + 7, cx, cy + 9);
                ctx.quadraticCurveTo(cx - 7, cy + 7, cx - 7, cy + 2);
                ctx.lineTo(cx - 7, cy - 5); ctx.closePath(); ctx.stroke();
                break;
            }
            case "close": {
                ctx.beginPath();
                ctx.moveTo(cx - 6, cy - 6); ctx.lineTo(cx + 6, cy + 6);
                ctx.moveTo(cx + 6, cy - 6); ctx.lineTo(cx - 6, cy + 6);
                ctx.stroke();
                break;
            }
            case "minimize": {
                ctx.beginPath(); ctx.moveTo(cx - 6, cy + 4); ctx.lineTo(cx + 6, cy + 4); ctx.stroke();
                break;
            }
            case "copy": {
                ctx.beginPath(); ctx.rect(cx - 7, cy - 7, 9, 9); ctx.stroke();
                ctx.beginPath(); ctx.rect(cx - 3, cy - 3, 9, 9); ctx.stroke();
                break;
            }
            case "search": {
                ctx.beginPath(); ctx.arc(cx - 1.5, cy - 1.5, 5.5, 0, 2 * Math.PI); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(cx + 3, cy + 3); ctx.lineTo(cx + 7.5, cy + 7.5); ctx.stroke();
                break;
            }
            case "chevron-down": {
                ctx.beginPath();
                ctx.moveTo(cx - 5, cy - 2.5); ctx.lineTo(cx, cy + 2.5); ctx.lineTo(cx + 5, cy - 2.5);
                ctx.stroke();
                break;
            }
            case "check": {
                ctx.beginPath();
                ctx.moveTo(cx - 6, cy); ctx.lineTo(cx - 1.5, cy + 5); ctx.lineTo(cx + 7, cy - 5);
                ctx.stroke();
                break;
            }
            case "bolt": {
                ctx.beginPath();
                ctx.moveTo(cx + 1, cy - 8); ctx.lineTo(cx - 6, cy + 1); ctx.lineTo(cx - 1, cy + 1);
                ctx.lineTo(cx - 2, cy + 8); ctx.lineTo(cx + 6, cy - 2); ctx.lineTo(cx + 1, cy - 2);
                ctx.closePath(); ctx.stroke();
                break;
            }
            case "dot-ok":  { ctx.beginPath(); ctx.arc(cx, cy, 3.5, 0, 2 * Math.PI); ctx.fill(); break; }
            default: {
                ctx.beginPath(); ctx.arc(cx, cy, 6, 0, 2 * Math.PI); ctx.stroke();
            }
            }
        }
    }
    onNameChanged: requestPaint()
    function requestPaint() { children[0].requestPaint(); }
}
