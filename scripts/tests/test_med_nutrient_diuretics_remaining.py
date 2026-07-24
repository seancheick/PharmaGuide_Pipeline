"""Section 1 — remaining diuretic records made drug/subclass-specific.

Sprint 3 left four diuretic records on the coarse class:diuretics (which mixes
loop, thiazide, and potassium-sparing agents). Each is actually specific:

- calcium   → LOOP only (loops are calciuric via NKCC2; thiazides RETAIN calcium)
- thiamine  → furosemide-specific
- folate    → triamterene-specific (DHFR inhibitor / folate analog)
- zinc      → see the zinc assertions (evidence-scoped or rejected)

Citations are also replaced (the originals were handbooks / a generic fact sheet /
a magnesium paper mis-cited for calcium). Test-first: taxonomy assertions fail on
pre-Section-1 data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parent.parent / "data"
LOOP = "class:loop_diuretics"


@pytest.fixture(scope="module")
def classes() -> dict:
    return json.loads((DATA / "drug_classes.json").read_text())["classes"]


@pytest.fixture(scope="module")
def depletions() -> dict:
    entries = json.loads((DATA / "medication_depletions.json").read_text())["depletions"]
    return {e["id"]: e for e in entries}


# --------------------------------------------------------------------------- #
# class:loop_diuretics
# --------------------------------------------------------------------------- #

def test_loop_class_exists_with_loops(classes):
    c = classes[LOOP]
    names = set(c["member_names"])
    for n in ("furosemide", "bumetanide", "torsemide", "ethacrynic acid"):
        assert n in names, f"{LOOP} missing loop agent {n}"


def test_loop_class_excludes_thiazides_and_ksparing(classes):
    rx = set(classes[LOOP]["member_rxcuis"])
    forbidden = {
        "5487": "hydrochlorothiazide",
        "2409": "chlorthalidone",
        "9997": "spironolactone",
        "644": "amiloride",
        "10763": "triamterene",
    }
    hits = {r: n for r, n in forbidden.items() if r in rx}
    assert not hits, f"{LOOP} must exclude non-loop agents: {hits}"


# --------------------------------------------------------------------------- #
# Repoints
# --------------------------------------------------------------------------- #

def test_calcium_is_loop_specific(depletions):
    assert depletions["DEP_DIURETICS_CALCIUM"]["drug_ref"]["id"] == LOOP


def test_thiamine_is_furosemide_specific(depletions):
    ref = depletions["DEP_DIURETICS_THIAMINE"]["drug_ref"]
    assert ref["type"] == "drug" and ref["id"] == "4603", "thiamine must be furosemide (rxcui 4603)"


def test_folate_is_triamterene_specific(depletions):
    ref = depletions["DEP_DIURETICS_FOLATE"]["drug_ref"]
    assert ref["type"] == "drug" and ref["id"] == "10763", "folate must be triamterene (rxcui 10763)"


def test_zinc_is_thiazide_scoped(depletions):
    # Evidence (Wester RCT) is thiazide-specific; loop is much weaker. The record
    # must NOT claim all-diuretics or loop scope.
    assert depletions["DEP_DIURETICS_ZINC"]["drug_ref"]["id"] == "class:thiazide_diuretics"


def test_all_four_reach_a_final_status(depletions):
    for eid in ("DEP_DIURETICS_CALCIUM", "DEP_DIURETICS_THIAMINE",
                "DEP_DIURETICS_FOLATE", "DEP_DIURETICS_ZINC"):
        e = depletions.get(eid)
        assert e is None or e.get("citation_review_status") in {"verified", "rejected"}, (
            f"{eid} left without a final status"
        )


def test_no_diuretic_record_left_on_coarse_class(depletions):
    # After Section 1, none of the four remaining diuretic records may point at
    # the coarse class:diuretics. (zinc lands on a scoped class or is rejected.)
    for eid in ("DEP_DIURETICS_CALCIUM", "DEP_DIURETICS_THIAMINE",
                "DEP_DIURETICS_FOLATE", "DEP_DIURETICS_ZINC"):
        e = depletions.get(eid)
        if e is None:
            continue  # rejected entries may be removed
        if e.get("citation_review_status") == "rejected":
            continue
        assert e["drug_ref"]["id"] != "class:diuretics", (
            f"{eid} still on coarse class:diuretics"
        )


# --------------------------------------------------------------------------- #
# Citations replaced — no handbook / generic-fact-sheet / wrong-topic sources on
# a published (verified) record. Filled in once research lands.
# --------------------------------------------------------------------------- #

def test_published_diuretic_records_have_primary_citations(depletions):
    banned = ("Drug-Induced Nutrient Depletion Handbook", "nlmcatalog")
    for eid in ("DEP_DIURETICS_CALCIUM", "DEP_DIURETICS_THIAMINE",
                "DEP_DIURETICS_FOLATE", "DEP_DIURETICS_ZINC"):
        e = depletions.get(eid)
        if e is None or e.get("citation_review_status") != "verified":
            continue
        for s in e["sources"]:
            label, url = s.get("label", ""), s.get("url", "")
            assert not any(b in label or b in url for b in banned), (
                f"{eid} verified but still cites a handbook/placeholder: {label}"
            )
