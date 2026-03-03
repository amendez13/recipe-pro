import os
import stat
import time
from pathlib import Path


os.environ.setdefault("RECIPE_PRO_SESSION_SECRET", "test-secret")

from app.app import _save_import_debug_snapshot


def test_import_debug_snapshot_disabled_by_default(tmp_path, monkeypatch):
    debug_dir = tmp_path / "snapshots"
    monkeypatch.delenv("RECIPE_PRO_IMPORT_DEBUG_SNAPSHOTS", raising=False)
    monkeypatch.setenv("RECIPE_PRO_IMPORT_DEBUG_DIR", str(debug_dir))

    snapshot = _save_import_debug_snapshot("flow123", "https://example.com", "page text", "prompt text")

    assert snapshot is None
    assert not debug_dir.exists()


def test_import_debug_snapshot_uses_private_permissions_and_prunes_old_files(tmp_path, monkeypatch):
    debug_dir = tmp_path / "snapshots"
    debug_dir.mkdir(parents=True, exist_ok=True)
    old_file = debug_dir / "old.page_text.txt"
    old_file.write_text("old", encoding="utf-8")
    old_time = time.time() - 3600
    os.utime(old_file, (old_time, old_time))

    monkeypatch.setenv("RECIPE_PRO_IMPORT_DEBUG_SNAPSHOTS", "1")
    monkeypatch.setenv("RECIPE_PRO_IMPORT_DEBUG_DIR", str(debug_dir))
    monkeypatch.setenv("RECIPE_PRO_IMPORT_DEBUG_RETENTION_SECONDS", "1")

    snapshot = _save_import_debug_snapshot("flow456", "https://example.com/r", "page text", "prompt text")

    assert snapshot is not None
    assert snapshot["pruned_files"] >= 1
    assert not old_file.exists()

    text_path = Path(snapshot["text_path"])
    prompt_path = Path(snapshot["prompt_path"])
    meta_path = Path(snapshot["meta_path"])
    assert text_path.exists()
    assert prompt_path.exists()
    assert meta_path.exists()

    assert stat.S_IMODE(debug_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(text_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(prompt_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(meta_path.stat().st_mode) == 0o600
