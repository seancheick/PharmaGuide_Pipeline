"""C3 regression — the "Contains:" allergen branch must respect negation.

`normalize_product`'s statement parser has a positive-allergen extractor:
``re.search(r"contains:?\s+([^.]+)", notes)`` → for each FDA allergen word in
the captured text, append it to ``labelText.parsed.allergens`` and synthesize a
"Contains: X" warning. It ran with **no negation guard**, so a *negated*
"contains" laundered into a false positive:

  - ``"Contains no milk."``                         → allergens=['milk']  (also 'dairy' in allergenFree — self-contradictory)
  - ``"Contains no sugar, dairy, wheat, soy or milk."`` (Does-NOT-Contain) → allergens=['milk','soy','wheat']
  - ``"Contains milk thistle extract."``            → allergens=['milk']  (milk thistle is a botanical, not dairy)

For an allergy app a false *positive* is not safety-inverting, but it corrupts
the allergen contract and contradicts the allergenFree list. The fix guards the
positive branch on negation and excludes "milk thistle" from the milk match,
while genuine "Contains: X" declarations still surface.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


def _allergens(normalizer, stmt_type: str, notes: str):
    product = {
        "fullName": "Test",
        "statements": [{"type": stmt_type, "notes": notes}],
        "activeIngredients": [{"name": "Vitamin C", "quantity": 100, "unit": "mg"}],
        "inactiveIngredients": [],
    }
    parsed = normalizer.normalize_product(product).get("labelText", {}).get("parsed", {})
    return parsed.get("allergens", [])


class TestNegatedContainsIsNotAPositiveAllergen:
    @pytest.mark.parametrize("stmt_type,notes,forbidden", [
        ("claim", "Contains no milk.", "milk"),
        ("Formulation re: Does NOT Contain", "Contains no sugar, dairy, wheat, soy or milk.", "milk"),
        ("Formulation re: Does NOT Contain", "Contains no sugar, dairy, wheat, soy or milk.", "soy"),
        ("claim", "This product contains no dairy or soy.", "soy"),
        ("claim", "Free of milk and soy.", "milk"),
    ])
    def test_negated_contains_yields_no_positive_allergen(
        self, normalizer, stmt_type, notes, forbidden
    ) -> None:
        allergens = _allergens(normalizer, stmt_type, notes)
        assert forbidden not in allergens, (
            f"Negated statement {notes!r} laundered a false {forbidden!r} allergen: {allergens}"
        )


class TestMilkThistleIsNotDairy:
    def test_milk_thistle_does_not_add_milk_allergen(self, normalizer) -> None:
        allergens = _allergens(normalizer, "claim", "Contains milk thistle extract for liver support.")
        assert "milk" not in allergens, f"milk thistle wrongly flagged milk: {allergens}"


class TestGenuinePositiveContainsStillSurfaces:
    """Negation guard must not suppress real 'Contains: X' declarations."""

    @pytest.mark.parametrize("notes,expected", [
        ("Contains: Milk, Soy.", {"milk", "soy"}),
        ("Contains: Wheat.", {"wheat"}),
        ("Contains milk and soy.", {"milk", "soy"}),
    ])
    def test_positive_contains_surfaces(self, normalizer, notes, expected) -> None:
        allergens = set(_allergens(normalizer, "Precaution", notes))
        assert expected.issubset(allergens), (
            f"Genuine positive {notes!r} lost allergens: got {allergens}, expected ⊇ {expected}"
        )
