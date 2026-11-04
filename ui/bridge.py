"""QObject-мосты между Python-бэком и QML. В QML — только визуальная логика.

Bridge публикует Property/Signal/Slot; QML ничего не знает про Vosk/Piper/Ollama.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import (Property, QObject, QTimer, QUrl, Signal, Slot)

from core.state_machine import AppState


class ThemeBridge(QObject):
    themeChanged = Signal()

    def __init__(self, themes_dir: Path, current: str = "reactor_cyan", parent=None) -> None:
        super().__init__(parent)
        self._dir = themes_dir
        self._name = current
        self._data: dict[str, Any] = {}
        self.load(current)

    def load(self, name: str) -> None:
        p = self._dir / f"{name}.json"
        if not p.is_file():
            p = self._dir / "reactor_cyan.json"
        self._name = p.stem
        try:
            self._data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._data = {"colors": {}, "glow": {"radius": 32, "opacity": 0.2},
                          "radii": {"s": 12, "m": 18, "l": 28}, "particle_count": 60,
                          "plasma_enabled": False, "font_family": "sans-serif",
                          "font_mono": "monospace"}
        self.themeChanged.emit()

    @Property(str, notify=themeChanged)
    def name(self) -> str:
        return self._name

    @Property("QVariantMap", notify=themeChanged)
    def colors(self) -> dict[str, Any]:
        return self._data.get("colors", {})

    @Property("QVariantMap", notify=themeChanged)
    def glow(self) -> dict[str, Any]:
        return self._data.get("glow", {})

    @Property("QVariantMap", notify=themeChanged)
    def radii(self) -> dict[str, Any]:
        return self._data.get("radii", {"s": 12, "m": 18, "l": 28})

    @Property(str, notify=themeChanged)
    def fontFamily(self) -> str:
        return self._data.get("font_family", "sans-serif")

    @Property(str, notify=themeChanged)
    def fontMono(self) -> str:
        return self._data.get("font_mono", "monospace")

    @Property(int, notify=themeChanged)
    def particleCount(self) -> int:
        return int(self._data.get("particle_count", 60))

    @Property(bool, notify=themeChanged)
    def plasmaEnabled(self) -> bool:
        return bool(self._data.get("plasma_enabled", True))

    @Slot(str, result="QVariantList")
    def listThemes(self, _dir_marker: str = "") -> list[str]:
        return sorted(p.stem for p in self._dir.glob("*.json"))


class ChatModel(QObject):
    """Лента диалога для QML (ListModel на стероидах — проще через QVariantList)."""

    messagesChanged = Signal()
    streamChunk = Signal(int, str)      # index, appended text (без пересоздания layout)
    streamEnd = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._msgs: list[dict[str, Any]] = []
        self._seq = 0

    @Property("QVariantList", notify=messagesChanged)
    def messages(self) -> list[dict[str, Any]]:
        return list(self._msgs)

    def add(self, role: str, content: str, meta: dict | None = None, demo: bool = False) -> int:
        self._seq += 1
        self._msgs.append({
            "id": self._seq, "role": role, "content": content,
            "time": time.strftime("%H:%M"),
            "meta": meta or {}, "demo": demo, "streaming": False,
        })
        self.messagesChanged.emit()
        return self._seq

    def begin_stream(self, demo: bool = False) -> int:
        idx = self.add("assistant", "", {"ttft_ms": None, "tps": None}, demo=demo) - 1
        self._msgs[idx]["streaming"] = True
        return idx

    def append_chunk(self, idx: int, chunk: str) -> None:
        if 0 <= idx < len(self._msgs):
            self._msgs[idx]["content"] += chunk
            self.streamChunk.emit(idx, chunk)

    def end_stream(self, idx: int, meta: dict | None = None) -> None:
        if 0 <= idx < len(self._msgs):
            self._msgs[idx]["streaming"] = False
            if meta:
                self._msgs[idx]["meta"] = meta
            self.streamEnd.emit(idx)
            self.messagesChanged.emit()

    @Slot(result="QVariantList")
    def getMessages(self) -> list[dict[str, Any]]:
        return list(self._msgs)


class CoreBridge(QObject):
    """Витрина ядра для QML: состояние, уровни, управление."""

    stateChanged = Signal(str)
    levelsChanged = Signal()
    interimChanged = Signal(str)
    busyChanged = Signal()
    settingsChanged = Signal()
    confirmChanged = Signal()
    toast = Signal(str, str)             # текст, уровень info|warn|error
    miniToggled = Signal(bool)
    bootStatusesChanged = Signal()
    geometrySaved = Signal(int, int, int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._state = AppState.BOOT.value
        self._rms = 0.0
        self._spectrum = [0.0] * 64
        self._interim = ""
        self.demo_mode = False
        self.mic_ok = True
        self.tts_ok = True
        self._confirm: dict[str, Any] = {}
        self._settings: dict[str, Any] = {}
        self._busy = False
        self._mini = False
        self._fps = 0.0
        self._frames = 0
        self._t0 = time.monotonic()
        self._net_mode = "offline"
        self._reduced_motion = False
        self._model_name = ""
        self._ttft = None
        self._boot_statuses: list[dict[str, Any]] = []
        # единый драйвер FPS-метрик (не по таймеру на элемент)
        self._fps_timer = QTimer(self)
        self._fps_timer.setInterval(1000)
        self._fps_timer.timeout.connect(self._fps_tick)
        self._fps_timer.start()

    # ---- свойства ----
    @Property(str, notify=stateChanged)
    def state(self) -> str:
        return self._state

    @Property(float, notify=levelsChanged)
    def rms(self) -> float:
        return self._rms

    @Property("QVariantList", notify=levelsChanged)
    def spectrum(self) -> list[float]:
        return self._spectrum

    @Property(str, notify=interimChanged)
    def interimText(self) -> str:
        return self._interim

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Property(bool, notify=busyChanged)
    def micAvailable(self) -> bool:
        return self.mic_ok

    @Property(bool, notify=busyChanged)
    def ttsAvailable(self) -> bool:
        return self.tts_ok

    @Property(bool, notify=settingsChanged)
    def demoMode(self) -> bool:
        return self.demo_mode

    @Property("QVariantMap", notify=confirmChanged)
    def pendingConfirm(self) -> dict[str, Any]:
        return self._confirm

    @Property("QVariantMap", notify=settingsChanged)
    def statusInfo(self) -> dict[str, Any]:
        return {"network": self._net_mode, "model": self._model_name,
                "fps": round(self._fps, 1), "ttft_ms": self._ttft,
                "mini": self._mini}

    @Property(str, notify=settingsChanged)
    def settingsJson(self) -> str:
        return json.dumps(self._settings, ensure_ascii=False)

    @Property("QVariantMap", notify=settingsChanged)
    def settingsObj(self) -> dict[str, Any]:
        return self._settings

    @Property("QVariantList", notify=bootStatusesChanged)
    def bootStatuses(self) -> list[dict[str, Any]]:
        return self._boot_statuses

    def set_boot_statuses(self, statuses: list[dict[str, Any]]) -> None:
        self._boot_statuses = statuses
        self.bootStatusesChanged.emit()

    @Slot(result="QVariantMap")
    def windowGeometry(self) -> dict[str, int]:
        g = self._settings.get("window", {}) or {}
        return {"x": int(g.get("x", -1)), "y": int(g.get("y", -1)),
                "w": int(g.get("w", 0)), "h": int(g.get("h", 0))}

    @Slot(int, int, int, int)
    def saveWindowGeometry(self, x: int, y: int, w: int, h: int) -> None:
        self.geometrySaved.emit(x, y, w, h)

    # ---- входящие от оркестратора ----
    def set_state(self, s: str) -> None:
        if s != self._state:
            self._state = s
            self.stateChanged.emit(s)

    def push_levels(self, rms: float, spec: list[float]) -> None:
        self._rms = rms
        self._spectrum = spec
        self._frames += 1
        self.levelsChanged.emit()

    def set_interim(self, text: str) -> None:
        if text != self._interim:
            self._interim = text
            self.interimChanged.emit(text)

    def set_busy(self, b: bool) -> None:
        if b != self._busy:
            self._busy = b
            self.busyChanged.emit()

    def set_status(self, network: str = "", model: str = "", ttft_ms=None) -> None:
        if network:
            self._net_mode = network
        if model:
            self._model_name = model
        if ttft_ms is not None:
            self._ttft = ttft_ms
        self.settingsChanged.emit()

    def set_settings(self, data: dict[str, Any]) -> None:
        self._settings = data
        self.settingsChanged.emit()

    def request_confirm(self, payload: dict[str, Any]) -> None:
        self._confirm = payload
        self.confirmChanged.emit()

    def _fps_tick(self) -> None:
        now = time.monotonic()
        dt = now - self._t0
        if dt > 0:
            self._fps = self._frames / dt
        self._frames = 0
        self._t0 = now
        self.settingsChanged.emit()  # обновляем statusInfo.fps раз в секунду

    # ---- исходящие слоты (из QML) ----
    sendTextRequested = Signal(str)
    stopRequested = Signal()
    pttPressed = Signal()
    pttReleased = Signal()
    muteToggled = Signal(bool)
    settingChanged = Signal(str, str)     # dotted key, JSON value
    confirmAnswered = Signal(str, bool)   # request_id, accepted
    themeSelected = Signal(str)
    networkModeSet = Signal(str)
    diagnosticsRequested = Signal()
    copyReportRequested = Signal()
    paletteCommand = Signal(str)
    reportTextRequested = Signal()
    reportReady = Signal(str)

    @Slot(str)
    def sendText(self, text: str) -> None:
        t = text.strip()
        if t:
            self.sendTextRequested.emit(t)

    @Slot()
    def stop(self) -> None:
        self.stopRequested.emit()

    @Slot()
    def pttDown(self) -> None:
        self.pttPressed.emit()

    @Slot()
    def pttUp(self) -> None:
        self.pttReleased.emit()

    @Slot(bool)
    def setMuted(self, muted: bool) -> None:
        self.muteToggled.emit(muted)

    @Slot(str, str)
    def setSetting(self, key: str, json_value: str) -> None:
        try:
            val = json.loads(json_value)
        except json.JSONDecodeError:
            val = json_value
        self.settingChanged.emit(key, json.dumps(val, ensure_ascii=False))

    @Slot(str, bool)
    def answerConfirm(self, request_id: str, accepted: bool) -> None:
        self._confirm = {}
        self.confirmChanged.emit()
        self.confirmAnswered.emit(request_id, accepted)

    @Slot(str)
    def selectTheme(self, name: str) -> None:
        self.themeSelected.emit(name)

    @Slot(str)
    def setNetworkMode(self, mode: str) -> None:
        self.networkModeSet.emit(mode)

    @Slot()
    def openDiagnostics(self) -> None:
        self.diagnosticsRequested.emit()

    reportCopied = Signal(str)

    @Slot(str)
    def copyReport(self, text: str) -> None:
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(text)
        self.toast.emit("Отчёт скопирован в буфер обмена", "info")

    @Slot(str)
    def runPaletteCommand(self, cmd: str) -> None:
        self.paletteCommand.emit(cmd)

    @Slot()
    def requestReport(self) -> None:
        self.reportTextRequested.emit()

    @Property(bool, notify=settingsChanged)
    def reducedMotion(self) -> bool:
        return self._reduced_motion

    @reducedMotion.setter  # type: ignore[attr-defined]
    def reducedMotion(self, v: bool) -> None:  # noqa: N802
        self._reduced_motion = bool(v)
        self.settingsChanged.emit()

    @Slot(result=bool)
    def toggleMini(self) -> bool:
        self._mini = not self._mini
        self.miniToggled.emit(self._mini)
        return self._mini

    @Slot(str, result="QVariantList")
    def fuzzySearch(self, query: str) -> list[dict[str, str]]:
        """Command palette: команды/настройки/история. Простейший fuzzy."""
        q = query.lower().strip()
        items = [
            {"label": "Стоп (отмена всего)", "cmd": "стоп"},
            {"label": "Открыть браузер", "cmd": "открой браузер"},
            {"label": "Системная информация", "cmd": "статус системы"},
            {"label": "Который час", "cmd": "который час"},
            {"label": "Тема: Reactor Cyan", "cmd": "theme:reactor_cyan"},
            {"label": "Тема: Amber Protocol", "cmd": "theme:amber_protocol"},
            {"label": "Тема: Nightfall Mono", "cmd": "theme:nightfall_mono"},
            {"label": "Режим: OFFLINE", "cmd": "net:offline"},
            {"label": "Режим: HYBRID", "cmd": "net:hybrid"},
            {"label": "Диагностика", "cmd": "diag"},
            {"label": "Мини-режим", "cmd": "mini"},
        ]
        if not q:
            return items
        out = []
        for it in items:
            lab = it["label"].lower()
            score = sum(1 for ch in q if ch in lab)
            if q in lab or score >= len(q):
                out.append(it)
        return out


def qml_url(ui_dir: Path) -> QUrl:
    return QUrl.fromLocalFile(str(ui_dir / "qml" / "Main.qml"))
