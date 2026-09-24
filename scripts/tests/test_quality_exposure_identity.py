"""Canonical identity and exposure regressions for the quality redesign."""
import pytest

from scoring_input_contract import _route_fiber_digestive_decision, get_scoring_ingredients
from scoring_v4.modules.fiber_digestive_dose import score_dose as fiber_dose
from scoring_v4.modules.fiber_digestive_helpers import fiber_rows, is_fiber_row
from scoring_v4.modules.sports_dose import score_dose as sports_dose
from scoring_v4.route_features import is_fiber_row as route_is_fiber_row
from serving_frequency import resolve_daily_serving_range


def row(identity, quantity, unit="g", **extra):
    return dict(name=identity.replace("_", " "), canonical_id=identity,
                quantity=quantity, unit=unit, unit_normalized=unit,
                category="fiber" if identity == "psyllium" else "sports",
                scoreable_identity=True, score_eligible_by_cleaner=True,
                cleaner_row_role="active_scorable", role_classification="active_scorable",
                source_section="active", raw_source_path="activeIngredients[0]", **extra)


def product(rows, frequency=1):
    value = {"ingredient_quality_data": {"ingredients_scorable": rows, "ingredients": rows}}
    if frequency is not None:
        value["servingSizes"] = [{"quantity": 1, "unit": "scoop", "minDailyServings": frequency,
                                   "maxDailyServings": frequency}]
    return value


@pytest.mark.parametrize("identity,amount", [("creatine", 3), ("beta_alanine", 4), ("hmb", 3)])
def test_daily_sports_amount_equivalence(identity, amount):
    split = sports_dose(product([row(identity, amount / 2)], 2))
    once = sports_dose(product([row(identity, amount)], 1))
    assert split["score"] == once["score"]
    assert split["metadata"]["dose_basis"] == once["metadata"]["dose_basis"]


def test_daily_fiber_amount_equivalence():
    assert fiber_dose(product([row("psyllium", 3)], 2))["score"] == fiber_dose(
        product([row("psyllium", 6)], 1))["score"]


def test_caffeine_benchmark_is_per_use_not_daily():
    assert sports_dose(product([row("caffeine", 150, "mg")], 3))["score"] == sports_dose(
        product([row("caffeine", 150, "mg")], 1))["score"]


def test_resolved_nonfiber_identity_wins_category_and_text():
    ingredient = row("glucosamine", 1.5)
    ingredient.update(category="fiber", raw_source_text="Glucosamine fiber complex")
    assert not route_is_fiber_row(ingredient)
    assert not is_fiber_row(ingredient)
    assert fiber_rows(product([ingredient])) == []


def test_prominent_non_digestive_active_blocks_incidental_material_fiber_route():
    facts = {"fiber_canonical_ids": ["fiber"], "fiber_mass_share": 0.84,
             "fiber_row_count": 1, "non_digestive_claim_prominent_count": 1}
    assert not _route_fiber_digestive_decision({}, "", features=facts)[0]


def test_structural_parent_quantity_does_not_duplicate_child_exposure():
    child = row("psyllium", 3)
    child["raw_source_path"] = "activeIngredients[0].nestedIngredients[0]"
    parent = row("psyllium", 3, is_parent_total=True)
    parent.update(cleaner_row_role="parent_total", role_classification="parent_total",
                  score_eligible_by_cleaner=False)
    rows = get_scoring_ingredients(product([parent, child]), strict=True).rows
    assert len(rows) == 1
    assert rows[0]["raw_source_path"] == child["raw_source_path"]


def test_carrier_oil_without_epa_dha_ownership_cannot_be_combined_exposure():
    value = product([row("fish_oil", 1000, "mg")])
    rows = get_scoring_ingredients(value, strict=True).rows
    assert not any(r.get("evidence_type") == "omega_epa_dha_aggregate" for r in rows)


def test_daily_exposure_preserves_frequency_uncertainty_and_source():
    from dataclasses import FrozenInstanceError
    from scoring_v4.exposure import row_exposure
    ingredient = row("creatine", 1500, "mg")
    exposure = row_exposure(product([ingredient], None), ingredient, basis="daily", unit="g")
    assert exposure.per_serving_amount == 1.5
    assert exposure.minimum is None and exposure.maximum is None
    assert exposure.frequency_defaulted is True
    assert exposure.source_path == "activeIngredients[0]"
    with pytest.raises(FrozenInstanceError):
        exposure.maximum = 3


def test_explicit_daily_exposure_preserves_interval_without_selecting_new_policy():
    from scoring_v4.exposure import row_exposure
    ingredient = row("creatine", 1500, "mg")
    value = product([ingredient], 2)
    value["servingSizes"][0]["maxDailyServings"] = 3
    exposure = row_exposure(value, ingredient, basis="daily", unit="g")
    assert (exposure.minimum, exposure.maximum) == (3, 4.5)
    assert exposure.basis == "daily" and exposure.unit == "g"
    assert not exposure.frequency_defaulted


def test_per_use_exposure_does_not_require_daily_frequency():
    from scoring_v4.exposure import row_exposure
    ingredient = row("caffeine", 0.15)
    exposure = row_exposure(product([ingredient], None), ingredient, basis="per_use", unit="mg")
    assert exposure.per_serving_amount == 150
    assert (exposure.minimum, exposure.maximum) == (150, 150)


@pytest.mark.parametrize("amount,unit", [(True, "g"), (float("inf"), "g"),
                                        (float("nan"), "g"), (3, "IU")])
def test_invalid_mass_is_unassessable(amount, unit):
    from scoring_v4.exposure import row_exposure
    ingredient = row("creatine", amount, unit)
    exposure = row_exposure(product([ingredient]), ingredient, basis="daily", unit="g")
    assert exposure.per_serving_amount is None
    assert exposure.minimum is None and exposure.maximum is None


def test_unknown_frequency_scores_one_serving_a_day_and_records_the_default():
    # No product ships with a "not evaluable" Dose: a silent label keeps the
    # one-serving-a-day fallback main always used; the default is provenance.
    silent = sports_dose(product([row("creatine", 3)], None))
    assert silent["score"] == sports_dose(product([row("creatine", 3)], 1))["score"]
    assert silent["metadata"]["benchmark_exposures"][0]["frequency_defaulted"] is True
    assert "not_evaluable_reason" not in silent["metadata"]


@pytest.mark.parametrize("as_list", [False, True])
def test_cleaner_preserves_quantity_operator_in_source_variants(as_list):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    cleaner = EnhancedDSLDNormalizer.__new__(EnhancedDSLDNormalizer)
    raw = {"operator": "<", "quantity": 1, "unit": "Gram(s)"}
    amount, unit, _, variants = cleaner._process_quantity([raw] if as_list else raw)
    assert amount == 1 and unit == "Gram(s)"
    assert variants[0]["operator"] == "<"


def test_upper_bound_fiber_is_not_exact_exposure():
    from scoring_v4.exposure import row_exposure
    ingredient = row("psyllium", 1)
    ingredient["raw_taxonomy"] = {"quantityVariants": [{"quantity": 1, "unit": "g", "operator": "<"}]}
    exposure = row_exposure(product([ingredient], 3), ingredient, basis="daily", unit="g")
    assert exposure.quantity_operator == "<"
    assert exposure.minimum == 0 and exposure.maximum == 3
    assert exposure.exact is False
    assert exposure.benchmark_amount == 3


def test_qualified_age_column_does_not_override_selected_exact_column():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from scoring_v4.exposure import row_exposure
    cleaner = EnhancedDSLDNormalizer.__new__(EnhancedDSLDNormalizer)
    cleaner._canonical_serving_row = {"quantity": 2}
    amount, unit, _, variants = cleaner._process_quantity([
        {"operator": "<", "quantity": 1, "unit": "g", "servingSizeQuantity": 1},
        {"operator": "=", "quantity": 1, "unit": "g", "servingSizeQuantity": 2},
    ])
    ingredient = row("psyllium", amount, unit)
    ingredient["raw_taxonomy"] = {"quantityVariants": variants}
    exposure = row_exposure(product([ingredient]), ingredient, basis="daily", unit="g")
    assert exposure.quantity_operator == "=" and exposure.exact


def test_conflicting_qualifiers_without_selected_column_are_unassessable():
    from scoring_v4.exposure import row_exposure
    ingredient = row("psyllium", 1)
    ingredient["raw_taxonomy"] = {"quantityVariants": [
        {"quantity": 1, "unit": "g", "operator": "<"},
        {"quantity": 1, "unit": "g", "operator": "="},
    ]}
    exposure = row_exposure(product([ingredient]), ingredient, basis="daily", unit="g")
    assert not exposure.exact and exposure.quantity_operator == "ambiguous"
    # An amount the label does not settle is never scored ...
    assert exposure.benchmark_amount is None
    assert fiber_dose(product([ingredient]))["components"]["fiber_effective_dose"] == 0
    # ... and the product is held out of the catalog until the column is fixed.
    from scoring_v4.gate_completeness import _has_unresolved_source_quantity
    assert _has_unresolved_source_quantity(product([ingredient]), [ingredient])
    exact = row("psyllium", 1)
    assert not _has_unresolved_source_quantity(product([exact]), [exact])


def test_raw_nested_fiber_operator_survives_cleaner_enricher_exposure():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.modules.fiber_digestive_helpers import nutrition_fiber_exposure
    cleaner = EnhancedDSLDNormalizer.__new__(EnhancedDSLDNormalizer)
    # Source shape verified against NIH DSLD 214586, dietary fiber <1g.
    raw_rows = [{"name": "Total Carbohydrates", "quantity": [{"quantity": 2, "unit": "Gram(s)"}],
                 "nestedRows": [{"name": "Dietary Fiber", "quantity": [{"operator": "<", "quantity": 1, "unit": "Gram(s)"}]}]}]
    ni = cleaner._extract_nutritional_info(raw_rows)
    enricher = SupplementEnricherV3.__new__(SupplementEnricherV3)
    value = product([], 3)
    value["nutrition_summary"] = enricher._collect_nutrition_summary({"nutritionalInfo": ni})
    exposure = nutrition_fiber_exposure(value)
    assert exposure.source_path == "ingredientRows[0].nestedRows[0]"
    assert exposure.quantity_operator == "<"
    assert exposure.minimum == 0 and exposure.maximum == 3
    assert not exposure.exact
    scored = fiber_dose(value | {"fullName": "Fiber"})
    # "<1 g" three times a day is scored on its stated 3 g, as main scored it.
    assert scored["components"]["fiber_effective_dose"] == 13.0
    assert scored["metadata"]["exposure_uncertainty"] == "quantity_qualified"


def test_conflicting_nutrition_owner_cannot_certify_summary_scalar():
    from scoring_v4.modules.fiber_digestive_helpers import nutrition_fiber_exposure
    value = product([], 1)
    value["nutrition_summary"] = {"dietary_fiber_g": 7, "dietary_fiber_source": {
        "amount": 1, "unit": "g", "raw_source_path": "ingredientRows[0]",
        "quantityVariants": [{"quantity": 1, "unit": "g", "operator": "<"}],
    }}
    exposure = nutrition_fiber_exposure(value)
    assert not exposure.exact
    assert exposure.source_path == "nutrition_summary.dietary_fiber_g"
    assert exposure.benchmark_amount is None
    from scoring_v4.gate_completeness import _has_unresolved_source_quantity
    assert _has_unresolved_source_quantity(value, [])


def test_qualified_caffeine_scores_its_stated_amount_and_records_the_qualifier():
    ingredient = row("caffeine", 200, "mg")
    ingredient["quantity_operator"] = "<"
    exact = row("caffeine", 200, "mg")
    result = sports_dose(product([ingredient], 3))
    assert result["score"] == sports_dose(product([exact], 3))["score"]
    assert result["metadata"]["benchmark_exposures"][0]["uncertainty"] == "quantity_qualified"


@pytest.mark.parametrize("frequency", [True, float("inf"), float("nan")])
def test_invalid_frequency_cannot_certify_daily_exposure(frequency):
    from scoring_v4.exposure import row_exposure
    ingredient = row("creatine", 3)
    exposure = row_exposure(product([ingredient], frequency), ingredient, basis="daily", unit="g")
    assert exposure.frequency_defaulted and not exposure.exact
    assert exposure.minimum is None and exposure.maximum is None


def test_course_exposure_does_not_invent_a_duration():
    from scoring_v4.exposure import row_exposure
    ingredient = row("creatine", 3)
    exposure = row_exposure(product([ingredient]), ingredient, basis="course", unit="g")
    assert exposure.uncertainty == "exposure_basis_unsupported"
    assert exposure.minimum is None and exposure.maximum is None


def test_primary_fiber_is_not_a_competing_non_digestive_claim():
    from scoring_v4.route_features import extract_route_features
    ingredient = row("psyllium", 6)
    value = product([ingredient], 1)
    value["fullName"] = "Neutral Label"
    classification = {"ingredients": [{"canonical_id": "psyllium", "role": "primary", "row_ref": ingredient["raw_source_path"]}]}
    facts = extract_route_features(value, [ingredient], classification)
    assert facts["non_digestive_claim_prominent_count"] == 0
    assert _route_fiber_digestive_decision(value, "", features=facts)[0]


@pytest.mark.parametrize("identity", ["beta_glucan", "prebiotics"])
def test_ambiguous_dual_purpose_claim_remains_digestive_competitor(identity):
    from scoring_v4.route_features import extract_route_features
    claimed = row(identity, 500, "mg")
    enzyme = row("amylase", 100, "mg")
    enzyme["raw_source_path"] = "activeIngredients[1]"
    value = product([claimed, enzyme], 1)
    value["fullName"] = "Immune Support"
    classification = {"ingredients": [
        {"canonical_id": identity, "role": "claim_prominent", "row_ref": claimed["raw_source_path"]},
        {"canonical_id": "amylase", "role": "adjunct", "row_ref": enzyme["raw_source_path"]},
    ]}
    facts = extract_route_features(value, [claimed, enzyme], classification)
    assert facts["non_digestive_claim_prominent_count"] == 1
    assert not _route_fiber_digestive_decision(value, "", features=facts)[0]


# The two defaulted-frequency tests (a DSLD default frequency is not label
# evidence) belong to held policy P6 and return with it.



def test_fiber_declaring_anchors_are_on_focus_other_anchors_and_ingredients_are_not():
    # 293400 Fiber Fusion Daily: Dietary Fiber, Oat Bran, stevia, plus a
    # "Proprietary Fiber Blend" header and an "Insoluble Fiber" sub-row the
    # contract marks as label-taxonomy anchors. The formula is all fiber.
    from scoring_v4.modules.fiber_digestive_formulation import score_formulation
    focus = lambda rows: score_formulation(product(rows))["components"]["fiber_formula_focus"]
    fiber, oat, stevia = row("fiber", 3), row("oat_bran", 3), row("nha_stevia", 44, "mg")
    fiber_anchors = [row("proprietary_fiber_blend", 3, identity_kind="label_taxonomy_anchor"),
                     row("fiber_unspecified", 2, identity_kind="label_taxonomy_anchor")]
    assert focus([fiber, oat, stevia, *fiber_anchors]) == 5.0
    # 213810 shape: a greens/herbal blend anchor is off-focus content.
    greens = row("superfood_greens_herbal_blends", 2, identity_kind="label_taxonomy_anchor")
    greens["name"] = "Superfood, Greens & Herbal Blends"
    assert focus([fiber, oat, stevia, greens, row("orange", 1)]) == 3.0
    # A disclosed off-focus ingredient counts, mapped identity or not.
    turmeric = row("turmeric", 0.5, identity_disposition="taxonomy_only")
    assert focus([fiber, stevia, turmeric, row("ginger", 0.5)]) == 3.0


def _directions(value, text, low, high):
    value["servingSizes"][0].update(minDailyServings=low, maxDailyServings=high)
    value["statements"] = [{"type": "Suggested/Recommended/Usage/Directions", "notes": text}]
    return value



def test_creatine_loading_peak_is_a_loading_protocol_not_an_overdose():
    # DSLD 77130 prints 1-4 scoops a day because days 1-5 load at 4 scoops.
    loading = _directions(product([row("creatine", 5)]), "Loading Phase: Day 1 through 5: 4 scoops daily. Then 1 scoop daily.", 1, 4)
    result = sports_dose(loading)
    assert result["metadata"]["dose_basis"] == "creatine_loading_protocol_up_to_20_g"
    # Without loading directions, 20 g/day stays the no-protocol band.
    plain = _directions(product([row("creatine", 5)]), "Take 1 scoop up to four times a day.", 1, 4)
    assert sports_dose(plain)["metadata"]["dose_basis"] == "creatine_above_10_g_no_loading_protocol"
    assert result["score"] > sports_dose(plain)["score"]
    # Loading wording does not make any amount a protocol: 40 g/day stays high-dose.
    heavy = _directions(product([row("creatine", 10)]), "Loading Phase: Day 1 through 5: 4 scoops daily. Then 1 scoop daily.", 1, 4)
    assert sports_dose(heavy)["metadata"]["dose_basis"] == "creatine_above_10_g_no_loading_protocol"


# Wording of the seven real creatine labels (77130, 306203, 307782-307784,
# 309604, 319643) and a defined initial period followed by maintenance.
@pytest.mark.parametrize("text", [
    "Loading Phase: Day 1 through 5: Take 1 scoop 4 times daily. Maintenance Phase: Day 6 forward: 1 scoop daily.",
    "Loading phase: Day 1 through 5: Mix 1 scoop with 6-10 oz of water and take 4 times daily. Maintenance phase: Day 6 forward: Mix 2 scoop.",
    "For the first 5 days take 4 scoops daily, then 1 scoop daily.",
    "Days 1-7: 4 servings a day. Thereafter 1 serving a day.",
])
def test_explicit_loading_protocols(text):
    from serving_frequency import has_loading_protocol
    assert has_loading_protocol({"statements": [{"type": "Suggested/Recommended/Usage/Directions", "notes": text}]})


@pytest.mark.parametrize("text", [
    "Take before workout.",
    "Take as needed.",
    "Cycle this product: 8 weeks on, 4 weeks off.",
    "Phase 1 formula. Take 2 scoops daily.",
    "For maintenance, take 1 scoop daily.",
    "Take 1 scoop daily, then drink plenty of water.",
])
def test_contingent_directions_are_not_loading(text):
    from serving_frequency import has_loading_protocol
    record = {"statements": [{"type": "Suggested/Recommended/Usage/Directions", "notes": text}]}
    assert not has_loading_protocol(record)
    loading = _directions(product([row("creatine", 5)]), text, 1, 4)
    assert sports_dose(loading)["metadata"]["dose_basis"] == "creatine_above_10_g_no_loading_protocol"


@pytest.mark.parametrize("text,state", [
    ("Take 1 scoop daily.", "daily"),
    ("Mix 1 scoop before your workout.", "contingent"),
    ("Take as needed.", "contingent"),
    ("Take 2 capsules with a meal.", "unstated"),
])
def test_daily_use_direction_state(text, state):
    from serving_frequency import daily_use_direction_state
    assert daily_use_direction_state({"statements": [{"type": "Suggested/Recommended/Usage/Directions", "notes": text}]}) == state


def test_reviewed_fiber_identities_added_in_task2():
    # oat_bran: 21 CFR 101.81 whole-oat beta-glucan source (DSLD 293400/293280).
    # oligosaccharides: IQM prebiotic fiber; dual-purpose like "prebiotics", so
    # it is fiber evidence but never defines a fiber product by itself.
    from scoring_v4.route_features import FIBER_CANONICALS, MATERIAL_FIBER_CANONICALS
    assert {"oat_bran", "oligosaccharides"} <= FIBER_CANONICALS
    assert "oat_bran" in MATERIAL_FIBER_CANONICALS
    assert "oligosaccharides" not in MATERIAL_FIBER_CANONICALS
