"""Tests for scripts/release_interaction_artifact.py.

Covers INTERACTION_DB_SPEC v2.2.0 §0.4 E1–E2 + §6.3 step 9:

- Validates interaction_db.sqlite + manifest shape before staging.
- Coexists with the catalog release artifact — never wipes scripts/dist/.
- Self-verifies the staged DB checksum against the source.
- Writes INTERACTION_RELEASE_NOTES.md summary.
- Exits non-zero on validation failure; staging dir left atomic.

Uses a real build_interaction_db.py run in tmp_path so the coupling
between the two scripts is exercised end-to-end.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import build_interaction_db as bid  # noqa: E402
import release_interaction_artifact as ria  # noqa: E402


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


MIN_DRAFT = {
    "id": "DDI_WAR_VITK",
    "type": "Med-Sup",
    "agent1_name": "Warfarin",
    "agent1_id": "11289",
    "agent2_name": "Vitamin K",
    "agent2_id": "C0042878",
    "severity": "avoid",
    "interaction_effect_type": "Inhibitor",
    "mechanism": "Opposes anticoagulation.",
    "management": "Maintain consistent intake.",
    "source_urls": ["https://ods.od.nih.gov/factsheets/VitaminK-HealthProfessional/"],
    "type_authored": "Med-Sup",
    "agent1_type": "drug",
    "agent2_type": "supplement",
    "source_pmids": [],
    "agent1_canonical_id": None,
    "agent2_canonical_id": "vitamin_k",
}

MIN_DRUG_CLASSES = {
    "_metadata": {"schema_version": "1.0.0"},
    "classes": {
        "class:warfarin_family": {
            "class_id": "class:warfarin_family",
            "class_name": "Vitamin K antagonists",
            "member_rxcuis": ["11289"],
            "source": "rxclass",
            "last_updated": "2026-04-11T00:00:00Z",
        }
    },
}


def _seed_build(tmp_path: Path) -> dict[str, Path]:
    """Run build_interaction_db.run_build once and return the artifact paths."""
    work = tmp_path / "interaction_db_output"
    work.mkdir()

    drafts_path = work / "normalized.json"
    drafts_path.write_text(
        json.dumps(
            {
                "_metadata": {"schema_version": "1.0.0"},
                "interactions": [MIN_DRAFT],
            }
        )
    )
    rp_path = work / "research_pairs.json"
    rp_path.write_text(
        json.dumps({"_metadata": {"schema_version": "1.0.0"}, "research_pairs": []})
    )
    dc_path = work / "drug_classes.json"
    dc_path.write_text(json.dumps(MIN_DRUG_CLASSES))
    ov_path = work / "interaction_overrides.json"
    ov_path.write_text(
        json.dumps({"_metadata": {"schema_version": "1.0.0"}, "overrides": []})
    )

    ctx = bid.BuildContext(
        normalized_drafts_path=drafts_path,
        research_pairs_path=rp_path,
        drug_classes_path=dc_path,
        overrides_path=ov_path,
        output_db=work / "interaction_db.sqlite",
        manifest_path=work / "interaction_db_manifest.json",
        report_path=work / "interaction_audit_report.json",
        build_time="2026-04-11T00:00:00Z",
        interaction_db_version="v2026.04.11.000000",
        pipeline_version="3.4.0",
        min_app_version="1.0.0",
    )
    bid.run_build(ctx)
    return {
        "work": work,
        "db": ctx.output_db,
        "manifest": ctx.manifest_path,
        "report": ctx.report_path,
    }


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #


def test_stage_release_writes_all_expected_files(tmp_path):
    paths = _seed_build(tmp_path)
    dist = tmp_path / "dist"

    result = ria.main(
        [
            "--input-dir",
            str(paths["work"]),
            "--output-dir",
            str(dist),
            "--min-interactions",
            "1",
        ]
    )
    assert result == 0
    assert (dist / "interaction_db.sqlite").is_file()
    assert (dist / "interaction_db_manifest.json").is_file()
    assert (dist / "INTERACTION_RELEASE_NOTES.md").is_file()


def test_staged_db_matches_source_checksum(tmp_path):
    paths = _seed_build(tmp_path)
    dist = tmp_path / "dist"
    assert (
        ria.main(
            ["--input-dir", str(paths["work"]), "--output-dir", str(dist), "--min-interactions", "1"]
        )
        == 0
    )
    assert _sha256(dist / "interaction_db.sqlite") == _sha256(paths["db"])


def test_staged_manifest_preserves_source_fields(tmp_path):
    paths = _seed_build(tmp_path)
    dist = tmp_path / "dist"
    assert (
        ria.main(
            ["--input-dir", str(paths["work"]), "--output-dir", str(dist), "--min-interactions", "1"]
        )
        == 0
    )
    staged = json.loads((dist / "interaction_db_manifest.json").read_text())
    for key in (
        "checksum",
        "interaction_db_version",
        "schema_version",
        "pipeline_version",
        "min_app_version",
        "integrity",
        "release_staged_at",
    ):
        assert key in staged, f"{key} missing from staged manifest"
    assert staged["checksum"].startswith("sha256:")


def test_release_notes_contains_key_fields(tmp_path):
    paths = _seed_build(tmp_path)
    dist = tmp_path / "dist"
    assert (
        ria.main(
            ["--input-dir", str(paths["work"]), "--output-dir", str(dist), "--min-interactions", "1"]
        )
        == 0
    )
    notes = (dist / "INTERACTION_RELEASE_NOTES.md").read_text()
    assert "interaction_db_version" in notes
    assert "v2026.04.11.000000" in notes
    assert "total_interactions" in notes
    assert "checksum_sha256" in notes


def test_coexists_with_catalog_dist_files(tmp_path):
    """Staging the interaction DB must not wipe unrelated files in dist/."""
    paths = _seed_build(tmp_path)
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "pharmaguide_core.db").write_bytes(b"existing catalog blob")
    (dist / "export_manifest.json").write_text('{"existing": "manifest"}')

    assert (
        ria.main(
            ["--input-dir", str(paths["work"]), "--output-dir", str(dist), "--min-interactions", "1"]
        )
        == 0
    )
    assert (dist / "pharmaguide_core.db").read_bytes() == b"existing catalog blob"
    assert "existing" in (dist / "export_manifest.json").read_text()
    assert (dist / "interaction_db.sqlite").is_file()


# --------------------------------------------------------------------------- #
# Failure modes
# --------------------------------------------------------------------------- #


def test_missing_db_fails_validation(tmp_path):
    work = tmp_path / "interaction_db_output"
    work.mkdir()
    (work / "interaction_db_manifest.json").write_text("{}")
    rc = ria.main(
        [
            "--input-dir",
            str(work),
            "--output-dir",
            str(tmp_path / "dist"),
            "--min-interactions",
            "1",
        ]
    )
    assert rc == 1


def test_missing_manifest_fails_validation(tmp_path):
    paths = _seed_build(tmp_path)
    paths["manifest"].unlink()
    rc = ria.main(
        [
            "--input-dir",
            str(paths["work"]),
            "--output-dir",
            str(tmp_path / "dist"),
            "--min-interactions",
            "1",
        ]
    )
    assert rc == 1


def test_integrity_check_failure_is_rejected(tmp_path):
    paths = _seed_build(tmp_path)
    # Corrupt the DB by overwriting a byte in the middle.
    db_bytes = bytearray(paths["db"].read_bytes())
    db_bytes[2000] ^= 0xFF
    paths["db"].write_bytes(bytes(db_bytes))
    rc = ria.main(
        [
            "--input-dir",
            str(paths["work"]),
            "--output-dir",
            str(tmp_path / "dist"),
            "--min-interactions",
            "1",
        ]
    )
    assert rc == 1


def test_min_interactions_floor_enforced(tmp_path):
    paths = _seed_build(tmp_path)
    rc = ria.main(
        [
            "--input-dir",
            str(paths["work"]),
            "--output-dir",
            str(tmp_path / "dist"),
            "--min-interactions",
            "100",
        ]
    )
    assert rc == 1


def test_checksum_mismatch_is_rejected(tmp_path):
    paths = _seed_build(tmp_path)
    manifest = json.loads(paths["manifest"].read_text())
    manifest["checksum"] = "sha256:deadbeef"
    paths["manifest"].write_text(json.dumps(manifest))
    rc = ria.main(
        [
            "--input-dir",
            str(paths["work"]),
            "--output-dir",
            str(tmp_path / "dist"),
            "--min-interactions",
            "1",
        ]
    )
    assert rc == 1


def test_print_json_mode_prints_result(tmp_path, capsys):
    paths = _seed_build(tmp_path)
    dist = tmp_path / "dist"
    rc = ria.main(
        [
            "--input-dir",
            str(paths["work"]),
            "--output-dir",
            str(dist),
            "--min-interactions",
            "1",
            "--print-json",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert "db_path" in payload
    assert "checksum_sha256" in payload
    assert payload["interaction_db_version"] == "v2026.04.11.000000"
