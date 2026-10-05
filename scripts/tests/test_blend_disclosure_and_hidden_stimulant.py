"""Every blend carries its 21 CFR 101.36 disclosure tier; hidden-stimulant caution needs materiality.

942 shipped blends left Enrich with disclosure_level null (flattened children under a parent
the cleaner did not flag). Consumers read null differently: Transparency treated 39 fully
quantified blends as hidden, while the safety gate skipped the rest. The tier now comes from
one rule (proprietary_blend_detector.disclosure_tier) for detector, cleaner and enricher.

Sean, 2026-10-04: disclosure and stimulant materiality are separate facts. An explicit stimulant
identity hidden in a partial/none blend triggers the caution; a caffeine-source botanical
triggers it only when the printed blend total cannot rule out a dose above the existing
STIMULANT_CAFFEINE_HIGH_DOSE line.
"""

import copy
import json
from pathlib import Path

import pytest

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3
from proprietary_blend_detector import disclosure_tier
from scoring_v4.gate_safety import _has_undisclosed_stimulant_blend
from scoring_v4.scored_artifact import build_scored_artifact

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.mark.parametrize("total,with_amounts,without_amounts,expected", [
    (True, 2, 0, "full"),
    (False, 2, 0, "full"),
    (True, 0, 3, "partial"),
    (True, 1, 2, "partial"),
    (False, 0, 3, "none"),
    (False, 1, 1, "none"),
    (True, 0, 0, "none"),
    (False, 0, 0, "none"),
    (False, 0, 1, "none"),
    (True, 0, 1, "partial"),
])
def test_disclosure_tier_follows_101_36(total, with_amounts, without_amounts, expected):
    assert disclosure_tier(total, with_amounts, without_amounts) == expected


@pytest.mark.parametrize("total,with_amounts,without_amounts,expected", [
    (True, 0, 1, "full"),
    (False, 0, 1, "none"),
    (True, 0, 2, "partial"),
])
def test_one_single_source_component_under_a_printed_total_is_full(total, with_amounts, without_amounts, expected):
    assert disclosure_tier(total, with_amounts, without_amounts, sole_single_source=True) == expected


@pytest.fixture(scope="module")
def pipeline():
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


def _run(pipeline, dsld_id):
    normalizer, enricher = pipeline
    raw = json.loads((FIXTURES / f"blend_disclosure_{dsld_id}_raw.json").read_text())
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(copy.deepcopy(raw)))
    return enriched, build_scored_artifact(enriched)


def _blend(enriched, name):
    return next(b for b in enriched["proprietary_blends"] if b["name"] == name)


@pytest.mark.parametrize("dsld_id", ["289060", "1179", "219842", "247106"])
def test_no_blend_leaves_enrich_without_a_tier(pipeline, dsld_id):
    enriched, _ = _run(pipeline, dsld_id)
    assert {b["disclosure_level"] for b in enriched["proprietary_blends"]} <= {"full", "partial", "none"}


def test_fully_quantified_caffeine_blend_is_full_and_not_hidden(pipeline):
    enriched, scored = _run(pipeline, "219842")
    assert _blend(enriched, "Caffeine Blend")["disclosure_level"] == "full"
    assert "STIMULANT_UNDISCLOSED_BLEND" not in scored["flags"]


def test_explicit_caffeine_hidden_in_partial_blend_is_a_caution(pipeline):
    enriched, scored = _run(pipeline, "1179")
    assert _blend(enriched, "Thermo Energy Intensifier")["disclosure_level"] == "partial"
    assert "STIMULANT_UNDISCLOSED_BLEND" in scored["flags"]
    assert scored["product_safety_status"] == "caution"


def test_tiny_multi_botanical_tea_blend_is_partial_without_stimulant_caution(pipeline):
    enriched, scored = _run(pipeline, "289060")
    assert _blend(enriched, "Stress & Energy Adaptogens (Extracts)")["disclosure_level"] == "partial"
    assert "STIMULANT_UNDISCLOSED_BLEND" not in scored["flags"]


def test_partial_blend_without_stimulant_has_no_stimulant_signal(pipeline):
    enriched, scored = _run(pipeline, "247106")
    assert _blend(enriched, "Organic Vegetables")["disclosure_level"] == "partial"
    assert not [f for f in scored["flags"] if f.startswith("STIMULANT_")]


def _product(name, total_mg, kids, level="partial"):
    return {"proprietary_blends": [{
        "name": name, "disclosure_level": level, "blend_total_mg": total_mg,
        "total_weight": total_mg, "unit": "mg" if total_mg else "",
        "child_ingredients": [{"name": k, "amount": None, "unit": ""} for k in kids],
    }]}


@pytest.mark.parametrize("name,total,kids,expected", [
    ("Energy Blend", 63.0, ["Green Tea extract", "Ginseng"], False),
    ("Energy Blend", 600.0, ["Green Tea extract", "Ginseng"], True),
    ("Energy Blend", None, ["Guarana seed extract"], True),
    ("Antioxidant Blend", 50.0, ["Synephrine HCl", "Grape seed"], True),
    ("Antioxidant Blend", 50.0, ["Caffeine Anhydrous"], True),
    ("Pre-Workout Matrix", 50.0, ["Beta-Alanine"], True),
    ("Antioxidant Blend", 900.0, ["Green Tea extract"], False),
])
def test_hidden_stimulant_needs_identity_or_material_botanical_bound(name, total, kids, expected):
    assert _has_undisclosed_stimulant_blend(_product(name, total, kids)) is expected


def test_fully_disclosed_blend_never_hides_a_stimulant():
    assert _has_undisclosed_stimulant_blend(
        _product("Energy Blend", 600.0, ["Caffeine"], level="full")) is False


def test_child_amount_is_never_the_printed_blend_total():
    """A flattened 'Energy Blend' with no printed total: one quantified child must not become the
    total (it would make the tier partial and bound a hidden guarana at the child's 50 mg)."""
    def child(name, qty, unit, order):
        return {"name": name, "standardName": name, "raw_source_text": name, "order": order,
                "quantity": qty, "unit": unit, "forms": [], "isNestedIngredient": True,
                "parentBlend": "Energy Blend", "disclosureLevel": None, "proprietaryBlend": False}
    product = {
        "id": "x", "product_name": "x", "fullName": "x", "inactiveIngredients": [],
        "activeIngredients": [
            {"name": "Energy Blend", "standardName": "Energy Blend", "raw_source_text": "Energy Blend",
             "order": 1, "quantity": 0, "unit": "NP", "forms": [], "proprietaryBlend": False},
            child("Green Tea extract", 50, "mg", 2),
            child("Guarana seed extract", 0, "NP", 3),
        ],
        "servingSizes": [{"order": 1, "minQuantity": 1, "maxQuantity": 1, "unit": "Capsule(s)",
                          "minDailyServings": 1, "maxDailyServings": 1}],
    }
    enriched, _ = SupplementEnricherV3().enrich_product(product)
    blend = _blend(enriched, "Energy Blend")
    assert blend["disclosure_level"] == "none"
    assert blend["blend_total_mg"] is None
    assert _has_undisclosed_stimulant_blend(enriched) is True


@pytest.mark.parametrize("total,expected", [(400.0, False), (400.1, True)])
def test_botanical_bound_uses_the_caution_line_exclusively(total, expected):
    assert _has_undisclosed_stimulant_blend(_product("Energy Blend", total, ["Green Tea extract"])) is expected


def test_explicit_caffeine_fires_without_a_printed_total():
    assert _has_undisclosed_stimulant_blend(_product("Antioxidant Blend", None, ["Caffeine"], level="none")) is True


def test_decaffeinated_tea_in_a_small_energy_blend_is_not_a_stimulant_warning():
    assert _has_undisclosed_stimulant_blend(
        _product("Energy Blend", 120.0, ["Decaffeinated Green Tea extract"])) is False


def test_full_blend_header_is_structure_not_a_missing_active(pipeline):
    """DSLD 230132: 'Sleep Blend' prints no total and quantifies all five components. Its header
    row is structure, so the fully disclosed label keeps complete-disclosure credit. (It used to
    pass only through a phantom row built from a child amount mistaken for the blend total.)"""
    _, scored = _run(pipeline, "230132")
    transparency = scored["_v4_module_breakdown"]["dimensions"]["transparency"]
    disclosure = transparency["metadata"]["complete_active_disclosure"]
    assert disclosure["qualifies"] is True, disclosure["blockers"]


@pytest.mark.parametrize("dsld_id,name", [
    ("328799", "Micronized Purified Flavonoid Fraction"),
    ("328071", "Milk Thistle seed extract"),
    ("332924", "Goldenseal"),
])
def test_printed_total_over_one_component_is_full(pipeline, dsld_id, name):
    """MPFF 500 mg from Sweet Orange Peel Extract; Milk Thistle seed extract 254 mg standardized to
    Silymarin; Goldenseal 1 g standardized to Berberine. With one listed component the printed
    total is that component's amount."""
    enriched, _ = _run(pipeline, dsld_id)
    assert _blend(enriched, name)["disclosure_level"] == "full"


def test_one_row_naming_two_protein_sources_still_hides_the_split(pipeline):
    """DSLD 47225: 'Blend (Amino Acid/Protein)' 8 g lists two 'Glutamic Acid' rows, each from
    Micellar Casein and Whey Protein Isolate; the casein/whey split is not printed."""
    enriched, _ = _run(pipeline, "47225")
    assert _blend(enriched, "Blend (Amino Acid/Protein)")["disclosure_level"] == "partial"


def test_sole_component_that_hides_its_own_row_is_partial(pipeline):
    """DSLD 232540: the blend's one row 'Milk Thistle extract' carries 'Phospholipids' with no
    amount, so the phospholipid share is hidden."""
    enriched, _ = _run(pipeline, "232540")
    assert _blend(enriched, "Milk Thistle Phospholipid Proprietary Blend")["disclosure_level"] == "partial"


def test_full_single_component_carries_the_printed_total_as_its_amount(pipeline):
    """A tier of full means the amount is known: MPFF's sole component is 500 mg, nothing hidden."""
    enriched, _ = _run(pipeline, "328799")
    blend = _blend(enriched, "Micronized Purified Flavonoid Fraction")
    assert blend["hidden_count"] == 0
    assert [(c["name"], c["amount"]) for c in blend["child_ingredients"]] == [("Sweet Orange Peel Extract", 500.0)]


def test_a_dropped_sibling_row_still_counts_against_full(pipeline):
    """Review finding: a second component the enricher does not keep as a blend member (here
    'Sugar') still makes the blend two unquantified components on the label."""
    normalizer, enricher = pipeline
    raw = json.loads((FIXTURES / "blend_disclosure_328799_raw.json").read_text())
    header = next(r for r in raw["ingredientRows"] if r["name"] == "Micronized Purified Flavonoid Fraction")
    sibling = copy.deepcopy(header["nestedRows"][0])
    sibling.update(name="Sugar", category="sugar", nestedRows=[], forms=[])
    header["nestedRows"].append(sibling)
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
    assert _blend(enriched, "Micronized Purified Flavonoid Fraction")["disclosure_level"] == "partial"


def test_cleaner_tier_accepts_a_bare_number_quantity():
    rows = [{"name": "A", "quantity": [{"quantity": 0, "unit": "NP"}], "forms": [],
             "nestedRows": [{"name": "B", "quantity": 80, "unit": "mg"}]}]
    assert EnhancedDSLDNormalizer()._determine_disclosure_level("Proprietary Blend", 500, "mg", rows) == "full"


@pytest.mark.parametrize("nested", [
    {"name": "Intermediate Marker", "quantity": [{"quantity": 100, "unit": "mg"}],
     "forms": [], "nestedRows": [{"name": "Caffeine", "quantity": [{"quantity": 0, "unit": "NP"}], "forms": [], "nestedRows": []}]},
    {"name": "Caffeine", "quantity": [{"quantity": 100, "unit": "NP"}], "forms": [], "nestedRows": []},
])
def test_sole_source_cannot_hide_deeper_or_unitless_amounts(pipeline, nested):
    normalizer, enricher = pipeline
    raw = json.loads((FIXTURES / "blend_disclosure_328799_raw.json").read_text())
    header = next(r for r in raw["ingredientRows"] if r["name"] == "Micronized Purified Flavonoid Fraction")
    header["nestedRows"][0]["nestedRows"] = [nested]
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
    assert _blend(enriched, header["name"])["disclosure_level"] == "partial"
