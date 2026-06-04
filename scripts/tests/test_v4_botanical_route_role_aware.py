"""V4 route-drift fix — role-aware botanical subprofile selector.

`is_botanical_product()` (the generic module's botanical subprofile selector, used
by BOTH generic_dose.py and generic_formulation.py) previously routed on raw
mass-dominance: any botanical active that out-massed the non-botanicals sent the
WHOLE product through the botanical formulation + dose adapters.

That let a mass-heavy botanical ADJUNCT hijack a product whose actual marketed
active is non-botanical (melatonin 3 mg hijacked by passion flower 100 mg+; zinc by
elderberry; iron by eleuthero). Same ingredient -> different dose logic across
products = route drift.

Policy (user-approved):
  - non-botanical active is primary/claim_prominent AND botanical is only
    major/adjunct  -> NOT the botanical profile
  - botanical is title-prominent  -> keep botanical profile only when material
  - tied title-prominent actives  -> grammar title-head wins, but botanical must be material
  - enzyme-product intent         -> generic/enzyme path, not botanical
  - roles absent                  -> fall back to the existing mass-dominance rule

Corpus scope at write time: 2183 botanical-routed products, 252 (11.5%) had a
non-botanical role-primary (the hijack). Fixtures below are the canonical patterns.
"""
from __future__ import annotations

from scoring_input_contract import classify_ingredient_roles
from scoring_v4.modules.botanical_profile import is_botanical_product

PRIMARY_ROLES = {"primary", "claim_prominent"}


def _row(canonical, name, quantity, unit, *, botanical=False, **extra):
    row = {"canonical_id": canonical, "name": name, "quantity": quantity, "unit": unit}
    if botanical:
        row["raw_taxonomy"] = {"category": "botanical"}
    row.update(extra)
    return row


def _product(name, rows, primary_type="general_supplement"):
    return {
        "product_name": name,
        "primary_type": primary_type,
        "ingredient_quality_data": {"ingredients_scorable": rows},
    }


def _roles(product):
    return {r["canonical_id"]: r["role"] for r in classify_ingredient_roles(product)}


# --- hijack cases: non-botanical hero, mass-heavy botanical adjunct -> NOT botanical

def test_melatonin_hero_passionflower_adjunct_is_not_botanical():
    p = _product("Melatonin 3 mg Sugar Free", [
        _row("melatonin", "Melatonin", 3, "mg"),
        _row("passion_flower", "Passion Flower Extract", 200, "mg", botanical=True),
    ])
    roles = _roles(p)
    assert roles["melatonin"] in PRIMARY_ROLES          # title hero
    assert roles["passion_flower"] not in PRIMARY_ROLES  # mass-heavy adjunct
    assert is_botanical_product(p) is False


def test_zinc_hero_elderberry_adjunct_is_not_botanical():
    p = _product("Zinc Lozenges with Elderberry", [
        _row("zinc", "Zinc", 15, "mg"),
        _row("elderberry", "Elderberry Extract", 100, "mg", botanical=True),
    ])
    roles = _roles(p)
    assert roles["zinc"] in PRIMARY_ROLES
    assert is_botanical_product(p) is False


def test_iron_hero_eleuthero_adjunct_is_not_botanical():
    p = _product("Iron with Eleuthero", [
        _row("iron", "Iron", 18, "mg"),
        _row("eleuthero", "Eleuthero Root Extract", 250, "mg", botanical=True),
    ])
    roles = _roles(p)
    assert roles["iron"] in PRIMARY_ROLES
    assert is_botanical_product(p) is False


# --- legit botanical cases: botanical is the hero -> stays botanical

def test_botanical_hero_with_trace_mineral_stays_botanical():
    p = _product("Turmeric Curcumin Extract", [
        _row("turmeric", "Turmeric Extract", 500, "mg", botanical=True),
        _row("zinc", "Zinc", 2, "mg"),
    ])
    roles = _roles(p)
    assert roles["turmeric"] in PRIMARY_ROLES
    assert is_botanical_product(p) is True


def test_botanical_title_with_vitamin_adjunct_stays_botanical():
    p = _product("Echinacea with Vitamin C", [
        _row("echinacea", "Echinacea Extract", 400, "mg", botanical=True),
        _row("vitamin_c", "Vitamin C", 60, "mg"),
    ])
    roles = _roles(p)
    assert roles["echinacea"] in PRIMARY_ROLES
    assert is_botanical_product(p) is True


def test_botanical_hero_outmassed_by_mineral_still_botanical():
    """A title-prominent botanical can own the route when still material.

    Ashwagandha is slightly smaller than magnesium here, but it is still a
    clinically material amount (> half the magnesium mass), so the product keeps
    the botanical profile.
    """
    p = _product("Ashwagandha with Magnesium", [
        _row("ashwagandha", "Ashwagandha Root Extract", 300, "mg", botanical=True),
        _row("magnesium", "Magnesium", 400, "mg"),
    ])
    roles = _roles(p)
    assert roles["ashwagandha"] in PRIMARY_ROLES
    assert is_botanical_product(p) is True


def test_trace_botanical_title_theme_does_not_hijack_enzyme_product():
    """Papaya Enzyme-style labels are enzyme products, not botanical products.

    A trace botanical title token must not pull a larger enzyme panel into the
    botanical profile; the generic/enzyme dose logic is the safer route.
    """
    p = _product("Papaya Enzyme", [
        _row("papaya", "Papaya", 15, "mg", botanical=True),
        _row("papain", "Papain", 90, "mg"),
        _row("bromelain", "Bromelain", 80, "mg"),
    ])
    roles = _roles(p)
    assert roles["papaya"] in PRIMARY_ROLES
    assert is_botanical_product(p) is False


def test_papaya_enzyme_title_uses_enzyme_not_botanical_profile_even_when_papaya_mass_dominates():
    """Real GNC-style pattern: papaya powder is heavier, but the product is an enzyme."""
    p = _product("Papaya Enzyme", [
        _row("papaya", "Papaya fruit powder", 45, "mg", botanical=True),
        _row(
            "digestive_enzymes",
            "Papain",
            6,
            "mg",
            raw_taxonomy={"category": "enzyme"},
        ),
    ], primary_type="fiber_digestive")
    roles = _roles(p)
    assert roles["papaya"] in PRIMARY_ROLES
    assert is_botanical_product(p) is False


def test_tocotrienols_title_marks_vitamin_e_as_nonbotanical_hero():
    """Tocotrienols are a vitamin E surface form; sesame lignans should not win."""
    p = _product("Tocotrienols With Sesame Lignans", [
        _row("vitamin_e", "Vitamin E", 50, "mg"),
        _row("sesame_lignans", "Sesame Lignans", 10, "mg", botanical=True),
    ])
    roles = _roles(p)
    assert roles["vitamin_e"] in PRIMARY_ROLES
    assert roles["sesame_lignans"] in PRIMARY_ROLES
    assert is_botanical_product(p) is False


def test_l_theanine_single_uses_generic_not_botanical_profile():
    """L-theanine has a companion active-compound entry in botanical data, but
    IQM/DSLD classify it as an amino acid/non-botanical. The botanical adapter
    must not cap its formulation below the generic bio path."""
    p = _product("L-Theanine 200 mg", [
        _row(
            "l_theanine",
            "L-Theanine",
            200,
            "mg",
            category="amino_acids",
            raw_taxonomy={"category": "non-nutrient/non-botanical"},
        ),
    ])
    assert is_botanical_product(p) is False


def test_phosphatidylserine_single_uses_generic_not_botanical_profile():
    """Phosphatidylserine is a phospholipid/fatty-acid active, not an herb."""
    p = _product("Phosphatidylserine 100 mg", [
        _row(
            "phosphatidylserine",
            "Sharp-PS Green Phosphatidylserine",
            100,
            "mg",
            category="fatty_acids",
            raw_taxonomy={"category": "fat"},
        ),
    ])
    assert is_botanical_product(p) is False


def test_source_botanical_antioxidant_still_uses_botanical_profile():
    """Plant-derived active compounds such as curcumin/quercetin remain
    botanical when the row carries an herbal category or botanical source form."""
    p = _product("Curcumin Phytosome", [
        _row(
            "curcumin",
            "Curcumin Phytosome",
            500,
            "mg",
            category="herbs",
            raw_taxonomy={"category": "non-nutrient/non-botanical"},
        ),
    ])
    assert is_botanical_product(p) is True


def test_isolated_antioxidant_with_botanical_source_form_stays_generic():
    p = _product("Quercetin", [
        _row(
            "quercetin",
            "Quercetin",
            500,
            "mg",
            category="antioxidants",
            raw_taxonomy={
                "category": "non-nutrient/non-botanical",
                "forms": [{"name": "Sophorae japonica", "category": "botanical"}],
            },
        ),
    ])
    assert is_botanical_product(p) is False


def test_antioxidant_without_botanical_source_stays_generic():
    """Setria/glutathione is a fermentation-derived antioxidant, not a
    botanical, even though a companion standardized-entry exists."""
    p = _product("Liposomal Glutathione", [
        _row(
            "glutathione",
            "Setria",
            250,
            "mg",
            category="antioxidants",
            raw_taxonomy={"category": "non-nutrient/non-botanical", "forms": []},
        ),
    ])
    assert is_botanical_product(p) is False


def test_duplicate_canonical_keeps_strongest_role_for_nonbotanical_hero():
    """Duplicate canonical rows must not let a later adjunct erase title ownership."""
    p = _product("Digestive Enzyme with Ginger", [
        _row("digestive_enzymes", "Protease", 20, "mg"),
        _row("digestive_enzymes", "Digestive Enzyme", 20, "mg"),
        _row("digestive_enzymes", "Lipase", 20, "mg"),
        _row("ginger", "Ginger Root Extract", 100, "mg", botanical=True),
    ])
    roles = _roles(p)
    assert roles["digestive_enzymes"] in PRIMARY_ROLES
    assert is_botanical_product(p) is False


# --- fallback: no clear role hero -> existing mass-dominance rule unchanged

# --- tie cases: botanical AND non-botanical both title-prominent -> title head wins

def test_tie_nonbotanical_head_with_separator_is_not_botanical():
    """'Zinc with Elderberry' -> zinc is the head -> not botanical."""
    p = _product("Zinc with Elderberry", [
        _row("zinc", "Zinc", 15, "mg"),
        _row("elderberry", "Elderberry Extract", 100, "mg", botanical=True),
    ])
    roles = _roles(p)
    assert roles["zinc"] in PRIMARY_ROLES and roles["elderberry"] in PRIMARY_ROLES
    assert is_botanical_product(p) is False


def test_tie_botanical_head_with_separator_stays_botanical():
    """'Elderberry with Zinc' -> elderberry is the head -> botanical (reverse order
    of the case above flips the owner)."""
    p = _product("Elderberry with Zinc", [
        _row("elderberry", "Elderberry Extract", 100, "mg", botanical=True),
        _row("zinc", "Zinc", 15, "mg"),
    ])
    roles = _roles(p)
    assert roles["zinc"] in PRIMARY_ROLES and roles["elderberry"] in PRIMARY_ROLES
    assert is_botanical_product(p) is True


def test_tie_ampersand_separator_botanical_head_stays_botanical():
    p = _product("Elderberry & Zinc Immune", [
        _row("elderberry", "Elderberry Extract", 100, "mg", botanical=True),
        _row("zinc", "Zinc", 15, "mg"),
    ])
    assert is_botanical_product(p) is True


def test_tie_no_separator_earliest_named_botanical_wins():
    """'Sambucus Elderberry Zinc' has no separator -> earliest-named ingredient
    (elderberry) owns -> botanical."""
    p = _product("Sambucus Elderberry Zinc", [
        _row("elderberry", "Elderberry Extract", 100, "mg", botanical=True),
        _row("zinc", "Zinc", 15, "mg"),
    ])
    assert is_botanical_product(p) is True


def test_no_title_hero_falls_back_to_mass_dominance():
    """Generic title naming no ingredient; neither side is a role hero. The
    mass-dominant botanical keeps the product on the botanical path (legacy rule)."""
    p = _product("Sleep Complex", [
        _row("melatonin", "Melatonin", 3, "mg"),
        _row("passion_flower", "Passion Flower Extract", 200, "mg", botanical=True),
    ])
    roles = _roles(p)
    assert roles["melatonin"] not in PRIMARY_ROLES   # not named in this title
    assert roles["passion_flower"] not in PRIMARY_ROLES
    assert is_botanical_product(p) is True            # mass fallback preserved
