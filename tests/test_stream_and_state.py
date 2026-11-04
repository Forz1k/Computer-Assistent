"""Тесты парсинга потоковых NDJSON-чанков Ollama (включая битые) и конечного автомата."""
from __future__ import annotations

import io
import json

import pytest

from core.state_machine import AppState, StateMachine
from llm.ollama_client import OllamaClient


class FakeResp(io.BytesIO):
    """Ответ, итерируемый по строкам как http.client.HTTPResponse."""

    def __iter__(self):
        for line in self.getvalue().split(b"\n"):
            yield line + b"\n"


def _client_with(lines: list[dict | str]) -> OllamaClient:
    body = b""
    for l in lines:
        body += (json.dumps(l, ensure_ascii=False) if isinstance(l, dict) else l).encode() + b"\n"
    c = OllamaClient.__new__(OllamaClient)  # без __init__: не трогаем сеть
    c.base_url = "http://127.0.0.1:11434"
    c.gateway = None
    c._open = lambda path, payload=None: FakeResp(body)  # type: ignore[assignment]
    return c


def test_stream_valid_chunks():
    c = _client_with([
        {"response": "При"},
        {"response": "вет!"},
        {"response": "", "done": True, "eval_count": 2, "eval_duration": 1_000_000_000},
    ])
    out = "".join(piece for piece, _ in c.generate_stream("m", "p"))
    assert out == "Привет!"


def test_stream_broken_json_skipped_not_crash():
    c = _client_with([
        {"response": "А"},
        "{битый json!!!",
        {"response": "Б"},
        {"response": "", "done": True},
    ])
    out = "".join(piece for piece, _ in c.generate_stream("m", "p"))
    assert out == "АБ"


def test_stream_cancel_flag_stops():
    flips = {"n": 0}

    def cancel():
        flips["n"] += 1
        return flips["n"] > 2  # отмена после пары чанков

    c = _client_with([
        {"response": "1"}, {"response": "2"}, {"response": "3"}, {"response": "4"},
        {"response": "", "done": True},
    ])
    got = [piece for piece, _ in c.generate_stream("m", "p", cancel_flag=cancel)]
    assert len(got) < 4, "отмена должна остановить выдачу до конца потока"


def test_ttft_measured():
    c = _client_with([{"response": "x"}, {"response": "", "done": True}])
    stats = None
    for _piece, stats in c.generate_stream("m", "p"):
        pass
    assert stats is not None and stats.ttft_s is not None and stats.ttft_s >= 0


class TestStateMachine:
    def test_boot_to_idle_allowed(self):
        sm = StateMachine()
        assert sm.state == AppState.BOOT
        sm.transition(AppState.IDLE)
        assert sm.state == AppState.IDLE

    def test_idle_to_listening(self):
        sm = StateMachine()
        sm.transition(AppState.IDLE)
        sm.transition(AppState.LISTENING)
        assert sm.state == AppState.LISTENING

    def test_error_returns_to_idle(self):
        sm = StateMachine()
        sm.transition(AppState.IDLE)
        sm.transition(AppState.ERROR)
        sm.transition(AppState.IDLE)
        assert sm.state == AppState.IDLE

    def test_illegal_transition_rejected_and_recorded(self):
        sm2 = StateMachine()
        sm2.transition(AppState.BOOT)
        sm2.transition(AppState.IDLE)
        sm2.transition(AppState.LISTENING)
        ok2 = sm2.transition(AppState.STREAMING)  # LISTENING сразу в STREAMING — запрещено
        assert ok2 is False
        assert sm2.state == AppState.LISTENING
        assert any("REJECTED" in h[2] for h in sm2.history)

    def test_wake_error_interrupt_any_state(self):
        """WAKE и ERROR разрешены как прерывание из любого состояния (кроме себя)."""
        sm = StateMachine()
        sm.transition(AppState.IDLE)
        assert sm.transition(AppState.WAKE) is True
        assert sm.transition(AppState.ERROR) is True

    def test_all_spec_states_defined(self):
        names = {s.value for s in AppState}
        for need in ("IDLE", "WAKE", "LISTENING", "THINKING",
                     "STREAMING", "SPEAKING", "ERROR", "MUTED"):
            assert need in names, f"нет состояния {need}"
