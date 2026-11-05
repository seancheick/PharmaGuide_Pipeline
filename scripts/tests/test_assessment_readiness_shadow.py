from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
import pytest


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from audits.assessment_readiness_shadow import build_shadow_report, AssessmentReadinessShadowError  # noqa: E402
from stage_manifest import write_stage_manifest  # noqa: E402


def _row(name: str, canonical_id: str) -> dict:
    return {
        "name": name,
        "standard_name": name,
        "canonical_id": canonical_id,
        "mapped": True,
        "mapped_identity": True,
        "scoreable_identity": True,
        "identity_disposition": "clean",
        "source_section": "active",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "role_classification": "active_scorable",
        "dose_class": "therapeutic_mass",
        "quantity": 100,
        "unit": "mg",
        "has_dose": True,
        "raw_source_path": "ingredientRows[0]",
        "source_row_ref": "ingredientRows[0]",
    }


def _product(dsld_id: str, row: dict) -> dict:
    return {
        "dsld_id": dsld_id,
        "product_name": row["name"],
        "form_factor": "capsule",
        "supplement_taxonomy": {"primary_type": "single_nutrient"},
        "ingredient_quality_data": {
            "ingredients_scorable": [row],
            "ingredients": [row],
            "total_active": 1,
        },
        "evidence_data": {"clinical_matches": []},
        "certification_data": {
            "verification_assessment": {
                "state": "verified_absent",
                "readiness": "complete",
                "reason_code": "registry_evaluated_no_match",
                "matched_programs": [],
            }
        },
        "rda_ul_data": {
            "collection_status": "complete",
            "dose_assessments": [
                {
                    "source_row_ref": "ingredientRows[0]",
                    "canonical_id": row["canonical_id"],
                    "material": True,
                    "conversion_status": "not_required",
                    "ul_assessment_status": "no_ul_applicable",
                    "readiness": "not_applicable",
                }
            ],
        },
    }


def _write_stage(products_dir: Path, products: list[dict]) -> None:
    stage_dir = products_dir / "output_Test_enriched" / "enriched"
    stage_dir.mkdir(parents=True)
    batch = stage_dir / "enriched_batch_1.json"
    batch.write_text(json.dumps(products), encoding="utf-8")
    write_stage_manifest(stage_dir, "enrich", [batch], run_id="readiness-shadow-test")


def test_shadow_measures_readiness_without_changing_catalog_eligibility(
    tmp_path: Path,
) -> None:
    ready = _product("ready", _row("Magnesium", "magnesium"))
    incomplete = _product(
        "evidence-backlog",
        _row("Unreviewed Botanical", "unreviewed_botanical"),
    )
    products = [ready, incomplete]
    original = copy.deepcopy(products)
    _write_stage(tmp_path, products)

    report = build_shadow_report(tmp_path, generated_at="2026-08-20T00:00:00Z")

    assert products == original
    assert report["mode"] == "measure_only"
    assert report["enforcement_enabled"] is False
    assert report["catalog_eligibility_changed"] is False
    # Evidence no longer gates eligibility, so both products are live-ready --
    # but the evidence backlog stays counted and queued for remediation.
    assert report["summary"] == {
        "product_count": 2,
        "live_ready_product_count": 2,
        "incomplete_product_count": 0,
        "shadow_incomplete_product_count": 1,
        "not_yet_evaluated_material_active_count": 1,
        "verification_not_evaluated_product_count": 0,
        "legacy_dose_inference_product_count": 0,
        "duplicate_product_id_count": 0,
    }
    queued = {row["dsld_id"]: row for row in report["remediation_queue"]}
    assert set(queued) == {"evidence-backlog"}
    assert queued["evidence-backlog"]["gates_catalog_eligibility"] is False
    assert queued["evidence-backlog"]["shadow_incomplete_dimensions"] == ["evidence"]
    assert report["dimension_readiness_counts"]["evidence"] == {
        "complete": 1,
        "incomplete": 1,
    }
    assert report["evidence_state_counts"] == {
        "evaluated_supported": 1,
        "not_yet_evaluated": 1,
    }
    assert report["remediation_queue"] == [
        {
            "gates_catalog_eligibility": False,
            "shadow_incomplete_dimensions": ["evidence"],
            "dsld_id": "evidence-backlog",
            "product_name": "Unreviewed Botanical",
            "stage_owner": "output_Test_enriched",
            "source_file": "enriched_batch_1.json",
            "module": "generic",
            "unavailable_reasons": [],
            "identity_blocking_findings": [],
            "identity_reason_code": "mapped_scoring_actives",
            "dose_reason_code": None,
            "not_yet_evaluated_material_actives": [
                {
                    "source_row_ref": "ingredientRows[0]",
                    "canonical_id": "unreviewed_botanical",
                    "name": "Unreviewed Botanical",
                    "role": "claim_prominent",
                    "reason_code": "no_reviewed_evidence_assessment",
                }
            ],
            "verification_state": "verified_absent",
            "dose_assessment_source": "typed_dose_assessments",
        }
    ]


def test_shadow_reads_only_manifest_owned_files(tmp_path: Path) -> None:
    _write_stage(tmp_path, [_product("owned", _row("Magnesium", "magnesium"))])
    stage_dir = tmp_path / "output_Test_enriched" / "enriched"
    stale = _product("stale", _row("Unknown", "unknown"))
    (stage_dir / ".stale.json").write_text(json.dumps([stale]), encoding="utf-8")

    report = build_shadow_report(tmp_path)

    assert report["summary"]["product_count"] == 1
    assert report["summary"]["incomplete_product_count"] == 0


def test_shared_cause_keeps_each_label_and_requires_rebuilt_closure(tmp_path: Path) -> None:
    products = [_product(str(i), _row("Unreviewed Botanical", "unreviewed_botanical"))
                for i in (1, 2)]
    _write_stage(tmp_path, products)
    report = build_shadow_report(tmp_path)
    groups = report["cause_backlog"]
    assert len(groups) == 1
    group = groups[0]
    assert group["dimension"] == "evidence"
    assert group["canonical_id"] == "unreviewed_botanical"
    assert group["affected_product_ids"] == ["1", "2"]
    assert group["owner"] == "assessment_readiness.py::evaluate_evidence_assessment"
    assert group["resolution"] is None
    assert group["regression_coverage"] == []
    assert group["review_result"] is None
    assert group["rebuilt_verification"] is None
    assert group["status"] == "open"
    assert {item["dsld_id"] for item in group["source_evidence"]} == {"1", "2"}
    for item in group["source_evidence"]:
        assert item["source_row_ref"] == "ingredientRows[0]"
        assert item["artifact_sha256"] == report["stages"][0]["owned_files"][0]["sha256"]
        assert item["assessment"]["state"] == "not_yet_evaluated"
    assert report["summary"]["product_count"] == 2


def test_release_dependencies_are_queued_even_when_readiness_is_complete(tmp_path: Path) -> None:
    _write_stage(tmp_path, [_product("ready", _row("Magnesium", "magnesium"))])
    stage = tmp_path / 'output_Test_scored' / 'scored'
    stage.mkdir(parents=True)
    path = stage / 'scored_batch_1.json'
    path.write_text(json.dumps([{'dsld_id': 'ready', 'assessment_readiness': {
        'release_assessment': {'is_complete': False, 'blockers': [
            'contributing_source_review_incomplete:used-study']}}}]))
    write_stage_manifest(stage, 'score', [path], run_id='release-test')
    report = build_shadow_report(tmp_path, scored_products_dir=tmp_path)
    assert report['release_assessments_included'] is True
    assert report['summary']['live_ready_product_count'] == 1
    assert report['remediation_queue'] == []
    assert len(report['cause_backlog']) == 1
    group = report['cause_backlog'][0]
    assert group['dimension'] == 'release'
    assert group['cause'] == 'contributing_source_review_incomplete'
    assert group['canonical_id'] == 'used-study'
    assert group['affected_product_ids'] == ['ready']
    assert group['source_evidence'][0]['artifact_sha256']
    assert group['rebuilt_verification'] is None
    path.write_text(json.dumps([{'dsld_id': 'ready'}]))
    write_stage_manifest(stage, 'score', [path], run_id='old-score-test')
    report = build_shadow_report(tmp_path, scored_products_dir=tmp_path)
    assert report['cause_backlog'][0]['cause'] == 'release_assessment_receipt_missing'
    path.write_text(json.dumps([{'dsld_id': 'different-cohort'}]))
    write_stage_manifest(stage, 'score', [path], run_id='mismatched-score-test')
    with pytest.raises(AssessmentReadinessShadowError, match='cohorts differ'):
        build_shadow_report(tmp_path, scored_products_dir=tmp_path)


def test_product_register_retains_complete_partial_and_scored_states(tmp_path: Path) -> None:
    products = [_product(pid, _row("Magnesium", "magnesium"))
                for pid in ("complete", "partial", "unscored", "suppressed")]
    products[1]["ingredient_quality_data"]["ingredients"][0].update({
        "plant_part": None, "preparation": "aqueous extract", "population": None})
    products[1]["brand"] = {"name": "Source brand"}
    products[1]["evidence_data"]["trial_payload"] = {"abstract": "x" * 1_000_000}
    products[1]["evidence_data"]["sources"] = [{"id": "study-a", "pmid": "123",
        "approval_status": "pending", "scope": {"population": None, "purpose": "sleep"}}]
    _write_stage(tmp_path, products)
    scored = []
    for product in products:
        pid = product["dsld_id"]
        scored.append({"dsld_id": pid,
            "quality_assessment_status": "complete" if pid == "complete" else "partial",
            "quality_score_status": {"unscored": "not_scored", "suppressed": "suppressed_safety"}.get(pid, "scored"),
            "score_unavailable_reason": "identity_unknown" if pid == "unscored" else None,
            "product_safety_status": "blocked" if pid == "suppressed" else "no_known_concerns",
            "quality_pillars_v4": {"evidence": {"evidence_result_state": "no_qualifying_evidence", "display_state": "reviewed"}},
            "assessment_readiness": {"release_assessment": {
                "is_complete": pid == "complete", "blockers": [] if pid == "complete" else ["first:material", "second:study"]}},
            "_v4_module_breakdown": {"evidence": {"source_assessments": [{"source_id": "study", "population": None}]}}})
    stage = tmp_path / "output_Test_scored" / "scored"
    stage.mkdir(parents=True)
    path = stage / "scored_batch_1.json"
    path.write_text(json.dumps(scored))
    write_stage_manifest(stage, "score", [path], run_id="register-test")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    report = build_shadow_report(tmp_path, scored_products_dir=tmp_path)
    register = {row["dsld_id"]: row for row in report["product_register"]}
    assert set(register) == {"complete", "partial", "unscored", "suppressed"}
    assert register["partial"]["source_assessments"]["evidence_subject_rows"][0]["preparation"] == "aqueous extract"
    assert register["partial"]["source_assessments"]["evidence_subject_rows"][0]["population"] is None
    assert "ingredient_quality_data" not in register["partial"]["source_assessments"]
    assert register["partial"]["source_assessments"]["evidence_references"]["sources"] == products[1]["evidence_data"]["sources"]
    assert "trial_payload" not in register["partial"]["source_assessments"]["evidence_references"]
    assert len(json.dumps(report)) < 100_000
    assert register["partial"]["brand"] == {"name": "Source brand"}
    assert register["partial"]["owner_readiness"]["is_live_ready"] is True
    assert register["partial"]["scored"]["assessment_readiness"]["release_assessment"]["blockers"] == ["first:material", "second:study"]
    assert register["complete"]["scored"]["quality_pillars_v4"] == scored[0]["quality_pillars_v4"]
    assert register["unscored"]["scored"]["score_unavailable_reason"] == "identity_unknown"
    assert register["suppressed"]["scored"]["product_safety_status"] == "blocked"
    assert register["partial"]["scored"]["module_evidence_facts"] == scored[1]["_v4_module_breakdown"]
    for row in register.values():
        assert row["source"]["artifact_sha256"] == report["stages"][0]["owned_files"][0]["sha256"]
        assert row["source"]["manifest_sha256"] == report["stages"][0]["manifest_sha256"]
        assert row["scored"]["source"]["artifact_sha256"]
    assert report["scored_summary"]["quality_assessment_status_counts"] == {"complete": 1, "partial": 3}
    assert sum(row["product_count"] for row in report["scored_summary"]["status_cross_tab"]) == 4
    assert report["scored_summary"]["release_blocker_counts"] == {"first:material": 3, "second:study": 3}
    assert all(p.read_bytes() == content for p, content in before.items())


def test_exact_register_rejects_duplicate_enriched_ids(tmp_path: Path) -> None:
    product = _product("duplicate", _row("Magnesium", "magnesium"))
    _write_stage(tmp_path, [product, product])
    with pytest.raises(AssessmentReadinessShadowError, match="duplicate enriched product ID"):
        build_shadow_report(tmp_path)


def test_exact_register_rejects_duplicate_scored_ids(tmp_path: Path) -> None:
    _write_stage(tmp_path, [_product("one", _row("Magnesium", "magnesium"))])
    stage = tmp_path / "output_Test_scored" / "scored"
    stage.mkdir(parents=True)
    path = stage / "scored_batch_1.json"
    path.write_text(json.dumps([{"dsld_id": "one"}, {"dsld_id": "one"}]))
    write_stage_manifest(stage, "score", [path], run_id="duplicate-test")
    with pytest.raises(AssessmentReadinessShadowError, match="duplicate scored product ID"):
        build_shadow_report(tmp_path, scored_products_dir=tmp_path)


@pytest.mark.parametrize("swapped", ["payload", "manifest"])
def test_report_receipts_describe_the_same_captured_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, swapped: str,
) -> None:
    import hashlib

    product = _product("captured", _row("Magnesium", "magnesium"))
    _write_stage(tmp_path, [product])
    stage = tmp_path / "output_Test_enriched" / "enriched"
    payload_path = stage / "enriched_batch_1.json"
    manifest_path = stage / ".stage_manifest.json"
    original_payload = payload_path.read_bytes()
    original_manifest = manifest_path.read_bytes()
    original_read_text = Path.read_text

    def changed_text(path: Path, *args, **kwargs):
        # Simulate ABA: a separate text read sees a temporary replacement,
        # while the bytes whose hashes were verified remain the original.
        if swapped == "payload" and path == payload_path:
            return json.dumps([_product("replacement", _row("Unknown", "unknown"))])
        if swapped == "manifest" and path == manifest_path:
            value = json.loads(original_manifest)
            value["run_id"] = "unbound-replacement"
            return json.dumps(value)
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", changed_text)
    report = build_shadow_report(tmp_path)
    assert report["product_register"][0]["dsld_id"] == "captured"
    assert report["product_register"][0]["source"]["artifact_sha256"] == hashlib.sha256(original_payload).hexdigest()
    assert report["stages"][0]["manifest_sha256"] == hashlib.sha256(original_manifest).hexdigest()
    assert report["stages"][0]["run_id"] == "readiness-shadow-test"


def test_frozen_capture_validates_auxiliary_and_unowned_files(tmp_path: Path) -> None:
    from stage_manifest import StageManifestError

    _write_stage(tmp_path, [_product("one", _row("Magnesium", "magnesium"))])
    stage = tmp_path / "output_Test_enriched" / "enriched"
    payload = stage / "enriched_batch_1.json"
    auxiliary = stage / "counts.txt"
    auxiliary.write_text("owned auxiliary")
    write_stage_manifest(stage, "enrich", [payload, auxiliary], run_id="auxiliary-test")
    report = build_shadow_report(tmp_path)
    assert {row["name"] for row in report["stages"][0]["owned_files"]} == {payload.name, auxiliary.name}
    auxiliary.write_text("changed auxiliary")
    with pytest.raises(StageManifestError, match="checksum mismatch: counts.txt"):
        build_shadow_report(tmp_path)
    write_stage_manifest(stage, "enrich", [payload, auxiliary], run_id="auxiliary-test")
    (stage / "unowned.json").write_text("[]")
    with pytest.raises(StageManifestError, match="unowned files: unowned.json"):
        build_shadow_report(tmp_path)


def test_frozen_capture_rejects_unsafe_path_before_reading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from stage_manifest import StageManifestError

    _write_stage(tmp_path, [_product("one", _row("Magnesium", "magnesium"))])
    stage = tmp_path / "output_Test_enriched" / "enriched"
    manifest = stage / ".stage_manifest.json"
    value = json.loads(manifest.read_bytes())
    value["owned_files"] = ["../outside.json"]
    manifest.write_text(json.dumps(value))
    original_read = Path.read_bytes
    opened = []

    def record_read(path: Path):
        opened.append(path)
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", record_read)
    with pytest.raises(StageManifestError, match="Invalid owned filename"):
        build_shadow_report(tmp_path)
    assert opened == [manifest]


def test_frozen_capture_binds_bytes_even_when_original_changes_after_capture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import hashlib

    _write_stage(tmp_path, [_product("captured", _row("Magnesium", "magnesium"))])
    path = tmp_path / "output_Test_enriched" / "enriched" / "enriched_batch_1.json"
    original = path.read_bytes()
    original_read = Path.read_bytes

    def swap_after_read(source: Path):
        content = original_read(source)
        if source == path:
            source.write_text(json.dumps([_product("replacement", _row("Unknown", "unknown"))]))
        return content

    monkeypatch.setattr(Path, "read_bytes", swap_after_read)
    report = build_shadow_report(tmp_path)
    assert report["product_register"][0]["dsld_id"] == "captured"
    assert report["product_register"][0]["source"]["artifact_sha256"] == hashlib.sha256(original).hexdigest()


def test_frozen_capture_rejects_external_symlink_before_reading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from stage_manifest import StageManifestError

    _write_stage(tmp_path, [_product("one", _row("Magnesium", "magnesium"))])
    stage = tmp_path / "output_Test_enriched" / "enriched"
    path = stage / "enriched_batch_1.json"
    outside = tmp_path / "outside.json"
    outside.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(outside)
    original_read = Path.read_bytes
    opened = []

    def record_read(source: Path):
        opened.append(source)
        return original_read(source)

    monkeypatch.setattr(Path, "read_bytes", record_read)
    with pytest.raises(StageManifestError, match="outside stage directory"):
        build_shadow_report(tmp_path)
    assert opened == [stage / ".stage_manifest.json"]


def test_shadow_reuses_owner_derivation_per_product_without_changing_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from collections import Counter
    from contextlib import nullcontext
    import scoring_input_contract
    from audits import assessment_readiness_shadow

    products = [_product("ready", _row("Magnesium", "magnesium")),
                _product("pending", _row("Unreviewed Botanical", "unreviewed_botanical"))]
    original_products = copy.deepcopy(products)
    _write_stage(tmp_path, products)
    before = {path: path.read_bytes() for path in tmp_path.rglob("*.json")}
    builds = Counter()
    build = scoring_input_contract._build_scoring_ingredients

    def measured_build(product, *, strict=True, allow_legacy_fallback=False):
        builds[(product.get("dsld_id"), strict, allow_legacy_fallback)] += 1
        return build(product, strict=strict, allow_legacy_fallback=allow_legacy_fallback)

    monkeypatch.setattr(scoring_input_contract, "_build_scoring_ingredients", measured_build)
    report = build_shadow_report(tmp_path, generated_at="2026-11-05T00:00:00Z")
    scoped_builds = builds.copy()
    assert set(key[0] for key in scoped_builds) == {"ready", "pending"}
    assert all(count == 1 for count in scoped_builds.values()), scoped_builds
    assert report["product_register"][0]["owner_readiness"]["evidence"]["readiness"] == "incomplete"
    assert report["product_register"][1]["owner_readiness"]["evidence"]["readiness"] == "complete"
    import hashlib
    rows = {row["dsld_id"]: row for row in report["product_register"]}
    for product in products:
        original_bytes = json.dumps(product, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
        assert rows[product["dsld_id"]]["source_product_sha256"] == hashlib.sha256(original_bytes).hexdigest()

    builds.clear()
    monkeypatch.setattr(assessment_readiness_shadow, "scoring_input_scope", lambda product: nullcontext(), raising=False)
    uncached = build_shadow_report(tmp_path, generated_at="2026-11-05T00:00:00Z")
    assert uncached == report
    assert sum(builds.values()) > sum(scoped_builds.values())
    assert products == original_products
    assert all(path.read_bytes() == content for path, content in before.items())
