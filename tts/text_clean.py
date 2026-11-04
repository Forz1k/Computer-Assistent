"""Препроцессинг текста для озвучки.

Убирает код/URL/markdown/эмодзи/таблицы, нормализует числа и даты к русскому
произношению. Никакой «магии»: только детерминированные правила, каждое — с тестом.
"""
from __future__ import annotations

import re

_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\u2B00-\u2BFF\uFE0F\u200D]+"
)
_CODE_BLOCK_RE = re.compile(r"```.*?(```|$)", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_URL_RE = re.compile(r"https?://\S+")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
_HDR_RE = re.compile(r"^\s*#{1,6}\s*", re.MULTILINE)
_BOLD_RE = re.compile(r"(\*{1,3}|_{1,3})(?=\S)(.+?)(?<=\S)\1")
_BULLET_RE = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
_NUM_SPACES = re.compile(r"(?<=\d)[ \u00A0](?=\d{3}(\D|$))")  # 1 000 -> 1000


def _num_to_words_ru(n: int) -> str:
    units = {
        1: ["один", "одна"], 2: ["два", "две"], 3: "три", 4: "четыре", 5: "пять",
        6: "шесть", 7: "семь", 8: "восемь", 9: "девять",
    }
    teens = {10: "десять", 11: "одиннадцать", 12: "двенадцать", 13: "тринадцать",
             14: "четырнадцать", 15: "пятнадцать", 16: "шестнадцать",
             17: "семнадцать", 18: "восемнадцать", 19: "девятнадцать"}
    tens = {2: "двадцать", 3: "тридцать", 4: "сорок", 5: "пятьдесят",
            6: "шестьдесят", 7: "семьдесят", 8: "восемьдесят", 9: "девяносто"}
    hundreds = {1: "сто", 2: "двести", 3: "триста", 4: "четыреста", 5: "пятьсот",
                6: "шестьсот", 7: "семьсот", 8: "восемьсот", 9: "девятьсот"}

    def gender_small(x: int, fem: bool) -> str:
        if x < 10:
            u = units[x]
            return u[1] if fem else u[0]
        if x < 20:
            return teens[x]
        t, r = divmod(x, 10)
        base = tens[t]
        if r:
            base += " " + (units[r][1] if fem else units[r][0])
        return base

    if n == 0:
        return "ноль"
    parts: list[str] = []
    classes = [(10**9, "миллиард", "миллиарда", "миллиардов", False),
               (10**6, "миллион", "миллиона", "миллионов", False),
               (10**3, "тысяча", "тысячи", "тысяч", True)]
    rest = n
    for div, one, few, many, fem in classes:
        c, rest = divmod(rest, div)
        if c:
            w = gender_small(c, fem) if c < 100 else _hundreds_only(c)
            tail = c % 10
            form = one if tail == 1 and c % 100 != 11 else (few if 2 <= tail <= 4 and not (12 <= c % 100 <= 14) else many)
            parts.append((w + " " if c > 1 else ("одна " if fem else ("один " if not fem else ""))) + form)
    if rest:
        parts.append(gender_small(rest, False))
    return " ".join(parts)


def _hundreds_only(n: int) -> str:
    h, r = divmod(n, 100)
    out = []
    if h:
        out.append({1: "сто", 2: "двести", 3: "триста", 4: "четыреста", 5: "пятьсот",
                    6: "шестьсот", 7: "семьсот", 8: "восемьсот", 9: "девятьсот"}[h])
    if r:
        out.append(_num_to_words_ru(r))
    return " ".join(out)


def _expand_numbers(text: str) -> str:
    def repl(m: re.Match) -> str:
        try:
            return _num_to_words_ru(int(m.group(0)))
        except (ValueError, RecursionError):
            return m.group(0)
    return re.sub(r"\b\d{1,9}\b", repl, text)


def clean_for_tts(text: str) -> str:
    """Возвращает текст, пригодный для произнесения вслух."""
    t = text
    t = _CODE_BLOCK_RE.sub("Код приведён в окне.", t)
    t = _INLINE_CODE_RE.sub(r"\1", t)
    t = _MD_LINK_RE.sub(r"\1", t)
    t = _URL_RE.sub("ссылка пропущена", t)
    t = _TABLE_ROW_RE.sub("", t)
    t = _HDR_RE.sub("", t)
    t = _BOLD_RE.sub(r"\2", t)
    t = _BULLET_RE.sub("", t)
    t = _EMOJI_RE.sub("", t)
    t = _NUM_SPACES.sub("", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{2,}", "\n", t).strip()
    t = _expand_numbers(t)
    return t


def split_sentences(text: str) -> list[str]:
    """Разбивает на предложения для потокового синтеза (не дожидаясь конца ответа)."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?…])\s+", text)
    out = [p.strip() for p in parts if p.strip()]
    return out
