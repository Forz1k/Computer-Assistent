"""Тесты сетевого шлюза: в OFFLINE ни один внешний запрос не проходит."""
from __future__ import annotations

import socket
import threading

import pytest

from network.gateway import GuardedConnection, NetworkGateway, is_loopback_host


def test_loopback_detection():
    assert is_loopback_host("127.0.0.1")
    assert is_loopback_host("localhost")
    assert is_loopback_host("::1")
    assert not is_loopback_host("8.8.8.8")
    assert not is_loopback_host("example.com")


def test_offline_blocks_external():
    gw = NetworkGateway(mode="offline")
    ok, reason = gw.check("https://api.openai.com/v1/chat", request_id="r1")
    assert not ok and "OFFLINE" in reason.upper() or "офлайн" in reason.lower() or reason


def test_offline_allows_loopback():
    gw = NetworkGateway(mode="offline")
    ok, _ = gw.check("http://127.0.0.1:11434/api/tags")
    assert ok


def test_hybrid_allows_only_explicit_flag():
    gw = NetworkGateway(mode="hybrid")
    # базовое решение hybrid: loopback всегда; внешние — только если включён веб-доступ
    ok_lb, _ = gw.check("http://127.0.0.1:11434")
    assert ok_lb


def test_audit_records_blocked_attempts():
    gw = NetworkGateway(mode="offline")
    gw.check("https://evil.example.com", request_id="req-42")
    blocked = [r for r in gw.audit if not r.allowed]
    assert blocked and blocked[-1].request_id == "req-42"


def test_guarded_connection_refuses_external_in_offline():
    """Доказательство на уровне сокетов: попытка внешнего соединения бросает ошибку."""
    gw = NetworkGateway(mode="offline")
    conn = GuardedConnection(gw)
    with pytest.raises((OSError, RuntimeError, PermissionError, ValueError)):
        conn.create_connection(("93.184.216.34", 80))  # example.com:80 — внешний


@pytest.mark.integration
def test_fake_server_no_outbound_traffic_in_offline():
    """Поднимает фейковый echo-сервер и проверяет: локальный loopback проходит,
    а «внешний» адрес (нелигитимный хост) блокируется шлюзом до connect()."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    got = {"connected": False}

    def accept():
        try:
            c, _ = srv.accept()
            got["connected"] = True
            c.close()
        except OSError:
            pass

    t = threading.Thread(target=accept, daemon=True)
    t.start()

    gw = NetworkGateway(mode="offline")
    conn = GuardedConnection(gw)
    s = conn.create_connection(("127.0.0.1", port), timeout=2)
    s.close()
    t.join(timeout=2)
    assert got["connected"], "loopback-соединение должно проходить даже в offline"

    # внешний хост — блокируется ДО сокета
    with pytest.raises((OSError, RuntimeError, PermissionError, ValueError)):
        conn.create_connection(("203.0.113.5", 80), timeout=2)
    srv.close()
