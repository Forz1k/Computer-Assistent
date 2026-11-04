"""Конечный автомат состояний ассистента (единый для UI и бэкенда).

Состояния соответствуют дизайн-спецификации (раздел 3.4). Переходы валидируются,
недопустимые переходы логируются и игнорируются (кроме ERROR/WAKE, которые
достижимы из любого состояния).
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field


class AppState(enum.Enum):
    BOOT = "BOOT"
    IDLE = "IDLE"
    WAKE = "WAKE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    STREAMING = "STREAMING"
    SPEAKING = "SPEAKING"
    ERROR = "ERROR"
    MUTED = "MUTED"


# Разрешённые переходы. WAKE/ERROR/MUTED добавляются отдельно (из любого).
_ALLOWED: dict[AppState, set[AppState]] = {
    AppState.BOOT: {AppState.IDLE, AppState.ERROR},
    AppState.IDLE: {AppState.LISTENING, AppState.THINKING, AppState.STREAMING,
                    AppState.SPEAKING, AppState.MUTED, AppState.ERROR},
    AppState.WAKE: {AppState.LISTENING, AppState.IDLE, AppState.MUTED, AppState.ERROR},
    AppState.LISTENING: {AppState.THINKING, AppState.IDLE, AppState.WAKE,
                         AppState.MUTED, AppState.ERROR},
    AppState.THINKING: {AppState.STREAMING, AppState.SPEAKING, AppState.IDLE,
                        AppState.MUTED, AppState.ERROR},
    AppState.STREAMING: {AppState.SPEAKING, AppState.THINKING, AppState.IDLE,
                         AppState.MUTED, AppState.ERROR},
    AppState.SPEAKING: {AppState.LISTENING, AppState.IDLE, AppState.THINKING,
                        AppState.MUTED, AppState.ERROR},
    AppState.ERROR: {AppState.IDLE, AppState.LISTENING, AppState.THINKING,
                     AppState.MUTED},
    AppState.MUTED: {AppState.IDLE, AppState.LISTENING, AppState.THINKING,
                     AppState.STREAMING, AppState.SPEAKING, AppState.WAKE,
                     AppState.ERROR},
}

_ALWAYS_ALLOWED = {AppState.WAKE, AppState.ERROR}


@dataclass
class StateMachine:
    """Простая машина состояний с историей переходов (для диагностики/тестов)."""

    state: AppState = AppState.BOOT
    reason: str = ""
    history: list[tuple[str, str, str]] = field(default_factory=list)

    def can(self, target: AppState) -> bool:
        if target in _ALWAYS_ALLOWED or target == self.state:
            return True
        # Из BOOT в IDLE; WAKE доступен из LISTENING/MUTED как «снова проснулись»
        if target in _ALLOWED.get(self.state, set()):
            return True
        return False

    def transition(self, target: AppState, reason: str = "") -> bool:
        """Возвращает True, если переход выполнен."""
        if not self.can(target):
            self.history.append((self.state.value, target.value, f"REJECTED:{reason}"))
            return False
        prev = self.state
        self.state = target
        self.reason = reason
        self.history.append((prev.value, target.value, reason))
        return True
