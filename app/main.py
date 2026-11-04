"""Composition root: сборка приложения, wire-up мостов, boot-проверки, shutdown.

Запуск: python -m app.main [--demo]
Все тяжёлые/сетевые проверки — вне GUI-потока (QThread BootWorker).
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, Qt, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtQml import QQmlApplicationEngine

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None

from audio.engine import AudioLevels            # noqa: E402
from config.settings import Settings, app_data_dir, redact_secrets  # noqa: E402
from core.events import EventBus, Orchestrator  # noqa: E402
from core.personas import get_persona           # noqa: E402
from core.router import route                   # noqa: E402
from core.state_machine import AppState         # noqa: E402
from diagnostics.checks import run_all          # noqa: E402
from llm.ollama_client import OllamaClient      # noqa: E402
from memory.store import Database               # noqa: E402
from network.gateway import NetworkGateway      # noqa: E402
from tools.registry import ToolRegistry         # noqa: E402
from tts.piper_engine import DummyEngine, PiperEngine, read_wav_mono  # noqa: E402
from tts.player import SpeechQueue              # noqa: E402
from tts.text_clean import clean_for_tts, split_sentences  # noqa: E402
from llm.worker import LLMWorker  # noqa: E402
from ui.bridge import ChatModel, CoreBridge, ThemeBridge, qml_url  # noqa: E402


class SoundPlayer(QObject):
    """UI-блипы (локально сгенерированные wav) через Qt Multimedia. 25% по умолчанию."""

    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self._players: dict[str, tuple[QMediaPlayer, QAudioOutput]] = {}
        for name in ("wake", "confirm", "error", "tick", "stop"):
            f = ROOT / "assets" / "sounds" / f"{name}.wav"
            if not f.is_file():
                continue
            player = QMediaPlayer()
            out = QAudioOutput(player)
            player.setSource(QUrl.fromLocalFile(str(f)))
            player.setAudioOutput(out)
            self._players[name] = (player, out)

    @Slot(str)
    def play(self, name: str) -> None:
        if not self.settings.get("sounds.enabled", True):
            return
        p = self._players.get(name)
        if not p:
            return
        player, out = p
        try:
            out.setVolume(float(self.settings.get("sounds.volume", 0.25)))
            player.stop()
            player.play()
        except Exception:
            pass


class _RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact_secrets(str(record.msg))
        except Exception:
            pass
        return True


def setup_logging() -> Path:
    home = app_data_dir()
    home.mkdir(parents=True, exist_ok=True)
    logf = home / "app.log"
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    h = RotatingFileHandler(logf, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    h.addFilter(_RedactFilter())
    root.addHandler(h)
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    sh.addFilter(_RedactFilter())
    root.addHandler(sh)
    return logf


class BootWorker(QThread):
    """Реальные проверки компонентов вне GUI-потока."""
    done = Signal(list)   # list[dict]

    def __init__(self, settings: Settings, gateway: NetworkGateway, parent=None) -> None:
        super().__init__(parent)
        self.s = settings
        self.gw = gateway

    def run(self) -> None:
        flat = {
            "ollama.base_url": self.s.get("ollama.base_url"),
            "stt.model_path": self.s.get("stt.model_path", ""),
            "voice.piper_bin": self.s.get("voice.piper_bin"),
            "voice.piper_model": self.s.get("voice.piper_model"),
            "workspace.root": self.s.get("workspace.root"),
            "network_mode": self.s.get("network_mode"),
        }
        try:
            statuses = run_all(flat, self.gw)
            self.done.emit([st.as_dict() for st in statuses])
        except Exception as e:
            logging.exception("boot failed")
            self.done.emit([{"name": "Boot", "status": "fail", "detail": str(e), "action": ""}])


class DemoDriver(QObject):
    """--demo: синтетический аудио + фейковый поток токенов. Бейдж DEMO обязателен."""
    tokenReady = Signal(str)
    finished = Signal(dict)

    def __init__(self, bridge: CoreBridge, chat: ChatModel, levels: AudioLevels, parent=None) -> None:
        super().__init__(parent)
        self.bridge = bridge
        self.chat = chat
        self.levels = levels
        self._idx = 0
        self._tokens: list[str] = []
        self._pos = 0
        self._timer = QTimer(self)
        self._timer.setInterval(70)
        self._timer.timeout.connect(self._tick)
        self._audio_timer = QTimer(self)
        self._audio_timer.setInterval(50)
        self._audio_timer.timeout.connect(self._feed_audio)
        self._audio_iter = None
        self.running = False
        self._cancel = False

    def start(self) -> None:
        from core.demo import demo_audio_loop, demo_token_stream, DEMO_CONVERSATION
        self._loop = demo_audio_loop()
        self._lp = 0
        self._audio_timer.start()
        self.running = True
        self.ask(DEMO_CONVERSATION[0]["user"])

    def _feed_audio(self) -> None:
        import numpy as np
        step = 800
        chunk = self._loop[self._lp:self._lp + step]
        self._lp = (self._lp + step) % len(self._loop)
        if len(chunk):
            self.levels.feed(chunk.astype(np.float32))

    def ask(self, user_text: str) -> None:
        from core.demo import DEMO_CONVERSATION, demo_token_stream
        self.chat.add("user", user_text, demo=True)
        self._tokens = list(demo_token_stream(self._idx))
        self._pos = 0
        self._cancel = False
        self.bridge.set_state("THINKING")
        QTimer.singleShot(500, self._begin_stream)

    def _begin_stream(self) -> None:
        if self._cancel or not self.running:
            return
        self._msg_idx = self.chat.begin_stream(demo=True)
        self.bridge.set_state("STREAMING")
        self._timer.start()

    def _tick(self) -> None:
        from core.demo import demo_meta
        if self._cancel or self._pos >= len(self._tokens):
            self._timer.stop()
            if not self._cancel:
                meta = demo_meta(self._idx)
                self.chat.end_stream(self._msg_idx, meta)
                self.bridge.set_status(ttft_ms=meta["ttft_ms"], model="DEMO (не реальная модель)")
                self._idx += 1
                # цикл демо: следующий вопрос через паузу
                from core.demo import DEMO_CONVERSATION
                nxt = DEMO_CONVERSATION[self._idx % len(DEMO_CONVERSATION)]["user"]
                QTimer.singleShot(2500, lambda: self.running and self.ask(nxt))
            return
        self.chat.append_chunk(self._msg_idx, self._tokens[self._pos])
        self._pos += 1

    def stop(self) -> None:
        self._cancel = True
        self.running = False
        self._timer.stop()
        self._audio_timer.stop()


class Application(QObject):
    """Связывает все подсистемы; точка graceful shutdown."""

    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__()
        self.started_at = time.monotonic()
        self.logfile = setup_logging()
        self.log = logging.getLogger("app")
        self.args = args

        data_home = app_data_dir()
        self.settings = Settings.load()
        if args.demo:
            self.settings.data["demo_mode"] = True
        self.gateway = NetworkGateway(mode=self.settings.get("network_mode", "offline"))
        self.db = Database(data_home / "history.db")
        self.bus = EventBus()
        self.orch = Orchestrator(self.bus)
        self.tools = ToolRegistry(Path(self.settings.get("workspace.root")))
        self.ollama = OllamaClient(self.settings.get("ollama.base_url"), gateway=self.gateway)

        # ---- UI-мосты ----
        self.theme = ThemeBridge(ROOT / "themes", self.settings.get("theme", "reactor_cyan"))
        self.bridge = CoreBridge()
        self.chat = ChatModel()
        self.bridge.demo_mode = bool(args.demo)
        self.bridge.set_settings({k: v for k, v in self.settings.data.items() if k != "online"})
        self.bridge.set_status(network=self.gateway.mode)

        # ---- аудио ----
        self.levels = AudioLevels()
        self.levels.levelsReady.connect(self.bridge.push_levels)
        self.tts_engine = PiperEngine(self.settings.get("voice.piper_bin", ""),
                                      self.settings.get("voice.piper_model", ""))
        if not self.tts_engine.available():
            self.bridge.tts_ok = False
        voices = self.tts_engine.voices()
        self.voice = voices[0] if voices else None
        self.speech = SpeechQueue(
            self.tts_engine if self.voice else DummyEngine(),
            self.voice or DummyEngine().voices()[0],
            output_callback=self._play_samples)
        self.speech.speechStarted.connect(self._on_speech_start)
        self.speech.speechFinished.connect(self._on_speech_end)
        self.speech.synthError.connect(lambda m: self.bridge.toast.emit(m, "warn"))
        self._out_stream = None
        self._pending_playback: list = []

        # ---- STT (ленивый запуск; без железа — мягко дизейблим) ----
        self.stt = None
        self._wake_cfg = None

        # ---- UI-блипы ----
        self.sounds = SoundPlayer(self.settings)

        # ---- LLM-воркер (singleton: одна тяжёлая генерация одновременно) ----
        self.llm_worker = LLMWorker(self.ollama, self.bus)
        self.llm_worker.token.connect(self._on_token)
        self.llm_worker.finished_ok.connect(self._on_llm_done)
        self.llm_worker.failed.connect(self._on_llm_fail)
        self._req_buf: dict[str, list] = {}   # req -> [idx, text]

        # ---- demo ----
        self.demo: DemoDriver | None = None
        if args.demo:
            self.demo = DemoDriver(self.bridge, self.chat, self.levels, self)

        # ---- wire-up моста <-> оркестратор ----
        self.bridge.sendTextRequested.connect(self.on_user_text)
        self.bridge.stopRequested.connect(self.on_stop)
        self.bridge.confirmAnswered.connect(self.on_confirm_answer)
        self.bridge.networkModeSet.connect(self._apply_net_mode)
        self.bridge.settingChanged.connect(self._apply_setting)
        self.bridge.diagnosticsRequested.connect(self.run_boot_checks)
        self.bridge.geometrySaved.connect(self._save_geometry)
        self.bridge.reducedMotion = bool(self.settings.get("reduced_motion", False))
        self.bridge.reportTextRequested.connect(self._provide_report)
        self.bridge.paletteCommand.connect(self._on_palette_cmd)
        self.bridge.muteToggled.connect(self._on_mute)
        self.bridge.pttPressed.connect(self._on_ptt_down)
        self.bridge.pttReleased.connect(self._on_ptt_up)
        self.bridge.themeSelected.connect(self._apply_theme)
        self.bridge.themeSelected.connect(lambda n: self.sounds.play("tick"))
        self.bus.error.connect(lambda m: self.bridge.toast.emit(m, "error"))
        self.bus.stateChanged.connect(self._on_state_sound)

        self._pending_tool: dict = {}

        # ---- окно ----
        self.engine = QQmlApplicationEngine()
        ctx = self.engine.rootContext()
        ctx.setContextProperty("core", self.bridge)
        ctx.setContextProperty("theme", self.theme)
        ctx.setContextProperty("chatModel", self.chat)
        ctx.setContextProperty("appVersion", "0.9.0")
        self.engine.quit.connect(QCoreApplication.instance().quit)
        self.engine.load(qml_url(ROOT / "ui"))
        if not self.engine.rootObjects():
            raise RuntimeError("QML не загрузился — см. лог")
        self.window = self.engine.rootObjects()[0]

        # ---- boot-проверки по факту запуска окна ----
        self.boot_worker = BootWorker(self.settings, self.gateway)
        self.boot_worker.done.connect(self._on_boot_done)
        QTimer.singleShot(150, self.boot_worker.start)
        self.levels.start()

        # глобальная горячая клавиша PTT (Windows: RegisterHotKey; иначе — кнопка UI)
        self.hotkey = None
        if sys.platform == "win32" and not args.demo:
            from ui.hotkeys import WinHotkey
            self.hotkey = WinHotkey(self.window.winId(), self.bridge.pttDown, self.bridge.pttUp)
            self.hotkey.register_default()

        QGuiApplication.instance().aboutToQuit.connect(self.shutdown)

    # =================== обработка пользовательского текста ===================
    @Slot(str)
    def on_user_text(self, text: str) -> None:
        req = self.orch.new_request()
        self.db.add_message("user", text)
        self.chat.add("user", text, demo=self.bridge.demo_mode)
        r = route(text)
        if r.handled:
            if r.direct_reply:
                self._deliver(req, r.direct_reply)
            elif r.tool:
                res = self.tools.execute(r.tool, r.args or {}, confirmed=not r.needs_confirmation,
                                         request_id=req)
                if res.get("status") == "needs_confirmation":
                    self._pending_tool = {"req": req, "tool": r.tool, "args": r.args}
                    self.sounds.play("confirm")
                    self.bridge.request_confirm({"request_id": req, "tool": r.tool,
                                                 "title": self.tools.spec(r.tool).title,
                                                 "args": res.get("args", {}),
                                                 "risk": res.get("risk", "low")})
                    self.db.log_audit(req, "user", r.tool, r.args or {}, "awaiting", False)
                else:
                    self._deliver(req, self._tool_summary(res))
            return
        if self.bridge.demo_mode and self.demo:
            self.demo.ask(text)
            return
        self._ask_llm(req, text)

    def _ask_llm(self, req: str, text: str) -> None:
        model = self.settings.get("ollama.model", "")
        if not model:
            models = []
            try:
                models = self.ollama.list_models()
            except Exception:
                pass
            if not models:
                self.orch.set_state(AppState.ERROR, "no-model")
                self._deliver(req, "Локальная модель не выбрана и Ollama недоступен. "
                                   "Открой диагностику (иконка щита внизу) — там инструкция.")
                return
            model = models[0]
            self.settings.set("ollama.model", model)
        persona = get_persona(self.settings.get("persona", "computer"))
        self.bridge.set_busy(True)
        self.orch.set_state(AppState.THINKING, "llm-request")
        self._req_buf[req] = [-1, ""]   # [stream_idx, accumulated text]
        self.llm_worker.submit(req, text, persona["system_prompt"], model,
                               int(self.settings.get("ollama.num_ctx", 4096)))

    @Slot(str, str)
    def _on_token(self, req: str, chunk: str) -> None:
        buf = self._req_buf.get(req)
        if buf is None or self.orch.cancelled():
            return
        if buf[0] < 0:
            buf[0] = self.chat.begin_stream(demo=False)
            self.orch.set_state(AppState.STREAMING, "first-token")
        buf[1] += chunk
        self.chat.append_chunk(buf[0], chunk)
        # стриминг речи по предложениям: как только накопилось законченное предложение
        while len(buf) < 3:
            buf.append(0)
        idx, cut, b = buf[2], -1, buf[1]
        for mark in (". ", "! ", "? ", "… "):
            p = b.rfind(mark)
            if p >= 0 and p + 2 > cut:
                cut = p + 2
        if cut > idx:
            seg = b[idx:cut]
            buf[2] = cut
            cleaned = clean_for_tts(seg)
            if cleaned:
                for s in split_sentences(cleaned):
                    self._speak(s)

    @Slot(str, dict)
    def _on_llm_done(self, req: str, meta: dict) -> None:
        self.bridge.set_busy(False)
        buf = self._req_buf.pop(req, None)
        if buf is None:
            return
        text = buf[1]
        spoken_upto = buf[2] if len(buf) > 2 else 0
        tail = text[spoken_upto:]
        if tail.strip():
            cleaned = clean_for_tts(tail)
            for s in split_sentences(cleaned):
                self._speak(s)
        if buf[0] >= 0:
            self.chat.end_stream(buf[0], meta)
            if text:
                self.db.add_message("assistant", text, meta)
        ttft = meta.get("ttft_ms")
        if ttft is not None:
            self.bridge.set_status(ttft_ms=ttft)
        if not meta.get("cancelled"):
            self.orch.set_state(AppState.SPEAKING if self._will_speak() else AppState.IDLE, "gen-done")

    @Slot(str, str)
    def _on_llm_fail(self, req: str, msg: str) -> None:
        self.bridge.set_busy(False)
        self.orch.set_state(AppState.ERROR, "llm-fail")
        buf = self._req_buf.pop(req, None)
        if buf and buf[0] >= 0:
            self.chat.end_stream(buf[0])
        self.sounds.play("error")
        self.bridge.toast.emit(msg, "error")
        QTimer.singleShot(1200, lambda: self.orch.set_state(AppState.IDLE, "recover"))

    def _will_speak(self) -> bool:
        return bool(self.settings.get("voice.enabled", True) and (self.voice or self.bridge.demo_mode))

    def _deliver(self, req: str, text: str) -> None:
        idx = self.chat.add("assistant", text, demo=self.bridge.demo_mode)
        self.db.add_message("assistant", text)
        cleaned = clean_for_tts(text)
        for s in split_sentences(cleaned):
            self._speak(s)

    def _tool_summary(self, res: dict) -> str:
        st = res.get("status")
        if st == "ok":
            t = res.get("tool", "")
            if t == "system_info":
                info = res.get("info", {})
                return ("Система: {os}, Python {python}, CPU ядер {cpu_count}, "
                        "RAM {ram_total_gb} ГБ (занято {ram_used_pct}%)").format(**info)
            return f"Готово: {t} → {res.get('opened') or res.get('created') or res.get('written') or 'ok'}"
        return f"Не выполнено: {res.get('message', st)}"

    # ================= подтверждения =================
    @Slot(str, bool)
    def on_confirm_answer(self, req: str, accepted: bool) -> None:
        p = self._pending_tool
        self._pending_tool = {}
        if not p:
            return
        if accepted:
            res = self.tools.execute(p["tool"], p["args"], confirmed=True, request_id=req)
            self.db.log_audit(req, "user", p["tool"], p["args"], res.get("status", "?"), True)
            self._deliver(req, self._tool_summary(res))
        else:
            self.db.log_audit(req, "user", p["tool"], p["args"], "rejected", False)
            self._deliver(req, "Действие отклонено.")

    # ================= речь =================
    def _speak(self, sentence: str) -> None:
        if not self.settings.get("voice.enabled", True):
            return
        self.speech.enqueue(sentence)

    @Slot()
    def _on_speech_start(self) -> None:
        self.orch.set_state(AppState.SPEAKING, "tts-start")
        if self.stt:
            self.stt.set_paused(True)   # честная «пауза микрофона» (half-duplex)

    @Slot(bool)
    def _on_speech_end(self, completed: bool) -> None:
        if self.stt:
            self.stt.set_paused(False)
        if self.orch.sm.state == AppState.SPEAKING:
            self.orch.set_state(AppState.IDLE, "tts-end")

    def _play_samples(self, samples, sr: int) -> None:
        """Вывод в устройство; без устройств — тихо дропаем (UI предупреждён)."""
        try:
            import sounddevice as sd
            if self._out_stream is None:
                if not sd.query_devices():
                    raise RuntimeError("no devices")
                dev = self.settings.get("audio.output_device")
                self._out_stream = sd.OutputStream(samplerate=sr, channels=1,
                                                   dtype="float32", device=dev)
                self._out_stream.start()
            self._out_stream.write(samples.reshape(-1, 1))
        except Exception:
            pass  # воспроизведение недоступно — уже отражено в диагностике

    # ================= misc =================
    @Slot()
    def on_stop(self) -> None:
        self.orch.cancel()
        self.speech.stop()
        if self.demo:
            self.demo.stop()
        if self.llm_worker.isRunning():
            self.llm_worker.stop()
        self.bridge.set_interim("")
        self.bridge.set_busy(False)
        self.bridge.toast.emit("Остановлено", "info")

    # ================= голосовые состояния / палитра / звук =================
    def _on_state_sound(self, new_state: str, reason: str) -> None:
        self.bridge.set_state(new_state)
        if new_state == "WAKE":
            self.sounds.play("wake")
        elif new_state == "ERROR" and reason != "llm-fail":
            self.sounds.play("error")

    def _on_mute(self, muted: bool) -> None:
        self.settings.set("voice.muted", muted)
        if muted:
            self.orch.set_state(AppState.MUTED, "user-mute")
            self.speech.stop()
            if self.stt:
                self.stt.set_paused(True)
        else:
            if self.orch.sm.state == AppState.MUTED:
                self.orch.set_state(AppState.IDLE, "unmute")
            if self.stt:
                self.stt.set_paused(False)

    def _on_ptt_down(self) -> None:
        if not self.bridge.micAvailable or self.bridge.demo_mode:
            return
        self._ptt_prev = self.orch.sm.state
        self.orch.set_state(AppState.LISTENING, "ptt")
        self._ensure_stt()
        if self.stt:
            self.stt.set_paused(False)

    def _on_ptt_up(self) -> None:
        if self.bridge.demo_mode:
            return
        if self.stt:
            text = self.stt.flush_final() if hasattr(self.stt, "flush_final") else ""
            if text:
                self.on_user_text(text)
            self.orch.set_state(AppState.THINKING if self.bridge.busy else AppState.IDLE, "ptt-end")

    def _ensure_stt(self) -> None:
        """Ленивый запуск Vosk-потока; без модели/микрофона — мягкий дизейбл."""
        if self.stt is not None or self.bridge.demo_mode:
            return
        model_path = self.settings.get("stt.model_path") or self.settings.get("wake.model_path", "")
        if not model_path:
            self.bridge.toast.emit("Модель Vosk не настроена — голосовой ввод недоступен (текстовый чат работает).", "warn")
            self.bridge.mic_ok = False
            return
        try:
            from stt.vosk_engine import VoskTranscriber
            self.stt = VoskTranscriber(model_path, device=self.settings.get("audio.input_device"))
            self.stt.interimText.connect(self.bridge.set_interim)
            self.stt.finalText.connect(self._on_stt_final)
            self.stt.errorOccurred.connect(lambda m: (self.bridge.toast.emit(m, "warn"),
                                                       setattr(self.bridge, "mic_ok", False)))
            self.stt.start()
        except Exception as e:
            self.bridge.toast.emit(f"Микрофон/STT недоступны: {e}", "warn")
            self.bridge.mic_ok = False

    def _on_stt_final(self, text: str) -> None:
        from wake.detector import WakeConfig, detect_wake
        self.bridge.set_interim("")
        cfg = WakeConfig(word=self.settings.get("wake.word", "компьютер"),
                         aliases=list(self.settings.get("wake.aliases", ["джарвис"])),
                         strictness=self.settings.get("wake.strictness", "medium"))
        st = self.orch.sm.state
        if st == AppState.LISTENING:
            self.on_user_text(text)
            return
        found, rest = detect_wake(text, cfg)
        if found:
            self.orch.set_state(AppState.WAKE, "wake-word")
            QTimer.singleShot(260, lambda: self.orch.set_state(AppState.LISTENING, "wake-ok"))
            if rest.strip():
                QTimer.singleShot(300, lambda: self.on_user_text(rest.strip()))

    def _on_palette_cmd(self, cmd: str) -> None:
        if cmd.startswith("theme:"):
            self._apply_theme(cmd.split(":", 1)[1])
        elif cmd.startswith("net:"):
            self._apply_net_mode(cmd.split(":", 1)[1])
        elif cmd == "diag":
            self.bridge.diagnosticsRequested.emit()
        elif cmd == "mini":
            self.bridge.toggleMini()
        else:
            self.on_user_text(cmd)

    def _provide_report(self) -> None:
        self.bridge.reportReady.emit(self.diagnostics_report())

    @Slot(str)
    def _apply_theme(self, name: str) -> None:
        self.theme.load(name)
        self.settings.set("theme", name)

    @Slot(str)
    def _apply_net_mode(self, mode: str) -> None:
        try:
            self.gateway.set_mode(mode)
        except ValueError as e:
            self.bridge.toast.emit(str(e), "error")
            return
        self.settings.set("network_mode", mode)
        self.bridge.set_status(network=mode)
        self.bridge.toast.emit(f"Сетевой режим: {mode.upper()}", "info")

    @Slot(str, str)
    def _apply_setting(self, key: str, json_value: str) -> None:
        import json
        try:
            val = json.loads(json_value)
        except json.JSONDecodeError:
            val = json_value
        self.settings.set(key, val)
        if key == "voice.rate":
            self.speech.rate = float(val)
        elif key == "voice.volume":
            self.speech.volume = float(val)
        elif key == "reduced_motion":
            self.bridge.reducedMotion = bool(val)
        elif key == "ui_scale":
            self.bridge.set_status()  # триггер settingsChanged -> Theme.refresh()
        elif key == "persona":
            pass  # применяется при следующем запросе через get_persona

    @Slot()
    def run_boot_checks(self) -> None:
        if self.boot_worker.isRunning():
            return
        self.boot_worker.start()

    @Slot(int, int, int, int)
    def _save_geometry(self, x: int, y: int, w: int, h: int) -> None:
        if w > 0 and h > 0:
            self.settings.data["window"] = {"x": x, "y": y, "w": w, "h": h}
            self.settings.save()

    @Slot(list)
    def _on_boot_done(self, statuses: list) -> None:
        self._boot_statuses = statuses
        self.bridge.set_boot_statuses(statuses)
        for st in statuses:
            self.bus.bootComponent.emit(st["name"], st["status"])
        ollama_ok = any(s["name"] == "Ollama" and s["status"] == "ok" for s in statuses)
        if ollama_ok:
            try:
                models = self.ollama.list_models()
                if models and not self.settings.get("ollama.model"):
                    self.settings.set("ollama.model", models[0])
                self.bridge.set_status(model=self.settings.get("ollama.model", ""))
            except Exception:
                pass
        audio = next((s for s in statuses if s["name"] == "Аудио"), None)
        if audio and audio["status"] == "warn":
            self.bridge.mic_ok = False
            self.bridge.busyChanged.emit()
        piper = next((s for s in statuses if s["name"] == "Piper TTS"), None)
        if piper and piper["status"] in ("fail", "warn"):
            self.bridge.tts_ok = False
            self.bridge.busyChanged.emit()
        if not self.bridge.demo_mode:
            self.orch.set_state(AppState.IDLE, "boot-ok")
            if self.settings.get("wake.always_on", True):
                QTimer.singleShot(400, self._ensure_stt)
        else:
            self.orch.set_state(AppState.IDLE, "boot-demo")
            if self.demo:
                self.demo.start()
        self.log.info("boot finished in %.2fs", time.monotonic() - self.started_at)

    def diagnostics_report(self) -> str:
        from diagnostics.checks import ComponentStatus, report_text
        sts = [ComponentStatus(**{k: v for k, v in s.items() if k in ComponentStatus.__dataclass_fields__})
               for s in getattr(self, "_boot_statuses", [])]
        return report_text(sts)

    @Slot()
    def shutdown(self) -> None:
        self.log.info("shutdown begin")
        self.orch.cancel()
        self.speech.shutdown()
        self.levels.stop()
        if self.stt:
            self.stt.stop_stream()
        if self.llm_worker.isRunning():
            self.llm_worker.stop()
            self.llm_worker.wait(2000)
        if self._out_stream is not None:
            try:
                self._out_stream.stop()
                self._out_stream.close()
            except Exception:
                pass
        if self.hotkey:
            self.hotkey.unregister()
        self.db.close()
        self.log.info("shutdown complete")


class LLMGenWorker(QThread):
    """Обёртка над blocking-итератором Ollama: генерация вне GUI-потока."""
    token = Signal(str)
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, client: OllamaClient, model: str, prompt: str, system: str,
                 num_ctx: int, cancel) -> None:
        super().__init__()
        self.client, self.model = client, model
        self.prompt, self.system, self.num_ctx = prompt, system, num_ctx
        self._cancel = cancel
        self._stop = False

    def stop_gen(self) -> None:
        self._stop = True

    def run(self) -> None:
        from llm.ollama_client import OllamaUnavailable, OllamaError
        meta = {}
        try:
            got = False
            for chunk, stats in self.client.generate_stream(
                    self.model, self.prompt, self.system, self.num_ctx,
                    cancel_flag=lambda: self._stop or self._cancel()):
                got = True
                self.token.emit(chunk)
            meta = {"ttft_ms": round((stats.ttft_s or 0) * 1000),
                    "tps": stats.tokens_per_s, "tokens": stats.total_tokens,
                    "cancelled": self._stop or self._cancel()}
            self.finished_ok.emit(meta)
            if not got and not meta["cancelled"]:
                self.failed.emit("Модель вернула пустой ответ.")
        except OllamaUnavailable as e:
            self.failed.emit(str(e))
        except OllamaError as e:
            self.failed.emit(str(e))
        except Exception as e:
            self.failed.emit(f"Сбой генерации: {type(e).__name__}: {e}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="computer-assistant")
    ap.add_argument("--demo", action="store_true", help="демо-режим без микрофона и Ollama")
    ap.add_argument("--software", action="store_true", help="программный рендер (без GPU)")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    if args.software:
        import os
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
    QGuiApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    app = QGuiApplication(sys.argv[:1])
    app.setApplicationName("Computer Assistant")
    app.setOrganizationName("ComputerAssistant")
    try:
        Application(args)
    except Exception as e:
        logging.exception("fatal startup")
        from PySide6.QtWidgets import QMessageBox  # только для ошибки старта
        QMessageBox.critical(None, "Computer Assistant",
                             f"Не удалось запуститься:\n{e}\n\nПодробности в логе.")
        return 1
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
