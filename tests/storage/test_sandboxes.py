from __future__ import annotations

from pathlib import Path

import ohmycode.storage.sandboxes as sand_mod
from ohmycode.storage.sandboxes import load_sandbox_snapshot, save_sandbox_snapshot


def test_save_and_load_sandbox_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(sand_mod, "SANDBOXES_DIR", tmp_path)

    archive = tmp_path / "demo.tar"
    archive.write_text("tar")
    save_sandbox_snapshot(
        session_name="20260403-abcdef12",
        archive_path=archive,
        image_ref="ohmycode-sandbox:demo",
        sandbox_config={"image": "python:3.11-slim"},
    )

    snapshot = load_sandbox_snapshot("20260403-abcdef12")

    assert snapshot is not None
    assert snapshot["session_name"] == "20260403-abcdef12"
    assert snapshot["image_ref"] == "ohmycode-sandbox:demo"
    assert Path(snapshot["archive_path"]).name == "demo.tar"


def test_load_sandbox_snapshot_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(sand_mod, "SANDBOXES_DIR", tmp_path)
    assert load_sandbox_snapshot("missing-session") is None
