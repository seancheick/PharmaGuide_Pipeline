"""A DSLD ``blend`` row with one constituent of the same identity is that ingredient.

Doctor's Best Saw Palmetto (269286, same label 269589) prints "Prosterol
320 mg". DSLD files the row as ``category=blend, ingredientGroup=Proprietary
Blend`` with one form, Saw Palmetto Berry Extract. "Prosterol" is a curated
saw palmetto alias, so the row and its only constituent name one ingredient.
The cleaner still made it a ``blend_header_total``. Enrichment then carried
BLEND_GENERAL, and every pillar read a blend that is not on the label: 31/100,
Evidence no_assessable_actives (golden set v4 finding F2).

A blend row stays a blend total when its constituent is a different identity,
a descriptor (``organic``, ``extract``), or a proprietary-blend owner such as
Velositol (amylopectin + chromium).
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


def _run(pipeline, label):
    from scoring_v4.scored_artifact import build_scored_artifact

    normalizer, enricher = pipeline
    cleaned = normalizer.normalize_product(json.loads((FIXTURES / label).read_text()))
    enriched, _ = enricher.enrich_product(cleaned)
    return cleaned, enriched, build_scored_artifact(enriched)


def test_prosterol_is_saw_palmetto_not_a_blend(pipeline):
    cleaned, enriched, scored = _run(pipeline, "saw_palmetto_prosterol_269286_raw.json")
    [row] = cleaned["activeIngredients"]
    assert (row["canonical_id"], row["quantity"], row["unit"]) == ("saw_palmetto", 320.0, "mg")
    assert row["cleaner_row_role"] != "blend_header_total"
    assert row["score_eligible_by_cleaner"] is True
    assert row["hierarchyType"] != "blend_header"
    iqd = [r.get("canonical_id") for r in enriched["ingredient_quality_data"]["ingredients"]]
    assert iqd == ["saw_palmetto"]
    evidence = scored["quality_pillars_v4"]["evidence"]
    assert evidence.get("evidence_result_state") != "no_assessable_actives"
    dose_text = json.dumps(scored["quality_pillars_v4"]["dose"])
    assert "blend total is disclosed" not in dose_text


def test_velositol_single_form_stays_a_blend_total(pipeline):
    """GNC 317632: Velositol's one form resolves to the same BLEND_VELOSITOL
    proprietary-blend owner; it is still amylopectin + chromium, not one IQM
    ingredient."""
    cleaned, _, _ = _run(pipeline, "velositol_317632_raw.json")
    velositol = [r for r in cleaned["activeIngredients"] if r.get("canonical_id") == "BLEND_VELOSITOL"]
    assert velositol and all(r["cleaner_row_role"] == "blend_header_total" for r in velositol)


@pytest.mark.parametrize("row", [
    # Constituent is a descriptor, not an identity (43975).
    {"name": "Organic Detoxifier Blend", "forms": [{"name": "organic", "category": "other"}]},
    # Constituent names a different identity than the row (31062).
    {"name": "Ultra Probiotics", "forms": [{"name": "Bacillus coagulans", "category": "bacteria"}]},
    # Two botanicals in the name, one generic form (2502).
    {"name": "Whole grape extract (Vitis vinifera) and Polygonum cuspidatum (root) extract",
     "forms": [{"name": "extract", "category": "other"}]},
])
def test_other_single_form_blend_rows_stay_blend_totals(pipeline, row):
    normalizer, _ = pipeline
    ing = {
        **row, "category": "blend", "ingredientGroup": "Proprietary Blend", "uniiCode": "1",
        "nestedRows": [], "quantity": [{"quantity": 500, "unit": "mg", "operator": "="}],
    }
    assert normalizer._is_dsld_active_blend_total_row(ing) is True


@pytest.mark.parametrize("role,kept", [("active_scorable", False), ("blend_header_total", True)])
def test_blend_group_is_identity_evidence_only_on_a_header(role, kept):
    from identity_integrity import extract_label_evidence

    row = {"name": "Prosterol", "ingredientGroup": "Proprietary Blend", "cleaner_row_role": role,
           "raw_taxonomy": {"ingredientGroup": "Proprietary Blend"}}
    groups = [e.field for e in extract_label_evidence(row) if e.kind == "structured_identity"]
    assert groups == (["ingredientGroup", "raw_taxonomy.ingredientGroup"] if kept else [])
    plain = {"name": "Saw Palmetto", "ingredientGroup": "Saw Palmetto", "cleaner_row_role": role}
    assert [e.value for e in extract_label_evidence(plain) if e.kind == "structured_identity"] == ["Saw Palmetto"]


def test_neumentix_named_single_extract_keeps_its_printed_dose(pipeline):
    normalizer, enricher = pipeline
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = {"id": 232839, "fullName": "Focus Tea Spearmint", "ingredientRows": [{
        "name": "Neumentix Phenolic Complex K110-42", "category": "blend",
        "ingredientGroup": "Proprietary Blend (Herb/Botanical)",
        "quantity": [{"quantity": 900, "unit": "mg"}], "nestedRows": [],
        "forms": [{"name": "Spearmint extract", "category": "botanical", "ingredientGroup": "Spearmint"}]}]}
    clean = normalizer.normalize_product(raw)
    [row] = clean["activeIngredients"]
    assert row["canonical_id"] == "spearmint"
    assert (row["quantity"], row["unit"]) == (900, "mg")
    assert row["cleaner_row_role"] != "blend_header_total"
    enriched, _ = enricher.enrich_product(clean)
    evidence = build_scored_artifact(enriched)["quality_pillars_v4"]["evidence"]
    assert evidence["evidence_result_state"] != "no_assessable_actives"
