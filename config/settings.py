"""Настройки приложения: JSON-файл + значения по умолчанию + миграции.

Секреты (API-ключи) здесь НЕ хранятся — только keyring (Windows Credential Manager).
В конфиге нет персональных путей: рабочая папка вычисляется из %USERPROFILE%.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

APP_DIR_ENV = "COMPUTER_ASSISTANT_HOME"


def app_data_dir() -> Path:
    """Каталог данных приложения (конфиг, БД, логи). Без персональных имён в коде."""
    env = os.environ.get(APP_DIR_ENV)
    if env:
        return Path(env)
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
        return base / "ComputerAssistant"
    return Path.home() / ".local" / "share" / "computer-assistant"


def default_workspace() -> Path:
    """Рабочая папка пользователя: %USERPROFILE%\\JarvisWorkspace (Windows) или ~/JarvisWorkspace."""
    if sys.platform == "win32":
        return Path(os.environ.get("USERPROFILE", str(Path.home()))) / "JarvisWorkspace"
    return Path.home() / "JarvisWorkspace"


CONFIG_VERSION = 1

DEFAULTS: dict[str, Any] = {
    "config_version": CONFIG_VERSION,
    "theme": "reactor_cyan",
    "reduced_motion": False,
    "ui_scale": 100,
    "network_mode": "offline",           # offline | hybrid | online
    "persona": "computer",               # jarvis | computer | neutral
    "language": "ru",
    "ollama": {
        "base_url": "http://127.0.0.1:11434",
        "model": "",                       # выбирается из реального /api/tags
        "num_ctx": 4096,
        "keep_alive": "5m",
        "timeout_s": 120,
    },
    "voice": {
        "piper_bin": "",                   # путь к piper.exe (настраивается)
        "piper_model": "",                 # путь к .onnx голоса
        "rate": 1.0,
        "volume": 1.0,
        "enabled": True,
        "sapi_fallback": True,
    },
    "stt": {"model_path": ""},          # путь к vosk-model-small-ru-*
    "audio": {
        "input_device": None,
        "output_device": None,
        "mic_gain": 1.0,
    },
    "wake": {
        "word": "компьютер",
        "aliases": ["джарвис"],
        "strictness": "medium",            # strict | medium | fuzzy
        "command_timeout_s": 6.0,
        "always_on": True,
        "ptt_hotkey": "ctrl+alt+space",
    },
    "sounds": {"enabled": True, "volume": 0.25},
    "workspace": {"root": str(default_workspace()), "max_file_mb": 8},
    "security": {"confirm_dangerous": True, "audit_enabled": True},
    "online": {"base_url": "", "model": "", "search_url": ""},  # ключ — только в keyring
    "demo_mode": False,
}


@dataclass
class Settings:
    data: dict[str, Any] = field(default_factory=lambda: json.loads(json.dumps(DEFAULTS)))
    path: Path | None = None
    _listeners: list[Any] = field(default_factory=list, repr=False)

    # -------- доступ --------
    def get(self, dotted: str, default: Any = None) -> Any:
        cur: Any = self.data
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    def set(self, dotted: str, value: Any) -> None:
        cur = self.data
        parts = dotted.split(".")
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
        cur[parts[-1]] = value
        self.save()
        for cb in self._listeners:
            cb(dotted, value)

    def changed(self, cb: Any) -> None:
        self._listeners.append(cb)

    # -------- персистентность --------
    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        p = path or app_data_dir() / "config.json"
        s = cls(path=p)
        if p.exists():
            try:
                loaded = json.loads(p.read_text(encoding="utf-8"))
                s.data = _merge(json.loads(json.dumps(DEFAULTS)), loaded)
                s.data = _migrate(s.data)
            except (json.JSONDecodeError, OSError):
                # повреждённый конфиг не роняет приложение — работаем на дефолтах
                pass
        return s

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)


def _migrate(data: dict[str, Any]) -> dict[str, Any]:
    """Миграции настроек. Версия хранится в config_version."""
    v = int(data.get("config_version", 0))
    if v < 1:
        data["config_version"] = CONFIG_VERSION
    return data


def _merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def redact_secrets(text: str) -> str:
    """Глушит потенциальные секреты в логах/отчётах (sk-..., Bearer ...)."""
    import re
    text = re.sub(r"(sk-[A-Za-z0-9_\-]{8})[A-Za-z0-9_\-]+", r"\1***REDACTED***", text)
    text = re.sub(r"(Bearer\s+)[A-Za-z0-9._\-]{6,}", r"\1***REDACTED***", text)
    return text
