"""Тесты structured tool-calling: строгий JSON, одна попытка восстановления, негатив."""
from __future__ import annotations

import pytest

from tools.tool_call import ToolCallError, looks_like_tool_call, parse_tool_call


ALLOWED = ["open_app", "write_file", "system_info"]


def test_plain_json_parses():
    tc = parse_tool_call('{"tool": "open_app", "args": {"alias": "браузер"}}', ALLOWED)
    assert tc.tool == "open_app" and tc.args["alias"] == "браузер"


def test_recovery_from_wrapped_json():
    raw = 'Конечно! Вот вызов:\n```json\n{"tool": "system_info", "args": {}}\n```\nНадеюсь помог.'
    tc = parse_tool_call(raw, ALLOWED)
    assert tc.tool == "system_info"


def test_unknown_tool_rejected():
    with pytest.raises(ToolCallError):
        parse_tool_call('{"tool": "delete_windows", "args": {}}', ALLOWED)


def test_non_json_rejected():
    with pytest.raises(ToolCallError):
        parse_tool_call("просто открой браузер пожалуйста", ALLOWED)


def test_broken_json_rejected():
    with pytest.raises(ToolCallError):
        parse_tool_call('{"tool": "open_app", args: {}}', ALLOWED)  # невалидный JSON


def test_missing_fields_rejected():
    with pytest.raises(ToolCallError):
        parse_tool_call('{"action": "open_app"}', ALLOWED)


def test_looks_like_positive():
    assert looks_like_tool_call('{"tool": "open_app", "args": {}}')


def test_looks_like_negative_prose():
    assert not looks_like_tool_call("Я думаю, что стоит открыть браузер.")
    assert not looks_like_tool_call("")
    assert not looks_like_tool_call("{ это не json")
