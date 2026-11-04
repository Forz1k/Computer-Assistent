"""Очередь воспроизведения речи с отменой и дренажем, вне GUI-потока.

Half-duplex: во время SPEAKING захват микрофона приостанавливается (это честная
«пауза микрофона», а не эхоподавление). on_speech_started/on_speech_finished —
коллбэки в поток оркестратора через Qt-сигналы (wire-up делает app/main.py).
"""
from __future__ import annotations

import threading
from collections import deque
from typing import Callable, Optional

import numpy as np
from PySide6.QtCore import QObject, Signal

from tts.base import AudioChunk, TTSEngine, VoiceInfo


class SpeechQueue(QObject):
    speechStarted = Signal()
    speechFinished = Signal(bool)   # True — дослушано до конца, False — отменено
    synthError = Signal(str)
    chunkLevels = Signal(float, list)  # rms + spectrum для ядра (SPEAKING)

    def __init__(self, engine: TTSEngine, voice: VoiceInfo,
                 output_callback: Optional[Callable[[np.ndarray, int], None]] = None,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.engine = engine
        self.voice = voice
        self.output_callback = output_callback  # (samples, sr) -> в аудио-устройство
        self.rate = 1.0
        self.volume = 1.0
        self._texts: deque[str] = deque()
        self._cancel = threading.Event()
        self._wake = threading.Event()
        self._active = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    # ---------- API для оркестратора (вызывается из GUI-потока) ----------
    def enqueue(self, sentence: str) -> None:
        if not sentence.strip():
            return
        with self._lock:
            self._texts.append(sentence)
        self._wake.set()
        self._ensure_thread()

    def stop(self) -> None:
        """Мгновенный стоп: отменяем синтез и сбрасываем очередь."""
        self._cancel.set()
        with self._lock:
            self._texts.clear()

    def is_speaking(self) -> bool:
        return self._active

    def shutdown(self, timeout: float = 2.0) -> None:
        self.stop()
        t = self._thread
        if t is not None and t.is_alive():
            t.join(timeout)

    # ---------- рабочий поток ----------
    def _ensure_thread(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._cancel.clear()
        self._thread = threading.Thread(target=self._run, name="tts-playback", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        from audio.engine import rms as _rms, spectrum as _spec
        started = False
        cancelled_any = False
        while True:
            with self._lock:
                text = self._texts.popleft() if self._texts else None
            if text is None:
                # очередь пуста — ждём новую реплику или выходим
                if not self._wake.wait(0.25):
                    with self._lock:
                        empty = not self._texts
                    if empty:
                        break
                    continue
                self._wake.clear()
                continue
            if self._cancel.is_set():
                cancelled_any = True
                break
            try:
                for chunk in self._synth_iter(text):
                    if self._cancel.is_set():
                        cancelled_any = True
                        raise _Cancelled()
                    self._play(chunk)
            except _Cancelled:
                break
            except Exception as e:
                self.synthError.emit(str(e))
                break
            finally:
                pass
        if started or self._active:
            self._active = False
            self.speechFinished.emit(not cancelled_any)

    def _synth_iter(self, text: str):
        gen = self.engine.synth_stream(text, self.voice, self.rate, self.volume,
                                       cancel=self._cancel.is_set)
        first = True
        for chunk in gen:
            if first:
                first = False
                if not self._active:
                    self._active = True
                    self.speechStarted.emit()
            yield chunk

    def _play(self, chunk: AudioChunk) -> None:
        from audio.engine import rms as _rms, spectrum as _spec
        if not self._active:
            self._active = True
            self.speechStarted.emit()
        if self.output_callback is not None:
            try:
                self.output_callback(chunk.samples, chunk.sample_rate)
            except Exception as e:  # устройство пропало — не роняем приложение
                self.synthError.emit(f"Ошибка воспроизведения: {e}")
                self._cancel.set()
                return
        # пауза ~ длительность куска, прерываемая отменой
        dur = len(chunk.samples) / max(chunk.sample_rate, 1)
        if self._cancel.wait(min(dur, 0.2)):
            return
        self.chunkLevels.emit(_rms(chunk.samples), _spec(chunk.samples))


class _Cancelled(Exception):
    pass
