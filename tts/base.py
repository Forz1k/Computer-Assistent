"""Базовые типы TTS-адаптеров."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Protocol


@dataclass
class VoiceInfo:
    id: str            # например ru_RU-denis-medium
    path: str          # путь к .onnx (или special-id для SAPI)
    engine: str        # piper | sapi | nulltalk | dummy
    language: str = "ru"
    label: str = ""

    def __post_init__(self) -> None:
        if not self.label:
            self.label = f"{self.id} ({self.engine})"


class TTSEngine(Protocol):
    """Интерфейс синтезатора. Реализации обязаны быть отменяемыми."""

    name: str

    def available(self) -> bool: ...

    def voices(self) -> list[VoiceInfo]: ...

    def synth_stream(self, text: str, voice: VoiceInfo, rate: float = 1.0,
                    volume: float = 1.0, cancel=None) -> Iterator["AudioChunk"]: ...


@dataclass
class AudioChunk:
    samples: object          # np.ndarray float32 mono
    sample_rate: int
    sentence: str = ""
