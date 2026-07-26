"""Section 3 — antiseizure medication relationships made mechanism-specific.

All seven DEP_ANTICONVULSANTS_* records pointed at ``class:anticonvulsants``, a
40-member class spanning drugs with opposite hepatic pharmacology.  The
mechanism prose already named the real actors; the attribution did not follow
it, so a levetiracetam or lamotrigine patient was warned about CYP450-induction
effects those drugs do not cause.

Two mechanisms, two attributions:

- **Enzyme induction** (carbamazepine, phenytoin, phenobarbital, primidone)
  accelerates catabolism of 25-hydroxyvitamin D and vitamin K, and drives the
  secondary calcium loss and the classic phenytoin folate depletion.
  → ``class:enzyme_inducing_antiseizure_medications``
- **Valproate** is an enzyme INHIBITOR with its own chemistry: acylcarnitine
  conjugation drains carnitine, and biotinidase inhibition drains biotin.
  → ``class:valproate`` (one moiety, four salts — the form on the label varies,
  the mechanism does not)

B12 keeps neither: its own text says "may", its evidence is ``probable``, and
its source is a catalog link rather than a study, so it is suppressed pending
citation rather than shipped against 40 drugs.

Test-first: every taxonomy assertion below fails on pre-Section-3 data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parent.parent / "data"

BROAD = "class:anticonvulsants"
INDUCERS = "class:enzyme_inducing_antiseizure_medications"
VALPROATE = "class:valproate"

# RxNorm-verified 2026-07-26 (live rxnav lookup).
VALPROATE_MEMBERS = {
    "266856": "divalproex sodium",
    "9919": "sodium valproate",
    "40254": "valproate",
    "11118": "valproic acid",
}


@pytest.fixture(scope="module")
def classes() -> dict:
    return json.loads((DATA / "drug_classes.json").read_text())["classes"]


@pytest.fixture(scope="module")
def depletions() -> dict:
    entries = json.loads((DATA / "medication_depletions.json").read_text())["depletions"]
    return {e["id"]: e for e in entries}


def _suppressed(entry: dict) -> bool:
    return entry.get("citation_review_status") in {"needs_revision", "rejected"}


# --------------------------------------------------------------------------- #
# class:valproate
# --------------------------------------------------------------------------- #

def test_valproate_class_exists_with_every_salt(classes):
    """Depakote is divalproex; the label form must not decide whether we warn."""
    assert VALPROATE in classes, f"{VALPROATE} not defined"
    c = classes[VALPROATE]
    assert dict(zip(c["member_rxcuis"], c["member_names"])) == VALPROATE_MEMBERS


def test_valproate_class_is_sorted_and_parallel(classes):
    c = classes[VALPROATE]
    assert len(c["member_rxcuis"]) == len(c["member_names"])
    pairs = list(zip(c["member_names"], c["member_rxcuis"]))
    assert pairs == sorted(pairs), "members must be sorted by (name, rxcui)"


def test_valproate_class_excludes_inducers(classes):
    """Valproate inhibits CYP450; it must never join the inducer class."""
    rx = set(classes[VALPROATE]["member_rxcuis"])
    for rxcui, name in (
        ("2002", "carbamazepine"),
        ("8183", "phenytoin"),
        ("8134", "phenobarbital"),
        ("8691", "primidone"),
    ):
        assert rxcui not in rx, f"{name} is an inducer, not valproate"


def test_inducer_class_excludes_valproate_and_non_inducers(classes):
    rx = set(classes[INDUCERS]["member_rxcuis"])
    forbidden = {
        "11118": "valproic acid (enzyme inhibitor)",
        "266856": "divalproex sodium (enzyme inhibitor)",
        "25480": "gabapentin (renally cleared, no hepatic induction)",
        "187832": "pregabalin (renally cleared, no hepatic induction)",
        "114477": "levetiracetam (no CYP induction)",
        "28439": "lamotrigine (no CYP induction)",
        "32624": "oxcarbazepine (weak, dose-dependent — deferred)",
    }
    for rxcui, why in forbidden.items():
        assert rxcui not in rx, f"{INDUCERS} must not contain {why}"


# --------------------------------------------------------------------------- #
# Re-attribution
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "entry_id,expected_class",
    [
        # Induction-driven: the prose already named these four drugs.
        ("DEP_ANTICONVULSANTS_VITAMIND", INDUCERS),
        ("DEP_ANTICONVULSANTS_CALCIUM", INDUCERS),
        ("DEP_ANTICONVULSANTS_VITAMINK", INDUCERS),
        ("DEP_ANTICONVULSANTS_FOLATE", INDUCERS),
        # Valproate chemistry, not induction.
        ("DEP_ANTICONVULSANTS_LCARNITINE", VALPROATE),
        ("DEP_ANTICONVULSANTS_BIOTIN", VALPROATE),
    ],
)
def test_record_points_at_its_actual_mechanism(depletions, entry_id, expected_class):
    ref = depletions[entry_id]["drug_ref"]
    assert ref["type"] == "class"
    assert ref["id"] == expected_class


def test_no_displayed_record_still_points_at_the_broad_class(depletions):
    """The 40-member class mixes inducers, inhibitors and renally-cleared drugs.

    Nothing user-visible may be attributed to it — a claim that broad is a
    false positive for most of its members.
    """
    offenders = [
        e["id"]
        for e in depletions.values()
        if (e.get("drug_ref") or {}).get("id") == BROAD and not _suppressed(e)
    ]
    assert offenders == [], f"still attributed to {BROAD}: {offenders}"


def test_b12_is_suppressed_pending_a_real_citation(depletions):
    """Its own mechanism says "may" and its source is a catalog, not a study."""
    entry = depletions["DEP_ANTICONVULSANTS_VITAMINB12"]
    assert entry["citation_review_status"] == "needs_revision"


# --------------------------------------------------------------------------- #
# Consumer copy must not out-scope the attribution
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "entry_id",
    [
        "DEP_ANTICONVULSANTS_CALCIUM",
        "DEP_ANTICONVULSANTS_VITAMINK",
        "DEP_ANTICONVULSANTS_FOLATE",
        "DEP_ANTICONVULSANTS_LCARNITINE",
        "DEP_ANTICONVULSANTS_BIOTIN",
    ],
)
def test_copy_does_not_claim_all_seizure_medications(depletions, entry_id):
    """A narrowed record whose prose still says "seizure medications" reads to
    the user as the whole class — the stale-wording trap."""
    entry = depletions[entry_id]
    for field in ("alert_headline", "alert_body", "monitoring_tip_short",
                  "acknowledgement_note", "recommendation", "mechanism"):
        text = (entry.get(field) or "").lower()
        for phrase in ("all seizure", "all aeds", "all antiepileptic",
                       "any seizure medication", "all anticonvulsants"):
            assert phrase not in text, f"{entry_id}.{field} over-claims: {phrase!r}"


def test_valproate_records_name_valproate_not_the_class(depletions):
    for entry_id in ("DEP_ANTICONVULSANTS_LCARNITINE", "DEP_ANTICONVULSANTS_BIOTIN"):
        entry = depletions[entry_id]
        blob = " ".join(
            str(entry.get(f) or "")
            for f in ("mechanism", "alert_body", "clinical_impact")
        ).lower()
        assert "valproa" in blob, f"{entry_id} must name valproate"
