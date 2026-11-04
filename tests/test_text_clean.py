"""Тесты препроцессинга текста для TTS."""
from __future__ import annotations

from tts.text_clean import clean_for_tts, split_sentences


def test_code_blocks_removed():
    out = clean_for_tts("Смотри:\n```python\nprint(1)\n```\nВот и всё.")
    assert "print" not in out
    assert "код" in out.lower()  # заменено на «код в окне»-формулировку


def test_markdown_stripped():
    out = clean_for_tts("**жирный** и `инлайн` и [ссылка](https://example.com)")
    assert "**" not in out and "`" not in out
    assert "http" not in out  # URL вырезается


def test_emoji_removed():
    out = clean_for_tts("готово ✅🚀")
    assert "✅" not in out and "🚀" not in out
    assert "готово" in out


def test_tables_removed():
    src = "| a | b |\n|---|---|\n| 1 | 2 |\nобычный текст"
    out = clean_for_tts(src)
    assert "|" not in out and "обычный текст" in out


def test_sentences_split():
    parts = split_sentences("Первое предложение. Второе! Третье?")
    assert len(parts) >= 3


def test_empty_input():
    assert clean_for_tts("") == ""


def test_numbers_expanded_or_kept_readably():
    out = clean_for_tts("42 компьютера")
    # либо словами, либо число осталось — но не мусор; главное — текст непустой
    assert out.strip() != ""
