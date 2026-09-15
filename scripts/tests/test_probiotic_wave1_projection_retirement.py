"""The old count-only what-if must not pretend to project current scores."""
import glob
import runpy
import sys
from pathlib import Path

import studied_formulas


def test_wave1_retires_numeric_formulation_projection_and_preserves_saved_reports(monkeypatch):
    script = Path(__file__).resolve().parents[1] / "audits/probiotic_curation_queue_2026_09_13/wave1_projection.py"
    monkeypatch.setattr(glob, "glob", lambda pattern: [])
    monkeypatch.setattr(sys, "argv", [str(script)])
    writes = []
    monkeypatch.setattr(Path, "write_text", lambda path, text, **kwargs: writes.append(path))
    registry_loader = studied_formulas._clinical_strain_registry
    result = runpy.run_path(str(script), run_name="__main__")
    notice = result["report"]["B_formulation_stubs"]
    assert notice["status"] == "superseded"
    assert "source-owned" in notice["note"]
    assert "replay.py" in notice["replacement"]
    assert all(isinstance(value, str) for value in notice.values())
    assert "A_evidence" in result["report"]
    assert result["report"]["A_evidence"]["status"] == "historical_approval_hypothesis"
    assert "products_changed_today" not in result["report"]["A_evidence"]
    assert result["report"]["_metadata"]["built"] != "2026-09-13"
    assert writes == []
    assert studied_formulas._clinical_strain_registry is registry_loader
