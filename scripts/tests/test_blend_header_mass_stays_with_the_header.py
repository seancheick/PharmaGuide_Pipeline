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


def test_an_unnamed_header_still_lends_its_mass_to_an_undosed_child():
    """GNC Ravage (2219): "Assault Proprietary Blend 5.3 g" names no identity
    (its own anchor is only the name slug) and its children carry no amounts,
    so the blend-level mass stays with the title child identity, as before."""
    rows = _rows("blend_2219_raw.json")
    lent = {(r.get("canonical_id"), r.get("quantity")) for r in rows
            if r.get("reason") == "identity_bearing_blend_header_mass_from_nested_child"}
    assert ("beta_alanine", 3.2) in lent and ("creatine_monohydrate", 3.1) in lent
    assert all(r.get("evidence_scope") == "blend_level" for r in rows
               if r.get("reason") == "identity_bearing_blend_header_mass_from_nested_child")


def test_a_lent_blend_mass_is_not_a_sports_dose():
    """Ravage's "ATP Optimizing Creatine Module 3.1 g" lists creatine
    monohydrate, creatine ethyl ester, creatine AKG, guanidinoacetate, AKG,
    arginine, glycine and methionine with no amounts. The 3.1 g is lent to the
    creatine child as a blend-level anchor, and sports Dose read it as a 3.1 g
    creatine dose: 20/20 (creatine_3_to_10_g). A blend mass lent to a child is
    not that child's individual dose (Codex, RR-04 review); the opaque blend
    is scored as one."""
    import json
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.modules.sports_helpers import sports_dosed_rows

    raw = json.loads((FIXTURES / "blend_2219_raw.json").read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    lent = [r for r in sports_dosed_rows(enriched)
            if r.get("reason") == "identity_bearing_blend_header_mass_from_nested_child"]
    assert lent == []


def test_a_self_named_bcaa_total_stays_a_sports_dose():
    from scoring_v4.modules.sports_helpers import sports_dosed_rows
    import json
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    raw = json.loads((FIXTURES / "bcaa_67304_raw.json").read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    assert any(r.get("canonical_id") == "branched_chain_amino_acids" for r in sports_dosed_rows(enriched))


def test_an_opaque_sports_blend_is_not_an_off_list_primary():
    """Ravage (2219) prints its sports actives only as blend totals (Assault
    Proprietary Blend 5.3 g, ATP Optimizing Creatine Module 3.1 g, ...) and
    discloses calcium, niacin and potassium. The off-list floor took the 5.3 g
    blend as an off-list disclosed primary and credited the vitamins' RDA
    adequacy as sports Dose (19.1/20). A blend total is not one disclosed
    active: the undisclosed blend is scored on its disclosure (Sean,
    2026-09-28, packet item 6)."""
    import json
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.modules.sports_dose import score_dose

    raw = json.loads((FIXTURES / "blend_2219_raw.json").read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    result = score_dose(enriched)
    assert result["metadata"]["dose_basis"] != "generic_dose_proxy_for_offlist_primary"
    assert result["metadata"]["not_evaluable_reason"] == "opaque_primary_sports_blend"
    assert result["penalties"]["opaque_primary_sports_blend"] < 0


def test_nested_botanical_anchor_preserves_identity_without_borrowing_a_child_dose():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_input_contract import get_scoring_ingredients
    from scoring_v4.scored_artifact import build_scored_artifact

    raw = json.loads((FIXTURES / "botanical_blend_321944_raw.json").read_text())
    enriched, errors = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    assert not errors
    rows = get_scoring_ingredients(enriched, strict=True).rows
    anchor = next(row for row in rows if row.get("reason") == "identity_bearing_blend_header_mass_from_nested_child"
                  and row.get("canonical_id") == "cordyceps")
    assert anchor["raw_taxonomy"]["category"] == "botanical"
    assert anchor["raw_taxonomy"]["forms"][0]["category"] == "botanical"
    assert anchor["raw_source_path"] == "ingredientRows[2]"
    assert anchor["quantity"] == 1000
    assert anchor["evidence_scope"] == "blend_level"
    assert "ingredientRows[2].nestedRows[0]" in anchor["linked_rows"]
    scored = build_scored_artifact(enriched)
    assert scored["_v4_module_breakdown"]["dimensions"]["formulation"]["metadata"]["formulation_profile"] == "botanical"


def test_overlapping_constituents_do_not_reconcile_a_partly_disclosed_preparation():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_input_contract import get_scoring_ingredients, profile_owner_candidate_rows
    from scoring_v4.scored_artifact import build_scored_artifact

    raw = json.loads((FIXTURES / "botanical_blend_59514_raw.json").read_text())
    enriched, errors = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    assert not errors
    rows = get_scoring_ingredients(enriched, strict=True).rows
    candidates = profile_owner_candidate_rows(rows, product=enriched)
    assert any(row.get("evidence_type") == "blend_anchor_mass" and row.get("quantity") == 380
               for row in candidates)
    scored = build_scored_artifact(enriched)
    components = scored["_v4_module_breakdown"]["dimensions"]["formulation"]["metadata"]["botanical_formulation"]
    assert components.get("plant_part_disclosed", 0) > 0
    assert components.get("extract_not_whole_herb", 0) > 0
