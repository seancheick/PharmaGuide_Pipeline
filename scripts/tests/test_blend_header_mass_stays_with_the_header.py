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
    from scoring_v4.modules.sports_dose import _score_primary

    # This label discloses a 250 mg BCAA preparation, not its individual amino
    # amounts. Preserve the existing aggregate band without lending its mass to
    # leucine or counting its header as an individually dosed sports ingredient.
    assert not any(r.get("canonical_id") == "branched_chain_amino_acids"
                   for r in sports_dosed_rows(enriched))
    assert _score_primary(enriched, "bcaa") == (11.4, "bcaa_completed_no_general_benchmark")


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
    assert "opaque_primary_sports_blend" not in result["penalties"]
    # Dose V4.1 section 2.3: the named actives' hidden amounts take the neutral.
    assert result["components"]["sports_primary_active_dose"] == 11.4
    assert result["metadata"]["dose_basis"] == "hidden_amount_neutral"

    # The public Dose explains the hidden amount instead of claiming a benchmark.
    from scoring_v4.scored_artifact import build_scored_artifact
    dose = build_scored_artifact(enriched)["quality_pillars_v4"]["dose"]
    assert dose["score"] == 11.4
    assert dose["reason"] == ("The main ingredient's amount is hidden in a proprietary blend, so its "
                              "dose cannot be assessed; Dose takes the neutral assessment value.")


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
    dose = scored["_v4_module_breakdown"]["dimensions"]["dose"]["metadata"]
    sensoril = next(row for row in rows if row.get("name") == "Sensoril")
    assert sensoril["raw_source_path"] == "ingredientRows[3]"
    assert sensoril["quantity"] == 250
    [assessment] = dose["reference_assessments"]
    assert assessment["canonical_id"] == "ashwagandha"
    assert assessment["amount"] == assessment["per_day_min"] == assessment["per_day_max"] == 250
    # Source exposure is retained without reintroducing the retired window or
    # borrowing the separate 1000 mg fungal blend's mass.
    assert dose["botanical_dose_band"] == "disclosed_no_reference"
    assert scored["quality_pillars_v4"]["dose"]["score"] == 11.4


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
    # The disclosed preparation keeps its own recognized identity and extract
    # quality (plant part is a Transparency fact since V4.1 Step 4).
    assert components.get("recognized_botanical_identity", 0) > 0
    assert components.get("extract_not_whole_herb", 0) > 0


def test_disclosed_bcaa_children_keep_their_distinct_cleaner_identities():
    """Source-form recognition cannot hide an explicitly dosed amino acid."""
    from enhanced_normalizer import EnhancedDSLDNormalizer

    raw = json.loads((FIXTURES / "bcaa_59952_raw.json").read_text())
    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    children = {row["raw_source_path"]: row for row in cleaned["activeIngredients"]
                if ".nestedRows[" in row["raw_source_path"]}
    assert [(children[f"ingredientRows[0].nestedRows[{i}]"]["canonical_id"],
             children[f"ingredientRows[0].nestedRows[{i}]"]["quantity"],
             children[f"ingredientRows[0].nestedRows[{i}]"]["cleaner_row_role"])
            for i in range(3)] == [
        ("l_leucine", 250.0, "active_scorable"),
        ("l_isoleucine", 125.0, "active_scorable"),
        ("l_valine", 125.0, "active_scorable"),
    ]
    assert [(row["quantity"], row["unit"], row["raw_source_path"])
            for row in cleaned["activeIngredients"]
            if row["canonical_id"] == "branched_chain_amino_acids"] == [
        (500.0, "mg", "ingredientRows[0]")]
