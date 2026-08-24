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
    _manifest_report_date,
    _validated_verification,
    render_markdown,
)
from audits.run_verification_gate import run_gate  # noqa: E402


def _payload(tmp_path: Path) -> dict:
    gates = {}
    for name in REQUIRED_VERIFICATION_GATES:
        log = tmp_path / f"{name}.log"
        receipt = tmp_path / f"{name}.receipt.json"
        assert run_gate(
            name=name,
            command=[sys.executable, "-c", f"print('{name}: passed')"],
            log_path=log,
            receipt_path=receipt,
            cwd=tmp_path,
        ) == 0
        gates[name] = {"receipt": str(receipt)}
    return {"schema_version": "2.0.0", "gates": gates}


def test_verification_requires_every_release_gate(tmp_path: Path) -> None:
    payload = _payload(tmp_path)
    payload["gates"].pop(REQUIRED_VERIFICATION_GATES[0])
    path = tmp_path / "verification.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="missing required gate"):
        _validated_verification(path)


def test_verification_rejects_nonzero_exit_code(tmp_path: Path) -> None:
    payload = _payload(tmp_path)
    name = REQUIRED_VERIFICATION_GATES[0]
    receipt = tmp_path / f"{name}.failed.receipt.json"
    assert run_gate(
        name=name,
        command=[sys.executable, "-c", "raise SystemExit(1)"],
        log_path=tmp_path / f"{name}.failed.log",
        receipt_path=receipt,
        cwd=tmp_path,
    ) == 1
    payload["gates"][name] = {"receipt": str(receipt)}
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
        assert gate["receipt_file_sha256"]


def test_verification_rejects_hand_authored_exit_code_without_receipt(
    tmp_path: Path,
) -> None:
    payload = _payload(tmp_path)
    name = REQUIRED_VERIFICATION_GATES[0]
    payload["gates"][name] = {
        "command": "pretend release passed",
        "exit_code": 0,
        "log": str(tmp_path / f"{name}.log"),
    }
    path = tmp_path / "verification.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="machine-generated receipt"):
        _validated_verification(path)


def test_verification_rejects_log_changed_after_receipt(tmp_path: Path) -> None:
    payload = _payload(tmp_path)
    name = REQUIRED_VERIFICATION_GATES[0]
    receipt = Path(payload["gates"][name]["receipt"])
    receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
    Path(receipt_payload["log"]).write_text("different output\n", encoding="utf-8")
    path = tmp_path / "verification.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="log hash mismatch"):
        _validated_verification(path)


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


def test_report_date_uses_canonical_generated_at_manifest_field() -> None:
    assert _manifest_report_date(
        {"generated_at": "2026-08-23T18:41:26.360840+00:00"}
    ) == "2026-08-23"


def test_report_date_retains_legacy_exported_at_compatibility() -> None:
    assert _manifest_report_date(
        {"exported_at": "2026-08-22T00:00:00Z"}
    ) == "2026-08-22"


def test_markdown_title_uses_artifact_report_date() -> None:
    report = {
        "report_date": "2026-08-23",
        "repositories": {
            "pipeline": {
                "branch": "codex/test",
                "source_head_at_generation": "a" * 40,
                "dirty": False,
            }
        },
        "candidate": {
            "live_product_count": 1,
            "detail_blob_count": 1,
            "verdict_counts": {"SAFE": 1},
        },
        "release_contract": {
            "export_schema_version": "2.4.0",
            "scoring_version": "4.3.0",
            "db_version": "test",
        },
        "quarantine": {
            "total": 12,
            "groups": {"safety_policy_review_required": 12},
        },
        "artifact_hashes": {"candidate_database_sha256": "b" * 64},
        "pending_clinical_signoff": {
            "us_policy_holds": [],
            "withheld_clinical_records": {
                "medication_depletions": {
                    "published": 1,
                    "withheld": 0,
                    "withheld_by_review_status": {},
                },
                "timing_rules": {
                    "published": 1,
                    "withheld": 0,
                    "withheld_by_review_status": {},
                },
            },
        },
        "integrity": {"sha256": "c" * 64},
    }

    assert render_markdown(report).startswith(
        "# Scoring integrity 2.4 candidate — 2026-08-23"
    )
    assert "12 products remain conservatively quarantined" in render_markdown(
        report
    )
