"""Read-only replay baselines must be complete, source-bound, and target-scoped."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from audits.scoring_applicability_2026_09_03 import audit_corpus as audit


@pytest.fixture
def baseline_report(tmp_path):
    baseline = {pid: audit.summary({"quality_score_v4_100": score})
                for pid, score in [("changed", 10), ("canary", 20), ("unchanged", 30)]}
    candidate = deepcopy(baseline["changed"])
    candidate["score"] = 40
    canary = deepcopy(baseline["canary"])
    canary["score"] = 50
    hashes = {"scripts/products/batch.json": "current-input-hash"}
    report = {"complete": True, "product_count": 3, "baseline_product_count": 3,
              "input_hashes": hashes, "errors": [],
              "changes": [{"id": "changed", "candidate": candidate}],
              "canaries": [{"id": "canary", "candidate": canary},
                           {"id": "changed", "candidate": candidate}]}
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(report))
    return path, baseline, hashes, report


def test_baseline_overlay_uses_candidate_summaries_and_preserves_unchanged(baseline_report):
    path, baseline, hashes, _ = baseline_report

    result, digest = audit.load_baseline_report(path, baseline, hashes)

    assert {pid: row["score"] for pid, row in result.items()} == {
        "changed": 40, "canary": 50, "unchanged": 30,
    }
    assert baseline["changed"]["score"] == 10
    assert digest == audit.sha(path)


@pytest.mark.parametrize("defect", ["incomplete", "count", "baseline_count", "hash",
                                    "missing_hash", "extra_hash", "unknown_id", "candidate",
                                    "conflicting_duplicate", "errors"])
def test_baseline_overlay_rejects_unproven_reports(baseline_report, defect):
    path, baseline, hashes, report = baseline_report
    report = deepcopy(report)
    if defect == "incomplete": report["complete"] = False
    if defect == "count": report["product_count"] = 2
    if defect == "baseline_count": report["baseline_product_count"] = 2
    if defect == "hash": report["input_hashes"]["scripts/products/batch.json"] = "stale"
    if defect == "missing_hash": report["input_hashes"] = {}
    if defect == "extra_hash": report["input_hashes"]["unrelated.json"] = "extra"
    if defect == "unknown_id": report["changes"][0]["id"] = "not-in-corpus"
    if defect == "candidate": report["changes"][0]["candidate"] = {"score": 40}
    if defect == "conflicting_duplicate":
        report["canaries"][-1]["candidate"] = {**report["canaries"][-1]["candidate"], "score": 99}
    if defect == "errors": report["errors"] = ["failed product"]
    path.write_text(json.dumps(report))

    with pytest.raises(ValueError, match="baseline|Baseline"):
        audit.load_baseline_report(path, baseline, hashes)


@pytest.mark.parametrize("value", ["", " ", ",", "one,,two"])
def test_empty_target_tokens_are_rejected(value):
    with pytest.raises(ValueError, match="target"):
        audit.parse_target_ids(value)


def test_target_parser_and_filter_do_not_turn_empty_selection_into_full_run():
    rows = [{"id": "one"}, {"dsld_id": "two"}, {"id": "three"}]
    assert audit.parse_target_ids(" one, two,one ") == {"one", "two"}
    assert audit.parse_target_ids(None) is None
    assert audit.target_products(rows, {"two"}) == [{"dsld_id": "two"}]
    assert audit.target_products(rows, set()) == []
    assert audit.target_products(rows, None) == rows


def test_process_file_filters_before_clean_source_lookup(tmp_path, monkeypatch):
    path = tmp_path / "not-selected.json"
    path.write_text(json.dumps([{"id": "excluded"}]))
    monkeypatch.setattr(audit, "select_stage_files", lambda *a, **k: pytest.fail("read unrelated clean inputs"))

    assert audit.process_file((str(path), {"wanted"}, {"wanted"})) == []


def test_noncanary_replay_refreshes_changed_blend_provenance_lane(tmp_path, monkeypatch):
    path = tmp_path / "scripts/products/output_Example_enriched/enriched/batch.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps([{"id": "one", "proprietary_blends": [{"source_path": "stale"}]}]))
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    fresh = {"blends": [{"source_row_ref": "ingredientRows[0]"}]}
    monkeypatch.setattr(audit, "ENRICHER", SimpleNamespace(
        _collect_certification_data=lambda p: {"verified_cert_programs": []},
        _collect_probiotic_data=lambda p: {},
        _collect_proprietary_data=lambda p: fresh,
    ), raising=False)

    def score(product):
        assert product["proprietary_data"] == fresh
        assert product["proprietary_blends"] == fresh["blends"]
        return {}

    monkeypatch.setitem(sys.modules, "scoring_v4.scored_artifact", SimpleNamespace(build_scored_artifact=score))
    monkeypatch.setitem(sys.modules, "studied_formulas", SimpleNamespace(assess_studied_formula=lambda p: {}))
    monkeypatch.setitem(sys.modules, "audits.evidence_match_reachability", SimpleNamespace(recompute_evidence=lambda e, p: {}))
    audit.process_file((str(path), set(), None))


def test_process_file_only_reenriches_target_with_its_cleaned_identity(tmp_path, monkeypatch):
    enriched = tmp_path / "scripts/products/output_Example_enriched/enriched/batch.json"
    cleaned = tmp_path / "scripts/products/output_Example/cleaned/batch.json"
    enriched.parent.mkdir(parents=True)
    cleaned.parent.mkdir(parents=True)
    enriched.write_text(json.dumps([{"id": "excluded"}, {"id": "wanted", "verified_cert_programs": [{"record_id": "before"}]}]))
    cleaned.write_text(json.dumps([{"id": "excluded"}, {"id": "wanted", "fullName": "clean target"}]))
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit, "select_stage_files", lambda *a, **k: [cleaned])
    calls = []

    def enrich(row):
        calls.append(row)
        return {**row, "evidence_data": {}, "verified_cert_programs": [{"record_id": "after"}]}, []

    monkeypatch.setattr(audit, "ENRICHER", SimpleNamespace(enrich_product=enrich), raising=False)
    score = {"quality_pillars_v4": {"evidence": {"score": 8, "detail": {"tags": {"native", "reviewed"}}}},
             "_v4_module_breakdown": {"dimensions": {"evidence": {"components": {"research": 8}}}}}
    monkeypatch.setitem(sys.modules, "scoring_v4.scored_artifact", SimpleNamespace(build_scored_artifact=lambda p: score))
    monkeypatch.setitem(sys.modules, "studied_formulas", SimpleNamespace(
        assess_studied_formula=lambda p: {"status": "unresolved_reference"},
        assess_probiotic_evidence=lambda p: {"strain_assessments": []},
    ))
    monkeypatch.setitem(sys.modules, "audits.evidence_match_reachability", SimpleNamespace(recompute_evidence=lambda e, p: {}))

    rows = audit.process_file((str(enriched), {"excluded", "wanted"}, {"wanted"}))

    assert [row["id"] for row in calls] == ["wanted"]
    assert rows[0]["name"] == "clean target"
    detail = rows[0]["candidate_detail"]
    assert detail["cert_records_before"] == [{"record_id": "before"}]
    assert detail["cert_records_after"] == [{"record_id": "after"}]
    assert detail["quality_pillars_v4"]["evidence"]["score"] == 8
    assert detail["_v4_module_breakdown"] == score["_v4_module_breakdown"]
    assert detail["native_evidence_assessment"] == {"strain_assessments": []}
    assert rows[0]["source_inputs"]["cleaned"] == str(cleaned.relative_to(tmp_path))
    json.dumps(rows, allow_nan=False)


def test_implementation_hashes_are_relative_to_selected_implementation(tmp_path):
    scripts = tmp_path / "scripts"
    (scripts / "config").mkdir(parents=True)
    (scripts / "example.py").write_text("VALUE = 1\n")
    (scripts / "config/enrichment_config.json").write_text("{}\n")

    hashes = audit.implementation_hashes(tmp_path)

    assert hashes["scripts/example.py"] == audit.sha(scripts / "example.py")
    assert hashes["scripts/config/enrichment_config.json"] == audit.sha(scripts / "config/enrichment_config.json")
    assert all(not Path(name).is_absolute() for name in hashes)


def test_worker_uses_selected_implementation_root(tmp_path, monkeypatch):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(audit.logging, "disable", lambda level: None)
    monkeypatch.setattr(audit, "ENRICHER", None, raising=False)
    monkeypatch.setitem(sys.modules, "enrich_supplements_v3", SimpleNamespace(
        __file__=str(scripts / "enrich_supplements_v3.py"), SupplementEnricherV3=lambda: "selected-enricher",
    ))

    audit.init_worker(tmp_path)

    assert sys.path[0] == str(scripts)
    assert audit.ENRICHER == "selected-enricher"


@pytest.mark.parametrize("target", ["wanted", "missing"])
def test_main_proves_target_counts_and_isolated_implementation(tmp_path, monkeypatch, target):
    input_root, implementation = tmp_path / "inputs", tmp_path / "implementation"
    for root in (input_root, implementation):
        (root / "scripts").mkdir(parents=True)
        (root / "scripts/enrich_supplements_v3.py").write_text("# fixture implementation\n")
        (root / "scripts/stage_manifest.py").write_text("# fixture manifest reader\n")
    sources = {}
    for stage, directory in [("score", "output_Example_scored/scored"),
                             ("enrich", "output_Example_enriched/enriched"),
                             ("clean", "output_Example/cleaned")]:
        file = input_root / "scripts/products" / directory / "batch.json"
        file.parent.mkdir(parents=True)
        file.write_text(json.dumps([{"id": "wanted"}, {"id": "excluded"}]))
        sources[stage] = [file]
    monkeypatch.setattr(audit, "ROOT", input_root)
    monkeypatch.setattr(audit, "select_stage_files", lambda directories, stage, **kwargs: sources[stage])
    monkeypatch.setattr(audit.subprocess, "check_output", lambda *a, **k: "fixture-revision\n")
    output = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["audit_corpus.py", "--output", str(output),
                                      "--target-ids", target, "--implementation-root", str(implementation)])

    class Pool:
        def __init__(self, **kwargs):
            assert kwargs["initargs"] == (str(implementation),)
            assert kwargs["mp_context"].get_start_method() == "spawn"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def map(self, func, tasks):
            assert list(tasks) == [(str(sources["enrich"][0]), {"wanted"}, {"wanted"})]
            yield [{"id": "wanted", "candidate": audit.summary({}), "rejected_evidence": [],
                    "cert_before": None, "evidence_before": [], "evidence_after": [],
                    "strains_before": [], "strains_after": [], "full_reenrichment": True}]

    monkeypatch.setattr(audit, "ProcessPoolExecutor", Pool)
    if target == "missing":
        with pytest.raises(SystemExit):
            audit.main()
        assert not output.exists()
        return

    audit.main()

    report = json.loads(output.read_text())
    assert report["complete"] is True
    assert report["product_count"] == report["baseline_product_count"] == 1
    assert report["full_baseline_product_count"] == 2
    assert report["full_reenrichment_ids"] == report["target_ids"] == ["wanted"]
    assert report["implementation_root"] == str(implementation)
    assert report["input_root"] == str(input_root)
    assert len(report["input_hashes"]) == 3
    assert report["candidate_code_hashes"]["scripts/enrich_supplements_v3.py"] == audit.sha(
        implementation / "scripts/enrich_supplements_v3.py"
    )
