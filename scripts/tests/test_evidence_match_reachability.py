"""Clinical-evidence match reachability and provenance gates."""

from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from audits.evidence_match_reachability import build_reachability_report  # noqa: E402


def _match(entry_id: str, canonical: str | None = "garlic") -> dict:
    match = {
        "id": entry_id,
        "standard_name": "Garlic Extract",
        "study_type": "systematic_review_meta",
        "evidence_level": "ingredient-human",
        "references_structured": [{"pmid": "fixture-only"}],
    }
    if canonical is not None:
        match["matched_canonical_ids"] = [canonical]
    return match


def _product(stamped: list[dict] | None = None) -> dict:
    return {
        "dsld_id": "1",
        "product_name": "Garlic 1200 mg",
        "evidence_data": {"clinical_matches": stamped or []},
    }


def test_new_exact_match_missing_from_stamped_artifact_fails_candidate_gate():
    report = build_reachability_report(
        [_product()],
        recompute=lambda product: {
            "clinical_matches": [_match("INGR_GARLIC")]
        },
    )

    assert report["summary"]["newly_reachable_native_match_count"] == 1
    assert report["summary"]["affected_product_count"] == 1
    assert report["summary"]["candidate_clean"] is False
    assert report["products"][0]["newly_reachable_native_ids"] == [
        "INGR_GARLIC"
    ]


def test_exact_stamped_and_recomputed_match_is_clean():
    match = _match("INGR_GARLIC")
    report = build_reachability_report(
        [_product([match])],
        recompute=lambda product: {"clinical_matches": [match]},
    )

    assert report["summary"]["candidate_clean"] is True
    assert report["summary"]["newly_reachable_native_match_count"] == 0
    assert report["summary"]["stale_native_match_count"] == 0
    assert report["summary"]["unlinked_recomputed_match_count"] == 0


def test_exact_studied_formula_replays_after_probiotic_collection():
    from types import SimpleNamespace
    from audits import evidence_match_reachability as audit
    from studied_formulas import formula_clinical_match
    from test_studied_formula_assessment import seed_label

    product = seed_label()
    product["id"] = "formula-reachability"
    match = formula_clinical_match(product)
    product["evidence_data"] = {"clinical_matches": [match], "match_count": 1}
    # The initial ingredient collector runs before the formula's probiotic
    # measurements exist; the final replay must include that later stage.
    enricher = SimpleNamespace(_collect_evidence_data=lambda *args: {
        "clinical_matches": [], "match_count": 0,
    })
    report = build_reachability_report([product], recompute=lambda p: audit.recompute_evidence(enricher, p))

    assert report["summary"]["candidate_clean"] is True
    assert report["recomputed_entry_product_counts"] == {"FORMULA_SEED_DS01": 1}

    product["activeIngredients"][-1]["quantity"] = 200
    report = build_reachability_report([product], recompute=lambda p: audit.recompute_evidence(enricher, p))
    assert report["summary"]["candidate_clean"] is False
    assert report["summary"]["stale_native_match_count"] == 1


def test_source_row_link_is_identity_provenance_without_fake_canonical():
    match = _match("FORMULA_EXAMPLE", canonical=None)
    match["matched_source_row_refs"] = ["ingredientRows[0].nestedRows[0]"]
    report = build_reachability_report([_product([match])], recompute=lambda p: {"clinical_matches": [match]})
    assert report["summary"]["candidate_clean"] is True
    assert report["products"] == []


def test_match_without_canonical_or_marker_provenance_fails_closed():
    unlinked = _match("INGR_GARLIC", canonical=None)
    report = build_reachability_report(
        [_product([unlinked])],
        recompute=lambda product: {"clinical_matches": [unlinked]},
    )

    assert report["summary"]["candidate_clean"] is False
    assert report["summary"]["unlinked_recomputed_match_count"] == 1
    assert report["products"][0]["unlinked_recomputed_ids"] == [
        "INGR_GARLIC"
    ]


def test_removed_or_narrowed_match_is_reported_as_stale():
    report = build_reachability_report(
        [_product([_match("BRAND_GENERIC_ALIAS_LEAK")])],
        recompute=lambda product: {"clinical_matches": []},
    )

    assert report["summary"]["candidate_clean"] is False
    assert report["summary"]["stale_native_match_count"] == 1
    assert report["products"][0]["stale_native_ids"] == [
        "BRAND_GENERIC_ALIAS_LEAK"
    ]
