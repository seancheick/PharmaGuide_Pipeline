"""Dr Pham's clinical review of 2026-11-03, one decision per section.

Consumer copy is checked against the committed review file, so a reworded
sentence fails here even if someone also rewords the expected text.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from build_final_db import (
    _safety_warning_policy_projection,
    _validate_warning_display_mode_consistency,
)
from enrich_supplements_v3 import SupplementEnricherV3

REVIEW_DIR = ROOT / "audits" / "clinical_review_20261103"
REVIEW = (REVIEW_DIR / "DR_PHAM_REVIEW_20261103.md").read_text(encoding="utf-8")
RULES = {
    rule["id"]: rule
    for rule in json.loads(
        (ROOT / "data" / "ingredient_interaction_rules.json").read_text(encoding="utf-8")
    )["interaction_rules"]
}
NCCIH = "https://www.nccih.nih.gov/health/bitter-orange"
CANADA_NOTICE = (
    "https://www.canada.ca/en/health-canada/services/drugs-health-products/"
    "natural-non-prescription/legislation-guidelines/guidance-documents/notice-use-synephrine.html"
)


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _hits(enricher, canonical_id: str, db: str = "banned_recalled_ingredients", quantity=100, unit="mg"):
    row = {
        "canonical_id": canonical_id,
        "canonical_source_db": db,
        "name": canonical_id,
        "standard_name": canonical_id,
        "quantity": quantity,
        "unit": unit,
        "raw_source_path": "ingredientRows[0]",
    }
    profile = enricher._collect_interaction_profile(
        {"activeIngredients": [row], "ingredient_quality_data": {"ingredients": [row]}}
    )
    return {
        hit["condition_id"]: hit
        for alert in profile["ingredient_alerts"]
        for hit in alert["condition_hits"]
    }


# --- Bitter orange (sections 1-3) -------------------------------------------

ORANGE_WARNING = "Avoid bitter-orange supplements during pregnancy or breastfeeding."
ORANGE_EXPLANATION = (
    "Safety during pregnancy and breastfeeding has not been established. "
    "Bitter-orange supplements may contain synephrine, and the amount may be undisclosed "
    "or differ from the label. Choose an alternative and discuss supplement use with a "
    "healthcare professional."
)
ORANGE_RULES = ("RULE_BANNED_BITTER_ORANGE_HYPERTENSION", "RULE_BANNED_BITTER_ORANGE_PREGNANCY")


def test_expected_bitter_orange_copy_is_her_copy():
    assert f"Warning: {ORANGE_WARNING}" in REVIEW
    assert f"Explanation: {ORANGE_EXPLANATION}" in REVIEW


@pytest.mark.parametrize("rule_id", ORANGE_RULES)
def test_bitter_orange_life_stage_tiers_and_no_cutoff(rule_id):
    rule = RULES[rule_id]
    block = rule["pregnancy_lactation"]
    assert block["pregnancy_category"] == "avoid"
    assert block["lactation_category"] == "avoid"
    assert not rule["dose_thresholds"]
    assert block["materiality"] == "presence"


@pytest.mark.parametrize("rule_id", ORANGE_RULES)
def test_bitter_orange_review_is_attributed_to_her(rule_id):
    rule = RULES[rule_id]
    assert "Dr. Pham" in rule["review_owner"]
    assert "Codex" not in rule["review_owner"]
    assert rule["last_reviewed"] == "2026-11-03"


@pytest.mark.parametrize(
    "subject, condition",
    [
        ("RISK_BITTER_ORANGE", "pregnancy"),
        ("RISK_BITTER_ORANGE", "lactation"),
        ("BANNED_BITTER_ORANGE", "pregnancy"),
        ("BANNED_BITTER_ORANGE", "lactation"),
    ],
)
def test_bitter_orange_card_carries_her_words_at_every_route(enricher, subject, condition):
    hit = _hits(enricher, subject)[condition]
    assert hit["severity"] == "avoid"
    shown = f"{hit['alert_headline']} {hit['alert_body']}"
    assert ORANGE_WARNING in shown
    assert ORANGE_EXPLANATION in hit["alert_body"]
    assert "contains synephrine, a stimulant" not in shown


@pytest.mark.parametrize("subject", ["RISK_BITTER_ORANGE", "BANNED_BITTER_ORANGE"])
@pytest.mark.parametrize("amount", [None, 2, 3, 3.1, 4])
def test_bitter_orange_stays_avoid_at_any_declared_amount(enricher, subject, amount):
    hits = _hits(enricher, subject, quantity=amount)
    assert hits["pregnancy"]["severity"] == "avoid"
    assert hits["lactation"]["severity"] == "avoid"
    assert hits["pregnancy"].get("dose_threshold_evaluation") is None


@pytest.mark.parametrize("subject", ["RISK_BITTER_ORANGE", "BANNED_BITTER_ORANGE"])
def test_bitter_orange_cites_nccih_first_and_the_notice_only_as_archive(enricher, subject):
    hits = _hits(enricher, subject)
    for condition in ("pregnancy", "lactation"):
        assert hits[condition]["sources"][0] == NCCIH
        assert CANADA_NOTICE not in hits[condition]["sources"]
    note = RULES["RULE_BANNED_BITTER_ORANGE_PREGNANCY"]["notes"]
    assert note.startswith("Archived Health Canada guidance")
    assert CANADA_NOTICE in note


def test_hypertension_entries_of_the_hypertension_rule_did_not_move():
    rule = RULES["RULE_BANNED_BITTER_ORANGE_HYPERTENSION"]
    digest = lambda value: hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    assert digest(rule["condition_rules"]) == (
        "95548b6530c483ec761ff41408d385ed4bdd12b1c136d718a1e18cd07f008334"
    )
    assert digest(rule["drug_class_rules"]) == (
        "368708e929844e953a4e21ff7a2de1acf962c519619abba85287021a20506993"
    )


# --- Tansy (section 4 and question D) ---------------------------------------

TANSY_WARNING = "Do not use tansy supplements or tansy essential oil during pregnancy."
TANSY_EXPLANATION = (
    "Tansy essential oil can contain thujone, a neurotoxic compound associated with convulsions. "
    "The amount of thujone varies by preparation, and pregnancy safety has not been established. "
    "PharmaGuide classifies oral tansy preparations as contraindicated during pregnancy as a "
    "precaution because of their potential toxicity and reproductive-safety concerns."
)


def test_expected_tansy_copy_is_her_copy():
    assert f"Warning: {TANSY_WARNING}" in REVIEW
    assert f"Explanation: {TANSY_EXPLANATION}" in REVIEW


def test_tansy_keeps_severity_with_limited_evidence_and_her_words(enricher):
    hit = _hits(enricher, "BANNED_TANSY")["pregnancy"]
    assert hit["severity"] == "contraindicated"
    assert hit["evidence_level"] == "limited"
    assert hit["alert_headline"] == TANSY_WARNING
    assert hit["alert_body"] == TANSY_EXPLANATION
    assert hit["mechanism"] == TANSY_EXPLANATION
    assert hit["action"] == TANSY_WARNING


def test_tansy_cites_the_two_papers_she_named(enricher):
    hit = _hits(enricher, "BANNED_TANSY")["pregnancy"]
    assert hit["sources"] == [
        "https://pubmed.ncbi.nlm.nih.gov/33673548/",
        "https://pubmed.ncbi.nlm.nih.gov/10725394/",
    ]


def test_tansy_makes_no_miscarriage_claim_on_the_pregnancy_card(enricher):
    hit = _hits(enricher, "BANNED_TANSY")["pregnancy"]
    for field in ("alert_headline", "alert_body", "mechanism", "action", "informational_note"):
        assert "miscarriage" not in hit[field].lower()


def test_tansy_breastfeeding_tier_did_not_move(enricher):
    hit = _hits(enricher, "BANNED_TANSY")["lactation"]
    assert hit["severity"] == "avoid"
    assert TANSY_WARNING not in hit["alert_body"]


def test_tansy_review_is_attributed_to_her():
    rule = RULES["RULE_BANNED_TANSY_PREGNANCY"]
    assert "Dr. Pham" in rule["review_owner"]
    assert rule["last_reviewed"] == "2026-11-03"


# Sean's ruling on the ban card, which everyone sees: no pregnancy language.
# The wording is his, not Dr. Pham's. Her text stays on the gated pregnancy card.

TANSY_BAN_BODY = (
    "Tansy essential oil can contain thujone, a neurotoxic compound associated with seizures. "
    "Thujone exposure varies by preparation, and whole-plant products should not be assumed "
    "free of this risk."
)
TANSY_BAN_ONE_LINER = "Tansy may contain thujone, a neurotoxic compound linked to seizures."
BANNED = {
    entry["id"]: entry
    for entry in json.loads(
        (ROOT / "data" / "banned_recalled_ingredients.json").read_text(encoding="utf-8")
    )["ingredients"]
}


def _tansy_ban_warning(**overrides):
    entry = BANNED["BANNED_TANSY"]
    policy = _safety_warning_policy_projection("BANNED_TANSY", entry["status"], {})
    return {
        "type": "high_risk_ingredient",
        "display_mode_default": policy["display_mode_default"],
        "safety_warning": entry["safety_warning"],
        "safety_warning_one_liner": entry["safety_warning_one_liner"],
        "detail": entry["reason"],
        "title": f"High-risk ingredient: {entry['standard_name']}",
        **overrides,
    }


def test_tansy_ban_text_is_seans_text():
    entry = BANNED["BANNED_TANSY"]
    assert entry["safety_warning_one_liner"] == TANSY_BAN_ONE_LINER
    assert entry["safety_warning"] == TANSY_BAN_BODY
    assert entry["reason"] == TANSY_BAN_BODY
    assert "clinical_review" not in entry
    latest = entry["review"]["change_log"][-1]
    assert latest["date"] == "2026-11-03"
    assert "Sean" in latest["change"]
    assert "Pham" not in latest["change"]


def test_tansy_review_block_keeps_aprils_facts_and_dates_them():
    review = BANNED["BANNED_TANSY"]["review"]
    assert review["reviewed_by"] == "dr_pham_clinical_signoff"
    assert review["status"] == "validated"
    assert review["last_reviewed_at"] == "2026-04-26"
    assert review["notes"] == (
        "Consumer copy replaced 2026-11-03 per Sean; the 2026-04-26 review predates this text."
    )


@pytest.mark.parametrize(
    "claim", ["pregnan", "miscarriage", "abortifacient", "fatalit", "maternal death"]
)
@pytest.mark.parametrize("field", ["safety_warning_one_liner", "safety_warning", "reason"])
def test_tansy_ban_text_drops_the_removed_claims(field, claim):
    assert claim not in BANNED["BANNED_TANSY"][field].lower()


def test_tansy_ban_card_stays_critical_and_passes_the_real_guard():
    warning = _tansy_ban_warning()
    assert "display_mode_default" not in BANNED["BANNED_TANSY"]
    assert warning["display_mode_default"] == "critical"
    _validate_warning_display_mode_consistency([warning], "BANNED_TANSY")


def test_the_guard_refuses_her_pregnancy_warning_on_the_ban_card():
    warning = _tansy_ban_warning(safety_warning_one_liner=TANSY_WARNING)
    with pytest.raises(ValueError, match="during pregnancy"):
        _validate_warning_display_mode_consistency([warning], "BANNED_TANSY")


def test_tansy_ban_text_reaches_the_warning(enricher):
    hits = enricher._check_banned_substances([{"name": "Tansy", "standardName": "Tansy"}])["substances"]
    tansy = next(hit for hit in hits if hit["banned_id"] == "BANNED_TANSY")
    assert tansy["status"] == "high_risk"
    assert tansy["safety_warning_one_liner"] == TANSY_BAN_ONE_LINER
    assert tansy["safety_warning"] == TANSY_BAN_BODY
    assert tansy["reason"] == TANSY_BAN_BODY


def test_ban_ruling_leaves_the_gated_cards_and_shared_sentence(enricher):
    hits = _hits(enricher, "BANNED_TANSY")
    assert hits["pregnancy"]["alert_headline"] == TANSY_WARNING
    assert hits["pregnancy"]["alert_body"] == TANSY_EXPLANATION
    shared = (
        "This substance is banned, recalled, or high-risk and should not be used during "
        "pregnancy or breastfeeding under any circumstances."
    )
    assert hits["lactation"]["alert_body"] == shared
    for rule_id in (
        "RULE_BANNED_TANSY_PREGNANCY",
        "RULE_BANNED_PENNYROYAL_PREGNANCY",
        "RULE_BANNED_RED_YEAST_RICE_STATINS",
        "RULE_BANNED_ADD_HORDENINE",
    ):
        assert RULES[rule_id]["pregnancy_lactation"]["alert_body"] == shared


# --- Caffeine in pregnancy (question A) -------------------------------------

CAFFEINE_HEADLINE = "High caffeine intake during pregnancy"
CAFFEINE_REVIEWED_FIRST = "This supplement provides 200 mg or more of caffeine per serving."
CAFFEINE_FIRST = "This supplement provides 200 mg or more of caffeine a day."
CAFFEINE_REST = (
    "ACOG recommends keeping total daily caffeine intake below 200 mg during pregnancy, "
    "including caffeine from drinks, foods and supplements. Avoid this high-caffeine supplement "
    "during pregnancy unless your prenatal care professional advises otherwise."
)


def _caffeine(enricher, amount):
    return _hits(enricher, "caffeine", db="ingredient_quality_map", quantity=amount)


def test_expected_caffeine_copy_is_her_copy_with_the_recorded_change():
    assert CAFFEINE_HEADLINE in REVIEW
    assert f"{CAFFEINE_REVIEWED_FIRST} {CAFFEINE_REST}" in REVIEW
    note = (REVIEW_DIR / "CAFFEINE_WORDING_CHANGE.md").read_text(encoding="utf-8")
    assert CAFFEINE_REVIEWED_FIRST in note and CAFFEINE_FIRST in note


@pytest.mark.parametrize("amount", [200, 200.1, 400])
def test_caffeine_at_or_above_200_mg_is_avoid_with_her_copy(enricher, amount):
    hit = _caffeine(enricher, amount)["pregnancy"]
    assert hit["severity"] == "avoid"
    assert hit["alert_headline"] == CAFFEINE_HEADLINE
    assert hit["alert_body"] == f"{CAFFEINE_FIRST} {CAFFEINE_REST}"
    assert hit["dose_decision"]["consumer_disposition"] == "block"


@pytest.mark.parametrize("amount", [100, 199.9])
def test_caffeine_below_200_mg_keeps_the_monitor_tier_and_never_her_copy(enricher, amount):
    hit = _caffeine(enricher, amount)["pregnancy"]
    assert hit["severity"] == "monitor"
    assert hit["alert_headline"] != CAFFEINE_HEADLINE
    assert CAFFEINE_FIRST not in hit["alert_body"]


@pytest.mark.parametrize("amount", [199.9, 200, 200.1])
def test_the_pregnancy_threshold_leaves_breastfeeding_alone(enricher, amount):
    hit = _caffeine(enricher, amount)["lactation"]
    assert hit["severity"] == "caution"
    assert CAFFEINE_HEADLINE != hit["alert_headline"]


def test_caffeine_threshold_is_on_the_daily_amount():
    threshold = next(
        t for t in RULES["RULE_INGREDIENT_CAFFEINE"]["dose_thresholds"] if t["target_id"] == "pregnancy"
    )
    assert (threshold["basis"], threshold["comparator"], threshold["value"], threshold["unit"]) == (
        "per_day", ">=", 200, "mg",
    )
    assert threshold["severity_if_met"] == "avoid"


def test_caffeine_review_is_attributed_to_her():
    rule = RULES["RULE_INGREDIENT_CAFFEINE"]
    assert "Dr. Pham" in rule["review_owner"]
    assert rule["last_reviewed"] == "2026-11-03"


# --- Overlapping rules show one concern (implementation condition 5) --------


def _orange_card(rule_id: str, headline: str) -> dict:
    return {
        "type": "interaction",
        "severity": "avoid",
        "display_mode_default": "suppress",
        "source": "interaction_rules",
        "source_rule_id": rule_id,
        "ingredient_canonical_id": "BANNED_BITTER_ORANGE",
        "condition_id": "pregnancy",
        "alert_headline": headline,
        "alert_body": ORANGE_EXPLANATION,
        "sources": [NCCIH],
    }


def test_two_rules_on_one_product_show_one_concern_and_keep_both_rule_ids():
    from build_final_db import _dedup_warnings

    cards = _dedup_warnings([_orange_card(rule_id, ORANGE_WARNING) for rule_id in ORANGE_RULES])
    assert len(cards) == 1
    assert cards[0]["source_rule_ids"] == sorted(ORANGE_RULES)
    assert cards[0]["source_rule_id"] in ORANGE_RULES


def test_a_warning_from_one_rule_gains_no_extra_field():
    from build_final_db import _dedup_warnings

    cards = _dedup_warnings([_orange_card(ORANGE_RULES[0], ORANGE_WARNING)])
    assert "source_rule_ids" not in cards[0]


def test_the_merged_rule_ids_survive_the_schema_3_reference():
    from export_schema import _warning_rule_ref

    ref = _warning_rule_ref({**_orange_card(ORANGE_RULES[0], ORANGE_WARNING), "source_rule_ids": sorted(ORANGE_RULES)})
    assert ref["source_rule_ids"] == sorted(ORANGE_RULES)


# --- Vitamin A form (sections 5-6) ------------------------------------------

VITAMIN_A = "RULE_IQM_VITAMIN_A_PREGNANCY_DOSE"
UNSPECIFIED_A = "vitamin a (unspecified)"
RETINYL = "retinyl palmitate"
MIXED_CAROTENES = "beta-carotene from mixed carotenoids"
FORM_REVIEW_HEADLINE = "Vitamin A form needs review"
FORM_REVIEW_BODY = (
    "This product lists vitamin A without enough information to determine how much is "
    "preformed vitamin A. High intakes of preformed vitamin A can be harmful during pregnancy. "
    "Check the form and total intake with your pharmacist or prenatal care professional."
)


def _nutrient_hits(enricher, canonical_id, rule_id, quantity, unit, form, forms=None, **row):
    standard_name = {"vitamin_a": "Vitamin A", "vitamin_e": "Vitamin E"}[canonical_id]
    row = {
        "canonical_id": canonical_id,
        "canonical_source_db": "ingredient_quality_map",
        "name": standard_name,
        "standard_name": standard_name,
        "quantity": quantity,
        "unit": unit,
        "raw_source_path": "ingredientRows[0]",
        "form_id": form,
        "matched_form": form,
        "matched_forms": [{"form_key": key} for key in forms or []],
        **row,
    }
    profile = enricher._collect_interaction_profile(
        {"activeIngredients": [row], "ingredient_quality_data": {"ingredients": [row]}}
    )
    return {
        hit["condition_id"]: hit
        for alert in profile["ingredient_alerts"]
        if alert["rule_id"] == rule_id
        for hit in alert["condition_hits"]
    }


def _vitamin_a(enricher, quantity, unit, form, forms=None, **row):
    return _nutrient_hits(enricher, "vitamin_a", VITAMIN_A, quantity, unit, form, forms, **row)


def _outcome(hit):
    decision = hit["dose_threshold_evaluation"]
    return hit["severity"], decision["evaluation_status"], decision["consumer_disposition"]


def test_form_review_note_is_her_text():
    normalized = " ".join(REVIEW.split())
    assert FORM_REVIEW_HEADLINE in normalized
    assert FORM_REVIEW_BODY in normalized


@pytest.mark.parametrize("target", ["pregnancy", "ttc"])
def test_pregnancy_and_trying_to_conceive_exclude_the_same_carotenoids(target):
    rows = [
        row for row in RULES[VITAMIN_A]["dose_thresholds"] if row["target_id"] == target
    ]
    assert rows
    for row in rows:
        assert set(row["profile_gate"]["excludes"]["nutrient_forms_any"]) == {
            "beta_carotene",
            "mixed_carotenoids",
        }


@pytest.mark.parametrize(
    "form",
    [
        "beta-carotene synthetic",
        MIXED_CAROTENES,
        "alpha-carotene (provitamin A activity)",
        "beta-cryptoxanthin (provitamin A activity)",
    ],
)
def test_carotenoid_only_rows_never_reach_the_preformed_limit(enricher, form):
    assert _vitamin_a(enricher, 25000, "IU", form) == {}


@pytest.mark.parametrize(
    "quantity, unit",
    [(12000, "IU"), (3600, "mcg"), (3600, "mcg RAE"), (10, "%"), (None, "")],
)
@pytest.mark.parametrize("target", ["pregnancy", "ttc"])
def test_undisclosed_form_shows_her_note_and_never_a_confirmed_excess(
    enricher, quantity, unit, target
):
    hit = _vitamin_a(enricher, quantity, unit, UNSPECIFIED_A)[target]
    severity, status, disposition = _outcome(hit)
    assert severity == "caution"
    assert status in {"form_unknown", "amount_unknown"}
    assert disposition == "review"
    assert hit["alert_headline"] == FORM_REVIEW_HEADLINE
    assert hit["alert_body"] == FORM_REVIEW_BODY


@pytest.mark.parametrize("target", ["pregnancy", "ttc"])
def test_undisclosed_form_within_the_limit_even_if_all_preformed_has_no_card(enricher, target):
    _, status, disposition = _outcome(_vitamin_a(enricher, 5000, "IU", UNSPECIFIED_A)[target])
    assert (status, disposition) == ("below_threshold", "suppress")


@pytest.mark.parametrize("quantity, unit", [(25000, "IU"), (4000, "mcg RAE")])
@pytest.mark.parametrize("target", ["pregnancy", "ttc"])
def test_mixed_row_with_no_declared_share_is_a_review_not_a_confirmed_excess(
    enricher, quantity, unit, target
):
    hit = _vitamin_a(
        enricher, quantity, unit, MIXED_CAROTENES, forms=[MIXED_CAROTENES, "retinyl acetate"]
    )[target]
    assert _outcome(hit)[1:] == ("form_unknown", "review")
    assert hit["severity"] == "caution"
    assert hit["alert_headline"] == FORM_REVIEW_HEADLINE


def test_mixed_row_within_the_limit_even_if_all_preformed_has_no_card(enricher):
    hit = _vitamin_a(
        enricher, 1500, "mcg RAE", MIXED_CAROTENES, forms=[MIXED_CAROTENES, "retinyl acetate"]
    )["pregnancy"]
    assert _outcome(hit)[1:] == ("below_threshold", "suppress")


# --- Breastfeeding (section C) ----------------------------------------------

VITAMIN_E = "RULE_IQM_VITAMIN_E_PREGNANCY_EXCESS"
ALPHA_TOCOPHEROL = "d-alpha-tocopherol"
OVER_LIMIT_HEADLINE = "Breastfeeding: avoid use"


def _vitamin_e(enricher, quantity, unit="mg", form=ALPHA_TOCOPHEROL, forms=None, **row):
    return _nutrient_hits(enricher, "vitamin_e", VITAMIN_E, quantity, unit, form, forms, **row)


def _at_age(hit, bracket="19+"):
    """What a person of this age is shown, read the way the device reads it."""
    decision = hit["dose_threshold_evaluation"]
    outcome = (decision.get("age_outcomes") or {}).get(bracket)
    if outcome is None:
        return hit["severity"], decision["evaluation_status"], decision["consumer_disposition"]
    return outcome["clinical_severity"], outcome["evaluation_status"], outcome["consumer_disposition"]


@pytest.mark.parametrize(
    "hits",
    [
        lambda enricher: _vitamin_a(enricher, 12000, "IU", RETINYL),
        lambda enricher: _vitamin_e(enricher, 1500),
    ],
)
def test_confirmed_above_the_limit_while_breastfeeding_reads_avoid(enricher, hits):
    hit = hits(enricher)["lactation"]
    assert _outcome(hit) == ("avoid", "above_threshold", "block")
    assert hit["alert_headline"] == OVER_LIMIT_HEADLINE
    assert hit["action"] == "Avoid use during breastfeeding."
    assert hit["profile_gate"]["requires"]["profile_flags_any"] == ["breastfeeding"]


def test_vitamin_a_is_never_contraindicated_while_breastfeeding():
    rows = [
        row
        for row in RULES[VITAMIN_A]["dose_thresholds"]
        if row["target_id"] == "lactation"
    ]
    assert rows and {row["severity_if_met"] for row in rows} == {"avoid"}


@pytest.mark.parametrize(
    "hits",
    [
        lambda enricher: _vitamin_a(enricher, 2000, "IU", RETINYL),
        lambda enricher: _vitamin_e(enricher, 100),
    ],
)
def test_within_the_limit_while_breastfeeding_has_no_over_limit_warning(enricher, hits):
    assert _outcome(hits(enricher)["lactation"])[1:] == ("below_threshold", "suppress")


@pytest.mark.parametrize(
    "hits",
    [
        lambda enricher: _vitamin_a(enricher, 12000, "IU", UNSPECIFIED_A),
        lambda enricher: _vitamin_a(enricher, None, "", UNSPECIFIED_A),
        lambda enricher: _vitamin_e(enricher, None, ""),
        lambda enricher: _vitamin_e(enricher, 1150, "IU", form="vitamin e (unspecified)"),
    ],
)
def test_unresolved_form_or_amount_while_breastfeeding_reads_review(enricher, hits):
    hit = hits(enricher)["lactation"]
    assert hit["severity"] == "monitor"
    assert hit["dose_threshold_evaluation"]["evaluation_status"] in {
        "form_unknown",
        "amount_unknown",
    }
    assert hit["dose_threshold_evaluation"]["consumer_disposition"] == "review"
    assert hit["alert_headline"] != OVER_LIMIT_HEADLINE


def test_carotenoids_stay_out_of_the_breastfeeding_limit(enricher):
    assert _vitamin_a(enricher, 25000, "IU", MIXED_CAROTENES) == {}


def test_one_breastfeeding_card_per_rule(enricher):
    profile_hits = [
        hit
        for hit in _vitamin_e(enricher, 1500).values()
        if hit["condition_id"] == "lactation"
    ]
    assert len(profile_hits) == 1


def test_bleeding_and_medication_rules_keep_running_within_the_limit(enricher):
    row = {
        "canonical_id": "vitamin_e",
        "canonical_source_db": "ingredient_quality_map",
        "name": "Vitamin E",
        "standard_name": "Vitamin E",
        "quantity": 100,
        "unit": "mg",
        "raw_source_path": "ingredientRows[0]",
        "form_id": ALPHA_TOCOPHEROL,
        "matched_form": ALPHA_TOCOPHEROL,
    }
    profile = enricher._collect_interaction_profile(
        {"activeIngredients": [row], "ingredient_quality_data": {"ingredients": [row]}}
    )
    alert = next(a for a in profile["ingredient_alerts"] if a["rule_id"] == VITAMIN_E)
    assert {"bleeding_disorders", "surgery_scheduled", "lactation"} <= {
        hit["condition_id"] for hit in alert["condition_hits"]
    }
    assert "anticoagulants" in {hit["drug_class_id"] for hit in alert["drug_class_hits"]}


# --- Vitamin E label table (section 7) --------------------------------------

@pytest.mark.parametrize(
    "quantity, unit, form, expected",
    [
        (1500, "mg", ALPHA_TOCOPHEROL, ("avoid", "above_threshold", "block")),
        (1500, "IU", "d-alpha-tocopherol", ("avoid", "above_threshold", "block")),
        (1400, "IU", "d-alpha-tocopherol", ("monitor", "below_threshold", "suppress")),
        (1200, "IU", "dl-alpha-tocopherol", ("avoid", "above_threshold", "block")),
        (1100, "IU", "dl-alpha-tocopherol", ("monitor", "below_threshold", "suppress")),
    ],
)
def test_a_known_preparation_converts_and_applies_the_adult_limit(enricher, quantity, unit, form, expected):
    assert _at_age(_vitamin_e(enricher, quantity, unit, form=form)["pregnancy"]) == expected


@pytest.mark.parametrize(
    "name, quantity, unit, form",
    [
        ("Vitamin E", 1200, "IU", "vitamin e (unspecified)"),
        ("Mixed Tocopherols", 1500, "mg", "mixed tocopherols"),
        ("Tocotrienols", 1500, "mg", "tocotrienols"),
    ],
)
def test_form_that_moves_the_answer_is_a_review_not_a_confirmed_excess(enricher, name, quantity, unit, form):
    hit = _vitamin_e(enricher, quantity, unit, form=form, name=name)["pregnancy"]
    assert _at_age(hit) == ("monitor", "form_unknown", "review")


def test_a_routine_amount_has_no_excess_warning(enricher):
    assert _at_age(_vitamin_e(enricher, 100)["pregnancy"]) == ("monitor", "below_threshold", "suppress")


# --- Age (section B) --------------------------------------------------------

TEEN = "14-18"
ADULT = "19+"


def _age_outcomes(hit):
    return hit["dose_threshold_evaluation"].get("age_outcomes")


def _both_read(hit, status, disposition):
    assert _age_outcomes(hit) is None, "age does not change this amount"
    assert _outcome(hit)[1:] == (status, disposition)


def _only_the_teen_limit_is_crossed(hit, teen_severity, adult_severity):
    decision = hit["dose_threshold_evaluation"]
    assert decision["evaluation_status"] == "age_dependent"
    assert decision["consumer_disposition"] == "review"
    assert decision["matched_threshold"] is False
    # Unknown age: neither a clearance nor an adult excess.
    assert hit["severity"] == adult_severity
    assert _at_age(hit, TEEN) == (teen_severity, "above_threshold", "block")
    assert _at_age(hit, ADULT) == (adult_severity, "below_threshold", "suppress")


VITAMIN_A_TARGETS = [
    ("pregnancy", "contraindicated", "caution"),
    ("ttc", "avoid", "caution"),
    ("lactation", "avoid", "monitor"),
]
VITAMIN_E_TARGETS = [("pregnancy", "avoid", "monitor"), ("lactation", "avoid", "monitor")]


@pytest.mark.parametrize("target, over, under", VITAMIN_A_TARGETS)
@pytest.mark.parametrize(
    "quantity, unit",
    [(2799, "mcg RAE"), (2800, "mcg RAE"), (9333, "IU"), (2800, "mcg")],
)
def test_vitamin_a_at_or_below_the_teen_limit_reads_within_for_everyone(enricher, target, over, under, quantity, unit):
    _both_read(_vitamin_a(enricher, quantity, unit, RETINYL)[target], "below_threshold", "suppress")


@pytest.mark.parametrize("target, over, under", VITAMIN_A_TARGETS)
@pytest.mark.parametrize(
    "quantity, unit",
    [(2801, "mcg RAE"), (9334, "IU"), (2999, "mcg RAE"), (3000, "mcg RAE"), (9999, "IU"), (10000, "IU")],
)
def test_vitamin_a_between_the_limits_depends_on_age(enricher, target, over, under, quantity, unit):
    _only_the_teen_limit_is_crossed(_vitamin_a(enricher, quantity, unit, RETINYL)[target], over, under)


@pytest.mark.parametrize("target, over, under", VITAMIN_A_TARGETS)
@pytest.mark.parametrize("quantity, unit", [(3001, "mcg RAE"), (10001, "IU")])
def test_vitamin_a_above_the_adult_limit_is_over_for_everyone(enricher, target, over, under, quantity, unit):
    hit = _vitamin_a(enricher, quantity, unit, RETINYL)[target]
    _both_read(hit, "above_threshold", "block")
    assert hit["severity"] == over


@pytest.mark.parametrize("target, over, under", VITAMIN_E_TARGETS)
@pytest.mark.parametrize("quantity", [799, 800])
def test_vitamin_e_at_or_below_the_teen_limit_reads_within_for_everyone(enricher, target, over, under, quantity):
    _both_read(_vitamin_e(enricher, quantity)[target], "below_threshold", "suppress")


@pytest.mark.parametrize("target, over, under", VITAMIN_E_TARGETS)
@pytest.mark.parametrize("quantity", [801, 999, 1000])
def test_vitamin_e_between_the_limits_depends_on_age(enricher, target, over, under, quantity):
    _only_the_teen_limit_is_crossed(_vitamin_e(enricher, quantity)[target], over, under)


@pytest.mark.parametrize("target, over, under", VITAMIN_E_TARGETS)
def test_vitamin_e_above_the_adult_limit_is_over_for_everyone(enricher, target, over, under):
    hit = _vitamin_e(enricher, 1001)[target]
    _both_read(hit, "above_threshold", "block")
    assert hit["severity"] == over


@pytest.mark.parametrize("target", ["pregnancy", "lactation"])
def test_an_upper_bound_above_only_the_teen_limit_is_a_teen_review(enricher, target):
    """E2: 670 to 900 mg is no exceedance for an adult and a possible one for a teenager."""
    hit = _vitamin_e(enricher, 670, quantity_upper=900)[target]
    assert hit["dose_threshold_evaluation"]["evaluation_status"] == "age_dependent"
    assert _at_age(hit, ADULT)[1:] == ("below_threshold", "suppress")
    assert _at_age(hit, TEEN)[1:] == ("form_unknown", "review")


@pytest.mark.parametrize(
    "hits",
    [
        lambda enricher: _vitamin_a(enricher, None, "", UNSPECIFIED_A),
        lambda enricher: _vitamin_e(enricher, None, ""),
    ],
)
def test_an_amount_no_limit_can_read_does_not_depend_on_age(enricher, hits):
    assert _age_outcomes(hits(enricher)["pregnancy"]) is None


def test_undisclosed_form_above_both_limits_keeps_her_note_at_every_age(enricher):
    hit = _vitamin_a(enricher, 12000, "IU", UNSPECIFIED_A)["pregnancy"]
    assert _age_outcomes(hit) is None
    assert hit["alert_headline"] == FORM_REVIEW_HEADLINE


def test_undisclosed_form_above_only_the_teen_limit_is_her_note_for_a_teen(enricher):
    hit = _vitamin_a(enricher, 9500, "IU", UNSPECIFIED_A)["pregnancy"]
    assert _at_age(hit, ADULT)[1:] == ("below_threshold", "suppress")
    teen = _age_outcomes(hit)[TEEN]
    assert teen["evaluation_status"] == "form_unknown"
    assert teen["consumer_disposition"] == "review"
    assert teen["alert_headline"] == FORM_REVIEW_HEADLINE
    assert teen["alert_body"] == FORM_REVIEW_BODY


def test_each_age_outcome_carries_the_whole_card_it_shows(enricher):
    hit = _vitamin_e(enricher, 900)["lactation"]
    teen, adult = _age_outcomes(hit)[TEEN], _age_outcomes(hit)[ADULT]
    assert teen["alert_headline"] == OVER_LIMIT_HEADLINE
    assert teen["action"] == "Avoid use during breastfeeding."
    assert adult["alert_headline"] == "Breastfeeding: monitoring is advised"
    assert "matched_copy" not in teen


def test_age_outcomes_survive_into_the_shipped_decision(enricher):
    from build_final_db import compact_dose_decision

    hit = _vitamin_e(enricher, 900)["pregnancy"]
    shipped = compact_dose_decision(hit["dose_decision"])
    assert shipped["evaluation_status"] == "age_dependent"
    assert shipped["age_outcomes"][TEEN]["clinical_severity"] == "avoid"
    assert shipped["age_outcomes"][ADULT]["consumer_disposition"] == "suppress"
    assert "age_outcomes" not in compact_dose_decision(
        _vitamin_e(enricher, 100)["pregnancy"]["dose_decision"]
    )


def test_a_failed_teen_conversion_still_blocks_release(enricher):
    thresholds = [
        {"scope": "condition", "target_id": "pregnancy", "comparator": ">", "value": 10, "unit": "iu",
         "severity_if_met": "avoid", "severity_if_not_met": "monitor"},
        {"scope": "condition", "target_id": "pregnancy", "comparator": ">", "value": 5, "unit": "mg",
         "severity_if_met": "avoid", "severity_if_not_met": "monitor", "age_brackets": [TEEN]},
    ]
    _, decision = enricher._evaluate_dose_thresholds_for_target(
        thresholds, "condition", "pregnancy",
        {"name": "x", "standard_name": "x", "quantity": 1, "unit": "IU"}, 1.0, "monitor",
    )
    assert decision["release_blocking"] is True


def test_the_age_brackets_are_the_ones_the_app_stores():
    brackets = {
        bracket
        for rule_id in (VITAMIN_A, VITAMIN_E)
        for row in RULES[rule_id]["dose_thresholds"]
        for bracket in row.get("age_brackets") or []
    }
    assert brackets == {TEEN}


def test_a_new_age_row_never_moves_the_gate_key_of_an_older_row():
    for rule_id in (VITAMIN_A, VITAMIN_E):
        rows = RULES[rule_id]["dose_thresholds"]
        seen_age_row = False
        for row in rows:
            seen_age_row = seen_age_row or bool(row.get("age_brackets"))
            assert not seen_age_row or row.get("age_brackets"), "append age rows at the end"


# --- E1: 249741 caffeine ----------------------------------------------------

@pytest.fixture(scope="module")
def caffeine_label_249741(enricher):
    from enhanced_normalizer import EnhancedDSLDNormalizer

    raw = json.loads(
        (ROOT / "tests" / "fixtures" / "dose_lineage_249741_raw.json").read_text(encoding="utf-8")
    )
    return enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))[0]


def _caffeine_row(product):
    [row] = [
        row
        for row in product["rda_ul_data"]["analyzed_ingredients"]
        if row.get("canonical_id") == "caffeine"
    ]
    return row


def test_the_compound_counts_as_its_estimated_caffeine_not_its_mass(caffeine_label_249741):
    exposure = _caffeine_row(caffeine_label_249741)["safety_exposure"]
    assert exposure["per_day"] == 180.0
    assert exposure["low_per_day"] == 180.0
    assert exposure["high_per_day"] == pytest.approx(202.3, abs=0.05)


def test_the_estimate_is_within_her_stated_composition():
    from enrich_supplements_v3 import DICAFFEINE_MALATE_CAFFEINE_FRACTION as fraction

    assert 22.2 <= 30 * fraction <= 22.5


def test_180_confirmed_with_an_estimate_above_200_is_never_a_proven_crossing(caffeine_label_249741):
    hits = [
        hit
        for alert in caffeine_label_249741["interaction_profile"]["ingredient_alerts"]
        if alert["rule_id"] == "RULE_INGREDIENT_CAFFEINE"
        for hit in alert["condition_hits"]
        if hit["condition_id"] == "pregnancy"
    ]
    assert hits
    for hit in hits:
        assert hit["dose_threshold_evaluation"]["evaluation_status"] == "form_unknown"


def test_another_caffeine_blend_header_keeps_its_whole_mass_as_the_upper_bound(enricher):
    rows = [
        {"name": "Caffeine Anhydrous", "canonical_id": "caffeine", "quantity": 180.0, "unit": "mg",
         "raw_source_path": "ingredientRows[0]"},
        {"name": "Energy Blend", "canonical_id": "caffeine", "quantity": 30.0, "unit": "mg",
         "raw_source_path": "ingredientRows[1]", "skip_reason": "blend_header_total_weight_only"},
    ]
    dose = enricher._distinct_caffeine_dose({}, rows)
    assert (dose["quantity"], dose["quantity_upper"]) == (180.0, 210.0)
    assert "compound_share_estimated" not in dose
