"""A scientific name in a label's forms names the plant, not a preparation.

PR #181 restored the identity of these rows and they were then held as
``disclosed_form_unmapped``:

- BulkSupplements 312995 (and 313496-313524) "Barley Grass", form "Hordeum vulgare"
  (DSLD botanical, group Barley). The binomial is the species of the row's own
  identity: a botanical_ingredients latin_name that the shared identity
  registry also records as a name of barley_grass. The label prints no preparation, so the row
  reads barley_grass's authored unspecified form.
- Nature's Way 204040 "Soy Isoflavones extract", forms "Isoflavones" and
  "Soybean". Soybean is the plant the isoflavones come from: the curated source
  terms already name "soy", "soybeans" and "glycine max" (form curation batch 9).

A binomial of another species, and any other curated name that states a
preparation, brand or different substance, still stays unmapped.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3
    logging.disable(logging.INFO)
    return SupplementEnricherV3()


def _enrich(enricher, pid):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    raw = json.loads((FIXTURES / f"held_form_{pid}_raw.json").read_text())
    enriched, _ = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    return enriched


@pytest.mark.parametrize("pid, name, canonical, form, bio", [
    ("312995", "Barley Grass", "barley_grass", "barley grass (unspecified)", 5.0),
    ("204040", "Soy Isoflavones extract", "isoflavones", "isoflavones (unspecified)", 8.0),
])
def test_a_species_or_source_name_in_forms_is_not_a_held_form(enricher, pid, name, canonical, form, bio):
    from score_supplements_v4 import score_product_v4
    enriched = _enrich(enricher, pid)
    row = next(r for r in enriched["ingredient_quality_data"]["ingredients"] if r["name"] == name)
    assert (row["canonical_id"], row["form_id"], row["bio_score"]) == (canonical, form, bio)
    assert row["unmapped_forms"] == []
    assert row["form_match_status"] == "n/a"
    readiness = score_product_v4(enriched)["v4_breakdown"]["assessment_readiness"]
    assert "disclosed_form_unmapped" not in readiness["identity"]["blocking_contract_findings"]
    assert readiness["is_live_ready"] is True


@pytest.mark.parametrize("parent, label, token", [
    # Another species' binomial is not this identity.
    ("wheatgrass", "Wheatgrass", "Hordeum vulgare"),
    ("black_cherry", "Black Cherry", "Cerasus avium"),
    ("barley_grass", "Barley Grass", "Triticum aestivum"),
    # A curated name of the parent that is not its species name states a
    # preparation, brand or other substance; IQM lacks it, so it stays held.
    ("turmeric", "Turmeric", "Curcumin Powder"),
    ("cayenne_pepper", "Cayenne Pepper", "Capsimax Capsicum Extract"),
    ("elderberry", "Elderberry", "Elderberry 10:1 Concentrate"),
    ("tart_cherry", "CherryPURE", "Sour Cherry, Powder"),
])
def test_only_the_parents_species_name_restates_it(enricher, parent, label, token):
    match = enricher._match_quality_map(
        label, label, enricher.databases["ingredient_quality_map"],
        cleaned_forms=[{"name": token, "category": "botanical"}], cleaner_canonical_id=parent)
    assert match["match_status"] == "FORM_DISCLOSED_UNMAPPED"
    assert match["unmapped_forms"] == [token]
