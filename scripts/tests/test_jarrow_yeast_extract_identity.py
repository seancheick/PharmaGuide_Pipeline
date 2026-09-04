"""Keep Jarrow's source extract distinct from whole yeast and glucan mass."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

import pytest

from scoring_input_contract import get_scoring_ingredients

if TYPE_CHECKING:
    from enrich_supplements_v3 import SupplementEnricherV3


EXTRACT_ID = "NHA_SACCHAROMYCES_CEREVISIAE_EXTRACT"


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    """Use the production registry and enrichment boundary without mocks."""
    from enrich_supplements_v3 import SupplementEnricherV3

    return SupplementEnricherV3()


def _jarrow_product(dsld_id: str) -> dict:
    """Retain the relevant real cleaned rows from Jarrow 264610 / 307558."""
    newer_label = dsld_id == "307558"
    name = "Saccharomyces cerevisiae " + ("Extract" if newer_label else "extract")
    forms = (
        [{"name": "extract", "source": "name_extraction"}]
        if newer_label else [{
            "name": "long, branched Beta 1,3/Beta 1,6 Glucans",
            "ingredientId": 36283,
            "order": 1,
            "prefix": "providing at least",
            "percent": 75,
            "category": "fiber",
            "ingredientGroup": "Beta Glucans",
            "uniiCode": None,
        }]
    )
    parent = {
        "name": name,
        "raw_source_text": name,
        "raw_source_path": "ingredientRows[0]",
        "standardName": "Brewer's Yeast",
        "canonical_id": "brewers_yeast",
        "canonical_source_db": "ingredient_quality_map",
        "ingredientGroup": (
            "Saccharomyces cerevisae" if newer_label else "Saccharomyces boulardii "
        ),
        "uniiCode": "978D8U419H" if newer_label else None,
        "quantity": 250.0,
        "unit": "mg",
        "dose_class": "therapeutic_mass",
        "source_section": "active",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "score_exclusion_reason": None,
        "forms": forms,
        "nestedIngredients": [],
        "isNestedIngredient": False,
        "parentBlend": None,
    }
    parent["raw_taxonomy"] = {
        "category": "botanical" if newer_label else "other",
        "ingredientGroup": parent["ingredientGroup"],
        "uniiCode": parent["uniiCode"],
        "forms": deepcopy(forms),
        "parentBlend": None,
        "isNestedIngredient": False,
        "nested_depth": 0,
    }
    active_rows = [parent]
    if newer_label:
        active_rows.append({
            "name": "Beta-1,3-1,6-Glucan",
            "raw_source_text": "Beta-1,3-1,6-Glucan",
            "raw_source_path": "ingredientRows[0].nestedRows[0]",
            "standardName": "Beta-Glucan",
            "canonical_id": "beta_glucan",
            "canonical_source_db": "ingredient_quality_map",
            "ingredientGroup": "Beta-Glucans",
            "uniiCode": "44FQ49X6UN",
            "quantity": 188.0,
            "unit": "mg",
            "dose_class": "therapeutic_mass",
            "source_section": "active",
            "cleaner_row_role": "active_scorable",
            "score_eligible_by_cleaner": True,
            "score_exclusion_reason": None,
            "forms": [],
            "nestedIngredients": [],
            "isNestedIngredient": True,
            "parentBlend": name,
            "parentBlendMass": 250,
            "parentBlendUnit": "mg",
            "notes": "75% long branched Beta-1,3-1,6-Glucan",
            "raw_taxonomy": {
                "category": "fiber",
                "ingredientGroup": "Beta-Glucans",
                "uniiCode": "44FQ49X6UN",
                "forms": [],
                "parentBlend": name,
                "isNestedIngredient": True,
                "nested_depth": 1,
            },
        })
    return {
        "id": dsld_id,
        "fullName": "Beta Glucan 250 mg" if newer_label else "Beta Glucan",
        "brandName": "Jarrow Formulas",
        "activeIngredients": active_rows,
        "inactiveIngredients": [],
        "servingSizes": [{
            "order": 1,
            "minQuantity": 1.0,
            "maxQuantity": 1.0,
            "unit": "Capsule(s)",
            "minDailyServings": 1,
            "maxDailyServings": 1,
            "normalizedServing": 1.0,
            "servingQuantitySource": "label",
            "dailyServingsSource": "label",
        }],
    }


@pytest.mark.parametrize("dsld_id", ["264610", "307558"])
def test_jarrow_extract_has_non_scorable_preparation_identity(
    enricher: SupplementEnricherV3, dsld_id: str,
) -> None:
    """An exact source preparation resolves identity, not an IQM quality score."""
    product, issues = enricher.enrich_product(_jarrow_product(dsld_id))
    assert product.get("enrichment_status") != "validation_failed", issues
    iqd = product["ingredient_quality_data"]
    parent = next(
        row for row in iqd["ingredients"]
        if row["raw_source_path"] == "ingredientRows[0]"
    )

    assert parent["canonical_id"] == EXTRACT_ID
    assert parent["canonical_source_db"] == "other_ingredients"
    assert parent["recognized_non_scorable"] is True
    assert parent["scoreable_identity"] is False
    assert parent["bio_score"] is None
    assert parent["form_id"] is None
    assert parent in iqd["ingredients_recognized_non_scorable"]
    assert parent not in iqd["ingredients_scorable"]
    assert all(
        row.get("canonical_id") != "brewers_yeast"
        for row in iqd["ingredients"]
    )
    scoring = get_scoring_ingredients(product, strict=True)
    assert scoring.mapped_coverage == 1.0
    assert scoring.unmapped_count == 0
    assert len(scoring.rows) == (2 if dsld_id == "307558" else 1)
    source_projection = next(
        row for row in scoring.rows
        if row["raw_source_path"] == "ingredientRows[0]"
    )
    assert source_projection["canonical_id"] == EXTRACT_ID.lower()
    assert source_projection["scoring_input_kind"] == "label_active_projection"
    assert source_projection["quantity"] == 250.0
    assert source_projection["unit"] == "mg"
    assert source_projection["generic_form_quality_credit"] is False


@pytest.mark.parametrize("dsld_id", ["264610", "307558"])
def test_jarrow_extract_preserves_source_dose_and_constituent_lineage(
    enricher: SupplementEnricherV3, dsld_id: str,
) -> None:
    """The extract amount never becomes a 250 mg beta-glucan amount."""
    source = _jarrow_product(dsld_id)
    product, issues = enricher.enrich_product(deepcopy(source))
    assert product.get("enrichment_status") != "validation_failed", issues
    for original, enriched in zip(
        source["activeIngredients"], product["activeIngredients"], strict=True,
    ):
        for field in (
            "name", "raw_source_text", "raw_source_path", "quantity", "unit",
            "forms", "raw_taxonomy", "isNestedIngredient", "parentBlend",
        ):
            assert enriched[field] == original[field]

    iqd = product["ingredient_quality_data"]["ingredients"]
    parent = next(row for row in iqd if row["raw_source_path"] == "ingredientRows[0]")
    assert parent["quantity"] == 250.0
    assert parent["unit"] == "mg"
    assert parent["source_label_name"] == source["activeIngredients"][0]["name"]
    assert parent["label_display_name"] == source["activeIngredients"][0]["name"]
    assert parent["source_label_form"] == (
        "extract" if dsld_id == "307558" else
        "providing at least long, branched Beta 1,3/Beta 1,6 Glucans"
    )
    assert parent["delivers_markers"] == []
    glucan_rows = [row for row in iqd if row.get("canonical_id") == "beta_glucan"]
    if dsld_id == "264610":
        assert len(source["activeIngredients"]) == len(iqd) == 1
        assert glucan_rows == []
        assert parent["raw_taxonomy"]["forms"][0]["percent"] == 75
    else:
        assert len(glucan_rows) == 1
        child = glucan_rows[0]
        assert child["quantity"] == 188.0
        assert child["unit"] == "mg"
        assert child["raw_source_path"] == "ingredientRows[0].nestedRows[0]"
        assert child["is_nested_ingredient"] is True
        assert child["parent_blend"] == parent["source_label_name"]
        assert child["parent_blend_mass_mg"] == 250.0


def test_exact_extract_record_has_no_borrowed_external_or_quality_identity(
    enricher: SupplementEnricherV3,
) -> None:
    """Label evidence supports a preparation record, not external-ID borrowing."""
    database = enricher.databases["other_ingredients"]
    entry = next(row for row in database["other_ingredients"] if row["id"] == EXTRACT_ID)
    assert entry["standard_name"] == "Saccharomyces cerevisiae Extract"
    assert entry["aliases"] == ["Saccharomyces cerevisiae extract"]
    assert entry["external_ids"] == {}
    assert entry["category"] == "active_pending_relocation"
    assert entry["is_active_only"] is True
    assert entry["is_additive"] is False
    assert not {"bio_score", "score", "forms", "clinical_studies"}.intersection(entry)
    assert database["_metadata"]["total_entries"] == len(database["other_ingredients"])


@pytest.mark.parametrize("dsld_id", ["264610", "307558"])
def test_jarrow_extract_does_not_inherit_live_yeast_evidence(
    enricher: SupplementEnricherV3, dsld_id: str,
) -> None:
    """Extract identity alone supplies neither CFU nor organism clinical studies."""
    product, issues = enricher.enrich_product(_jarrow_product(dsld_id))
    assert product.get("enrichment_status") != "validation_failed", issues
    assert product["probiotic_data"] == {"is_probiotic_product": False}
    assert product["evidence_data"]["clinical_matches"] == []
    assert product["evidence_data"]["match_count"] == 0
    assert product["primary_type"] != "probiotic"


def test_bare_yeast_extract_stays_unresolved(
    enricher: SupplementEnricherV3,
) -> None:
    """The new exact record cannot settle an ambiguous generic extract label."""
    source = _jarrow_product("264610")
    source["activeIngredients"][0].update({
        "name": "yeast extract", "raw_source_text": "yeast extract",
    })
    product, issues = enricher.enrich_product(source)
    assert product.get("enrichment_status") != "validation_failed", issues
    row = product["ingredient_quality_data"]["ingredients"][0]
    assert row["canonical_id"] is None
    assert row["identity_disposition"] == "identity_conflict"
    assert row["scoreable_identity"] is False
    assert not row.get("recognized_non_scorable")
    assert product["probiotic_data"] == {"is_probiotic_product": False}
    scoring = get_scoring_ingredients(product, strict=True)
    assert scoring.rows == []
    assert scoring.unmapped_count == 1
    assert scoring.mapped_coverage < 1.0


def test_live_s_boulardii_keeps_its_source_owned_cfu(
    enricher: SupplementEnricherV3,
) -> None:
    """An unrelated exact extract record cannot demote a live probiotic row."""
    live = {
        "name": "Saccharomyces boulardii",
        "raw_source_text": "Saccharomyces boulardii",
        "ingredientGroup": "Saccharomyces boulardii",
        "canonical_id": "saccharomyces_boulardii",
        "category": "probiotic",
        "raw_source_path": "ingredientRows[0]",
        "quantity": 5_000_000_000,
        "unit": "CFU",
        "forms": [],
    }
    result = enricher._collect_probiotic_data({
        "activeIngredients": [live], "inactiveIngredients": [],
    })
    assert result["is_probiotic_product"] is True
    assert result["total_strain_count"] == 1
    assert result["total_cfu"] == 5_000_000_000
