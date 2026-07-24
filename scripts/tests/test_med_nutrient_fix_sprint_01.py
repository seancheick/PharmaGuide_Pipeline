"""Fix Sprint 01 — regression lock for 4 needs_revision → publication-ready
conversions (see scripts/audits/fix_sprint_01/research.md). Every user-visible
claim was content-re-verified; citations were PubMed title+abstract verified.
"""

import json
import os

from test_med_nutrient_ul_safety import _UL, _max_dose


def _entries():
    path = os.path.join(
        os.path.dirname(__file__), os.pardir, "data", "medication_depletions.json"
    )
    with open(path, encoding="utf-8") as f:
        return {e["id"]: e for e in json.load(f)["depletions"]}


# Audit-metadata string fields are provenance, not user-visible copy — a review
# note may legitimately quote the very figure we removed from the display copy.
_META_KEYS = {
    "id",
    "citation_review_status",
    "citation_review_note",
    "reviewed_at",
    "reviewer",
}


def _all_text(e):
    """Concatenate the user-visible display string fields for phrase checks."""
    return " ".join(
        str(v) for k, v in e.items() if isinstance(v, str) and k not in _META_KEYS
    )


def _pmids(e):
    return {
        s.get("url", "").rstrip("/").rsplit("/", 1)[-1] for s in e.get("sources", [])
    }


def test_levothyroxine_calcium_verified_and_honest():
    e = _entries()["DEP_LEVOTHYROXINE_CALCIUM"]
    assert e["citation_review_status"] == "verified"
    # overstated magnitude corrected, tangents removed
    assert "40%" not in _all_text(e)
    assert "over-replacement" not in _all_text(e).lower()
    # verified on-topic sources kept
    assert {"10838651", "11716045"} <= _pmids(e)


def test_levothyroxine_iron_verified_with_primary_trial():
    e = _entries()["DEP_LEVOTHYROXINE_IRON"]
    assert e["citation_review_status"] == "verified"
    # placeholder replaced with the controlled trial
    assert "1443969" in _pmids(e)
    src_urls = " ".join(s.get("url", "") for s in e.get("sources", []))
    assert "ods.od.nih.gov" not in src_urls  # NIH-ODS placeholder gone
    assert "30–45%" not in _all_text(e) and "30-45%" not in _all_text(e)
    assert "thyroperoxidase" not in _all_text(e).lower()  # tangent removed


def test_ocp_b6_verified_downgraded_and_ul_safe():
    e = _entries()["DEP_OCP_VITAMINB6"]
    assert e["citation_review_status"] == "verified"
    assert e["evidence_level"] == "possible"  # weakest tier in the corpus enum
    assert "21967158" in _pmids(e)  # Wilson 2011
    # UL-safe: no above-UL B6 dose survives in any recommendation field
    limit, unit = _UL["vitamin_b6"]
    for field in ("recommendation", "alert_body", "monitoring_tip_short"):
        dose = _max_dose(e.get(field) or "", unit)
        assert dose is None or dose <= limit, f"{field}: {dose} {unit} > UL"
    # the high-dose caution is stated
    assert "not recommended" in e["recommendation"].lower()


def test_ocp_folate_rejected_premise_contradicted():
    e = _entries()["DEP_OCP_FOLATE"]
    assert e["citation_review_status"] == "rejected"
    assert "21967158" in _pmids(e)  # Wilson 2011 (the contradicting review)
    assert e.get("citation_review_note")  # rationale recorded in-place


# NOTE: the absolute corpus status counts are asserted by the MOST RECENT fix
# sprint only (currently test_med_nutrient_fix_sprint_02.py). Pinning them in
# every sprint file would mean each new sprint has to edit every older one. The
# per-entry assertions above are this sprint's durable contribution.
