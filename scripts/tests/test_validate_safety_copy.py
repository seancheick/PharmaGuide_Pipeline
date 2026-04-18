"""Tests for scripts/validate_safety_copy.py — authored-copy contract.

Covers the banned_recalled Path C fields and the interaction-rule authored
copy contract. Uses injected fixtures (not the production JSON files) so
tests are deterministic regardless of authoring progress.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Add scripts/ to sys.path so we can import the validator module.
SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

from validate_safety_copy import (  # noqa: E402
    validate_banned_recalled_entry,
    validate_depletion_entry,
    validate_interaction_sub_rule,
    validate_interaction_rule,
)


# ---------------------------------------------------------------------------
# banned_recalled per-entry validator
# ---------------------------------------------------------------------------


def _good_substance_entry() -> dict:
    return {
        "id": "banned_ephedra",
        "standard_name": "Ephedra",
        "ban_context": "substance",
        "safety_warning": (
            "FDA banned ephedra in dietary supplements in 2004 after it was "
            "linked to strokes, heart attacks, and over 155 deaths. Stop and "
            "consult a doctor."
        ),
        "safety_warning_one_liner": (
            "FDA-banned stimulant linked to strokes and heart attacks. Stop "
            "immediately."
        ),
    }


def _good_adulterant_entry() -> dict:
    return {
        "id": "adulterant_metformin",
        "standard_name": "Metformin (as undeclared adulterant)",
        "ban_context": "adulterant_in_supplements",
        "safety_warning": (
            "A prescription diabetes drug found undeclared in supplements — "
            "risk of dangerous low blood sugar. Stop the supplement and talk "
            "to your doctor. Does not affect prescribed metformin."
        ),
        "safety_warning_one_liner": (
            "Prescription drug hidden in supplements. Stop and consult your doctor."
        ),
    }


def test_good_substance_passes_strict():
    result = validate_banned_recalled_entry(_good_substance_entry(), strict=True)
    assert result.ok, f"expected clean pass, got {result.errors}"


def test_good_adulterant_passes_strict():
    result = validate_banned_recalled_entry(_good_adulterant_entry(), strict=True)
    assert result.ok, f"expected clean pass, got {result.errors}"


def test_adulterant_without_guardrail_fails():
    entry = _good_adulterant_entry()
    # Strip the "in supplements" guardrail phrase.
    entry["safety_warning"] = (
        "Metformin is a prescription diabetes drug linked to cardiovascular risk. "
        "Stop and consult your doctor."
    )
    result = validate_banned_recalled_entry(entry, strict=True)
    assert not result.ok
    assert any("guardrail" in e.lower() or "in supplement" in e.lower()
               for e in result.errors), result.errors


def test_encyclopedic_opener_fails():
    entry = _good_substance_entry()
    entry["safety_warning"] = (
        "Ephedra is a synthetic stimulant that was banned by FDA in 2004 "
        "after linked deaths. Stop and consult a doctor."
    )
    result = validate_banned_recalled_entry(entry, strict=True)
    assert not result.ok
    assert any("encyclopedic opener" in e for e in result.errors), result.errors


def test_derivation_template_opener_fails():
    entry = _good_substance_entry()
    entry["safety_warning"] = (
        "Ephedra is banned: linked to strokes, heart attacks. Stop and "
        "consult a doctor."
    )
    result = validate_banned_recalled_entry(entry, strict=True)
    assert not result.ok
    assert any("derivation template" in e for e in result.errors), result.errors


def test_missing_risk_verb_fails():
    entry = _good_substance_entry()
    entry["safety_warning"] = (
        "Ephedra is a stimulant historically used in weight-loss products and "
        "has been reviewed by FDA several times since the 1990s for efficacy."
    )
    result = validate_banned_recalled_entry(entry, strict=True)
    assert not result.ok
    assert any("risk/action verb" in e for e in result.errors), result.errors


def test_one_liner_without_terminal_punct_fails():
    entry = _good_substance_entry()
    entry["safety_warning_one_liner"] = "FDA-banned stimulant linked to strokes"
    result = validate_banned_recalled_entry(entry, strict=True)
    assert not result.ok
    assert any("terminal punctuation" in e or "must end with" in e
               for e in result.errors), result.errors


def test_one_liner_with_semicolon_fails():
    entry = _good_substance_entry()
    entry["safety_warning_one_liner"] = "Stop; consult your doctor."
    result = validate_banned_recalled_entry(entry, strict=True)
    assert not result.ok
    assert any("semicolon" in e for e in result.errors), result.errors


def test_length_bounds_enforced():
    entry = _good_substance_entry()
    entry["safety_warning"] = "Stop!"  # way too short
    result = validate_banned_recalled_entry(entry, strict=True)
    assert not result.ok
    assert any("length" in e for e in result.errors), result.errors


def test_legacy_warning_message_field_blocked():
    entry = _good_substance_entry()
    entry["warning_message"] = "leftover Flutter field"
    result = validate_banned_recalled_entry(entry, strict=True)
    assert not result.ok
    assert any("warning_message" in e for e in result.errors), result.errors


def test_invalid_ban_context_fails():
    entry = _good_substance_entry()
    entry["ban_context"] = "oops_typo"
    result = validate_banned_recalled_entry(entry, strict=True)
    assert not result.ok
    assert any("invalid ban_context" in e for e in result.errors), result.errors


def test_authoring_mode_allows_missing_fields():
    entry = {
        "id": "banned_something",
        "standard_name": "Something",
    }
    # Authoring mode — missing authored fields are warnings, not errors.
    result = validate_banned_recalled_entry(entry, strict=False)
    assert result.ok, f"authoring mode should not fail on missing fields: {result.errors}"
    assert any("ban_context" in w for w in result.warnings)


def test_strict_mode_rejects_missing_fields():
    entry = {
        "id": "banned_something",
        "standard_name": "Something",
    }
    result = validate_banned_recalled_entry(entry, strict=True)
    assert not result.ok
    assert any("missing ban_context" in e for e in result.errors)
    assert any("missing safety_warning" in e for e in result.errors)


# ---------------------------------------------------------------------------
# interaction_rules per-sub-rule validator
# ---------------------------------------------------------------------------


def _good_avoid_drug_class_rule() -> dict:
    return {
        "alert_headline": "May boost your diabetes medication",
        "alert_body": (
            "Berberine lowers blood sugar like metformin. If you take a "
            "diabetes medication, monitor glucose and talk to your prescriber "
            "before adding berberine."
        ),
        "informational_note": (
            "Berberine has blood-sugar-lowering effects relevant to people "
            "on diabetes medications."
        ),
    }


def test_good_avoid_rule_passes_strict():
    result = validate_interaction_sub_rule(
        "RULE_X", "drug_class_rule",
        _good_avoid_drug_class_rule(), "avoid", strict=True,
    )
    assert result.ok, result.errors


def test_severe_rule_missing_conditional_framing_fails():
    sub = _good_avoid_drug_class_rule()
    sub["alert_body"] = (
        "Berberine lowers blood sugar with effects similar to metformin. "
        "Stop berberine when taking diabetes medications, and check with "
        "a doctor."
    )
    result = validate_interaction_sub_rule(
        "RULE_X", "drug_class_rule", sub, "avoid", strict=True,
    )
    assert not result.ok
    assert any("conditional framing" in e for e in result.errors), result.errors


def test_screaming_headline_fails():
    sub = _good_avoid_drug_class_rule()
    sub["alert_headline"] = "STOP: interaction with diabetes meds"
    result = validate_interaction_sub_rule(
        "RULE_X", "drug_class_rule", sub, "avoid", strict=True,
    )
    assert not result.ok
    assert any("screaming alarm" in e for e in result.errors), result.errors


def test_medical_acronyms_allowed_in_headline():
    """MAOI, FDA, SSRI, NSAID — legitimate medical acronyms must not trip
    the all-caps check."""
    sub = _good_avoid_drug_class_rule()
    sub["alert_headline"] = "Interaction with MAOI antidepressants"
    result = validate_interaction_sub_rule(
        "RULE_X", "drug_class_rule", sub, "avoid", strict=True,
    )
    assert result.ok, result.errors


def test_exclamation_in_headline_fails():
    sub = _good_avoid_drug_class_rule()
    sub["alert_headline"] = "Do not take with diabetes meds!"
    result = validate_interaction_sub_rule(
        "RULE_X", "drug_class_rule", sub, "avoid", strict=True,
    )
    assert not result.ok
    assert any("should not end with !" in e for e in result.errors), result.errors


def test_imperative_in_informational_note_fails():
    sub = _good_avoid_drug_class_rule()
    sub["informational_note"] = (
        "Stop berberine if you take a diabetes medication without your "
        "doctor's approval first."
    )
    result = validate_interaction_sub_rule(
        "RULE_X", "drug_class_rule", sub, "avoid", strict=True,
    )
    assert not result.ok
    assert any("imperative verb" in e for e in result.errors), result.errors


def test_caution_rule_doesnt_require_conditional_framing():
    """Non-severe rules may use any framing — they're not rendered without profile."""
    sub = {
        "alert_headline": "Minor vitamin interaction",
        "alert_body": (
            "This vitamin has mild interaction potential with your product. "
            "Consult your doctor for personalized guidance when combining."
        ),
    }
    result = validate_interaction_sub_rule(
        "RULE_X", "condition_rule", sub, "caution", strict=True,
    )
    # Caution rules may miss informational_note without strict failure.
    assert result.ok, result.errors


def test_contraindicated_requires_informational_note():
    sub = {
        "alert_headline": "Do not combine with MAOI antidepressants",
        "alert_body": (
            "5-HTP raises serotonin directly. If you take an MAOI, "
            "combining carries serotonin syndrome risk. Do not combine."
        ),
    }
    result = validate_interaction_sub_rule(
        "RULE_X", "drug_class_rule", sub, "contraindicated", strict=True,
    )
    assert not result.ok
    assert any("informational_note" in e for e in result.errors), result.errors


# ---------------------------------------------------------------------------
# medication_depletions per-entry validator (v5.2)
# ---------------------------------------------------------------------------


def _good_depletion_entry() -> dict:
    # Canonical v5.2.1 exemplar — matches Dr. Pham's clinical review
    # round 1. Passes the nocebo-safe validator rules (no numeric
    # stats, ≤2 symptom terms, ≤3 sentences).
    return {
        "id": "DEP_METFORMIN_VITAMINB12",
        "drug_ref": {"display_name": "Metformin"},
        "depleted_nutrient": {"standard_name": "Vitamin B12", "canonical_id": "vitamin_b12"},
        "severity": "significant",
        "alert_headline": "May lower vitamin B12 over time",
        "alert_body": (
            "With long-term use, metformin can reduce how well vitamin B12 "
            "is absorbed. Some people develop lower levels over years, "
            "which may show up as fatigue or tingling."
        ),
        "acknowledgement_note": (
            "Nice — you're taking B12, which aligns with guidance for "
            "long-term metformin use."
        ),
        "monitoring_tip_short": (
            "Consider checking B12 levels every 2-3 years; easy to review "
            "at a routine visit."
        ),
    }


def test_good_depletion_passes_strict():
    result = validate_depletion_entry(_good_depletion_entry(), strict=True)
    assert result.ok, f"expected clean pass, got {result.errors}"


def test_depleted_by_opener_fails():
    entry = _good_depletion_entry()
    entry["alert_headline"] = "Depleted by metformin — watch levels"
    result = validate_depletion_entry(entry, strict=True)
    assert not result.ok
    assert any("Depleted by" in e for e in result.errors), result.errors


def test_alert_body_without_onset_framing_fails():
    entry = _good_depletion_entry()
    # No "over time" / "long-term" / "years" / etc.
    entry["alert_body"] = (
        "Metformin lowers vitamin B12 absorption. Some people experience "
        "numbness or fatigue. Talk to your doctor."
    )
    result = validate_depletion_entry(entry, strict=True)
    assert not result.ok
    assert any("onset framing" in e for e in result.errors), result.errors


def test_acknowledgement_with_caution_verb_fails():
    entry = _good_depletion_entry()
    # Ack is shown to users who ARE covering — must not hedge.
    entry["acknowledgement_note"] = (
        "You're taking B12, which helps reduce the risk of deficiency from "
        "long-term metformin use."
    )
    result = validate_depletion_entry(entry, strict=True)
    assert not result.ok
    assert any("caution verb" in e for e in result.errors), result.errors


def test_monitoring_tip_without_action_verb_fails():
    entry = _good_depletion_entry()
    entry["monitoring_tip_short"] = (
        "B12 deficiency develops slowly and may go unnoticed for years."
    )
    result = validate_depletion_entry(entry, strict=True)
    assert not result.ok
    assert any("soft action verb" in e for e in result.errors), result.errors


def test_monitoring_tip_with_loud_verb_fails():
    entry = _good_depletion_entry()
    entry["monitoring_tip_short"] = (
        "Stop metformin immediately if you notice numbness in your hands."
    )
    result = validate_depletion_entry(entry, strict=True)
    assert not result.ok
    assert any("loud verb" in e for e in result.errors), result.errors


def test_adequacy_threshold_must_be_positive():
    entry = _good_depletion_entry()
    entry["adequacy_threshold_mcg"] = -10
    result = validate_depletion_entry(entry, strict=True)
    assert not result.ok
    assert any("positive number" in e for e in result.errors), result.errors


def test_adequacy_threshold_valid_number_passes():
    entry = _good_depletion_entry()
    entry["adequacy_threshold_mcg"] = 1000
    result = validate_depletion_entry(entry, strict=True)
    assert result.ok, result.errors


def test_depletion_authoring_mode_allows_missing():
    entry = {
        "id": "DEP_X",
        "drug_ref": {"display_name": "Drug"},
        "depleted_nutrient": {"standard_name": "Nutrient"},
    }
    result = validate_depletion_entry(entry, strict=False)
    assert result.ok, f"authoring mode should not fail: {result.errors}"
    assert any("alert_headline" in w for w in result.warnings)


def test_depletion_strict_mode_rejects_missing():
    entry = {
        "id": "DEP_X",
        "drug_ref": {"display_name": "Drug"},
        "depleted_nutrient": {"standard_name": "Nutrient"},
    }
    result = validate_depletion_entry(entry, strict=True)
    assert not result.ok


def test_depletion_screaming_headline_fails():
    entry = _good_depletion_entry()
    entry["alert_headline"] = "URGENT: check vitamin B12 levels now"
    result = validate_depletion_entry(entry, strict=True)
    assert not result.ok
    assert any("screaming" in e for e in result.errors), result.errors


# ---------------------------------------------------------------------------
# v5.2.1 nocebo rules (clinical review round 1, per Dr. Pham)
# ---------------------------------------------------------------------------


def test_numeric_stat_in_body_fails():
    # "Up to 30% of long-term users develop …" is true and sourced, but
    # in a 200-char mobile card it reads as "you're at significant
    # risk" — alarm-forward priming. Stats belong in clinical_impact.
    entry = _good_depletion_entry()
    entry["alert_body"] = (
        "Long-term metformin use can reduce B12 absorption. Up to 30% of "
        "long-term users develop low levels."
    )
    result = validate_depletion_entry(entry, strict=True)
    assert not result.ok
    assert any("numeric stat" in e for e in result.errors), result.errors


def test_numeric_ratio_in_body_fails():
    entry = _good_depletion_entry()
    entry["alert_body"] = (
        "With long-term use, metformin can lower B12 levels. About 1 in 3 "
        "long-term users develop deficiency over years."
    )
    result = validate_depletion_entry(entry, strict=True)
    assert not result.ok
    assert any("numeric stat" in e for e in result.errors), result.errors


def test_absolute_causal_claim_in_body_fails():
    entry = _good_depletion_entry()
    entry["alert_body"] = (
        "Long-term metformin use will cause B12 deficiency over time in "
        "most patients; absorption drops gradually."
    )
    result = validate_depletion_entry(entry, strict=True)
    assert not result.ok
    assert any("absolute causal claim" in e for e in result.errors), result.errors


def test_acute_framing_in_body_fails():
    entry = _good_depletion_entry()
    entry["alert_body"] = (
        "With regular use, metformin immediately reduces B12 over time. "
        "Some people develop lower levels."
    )
    result = validate_depletion_entry(entry, strict=True)
    assert not result.ok
    assert any("acute-tense framing" in e for e in result.errors), result.errors


def test_catastrophizing_in_body_warns_not_fails():
    entry = _good_depletion_entry()
    entry["alert_body"] = (
        "Long-term metformin use can lead to severe B12 depletion over "
        "time. Some people develop lower levels gradually."
    )
    result = validate_depletion_entry(entry, strict=True)
    # Catastrophizing is a WARN (style), not a hard FAIL — the other
    # absolute-claim rule ('lead to') catches it harder. Check that the
    # catastrophizing warning fires regardless.
    assert any("catastrophizing" in w for w in result.warnings), result.warnings


def test_symptom_list_over_two_warns():
    entry = _good_depletion_entry()
    entry["alert_body"] = (
        "With long-term use, levels drop gradually over years. Some people "
        "notice fatigue, tingling, weakness, and numbness."
    )
    result = validate_depletion_entry(entry, strict=True)
    # Should pass (still valid) but emit a nocebo warning.
    assert any("symptom terms" in w for w in result.warnings), result.warnings


def test_two_symptoms_is_ok():
    # Dr. Pham's canonical metformin entry names 2 symptoms — fine.
    entry = _good_depletion_entry()
    entry["alert_body"] = (
        "With long-term use, metformin can reduce how well vitamin B12 is "
        "absorbed. Some people develop lower levels over years, which may "
        "show up as fatigue or tingling."
    )
    result = validate_depletion_entry(entry, strict=True)
    assert result.ok, result.errors


def test_sentence_count_over_three_warns():
    entry = _good_depletion_entry()
    entry["alert_body"] = (
        "Long-term use can lower B12. Over years, levels drop. Some people "
        "notice it. Fatigue may show up."
    )
    result = validate_depletion_entry(entry, strict=True)
    assert any("sentences" in w for w in result.warnings), result.warnings


# ---------------------------------------------------------------------------
# food_sources_short rules (v5.2.1)
# ---------------------------------------------------------------------------


def test_good_food_sources_passes():
    entry = _good_depletion_entry()
    entry["food_sources_short"] = (
        "Food sources of magnesium include leafy greens, nuts, seeds, "
        "whole grains, and dark chocolate."
    )
    result = validate_depletion_entry(entry, strict=True)
    assert result.ok, result.errors


def test_food_sources_absorption_blocked_hint_passes():
    entry = _good_depletion_entry()
    entry["food_sources_short"] = (
        "Because metformin reduces B12 absorption, food sources may not "
        "be enough on their own — a supplement is often more reliable."
    )
    result = validate_depletion_entry(entry, strict=True)
    assert result.ok, result.errors


def test_food_sources_imperative_warns():
    entry = _good_depletion_entry()
    entry["food_sources_short"] = (
        "Eat more leafy greens, nuts, and whole grains to boost magnesium "
        "intake over time."
    )
    result = validate_depletion_entry(entry, strict=True)
    assert any("imperative framing" in w for w in result.warnings), result.warnings


def test_food_sources_banned_word_fails():
    entry = _good_depletion_entry()
    entry["food_sources_short"] = (
        "Food sources of B12 include meat and eggs; without them, you "
        "are at risk for deficiency over time."
    )
    result = validate_depletion_entry(entry, strict=True)
    assert not result.ok
    assert any("alarm word" in e for e in result.errors), result.errors


def test_food_sources_length_bounds():
    entry = _good_depletion_entry()
    entry["food_sources_short"] = "Leafy greens, nuts, seeds."  # too short
    result = validate_depletion_entry(entry, strict=True)
    assert not result.ok
    assert any("length" in e for e in result.errors), result.errors


def test_food_sources_optional():
    # Entry without food_sources_short should still validate strict.
    entry = _good_depletion_entry()
    entry.pop("food_sources_short", None)
    result = validate_depletion_entry(entry, strict=True)
    assert result.ok, result.errors


def test_both_threshold_fields_set_fails():
    entry = _good_depletion_entry()
    entry["adequacy_threshold_mcg"] = 500
    entry["adequacy_threshold_mg"] = 200
    result = validate_depletion_entry(entry, strict=True)
    assert not result.ok
    assert any("both adequacy_threshold" in e for e in result.errors), result.errors


# ---------------------------------------------------------------------------
# End-to-end: the shipped exemplar drafts must validate under strict mode
# ---------------------------------------------------------------------------


def test_banned_recalled_exemplars_pass_strict():
    path = SCRIPTS_DIR / "safety_copy_exemplars" / "banned_recalled_drafts.json"
    with path.open() as f:
        doc = json.load(f)
    for draft in doc["drafts"]:
        # Build a candidate entry from the draft for validation.
        entry = {
            "id": draft["_target"].lower(),
            "standard_name": draft["_target"].split("_", 1)[-1].replace("_", " ").title(),
            "ban_context": draft["ban_context"],
            "safety_warning": draft["safety_warning"],
            "safety_warning_one_liner": draft["safety_warning_one_liner"],
        }
        result = validate_banned_recalled_entry(entry, strict=True)
        assert result.ok, (
            f"exemplar {draft['_target']} failed strict validator: {result.errors}"
        )


def test_interaction_rules_exemplars_pass_strict():
    path = SCRIPTS_DIR / "safety_copy_exemplars" / "interaction_rules_drafts.json"
    with path.open() as f:
        doc = json.load(f)
    for draft in doc["drafts"]:
        sub = {
            "alert_headline": draft["alert_headline"],
            "alert_body": draft["alert_body"],
            "informational_note": draft.get("informational_note"),
        }
        result = validate_interaction_sub_rule(
            draft["rule_id"],
            draft["sub_rule_kind"],
            sub,
            draft["severity"],
            strict=True,
        )
        assert result.ok, (
            f"interaction exemplar {draft['_target']} failed: {result.errors}"
        )


# ---------------------------------------------------------------------------
# Real-file smoke: authoring mode must pass against the production file
# (every violation must be a warning, never an error, until strict release).
# ---------------------------------------------------------------------------


def test_production_banned_recalled_clean_in_authoring_mode():
    path = SCRIPTS_DIR / "data" / "banned_recalled_ingredients.json"
    with path.open() as f:
        doc = json.load(f)
    total_errors = []
    for entry in doc.get("ingredients", []):
        result = validate_banned_recalled_entry(entry, strict=False)
        total_errors.extend(result.errors)
    assert not total_errors, (
        f"production banned_recalled has {len(total_errors)} hard errors in "
        f"authoring mode — authoring transition should produce warnings only: "
        f"{total_errors[:10]}"
    )


def test_production_interaction_rules_clean_in_authoring_mode():
    path = SCRIPTS_DIR / "data" / "ingredient_interaction_rules.json"
    with path.open() as f:
        doc = json.load(f)
    total_errors = []
    for rule in doc.get("interaction_rules", []):
        result = validate_interaction_rule(rule, strict=False)
        total_errors.extend(result.errors)
    assert not total_errors, (
        f"production interaction_rules has {len(total_errors)} hard errors "
        f"in authoring mode: {total_errors[:10]}"
    )


def test_production_depletions_clean_in_authoring_mode():
    path = SCRIPTS_DIR / "data" / "medication_depletions.json"
    with path.open() as f:
        doc = json.load(f)
    total_errors = []
    for entry in doc.get("depletions", []):
        result = validate_depletion_entry(entry, strict=False)
        total_errors.extend(result.errors)
    assert not total_errors, (
        f"production medication_depletions has {len(total_errors)} hard "
        f"errors in authoring mode: {total_errors[:10]}"
    )


def test_depletion_exemplars_pass_strict():
    """All shipped exemplar depletion drafts must validate under strict mode."""
    path = SCRIPTS_DIR / "safety_copy_exemplars" / "depletion_drafts.json"
    if not path.exists():
        pytest.skip("depletion_drafts.json not yet present")
    with path.open() as f:
        doc = json.load(f)
    for draft in doc["drafts"]:
        entry = {
            "id": draft["_target"],
            "drug_ref": {"display_name": draft.get("drug_display_name", "")},
            "depleted_nutrient": {
                "standard_name": draft.get("nutrient_name", "")
            },
            "alert_headline": draft["alert_headline"],
            "alert_body": draft["alert_body"],
            "acknowledgement_note": draft["acknowledgement_note"],
            "monitoring_tip_short": draft["monitoring_tip_short"],
        }
        if "adequacy_threshold_mcg" in draft:
            entry["adequacy_threshold_mcg"] = draft["adequacy_threshold_mcg"]
        if "adequacy_threshold_mg" in draft:
            entry["adequacy_threshold_mg"] = draft["adequacy_threshold_mg"]
        result = validate_depletion_entry(entry, strict=True)
        assert result.ok, (
            f"depletion exemplar {draft['_target']} failed strict validator: "
            f"{result.errors}"
        )
