"""V4 Phase 6 — Botanical Profile (formulation + dose adapters).

Botanicals stop being scored like vitamins. V4.1 Step 4: the formulation
adapter gives a recognized identity the neutral baseline and earns extract and
marker-standardization quality (plant part and amount are Transparency facts,
a brand name is an Evidence fact); the dose adapter grades the daily amount
against reviewed source references; completed no-benchmark conclusions and
recognized ingredients with source-confirmed hidden amounts use the shared neutral.

Spec: docs/superpowers/specs/2026-06-01-v4-botanical-profile-design.md
"""
from __future__ import annotations

import pytest

from scoring_v4.modules.botanical_profile import (  # noqa: E402
    is_botanical_product,
    score_botanical_formulation,
    score_botanical_dose,
    BOTANICAL_FORMULATION_CAP,
    _mass_mg,
    _primary_botanical_active,
)
from scoring_v4.modules.generic_helpers import (
    archetype_dose_reference,
    dose_reference_scope,
    unbenchmarked_dose_credit,
)

# Production scores the botanical profile on its archetype Dose reference (21).
BOTANICAL_DOSE_REFERENCE = archetype_dose_reference("generic", {"botanical_profile_applied": True})


@pytest.fixture(autouse=True)
def _botanical_dose_reference():
    with dose_reference_scope(BOTANICAL_DOSE_REFERENCE):
        yield


def _neutral():
    """The shared unbenchmarked neutral (11.4 public) on the active reference."""
    return unbenchmarked_dose_credit()


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


def test_mass_mg_handles_qualified_micronutrient_units():
    assert _mass_mg({"quantity": 1000, "unit": "mcg DFE"}) == 1.0
    assert _mass_mg({"quantity": 1300, "unit": "mcg RAE"}) == 1.3
    assert _mass_mg({"quantity": 1.7, "unit": "mg DFE"}) == 1.7


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
    if "KSM-66" in ing.get("name", "") and ing.get("raw_source_path"):
        # The enricher's record for a label that names KSM-66 on this row.
        product["evidence_data"] = {"clinical_matches": [{
            "id": "BRAND_KSM66", "evidence_level": "branded-rct",
            "matched_source_row_refs": [ing["raw_source_path"]],
        }]}
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
    assert formulation["components"]["recognized_botanical_identity"] == 7.2
    assert formulation["components"]["marker_standardization_declared"] == 3.2

    dose = score_botanical_dose(product)
    assert dose["band"] == "disclosed_no_reference"
    assert dose["score"] == _neutral()


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
    assert dose["band"] == "disclosed_no_reference"
    assert dose["score"] == _neutral()


def test_vitamin_product_is_not_botanical():
    vit = {
        "primary_type": "single_vitamin",
        "ingredient_quality_data": {"ingredients_scorable": [
            {"canonical_id": "vitamin_c_ascorbic_acid", "name": "Vitamin C",
             "quantity": 500, "unit": "mg", "raw_taxonomy": {"category": "vitamin"}}]},
    }
    assert is_botanical_product(vit) is False


# --- formulation adapter ---------------------------------------------------

def test_ksm66_formulation_earns_extract_and_standardization_once():
    # neutral identity 7.2 + extract 1.6 + full standardization 3.2 = 12 of 15.
    # Plant part and amount are Transparency facts; the brand is an Evidence
    # fact, so a branded extract earns its standardization once, not twice.
    ksm66 = _botanical_ingredient(raw_source_path="ingredientRows[0]", plantPart="root")
    out = score_botanical_formulation(_botanical_product(ingredient=ksm66))
    assert BOTANICAL_FORMULATION_CAP == 15.0
    assert out["components"] == {
        "recognized_botanical_identity": 7.2,
        "extract_not_whole_herb": 1.6,
        "marker_standardization_declared": 3.2,
    }
    assert out["score"] == 12.0


def test_standardization_tier_credit_is_proportional():
    # Calibration v2: marker standardization is tiered 0-4, not binary on
    # meets_threshold, so a near-threshold or disclosed standardization earns
    # partial credit while a plain powder / no-evidence ingredient earns nothing.
    from scoring_v4.modules.botanical_profile import _standardization_tier_credit

    def case(**item):
        product = {"formulation_data": {"standardized_botanicals": [dict(item, botanical_id="boswellia")]}}
        row = {"canonical_id": "boswellia", "standard_name": "Boswellia serrata", "name": "Boswellia serrata"}
        return _standardization_tier_credit(product, row)

    assert case(meets_threshold=True) == 3.2
    assert case(meets_threshold=False, percentage_found=52, min_threshold=65,
                evidence_source="percentage_context") == 2.4   # 80% of spec
    assert case(meets_threshold=False, percentage_found=40, min_threshold=65,
                evidence_source="percentage_context") == 1.6   # 62% of spec
    assert case(meets_threshold=False, percentage_found=20, min_threshold=65,
                evidence_source="percentage_context") == 0.0   # < 50% -> under-standardized
    # A marker named without an amount is disclosure, not measured quality.
    assert case(meets_threshold=False, percentage_found=0, min_threshold=65,
                evidence_source="marker_word_match") == 0.0
    assert case(meets_threshold=False, percentage_found=0, min_threshold=65,
                evidence_source="none") == 0.0                  # whole-food / no evidence


def test_plain_whole_herb_powder_scores_modestly():
    # whole herb powder, no standardization, not branded, with a recognized id + dose
    ing = _botanical_ingredient(name="Ashwagandha Root Powder",
                                form="Ashwagandha Root Powder", quantity=500, plantPart="root")
    out = score_botanical_formulation(_botanical_product(ingredient=ing, standardized=False))
    # Only the neutral identity baseline: no extract or standardization quality.
    assert out["components"] == {"recognized_botanical_identity": 7.2}
    assert out["score"] == 7.2


def test_weak_unidentified_botanical_penalised():
    ing = {"name": "Proprietary Herbal Blend", "standard_name": "Herbal Blend",
           "canonical_id": "", "quantity": 0, "unit": "",
           "raw_taxonomy": {"category": "botanical", "forms": []}}
    out = score_botanical_formulation(_botanical_product(ingredient=ing, standardized=False))
    assert out["score"] <= 0.0
    assert out["components"].get("weak_or_unidentified_botanical") == -4.0


# --- dose adapter ----------------------------------------------------------

def test_disclosed_studied_regimen_remains_neutral():
    # Source exposure envelopes do not establish clinical scoring windows.
    out = score_botanical_dose(_botanical_product())
    assert out["score"] == _neutral()
    assert out["band"] == "disclosed_no_reference"


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
    assert out["band"] == "disclosed_no_reference"
    assert out["score"] == _neutral()
    from scoring_v4.modules.botanical_profile import _dosing_entry_for
    assert _dosing_entry_for(ing)["id"] == "saw_palmetto_extract"
    assert _dosing_entry_for(ing)["reference_semantics"]["reference_type"] == "discrete_studied_regimen"


def test_below_studied_regimen_remains_neutral():
    ing = _botanical_ingredient(quantity=100)  # below 250
    out = score_botanical_dose(_botanical_product(ingredient=ing))
    # Completed general benchmark review uses neutral at every disclosed amount.
    assert out["score"] == _neutral()
    assert out["band"] == "disclosed_no_reference"


def test_reviewed_eyebright_route_mismatch_is_completed_general_neutral():
    # a botanical NOT in rda_therapeutic_dosing, but with a disclosed dose
    ing = _botanical_ingredient(name="Eyebright", standard_name="Eyebright",
                                canonical_id="eyebright", form="Eyebright Herb", quantity=300)
    out = score_botanical_dose(_botanical_product(ingredient=ing))
    # Eye-drop research supplies no oral-leaf threshold; a reviewed limitation is complete.
    assert out["score"] == _neutral()
    assert out["metadata"]["benchmark"] == "absent"
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
    assert out["band"] == "disclosed_no_reference"
    assert out["score"] == _neutral()
    from scoring_v4.modules.botanical_profile import _dosing_entry_for
    assert _dosing_entry_for(ing)["id"] == "grape_seed_extract"
    assert _dosing_entry_for(ing)["reference_semantics"]["reference_type"] == "no_benchmark"


def test_primary_botanical_no_dose_floors_low_not_excluded():
    ing = _botanical_ingredient(quantity=0, unit="")
    out = score_botanical_dose(_botanical_product(ingredient=ing))
    # Dose V4.1 section 2.3: only a genuinely hidden amount (a blend member
    # printed without its amount) takes the neutral; a missing amount with a
    # studied range keeps 0. Still never None: it stays in the denominator.
    assert out["score"] == 0.0
    assert out["band"] == "primary_no_dose"
    hidden = score_botanical_dose(_botanical_product(
        ingredient=_botanical_ingredient(quantity=0, unit="", isNestedIngredient=True)))
    assert hidden["score"] == pytest.approx(unbenchmarked_dose_credit())
    assert out["metadata"]["benchmark"] == "absent"
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

def test_above_studied_regimen_does_not_infer_a_safety_ceiling():
    # High study exposure is not a safety upper limit or numerical Dose penalty.
    ing = _botanical_ingredient(quantity=10000)
    out = score_botanical_dose(_botanical_product(ingredient=ing))
    assert out["band"] == "disclosed_no_reference"
    assert out["score"] == _neutral()


# --- anchor-only dose (P6 review P2#3) -------------------------------------

def test_anchor_only_dose_treated_as_blend_total_not_within_range():
    # A blend/anchor total (scoring_input_kind=product_level_evidence) is NOT a
    # verified per-ingredient dose and never earns within_studied_range credit.
    # Dose V4.1 section 2.3: the hidden amount takes the shared neutral.
    ing = _botanical_ingredient(quantity=500, scoring_input_kind="product_level_evidence",
                                evidence_type="blend_anchor_mass")
    out = score_botanical_dose(_botanical_product(ingredient=ing))
    assert out["band"] == "blend_total_only"
    assert out["score"] == pytest.approx(unbenchmarked_dose_credit())
    assert out["metadata"]["benchmark"] == "absent"


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
    # Known red-wine material has a reviewed general-neutral Dose conclusion.
    # This total still never becomes an invented per-component quantity.
    assert out["score"] == _neutral()
    assert out["metadata"]["benchmark"] == "absent"


def test_disclosed_ksm66_row_outranks_synthetic_blend_total():
    """A blend total is fallback evidence, never a replacement for its child.

    The submitted Youtheory label discloses KSM-66 at 600 mg and also carries a
    product-level 1,000 mg blend projection.  Botanical formulation and dose
    must use the real label row so the branded form and per-ingredient dose are
    not erased by the larger synthetic total.
    """
    ksm66 = _botanical_ingredient(
        raw_source_path="ingredientRows[0].nestedRows[0]",
    )
    powder = _botanical_ingredient(
        name="Organic Ashwagandha Root Powder",
        form="Ashwagandha Root Powder",
        quantity=400,
        raw_source_path="ingredientRows[0].nestedRows[1]",
        matched_form="ashwagandha (unspecified)",
    )
    product = _botanical_product(ingredient=ksm66)
    product["ingredient_quality_data"]["ingredients_scorable"].append(powder)
    product["ingredient_quality_data"]["ingredients"].append(powder)
    projection = _blend_anchor_evidence(
        "ashwagandha",
        "Organic Ashwagandha Root Extract",
        1000.0,
    )
    projection["raw_source_path"] = "ingredientRows[0]"
    projection["linked_rows"] = ["ingredientRows[0]"]
    product["product_scoring_evidence"] = [projection]

    formulation = score_botanical_formulation(product)
    dose = score_botanical_dose(product)

    assert "branded_clinically_studied_extract" not in formulation["components"]
    assert formulation["components"]["marker_standardization_declared"] == 3.2
    assert dose["band"] == "disclosed_no_reference"
    assert dose["score"] == _neutral()


def test_blend_reconciliation_counts_nonbotanical_disclosed_children():
    """Owner selection reconciles against every disclosed blend child.

    The botanical scorer must use the same ownership boundary as product
    classification.  A 1,000 mg rollup made from 600 mg KSM-66 plus 400 mg
    GABA is fully disclosed even though only one child is botanical.
    """
    ksm66 = _botanical_ingredient(
        raw_source_path="ingredientRows[0].nestedRows[0]",
    )
    gaba = {
        "name": "GABA",
        "standard_name": "GABA",
        "canonical_id": "gaba",
        "matched_form": "gaba (unspecified)",
        "quantity": 400,
        "unit": "mg",
        "mapped": True,
        "raw_source_path": "ingredientRows[0].nestedRows[1]",
        "raw_taxonomy": {
            "category": "non-nutrient/non-botanical",
            "ingredientGroup": "GABA",
            "forms": [],
        },
    }
    product = _botanical_product(ingredient=ksm66)
    product["ingredient_quality_data"]["ingredients_scorable"].append(gaba)
    product["ingredient_quality_data"]["ingredients"].append(gaba)
    projection = _blend_anchor_evidence(
        "ashwagandha",
        "Ashwagandha + GABA Blend",
        1000.0,
    )
    projection["raw_source_path"] = "ingredientRows[0]"
    projection["linked_rows"] = [
        "ingredientRows[0]",
        "ingredientRows[0].nestedRows[0]",
        "ingredientRows[0].nestedRows[1]",
    ]
    product["product_scoring_evidence"] = [projection]

    formulation = score_botanical_formulation(product)
    dose = score_botanical_dose(product)

    assert "branded_clinically_studied_extract" not in formulation["components"]
    assert formulation["components"]["marker_standardization_declared"] == 3.2
    assert dose["band"] == "disclosed_no_reference"
    assert dose["score"] == _neutral()


def test_top_level_proprietary_botanical_blend_total_gets_conservative_profile():
    """A pure botanical proprietary blend with only a total amount is evaluable,
    but only as blend_total_only. It must not fall to generic no-dose fallback,
    and it must not receive within-range per-ingredient dose credit."""
    from scoring_input_contract import get_scoring_ingredients
    from scoring_v4.modules.generic import score_generic

    product = {
        "product_name": "Liver Botanicals Proprietary Blend 900",
        "primary_type": "general_supplement",
        "ingredient_quality_data": {"ingredients_scorable": [], "ingredients": []},
        "proprietary_blends": [
            {
                "name": "Proprietary Liver Botanical Blend",
                "blend_total_mg": 900.0,
                "unit": "mg",
                "hidden_count": 3,
                "nested_count": 3,
                "child_ingredients": [
                    {"name": "Milk thistle seed extract", "amount": None, "unit": ""},
                    {"name": "Dandelion root", "amount": None, "unit": ""},
                    {"name": "Artichoke leaf", "amount": None, "unit": ""},
                ],
            }
        ],
    }

    rows = get_scoring_ingredients(product, strict=True).rows
    assert len(rows) == 1
    assert rows[0]["evidence_type"] == "blend_anchor_mass"
    assert rows[0]["reason"] == "proprietary_blend_total_from_botanical_child"
    assert rows[0]["canonical_id"] == "milk_thistle"

    assert is_botanical_product(product) is True
    dose = score_botanical_dose(product)
    assert dose["band"] == "blend_total_only"
    # The input owner confirms the known milk-thistle identity and hidden
    # component share. No numerical benchmark is applied to the blend total.
    assert dose["metadata"]["benchmark"] == "unresolved"
    assert dose["metadata"]["assessment_status"] == "complete"
    assert dose["metadata"]["reason_code"] == "amount_not_declared"
    assert dose["score"] == _neutral()

    result = score_generic(product)
    formulation = result.dimensions["formulation"]
    assert formulation.metadata["botanical_profile_applied"] is True
    assert result.dimensions["dose"].metadata["botanical_dose_band"] == "blend_total_only"
    assert result.dimensions["evidence"].metadata["primary_evidence_floor"] == 0.0
    assert result.dimensions["formulation"].score > 0
    assert result.dimensions["dose"].score == _neutral()


def test_top_level_food_matrix_blend_does_not_create_botanical_profile():
    """Food/vegetable matrices are blend opacity signals, not botanical dose evidence."""
    from scoring_input_contract import get_scoring_ingredients

    product = {
        "product_name": "Daily Greens Food Matrix",
        "primary_type": "general_supplement",
        "ingredient_quality_data": {"ingredients_scorable": [], "ingredients": []},
        "proprietary_blends": [
            {
                "name": "Organic Vegetables",
                "blend_total_mg": 62.0,
                "unit": "mg",
                "child_ingredients": [
                    {"name": "organic Broccoli", "amount": None, "unit": ""},
                    {"name": "organic Kale", "amount": None, "unit": ""},
                    {"name": "organic Parsley", "amount": None, "unit": ""},
                    {"name": "organic Spinach", "amount": None, "unit": ""},
                    {"name": "organic Tomato", "amount": None, "unit": ""},
                ],
            }
        ],
    }

    assert get_scoring_ingredients(product, strict=True).rows == []
    assert is_botanical_product(product) is False


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
    assert out["components"]["recognized_botanical_identity"] == 7.2
    assert "quantified_dose_present" not in out["components"]
    assert out["score"] > 0.0


def test_botanical_dose_compares_minimum_daily_exposure_to_daily_reference():
    # 150 mg twice daily reaches the 250 mg/day lower bound. A range of
    # one to two servings must not use its maximum to claim adequacy.
    product = _botanical_product(_botanical_ingredient(quantity=150))
    product['serving_basis'] = {
        'min_servings_per_day': 2, 'max_servings_per_day': 2,
        'servings_per_day_source': 'servingSizes',
    }
    assert score_botanical_dose(product)['band'] == 'disclosed_no_reference'
    product['serving_basis']['min_servings_per_day'] = 1
    assert score_botanical_dose(product)['band'] == 'disclosed_no_reference'


def test_whole_herb_mass_cannot_use_an_extract_dose_reference():
    row = _botanical_ingredient(name='Ashwagandha Root Powder', standard_name='Ashwagandha',
                               form='Ashwagandha Root Powder', quantity=500,
                               matched_form='Ashwagandha Root Powder')
    product = _botanical_product(row, standardized=False)
    assert score_botanical_dose(product)['band'] == 'disclosed_no_reference'
def test_primary_botanical_tie_break_reads_form_quality_through_its_owner():
    """Equal mass, both recognized: the last tie-break is form quality, read
    through generic_helpers.bio_score_of (the one owner). bio_score is the only
    form-quality value (c3afa98b): a row carrying only the retired IQM `score`
    has no form quality and never outranks a scored row."""
    current = _botanical_ingredient(bio_score=6)
    rhodiola = dict(name="Rhodiola Extract", standard_name="Rhodiola",
                    canonical_id="rhodiola", form="Rhodiola Root Extract", quantity=600)
    better = _botanical_ingredient(**rhodiola, bio_score=12)
    retired_only = _botanical_ingredient(**rhodiola, score=12)

    product = _botanical_product(current)
    product["ingredient_quality_data"]["ingredients_scorable"] = [current, better]
    product["ingredient_quality_data"]["ingredients"] = [current, better]
    assert _primary_botanical_active(product)["canonical_id"] == "rhodiola"

    product["ingredient_quality_data"]["ingredients_scorable"] = [retired_only, current]
    product["ingredient_quality_data"]["ingredients"] = [retired_only, current]
    assert _primary_botanical_active(product)["canonical_id"] == "ashwagandha"


def test_completed_no_benchmark_accepts_printed_volume_without_inventing_mass():
    row = _botanical_ingredient(quantity=0.2, unit="mL")
    assert _mass_mg(row) is None
    result = score_botanical_dose(_botanical_product(ingredient=row))
    assert result["band"] == "disclosed_no_reference"
    assert result["score"] == _neutral()


def test_disclosed_volume_does_not_complete_unresolved_benchmark(monkeypatch):
    import scoring_v4.modules.botanical_profile as owner
    monkeypatch.setattr(owner, "_botanical_benchmark", lambda row: "unresolved")
    row = _botanical_ingredient(quantity=0.2, unit="mL")
    result = score_botanical_dose(_botanical_product(ingredient=row))
    assert result["score"] == 0
    assert result["metadata"]["benchmark"] == "unresolved"


def test_printed_botanical_volume_reaches_public_dose_pillar():
    from scoring_v4.scored_artifact import build_scored_artifact
    product = _botanical_product(ingredient=_botanical_ingredient(quantity=0.2, unit="mL"))
    artifact = build_scored_artifact(product)
    dose = artifact["quality_pillars_v4"]["dose"]
    assert dose["score"] == 11.4
    assert "no amount" not in " ".join(dose.get("reasons", [])).lower()


def test_exact_printed_zero_is_disclosure_without_positive_neutral_credit():
    row = _botanical_ingredient(quantity=0, unit="mg", raw_source_path="ingredientRows[0]",
        raw_taxonomy={"category": "botanical", "quantityVariants": [{
            "quantity": 0, "unit": "mg", "selected_for_analysis": True, "quantity_parsed": True}]})
    from scoring_input_contract import dose_disclosure_status
    assert dose_disclosure_status(row) == "disclosed"
    assert score_botanical_dose(_botanical_product(ingredient=row))["score"] == 0


@pytest.mark.parametrize("quantity", [-0.2, 0, None, float("nan")])
def test_stale_disclosure_flag_does_not_turn_invalid_volume_into_neutral(quantity):
    row = _botanical_ingredient(quantity=quantity, unit="mL", has_dose=True)
    assert score_botanical_dose(_botanical_product(ingredient=row))["score"] == 0


def test_canonical_botanical_identity_survives_raw_blend_parent():
    from scoring_v4.scored_artifact import build_scored_artifact
    row = _botanical_ingredient(
        name="Neumentix Phenolic Complex K110-42", standard_name="Spearmint",
        canonical_id="spearmint", quantity=900, matched_form="neumentix spearmint extract",
        scoreable_identity=True, identity_confidence=1.0,
        raw_source_path="ingredientRows[0]", canonical_source_db="ingredient_quality_map",
        raw_taxonomy={"category": "blend", "ingredientGroup": "Proprietary Blend (Herb/Botanical)",
                      "forms": [{"name": "Spearmint extract", "category": "botanical"}]},
    )
    product = _botanical_product(row, standardized=False)
    product["product_name"] = "Neumentix"
    owner = _primary_botanical_active(product)
    assert owner["_scoring_classification"]["profile_eligibility"]["botanical"]["eligible"] is True
    artifact = build_scored_artifact(product)
    formulation = artifact["quality_pillars_v4"]["formulation"]
    assert score_botanical_formulation(product)["metadata"]["recognized"] is True
    assert formulation["score"] > 0
    assert "weak_or_unidentified_botanical" not in str(formulation)


@pytest.mark.parametrize("scoreable, eligible, canonical", [
    (False, True, "spearmint"), (True, False, "spearmint"),
    (True, True, ""), (True, True, "blend_unknown"),
])
def test_botanical_profile_evidence_does_not_replace_strict_identity(scoreable, eligible, canonical):
    from scoring_v4.modules.botanical_profile import _recognized_botanical_identity
    row = {"canonical_id": canonical, "category": "herbs", "scoreable_identity": scoreable,
           "raw_taxonomy": {"category": "blend"},
           "_scoring_classification": {"profile_eligibility": {"botanical": {"eligible": eligible}}}}
    assert _recognized_botanical_identity(row) is False


def test_recognized_identity_without_benchmark_review_stays_unfinished(monkeypatch):
    """Identity recognition cannot certify that a benchmark search completed."""
    import scoring_v4.modules.botanical_profile as owner
    import evidence_resolver
    monkeypatch.setattr(owner, "_dosing_entry_for", lambda row: None)
    monkeypatch.setattr(evidence_resolver, "_load_literature_evidence", lambda: {})
    product = _botanical_product()
    assert owner._recognized_botanical_identity(_primary_botanical_active(product)) is True
    from scoring_v4.scored_artifact import build_scored_artifact
    artifact = build_scored_artifact(product)
    assert score_botanical_dose(product)["metadata"]["benchmark"] == "unresolved"
    assert artifact["quality_pillars_v4"]["dose"]["score"] == 0
    assert artifact["quality_assessment_status"] == "partial"


def test_neumentix_review_completes_general_threshold_without_borrowing_spearmint_tea():
    from scoring_v4.modules.botanical_profile import _botanical_benchmark, _dosing_entry_for
    row = {'canonical_id': 'spearmint', 'standard_name': 'Spearmint',
           'name': 'Neumentix Phenolic Complex K110-42', 'matched_form': 'neumentix spearmint extract'}
    entry = _dosing_entry_for(row)
    assert entry is not None
    assert entry['id'] == 'neumentix_spearmint_extract'
    assert entry['reference_semantics']['reference_type'] == 'no_benchmark'
    assert entry['references'] == ['29314866']
    assert _botanical_benchmark(row) == 'absent'
    assert not entry.get('typical_dosing_range')
    assert not entry.get('upper_limit')
    for generic in [
        {'canonical_id': 'spearmint', 'name': 'Spearmint tea', 'matched_form': 'spearmint (unspecified)'},
        {'canonical_id': 'spearmint', 'name': 'Spearmint extract', 'matched_form': 'spearmint extract'},
    ]:
        # Generic spearmint now has its own completed neutral reference.
        # It borrows neither Neumentix's study nor the tea's printed regimen.
        assert _botanical_benchmark(generic) == 'absent'
        assert _dosing_entry_for(generic) is None


def test_exact_preparation_review_does_not_override_conflicting_botanical_identity():
    row = _botanical_ingredient(
        name="Neumentix Phenolic Complex K110-42", standard_name="Rosemary",
        canonical_id="rosemary", quantity=900, matched_form="neumentix spearmint extract",
        scoreable_identity=False, identity_disposition="identity_conflict",
    )
    from scoring_v4.modules.botanical_profile import _recognized_botanical_identity
    assert _recognized_botanical_identity(row) is False
    assert score_botanical_dose(_botanical_product(row))["score"] == 0


@pytest.mark.parametrize("flags,expected", [
    ({"scoreable_identity": False}, False),
    ({"scoreable_identity": True, "identity_disposition": "identity_conflict"}, False),
    ({"identity_disposition": "identity_conflict"}, False),
    ({}, True),
])
def test_known_botanical_fallback_respects_explicit_identity_veto(flags, expected):
    from scoring_v4.modules.botanical_profile import _recognized_botanical_identity
    row = {"canonical_id": "rosemary", "name": "Rosemary", **flags}
    assert _recognized_botanical_identity(row) is expected


@pytest.mark.parametrize("shape", ["nested_hidden", "source_owned_lent_mass"])
def test_known_botanical_hidden_amount_completes_without_claiming_benchmark(shape):
    row = _botanical_ingredient(name="Green Bell Pepper", standard_name="Green Bell Pepper",
                                canonical_id="green_bell_pepper", form="Green Bell Pepper",
                                quantity=0, unit="NP", isNestedIngredient=True)
    if shape == "source_owned_lent_mass":
        row.update(quantity=1660, unit="mg", isNestedIngredient=False,
                   scoring_input_kind="product_level_evidence", evidence_type="blend_anchor_mass",
                   reason="identity_bearing_blend_header_mass_from_nested_child")
    result = score_botanical_dose(_botanical_product(ingredient=row, standardized=False))
    assert result["score"] == _neutral()
    assert result["metadata"]["benchmark"] == "unresolved"
    assert result["metadata"]["assessment_status"] == "complete"
    assert result["metadata"]["reason_code"] == "amount_not_declared"


@pytest.mark.parametrize("change", ["unknown_identity", "identity_rejected", "identity_conflict",
                                    "capture_missing", "unproved_projection", "disclosed"])
def test_hidden_amount_completion_does_not_waive_owner_gaps(change):
    row = _botanical_ingredient(name="Green Bell Pepper", standard_name="Green Bell Pepper",
                                canonical_id="green_bell_pepper", form="Green Bell Pepper",
                                quantity=0, unit="NP", isNestedIngredient=True)
    if change == "unknown_identity":
        row.update(name="Unreviewed Novel Herb", standard_name="Unreviewed Novel Herb",
                   canonical_id="unreviewed_novel_herb", matched_form="Unreviewed Novel Herb",
                   raw_taxonomy={"category": "botanical", "forms": []})
    elif change == "identity_rejected":
        row["scoreable_identity"] = False
    elif change == "identity_conflict":
        row["identity_disposition"] = "identity_conflict"
    elif change == "capture_missing":
        row["isNestedIngredient"] = False
    elif change == "unproved_projection":
        row.update(quantity=1660, unit="mg", isNestedIngredient=False,
                   scoring_input_kind="product_level_evidence", evidence_type="blend_anchor_mass",
                   reason="identity_bearing_active_anchor_mass")
    else:
        row.update(quantity=100, unit="mg", isNestedIngredient=False)
    result = score_botanical_dose(_botanical_product(ingredient=row, standardized=False))
    assert result["score"] == 0
    assert result["metadata"]["benchmark"] == "unresolved"
    assert result["metadata"].get("assessment_status") != "complete"


@pytest.mark.parametrize("change", [None, "conflict", "unmapped", "capture", "excluded"])
def test_known_hidden_source_identity_is_not_rejected_for_missing_dose(change):
    from scoring_v4.modules.botanical_profile import score_botanical_purpose_dose

    row = _botanical_ingredient(
        name="Acai fruit powder", standard_name="Acai Berry", canonical_id="acai_berry",
        quantity=0, unit="unspecified", scoreable_identity=False, mapped_identity=True,
        identity_disposition="clean", identity_taxonomy_coherent=True,
        identity_decision_reason="no_dose_evidence", cleaner_row_role="active_scorable",
        score_eligible_by_cleaner=True, score_exclusion_reason="recognized_non_scorable",
        parent_blend="Proprietary Fruit & Vegetable Blend", parent_blend_mass_mg=105,
        raw_source_path="ingredientRows[21].forms[0]",
    )
    if change == "conflict":
        row["identity_disposition"] = "identity_conflict"
    elif change == "unmapped":
        row["mapped_identity"] = False
    elif change == "capture":
        row.pop("parent_blend")
        row.pop("parent_blend_mass_mg")
    elif change == "excluded":
        row["cleaner_row_role"] = "nested_display_only"
        row["score_eligible_by_cleaner"] = False
    result = score_botanical_purpose_dose(_botanical_product(row), row)
    if change is None:
        assert result["score"] == _neutral()
        assert result["metadata"]["reason_code"] == "amount_not_declared"
        assert result["metadata"]["assessment_status"] == "complete"
        assert row["quantity"] == 0
    else:
        assert result["score"] == 0
        assert result["metadata"].get("assessment_status") != "complete"


@pytest.mark.parametrize('canonical', [
    'citrus_bioflavonoids', 'cayenne_pepper', 'pomegranate', 'hops', 'stinging_nettle',
    'acai_berry', 'mucuna_pruriens', 'goji_berry', 'cat_s_claw', 'tart_cherry',
    'peppermint', 'spearmint', 'magnolia_bark', 'shiitake', 'dark_sweet_cherry',
    'african_mango', 'olive_fruit_extract', 'turkey_tail', 'arjuna', 'piperine',
    'capsaicin',
    'blueberry', 'garcinia_cambogia', 'green_coffee_bean', 'pumpkin',
    'broccoli', 'rose_hips', 'dandelion', 'horsetail',
    'ginger_extract', 'apple_cider_vinegar', 'goldenseal', 'guarana',
    'tribulus', 'olive_leaf_powder', 'licorice', 'gotu_kola',
    'rosemary', 'fennel', 'globe_artichoke', 'uva_ursi_leaf',
    'dong_quai', 'marshmallow_root', 'white_willow_bark', 'hawthorn',
    'oat_straw', 'lions_mane', 'butterbur', 'red_clover',
    'blood_orange_extract', 'black_tea_leaf', 'siberian_ginseng', 'feverfew',
    'oregano', 'barberry_root', 'wild_yam_root', 'maitake',
    'hoodia_gordonii', 'butchers_broom_root', 'cranberry_fruit', 'chicory_root',
    'hibiscus_extract', 'nopal', 'celery_seed', 'moringa',
    'horse_chestnut_seed', 'yerba_mate_leaf', 'coffee_fruit', 'caralluma',
    'picrorhiza', 'winged_treebine', 'olive_fruit', 'jujube',
    'oolong_tea_leaf', 'turkey_rhubarb_root', 'broccoli_sprout', 'puerarin',
    'cocoa', 'citrus_bergamot', 'coleus_forskohlii_root', 'black_garlic',
    'english_ivy', 'cloves', 'guggul', 'mastic_gum',
    'dgl_deglycyrrhizinated_licorice', 'shiitake_mushroom', 'ashwagandha_root', 'siberian_rhubarb',
    'maqui_berry', 'matcha_tea_powder', 'nha_univestin', 'triphala_powder',
    'nha_monk_fruit', 'nha_stevia', 'nha_raspberry_natural', 'oi_natural_strawberry_flavor',
    'nha_pomegranate_juice', 'nha_apple_puree_concentrate', 'red_clover_flower', 'butternut_squash_seed_oil',
    'chinese_wolfberry_fruit', 'nettle_root',
    'avocado_oil', 'black_cherry', 'blessed_thistle', 'buckthorn_bark', 'cnidium',
    'fadogia_agrestis', 'fo_ti', 'frangula', 'galla_chinensis', 'hydrangea_root',
    'hyssop', 'irish_sea_moss', 'mulberry_mistletoe', 'nha_bladderwrack',
    'nha_hemp_extract', 'nobiletin', 'okra_fruit', 'purple_corn_extract', 'radish',
    'sarsaparilla', 'sweet_wormwood_herb', 'yellow_dock_root',
])
def test_completed_source_specific_review_does_not_require_an_invented_general_dose_curve(canonical):
    from evidence_resolver import _load_literature_evidence
    from scoring_v4.modules.botanical_profile import _botanical_benchmark

    record = _load_literature_evidence()[canonical]
    semantics = record['reference_semantics']
    assert semantics['curve'] == 'completed_no_benchmark_neutral'
    assert semantics['source_ids']
    assert semantics['owner'] == f"scripts/data/literature_evidence_records.json::{record['canonical_id']}"
    assert _botanical_benchmark({'canonical_id': canonical, 'name': canonical}) == 'absent'


@pytest.mark.parametrize('kind,band', [('label_active_projection', 'disclosed_no_reference'),
                                      ('product_level_evidence', 'blend_total_only')])
def test_direct_label_active_projection_is_not_a_hidden_blend_total(kind, band):
    from scoring_v4.modules.botanical_profile import score_botanical_purpose_dose
    row = _botanical_ingredient(
        name='Cranberry Concentrate', standard_name='Cranberry', canonical_id='cranberry',
        quantity=400, scoreable_identity=True, scoring_input_kind=kind,
        evidence_type='blend_anchor_mass', evidence_scope='row_level',
        reason='identity_bearing_active_anchor_mass', raw_source_path='ingredientRows[0]',
        _scoring_classification={'profile_eligibility': {'botanical': {'eligible': True}}},
    )
    result = score_botanical_purpose_dose(_botanical_product(row), row)
    assert result['band'] == band
    assert row['quantity'] == 400
    assert result['metadata'].get('reason_code') != 'amount_not_declared'


@pytest.mark.parametrize('canonical,name,owner', [
    ('sytrinol', 'Sytrinol', 'BRAND_SYTRINOL'),
    ('tesnor_pomegranate_cocoa_blend', 'Tesnor Pomegranate Cocoa Blend', 'BRAND_TESNOR'),
])
def test_exact_branded_dose_uses_existing_reviewed_reference_without_component_transfer(canonical, name, owner):
    from scoring_v4.modules.botanical_profile import _dosing_entry_for, _botanical_benchmark
    row = _botanical_ingredient(name=name, standard_name=name, canonical_id=canonical)
    assert _dosing_entry_for(row)['id'] == owner
    assert _botanical_benchmark(row) == 'absent'
    child = _botanical_ingredient(name='Pomegranate peel extract', standard_name='Pomegranate',
                                  canonical_id='pomegranate')
    assert _dosing_entry_for(child) is None
    child['matched_form'] = name
    assert _dosing_entry_for(child) is None


def test_literature_dose_requires_its_own_content_bound_source_proof(monkeypatch):
    import copy
    from evidence_resolver import _load_literature_evidence
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    record = copy.deepcopy(_load_literature_evidence()['spearmint'])
    record.get('verification_provenance', {}).pop('reference_citations', None)
    monkeypatch.setattr('evidence_resolver._load_literature_evidence', lambda: {'spearmint': record})
    row = {'canonical_id': 'spearmint', 'name': 'spearmint'}
    assert _botanical_benchmark(row) == 'unresolved'


def test_backed_dose_proof_cannot_be_replaced_by_evidence_verification(monkeypatch):
    import copy
    from evidence_resolver import _backed_studies_index
    from scoring_v4.modules import botanical_profile as profile
    record = copy.deepcopy(next(r for r in _backed_studies_index()['sytrinol'] if r['id'] == 'BRAND_SYTRINOL'))
    record['verification_provenance'].pop('reference_citations', None)
    monkeypatch.setattr(profile, '_dosing_entry_for', lambda row: record)
    assert profile._botanical_benchmark({'canonical_id': 'sytrinol'}) == 'unresolved'


def test_backed_reference_owner_corruption_cannot_bypass_dose_proof(monkeypatch):
    import copy
    from evidence_resolver import _backed_studies_index
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    record = copy.deepcopy(next(r for r in _backed_studies_index()['sytrinol'] if r['id'] == 'BRAND_SYTRINOL'))
    record['reference_semantics'].pop('owner')
    monkeypatch.setattr('evidence_resolver._backed_studies_index', lambda: {'sytrinol': [record]})
    assert _botanical_benchmark({'canonical_id': 'sytrinol', 'name': 'Sytrinol'}) == 'unresolved'
