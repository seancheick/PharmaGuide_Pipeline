"""The holdout benchmark scores drafts against human-checked gold only.

Synthetic set: no photos, no provider. The gates in HOLDOUT.md are frozen;
this test pins their behaviour on a tiny development split.
"""
from __future__ import annotations

import copy
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
        "checked_by": [{"checker": c, "checked_at": "2026-09-08T00:00:00Z"} for c in checkers],
        "expected": expected,
        "identity": {"brand": "Example Brand", "product_name": "Magnesium Glycinate 200 mg"},
        "rows": [
            {
                "display_name": "Magnesium (as magnesium glycinate)",
                "amount": {"value": 200, "unit_text": "mg"},
                "owner": None,
                "readable": True,
            },
            {"display_name": "Smudged row", "amount": None, "owner": None, "readable": False},
        ],
    }


def _write_set(root: Path, entries: list[dict], golds: dict[str, dict]) -> None:
    (root / "gold").mkdir(parents=True)
    for key, gold in golds.items():
        (root / "gold" / f"{key}.json").write_text(json.dumps(gold), encoding="utf-8")
    manifest = {"schema_version": "submission_holdout_v1", "frozen_at": "2026-09-08", "products": entries}
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _entry(key: str, family: str, split: str = "development") -> dict:
    return {"product_key": key, "family": family, "split": split, "gold": f"gold/{key}.json", "cases": []}


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
    (run / f"{key}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_perfect_development_run_qualifies(holdout) -> None:
    root, run = holdout
    _write(run, "d-1", _valid_draft())
    _write(run, "d-2", _valid_draft())
    _write(run, "d-3", {**_valid_draft(), "abstained": True, "abstain_reason": "unreadable"})
    (run / "d-1.meta.json").write_text(json.dumps({"latency_seconds": 12, "cost_microcents": 5}))
    (run / "d-2.meta.json").write_text(json.dumps({"latency_seconds": 90, "cold_start": True}))

    report = evaluate(root, run, "development")

    assert report["verdict"] == "qualifies", report["gates"]
    metrics = report["metrics"]
    assert metrics["row_recall"] == {"n": 2, "N": 2, "rate": 1.0, "ci95": (0.3424, 1.0)}
    assert metrics["tuple_exact_rate"]["rate"] == 1.0
    assert metrics["coverage"]["N"] == 2 and metrics["missing_coverage"] == []
    assert metrics["expected_abstentions_honoured_rate"] == {"n": 1, "N": 1, "rate": 1.0, "ci95": (0.2065, 1.0)}
    assert metrics["latency_p95_seconds"] == 12 and metrics["cold_start_latency_seconds"] == [90.0]
    assert metrics["cost_microcents_total"] == 5
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
    failed = {name for name, gate in report["gates"].items() if not gate["passed"]}
    assert failed == {"invented_actives", "magnitude_errors", "wrong_product_substitutions", "tuple_exact_rate"}


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
    assert metrics["row_recall"]["N"] == 0  # nothing was drafted, so no quality claim
    assert metrics["row_recall_including_missing_coverage"] == {"n": 0, "N": 2, "rate": 0.0, "ci95": (0.0, 0.6576)}
    assert metrics["expected_abstentions_honoured_rate"]["rate"] == 0.0
    assert report["verdict"] == "does_not_qualify"


def test_gold_must_be_checked_by_two_humans(holdout) -> None:
    root, run = holdout
    single = _gold("d-1", checkers=("ab",))
    (root / "gold" / "d-1.json").write_text(json.dumps(single), encoding="utf-8")
    with pytest.raises(BenchmarkError, match="two distinct human checkers"):
        evaluate(root, run, "development")
    tainted = _gold("d-1")
    tainted["checked_by"][1]["model"] = "gemma4"
    (root / "gold" / "d-1.json").write_text(json.dumps(tainted), encoding="utf-8")
    with pytest.raises(BenchmarkError, match="human-checked"):
        evaluate(root, run, "development")


def test_families_may_not_leak_across_splits(tmp_path: Path) -> None:
    root = tmp_path / "leak"
    _write_set(
        root,
        [_entry("d-1", "brand-a/mag"), _entry("h-1", "brand-a/mag", "holdout")],
        {"d-1": _gold("d-1"), "h-1": _gold("h-1")},
    )
    with pytest.raises(BenchmarkError, match="both splits"):
        evaluate(root, root / "runs" / "none", "development")


def test_holdout_ledger_marks_a_second_evaluation_as_consumed(holdout, capsys) -> None:
    root, run = holdout
    _write(run, "h-1", _valid_draft())
    argv = ["--holdout", str(root), "--run", "runs/r1", "--split", "holdout",
            "--configuration", "fake:sha256:abc:p1:prep1", "--out", str(root / "report.json")]
    assert benchmark.main(argv) == 0
    first = json.loads((root / "report.json").read_text())
    assert first["holdout_consumed"] is False and first["verdict"] == "qualifies"
    assert benchmark.main(argv) == 0
    second = json.loads((root / "report.json").read_text())
    assert second["holdout_consumed"] is True
    assert "already evaluated 1x" in capsys.readouterr().err
    ledger = (root / "holdout_runs.jsonl").read_text().splitlines()
    assert len(ledger) == 2 and json.loads(ledger[1])["earlier_runs_of_this_configuration"] == 1


def test_holdout_split_requires_a_named_configuration(holdout) -> None:
    root, _run = holdout
    with pytest.raises(SystemExit):
        benchmark.main(["--holdout", str(root), "--run", "runs/r1", "--split", "holdout"])
