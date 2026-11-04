"""Vosk STT: потоковое распознавание с interim-результатами.

Ленивые импорты vosk/sounddevice; без модели/микрофона объект просто не стартует,
приложение остаётся живым (текстовый чат полностью работает).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Signal


class VoskTranscriber(QThread):
    """Поток: микрофон -> Vosk. interimText — живой partial, finalText — готовая фраза."""

    interimText = Signal(str)
    finalText = Signal(str)
    micLevel = Signal(float)          # RMS для индикатора уровня в настройках
    errorOccurred = Signal(str)
    speechDetectedEnd = Signal()      # энергетический VAD: конец фразы (фолбэк silero)

    def __init__(self, model_path: str, device=None, sample_rate: int = 16000,
                 parent=None) -> None:
        super().__init__(parent)
        self.model_path = model_path
        self.device = device
        self.sample_rate = sample_rate
        self._stop = False
        self._pause = False
        self.last_final = ""           # half-duplex: пауза микрофона при TTS
        self._vad_threshold = 0.012
        self._silence_frames = 0

    def set_paused(self, paused: bool) -> None:
        self._pause = paused

    def is_paused(self) -> bool:
        return self._pause

    def flush_final(self) -> str:
        """Забрать последнюю финальную фразу (для PTT: отпустил — отправили)."""
        t, self.last_final = self.last_final, ""
        return t.strip()

    def stop_stream(self) -> None:
        self._stop = True
        self.wait(3000)

    def run(self) -> None:  # QThread entry
        try:
            from vosk import KaldiRecognizer, Model
        except ImportError:
            self.errorOccurred.emit("Vosk не установлен (pip install vosk). Голосовой ввод недоступен.")
            return
        if not self.model_path or not Path(self.model_path).is_dir():
            self.errorOccurred.emit(
                f"Модель Vosk не найдена по пути: {self.model_path}. "
                "Скачайте vosk-model-small-ru и укажите папку в настройках.")
            return
        try:
            import sounddevice as sd
        except Exception as e:
            self.errorOccurred.emit(f"Звук недоступен: {e}")
            return
        try:
            model = Model(self.model_path)
            rec = KaldiRecognizer(model, self.sample_rate)
            rec.SetWords(False)
            stream = sd.InputStream(samplerate=self.sample_rate, channels=1,
                                    dtype="int16", blocksize=2500, device=self.device)
        except Exception as e:
            self.errorOccurred.emit(f"Не удалось открыть микрофон/модель: {e}")
            return

        import numpy as np
        with stream:
            while not self._stop:
                data, _xrun = stream.read(2500)
                mono = data[:, 0]
                rms = float(np.sqrt(np.mean(mono.astype(np.float32) ** 2)) / 32768.0)
                self.micLevel.emit(rms)
                if self._pause:
                    continue
                buf = mono.tobytes()
                if rec.AcceptWaveform(buf):
                    res = json.loads(rec.Result())
                    text = res.get("text", "").strip()
                    if text:
                        self.last_final = text
                        self.finalText.emit(text)
                else:
                    part = json.loads(rec.PartialResult()).get("partial", "")
                    if part:
                        self.interimText.emit(part)
                # простой энергетический VAD для конца фразы
                if rms > self._vad_threshold:
                    self._silence_frames = 0
                else:
                    self._silence_frames += 1
                    if self._silence_frames == 45:  # ~1.5 с тишины при 2500/16000
                        self.speechDetectedEnd.emit()
