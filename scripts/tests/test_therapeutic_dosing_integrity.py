"""Integrity + contract regression suite for the dosing reference DBs.

Covers `rda_therapeutic_dosing.json` (botanical + collagen scoring source) and the
citation-verifier wiring shared with `rda_optimal_uls.json`. Grows per batch of the
dosing-overhaul plan (boundary cleanup, migration, verified expansion).

These assertions are deliberately structural/contractual — clinical dose-range
*values* are validated against primary sources during the per-entry research pass,
and the dose *bands* are asserted by the v4 scorer suites
(test_v4_botanical_profile / test_v4_collagen_profile / test_collagen_taxonomy).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
THERAPEUTIC = DATA_DIR / "rda_therapeutic_dosing.json"
OPTIMAL_ULS = DATA_DIR / "rda_optimal_uls.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


@pytest.fixture(scope="module")
def therapeutic() -> dict:
    return _load(THERAPEUTIC)


@pytest.fixture(scope="module")
def optimal_uls() -> dict:
    return _load(OPTIMAL_ULS)


# ── metadata count truth ────────────────────────────────────────────────

def test_therapeutic_metadata_count_matches(therapeutic):
    entries = therapeutic["therapeutic_dosing"]
    assert therapeutic["_metadata"]["total_entries"] == len(entries)


def test_optimal_uls_metadata_count_matches(optimal_uls):
    entries = optimal_uls["nutrient_recommendations"]
    assert optimal_uls["_metadata"]["total_entries"] == len(entries)


# ── references[] shape: bare PMID digit-strings only ────────────────────

@pytest.mark.parametrize("filename", ["rda_therapeutic_dosing.json", "rda_optimal_uls.json"])
def test_references_are_bare_pmid_strings(filename):
    data = _load(DATA_DIR / filename)
    key = "therapeutic_dosing" if "therapeutic" in filename else "nutrient_recommendations"
    for e in data[key]:
        refs = e.get("references")
        if refs is None:
            continue
        assert isinstance(refs, list), f"{e.get('standard_name')}: references must be a list"
        for r in refs:
            assert isinstance(r, str) and r.isdigit(), (
                f"{e.get('standard_name')}: reference {r!r} must be a bare PMID digit-string"
            )


def test_no_source_pmids_convention_drift(therapeutic, optimal_uls):
    """Single citation convention: references[]. No parallel source_pmids field."""
    for data, key in ((therapeutic, "therapeutic_dosing"), (optimal_uls, "nutrient_recommendations")):
        for e in data[key]:
            assert "source_pmids" not in e, f"{e.get('standard_name')}: use references[], not source_pmids"


# ── collagen scorer-contract guard (committed v4 Phase 7, commit eec0e3ba) ──

# collagen_profile keys dose routing on these exact normalized aliases — renaming
# them silently breaks collagen dose scoring. Locked here.
COLLAGEN_REQUIRED_ALIASES = {"uc-ii", "nem", "biocell", "gelatin", "collagen"}


def test_collagen_routing_aliases_present(therapeutic):
    all_aliases = set()
    for e in therapeutic["therapeutic_dosing"]:
        all_aliases.update(a.lower() for a in (e.get("aliases") or []))
        all_aliases.add((e.get("standard_name") or "").lower())
    missing = {a for a in COLLAGEN_REQUIRED_ALIASES if a not in all_aliases}
    assert not missing, f"collagen routing aliases missing (breaks collagen_profile): {missing}"


def test_collagen_entries_carry_verified_references(therapeutic):
    """The 5 collagen entries shipped with content-verified PMIDs — keep them."""
    collagen_ids = {
        "collagen_peptides", "uc_ii_collagen", "biocell_collagen",
        "gelatin", "eggshell_membrane_nem",
    }
    by_id = {e.get("id"): e for e in therapeutic["therapeutic_dosing"]}
    for cid in collagen_ids:
        assert cid in by_id, f"collagen entry {cid} missing"
        assert by_id[cid].get("references"), f"collagen entry {cid} must keep its verified references[]"


# ── citation verifier wiring ────────────────────────────────────────────

def test_citation_verifier_configs_present():
    """Both dosing files must have a content-verifier FILE_CONFIG so their PMIDs
    are gated by verify_all_citations_content.py (pmid_list source format)."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api_audit"))
    import verify_all_citations_content as vac

    by_file = {c["file"]: c for c in vac.FILE_CONFIGS}
    for fname in ("rda_therapeutic_dosing.json", "rda_optimal_uls.json"):
        assert fname in by_file, f"no verifier FILE_CONFIG for {fname}"
        assert by_file[fname]["source_format"] == "pmid_list"
        assert by_file[fname]["sources_field"] == "references"
