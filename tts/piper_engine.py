"""Piper TTS: два пути, оба честные.

1) piper-tts Python-пакет (pip install piper-tts) — основной, если установлен;
2) внешний бинарь piper.exe + .onnx голос — если пользователь скачал сам
   (пути настраиваются в Settings.voice.piper_bin / piper_model).

Приложение запускается и работает без Piper: available() == False, UI показывает
инструкцию. Никаких автоматических загрузок моделей.
"""
from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path
from typing import Callable, Iterator, Optional

import numpy as np

from tts.base import AudioChunk, VoiceInfo


class PiperEngine:
    name = "piper"

    def __init__(self, bin_path: str = "", model_path: str = "",
                 voices_dir: str = "") -> None:
        self.bin_path = bin_path
        self.model_path = model_path
        self.voices_dir = voices_dir or str(Path.home() / ".local" / "share" / "piper-voices")
        self._py_synthesizer = None       # кэш объекта Voice пiper-tts
        self._py_voice_id: str = ""

    # ---------- обнаружение ----------
    def _python_piper_available(self) -> bool:
        try:
            import piper  # noqa: F401
            return True
        except ImportError:
            return False

    def _binary_available(self) -> bool:
        if self.bin_path and Path(self.bin_path).is_file():
            return True
        return shutil.which("piper") is not None

    def available(self) -> bool:
        return self._python_piper_available() or self._binary_available()

    def voices(self) -> list[VoiceInfo]:
        """Реально найденные локально голоса. Ничего не выдумывается."""
        found: list[VoiceInfo] = []
        seen: set[str] = set()
        if self.model_path and Path(self.model_path).is_file():
            vid = Path(self.model_path).stem
            found.append(VoiceInfo(vid, self.model_path, "piper"))
            seen.add(vid)
        vdir = Path(self.voices_dir)
        if vdir.is_dir():
            for onnx in sorted(vdir.rglob("*.onnx")):
                vid = onnx.stem
                if vid not in seen:
                    found.append(VoiceInfo(vid, str(onnx), "piper"))
                    seen.add(vid)
        # голоса, известные pip-пакету (если сеть запрещена — просто пусто)
        if self._python_piper_available():
            try:
                from piper.download.voices import get_voices  # локальный catalog json
                for key in get_voices():
                    vid = str(key)
                    if vid.startswith("ru_") and vid not in seen:
                        found.append(VoiceInfo(vid, "", "piper-pip", label=f"{vid} (через pip, нужен файл голоса)"))
                        seen.add(vid)
            except Exception:
                pass
        return found

    def voice_path(self, voice: VoiceInfo) -> Optional[str]:
        if voice.path and Path(voice.path).is_file():
            return voice.path
        # поиск по имени в voices_dir
        vdir = Path(self.voices_dir)
        if vdir.is_dir():
            for onnx in vdir.rglob(f"{voice.id}.onnx"):
                return str(onnx)
        return None

    # ---------- синтез ----------
    def synth_stream(self, text: str, voice: VoiceInfo, rate: float = 1.0,
                     volume: float = 1.0,
                     cancel: Optional[Callable[[], bool]] = None) -> Iterator[AudioChunk]:
        path = self.voice_path(voice)
        if path is None:
            raise FileNotFoundError(
                f"Файл голоса не найден: {voice.id}. Скачайте голос Piper вручную и укажите путь в настройках.")
        if self._python_piper_available():
            yield from self._synth_python(text, path, rate, volume, cancel)
        else:
            yield from self._synth_binary(text, path, rate, volume, cancel)

    def _synth_python(self, text, path, rate, volume, cancel) -> Iterator[AudioChunk]:
        from piper import PiperVoice  # ленивый импорт

        if self._py_synthesizer is None or self._py_voice_id != path:
            self._py_synthesizer = PiperVoice.load(path)
            self._py_voice_id = path
        syn = self._py_synthesizer
        sr = syn.config.sample_rate
        chunks_per_send = int(sr * 0.05)
        buf = np.zeros(0, dtype=np.float32)
        for chunk in syn.synthesize(text):
            if cancel and cancel():
                return
            audio = chunk.audio_float_array.astype(np.float32) * min(1.0, volume)
            buf = np.concatenate([buf, audio])
            while len(buf) >= chunks_per_send:
                yield AudioChunk(buf[:chunks_per_send], sr)
                buf = buf[chunks_per_send:]
        if len(buf):
            yield AudioChunk(buf, sr)

    def _synth_binary(self, text, path, rate, volume, cancel) -> Iterator[AudioChunk]:
        exe = self.bin_path or "piper"
        cmd = [exe, "--model", path, "--output-raw"]
        if rate != 1.0:
            cmd += ["--length_scale", str(round(1.0 / max(rate, 0.1), 3))]
        proc = subprocess.run(cmd, input=text.encode("utf-8"),  # noqa: S603 — фикс. список
                              capture_output=True, shell=False, timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(f"Piper завершился с кодом {proc.returncode}: "
                               f"{proc.stderr.decode('utf-8', 'replace')[:300]}")
        pcm = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        pcm *= min(1.0, volume)
        sr = 22050
        step = int(sr * 0.05)
        for i in range(0, len(pcm), step):
            if cancel and cancel():
                return
            yield AudioChunk(pcm[i:i + step], sr)


class DummyEngine:
    """Для тестов/без железа: выдаёт тихий синус вместо речи. ВСЕГДА помечен как dummy."""
    name = "dummy"

    def __init__(self) -> None:
        pass

    def available(self) -> bool:
        return True

    def voices(self) -> list[VoiceInfo]:
        return [VoiceInfo("dummy-tone", "", "dummy", label="Тестовый тон (не речь)")]

    def synth_stream(self, text, voice, rate=1.0, volume=1.0, cancel=None) -> Iterator[AudioChunk]:
        sr = 22050
        n = max(int(sr * min(len(text) * 0.03, 3.0)), sr // 4)
        t = np.arange(n, dtype=np.float32) / sr
        sig = (np.sin(2 * np.pi * 320 * t) * 0.15 * volume).astype(np.float32)
        step = int(sr * 0.05)
        for i in range(0, n, step):
            if cancel and cancel():
                return
            yield AudioChunk(sig[i:i + step], sr)


def read_wav_mono(path: str) -> tuple[np.ndarray, int]:
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        if w.getnchannels() == 2:
            data = data.reshape(-1, 2).mean(axis=1)
        return data.astype(np.float32) / 32768.0, sr
