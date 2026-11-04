"""Аудио-подсистема: захват, уровни RMS, FFT для визуализатора, воспроизведение.

Всё железо-зависимое — лениво (sounddevice импортируется при старте потока).
Без звуковых устройств приложение работает: capture не стартует, UI получает
уровни 0 и мягко дизейблит голосовые элементы.

Ring levels публикуются в GUI через Qt-сигнал из QThread (queued connection).
"""
from __future__ import annotations

import math
from collections import deque

import numpy as np
from PySide6.QtCore import QThread, Signal


SR = 16000
FFT_BINS = 64


def rms(chunk: np.ndarray) -> float:
    if chunk.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))


def spectrum(chunk: np.ndarray, bins: int = FFT_BINS) -> list[float]:
    """Нормализованный радиальный спектр (0..1) с attack/release сглаживанием."""
    n = min(len(chunk), 2048)
    if n < 64:
        return [0.0] * bins
    win = np.hanning(n)
    sp = np.abs(np.fft.rfft(chunk[:n] * win))
    # логарифмическое распределение корзин
    freqs = np.fft.rfftfreq(n, 1 / SR)
    edges = np.geomspace(50, min(SR / 2 - 1, 8000), bins + 1)
    out = []
    for i in range(bins):
        m = (freqs >= edges[i]) & (freqs < edges[i + 1])
        v = float(np.max(sp[m])) if m.any() else 0.0
        out.append(min(1.0, v / 900.0))
    return out


class LevelSmoother:
    """attack ~40 мс, release ~220 мс при 60 FPS."""

    def __init__(self, bins: int = FFT_BINS) -> None:
        self.bins = bins
        self.vals = [0.0] * bins
        self.a_in = 1 - math.exp(-1 / (60 * 0.040))
        self.a_out = 1 - math.exp(-1 / (60 * 0.220))

    def update(self, target: list[float]) -> list[float]:
        for i, t in enumerate(target):
            a = self.a_in if t > self.vals[i] else self.a_out
            self.vals[i] += a * (t - self.vals[i])
        return list(self.vals)


class AudioLevels(QThread):
    """Источник уровней для ядра: микрофон или внешний буфер (TTS/демо).

    feed(buf) позволяет без микрофона кормить визуализатор синтезированным
    аудио (режим SPEAKING) или демо-потоком.
    """

    levelsReady = Signal(float, list)  # rms, spectrum[64]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._stop = False
        self._external: deque[np.ndarray] = deque(maxlen=8)
        self._smoother = LevelSmoother()
        self.device = None
        self.capture_ok = False

    def feed(self, samples: np.ndarray) -> None:
        self._external.append(samples)

    def run(self) -> None:
        stream = None
        sd = None
        try:
            import sounddevice as _sd
            sd = _sd
            if sd.query_devices():
                stream = sd.InputStream(samplerate=SR, channels=1, dtype="float32",
                                        device=self.device)
                stream.start()
                self.capture_ok = True
            else:
                self.capture_ok = False
        except Exception:
            self.capture_ok = False

        interval = 1 / 30.0
        import time as _t
        while not self._stop:
            frame = None
            # приоритет: внешний поток (TTS/демо), иначе микрофон
            if self._external:
                frame = self._external.popleft()
            elif stream is not None:
                try:
                    data, _overflow = stream.read(512)
                    frame = data[:, 0]
                except Exception:
                    frame = None
            if frame is None:
                frame = np.zeros(512, dtype=np.float32)
            r = rms(frame)
            sp = self._smoother.update(spectrum(frame))
            self.levelsReady.emit(r, sp)
            _t.sleep(interval)

        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

    def stop(self) -> None:
        self._stop = True
        self.wait(2000)
