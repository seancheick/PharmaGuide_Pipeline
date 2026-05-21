"""SP-3 form_factor vocab + normalizer regression tests.

Three concerns:
  TestVocabSync         — JSON ↔ Python loader ↔ Flutter Dart consistency.
                          The Dart side is checked when the Flutter repo is
                          available at the expected location; otherwise that
                          test skips.
  TestNormalizer        — alias / langual-code / substring matching, edge
                          cases, defensive handling.
  TestRealCatalogCoverage — every real raw form_factor seen in the enriched
                            catalog must canonicalize to a non-`unknown`
                            ID (catches missing aliases).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from form_factor_normalizer import (
    FORM_FACTOR_UNKNOWN,
    _FALLBACK_IDS,
    _load_vocab,
    canonicalize_form_factor,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
VOCAB_PATH = REPO_ROOT / "scripts" / "data" / "form_factor_vocab.json"


# ============================================================================
# TestVocabSync — JSON, Python fallback, and Flutter must agree
# ============================================================================

class TestVocabSync:

    def test_vocab_json_loads(self):
        with open(VOCAB_PATH) as fh:
            data = json.load(fh)
        assert "form_factors" in data
        assert "_metadata" in data
        assert data["_metadata"]["schema_version"]
        assert len(data["form_factors"]) == data["_metadata"]["total_entries"]

    def test_python_fallback_matches_json_ids(self):
        """The hardcoded fallback in form_factor_normalizer.py must include
        every JSON id in the same order. Drift = a stale fallback."""
        with open(VOCAB_PATH) as fh:
            data = json.load(fh)
        json_ids = tuple(e["id"] for e in data["form_factors"])
        assert _FALLBACK_IDS == json_ids, (
            "Python fallback drifted from JSON.\n"
            f"  In JSON not Python: {set(json_ids) - set(_FALLBACK_IDS)}\n"
            f"  In Python not JSON: {set(_FALLBACK_IDS) - set(json_ids)}\n"
            "Update _FALLBACK_IDS in form_factor_normalizer.py."
        )

    def test_all_ids_have_aliases(self):
        with open(VOCAB_PATH) as fh:
            data = json.load(fh)
        for entry in data["form_factors"]:
            assert entry.get("aliases"), (
                f"Form-factor id {entry.get('id')!r} has no aliases — "
                f"normalizer can never match a label to it."
            )

    def test_no_duplicate_ids(self):
        with open(VOCAB_PATH) as fh:
            data = json.load(fh)
        ids = [e["id"] for e in data["form_factors"]]
        assert len(ids) == len(set(ids))

    def test_no_alias_maps_to_two_ids(self):
        """Aliases must be unambiguous — same alias mapping to two canonical
        ids would make normalization non-deterministic."""
        with open(VOCAB_PATH) as fh:
            data = json.load(fh)
        seen: dict[str, str] = {}
        from form_factor_normalizer import _normalize_text
        for entry in data["form_factors"]:
            fid = entry["id"]
            for alias in entry.get("aliases", []):
                norm = _normalize_text(alias)
                if norm in seen and seen[norm] != fid:
                    pytest.fail(
                        f"Alias {alias!r} maps to both {seen[norm]!r} and "
                        f"{fid!r}. Make aliases unique."
                    )
                seen[norm] = fid

    def test_flutter_dart_vocab_present_when_repo_available(self):
        """If the Flutter app repo is checked out at the expected sibling
        location, the Dart vocab loader file must exist with the expected
        public API surface. The Dart loader reads `assets/data/form_factor_vocab.json`
        at runtime so individual IDs are not hardcoded in the .dart file —
        instead we verify (1) the JSON asset is present, (2) the Dart
        loader function exists, (3) the registry wires it in."""
        flutter_root = Path("/Users/seancheick/PharmaGuide ai")
        if not flutter_root.exists():
            pytest.skip("Flutter repo not checked out at expected location")

        asset_path = flutter_root / "assets" / "data" / "form_factor_vocab.json"
        if not asset_path.is_file():
            pytest.skip("Flutter form_factor_vocab.json asset not yet copied")
        # Asset must be identical to the pipeline source.
        with open(VOCAB_PATH) as fh:
            pipeline = json.load(fh)
        with open(asset_path) as fh:
            flutter = json.load(fh)
        assert pipeline == flutter, (
            "Flutter assets/data/form_factor_vocab.json drifted from pipeline "
            "scripts/data/form_factor_vocab.json. Re-copy the pipeline file."
        )

        dart_path = flutter_root / "lib" / "core" / "data" / "form_factor_vocab.dart"
        if not dart_path.is_file():
            pytest.skip("Flutter form_factor_vocab.dart not yet generated")
        dart_src = dart_path.read_text()
        assert "class FormFactorEntry" in dart_src, "Dart entry class missing"
        assert "loadFormFactorVocab" in dart_src, "Dart loader fn missing"
        assert "form_factor_vocab.json" in dart_src, "Dart loader doesn't load the asset"

        registry_path = flutter_root / "lib" / "core" / "data" / "vocab_registry.dart"
        if registry_path.is_file():
            registry_src = registry_path.read_text()
            assert "FormFactorEntry" in registry_src, "VocabRegistry missing FormFactorEntry"
            assert "loadFormFactorVocab" in registry_src, "VocabRegistry missing loader call"
            assert "formFactor(" in registry_src, "VocabRegistry missing formFactor() getter"


# ============================================================================
# TestNormalizer — canonicalize_form_factor() behavior
# ============================================================================

class TestNormalizer:

    @pytest.mark.parametrize("raw,expected", [
        # Exact alias matches
        ("Capsule", "capsule"),
        ("capsules", "capsule"),
        ("Vegetarian Capsule", "capsule"),
        ("Softgel", "softgel"),
        ("Softgel Capsule", "softgel"),
        ("Soft-Gel", "softgel"),
        ("Tablet", "tablet"),
        ("Tablet or Pill", "tablet"),
        ("Chewable Tablet", "chewable"),
        ("Gummy", "gummy"),
        ("Gummy or Jelly", "gummy"),
        ("Gummies", "gummy"),
        ("Powder", "powder"),
        ("Drink Mix", "powder"),
        ("Liquid", "liquid"),
        ("Tincture", "tincture"),
        ("Lozenge", "lozenge"),
        ("Sublingual Tablet", "sublingual"),
        ("Drops", "drops"),
        ("Oral Spray", "spray"),
        ("Protein Bar", "bar"),
        ("Transdermal Patch", "patch"),
        ("Topical Cream", "topical"),
        ("Tea Bag", "tea_bag"),
        ("Other", "other"),
        ("Unknown", "unknown"),
    ])
    def test_alias_canonicalization(self, raw, expected):
        assert canonicalize_form_factor(raw) == expected

    def test_softgel_capsule_substring_beats_capsule(self):
        """`Softgel Capsule` contains both `softgel` and `capsule` aliases.
        Longest-alias-first ordering must return `softgel`."""
        assert canonicalize_form_factor("Softgel Capsule") == "softgel"

    def test_dsld_langual_code_lookup(self):
        """DSLD langualCode is the most authoritative signal when supplied."""
        assert canonicalize_form_factor("Capsule", langual_code="e0161") == "softgel"
        assert canonicalize_form_factor("anything", langual_code="e0159") == "capsule"

    def test_langual_code_unknown_falls_to_text(self):
        """Unknown langual code -> use the text fallback."""
        assert canonicalize_form_factor("Powder", langual_code="e9999") == "powder"

    def test_empty_value_returns_unknown(self):
        assert canonicalize_form_factor("") == FORM_FACTOR_UNKNOWN
        assert canonicalize_form_factor(None) == FORM_FACTOR_UNKNOWN

    def test_unrecognized_text_returns_unknown(self):
        assert canonicalize_form_factor("intergalactic plasma") == FORM_FACTOR_UNKNOWN

    def test_case_and_whitespace_insensitive(self):
        assert canonicalize_form_factor("  CAPSULE  ") == "capsule"
        assert canonicalize_form_factor("Gummy/Jelly") == "gummy"

    def test_returns_string_never_none(self):
        for raw in (None, "", 0, [], {}, "weird"):
            result = canonicalize_form_factor(raw)
            assert isinstance(result, str)
            assert result  # non-empty


# ============================================================================
# TestRealCatalogCoverage — every observed raw value must canonicalize
# ============================================================================

class TestRealCatalogCoverage:

    # Real catalog raw form_factor values captured 2026-05-21 from the
    # enriched dataset (top occurrences). Each must map to a non-`unknown`
    # canonical id — except "unknown" itself, which is the explicit
    # missing-data sentinel.
    REAL_CATALOG_VALUES = (
        ("capsule", "capsule"),
        ("powder", "powder"),
        ("tablet", "tablet"),
        ("other (e.g. tea bag)", "tea_bag"),
        ("gummy", "gummy"),
        ("liquid", "liquid"),
        ("lozenge", "lozenge"),
        ("bar", "bar"),
        # DSLD descriptions verbatim
        ("Softgel Capsule", "softgel"),
        ("Tablet or Pill", "tablet"),
        ("Gummy or Jelly", "gummy"),
        # Explicit unknown
        ("unknown", "unknown"),
    )

    @pytest.mark.parametrize("raw,expected", REAL_CATALOG_VALUES)
    def test_real_catalog_value_canonicalizes(self, raw, expected):
        assert canonicalize_form_factor(raw) == expected, (
            f"Real catalog value {raw!r} must canonicalize to {expected!r}, "
            f"got {canonicalize_form_factor(raw)!r}. Add an alias to the "
            f"vocab JSON."
        )
