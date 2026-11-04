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

REVIEW = (
    ROOT / "audits" / "clinical_review_20261103" / "DR_PHAM_REVIEW_20261103.md"
).read_text(encoding="utf-8")
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
