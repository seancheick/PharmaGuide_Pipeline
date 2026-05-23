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

    def test_safety_blocked_substance_gets_specific_reason_if_mapping_gate_reaches_it(
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
        assert result["not_scorable_reason"] == "safety_blocked_substance"

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
