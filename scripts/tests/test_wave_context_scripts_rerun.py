"""The documented Wave 2 curation command stays safe to rerun after later dispositions.

``wave2_contexts.py`` is a one-shot migration whose rerun verifies the
materialized rows instead of appending duplicates. Source-bound dispositions
(``apply_batch1_disposition.py``) later patch individual fields of some Wave 2
rows; the rerun must accept exactly those declared patches and nothing else.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/audits/probiotic_curation_queue_2026_09_13/wave2_contexts.py"
REGISTRY = ROOT / "scripts/data/clinically_relevant_strains.json"


def test_wave2_contexts_rerun_verifies_patched_rows_without_writing():
    before = REGISTRY.read_bytes()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "Wave 2 already applied; verified 59 contexts; no changes written" in result.stdout
    assert REGISTRY.read_bytes() == before
