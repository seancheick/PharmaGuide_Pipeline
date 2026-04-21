"""
Sprint D2.7 + D3.4 + D3.6 regression tests — post-D5.1 gap closures.

Context: after the first full D5.1 pipeline run, 19 of 20 brands hit
``blocked=0``. GNC had 9 blocks + Doctor's Best had 4 minor unmapped
rows. Root-cause analysis found 4 categories:

1. **Coverage-gate policy** — proprietary_blends-routed ingredients
   (Velositol / MyoTor / Tesnor / Metabolaid) are recognized by the
   cleaner but the coverage gate counted them as unmatched, blocking
   products with one exotic branded blend out of 9 scorable actives.
2. **Missing blend aliases** — "100% Whey Protein Blend" wasn't in
   proprietary_blends blend_terms.
3. **Qualifier-strip gaps** — ``", Powder"`` / leading ``N%`` /
   leading adjectives (organic / whole leaf) weren't stripped on
   the fallback lookup.
4. **Doctor's Best specifics** — Glycolipids / Phytosome
   Curcuminoids / Serrapeptase Enzyme / Lutein 2020 Marigold labels
   needed targeted DB entries.

These tests lock in the fixes so the gaps don't re-open.
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
# D2.7.1 — enricher routes proprietary_blends → recognized_non_scorable
# ---------------------------------------------------------------------------


class TestProprietaryBlendsRecognizedNonScorable:
    """When a row's canonical_source_db is proprietary_blends, the enricher
    must route it through the recognized_non_scorable path (not unmapped)."""

    def test_enricher_source_has_proprietary_blends_policy(self) -> None:
        source = Path("scripts/enrich_supplements_v3.py").read_text()
        # Match the D2.7.1 fix signature — canonical_src check + explicit tag.
        assert "canonical_source_db" in source and "'proprietary_blends'" in source, (
            "D2.7.1 fix missing: enricher must check canonical_source_db == "
            "'proprietary_blends' before treating a row as unmapped."
        )
        assert "proprietary_blend_member" in source, (
            "D2.7.1 fix must tag routed rows with recognition_reason="
            "'proprietary_blend_member' for gate exclusion."
        )


# ---------------------------------------------------------------------------
# D2.7.2 — BLEND_PROTEIN covers "100% Whey Protein Blend" etc.
# ---------------------------------------------------------------------------


class TestWheyBlendAliasesExpanded:
    @pytest.mark.parametrize("raw", [
        "100% Whey Protein Blend",
        "Whey Protein Blend",
        "Whey Protein Complex",
        "Whey Protein Matrix",
        "Complete Protein Blend",
        "Multi-source Protein Blend",
    ])
    def test_whey_blend_resolves(self, normalizer, raw) -> None:
        r = normalizer._resolve_canonical_identity(raw, raw_name=raw)
        assert r is not None and r[0] == "BLEND_PROTEIN", (
            f"{raw!r} should resolve to BLEND_PROTEIN; got {r!r}"
        )


# ---------------------------------------------------------------------------
# D2.7.3 — qualifier strip handles ", Powder", leading percent, adjectives
# ---------------------------------------------------------------------------


class TestExtendedQualifierStrip:
    @pytest.mark.parametrize("raw,expected_contains", [
        ("Hawthorn, Powder",                "hawthorn"),
        ("Fenugreek, Powder",               "fenugreek"),
        ("Curcumin Phytosome:",             "curcumin"),
        ("Fenugreek Extract :",             "fenugreek"),
        ("88% organic whole leaf Aloe vera","aloe_vera"),
        ("100% Whey Protein Blend",         "BLEND_PROTEIN"),
        ("Organic Aloe Vera",               "aloe_vera"),
        ("whole leaf Aloe Vera",            "aloe_vera"),
        ("raw Turmeric",                    "turmeric"),
    ])
    def test_strip_recovers_canonical(self, normalizer, raw, expected_contains) -> None:
        r = normalizer._resolve_canonical_identity(raw, raw_name=raw)
        assert r is not None, f"{raw!r} did not resolve"
        assert expected_contains.lower() in (r[0] or "").lower(), (
            f"{raw!r} resolved to {r[0]!r}; expected canonical containing "
            f"{expected_contains!r}."
        )


class TestStripPreservesRealNames:
    """The extended strip must not over-strip valid supplement names."""

    @pytest.mark.parametrize("raw,expected", [
        # Trailing colon only — strip should remove it
        ("Vitamin C:",                  "Vitamin C"),
        # No qualifier — untouched
        ("Vitamin C",                   "Vitamin C"),
        # Mid-name 'powder' is NOT a trailing qualifier
        ("Powder Coating Ingredient",   "Powder Coating Ingredient"),
        # Embedded percentages in body stay
        ("Curcumin 95% extract",        "Curcumin 95% extract"),
    ])
    def test_strip_does_not_corrupt(self, normalizer, raw, expected) -> None:
        got = normalizer._strip_qualifier_suffixes(raw)
        assert got == expected, f"Strip corrupted {raw!r}: got {got!r}"


# ---------------------------------------------------------------------------
# D3.4 — form-alias additions for gingerol / PAC / Bioperinie / phytosome curcuminoids
# ---------------------------------------------------------------------------


class TestD34FormAliases:
    @pytest.mark.parametrize("raw,expected_canonical", [
        ("Phytosome Curcuminoids",       "curcumin"),
        ("Curcumin Phytosome:",          "curcumin"),
        # Marigold is a pre-existing lutein alias — sanity check
        ("Marigold flower extract",      "lutein"),
    ])
    def test_form_alias_resolves(self, normalizer, raw, expected_canonical) -> None:
        r = normalizer._resolve_canonical_identity(raw, raw_name=raw)
        assert r is not None and r[0] == expected_canonical, (
            f"{raw!r} -> {r!r}; expected canonical_id={expected_canonical!r}"
        )

    def test_gingerol_form_alias_present(self) -> None:
        iqm = json.loads((DATA_DIR / "ingredient_quality_map.json").read_text())
        ginger_std = iqm.get("ginger", {}).get("forms", {}).get("ginger extract standardized", {})
        aliases_lower = [a.lower() for a in ginger_std.get("aliases", [])]
        for req in ("gingerol", "gingerols", "6-gingerol"):
            assert req in aliases_lower, (
                f"D3.4 regression: {req!r} missing from ginger.forms['ginger extract standardized']."
            )

    def test_pac_canonical_exists_with_cranberry_crosslink(self) -> None:
        """Generic PAC aliases live on the dedicated `pac` IQM canonical AND
        on cranberry's standardized form (pac is cranberry's standardization
        marker — same pattern as vitexin/hawthorn, silymarin/milk_thistle).
        The cross-ingredient allowlist in test_ingredient_quality_map_schema.py
        permits this overlap because form lookup is parent-scoped after
        canonical resolution."""
        iqm = json.loads((DATA_DIR / "ingredient_quality_map.json").read_text())
        # Dedicated pac canonical must exist and cover the generic terms
        pac = iqm.get("pac", {})
        pac_aliases = [a.lower() for a in pac.get("forms", {}).get("pac (unspecified)", {}).get("aliases", [])]
        for req in ("pac", "proanthocyanidins type a", "cranberry pacs"):
            assert req in pac_aliases, (
                f"{req!r} missing from pac canonical — generic PAC aliases "
                f"must live here."
            )
        # Cranberry form: cranberry-specific PAC aliases + generic singular/plural
        # (needed for label-text "Proanthocyanidin" to form-match when parent
        # is already resolved to cranberry by the cleaner).
        cran = iqm.get("cranberry", {}).get("forms", {}).get("cranberry extract (25% proanthocyanidins)", {})
        cran_aliases = [a.lower() for a in cran.get("aliases", [])]
        for req in (
            "cranberry pacs",
            "cranberry proanthocyanidins",
            "proanthocyanidin",
            "proanthocyanidins",
        ):
            assert req in cran_aliases, (
                f"D2.9.1 regression: {req!r} missing from cranberry extract form."
            )

    def test_piperine_bioperinie_ocr_alias_present(self) -> None:
        iqm = json.loads((DATA_DIR / "ingredient_quality_map.json").read_text())
        pip = iqm.get("piperine", {}).get("forms", {}).get("piperine (unspecified)", {})
        aliases_lower = [a.lower() for a in pip.get("aliases", [])]
        assert "bioperinie" in aliases_lower, (
            "D3.4 regression: OCR-typo 'bioperinie' alias missing from piperine form."
        )


# ---------------------------------------------------------------------------
# D3.6 — Doctor's Best specific-label coverage
# ---------------------------------------------------------------------------


class TestDoctorsBestGapClosures:
    @pytest.mark.parametrize("raw,expected_source,expected_id_contains", [
        ("Serrapeptase Enzyme",                      "ingredient_quality_map", "digestive_enzymes"),
        ("Serrapeptidase",                           "ingredient_quality_map", "digestive_enzymes"),
        ("Glycolipids",                              "other_ingredients",      "NHA_GLYCOLIPIDS"),
        ("Glycolipid",                               "other_ingredients",      "NHA_GLYCOLIPIDS"),
        ("Lutein 2020 Marigold flower extract",      "ingredient_quality_map", "lutein"),
        ("Lutein 2020",                              "ingredient_quality_map", "lutein"),
    ])
    def test_label_variant_resolves(self, normalizer, raw, expected_source, expected_id_contains) -> None:
        r = normalizer._resolve_canonical_identity(raw, raw_name=raw)
        assert r is not None and r[0] is not None, f"{raw!r} did not resolve"
        assert r[1] == expected_source, (
            f"{raw!r} resolved to source {r[1]!r}; expected {expected_source!r}"
        )
        assert expected_id_contains.lower() in (r[0] or "").lower(), (
            f"{raw!r} resolved to id {r[0]!r}; expected to contain {expected_id_contains!r}"
        )


class TestGlycolipidsEntryExists:
    def test_nha_glycolipids_entry_in_other_ingredients(self) -> None:
        data = json.loads((DATA_DIR / "other_ingredients.json").read_text())
        entries = [e for e in data.get("other_ingredients", [])
                   if isinstance(e, dict) and e.get("id") == "NHA_GLYCOLIPIDS"]
        assert len(entries) == 1
        entry = entries[0]
        assert entry.get("category") == "lipid_structural"
        assert entry.get("is_additive") is True
        assert entry.get("cui_status") == "no_confirmed_umls_match"
