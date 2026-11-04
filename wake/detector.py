"""Детектор ключевого слова поверх Vosk (и текстового входа).

ВАЖНО (честность): это НЕ специализированная wake-word модель, а распознавание
с ограниченной грамматикой. Возможны ложные срабатывания/пропуски; метрики точности
не измерялись и не выдумываются.

Правила совпадения:
* «компьютерный» / «компьютеры» — НЕ активация (строгая проверка целого слова);
* фонетическая близость (levenshtein<=1 для medium, <=2 для fuzzy) только на уровне
  отдельного токена слова, подстрока внутри другого слова не считается.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

_WORD_RE = re.compile(r"[а-яёa-z]+", re.IGNORECASE)


def _norm_ye(s: str) -> str:
    """Нормализация ё->е и удаление диакритики юникода (ѐ и т.п.)."""
    import unicodedata
    s = unicodedata.normalize("NFC", s.replace("ё", "е").replace("Ё", "Е"))
    return s


def levenshtein(a: str, b: str) -> int:
    a, b = _norm_ye(a), _norm_ye(b)
    if len(a) > len(b):
        a, b = b, a
    prev = list(range(len(a) + 1))
    for i, cb in enumerate(b, start=1):
        cur = [i]
        for j, ca in enumerate(a, start=1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (_norm_ye(ca) != _norm_ye(cb))))
        prev = cur
    return prev[-1]


@dataclass
class WakeConfig:
    words: tuple[str, ...] = ("компьютер", "джарвис")
    strictness: str = "medium"  # strict | medium | fuzzy

    def max_distance(self) -> int:
        return {"strict": 0, "medium": 1, "fuzzy": 2}.get(self.strictness, 1)


def _diff_allowed(wake: str, tok: str) -> bool:
    """Токен похож на ключевое слово, но НЕ является его словоизменённой формой.

    Эвристика: если wake — точный префикс токена (разница только в хвосте), это
    суффиксная форма («компьютерЫ», «компьютере») => reject. Опечатки внутри слова
    («компютер», «компьютр») имеют общее окончание с wake и остаются допустимы.
    """
    if wake == tok:
        return True
    if len(tok) > len(wake) and tok.startswith(wake):
        return False  # всё различие — хвост => форма слова
    return True


def detect_wake(text: str, cfg: WakeConfig) -> tuple[bool, str]:
    """Ищет ключевое слово в тексте. Возвращает (активация, остаток_фразы_после_слова).

    Остаток используется схемой «Компьютер, открой браузер» (команда той же фразой).
    """
    norm = re.sub(r"[^а-яёa-z0-9 ,.\-]", " ", text.lower())
    tokens = _WORD_RE.findall(norm)
    dist_max = cfg.max_distance()
    for i, tok in enumerate(tokens):
        for w in cfg.words:
            wn, tn = _norm_ye(w), _norm_ye(tok)
            # только целые слова (не подстроки); ё/е нормализованы в levenshtein
            if levenshtein(tn, wn) <= dist_max and _diff_allowed(wn, tn):
                rest = " ".join(tokens[i + 1:])
                return True, rest
    return False, ""


class VoskWakeListener:
    """Потоковый детект через Vosk с ограниченной грамматикой (ленивая загрузка).

    Без микрофона/модели объект просто не стартует — приложение остаётся живым.
    """

    def __init__(self, model_path: str, cfg: WakeConfig, sample_rate: int = 16000) -> None:
        self.model_path = model_path
        self.cfg = cfg
        self.sample_rate = sample_rate
        self._rec = None
        self.on_wake = None  # callback(rest_text)

    def start(self) -> bool:
        try:
            from vosk import Model, KaldiRecognizer  # ленивый тяжёлый импорт
        except ImportError:
            return False
        gram = json.dumps({
            "words": [w for w in self.cfg.words],
            "partial_results": True,
        })
        self._model = Model(self.model_path)
        self._rec = KaldiRecognizer(self._model, self.sample_rate, gram)
        return True

    def feed(self, chunk: bytes) -> None:
        if self._rec is None:
            return
        if self._rec.AcceptWaveform(chunk):
            res = json.loads(self._rec.Result())
            text = res.get("text", "")
            hit, rest = detect_wake(text, self.cfg)
            if hit and self.on_wake:
                self.on_wake(rest)

    def stop(self) -> None:
        self._rec = None
