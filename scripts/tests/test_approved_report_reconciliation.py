"""Approved source conclusions and exact material identities must survive consumers."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from clinical_applicability import assess_clinical_source_review
from clinical_evidence_schema import validate_ingredient_context
from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3
from probiotic_measurements import context_accepted_for_scoring
from scoring_input_contract import get_scoring_ingredients
from scoring_v4.scored_artifact import build_scored_artifact


@pytest.fixture(scope="module")
def records():
    data = json.loads((Path(__file__).parents[1] / "data/backed_clinical_studies.json").read_text())
    return {r["id"]: r for r in data["backed_clinical_studies"]}


def test_cs4_method_regimen_and_null_comparison_are_completed_without_credit(records):
    record = records["PRECLIN_CORDYCEPS"]
    contexts = [c for c in record["study_contexts"] if c["source_pmids"] == ["20804368"]]
    assert len(contexts) == 1
    context = contexts[0]
    assert context["dose"]["values"] == [2997]
    assert context["dose"]["duration_days"] == 84
    assert validate_ingredient_context(context, require_complete_review=True) == []
    assert context["review_status"] == "clinician_approved"
    assert not context_accepted_for_scoring(context)
    assert any(o["direction"] == "null" and o["outcome_role"] == "direct_between_group_effect"
               for o in context["outcomes"])
    assert all(o["outcome_role"] == "within_group_change"
               for o in context["outcomes"] if o["direction"] == "positive")
    assert not assess_clinical_source_review(record)["is_complete"]


@pytest.mark.parametrize("owner,pmid", [
    ("PRECLIN_CORDYCEPS", "27408987"), ("INGR_ECHINACEA", "24554461"),
])
def test_approved_nontransfer_review_does_not_enable_general_ingredient_credit(records, owner, pmid):
    context = next(c for c in records[owner]["study_contexts"] if c["source_pmids"] == [pmid])
    assert context["review_status"] == "clinician_approved"
    assert context["clinical_review"]["reviewed_at"] == "2026-10-28"
    assert validate_ingredient_context(context, require_complete_review=True) == []
    assert not context_accepted_for_scoring(context)
    assert records[owner]["study_type"] != "reference"


def test_collagen_original_comparator_retrieval_does_not_clear_pooling_hold(records):
    record = records["INGR_COLLAGEN_PEPTIDES"]
    context = next(c for c in record["study_contexts"] if c["context_id"] == "collagen_knee_meta_37717022")
    assert any("20401752" in note and "glucosamine" in note for note in context["limitations"])
    assert record["scoring_eligible"] is False
    assert context["scoring_eligible"] is False
    assert context["clinical_review"]["reviewed_at"] == "2026-10-26"


@pytest.fixture(scope="module")
def materials():
    raws = json.loads((Path(__file__).parent / "fixtures/approved_report_material_rows.json").read_text())
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    result = {}
    for pid, raw in raws.items():
        clean = normalizer.normalize_product(deepcopy(raw))
        product, issues = enricher.enrich_product(deepcopy(clean))
        assert product.get("enrichment_status") != "validation_failed", issues
        result[pid] = (clean, product)
    return result


@pytest.mark.parametrize("pid,ref,canonical,amount", [
    ("329993", "ingredientRows[0]", "lions_mane", 1000),
    ("330511", "ingredientRows[0]", "reishi", 1000),
    ("245957", "ingredientRows[0].nestedRows[0]", "acerola_cherry", 938),
])
def test_registered_material_survives_non_scorable_recognition(materials, pid, ref, canonical, amount):
    _, product = materials[pid]
    rows = get_scoring_ingredients(product).rows
    matching = [r for r in rows if r.get("raw_source_path") == ref]
    assert matching and {r["canonical_id"] for r in matching} == {canonical}
    assert {r["quantity"] for r in matching} == {amount}
    artifact = build_scored_artifact(product)
    assert artifact["quality_score_status"] != "suppressed_safety"


def test_botanical_lions_mane_is_the_mushroom_not_the_jellyfish():
    data = json.loads((Path(__file__).parents[1] / "data/botanical_ingredients.json").read_text())
    entry = next(e for e in data["botanical_ingredients"] if e["id"] == "lion_s_mane")
    assert entry["cui"] == "C6049163"  # C1001731 is Cyanea capillata


def test_reviewed_literature_record_follows_exact_equivalence():
    from evidence_resolver import _load_literature_evidence, literature_record_for

    assert "lions_mane" not in _load_literature_evidence()
    assert literature_record_for("lions_mane")["canonical_id"] == "lion_s_mane"
    # A record of its own wins; NHA_BLADDERWRACK's approved neutral is scoped
    # to that record and no equivalence carries it to the botanical entry.
    assert literature_record_for("bladderwrack")["canonical_id"] == "bladderwrack"
    assert literature_record_for("lion_s_mane")["canonical_id"] == "lion_s_mane"
    assert literature_record_for("no_such_canonical") == {}


@pytest.mark.parametrize("pid", ["329997", "329993"])
def test_lions_mane_keeps_its_approved_neutral_dose(materials, pid):
    _, product = materials[pid]
    assert {r["canonical_id"] for r in get_scoring_ingredients(product).rows} == {"lions_mane"}
    artifact = build_scored_artifact(product)
    assert artifact["quality_score_status"] == "scored"
    assert artifact["quality_pillars_v4"]["dose"]["score"] > 0


def test_unreviewed_umbrella_recognition_keeps_its_scoped_dose_proof(materials):
    # Whole-thallus bladderwrack keeps NHA_BLADDERWRACK, whose approved neutral
    # Dose is scoped to that record; no equivalence joins it to the botanical.
    _, product = materials["337206"]
    rows = product["ingredient_quality_data"]["ingredients_recognized_non_scorable"]
    assert {r["canonical_id"] for r in rows if r["name"] == "Bladderwrack"} == {"NHA_BLADDERWRACK"}
    assert build_scored_artifact(product)["quality_pillars_v4"]["dose"]["score"] > 0
