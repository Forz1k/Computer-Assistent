"""Сетевой шлюз — ЕДИНСТВЕННОЕ место, откуда разрешены исходящие запросы.

Режимы: OFFLINE (только loopback), HYBRID (петлобэк + явно включённые функции),
ONLINE (настроенные внешние эндпоинты). Все попытки блокируются и пишутся в аудит.

Для HTTP-клиентов шлюз даёт валидатор allow_host() перед запросом; также можно
использовать guarded_urlopen / guarded_create_connection как нижний уровень.
"""
from __future__ import annotations

import ipaddress
import socket
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urlparse

OFFLINE = "offline"
HYBRID = "hybrid"
ONLINE = "online"


def is_loopback_host(host: str) -> bool:
    """True для 127.0.0.0/8, ::1, localhost."""
    h = host.strip().lower().strip("[]")
    if h == "localhost":
        return True
    try:
        return ipaddress.ip_address(h).is_loopback
    except ValueError:
        return False


@dataclass
class AuditRecord:
    ts: float
    mode: str
    target: str
    allowed: bool
    reason: str
    request_id: str = ""


@dataclass
class NetworkGateway:
    """Политика исходящего трафика + журнал аудита (в памяти; persistence — у memory)."""

    mode: str = OFFLINE
    # В HYBRID/ONLINE: явные разрешения по хосту (выданные пользователем в настройках)
    allowed_hosts: set[str] = field(default_factory=set)
    audit: list[AuditRecord] = field(default_factory=list)
    _show_first_confirm: bool = True

    def set_mode(self, mode: str) -> None:
        if mode not in (OFFLINE, HYBRID, ONLINE):
            raise ValueError(f"Неизвестный сетевой режим: {mode}")
        self.mode = mode

    def check(self, url_or_host: str, request_id: str = "") -> tuple[bool, str]:
        """Разрешён ли запрос? Возвращает (allowed, reason). Пишет аудит."""
        target = self._normalize(url_or_host)
        host = urlparse("//" + target).hostname or target
        allowed, reason = self._decide(host)
        self.audit.append(AuditRecord(
            ts=time.time(), mode=self.mode, target=target,
            allowed=allowed, reason=reason,
            request_id=request_id or uuid.uuid4().hex[:8],
        ))
        if len(self.audit) > 2000:
            del self.audit[:1000]
        return allowed, reason

    def _decide(self, host: str) -> tuple[bool, str]:
        if is_loopback_host(host):
            return True, "loopback"
        if self.mode == OFFLINE:
            return False, "Заблокировано: режим OFFLINE разрешает только loopback"
        if host.lower() in {h.lower() for h in self.allowed_hosts}:
            return True, "host explicitly allowed by user"
        if self.mode == HYBRID:
            return False, "HYBRID: внешний хост не включён пользователем явно"
        # ONLINE: всё ещё требуем, чтобы хост был настроен (base_url/search_url)
        return False, "ONLINE: хост не настроен в разделе «Сеть»"

    @staticmethod
    def _normalize(s: str) -> str:
        s = s.strip()
        if "://" in s:
            p = urlparse(s)
            host = p.hostname or ""
            port = f":{p.port}" if p.port else ""
            return host + port
        return s

    # ---------- интеграция с httpx/requests/socket ----------
    def validator(self) -> Callable[[str], None]:
        def _v(url: str) -> None:
            ok, reason = self.check(url)
            if not ok:
                raise PermissionError(f"NetworkGateway: {reason} ({url})")
        return _v


class GuardedConnection:
    """socket.create_connection с проверкой через шлюз (для низкоуровневых клиентов)."""

    def __init__(self, gateway: NetworkGateway) -> None:
        self.gw = gateway

    def create_connection(self, address: Any, **kw: Any) -> socket.socket:
        host = address[0]
        ok, reason = self.gw.check(f"{host}:{address[1]}" if len(address) > 1 else str(host))
        if not ok:
            raise PermissionError(f"NetworkGateway: {reason}")
        return socket.create_connection(address, **kw)
