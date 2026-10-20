"""A whole tart cherry powder is not an extract.

"sour cherry, powder", "tart cherry powder", "tart cherry fruit powder" and
"cherrypure tart cherry fruit & skin powder" were aliases of the 'tart cherry
extract' form (bio 6). Since 6d7d535d0 a printed powder never reads an extract
form, so they matched nothing and Life Extension 328723 "CherryPURE" (form
"Sour Cherry, Powder") was held as disclosed_form_unmapped. CherryPURE is a
freeze-dried tart cherry skin powder (Shoreline Fruit), not an established
solvent extract; IQM has no powder form, so the label reads tart cherry's
authored unspecified form, as "Prunus cerasus, Powder" already does.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
POWDER_ALIASES = ["sour cherry, powder", "tart cherry powder", "tart cherry fruit powder",
                  "cherrypure tart cherry fruit & skin powder"]


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3
    logging.disable(logging.INFO)
    return SupplementEnricherV3()


def test_cherrypure_powder_reads_unspecified_tart_cherry(enricher):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from score_supplements_v4 import score_product_v4
    raw = json.loads((FIXTURES / "held_form_328723_raw.json").read_text())
    enriched, _ = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    row = next(r for r in enriched["ingredient_quality_data"]["ingredients"] if r["name"] == "CherryPURE")
    assert (row["canonical_id"], row["form_id"], row["bio_score"]) == ("tart_cherry", "tart cherry (unspecified)", 5.0)
    assert row["unmapped_forms"] == [] and row["form_match_status"] == "n/a"
    assert score_product_v4(enriched)["v4_breakdown"]["assessment_readiness"]["is_live_ready"] is True


@pytest.mark.parametrize("token, form", [
    ("Sour Cherry, Powder", "tart cherry (unspecified)"),
    ("Tart Cherry Powder", "tart cherry (unspecified)"),
    ("Tart Cherry Fruit Powder", "tart cherry (unspecified)"),
    # A printed extract keeps the extract form.
    ("Tart Cherry Extract", "tart cherry extract"),
    ("Montmorency Tart Cherry Extract", "tart cherry extract"),
])
def test_a_printed_powder_is_never_read_as_the_extract(enricher, token, form):
    match = enricher._match_quality_map(
        "Tart Cherry", "Tart Cherry", enricher.databases["ingredient_quality_map"],
        cleaned_forms=[{"name": token, "category": "botanical"}], cleaner_canonical_id="tart_cherry")
    assert match.get("match_status") != "FORM_DISCLOSED_UNMAPPED"
    assert match["form_id"] == form


def test_no_powder_alias_sits_on_the_tart_cherry_extract_form():
    iqm = json.loads((Path(__file__).resolve().parents[1] / "data" / "ingredient_quality_map.json").read_text())
    forms = iqm["tart_cherry"]["forms"]
    extract = {a.lower() for a in forms["tart cherry extract"]["aliases"]}
    unspecified = {a.lower() for a in forms["tart cherry (unspecified)"]["aliases"]}
    assert not extract & set(POWDER_ALIASES)
    assert set(POWDER_ALIASES) <= unspecified
