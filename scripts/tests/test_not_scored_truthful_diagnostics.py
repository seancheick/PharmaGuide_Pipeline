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
    def test_standardized_botanical_no_scorable_anchor_fires_when_not_track_a1_eligible(
        self, scorer
    ):
        """Step-3b diagnostic reason for products with meets_threshold=True but
        WITHOUT a real anchor row that satisfies Track A.1 strict identity match.

        Doctor's Best Digestive Enzymes pattern: Bromelain has meets_threshold=True
        via marker_word_match, but the actual Bromelain row is qty=0 NP nested in
        an undosed enzyme blend. Track A.1 correctly excludes this (no real anchor
        dose). The step-3b diagnostic still fires for downstream consumers.

        Used to test 'anchor reason takes precedence over other step-3b reasons'
        with a Curcumin C3 fixture, but that fixture is now Track-A.1-eligible
        and gets actually scored — see TestTrackA1StandardizedBotanicalAnchorSlice.
        """
        product = _make_rejected_with_rows(
            _rejected_row(
                name="Digestive Enzyme Blend",
                standard_name="Digestive Enzyme Blends",
                quantity=0.0,
                unit="NP",
                recognized_non_scorable=False,
                skip_reason="recognized_non_scorable",
                score_exclusion_reason="recognized_non_scorable",
                recognition_source=None,
                recognition_reason=None,
                canonical_source_db="proprietary_blends",
            ),
            _rejected_row(
                name="Bromelain",
                standard_name="Digestive Enzymes",
                canonical_id="digestive_enzymes",
                quantity=0.0,
                unit="NP",
                recognized_non_scorable=False,
                skip_reason="nested_under_non_therapeutic_parent",
                score_exclusion_reason="nested_display_only",
                recognition_source=None,
                recognition_reason=None,
                canonical_source_db="ingredient_quality_map",
            ),
        )
        product["formulation_data"]["standardized_botanicals"] = [
            {
                "name": "Bromelain",
                "standard_name": "Bromelain",
                "meets_threshold": True,
                "evidence_source": "marker_word_match",
            }
        ]
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert result["not_scorable_reason"] == "standardized_botanical_no_scorable_anchor"
        assert "SCORED_VIA_STANDARDIZED_BOTANICAL_ANCHOR" not in result["flags"]

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
        """Bone, Flesh & Cartilage 440 mg pattern — named blend header
        (standard_name="Bone, Flesh & Cartilage Blend") with NO canonical_id.
        Step-3b classifies this as blend_header_primary_active_not_scored.

        Note: blend headers WITH valid canonical_id (e.g., Turmeric Complex
        with canonical_id="turmeric") are now promoted by Track A.2a — see
        TestTrackA2BlendHeaderAnchorSlice. This step-3b reason still fires
        for the 133 Bucket A products that A.2a held back (91 with
        canonical_id=None, 17 BLEND_* canonicals, 20 denylisted class-level
        canonicals, etc.)."""
        product = _make_rejected_with_rows(
            _rejected_row(
                name="Bone, Flesh & Cartilage Blend",
                standard_name="Bone, Flesh & Cartilage Blend",
                canonical_id=None,
                canonical_source_db=None,
                quantity=880.0,
                unit="mg",
                recognized_non_scorable=False,
                skip_reason="blend_header_total_weight_only",
                score_exclusion_reason="blend_header_total",
                recognition_source=None,
                recognition_reason=None,
                is_blend_header=True,
                blend_total_weight_only=True,
            ),
            _rejected_row(
                name="Bone",
                standard_name="Bone",
                canonical_id=None,
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


# ---------------------------------------------------------------------------
# Track A.1 — Standardized Botanical Anchor scoring slice.
#
# Spec: reports/not_scored_triage/track_A1_standardized_botanical_anchor_spec.md
#
# This is a SCORING change, not reporting. When a product has no IQM
# ingredients_scorable but at least one formulation_data.standardized_botanicals[]
# row with meets_threshold=True AND a real dosed row whose identity matches
# (strict — exact normalized match or canonical_source_db=standardized_botanicals;
# NO token intersection), let the sections compute and emit a conservative
# capped score with a verdict ceiling.
#
# Constants:
#   display cap        = 60.0/100 (= 48.0/80 quality_score)
#   verdict ceiling    = CAUTION (anchor products are never SAFE)
#   poor threshold     = 32.0/80 (unchanged from v3 config)
#   flag               = SCORED_VIA_STANDARDIZED_BOTANICAL_ANCHOR
#   score_basis        = "standardized_botanical_anchor"
# ---------------------------------------------------------------------------


def _make_anchor_eligible(
    *,
    std_bot_name: str = "EpiCor",
    std_bot_std_name: str = "EpiCor",
    row_name: str = "EpiCor",
    row_std_name: str = "EpiCor",
    row_canonical_id: str = "epicor",
    row_canonical_source_db: str = "standardized_botanicals",
    row_quantity: float = 500.0,
    row_unit: str = "mg",
    extra_rows=(),
):
    """Builder for a product that satisfies the strict anchor eligibility rule.

    Defaults model the EpiCor 500 mg canary: single dosed row whose identity
    matches a meets_threshold standardized botanical via
    canonical_source_db=standardized_botanicals AND exact name/std_name.
    """
    product = _make_strict_contract_rejected()
    iqd = product["ingredient_quality_data"]
    iqd["total_active"] = 1 + len(extra_rows)
    rows = [
        _rejected_row(
            name=row_name,
            standard_name=row_std_name,
            canonical_id=row_canonical_id,
            canonical_source_db=row_canonical_source_db,
            quantity=row_quantity,
            unit=row_unit,
            recognized_non_scorable=False,
            skip_reason="recognized_non_scorable",
            score_exclusion_reason="recognized_non_scorable",
            recognition_source="standardized_botanicals",
            recognition_reason="botanical_identity",
        )
    ] + [dict(r) for r in extra_rows]
    iqd["skipped_non_scorable_count"] = len(rows)
    iqd["ingredients_skipped"] = rows
    iqd["ingredients_recognized_non_scorable"] = []
    product["formulation_data"]["standardized_botanicals"] = [
        {
            "name": std_bot_name,
            "standard_name": std_bot_std_name,
            "meets_threshold": True,
            "evidence_source": "branded_form",
        }
    ]
    return product


class TestTrackA1StandardizedBotanicalAnchorSlice:
    # --- positive eligibility ---

    def test_anchor_via_canonical_source_db_standardized_botanicals(self, scorer):
        """EpiCor-style row: src_db is standardized_botanicals + real dose.
        Anchor activates regardless of std_name/canonical_id matching."""
        product = _make_anchor_eligible()
        result = scorer.score_product(product)

        assert result["verdict"] != "NOT_SCORED"
        assert result["scoring_status"] == "scored"
        assert result["score_basis"] == "standardized_botanical_anchor"
        assert "SCORED_VIA_STANDARDIZED_BOTANICAL_ANCHOR" in result["flags"]
        assert result["not_scorable_reason"] is None
        assert result["section_scores"]["A_ingredient_quality"]["score"] is not None
        assert (
            "scored_via_standardized_botanical_anchor_path"
            in result["strict_scoring_contract"]["findings"]
        )
        assert (
            result["scoring_metadata"]["strict_scoring_contract"]
            == result["strict_scoring_contract"]
        )

    def test_anchor_via_exact_std_name_match(self, scorer):
        """Curcumin C3 pattern: row src_db is ingredient_quality_map (not
        standardized_botanicals), but exact std_name match wins anchor."""
        product = _make_anchor_eligible(
            std_bot_name="Curcumin C3 Complex",
            std_bot_std_name="Curcumin",
            row_name="Curcumin C3 Complex",
            row_std_name="Curcumin",
            row_canonical_id="curcumin",
            row_canonical_source_db="ingredient_quality_map",
            row_quantity=1000.0,
        )
        result = scorer.score_product(product)

        assert result["verdict"] != "NOT_SCORED"
        assert "SCORED_VIA_STANDARDIZED_BOTANICAL_ANCHOR" in result["flags"]

    # --- negative eligibility (regression guards) ---

    def test_anchor_does_not_trigger_when_nested_undosed_blend(self, scorer):
        """Doctor's Best Digestive Enzymes pattern. Bromelain has
        meets_threshold=True but the actual row is qty=0 NP — no real anchor
        dose exists. Must stay NOT_SCORED."""
        product = _make_strict_contract_rejected()
        iqd = product["ingredient_quality_data"]
        iqd["total_active"] = 2
        iqd["ingredients_skipped"] = [
            _rejected_row(
                name="Digestive Enzyme Blend",
                standard_name="Digestive Enzyme Blends",
                quantity=0.0,
                unit="NP",
                skip_reason="recognized_non_scorable",
                canonical_source_db="proprietary_blends",
            ),
            _rejected_row(
                name="Bromelain",
                standard_name="Digestive Enzymes",
                canonical_id="digestive_enzymes",
                quantity=0.0,
                unit="NP",
                skip_reason="nested_under_non_therapeutic_parent",
                canonical_source_db="ingredient_quality_map",
            ),
        ]
        product["formulation_data"]["standardized_botanicals"] = [
            {
                "name": "Bromelain",
                "standard_name": "Bromelain",
                "meets_threshold": True,
                "evidence_source": "marker_word_match",
            }
        ]
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert "SCORED_VIA_STANDARDIZED_BOTANICAL_ANCHOR" not in result["flags"]

    def test_anchor_does_not_trigger_when_dose_belongs_to_unrelated_blend(self, scorer):
        """Green Coffee Bean 62034 pattern. Standardized botanical exists, but
        the dosed row is a generic Proprietary Blend (not the standardized
        active). Strict identity match prevents the unrelated blend mass from
        anchoring the standardized botanical."""
        product = _make_strict_contract_rejected()
        iqd = product["ingredient_quality_data"]
        iqd["total_active"] = 2
        iqd["ingredients_skipped"] = [
            _rejected_row(
                name="Proprietary Blend",
                standard_name="General Proprietary Blends",
                canonical_id="BLEND_GENERAL",
                quantity=1500.0,
                unit="mg",
                skip_reason="recognized_non_scorable",
                canonical_source_db="proprietary_blends",
                is_blend_header=True,
            ),
            _rejected_row(
                name="Green Coffee bean extract",
                standard_name="Chlorogenic Acids",
                canonical_id="chlorogenic_acids",
                quantity=0.0,
                unit="NP",
                skip_reason="nested_under_non_therapeutic_parent",
                canonical_source_db="ingredient_quality_map",
            ),
        ]
        product["formulation_data"]["standardized_botanicals"] = [
            {
                "name": "Green Coffee bean extract",
                "standard_name": "Green Coffee Bean",
                "meets_threshold": True,
                "evidence_source": "percentage_local",
            }
        ]
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert "SCORED_VIA_STANDARDIZED_BOTANICAL_ANCHOR" not in result["flags"]

    def test_anchor_does_not_trigger_when_no_meets_threshold(self, scorer):
        """Standardized botanical present but meets_threshold=False — anchor
        should not activate. Product stays NOT_SCORED with the step-3b
        diagnostic instead."""
        product = _make_anchor_eligible()
        product["formulation_data"]["standardized_botanicals"][0]["meets_threshold"] = False
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert "SCORED_VIA_STANDARDIZED_BOTANICAL_ANCHOR" not in result["flags"]

    def test_anchor_does_not_trigger_without_standardized_botanicals(self, scorer):
        product = _make_anchor_eligible()
        product["formulation_data"]["standardized_botanicals"] = []
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert "SCORED_VIA_STANDARDIZED_BOTANICAL_ANCHOR" not in result["flags"]

    def test_anchor_does_not_trigger_when_dose_unit_is_NP(self, scorer):
        """Evening Primrose Oil pattern: identity matches but unit is
        'unspecified' / NP. Dose check rejects."""
        product = _make_anchor_eligible(row_quantity=0.0, row_unit="unspecified")
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert "SCORED_VIA_STANDARDIZED_BOTANICAL_ANCHOR" not in result["flags"]

    def test_anchor_identity_match_is_strict_not_token_intersection(self, scorer):
        """Guard against the bug where shared generic words (extract, root,
        complex, oil) would falsely match. Row 'Marshmallow Extract' must NOT
        anchor a 'Bromelain Extract' standardized botanical just because
        both contain 'Extract'."""
        product = _make_anchor_eligible(
            std_bot_name="Bromelain Extract",
            std_bot_std_name="Bromelain",
            row_name="Marshmallow Extract",
            row_std_name="Marshmallow Root",
            row_canonical_id="marshmallow_root",
            row_canonical_source_db="botanical_ingredients",  # NOT standardized_botanicals
            row_quantity=1000.0,
        )
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert "SCORED_VIA_STANDARDIZED_BOTANICAL_ANCHOR" not in result["flags"]

    # --- architectural locks ---

    def test_anchor_a1_remains_zero_no_invented_bio_score(self, scorer):
        """The whole point: do NOT invent an IQM A1 bio_score for anchor
        products. A1 must compute to 0.0 because ingredients_scorable is empty."""
        product = _make_anchor_eligible()
        result = scorer.score_product(product)

        assert result["section_scores"]["A_ingredient_quality"]["score"] is not None
        # the actual A1 value lives in breakdown
        assert result["breakdown"]["A"]["A1"] == 0.0

    def test_b0_safety_block_still_wins_over_anchor(self, scorer):
        """Safety gate at B0 must still trip for anchor-eligible products
        carrying banned ingredients. The anchor path only activates AFTER
        B0 passes."""
        product = _make_anchor_eligible()
        product["contaminant_data"]["banned_substances"] = {
            "found": True,
            "substances": [
                {
                    "ingredient": "Ephedra",
                    "match_type": "exact",
                    "status": "banned",
                    "severity_level": "critical",
                }
            ],
        }
        result = scorer.score_product(product)

        assert result["verdict"] in {"BLOCKED", "UNSAFE"}
        # anchor flag must NOT be emitted when safety gate trips
        assert "SCORED_VIA_STANDARDIZED_BOTANICAL_ANCHOR" not in result["flags"]

    # --- verdict ceiling ---

    def test_anchor_ceiling_forces_caution_when_otherwise_safe(self, scorer):
        """Anchor product whose raw quality_score >= poor_threshold (32) but
        without safety flags would normally verdict SAFE. Ceiling forces
        CAUTION. Locks the 'never SAFE' invariant."""
        product = _make_anchor_eligible()
        # ensure section B gives a high score (no harmful_additives etc) → push above poor_threshold
        # _make_strict_contract_rejected() already has empty contaminant_data;
        # the EpiCor-style fixture's B alone clears poor_threshold.
        result = scorer.score_product(product)

        assert result["score_80"] is not None
        if result["score_80"] >= 32.0:
            assert result["verdict"] == "CAUTION", (
                f"Anchor product with quality_score={result['score_80']} >= 32 "
                f"must be CAUTION, not {result['verdict']}"
            )

    def test_anchor_poor_remains_poor_below_threshold(self, scorer):
        """Cran-Max pattern: low B + low D → quality_score 18/80 < 32 → POOR.
        Ceiling does NOT upgrade POOR to CAUTION; only blocks SAFE."""
        product = _make_anchor_eligible()
        # zero out B/C/D signals so the math lands below poor_threshold
        product["contaminant_data"] = {
            "banned_substances": {"found": False, "substances": []},
            "harmful_additives": {"found": True, "additives": [
                {"name": "Artificial Color", "severity": "critical"},
                {"name": "Sucralose", "severity": "moderate"},
            ]},
            "allergens": {"found": False, "allergens": []},
        }
        result = scorer.score_product(product)

        if result["score_80"] is not None and result["score_80"] < 32.0:
            assert result["verdict"] == "POOR"

    # --- score cap ---

    def test_anchor_score_capped_at_display_60(self, scorer):
        """Defensive cap at 60.0/100. Even if a product hits the absolute
        ceiling of B+C+D+A5b, display must not exceed 60."""
        product = _make_anchor_eligible()
        # synthesize maximum-possible product-level signals
        product["delivery_tier"] = 1  # +3 A3
        product["absorption_enhancer_paired"] = True  # +3 A4
        product["formulation_data"]["organic"] = {"usda_verified": True}  # +1 A5a
        product["formulation_data"]["synergy_clusters"] = []  # 0 A5c
        product["manufacturer_data"]["top_manufacturer"] = {"found": True, "score_bonus": 5}
        product["evidence_data"] = {"clinical_matches": [
            {"study_id": "PMID12345", "ingredient": "EpiCor", "strength": "RCT"},
        ] * 5, "match_count": 5}
        result = scorer.score_product(product)

        if "SCORED_VIA_STANDARDIZED_BOTANICAL_ANCHOR" in result["flags"]:
            assert result["score_100_equivalent"] is not None
            assert result["score_100_equivalent"] <= 60.0, (
                f"Anchor product display={result['score_100_equivalent']} exceeds cap 60.0"
            )


# ---------------------------------------------------------------------------
# Track A.2a — Bucket A blend-header anchor scoring slice (narrow).
#
# Spec: reports/not_scored_triage/track_A2_blend_header_anchor_spec.md
#
# Eligibility (must satisfy ALL):
#   1. ingredients_scorable empty
#   2. Track A.1 (standardized_botanical anchor) does NOT fire
#   3. At least one blend_header row with:
#        - quantity > 0, unit not in ANCHOR_NON_DOSE_UNITS
#        - canonical_id non-empty
#        - canonical_id NOT starting with BLEND_ or PII_
#        - canonical_id NOT in {prebiotics, probiotics, whey_protein, collagen}
#          (digestive_enzymes landed in Wave 6.Z A.2b with a child-dose guard)
#        - canonical_source_db in {ingredient_quality_map, botanical_ingredients}
#
# Constants:
#   display cap        = 60.0/100 (= 48.0/80 quality)
#   verdict ceiling    = CAUTION (anchor products are never SAFE)
#   flag               = SCORED_VIA_BLEND_HEADER_ANCHOR
#   score_basis        = "blend_header_anchor"
# ---------------------------------------------------------------------------


def _make_blend_header_anchor_eligible(
    *,
    header_name: str = "Creatine Monohydrate Blend",
    header_std_name: str = "Creatine Monohydrate",
    header_canonical_id: str = "creatine_monohydrate",
    header_canonical_source_db: str = "ingredient_quality_map",
    header_quantity: float = 5.0,
    header_unit: str = "Gram(s)",
):
    """Builder for a Bucket A blend-header anchor candidate.

    Defaults model the GNC Creatine Advance XR canary: blend header carries
    canonical_id=creatine_monohydrate, real 5g dose, src_db=IQM.
    """
    product = _make_strict_contract_rejected()
    iqd = product["ingredient_quality_data"]
    iqd["total_active"] = 1
    iqd["ingredients_skipped"] = [
        _rejected_row(
            name=header_name,
            standard_name=header_std_name,
            canonical_id=header_canonical_id,
            canonical_source_db=header_canonical_source_db,
            quantity=header_quantity,
            unit=header_unit,
            recognized_non_scorable=False,
            skip_reason="blend_header_total_weight_only",
            score_exclusion_reason="blend_header_total",
            recognition_source=None,
            recognition_reason=None,
            is_blend_header=True,
            blend_total_weight_only=True,
            is_proprietary_blend=True,  # preserves B5 opacity penalty path
        )
    ]
    iqd["skipped_non_scorable_count"] = 1
    iqd["ingredients_recognized_non_scorable"] = []
    # IMPORTANT: must NOT have meets_threshold standardized botanical, or A.1
    # would win precedence (which is correct, but breaks the A.2a path test).
    product["formulation_data"]["standardized_botanicals"] = []
    return product


class TestTrackA2BlendHeaderAnchorSlice:
    # --- positive eligibility ---

    def test_blend_header_anchor_eligible_for_single_compound_canonical(self, scorer):
        """Creatine pattern: blend header has canonical_id=creatine_monohydrate,
        real dose 5g, src_db=IQM."""
        product = _make_blend_header_anchor_eligible()
        result = scorer.score_product(product)

        assert result["verdict"] != "NOT_SCORED"
        assert result["scoring_status"] == "scored"
        assert result["score_basis"] == "blend_header_anchor"
        assert "SCORED_VIA_BLEND_HEADER_ANCHOR" in result["flags"]
        assert result["not_scorable_reason"] is None
        # contract finding present
        findings = result["strict_scoring_contract"]["findings"]
        assert "scored_via_blend_header_anchor_path" in findings

    def test_blend_header_anchor_eligible_for_botanical_canonical(self, scorer):
        """Echinacea pattern: header canonical_id=echinacea, src_db=botanical_ingredients."""
        product = _make_blend_header_anchor_eligible(
            header_name="Echinacea Root Blend",
            header_std_name="Echinacea",
            header_canonical_id="echinacea",
            header_canonical_source_db="botanical_ingredients",
            header_quantity=900.0,
            header_unit="mg",
        )
        result = scorer.score_product(product)

        assert result["verdict"] != "NOT_SCORED"
        assert "SCORED_VIA_BLEND_HEADER_ANCHOR" in result["flags"]

    # --- negative eligibility — DENYLIST enforcement ---

    @pytest.mark.parametrize(
        "denylisted_canon",
        # digestive_enzymes was removed from this list when Wave 6.Z A.2b
        # landed (see scripts/tests/test_blend_header_anchor_digestive_enzymes_v1_2026_05_25.py).
        # The remaining four cids still need dedicated slices.
        ["prebiotics", "probiotics", "whey_protein", "collagen"],
    )
    def test_blend_header_anchor_rejects_denylisted_canonical(self, scorer, denylisted_canon):
        """Class-level canonicals still denylisted because each needs its
        own dedicated scoring slice (CFU provenance / fiber / protein).
        They must stay NOT_SCORED under Track A.2a."""
        product = _make_blend_header_anchor_eligible(
            header_canonical_id=denylisted_canon,
        )
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert "SCORED_VIA_BLEND_HEADER_ANCHOR" not in result["flags"]

    @pytest.mark.parametrize(
        "blend_canon",
        ["BLEND_GENERAL", "BLEND_SUPERFOOD", "BLEND_ENZYME", "BLEND_METABOLAID"],
    )
    def test_blend_header_anchor_rejects_BLEND_prefix(self, scorer, blend_canon):
        """BLEND_* prefixed canonicals are generic-blend taxonomy by definition.
        They ARE the opacity case and must stay NOT_SCORED."""
        product = _make_blend_header_anchor_eligible(header_canonical_id=blend_canon)
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert "SCORED_VIA_BLEND_HEADER_ANCHOR" not in result["flags"]

    @pytest.mark.parametrize(
        "pii_canon",
        ["PII_HERBAL_EXTRACT_GENERIC", "PII_SEDITOL_BRANDED_BLEND", "PII_XYLANASE"],
    )
    def test_blend_header_anchor_rejects_PII_prefix(self, scorer, pii_canon):
        """PII_* prefixed canonicals are broad generic IDs. Must stay NOT_SCORED."""
        product = _make_blend_header_anchor_eligible(header_canonical_id=pii_canon)
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert "SCORED_VIA_BLEND_HEADER_ANCHOR" not in result["flags"]

    def test_blend_header_anchor_rejects_when_canonical_id_is_none(self, scorer):
        """91 of 187 Bucket A products have header canonical_id=None.
        Named blend with no IQM identity is too uncertain — must stay NOT_SCORED."""
        product = _make_blend_header_anchor_eligible(header_canonical_id="")
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert "SCORED_VIA_BLEND_HEADER_ANCHOR" not in result["flags"]

    def test_blend_header_anchor_rejects_when_src_db_is_proprietary_blends(self, scorer):
        """canonical_source_db=proprietary_blends means it's just a generic
        blend taxonomy entry, not a real IQM/botanical identity."""
        product = _make_blend_header_anchor_eligible(
            header_canonical_source_db="proprietary_blends",
        )
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert "SCORED_VIA_BLEND_HEADER_ANCHOR" not in result["flags"]

    def test_blend_header_anchor_rejects_when_src_db_is_other_ingredients(self, scorer):
        product = _make_blend_header_anchor_eligible(
            header_canonical_source_db="other_ingredients",
        )
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert "SCORED_VIA_BLEND_HEADER_ANCHOR" not in result["flags"]

    def test_blend_header_anchor_rejects_when_dose_is_NP_or_zero(self, scorer):
        product = _make_blend_header_anchor_eligible(
            header_quantity=0.0, header_unit="NP",
        )
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert "SCORED_VIA_BLEND_HEADER_ANCHOR" not in result["flags"]

    # --- architectural locks ---

    def test_blend_header_anchor_a1_stays_zero(self, scorer):
        """Critical: A1 must remain 0.0 for these products. The existing
        proprietary-blend skip in _compute_bioavailability_score preserves
        blend opacity — anchor scoring does NOT pollute A1."""
        product = _make_blend_header_anchor_eligible()
        result = scorer.score_product(product)

        assert "SCORED_VIA_BLEND_HEADER_ANCHOR" in result["flags"]
        assert result["breakdown"]["A"]["A1"] == 0.0

    def test_b0_safety_block_wins_over_blend_header_anchor(self, scorer):
        """Safety gate B0 must still trip for anchor-eligible products carrying
        banned ingredients. Anchor flag must NOT be emitted under B0 BLOCKED."""
        product = _make_blend_header_anchor_eligible()
        product["contaminant_data"]["banned_substances"] = {
            "found": True,
            "substances": [
                {
                    "ingredient": "Ephedra",
                    "match_type": "exact",
                    "status": "banned",
                    "severity_level": "critical",
                }
            ],
        }
        result = scorer.score_product(product)

        assert result["verdict"] in {"BLOCKED", "UNSAFE"}
        assert "SCORED_VIA_BLEND_HEADER_ANCHOR" not in result["flags"]

    # --- precedence ---

    def test_track_a1_anchor_wins_over_bucket_a(self, scorer):
        """Both signals present: A.1 takes precedence (standardized botanical
        signal is more informative than blend-header identity alone)."""
        product = _make_blend_header_anchor_eligible(
            header_canonical_id="curcumin",
            header_canonical_source_db="ingredient_quality_map",
        )
        # add meets_threshold standardized botanical that A.1 would match
        product["formulation_data"]["standardized_botanicals"] = [
            {
                "name": "Creatine Monohydrate Blend",
                "standard_name": "Creatine Monohydrate",
                "meets_threshold": True,
                "evidence_source": "branded_form",
            }
        ]
        result = scorer.score_product(product)

        assert "SCORED_VIA_STANDARDIZED_BOTANICAL_ANCHOR" in result["flags"]
        assert "SCORED_VIA_BLEND_HEADER_ANCHOR" not in result["flags"]
        assert result["score_basis"] == "standardized_botanical_anchor"

    # --- cap + ceiling ---

    def test_blend_header_anchor_score_capped_at_display_60(self, scorer):
        """Defensive cap at 60.0/100 — same as Track A.1."""
        product = _make_blend_header_anchor_eligible()
        # synthesize maximum-possible product-level signals
        product["delivery_tier"] = 1
        product["absorption_enhancer_paired"] = True
        product["formulation_data"]["organic"] = {"usda_verified": True}
        product["manufacturer_data"]["top_manufacturer"] = {"found": True, "score_bonus": 5}
        product["evidence_data"] = {
            "clinical_matches": [
                {"study_id": "PMID12345", "ingredient": "Creatine", "strength": "RCT"}
            ] * 5,
            "match_count": 5,
        }
        result = scorer.score_product(product)

        if "SCORED_VIA_BLEND_HEADER_ANCHOR" in result["flags"]:
            assert result["score_100_equivalent"] is not None
            assert result["score_100_equivalent"] <= 60.0, (
                f"Bucket A anchor display={result['score_100_equivalent']} exceeds cap 60.0"
            )

    def test_blend_header_anchor_ceiling_forces_caution_when_otherwise_safe(self, scorer):
        """Anchor products are never SAFE. If math would verdict SAFE, force CAUTION."""
        product = _make_blend_header_anchor_eligible()
        result = scorer.score_product(product)

        assert result["score_80"] is not None
        if result["score_80"] >= 32.0:
            assert result["verdict"] == "CAUTION", (
                f"Bucket A anchor quality_score={result['score_80']} >= 32 "
                f"must be CAUTION, not {result['verdict']}"
            )
