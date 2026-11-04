"""Structured tool-calling: строгий JSON от модели + одна попытка восстановления.

Никакого парсинга «на глазок» регулярками по всему тексту: сначала json.loads всего
ответа; если не валится — извлекаем первый сбалансированный {...} блок (детерминированно,
не жадно) и пробуем ещё раз. Невалидно после обеих попыток — вежливая ошибка.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolCall:
    tool: str
    args: dict[str, Any]


class ToolCallError(ValueError):
    pass


def _balanced_json_slice(text: str) -> str | None:
    """Первый сбалансированный JSON-объект (учитывая строки/экраны). Детерминированно."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    return None


def parse_tool_call(raw: str, allowed_tools: list[str]) -> ToolCall:
    """Разбирает ответ модели в ToolCall. Бросает ToolCallError при невалидном."""
    candidates: list[str] = []
    t = raw.strip()
    candidates.append(t)
    sliced = _balanced_json_slice(t)
    if sliced and sliced != t:
        candidates.append(sliced)
    obj: Any = None
    for cand in candidates:      # попытка 1 и «одна попытка восстановления» — попытка 2
        try:
            obj = json.loads(cand)
            break
        except json.JSONDecodeError:
            continue
    if obj is None or not isinstance(obj, dict):
        raise ToolCallError("Модель вернула не JSON-вызов инструмента.")
    name = obj.get("tool")
    args = obj.get("args", {})
    if not isinstance(name, str) or not isinstance(args, dict):
        raise ToolCallError("В JSON нет полей tool/args нужных типов.")
    if name not in allowed_tools:
        raise ToolCallError(f"Инструмент «{name}» отсутствует в реестре. Доступны: {', '.join(allowed_tools)}")
    return ToolCall(tool=name, args=args)


def looks_like_tool_call(raw: str) -> bool:
    """Эвристика для роутера: отправлять ли ответ модели в tool-pipeline.

    Только явные маркеры: валидный JSON со key "tool" либо текст, начинающийся с '{'.
    Обычный прозаический ответ никогда не сойдёт за вызов.
    """
    t = raw.strip()
    if not t.startswith("{"):
        return False
    try:
        obj = json.loads(_balanced_json_slice(t) or "")
    except (json.JSONDecodeError, TypeError):
        return False
    return isinstance(obj, dict) and "tool" in obj
