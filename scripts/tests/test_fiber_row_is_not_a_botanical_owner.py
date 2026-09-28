"""A dietary-fiber row is not a botanical, whatever plant it was made from.

Life Extension Keto Brain and Body Boost (233404/233406) lists "FiberSmart
Resistant Starch" 20 g (DSLD category `fiber`, form "from Cassava"), BHB 6 g,
calcium, magnesium and mangiferin 150 mg. The classification contract had no
domain for DSLD's `fiber` category, so the cassava source form made the fiber row
an `herb`; the product became a `botanical_blend` owner and the botanical profile
replaced the Formulation form average (8.7) with 0 and a -4 "unidentified
botanical" penalty: total 40.4 (audit RR-07, reproduced by Codex).

The source plant of an isolated fiber is provenance, not a botanical
intervention: the row is `fiber`, a material non-botanical deliverable, and the
product keeps the generic Formulation path.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module", params=["233404", "233406"])
def enriched(request):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    raw = json.loads((FIXTURES / f"fibersmart_{request.param}_raw.json").read_text())
    product, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    return product


def test_the_fiber_row_is_fiber_not_herb(enriched):
    from scoring_input_contract import build_scoring_classification

    contract = build_scoring_classification(enriched)
    fiber = next(r for r in contract["ingredients"] if r.get("name") == "FiberSmart Resistant Starch")
    assert fiber["ingredient_domain"] == "fiber"
    assert fiber["profile_eligibility"]["botanical"]["eligible"] is False
    assert contract["profile_eligibility"]["botanical"]["eligible"] is False


def test_the_product_keeps_its_form_score(enriched):
    from scoring_v4.modules.botanical_profile import is_botanical_product
    from scoring_v4.scored_artifact import build_scored_artifact

    assert is_botanical_product(enriched) is False
    formulation = build_scored_artifact(enriched)["quality_pillars_v4"]["formulation"]
    assert formulation["score"] > 0
