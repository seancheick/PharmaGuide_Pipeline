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
