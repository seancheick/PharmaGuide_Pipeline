"""
Expanded source-descriptor recognition for _is_source_material_descriptor_for_fallback_audit.

The form_fallback_audit_report's action_needed_differs bucket is being flooded
with rows where the raw label text is genuinely a SOURCE descriptor (animal
tissue, plant species, species binomial, yeast culture, mineral source claim,
marker compound) rather than a missing IQM form alias.

Examples from real pipeline output (2026-04-19 audit across 15 brands):
  - Pancreatin with form "Pancreas" (DSLD forms[].category="animal part or source")
  - Vitamin B6 with form "S. cerevisiae culture"
  - Superoxide Dismutase with form "Cantaloupe" (GliSODin source)
  - Iron with form "Ionic Plant Based Minerals"
  - Magnesium with form "Algae, Dead Sea Minerals"
  - Vitamin C with form "Emblic Fruit Extract"
  - Digestive enzymes with forms "Carica papaya extract, dried, purified",
    "Ananas comosus extract, dried, purified"
  - Sulforaphane with form "Broccoli Flower Juice, Broccoli Stem Juice"
  - Fish Oil with form "USA wild-caught Alaska Pollock"

In all these cases the enricher's parent-default fallback IS the correct
clinical form (pancreatic enzymes animal-derived, vitamin b6 unspecified, etc.);
the row is flagged only because the raw text doesn't literally match an alias.

These should classify as audit noise with reason="source_material_descriptor".
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


class TestAnimalTissueSources:
    """Animal tissues / organs should be recognized as source descriptors."""

    @pytest.mark.parametrize("text", [
        "pancreas",
        "sus scrofa pancreas",
        "sus scrofa pancreas extract",
        "sus scrofa pancreas extract, dried, purified",
        "bos taurus pancreas",
        "bos taurus pancreas extract",
        "bos taurus pancreas extract, dried, purified",
        "bos taurus pancreas extract, dried, purified, sus scrofa pancreas extract, dried, purified",
    ])
    def test_pancreas_variants(self, enricher, text):
        assert enricher._is_source_material_descriptor_for_fallback_audit(text), text


class TestLatinBinomialSources:
    """Latin genus-species binomials naming the source organism."""

    @pytest.mark.parametrize("text", [
        "carica papaya extract",
        "carica papaya extract, dried, purified",
        "carica papaya extract, dried purified aqueous",
        "ananas comosus extract",
        "ananas comosus extract, dried, purified",
        "brassica oleracea italica sprout concentrate, brassica oleracea italica whole plant concentrate",
        "camellia sinensis",
        "panax notoginseng, rosa roxburghii",
        "cerasus vulgaris mill fruit extract",
        "lepidium meyenii, powder",
        "sambucus nigra l.",
        "sambucus nigra fruit extract, concentrate",
        "cimicifuga racemosa root extract",
        "paullinia cupana seed extract",
        "withania somnifera leaf extract, withania somnifera root extract",
    ])
    def test_latin_binomial_with_tissue(self, enricher, text):
        assert enricher._is_source_material_descriptor_for_fallback_audit(text), text


class TestYeastCultureSources:
    """Yeast fermentation cultures are source substrates, not nutrient forms."""

    @pytest.mark.parametrize("text", [
        "s. cerevisiae culture",
        "s cerevisiae culture",
        "saccharomyces cerevisiae",
        "saccharomyces cerevisiae culture",
    ])
    def test_cerevisiae_culture(self, enricher, text):
        assert enricher._is_source_material_descriptor_for_fallback_audit(text), text


class TestWholeFoodPlantSources:
    """Whole plant / fruit sources (amla, emblic, moringa, broccoli, cantaloupe)."""

    @pytest.mark.parametrize("text", [
        "emblic fruit extract",
        "moringa",
        "cantaloupe",
        "broccoli flower juice, broccoli stem juice",
        "peach fruit extract",
        "organic black elderberry juice concentrate",
    ])
    def test_plant_source_descriptors(self, enricher, text):
        assert enricher._is_source_material_descriptor_for_fallback_audit(text), text


class TestFishAndMarineSources:
    """Fish species and marine source descriptors."""

    @pytest.mark.parametrize("text", [
        "fish",
        "cod fish",
        "usa wild-caught alaska pollock",
        "omega-3 fatty acids, sardines",
    ])
    def test_marine_sources(self, enricher, text):
        assert enricher._is_source_material_descriptor_for_fallback_audit(text), text


class TestMineralSourceClaims:
    """Generic mineral-source marketing claims (algae, ionic, dead sea, trace)."""

    @pytest.mark.parametrize("text", [
        "algae, dead sea minerals",
        "algae, sea mineral salt",
        "ionic plant based minerals",
        "ionic minerals",
        "mineral complex",
    ])
    def test_mineral_source_claims(self, enricher, text):
        assert enricher._is_source_material_descriptor_for_fallback_audit(text), text


class TestMarkerCompoundsAsStandardization:
    """Marker compounds / constituents should classify as standardization markers."""

    @pytest.mark.parametrize("text", [
        "polyphenols, punicalagin",
        "beta-caryophyllene, phytocannabinoids, terpenes",
        "spm, resolvins, protectins",
        "resolvins, protectins",
        "biologically active sterols, fatty acids",
        "organic acids",
    ])
    def test_marker_compound(self, enricher, text):
        # Either source_material_descriptor OR standardization_marker is acceptable
        assert (
            enricher._is_source_material_descriptor_for_fallback_audit(text)
            or enricher._is_standardization_marker_for_fallback_audit(text)
        ), text


class TestMarketingBlendLabels:
    """Marketing blend labels that the cleaner surfaces as form text."""

    @pytest.mark.parametrize("text", [
        "organic immune blend",
        "organic food blend",
        "beauty blend",
        "trace mineral complex",
    ])
    def test_marketing_blend(self, enricher, text):
        assert enricher._is_source_material_descriptor_for_fallback_audit(text), text


class TestVitaminComplexMarketingLabels:
    """Hybrid blend labels (Vitamin K Complex, B Complex) lacking a specific form."""

    @pytest.mark.parametrize("text", [
        "k complex",
        "vitamin k complex",
        "k2 vitamin k complex",
        "b complex",
        "vitamin b complex",
        "d complex",
        "vitamin d complex",
    ])
    def test_vitamin_complex_labels(self, enricher, text):
        assert enricher._is_source_material_descriptor_for_fallback_audit(text), text


class TestNegativeCases:
    """Real forms that must NOT be misclassified as source descriptors."""

    @pytest.mark.parametrize("text", [
        # Real mineral salts — must stay actionable as form-alias gaps
        "calcium citrate",
        "magnesium bisglycinate",
        "zinc picolinate",
        "ferric saccharate",
        "calcium caprylate",
        "dimagnesium phosphate",
        "eggshell calcium",
        "sodium tetraborate",
        "manganese dioxide",
        # Real chemistry / derivatives
        "methylcobalamin",
        "pyridoxal-5-phosphate",
        "d-alpha-tocopherol",
        # Real branded delivery systems
        "phospholipid complex",
        "time-sorb",
        "chelamax",
        # Bacterial strains that look binomial but name real probiotic strains
        # must stay out of noise (they are form-specificity action items, not
        # source descriptors). Tested separately: lb-87 etc. are strain codes.
    ])
    def test_real_forms_not_misclassified(self, enricher, text):
        assert not enricher._is_source_material_descriptor_for_fallback_audit(text), (
            f"{text!r} is a real form alias gap, not a source descriptor"
        )
