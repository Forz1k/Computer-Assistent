"""Тесты роутера быстрых команд (без LLM)."""
from __future__ import annotations

from datetime import datetime

from core.router import route


def test_open_browser_routes_to_tool():
    r = route("открой браузер")
    assert r.handled and r.tool == "open_app"
    assert r.args == {"alias": "браузер"}
    assert r.needs_confirmation  # запуск приложения — с подтверждением


def test_stop_is_direct():
    r = route("стоп")
    assert r.handled and r.direct_reply.lower().startswith("остановлено")


def test_time_direct_with_fixed_clock():
    r = route("который час", now=datetime(2026, 11, 4, 13, 37))
    assert r.handled and "13:37" in r.direct_reply


def test_volume_clamped():
    r = route("громкость 250")
    assert r.handled and r.args["level"] == 100
    r2 = route("громкость 30")
    assert r2.args["level"] == 30


def test_create_folder():
    r = route("создай папку проекты")
    assert r.handled and r.tool == "create_folder" and r.args["path"] == "проекты"


def test_system_info_no_confirmation():
    r = route("сколько памяти")
    assert r.handled and r.tool == "system_info" and not r.needs_confirmation


def test_plain_chat_not_handled():
    r = route("расскажи про римскую империю")
    assert not r.handled
