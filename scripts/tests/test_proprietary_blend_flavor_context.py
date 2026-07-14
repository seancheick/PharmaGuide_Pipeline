"""C10.3 — a blend term inside a FLAVOR/COLOR descriptor is not a blend.

`re.escape(term)` matched "Fruit Blend" inside "Natural Tropical Fruit Blend
Flavor", so a flavoring picked up a −10 no-disclosure proprietary-blend penalty.
A blend term immediately followed by a flavor/color word is a formulation
flavoring/coloring, not a scored proprietary active blend, and must not be
penalized. A genuine blend that merely lists "(natural flavors)" in a
parenthetical is unaffected.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from proprietary_blend_detector import ProprietaryBlendDetector


@pytest.fixture(scope="module")
def detector() -> ProprietaryBlendDetector:
    return ProprietaryBlendDetector()


def _penalty(detector, ingredients):
    product = {
        "id": "t", "fullName": "Test",
        "activeIngredients": ingredients, "inactiveIngredients": [], "otherIngredients": [],
    }
    return detector.analyze_product(product).to_dict()["total_penalty_applicable"]


class TestFlavorColorNotPenalized:
    @pytest.mark.parametrize("name", [
        "Natural Tropical Fruit Blend Flavor",
        "Mixed Berry Blend Flavoring",
        "Citrus Blend Natural Flavor",
    ])
    def test_flavor_blend_name_no_penalty(self, detector, name) -> None:
        assert _penalty(detector, [{"name": name, "quantity": 50, "unit": "mg"}]) == 0, (
            f"{name!r} is a flavoring, not a proprietary active blend — must not be penalized."
        )


class TestRealBlendStillPenalized:
    def test_undisclosed_energy_blend_still_penalized(self, detector) -> None:
        # Control: a genuine undisclosed proprietary blend must still fire.
        penalty = _penalty(detector, [
            {"name": "Proprietary Energy Blend", "quantity": 500, "unit": "mg",
             "nestedIngredients": [{"name": "Caffeine"}, {"name": "Taurine"}]},
        ])
        assert penalty < 0, "A real undisclosed proprietary blend must still be penalized."
