"""Fix Sprint 02 — regression lock for statins→CoQ10, corticosteroids→calcium,
and corticosteroids→vitamin D (see scripts/audits/fix_sprint_02/research.md).

Field-level audit results are recorded in research.md; this file locks the
resulting published state. Entry-level `verified` requires every published field
to pass, so these assertions target the specific defects that were fixed:
causal overstatement, universal recommendation, unsupported dose, mechanism
error, placeholder citation, and unsupported comparison amount.
"""

import json
import os

# Audit-metadata fields are provenance, not user-visible copy — a review note may
# legitimately quote the very phrase removed from the display copy.
_META_KEYS = {
    "id",
    "citation_review_status",
    "citation_review_note",
    "reviewed_at",
    "reviewer",
}


def _entries():
    path = os.path.join(
        os.path.dirname(__file__), os.pardir, "data", "medication_depletions.json"
    )
    with open(path, encoding="utf-8") as f:
        return {e["id"]: e for e in json.load(f)["depletions"]}


def _display_text(e):
    return " ".join(
        str(v) for k, v in e.items() if isinstance(v, str) and k not in _META_KEYS
    )


def _pmids(e):
    return {
        s.get("url", "").rstrip("/").rsplit("/", 1)[-1] for s in e.get("sources", [])
    }


def _source_urls(e):
    return " ".join(s.get("url", "") for s in e.get("sources", []))


def test_statins_coq10_relationship_kept_causal_claims_removed():
    e = _entries()["DEP_STATINS_COQ10"]
    assert e["citation_review_status"] == "verified"
    assert e["severity"] == "mild"  # real relationship, unproven consequence
    assert e["depletion_type"] == "depletion"
    text = _display_text(e)
    # causal overstatement + unsupported tissue claim removed
    assert "cardiac" not in text.lower()
    # unsupported routine dose removed
    assert "100–200 mg" not in text and "100-200 mg" not in text
    # unsupported comparison amount removed entirely
    assert "adequacy_threshold_mg" not in e
    # uncertainty is stated, not implied
    assert "uncertain" in e["recommendation"].lower()
    # both sides of the conflicting supplementation evidence are cited
    assert {"26192349", "8463436", "30371340", "32179207"} <= _pmids(e)
    assert "ods.od.nih.gov" not in _source_urls(e)


def test_corticosteroids_calcium_scoped_and_not_universal():
    e = _entries()["DEP_CORTICOSTEROIDS_CALCIUM"]
    assert e["citation_review_status"] == "verified"
    assert e["depletion_type"] == "depletion"  # genuine loss mechanism
    text = _display_text(e)
    # universal recommendation removed
    assert "All patients" not in text
    assert "1,000–1,500" not in text and "1,000-1,500" not in text
    # scope narrowed to prolonged systemic exposure
    assert "systemic" in text.lower()
    # comparison amount removed (guideline targets TOTAL intake incl. diet)
    assert "adequacy_threshold_mg" not in e
    # guideline + mechanism citations replace the placeholder
    assert {"37845798", "14687590"} <= _pmids(e)
    assert "ods.od.nih.gov" not in _source_urls(e)


def test_corticosteroids_vitamind_retyped_and_mechanism_error_removed():
    e = _entries()["DEP_CORTICOSTEROIDS_VITAMIND"]
    assert e["citation_review_status"] == "verified"
    # the depletion premise failed; this is now a monitoring consideration
    assert e["depletion_type"] == "monitoring_stability"
    assert e["evidence_level"] == "probable"
    text = _display_text(e)
    # the suspect mechanism is gone entirely
    assert "cyp24a1" not in text.lower()
    assert "hepatic" not in text.lower()
    # no universal dose
    assert "4,000 IU" not in text and "1,000–2,000 IU" not in text
    # false headline replaced
    assert "can lower vitamin d with long-term use" not in text.lower()
    assert "adequacy_threshold_mcg" not in e
    assert "37845798" in _pmids(e)  # 2022 ACR GIOP guideline
    assert "ods.od.nih.gov" not in _source_urls(e)


def test_corpus_status_counts_after_sprint_02():
    import collections

    c = collections.Counter(
        e.get("citation_review_status", "unverified") for e in _entries().values()
    )
    assert c["verified"] == 15
    assert c["needs_revision"] == 5
    assert c["rejected"] == 1
    assert c["unverified"] == 59
