"""TDD for workload-aware worker sizing in BatchProcessor.

Every spawned worker (macOS `spawn`) re-imports the module tree AND runs
init_worker, which loads ~29.5MB of reference JSON to build an
EnhancedDSLDNormalizer. For a small brand (e.g. 22 files) spawning the full
4-worker pool means ~4x that warmup — which dwarfs the actual work and shows
up as a per-brand pause at "Processing batch 1/1".

`_effective_workers(file_count)` sizes the pool to the batch: serial
(in-process, ONE reference load, no spawn) for small batches, scaling up to the
configured `max_workers` for large ones. This is a pure PERFORMANCE change with
zero accuracy impact — the serial and pool paths call the same
`process_single_file` and both re-order results to input-file order
(batch_processor.py ~890), so per-file output is byte-identical either way.
"""
import json
from collections import Counter
from concurrent.futures import Future
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

from unittest.mock import MagicMock

import pytest

from batch_processor import BatchProcessor, ProcessingResult


def _cfg(tmp_path, max_workers=4, min_files_per_worker=None):
    proc = {"batch_size": 500, "max_workers": max_workers}
    if min_files_per_worker is not None:
        proc["min_files_per_worker"] = min_files_per_worker
    return {
        "processing": proc,
        "paths": {
            "output_directory": str(tmp_path / "out"),
            "log_directory": str(tmp_path / "logs"),
        },
        "validation": {"verify_output": False, "check_input_integrity": False},
        "output_format": {},
        "ui": {"show_progress_bar": False},
    }


# --- _effective_workers: pure decision logic (default min_files_per_worker=50) ---

@pytest.mark.parametrize("count,expected", [
    (0, 1), (1, 1), (22, 1), (49, 1),   # small brands -> serial, no spawn
    (50, 1), (99, 1), (100, 2), (150, 3),  # scales with size
    (200, 4), (500, 4), (5000, 4),      # capped at configured max_workers
])
def test_effective_workers_default_gradient(tmp_path, count, expected):
    p = BatchProcessor(_cfg(tmp_path, max_workers=4))
    assert p._effective_workers(count) == expected


def test_never_exceeds_configured_max(tmp_path):
    p = BatchProcessor(_cfg(tmp_path, max_workers=2))
    assert p._effective_workers(100_000) == 2


def test_never_returns_below_one(tmp_path):
    p = BatchProcessor(_cfg(tmp_path, max_workers=4))
    assert p._effective_workers(0) == 1
    assert p._effective_workers(3) == 1


def test_zero_threshold_opts_out_of_throttling(tmp_path):
    # min_files_per_worker=0 restores the old always-max behavior.
    p = BatchProcessor(_cfg(tmp_path, max_workers=4, min_files_per_worker=0))
    assert p._effective_workers(3) == 4


def test_threshold_is_configurable(tmp_path):
    p = BatchProcessor(_cfg(tmp_path, max_workers=4, min_files_per_worker=10))
    assert p._effective_workers(9) == 1
    assert p._effective_workers(25) == 2
    assert p._effective_workers(40) == 4


def test_configured_single_worker_stays_serial(tmp_path):
    p = BatchProcessor(_cfg(tmp_path, max_workers=1))
    assert p._effective_workers(100_000) == 1


# --- routing: a small batch must NOT instantiate the process pool ---

def test_small_batch_takes_serial_path_no_pool(tmp_path, monkeypatch):
    import batch_processor as bp

    p = BatchProcessor(_cfg(tmp_path, max_workers=4))  # default threshold 50
    files = []
    for i in range(5):
        f = tmp_path / f"{i:03d}.json"
        f.write_text(json.dumps({"id": f"P{i}", "ingredientRows": []}), encoding="utf-8")
        files.append(f)

    # If the pool is ever constructed for a 5-file batch, fail loudly.
    pool = MagicMock(side_effect=AssertionError("ProcessPoolExecutor used for a 5-file batch"))
    monkeypatch.setattr(bp, "ProcessPoolExecutor", pool)
    monkeypatch.setattr(bp, "init_worker", lambda *a, **k: None)
    monkeypatch.setattr(
        bp, "process_single_file",
        lambda fp, out=None: ProcessingResult(
            success=True, status="success",
            data={"id": fp, "dsld_id": fp, "product_name": "T"},
            file_path=fp, processing_time=0.0, unmapped_ingredients=[],
        ),
    )
    monkeypatch.setattr(p, "validate_input_file", lambda f: (True, None))

    p.process_batch(0, files)
    pool.assert_not_called()


def _multi_batch_probe(tmp_path, monkeypatch, *, max_workers, count):
    import batch_processor as bp

    config = _cfg(tmp_path, max_workers=max_workers, min_files_per_worker=1)
    config["processing"]["batch_size"] = 2
    processor = BatchProcessor(config)
    source = tmp_path / "raw"
    source.mkdir()
    files = []
    for i in range(count):
        path = source / f"{i}.json"
        path.write_text(json.dumps({"id": str(i)}))
        files.append(path)
    events = []
    monkeypatch.setattr(bp, "init_worker", lambda output: events.append(("init", output)))
    monkeypatch.setattr(processor, "validate_input_file", lambda _: (True, None))
    monkeypatch.setattr(processor, "_save_unmapped_ingredients", lambda **kwargs: None)
    monkeypatch.setattr(processor, "_write_stage_manifest", lambda _: None)

    def process(filename, *args):
        return ProcessingResult(success=True, status="success", file_path=filename,
                                raw_id=Path(filename).stem,
                                data={"id": Path(filename).stem, "activeIngredients": [],
                                      "inactiveIngredients": []}, unmapped_ingredients=[])

    monkeypatch.setattr(bp, "process_single_file_with_timeout", process)

    class CompletedPool:
        def __init__(self, max_workers, initializer, initargs):
            events.append(("pool", max_workers))
            self.initializer, self.initargs = initializer, initargs
        def __enter__(self):
            self.initializer(*self.initargs)
            return self
        def __exit__(self, *args):
            events.append(("close", None))
        def submit(self, function, *args):
            future = Future()
            future.set_result(function(*args))
            return future

    monkeypatch.setattr(bp, "ProcessPoolExecutor", CompletedPool)
    return processor, files, events


def test_serial_worker_is_initialized_once_for_multiple_batches(tmp_path, monkeypatch):
    processor, files, events = _multi_batch_probe(tmp_path, monkeypatch, max_workers=1, count=5)

    summary = processor.process_all_files(files)

    assert summary["results"]["cleaned"] == 5
    assert [event for event, _ in events] == ["init"]


def test_pool_is_reused_then_closed_before_smaller_serial_tail(tmp_path, monkeypatch):
    processor, files, events = _multi_batch_probe(tmp_path, monkeypatch, max_workers=2, count=5)

    summary = processor.process_all_files(files)

    assert summary["results"]["cleaned"] == 5
    assert [event for event, _ in events] == ["pool", "init", "close", "init"]
    assert [count for event, count in events if event == "pool"] == [2]


def test_worker_resources_close_when_a_later_batch_aborts(tmp_path, monkeypatch):
    processor, files, events = _multi_batch_probe(tmp_path, monkeypatch, max_workers=2, count=4)
    original = processor.process_batch

    def abort(batch_num, *args, **kwargs):
        if batch_num == 1:
            raise RuntimeError("abort after first batch")
        return original(batch_num, *args, **kwargs)

    monkeypatch.setattr(processor, "process_batch", abort)
    with pytest.raises(RuntimeError, match="abort after first batch"):
        processor.process_all_files(files)

    assert [event for event, _ in events] == ["pool", "init", "close"]
    assert getattr(processor, "_worker_resources", None) is None


def test_broken_worker_pool_is_replaced_for_the_next_batch(tmp_path, monkeypatch):
    import batch_processor as bp
    from concurrent.futures.process import BrokenProcessPool

    processor, files, events = _multi_batch_probe(tmp_path, monkeypatch, max_workers=2, count=4)
    completed_pool = bp.ProcessPoolExecutor

    class BreakOnce(completed_pool):
        def submit(self, function, filename, *args):
            if filename == str(files[0]):
                future = Future()
                future.set_exception(BrokenProcessPool("worker terminated"))
                return future
            return super().submit(function, filename, *args)

    monkeypatch.setattr(bp, "ProcessPoolExecutor", BreakOnce)

    summary = processor.process_all_files(files)

    assert summary["results"]["errors"] == 1
    assert summary["results"]["cleaned"] == 3
    assert [event for event, _ in events] == ["pool", "init", "close", "pool", "init", "close"]


def test_pool_death_during_submission_aborts_without_a_success_manifest(tmp_path, monkeypatch):
    import batch_processor as bp
    from concurrent.futures.process import BrokenProcessPool

    processor, files, events = _multi_batch_probe(tmp_path, monkeypatch, max_workers=2, count=4)
    completed_pool = bp.ProcessPoolExecutor
    manifests = []
    monkeypatch.setattr(processor, "_write_stage_manifest", lambda _: manifests.append(True))

    class DiesBetweenBatches(completed_pool):
        def submit(self, function, filename, *args):
            if filename == str(files[2]):
                raise BrokenProcessPool("worker died before next submission")
            return super().submit(function, filename, *args)

    monkeypatch.setattr(bp, "ProcessPoolExecutor", DiesBetweenBatches)
    with pytest.raises(BrokenProcessPool, match="worker died before next submission"):
        processor.process_all_files(files)

    assert not manifests
    assert getattr(processor, "_worker_resources", None) is None
    assert [event for event, _ in events] == ["pool", "init", "close"]


def test_serial_worker_references_are_released_between_invocations(tmp_path, monkeypatch):
    import batch_processor as bp

    identities = []
    for name in ("first", "second"):
        processor, files, _ = _multi_batch_probe(tmp_path / name, monkeypatch, max_workers=1, count=4)

        def initialize(_):
            bp._worker_normalizer = object()
            bp._worker_validator = object()
            identities.append(bp._worker_normalizer)

        monkeypatch.setattr(bp, "init_worker", initialize)
        processor.process_all_files(files)
        assert bp._worker_normalizer is None
        assert bp._worker_validator is None

    assert len(identities) == 2
    assert identities[0] is not identities[1]


def test_worker_diagnostics_do_not_accumulate_across_products_or_failed_labels(tmp_path, monkeypatch):
    import batch_processor as bp
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer.__new__(EnhancedDSLDNormalizer)
    normalizer.unmapped_ingredients = Counter()
    normalizer.unmapped_details = {}
    before = []

    def normalize(raw):
        before.append((dict(normalizer.unmapped_ingredients), dict(normalizer.unmapped_details)))
        normalizer.unmapped_ingredients["Same Unknown"] += 1
        normalizer.unmapped_details["Same Unknown"] = {"is_active": raw["id"] != "failed"}
        if raw["id"] == "failed":
            raise ValueError("failed after recording a diagnostic")
        return {"id": raw["id"], "metadata": {}, "activeIngredients": [], "inactiveIngredients": []}

    normalizer.normalize_product = normalize
    monkeypatch.setattr(bp, "_worker_normalizer", normalizer)
    monkeypatch.setattr(bp, "_worker_validator", SimpleNamespace(
        validate_cleaned_product=lambda _: [],
        validate_product=lambda _: ("success", [], {}),
    ))
    results = []
    for label in ("first", "failed", "last"):
        path = tmp_path / f"{label}.json"
        path.write_text(json.dumps({"id": label}))
        results.append(bp.process_single_file(str(path)))

    assert before == [({}, {}), ({}, {}), ({}, {})]
    assert [result.success for result in results] == [True, False, True]
    assert results[0].unmapped_ingredients == results[2].unmapped_ingredients == ["Same Unknown"]
    assert results[0].unmapped_details == results[2].unmapped_details == {
        "Same Unknown": {"is_active": True},
    }


@pytest.mark.parametrize("workers", [1, 2], ids=["serial", "pool"])
def test_real_multibatch_reuse_preserves_products_and_reports(tmp_path, workers):
    """Exercise actual worker processes and frozen labels, not a mock pool."""
    fixture_root = Path(__file__).parent / "fixtures"
    files = [fixture_root / f"evidence_subject_{label_id}_raw.json"
             for label_id in (19505, 251338, 54775, 176055, 321604, 278019)]

    def capture(destination, reuse):
        config = _cfg(destination, max_workers=workers, min_files_per_worker=1)
        processor = BatchProcessor(config)
        results = []
        with processor._worker_session() if reuse else nullcontext():
            for batch_num in range(3):
                results.append(processor.process_batch(batch_num, files[batch_num * 2:batch_num * 2 + 2]))
        assert all(not result["errors"] and result["write_success"] for result in results)
        processor._save_unmapped_ingredients(processed_count_override=6)
        assert not processor.report_write_failures
        products = {}
        for disposition in ("cleaned", "needs_review", "incomplete"):
            for path in (processor.output_dir / disposition).glob("*.json"):
                rows = json.loads(path.read_text())
                for row in rows:
                    row["metadata"].pop("lastCleaned", None)
                products[f"{disposition}/{path.name}"] = rows
        reports = {}
        for path in (processor.output_dir / "unmapped").glob("*.json"):
            report = json.loads(path.read_text())
            report.get("metadata", {}).pop("generated_at", None)
            reports[path.name] = report
        assert sum(len(rows) for rows in products.values()) == 6
        return products, reports

    assert capture(tmp_path / "fresh_each_batch", False) == capture(tmp_path / "reused", True)


def test_broken_worker_reference_recheck_releases_budget_and_resets_state(tmp_path, monkeypatch):
    import batch_processor as bp

    processor = BatchProcessor(_cfg(tmp_path))
    events = []

    def verify_references():
        events.append("validate")
        assert events == ["workers_closed", "validate"]
        raise RuntimeError("unusable unit conversions")

    monkeypatch.setattr(bp, "EnhancedDSLDNormalizer", verify_references)
    with pytest.raises(RuntimeError, match="unit conversions"):
        with processor._worker_session():
            processor._worker_resources.callback(events.append, "workers_closed")
            processor._worker_reference_check_required = True
    assert processor._worker_resources is None
    assert processor._worker_reference_check_required is False
    # A subsequent healthy invocation must not repeat the failed-session check.
    with processor._worker_session():
        pass
    assert events == ["workers_closed", "validate"]
