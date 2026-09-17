"""Evidence-expansion Phase 1 audit contract (A-H taxonomy, coverage, queue).

Integrity invariants that must hold whatever the corpus looks like:
an unreviewed identity is never reported as reviewed, "no qualifying evidence"
requires a documented bounded search, a matched record that carries no efficacy
credit is not an evidence gap, and PubMed result volume never reaches evidence
strength.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from audits.evidence_expansion_2026_09 import build_inventory, build_queue  # noqa: E402


def _row(canonical_id="l_glutamine", **overrides):
    row = {"name": "L-Glutamine", "standard_name": "L-Glutamine", "canonical_id": canonical_id,
           "category": "amino_acids", "quantity": 500.0, "unit_normalized": "mg", "has_dose": True,
           "mapped": True, "role_classification": "active_scorable", "form_id": "l-glutamine powder"}
    row.update(overrides)
    return row


def _product(rows=None, accepted=(), rejected=(), **overrides):
    product = {"dsld_id": "1", "brand_name": "B", "product_name": "P", "module": "generic", "evidence": 0.0,
               "rows": [_row()] if rows is None else rows, "accepted_matches": list(accepted),
               "rejected_matches": list(rejected), "skipped_reasons_breakdown": {}}
    product.update(overrides)
    return product


def test_identity_without_a_record_is_not_reviewed_not_evidence_absent():
    primary, reasons, details = build_inventory.classify_zero(_product(), set(), {})

    assert primary == "A"
    assert reasons == ["A"]
    assert details == ["A_l_glutamine"]


def test_no_qualifying_evidence_requires_a_documented_bounded_search():
    reviewed = {build_inventory.ge._canonical_text("l_glutamine")}

    _, reasons, _ = build_inventory.classify_zero(_product(), reviewed, {})

    assert reasons == ["B"]


def test_matched_record_without_efficacy_credit_is_not_an_evidence_gap(monkeypatch):
    # A reference-only record (INGR_COPPER) matches but earns no points.
    monkeypatch.setattr(build_inventory, "reviewed_entries", lambda: {
        "INGR_COPPER": {"id": "INGR_COPPER", "study_type": "reference", "evidence_level": "reference",
                        "effect_direction": "positive_weak"}})
    product = _product(rows=[_row("copper")], accepted=[{"id": "INGR_COPPER"}])

    primary, reasons, details = build_inventory.classify_zero(product, set(), {"copper": ["INGR_COPPER"]})

    assert primary == "E" and "A" not in reasons
    assert details == ["E_accepted_match_zero_points"]


def test_accepted_match_with_points_and_zero_evidence_is_a_scorer_defect_candidate(monkeypatch):
    monkeypatch.setattr(build_inventory, "reviewed_entries", lambda: {
        "INGR_X": {"id": "INGR_X", "study_type": "systematic_review_meta", "evidence_level": "ingredient-human",
                   "effect_direction": "positive_strong"}})
    product = _product(accepted=[{"id": "INGR_X"}])

    primary, _, details = build_inventory.classify_zero(product, set(), {"l glutamine": ["INGR_X"]})

    assert primary == "G"
    assert details == ["G_accepted_match_with_points"]


def test_dose_and_form_rejections_are_separated():
    dose = _product(rejected=[{"id": "INGR_X", "reason_code": "below_applicable_clinical_dose"}])
    form = _product(rejected=[{"id": "INGR_X", "reason_code": "clinical_form_mismatch"}])

    assert build_inventory.classify_zero(dose, set(), {})[0] == "D"
    assert build_inventory.classify_zero(form, set(), {})[0] == "C"


def test_label_active_demoted_upstream_is_not_missing_evidence():
    product = _product(rows=[_row(role_classification="inactive_non_scorable", mapped=False)],
                       skipped_reasons_breakdown={"is_additive": 1})

    primary, reasons, details = build_inventory.classify_zero(product, set(), {})

    assert primary == "H" and reasons == ["H"]
    assert details == ["H_label_active_demoted_is_additive"]


def test_zero_amount_nutrition_panel_row_is_not_an_evidence_target():
    assert build_inventory.is_evidence_target_row(_row(quantity=0.0)) is False
    assert build_inventory.is_evidence_target_row(_row()) is True


def test_curation_recoverability_needs_a_mapped_dosed_active_without_a_record():
    assert build_inventory.recoverable_by_curation(_product(), {}) is True
    assert build_inventory.recoverable_by_curation(_product(), {"l glutamine": ["INGR_X"]}) is False
    assert build_inventory.recoverable_by_curation(_product(rows=[_row(has_dose=False)]), {}) is False


def test_discovery_volume_never_reaches_priority():
    identity = {"slots": 100, "products": 50, "evidence_le8_products": 10,
                "review_state": "not_reviewed", "candidate_discovery_volume": 9999}
    baseline = dict(identity, candidate_discovery_volume=0)

    assert build_queue.gap_priority(identity) == build_queue.gap_priority(baseline)
    assert build_queue.exposure_priority(identity) == build_queue.exposure_priority(baseline)


def test_queue_uncertainty_ranks_unreviewed_above_reviewed():
    base = {"slots": 100, "products": 50, "evidence_le8_products": 10}
    unreviewed = build_queue.gap_priority(dict(base, review_state="not_reviewed"))
    legacy = build_queue.gap_priority(dict(base, review_state="legacy_review_state_not_established"))
    reviewed = build_queue.gap_priority(
        dict(base, review_state="reviewed_no_qualifying_evidence_in_documented_scope"))

    assert unreviewed > legacy > reviewed


@pytest.mark.parametrize("name, expected_absent", [
    ("Garcinia Cambogia (Fruit) Extract", '"Extract"[tiab]'),
    ("Beet Root Powder", '"Powder"[tiab]'),
])
def test_generic_label_words_never_become_their_own_search_term(name, expected_absent):
    from audits.evidence_expansion_2026_09 import discover_literature

    clause = discover_literature.name_clause({"canonical_id": "x", "label_name": name,
                                              "label_spellings_seen": [name]})

    assert expected_absent.lower() not in clause.lower()


def test_homonym_exclusions_are_visible_in_the_query():
    from audits.evidence_expansion_2026_09 import discover_literature

    clause = discover_literature.name_clause({"canonical_id": "l_tyrosine", "label_name": "L-Tyrosine",
                                              "label_spellings_seen": ["Tyrosine"]})

    assert '"Tyrosine"[tiab]' in clause
    assert "NOT" in clause and "tyrosine kinase" in clause


def test_quarantined_screening_drafts_are_never_read_by_curation_tooling():
    """Draft subagent output contains known non-contiguous and composed "quotes".

    It is kept for audit provenance only; nothing in the curation toolchain may read it.
    """
    from pathlib import Path

    audit_dir = Path(__file__).resolve().parents[1] / "audits" / "evidence_expansion_2026_09"
    quarantine = audit_dir / "QUARANTINE_screening_drafts"

    assert quarantine.is_dir(), "the drafts must stay in a directory whose name marks them quarantined"
    readers = [path.name for path in audit_dir.glob("*.py")
               if quarantine.name in path.read_text()]

    assert readers == [], f"curation tooling must not read quarantined drafts: {readers}"
