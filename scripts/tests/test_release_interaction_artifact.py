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
    profile_rules_path = work / "ingredient_interaction_rules.json"
    profile_rules_path.write_text(
        json.dumps(
            {
                "_metadata": {"schema_version": "6.2.4", "total_entries": 1},
                "interaction_rules": [
                    {
                        "id": "RULE_TEST",
                        "subject_ref": {
                            "db": "ingredient_quality_map",
                            "canonical_id": "vitamin_k",
                        },
                        "condition_rules": [],
                        "drug_class_rules": [],
                        "dose_thresholds": [],
                        "pregnancy_lactation": {},
                    }
                ],
            }
        )
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
        profile_warning_rules_path=profile_rules_path,
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


def test_research_pairs_require_queryable_rxcui_bridge(tmp_path):
    paths = _seed_build(tmp_path)
    con = sqlite3.connect(paths["db"])
    try:
        con.execute(
            """
            INSERT INTO research_pairs (
              pair_id, cui_a, cui_b, entity_a_name, entity_b_name,
              entity_a_type, entity_b_type, canonical_id_a, canonical_id_b,
              rxcui_a, rxcui_b, paper_count, human_study_count,
              clinical_study_count, top_sentences_json, top_pmids_json,
              latest_paper_year, source, last_updated
            ) VALUES (
              'C0042878-C0043031', 'C0042878', 'C0043031',
              'Vitamin K', 'Warfarin', 'supplement', 'drug',
              'vitamin_k', NULL, NULL, NULL, 3, 2, 1,
              '[]', '["12345"]', 2024, 'suppai',
              '2026-04-11T00:00:00Z'
            )
            """
        )
        con.execute(
            """
            UPDATE interaction_db_metadata
            SET value = '1'
            WHERE key = 'source_suppai_count'
            """
        )
        con.commit()
    finally:
        con.close()

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


# --------------------------------------------------------------------------- #
# Publication: the GitHub Release asset and the app's hydration pin
# --------------------------------------------------------------------------- #


PIPELINE_REPO = "seancheick/PharmaGuide_Pipeline"
HEAD_SHA = "3f593737083bb3c0fcfd62822b078bdd914d82c4"


def _staged_dist_and_pin(tmp_path: Path, *, pin_current: bool = False):
    dist = tmp_path / "dist"
    dist.mkdir()
    db = dist / ria.DB_FILENAME
    db.write_bytes(b"SQLite format 3\x00staged interaction db")
    sha = _sha256(db)
    (dist / ria.MANIFEST_FILENAME).write_text(
        json.dumps(
            {
                "checksum": f"sha256:{sha}",
                "checksum_sha256": sha,
                "interaction_db_version": "1.0.12",
                "schema_version": "2.0.0",
            }
        )
    )
    (dist / ria.RELEASE_NOTES_FILENAME).write_text("# notes\n")

    pin = {
        "_comment": "hydration pin — kept verbatim",
        "repo": PIPELINE_REPO,
        "tag": "clinical-db-2026.09.12.1",
        "filename": ria.DB_FILENAME,
        "url": "https://example.invalid/old",
        "sha256": sha if pin_current else "0" * 64,
        "size_bytes": 1,
        "min_size_bytes": 1048576,
        "pipeline_commit": "old",
        "interaction_db_version": "1.0.12" if pin_current else "1.0.11",
        "schema_version": "2.0.0",
        "clinical_content_hash": "sha256:kept",
        "runtime_contract": 1,
    }
    flutter = tmp_path / "flutter"
    pin_path = flutter / ria.FLUTTER_PIN_RELPATH
    pin_path.parent.mkdir(parents=True)
    pin_path.write_text(json.dumps(pin, indent=2) + "\n")
    return dist, flutter, pin_path, sha


class _FakeGh:
    def __init__(self, releases: list[dict]):
        self.releases = releases
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> str:
        self.calls.append(args)
        if args[0] == "api":
            return json.dumps(self.releases)
        if args[:2] == ["release", "create"]:
            return ""
        raise AssertionError(f"unexpected gh call {args}")

    def creates(self) -> list[list[str]]:
        return [c for c in self.calls if c[:2] == ["release", "create"]]


def _asset(sha: str) -> dict:
    return {"name": ria.DB_FILENAME, "digest": f"sha256:{sha}"}


def _publish(dist, flutter, gh, *, downloaded_sha, pushed=True):
    return ria.publish_flutter_pin(
        dist_dir=dist,
        flutter_repo=flutter,
        gh=gh,
        download_sha256=lambda url: downloaded_sha,
        pipeline_head=lambda: (HEAD_SHA, pushed),
        today="2026.09.25",
    )


def test_publish_is_a_no_op_when_the_pin_names_the_staged_artifact(tmp_path):
    dist, flutter, pin_path, _ = _staged_dist_and_pin(tmp_path, pin_current=True)
    before = pin_path.read_bytes()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("a current pin must not touch the network or git")

    result = ria.publish_flutter_pin(
        dist_dir=dist,
        flutter_repo=flutter,
        gh=forbidden,
        download_sha256=forbidden,
        pipeline_head=forbidden,
        today="2026.09.25",
    )

    assert result["action"] == "current"
    assert pin_path.read_bytes() == before


def test_publish_creates_the_next_dated_release_and_moves_the_pin(tmp_path):
    dist, flutter, pin_path, sha = _staged_dist_and_pin(tmp_path)
    gh = _FakeGh(
        [
            {"tag_name": "clinical-db-2026.09.25.1", "assets": [_asset("f" * 64)]},
            {"tag_name": "clinical-db-2026.07.24", "assets": [_asset("e" * 64)]},
            {"tag_name": "v1.0.0", "assets": []},
        ]
    )

    result = _publish(dist, flutter, gh, downloaded_sha=sha)

    tag = "clinical-db-2026.09.25.2"
    assert result == {"action": "published", "tag": tag}
    (create,) = gh.creates()
    assert create[2] == tag
    assert create[create.index("--repo") + 1] == PIPELINE_REPO
    assert create[create.index("--target") + 1] == HEAD_SHA
    assert create[create.index("--notes-file") + 1] == str(dist / ria.RELEASE_NOTES_FILENAME)
    assert create[-2:] == [str(dist / ria.DB_FILENAME), str(dist / ria.MANIFEST_FILENAME)]

    pin = json.loads(pin_path.read_text())
    assert pin["tag"] == tag
    assert pin["url"] == (
        f"https://github.com/{PIPELINE_REPO}/releases/download/{tag}/{ria.DB_FILENAME}"
    )
    assert pin["sha256"] == sha
    assert pin["size_bytes"] == (dist / ria.DB_FILENAME).stat().st_size
    assert pin["pipeline_commit"] == HEAD_SHA
    assert pin["interaction_db_version"] == "1.0.12"
    assert pin["schema_version"] == "2.0.0"
    # Fields the release does not own stay exactly as the app wrote them.
    assert pin["_comment"] == "hydration pin — kept verbatim"
    assert pin["min_size_bytes"] == 1048576
    assert pin["clinical_content_hash"] == "sha256:kept"
    assert pin["runtime_contract"] == 1
    assert list(pin)[:3] == ["_comment", "repo", "tag"]
    assert "\\u2014" in pin_path.read_text()


def test_publish_reuses_a_release_that_already_carries_the_asset(tmp_path):
    dist, flutter, pin_path, sha = _staged_dist_and_pin(tmp_path)
    release_commit = "315e59c0ffa84106de3e7b19e59efa485199f245"
    gh = _FakeGh(
        [
            {
                "tag_name": "clinical-db-2026.09.25.1",
                "target_commitish": release_commit,
                "assets": [_asset(sha)],
            }
        ]
    )

    result = _publish(dist, flutter, gh, downloaded_sha=sha)

    assert result == {"action": "reused", "tag": "clinical-db-2026.09.25.1"}
    assert gh.creates() == []
    pin = json.loads(pin_path.read_text())
    assert pin["tag"] == "clinical-db-2026.09.25.1"
    # The pin records the commit the published asset is tagged at, not today's HEAD.
    assert pin["pipeline_commit"] == release_commit


def test_publish_never_pins_a_draft_release(tmp_path):
    # A draft's assets are not publicly downloadable, so CI could not hydrate it.
    dist, flutter, pin_path, sha = _staged_dist_and_pin(tmp_path)
    gh = _FakeGh(
        [{"tag_name": "clinical-db-2026.09.25.1", "draft": True, "assets": [_asset(sha)]}]
    )

    result = _publish(dist, flutter, gh, downloaded_sha=sha)

    assert result == {"action": "published", "tag": "clinical-db-2026.09.25.2"}
    assert json.loads(pin_path.read_text())["tag"] == "clinical-db-2026.09.25.2"

def test_publish_omits_the_target_when_the_commit_is_not_on_the_remote(tmp_path):
    dist, flutter, pin_path, sha = _staged_dist_and_pin(tmp_path)
    gh = _FakeGh([])

    _publish(dist, flutter, gh, downloaded_sha=sha, pushed=False)

    (create,) = gh.creates()
    assert create[2] == "clinical-db-2026.09.25.1"
    assert "--target" not in create
    assert json.loads(pin_path.read_text())["pipeline_commit"] == HEAD_SHA


def test_publish_refuses_a_download_that_does_not_match(tmp_path):
    dist, flutter, pin_path, _ = _staged_dist_and_pin(tmp_path)
    before = pin_path.read_bytes()

    with pytest.raises(ria.ReleaseValidationError, match="downloaded"):
        _publish(dist, flutter, _FakeGh([]), downloaded_sha="a" * 64)

    assert pin_path.read_bytes() == before


def test_publish_refuses_a_staged_db_that_does_not_match_its_manifest(tmp_path):
    dist, flutter, pin_path, _ = _staged_dist_and_pin(tmp_path)
    (dist / ria.DB_FILENAME).write_bytes(b"SQLite format 3\x00tampered")
    gh = _FakeGh([])
    before = pin_path.read_bytes()

    with pytest.raises(ria.ReleaseValidationError, match="manifest"):
        _publish(dist, flutter, gh, downloaded_sha="a" * 64)

    assert gh.calls == []
    assert pin_path.read_bytes() == before


def test_publish_flag_is_wired_into_the_cli(tmp_path, capsys):
    dist, flutter, _, _ = _staged_dist_and_pin(tmp_path, pin_current=True)

    rc = ria.main(["--output-dir", str(dist), "--publish-flutter-pin", str(flutter)])

    assert rc == 0
    assert "already names" in capsys.readouterr().out
