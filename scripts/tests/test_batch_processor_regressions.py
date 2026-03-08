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

    def fake_process_batch(batch_num, batch_files):
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
    monkeypatch.setattr(processor, "_save_unmapped_ingredients", lambda: None)
    monkeypatch.setattr(processor, "_generate_processing_report", lambda summary, batch_results: None)
    monkeypatch.setattr(processor, "_generate_detailed_review_report", lambda: None)

    processor.process_all_files(files, resume=True)

    assert observed
    assert observed[0][0] == "020.json"
