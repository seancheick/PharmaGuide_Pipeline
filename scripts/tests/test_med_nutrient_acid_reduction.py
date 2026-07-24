"""Section 2 — remaining acid-reduction records re-scoped by evidence.

The four records sat on the coarse class:antacids ("PPIs and antacids") but the
mechanism is acid-SUPPRESSION, not neutralizing antacids:

- iron    → PPI + H2 (new class:acid_suppressants); spans both tiers (Lam 2017)
- calcium → PPI-only (fracture epi null for H2)
- vitamin C, zinc → REJECTED as depletion warnings (evidence-based)

Test-first: assertions fail on pre-Section-2 data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parent.parent / "data"
ACID = "class:acid_suppressants"


@pytest.fixture(scope="module")
def classes() -> dict:
    return json.loads((DATA / "drug_classes.json").read_text())["classes"]


@pytest.fixture(scope="module")
def depletions() -> dict:
    entries = json.loads((DATA / "medication_depletions.json").read_text())["depletions"]
    return {e["id"]: e for e in entries}


# --------------------------------------------------------------------------- #
# class:acid_suppressants (PPI + H2)
# --------------------------------------------------------------------------- #

def test_acid_suppressant_class_spans_ppi_and_h2(classes):
    names = set(classes[ACID]["member_names"])
    assert "omeprazole" in names and "pantoprazole" in names, "must include PPIs"
    assert "famotidine" in names and "cimetidine" in names, "must include H2 blockers"


def test_acid_suppressant_class_excludes_neutralizing_antacids(classes):
    # Neutralizing antacids (calcium carbonate etc.) SUPPRESS nothing — they must
    # not be in the acid-suppressant class.
    names = {n.lower() for n in classes[ACID]["member_names"]}
    for antacid in ("calcium carbonate", "aluminum hydroxide", "magnesium hydroxide"):
        assert antacid not in names, f"{antacid} must not be in {ACID}"


# --------------------------------------------------------------------------- #
# Re-scopes + statuses
# --------------------------------------------------------------------------- #

def test_iron_is_acid_suppressant_scoped_and_verified(depletions):
    e = depletions["DEP_ANTACIDS_IRON"]
    assert e["drug_ref"]["id"] == ACID
    assert e["citation_review_status"] == "verified"


def test_calcium_is_ppi_only_and_verified(depletions):
    e = depletions["DEP_ANTACIDS_CALCIUM"]
    assert e["drug_ref"]["id"] == "class:proton_pump_inhibitors"
    assert e["citation_review_status"] == "verified"


@pytest.mark.parametrize("entry_id", ["DEP_ANTACIDS_VITAMINC", "DEP_ANTACIDS_ZINC"])
def test_weak_records_rejected_with_rationale(depletions, entry_id):
    e = depletions[entry_id]
    assert e["citation_review_status"] == "rejected", f"{entry_id} should be rejected"
    assert e.get("citation_review_note"), f"{entry_id} rejection must carry a documented rationale"


def test_no_antacid_record_left_on_coarse_antacid_class_when_verified(depletions):
    # A verified acid-reduction record must be scoped (PPI or acid_suppressants),
    # never the coarse class:antacids ("PPIs and antacids").
    for eid in ("DEP_ANTACIDS_IRON", "DEP_ANTACIDS_CALCIUM"):
        assert depletions[eid]["drug_ref"]["id"] != "class:antacids"


def test_acid_reduction_records_drop_handbook_citations(depletions):
    banned = ("Drug-Induced Nutrient Depletion Handbook", "nlmcatalog")
    for eid in ("DEP_ANTACIDS_IRON", "DEP_ANTACIDS_CALCIUM",
                "DEP_ANTACIDS_VITAMINC", "DEP_ANTACIDS_ZINC"):
        for s in depletions[eid]["sources"]:
            blob = s.get("label", "") + s.get("url", "")
            assert not any(b in blob for b in banned), f"{eid} still cites a handbook/placeholder"
