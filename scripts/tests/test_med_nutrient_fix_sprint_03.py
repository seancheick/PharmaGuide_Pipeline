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


# NOTE: the Sprint-3 "deferred diuretic records untouched" test was retired once
# Section 1 (audit/med-nutrient-diuretics-remaining) completed that deferred work
# — calcium→loop class, thiamine→furosemide, folate→triamterene, zinc→thiazide.
# Their final state is owned by test_med_nutrient_diuretics_remaining.py.


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


# --------------------------------------------------------------------------- #
# Step 3 — enzyme-inducing antiseizure medications → vitamin D
#
# Vitamin D catabolism is driven by strong hepatic CYP inducers, not every AED.
# Only the vitamin D record moves. valproate (an enzyme INHIBITOR — biotin /
# L-carnitine records) must never enter this class; oxcarbazepine is a weaker,
# dose-dependent inducer left for separate review.
# --------------------------------------------------------------------------- #

EIASM = "class:enzyme_inducing_antiseizure_medications"
EIASM_REQUIRED = {"2002": "carbamazepine", "8134": "phenobarbital", "8183": "phenytoin", "8691": "primidone"}
EIASM_FORBIDDEN_NAMES = {"valproate", "valproic acid", "divalproex", "oxcarbazepine"}
EIASM_FORBIDDEN_RXCUIS = {"32624"}  # oxcarbazepine


def test_eiasm_class_exists_with_the_four_inducers(classes):
    assert EIASM in classes, f"{EIASM} not defined"
    c = classes[EIASM]
    rx, names = set(c["member_rxcuis"]), set(c["member_names"])
    for rxcui, name in EIASM_REQUIRED.items():
        assert rxcui in rx and name in names, f"{EIASM} missing {name} ({rxcui})"


def test_eiasm_excludes_valproate_and_oxcarbazepine(classes):
    c = classes[EIASM]
    names = {n.lower() for n in c["member_names"]}
    rx = set(c["member_rxcuis"])
    assert not (names & EIASM_FORBIDDEN_NAMES), (
        f"{EIASM} must exclude non-inducers {names & EIASM_FORBIDDEN_NAMES} "
        "(valproate is an enzyme INHIBITOR; oxcarbazepine pending separate review)"
    )
    assert not (rx & EIASM_FORBIDDEN_RXCUIS), f"{EIASM} must exclude rxcui {rx & EIASM_FORBIDDEN_RXCUIS}"


def test_vitamin_d_anticonvulsant_repointed(depletions):
    assert depletions["DEP_ANTICONVULSANTS_VITAMIND"]["drug_ref"]["id"] == EIASM


@pytest.mark.parametrize(
    "entry_id",
    [
        "DEP_ANTICONVULSANTS_CALCIUM", "DEP_ANTICONVULSANTS_FOLATE", "DEP_ANTICONVULSANTS_VITAMINB12",
        "DEP_ANTICONVULSANTS_VITAMINK", "DEP_ANTICONVULSANTS_BIOTIN", "DEP_ANTICONVULSANTS_LCARNITINE",
    ],
)
def test_deferred_anticonvulsant_records_untouched(depletions, entry_id):
    # Especially BIOTIN + LCARNITINE — valproate-specific, must never ride the
    # enzyme-inducing class.
    assert depletions[entry_id]["drug_ref"]["id"] == "class:anticonvulsants", (
        f"{entry_id} must NOT be repointed in Sprint 3 (see research.md)"
    )


# --------------------------------------------------------------------------- #
# Permanent regression — no dead / inert class references
#
# The PM contract: every class a depletion record points at must exist, have at
# least one member, and resolve at least one RxCUI. build_interaction_db.py emits
# one drug_class_map row per drug_classes.json class straight from member_rxcuis,
# so "exists with ≥1 numeric member_rxcui" is equivalent to "≥1 rxcui reaches
# drug_class_map" — a dead or empty class would silently disable a signal.
# (The app-bridge resolution leg is covered by the Flutter parity test.)
# --------------------------------------------------------------------------- #


def test_every_referenced_class_exists_has_members_and_resolves_rxcuis(classes, depletions):
    dead, empty, unresolved = [], [], []
    for e in depletions.values():
        ref = e["drug_ref"]
        if ref["type"] != "class":
            continue
        cid = ref["id"]
        if cid not in classes:
            dead.append((e["id"], cid))
            continue
        rxcuis = classes[cid].get("member_rxcuis", [])
        if len(rxcuis) < 1:
            empty.append((e["id"], cid))
        elif not any(str(r).isdigit() for r in rxcuis):
            unresolved.append((e["id"], cid))
    assert not dead, f"depletion records point at nonexistent classes: {dead}"
    assert not empty, f"depletion records point at member-less classes: {empty}"
    assert not unresolved, f"classes resolve no numeric RxCUI: {unresolved}"


def test_ppi_class_positively_resolves_omeprazole(classes):
    # Destination of the Step 2 repoint must really resolve a canonical PPI.
    assert "7646" in set(classes[PPI]["member_rxcuis"]), "PPI class must resolve omeprazole (7646)"
