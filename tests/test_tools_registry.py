"""Тесты реестра инструментов: песочница путей, подтверждения, бэкапы, аудит."""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.registry import PathEscape, ToolError, ToolRegistry, safe_resolve


def test_safe_resolve_blocks_dotdot(workspace: Path):
    outside = workspace.parent / "secret.txt"
    outside.write_text("nope")
    with pytest.raises(PathEscape):
        safe_resolve("../secret.txt", [workspace], must_exist=True)


def test_safe_resolve_blocks_absolute_outside(workspace: Path):
    with pytest.raises(PathEscape):
        safe_resolve("/etc/passwd", [workspace])


def test_safe_resolve_blocks_symlink_escape(workspace: Path):
    real_outside = workspace.parent / "outside_dir"
    real_outside.mkdir()
    (real_outside / "victim.txt").write_text("data")
    link = workspace / "link"
    try:
        link.symlink_to(real_outside)
    except OSError:
        pytest.skip("симлинки недоступны в этой среде")
    with pytest.raises(PathEscape):
        safe_resolve(str(link / "victim.txt"), [workspace], must_exist=True)


@pytest.mark.skipif(True, reason="placeholder")
def _unused():
    pass


def test_unc_blocked(workspace: Path):
    with pytest.raises(PathEscape):
        safe_resolve("\\\\server\\share\\x.txt", [workspace])


def test_empty_path_blocked(workspace: Path):
    with pytest.raises(PathEscape):
        safe_resolve("   ", [workspace])


def test_inside_root_ok(workspace: Path):
    (workspace / "a.txt").write_text("hi")
    p = safe_resolve("a.txt", [workspace], must_exist=True)
    assert p == (workspace / "a.txt").resolve()


def test_confirmation_required_for_open_app(workspace: Path):
    reg = ToolRegistry(workspace)
    res = reg.execute("open_app", {"alias": "браузер"}, confirmed=False)
    assert res["status"] == "needs_confirmation"
    # неподтверждённое действие не попало в исполнение как ok
    assert reg.audit[-1]["confirmed"] is False


def test_write_file_creates_backup_on_overwrite(workspace: Path):
    reg = ToolRegistry(workspace)
    f = workspace / "notes.txt"
    f.write_text("v1")
    res = reg.execute("write_file", {"path": "notes.txt", "content": "v2"}, confirmed=True)
    assert res["status"] == "ok"
    assert f.read_text() == "v2"
    backups = list(workspace.glob("notes.txt.backup_*"))
    assert len(backups) == 1
    assert backups[0].read_text() == "v1"


def test_write_new_file_no_backup(workspace: Path):
    reg = ToolRegistry(workspace)
    res = reg.execute("write_file", {"path": "new.txt", "content": "x"}, confirmed=True)
    assert res["status"] == "ok" and res.get("backup") is None


def test_write_outside_workspace_rejected(workspace: Path):
    reg = ToolRegistry(workspace)
    res = reg.execute("write_file", {"path": "../../evil.txt", "content": "x"}, confirmed=True)
    assert res["status"] == "error"
    assert not (workspace.parent / "evil.txt").exists()


def test_unknown_tool_raises(workspace: Path):
    reg = ToolRegistry(workspace)
    with pytest.raises(ToolError):
        reg.spec("rm_rf_everything")


def test_url_scheme_validation(workspace: Path):
    reg = ToolRegistry(workspace)
    res = reg.execute("open_url", {"url": "file:///C:/Windows/x"}, confirmed=True)
    assert res["status"] == "error"


def test_audit_records_every_action(workspace: Path):
    reg = ToolRegistry(workspace)
    reg.execute("system_info", {}, request_id="req-1")
    last = reg.audit[-1]
    assert last["tool"] == "system_info"
    assert last["request_id"] == "req-1"
    assert last["status"] in ("ok", "error")


def test_json_schema_lists_only_registered(workspace: Path):
    reg = ToolRegistry(workspace)
    schema = reg.json_schema()
    assert "open_app" in schema["properties"]["tool"]["enum"]
    assert "eval" not in schema["properties"]["tool"]["enum"]
