"""Оркестратор диалога: единая шина событий + конечный автомат.

Потоки-воркеры (LLM, аудио) общаются с UI ТОЛЬКО через сигналы этого объекта.
Отмена сквозная: cancel() останавливает генерацию и очередь речи.
"""
from __future__ import annotations

import uuid
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot, Property, QTimer

from core.state_machine import AppState, StateMachine


class EventBus(QObject):
    """Сигналы для QML-моста."""

    stateChanged = Signal(str, str)          # new_state, reason
    interimText = Signal(str)                # живой сериализованный partial STT
    finalText = Signal(str)                  # финальная распознанная фраза
    replyStarted = Signal(str)               # message id / request id
    replyToken = Signal(str, str)            # request_id, token chunk
    replyFinished = Signal(str, dict)        # request_id, meta {ttft, tps}
    toolEvent = Signal(dict)                 # карточка инструмента/подтверждения
    error = Signal(str)                      # текст ошибки
    statusTick = Signal(dict)                # нижняя строка состояния
    confirmRequested = Signal(dict)          # модальный лист подтверждения
    bootComponent = Signal(str, str)         # имя компонента, статус ok/warn/fail


class Orchestrator(QObject):
    def __init__(self, bus: EventBus, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.bus = bus
        self.sm = StateMachine()
        self._cancel_flag = False
        self._current_req = ""

    # ---- состояние ----
    def set_state(self, s: AppState, reason: str = "") -> bool:
        ok = self.sm.transition(s, reason)
        if ok:
            self.bus.stateChanged.emit(s.value, reason)
        return ok

    state = Property(str, lambda: self.sm.state.value, notify=lambda: None)

    # ---- отмена (из UI в любом потоке — слот) ----
    @Slot()
    def cancel(self) -> None:
        self._cancel_flag = True
        self.set_state(AppState.IDLE, "user-cancel")

    def cancelled(self) -> bool:
        return self._cancel_flag

    def new_request(self) -> str:
        self._cancel_flag = False
        self._current_req = uuid.uuid4().hex[:10]
        return self._current_req

    @property
    def request_id(self) -> str:
        return self._current_req
