"""SP-4 ingredient_category vocab + normalizer regression tests.

Mirror of test_form_factor_vocab.py for the ingredient_category vocab.
Three concerns:
  TestVocabSync   — JSON ↔ Python fallback ↔ Flutter parity (Dart check
                    skips when Flutter repo not co-located).
  TestNormalizer  — alias / pluralization / edge cases.
  TestParityWithLegacy — every category in the legacy supplement_type_utils
                          CATEGORY_ALIASES map canonicalizes to the same
                          target via the new normalizer (no drift during
                          migration).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ingredient_category_normalizer import (
    INGREDIENT_CATEGORY_UNKNOWN,
    _FALLBACK_IDS,
    _load_vocab,
    canonicalize_ingredient_category,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
VOCAB_PATH = REPO_ROOT / "scripts" / "data" / "ingredient_category_vocab.json"


# ============================================================================
# TestVocabSync
# ============================================================================

class TestVocabSync:

    def test_vocab_json_loads(self):
        with open(VOCAB_PATH) as fh:
            data = json.load(fh)
        assert "ingredient_categories" in data
        assert "_metadata" in data
        assert data["_metadata"]["schema_version"]
        assert len(data["ingredient_categories"]) == data["_metadata"]["total_entries"]

    def test_python_fallback_matches_json_ids(self):
        with open(VOCAB_PATH) as fh:
            data = json.load(fh)
        json_ids = tuple(e["id"] for e in data["ingredient_categories"])
        assert _FALLBACK_IDS == json_ids, (
            "Python fallback drifted from JSON.\n"
            f"  In JSON not Python: {set(json_ids) - set(_FALLBACK_IDS)}\n"
            f"  In Python not JSON: {set(_FALLBACK_IDS) - set(json_ids)}"
        )

    def test_all_ids_have_aliases(self):
        with open(VOCAB_PATH) as fh:
            data = json.load(fh)
        for entry in data["ingredient_categories"]:
            assert entry.get("aliases"), (
                f"Category id {entry.get('id')!r} has no aliases."
            )

    def test_no_duplicate_ids(self):
        with open(VOCAB_PATH) as fh:
            data = json.load(fh)
        ids = [e["id"] for e in data["ingredient_categories"]]
        assert len(ids) == len(set(ids))

    def test_no_alias_maps_to_two_ids(self):
        with open(VOCAB_PATH) as fh:
            data = json.load(fh)
        from ingredient_category_normalizer import _normalize_text
        seen: dict[str, str] = {}
        for entry in data["ingredient_categories"]:
            fid = entry["id"]
            for alias in entry.get("aliases", []):
                norm = _normalize_text(alias)
                if norm in seen and seen[norm] != fid:
                    pytest.fail(
                        f"Alias {alias!r} maps to both {seen[norm]!r} and {fid!r}."
                    )
                seen[norm] = fid

    def test_iqm_relationship_documented(self):
        """Every entry mapped to an IQM parent category must use a real IQM
        parent id from iqm_category_vocab.json."""
        iqm_path = REPO_ROOT / "scripts" / "data" / "iqm_category_vocab.json"
        if not iqm_path.is_file():
            pytest.skip("iqm_category_vocab.json not present")
        with open(iqm_path) as fh:
            iqm_data = json.load(fh)
        iqm_ids = {e["id"] for e in iqm_data.get("iqm_categories", [])}
        with open(VOCAB_PATH) as fh:
            data = json.load(fh)
        for entry in data["ingredient_categories"]:
            mapped = entry.get("iqm_parent_category")
            if mapped is not None:
                assert mapped in iqm_ids, (
                    f"Ingredient category {entry['id']!r} claims IQM parent "
                    f"{mapped!r} but it is not in iqm_category_vocab.json."
                )


# ============================================================================
# TestNormalizer
# ============================================================================

class TestNormalizer:

    @pytest.mark.parametrize("raw,expected", [
        # Singular canonical (pass-through)
        ("vitamin", "vitamin"),
        ("mineral", "mineral"),
        ("herb", "herb"),
        ("botanical", "botanical"),
        ("antioxidant", "antioxidant"),
        ("fatty_acid", "fatty_acid"),
        ("amino_acid", "amino_acid"),
        ("probiotic", "probiotic"),
        ("bacteria", "bacteria"),
        ("protein", "protein"),
        ("fiber", "fiber"),
        ("enzyme", "enzyme"),
        ("functional_food", "functional_food"),
        # Plural aliases (IQM source forms)
        ("vitamins", "vitamin"),
        ("minerals", "mineral"),
        ("herbs", "herb"),
        ("antioxidants", "antioxidant"),
        ("fatty_acids", "fatty_acid"),
        ("amino_acids", "amino_acid"),
        ("probiotics", "probiotic"),
        ("proteins", "protein"),
        ("fibers", "fiber"),
        ("enzymes", "enzyme"),
        ("functional_foods", "functional_food"),
        # Space-separated variants
        ("fatty acid", "fatty_acid"),
        ("fatty acids", "fatty_acid"),
        ("amino acid", "amino_acid"),
        ("amino acids", "amino_acid"),
        ("functional food", "functional_food"),
        ("functional foods", "functional_food"),
        # Excipient → inactive
        ("excipient", "inactive"),
        ("excipients", "inactive"),
        # British spelling
        ("fibre", "fiber"),
        ("fibres", "fiber"),
        # Edge tokens
        ("delivery", "delivery"),
        ("additive", "additive"),
        ("additives", "additive"),
        ("inactive", "inactive"),
        ("inactives", "inactive"),
        ("other", "other"),
    ])
    def test_alias_canonicalization(self, raw, expected):
        assert canonicalize_ingredient_category(raw) == expected

    def test_empty_returns_unknown_sentinel(self):
        assert canonicalize_ingredient_category("") == INGREDIENT_CATEGORY_UNKNOWN
        assert canonicalize_ingredient_category(None) == INGREDIENT_CATEGORY_UNKNOWN

    def test_unrecognized_passes_through_normalized(self):
        """Unlike form_factor `unknown` sentinel, ingredient_category passes
        unrecognized values through (after normalization) so unusual edge
        tokens like `section_other` or `blend_header` survive downstream."""
        assert canonicalize_ingredient_category("section_other") == "section_other"
        assert canonicalize_ingredient_category("blend header") == "blend_header"
        assert canonicalize_ingredient_category("MysteryCategory") == "mysterycategory"

    def test_case_and_whitespace_insensitive(self):
        assert canonicalize_ingredient_category("  VITAMIN  ") == "vitamin"
        assert canonicalize_ingredient_category("Vitamin") == "vitamin"
        assert canonicalize_ingredient_category("FATTY-ACID") == "fatty_acid"

    def test_returns_string_never_none(self):
        for raw in (None, "", 0, [], {}, "weird"):
            result = canonicalize_ingredient_category(raw)
            assert isinstance(result, str)


# ============================================================================
# TestParityWithLegacy — output of new normalizer must match the legacy
# supplement_type_utils.canonical_category() for every alias in the old
# hardcoded map. Catches drift during migration.
# ============================================================================

class TestParityWithLegacy:

    def test_legacy_canonical_category_outputs_match_new_normalizer(self):
        """Every alias the legacy CATEGORY_ALIASES map handled must
        canonicalize to the same canonical id under the new normalizer."""
        from supplement_type_utils import CATEGORY_ALIASES, canonical_category
        for raw_alias, legacy_output in CATEGORY_ALIASES.items():
            new_output = canonicalize_ingredient_category(raw_alias)
            # Direct equality required for known canonical forms.
            assert new_output == legacy_output, (
                f"Parity break: legacy canonical_category({raw_alias!r}) = "
                f"{legacy_output!r}, new canonicalize_ingredient_category() = "
                f"{new_output!r}. The new vocab must absorb every legacy alias."
            )


# ============================================================================
# Flutter parity (skipped if Flutter repo not co-located)
# ============================================================================

class TestFlutterParity:

    def test_flutter_dart_vocab_when_repo_available(self):
        flutter_root = Path("/Users/seancheick/PharmaGuide ai")
        if not flutter_root.exists():
            pytest.skip("Flutter repo not checked out at expected location")
        asset_path = flutter_root / "assets" / "data" / "ingredient_category_vocab.json"
        if not asset_path.is_file():
            pytest.skip("Flutter ingredient_category_vocab.json asset not yet copied")
        with open(VOCAB_PATH) as fh:
            pipeline = json.load(fh)
        with open(asset_path) as fh:
            flutter = json.load(fh)
        assert pipeline == flutter, (
            "Flutter ingredient_category_vocab.json drifted from pipeline source."
        )
        dart_path = flutter_root / "lib" / "core" / "data" / "ingredient_category_vocab.dart"
        if not dart_path.is_file():
            pytest.skip("Dart loader not yet generated")
        dart_src = dart_path.read_text()
        assert "class IngredientCategoryEntry" in dart_src
        assert "loadIngredientCategoryVocab" in dart_src
        assert "ingredient_category_vocab.json" in dart_src
