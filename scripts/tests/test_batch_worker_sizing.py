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
