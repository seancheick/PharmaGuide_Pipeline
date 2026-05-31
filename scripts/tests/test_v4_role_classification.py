"""V4 Phase 2 — ingredient role classification (compatibility mode).

Tests the deterministic, scoring-time `classify_ingredient_roles()` contract.
Phase 2 CLASSIFIES ONLY — it must not change any score, cap, or verdict.

Design spec: docs/superpowers/specs/2026-05-31-v4-role-classification-design.md

Level -> role map (user-approved Option 1):
  L1 drives module        -> primary
  L2 named in title       -> claim_prominent  (role_source=product_name)
  L3 front-label claim    -> INERT (no data source; never emit a claim reason)
  L4 required for subtype -> major  (multi micronutrient panel)
  L5 high comparable mass -> major
  L6 otherwise            -> adjunct
"""
from __future__ import annotations

from scoring_input_contract import classify_ingredient_roles  # noqa: E402


def _row(canonical, name, quantity, unit, **extra):
    row = {"canonical_id": canonical, "name": name, "quantity": quantity, "unit": unit}
    row.update(extra)
    return row


def _product(name, primary_type, rows):
    return {
        "product_name": name,
        "primary_type": primary_type,
        "ingredient_quality_data": {"ingredients_scorable": rows},
    }


def _by_canonical(product, module=None):
    return {r["canonical_id"]: r for r in classify_ingredient_roles(product, module=module)}


def test_omega_epa_dha_are_primary_drivers():
    product = _product("Triple Strength Fish Oil", "omega_3", [
        _row("epa", "EPA", 600, "mg"),
        _row("dha", "DHA", 400, "mg"),
        _row("vitamin_e", "Vitamin E", 10, "mg"),
    ])
    roles = _by_canonical(product, module="omega")
    assert roles["epa"]["role"] == "primary"
    assert roles["dha"]["role"] == "primary"
    assert roles["epa"]["role_source"] == "router_driver"
    assert roles["vitamin_e"]["role"] == "adjunct"


def test_sports_protein_is_primary_flavor_is_adjunct():
    product = _product("Whey Protein Isolate Chocolate", "protein_powder", [
        _row("whey_protein", "Whey Protein Isolate", 25, "g"),
        _row("sucralose", "Sucralose", 50, "mg"),
    ])
    roles = _by_canonical(product, module="sports")
    assert roles["whey_protein"]["role"] == "primary"
    assert roles["sucralose"]["role"] == "adjunct"


def test_botanical_named_in_title_is_claim_prominent():
    product = _product("Organic Ashwagandha Extract", "herbal_botanical", [
        _row("ashwagandha", "Ashwagandha Root Extract", 600, "mg"),
        _row("black_pepper", "Black Pepper Extract", 5, "mg"),
    ])
    roles = _by_canonical(product, module="generic")
    ashwa = roles["ashwagandha"]
    assert ashwa["role"] == "claim_prominent"
    assert ashwa["role_reason"] == "named_in_product_title"
    assert ashwa["role_source"] == "product_name"
    assert roles["black_pepper"]["role"] == "adjunct"


def test_melatonin_small_mass_is_not_demoted_to_adjunct():
    # The "NOT raw mass first" rule: a 1 mg title-named active outranks a
    # 500 mg non-featured filler. Title (L2) precedes mass (L5).
    product = _product("Melatonin 1 mg", "sleep_support", [
        _row("melatonin", "Melatonin", 1, "mg"),
        _row("rice_flour", "Rice Flour", 500, "mg"),
    ])
    roles = _by_canonical(product, module="generic")
    assert roles["melatonin"]["role"] == "claim_prominent"
    assert roles["melatonin"]["role"] != "adjunct"
    assert roles["rice_flour"]["role"] == "major"


def test_multi_panel_micronutrients_major_tiny_blend_adjunct():
    product = _product("Daily Multivitamin", "multivitamin", [
        _row("vitamin_c_ascorbic_acid", "Vitamin C", 90, "mg"),
        _row("vitamin_d", "Vitamin D3", 25, "mcg"),  # tiny mass but core panel
        _row("green_tea_extract", "Green Tea Extract", 5, "mg", is_proprietary_blend=True),
    ])
    roles = _by_canonical(product, module="multi_or_prenatal")
    assert roles["vitamin_c_ascorbic_acid"]["role"] == "major"
    assert roles["vitamin_d"]["role"] == "major"  # 25 mcg not demoted by mass
    assert roles["green_tea_extract"]["role"] == "adjunct"


def test_multi_adjunct_probiotic_is_adjunct_not_capping():
    product = _product("Women's Multivitamin", "multivitamin", [
        _row("vitamin_c_ascorbic_acid", "Vitamin C", 90, "mg"),
        _row("lactobacillus_acidophilus", "Lactobacillus acidophilus", 5,
             "billion cfu", dose_class="probiotic_cfu"),
    ])
    roles = _by_canonical(product, module="multi_or_prenatal")
    assert roles["vitamin_c_ascorbic_acid"]["role"] == "major"
    # Probiotic add-on in a multi must be adjunct so Phase 3 does NOT cap the
    # whole multivitamin for missing CFU.
    assert roles["lactobacillus_acidophilus"]["role"] == "adjunct"


def test_provenance_contract_complete_and_no_fake_claims():
    product = _product("Organic Ashwagandha Extract", "herbal_botanical", [
        _row("ashwagandha", "Ashwagandha", 600, "mg"),
        _row("black_pepper", "Black Pepper", 5, "mg"),
    ])
    roles = classify_ingredient_roles(product, module="generic")
    assert roles
    required = {"canonical_id", "role", "role_reason", "role_source", "role_confidence"}
    for r in roles:
        assert required.issubset(r), f"missing provenance keys: {r}"
        assert r["role"] in {"primary", "claim_prominent", "major", "adjunct"}
        assert r["role_confidence"] in {"high", "medium", "low"}
        # Honest provenance: never fabricate a front-label-claim signal.
        assert r["role_reason"] != "front_label_claim"
        assert r["role_source"] != "front_label_claim"


def test_classification_is_deterministic():
    product = _product("Triple Strength Fish Oil", "omega_3", [
        _row("epa", "EPA", 600, "mg"),
        _row("dha", "DHA", 400, "mg"),
    ])
    first = classify_ingredient_roles(product, module="omega")
    second = classify_ingredient_roles(product, module="omega")
    assert first == second


def test_module_autodetected_via_router_when_not_passed():
    product = _product("Triple Strength Fish Oil", "omega_3", [
        _row("epa", "EPA", 600, "mg"),
        _row("dha", "DHA", 400, "mg"),
    ])
    roles = _by_canonical(product)  # module=None -> router class_for_product
    assert roles["epa"]["role"] == "primary"


# --- Code-review fixes (REVIEW_phase2.md) -----------------------------------

def test_title_match_is_whole_word_not_substring():
    # CR-01: "iron" must NOT match because it is a substring of "Environmental".
    # A trace mineral matching mid-word would mis-cap the product in Phase 3.
    product = _product("Environmental Greens Formula", "greens_powder", [
        _row("greens_blend", "Organic Greens Blend", 1000, "mg"),
        _row("iron", "Iron", 5, "mg"),
    ])
    roles = _by_canonical(product, module="generic")
    assert roles["iron"]["role"] != "claim_prominent"
    assert roles["iron"]["role"] == "adjunct"


def test_omega_parent_canonical_is_primary():
    # WR-01: fish-oil/krill parents route a product to the omega module, so a
    # parent-only row is the module driver and must be primary.
    product = _product("Fish Oil 1000 mg", "omega_3", [
        _row("fish_oil", "Fish Oil", 1000, "mg"),
    ])
    roles = _by_canonical(product, module="omega")
    assert roles["fish_oil"]["role"] == "primary"


def test_module_driver_without_dose_is_still_primary():
    # WR-02 (pinned): drivers are primary even when dose is absent. Phase 3 owns
    # the missing-primary-dose cap, so the role must still surface the driver.
    product = _product("Algae DHA", "omega_3", [
        {"canonical_id": "dha", "name": "DHA", "has_dose": True},
    ])
    roles = _by_canonical(product, module="omega")
    assert roles["dha"]["role"] == "primary"


def test_duplicate_canonical_yields_one_role_per_row():
    # WR-05: classifier returns one dict per scoring row (no collapse).
    product = _product("Magnesium Complex", "single_mineral", [
        _row("magnesium", "Magnesium Glycinate", 200, "mg"),
        _row("magnesium", "Magnesium Citrate", 100, "mg"),
    ])
    roles = classify_ingredient_roles(product, module="generic")
    assert len(roles) == 2
