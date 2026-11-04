"""Тесты детектора ключевого слова, включая негативные словоформы."""
from __future__ import annotations

import pytest

from wake.detector import WakeConfig, detect_wake, levenshtein


CFG_STRICT = WakeConfig(strictness="strict")
CFG_MED = WakeConfig(strictness="medium")


@pytest.mark.parametrize("text", [
    "компьютер",
    "Компьютер, открой браузер",
    "джарвис включи музыку",
    "привет компьютер как дела",
    "Компьютер!",
])
def test_positive_activation(text: str):
    hit, _rest = detect_wake(text, CFG_STRICT)
    assert hit, text


@pytest.mark.parametrize("text", [
    "компьютерный магазин",     # прилагательное — НЕ активация
    "компьютеры сломались",     # множественное — НЕ активация
    "в компьютере шум",         # предложный падеж внутри слова-формы — НЕ активация
    "вычислительная система",   # нет ключа вообще
    "компания пью воду",        # подстрока «комп…пью» склеенными токенами — НЕ активация
])
def test_negative_forms(text: str):
    hit, _rest = detect_wake(text, CFG_STRICT)
    assert not hit, f"ложная активация на: {text}"


def test_rest_extracted():
    hit, rest = detect_wake("компьютер открой браузер", CFG_STRICT)
    assert hit
    assert "открой" in rest and "браузер" in rest


@pytest.mark.parametrize("typo", ["компютер", "компьютр"])
def test_medium_forgives_typos(typo: str):
    hit, _ = detect_wake(f"{typo} стоп", CFG_MED)
    assert hit, typo


def test_medium_rejects_two_char_swap():
    # «компьюетр» — перестановка 2 букв (расстояние 2) — medium не прощает, fuzzy прощает
    hit, _ = detect_wake("компьюетр стоп", CFG_MED)
    assert not hit
    hit2, _ = detect_wake("компьюетр стоп", WakeConfig(strictness="fuzzy"))
    assert hit2


def test_medium_still_rejects_wordforms():
    hit, _ = detect_wake("компьютерный клуб", CFG_MED)
    assert not hit


def test_yo_normalization():
    hit, _ = detect_wake("Компьютер", CFG_STRICT)      # с ё
    assert hit
    hit2, _ = detect_wake("Компьютер", CFG_STRICT)     # без ё (е)
    assert hit2


def test_levenshtein_basic():
    assert levenshtein("кот", "кот") == 0
    assert levenshtein("кот", "код") == 1
    assert levenshtein("", "abc") == 3
