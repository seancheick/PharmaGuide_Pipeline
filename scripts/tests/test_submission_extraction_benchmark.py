"""The holdout benchmark scores drafts against human-checked gold only.

Synthetic set: no photos, no provider. The gates in HOLDOUT.md are frozen;
this test pins their behaviour on a tiny development split.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from submission_review.extraction import benchmark
from submission_review.extraction.benchmark import BenchmarkError, evaluate

FIXTURE = (
    Path(__file__).parents[1] / "submission_review" / "fixtures" / "label_draft_v1_cases.json"
)


def _valid_draft() -> dict:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    return copy.deepcopy(next(c for c in cases if c.get("valid"))["payload"])


def _gold(key: str, expected: str = "draft", checkers=("ab", "cd")) -> dict:
    return {
        "schema_version": "gold_label_v1",
        "product_key": key,
        "checked_by": [{"checker": c, "checked_at": "2026-09-08T00:00:00Z", "human": True,
                        "independent": True, "model_output_seen": False} for c in checkers],
        "expected": expected,
        "identity": {"brand": "Example Brand", "product_name": "Magnesium Glycinate 200 mg", "barcode_digits_seen": "012345678905"},
        "serving": {"size": "2 capsules", "basis_text": "Amount Per Serving", "servings_per_container": "60", "amount": None},
        "other_ingredients": {"text": "Vegetable cellulose, rice flour", "disclosure_hint": "present"},
        "statements": ["Take two capsules daily with food."],
        "rows": [
            {
                "display_name": "Magnesium (as magnesium glycinate)",
                "amount": {"value": 200, "unit_text": "mg"},
                "owner": None,
                "parent_index": None,
                "is_blend_header": False,
                "percent_dv": 48,
                "form_text": "magnesium glycinate",
                "readable": True,
            },
            {"display_name": "Smudged row", "amount": None, "owner": None, "parent_index": None,
             "is_blend_header": False, "percent_dv": None, "form_text": None, "readable": False},
        ],
    }


CONFIG = {"provider": "fake", "model": "fake-1", "model_digest": "a" * 64,
          "prompt_version": "p1", "prompt_sha256": "b" * 64, "preparation": {"version": "prep1"}}


def _write_set(root: Path, entries: list[dict], golds: dict[str, dict], *, freeze=True, synthetic=True) -> None:
    (root / "gold").mkdir(parents=True)
    # Each fixture represents a distinct synthetic product, including the raw
    # barcode/brand/name. These are test identifiers, never a real gold set.
    for index, entry in enumerate(entries):
        key = entry["product_key"]
        identity = golds[key]["identity"]
        replacements = {"brand": entry["brand"], "product_name": f"Synthetic product {key}",
                        "barcode_digits_seen": f"{990000000000 + index:012d}"}
        for field, default in _gold(key)["identity"].items():
            if identity[field] == default:
                identity[field] = replacements[field]
    for key, gold in golds.items():
        (root / "gold" / f"{key}.json").write_text(json.dumps(gold), encoding="utf-8")
    for entry in entries:
        key = entry["product_key"]
        entry["gold_sha256"] = hashlib.sha256((root / entry["gold"]).read_bytes()).hexdigest()
        entry["photos"] = []
        for i in range(2):
            path = root / "photos" / key / f"{i}.jpg"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"SYNTHETIC TEST BYTES ONLY {key} {i}".encode())
            token = hashlib.md5(f"{key}/{i}".encode()).hexdigest()
            photo_id = f"{token[:8]}-{token[8:12]}-{token[12:16]}-{token[16:20]}-{token[20:]}"
            entry["photos"].append({"photo_id": photo_id, "path": str(path.relative_to(root)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest = {"schema_version": "submission_holdout_v1", "frozen_at": "2026-09-08T00:00:00Z", "products": entries,
                "candidates": [{"id": "candidate-a", "configuration": CONFIG}]}
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if freeze:
        benchmark.freeze_holdout(root, synthetic=synthetic)


def _entry(key: str, family: str, split: str = "development") -> dict:
    return {"product_key": key, "brand": family.split("/")[0], "family": family, "split": split,
            "gold": f"gold/{key}.json", "cases": []}


@pytest.fixture
def holdout(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "holdout"
    entries = [
        _entry("d-1", "brand-a/mag"),
        _entry("d-2", "brand-b/mag"),
        _entry("d-3", "brand-c/blur"),
        _entry("h-1", "brand-z/mag", "holdout"),
    ]
    golds = {
        "d-1": _gold("d-1"),
        "d-2": _gold("d-2"),
        "d-3": _gold("d-3", expected="abstain"),
        "h-1": _gold("h-1"),
    }
    _write_set(root, entries, golds)
    run = root / "runs" / "r1"
    run.mkdir(parents=True)
    return root, run


def _write(run: Path, key: str, payload: dict) -> None:
    root = next(p for p in run.parents if (p / "manifest.json").exists())
    manifest = json.loads((root / "manifest.json").read_text())
    entry = next(p for p in manifest["products"] if p["product_key"] == key)
    payload = copy.deepcopy(payload)
    inputs = []
    if payload.get("schema_version") == "label_draft_v1" and "evidence_snapshot" in payload:
        gold_identity = json.loads((root / entry["gold"]).read_text())["identity"]
        defaults = _valid_draft()["identity"]
        for field in ("brand", "product_name", "barcode_digits_seen"):
            if payload["identity"][field]["value"] == defaults[field]["value"]:
                payload["identity"][field]["value"] = gold_identity[field]
        old = list(payload["evidence_snapshot"])
        photos = entry["photos"]
        new_ids = {photo: photos[i]["photo_id"] for i, photo in enumerate(old)}
        payload["evidence_snapshot"] = {p["photo_id"]: p["sha256"] for p in photos}
        def replace_ids(value):
            if isinstance(value, dict):
                if value.get("photo_id") in new_ids:
                    value["photo_id"] = new_ids[value["photo_id"]]
                for child in value.values():
                    replace_ids(child)
            elif isinstance(value, list):
                for child in value:
                    replace_ids(child)
        replace_ids(payload)
        for sent, photo in zip(payload["sent_inputs"], photos):
            sent["original_sha256"] = sent["sent_sha256"] = photo["sha256"]
            sent.pop("crop", None)
            local = run / f"{key}-{sent['input_id']}.jpg"
            local.write_bytes((root / photo["path"]).read_bytes())
            inputs.append({"input_id": sent["input_id"], "path": local.name})
    (run / f"{key}.json").write_text(json.dumps(payload), encoding="utf-8")
    (run / "configuration.json").write_text(json.dumps({"candidate_id": "candidate-a", "configuration": CONFIG}))
    (run / f"{key}.meta.json").write_text(json.dumps({"sent_inputs": inputs}))


def _measure(run, key, *, latency=12, manual=100, assisted=60, critical=0):
    path = run / f"{key}.meta.json"
    meta = json.loads(path.read_text())
    meta.update({"latency_seconds": latency, "review": {"reviewer": "synthetic-reviewer", "completed": True,
                 "checked_at": "2026-09-09T00:00:00Z", "critical_errors": critical,
                 "manual_seconds": manual, "assisted_seconds": assisted,
                 "reviewed_output_sha256": hashlib.sha256((run / f"{key}.json").read_bytes()).hexdigest()}})
    path.write_text(json.dumps(meta))


def test_perfect_synthetic_development_run_only_provides_preliminary_metrics(holdout) -> None:
    root, run = holdout
    _write(run, "d-1", _valid_draft())
    _write(run, "d-2", _valid_draft())
    _write(run, "d-3", {**_valid_draft(), "abstained": True, "abstain_reason": "unreadable"})
    _measure(run, "d-1")
    _measure(run, "d-2", latency=90)
    _measure(run, "d-3")

    report = evaluate(root, run, "development")

    assert report["verdict"] != "qualifies", report["gates"]
    metrics = report["metrics"]
    assert metrics["row_recall"] == {"n": 2, "N": 2, "rate": 1.0, "ci95": (0.3424, 1.0)}
    assert metrics["tuple_exact_rate"]["rate"] == 1.0
    assert metrics["coverage"]["N"] == 2 and metrics["missing_coverage"] == []
    assert metrics["expected_abstentions_honoured_rate"] == {"n": 1, "N": 1, "rate": 1.0, "ci95": (0.2065, 1.0)}
    assert metrics["latency_p95_seconds"] == 90
    assert report["families"]["brand-a/mag"]["row_recall"]["N"] == 1
    assert report["products"] == 3  # the holdout product is not touched


def test_invented_rows_magnitude_errors_and_wrong_product_fail_gates(holdout) -> None:
    root, run = holdout
    bad = _valid_draft()
    bad["ingredient_rows"][0]["amount"]["value"] = {"unit_text": "mg", "value": 2000}
    extra = copy.deepcopy(bad["ingredient_rows"][0])
    extra["display_name"]["value"] = "Ashwagandha extract"
    bad["ingredient_rows"].append(extra)
    bad["identity"]["brand"]["value"] = "Other Brand"
    _write(run, "d-1", bad)
    _write(run, "d-2", _valid_draft())
    _write(run, "d-3", {"schema_version": "extraction_failure_v1", "code": "model_failure", "detail": "x"})

    report = evaluate(root, run, "development")

    metrics = report["metrics"]
    assert metrics["invented_actives"] == 1
    assert metrics["magnitude_errors"] == 1
    assert metrics["wrong_product_substitutions"] == 1
    assert metrics["tuple_exact_rate"] == {"n": 1, "N": 2, "rate": 0.5, "ci95": (0.0945, 0.9055)}
    assert metrics["expected_abstentions_honoured_rate"]["rate"] == 1.0  # a typed failure honours it
    assert report["verdict"] == "does_not_qualify"
    failed = {name for name, gate in report["gates"].items() if gate["passed"] is False}
    assert failed == {"invented_actives", "magnitude_errors", "wrong_product_substitutions",
                      "tuple_exact_rate", "field_fidelity", "dose_accuracy"}
    # The dimensions discriminate: the corrupted amount kept its printed unit
    # and its ownership, so only the dose reads as wrong.
    per_field = metrics["per_field"]
    assert per_field["dose"]["observations"]["rate"] < 1.0
    assert per_field["unit"]["observations"]["rate"] == 1.0
    assert per_field["blend_nesting"]["observations"]["rate"] == 1.0
    assert per_field["identity"]["observations"]["rate"] < 1.0


def test_per_field_reporting_separates_a_dose_error_from_a_unit_error(holdout) -> None:
    """An aggregate cannot tell these apart, and they are not the same risk."""
    root, run = holdout
    wrong_unit = _valid_draft()
    wrong_unit["ingredient_rows"][0]["amount"]["value"]["unit_text"] = "mcg"
    _write(run, "d-1", wrong_unit)
    _write(run, "d-2", _valid_draft())
    _write(run, "d-3", {**_valid_draft(), "abstained": True, "abstain_reason": "unreadable"})

    per_field = evaluate(root, run, "development")["metrics"]["per_field"]

    assert per_field["unit"]["observations"] == {"n": 1, "N": 2, "rate": 0.5, "ci95": (0.0945, 0.9055)}
    # A wrong unit is also a wrong dose; a wrong dose is not always a wrong unit.
    assert per_field["dose"]["observations"]["rate"] == 0.5
    assert per_field["row_presence"]["observations"]["rate"] == 1.0
    assert per_field["statements"]["observations"]["rate"] == 1.0
    # One of the two drafted products carries the error, and the product-level
    # denominator counts labels, not fields.
    assert per_field["unit"]["products_without_error"] == {"n": 1, "N": 2, "rate": 0.5, "ci95": (0.0945, 0.9055)}


def test_qualification_gates_use_product_level_dimension_rate(tmp_path: Path) -> None:
    """A product with two rows contributes one independent dose observation."""
    root = tmp_path / "holdout"
    entries = [
        _entry("d-1", "brand-a/mag"),
        _entry("d-2", "brand-b/mag"),
        _entry("d-3", "brand-c/blur"),
    ]
    golds = {key: _gold(key) for key in ("d-1", "d-2")}
    golds["d-3"] = _gold("d-3", expected="abstain")
    for gold in (golds["d-1"], golds["d-2"]):
        gold["rows"][1] = {
            "display_name": "Zinc",
            "amount": {"value": 10, "unit_text": "mg"},
            "owner": None,
            "parent_index": None,
            "is_blend_header": False,
            "percent_dv": None,
            "form_text": None,
            "readable": True,
        }
    _write_set(root, entries, golds)
    run = root / "runs" / "r1"
    run.mkdir(parents=True)

    first = _valid_draft()
    first["ingredient_rows"][0]["amount"]["value"]["value"] = 999
    extra = copy.deepcopy(first["ingredient_rows"][0])
    extra["display_name"]["value"] = "Zinc"
    extra["amount"]["value"]["value"] = 10
    first["ingredient_rows"].append(extra)
    second = _valid_draft()
    second_extra = copy.deepcopy(second["ingredient_rows"][0])
    second_extra["display_name"]["value"] = "Zinc"
    second_extra["amount"]["value"]["value"] = 10
    second["ingredient_rows"].append(second_extra)
    _write(run, "d-1", first)
    _write(run, "d-2", second)
    _write(run, "d-3", {**_valid_draft(), "abstained": True, "abstain_reason": "unreadable"})

    report = evaluate(root, run, "development")
    per_field = report["metrics"]["per_field"]["dose"]
    assert per_field["observations"]["rate"] == 0.75
    assert per_field["products_without_error"]["rate"] == 0.5
    assert report["gates"]["dose_accuracy"]["observed"] == 0.5


def test_gold_must_transcribe_printed_statements(holdout) -> None:
    root, _ = holdout
    gold = json.loads((root / "gold" / "d-1.json").read_text())
    del gold["statements"]
    (root / "gold" / "d-1.json").write_text(json.dumps(gold))
    entry = json.loads((root / "manifest.json").read_text())
    with pytest.raises(benchmark.BenchmarkError, match="statements"):
        benchmark.load_gold(root, next(
            p | {"gold_sha256": hashlib.sha256((root / "gold" / "d-1.json").read_bytes()).hexdigest()}
            for p in entry["products"] if p["product_key"] == "d-1"))


def test_a_missed_warning_is_reported_without_blocking_qualification(holdout) -> None:
    """Warnings are measured, not gated: a missed direction is not a dose."""
    root, run = holdout
    silent = _valid_draft()
    silent["statements"] = []
    _write(run, "d-1", silent)
    _write(run, "d-2", _valid_draft())
    _write(run, "d-3", {**_valid_draft(), "abstained": True, "abstain_reason": "unreadable"})

    report = evaluate(root, run, "development")

    assert report["metrics"]["per_field"]["statements"]["observations"]["rate"] == 0.5
    assert "statements" not in report["gates"]


def test_missing_invalid_and_abstained_outputs_are_missing_coverage(holdout) -> None:
    root, run = holdout
    _write(run, "d-1", {"schema_version": "label_draft_v1", "not": "a draft"})
    _write(run, "d-2", {**_valid_draft(), "abstained": True, "abstain_reason": "glare"})
    _write(run, "d-3", _valid_draft())  # drafted where an abstention was expected

    report = evaluate(root, run, "development")

    metrics = report["metrics"]
    assert metrics["schema_safe_rate"] == {"n": 2, "N": 3, "rate": 0.6667, "ci95": (0.2077, 0.9385)}
    assert [m["product_key"] for m in metrics["missing_coverage"]] == ["d-1", "d-2"]
    assert metrics["missing_coverage"][0]["output"] == "invalid"
    assert metrics["row_recall"]["N"] == 2
    assert metrics["row_recall_including_missing_coverage"] == {"n": 0, "N": 2, "rate": 0.0, "ci95": (0.0, 0.6576)}
    assert metrics["expected_abstentions_honoured_rate"]["rate"] == 0.0
    assert report["verdict"] == "does_not_qualify"


def test_gold_must_be_checked_by_two_humans(holdout) -> None:
    root, run = holdout
    single = _gold("d-1", checkers=("ab",))
    (root / "gold" / "d-1.json").write_text(json.dumps(single), encoding="utf-8")
    with pytest.raises(BenchmarkError, match="changed|checksum"):
        evaluate(root, run, "development")
    tainted = _gold("d-1")
    tainted["checked_by"][1]["model"] = "gemma4"
    (root / "gold" / "d-1.json").write_text(json.dumps(tainted), encoding="utf-8")
    with pytest.raises(BenchmarkError, match="changed|checksum"):
        evaluate(root, run, "development")


def test_families_may_not_leak_across_splits(tmp_path: Path) -> None:
    root = tmp_path / "leak"
    with pytest.raises(BenchmarkError, match="both splits"):
        _write_set(root, [_entry("d-1", "brand-a/mag"), _entry("h-1", "brand-a/mag", "holdout")],
                   {"d-1": _gold("d-1"), "h-1": _gold("h-1")})


def test_holdout_ledger_marks_a_second_evaluation_as_consumed(holdout, capsys) -> None:
    root, run = holdout
    _write(run, "h-1", _valid_draft())
    argv = ["--holdout", str(root), "--run", "runs/r1", "--split", "holdout",
            "--configuration", "candidate-a", "--out", str(root / "report.json")]
    assert benchmark.main(argv) == 0
    first = json.loads((root / "report.json").read_text())
    assert first["holdout_consumed"] is False and first["verdict"] != "qualifies"
    assert benchmark.main(argv) == 0
    second = json.loads((root / "report.json").read_text())
    assert second["holdout_consumed"] is True
    assert second["verdict"] != "qualifies"
    ledger = (root / "holdout_runs.jsonl").read_text().splitlines()
    assert len(ledger) == 2 and json.loads(ledger[1])["earlier_runs_of_this_configuration"] == 1


def test_holdout_split_requires_a_named_configuration(holdout) -> None:
    root, _run = holdout
    with pytest.raises(SystemExit):
        benchmark.main(["--holdout", str(root), "--run", "runs/r1", "--split", "holdout"])


REFERENCE = {
    "source_name": "NIH DSLD",
    "source_record_id": "178392",
    "formula_fingerprint": "f" * 64,
    "imported_at": "2026-09-10T00:00:00Z",
    "disagreements_resolved": 3,
}


def _confirmer(name: str = "ab", *, confirmed: bool = True) -> dict:
    return {"checker": name, "checked_at": "2026-09-10T00:00:00Z", "human": True,
            "independent": True, "model_output_seen": False,
            "confirmed_physical_label": confirmed}


def _load(root: Path, key: str, gold: dict):
    """Rewrite one gold file and read it back through the real loader."""
    path = root / "gold" / f"{key}.json"
    path.write_text(json.dumps(gold), encoding="utf-8")
    entry = dict(next(p for p in json.loads((root / "manifest.json").read_text())["products"]
                      if p["product_key"] == key))
    entry["gold_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return benchmark.load_gold(root, entry)


def test_reference_sourced_gold_needs_only_one_human_confirmation(holdout) -> None:
    """The second reading already exists; it was written from the label."""
    root, _ = holdout
    gold = {**_gold("d-1"), "sourced_from": REFERENCE, "checked_by": [_confirmer()]}
    assert _load(root, "d-1", gold)["sourced_from"]["source_record_id"] == "178392"


def test_reference_sourced_gold_still_needs_the_physical_label_confirmed(holdout) -> None:
    """The one judgement no record and no tool can make."""
    root, _ = holdout
    gold = {**_gold("d-1"), "sourced_from": REFERENCE,
            "checked_by": [_confirmer(confirmed=False)]}
    with pytest.raises(BenchmarkError, match="confirmed the physical label"):
        _load(root, "d-1", gold)


def test_a_model_may_never_be_named_as_the_gold_source(holdout) -> None:
    """The route exists only because the source is independent of any model."""
    root, _ = holdout
    for poison in ("model", "provider", "generated_by", "prompt_version"):
        gold = {**_gold("d-1"), "sourced_from": {**REFERENCE, poison: "qwen3-vl:4b"},
                "checked_by": [_confirmer()]}
        with pytest.raises(BenchmarkError, match="a model may not be a gold source"):
            _load(root, "d-1", gold)


def test_an_import_with_unsettled_disagreements_is_not_gold(holdout) -> None:
    root, _ = holdout
    missing = {k: v for k, v in REFERENCE.items() if k != "disagreements_resolved"}
    gold = {**_gold("d-1"), "sourced_from": missing, "checked_by": [_confirmer()]}
    with pytest.raises(BenchmarkError, match="how many disagreements were resolved"):
        _load(root, "d-1", gold)
    for key in ("source_name", "source_record_id", "formula_fingerprint"):
        thin = {k: v for k, v in REFERENCE.items() if k != key}
        gold = {**_gold("d-1"), "sourced_from": thin, "checked_by": [_confirmer()]}
        with pytest.raises(BenchmarkError, match=f"sourced_from needs {key}"):
            _load(root, "d-1", gold)


def test_reference_source_requires_utc_sha256_provenance(holdout) -> None:
    root, _ = holdout
    for imported_at in ("2026-09-10T00:00:00+05:00", "2026-09-10T00:00:00"):
        gold = {**_gold("d-1"), "sourced_from": {**REFERENCE, "imported_at": imported_at},
                "checked_by": [_confirmer()]}
        with pytest.raises(BenchmarkError, match="UTC timestamp"):
            _load(root, "d-1", gold)
    gold = {**_gold("d-1"), "sourced_from": {**REFERENCE, "formula_fingerprint": "not-a-hash"},
            "checked_by": [_confirmer()]}
    with pytest.raises(BenchmarkError, match="formula_fingerprint"):
        _load(root, "d-1", gold)


def test_without_a_reference_two_people_are_still_required(holdout) -> None:
    """The original route is unchanged; the amendment adds one, removes none."""
    root, _ = holdout
    gold = {**_gold("d-1"), "checked_by": [_confirmer()]}
    with pytest.raises(BenchmarkError, match="two distinct human checkers"):
        _load(root, "d-1", gold)
