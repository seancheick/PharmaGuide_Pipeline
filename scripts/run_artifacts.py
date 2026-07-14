"""Shared run identity and atomic report artifact helpers."""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def new_run_id() -> str:
    """Return a sortable, collision-resistant pipeline run identifier."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{timestamp}-{uuid.uuid4().hex[:12]}"


def ensure_run_id(run_id: str | None = None) -> str:
    candidate = run_id or new_run_id()
    if not isinstance(candidate, str) or not _RUN_ID_RE.fullmatch(candidate):
        raise ValueError(f"Invalid pipeline run ID: {candidate!r}")
    return candidate


def report_run_directory(report_root: Path, run_id: str) -> Path:
    """Return the isolated report directory for a validated run ID."""
    safe_run_id = ensure_run_id(run_id)
    directory = Path(report_root) / "runs" / safe_run_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def atomic_write_json(path: Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def atomic_write_text(path: Path, content: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
