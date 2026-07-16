"""RC1: classification sees genuine unresolved label actives, scoring does not.

The two populations must come from one scoring-input owner.  This suite pins
the exact boundary that the earlier 3,662-product broad detector blurred:
``active_unmapped`` + ``no_quality_map_match`` is a label active; nutrition
facts, recognized non-scorables, additives/excipients and structural rows are
not.
"""

from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from supplement_taxonomy import classify_supplement  # noqa: E402


def _mapped(
    name: str,
    canonical_id: str,
    category: str,
    *,
    path: str = "ingredientRows[0]",
) -> dict:
    return {
        "name": name,
        "canonical_id": canonical_id,
        "category": category,
        "quantity": 100.0,
        "unit": "mg",
        "has_dose": True,
        "mapped": True,
        "mapped_identity": True,
        "scoreable_identity": True,
        "identity_disposition": "clean",
        "source_section": "active",
        "raw_source_path": path,
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "role_classification": "active_scorable",
        "dose_class": "therapeutic_mass",
    }


def _unresolved(
    name: str,
    canonical_id: str | None,
    category: str,
    *,
    path: str = "ingredientRows[1]",
    skip_reason: str = "no_quality_map_match",
    role: str = "active_unmapped",
    is_excipient: bool = False,
) -> dict:
    return {
        "name": name,
        "canonical_id": canonical_id,
        "category": category,
        "quantity": 100.0,
        "unit": "mg",
        "has_dose": True,
        "mapped": False,
        "mapped_identity": False,
        "scoreable_identity": False,
        "identity_disposition": "repaired" if canonical_id else "unresolved",
        "source_section": "active",
        "raw_source_path": path,
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "role_classification": role,
        "skip_reason": skip_reason,
        "dose_class": "therapeutic_mass",
        "is_excipient": is_excipient,
    }


def _product(name: str, *, scorable: list[dict], all_rows: list[dict]) -> dict:
    return {
        "dsld_id": "rc1-fixture",
        "product_name": name,
        "fullName": name,
        "ingredient_quality_data": {
            "ingredients_scorable": scorable,
            "ingredients": all_rows,
            "ingredients_skipped": [row for row in all_rows if row not in scorable],
        },
        "probiotic_data": {"is_probiotic_product": False, "total_cfu": 0},
    }


def test_unmapped_dosed_nattokinase_is_classification_evidence_not_score_evidence():
    row = _unresolved("Natto Extract", "nattokinase", "enzyme")
    taxonomy = classify_supplement(_product("Nattokinase", scorable=[], all_rows=[row]))

    # Nattokinase is a systemic fibrinolytic enzyme, not a digestive enzyme.
    # RC1 restores the identity without inventing the clinically wrong cohort.
    assert taxonomy["primary_type"] == "general_supplement"
    assert taxonomy["secondary_type"] == "nattokinase"
    assert taxonomy["quantified_label_active_count"] == 1
    assert taxonomy["scorable_active_count"] == 0
    assert taxonomy["unresolved_quantified_active_count"] == 1
    assert taxonomy["is_single_scorable_active"] is False
    assert taxonomy["classification_input_contract"] == "quantified_label_actives"


def test_unmapped_dosed_botanical_uses_label_taxonomy_for_classification():
    row = _unresolved("Horsetail Whole Herb Extract", "horsetail", "minerals")
    row["raw_taxonomy"] = {"category": "botanical"}

    taxonomy = classify_supplement(_product("Horsetail Extract", scorable=[], all_rows=[row]))

    assert taxonomy["primary_type"] == "herbal_botanical"
    assert taxonomy["category_breakdown"] == {"botanical": 1}


def test_mapped_and_unmapped_rows_for_same_identity_remain_one_scorable_active():
    mapped = _mapped("Magnesium", "magnesium", "mineral")
    unresolved_same = _unresolved(
        "Magnesium Glycinate source row",
        "magnesium",
        "mineral",
        path="ingredientRows[1]",
    )
    taxonomy = classify_supplement(_product(
        "Magnesium Glycinate",
        scorable=[mapped],
        all_rows=[mapped, unresolved_same],
    ))

    assert taxonomy["quantified_label_active_count"] == 1
    assert taxonomy["scorable_active_count"] == 1
    assert taxonomy["unresolved_quantified_active_count"] == 0
    assert taxonomy["is_single_scorable_active"] is True


def test_distinct_unresolved_identity_blocks_single_scorable_fact():
    mapped = _mapped("Magnesium", "magnesium", "mineral")
    horsetail = _unresolved("Horsetail", "horsetail", "botanical")
    taxonomy = classify_supplement(_product(
        "Magnesium with Horsetail",
        scorable=[mapped],
        all_rows=[mapped, horsetail],
    ))

    assert taxonomy["quantified_label_active_count"] == 2
    assert taxonomy["scorable_active_count"] == 1
    assert taxonomy["unresolved_quantified_active_count"] == 1
    assert taxonomy["is_single_scorable_active"] is False


def test_unresolved_row_without_identity_is_distinct_and_blocks_single():
    mapped = _mapped("Magnesium", "magnesium", "mineral")
    unknown = _unresolved("Novel active", None, "unknown")
    taxonomy = classify_supplement(_product(
        "Magnesium Plus",
        scorable=[mapped],
        all_rows=[mapped, unknown],
    ))

    assert taxonomy["quantified_label_active_count"] == 2
    assert taxonomy["unresolved_quantified_active_count"] == 1
    assert taxonomy["is_single_scorable_active"] is False


def test_excipients_recognized_non_scorables_and_structural_rows_stay_excluded():
    rows = [
        {
            **_unresolved("EDTA Disodium", "edta", "other", is_excipient=True),
            "identity_disposition": "identity_conflict",
        },
        _unresolved(
            "Dietary Fiber",
            "fiber",
            "fiber",
            path="ingredientRows[2]",
            skip_reason="excluded_nutrition_fact",
            role="inactive_non_scorable",
        ),
        _unresolved(
            "Carrot Powder",
            "carrot",
            "botanical",
            path="ingredientRows[3]",
            skip_reason="recognized_non_scorable",
            role="recognized_non_scorable",
        ),
        {
            **_unresolved(
                "Proprietary Blend",
                None,
                "blend",
                path="ingredientRows[4]",
                skip_reason="blend_header_total_weight_only",
            ),
            "cleaner_row_role": "blend_header_total",
            "score_eligible_by_cleaner": False,
            "is_blend_header": True,
        },
    ]
    # These are negative boundary fixtures, not valid scoring identities.  A
    # scoreable disposition would correctly let the authoritative scoring
    # contract recover the row before taxonomy sees it.
    for row in rows[1:3]:
        row["identity_disposition"] = "identity_conflict"

    taxonomy = classify_supplement(_product("Inactive Boundary", scorable=[], all_rows=rows))

    assert taxonomy["quantified_label_active_count"] == 0
    assert taxonomy["scorable_active_count"] == 0
    assert taxonomy["unresolved_quantified_active_count"] == 0
    assert taxonomy["primary_type"] == "general_supplement"


def test_scorer_recovered_np_row_does_not_expand_classification_population():
    """The scorer can recover mapped skipped rows for its own assembly.

    That recovery is not RC1's quantified-label population.  Admitting it here
    resurrects decorative probiotic-base false positives across the corpus.
    """
    recovered = _mapped("Decorative Acidophilus", "acidophilus", "probiotic")
    recovered.update({
        "quantity": 0.0,
        "unit": "NP",
        "has_dose": False,
        "dose_class": "probiotic_cfu",
        "role_classification": "recognized_non_scorable",
    })
    product = _product("Whole Food Base", scorable=[], all_rows=[recovered])

    taxonomy = classify_supplement(product)

    assert taxonomy["quantified_label_active_count"] == 0
    assert taxonomy["primary_type"] == "general_supplement"


def test_taxonomy_incoherent_plant_omega_repair_cannot_claim_fish_oil_cohort():
    row = _unresolved("Omega-3 Fatty Acids", "fish_oil", "fatty_acids")
    row.update({
        "canonical_id_before": "omega_3",
        "canonical_id_after": "fish_oil",
        "identity_taxonomy_coherent": False,
        "raw_taxonomy": {"category": "fatty acid", "ingredientGroup": "Omega-3"},
        "parent_blend": "Organic Cranberry and Pumpkin Seed Oil Blend",
    })
    taxonomy = classify_supplement(_product(
        "Vegan D3 Organic Spray",
        scorable=[],
        all_rows=[row],
    ))

    assert taxonomy["quantified_label_active_count"] == 1
    assert taxonomy["unresolved_quantified_active_count"] == 1
    assert taxonomy["primary_type"] != "omega_3"


def test_incoherent_nattokinase_repair_uses_pre_repair_systemic_identity():
    row = _unresolved("Natto Extract", "soybean", "enzymes")
    row.update({
        "canonical_id_before": "nattokinase",
        "canonical_id_after": "soybean",
        "identity_taxonomy_coherent": False,
        "raw_taxonomy": {
            "category": "botanical",
            "ingredientGroup": "Soy",
            "forms": [{"name": "Nattokinase", "category": "enzyme"}],
        },
    })
    taxonomy = classify_supplement(_product("Nattokinase", scorable=[], all_rows=[row]))

    assert taxonomy["secondary_type"] == "nattokinase"
    assert taxonomy["primary_type"] == "general_supplement"
    assert taxonomy["primary_type"] != "fiber_digestive"


def test_incoherent_horsetail_repair_prefers_label_parent_over_silica_form():
    row = _unresolved("Horsetail Whole Herb Extract", "horsetail", "minerals")
    row.update({
        "canonical_id_before": "silica",
        "canonical_id_after": "horsetail",
        "identity_taxonomy_coherent": False,
        "raw_taxonomy": {
            "category": "botanical",
            "ingredientGroup": "Horsetail",
            "forms": [{"name": "Silica", "category": "mineral"}],
        },
    })
    taxonomy = classify_supplement(_product("Horsetail Extract", scorable=[], all_rows=[row]))

    assert taxonomy["primary_type"] == "herbal_botanical"
    assert taxonomy["primary_type"] != "single_mineral"


def test_unresolved_named_probiotic_strain_remains_probiotic_without_cfu():
    row = _unresolved(
        "Saccharomyces boulardii",
        "saccharomyces_boulardii",
        "probiotics",
    )
    row.update({
        "canonical_id_before": "brewers_yeast",
        "canonical_id_after": "saccharomyces_boulardii",
        "identity_taxonomy_coherent": False,
        "raw_taxonomy": {"category": "botanical", "ingredientGroup": "Saccharomyces boulardii"},
    })
    taxonomy = classify_supplement(_product("Sacro-B", scorable=[], all_rows=[row]))

    assert taxonomy["primary_type"] == "probiotic"


def test_epicor_fermentate_is_not_promoted_to_live_probiotic():
    epicor = _mapped("EpiCor dried Yeast Fermentate", "brewers_yeast", "functional_food")
    epicor["source_label_name"] = "Saccharomyces cerevisiae"
    taxonomy = classify_supplement(_product("EpiCor 500 mg", scorable=[epicor], all_rows=[epicor]))

    assert taxonomy["primary_type"] != "probiotic"


def test_single_unresolved_shark_cartilage_keeps_joint_intent():
    row = _unresolved("Shark Cartilage", "collagen", "unknown")
    row.update({
        "canonical_id_before": "chondroitin",
        "canonical_id_after": "collagen",
        "identity_taxonomy_coherent": False,
        "raw_taxonomy": {"category": "animal part or source", "ingredientGroup": "Cartilage"},
    })
    taxonomy = classify_supplement(_product("Shark Cartilage", scorable=[], all_rows=[row]))

    assert taxonomy["primary_type"] == "joint_support"


def test_b5_title_remains_dominant_when_calcium_is_a_second_label_active():
    b5 = _mapped("Pantothenic Acid", "vitamin_b5_pantothenic_acid", "vitamin")
    calcium = _unresolved("Calcium", "calcium", "minerals")
    taxonomy = classify_supplement(_product(
        "Pantothenic Acid B5 500 mg",
        scorable=[b5],
        all_rows=[b5, calcium],
    ))

    assert taxonomy["primary_type"] == "single_vitamin"
    assert taxonomy["is_single_scorable_active"] is False
