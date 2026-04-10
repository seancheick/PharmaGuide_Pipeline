import json
from pathlib import Path
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from batch_processor import BatchProcessor, BatchState


def _make_config(tmp_path):
    return {
        "processing": {
            "batch_size": 10,
            "max_workers": 1,
        },
        "paths": {
            "output_directory": str(tmp_path / "out"),
            "log_directory": str(tmp_path / "logs"),
        },
        "validation": {
            "verify_output": False,
            "check_input_integrity": False,
        },
        "output_format": {},
        "ui": {"show_progress_bar": False},
    }


def test_resume_does_not_skip_remaining_files(tmp_path, monkeypatch):
    cfg = _make_config(tmp_path)
    processor = BatchProcessor(cfg)

    files = []
    for i in range(100):
        path = tmp_path / f"{i:03d}.json"
        path.write_text(json.dumps({"id": i, "ingredientRows": [{"name": "Vitamin C"}]}), encoding="utf-8")
        files.append(path)

    processed = [str(p) for p in files[:20]]
    state = BatchState(
        started="2026-03-08T00:00:00Z",
        last_updated="2026-03-08T00:10:00Z",
        last_completed_batch=1,
        total_batches=10,
        processed_files=20,
        total_files=100,
        errors=[],
        can_resume=True,
        config_checksum=processor._get_config_checksum(),
        file_manifest_checksum=processor._get_file_manifest_checksum(files),
        processed_file_paths=processed,
    )
    processor.save_state(state)

    observed = []

    def fake_process_batch(batch_num, batch_files, output_batch_num=None):
        observed.append([p.name for p in batch_files])
        return {
            "summary": {
                "processed": len(batch_files),
                "cleaned": len(batch_files),
                "needs_review": 0,
                "incomplete": 0,
                "errors": 0,
            },
            "errors": [],
            "unmapped_count": 0,
            "processed_files": [str(p) for p in batch_files],
        }

    monkeypatch.setattr(processor, "process_batch", fake_process_batch)
    monkeypatch.setattr(processor, "_generate_final_summary", lambda batch_results, total_time: {"ok": True})
    monkeypatch.setattr(processor, "_save_unmapped_ingredients", lambda *a, **kw: None)
    monkeypatch.setattr(processor, "_generate_processing_report", lambda summary, batch_results: None)
    monkeypatch.setattr(processor, "_generate_detailed_review_report", lambda: None)

    processor.process_all_files(files, resume=True)

    assert observed
    assert observed[0][0] == "020.json"


def test_unmapped_tracker_save_receives_real_processed_file_count(tmp_path, monkeypatch):
    cfg = _make_config(tmp_path)
    processor = BatchProcessor(cfg)

    files = []
    for i in range(5):
        path = tmp_path / f"{i:03d}.json"
        path.write_text(json.dumps({"id": i, "ingredientRows": [{"name": "Vitamin C"}]}), encoding="utf-8")
        files.append(path)

    seen = {}

    def fake_process_batch(batch_num, batch_files, output_batch_num=None):
        return {
            "summary": {
                "processed": len(batch_files),
                "cleaned": len(batch_files),
                "needs_review": 0,
                "incomplete": 0,
                "errors": 0,
            },
            "errors": [],
            "unmapped_count": 0,
            "processed_files": [str(p) for p in batch_files],
            "write_success": True,
        }

    def fake_save_unmapped_ingredients(processed_count_override=None):
        seen["processed_count_override"] = processed_count_override

    monkeypatch.setattr(processor, "process_batch", fake_process_batch)
    monkeypatch.setattr(processor, "_generate_final_summary", lambda batch_results, total_time: {"ok": True})
    monkeypatch.setattr(processor, "_save_unmapped_ingredients", fake_save_unmapped_ingredients)
    monkeypatch.setattr(processor, "_generate_processing_report", lambda summary, batch_results: None)
    monkeypatch.setattr(processor, "_generate_detailed_review_report", lambda: None)

    processor.process_all_files(files, resume=False)

    assert seen["processed_count_override"] == 5


def test_manifest_checksum_changes_when_same_size_and_mtime_content_changes(tmp_path):
    cfg = _make_config(tmp_path)
    processor = BatchProcessor(cfg)

    path = tmp_path / "same.json"
    original = {"id": 1, "ingredientRows": [{"name": "AAAA"}]}
    updated = {"id": 1, "ingredientRows": [{"name": "BBBB"}]}

    path.write_text(json.dumps(original, separators=(",", ":")), encoding="utf-8")
    fixed_mtime = 1_700_000_000
    os.utime(path, (fixed_mtime, fixed_mtime))
    before = processor._get_file_manifest_checksum([path])

    replacement = json.dumps(updated, separators=(",", ":"))
    assert len(replacement) == len(path.read_text(encoding="utf-8"))
    path.write_text(replacement, encoding="utf-8")
    os.utime(path, (fixed_mtime, fixed_mtime))
    after = processor._get_file_manifest_checksum([path])

    assert before != after


def test_reference_data_memory_estimate_sums_json_payloads(tmp_path):
    cfg = _make_config(tmp_path)
    cfg["processing"]["max_workers"] = 3
    processor = BatchProcessor(cfg)

    data_dir = tmp_path / "refdata"
    data_dir.mkdir()
    (data_dir / "a.json").write_text("{}", encoding="utf-8")
    (data_dir / "b.json").write_text('{"k":"value"}', encoding="utf-8")

    diagnostics = processor._estimate_reference_data_memory(data_dir=data_dir)

    assert diagnostics["reference_json_count"] == 2
    assert diagnostics["reference_payload_bytes"] == (
        (data_dir / "a.json").stat().st_size + (data_dir / "b.json").stat().st_size
    )
    assert diagnostics["estimated_total_worker_payload_bytes"] == (
        diagnostics["reference_payload_bytes"] * 3
    )


# ---------------------------------------------------------------------------
# Phase 0 failing test — HIGH #3: dedup key fragility on empty-string id.
# ---------------------------------------------------------------------------


from collections import Counter
from batch_processor import ProcessingResult


def _make_processing_result(product_id, file_name="test.json"):
    """Helper: build a minimal successful ProcessingResult carrying a cleaned product."""
    return ProcessingResult(
        success=True,
        status="success",
        data={"id": product_id, "dsld_id": product_id, "product_name": "Test"},
        file_path=file_name,
        processing_time=0.01,
        unmapped_ingredients=[],
    )


def test_dedup_rejects_or_tracks_empty_string_id(tmp_path, monkeypatch):
    """HIGH #3: if a cleaned record carries id=''/None/missing, the dedup
    chain at batch_processor.py:1017-1027 computes an empty dsld_id and
    skips registration. A second record with the same empty id bypasses
    the duplicate check and both are added to 'cleaned[]' silently. For a
    medical-grade pipeline, empty/None IDs must either be rejected OR
    stably tracked — never silently allowed through."""
    cfg = _make_config(tmp_path)
    processor = BatchProcessor(cfg)
    # Ensure verify_output does not reject these synthetic records.
    monkeypatch.setattr(processor, "verify_output", lambda data, raw=None: (True, {}))

    cleaned, needs_review, incomplete, errors = [], [], [], []
    batch_unmapped = Counter()

    first = _make_processing_result("", file_name="first.json")
    second = _make_processing_result("", file_name="second.json")

    processor._categorize_result(first, cleaned, needs_review, incomplete, errors, batch_unmapped)
    processor._categorize_result(second, cleaned, needs_review, incomplete, errors, batch_unmapped)

    # Correct behavior: either reject empty-id records to errors/quarantine,
    # or register them under a stable key so the second one is detected as
    # a duplicate. In either case, 'cleaned' must NOT contain both.
    assert len(cleaned) <= 1, (
        f"Two cleaned records with empty id='' both landed in cleaned[]. "
        f"Root cause: batch_processor dedup uses "
        f"str(result.data.get('id', result.data.get('dsld_id', ''))); "
        f"an empty-string fallback evaluates falsy and skips both "
        f"registration and lookup. cleaned len={len(cleaned)}, "
        f"errors len={len(errors)}."
    )


def test_dedup_rejects_or_tracks_none_id(tmp_path, monkeypatch):
    """Same defense for id=None (missing key path)."""
    cfg = _make_config(tmp_path)
    processor = BatchProcessor(cfg)
    monkeypatch.setattr(processor, "verify_output", lambda data, raw=None: (True, {}))

    cleaned, needs_review, incomplete, errors = [], [], [], []
    batch_unmapped = Counter()

    # Build results with id=None explicitly (also no dsld_id present)
    first = ProcessingResult(
        success=True, status="success",
        data={"id": None, "product_name": "No-id product A"},
        file_path="a.json", processing_time=0.01,
    )
    second = ProcessingResult(
        success=True, status="success",
        data={"id": None, "product_name": "No-id product B"},
        file_path="b.json", processing_time=0.01,
    )

    processor._categorize_result(first, cleaned, needs_review, incomplete, errors, batch_unmapped)
    processor._categorize_result(second, cleaned, needs_review, incomplete, errors, batch_unmapped)

    assert len(cleaned) <= 1, (
        "Two records with id=None both landed in cleaned[]. Dedup "
        "must reject or canonicalize missing IDs."
    )


def test_dedup_still_blocks_real_duplicate_ids(tmp_path, monkeypatch):
    """Regression lock: the fix must not break the existing real-id dedup."""
    cfg = _make_config(tmp_path)
    processor = BatchProcessor(cfg)
    monkeypatch.setattr(processor, "verify_output", lambda data, raw=None: (True, {}))

    cleaned, needs_review, incomplete, errors = [], [], [], []
    batch_unmapped = Counter()

    first = _make_processing_result("12345", file_name="first.json")
    dupe = _make_processing_result("12345", file_name="dupe.json")

    processor._categorize_result(first, cleaned, needs_review, incomplete, errors, batch_unmapped)
    processor._categorize_result(dupe, cleaned, needs_review, incomplete, errors, batch_unmapped)

    assert len(cleaned) == 1, f"Expected one kept, got {len(cleaned)}"
