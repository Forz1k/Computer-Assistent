"""Проверки компонентов для boot-экрана и диагностического экрана.

Каждая проверка РЕАЛЬНАЯ (HTTP, путь, устройство) и возвращает понятную инструкцию
«что сделать», если пункт красный. Никаких фейковых «готово».
"""
from __future__ import annotations

import importlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ComponentStatus:
    name: str
    status: str            # ok | warn | fail
    detail: str            # что обнаружено (реально)
    action: str = ""       # «что сделать» для пользователя
    latency_ms: int | None = None
    version: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status, "detail": self.detail,
                "action": self.action, "latency_ms": self.latency_ms, "version": self.version}


def _pkg_version(name: str) -> str:
    try:
        m = importlib.import_module(name)
        return str(getattr(m, "__version__", getattr(m, "version", "?")))
    except ImportError:
        return ""


def check_ollama(base_url: str, gateway=None) -> ComponentStatus:
    from llm.ollama_client import OllamaClient, OllamaUnavailable
    c = OllamaClient(base_url, gateway=gateway)
    t0 = time.monotonic()
    try:
        models = c.list_models()
        lat = int((time.monotonic() - t0) * 1000)
        if not models:
            return ComponentStatus("Ollama", "warn", "Сервер отвечает, но моделей нет",
                                   "Выполните: ollama pull <модель>. Список: ollama list", lat)
        return ComponentStatus("Ollama", "ok", f"{len(models)} модел(ей): {', '.join(models[:3])}",
                               "", lat)
    except OllamaUnavailable as e:
        return ComponentStatus("Ollama", "fail", str(e)[:200],
                               "Установите Ollama (ollama.com/download) и запустите: ollama serve",
                               None)


def check_vosk_model(model_path: str) -> ComponentStatus:
    ver = _pkg_version("vosk")
    if not ver:
        return ComponentStatus("Vosk STT", "fail", "Пакет vosk не установлен",
                               "pip install vosk")
    p = Path(model_path or "")
    if not p.is_dir():
        return ComponentStatus("Vosk STT", "warn", f"Модель не найдена: {p or 'не задан путь'}",
                               "Скачайте vosk-model-small-ru (~45 МБ) с alphacephei.com/vosk/models "
                               "и укажите папку в настройках → Голос", version=ver)
    if not (p / "am").exists() and not any(p.iterdir()):
        return ComponentStatus("Vosk STT", "warn", f"Папка есть, но модель внутри неполная: {p}",
                               "Распакуйте архив модели целиком в эту папку", version=ver)
    return ComponentStatus("Vosk STT", "ok", f"Модель: {p.name}", "", version=ver)


def check_audio_devices() -> ComponentStatus:
    try:
        import sounddevice as sd
    except Exception as e:
        return ComponentStatus("Аудио", "fail", f"sounddevice недоступен: {e}",
                               "pip install sounddevice (на Linux нужен libportaudio2)")
    try:
        devs = sd.query_devices()
    except Exception as e:
        return ComponentStatus("Аудио", "fail", f"ПортAudio не инициализирован: {e}",
                               "Проверьте звуковую подсистему ОС")
    ins = [d for d in devs if d.get("max_input_channels", 0) > 0]
    outs = [d for d in devs if d.get("max_output_channels", 0) > 0]
    if not ins and not outs:
        return ComponentStatus("Аудио", "warn", "Звуковых устройств не обнаружено",
                               "Голосовые функции будут задизейблены; текстовый чат работает.",
                               version=_pkg_version("sounddevice"))
    return ComponentStatus("Аудио", "ok", f"входов: {len(ins)}, выходов: {len(outs)}",
                           "", version=_pkg_version("sounddevice"))


def check_piper(bin_path: str, model_path: str) -> ComponentStatus:
    from tts.piper_engine import PiperEngine
    eng = PiperEngine(bin_path=bin_path, model_path=model_path)
    ver = _pkg_version("piper")
    if not eng.available():
        return ComponentStatus("Piper TTS", "fail", "Piper не найден (ни пакет, ни бинарь)",
                               "pip install piper-tts — или скачайте бинарь github.com/rhasspy/piper "
                               "и укажите путь в настройках. Без Piper работает резервный голос ОС.",
                               version=ver)
    voices = eng.voices()
    if not voices:
        return ComponentStatus("Piper TTS", "warn", "Движок есть, голоса не найдены",
                               "Скачайте русский .onnx голос (rhasspy/piper-voices на HuggingFace) "
                               "и укажите путь в настройках", version=ver)
    return ComponentStatus("Piper TTS", "ok", f"Голосов: {len(voices)} (первый: {voices[0].id})",
                           "", version=ver)


def check_workspace(root: str) -> ComponentStatus:
    p = Path(root)
    if p.is_dir():
        try:
            testf = p / ".write_test.tmp"
            testf.write_text("ok", encoding="utf-8")
            testf.unlink()
            return ComponentStatus("Рабочая папка", "ok", str(p))
        except OSError as e:
            return ComponentStatus("Рабочая папка", "fail", f"Нет прав на запись: {e}",
                                   "Выберите другую папку в настройках")
    return ComponentStatus("Рабочая папка", "warn", f"Не существует: {p}",
                           "Будет создана при первом действии; или выберите свою в настройках")


def run_all(settings: dict[str, Any], gateway=None) -> list[ComponentStatus]:
    """Внимание: вызывать вне GUI-потока (сетевые проверки)."""
    out = [
        check_ollama(settings.get("ollama.base_url", "http://127.0.0.1:11434"), gateway),
        check_vosk_model(settings.get("stt.model_path", "")),
        check_audio_devices(),
        check_piper(settings.get("voice.piper_bin", ""), settings.get("voice.piper_model", "")),
        check_workspace(settings.get("workspace.root", "")),
    ]
    mode = settings.get("network_mode", "offline")
    out.append(ComponentStatus(
        "Сеть", "ok" if mode != "online" else "warn",
        f"Режим: {mode.upper()}",
        "" if mode == "offline" else "Внешние запросы возможны только к явно настроенным хостам"))
    return out


def report_text(statuses: list[ComponentStatus]) -> str:
    lines = ["Отчёт о компонентах Computer Assistant", "=" * 40]
    for s in statuses:
        icon = {"ok": "[OK]  ", "warn": "[WARN]", "fail": "[FAIL]"}[s.status]
        lat = f" ({s.latency_ms} мс)" if s.latency_ms is not None else ""
        v = f" v{ s.version}" if s.version else ""
        lines.append(f"{icon} {s.name}{v}: {s.detail}{lat}")
        if s.action:
            lines.append(f"      → {s.action}")
    return "\n".join(lines)
