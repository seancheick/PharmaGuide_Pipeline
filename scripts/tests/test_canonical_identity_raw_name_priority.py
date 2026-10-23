"""
Canonical-identity raw_name-priority regression test.

When the cleaner's fuzzy matcher collapses a sharply-defined source
label into a broader umbrella parent — e.g., "Fish Oil concentrate" →
"Omega-3 Fatty Acids" at the standard_name resolution stage —
``_resolve_canonical_identity`` now prefers a raw_name lookup before
falling back to the standard_name lookup.

Why this matters: under Phase 3 the enricher honors the cleaner's
``canonical_id`` as a hard constraint. If the cleaner emits the
umbrella canonical, the enricher is locked out of the more specific
form-level match. The raw_name-first reverse-index probe keeps the
sharper canonical (``fish_oil`` vs ``omega_3``, both legitimate IQM
parents with different bio_scores) intact.

See Phase 3 shadow-diff notes in
docs/HANDOFF_2026-04-20_PIPELINE_REFACTOR.md and the Phase 3 enricher
test file ``test_phase3_cleaner_canonical_authority.py``.
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


class TestRawNamePriority:
    """raw_name hits win over standard_name hits; misses fall back."""

    def test_fish_oil_concentrate_resolves_fish_oil_not_omega_3(self, normalizer) -> None:
        # Cleaner's fuzzy matcher maps the raw "Fish Oil concentrate" to
        # standard_name "Omega-3 Fatty Acids" (the umbrella IQM parent).
        # Reverse-index-first with raw_name should recover the sharper
        # fish_oil canonical (bio=10) instead of omega_3 (bio=8).
        result = normalizer._resolve_canonical_identity(
            standard_name="Omega-3 Fatty Acids",
            raw_name="Fish Oil concentrate",
        )
        assert result == ("fish_oil", "ingredient_quality_map")

    def test_unambiguous_raw_name_wins(self, normalizer) -> None:
        result = normalizer._resolve_canonical_identity(
            standard_name="Omega-3 Fatty Acids",
            raw_name="Fish Oil",
        )
        assert result == ("fish_oil", "ingredient_quality_map")

    def test_raw_name_miss_falls_back_to_standard(self, normalizer) -> None:
        # When raw_name isn't a reverse-index key, behavior matches the
        # pre-Phase-3 contract — use standard_name.
        # Post-B38 (2026-04-25): the architectural merge made fish_oil the bulk
        # omega-3 supplement parent; omega_3 retained only metabolite forms.
        # Standard_name "Omega-3 Fatty Acids" now resolves to fish_oil.
        result = normalizer._resolve_canonical_identity(
            standard_name="Omega-3 Fatty Acids",
            raw_name="Some Random Label Token No One Ships",
        )
        assert result == ("fish_oil", "ingredient_quality_map")

    def test_both_miss_returns_none(self, normalizer) -> None:
        result = normalizer._resolve_canonical_identity(
            standard_name="Nonexistent Parent",
            raw_name="Also Nonexistent",
        )
        assert result == (None, None)

    def test_silybin_phytosome_still_resolves_milk_thistle(self, normalizer) -> None:
        # Regression guard: the Phase 3 primary target should keep working.
        result = normalizer._resolve_canonical_identity(
            standard_name="Milk Thistle",
            raw_name="Silybin Phytosome",
        )
        assert result == ("milk_thistle", "ingredient_quality_map")

    def test_exact_dcp_identity_beats_broader_nutrient_aliases(self, normalizer) -> None:
        # Dicalcium phosphate has its own IQM canonical. It also appears as a
        # form alias under calcium and phosphorus, but those broader aliases
        # must not win by JSON insertion order when the literal identity is
        # dicalcium phosphate.
        result = normalizer._resolve_canonical_identity(
            standard_name="Phosphorus",
            raw_name="Dicalcium Phosphate",
        )
        assert result == ("dicalcium_phosphate", "ingredient_quality_map")

    def test_empty_raw_name_uses_standard(self, normalizer) -> None:
        # Defensive: empty raw_name must not short-circuit the standard_name path.
        result = normalizer._resolve_canonical_identity(
            standard_name="Fish Oil",
            raw_name="",
        )
        assert result == ("fish_oil", "ingredient_quality_map")

    def test_none_raw_name_uses_standard(self, normalizer) -> None:
        result = normalizer._resolve_canonical_identity(
            standard_name="Fish Oil",
            raw_name=None,
        )
        assert result == ("fish_oil", "ingredient_quality_map")


@pytest.mark.parametrize("name,expected", [("Grape skin extract", "grape"), ("Safflower Oil", "PII_SAFFLOWER_OIL"), ("Grape Seed Extract", "grape_seed_extract"), ("CLA safflower oil", "cla")])
def test_source_material_does_not_become_a_different_studied_preparation(name, expected):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    product = {"id": "source-material-identity", "fullName": name,
        "ingredientRows": [{"name": name, "category": "botanical" if "Grape" in name else "fat",
            "quantity": [{"quantity": 100, "unit": "mg"}], "forms": [], "nestedRows": []}]}
    rows = EnhancedDSLDNormalizer().normalize_product(product)["activeIngredients"]
    assert rows and rows[0]["canonical_id"] == expected


@pytest.mark.parametrize("name", ["L-Cystine", "Cystine"])
def test_cystine_does_not_borrow_cysteine_identity(normalizer, name):
    product = {"id": "cystine-identity", "fullName": name,
        "ingredientRows": [{"name": name, "category": "amino acid",
            "quantity": [{"quantity": 500, "unit": "mg"}], "forms": [], "nestedRows": []}]}
    rows = normalizer.normalize_product(product)["activeIngredients"]
    assert rows and rows[0]["name"] == name
    assert rows[0]["canonical_id"] != "l_cysteine"
    assert rows[0]["quantity"] == 500


def test_cysteine_identity_remains_mapped(normalizer):
    assert normalizer._resolve_canonical_identity(
        standard_name="L-Cysteine", raw_name="L-Cysteine"
    ) == ("l_cysteine", "ingredient_quality_map")


def test_separate_cystine_row_does_not_veto_cysteine(normalizer):
    raw = {"id": "separate-amino-acids", "fullName": "Amino acids",
        "ingredientRows": [{"name": name, "category": "amino acid",
            "quantity": [{"quantity": 500, "unit": "mg"}], "forms": [], "nestedRows": []}
            for name in ["L-Cystine", "L-Cysteine", "N-Acetyl-L-Cysteine"]]}
    rows = normalizer.normalize_product(raw)["activeIngredients"]
    by_name = {row["name"]: row for row in rows}
    assert by_name["L-Cystine"]["canonical_id"] != "l_cysteine"
    assert by_name["L-Cysteine"]["canonical_id"] == "l_cysteine"
    assert by_name["N-Acetyl-L-Cysteine"]["canonical_id"] == "nac"
