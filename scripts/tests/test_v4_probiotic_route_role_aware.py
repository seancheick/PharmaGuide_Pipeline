"""V4 probiotic route-drift fix — strain-dominance gate.

Regression (found in the post-pipeline re-audit): products that merely *contain* an
adjunct probiotic strain (a 32-vitamin multivitamin, a whey protein, an electrolyte
drink) were routed to the probiotic module by the `_is_probiotic_class` fallback,
then blocked by the module-relevant identity guard -> NOT_SCORED, discarding their
real (multi / sports / generic) identity. 47 shipped products affected.

Root cause: the fallback fired on (is_probiotic_product AND strain_count>0 AND
(CFU OR "probiotic" in name)) without checking whether the probiotic is the product's
DOMINANT identity. Empirically, real-vs-misroute does not follow primary_type; it
follows strain dominance.

Fix: route probiotic via fallback only when the strains dominate the scorable
identity (strain_count >= non-probiotic scorable rows), or the non-probiotic panel
is tiny AND the name explicitly says probiotic. Taxonomy `primary_type == "probiotic"`
still routes probiotic unconditionally.
"""
from __future__ import annotations

from scoring_v4.router import class_for_product


def _vit_rows(n):
    return [{"name": f"Vitamin {i}", "canonical_id": f"vit_{i}", "mapped": True,
             "quantity": 10, "unit": "mg"} for i in range(n)]


def _prod(name, primary_type, scorable, *, strains, has_cfu, is_prob=True):
    return {
        "product_name": name,
        "primary_type": primary_type,
        "probiotic_data": {
            "is_probiotic_product": is_prob,
            "total_strain_count": strains,
            "has_cfu": has_cfu,
            "total_cfu": 1_000_000_000.0 if has_cfu else 0,
        },
        "ingredient_quality_data": {"total_active": len(scorable), "ingredients_scorable": scorable},
    }


# --- misroutes: adjunct probiotic must NOT capture the product ---

def test_multivitamin_with_adjunct_strain_routes_multi_not_probiotic():
    p = _prod("Women's Ultra Mega With Probiotics", "multivitamin", _vit_rows(32),
              strains=1, has_cfu=True)
    assert class_for_product(p) != "probiotic"
    assert class_for_product(p) == "multi_or_prenatal"


def test_whey_with_adjunct_strain_does_not_route_probiotic():
    rows = [{"name": "Whey Protein", "canonical_id": "whey_protein", "mapped": True, "quantity": 25, "unit": "g"},
            {"name": "Calcium", "canonical_id": "calcium", "mapped": True, "quantity": 200, "unit": "mg"},
            {"name": "Potassium", "canonical_id": "potassium", "mapped": True, "quantity": 100, "unit": "mg"}]
    p = _prod("Dynamic Whey Vanilla", "protein_powder", rows, strains=1, has_cfu=True)
    assert class_for_product(p) != "probiotic"


def test_hydration_multi_with_adjunct_strain_routes_multi_not_probiotic():
    p = _prod("Amplified Hydration Lemon Lime", "multivitamin", _vit_rows(9),
              strains=1, has_cfu=True)
    assert class_for_product(p) != "probiotic"


# --- real probiotics: strains dominate -> must still route probiotic ---

def test_real_probiotic_strains_dominant_routes_probiotic():
    """FloraMend-style: many strains, no non-probiotic scorable panel."""
    p = _prod("FloraMend Prime Probiotic", "general_supplement", [], strains=6, has_cfu=False)
    assert class_for_product(p) == "probiotic"


def test_probiotic_gummy_small_panel_with_name_routes_probiotic():
    """Tiny vitamin panel + explicit probiotic name -> probiotic."""
    p = _prod("Probiotic Gummies", "general_supplement", _vit_rows(2), strains=1, has_cfu=True)
    assert class_for_product(p) == "probiotic"


def test_taxonomy_probiotic_always_routes_probiotic():
    p = _prod("Daily Probiotic 50 Billion", "probiotic", _vit_rows(3), strains=10, has_cfu=True)
    assert class_for_product(p) == "probiotic"


# --- pure-strain products: no CFU, no "probiotic" name, but strains ARE the
#     only scorable identity (panel==0) -> probiotic (FLORASSIST gap) ---

def test_pure_multistrain_no_cfu_no_name_routes_probiotic():
    """FLORASSIST Balance: 10 named strains, no CFU disclosed, brand name lacks
    'probiotic', and nothing else scorable. It is unambiguously a probiotic."""
    p = _prod("FLORASSIST Balance", "general_supplement", [], strains=10, has_cfu=False)
    assert class_for_product(p) == "probiotic"


def test_vitamin_with_adjunct_strains_and_panel_stays_nonprobiotic():
    """Guard: Garden-of-life-'Raw'-style Biotin carries adjunct strains but the
    biotin IS the product (panel>=1). The pure-strain relaxation must NOT capture
    it just because strains outnumber the 1-row panel."""
    p = _prod("Biotin 10,000 mcg", "single_vitamin",
              [{"name": "Biotin", "canonical_id": "vitamin_b7_biotin", "mapped": True, "quantity": 10000, "unit": "mcg"}],
              strains=6, has_cfu=False)
    assert class_for_product(p) != "probiotic"


def test_single_strain_pure_no_cfu_no_name_does_not_route_probiotic():
    """A lone incidental strain with no CFU/name evidence is too weak to claim the
    probiotic module (requires >=2 strains for the no-CFU/no-name path)."""
    p = _prod("Break It Down Organic Pineapple", "general_supplement", [], strains=1, has_cfu=False)
    assert class_for_product(p) != "probiotic"


def test_pure_strain_with_nonprobiotic_title_hero_stays_nonprobiotic():
    """Hero guard: even with panel==0 and >=2 strains, a product advertising a
    non-probiotic hero (zinc) must NOT be promoted — its real panel was likely lost
    upstream. Protects against future cleaner/enricher panel-loss."""
    p = _prod("Whole Food Zinc Quercetin Complex", "general_supplement", [], strains=5, has_cfu=False)
    assert class_for_product(p) != "probiotic"


def test_pure_strain_with_nonprobiotic_taxonomy_stays_nonprobiotic():
    """Hero guard via taxonomy: a fiber product with strains but no CFU/probiotic
    name stays non-probiotic even at panel==0."""
    p = _prod("Daily Prebiotic Fiber", "fiber_digestive", [], strains=5, has_cfu=False)
    assert class_for_product(p) != "probiotic"
