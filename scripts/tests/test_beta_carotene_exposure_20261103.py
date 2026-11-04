"""The lung-cancer rules judge beta-carotene, never a vitamin A activity figure.

RAE is activity, not mass. Every amount here is beta-carotene mass at the converter's
supplemental factor, which is how the rule's thresholds are written: 15 mg is 7,500 mcg
RAE and 20 mg is 10,000. A mixture's mass is only a maximum, and a mixture's RAE or IU
figure is neither a confirmed amount nor a maximum.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from build_final_db import build_detail_blob
from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3
from score_supplements_v4 import score_product_v4

FIXTURES = Path(__file__).parent / "fixtures"
DATA = Path(__file__).parent.parent / "data"
FACTOR = json.loads((DATA / "unit_conversions.json").read_text())["vitamin_conversions"][
    "vitamin_a_beta_carotene_supplement"
]["conversions"]["mcg_beta_carotene_to_mcg_rae"]


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _raw(dsld_id):
    return json.loads((FIXTURES / f"dose_lineage_{dsld_id}_raw.json").read_text())


def _enrich(enricher, raw):
    product, _ = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    return product


def _label(confirmed_mcg_rae=None, mixture_mcg=None):
    """228355: Vitamin A from beta-carotene alone, beside a Mixed Carotenoids mass row."""
    raw = _raw("228355")
    declared, mixture = raw["ingredientRows"][0], raw["ingredientRows"][40]
    assert (declared["name"], mixture["name"]) == ("Vitamin A", "Mixed Carotenoids")
    rows = []
    if confirmed_mcg_rae is not None:
        declared["quantity"][0].update(quantity=confirmed_mcg_rae, unit="mcg RAE")
        rows.append(declared)
    if mixture_mcg is not None:
        mixture["quantity"][0].update(quantity=mixture_mcg, unit="mcg")
        rows.append(mixture)
    raw["ingredientRows"] = rows
    return raw


def _decisions(product, condition="current_smoker"):
    return [
        hit.get("dose_threshold_evaluation") or hit.get("dose_decision")
        for alert in product["interaction_profile"]["ingredient_alerts"]
        if "LUNG_CANCER" in str(alert.get("rule_id"))
        for hit in alert.get("condition_hits") or []
        if hit.get("condition_id") == condition
    ]


def _one_decision(product):
    [status] = {d["evaluation_status"] for d in _decisions(product)}
    return status, _decisions(product)[0]


@pytest.mark.parametrize(
    ("dsld_id", "vitamin_a_rae"),
    [("293269", 700.0), ("328639", 900.0), ("328127", 900.0)],
)
def test_a_mixture_vitamin_a_figure_is_no_beta_carotene_amount(enricher, dsld_id, vitamin_a_rae):
    product = _enrich(enricher, _raw(dsld_id))
    status, decision = _one_decision(product)
    assert status == "amount_unknown"
    assert decision["dose_evaluation"] is None
    assert decision["consumer_disposition"] == "suppress"
    # The vitamin A figure itself stays what the label prints.
    [row] = [
        r for r in product["rda_ul_data"]["analyzed_ingredients"]
        if r.get("ingredient") == "Vitamin A"
    ]
    assert row["safety_exposure"]["per_day"] == pytest.approx(vitamin_a_rae)
    # A concern that needs no amount stays.
    assert any(
        hit["condition_id"] == "pregnancy"
        for alert in product["interaction_profile"]["ingredient_alerts"]
        if "LUNG_CANCER" in str(alert.get("rule_id"))
        for hit in alert["condition_hits"]
    )


@pytest.mark.parametrize("dsld_id", ["293269", "328639", "328127"])
@pytest.mark.parametrize("condition", ["current_smoker", "former_smoker", "asbestos_exposure"])
def test_a_vitamin_a_figure_raises_no_concern(enricher, dsld_id, condition):
    """FitScore reads this summary: at caution it tells a smoker to use caution from a multi."""
    product = _enrich(enricher, _raw(dsld_id))
    summary = product["interaction_profile"]["condition_summary"][condition]
    assert summary["highest_severity"] == "informational"
    assert {d["evaluation_status"] for d in _decisions(product, condition)} == {"amount_unknown"}


def test_a_declaration_from_beta_carotene_alone_keeps_its_conversion(enricher):
    status, decision = _one_decision(_enrich(enricher, _raw("178431")))
    assert status == "above_threshold"
    assert decision["dose_evaluation"]["converted_amount"] == pytest.approx(7500.0)
    assert decision["consumer_disposition"] == "review"


@pytest.mark.parametrize(
    ("mcg_rae", "status", "disposition"),
    [(7499, "below_threshold", "suppress"), (7500, "above_threshold", "review")],
)
def test_confirmed_beta_carotene_meets_the_rule_at_its_line(enricher, mcg_rae, status, disposition):
    found, decision = _one_decision(_enrich(enricher, _label(mcg_rae)))
    assert found == status
    assert decision["dose_evaluation"]["converted_amount"] == pytest.approx(mcg_rae)
    assert decision["consumer_disposition"] == disposition


def test_mass_reaches_the_rule_at_the_converter_factor(enricher):
    assert FACTOR == 0.5
    product = _enrich(enricher, _label(mixture_mcg=15000))
    [mixture] = product["rda_ul_data"]["analyzed_ingredients"]
    assert mixture["safety_exposure"]["high_per_day"] == pytest.approx(15000 * FACTOR)


def test_a_small_mixture_beside_a_declaration_stays_hidden(enricher):
    product = _enrich(enricher, _raw("228355"))
    decisions = _decisions(product)
    assert {d["evaluation_status"] for d in decisions} == {"below_threshold"}
    assert {d["dose_evaluation"]["converted_amount"] for d in decisions} == {4500.0}
    [mixture] = [
        r for r in product["rda_ul_data"]["analyzed_ingredients"]
        if r.get("ingredient") == "Mixed Carotenoids"
    ]
    assert mixture["safety_exposure"]["low_per_day"] == 0.0
    assert mixture["safety_exposure"]["high_per_day"] == pytest.approx(86.0)


def test_a_maximum_crossing_the_line_could_not_be_evaluated(enricher):
    """Sean's example: 10 mg confirmed + 8 mg mixture is 10-18 mg, across the 15 mg line."""
    product = _enrich(enricher, _label(5000, 8000))
    status, decision = _one_decision(product)
    assert status == "form_unknown"
    # No card: the rule's own text states an amount. The reader reports an incomplete check.
    assert decision["consumer_disposition"] == "suppress"
    assert decision["release_blocking"] is False
    assert decision["dose_evaluation"]["converted_amount"] == pytest.approx(5000.0)
    hits = [
        hit for alert in product["interaction_profile"]["ingredient_alerts"]
        if "LUNG_CANCER" in str(alert.get("rule_id"))
        for hit in alert["condition_hits"] if hit["condition_id"] == "current_smoker"
    ]
    assert {hit["severity"] for hit in hits} == {"caution"}
    blob = build_detail_blob(product, score_product_v4(product))
    [card] = [w for w in blob["warnings"] if w.get("condition_ids") == ["current_smoker"]
              and w.get("ingredient_canonical_id") == "beta_carotene"]
    assert card["dose_decision"]["consumer_disposition"] == "suppress"
    # The confirmed part stays readable for a stack, on the same unresolved card.
    assert card["dose_decision"]["evaluation_status"] == "form_unknown"
    assert card["dose_decision"]["evaluated_daily_amount"] == pytest.approx(5000.0)
    # The state belongs to the affected reader: the label still scores, Evidence intact.
    scored = score_product_v4(product)
    alone = score_product_v4(_enrich(enricher, _label(5000, 1000)))
    assert scored["quality_score_v4_100"] is not None
    assert scored["quality_pillars_v4"]["evidence"]["score"] == alone["quality_pillars_v4"]["evidence"]["score"]


def test_an_unresolved_maximum_is_for_the_affected_reader_only(enricher):
    product = _enrich(enricher, _label(mixture_mcg=25000))
    dose_hits = [
        hit for alert in product["interaction_profile"]["ingredient_alerts"]
        if "LUNG_CANCER" in str(alert.get("rule_id")) for hit in alert.get("dose_hits") or []
    ]
    status, decision = _one_decision(product)
    assert (status, decision["dose_evaluation"]) == ("form_unknown", None)
    assert dose_hits and all(
        (hit.get("dose_threshold_evaluation") or hit).get("consumer_disposition") == "suppress"
        for hit in dose_hits
    )


def test_a_maximum_under_the_line_rules_an_excess_out(enricher):
    product = _enrich(enricher, _label(mixture_mcg=10000))
    status, decision = _one_decision(product)
    assert status == "below_threshold"
    assert decision["consumer_disposition"] == "suppress"
    assert decision["dose_evaluation"]["converted_amount"] == 0.0
    blob = build_detail_blob(product, score_product_v4(product))
    [card] = [w for w in blob["warnings"] if w.get("condition_ids") == ["current_smoker"]
              and w.get("ingredient_canonical_id") == "beta_carotene"]
    assert card["dose_decision"]["evaluated_daily_amount"] == 0.0


def test_confirmed_mass_at_the_line_is_confirmed_whatever_the_mixture_adds(enricher):
    product = _enrich(enricher, _label(7500, 8000))
    status, decision = _one_decision(product)
    assert status == "above_threshold"
    assert decision["dose_evaluation"]["converted_amount"] == pytest.approx(7500.0)


def test_no_usable_amount_gives_no_number(enricher):
    raw = _label(1000)
    raw["ingredientRows"][0]["quantity"][0].update(quantity=0, unit="NP")
    assert all(
        decision is None or decision["dose_evaluation"] is None
        for decision in _decisions(_enrich(enricher, raw))
    )


def _stack_rows(product):
    blob = build_detail_blob(product, score_product_v4(product))
    amounts = [
        (warning.get("dose_decision") or {}).get("evaluated_daily_amount")
        for warning in blob["warnings"]
        if warning.get("ingredient_canonical_id") == "beta_carotene"
        and "current_smoker" in (warning.get("condition_ids") or [])
    ]
    ranges = [
        row["safety_exposure"]
        for row in blob["ingredients"]
        if "low_per_day" in (row.get("safety_exposure") or {})
        and row.get("canonical_id") == "beta_carotene"
    ]
    return amounts, ranges


def test_a_stack_never_adds_vitamin_a_figures_as_beta_carotene(enricher):
    products = [_enrich(enricher, _raw(i)) for i in ("293269", "328639", "328127")] * 4
    # Twelve rows totalling 10,000 mcg RAE of vitamin A activity are no beta-carotene amount.
    assert sum(
        (r.get("safety_exposure") or {}).get("per_day") or 0
        for p in products for r in p["rda_ul_data"]["analyzed_ingredients"]
        if r.get("ingredient") == "Vitamin A"
    ) == pytest.approx(10000.0)
    for product in products[:3]:
        amounts, _ = _stack_rows(product)
        assert amounts and all(amount is None for amount in amounts)


def test_a_stack_keeps_confirmed_and_maximum_apart(enricher):
    confirmed, _ = _stack_rows(_enrich(enricher, _label(5000)))
    mixture_amounts, mixture_ranges = _stack_rows(_enrich(enricher, _label(mixture_mcg=8000)))
    assert set(confirmed) == {5000.0}
    assert not any(mixture_amounts)
    [exposure] = mixture_ranges
    assert (exposure["low_per_day"], exposure["high_per_day"]) == (0.0, pytest.approx(4000.0))
    assert exposure["unit"] == "mcg RAE"
    # 5,000 confirmed stays under 7,500, while 5,000 + 4,000 possible reaches it.
    assert max(confirmed) < 7500 <= max(confirmed) + exposure["high_per_day"]


# Sean's ruling, 2026-11-04: 184325 and 184326 read the manufacturer's stated composition.
SHEET_MCG_PER_CAPSULE = 14280


def _sheet_label(dsld_id):
    return json.loads((FIXTURES / f"beta_carotene_{dsld_id}_raw.json").read_text())


def _no_record(dsld_id):
    normalizer = EnhancedDSLDNormalizer()
    normalizer._label_corrections_by_dsld_id = {
        key: value for key, value in normalizer._label_corrections_by_dsld_id.items() if key != dsld_id
    }
    return normalizer.normalize_product(_sheet_label(dsld_id))


@pytest.mark.parametrize("dsld_id", ["184325", "184326"])
def test_a_reviewed_composition_reads_the_stated_mass(enricher, dsld_id):
    product = _enrich(enricher, _sheet_label(dsld_id))
    status, decision = _one_decision(product)
    assert status == "above_threshold"
    assert decision["consumer_disposition"] == "review"
    dose = decision["dose_evaluation"]
    assert dose["converted_amount"] == pytest.approx(2 * SHEET_MCG_PER_CAPSULE * FACTOR)
    assert dose["dose_source"] == "manufacturer_typical_composition"
    assert dose["conversion_method"]
    record = product["manufacturer_composition"]
    assert record["basis"] == "typical"
    assert record["source_date"] == "2021-04"
    assert record["source_url"].endswith("PURE_PIS_BetaCarotene_final.pdf")
    blob = build_detail_blob(product, score_product_v4(product))
    decisions = [
        w["dose_decision"] for w in blob["warnings"]
        if w.get("ingredient_canonical_id") == "beta_carotene" and w.get("dose_decision")
    ]
    assert decisions
    assert {d["evaluated_daily_amount"] for d in decisions} == {14280.0}
    assert {d["dose_source"] for d in decisions} == {"manufacturer_typical_composition"}


@pytest.mark.parametrize("dsld_id", ["184325", "184326"])
def test_the_vitamin_a_row_and_its_rules_are_unchanged(enricher, dsld_id):
    with_record = _enrich(enricher, _sheet_label(dsld_id))
    without, _ = enricher.enrich_product(_no_record(dsld_id))
    [row] = with_record["rda_ul_data"]["analyzed_ingredients"]
    [other] = without["rda_ul_data"]["analyzed_ingredients"]
    # The panel reading stamps its zero mass on the exposure; nothing else differs.
    for field in ("low_per_day", "high_per_day"):
        other["safety_exposure"].pop(field)
    assert other == row
    assert row["safety_exposure"]["per_day"] == 15000.0

    def others(product):
        return [
            alert for alert in product["interaction_profile"]["ingredient_alerts"]
            if "LUNG_CANCER" not in str(alert.get("rule_id"))
        ]

    assert others(with_record) == others(without)
    assert score_product_v4(with_record) == score_product_v4(without)


def _changed_amount(raw):
    raw["ingredientRows"][0]["quantity"][0]["quantity"] = 8000


def _changed_edition(raw):
    raw["productVersionCode"] = "code: BE1 v9"


@pytest.mark.parametrize("dsld_id", ["184325", "184326"])
@pytest.mark.parametrize("change", [_changed_amount, _changed_edition])
def test_a_record_that_no_longer_binds_is_unresolved(enricher, dsld_id, change):
    raw = _sheet_label(dsld_id)
    change(raw)
    product = _enrich(enricher, raw)
    assert product["manufacturer_composition"] == {"bound": False}
    decisions = _decisions(product)
    assert decisions
    for decision in decisions:
        assert decision["evaluation_status"] == "form_unknown"
        assert decision["consumer_disposition"] == "suppress"
        assert decision["dose_evaluation"] is None
    blob = build_detail_blob(product, score_product_v4(product))
    exported = [
        w["dose_decision"] for w in blob["warnings"]
        if w.get("ingredient_canonical_id") == "beta_carotene" and w.get("dose_decision")
    ]
    assert exported
    assert {d["evaluation_status"] for d in exported} == {"form_unknown"}
    assert {d["evaluated_daily_amount"] for d in exported} == {None}


def test_no_other_label_takes_this_path(enricher):
    corrections = json.loads(
        (FIXTURES.parent.parent / "data/curated_overrides/product_label_corrections.json").read_text()
    )["corrections"]
    assert {key for key, entry in corrections.items() if "manufacturer_composition" in entry} == {
        "184325", "184326",
    }
    product = _enrich(enricher, _raw("328639"))
    assert product.get("manufacturer_composition") is None
    status, decision = _one_decision(product)
    assert status == "amount_unknown"
    assert decision["dose_evaluation"] is None
