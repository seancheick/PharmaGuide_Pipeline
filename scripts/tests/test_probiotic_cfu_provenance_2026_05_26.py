"""Wave 6.Z probiotic CFU provenance regression locks."""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture
def enricher():
    return SupplementEnricherV3()


def _product_level_probiotic_data(total_cfu=20_000_000_000):
    return {
        "is_probiotic_product": True,
        "has_cfu": True,
        "total_cfu": total_cfu,
        "total_strain_count": 3,
        "probiotic_blends": [
            {"name": "Probiotic Blend", "raw_source_path": "activeIngredients[1]"}
        ],
        "cfu_source": "product_identity",
        "cfu_raw_source_path": "fullName",
        "cfu_evidence_scope": "product_level",
        "cfu_linked_rows": ["fullName"],
    }


def _fiber_row():
    return {
        "name": "Dietary Fiber",
        "standardName": "Dietary Fiber",
        "canonical_id": "fiber",
        "quantity": 5,
        "unit": "g",
        "score_eligible_by_cleaner": True,
        "cleaner_row_role": "active_scorable",
    }


def _cfu_evidence(evidence):
    rows = [row for row in evidence if row.get("evidence_type") == "probiotic_cfu"]
    assert rows, "Expected probiotic_cfu evidence row"
    return rows[0]


def test_product_name_cfu_guarantee_populates_product_level_provenance(enricher):
    product = {
        "id": "garden_of_life_name_cfu",
        "product_name": "Dr. Formulated Probiotics Daily Care 25 Billion CFU Guaranteed",
        "fullName": "Garden of Life Dr. Formulated Probiotics Daily Care 25 Billion CFU Guaranteed",
        "bundleName": "",
        "statements": [],
        "activeIngredients": [
            {
                "name": "Daily Probiotic Blend",
                "standardName": "Probiotic Blend",
                "category": "probiotic",
                "quantity": 0,
                "unit": "NP",
                "raw_source_path": "activeIngredients[0]",
                "nestedIngredients": [
                    {"name": "Lactobacillus acidophilus"},
                    {"name": "Bifidobacterium lactis"},
                    {"name": "Lactobacillus plantarum"},
                ],
                "harvestMethod": "",
                "notes": "",
            }
        ],
        "inactiveIngredients": [],
    }

    probiotic_data = enricher._collect_probiotic_data(product)

    assert probiotic_data["is_probiotic_product"] is True
    assert probiotic_data["has_cfu"] is True
    assert probiotic_data["total_cfu"] == pytest.approx(25_000_000_000)
    assert probiotic_data["total_billion_count"] == pytest.approx(25.0)
    assert probiotic_data["cfu_source"] == "product_identity"
    assert probiotic_data["cfu_raw_source_path"] in {"product_name", "fullName"}
    assert probiotic_data["cfu_evidence_scope"] == "product_level"
    assert probiotic_data["cfu_raw_source_path"] in probiotic_data["cfu_linked_rows"]


def test_blend_header_total_does_not_double_count_nested_strain_cfus(enricher):
    """A flattened blend header can carry the aggregate CFU guarantee while
    nested strain rows carry individual CFUs. The header is provenance, not a
    fifth strain, and its total must not stack on top of child CFUs."""
    product = {
        "id": "florasport_like",
        "product_name": "FloraSport 20B",
        "fullName": "Thorne FloraSport 20B",
        "bundleName": "",
        "statements": [],
        "activeIngredients": [
            {
                "name": "Probiotic Blend",
                "standardName": "Probiotic & Microbiome Blends",
                "category": "blend",
                "quantity": 250,
                "unit": "mg",
                "raw_source_path": "ingredientRows[0]",
                "cleaner_row_role": "blend_header_total",
                "hierarchyType": "blend_header",
                "score_exclusion_reason": "blend_header_total",
                "nestedIngredients": [],
                "notes": "20 Billion CFUs, At time of expiration when stored as recommended",
            },
            {
                "name": "Lactobacillus paracasei UALpc-04",
                "standardName": "Lactobacillus Paracasei",
                "category": "bacteria",
                "quantity": 0,
                "unit": "NP",
                "raw_source_path": "ingredientRows[0].nestedRows[0]",
                "parentBlend": "Probiotic Blend",
                "nestedIngredients": [],
                "notes": "5 Billion CFUs",
            },
            {
                "name": "Lactobacillus acidophilus UALa-01",
                "standardName": "Lactobacillus Acidophilus",
                "category": "bacteria",
                "quantity": 0,
                "unit": "NP",
                "raw_source_path": "ingredientRows[0].nestedRows[1]",
                "parentBlend": "Probiotic Blend",
                "nestedIngredients": [],
                "notes": "5 Billion CFUs",
            },
            {
                "name": "Bacillus subtilis DE111",
                "standardName": "Bacillus subtilis DE111",
                "category": "bacteria",
                "quantity": 0,
                "unit": "NP",
                "raw_source_path": "ingredientRows[0].nestedRows[2]",
                "parentBlend": "Probiotic Blend",
                "nestedIngredients": [],
                "notes": "5 Billion CFUs",
            },
            {
                "name": "Bifidobacterium animalis lactis HN019",
                "standardName": "Bifidobacterium Lactis",
                "category": "bacteria",
                "quantity": 0,
                "unit": "NP",
                "raw_source_path": "ingredientRows[0].nestedRows[3]",
                "parentBlend": "Probiotic Blend",
                "nestedIngredients": [],
                "notes": "5 Billion CFUs",
            },
        ],
        "inactiveIngredients": [],
    }

    probiotic_data = enricher._collect_probiotic_data(product)

    assert probiotic_data["is_probiotic_product"] is True
    assert probiotic_data["total_strain_count"] == 4
    assert probiotic_data["total_billion_count"] == pytest.approx(20.0)
    assert probiotic_data["total_cfu"] == pytest.approx(20_000_000_000)
    assert probiotic_data["guarantee_type"] == "at_expiration"
    assert probiotic_data["cfu_raw_source_path"] == "ingredientRows[0]"
    assert probiotic_data["cfu_linked_rows"] == [
        "ingredientRows[0]",
        "ingredientRows[0].nestedRows[0]",
        "ingredientRows[0].nestedRows[1]",
        "ingredientRows[0].nestedRows[2]",
        "ingredientRows[0].nestedRows[3]",
    ]
    assert all(
        "Probiotic Blend" not in (blend.get("strains") or [])
        for blend in probiotic_data["probiotic_blends"]
    )
    assert {
        strain["strain"]: strain["cfu_per_day"]
        for strain in probiotic_data["clinical_strains"]
    }["Bifidobacterium animalis lactis HN019"] == pytest.approx(5_000_000_000)


def test_generic_flattened_header_carries_aggregate_live_cell_guarantee(enricher):
    product = {
        "id": "floramend_like",
        "product_name": "FloraMend Prime Probiotic",
        "statements": [],
        "activeIngredients": [
            {
                "name": "Proprietary Blend",
                "standardName": "General Proprietary Blends",
                "category": "blend",
                "quantity": 0,
                "unit": "NP",
                "raw_source_path": "ingredientRows[0]",
                "cleaner_row_role": "blend_header_total",
                "hierarchyType": "blend_header",
                "score_exclusion_reason": "blend_header_total",
                "nestedIngredients": [],
                "notes": "5 billion live cells at time of expiration",
            },
            {
                "name": "Lactobacillus gasseri KS-13",
                "standardName": "Lactobacillus Gasseri",
                "category": "bacteria",
                "quantity": 0,
                "unit": "NP",
                "raw_source_path": "ingredientRows[0].nestedRows[0]",
                "parentBlend": "Proprietary Blend",
                "nestedIngredients": [],
            },
        ],
        "inactiveIngredients": [],
    }

    probiotic_data = enricher._collect_probiotic_data(product)

    assert probiotic_data["total_strain_count"] == 1
    assert probiotic_data["total_billion_count"] == pytest.approx(5.0)
    assert probiotic_data["guarantee_type"] == "at_expiration"
    assert probiotic_data["cfu_raw_source_path"] == "ingredientRows[0]"


def test_multi_serving_probiotic_uses_canonical_header_without_counting_it_as_strain(enricher):
    """Ages-based label columns are alternatives, never additive strains/CFU."""
    product = {
        "id": "184730_like",
        "product_name": "Probiotic 123",
        "serving_basis": {"canonical_serving_size_quantity": 0.5},
        "statements": [],
        "activeIngredients": [
            {
                "name": "Probiotic Blend",
                "standardName": "Probiotic & Microbiome Blends",
                "category": "blend",
                "raw_source_path": "ingredientRows[0]",
                "cleaner_row_role": "blend_header_total",
                "hierarchyType": "blend_header",
                "score_exclusion_reason": "blend_header_total",
                "raw_taxonomy": {"quantityVariants": [{"serving_size_quantity": 0.25}]},
                "nestedIngredients": [],
                "notes": "Probiotic Blend Note: (providing:) (1.12 billion CFU)",
            },
            {
                "name": "Probiotic Blend",
                "standardName": "Probiotic & Microbiome Blends",
                "category": "blend",
                "raw_source_path": "ingredientRows[1]",
                "cleaner_row_role": "blend_header_total",
                "hierarchyType": "blend_header",
                "score_exclusion_reason": "blend_header_total",
                "raw_taxonomy": {"quantityVariants": [{"serving_size_quantity": 0.5}]},
                "nestedIngredients": [],
                "notes": "Probiotic Blend Note: (providing:) (2.25 billion CFU)",
            },
            {
                "name": "Bifidobacterium bifidum (Bb-06)",
                "standardName": "Bifidobacterium Bifidum",
                "category": "bacteria",
                "raw_source_path": "ingredientRows[1].nestedRows[0]",
                "parentBlend": "Probiotic Blend",
                "nestedIngredients": [],
            },
            {
                "name": "Bifidobacterium lactis (Bl-04)",
                "standardName": "Bifidobacterium Lactis",
                "category": "bacteria",
                "raw_source_path": "ingredientRows[1].nestedRows[1]",
                "parentBlend": "Probiotic Blend",
                "nestedIngredients": [],
            },
            {
                "name": "Lactobacillus acidophilus (La-14)",
                "standardName": "Lactobacillus Acidophilus",
                "category": "bacteria",
                "raw_source_path": "ingredientRows[1].nestedRows[2]",
                "parentBlend": "Probiotic Blend",
                "nestedIngredients": [],
            },
        ],
        "inactiveIngredients": [],
    }

    probiotic_data = enricher._collect_probiotic_data(product)

    assert probiotic_data["total_strain_count"] == 3
    assert probiotic_data["total_billion_count"] == pytest.approx(2.25)
    assert probiotic_data["cfu_linked_rows"] == ["ingredientRows[1]"]
    assert all(
        "Probiotic Blend" not in (blend.get("strains") or [])
        for blend in probiotic_data["probiotic_blends"]
    )


def test_distinct_same_name_blends_without_serving_evidence_remain_additive(enricher):
    product = {
        "id": "two_distinct_blends",
        "product_name": "Two Blend Probiotic",
        "statements": [],
        "activeIngredients": [
            {
                "name": "Probiotic Blend",
                "category": "blend",
                "raw_source_path": "ingredientRows[0]",
                "cleaner_row_role": "blend_header_total",
                "nestedIngredients": [],
                "notes": "1 billion CFU",
            },
            {
                "name": "Lactobacillus acidophilus La-14",
                "category": "bacteria",
                "raw_source_path": "ingredientRows[0].nestedRows[0]",
                "nestedIngredients": [],
            },
            {
                "name": "Probiotic Blend",
                "category": "blend",
                "raw_source_path": "ingredientRows[1]",
                "cleaner_row_role": "blend_header_total",
                "nestedIngredients": [],
                "notes": "2 billion CFU",
            },
            {
                "name": "Bifidobacterium lactis Bl-04",
                "category": "bacteria",
                "raw_source_path": "ingredientRows[1].nestedRows[0]",
                "nestedIngredients": [],
            },
        ],
        "inactiveIngredients": [],
    }

    probiotic_data = enricher._collect_probiotic_data(product)

    assert probiotic_data["total_strain_count"] == 2
    assert probiotic_data["total_billion_count"] == pytest.approx(3.0)
    assert len([
        blend
        for blend in probiotic_data["probiotic_blends"]
        if blend.get("is_blend_header_total")
    ]) == 2


def test_fiber_support_row_does_not_block_probiotic_cfu_product_evidence(enricher):
    enriched = {
        "activeIngredients": [
            _fiber_row(),
            {
                "name": "Probiotic Blend",
                "standardName": "Probiotic Blend",
                "canonical_id": "probiotics",
                "quantity": 100,
                "unit": "mg",
                "score_eligible_by_cleaner": False,
                "cleaner_row_role": "blend_header_total",
            },
        ],
        "probiotic_data": _product_level_probiotic_data(),
        "supplement_taxonomy": {"primary_type": "probiotic"},
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {
                    "name": "Dietary Fiber",
                    "canonical_id": "fiber",
                    "dose_class": "nutrition_fact",
                }
            ]
        },
    }

    evidence = enricher._collect_product_scoring_evidence(enriched)
    cfu = _cfu_evidence(evidence)

    assert cfu["scoreable"] is True
    assert cfu["canonical_id"] == "probiotic_cfu_total"
    assert cfu["clean_identity_id"] is None
    assert cfu["scoring_parent_id"] == "probiotic_cfu_total"
    assert cfu["evidence_canonical_id"] == "probiotic_cfu_total"
    assert cfu["canonical_source_db"] == "probiotic_data"
    assert cfu["evidence_origin"] == "native_enrichment"
    assert cfu["reason"] == "product_level_cfu_with_probiotic_identity"
    assert cfu["confidence"] == "high"


def test_streptococcus_strain_is_probiotic_not_an_accessory_active(enricher):
    enriched = {
        "activeIngredients": [
            {
                "name": "BLIS K12 S. salivarius K12",
                "standardName": "Streptococcus Salivarius",
                "canonical_id": "streptococcus_salivarius",
                "quantity": 20,
                "unit": "mg",
                "score_eligible_by_cleaner": True,
                "cleaner_row_role": "active_scorable",
            }
        ],
        "probiotic_data": _product_level_probiotic_data(
            total_cfu=2_000_000_000
        ),
        "supplement_taxonomy": {"primary_type": "probiotic"},
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {
                    "name": "BLIS K12 S. salivarius K12",
                    "standard_name": "Streptococcus Salivarius",
                    "canonical_id": "streptococcus_salivarius",
                    "dose_class": "therapeutic_mass",
                }
            ]
        },
    }

    cfu = _cfu_evidence(
        enricher._collect_product_scoring_evidence(enriched)
    )

    assert cfu["scoreable"] is True
    assert cfu["reason"] == "product_level_cfu_with_probiotic_identity"
    assert "rejection_reason" not in cfu


def test_probiotic_blend_form_identities_support_owner_cfu_without_dose_inflation(
    enricher,
):
    from supplement_taxonomy import classify_supplement

    enriched = {
        "product_name": "Probiotic Complex 1",
        "activeIngredients": [
            {
                "name": "Probiotic Complex Blend",
                "standardName": "Probiotics",
                "canonical_id": "probiotics",
                "raw_source_path": "ingredientRows[0]",
                "quantity": 1_000_000_000,
                "unit": "Organism(s)",
                "cleaner_row_role": "blend_header_total",
                "score_eligible_by_cleaner": False,
                "score_exclusion_reason": "blend_header_total",
                "dose_class": "blend_total_weight",
                "forms": [
                    {
                        "name": "B. bifidum",
                        "category": "bacteria",
                        "ingredientGroup": "Bifidobacterium bifidum",
                        "percent": 40,
                    },
                    {
                        "name": "L. acidophilus",
                        "category": "bacteria",
                        "ingredientGroup": "Lactobacillus acidophilus",
                        "percent": 40,
                    },
                    {
                        "name": "L. helveticus",
                        "category": "bacteria",
                        "ingredientGroup": "Lactobacillus helveticus",
                        "percent": 10,
                    },
                    {
                        "name": "S. thermophilus",
                        "category": "bacteria",
                        "ingredientGroup": "Streptococcus thermophilus",
                        "percent": 10,
                    },
                ],
            }
        ],
        "inactiveIngredients": [],
        "ingredient_quality_data": {
            "ingredients_scorable": [],
            "ingredients": [],
        },
        "statements": [],
    }

    enriched["probiotic_data"] = enricher._collect_probiotic_data(enriched)
    enriched["supplement_taxonomy"] = classify_supplement(enriched)
    cfu = _cfu_evidence(
        enricher._collect_product_scoring_evidence(enriched)
    )

    assert enriched["probiotic_data"]["total_strain_count"] == 4
    assert enriched["supplement_taxonomy"]["primary_type"] == "probiotic"
    assert cfu["scoreable"] is True
    assert cfu["dose_value"] == 1_000_000_000
    assert cfu["raw_source_path"] == "ingredientRows[0]"
    assert cfu["linked_rows"] == ["ingredientRows[0]"]


def test_product_cfu_evidence_is_rejected_when_taxonomy_is_not_probiotic(enricher):
    """Source-of-truth gate requires scoreable CFU evidence to agree with
    supplement_taxonomy.primary_type. Probiotic row identity is diagnostic
    only until taxonomy routes the product to the probiotic peer class."""
    enriched = {
        "activeIngredients": [
            _fiber_row(),
            {
                "name": "Probiotic Blend",
                "standardName": "Probiotic Blend",
                "canonical_id": "probiotics",
                "quantity": 100,
                "unit": "mg",
                "score_eligible_by_cleaner": False,
                "cleaner_row_role": "blend_header_total",
            },
        ],
        "probiotic_data": _product_level_probiotic_data(),
        "supplement_taxonomy": {"primary_type": "fiber_digestive"},
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {
                    "name": "Dietary Fiber",
                    "canonical_id": "fiber",
                    "dose_class": "nutrition_fact",
                }
            ]
        },
    }

    evidence = enricher._collect_product_scoring_evidence(enriched)
    cfu = _cfu_evidence(evidence)

    assert cfu["scoreable"] is False
    assert cfu["scoreable_identity"] is False
    assert cfu["rejection_reason"] == "product_taxonomy_not_probiotic"


def test_blend_total_cfu_scope_is_normalized_at_scoring_boundary(enricher):
    enriched = {
        "activeIngredients": [],
        "probiotic_data": {
            **_product_level_probiotic_data(total_cfu=1_500_000_000),
            "cfu_raw_source_path": "ingredientRows[0]",
            "cfu_linked_rows": ["ingredientRows[0]"],
            "cfu_evidence_scope": "blend_total",
        },
        "supplement_taxonomy": {"primary_type": "probiotic"},
        "ingredient_quality_data": {"ingredients_scorable": []},
    }

    cfu = _cfu_evidence(enricher._collect_product_scoring_evidence(enriched))

    assert cfu["evidence_scope"] == "blend_level"
    assert cfu["source_evidence_scope"] == "blend_total"


def test_product_cfu_gets_one_typed_non_ul_dose_assessment(enricher):
    enriched = {
        "product_scoring_evidence": [
            {
                "evidence_type": "probiotic_cfu",
                "scoreable": True,
                "dose_class": "probiotic_cfu",
                "dose_value": 1_500_000_000,
                "dose_unit": "CFU",
                "raw_source_path": "ingredientRows[0]",
                "linked_rows": ["ingredientRows[0]"],
                "name": "Total Probiotic CFU",
                "canonical_id": "probiotic_cfu_total",
            }
        ],
        "rda_ul_data": {
            "collection_status": "complete",
            "dose_assessments": [],
        },
    }

    enricher._append_product_evidence_dose_assessments(enriched)

    assessments = enriched["rda_ul_data"]["dose_assessments"]
    assert len(assessments) == 1
    assert assessments[0]["source_path"] == "ingredientRows[0]"
    assert assessments[0]["dose_class"] == "probiotic_cfu"
    assert assessments[0]["ul_assessment_status"] == "no_ul_applicable"
    assert assessments[0]["readiness"] == "not_applicable"


def test_fiber_primary_product_with_accessory_probiotics_rejects_cfu_evidence(enricher):
    enriched = {
        "product_name": "Clear Mixing Super Fiber With Probiotics",
        "fullName": "Clear Mixing Super Fiber With Probiotics",
        "activeIngredients": [
            _fiber_row(),
            {
                "name": "LAB4",
                "standardName": "LAB4",
                "quantity": 1_000_000_000,
                "unit": "Viable Cells",
                "score_eligible_by_cleaner": False,
                "cleaner_row_role": "blend_header_total",
            },
        ],
        "probiotic_data": _product_level_probiotic_data(total_cfu=1_000_000_000),
        "supplement_taxonomy": {"primary_type": "fiber_digestive"},
        "ingredient_quality_data": {
            "ingredients_scorable": [],
            "ingredients_skipped": [
                {
                    "name": "Dietary Fiber",
                    "canonical_id": "fiber",
                    "dose_class": "nutrition_fact",
                }
            ],
        },
    }

    evidence = enricher._collect_product_scoring_evidence(enriched)
    cfu = _cfu_evidence(evidence)

    assert cfu["scoreable"] is False
    assert cfu["rejection_reason"] == "non_probiotic_strict_active_present"


def test_unrelated_strict_active_still_rejects_accessory_probiotic_cfu(enricher):
    enriched = {
        "activeIngredients": [
            {
                "name": "Vitamin C",
                "standardName": "Vitamin C",
                "canonical_id": "vitamin_c",
                "quantity": 500,
                "unit": "mg",
                "score_eligible_by_cleaner": True,
                "cleaner_row_role": "active_scorable",
            }
        ],
        "probiotic_data": _product_level_probiotic_data(total_cfu=5_000_000_000),
        "supplement_taxonomy": {"primary_type": "general_supplement"},
        "ingredient_quality_data": {"ingredients_scorable": []},
    }

    evidence = enricher._collect_product_scoring_evidence(enriched)
    cfu = _cfu_evidence(evidence)

    assert cfu["scoreable"] is False
    assert cfu["rejection_reason"] == "non_probiotic_strict_active_present"


@pytest.mark.parametrize("statement", [
    # Nature's Way Fortify Women's 50 Billion (DSLD 327967) label statement;
    # shipped as "not stated" and cost the dose pillar its 0.85 multiplier.
    "Guarantees 50 billion live probiotic cultures through the date of expiration",
    "50 billion CFU guaranteed until the expiration date",
    "Viable probiotic cultures guaranteed through the best by date",
])
def test_guarantee_through_the_date_of_expiration(enricher, statement):
    assert enricher._extract_guarantee_type(statement) == "at_expiration"


@pytest.mark.parametrize("statement", [
    # CVS 19171 / 19172: real probiotic potency guarantees that name the
    # organism rather than saying "CFU" or "cultures" (lost when the 2026-09-16
    # context guard required those words).
    "which contains over 100 million active Lactobacillus Acidophilus "
    "(including the naturally occurring metabolic product produced by "
    "Lactobacilli) at the time of manufacture.",
    "Contains a minimum of 1 Billion live bacteria when manufactured, and "
    "provides an effective amount through expiration date.",
])
def test_organism_named_potency_guarantee_keeps_its_type(enricher, statement):
    assert enricher._extract_guarantee_type(statement) in {"at_manufacture", "at_expiration"}


@pytest.mark.parametrize("statement", [
    "Store below 25C. Discard after the expiration date.",
    "Do not use after the expiration date printed on the bottle.",
    "Keep refrigerated until the expiration date.",
    "Keep refrigerated until expiration.",
    "Vitamin potency guaranteed through the expiration date.",
    "Guaranteed potency through the best by date.",
    "Quality guaranteed through the best by date.",
])
def test_expiration_storage_advice_is_not_a_potency_guarantee(enricher, statement):
    assert enricher._extract_guarantee_type(statement) is None


def test_statement_guarantee_survives_when_rows_already_carry_the_total(enricher):
    """The label's rows own the CFU count and a statement owns the guarantee.
    The guarantee used to be read only when the statement also supplied the
    count, so an equal row total silently discarded it."""
    product = {
        "id": "row_total_statement_guarantee",
        "product_name": "Daily Probiotic",
        "fullName": "Daily Probiotic",
        "bundleName": "",
        "statements": [
            {"type": "Formula re: Contains",
             "notes": "Guarantees 10 billion live cultures through the date of expiration"},
        ],
        "activeIngredients": [
            {
                "name": "Lactobacillus rhamnosus GG",
                "standardName": "Lactobacillus rhamnosus GG",
                "category": "probiotic",
                "quantity": 10,
                "unit": "billion CFU",
                "raw_source_path": "ingredientRows[0]",
                "harvestMethod": "",
                "notes": "",
            }
        ],
        "inactiveIngredients": [],
    }

    probiotic_data = enricher._collect_probiotic_data(product)

    assert probiotic_data["total_billion_count"] == pytest.approx(10.0)
    assert probiotic_data["guarantee_type"] == "at_expiration"


# ── guarantee locality (Codex audit 2026-09-16) ──────────────────────────────
# The probiotic context and the guarantee timing must come from the same
# statement and sentence. Joining statements let an organism named in one
# statement vouch for an unrelated "potency guaranteed" claim in another.

@pytest.mark.parametrize("text", [
    "Contains Lactobacillus acidophilus. Vitamin potency guaranteed through expiration.",
    "Contains 10 billion CFU. Vitamin potency guaranteed through expiration.",
    "Contains 10 billion CFU; Vitamin potency guaranteed through expiration.",
    "Lactobacillus acidophilus 1 billion CFU\r\nVitamin C potency guaranteed through expiration",
])
def test_guarantee_needs_probiotic_context_in_the_same_sentence(enricher, text):
    assert enricher._extract_guarantee_type(text) is None


@pytest.mark.parametrize("text, expected", [
    ("L. rhamnosus GG 10 billion CFU guaranteed through expiration.", "at_expiration"),
    ("Guarantees 50 billion live probiotic cultures through the date of expiration\r\n"
     "Formulated with 10 diverse probiotic strains", "at_expiration"),
    ("Contains Lactobacillus acidophilus. 5 billion CFU at time of manufacture.", "at_manufacture"),
])
def test_local_guarantee_is_still_read(enricher, text, expected):
    assert enricher._extract_guarantee_type(text) == expected


@pytest.mark.parametrize("text, expected", [
    # Emergen-C 206889: one guarantee covers the culture count and vitamin C.
    ("Each packet is guaranteed to deliver 2 billion live active cultures and a boost of "
     "250 mg of Vitamin C through the expiration date.", "at_expiration"),
    ("Guaranteed 10 billion CFU through expiration, with digestive enzymes.", "at_expiration"),
])
def test_count_guarantee_that_also_names_another_nutrient_is_read(enricher, text, expected):
    assert enricher._extract_guarantee_type(text) == expected


@pytest.mark.parametrize("text", [
    "10 billion CFU, vitamin potency guaranteed through expiration",
    "Contains 5 billion CFU and Vitamin C potency guaranteed through the expiration date",
    "Probiotics plus minerals: mineral content guaranteed through expiration",
])
def test_guarantee_whose_subject_is_another_nutrient_abstains(enricher, text):
    assert enricher._extract_guarantee_type(text) is None


def test_statements_do_not_vouch_for_each_other(enricher):
    product = {
        "id": "cross_statement",
        "product_name": "Daily Probiotic",
        "fullName": "Daily Probiotic",
        "bundleName": "",
        "statements": [
            {"type": "Formula re: Contains", "notes": "Contains Lactobacillus acidophilus"},
            {"type": "General Statements", "notes": "Vitamin potency guaranteed through expiration"},
        ],
        "activeIngredients": [{
            "name": "Lactobacillus acidophilus", "standardName": "Lactobacillus acidophilus",
            "category": "probiotic", "quantity": 1, "unit": "billion CFU",
            "raw_source_path": "ingredientRows[0]", "harvestMethod": "", "notes": "",
        }],
        "inactiveIngredients": [],
    }
    assert enricher._collect_probiotic_data(product)["guarantee_type"] is None


def test_probiotic_row_text_is_its_own_context(enricher):
    """Garden of Life 173757: the row's harvestMethod reads "Guaranteed per
    serving, at time of manufacture." — the row itself is the probiotic."""
    product = {
        "id": "row_guarantee",
        "product_name": "Prostate+",
        "fullName": "Prostate+",
        "bundleName": "",
        "statements": [],
        "activeIngredients": [{
            "name": "Lactobacillus bulgaricus", "standardName": "Lactobacillus bulgaricus",
            "category": "probiotic", "quantity": 0, "unit": "NP",
            "raw_source_path": "ingredientRows[0]",
            "harvestMethod": "Guaranteed per serving, at time of manufacture.", "notes": "",
        }],
        "inactiveIngredients": [],
    }
    assert enricher._collect_probiotic_data(product)["guarantee_type"] == "at_manufacture"


def _probiotic_statement_product(note, extra_actives=()):
    strain = {"name": "Lactobacillus rhamnosus GG", "standardName": "Lactobacillus rhamnosus GG",
              "category": "probiotic", "quantity": 10, "unit": "billion CFU",
              "raw_source_path": "ingredientRows[0]", "harvestMethod": "", "notes": "",
              "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable"}
    return {
        "id": "unqualified_potency", "product_name": "Daily Probiotic", "fullName": "Daily Probiotic",
        "bundleName": "", "statements": [{"type": "General Statements", "notes": note}],
        "activeIngredients": [strain, *extra_actives], "inactiveIngredients": [],
    }


def test_unqualified_potency_guarantee_counts_on_a_probiotic_only_product(enricher):
    """GNC "Probiotic Complex 50 Billion CFUs", MegaFlora, Primadophilus print
    "Guaranteed potency through expiration date" with no nutrient named: on a
    product whose only actives are probiotics that potency is probiotic."""
    product = _probiotic_statement_product("Guaranteed potency through expiration date")
    assert enricher._collect_probiotic_data(product)["guarantee_type"] == "at_expiration"


def test_unqualified_potency_guarantee_abstains_on_a_combination_product(enricher):
    vitamin_c = {"name": "Vitamin C", "standardName": "Vitamin C", "canonical_id": "vitamin_c",
                 "category": "vitamin", "quantity": 60, "unit": "mg",
                 "raw_source_path": "ingredientRows[1]", "score_eligible_by_cleaner": True,
                 "cleaner_row_role": "active_scorable"}
    product = _probiotic_statement_product("Guaranteed potency through expiration date", [vitamin_c])
    assert enricher._collect_probiotic_data(product)["guarantee_type"] is None


def test_a_named_non_probiotic_potency_never_counts(enricher):
    product = _probiotic_statement_product("Vitamin potency guaranteed through expiration")
    assert enricher._collect_probiotic_data(product)["guarantee_type"] is None


def test_raw_12091_manufacture_count_does_not_inherit_effective_expiry_level(enricher):
    import json
    from pathlib import Path
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = json.loads((Path(__file__).parent / 'fixtures' / 'probiotic_cfu_guarantee_12091_raw.json').read_text())
    enriched = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))[0]
    assert enriched['probiotic_data']['total_cfu'] == 5e9
    assert enriched['probiotic_data']['guarantee_type'] == 'at_manufacture'
    artifact = build_scored_artifact(enriched)
    assert artifact['_v4_module_breakdown']['dimensions']['dose']['metadata']['cfu_guarantee']['type'] == 'at_manufacture'


@pytest.mark.parametrize('text,expected', [
    ('Contains 5 billion live cells when manufactured and an effective level at time of expiration.', 'at_manufacture'),
    ('Contains 1 billion live bacteria when manufactured. Provides an effective amount through expiration date.', 'at_manufacture'),
    ('Contains 10 billion CFU at manufacture and provides 5 billion CFU through expiration.', 'at_manufacture'),
    ('Contains 5 billion CFU at manufacture and provides 5 billion CFU through expiration.', 'at_expiration'),
    ('Contains 5 billion CFU at manufacture and at time of expiration.', 'at_expiration'),
    ('Contains 10 billion CFU at manufacture and guarantees 5 billion CFU through expiration.', 'at_manufacture'),
    ('Contains 10 billion CFU at manufacture, provides 5 billion CFU through expiration.', 'at_manufacture'),
    ('Contains 5 billion live cells when manufactured and effective levels through expiration.', 'at_manufacture'),
    ('Contains 5 billion live cells when manufactured, with an effective level through expiration.', 'at_manufacture'),
])
def test_guarantee_stays_bound_to_selected_count(enricher, text, expected):
    assert enricher._extract_cfu(text, ingredient={'name': 'Probiotic Blend'})['guarantee_type'] == expected


def _count_guarantee_product(rows, statements=()):
    return {
        'id': 'cfu_count_warranty_binding', 'product_name': 'Daily Probiotic',
        'fullName': 'Daily Probiotic', 'bundleName': '', 'inactiveIngredients': [],
        'activeIngredients': [
            {'name': name, 'standardName': name, 'category': 'probiotic',
             'quantity': count, 'unit': 'billion CFU',
             'raw_source_path': f'ingredientRows[{i}]', 'notes': notes}
            for i, (name, count, notes) in enumerate(rows)
        ],
        'statements': [{'type': 'Formula re: Contains', 'notes': s} for s in statements],
    }


def test_larger_product_count_replaces_the_smaller_rows_warranty(enricher):
    product = _count_guarantee_product(
        [('Lactobacillus rhamnosus GG', 1, '1 billion CFU guaranteed through expiration')],
        ['10 billion live cultures at manufacture'],
    )
    data = enricher._collect_probiotic_data(product)
    assert data['total_cfu'] == 10e9
    assert data['guarantee_type'] == 'at_manufacture'


def test_smaller_statement_count_cannot_warranty_a_larger_total(enricher):
    product = _count_guarantee_product(
        [('Lactobacillus rhamnosus GG', 10, '')],
        ['5 billion live cultures guaranteed through expiration'],
    )
    data = enricher._collect_probiotic_data(product)
    assert data['total_cfu'] == 10e9
    assert data['guarantee_type'] is None


@pytest.mark.parametrize('second_notes,expected', [
    ('', None),
    ('5 billion CFU at manufacture', 'at_manufacture'),
    ('5 billion CFU guaranteed through expiration', 'at_expiration'),
])
def test_aggregate_warranty_covers_every_counted_row(enricher, second_notes, expected):
    product = _count_guarantee_product([
        ('Lactobacillus rhamnosus GG', 5, '5 billion CFU guaranteed through expiration'),
        ('Bifidobacterium longum BB536', 5, second_notes),
    ])
    data = enricher._collect_probiotic_data(product)
    assert data['total_cfu'] == 10e9
    assert data['guarantee_type'] == expected


def test_independent_statements_cannot_recombine_count_and_warranty(enricher):
    product = _count_guarantee_product([('Lactobacillus rhamnosus GG', 0, '')], [
        '10 billion live cultures at manufacture',
        '5 billion live cultures guaranteed through expiration',
    ])
    data = enricher._collect_probiotic_data(product)
    assert data['total_cfu'] == 10e9
    assert data['guarantee_type'] == 'at_manufacture'


@pytest.mark.parametrize('notes,count', [
    ('Total Lacto cultures (35 billion CFU) Total Bifido cultures (15 billion CFU) Total Probiotic Cultures 50 billion CFU at expiration date.', 50),
    ('Total Lacto cultures (30 billion CFU) Total Bifido cultures (60 billion CFU) Total Probiotic Cultures 90 billion CFU at expiration date.', 90),
])
def test_explicit_header_total_warranty_uses_matching_count(enricher, notes, count):
    assert enricher._extract_guarantee_type(notes, subject_is_probiotic=True, target_cfu_count=count * 1e9) == 'at_expiration'


def test_statement_warranty_is_bound_after_final_count_selection(enricher):
    product = _count_guarantee_product([
        ('Lactobacillus rhamnosus GG', 1, ''),
        ('Bifidobacterium longum BB536', 1, ''),
    ], [
        '1 billion each of two probiotic strains',
        'Each packet is guaranteed to deliver 2 billion live active cultures and a boost of 250 mg of Vitamin C through the expiration date.',
    ])
    product['servingSizes'] = [{'quantity': 1, 'unit': 'packet'}]
    product['serving_basis'] = {'canonical_serving_size_quantity': 1}
    data = enricher._collect_probiotic_data(product)
    assert data['total_cfu'] == 2e9
    assert data['guarantee_type'] == 'at_expiration'


def test_product_count_replacement_keeps_matching_explicit_header_warranty(enricher):
    product = _count_guarantee_product([
        ('Probiotic Blend', 50, 'Total Lacto cultures (35 billion CFU) Total Bifido cultures (15 billion CFU) Total Probiotic Cultures 50 billion CFU at expiration date.'),
    ])
    data = enricher._collect_probiotic_data(product)
    assert data['total_cfu'] == 50e9
    assert data['guarantee_type'] == 'at_expiration'


def test_literal_header_count_keeps_its_manufacture_warranty(enricher):
    data = enricher._collect_probiotic_data(_count_guarantee_product([
        ('Probiotic Blend', 0, '(2,000,000,000 CFUs) (at time of manufacture)'),
    ], ['2 billion live cultures']))
    assert data['total_cfu'] == 2e9
    assert data['guarantee_type'] == 'at_manufacture'


def test_daily_statement_keeps_equivalent_capsule_count_warranty(enricher):
    product = _count_guarantee_product([
        ('Lactobacillus reuteri NCIMB 30242', 2.5, '2.5 billion live cultures guaranteed through expiration'),
    ], ['5 billion live probiotic cultures per day'])
    product['servingSizes'] = [{'quantity': 1, 'unit': 'capsules', 'minDailyServings': 2, 'maxDailyServings': 2}]
    data = enricher._collect_probiotic_data(product)
    # total_cfu is the per-serving panel count (the app shows "total per
    # serving"); the per-day statement restates it, it does not replace it.
    assert data['total_cfu'] == 2.5e9
    assert data['guarantee_type'] == 'at_expiration'


def test_explicit_probiotic_cell_unit_owns_qualitative_header_warranty(enricher):
    product = _count_guarantee_product([
        ('Probiotic Blend', 1e9, 'at time of manufacture'),
    ], ['1 billion cells'])
    product['activeIngredients'][0]['unit'] = 'Cell(s)'
    data = enricher._collect_probiotic_data(product)
    assert data['total_cfu'] == 1e9
    assert data['guarantee_type'] == 'at_manufacture'


@pytest.mark.parametrize('statement,low,high', [
    ('5 billion live probiotic cultures', 2, 2),
    ('5 billion live probiotic cultures per day', 1, 1),
])
def test_unproven_daily_equivalence_does_not_warrant_larger_count(enricher, statement, low, high):
    product = _count_guarantee_product([
        ('Lactobacillus reuteri NCIMB 30242', 2.5, '2.5 billion live cultures guaranteed through expiration'),
    ], [statement])
    product['servingSizes'] = [{'quantity': 1, 'unit': 'capsules', 'minDailyServings': low, 'maxDailyServings': high}]
    assert enricher._collect_probiotic_data(product)['guarantee_type'] is None


@pytest.mark.parametrize('text,count,expected', [
    ('Contains 10 billion CFU at manufacture (5 billion CFU guaranteed through expiration)', 10, 'at_manufacture'),
    ('(10 billion CFU at manufacture)(5 billion CFU at expiration)', 10, 'at_manufacture'),
    ('Total Lacto Cultures (30 billion CFU) Total Bifido Cultures (60 billion CFU) Total Probiotic Cultures 90 billion CFU at expiration date.', 30, None),
    ('(providing 2.5 billion live cultures) (CFUs guaranteed through printed expiration date.)', 2.5, 'at_expiration'),
])
def test_parenthetical_and_total_claims_keep_their_own_warranty(enricher, text, count, expected):
    assert enricher._extract_guarantee_type(text, subject_is_probiotic=True, target_cfu_count=count * 1e9) == expected


@pytest.mark.parametrize('text', [
    'Contains 10 billion CFU at manufacture (guaranteed effective levels through expiration).',
    'Contains 10 billion CFU at manufacture / 5 billion CFU guaranteed through expiration.',
])
def test_renewed_parenthetical_or_slash_claim_cannot_warrant_selected_amount(enricher, text):
    assert enricher._extract_guarantee_type(text, True, 10e9) == 'at_manufacture'


def test_best_by_date_alone_does_not_warrant_probiotic_only_product(enricher):
    product = _count_guarantee_product([
        ('Lactobacillus rhamnosus GG', 1.5, ''),
    ], ['Lot No.: Y20574\nBest By Date: 09/14'])
    assert enricher._collect_probiotic_data(product)['guarantee_type'] is None



def test_raw_literal_cfu_count_preserves_label_ownership_and_safety(enricher):
    import json
    from pathlib import Path
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = json.loads((Path(__file__).parent / 'fixtures' / 'probiotic_literal_cfu_232059_raw.json').read_text())
    enriched = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))[0]
    data = enriched['probiotic_data']
    assert data['total_cfu'] == 2e9
    assert data['guarantee_type'] == 'at_manufacture'
    assert data['cfu_raw_source_path'] == 'ingredientRows[0]'
    artifact = build_scored_artifact(enriched)
    assert artifact['product_safety_status'] == 'no_known_catalog_concern'


@pytest.mark.parametrize('statement', ['CFU count at time of manufacture.', 'Colony Forming Units at time of manufacture.'])
def test_explicit_unquantified_cfu_subject_keeps_its_timing(enricher, statement):
    product = _count_guarantee_product([('Lactobacillus rhamnosus GG', 1, '')], [statement])
    assert enricher._collect_probiotic_data(product)['guarantee_type'] == 'at_manufacture'



def test_raw_total_cultures_is_metadata_not_nutrition_or_a_strain(enricher):
    import json
    from pathlib import Path
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from scoring_input_contract import get_evidence_subject_rows
    raw = json.loads((Path(__file__).parent / 'fixtures' / 'probiotic_cfu_total_297668_raw.json').read_text())
    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    total = next(row for row in enricher._flatten_active_ingredients_for_analysis(cleaned['activeIngredients'])
                 if row.get('raw_source_path') == 'ingredientRows[1].nestedRows[16]')
    assert total['cleaner_row_role'] == 'blend_header_total'
    assert total['score_eligible_by_cleaner'] is False
    assert '30 Billion CFU' in total['notes']
    enriched = enricher.enrich_product(cleaned)[0]
    data = enriched['probiotic_data']
    assert data['total_cfu'] == 30e9
    assert data['guarantee_type'] == 'at_expiration'
    assert 'ingredientRows[1]' in data['strain_allocation_owner_refs']
    assert not any('Total Probiotic Cultures' in b.get('strains', []) for b in data['probiotic_blends'])
    assert not any(row.get('name') == 'Total Probiotic Cultures' for row in get_evidence_subject_rows(enriched))


def test_nested_cfu_total_has_one_aggregate_owner(enricher):
    product = _count_guarantee_product([
        ('Probiotic Blend', 0, ''), ('Total Probiotic Cultures', 10, '10 billion CFU through expiration'),
        ('Lactobacillus rhamnosus GG', 4, '4 billion CFU through expiration'),
    ])
    parent, total, strain = product['activeIngredients']
    parent.update(cleaner_row_role='blend_header_total', score_eligible_by_cleaner=False)
    total.update(raw_source_path='ingredientRows[0].nestedRows[1]', cleaner_row_role='blend_header_total', score_eligible_by_cleaner=False, dose_role='declared_total')
    strain['raw_source_path'] = 'ingredientRows[0].nestedRows[0]'
    data = enricher._collect_probiotic_data(product)
    assert data['total_cfu'] == 10e9
    assert data['guarantee_type'] == 'at_expiration'


@pytest.mark.parametrize('nested_count,expected_count,expected_timing', [
    (50, 70, 'at_expiration'),
    (40, 70, None),
    (60, 80, 'at_expiration'),
])
def test_nested_total_warranty_matches_its_counted_subtree(enricher, nested_count, expected_count, expected_timing):
    product = _count_guarantee_product([
        ('Probiotic Blend', 50, ''),
        ('Total Probiotic Cultures', nested_count, 'through expiration'),
        ('Lactobacillus rhamnosus GG', 20, '20 billion CFU through expiration'),
    ])
    parent, total, _ = product['activeIngredients']
    parent.update(cleaner_row_role='blend_header_total', score_eligible_by_cleaner=False)
    total.update(raw_source_path='ingredientRows[0].nestedRows[0]',
                 cleaner_row_role='blend_header_total', score_eligible_by_cleaner=False,
                 dose_role='declared_total')
    data = enricher._collect_probiotic_data(product)
    assert data['total_cfu'] == expected_count * 1e9
    assert data['guarantee_type'] == expected_timing


def test_three_level_headers_count_members_once(enricher):
    product = _count_guarantee_product([
        ('Probiotic Blend', 0, ''), ('Probiotic Blend', 6, '6 billion CFU through expiration'),
        ('Lactobacillus rhamnosus GG', 3, '3 billion CFU through expiration'),
        ('Bifidobacterium longum BB536', 3, '3 billion CFU through expiration'),
        ('Lactobacillus reuteri NCIMB 30242', 4, '4 billion CFU through expiration'),
    ])
    outer, inner, first, second, sibling = product['activeIngredients']
    for header in (outer, inner):
        header.update(cleaner_row_role='blend_header_total', score_eligible_by_cleaner=False)
    inner['raw_source_path'] = 'ingredientRows[0].nestedRows[0]'
    first['raw_source_path'] = 'ingredientRows[0].nestedRows[0].nestedRows[0]'
    second['raw_source_path'] = 'ingredientRows[0].nestedRows[0].nestedRows[1]'
    sibling['raw_source_path'] = 'ingredientRows[0].nestedRows[1]'
    data = enricher._collect_probiotic_data(product)
    assert data['total_cfu'] == 10e9
    assert data['guarantee_type'] == 'at_expiration'


@pytest.mark.parametrize('total_count,declared_total,expected_owner', [
    (0, True, True), (10, True, True), (0, False, False),
])
def test_terminal_total_metadata_does_not_make_strain_allocation_incomplete(enricher, total_count, declared_total, expected_owner):
    product = _count_guarantee_product([
        ('Probiotic Blend', 0, ''), ('Total Probiotic Cultures', total_count, ''),
        ('Lactobacillus rhamnosus GG', 0, ''),
    ])
    parent, total, strain = product['activeIngredients']
    for row in (parent, total):
        row.update(cleaner_row_role='blend_header_total', score_eligible_by_cleaner=False)
    total['raw_source_path'] = 'ingredientRows[0].nestedRows[1]'
    strain['raw_source_path'] = 'ingredientRows[0].nestedRows[0]'
    if declared_total:
        total['dose_role'] = 'declared_total'
    data = enricher._collect_probiotic_data(product)
    assert ('ingredientRows[0]' in data['strain_allocation_owner_refs']) is expected_owner


def _serving_basis_product(row_count, row_notes, statement, serving, variants=None):
    product = _count_guarantee_product(
        [('Lactobacillus rhamnosus GG', row_count, row_notes)], [statement])
    product['servingSizes'] = [serving]
    if variants is not None:
        product['activeIngredients'][0]['quantityVariants'] = variants
    return product


_ONE_CAPSULE_UP_TO_THREE = {'minQuantity': 1, 'maxQuantity': 1, 'unit': 'Capsule(s)',
                            'minDailyServings': 1, 'maxDailyServings': 3}


def test_statement_count_for_more_units_does_not_replace_per_serving_rows(enricher):
    # Raw 242637: 5 billion per 1-capsule panel serving; "15 billion CFU in a
    # 3 capsule serving" is the same potency stated for three capsules.
    data = enricher._collect_probiotic_data(_serving_basis_product(
        5, '(5 Billion CFU) (CFU count at time of manufacture)',
        'made to provide 15 billion CFU in a 3 capsule serving with 13 species',
        _ONE_CAPSULE_UP_TO_THREE,
        [{'serving_size_quantity': 1, 'serving_size_unit': 'Capsule(s)'}]))
    assert data['total_cfu'] == 5e9
    assert data['guarantee_type'] == 'at_manufacture'


@pytest.mark.parametrize('statement,low,high', [
    ('5 billion live probiotic cultures per day', 1, 2),
    ('5 billion live probiotic cultures per day', 1, 3),
    # Raw 321379/322603: "15 Billion CFU Daily" over 1-3 servings a day.
    ('5 Billion CFU Daily\r\nCFU count at time of manufacture', 1, 3),
])
def test_unresolvable_daily_basis_never_replaces_per_serving_rows(enricher, statement, low, high):
    data = enricher._collect_probiotic_data(_serving_basis_product(
        2.5, '2.5 billion live cultures guaranteed through expiration', statement,
        {'quantity': 1, 'unit': 'capsules', 'minDailyServings': low, 'maxDailyServings': high}))
    assert data['total_cfu'] == 2.5e9
    assert data['guarantee_type'] == 'at_expiration'


def test_per_unit_statement_is_rebased_onto_the_panel_serving(enricher):
    # 3 billion per capsule on a 2-capsule serving is 6 billion per serving.
    data = enricher._collect_probiotic_data(_serving_basis_product(
        4, '', '3 billion active cultures per capsule',
        {'minQuantity': 2, 'maxQuantity': 2, 'unit': 'Capsule(s)',
         'minDailyServings': 1, 'maxDailyServings': 1},
        [{'serving_size_quantity': 2, 'serving_size_unit': 'Capsule(s)'}]))
    assert data['total_cfu'] == 6e9


def test_statement_for_the_selected_audience_column_still_owns_the_count(enricher):
    # Raw 267658: the analysed column is 2 gummies; "2 billion CFU's in 2
    # gummies" is that column's count and exceeds the shared 1 billion note.
    product = _serving_basis_product(
        1, '1 Billion CFUs', "2 billion CFU's in 2 gummies at time of expiration",
        {'minQuantity': 2, 'maxQuantity': 2, 'unit': 'Gummy(ies)',
         'minDailyServings': 1, 'maxDailyServings': 1},
        [{'serving_size_quantity': 1, 'serving_size_unit': 'Gummy(ies)'},
         {'serving_size_quantity': 2, 'serving_size_unit': 'Gummy(ies)',
          'selected_for_analysis': True}])
    product['serving_basis'] = {'canonical_serving_size_quantity': 2.0}
    data = enricher._collect_probiotic_data(product)
    assert data['total_cfu'] == 2e9
    assert data['guarantee_type'] == 'at_expiration'


@pytest.mark.parametrize('statement', [
    '15 billion live cultures per serving',
    '15 billion live cultures',
])
def test_same_basis_statement_keeps_replacing_a_smaller_row_sum(enricher, statement):
    data = enricher._collect_probiotic_data(_serving_basis_product(
        5, '', statement,
        {'minQuantity': 2, 'maxQuantity': 2, 'unit': 'Capsule(s)',
         'minDailyServings': 1, 'maxDailyServings': 1}))
    assert data['total_cfu'] == 15e9


def test_raw_242637_total_is_the_panel_serving_count(enricher):
    import json
    from pathlib import Path
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = json.loads((Path(__file__).parent / 'fixtures' / 'probiotic_cfu_serving_basis_242637_raw.json').read_text())
    enriched = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))[0]
    assert enriched['probiotic_data']['total_cfu'] == 5e9
    assert enriched['probiotic_data']['guarantee_type'] == 'at_manufacture'
    artifact = build_scored_artifact(enriched)
    assert artifact['_v4_module_breakdown']['dimensions']['dose']['metadata']['cfu_guarantee']['type'] == 'at_manufacture'


def test_daily_statement_warranty_binds_to_the_restated_row_count(enricher):
    data = enricher._collect_probiotic_data(_serving_basis_product(
        2.5, '', '5 billion live cultures per day guaranteed through expiration',
        {'quantity': 1, 'unit': 'capsules', 'minDailyServings': 2, 'maxDailyServings': 2}))
    assert data['total_cfu'] == 2.5e9
    assert data['guarantee_type'] == 'at_expiration'


@pytest.mark.parametrize('statement', [
    '15 billion CFU in a 3 capsule serving. Take 1 capsule per day.',
    '15 billion CFU per serving and 2 billion CFU per capsule',
])
def test_basis_is_read_only_from_the_counts_own_clause(enricher, statement):
    data = enricher._collect_probiotic_data(_serving_basis_product(
        5, '', statement,
        {'minQuantity': 3, 'maxQuantity': 3, 'unit': 'Capsule(s)',
         'minDailyServings': 1, 'maxDailyServings': 1},
        [{'serving_size_quantity': 3, 'serving_size_unit': 'Capsule(s)'}]))
    assert data['total_cfu'] == 15e9


def test_daily_adjective_is_not_a_basis(enricher):
    data = enricher._collect_probiotic_data(_serving_basis_product(
        5, '', '15 billion live cultures for daily digestive support',
        {'minQuantity': 1, 'maxQuantity': 1, 'unit': 'Capsule(s)',
         'minDailyServings': 1, 'maxDailyServings': 3},
        [{'serving_size_quantity': 1, 'serving_size_unit': 'Capsule(s)'}]))
    assert data['total_cfu'] == 15e9


def test_basis_opening_the_next_label_line_belongs_to_the_count(enricher):
    # Raw 74379: 2.5 billion per capsule, 2 capsules a day.
    data = enricher._collect_probiotic_data(_serving_basis_product(
        2.5, '(providing 2.5 billion live cultures) (CFUs guaranteed through printed expiration date.)',
        '5 billion live probiotic cultures\nPer day\n#1 cardiologist preferred probiotic strain',
        {'quantity': 1, 'unit': 'capsules', 'minDailyServings': 2, 'maxDailyServings': 2}))
    assert data['total_cfu'] == 2.5e9
    assert data['guarantee_type'] == 'at_expiration'


def test_directions_on_the_next_line_are_not_the_counts_basis(enricher):
    data = enricher._collect_probiotic_data(_serving_basis_product(
        5, '', '15 billion live cultures\nTake 1 capsule per day',
        {'quantity': 1, 'unit': 'capsules', 'minDailyServings': 2, 'maxDailyServings': 2}))
    assert data['total_cfu'] == 15e9


def test_zero_unit_basis_cannot_replace_rows(enricher):
    data = enricher._collect_probiotic_data(_serving_basis_product(
        5, '', '15 billion CFU per 0 capsules',
        {'minQuantity': 1, 'maxQuantity': 1, 'unit': 'Capsule(s)',
         'minDailyServings': 1, 'maxDailyServings': 1},
        [{'serving_size_quantity': 1, 'serving_size_unit': 'Capsule(s)'}]))
    assert data['total_cfu'] == 5e9



@pytest.mark.parametrize('statement', [
    'Provides 50 billion CFU in capsules',
    '50 billion CFU in capsule form',
    'Delivers 50 billion CFU in a capsule designed to survive stomach acid',
])
def test_dosage_form_wording_is_not_a_per_unit_basis(enricher, statement):
    data = enricher._collect_probiotic_data(_serving_basis_product(
        30, '', statement,
        {'minQuantity': 2, 'maxQuantity': 2, 'unit': 'Capsule(s)',
         'minDailyServings': 1, 'maxDailyServings': 1},
        [{'serving_size_quantity': 2, 'serving_size_unit': 'Capsule(s)'}]))
    assert data['total_cfu'] == 50e9


def test_daily_adjective_at_the_window_edge_is_not_a_basis(enricher):
    # The old 90-character cutoff ended the search right after "daily".
    head, tail = '15 billion live cultures ', ' a daily'
    statement = head + 'x' * (90 - len(head) - len(tail)) + tail + ' digestive routine'
    data = enricher._collect_probiotic_data(_serving_basis_product(
        5, '', statement,
        {'minQuantity': 1, 'maxQuantity': 1, 'unit': 'Capsule(s)',
         'minDailyServings': 1, 'maxDailyServings': 3},
        [{'serving_size_quantity': 1, 'serving_size_unit': 'Capsule(s)'}]))
    assert data['total_cfu'] == 15e9


def test_defaulted_daily_frequency_cannot_restate_a_per_day_count(enricher):
    data = enricher._collect_probiotic_data(_serving_basis_product(
        5, '', '15 billion CFU per day',
        {'minQuantity': 1, 'maxQuantity': 1, 'unit': 'Capsule(s)'},
        [{'serving_size_quantity': 1, 'serving_size_unit': 'Capsule(s)'}]))
    assert data['total_cfu'] == 5e9


@pytest.mark.parametrize('statement,expected', [
    ('Per 3 capsules: 15 billion CFU', 5e9),
    ('Each 3-capsule serving provides 15 billion CFU', 5e9),
    ('Per day: 15 billion CFU', 7.5e9),
])
def test_statement_prefix_basis_reaches_production_artifact(enricher, statement, expected):
    from scoring_v4.scored_artifact import build_scored_artifact
    product = _serving_basis_product(5, '', statement, {
        'minQuantity': 1, 'maxQuantity': 1, 'unit': 'Capsule(s)',
        'minDailyServings': 2, 'maxDailyServings': 2})
    enriched = enricher.enrich_product(product)[0]
    assert enriched['probiotic_data']['total_cfu'] == expected
    artifact = build_scored_artifact(enriched)
    disclosure = artifact['_v4_module_breakdown']['dimensions']['transparency']['metadata']['aggregate_cfu_disclosure']
    assert disclosure['total_billion_count'] == expected / 1e9


def test_unresolved_daily_statement_without_panel_cfu_has_no_per_serving_total(enricher):
    from scoring_v4.scored_artifact import build_scored_artifact
    product = _serving_basis_product(0, '', '15 billion CFU per day', _ONE_CAPSULE_UP_TO_THREE)
    enriched = enricher.enrich_product(product)[0]
    assert enriched['probiotic_data']['has_cfu'] is False
    assert enriched['probiotic_data']['total_cfu'] == 0
    artifact = build_scored_artifact(enriched)
    assert artifact['quality_score_status'] == 'not_scored'
    assert artifact['quality_score_v4_100'] is None


@pytest.mark.parametrize('statement,expected', [
    ('5 billion CFU per day guaranteed through expiration', None),
    ('15 billion CFU per 3 capsules at manufacture. 15 billion CFU per capsule guaranteed through expiration.', 'at_manufacture'),
])
def test_statement_guarantee_requires_the_same_per_serving_count(enricher, statement, expected):
    product = _serving_basis_product(5, '', statement, {
        'minQuantity': 1, 'maxQuantity': 1, 'unit': 'Capsule(s)',
        'minDailyServings': 2, 'maxDailyServings': 2})
    enriched = enricher.enrich_product(product)[0]
    assert enriched['probiotic_data']['guarantee_type'] == expected
