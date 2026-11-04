"""Чтение/запись документов в рабочей папке (TXT, MD, DOCX, PDF).

Честность: скан-PDF без текстового слоя → явный ответ «нужен OCR», а не пустой успех.
Лимиты размера и предупреждение об обрезке контекста — реальные, не декоративные.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tools.registry import PathEscape, safe_resolve


@dataclass
class DocRead:
    text: str
    kind: str            # txt | md | docx | pdf
    truncated: bool = False
    needs_ocr: bool = False
    warning: str = ""


MAX_BYTES_DEFAULT = 8 * 1024 * 1024
MAX_CHARS_CONTEXT = 60_000   # сколько текста отдаём в контекст LLM


def read_document(path_raw: str, roots: list[Path],
                  max_bytes: int = MAX_BYTES_DEFAULT) -> DocRead:
    p = safe_resolve(path_raw, roots, must_exist=True)
    size = p.stat().st_size
    if size > max_bytes:
        raise PathEscape(f"Файл {size/2**20:.1f} МБ превышает лимит {max_bytes/2**20:.0f} МБ")
    ext = p.suffix.lower()
    if ext in (".txt", ".md"):
        raw = p.read_text(encoding="utf-8", errors="replace")
        trunc = len(raw) > MAX_CHARS_CONTEXT
        return DocRead(raw[:MAX_CHARS_CONTEXT], "md" if ext == ".md" else "txt",
                       truncated=trunc,
                       warning=("Контекст обрезан до %d символов" % MAX_CHARS_CONTEXT) if trunc else "")
    if ext == ".docx":
        return _read_docx(p)
    if ext == ".pdf":
        return _read_pdf(p)
    raise PathEscape(f"Неподдерживаемый формат: {ext or 'без расширения'}")


def _read_docx(p: Path) -> DocRead:
    try:
        import docx  # python-docx
    except ImportError:
        raise PathEscape("Для чтения DOCX установите: pip install python-docx") from None
    d = docx.Document(str(p))
    text = "\n".join(par.text for par in d.paragraphs)
    trunc = len(text) > MAX_CHARS_CONTEXT
    return DocRead(text[:MAX_CHARS_CONTEXT], "docx", truncated=trunc,
                   warning="Контекст обрезан" if trunc else "")


def _read_pdf(p: Path) -> DocRead:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise PathEscape("Для чтения PDF установите: pip install pypdf") from None
    reader = PdfReader(str(p))
    parts = []
    for page in reader.pages[:80]:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    text = "\n".join(parts).strip()
    if not text:
        return DocRead("", "pdf", needs_ocr=True,
                       warning="В PDF нет извлекаемого текста — похоже на скан. Нужен OCR, "
                               "он в MVP не входит.")
    trunc = len(text) > MAX_CHARS_CONTEXT
    return DocRead(text[:MAX_CHARS_CONTEXT], "pdf", truncated=trunc,
                   warning="Контекст обрезан" if trunc else "")


def write_document(path_raw: str, content: str, roots: list[Path]) -> dict[str, str]:
    """Запись с бэкапом при перезаписи (те же правила, что у write_file)."""
    import time
    p = safe_resolve(path_raw, roots)
    backup = None
    if p.exists():
        backup = p.with_name(p.name + f".backup_{time.strftime('%Y%m%d_%H%M%S')}")
        backup.write_bytes(p.read_bytes())
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"written": str(p), "backup": str(backup) if backup else ""}


PROJECT_STRUCTURES: dict[str, list[str]] = {
    "python-cli": ["README.md", "requirements.txt", "src/main.py", "tests/test_smoke.py"],
    "python-app": ["README.md", "requirements.txt", "src/app.py", "src/config.py",
                   "tests/test_smoke.py"],
    "docs": ["README.md", "docs/notes.md"],
}


def propose_project_structure(kind: str) -> list[str]:
    return PROJECT_STRUCTURES.get(kind, PROJECT_STRUCTURES["docs"])
