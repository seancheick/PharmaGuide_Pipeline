"""Candidate reports may only claim gates backed by successful command logs."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from audits.generate_candidate_report import (  # noqa: E402
    REQUIRED_VERIFICATION_GATES,
    _artifact_hashes,
    _validated_verification,
)


def _payload(tmp_path: Path) -> dict:
    gates = {}
    for name in REQUIRED_VERIFICATION_GATES:
        log = tmp_path / f"{name}.log"
        log.write_text(f"{name}: passed\n", encoding="utf-8")
        gates[name] = {
            "command": f"run {name}",
            "exit_code": 0,
            "log": str(log),
            "summary": "passed",
        }
    return {"schema_version": "1.0.0", "gates": gates}


def test_verification_requires_every_release_gate(tmp_path: Path) -> None:
    payload = _payload(tmp_path)
    payload["gates"].pop(REQUIRED_VERIFICATION_GATES[0])
    path = tmp_path / "verification.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="missing required gate"):
        _validated_verification(path)


def test_verification_rejects_nonzero_exit_code(tmp_path: Path) -> None:
    payload = _payload(tmp_path)
    payload["gates"][REQUIRED_VERIFICATION_GATES[0]]["exit_code"] = 1
    path = tmp_path / "verification.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="did not pass"):
        _validated_verification(path)


def test_verification_hashes_each_preserved_log(tmp_path: Path) -> None:
    payload = _payload(tmp_path)
    path = tmp_path / "verification.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    verified = _validated_verification(path)

    for gate in verified["gates"].values():
        log_bytes = Path(gate["log"]).read_bytes()
        assert gate["log_sha256"] == hashlib.sha256(log_bytes).hexdigest()


def test_artifact_hashes_include_interaction_database_and_manifest(
    tmp_path: Path,
) -> None:
    for name in (
        "pharmaguide_core.db",
        "export_manifest.json",
        "detail_index.json",
        "interaction_db.sqlite",
        "interaction_db_manifest.json",
    ):
        (tmp_path / name).write_bytes(name.encode("utf-8"))

    hashes = _artifact_hashes(tmp_path)

    assert "interaction_database_sha256" in hashes
    assert "interaction_database_manifest_sha256" in hashes
