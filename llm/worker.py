"""LLM-воркер: тяжёлая генерация вне GUI-потока, с отменой и метриками.

QThread + явная остановка; сигнал finished delivers stats. Одна тяжёлая
генерация одновременно (защита через isBusy).
"""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal, Slot

from core.events import EventBus
from core.state_machine import AppState
from llm.ollama_client import OllamaClient, OllamaUnavailable, OllamaError


class LLMWorker(QThread):
    token = Signal(str, str)        # request_id, chunk
    finished_ok = Signal(str, dict)  # request_id, meta
    failed = Signal(str, str)        # request_id, понятный текст ошибки

    def __init__(self, client: OllamaClient, bus: EventBus, parent=None) -> None:
        super().__init__(parent)
        self.client = client
        self.bus = bus
        self._job: tuple[str, str, str, str, int] | None = None  # req,prompt,system,model,num_ctx
        self._cancel = False

    @Slot(str, str, str, str, int)
    def submit(self, request_id: str, prompt: str, system: str, model: str, num_ctx: int) -> None:
        if self.isRunning():
            self.failed.emit(request_id, "Уже выполняется одна генерация — подождите или нажмите «Стоп».")
            return
        self._job = (request_id, prompt, system, model, num_ctx)
        self._cancel = False
        self.start()

    @Slot()
    def stop(self) -> None:
        self._cancel = True

    def run(self) -> None:  # QThread entry
        if not self._job:
            return
        req_id, prompt, system, model, num_ctx = self._job
        stats = None
        try:
            got_any = False
            for chunk, stats in self.client.generate_stream(
                    model, prompt, system, num_ctx,
                    cancel_flag=lambda: self._cancel):
                got_any = True
                self.token.emit(req_id, chunk)
            if self._cancel:
                self.finished_ok.emit(req_id, {"cancelled": True})
                return
            meta = {"ttft_ms": round((stats.ttft_s or 0) * 1000), "tps": stats.tokens_per_s,
                    "tokens": stats.total_tokens, "cancelled": False}
            self.finished_ok.emit(req_id, meta)
            if not got_any:
                self.failed.emit(req_id, "Модель вернула пустой ответ.")
        except OllamaUnavailable as e:
            self.failed.emit(req_id, str(e))
        except OllamaError as e:
            self.failed.emit(req_id, str(e))
        except Exception as e:  # не роняем приложение
            self.failed.emit(req_id, f"Сбой генерации: {type(e).__name__}: {e}")
