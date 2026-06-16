"""Product-aware active-form duplicate tagging for inactive label rows.

Some DSLD products list a nutrient's chemical form in ``inactiveIngredients``
even though the active panel already carries the parent nutrient. Example:
Vitamin B6 as an active, with Pyridoxine HCl echoed in the inactive list.

The resolver alone cannot decide this safely because many terms are dual-use:
Leucine, magnesium oxide, potassium chloride, rosemary extract, and calcium
salts may be real inactives in products where their parent active is absent.
The build layer has the product's active list, so the duplicate decision lives
there.
"""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from build_final_db import build_detail_blob
from inactive_ingredient_resolver import InactiveIngredientResolver


POLICY = "active_form_duplicate"


def _scored_minimal():
    return {
        "score_80": 50.0,
        "display": "50/80",
        "display_100": "62/100",
        "score_100_equivalent": 62.0,
        "grade": "Fair",
        "verdict": "SAFE",
        "safety_verdict": "SAFE",
        "mapped_coverage": 1.0,
        "badges": [],
        "flags": [],
        "section_scores": {},
        "score_breakdown": {},
        "summary": {},
        "supp_type": "multivitamin",
        "unmapped_actives": [],
    }


def _enriched(active, inactive, *, product_name="Active Form Duplicate Test"):
    active_rows = []
    iqd_rows = []
    for row in active:
        name = row["name"]
        canonical_id = row["canonical_id"]
        parent_key = row.get("parent_key", canonical_id)
        active_rows.append({
            "name": name,
            "standardName": row.get("standardName", name),
            "normalized_key": row.get("normalized_key", parent_key),
            "raw_source_text": name,
            "forms": row.get("forms", []),
            "quantity": row.get("quantity", 1),
            "unit": row.get("unit", "mg"),
            "canonical_id": canonical_id,
            "mapped": True,
        })
        iqd_rows.append({
            "raw_source_text": name,
            "name": name,
            "standard_name": row.get("standardName", name),
            "parent_key": parent_key,
            "canonical_id": canonical_id,
            "form": row.get("matched_form", ""),
            "category": row.get("category", "vitamins"),
            "bio_score": 10,
            "natural": True,
            "score": 10.0,
            "mapped": True,
            "notes": "",
            "matched_form": row.get("matched_form", ""),
            "matched_forms": [],
            "extracted_forms": [],
            "safety_hits": [],
        })

    return {
        "dsld_id": "B2-CANARY",
        "product_name": product_name,
        "brandName": "Regression",
        "upcSku": "0",
        "imageUrl": "",
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": "multivitamin"},
        "enrichment_version": "3.1.0",
        "is_certified_organic": False,
        "is_trusted_manufacturer": True,
        "manufacturing_region": "USA",
        "named_cert_programs": [],
        "has_full_disclosure": True,
        "compliance_data": {},
        "probiotic_data": {"is_probiotic_product": False},
        "contaminant_data": {"banned_substances": {"substances": []}},
        "harmful_additives": [],
        "allergen_hits": [],
        "interaction_profile": {"ingredient_alerts": []},
        "dietary_sensitivity_data": {"warnings": []},
        "activeIngredients": active_rows,
        "ingredient_quality_data": {"ingredients": iqd_rows},
        "dosage_normalization": {"normalized_ingredients": []},
        "inactiveIngredients": [
            {
                "name": name,
                "raw_source_text": name,
                "standardName": standard_name or name,
                "forms": [],
            }
            for name, standard_name in inactive
        ],
        "certification_data": {},
        "proprietary_data": {"has_proprietary_blends": False, "blends": []},
        "serving_basis": {
            "basis_count": 1,
            "basis_unit": "capsule",
            "min_servings_per_day": 1,
            "max_servings_per_day": 1,
        },
        "manufacturer_data": {"violations": {}},
        "evidence_data": {"match_count": 0, "clinical_matches": [], "unsubstantiated_claims": []},
        "rda_ul_data": {
            "collection_enabled": True,
            "ingredients_with_rda": 0,
            "analyzed_ingredients": 0,
            "count": 0,
            "adequacy_results": [],
            "conversion_evidence": [],
            "safety_flags": [],
            "has_over_ul": False,
        },
        "raw_inactives_count": len(inactive),
        "raw_actives_count": len(active),
    }


def _inactive(blob, name):
    for row in blob["inactive_ingredients"]:
        if row["name"] == name:
            return row
    raise AssertionError(f"inactive {name!r} not found")


@pytest.fixture(scope="module")
def resolver():
    return InactiveIngredientResolver()


@pytest.mark.parametrize(
    "name",
    [
        "Pyridoxine Hydrochloride",
        "Cyanocobalamin",
        "Thiamine Mononitrate",
        "Leucine",
        "Potassium Chloride",
        "Rosemary Leaf Extract",
    ],
)
def test_resolver_does_not_product_blind_tag_active_forms(resolver, name):
    r = resolver.resolve(raw_name=name)
    assert r.inactive_policy != POLICY
    assert r.matched_source != "active_nutrient_form"


def test_builder_tags_duplicate_form_when_parent_active_is_present():
    enriched = _enriched(
        active=[
            {
                "name": "Vitamin B6",
                "standardName": "Vitamin B6 (Pyridoxine)",
                "canonical_id": "vitamin_b6_pyridoxine",
                "parent_key": "vitamin_b6",
            }
        ],
        inactive=[("Pyridoxine Hydrochloride", "Vitamin B6 (Pyridoxine)")],
    )

    row = _inactive(build_detail_blob(enriched, _scored_minimal()), "Pyridoxine Hydrochloride")

    assert row["inactive_policy"] == POLICY
    assert row["matched_source"] == "active_nutrient_form"
    assert row["matched_rule_id"] == "vitamin_b6_pyridoxine"
    assert row["is_active_only"] is True
    assert row["label_row_disposition"] == "active_only"
    assert row["functional_roles"] == []


def test_builder_honors_iqm_parent_relationships_for_generic_actives():
    enriched = _enriched(
        active=[
            {
                "name": "Vitamin K",
                "standardName": "Vitamin K",
                "canonical_id": "vitamin_k",
                "parent_key": "vitamin_k",
            }
        ],
        inactive=[("Phytonadione", "Vitamin K1")],
    )

    row = _inactive(build_detail_blob(enriched, _scored_minimal()), "Phytonadione")

    assert row["inactive_policy"] == POLICY
    assert row["matched_rule_id"] == "vitamin_k1"


@pytest.mark.parametrize(
    "active,inactive_name,inactive_standard",
    [
        (
            [{"name": "Zinc", "standardName": "Zinc", "canonical_id": "zinc", "parent_key": "zinc"}],
            "Leucine",
            "L-Leucine",
        ),
        (
            [{"name": "EPA", "standardName": "EPA", "canonical_id": "epa", "parent_key": "epa"}],
            "Potassium Chloride",
            "Potassium",
        ),
        (
            [{"name": "Ubiquinol", "standardName": "Ubiquinol", "canonical_id": "coq10", "parent_key": "coq10"}],
            "Rosemary Leaf Extract",
            "Rosemary",
        ),
    ],
)
def test_builder_does_not_tag_dual_use_form_when_parent_active_absent(
    active,
    inactive_name,
    inactive_standard,
):
    enriched = _enriched(active=active, inactive=[(inactive_name, inactive_standard)])

    row = _inactive(build_detail_blob(enriched, _scored_minimal()), inactive_name)

    assert row["inactive_policy"] != POLICY
    assert row["matched_source"] != "active_nutrient_form"
    assert row["is_active_only"] is False


@pytest.mark.parametrize(
    "raw_name,expected_rule,expected_roles",
    [
        ("Dicalcium Phosphate", "PII_DICALCIUM_PHOSPHATE", ["filler", "binder"]),
        ("Calcium Carbonate", "PII_CALCIUM_CARBONATE", ["filler", "colorant_natural"]),
        ("Rosemary Leaf Extract", "NHA_NATURAL_PRESERVATIVES", ["preservative"]),
        (
            "Natural & Artificial Flavors",
            "NHA_NATURAL_AND_ARTIFICIAL_FLAVORS",
            ["flavor_natural", "flavor_artificial"],
        ),
    ],
)
def test_known_dual_use_or_blend_inactives_resolve_to_excipient_roles(
    resolver,
    raw_name,
    expected_rule,
    expected_roles,
):
    r = resolver.resolve(raw_name=raw_name)
    assert r.matched_source == "other_ingredients"
    assert r.matched_rule_id == expected_rule
    assert r.functional_roles == expected_roles
    assert r.inactive_policy != POLICY
