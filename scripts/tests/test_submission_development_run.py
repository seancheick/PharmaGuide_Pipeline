"""Driving the real extractor over a synthetic development split.

Synthetic photographs prove wiring and nothing else: no accuracy claim can come
from a label this test drew itself. What is checked here is that the same
preparation, extractor and envelope the queue worker uses can be run over the
frozen set layout, that the output is scorable, and that the held-out split
cannot be consumed from a tuning loop.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest
from PIL import Image

from submission_review.extraction import benchmark
from submission_review.extraction.adapters.fake_adapter import FakeAdapter
from submission_review.extraction.development import (
    DevelopmentRunError,
    gold_template,
    intake_manifest_entry,
    run_development_split,
)
from submission_review.extraction.extractor import ExtractionConfig, LabelDraftExtractor


def _config() -> ExtractionConfig:
    return ExtractionConfig(
        provider="fake",
        model="fake-1",
        model_digest="c" * 64,
        prompt_version="p1",
        retention_policy_version="local-only-v1",
    )


def _jpeg(seed: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (48, 36), (seed % 255, 90, 140)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _build_set(root: Path, keys=("d-1", "d-2"), split: str = "development",
               prep_version: str = 'prep_v1') -> None:
    (root / "gold").mkdir(parents=True, exist_ok=True)
    entries = []
    for index, key in enumerate(keys):
        photo_dir = root / "photos" / key
        photo_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for shot in range(2):
            path = photo_dir / f"{shot}.jpg"
            path.write_bytes(_jpeg(index * 10 + shot))
            paths.append(path)
        entry = intake_manifest_entry(key, f"Brand {index}/line", split, paths, root)
        # A person fills the blank template in; these stand in for that.
        gold = gold_template(key)
        gold["identity"]["brand"] = f"Brand {index}"
        gold["identity"]["product_name"] = f"Product {key}"
        gold["identity"]["barcode_digits_seen"] = f"{990000000000 + index:012d}"
        gold["serving"]["size"] = "2 capsules"
        gold["serving"]["servings_per_container"] = "60"
        gold["serving"]["basis_text"] = "Amount Per Serving"
        gold["other_ingredients"]["text"] = "Vegetable cellulose"
        gold["rows"][0]["display_name"] = "Magnesium"
        gold["rows"][0]["amount"] = {"value": 200, "unit_text": "mg"}
        gold["checked_by"][0].update(checker="ab", checked_at="2026-09-09T00:00:00Z")
        gold["checked_by"][1].update(checker="cd", checked_at="2026-09-09T00:00:00Z")
        (root / "gold" / f"{key}.json").write_text(json.dumps(gold))
        entry["gold_sha256"] = hashlib.sha256(
            (root / "gold" / f"{key}.json").read_bytes()
        ).hexdigest()
        entries.append(entry)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "submission_holdout_v1",
                "frozen_at": "2026-09-09T00:00:00Z",
                "products": entries,
                "candidates": [
                    {
                        "id": "candidate-a",
                        "configuration": {
                            "provider": "fake",
                            "model": "fake-1",
                            "model_digest": "c" * 64,
                            "prompt_version": "p1",
                            "prompt_sha256": FakeAdapter.prompt_sha256,
                            "preparation": {"version": prep_version},
                        },
                    }
                ],
            }
        )
    )
    benchmark.freeze_holdout(root, synthetic=True)


def test_a_development_run_writes_output_the_benchmark_can_read(tmp_path: Path) -> None:
    root = tmp_path / "set"
    _build_set(root)
    run_dir = root / "runs" / "r1"

    summary = run_development_split(
        root, run_dir, LabelDraftExtractor(FakeAdapter()), _config()
    )

    assert summary["products"] == 2 and summary["drafted"] == 2
    for key in ("d-1", "d-2"):
        draft = json.loads((run_dir / f"{key}.json").read_text())
        assert draft["schema_version"] == "label_draft_v1"
        # Provenance survives to the scorable artefact.
        assert draft["sent_inputs"]
        meta = json.loads((run_dir / f"{key}.meta.json").read_text())
        assert meta["latency_seconds"] >= 0
    # Use the actual consumer, not a JSON-read proxy for it.
    report = benchmark.evaluate(root, run_dir, "development")
    assert report["configuration"] == "candidate-a"


def test_development_run_uses_the_same_opt_in_profile_as_worker(tmp_path):
    from dataclasses import replace
    from submission_review.extraction.photo_prep import LOCAL_PREPARATION_VERSION
    root = tmp_path / 'set'
    _build_set(root, prep_version=LOCAL_PREPARATION_VERSION)
    config = replace(_config(), prep_config_version=LOCAL_PREPARATION_VERSION)
    class InspectingAdapter(FakeAdapter):
        def extract(self, bundle, configuration):
            assert bundle.prep_config_version == LOCAL_PREPARATION_VERSION
            return super().extract(bundle, configuration)
    result = run_development_split(root, root / 'runs' / 'bounded',
                                   LabelDraftExtractor(InspectingAdapter()), config)
    assert result['drafted'] == 2


def test_run_cannot_overwrite_gold_or_an_existing_run(tmp_path):
    root = tmp_path / "set"
    _build_set(root)
    before = (root / "gold/d-1.json").read_bytes()
    with pytest.raises(DevelopmentRunError):
        run_development_split(root, root / "gold", LabelDraftExtractor(FakeAdapter()), _config())
    assert (root / "gold/d-1.json").read_bytes() == before
    run = root / "runs/one"
    run_development_split(root, run, LabelDraftExtractor(FakeAdapter()), _config())
    with pytest.raises(DevelopmentRunError):
        run_development_split(root, run, LabelDraftExtractor(FakeAdapter()), _config())


def test_the_held_out_split_cannot_be_run_from_a_tuning_loop(tmp_path: Path) -> None:
    root = tmp_path / "set"
    _build_set(root)

    with pytest.raises(DevelopmentRunError) as error:
        run_development_split(
            root,
            root / "runs" / "r1",
            LabelDraftExtractor(FakeAdapter()),
            _config(),
            split="holdout",
        )

    assert "single ledgered evaluation" in str(error.value)


def test_a_failing_adapter_writes_a_typed_failure_not_a_gap(tmp_path: Path) -> None:
    root = tmp_path / "set"
    _build_set(root)
    run_dir = root / "runs" / "r1"

    summary = run_development_split(
        root,
        run_dir,
        LabelDraftExtractor(FakeAdapter(fail_with="provider_unavailable")),
        _config(),
    )

    assert summary["failed"] == 2
    written = json.loads((run_dir / "d-1.json").read_text())
    # A missing file would read as "not attempted"; a typed failure is honest.
    assert written["schema_version"] == "extraction_failure_v1"
    assert written["code"] == "provider_unavailable"


def test_a_gold_template_is_blank_and_needs_two_independent_checkers() -> None:
    template = gold_template("d-1")

    assert template["identity"]["brand"] == ""
    assert template["rows"][0]["display_name"] == ""
    checkers = template["checked_by"]
    assert len(checkers) == 2
    for checker in checkers:
        assert checker["human"] is True
        assert checker["independent"] is True
        assert checker["model_output_seen"] is False


def test_a_template_never_carries_a_model_answer(tmp_path: Path) -> None:
    root = tmp_path / "set"
    _build_set(root)
    run_dir = root / "runs" / "r1"
    before = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((root / "gold").iterdir())
    }

    run_development_split(root, run_dir, LabelDraftExtractor(FakeAdapter()), _config())

    after = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((root / "gold").iterdir())
    }

    # A gold answer produced from a model is not gold, so a run must leave the
    # checked answers byte-for-byte alone.
    assert after == before


def test_intake_hashes_the_bytes_actually_on_disk(tmp_path: Path) -> None:
    root = tmp_path / "set"
    photo_dir = root / "photos" / "h-1"
    photo_dir.mkdir(parents=True)
    path = photo_dir / "0.jpg"
    path.write_bytes(_jpeg(3))

    entry = intake_manifest_entry("h-1", "brand-z/line", "holdout", [path], root)

    assert entry["split"] == "holdout"
    assert entry["photos"][0]["sha256"] == hashlib.sha256(_jpeg(3)).hexdigest()
    assert entry["photos"][0]["path"] == "photos/h-1/0.jpg"


def test_an_unknown_split_is_refused_at_intake(tmp_path: Path) -> None:
    with pytest.raises(DevelopmentRunError):
        intake_manifest_entry("h-1", "b/l", "training", [], tmp_path)
