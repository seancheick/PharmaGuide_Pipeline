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


def test_chained_baseline_preserves_ancestor_changes_and_child_overrides(baseline_report):
    parent, baseline, hashes, report = baseline_report
    child = parent.with_name("child.json")
    child_report = {**report, "baseline_report": parent.name,
                    "baseline_report_sha256": audit.sha(parent), "canaries": [],
                    "changes": [{"id": "canary", "candidate": {**baseline["canary"], "score": 60}}]}
    child.write_text(json.dumps(child_report))

    result, digest = audit.load_baseline_report(child, baseline, hashes)

    assert {pid: row["score"] for pid, row in result.items()} == {
        "changed": 40, "canary": 60, "unchanged": 30,
    }
    assert digest == audit.sha(child)
    assert baseline["changed"]["score"] == 10


@pytest.mark.parametrize("defect", ["missing_parent", "missing_digest", "wrong_digest", "cycle",
                                    "incomplete", "count", "baseline_count", "inputs", "errors"])
def test_chained_baseline_rejects_unproven_ancestors(baseline_report, defect):
    parent, baseline, hashes, report = baseline_report
    child = parent.with_name("child.json")
    child_report = {**report, "changes": [], "canaries": [], "baseline_report": str(parent)}
    if defect == "incomplete": report["complete"] = False
    if defect == "count": report["product_count"] = 2
    if defect == "baseline_count": report["baseline_product_count"] = 2
    if defect == "inputs": report["input_hashes"] = {"stale": "hash"}
    if defect == "errors": report["errors"] = ["failed ancestor"]
    if defect == "cycle":
        report.update(baseline_report=str(child), baseline_report_sha256="0" * 64)
    parent.write_text(json.dumps(report))
    child_report["baseline_report_sha256"] = audit.sha(parent)
    if defect == "missing_parent": child_report["baseline_report"] = str(parent.with_name("missing.json"))
    if defect == "missing_digest": child_report.pop("baseline_report_sha256")
    if defect == "wrong_digest": child_report["baseline_report_sha256"] = "0" * 64
    child.write_text(json.dumps(child_report))

    with pytest.raises(ValueError, match="[Bb]aseline"):
        audit.load_baseline_report(child, baseline, hashes)


@pytest.mark.parametrize("value", ["", " ", ",", "one,,two"])
def test_empty_target_tokens_are_rejected(value):
    with pytest.raises(ValueError, match="target"):
        audit.parse_target_ids(value)


def test_existing_report_cannot_be_overwritten_even_if_not_immediate_baseline(tmp_path, monkeypatch):
    scripts = tmp_path / "scripts"
    (scripts / "products").mkdir(parents=True)
    (scripts / "enrich_supplements_v3.py").write_text("# fixture")
    output = tmp_path / "ancestor.json"
    output.write_text("immutable ancestor")
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["audit_corpus.py", "--output", str(output)])
    with pytest.raises(SystemExit, match="2"):
        audit.main()
    assert output.read_text() == "immutable ancestor"


def test_target_parser_and_filter_do_not_turn_empty_selection_into_full_run():
    rows = [{"id": "one"}, {"dsld_id": "two"}, {"id": "three"}]
    assert audit.parse_target_ids(" one, two,one ") == {"one", "two"}
    assert audit.parse_target_ids(None) is None
    assert audit.target_products(rows, {"two"}) == [{"dsld_id": "two"}]
    assert audit.target_products(rows, set()) == []
    assert audit.target_products(rows, None) == rows


def test_extra_clean_reenrichment_preserves_full_corpus_selection():
    assert audit.merge_reenrichment_ids({"canary"}, {"derivative"}, {"canary", "derivative", "other"}) == {"canary", "derivative"}
    assert audit.merge_reenrichment_ids({"canary"}, None, {"canary", "other"}) == {"canary"}
    with pytest.raises(ValueError, match="absent"):
        audit.merge_reenrichment_ids({"canary"}, {"missing"}, {"canary"})


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
    score = {"assessment_readiness": {"identity": "unresolved", "is_ready": False},
             "quality_pillars_v4": {"evidence": {"score": 8, "detail": {"tags": {"native", "reviewed"}}}},
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
    assert rows[0]["readiness"] == score["assessment_readiness"]
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


@pytest.mark.parametrize("explicit_inputs", [False, True])
def test_worker_uses_selected_implementation_root(tmp_path, monkeypatch, explicit_inputs):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(audit.logging, "disable", lambda level: None)
    monkeypatch.setattr(audit, "ENRICHER", None, raising=False)
    monkeypatch.setattr(audit, "ROOT", audit.ROOT)
    original_root = audit.ROOT
    monkeypatch.setitem(sys.modules, "enrich_supplements_v3", SimpleNamespace(
        __file__=str(scripts / "enrich_supplements_v3.py"), SupplementEnricherV3=lambda: "selected-enricher",
    ))

    if explicit_inputs:
        audit.init_worker(tmp_path, tmp_path / "separate-inputs")
    else:
        audit.init_worker(tmp_path)

    assert sys.path[0] == str(scripts)
    assert audit.ENRICHER == "selected-enricher"
    assert audit.ROOT == (tmp_path / "separate-inputs" if explicit_inputs else original_root)


@pytest.mark.parametrize("target", ["wanted", "missing"])
@pytest.mark.parametrize("scenario", ["default", "input_root", "chain", "ancestor_changed"])
def test_main_proves_target_counts_and_isolated_implementation(tmp_path, monkeypatch, target, scenario):
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
    monkeypatch.setattr(audit, "ROOT", implementation if scenario == "input_root" else input_root)

    def stage_files(directories, stage, **kwargs):
        assert all(path.is_relative_to(input_root) for path in directories)
        return sources[stage]

    monkeypatch.setattr(audit, "select_stage_files", stage_files)
    monkeypatch.setattr(audit.subprocess, "check_output", lambda *a, **k: "fixture-revision\n")
    output = tmp_path / "report.json"
    argv = ["audit_corpus.py", "--output", str(output), "--target-ids", target,
            "--implementation-root", str(implementation)]
    if scenario == "input_root": argv.extend(["--input-root", str(input_root)])
    candidate = audit.summary({})
    if scenario in {"chain", "ancestor_changed"}:
        hashes = {str(file.relative_to(input_root)): audit.sha(file)
                  for files in sources.values() for file in files}
        parent = tmp_path / "parent.json"
        child = tmp_path / "child.json"
        candidate = audit.summary({"quality_score_v4_100": 40})
        parent_report = {"complete": True, "product_count": 2, "baseline_product_count": 2,
                         "input_hashes": hashes, "errors": [], "canaries": [],
                         "changes": [{"id": "wanted", "candidate": candidate}]}
        parent.write_text(json.dumps(parent_report))
        child.write_text(json.dumps({**parent_report, "changes": [],
            "baseline_report": str(parent), "baseline_report_sha256": audit.sha(parent)}))
        argv.extend(["--baseline-report", str(child)])
    monkeypatch.setattr(sys, "argv", argv)

    class Pool:
        def __init__(self, **kwargs):
            assert kwargs["initargs"] == (str(implementation), str(input_root))
            assert kwargs["mp_context"].get_start_method() == "spawn"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def map(self, func, tasks):
            assert list(tasks) == [(str(sources["enrich"][0]), {"wanted"}, {"wanted"})]
            if scenario == "ancestor_changed":
                parent.write_text(parent.read_text() + "\n")
            yield [{"id": "wanted", "candidate": candidate, "rejected_evidence": [],
                    "cert_before": None, "evidence_before": [], "evidence_after": [],
                    "strains_before": [], "strains_after": [], "full_reenrichment": True}]

    monkeypatch.setattr(audit, "ProcessPoolExecutor", Pool)
    if target == "missing":
        with pytest.raises(SystemExit):
            audit.main()
        assert not output.exists()
        return

    if scenario == "ancestor_changed":
        with pytest.raises((ValueError, RuntimeError), match="[Bb]aseline"):
            audit.main()
        assert json.loads(output.read_text())["complete"] is False
        return

    audit.main()

    report = json.loads(output.read_text())
    assert report["complete"] is True
    assert report["product_count"] == report["baseline_product_count"] == 1
    assert report["full_baseline_product_count"] == 2
    assert report["full_reenrichment_ids"] == report["target_ids"] == ["wanted"]
    assert report["implementation_root"] == str(implementation)
    assert report["input_root"] == str(input_root)
    assert report["changes"] == []
    assert len(report["input_hashes"]) == 3
    assert report["candidate_code_hashes"]["scripts/enrich_supplements_v3.py"] == audit.sha(
        implementation / "scripts/enrich_supplements_v3.py"
    )
