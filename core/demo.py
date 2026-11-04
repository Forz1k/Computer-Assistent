"""Демо-движок: синтетический аудио-поток + фейковый поток токенов.

Нужен для красивых GIF/скриншотов без микрофона и без Ollama.
ЧЕСТНОСТЬ: в UI всегда виден бейдж DEMO; демо не выдаёт себя за реальную работу —
все реплики помечены, статусные строки говорят «демо-источник».
"""
from __future__ import annotations

import math
import random
from typing import Iterator

import numpy as np

SR = 16000


def demo_audio_loop(seconds: float = 8.0, seed: int = 7) -> np.ndarray:
    """Мягкий «голосоподобный» спектр + пульсации для визуализатора."""
    rng = random.Random(seed)
    n = int(SR * seconds)
    t = np.linspace(0, seconds, n, endpoint=False, dtype=np.float32)
    f0 = 120 + 40 * np.sin(2 * math.pi * 0.11 * t)          # медленно «гуляющий» основной тон
    phase = 2 * np.pi * np.cumsum(f0) / SR
    sig = np.sin(phase) * 0.5
    for k in (2, 3, 5):                                     # форманты
        sig += np.sin(phase * k + rng.uniform(0, 6)) * 0.18 / k
    env = 0.5 + 0.5 * np.sin(2 * math.pi * 1.7 * t) ** 2    # слоги речи
    sig *= env.astype(np.float32)
    sig += np.random.default_rng(seed).normal(0, 0.015, n).astype(np.float32)
    return (sig * 0.35).astype(np.float32)


DEMO_CONVERSATION: list[dict] = [
    {"user": "Компьютер, статус систем",
     "reply_tokens": ["Системы ", "в норме. ", "Ядро ", "реактора ", "стабильно, ",
                      "все подсистемы ", "отвечают.", "\n\n", "(демонстрационный ответ)"]},
    {"user": "Компьютер, расскажи про этот интерфейс",
     "reply_tokens": ["Это HUD голосового ассистента: ", "ядро реагирует на звук в реальном времени, ",
                      "состояния — конечный автомат, ", "речь синтезируется локально.",
                      "\n\n", (
                          "```python\nprint('demo')\n```\n\n"), "(демонстрационный ответ)"]},
]


def demo_token_stream(idx: int, delay_range=(0.03, 0.09), cancel=None) -> Iterator[str]:
    """Не использовать time.sleep в GUI-потоке! Возвращает итератор чанков;
    планирование по таймеру делает DemoDriver (QTimer). Здесь — только данные."""
    tokens = DEMO_CONVERSATION[idx % len(DEMO_CONVERSATION)]["reply_tokens"]
    for tok in tokens:
        if cancel and cancel():
            return
        yield tok


def demo_meta(idx: int) -> dict:
    return {"ttft_ms": random.randint(120, 400), "tps": round(random.uniform(9, 21), 1),
            "tokens": len(DEMO_CONVERSATION[idx % len(DEMO_CONVERSATION)]["reply_tokens"]),
            "demo": True}
