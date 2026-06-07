"""V4 Phase 6 — Botanical Profile (formulation + dose adapters).

Botanicals stop being scored like vitamins. The formulation adapter credits
botanical-specific quality signals (identity, plant part, extract, marker
standardization, branded clinically-studied extract); the dose adapter uses
clinical therapeutic ranges (rda_therapeutic_dosing.json) instead of the RDA/UL
proxy.

Spec: docs/superpowers/specs/2026-06-01-v4-botanical-profile-design.md
"""
from __future__ import annotations

from scoring_v4.modules.botanical_profile import (  # noqa: E402
    is_botanical_product,
    score_botanical_formulation,
    score_botanical_dose,
    BOTANICAL_FORMULATION_CAP,
    _mass_mg,
)


# --- unit normalization (DSLD "Gram(s)" spelling) --------------------------

def test_mass_mg_handles_dsld_gram_spelling():
    # DSLD's standard gram unit is "Gram(s)" (1906 rows in catalog), not "g".
    # It must convert to mg, not fall through to the assume-mg branch.
    assert _mass_mg({"quantity": 2.5, "unit": "Gram(s)"}) == 2500.0
    assert _mass_mg({"quantity": 1.13, "unit": "Gram(s)"}) == 1130.0
    assert _mass_mg({"quantity": 10, "unit": "Gram(s)"}) == 10000.0


def test_mass_mg_plain_units_unchanged():
    assert _mass_mg({"quantity": 500, "unit": "mg"}) == 500.0
    assert _mass_mg({"quantity": 100, "unit": "mcg"}) == 0.1
    assert _mass_mg({"quantity": 3, "unit": "g"}) == 3000.0
    assert _mass_mg({"quantity": 5, "unit": "grams"}) == 5000.0


def test_mass_mg_blank_unit_defaults_to_mg_but_non_mass_units_do_not():
    assert _mass_mg({"quantity": 250, "unit": ""}) == 250.0
    assert _mass_mg({"quantity": 10, "unit": "Billion CFU"}) is None
    assert _mass_mg({"quantity": 1200, "unit": "ALU"}) is None
    assert _mass_mg({"quantity": 400, "unit": "IU"}) is None


def _botanical_ingredient(name="KSM-66", standard_name="Ashwagandha",
                          canonical_id="ashwagandha", form="Ashwagandha Root Extract",
                          quantity=600, unit="mg", **extra):
    row = {
        "name": name,
        "standard_name": standard_name,
        "canonical_id": canonical_id,
        "matched_form": name + " " + standard_name.lower(),
        "quantity": quantity,
        "unit": unit,
        "mapped": True,
        "raw_taxonomy": {"category": "botanical", "ingredientGroup": standard_name,
                         "forms": [{"name": form}]},
    }
    row.update(extra)
    return row


def _botanical_product(ingredient=None, *, primary_type="herbal_botanical",
                       standardized=True):
    ing = ingredient or _botanical_ingredient()
    product = {
        "product_name": "KSM-66 Ashwagandha",
        "primary_type": primary_type,
        "ingredient_quality_data": {"ingredients_scorable": [ing], "ingredients": [ing]},
        "formulation_data": {},
    }
    if standardized:
        product["formulation_data"]["standardized_botanicals"] = [{
            "name": "KSM-66", "botanical_id": "ashwagandha", "standard_name": "Ashwagandha",
            "markers": ["withanolides", "withaferin A"], "percentage_found": 5.0,
            "min_threshold": 2.5, "meets_threshold": True,
        }]
    return product


def _blend_anchor_evidence(canonical_id: str, name: str, dose_value: float, dose_unit: str = "mg"):
    return {
        "name": name,
        "canonical_id": canonical_id,
        "clean_identity_id": canonical_id,
        "scoring_parent_id": canonical_id,
        "evidence_canonical_id": canonical_id,
        "canonical_source_db": "ingredient_quality_map",
        "evidence_origin": "compatibility_derived",
        "evidence_type": "blend_anchor_mass",
        "scoreable": True,
        "scoreable_identity": True,
        "score_eligible_by_cleaner": True,
        "dose_class": "therapeutic_mass",
        "dose_value": dose_value,
        "dose_unit": dose_unit,
        "source": "activeIngredients",
        "raw_source_path": "ingredientRows[1]",
        "evidence_scope": "blend_level",
        "linked_rows": ["ingredientRows[1]"],
        "confidence": "medium",
        "reason": "identity_bearing_blend_header_mass",
    }


# --- detector --------------------------------------------------------------

def test_botanical_product_detected_by_taxonomy():
    assert is_botanical_product(_botanical_product()) is True


def test_standardized_botanical_identity_routes_even_when_taxonomy_category_drifted():
    row = {
        "name": "Curcumin Phytosome",
        "standard_name": "Curcumin",
        "canonical_id": "curcumin",
        "matched_form": "Meriva curcumin phytosome",
        "quantity": 500,
        "unit": "mg",
        "mapped": True,
        "raw_taxonomy": {"category": "non-nutrient/non-botanical", "forms": []},
    }
    product = {
        "product_name": "Curcumin Phytosome 500 mg",
        "primary_type": "general_supplement",
        "ingredient_quality_data": {"ingredients_scorable": [row], "ingredients": [row]},
        "formulation_data": {
            "standardized_botanicals": [{
                "name": "Meriva",
                "botanical_id": "curcumin",
                "standard_name": "Curcumin",
                "markers": ["curcuminoids"],
                "percentage_found": 95.0,
                "min_threshold": 95,
                "meets_threshold": True,
            }]
        },
    }

    assert is_botanical_product(product) is True
    formulation = score_botanical_formulation(product)
    assert formulation["components"]["recognized_botanical_identity"] == 6.0
    assert formulation["components"]["marker_standardization_declared"] == 4.0

    dose = score_botanical_dose(product)
    assert dose["band"] == "within_studied_range"
    assert dose["score"] == 21.0


def test_standardized_botanical_parent_complex_total_is_dose_evaluable():
    row = {
        "name": "Curcumin Phytosome",
        "standard_name": "Curcumin",
        "canonical_id": "curcumin",
        "matched_form": "Meriva curcumin phytosome",
        "quantity": 500,
        "unit": "mg",
        "mapped": True,
        "is_parent_total": True,
        "raw_taxonomy": {
            "category": "non-nutrient/non-botanical",
            "forms": [
                {"name": "Curcuma longa", "category": "botanical"},
                {"name": "Phosphatidylcholine", "category": "fat"},
            ],
        },
    }
    product = {
        "product_name": "Curcumin Phytosome 500 mg",
        "primary_type": "general_supplement",
        "ingredient_quality_data": {"ingredients_scorable": [row], "ingredients": [row]},
        "formulation_data": {
            "standardized_botanicals": [{
                "name": "Curcumin Phytosome",
                "botanical_id": "turmeric",
                "standard_name": "Turmeric",
                "markers": ["curcuminoids"],
                "percentage_found": 0.0,
                "min_threshold": 95,
                "meets_threshold": True,
                "evidence_source": "marker_word_match",
            }]
        },
    }

    dose = score_botanical_dose(product)
    assert dose["band"] == "within_studied_range"
    assert dose["score"] == 21.0


def test_vitamin_product_is_not_botanical():
    vit = {
        "primary_type": "single_vitamin",
        "ingredient_quality_data": {"ingredients_scorable": [
            {"canonical_id": "vitamin_c_ascorbic_acid", "name": "Vitamin C",
             "quantity": 500, "unit": "mg", "raw_taxonomy": {"category": "vitamin"}}]},
    }
    assert is_botanical_product(vit) is False


# --- formulation adapter ---------------------------------------------------

def test_ksm66_formulation_caps_at_15():
    # recognized(6)+plant_part(2)+dose(2)+extract(2)+marker(4)+branded(3) = 19 -> cap 15
    out = score_botanical_formulation(_botanical_product())
    assert out["score"] == BOTANICAL_FORMULATION_CAP == 15.0
    c = out["components"]
    assert c["recognized_botanical_identity"] == 6.0
    assert c["plant_part_disclosed"] == 2.0
    assert c["quantified_dose_present"] == 2.0
    assert c["extract_not_whole_herb"] == 2.0
    assert c["marker_standardization_declared"] == 4.0
    assert c["branded_clinically_studied_extract"] == 3.0


def test_standardization_tier_credit_is_proportional():
    # Calibration v2: marker standardization is tiered 0-4, not binary on
    # meets_threshold, so a near-threshold or disclosed standardization earns
    # partial credit while a plain powder / no-evidence ingredient earns nothing.
    from scoring_v4.modules.botanical_profile import _standardization_tier_credit

    def case(**item):
        product = {"formulation_data": {"standardized_botanicals": [dict(item, botanical_id="boswellia")]}}
        row = {"canonical_id": "boswellia", "standard_name": "Boswellia serrata", "name": "Boswellia serrata"}
        return _standardization_tier_credit(product, row)

    assert case(meets_threshold=True) == 4.0
    assert case(meets_threshold=False, percentage_found=52, min_threshold=65,
                evidence_source="percentage_context") == 3.0   # 80% of spec
    assert case(meets_threshold=False, percentage_found=40, min_threshold=65,
                evidence_source="percentage_context") == 2.0   # 62% of spec
    assert case(meets_threshold=False, percentage_found=20, min_threshold=65,
                evidence_source="percentage_context") == 0.0   # < 50% -> under-standardized
    assert case(meets_threshold=False, percentage_found=0, min_threshold=65,
                evidence_source="marker_word_match") == 1.0     # disclosed, no amount
    assert case(meets_threshold=False, percentage_found=0, min_threshold=65,
                evidence_source="none") == 0.0                  # whole-food / no evidence


def test_plain_whole_herb_powder_scores_modestly():
    # whole herb powder, no standardization, not branded, with a recognized id + dose
    ing = _botanical_ingredient(name="Ashwagandha Root Powder",
                                form="Ashwagandha Root Powder", quantity=500)
    out = score_botanical_formulation(_botanical_product(ingredient=ing, standardized=False))
    c = out["components"]
    assert c.get("recognized_botanical_identity") == 6.0
    assert c.get("plant_part_disclosed") == 2.0
    assert c.get("quantified_dose_present") == 2.0
    assert "extract_not_whole_herb" not in c  # powder, not extract
    assert "marker_standardization_declared" not in c
    assert "branded_clinically_studied_extract" not in c
    assert out["score"] == 10.0


def test_weak_unidentified_botanical_penalised():
    ing = {"name": "Proprietary Herbal Blend", "standard_name": "Herbal Blend",
           "canonical_id": "", "quantity": 0, "unit": "",
           "raw_taxonomy": {"category": "botanical", "forms": []}}
    out = score_botanical_formulation(_botanical_product(ingredient=ing, standardized=False))
    assert out["score"] <= 0.0
    assert out["components"].get("weak_or_unidentified_botanical") == -4.0


# --- dose adapter ----------------------------------------------------------

def test_dose_within_studied_range():
    # ashwagandha 250-600; 600mg is within range
    out = score_botanical_dose(_botanical_product())
    assert 20.0 <= out["score"] <= 22.0
    assert out["band"] == "within_studied_range"


def test_dose_exact_target_reference_counts_within_range():
    # saw palmetto is stored as a single target dose ("320" mg), not a range.
    ing = _botanical_ingredient(
        name="Saw Palmetto",
        standard_name="Saw Palmetto",
        canonical_id="saw_palmetto_berry",
        form="Saw Palmetto Berry Extract",
        quantity=320,
    )
    out = score_botanical_dose(_botanical_product(ingredient=ing))
    assert out["band"] == "within_studied_range"
    assert out["score"] == 21.0
    assert out["metadata"]["range_mg"] == [320.0, 320.0]


def test_dose_below_studied_range():
    ing = _botanical_ingredient(quantity=100)  # below 250
    out = score_botanical_dose(_botanical_product(ingredient=ing))
    # Calibration v2: a verified under-range dose floors at 12 (was 10) — a real
    # but not destructive signal; transparency (a disclosed dose) is still credited.
    assert out["score"] == 12.0
    assert out["band"] == "below_studied_range"


def test_dose_disclosed_no_clinical_reference():
    # a botanical NOT in rda_therapeutic_dosing, but with a disclosed dose
    ing = _botanical_ingredient(name="Eyebright", standard_name="Eyebright",
                                canonical_id="eyebright", form="Eyebright Herb", quantity=300)
    out = score_botanical_dose(_botanical_product(ingredient=ing))
    # Calibration v2: a disclosed dose with no clinical reference in our 44-entry
    # DB floors at 12 (was 10) — it is a matcher gap, not a quality defect.
    assert out["score"] == 12.0
    assert out["band"] == "disclosed_no_reference"


def test_dose_grape_seed_matches_clinical_range_by_canonical_id():
    # Phase 4 lock-in: grape seed extract is canonicalized to grape_seed_extract
    # corpus-wide (range 100-800 mg). A 100mg grape-seed-primary product must land
    # in the clinical range, NOT the no-reference floor. Guards the "grape seed
    # doesn't match its dose range" risk the cutover plan flagged (which does not
    # reproduce because the enricher already stamps the canonical id).
    ing = _botanical_ingredient(
        name="Grape Seed Extract", standard_name="Grape Seed Extract",
        canonical_id="grape_seed_extract", form="Grape Seed Extract", quantity=100,
    )
    out = score_botanical_dose(_botanical_product(ingredient=ing, standardized=False))
    assert out["band"] == "within_studied_range"
    assert out["score"] == 21.0
    assert out["metadata"]["range_mg"] == [100.0, 800.0]


def test_primary_botanical_no_dose_floors_low_not_excluded():
    ing = _botanical_ingredient(quantity=0, unit="")
    out = score_botanical_dose(_botanical_product(ingredient=ing))
    # Calibration v2: a primary botanical with no disclosed dose floors at 5 (was
    # 0) — non-disclosure loses most credit, but is not destroyed ("lose credit,
    # not all"). Still never None (must stay in the denominator).
    assert out["score"] == 5.0
    assert out["band"] == "primary_no_dose"
    assert out["score"] is not None
    # critical: 0, NOT None (must not be excluded from the denominator)
    assert out["score"] is not None


# --- mixed-product routing (P6 review P2#1: mass-dominance gate) ------------

def _mineral(name="Magnesium", canonical_id="magnesium", quantity=400, unit="mg"):
    return {"name": name, "standard_name": name, "canonical_id": canonical_id,
            "quantity": quantity, "unit": unit, "mapped": True,
            "raw_taxonomy": {"category": "mineral"}}


def _mixed_product(rows):
    return {"status": "active", "primary_type": "generic",
            "ingredient_quality_data": {"ingredients_scorable": rows, "ingredients": rows,
                                        "total_active": len(rows)}}


def test_mineral_dominant_with_token_herb_is_not_botanical():
    # Magnesium 400 mg (mineral) dominates Ginger 50 mg (token herb). The product
    # must NOT route to the botanical profile — that would discard magnesium's
    # RDA/UL dose adequacy and score the whole product off the trace herb.
    p = _mixed_product([_mineral("Magnesium", "magnesium", 400, "mg"),
                        _botanical_ingredient(name="Ginger", standard_name="Ginger",
                                              canonical_id="ginger", form="Ginger Root",
                                              quantity=50)])
    assert is_botanical_product(p) is False


def test_botanical_dominant_over_trace_mineral_is_botanical():
    # 241706-style: green tea 100 mg (botanical) dominates chromium 100 mcg
    # (= 0.1 mg). The botanical is mass-dominant -> still routes botanical.
    p = _mixed_product([_mineral("Chromium", "chromium", 100, "mcg"),
                        _botanical_ingredient(name="Green Tea Extract",
                                              standard_name="Green Tea",
                                              canonical_id="green_tea_extract",
                                              form="Green Tea Leaf Extract", quantity=100)])
    assert is_botanical_product(p) is True


def test_pure_botanical_with_no_competing_mineral_is_botanical():
    # No non-botanical actives -> routes botanical regardless of mass.
    p = _mixed_product([_botanical_ingredient()])
    assert is_botanical_product(p) is True


# --- megadose (P6 review P2#2) ---------------------------------------------

def test_megadose_above_studied_range_credited_below_near():
    # ashwagandha 10000 mg (studied 250-600). A 16x megadose must NOT earn the
    # same near-range credit (16) as a dose just outside the window.
    ing = _botanical_ingredient(quantity=10000)
    out = score_botanical_dose(_botanical_product(ingredient=ing))
    assert out["band"] == "above_studied_range"
    assert out["score"] == 12.0  # < near_studied_range (16)


# --- anchor-only dose (P6 review P2#3) -------------------------------------

def test_anchor_only_dose_treated_as_blend_total_not_within_range():
    # A blend/anchor total (scoring_input_kind=product_level_evidence) is NOT a
    # verified per-ingredient dose. It must score like a blend total (10 in
    # calibration v2, was 7), not earn full within_studied_range credit (21) —
    # otherwise removing the botanical-anchor CAUTION ceiling would over-credit
    # opaque blends.
    ing = _botanical_ingredient(quantity=500, scoring_input_kind="product_level_evidence",
                                evidence_type="blend_anchor_mass")
    out = score_botanical_dose(_botanical_product(ingredient=ing))
    assert out["band"] == "blend_total_only"
    assert out["score"] == 10.0


def test_product_level_botanical_evidence_is_visible_to_profile_scorer():
    product = {
        "product_name": "Red Wine Complex 200 mg",
        "primary_type": "general_supplement",
        "ingredient_quality_data": {"ingredients_scorable": [], "ingredients": []},
        "product_scoring_evidence": [
            _blend_anchor_evidence("red_wine_extract", "Red Wine Complex", 200.0)
        ],
    }

    assert is_botanical_product(product) is True
    out = score_botanical_dose(product)
    assert out["band"] == "blend_total_only"
    assert out["score"] == 10.0  # calibration v2 (was 7)


def test_botanical_formulation_prefers_recognized_anchor_over_unmapped_blend_header():
    """Relora/Seditol shape: a parent proprietary-blend total and a recognized
    nested botanical anchor can carry the same mass. The botanical formulation
    selector must choose the recognized botanical anchor, not the unmapped
    parent header, otherwise formulation collapses to 0."""
    product = {
        "product_name": "Relora",
        "primary_type": "general_supplement",
        "ingredient_quality_data": {"ingredients_scorable": [], "ingredients": []},
        "product_scoring_evidence": [
            _blend_anchor_evidence("relora_patented_proprietary_blend", "Relora Patented Proprietary Blend", 250.0),
            _blend_anchor_evidence("magnolia_bark", "Magnolia (Magnolia officinalis) extract", 250.0),
        ],
    }
    product["product_scoring_evidence"][0]["canonical_source_db"] = "unmapped"
    product["product_scoring_evidence"][0]["clean_identity_id"] = None

    out = score_botanical_formulation(product)

    assert out["metadata"]["recognized"] is True
    assert out["components"]["recognized_botanical_identity"] == 6.0
    assert out["components"]["quantified_dose_present"] == 2.0
    assert out["score"] > 0.0
