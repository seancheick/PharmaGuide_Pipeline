"""Tests for scripts/build_interaction_db.py.

TDD coverage for M2 SQLite builder (INTERACTION_DB_SPEC v2.2.0 §6.3–§6.5 +
§0.4 E1–E14). All tests run fully offline against in-memory fixtures — no
disk-bound golden fixture coupling and no network.

Covered (gate requires ≥15; this module ships 22):

- Schema creation: every §6.4 table + column + index exists
- FTS5 virtual table on interactions(agent1_name, agent2_name) (E5)
- Tombstone columns version_added / version_last_modified /
  retired_at / retired_reason on interactions (E4)
- provenance column distinct from source (E3)
- Curated row insertion from normalized verify_interactions output
- Research pair insertion from ingest_suppai output
- Drug class map population from drug_classes.json
- interaction_db_metadata keys: schema_version, built_at,
  source_drafts_count, source_suppai_count, total_interactions,
  interaction_db_version, pipeline_version, min_app_version
  (sha256_checksum is NOT embedded — the manifest is the sole source of
  truth for the file's hash; storing the file's own hash inside the file
  would invalidate the hash.)
- Dedup same-key rows: curated beats suppai beats raw
- Conflict resolution: more-cautious severity wins on draft collision
- Override precedence: interaction_overrides.json beats curated
- PubMed PMID enrichment from curated source_pmids
- PRAGMA integrity_check = ok after build
- PRAGMA user_version reflects schema version
- --build-time produces deterministic last_updated + metadata
- --dry-run leaves no output files
- FTS5 search by medication name returns the row
- Provenance derived from source URL host
- Drug class assignment from RXCUI lookup
- Manifest mirrors export_manifest.json shape (E2)
- Row order is sorted for deterministic SQLite page layout
- Audit report captures dropped + resolved conflicts
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


# --------------------------------------------------------------------------- #
# Minimal normalized-shape fixtures (same schema verify_interactions emits)
# --------------------------------------------------------------------------- #


CURATED_ROW_WARFARIN_VITK = {
    "id": "DDI_WAR_VITK",
    "type": "Med-Sup",
    "agent1_name": "Warfarin",
    "agent1_id": "11289",
    "agent2_name": "Vitamin K",
    "agent2_id": "C0042878",
    "severity": "avoid",
    "interaction_effect_type": "Inhibitor",
    "mechanism": "Vitamin K opposes warfarin anticoagulant effect.",
    "management": "Maintain consistent vitamin K intake.",
    "source_urls": [
        "https://ods.od.nih.gov/factsheets/VitaminK-HealthProfessional/",
        "https://pubmed.ncbi.nlm.nih.gov/12345678/",
    ],
    "type_authored": "Med-Sup",
    "agent1_type": "drug",
    "agent2_type": "supplement",
    "source_pmids": ["12345678"],
    "agent1_canonical_id": None,
    "agent2_canonical_id": "vitamin_k",
}

CURATED_ROW_IRON_CALCIUM = {
    "id": "DDI_IRON_CALCIUM",
    "type": "Sup-Sup",
    "agent1_name": "Calcium",
    "agent1_id": "C0006675",
    "agent2_name": "Iron",
    "agent2_id": "C0302583",
    "severity": "caution",
    "interaction_effect_type": "Inhibitor",
    "mechanism": "Calcium reduces iron absorption at the brush border.",
    "management": "Separate iron and calcium by 2 hours.",
    "source_urls": [
        "https://ods.od.nih.gov/factsheets/Iron-HealthProfessional/"
    ],
    "type_authored": "Sup-Sup",
    "agent1_type": "supplement",
    "agent2_type": "supplement",
    "source_pmids": [],
    "agent1_canonical_id": "calcium",
    "agent2_canonical_id": "iron",
}

CURATED_ROW_SSRI_STJOHNS = {
    "id": "DDI_SSRI_STJOHNS",
    "type": "Med-Sup",
    "agent1_name": "Fluoxetine",
    "agent1_id": "4493",
    "agent2_name": "St. John's Wort",
    "agent2_id": "C0813171",
    "severity": "avoid",
    "interaction_effect_type": "Additive",
    "mechanism": "Serotonergic additive effect raises serotonin syndrome risk.",
    "management": "Avoid concurrent use.",
    "source_urls": ["https://nccih.nih.gov/health/stjohnswort"],
    "type_authored": "Med-Sup",
    "agent1_type": "drug",
    "agent2_type": "supplement",
    "source_pmids": [],
    "agent1_canonical_id": None,
    "agent2_canonical_id": "st_johns_wort",
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
        },
        "class:ssris": {
            "class_id": "class:ssris",
            "class_name": "SSRIs",
            "member_rxcuis": ["4493", "36437"],
            "source": "rxclass",
            "last_updated": "2026-04-11T00:00:00Z",
        },
    },
}

MIN_RESEARCH_PAIRS = [
    {
        "pair_id": "C0006675-C0302583",
        "cui_a": "C0006675",
        "cui_b": "C0302583",
        "entity_a_name": "Calcium",
        "entity_b_name": "Iron",
        "entity_a_type": "supplement",
        "entity_b_type": "supplement",
        "canonical_id_a": "calcium",
        "canonical_id_b": "iron",
        "paper_count": 5,
        "human_study_count": 4,
        "clinical_study_count": 2,
        "top_sentences": [
            {
                "uid": "s1",
                "pmid": "11111",
                "text": "Calcium significantly reduced iron absorption.",
                "score_tuple": [0, 1, 1, 2020, 45],
            }
        ],
        "top_papers": [
            {"pmid": "11111", "year": 2020, "clinical_study": True, "human_study": True}
        ],
        "latest_paper_year": 2020,
    },
    {
        "pair_id": "C0015689-C0772125",
        "cui_a": "C0015689",
        "cui_b": "C0772125",
        "entity_a_name": "Omega-3",
        "entity_b_name": "Ginkgo",
        "entity_a_type": "supplement",
        "entity_b_type": "supplement",
        "canonical_id_a": "omega_3",
        "canonical_id_b": "ginkgo_biloba",
        "paper_count": 3,
        "human_study_count": 2,
        "clinical_study_count": 1,
        "top_sentences": [],
        "top_papers": [
            {"pmid": "22222", "year": 2018, "clinical_study": False, "human_study": True}
        ],
        "latest_paper_year": 2018,
    },
]


@pytest.fixture
def normalized_drafts() -> dict:
    return {
        "_metadata": {
            "schema_version": "1.0.0",
            "verified_at": "2026-04-11T00:00:00Z",
            "source_count": 1,
            "verified_count": 3,
        },
        "interactions": [
            CURATED_ROW_WARFARIN_VITK,
            CURATED_ROW_IRON_CALCIUM,
            CURATED_ROW_SSRI_STJOHNS,
        ],
    }


@pytest.fixture
def research_pairs_payload() -> dict:
    return {
        "_metadata": {
            "schema_version": "1.0.0",
            "source": "supp.ai",
            "last_updated": "2026-04-11T00:00:00Z",
            "total_pairs": len(MIN_RESEARCH_PAIRS),
        },
        "research_pairs": MIN_RESEARCH_PAIRS,
    }


@pytest.fixture
def empty_overrides() -> dict:
    return {
        "_metadata": {"schema_version": "1.0.0"},
        "overrides": [],
    }


@pytest.fixture
def build_ctx(
    tmp_path, normalized_drafts, research_pairs_payload, empty_overrides
) -> bid.BuildContext:
    """Canonical build context for tests — fixture paths all under tmp_path."""
    drafts_path = tmp_path / "normalized.json"
    drafts_path.write_text(json.dumps(normalized_drafts))
    rp_path = tmp_path / "research_pairs.json"
    rp_path.write_text(json.dumps(research_pairs_payload))
    dc_path = tmp_path / "drug_classes.json"
    dc_path.write_text(json.dumps(MIN_DRUG_CLASSES))
    ov_path = tmp_path / "interaction_overrides.json"
    ov_path.write_text(json.dumps(empty_overrides))
    return bid.BuildContext(
        normalized_drafts_path=drafts_path,
        research_pairs_path=rp_path,
        drug_classes_path=dc_path,
        overrides_path=ov_path,
        output_db=tmp_path / "interaction_db.sqlite",
        manifest_path=tmp_path / "interaction_db_manifest.json",
        report_path=tmp_path / "interaction_audit_report.json",
        build_time="2026-04-11T00:00:00Z",
        interaction_db_version="v2026.04.11.000000",
        pipeline_version="3.4.0",
        min_app_version="1.0.0",
    )


def _build(ctx: bid.BuildContext) -> dict:
    """Run the full build and return the audit report dict."""
    bid.run_build(ctx)
    assert ctx.output_db.exists()
    return json.loads(ctx.report_path.read_text())


def _conn(db: Path) -> sqlite3.Connection:
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    return c


# --------------------------------------------------------------------------- #
# Schema shape
# --------------------------------------------------------------------------- #


def test_all_core_tables_exist(build_ctx):
    _build(build_ctx)
    con = _conn(build_ctx.output_db)
    tables = {
        r["name"]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    for expected in (
        "interactions",
        "research_pairs",
        "drug_class_map",
        "interaction_db_metadata",
        "interactions_fts",
    ):
        assert expected in tables, f"{expected} missing: {sorted(tables)}"


def test_interactions_columns_match_spec(build_ctx):
    _build(build_ctx)
    con = _conn(build_ctx.output_db)
    cols = {r["name"] for r in con.execute("PRAGMA table_info(interactions)")}
    # §6.4 base
    required_base = {
        "id",
        "agent1_type",
        "agent1_name",
        "agent1_id",
        "agent1_canonical_id",
        "agent1_drug_class",
        "agent2_type",
        "agent2_name",
        "agent2_id",
        "agent2_canonical_id",
        "agent2_drug_class",
        "severity",
        "effect_type",
        "mechanism",
        "management",
        "evidence_level",
        "source_urls_json",
        "source_pmids_json",
        "bidirectional",
        "dose_dependent",
        "dose_threshold_text",
        "type_authored",
        "source",
        "last_updated",
    }
    # E3 + E4 enhancements
    required_enhancements = {
        "provenance",
        "version_added",
        "version_last_modified",
        "retired_at",
        "retired_reason",
    }
    missing = (required_base | required_enhancements) - cols
    assert not missing, f"missing columns: {missing}"


def test_research_pairs_columns_match_spec(build_ctx):
    _build(build_ctx)
    con = _conn(build_ctx.output_db)
    cols = {r["name"] for r in con.execute("PRAGMA table_info(research_pairs)")}
    required = {
        "pair_id",
        "cui_a",
        "cui_b",
        "entity_a_name",
        "entity_b_name",
        "entity_a_type",
        "entity_b_type",
        "canonical_id_a",
        "canonical_id_b",
        "rxcui_a",
        "rxcui_b",
        "paper_count",
        "human_study_count",
        "clinical_study_count",
        "top_sentences_json",
        "top_pmids_json",
        "latest_paper_year",
        "source",
        "last_updated",
    }
    missing = required - cols
    assert not missing, f"missing columns: {missing}"


def test_all_required_indexes_present(build_ctx):
    _build(build_ctx)
    con = _conn(build_ctx.output_db)
    names = {
        r["name"]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
    }
    for expected in (
        "idx_int_a1_canon",
        "idx_int_a2_canon",
        "idx_int_a1_id",
        "idx_int_a2_id",
        "idx_int_a1_class",
        "idx_int_a2_class",
        "idx_rp_canon_a",
        "idx_rp_canon_b",
        "idx_rp_cui_a",
        "idx_rp_cui_b",
    ):
        assert expected in names, f"{expected} missing: {sorted(names)}"


def test_fts5_virtual_table_queryable(build_ctx):
    _build(build_ctx)
    con = _conn(build_ctx.output_db)
    rows = con.execute(
        "SELECT id FROM interactions_fts WHERE interactions_fts MATCH ?",
        ("warfarin",),
    ).fetchall()
    ids = {r["id"] for r in rows}
    assert "DDI_WAR_VITK" in ids, (
        f"FTS5 should match 'warfarin' — got {ids}"
    )


# --------------------------------------------------------------------------- #
# Row insertion + content
# --------------------------------------------------------------------------- #


def test_curated_rows_inserted_with_correct_severity(build_ctx):
    _build(build_ctx)
    con = _conn(build_ctx.output_db)
    got = {
        r["id"]: r["severity"]
        for r in con.execute("SELECT id, severity FROM interactions")
    }
    assert got["DDI_WAR_VITK"] == "avoid"
    assert got["DDI_IRON_CALCIUM"] == "caution"
    assert got["DDI_SSRI_STJOHNS"] == "avoid"


def test_research_pairs_populated(build_ctx):
    _build(build_ctx)
    con = _conn(build_ctx.output_db)
    rows = con.execute(
        "SELECT pair_id, paper_count, canonical_id_a, canonical_id_b FROM research_pairs"
    ).fetchall()
    assert len(rows) == 2
    by_id = {r["pair_id"]: r for r in rows}
    assert by_id["C0006675-C0302583"]["paper_count"] == 5
    assert by_id["C0006675-C0302583"]["canonical_id_a"] == "calcium"
    assert by_id["C0015689-C0772125"]["paper_count"] == 3


def test_drug_class_map_populated(build_ctx):
    _build(build_ctx)
    con = _conn(build_ctx.output_db)
    rows = {
        r["class_id"]: json.loads(r["drug_rxcuis_json"])
        for r in con.execute(
            "SELECT class_id, drug_rxcuis_json FROM drug_class_map"
        )
    }
    assert rows["class:warfarin_family"] == ["11289"]
    assert rows["class:ssris"] == ["4493", "36437"]


def test_drug_class_auto_assigned_from_rxcui(build_ctx):
    """RXCUI 11289 should be tagged with class:warfarin_family; 4493 with class:ssris."""
    _build(build_ctx)
    con = _conn(build_ctx.output_db)
    wf = con.execute(
        "SELECT agent1_drug_class FROM interactions WHERE id=?",
        ("DDI_WAR_VITK",),
    ).fetchone()
    ssri = con.execute(
        "SELECT agent1_drug_class FROM interactions WHERE id=?",
        ("DDI_SSRI_STJOHNS",),
    ).fetchone()
    assert wf["agent1_drug_class"] == "class:warfarin_family"
    assert ssri["agent1_drug_class"] == "class:ssris"


def test_provenance_derived_from_source_urls(build_ctx):
    _build(build_ctx)
    con = _conn(build_ctx.output_db)
    rows = {
        r["id"]: r["provenance"]
        for r in con.execute("SELECT id, provenance FROM interactions")
    }
    # Warfarin entry has NIH ODS + PubMed — NIH ODS is the most authoritative
    # so the row's provenance should be nih_ods (first allow-listed host wins).
    assert rows["DDI_WAR_VITK"] == "nih_ods"
    assert rows["DDI_SSRI_STJOHNS"] == "nccih"
    assert rows["DDI_IRON_CALCIUM"] == "nih_ods"


def test_source_pmids_persisted(build_ctx):
    _build(build_ctx)
    con = _conn(build_ctx.output_db)
    row = con.execute(
        "SELECT source_pmids_json FROM interactions WHERE id=?", ("DDI_WAR_VITK",)
    ).fetchone()
    assert json.loads(row["source_pmids_json"]) == ["12345678"]


def test_tombstone_columns_initialized_on_new_rows(build_ctx):
    _build(build_ctx)
    con = _conn(build_ctx.output_db)
    row = con.execute(
        "SELECT version_added, version_last_modified, retired_at, retired_reason "
        "FROM interactions WHERE id=?",
        ("DDI_WAR_VITK",),
    ).fetchone()
    assert row["version_added"] == "v2026.04.11.000000"
    assert row["version_last_modified"] == "v2026.04.11.000000"
    assert row["retired_at"] is None
    assert row["retired_reason"] is None


# --------------------------------------------------------------------------- #
# Dedup, conflict resolution, overrides
# --------------------------------------------------------------------------- #


def test_dedup_same_key_keeps_curated_over_suppai(tmp_path, build_ctx, normalized_drafts):
    # Add a duplicate research_pair matching the Iron×Calcium curated row.
    con_rp = json.loads(build_ctx.research_pairs_path.read_text())
    dup_rp = {
        "pair_id": "C0006675-C0302583",  # duplicates curated Sup-Sup row by canon-pair
        "cui_a": "C0006675",
        "cui_b": "C0302583",
        "entity_a_name": "Calcium",
        "entity_b_name": "Iron",
        "entity_a_type": "supplement",
        "entity_b_type": "supplement",
        "canonical_id_a": "calcium",
        "canonical_id_b": "iron",
        "paper_count": 99,
        "human_study_count": 50,
        "clinical_study_count": 25,
        "top_sentences": [],
        "top_papers": [],
        "latest_paper_year": 2024,
    }
    con_rp["research_pairs"] = [dup_rp]
    build_ctx.research_pairs_path.write_text(json.dumps(con_rp))

    _build(build_ctx)
    con = _conn(build_ctx.output_db)
    # Curated Iron×Calcium row still present in interactions with curated severity.
    row = con.execute(
        "SELECT severity, source, mechanism FROM interactions WHERE id=?",
        ("DDI_IRON_CALCIUM",),
    ).fetchone()
    assert row["source"] == "curated"
    assert row["severity"] == "caution"
    # Research pair row coexists in research_pairs table (separate tier).
    rp = con.execute(
        "SELECT paper_count FROM research_pairs WHERE pair_id=?",
        ("C0006675-C0302583",),
    ).fetchone()
    assert rp["paper_count"] == 99


def test_conflict_resolution_more_cautious_wins(tmp_path, build_ctx, monkeypatch):
    """Two curated drafts colliding on the same pair → more-cautious severity wins.

    Updated 2026-04-26: build is strict-by-default and now FAILS on duplicate
    pair_keys. The conflict-resolution merge logic is preserved as a bypass
    path (set ALLOW_CURATED_CONFLICTS=1) for emergency rebuilds. This test
    exercises the bypass path to confirm the merge logic still works.
    """
    drafts = json.loads(build_ctx.normalized_drafts_path.read_text())
    softer = dict(CURATED_ROW_WARFARIN_VITK)
    softer["id"] = "DDI_WAR_VITK_SOFTER"
    softer["severity"] = "caution"  # less cautious than the original 'avoid'
    drafts["interactions"].append(softer)
    build_ctx.normalized_drafts_path.write_text(json.dumps(drafts))

    monkeypatch.setenv("ALLOW_CURATED_CONFLICTS", "1")
    report = _build(build_ctx)
    con = _conn(build_ctx.output_db)
    row = con.execute(
        "SELECT severity FROM interactions WHERE agent1_id=? AND agent2_id=?",
        ("11289", "C0042878"),
    ).fetchone()
    assert row["severity"] == "avoid", (
        "more-cautious-wins broke — expected 'avoid' (from 'avoid' vs 'caution')"
    )
    assert report["resolved_conflicts"], "conflict should be logged in audit report"


def test_strict_mode_fails_on_duplicate_pair_keys(tmp_path, build_ctx):
    """Without ALLOW_CURATED_CONFLICTS=1, build raises ValueError on duplicates."""
    import pytest as _pytest
    drafts = json.loads(build_ctx.normalized_drafts_path.read_text())
    softer = dict(CURATED_ROW_WARFARIN_VITK)
    softer["id"] = "DDI_WAR_VITK_SOFTER"
    softer["severity"] = "caution"
    drafts["interactions"].append(softer)
    build_ctx.normalized_drafts_path.write_text(json.dumps(drafts))

    with _pytest.raises(ValueError, match="duplicate pair_key"):
        _build(build_ctx)


def test_override_beats_curated(tmp_path, build_ctx):
    overrides = {
        "_metadata": {"schema_version": "1.0.0"},
        "overrides": [
            {
                "id": "DDI_WAR_VITK",
                "severity": "contraindicated",
                "mechanism": "OVERRIDDEN mechanism text",
                "management": "OVERRIDDEN management text",
                "source_urls": [
                    "https://ods.od.nih.gov/factsheets/VitaminK-HealthProfessional/"
                ],
                "source_pmids": [],
                "reason": "manual escalation",
            }
        ],
    }
    build_ctx.overrides_path.write_text(json.dumps(overrides))
    _build(build_ctx)
    con = _conn(build_ctx.output_db)
    row = con.execute(
        "SELECT severity, mechanism, source FROM interactions WHERE id=?",
        ("DDI_WAR_VITK",),
    ).fetchone()
    assert row["severity"] == "contraindicated"
    assert row["mechanism"] == "OVERRIDDEN mechanism text"
    assert row["source"] == "override"


# --------------------------------------------------------------------------- #
# PRAGMAs + determinism + flags
# --------------------------------------------------------------------------- #


def test_pragma_integrity_check_ok(build_ctx):
    _build(build_ctx)
    con = _conn(build_ctx.output_db)
    result = con.execute("PRAGMA integrity_check").fetchone()[0]
    assert result == "ok"


def test_pragma_user_version_set(build_ctx):
    _build(build_ctx)
    con = _conn(build_ctx.output_db)
    assert con.execute("PRAGMA user_version").fetchone()[0] == 1


def test_metadata_table_has_required_keys(build_ctx):
    _build(build_ctx)
    con = _conn(build_ctx.output_db)
    kv = {
        r["key"]: r["value"]
        for r in con.execute("SELECT key, value FROM interaction_db_metadata")
    }
    for k in (
        "schema_version",
        "built_at",
        "source_drafts_count",
        "source_suppai_count",
        "total_interactions",
        "interaction_db_version",
        "pipeline_version",
        "min_app_version",
    ):
        assert k in kv, f"{k} missing from metadata: {sorted(kv)}"
    # sha256_checksum is intentionally NOT in embedded metadata — storing
    # the file's own hash inside the file would invalidate the hash. The
    # manifest is the sole source of truth for the checksum.
    assert "sha256_checksum" not in kv
    assert kv["built_at"] == "2026-04-11T00:00:00Z"
    assert kv["interaction_db_version"] == "v2026.04.11.000000"
    assert kv["total_interactions"] == "3"


def test_manifest_mirrors_export_manifest_shape(build_ctx):
    _build(build_ctx)
    manifest = json.loads(build_ctx.manifest_path.read_text())
    for k in (
        "checksum",
        "db_version",
        "schema_version",
        "pipeline_version",
        "min_app_version",
        "integrity",
        "interaction_db_version",
    ):
        assert k in manifest, f"{k} missing from manifest"
    assert manifest["checksum"].startswith("sha256:")
    assert manifest["integrity"]["integrity_check"] == "ok"


def test_dry_run_writes_nothing(tmp_path, build_ctx):
    build_ctx.dry_run = True
    bid.run_build(build_ctx)
    assert not build_ctx.output_db.exists()
    assert not build_ctx.manifest_path.exists()


def test_build_time_locks_last_updated(build_ctx):
    _build(build_ctx)
    con = _conn(build_ctx.output_db)
    for r in con.execute(
        "SELECT last_updated FROM interactions"
    ).fetchall():
        assert r["last_updated"] == "2026-04-11T00:00:00Z"
    for r in con.execute(
        "SELECT last_updated FROM research_pairs"
    ).fetchall():
        assert r["last_updated"] == "2026-04-11T00:00:00Z"


def test_build_is_content_deterministic(tmp_path, build_ctx):
    """Two builds with the same --build-time yield the same row-content hash.

    This is the content-level determinism check. The stronger byte-identity
    check lives in test_build_is_byte_identical_deterministic below.
    """

    def content_hash(db: Path) -> str:
        con = _conn(db)
        buckets: list[str] = []
        for table in (
            "interactions",
            "research_pairs",
            "drug_class_map",
            "interaction_db_metadata",
        ):
            rows = con.execute(f"SELECT * FROM {table}").fetchall()
            col_names = [d[0] for d in con.execute(f"SELECT * FROM {table}").description]
            serialized = [
                json.dumps(
                    {c: r[c] for c in col_names}, sort_keys=True, default=str
                )
                for r in rows
            ]
            serialized.sort()
            buckets.append(table + ":" + "\n".join(serialized))
        return hashlib.sha256("\n\n".join(buckets).encode()).hexdigest()

    _build(build_ctx)
    h1 = content_hash(build_ctx.output_db)

    build_ctx.output_db.unlink()
    build_ctx.manifest_path.unlink()
    build_ctx.report_path.unlink()
    _build(build_ctx)
    h2 = content_hash(build_ctx.output_db)

    assert h1 == h2, "content hashes diverged between builds"


def test_build_is_byte_identical_deterministic(tmp_path, build_ctx):
    """T8: Two builds with the same --build-time must produce byte-identical
    SQLite files (same SHA-256 of the raw blob on disk), and the manifest
    checksum must match that SHA-256 in both runs.

    This is a stronger guarantee than content-equivalence: it proves
    every byte of the SQLite page layout — VACUUM output, ANALYZE stat1
    rows, FTS5 internal tables, metadata values — is deterministic
    modulo the inputs and --build-time. Flutter repo LFS-tracks this
    blob; any drift would cause spurious LFS diffs on every build.
    """

    def file_sha(p: Path) -> str:
        h = hashlib.sha256()
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    _build(build_ctx)
    db_hash_a = file_sha(build_ctx.output_db)
    manifest_a = json.loads(build_ctx.manifest_path.read_text())
    assert manifest_a["checksum"] == f"sha256:{db_hash_a}", (
        "manifest checksum drifted from actual file hash on first build "
        "— sha256 self-reference bug re-introduced?"
    )

    build_ctx.output_db.unlink()
    build_ctx.manifest_path.unlink()
    build_ctx.report_path.unlink()

    _build(build_ctx)
    db_hash_b = file_sha(build_ctx.output_db)
    manifest_b = json.loads(build_ctx.manifest_path.read_text())

    assert db_hash_a == db_hash_b, (
        f"byte-identity broken: run A={db_hash_a}, run B={db_hash_b}"
    )
    assert manifest_b["checksum"] == f"sha256:{db_hash_b}", (
        "manifest checksum drifted from actual file hash on second build"
    )
    assert manifest_a["checksum"] == manifest_b["checksum"]


# --------------------------------------------------------------------------- #
# Audit report
# --------------------------------------------------------------------------- #


def test_audit_report_shape(build_ctx):
    report = _build(build_ctx)
    for key in (
        "build_time",
        "total_interactions",
        "source_drafts_count",
        "source_suppai_count",
        "resolved_conflicts",
        "dropped_entries",
        "override_count",
    ):
        assert key in report, f"{key} missing from audit report"
    assert report["total_interactions"] == 3
    assert report["source_drafts_count"] == 3
    assert report["source_suppai_count"] == 2
