"""Persistent sandbox snapshot metadata."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


SANDBOXES_DIR = Path.home() / ".ohmycode" / "sandboxes"


def _ensure_dir() -> None:
    SANDBOXES_DIR.mkdir(parents=True, exist_ok=True)


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return slug or "sandbox"


def _metadata_path(session_name: str) -> Path:
    return SANDBOXES_DIR / f"{_slug(session_name)}.json"


def sandbox_archive_path(session_name: str) -> Path:
    _ensure_dir()
    return SANDBOXES_DIR / f"{_slug(session_name)}.tar"


def save_sandbox_snapshot(
    session_name: str,
    archive_path: Path,
    image_ref: str,
    sandbox_config: dict[str, Any],
) -> Path:
    _ensure_dir()
    metadata = {
        "session_name": session_name,
        "archive_path": str(archive_path),
        "image_ref": image_ref,
        "sandbox_config": sandbox_config,
        "saved_at": datetime.now().isoformat(),
    }
    path = _metadata_path(session_name)
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_sandbox_snapshot(session_name: str) -> dict[str, Any] | None:
    path = _metadata_path(session_name)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
