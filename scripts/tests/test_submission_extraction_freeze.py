"""Freeze and qualification mechanics, with explicitly fabricated test bytes only.

These tests prove the validator; they are never a real 60-product gold receipt.
"""
import copy
import hashlib
import json

import pytest

from submission_review.extraction import benchmark
from test_submission_extraction_benchmark import _entry, _gold, _write_set, _write, _valid_draft, _measure, holdout


CASES = ["glare", "curved_bottle", "tiny_print", "split_facts", "combined_facts_other",
         "wrong_slot", "mismatched_bottle", "ambiguous_serving", "nested_blend", "multiple_forms",
         "unit_mg", "unit_mcg", "unit_g", "unit_IU", "unit_CFU", "unit_AFU", "dv_only",
         "serving_range", "foreign_language", "handwritten", "expired_date", "unreadable"]


def _population(root, *, freeze=True):
    entries = [_entry(f"d-{i}", f"development-brand-{i}") for i in range(20)]
    entries += [_entry(f"h-{i}", f"holdout-brand-{i}", "holdout") for i in range(40)]
    for e in entries:
        e["cases"] = CASES.copy()  # Synthetic validation of coverage mechanics.
    _write_set(root, entries, {e["product_key"]: _gold(e["product_key"], "abstain" if e["product_key"] in ("h-38", "h-39") else "draft") for e in entries}, freeze=freeze, synthetic=False)
    return entries


def test_tiny_set_cannot_freeze_for_qualification(tmp_path):
    _write_set(tmp_path, [_entry("h-1", "brand", "holdout")], {"h-1": _gold("h-1")}, freeze=False)
    with pytest.raises(benchmark.BenchmarkError, match="20 development.*40 holdout"):
        benchmark.freeze_holdout(tmp_path)


@pytest.mark.parametrize("change", ["duplicate", "brand", "cases", "checker", "gold_sha256", "photo_sha256"])
def test_freeze_rejects_invalid_population_and_attestations(tmp_path, change):
    _population(tmp_path, freeze=False)
    path = tmp_path / "manifest.json"
    manifest = json.loads(path.read_text())
    if change == "duplicate":
        manifest["products"][1]["product_key"] = manifest["products"][0]["product_key"]
    elif change == "brand":
        manifest["products"][-1]["brand"] = manifest["products"][0]["brand"]
    elif change == "cases":
        for p in manifest["products"]:
            p["cases"] = []
    elif change == "checker":
        gold_path = tmp_path / manifest["products"][0]["gold"]
        gold = json.loads(gold_path.read_text())
        gold["checked_by"][1]["model_output_seen"] = True
        gold_path.write_text(json.dumps(gold))
        manifest["products"][0]["gold_sha256"] = hashlib.sha256(gold_path.read_bytes()).hexdigest()
    elif change == "gold_sha256":
        manifest["products"][0]["gold_sha256"] = "0" * 64
    else:
        manifest["products"][0]["photos"][0]["sha256"] = "0" * 64
    path.write_text(json.dumps(manifest))
    with pytest.raises(benchmark.BenchmarkError):
        benchmark.freeze_holdout(tmp_path)


@pytest.mark.parametrize("part", ["gold", "photo", "manifest", "receipt"])
def test_frozen_bytes_cannot_change(holdout, part):
    root, run = holdout
    _write(run, "h-1", _valid_draft())
    manifest = json.loads((root / "manifest.json").read_text())
    path = {"gold": root / "gold/h-1.json", "photo": root / manifest["products"][0]["photos"][0]["path"],
            "manifest": root / "manifest.json", "receipt": root / "freeze.json"}[part]
    if part == "receipt":
        benchmark.evaluate(root, run, "holdout")  # Ledger binds the first receipt.
        receipt = json.loads(path.read_text())
        receipt["mode"] = "qualification"
        path.write_text(json.dumps(receipt))
    else:
        path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(benchmark.BenchmarkError):
        benchmark.evaluate(root, run, "holdout")


def test_run_requires_predeclared_unchanged_candidate(holdout):
    root, run = holdout
    _write(run, "h-1", _valid_draft())
    path = run / "configuration.json"
    config = json.loads(path.read_text())
    config["configuration"]["preparation"]["version"] = "tuned-after-exposure"
    path.write_text(json.dumps(config))
    with pytest.raises(benchmark.BenchmarkError, match="predeclared"):
        benchmark.evaluate(root, run, "holdout")


def test_output_and_sent_bytes_must_belong_to_own_product(holdout):
    root, run = holdout
    _write(run, "d-1", _valid_draft())
    _write(run, "d-2", _valid_draft())
    (run / "d-1.json").write_bytes((run / "d-2.json").read_bytes())
    report = benchmark.evaluate(root, run, "development")
    assert report["per_product"][0]["output"] == "invalid"
    _write(run, "d-1", _valid_draft())
    (run / "d-1-input-1.jpg").write_bytes(b"different sent bytes")
    report = benchmark.evaluate(root, run, "development")
    assert report["per_product"][0]["output"] == "invalid"


def test_run_identity_includes_measurements_and_exact_frozen_receipt(holdout):
    root, run = holdout
    _write(run, "d-1", _valid_draft())
    before = benchmark.evaluate(root, run, "development")
    _measure(run, "d-1")
    after = benchmark.evaluate(root, run, "development")
    assert before["run_sha256"] != after["run_sha256"]
    assert after["freeze_sha256"] == hashlib.sha256((root / "freeze.json").read_bytes()).hexdigest()
    (run / "d-1-input-1.jpg").write_bytes(b"changed sent image")
    changed = benchmark.evaluate(root, run, "development")
    assert after["run_sha256"] != changed["run_sha256"]


def test_freeze_rejects_configuration_without_immutable_model_and_prompt_digests(tmp_path):
    _population(tmp_path, freeze=False)
    path = tmp_path / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["candidates"][0]["configuration"].pop("model_digest")
    path.write_text(json.dumps(manifest))
    with pytest.raises(benchmark.BenchmarkError, match="digest"):
        benchmark.freeze_holdout(tmp_path)


@pytest.mark.parametrize("path,value", [(["serving", "amount"], "2 capsules"),
                                      (["identity", "brand"], []),
                                      (["rows", 0, "display_name"], {}),
                                      (["rows", 0, "percent_dv"], []),
                                      (["rows"], [])])
def test_gold_cannot_freeze_unscorable_malformed_readable_fields(tmp_path, path, value):
    gold = _gold("h-1")
    target = gold
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(benchmark.BenchmarkError):
        _write_set(tmp_path, [_entry("h-1", "brand", "holdout")], {"h-1": gold})


def test_copied_source_photo_cannot_cross_product_boundaries(tmp_path):
    _population(tmp_path, freeze=False)
    path = tmp_path / "manifest.json"
    manifest = json.loads(path.read_text())
    first = manifest["products"][0]["photos"][0]
    copied = manifest["products"][-1]["photos"][0]
    (tmp_path / copied["path"]).write_bytes((tmp_path / first["path"]).read_bytes())
    copied["sha256"] = first["sha256"]
    path.write_text(json.dumps(manifest))
    with pytest.raises(benchmark.BenchmarkError, match="photo.*product"):
        benchmark.freeze_holdout(tmp_path)


def test_duplicate_candidate_configuration_is_rejected_before_exposure(tmp_path):
    _population(tmp_path, freeze=False)
    path = tmp_path / "manifest.json"
    manifest = json.loads(path.read_text())
    alias = copy.deepcopy(manifest["candidates"][0])
    alias["id"] = "candidate-alias"
    manifest["candidates"].append(alias)
    path.write_text(json.dumps(manifest))
    with pytest.raises(benchmark.BenchmarkError, match="configuration"):
        benchmark.freeze_holdout(tmp_path)


@pytest.mark.parametrize("duplicate", ["barcode", "brand_and_name", "gold_brand_cross_split"])
def test_real_gold_identity_governs_population_uniqueness(tmp_path, duplicate):
    _population(tmp_path, freeze=False)
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    first, last = manifest["products"][0], manifest["products"][-1]
    original = json.loads((tmp_path / first["gold"]).read_text())
    path = tmp_path / last["gold"]
    gold = json.loads(path.read_text())
    if duplicate == "barcode":
        gold["identity"]["barcode_digits_seen"] = original["identity"]["barcode_digits_seen"]
    elif duplicate == "brand_and_name":
        gold["identity"].update(brand=original["identity"]["brand"], product_name=original["identity"]["product_name"], barcode_digits_seen=None)
    else:
        gold["identity"]["brand"] = original["identity"]["brand"]
        gold["identity"]["product_name"] = "Different product in same real brand"
    path.write_text(json.dumps(gold))
    last["gold_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(benchmark.BenchmarkError, match="identity|brand|barcode"):
        benchmark.freeze_holdout(tmp_path)


def test_qualification_requires_all_evidence_and_can_only_be_earned_once(tmp_path):
    _population(tmp_path)
    run = tmp_path / "run"
    run.mkdir()
    for i in range(40):
        draft = _valid_draft()
        if i >= 38:
            draft.update(abstained=True, abstain_reason="unreadable")
        _write(run, f"h-{i}", draft)
        _measure(run, f"h-{i}")
    report = benchmark.evaluate(tmp_path, run, "holdout")
    assert report["verdict"] == "qualifies", report["gates"]
    assert report["metrics"]["reviewer_median_time_reduction"] == 0.4
    replay = benchmark.evaluate(tmp_path, run, "holdout")
    assert replay["holdout_consumed"] is True
    assert replay["verdict"] == "does_not_qualify"


@pytest.mark.parametrize("issue", ["missing_review", "critical", "median", "tail", "latency", "missing_latency", "stale_review", "partial_wrong_brand"])
def test_operational_gates_fail_or_remain_not_evaluated(tmp_path, issue):
    _population(tmp_path)
    run = tmp_path / "run"
    run.mkdir()
    for i in range(40):
        draft = _valid_draft()
        if i >= 38:
            draft.update(abstained=True, abstain_reason="unreadable")
        elif issue == "partial_wrong_brand" and i == 0:
            draft["identity"]["brand"].update(value="Clearly Other Product Brand", status="partial")
        _write(run, f"h-{i}", draft)
        _measure(run, f"h-{i}", assisted=80 if issue == "median" else 60)
    for i in range(4):
        path = run / f"h-{i}.meta.json"
        meta = json.loads(path.read_text())
        if issue == "missing_review": meta.pop("review")
        elif issue == "critical": meta["review"]["critical_errors"] = 1
        elif issue == "tail": meta["review"]["assisted_seconds"] = 120
        elif issue == "latency": meta.update(latency_seconds=80, cold_start=True)
        elif issue == "missing_latency": meta.pop("latency_seconds")
        elif issue == "stale_review": meta["review"]["reviewed_output_sha256"] = "0" * 64
        path.write_text(json.dumps(meta))
    report = benchmark.evaluate(tmp_path, run, "holdout")
    assert report["verdict"] != "qualifies"
    if issue in ("missing_review", "missing_latency", "stale_review"):
        assert report["verdict"] == "not_evaluated"
