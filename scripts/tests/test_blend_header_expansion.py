"""
Sprint D2.3 regression tests — blend header / branded blend expansion.

Context: ~200 silently-mapped rows in the deep accuracy audit were
blend-header names that didn't appear in any reference DB's
reverse-index key set. Examples:
  "Amino Acid Blend", "Amino Acceleration System", "Eye Health Support",
  "Joint Cushion Support Blend", "Salad Extract", "Protease SP",
  "Protease Aminogen", "Vitaberry Plus(TM)", "ActivAIT Mustard Essential Oil".

The proprietary_blends.json file already covered many blend families
(STIMULANT / NOOTROPIC / PROTEIN / ENZYME / GENERAL / SUPERFOOD etc),
but specific label variants weren't in the ``blend_terms`` lists. Fix:
added 39 new blend_terms across BLEND_PROTEIN / BLEND_ENZYME /
BLEND_SUPERFOOD / BLEND_GENERAL, expanded Vitaberry aliases with
(TM)/Plus variants, and created a new NHA_ACTIVAIT_MUSTARD_EO entry
in other_ingredients.

These tests guard the expansion so no one accidentally deletes the new
terms and re-opens the silent-mapping gap.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer

DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


# ---------------------------------------------------------------------------
# BLEND_PROTEIN — amino-acid blend headers
# ---------------------------------------------------------------------------


class TestAminoAcidBlendHeaders:
    @pytest.mark.parametrize("raw", [
        "Amino Acid Blend",
        "Amino Acceleration System",
        "Branched Chain Amino Acid Blend",
        "Natural Amino Complex",
        "Amino Complex",
        "Essential Amino Acid Blend",
        "EAA Blend",
        "EAA Complex",
        "Full-Spectrum Amino Complex",
    ])
    def test_resolves_to_blend_protein(self, normalizer, raw) -> None:
        r = normalizer._resolve_canonical_identity(raw, raw_name=raw)
        assert r is not None and r[0] == "BLEND_PROTEIN", (
            f"{raw!r} should resolve to BLEND_PROTEIN; got {r!r}"
        )


# ---------------------------------------------------------------------------
# BLEND_GENERAL — cross-category support blends
# ---------------------------------------------------------------------------


class TestGeneralSupportBlends:
    @pytest.mark.parametrize("raw", [
        "Eye Health Support",
        "Eye Health Support Blend",
        "Joint Cushion Support Blend",
        "Joint Support Complex",
        "Joint Support Blend",
        "Joint & Mobility Blend",
        "Cognitive Support Blend",
        "Memory Support Blend",
        "Skin Support Blend",
        "Hair Support Blend",
        "Nail Support Blend",
        "Heart Health Blend",
        "Cardiovascular Support Blend",
        "Bone Health Blend",
        "Hormone Support Blend",
    ])
    def test_resolves_to_blend_general(self, normalizer, raw) -> None:
        r = normalizer._resolve_canonical_identity(raw, raw_name=raw)
        assert r is not None and r[0] == "BLEND_GENERAL", (
            f"{raw!r} should resolve to BLEND_GENERAL; got {r!r}"
        )


# ---------------------------------------------------------------------------
# BLEND_SUPERFOOD — salad / greens / veggie blends
# ---------------------------------------------------------------------------


class TestSuperfoodBlends:
    @pytest.mark.parametrize("raw", [
        "Salad Extract",
        "Salad Blend",
        "Vegetable Extract Blend",
        "Veggie Blend",
        "Organic Vegetable Blend",
        "Green Blend",
        "Whole Foods Blend",
        "Whole Food Blend",
    ])
    def test_resolves_to_blend_superfood(self, normalizer, raw) -> None:
        r = normalizer._resolve_canonical_identity(raw, raw_name=raw)
        assert r is not None and r[0] == "BLEND_SUPERFOOD", (
            f"{raw!r} should resolve to BLEND_SUPERFOOD; got {r!r}"
        )


# ---------------------------------------------------------------------------
# BLEND_ENZYME — protease variants
# ---------------------------------------------------------------------------


class TestEnzymeBlends:
    """
    Enzyme-family names that previously silent-mapped. Accept either
    BLEND_ENZYME (proprietary_blends canonical) OR ``digestive_enzymes``
    (IQM canonical, scoreable) as resolution — IQM wins in the reverse-
    index priority order (4 > 8) for names already aliased there, which
    is actually preferable because IQM gives a scoreable parent while
    BLEND_ENZYME is a transparency signal only.
    """

    @pytest.mark.parametrize("raw,acceptable", [
        ("Protease SP",            {"BLEND_ENZYME"}),
        ("Protease Aminogen",      {"BLEND_ENZYME"}),
        ("Aminogen",               {"BLEND_ENZYME", "digestive_enzymes"}),
        ("Enzyme Mix",             {"BLEND_ENZYME", "digestive_enzymes"}),
        ("Enzyme Blend",           {"BLEND_ENZYME", "digestive_enzymes"}),
        ("Enzyme Activity Blend",  {"BLEND_ENZYME", "digestive_enzymes"}),
        ("Digestive Aid Blend",    {"BLEND_ENZYME", "digestive_enzymes"}),
    ])
    def test_resolves_to_enzyme_canonical(self, normalizer, raw, acceptable) -> None:
        r = normalizer._resolve_canonical_identity(raw, raw_name=raw)
        assert r is not None, f"{raw!r} did not resolve"
        assert r[0] in acceptable, (
            f"{raw!r} resolved to {r[0]!r}; acceptable: {acceptable}"
        )


# ---------------------------------------------------------------------------
# Branded blend entries — Vitaberry / ActivAIT
# ---------------------------------------------------------------------------


class TestBrandedBlendEntries:
    @pytest.mark.parametrize("raw,expected_id", [
        ("Vitaberry", "PII_VITABERRY_BRANDED_BLEND"),
        ("Vitaberry Plus", "PII_VITABERRY_BRANDED_BLEND"),
        ("Vitaberry Plus(TM)", "PII_VITABERRY_BRANDED_BLEND"),
        ("Vitaberry Plus TM", "PII_VITABERRY_BRANDED_BLEND"),
        ("ActivAIT", "NHA_ACTIVAIT_MUSTARD_EO"),
        ("ActivAIT Mustard", "NHA_ACTIVAIT_MUSTARD_EO"),
        ("ActivAIT Mustard Essential Oil", "NHA_ACTIVAIT_MUSTARD_EO"),
        ("ActivAIT Mustard Oil", "NHA_ACTIVAIT_MUSTARD_EO"),
    ])
    def test_branded_blend_resolves(self, normalizer, raw, expected_id) -> None:
        r = normalizer._resolve_canonical_identity(raw, raw_name=raw)
        assert r is not None and r[0] == expected_id, (
            f"{raw!r} should resolve to {expected_id!r}; got {r!r}"
        )


# ---------------------------------------------------------------------------
# Data invariant — new blend_terms must stay present
# ---------------------------------------------------------------------------


class TestBlendTermsPresence:
    """Guard against accidental deletion of the D2.3 expansion."""

    def test_blend_protein_has_amino_acid_blend(self) -> None:
        data = json.loads((DATA_DIR / "proprietary_blends.json").read_text())
        bp = next(e for e in data["proprietary_blend_concerns"] if e.get("id") == "BLEND_PROTEIN")
        terms_lower = [t.lower() for t in bp.get("blend_terms", [])]
        for required in ("amino acid blend", "amino acceleration system", "natural amino complex"):
            assert required in terms_lower, (
                f"Sprint D2.3 regression: '{required}' removed from BLEND_PROTEIN "
                f"blend_terms — this will re-open silent mapping on ~20 label variants."
            )

    def test_blend_general_has_support_blend_variants(self) -> None:
        data = json.loads((DATA_DIR / "proprietary_blends.json").read_text())
        bg = next(e for e in data["proprietary_blend_concerns"] if e.get("id") == "BLEND_GENERAL")
        terms_lower = [t.lower() for t in bg.get("blend_terms", [])]
        for required in ("eye health support", "joint cushion support blend", "cognitive support blend"):
            assert required in terms_lower

    def test_blend_enzyme_has_protease_variants(self) -> None:
        data = json.loads((DATA_DIR / "proprietary_blends.json").read_text())
        be = next(e for e in data["proprietary_blend_concerns"] if e.get("id") == "BLEND_ENZYME")
        terms_lower = [t.lower() for t in be.get("blend_terms", [])]
        for required in ("protease sp", "protease aminogen", "aminogen"):
            assert required in terms_lower

    def test_activait_entry_exists(self) -> None:
        data = json.loads((DATA_DIR / "other_ingredients.json").read_text())
        entries = [e for e in data.get("other_ingredients", [])
                   if isinstance(e, dict) and e.get("id") == "NHA_ACTIVAIT_MUSTARD_EO"]
        assert len(entries) == 1, "NHA_ACTIVAIT_MUSTARD_EO entry must exist"
        aliases_lower = [a.lower() for a in entries[0].get("aliases", [])]
        for required in ("activait", "activait mustard essential oil"):
            assert required in aliases_lower


# ---------------------------------------------------------------------------
# Cleaner-level: synthetic row carrying a blend header now maps + has canonical
# ---------------------------------------------------------------------------


class TestCleanerRowBuilderHonorsBlendHeaders:
    """End-to-end contract: cleaner emits mapped=True + canonical_id for blend headers."""

    def _make_row(self, name: str) -> dict:
        return {
            "name": name,
            "order": 1,
            "quantity": 500,
            "unit": "mg",
            "ingredientGroup": name,
        }

    @pytest.mark.parametrize("name", [
        "Amino Acid Blend",
        "Eye Health Support",
        "Protease SP",
        "Salad Extract",
        "Vitaberry Plus(TM)",
        "ActivAIT Mustard Essential Oil",
    ])
    def test_cleaner_assigns_canonical_and_keeps_mapped(self, normalizer, name) -> None:
        row = self._make_row(name)
        result = normalizer._process_single_ingredient_enhanced(row, is_active=True)
        if isinstance(result, list):
            result = result[0]
        assert result is not None
        assert result.get("mapped") is True, (
            f"{name!r}: cleaner should emit mapped=True post-D2.3 (was silently-mapped "
            f"pre-D2.3). Got mapped={result.get('mapped')}, canonical_id="
            f"{result.get('canonical_id')}."
        )
        assert result.get("canonical_id") is not None, (
            f"{name!r}: cleaner must emit canonical_id post-D2.3."
        )
