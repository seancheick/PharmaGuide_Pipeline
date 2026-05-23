"""Truthful NOT_SCORED diagnostics — step 1 of the NOT_SCORED triage slice.

Plan / context:
  - Full corpus audit (reports/not_scored_triage/SUMMARY.md, 2026-05-23) showed
    470 NOT_SCORED products. Every one carried the same misleading flag triplet:
        NO_ACTIVES_DETECTED + SCORING_INPUT_CONTRACT_GAP + SUPPLEMENT_TYPE_REINFERRED
    even though the enriched ingredient_quality_data.total_active was > 0 for
    460 of them. The enricher saw actives; the strict scoring contract filtered
    them out. The flag was lying about the state.

  - User decision: do NOT bulk-promote rejected rows back into ingredients_scorable
    (would break the strict contract just hardened). Instead, fix the *reporting*
    so the pipeline tells the truth about what's happening.

  - This slice is reporting-only:
      * Keep `NO_ACTIVES_DETECTED` only when enriched total_active == 0
        (the ~10 cases that are truly empty — DSLD authoring gaps).
      * Emit `NO_STRICT_SCORING_CANDIDATES` instead when enriched total_active
        > 0 but the strict-contract filter rejected everything.
      * Populate a new `not_scorable_reason` field on the scored product output
        so downstream consumers can distinguish the categories. Initial value
        is the generic `strict_contract_all_candidates_rejected`; the specific
        fail-closed vocab (macro_only_product, label_dose_not_declared,
        carrier_oil_only, plain_botanical_no_iqm_rule, etc.) is added in
        step 3 of the slice and refines this catch-all.

  - Verdict and scoring_status remain NOT_SCORED / not_applicable; this slice
    only changes the diagnostic strings, not the scoring decision.
"""

from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from score_supplements import SupplementScorer  # noqa: E402
from test_score_supplements import make_base_product  # noqa: E402


@pytest.fixture
def scorer():
    return SupplementScorer()


def _wipe_actives(product):
    """Strip all active-side fields so the mapping gate trips."""
    iqd = product["ingredient_quality_data"]
    iqd["ingredients_scorable"] = []
    iqd["ingredients"] = []
    iqd["unmapped_count"] = 0
    product["proprietary_data"]["total_active_ingredients"] = 0


def _make_truly_empty():
    """Product with no enriched actives (DSLD authoring gap case)."""
    product = make_base_product()
    _wipe_actives(product)
    product["ingredient_quality_data"]["total_active"] = 0
    product["supplement_type"] = {"type": "unknown", "active_count": 0}
    return product


def _make_strict_contract_rejected():
    """Product where enriched actives exist but the strict contract rejected them all.

    Mirrors the corpus pattern: total_active > 0, ingredients_scorable empty,
    skipped_reasons_breakdown carries the rejection categories.
    """
    product = make_base_product()
    _wipe_actives(product)
    iqd = product["ingredient_quality_data"]
    # enricher saw 12 actives (FYI Restore / 173708 pattern)
    iqd["total_active"] = 12
    iqd["skipped_non_scorable_count"] = 12
    iqd["skipped_reasons_breakdown"] = {
        "blend_header_total_weight_only": 2,
        "nested_under_non_therapeutic_parent": 10,
    }
    return product


def _make_rejected_with_rows(*rows, total_active=None):
    """Product with no strict scorable rows but explicit skipped-row evidence."""
    product = _make_strict_contract_rejected()
    iqd = product["ingredient_quality_data"]
    row_list = [dict(row) for row in rows]
    iqd["total_active"] = total_active if total_active is not None else max(1, len(row_list))
    iqd["skipped_non_scorable_count"] = len(row_list)
    iqd["ingredients_skipped"] = row_list
    iqd["ingredients_recognized_non_scorable"] = [
        row for row in row_list if row.get("recognized_non_scorable")
    ]
    return product


def _rejected_row(**overrides):
    row = {
        "name": "Rejected Active",
        "standard_name": "Rejected Active",
        "quantity": 1000.0,
        "unit": "mg",
        "has_dose": True,
        "recognized_non_scorable": True,
        "role_classification": "recognized_non_scorable",
        "skip_reason": "recognized_non_scorable",
        "score_exclusion_reason": "recognized_non_scorable",
        "recognition_source": "other_ingredients",
        "recognition_reason": "recognized_non_scorable",
        "recognition_type": "non_scorable",
    }
    row.update(overrides)
    return row


class TestTruthfulNotScoredFlags:
    def test_truly_zero_actives_keeps_no_actives_detected(self, scorer):
        """The ~10 corpus cases with total_active=0 are real DSLD authoring gaps.

        Their flag should remain NO_ACTIVES_DETECTED because that is in fact
        what happened: no actives reached the enricher.
        """
        product = _make_truly_empty()
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert "NO_ACTIVES_DETECTED" in result["flags"]
        assert "NO_STRICT_SCORING_CANDIDATES" not in result["flags"]
        assert result.get("not_scorable_reason") == "no_actives_detected"

    def test_strict_contract_rejection_emits_new_flag(self, scorer):
        """The ~460 corpus cases where enricher saw actives but contract dropped them.

        Flag must be NO_STRICT_SCORING_CANDIDATES — NOT the misleading
        NO_ACTIVES_DETECTED, because actives were in fact detected.
        SCORING_INPUT_CONTRACT_GAP is still accurate and remains.
        """
        product = _make_strict_contract_rejected()
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert "NO_STRICT_SCORING_CANDIDATES" in result["flags"]
        assert "NO_ACTIVES_DETECTED" not in result["flags"]
        assert "SCORING_INPUT_CONTRACT_GAP" in result["flags"]

    def test_strict_contract_rejection_populates_not_scorable_reason(self, scorer):
        """Lock the canonical step-1 reason string.

        Step-3 refines this catch-all into specific values (macro_only_product,
        label_dose_not_declared, plain_botanical_no_iqm_rule, etc.). Until then,
        the step-1 contract is: any product whose enricher saw actives but the
        strict contract rejected all of them carries this exact reason string.
        """
        product = _make_strict_contract_rejected()
        result = scorer.score_product(product)

        assert result["not_scorable_reason"] == "strict_contract_all_candidates_rejected"

    def test_mapping_gate_returns_truthful_reason_field(self, scorer):
        """The internal mapping_gate.reason should not lie either.

        Downstream code consults gate['reason']; it must match the flag.
        """
        product = _make_strict_contract_rejected()
        gate = scorer._mapping_gate(product)

        assert gate["stop"] is True
        assert gate["reason"] == "NO_STRICT_SCORING_CANDIDATES"
        assert "NO_STRICT_SCORING_CANDIDATES" in gate["flags"]
        assert "NO_ACTIVES_DETECTED" not in gate["flags"]

    def test_mapping_gate_truly_empty_keeps_legacy_reason(self, scorer):
        product = _make_truly_empty()
        gate = scorer._mapping_gate(product)

        assert gate["stop"] is True
        assert gate["reason"] == "NO_ACTIVES_DETECTED"
        assert "NO_ACTIVES_DETECTED" in gate["flags"]
        assert "NO_STRICT_SCORING_CANDIDATES" not in gate["flags"]

    def test_score_remains_none_for_both_paths(self, scorer):
        """Reporting-only slice — verdict and score must not change."""
        for builder in (_make_truly_empty, _make_strict_contract_rejected):
            product = builder()
            result = scorer.score_product(product)
            assert result["verdict"] == "NOT_SCORED", builder.__name__
            assert result["score_80"] is None, builder.__name__
            assert result["scoring_status"] == "not_applicable", builder.__name__


class TestEnrichedActivesSignal:
    """Lock the source-of-truth field that decides which flag to emit.

    The signal is ingredient_quality_data.total_active — the enricher's own
    count of active rows it saw, before the strict-contract filter.
    """

    def test_signal_is_ingredient_quality_data_total_active(self, scorer):
        product = _make_strict_contract_rejected()
        assert product["ingredient_quality_data"]["total_active"] == 12

        gate = scorer._mapping_gate(product)
        assert gate["reason"] == "NO_STRICT_SCORING_CANDIDATES"

        # Now flip the signal and re-evaluate.
        product["ingredient_quality_data"]["total_active"] = 0
        gate2 = scorer._mapping_gate(product)
        assert gate2["reason"] == "NO_ACTIVES_DETECTED"

    @pytest.mark.parametrize(
        "malformed_value",
        [None, "", "n/a", "12", "12.0", 12.0, -1, "garbage", []],
    )
    def test_malformed_total_active_does_not_crash_diagnostic_path(
        self, scorer, malformed_value
    ):
        """Reporting-layer hardening — a diagnostic path must never crash.

        DSLD/enricher contracts say total_active is an int >= 0, but a single
        malformed product must not take down a scoring run. The diagnostic
        gate must coerce safely and degrade to one of the two legal reasons
        ("NO_ACTIVES_DETECTED" or "NO_STRICT_SCORING_CANDIDATES").
        """
        product = _make_strict_contract_rejected()
        product["ingredient_quality_data"]["total_active"] = malformed_value

        gate = scorer._mapping_gate(product)
        assert gate["stop"] is True
        assert gate["reason"] in {
            "NO_ACTIVES_DETECTED",
            "NO_STRICT_SCORING_CANDIDATES",
        }
        assert gate.get("not_scorable_reason") in {
            "no_actives_detected",
            "strict_contract_all_candidates_rejected",
        }


class TestSpecificNotScoredReasonVocab:
    def test_carrier_oil_only_gets_specific_reason(self, scorer):
        product = _make_rejected_with_rows(
            _rejected_row(
                name="Organic Coconut Oil",
                standard_name="Extra Virgin Coconut Oil",
                recognition_reason="carrier_oil",
                canonical_source_db="other_ingredients",
            ),
            _rejected_row(
                name="Lauric Acid",
                standard_name="Lauric Acid",
                recognized_non_scorable=False,
                role_classification="inactive_non_scorable",
                skip_reason="excluded_nutrition_fact",
                score_exclusion_reason="excluded_nutrition_fact",
                recognition_source=None,
                recognition_reason=None,
            ),
        )

        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert result["score_80"] is None
        assert result["not_scorable_reason"] == "carrier_oil_only"

    def test_nutrition_fact_only_is_not_mislabeled_as_carrier_oil(self, scorer):
        """Negative guard against the carrier_oil_only over-classification.

        Note: after step 3b shipped, a single Dietary Fiber row IS legitimately
        macro_only_product (the macro-only-product rule subsumes this case).
        The point of this test is to verify the row never gets mislabeled as
        carrier_oil_only just because it sits in the same area of the
        diagnostic precedence tree.
        """
        product = _make_rejected_with_rows(
            _rejected_row(
                name="Dietary Fiber",
                standard_name="Fiber",
                recognized_non_scorable=False,
                role_classification="inactive_non_scorable",
                skip_reason="excluded_nutrition_fact",
                score_exclusion_reason="excluded_nutrition_fact",
                recognition_source=None,
                recognition_reason=None,
                canonical_source_db="ingredient_quality_map",
            )
        )

        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert result["not_scorable_reason"] != "carrier_oil_only"
        assert result["not_scorable_reason"] == "macro_only_product"

    def test_safety_flagged_substance_gets_specific_reason_if_mapping_gate_reaches_it(
        self, scorer
    ):
        product = _make_rejected_with_rows(
            _rejected_row(
                name="Colloidal Silver",
                standard_name="Colloidal Silver",
                recognition_source="banned_recalled_ingredients",
                recognition_reason="banned",
                canonical_source_db="banned_recalled",
            )
        )

        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert result["not_scorable_reason"] == "safety_flagged_substance_only"

    def test_excipient_only_gets_specific_reason(self, scorer):
        product = _make_rejected_with_rows(
            _rejected_row(
                name="Soya Lecithin",
                standard_name="Soya Lecithin",
                recognition_source="excipient_list",
                recognition_reason="known_excipient_partial",
                canonical_source_db="allergens",
            )
        )

        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert result["not_scorable_reason"] == "excipient_only_no_active"

    def test_allergen_source_alone_is_not_mislabeled_as_excipient_only(self, scorer):
        product = _make_rejected_with_rows(
            _rejected_row(
                name="Wheat Germ Oil",
                standard_name="Wheat",
                recognized_non_scorable=False,
                role_classification="inactive_non_scorable",
                skip_reason="no_quality_map_match",
                score_exclusion_reason="no_quality_map_match",
                recognition_source=None,
                recognition_reason=None,
                canonical_source_db="allergens",
            )
        )

        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert result["not_scorable_reason"] == "strict_contract_all_candidates_rejected"

    def test_subthreshold_absorption_enhancer_only_gets_specific_reason(self, scorer):
        product = _make_rejected_with_rows(
            _rejected_row(
                name="BioPerine Black Pepper Extract",
                standard_name="Piperine",
                quantity=3.0,
                recognition_source="absorption_enhancers",
                recognition_reason="absorption_enhancer_sub_threshold",
                recognition_type="threshold_demotion",
                demotion_reason="absorption_enhancer_sub_threshold",
                canonical_source_db="ingredient_quality_map",
            )
        )

        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert result["not_scorable_reason"] == "absorption_enhancer_sub_threshold_only"

    def test_blend_header_plus_subthreshold_enhancer_gets_bucket_a_reason(self, scorer):
        product = _make_rejected_with_rows(
            _rejected_row(
                name="Turmeric Curcumin Complex",
                standard_name="Turmeric",
                recognized_non_scorable=False,
                role_classification="inactive_non_scorable",
                skip_reason="blend_header_total_weight_only",
                score_exclusion_reason="blend_header_total",
                recognition_source=None,
                recognition_reason=None,
                is_blend_header=True,
                blend_total_weight_only=True,
            ),
            _rejected_row(
                name="BioPerine Black Pepper Extract",
                standard_name="Piperine",
                quantity=3.0,
                recognition_source="absorption_enhancers",
                recognition_reason="absorption_enhancer_sub_threshold",
                recognition_type="threshold_demotion",
                demotion_reason="absorption_enhancer_sub_threshold",
                canonical_source_db="ingredient_quality_map",
            ),
        )

        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert (
            result["not_scorable_reason"]
            == "blend_header_primary_with_absorption_enhancer_only"
        )


# ---------------------------------------------------------------------------
# Step 3b — expanded reporting-only vocab.
#
# Refines the 440-product residual in the step-1 catch-all
# 'strict_contract_all_candidates_rejected' into per-pattern diagnostic
# strings so downstream gates and the Flutter app can distinguish a real
# scoring-anchor gap from a genuinely-correct fail-closed. No scoring
# change; verdict and score remain NOT_SCORED / None for every case below.
#
# Deterministic precedence (after the step-3a checks already in place):
#   1. standardized_botanical_no_scorable_anchor  (highest signal — product-level)
#   2. active_pending_relocation_iqm_gap
#   3. blend_dose_in_product_name_only            (specific row reason)
#   4. macro_only_product
#   5. blend_header_primary_active_not_scored     (header has identity)
#   6. blend_total_no_scorable_identity           (header lacks identity)
#   7. plain_botanical_no_iqm_rule
#   8. label_dose_not_declared
#   → falls through to 'strict_contract_all_candidates_rejected'
# ---------------------------------------------------------------------------


class TestStep3bExpandedReasonVocab:
    def test_standardized_botanical_anchor_takes_precedence_when_meets_threshold(
        self, scorer
    ):
        """Product with empty scorable but validated meets_threshold standardized
        botanical evidence — even if the rejected rows look like plain blend
        headers or plain botanicals, the anchor signal wins because it's the
        most informative diagnostic and unlocks the Wave-6 scoring slice."""
        product = _make_rejected_with_rows(
            _rejected_row(
                name="Curcumin C3 Complex",
                standard_name="Turmeric",
                recognized_non_scorable=False,
                skip_reason="blend_header_total_weight_only",
                score_exclusion_reason="blend_header_total",
                recognition_source=None,
                recognition_reason=None,
                is_blend_header=True,
                blend_total_weight_only=True,
            ),
        )
        product["formulation_data"]["standardized_botanicals"] = [
            {
                "name": "Curcumin C3 Complex",
                "standard_name": "Turmeric",
                "meets_threshold": True,
            }
        ]
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert result["not_scorable_reason"] == "standardized_botanical_no_scorable_anchor"

    def test_active_pending_relocation_marker_emits_iqm_gap_reason(self, scorer):
        """Source DB explicitly flags this ingredient as needing IQM relocation.
        Bucket-B audit candidate for the small IQM batch slice."""
        product = _make_rejected_with_rows(
            _rejected_row(
                name="Cayenne Pepper",
                standard_name="Chili Pepper",
                recognition_source="other_ingredients",
                recognition_reason="active_pending_relocation",
                canonical_source_db="botanical_ingredients",
            )
        )
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert result["not_scorable_reason"] == "active_pending_relocation_iqm_gap"

    def test_blend_header_without_dosage_emits_product_name_only_reason(self, scorer):
        """Tocotrienols 50 mg / 203189 pattern — product name carries the dose
        but the label row has unit=NP."""
        product = _make_rejected_with_rows(
            _rejected_row(
                name="Tocotrienol-Tocopherol Complex",
                standard_name="Vitamin E",
                quantity=0.0,
                unit="NP",
                recognized_non_scorable=False,
                skip_reason="blend_header_without_dosage",
                score_exclusion_reason="blend_header_without_dosage",
                recognition_source=None,
                recognition_reason=None,
                is_blend_header=True,
            ),
        )
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert result["not_scorable_reason"] == "blend_dose_in_product_name_only"

    def test_all_macro_rows_emit_macro_only_product(self, scorer):
        """Glucomannan / Fiber Fusion pattern — every row is a macro/nutrition fact."""
        product = _make_rejected_with_rows(
            _rejected_row(
                name="Dietary Fiber",
                standard_name="Fiber",
                quantity=4.0,
                unit="Gram(s)",
                recognized_non_scorable=False,
                skip_reason="excluded_nutrition_fact",
                score_exclusion_reason="excluded_nutrition_fact",
                recognition_source=None,
                recognition_reason=None,
            ),
            _rejected_row(
                name="Total Carbohydrate",
                standard_name="Carbohydrate",
                quantity=4.0,
                unit="Gram(s)",
                recognized_non_scorable=False,
                skip_reason="excluded_nutrition_fact",
                score_exclusion_reason="excluded_nutrition_fact",
                recognition_source=None,
                recognition_reason=None,
            ),
        )
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert result["not_scorable_reason"] == "macro_only_product"

    def test_blend_header_with_identity_emits_primary_active_not_scored(self, scorer):
        """Turmeric Complex 500 mg without piperine — blend header has real
        identity (canonical_id=turmeric, standard_name=Turmeric) but the
        scorer can't credit per-ingredient dose. Bucket-A scoring slice target."""
        product = _make_rejected_with_rows(
            _rejected_row(
                name="Turmeric Curcumin Complex",
                standard_name="Turmeric",
                canonical_id="turmeric",
                canonical_source_db="botanical_ingredients",
                recognized_non_scorable=False,
                skip_reason="blend_header_total_weight_only",
                score_exclusion_reason="blend_header_total",
                recognition_source=None,
                recognition_reason=None,
                is_blend_header=True,
                blend_total_weight_only=True,
            ),
            _rejected_row(
                name="Turmeric Root",
                standard_name="Turmeric",
                canonical_id="turmeric",
                quantity=0.0,
                unit="NP",
                recognized_non_scorable=False,
                skip_reason="nested_under_non_therapeutic_parent",
                score_exclusion_reason="nested_display_only",
                recognition_source=None,
                recognition_reason=None,
            ),
        )
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert result["not_scorable_reason"] == "blend_header_primary_active_not_scored"

    def test_blend_header_without_identity_emits_no_scorable_identity(self, scorer):
        """Generic 'Proprietary Blend' header with no canonical_id — we don't
        even know what's in it. Distinct from blend_header_primary_active_not_scored
        because the diagnostic is much more pessimistic."""
        product = _make_rejected_with_rows(
            _rejected_row(
                name="Proprietary Blend",
                standard_name="Proprietary Blend",
                canonical_id=None,
                canonical_source_db=None,
                recognized_non_scorable=False,
                skip_reason="blend_header_total_weight_only",
                score_exclusion_reason="blend_header_total",
                recognition_source=None,
                recognition_reason=None,
                is_blend_header=True,
                blend_total_weight_only=True,
            ),
        )
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert result["not_scorable_reason"] == "blend_total_no_scorable_identity"

    def test_plain_botanical_recognition_emits_no_iqm_rule_reason(self, scorer):
        """Marshmallow Root / Cissus / Burdock pattern — recognized as a real
        plant by part, but no IQM rule to score it and no standardized-extract
        evidence. Wave-6 scoring-design candidate (Standardized Botanical Anchor
        is for the meets_threshold subset; this is the plain-herb residual)."""
        product = _make_rejected_with_rows(
            _rejected_row(
                name="Marshmallow",
                standard_name="Marshmallow Root",
                canonical_id="marshmallow_root",
                quantity=1000.0,
                unit="mg",
                recognition_source="botanical_ingredients",
                recognition_reason="root",
                canonical_source_db="botanical_ingredients",
            )
        )
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert result["not_scorable_reason"] == "plain_botanical_no_iqm_rule"

    def test_all_no_dose_rows_emit_label_dose_not_declared(self, scorer):
        """Children's Chewable Vitamin pattern — every row is a recognized
        nutrient but the label has unit=NP. Cannot score what isn't dosed."""
        product = _make_rejected_with_rows(
            _rejected_row(
                name="Vitamin A",
                standard_name="Vitamin A",
                quantity=0.0,
                unit="NP",
                recognition_source="iqd_contract",
                recognition_reason="no_dose_evidence",
                canonical_source_db="ingredient_quality_map",
            ),
            _rejected_row(
                name="Vitamin C",
                standard_name="Vitamin C",
                quantity=0.0,
                unit="NP",
                recognition_source="iqd_contract",
                recognition_reason="no_dose_evidence",
                canonical_source_db="ingredient_quality_map",
            ),
        )
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert result["not_scorable_reason"] == "label_dose_not_declared"

    def test_anchor_supersedes_other_specific_reasons(self, scorer):
        """Sanity check: meets_threshold standardized botanical wins even when
        the product also looks like a pending-relocation candidate."""
        product = _make_rejected_with_rows(
            _rejected_row(
                name="Cayenne Pepper",
                standard_name="Chili Pepper",
                recognition_source="other_ingredients",
                recognition_reason="active_pending_relocation",
                canonical_source_db="botanical_ingredients",
            )
        )
        product["formulation_data"]["standardized_botanicals"] = [
            {
                "name": "Cayenne Standardized",
                "standard_name": "Cayenne",
                "meets_threshold": True,
            }
        ]
        result = scorer.score_product(product)

        assert result["not_scorable_reason"] == "standardized_botanical_no_scorable_anchor"

    def test_truly_unknown_pattern_keeps_generic_fallback(self, scorer):
        """Products whose row reasons don't match any specific pattern should
        keep the step-1 catch-all so we can investigate them. Negative case
        guards against over-broad classification."""
        product = _make_rejected_with_rows(
            _rejected_row(
                name="Mystery Compound XYZ",
                standard_name="Unknown",
                quantity=500.0,
                unit="mg",
                recognized_non_scorable=False,
                skip_reason="no_quality_map_match",
                score_exclusion_reason="no_quality_map_match",
                recognition_source=None,
                recognition_reason=None,
                canonical_source_db="unmapped",
            )
        )
        result = scorer.score_product(product)

        assert result["not_scorable_reason"] == "strict_contract_all_candidates_rejected"
