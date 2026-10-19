"""Dashboard score index: versioned, incremental, read-only projection of v4 artifacts.

Hermetic: tiny scored batches and a release dist under tmp_path, so CI runs it.
"""

from __future__ import annotations

import json
import os
import sqlite3

import pandas as pd
import pyarrow.dataset as pds
import pytest

from dashboard_index_fixtures import scored_product, write_batch, write_release
from scripts.dashboard import score_index as si


@pytest.fixture
def roots(tmp_path):
    scan, dist, cache = tmp_path / "products", tmp_path / "dist", tmp_path / "cache"
    write_batch(scan, "Acme", [scored_product("1"), scored_product("2", dose_neutral=True, verification_neutral=True),
                               scored_product("3", status="suppressed_safety", safety="blocked")])
    write_batch(scan, "Beta", [scored_product("4", deduction=3.0, floor=True), scored_product("5", status="not_scored",
                                                                                              assessment="partial")])
    write_release(dist, [scored_product("1"), scored_product("2", dose_neutral=True), scored_product("9")])
    return si.default_paths(scan, dist, cache)


def _reader(paths):
    return si.IndexReader(paths)


def test_refresh_projects_both_planes_and_reconciles(roots):
    meta = si.refresh(roots)
    reader = _reader(roots)
    cand, rel = reader.latest("candidate"), reader.latest("release")
    assert cand.startswith("candidate-") and rel.startswith("release-")
    products = reader.frame(cand, "products").set_index("dsld_id")
    assert set(products.index) == {"1", "2", "3", "4", "5"}
    # Read-side consistency: receipts sum to pillars and pillars to the total.
    scored = products[products["quality_score_status"] == "scored"]
    assert (scored["receipt_mismatch_max"] <= si.RECONCILE_TOLERANCE).all()
    assert (scored["pillar_sum_mismatch"] <= si.RECONCILE_TOLERANCE).all()
    ledgers = reader.frame(cand, "ledgers")
    assert ((ledgers["entry_sum"] - ledgers["score"]).abs() <= si.RECONCILE_TOLERANCE).all()
    # Audit states are recorded, not judged.
    assert products.loc["2", "neutral_only_pillars"].tolist() == ["dose", "verification", "safety_hygiene"]
    assert products.loc["2", "dose_basis"] == "disclosed_no_reference"
    assert bool(products.loc["2", "verification_fail_open"]) is True
    # A floor that fully absorbs a deduction shows nominal vs realized.
    assert products.loc["4", "nominal_deductions"] == -3.0
    assert products.loc["4", "realized_deductions"] == 0.0
    assert products.loc["4", "absorbed_points"] == 3.0
    assert bool(products.loc["4", "has_floor"]) and bool(products.loc["4", "has_deduction"])
    # Suppressed / not-scored rows keep their reasons and carry no receipts.
    assert products.loc["3", "blocking_reason"] == "BANNED_X"
    assert list(products.loc["3", "receipt_entry_ids"]) == []
    assert products.loc["5", "quality_assessment_status"] == "partial"
    assert meta["findings"]["critical"] == 0


def test_release_whole_number_total_is_not_a_pillar_sum_defect(roots):
    si.refresh(roots)
    reader = _reader(roots)
    release = reader.frame(reader.latest("release"), "products").set_index("dsld_id")
    assert release.loc["1", "total"] == float(round(release.loc["1", "total"]))
    assert (release["pillar_sum_mismatch"].dropna() == 0).all()
    # Release rows carry receipt summaries for catalog-wide filters.
    assert len(release.loc["1", "receipt_entry_ids"]) > 0


def test_candidate_and_release_same_id_stay_separate(roots):
    si.refresh(roots)
    reader = _reader(roots)
    cand = reader.product(reader.latest("candidate"), "2")["products"]
    rel = reader.product(reader.latest("release"), "2")["products"]
    assert len(cand) == 1 and len(rel) == 1
    assert cand.iloc[0]["config_version"] == "1.29.1-test"
    assert not pd.isna(rel.iloc[0]["blob_sha256"]) and pd.isna(cand.iloc[0]["blob_sha256"])


def test_unchanged_batch_is_reused_and_changed_manifest_reparsed(roots, monkeypatch):
    si.refresh(roots)
    parsed = []
    real = si._parse_candidate_part
    monkeypatch.setattr(si, "_parse_candidate_part", lambda source: parsed.append(source["part"]) or real(source))
    si.refresh(roots)
    assert parsed == []  # nothing changed: every partition hard-linked from the previous build
    # Same mtime, new content: the manifest hash is the identity, not mtime.
    stage = roots.scan_dir / "output_Beta_scored" / "scored"
    stat = (stage / "scored_batch_1.json").stat()
    write_batch(roots.scan_dir, "Beta", [scored_product("4", deduction=2.0)])
    os.utime(stage / "scored_batch_1.json", ns=(stat.st_atime_ns, stat.st_mtime_ns))
    meta = si.refresh(roots)
    assert parsed == ["Beta"]
    products = _reader(roots).frame(meta["latest"]["candidate"], "products")
    assert set(products["dsld_id"]) == {"1", "2", "3", "4"}


def test_deleted_batch_drops_out(roots):
    si.refresh(roots)
    import shutil
    shutil.rmtree(roots.scan_dir / "output_Beta_scored")
    reader = _reader(roots)
    assert reader.staleness()["candidate_removed"] == ["Beta"]
    meta = si.refresh(roots)
    assert set(_reader(roots).frame(meta["latest"]["candidate"], "products")["dsld_id"]) == {"1", "2", "3"}


def test_release_blob_change_reparses_only_that_product(roots, monkeypatch):
    si.refresh(roots)
    write_release(roots.build_root.parent / "dist2", [scored_product("1"), scored_product("2", evidence_score=4.0),
                                                       scored_product("9")], db_version="2026.10.16")
    import shutil
    shutil.rmtree(roots.build_root)
    (roots.build_root.parent / "dist2").rename(roots.build_root)
    seen = []
    real = si.project_product
    monkeypatch.setattr(si, "project_product", lambda product, **kw: seen.append(kw.get("source_part")) or real(product, **kw))
    meta = si.refresh(roots)
    assert seen.count("release") == 1  # only product 2's blob hash changed
    rel = _reader(roots).frame(meta["latest"]["release"], "products").set_index("dsld_id")
    assert rel.loc["2", "pillar_evidence"] == 4.0 and len(rel) == 3


def test_failed_build_keeps_current_pointer_and_previous_build(roots, monkeypatch):
    first = si.refresh(roots)
    write_batch(roots.scan_dir, "Acme", [scored_product("1", evidence_score=3.0)])
    monkeypatch.setattr(si, "_validate", lambda staging, meta: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        si.refresh(roots)
    assert json.loads(roots.current_pointer.read_text())["build_id"] == first["build_id"]
    assert json.loads(roots.status_file.read_text())["ok"] is False
    assert not any(p.name.startswith(".staging") for p in roots.builds.iterdir())


def test_schema_version_mismatch_is_treated_as_absent(roots, monkeypatch):
    si.refresh(roots)
    monkeypatch.setattr(si, "INDEX_SCHEMA_VERSION", si.INDEX_SCHEMA_VERSION + 1)
    assert si.current_build(roots) is None
    assert _reader(roots).staleness()["stale"] is True


def test_lock_blocks_concurrent_refresh(roots):
    with si._refresh_lock(roots.cache_root):
        with pytest.raises(si.IndexBusy):
            si.refresh(roots)


def test_run_key_differs_by_plane_and_schema():
    assert si._run_key("candidate", "x") != si._run_key("release", "x")
    key = si._run_key("candidate", "x")
    original = si.INDEX_SCHEMA_VERSION
    try:
        si.INDEX_SCHEMA_VERSION = original + 1
        assert si._run_key("candidate", "x") != key
    finally:
        si.INDEX_SCHEMA_VERSION = original


def test_provenance_separates_indexer_sha_from_artifact_fingerprints(roots):
    meta = si.refresh(roots)
    candidate = next(run for run in meta["runs"] if run["plane"] == "candidate")
    assert candidate["artifact_stage_code_fingerprints"] == ["code1"]
    assert candidate["artifact_reference_data_fingerprints"] == ["ref1"]
    assert "dashboard_indexer_git_sha" in meta and "dashboard_indexer_git_sha" not in candidate


def test_backfill_adds_pillar_only_runs_once(roots, tmp_path):
    si.refresh(roots)
    old = tmp_path / "old"
    write_release(old, [scored_product("1"), scored_product("2")], db_version="2026.09.01")
    first = si.backfill(roots, [old / "pharmaguide_core.db"])
    second = si.backfill(roots, [old / "pharmaguide_core.db"])
    assert len(first["added"]) == 1 and second["added"] == []
    run = first["added"][0]
    assert run["fidelity"] == si.FIDELITY_PILLARS and run["plane"] == "backfill"
    rows = _reader(roots).frame(run["run_key"], "products")
    assert len(rows) == 2 and rows["pillar_dose"].notna().all()


def test_new_candidate_run_keeps_history(roots):
    first = si.refresh(roots)
    write_batch(roots.scan_dir, "Acme", [scored_product("1", evidence_score=4.0), scored_product("2")],
                stage_code="code2")
    second = si.refresh(roots)
    candidates = [run for run in second["runs"] if run["plane"] == "candidate"]
    assert len(candidates) == 2
    assert first["latest"]["candidate"] in {run["run_key"] for run in candidates}
    assert si.gc(roots, keep=1) and si.current_build(roots) is not None


def test_canary_records_keep_full_scored_records_and_follow_membership(roots, monkeypatch):
    monkeypatch.setattr(si, "canary_ids", lambda: {"2"})
    si.refresh(roots)
    records = _reader(roots).canary_records()
    assert set(records) == {"2"} and "quality_pillars_v4" in records["2"]
    monkeypatch.setattr(si, "canary_ids", lambda: {"1", "2"})
    assert _reader(roots).staleness()["stale"] is True    # membership change re-reads the parts
    si.refresh(roots)
    assert set(_reader(roots).canary_records()) == {"1", "2"}


def test_backfill_and_ingredient_refresh_leave_the_previous_build_intact(roots, tmp_path):
    """New builds hard-link old partitions; writing their metadata must never touch the old build."""
    from dashboard_index_fixtures import enriched_product, write_enriched

    first = si.refresh(roots)
    old = roots.builds / first["build_id"]
    old_meta = (old / "index_meta.json").read_text()
    write_release(tmp_path / "older", [scored_product("1")], db_version="2026.09.01")
    si.backfill(roots, [tmp_path / "older" / "pharmaguide_core.db"])
    write_enriched(roots.scan_dir, "Acme", [enriched_product("1")])
    si.refresh_ingredients(roots)
    assert (old / "index_meta.json").read_text() == old_meta
    si._validate(old, si._load_meta(old))   # last-known-good still validates
    assert si._load_meta(old)["build_id"] == first["build_id"]


def test_failed_backfill_cleans_staging_and_records_status(roots, tmp_path):
    si.refresh(roots)
    with pytest.raises(Exception):
        si.backfill(roots, [tmp_path / "missing.db"])
    assert not any(p.name.startswith(".staging") for p in roots.builds.iterdir())
    assert json.loads(roots.status_file.read_text())["ok"] is False


@pytest.mark.parametrize("units, expected", [(["mcg"], "mcg"), (["mcg", "mg"], None), ([], None)])
def test_label_reference_unit_is_recorded_not_borrowed_from_amount(units, expected):
    product = {
        "dsld_id": "copper", "display_ingredients": [
            {"canonical_id": "copper", "label_display_name": "Copper", "exact_dose_text": "2 mg"}],
        "rda_ul_data": {"ingredients_with_rda": [
            {"canonical_id": "copper", "nutrient_unit": unit, "converted_unit": "mg", "ul_gate_eligible": True}
            for unit in units]},
    }
    row = si.project_enriched(product, source_part="test")["label_facts"][0]
    assert row.get("nutrient_unit") == expected
    assert row["amount"] == "2 mg"


def test_ingredient_index_builds_reuses_and_survives_core_refresh(roots, monkeypatch):
    from dashboard_index_fixtures import enriched_product, write_enriched

    write_enriched(roots.scan_dir, "Acme", [enriched_product("1"),
                                            enriched_product("2", forms=[("magnesium", "magnesium oxide")])])
    si.refresh(roots)
    assert _reader(roots).ingredient_staleness()["built"] is False
    si.refresh_ingredients(roots)
    reader = _reader(roots)
    assert set(reader.ingredient_frame()["matched_form"]) == {"magnesium glycinate", "magnesium oxide"}
    assert set(reader.ingredient_frame("product_meta")["entry_date"]) == {"2021-05-01"}
    meta = reader.ingredient_frame("product_meta", filter=pds.field("dsld_id") == "1").iloc[0]
    assert (meta["serving"], meta["servings_per_container"], meta["directions"]) == (
        "2 Capsule(s), 1–2× per day", 30.0, "Take two capsules daily.")   # storage note is not a direction
    label = reader.ingredient_frame("label_facts", filter=pds.field("dsld_id") == "1").sort_values("seq")
    label = label[["section", "name", "amount", "daily_value", "form"]].astype(object)
    assert label.where(label.notna(), None).values.tolist() == [
        ["active", "Magnesium", "100 mg", 24.0, "Magnesium Glycinate"],
        ["inactive", "Vegetable Cellulose", None, None, None]]
    assert reader.ingredient_staleness()["stale"] is False
    parsed = []
    real = si._parse_candidate_part
    monkeypatch.setattr(si, "_parse_candidate_part", lambda source: parsed.append(source["part"]) or real(source))
    si.refresh_ingredients(roots)
    assert parsed == []                      # unchanged enriched batch reused
    si.refresh(roots)                        # a core refresh keeps the ingredient index
    assert len(_reader(roots).ingredient_frame()) == 2
    write_enriched(roots.scan_dir, "Acme", [enriched_product("1")])
    assert _reader(roots).ingredient_staleness()["changed"] == ["Acme"]


def test_backfill_identity_includes_catalog_contents(roots, tmp_path):
    si.refresh(roots)
    old = tmp_path / "old"
    write_release(old, [scored_product("1")])
    db = old / "pharmaguide_core.db"
    first = si.backfill(roots, [db])
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE products_core SET quality_score_v4_100 = quality_score_v4_100 - 1")
    second = si.backfill(roots, [db])
    assert len(second["added"]) == 1
    assert first["added"][0]["run_key"] != second["added"][0]["run_key"]
