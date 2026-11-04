"""Пакет «Компьютер-ассистент»: голосовой HUD-ассистент для Windows (PySide6/QML).

Точка входа — app.main. Пакеты UI ничего не знают про Vosk/Piper/Ollama напрямую:
взаимодействие только через QObject-мосты (ui/bridge.py).
"""

__version__ = "0.1.0"
APP_NAME = "Computer Assistant"
APP_ORG = "computer-assistant"
