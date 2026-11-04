"""Клиент Ollama (реальный HTTP API: /api/tags, /api/generate streaming).

Никаких выдуманных моделей: список берётся из /api/tags. Отмена — закрытие
стримингового соединения. TTFT и токены/сек измеряются фактически.
Ленивый импорт httpx — вне GUI-потока при импорте модуля это безопасно.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import AsyncIterator, Iterator, Protocol


class GatewayLike(Protocol):
    def check(self, url: str, request_id: str = "") -> tuple[bool, str]: ...


class OllamaError(RuntimeError):
    pass


class OllamaUnavailable(OllamaError):
    pass


@dataclass
class GenStats:
    ttft_s: float | None = None
    tokens_per_s: float | None = None
    total_tokens: int = 0
    elapsed_s: float = 0.0


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434",
                 gateway: GatewayLike | None = None, timeout_s: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.gateway = gateway
        self.timeout_s = timeout_s

    # ---- низкоуровневый HTTP: urllib (без внешних зависимостей) ----
    def _open(self, path: str, payload: dict | None = None):
        import urllib.error
        import urllib.request

        url = self.base_url + path
        if self.gateway is not None:
            ok, reason = self.gateway.check(url)
            if not ok:
                raise OllamaUnavailable(f"Шлюз заблокировал запрос к {url}: {reason}")
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json"})
        try:
            return urllib.request.urlopen(req, timeout=min(self.timeout_s, 5.0) if data is None else self.timeout_s)
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            raise OllamaUnavailable(f"Ollama недоступен по адресу {url}: {e}") from e

    def is_available(self) -> bool:
        try:
            with self._open("/api/tags"):
                return True
        except OllamaUnavailable:
            return False

    def list_models(self) -> list[str]:
        """Реальные установленные модели."""
        with self._open("/api/tags") as r:
            body = json.loads(r.read().decode("utf-8"))
        return [m.get("name", "") for m in body.get("models", []) if m.get("name")]

    def generate_stream(self, model: str, prompt: str, system: str = "",
                        num_ctx: int = 4096, keep_alive: str = "5m",
                        cancel_flag=None) -> Iterator[tuple[str, GenStats]]:
        """Генерация с потоковой выдачей токенов.

        yield (текст_чанка, статистика). cancel_flag — callable()->bool.
        Протокол /api/generate: NDJSON, поля response/done.
        """
        stats = GenStats()
        t0 = time.monotonic()
        payload = {
            "model": model, "prompt": prompt, "stream": True,
            "system": system or None,
            "options": {"num_ctx": num_ctx},
            "keep_alive": keep_alive,
        }
        with self._open("/api/generate", payload) as resp:
            for raw in resp:
                if cancel_flag and cancel_flag():
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    # битый чанк — пропускаем, не падаем (тест на это есть)
                    continue
                piece = obj.get("response", "")
                if piece:
                    if stats.ttft_s is None:
                        stats.ttft_s = time.monotonic() - t0
                    stats.total_tokens += 1
                    yield piece, stats
                if obj.get("done"):
                    ev = obj.get("eval_count")
                    ev_dur = obj.get("eval_duration")
                    if ev and ev_dur:
                        stats.tokens_per_s = round(ev / (ev_dur / 1e9), 2)
                    break
        stats.elapsed_s = time.monotonic() - t0
        if stats.tokens_per_s is None and stats.total_tokens and stats.elapsed_s > 0:
            stats.tokens_per_s = round(stats.total_tokens / stats.elapsed_s, 2)
