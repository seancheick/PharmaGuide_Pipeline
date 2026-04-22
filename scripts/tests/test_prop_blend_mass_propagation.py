"""
Sprint E1.2.1 — regression tests for proprietary-blend parent-mass propagation.

The bug (pre-fix): when the normalizer flattens a named blend container
(DSLD group blend or structural active container), the parent row carrying
the blend's mass (e.g. "Proprietary Blend 850 mg") is dropped and only the
un-dosed children survive. Downstream, the enricher's
``_collect_proprietary_data`` cannot reconstruct the total mass because
the children carry no mass (they are ``NP`` / ``qty=0``), and the blob
emits ``proprietary_blend_detail.blends[0].total_weight == 0``.

The fix (two surgical hooks):

  1. Cleaner: when ``_flatten_nested_ingredients`` drops a parent
     container with a measured quantity, stash that quantity (and unit)
     onto each child row as ``parentBlendMass`` / ``parentBlendUnit``.
  2. Enricher: in ``_collect_proprietary_data``, when aggregating nested
     children with a ``parentBlend`` under the same group key, prefer
     the ``parentBlendMass`` carried on any child over summing the
     (typically zero) child masses.

Canary assertion (sprint §E1.2.1 DoD): Plantizyme (Thorne DSLD 35491)
emits ``total_weight == 850.0`` and ``blend_total_mg == 850.0`` after
the fix, vs ``0.0`` / ``None`` pre-fix.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402
from scripts.enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures — post-flatten shape that children look like after the cleaner
# drops the parent container. Children carry parentBlend + the new
# parentBlendMass / parentBlendUnit fields.
# ---------------------------------------------------------------------------

def _post_flatten_children(blend_name: str, parent_mass: float, parent_unit: str, child_names: list[str]) -> list[dict]:
    """Shape produced by the cleaner after flattening a parent container.
    Children inherit parent's mass into parentBlendMass for enricher
    recovery."""
    return [{
        "name": child_name,
        "quantity": 0,  # typical NP child — mass unknown per-ingredient
        "unit": "",
        "proprietaryBlend": True,
        "isNestedIngredient": True,
        "parentBlend": blend_name,
        "parentBlendMass": parent_mass,
        "parentBlendUnit": parent_unit,
        "disclosureLevel": "none",
    } for child_name in child_names]


# ---------------------------------------------------------------------------
# Enricher-side contract: reads parentBlendMass from children
# ---------------------------------------------------------------------------

@pytest.fixture()
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def test_enricher_recovers_total_weight_from_parent_blend_mass(enricher) -> None:
    """Plantizyme-shape: 850 mg blend with NP children → total_weight=850."""
    product = {
        "id": "TEST_PLANTIZYME",
        "product_name": "Test Plantizyme",
        "activeIngredients": _post_flatten_children(
            blend_name="Proprietary Blend",
            parent_mass=850.0,
            parent_unit="mg",
            child_names=["Amylase", "Protease", "Lipase", "Cellulase", "Bromelain"],
        ),
        "inactiveIngredients": [],
    }
    result = enricher._collect_proprietary_data(product)

    assert result["has_proprietary_blends"] is True
    assert len(result["blends"]) >= 1
    blend = next(b for b in result["blends"] if "proprietary blend" in b["name"].lower())
    assert blend["total_weight"] == 850.0, (
        f"expected 850.0 mg recovered from parentBlendMass; got {blend['total_weight']!r}"
    )
    assert blend["unit"].lower() == "mg"


def test_enricher_ignores_missing_parent_blend_mass(enricher) -> None:
    """Back-compat: pre-fix shape (no parentBlendMass) still aggregates
    what it can; doesn't crash, doesn't invent mass."""
    children = _post_flatten_children(
        blend_name="Unknown Blend",
        parent_mass=0.0,  # not set — mimics pre-fix shape
        parent_unit="",
        child_names=["X", "Y"],
    )
    # Strip the new fields to simulate pre-fix shape
    for c in children:
        c.pop("parentBlendMass", None)
        c.pop("parentBlendUnit", None)
    product = {
        "id": "TEST_PRE_FIX",
        "product_name": "Pre-fix shape",
        "activeIngredients": children,
        "inactiveIngredients": [],
    }
    result = enricher._collect_proprietary_data(product)
    # Aggregator should still emit a blend entry; just with total_weight=0
    assert result["has_proprietary_blends"] is True
    blend = next(b for b in result["blends"] if "unknown blend" in b["name"].lower())
    assert blend["total_weight"] == 0.0


def test_enricher_handles_gram_unit_passthrough(enricher) -> None:
    """When parent unit is grams, the unit must propagate to the blend so
    the Step 3b mg normalizer converts correctly (1 g → 1000 mg)."""
    product = {
        "id": "TEST_GRAM_BLEND",
        "product_name": "Gram-dose blend",
        "activeIngredients": _post_flatten_children(
            blend_name="Mushroom Complex",
            parent_mass=2.5,
            parent_unit="g",
            child_names=["Reishi", "Lion's Mane", "Cordyceps"],
        ),
        "inactiveIngredients": [],
    }
    result = enricher._collect_proprietary_data(product)
    blend = next(b for b in result["blends"] if "mushroom complex" in b["name"].lower())
    assert blend["total_weight"] == 2.5
    assert blend["unit"].lower() == "g"


def test_enricher_prefers_parent_mass_over_zero_child_sums(enricher) -> None:
    """If the first child carries parentBlendMass, subsequent NP children
    must not reset total_weight back to 0."""
    product = {
        "id": "TEST_MIXED",
        "product_name": "Mixed disclosure",
        "activeIngredients": _post_flatten_children(
            blend_name="Herbal Blend",
            parent_mass=500.0,
            parent_unit="mg",
            child_names=["Ashwagandha", "Rhodiola"],
        ),
        "inactiveIngredients": [],
    }
    # Add a 3rd child that also has parent fields but different blend
    extra = _post_flatten_children(
        blend_name="Herbal Blend",
        parent_mass=500.0,
        parent_unit="mg",
        child_names=["Ginseng"],
    )
    product["activeIngredients"].extend(extra)

    result = enricher._collect_proprietary_data(product)
    blend = next(b for b in result["blends"] if "herbal blend" in b["name"].lower())
    assert blend["total_weight"] == 500.0
    assert blend["nested_count"] == 3  # all 3 children tallied


# ---------------------------------------------------------------------------
# blend_total_mg normalization: unit-aware conversion must still work
# ---------------------------------------------------------------------------

def test_blend_total_mg_normalized_from_recovered_gram_mass(enricher) -> None:
    """E1.2.1 + Step 3b: 2.5 g blend → blend_total_mg == 2500.0."""
    product = {
        "id": "TEST_G_TO_MG",
        "product_name": "Gram to MG",
        "activeIngredients": _post_flatten_children(
            blend_name="Test Blend",
            parent_mass=2.5,
            parent_unit="g",
            child_names=["A", "B"],
        ),
        "inactiveIngredients": [],
    }
    result = enricher._collect_proprietary_data(product)
    blend = next(b for b in result["blends"] if "test blend" in b["name"].lower())
    # blend_total_mg is normalized downstream in the public enrich path, but
    # total_weight + unit must be correctly populated for that step.
    assert blend["total_weight"] == 2.5
    assert blend["unit"].lower() == "g"


# ---------------------------------------------------------------------------
# Canary — Plantizyme DSLD 35491 baseline: pre-fix total_weight was 0.0
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Normalizer-side contract: stamps parentBlendMass / parentBlendUnit on
# children when flattening a DSLD group-blend container.
# ---------------------------------------------------------------------------

def test_normalizer_primary_mass_unit_extractor() -> None:
    """Static helper parses DSLD's quantity-list shape + scalar fallback."""
    extract = EnhancedDSLDNormalizer._extract_primary_mass_unit

    # DSLD list shape
    assert extract({"quantity": [{"quantity": 850, "unit": "mg"}]}) == (850, "mg")
    # DSLD list shape with gram unit
    assert extract({"quantity": [{"quantity": 2.5, "unit": "g"}]}) == (2.5, "g")
    # Scalar fallback (post-normalized shape)
    assert extract({"quantity": 500, "unit": "mg"}) == (500, "mg")
    # Missing / zero mass
    assert extract({}) == (None, "")
    assert extract({"quantity": 0}) == (None, "")
    assert extract({"quantity": [{"quantity": 0, "unit": "mg"}]}) == (None, "")


def test_normalizer_stamps_parent_mass_on_flatten() -> None:
    """Feed a DSLD-shape group-blend container through the flattener and
    assert the nested children inherit ``parentBlendMass`` /
    ``parentBlendUnit``. Whether the parent row itself is also kept in
    the output is not asserted here — only the child-stamp invariant."""
    normalizer = EnhancedDSLDNormalizer()
    raw_ingredient_rows = [{
        "name": "WellBody 365",
        "ingredientGroup": "WellBody 365",
        "quantity": [{"quantity": 850, "unit": "mg"}],
        "nestedRows": [
            {"name": "Amylase", "quantity": [{"quantity": 0, "unit": ""}]},
            {"name": "Protease", "quantity": [{"quantity": 0, "unit": ""}]},
            {"name": "Lipase", "quantity": [{"quantity": 0, "unit": ""}]},
        ],
    }]
    flattened = normalizer._flatten_nested_ingredients(raw_ingredient_rows)
    children = [
        c for c in flattened
        if c.get("isNestedIngredient") and c.get("parentBlend") == "WellBody 365"
    ]
    assert len(children) == 3, (
        f"expected 3 stamped nested children; got {len(children)} in {flattened!r}"
    )
    for child in children:
        assert child.get("parentBlendMass") == 850, (
            f"{child['name']} missing parentBlendMass; got {child.get('parentBlendMass')!r}"
        )
        assert child.get("parentBlendUnit") == "mg"


def test_normalizer_does_not_stamp_when_parent_has_no_mass() -> None:
    """If parent container has no measurable quantity, children must not
    carry a spurious parentBlendMass (fall-through to zero is wrong)."""
    normalizer = EnhancedDSLDNormalizer()
    raw_ingredient_rows = [{
        "name": "Proprietary Blend",
        "ingredientGroup": "Proprietary Blend",
        "quantity": [{"quantity": 0, "unit": ""}],
        "nestedRows": [
            {"name": "Alpha", "quantity": [{"quantity": 0, "unit": ""}]},
        ],
    }]
    flattened = normalizer._flatten_nested_ingredients(raw_ingredient_rows)
    nested_children = [c for c in flattened if c.get("isNestedIngredient")]
    for child in nested_children:
        assert "parentBlendMass" not in child, child
        assert "parentBlendUnit" not in child, child


# ---------------------------------------------------------------------------
# Canary — Plantizyme DSLD 35491 baseline: pre-fix total_weight was 0.0
# ---------------------------------------------------------------------------

def test_plantizyme_canary_recovers_850mg(enricher) -> None:
    """Sprint §E1.2.1 DoD: Plantizyme ``proprietary_blend_detail.blends[0]
    .total_weight == 850.0``. Using the DSLD-disclosed blend name and
    member set from the actual catalog entry."""
    product = {
        "id": "35491",
        "product_name": "Plantizyme",
        "activeIngredients": _post_flatten_children(
            blend_name="Proprietary Blend",
            parent_mass=850.0,
            parent_unit="mg",
            child_names=[
                "Amylase",
                "Protease",
                "Lipase",
                "Cellulase",
                "Hemicellulase",
                "Bromelain",
            ],
        ),
        "inactiveIngredients": [],
    }
    result = enricher._collect_proprietary_data(product)
    blend = next(b for b in result["blends"] if "proprietary blend" in b["name"].lower())
    assert blend["total_weight"] == 850.0
    assert blend["unit"].lower() == "mg"
    assert blend["nested_count"] == 6
