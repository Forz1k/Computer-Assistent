"""Роутер быстрых детерминированных команд (без LLM).

«открой браузер», «стоп», «громкость 30», «время», «создай папку X» —
распознаются правилами и выполняются через ToolRegistry. Если правило не
сработало — текст уходит в LLM.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RouteResult:
    handled: bool
    tool: str = ""
    args: dict | None = None
    direct_reply: str = ""      # ответ без инструмента (время, помощь)
    needs_confirmation: bool = False


_OPEN = r"(?:открой|запусти|включи|подними)\s+(?:мой\s+)?(\w+)"
_CREATE_FOLDER = r"(?:создай|сделай)\s+(?:новую\s+)?папку\s+[«\"]?([\w\-. ]+)[»\"]?"
_WRITE_NOTE = r"(?:запиши|сохрани|создай)\s+файл\s+[«\"]?([\w\-.\\/ ]+)[»\"]?"
_SYSINFO = r"(?:система|сколько памяти|характеристики|инфо[- ]?rms?system|статус системы|версия)"
_TIME = r"(?:который час|какое время|текущее время|сколько времени)"
_STOP = r"^(?:стоп|прекрати|отмена|cancel|stop)\b"
_VOLUME = r"громкость\s+(\d{1,3})"


def route(text: str, now: datetime | None = None) -> RouteResult:
    t = text.strip().lower()
    if not t:
        return RouteResult(handled=False)
    if re.match(_STOP, t):
        return RouteResult(handled=True, direct_reply="Остановлено.")
    m = re.search(_TIME, t)
    if m:
        dt = now or datetime.now()
        return RouteResult(handled=True, direct_reply=f"Сейчас {dt.strftime('%H:%M')}.")
    m = re.search(_VOLUME, t)
    if m:
        v = max(0, min(100, int(m.group(1))))
        return RouteResult(handled=True, direct_reply=f"Громкость установлена: {v}%.",
                           tool="set_volume", args={"level": v})
    m = re.search(_OPEN, t)
    if m:
        return RouteResult(handled=True, tool="open_app", args={"alias": m.group(1)},
                           needs_confirmation=True)
    m = re.search(_CREATE_FOLDER, t)
    if m:
        return RouteResult(handled=True, tool="create_folder", args={"path": m.group(1)})
    m = re.search(_WRITE_NOTE, t)
    if m:
        return RouteResult(handled=True, tool="write_file",
                           args={"path": m.group(1), "content": ""},
                           needs_confirmation=True)
    if re.search(_SYSINFO, t):
        return RouteResult(handled=True, tool="system_info", args={})
    url_m = re.search(r"\b(?:открой\s+)?(https?://\S+)", t)
    if url_m:
        return RouteResult(handled=True, tool="open_url", args={"url": url_m.group(1)},
                           needs_confirmation=True)
    return RouteResult(handled=False)
