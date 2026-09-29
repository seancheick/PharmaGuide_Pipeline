"""A three-letter ingredient named in the title is title-named.

`scoring_input_contract._named_in_title` bars title tokens shorter than four
characters so that fragments of longer names ("oil" of "Fish Oil") cannot make
an ingredient claim-prominent. The floor also dropped ingredients whose whole
name is a three-letter token: "Glucosamine/MSM" (182940) marked only
glucosamine as named in its title (register Q39c). A whole one-token name still
has to equal a title token exactly.
"""
import json
import logging
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def _roles(pid):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_input_contract import classify_ingredient_roles, get_scoring_ingredients

    logging.disable(logging.INFO)
    raw = json.loads((FIXTURES / f"title_short_name_{pid}_raw.json").read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    rows = get_scoring_ingredients(enriched, strict=True).rows
    return {r.get("name"): role["role"] for r, role in zip(rows, classify_ingredient_roles(enriched, rows=rows))}


def test_msm_is_named_in_glucosamine_msm():
    roles = _roles("182940")
    assert roles["MSM"] == "claim_prominent"
    assert roles["Glucosamine Sulfate"] == "claim_prominent"


def test_a_short_fragment_of_a_longer_name_still_does_not_match():
    from scoring_input_contract import _named_in_title

    assert _named_in_title({"name": "MSM", "canonical_id": "msm"}, "glucosamine msm")
    assert not _named_in_title({"name": "Fish Oil", "canonical_id": "fish_oil"}, "oil of oregano")
    assert not _named_in_title({"name": "MSM", "canonical_id": "msm"}, "msmx complex")
