"""Fix Sprint 03 — regression locks (Step 1: diuretics → potassium/magnesium).

The safety goal: potassium/magnesium depletion advice must never fire for
potassium-sparing diuretics (spironolactone, eplerenone, amiloride, triamterene,
canrenone, finerenone). That hazard is removed by pointing the two reviewed
diuretic records at a new loop+thiazide class that EXCLUDES every K-sparing agent.

Test-first: every assertion below fails on pre-Sprint-3 data.

Later steps (PPI, enzyme-inducing AEDs) extend this file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parent.parent / "data"
COMBINED = "class:loop_and_thiazide_diuretics"

# RxNorm-verified potassium-sparing / non-loop-thiazide agents that must NEVER
# appear in the combined class (rxcui → name, for readable failures).
FORBIDDEN_IN_COMBINED = {
    "644": "amiloride",
    "1982": "canrenone",
    "298869": "eplerenone",
    "2562811": "finerenone",
    "9997": "spironolactone",
    "10763": "triamterene",
    "302285": "conivaptan",   # aquaretic vaptan
    "358257": "tolvaptan",    # aquaretic vaptan
    "10437": "theobromine",   # methylxanthine, not a clinical diuretic drug
    "6774": "mersalyl",       # obsolete organomercurial
}

# Loop + thiazide agents that must be present (rxcui → name), RxNorm-verified.
REQUIRED_IN_COMBINED = {
    "4603": "furosemide",
    "1808": "bumetanide",
    "38413": "torsemide",
    "5487": "hydrochlorothiazide",
    "2409": "chlorthalidone",
}


@pytest.fixture(scope="module")
def classes() -> dict:
    return json.loads((DATA / "drug_classes.json").read_text())["classes"]


@pytest.fixture(scope="module")
def depletions() -> dict:
    entries = json.loads((DATA / "medication_depletions.json").read_text())["depletions"]
    return {e["id"]: e for e in entries}


# --------------------------------------------------------------------------- #
# The new combined class
# --------------------------------------------------------------------------- #


def test_combined_class_exists(classes):
    assert COMBINED in classes, f"{COMBINED} not defined in drug_classes.json"


def test_combined_class_has_loop_and_thiazide_members(classes):
    c = classes[COMBINED]
    rx = set(c["member_rxcuis"])
    names = set(c["member_names"])
    for rxcui, name in REQUIRED_IN_COMBINED.items():
        assert rxcui in rx, f"{COMBINED} missing {name} ({rxcui})"
        assert name in names, f"{COMBINED} missing name {name}"


def test_combined_class_excludes_all_potassium_sparing(classes):
    c = classes[COMBINED]
    rx = set(c["member_rxcuis"])
    names = set(c["member_names"])
    hits_rx = {r: n for r, n in FORBIDDEN_IN_COMBINED.items() if r in rx}
    hits_name = {n for n in FORBIDDEN_IN_COMBINED.values() if n in names}
    assert not hits_rx, f"{COMBINED} must EXCLUDE these rxcuis (hyperkalemia hazard): {hits_rx}"
    assert not hits_name, f"{COMBINED} must EXCLUDE these names: {hits_name}"


def test_combined_class_arrays_aligned_and_sorted(classes):
    c = classes[COMBINED]
    pairs = list(zip(c["member_names"], c["member_rxcuis"]))
    assert len(c["member_rxcuis"]) == len(c["member_names"]), "rxcui/name length mismatch"
    assert pairs == sorted(pairs), "members must be sorted by (name, rxcui) for byte-identical builds"
    # anchor one pair explicitly so a future shuffle is caught
    assert ("furosemide", "4603") in pairs


# --------------------------------------------------------------------------- #
# The two repointed records
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("entry_id", ["DEP_DIURETICS_POTASSIUM", "DEP_DIURETICS_MAGNESIUM"])
def test_reviewed_diuretic_records_repointed(depletions, entry_id):
    assert depletions[entry_id]["drug_ref"]["id"] == COMBINED, (
        f"{entry_id} must point at {COMBINED}, not the coarse class:diuretics"
    )


@pytest.mark.parametrize(
    "entry_id",
    ["DEP_DIURETICS_ZINC", "DEP_DIURETICS_CALCIUM", "DEP_DIURETICS_THIAMINE", "DEP_DIURETICS_FOLATE"],
)
def test_deferred_diuretic_records_untouched(depletions, entry_id):
    # These are drug/subclass-specific (folate=triamterene, calcium=loop,
    # thiamine=furosemide, zinc=TBD) and are handled in later entry-specific
    # audits — they must stay on class:diuretics this sprint.
    assert depletions[entry_id]["drug_ref"]["id"] == "class:diuretics", (
        f"{entry_id} must NOT be repointed in Step 1 (see fix_sprint_03/research.md)"
    )


def test_potassium_recommendation_copy_fixed(depletions):
    rec = depletions["DEP_DIURETICS_POTASSIUM"]["recommendation"].lower()
    assert "potassium-rich foods" in rec, "recommendation must say 'potassium-rich foods'"
    assert "potassium-sparing foods" not in rec, (
        "'potassium-sparing foods' is factually wrong (that names a drug class, not foods)"
    )


# --------------------------------------------------------------------------- #
# Step 2 — antacids → PPI (B12, magnesium)
#
# class:antacids is direct neutralising products (Ca/Al/Mg salts). PPI-associated
# B12 malabsorption and hypomagnesemia belong on class:proton_pump_inhibitors.
# Only the two PPI-mechanism records move; the acid-reduction records
# (calcium/iron/vitamin C/zinc) stay for a later entry-specific audit.
# --------------------------------------------------------------------------- #

PPI = "class:proton_pump_inhibitors"


@pytest.mark.parametrize("entry_id", ["DEP_ANTACIDS_VITAMINB12", "DEP_ANTACIDS_MAGNESIUM"])
def test_ppi_records_repointed(depletions, entry_id):
    assert depletions[entry_id]["drug_ref"]["id"] == PPI, (
        f"{entry_id} is a PPI-mechanism effect and must point at {PPI}"
    )


@pytest.mark.parametrize("entry_id", ["DEP_ANTACIDS_VITAMINB12", "DEP_ANTACIDS_MAGNESIUM"])
def test_ppi_record_display_name_not_stale(depletions, entry_id):
    # Was "PPIs and antacids ..." — stale once the ref is PPI-only.
    disp = depletions[entry_id]["drug_ref"]["display_name"].lower()
    assert "antacid" not in disp, f"{entry_id} display_name still names antacids after PPI repoint"


@pytest.mark.parametrize(
    "entry_id",
    ["DEP_ANTACIDS_CALCIUM", "DEP_ANTACIDS_IRON", "DEP_ANTACIDS_VITAMINC", "DEP_ANTACIDS_ZINC"],
)
def test_deferred_antacid_records_untouched(depletions, entry_id):
    assert depletions[entry_id]["drug_ref"]["id"] == "class:antacids", (
        f"{entry_id} must NOT be repointed in Sprint 3 (different evidence/scope — see research.md)"
    )


def test_magnesium_misattributed_citation_corrected(depletions):
    # PMID 22762246 is Hess 2012 (Aliment Pharmacol Ther), not the Danziger 2013
    # (Kidney Int) label it previously carried. PMID real + on-topic; label fixed.
    src = next(
        s for s in depletions["DEP_ANTACIDS_MAGNESIUM"]["sources"]
        if "22762246" in s.get("url", "")
    )
    assert "Hess" in src["label"], "magnesium citation label must be corrected to Hess et al."
    assert "Danziger" not in src["label"], "stale misattributed 'Danziger' label must be gone"
    assert "22762246" in src["url"], "the real, on-topic PMID stays"
