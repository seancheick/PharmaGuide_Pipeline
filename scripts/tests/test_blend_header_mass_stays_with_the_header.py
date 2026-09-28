"""A blend header's mass stays with the header when the header names itself.

`_derive_blend_header_anchor_from_nested_child` gives an unnamed blend's mass an
identity by borrowing a child's (a "Proprietary Blend 500 mg" of ashwagandha
root and extract). It also fired when the header already carried its own
identity anchor, so "2:1:1 BCAA 6,000 mg" produced a BCAA aggregate row AND an
`l_leucine` row of 6,000 mg beside the label's own 3,000 mg leucine child
(270253), and GNC 67304's undosed leucine inherited the whole 250 mg BCAA header
(audit RR-04, reproduced by Codex). Every reader of `l_leucine` then depended on
row order to ignore it.

The header's own anchor is the blend-level fact; no child inherits it. A child
with its own amount keeps that amount.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def _rows(label):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_input_contract import get_scoring_ingredients

    logging.disable(logging.INFO)
    raw = json.loads((FIXTURES / label).read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    return get_scoring_ingredients(enriched, strict=True).rows


@pytest.mark.parametrize("label,header_mg,leucine_mg", [
    ("bcaa_270253_raw.json", 6000.0, [3000.0]),
    ("bcaa_59952_raw.json", 500.0, [250.0]),
    ("bcaa_67304_raw.json", 250.0, []),
])
def test_the_header_mass_is_not_a_child_dose(label, header_mg, leucine_mg):
    rows = _rows(label)
    bcaa = [r for r in rows if r.get("canonical_id") == "branched_chain_amino_acids"]
    assert [(r.get("quantity"), r.get("evidence_scope")) for r in bcaa] == [(header_mg, "blend_level")]
    assert [r.get("quantity") for r in rows if r.get("canonical_id") == "l_leucine"] == leucine_mg
    assert not any(r.get("reason") == "identity_bearing_blend_header_mass_from_nested_child" for r in rows)
