"""Star anise is not anise.

IQM 'anise (unspecified)' (Anise, Pimpinella anisum; GSRS 21C2F5E8RE "ANISE",
parent PIMPINELLA ANISUM WHOLE) listed "star anise" and "illicium verum"
(cc2b80699). Star anise is Illicium verum (Schisandraceae; GSRS XKC1657P78
"STAR ANISE", parent ILLICIUM VERUM WHOLE), a different plant with its own
caution (do not confuse with toxic Illicium anisatum). botanical_ingredients
already owns it as star_anise, so star anise rows resolve there, not to anise.
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


@pytest.mark.parametrize("pid, name", [
    ("311657", "Star Anise Fruit & Seed Extract"),
    ("330859", "Star Anise Fruit Extract"),
    # Control: already the star anise record before the fix.
    ("252910", "Star Anise extract"),
])
def test_a_star_anise_row_is_never_anise(enricher, pid, name):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    raw = json.loads((FIXTURES / f"star_anise_{pid}_raw.json").read_text())
    enriched, _ = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    row = next(r for r in enriched["ingredient_quality_data"]["ingredients"] if r["name"] == name)
    assert row["canonical_id"] == "star_anise"


def test_no_anise_form_names_star_anise():
    iqm = json.loads((Path(__file__).resolve().parents[1] / "data" / "ingredient_quality_map.json").read_text())
    names = {a.lower() for form in iqm["anise"]["forms"].values() for a in form.get("aliases") or []}
    assert not names & {"star anise", "illicium verum"}
