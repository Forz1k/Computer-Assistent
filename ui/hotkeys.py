"""Глобальная горячая клавиша PTT для Windows через RegisterHotKey (ctypes).

Без прав администратора, без низкоуровневых хуков (их блокируют антивирусы).
Реализация: скрытое окно сообщений + поток с GetMessageW. Если регистрация
не удалась (клавиша занята другим приложением) — честно логируем и молча
отключаемся; кнопка PTT в UI продолжает работать.
"""
from __future__ import annotations

import ctypes
import logging
import threading
from ctypes.wintypes import BOOL, DWORD, HANDLE, HWND, MSG
from typing import Callable

log = logging.getLogger("ui.hotkeys")

MOD_CONTROL = 0x0002
MOD_ALT = 0x0008
MOD_NOREPEAT = 0x4000
VK_SPACE = 0x20
WM_HOTKEY = 0x0312
WM_DESTROY = 0x0002
PM_REMOVE = 1

HOTKEY_ID = 0xB001


class WinHotkey:
    """Регистрирует Ctrl+Alt+Space (или иную комбинацию) глобально."""

    def __init__(self, hwnd_owner: int, on_down: Callable[[], None],
                 on_up: Callable[[], None]) -> None:
        self._hwnd_owner = int(hwnd_owner)
        self._on_down = on_down
        self._on_up = on_up
        self._thread: threading.Thread | None = None
        self._stop: threading.Event | None = None
        self._registered = False

    def register_default(self, vk: int = VK_SPACE, mods: int = MOD_CONTROL | MOD_ALT | MOD_NOREPEAT) -> bool:
        return self.register(vk, mods)

    def register(self, vk: int, mods: int) -> bool:
        if self._registered:
            return True
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

            WNDPROC = ctypes.WINFUNCTYPE(LRESULT := ctypes.c_long, HWND, UINT := ctypes.c_uint,
                                         WPARAM := ctypes.c_ulonglong, LPARAM := ctypes.c_long)

            class _Wnd:
                def __init__(self) -> None:
                    self.hwnd = None
                    self.cb = WNDPROC(self._proc)

                def _proc(self, h, msg_, w, l):  # noqa: ANN001
                    if msg_ == WM_HOTKEY and int(w) == HOTKEY_ID:
                        # flags в lParam bit 4: keyUp
                        key_up = bool(int(l) & 0x10)
                        cb = self._on_up if key_up else self._on_down
                        try:
                            cb()
                        except Exception:  # noqa: BLE001
                            log.exception("hotkey callback error")
                        return 0
                    if msg_ == WM_DESTROY:
                        user32.PostQuitMessage(0)
                        return 0
                    return user32.DefWindowProcW(h, msg_, w, l)

            wnd = _Wnd()
            self._wnd = wnd
            self._user32 = user32

            atom = user32.RegisterClassW(None, wnd.cb, 0, 0, 0, None, None, None, None,
                                         None, "JarvisHotkeyWnd")
            if not atom:
                raise OSError(ctypes.get_last_error())
            hwnd = user32.CreateWindowExW(0, atom, "hotkeys", 0, 0, 0, 0, 0,
                                          None, None, kernel32.GetModuleHandleW(None), None)
            if not hwnd:
                raise OSError(ctypes.get_last_error())
            wnd.hwnd = hwnd
            if not user32.RegisterHotKey(hwnd, HOTKEY_ID, mods, vk):
                raise OSError(ctypes.get_last_error())
            self._registered = True

            self._stop = threading.Event()

            def loop() -> None:
                msg = MSG()
                while not self._stop.is_set():
                    r = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                    if r in (0, -1):
                        break
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                user32.UnregisterHotKey(hwnd, HOTKEY_ID)
                user32.DestroyWindow(hwnd)

            self._thread = threading.Thread(target=loop, name="hotkey-loop", daemon=True)
            self._thread.start()
            log.info("Горячая клавиша PTT зарегистрирована (Ctrl+Alt+Space)")
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("Не удалось зарегистрировать горячую клавишу: %s — используйте кнопку PTT в UI", exc)
            self._registered = False
            return False

    def unregister(self) -> None:
        if self._stop is not None:
            self._stop.set()
        if getattr(self, "_wnd", None) and getattr(self, "_user32", None):
            try:
                self._user32.PostThreadMessageW(DWORD(threading.get_native_id()), WM_DESTROY, 0, 0)
            except Exception:  # noqa: BLE001
                pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._registered = False
