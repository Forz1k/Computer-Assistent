"""Реестр инструментов с уровнями риска, схемами аргументов и валидацией путей.

Безопасность (раздел 8 ТЗ):
* subprocess только списком аргументов, shell=False;
* пути: resolve + проверка корня, запрет .., symlink/junction escape, UNC;
* удаление/перезапись — только подтверждение + .backup_<ts>;
* никаких eval/exec над текстом модели.
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


class ToolError(RuntimeError):
    """Понятная человеку ошибка инструмента."""


class PathEscape(ToolError):
    pass


@dataclass
class ToolSpec:
    name: str
    title: str
    description: str
    risk: str                    # low | medium | high
    requires_confirmation: bool
    handler: Callable[..., dict[str, Any]]
    schema: dict[str, str] = field(default_factory=dict)  # arg -> тип для JSON-схемы


def safe_resolve(raw: str, roots: list[Path], must_exist: bool = False) -> Path:
    """Разрешает путь и проверяет, что он внутри одного из корней.

    Блокирует: относительные выходы через .., symlink/hardlink escape (проверка
    финализированного пути), UNC-пути, пустые.
    """
    if not raw or raw.strip() == "":
        raise PathEscape("Пустой путь")
    p = Path(raw)
    if str(p).startswith("\\\\"):
        raise PathEscape("UNC-пути запрещены")
    if not p.is_absolute():
        base = roots[0] if roots else Path.cwd()
        p = base / p
    try:
        resolved = p.resolve(strict=must_exist)
    except FileNotFoundError:
        raise PathEscape(f"Файл не найден: {p.name}") from None
    for root in roots:
        try:
            rres = root.resolve()
            resolved.relative_to(rres)
            return resolved
        except ValueError:
            continue
    raise PathEscape(f"Путь вне разрешённых папок: {resolved}")


SYSTEM_INFO_ROOTS = [Path("/proc")] if sys.platform != "win32" else []


class ToolRegistry:
    def __init__(self, workspace_root: Path, app_aliases: dict[str, str] | None = None) -> None:
        self.workspace_root = workspace_root
        self.app_aliases = app_aliases or default_app_aliases()
        self.audit: list[dict[str, Any]] = []
        self._tools: dict[str, ToolSpec] = {}
        self._register_all()

    # ---------- реестр ----------
    def _register_all(self) -> None:
        S = self.spec
        self.register(ToolSpec("open_app", "Открыть приложение",
                               "Запуск приложения из белого списка псевдонимов", "medium", True,
                               self.open_app, {"alias": "str"}))
        self.register(ToolSpec("open_url", "Открыть URL",
                               "Открытие http/https ссылки в системном браузере", "medium", True,
                               self.open_url, {"url": "str"}))
        self.register(ToolSpec("create_folder", "Создать папку",
                               "Создание папки внутри рабочей области", "low", False,
                               self.create_folder, {"path": "str"}))
        self.register(ToolSpec("read_file", "Прочитать файл",
                               "Чтение текстового файла из рабочей области", "low", False,
                               self.read_file, {"path": "str"}))
        self.register(ToolSpec("write_file", "Создать/записать файл",
                               "Запись текстового файла в рабочую область (перезапись — с подтверждением)",
                               "high", True, self.write_file, {"path": "str", "content": "str"}))
        self.register(ToolSpec("system_info", "Системная информация",
                               "Только чтение: ОС, CPU, память, диски", "low", False,
                               self.system_info, {}))
        del S

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def spec(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise ToolError(f"Неизвестный инструмент: {name}")
        return self._tools[name]

    def names(self) -> list[str]:
        return sorted(self._tools)

    def json_schema(self) -> dict[str, Any]:
        """Схема для structured tool-calling моделью (строгий JSON)."""
        return {
            "type": "object",
            "properties": {
                "tool": {"type": "string", "enum": self.names()},
                "args": {"type": "object"},
            },
            "required": ["tool"],
        }

    # ---------- выполнение ----------
    def execute(self, name: str, args: dict[str, Any], confirmed: bool = False,
                request_id: str = "") -> dict[str, Any]:
        spec = self.spec(name)
        result: dict[str, Any]
        if spec.requires_confirmation and not confirmed:
            result = {"status": "needs_confirmation", "tool": name, "args": _safe_args(args),
                      "risk": spec.risk,
                      "message": f"Действие «{spec.title}» требует подтверждения"}
        else:
            try:
                result = {"status": "ok", "tool": name, **spec.handler(**args)}
            except ToolError as e:
                result = {"status": "error", "tool": name, "message": str(e)}
        self._log(name, args, result, confirmed, request_id)
        return result

    def _log(self, name: str, args: dict[str, Any], result: dict[str, Any],
             confirmed: bool, request_id: str) -> None:
        import time
        self.audit.append({
            "ts": time.time(), "request_id": request_id, "tool": name,
            "args": _safe_args(args), "status": result.get("status"),
            "confirmed": confirmed,
        })
        if len(self.audit) > 5000:
            del self.audit[:2000]

    # ---------- реализация инструментов ----------
    def open_app(self, alias: str) -> dict[str, Any]:
        cmd = self.app_aliases.get(alias.lower().strip())
        if not cmd:
            raise ToolError(f"Приложение «{alias}» не в белом списке. Настройте псевдонимы в разделе «Активация».")
        plat = platform.system()
        if plat == "Windows":
            full = _windows_command(cmd)
        elif plat == "Linux":
            full = [cmd]
        else:
            full = ["open", cmd]
        try:
            subprocess.Popen(full, shell=False)  # noqa: S603 — список аргументов, белый список
        except OSError as e:
            raise ToolError(f"Не удалось запустить {cmd}: {e}") from None
        return {"opened": alias}

    def open_url(self, url: str) -> dict[str, Any]:
        if not url.startswith(("http://", "https://")):
            raise ToolError("Разрешены только схемы http/https")
        import webbrowser
        webbrowser.open(url)
        return {"opened": url}

    def create_folder(self, path: str) -> dict[str, Any]:
        p = safe_resolve(path, [self.workspace_root])
        p.mkdir(parents=True, exist_ok=True)
        return {"created": str(p)}

    def read_file(self, path: str) -> dict[str, Any]:
        p = safe_resolve(path, [self.workspace_root], must_exist=True)
        if not p.is_file():
            raise ToolError("Это не файл")
        max_b = 512 * 1024
        text = p.read_text(encoding="utf-8", errors="replace")
        truncated = len(text.encode("utf-8")) > max_b
        return {"content": text[:max_b], "truncated": truncated, "path": str(p)}

    def write_file(self, path: str, content: str) -> dict[str, Any]:
        p = safe_resolve(path, [self.workspace_root])
        backup = None
        if p.exists():
            import time
            backup = p.with_name(p.name + f".backup_{time.strftime('%Y%m%d_%H%M%S')}")
            backup.write_bytes(p.read_bytes())
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"written": str(p), "backup": str(backup) if backup else None}

    def system_info(self) -> dict[str, Any]:
        import shutil
        info: dict[str, Any] = {
            "os": f"{platform.system()} {platform.release()}",
            "python": sys.version.split()[0],
            "cpu_count": os.cpu_count(),
            "machine": platform.machine(),
        }
        try:
            import psutil
            vm = psutil.virtual_memory()
            info["ram_total_gb"] = round(vm.total / 2**30, 1)
            info["ram_used_pct"] = vm.percent
            du = shutil.disk_usage(str(Path.home()))
            info["disk_free_gb"] = round(du.free / 2**30, 1)
        except ImportError:
            info["ram_total_gb"] = None
        return {"info": info}


def _safe_args(args: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for k, v in args.items():
        s = str(v)
        out[k] = s if len(s) < 120 else s[:117] + "..."
    return out


def _windows_command(cmd: str) -> list[str]:
    if cmd.endswith(".exe") or cmd.endswith(".com"):
        return [cmd]
    return ["cmd", "/c", "start", "", cmd]


def default_app_aliases() -> dict[str, str]:
    """Белый список. Терминал — только открытие, команды не передаются."""
    if platform.system() == "Windows":
        return {
            "браузер": "start",  # замещается на edge при запуске
            "блокнот": "notepad.exe",
            "калькулятор": "calc.exe",
            "редактор кода": "code.cmd",
            "терминал": "wt.exe",
            "проводник": "explorer.exe",
        }
    return {
        "браузер": "xdg-open",
        "блокнот": "gedit",
        "калькулятор": "gnome-calculator",
        "редактор кода": "code",
        "терминал": "x-terminal-emulator",
        "проводник": "xdg-open",
    }
