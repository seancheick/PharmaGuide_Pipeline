"""A salt token beside its compound is one compound; a brand is not a nutrient.

Register Q35. `_build_form_info_from_cleaned` turns the cleaner's forms[] into
match candidates:

(a) "Folate (as (6S)-5-Methyltetrahydrofolic Acid, Glucosamine Salt)" is
    Quatrefolic and "... Calcium Salt" is Metafolin. The cleaner splits the
    parenthetical into a compound token and a counter-ion token; the salt token
    alone matches nothing, so the row read an unmapped disclosed form and the
    product was held (223572, 248756, 321975, 323711; aliasing the salt token
    alone made the row two forms instead, 845d17c5). The salt now folds into
    its neighbouring compound, tried as "compound, salt" then the compound.
(b) When the cleaner extracts a brand token ("Albion"), the match name is the
    brand and a bare salt qualifier built "Albion malate" instead of
    "Magnesium malate" (328832, 322515). The nutrient builds the salt too.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


def _rows(pipeline, pid, canonical):
    normalizer, enricher = pipeline
    raw = json.loads((FIXTURES / f"q35_{pid}_raw.json").read_text())
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
    return [r for r in enriched["ingredient_quality_data"]["ingredients"]
            if r.get("canonical_id") == canonical and r.get("form_match_status") != "n/a"]


@pytest.mark.parametrize("pid,forms", [
    ("223572", {"quatrefolic"}),
    ("323711", {"quatrefolic"}),
    ("248756", {"metafolin"}),
    # "L-5-Methyltetrahydrofolic Acid" + "Glucosamine Salt": no IQM alias names
    # the pair, so the compound reads its own named form, never an unmapped salt.
    ("321975", {"5-methyltetrahydrofolate (5-MTHF)"}),
])
def test_a_folate_salt_reads_one_compound(pipeline, pid, forms):
    rows = _rows(pipeline, pid, "vitamin_b9_folate")
    assert rows and {r.get("matched_form") for r in rows} == forms
    assert all(r.get("form_match_status") == "mapped" for r in rows)


@pytest.mark.parametrize("pid,form", [
    ("328832", "magnesium malate"),
    ("322515", "magnesium glycinate"),
])
def test_an_albion_salt_reads_the_nutrient_salt(pipeline, pid, form):
    rows = [r for r in _rows(pipeline, pid, "magnesium") if "Albion" in (r.get("name") or "")]
    assert [(r.get("matched_form"), r.get("form_match_status")) for r in rows] == [(form, "mapped")]
