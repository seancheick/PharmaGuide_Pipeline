"""Phase 0 config-driven calibration — shared config registry contract.

Locks the loader/fingerprint/provenance seam that every v4 scoring module will
read knobs from. No scoring behavior here — just the infrastructure contract.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "scoring_v4"))


def test_load_rubric_returns_omega_config():
    from scoring_v4.config_registry import load_rubric

    rubric = load_rubric("omega")
    assert isinstance(rubric, dict)
    # real dict (not a MappingProxy) so module `isinstance(x, dict)` guards work
    assert isinstance(rubric["dose"], dict)
    assert "dimension_caps" in rubric
    assert "epa_dha_bands" in rubric["dose"]


def test_load_rubric_returns_fresh_copy_each_call():
    """Callers get an independent dict — mutating one must not affect the next
    (matches the old `json.loads(read_text())` per-call semantics)."""
    from scoring_v4.config_registry import load_rubric

    a = load_rubric("omega")
    a["dose"]["epa_dha_bands"] = []  # mutate the copy
    b = load_rubric("omega")
    assert b["dose"]["epa_dha_bands"] != []  # next caller is unaffected


def test_unknown_rubric_raises():
    from scoring_v4.config_registry import load_rubric

    try:
        load_rubric("does_not_exist")
        assert False, "expected KeyError for unknown rubric"
    except KeyError:
        pass


def test_config_fingerprint_is_stable_hex():
    from scoring_v4.config_registry import config_fingerprint

    fp = config_fingerprint("omega")
    assert isinstance(fp, str) and len(fp) == 16
    int(fp, 16)  # valid hex
    assert config_fingerprint("omega") == fp  # stable across calls


def test_config_version_reads_metadata_schema_version():
    from scoring_v4.config_registry import config_version

    v = config_version("omega")
    assert isinstance(v, str) and v != "" and v != "unknown"


def test_all_config_provenance_shape():
    from scoring_v4.config_registry import all_config_provenance

    prov = all_config_provenance()
    assert "omega" in prov
    assert set(prov["omega"].keys()) == {"schema_version", "fingerprint"}
    assert len(prov["omega"]["fingerprint"]) == 16
