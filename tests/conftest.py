"""Общие фикстуры тестов. Никакого железа не требуется — всё мокается."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# корень проекта в sys.path (для запуска pytest из любой директории)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws
