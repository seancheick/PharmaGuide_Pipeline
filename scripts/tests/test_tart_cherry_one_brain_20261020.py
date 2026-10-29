"""Tart cherry has one identity whatever the label spelling.

botanical_ingredients `tart_cherry_fruit` and IQM `tart_cherry` are the same
substance (GSRS 1L29G6428X SOUR CHERRY, parent PRUNUS CERASUS WHOLE), but 33
CherryPure rows resolved to the botanical record and were scored as a
different identity. A reviewed exact_equivalent row now makes the botanical
record defer to IQM. IQM tart_cherry carries the verified UNII; the botanical
record's RXCUI 1012134 ("sour cherry allergenic extract", an allergen
immunotherapy concept) is removed as a wrong mapping; the literature record is
keyed to the IQM identity; and the CherryPure spellings read the IQM form their
words name ("... Proanthocyanidin extract" -> tart cherry extract; "... powder"
-> tart cherry (unspecified)).
"""
import json
import logging
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "data"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    logging.disable(logging.INFO)
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


@pytest.mark.parametrize("pid, name, form", [
    ("47815", "CherryPure Tart Cherry (Prunus cerasus) Proanthocyanidin extract", "tart cherry extract"),
    ("74531", "CherryPure Sour Cherry (Tart Cherry) Proanthocyanidin extract", "tart cherry extract"),
    ("58997", "CherryPure Tart Cherry (Prunus cerasus) extract", "tart cherry extract"),
    ("182627", "CherryPure Sour Cherry (Tart Cherry) Proanthocyanidin powder", "tart cherry (unspecified)"),
    ("212516", "CherryPURE Whole Montmorency Tart Cherry Fruit Powder", "tart cherry (unspecified)"),
])
def test_a_cherrypure_row_is_iqm_tart_cherry(pipeline, pid, name, form):
    normalizer, enricher = pipeline
    raw = json.loads((FIXTURES / f"tart_cherry_one_brain_{pid}_raw.json").read_text())
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
    row = next(r for r in enriched["ingredient_quality_data"]["ingredients"] if r["name"] == name)
    assert (row["canonical_id"], row["form_id"]) == ("tart_cherry", form)


def test_the_botanical_record_defers_to_iqm(pipeline):
    registry = pipeline[1]._current_canonical_identity_registry()
    assert registry.canonicalize("tart_cherry_fruit", "botanical_ingredients") == ("tart_cherry", "ingredient_quality_map")


def test_identifiers_sit_on_the_right_records():
    iqm = json.loads((DATA / "ingredient_quality_map.json").read_text())["tart_cherry"]
    assert iqm["external_ids"]["unii"] == "1L29G6428X"
    botanical = next(r for r in json.loads((DATA / "botanical_ingredients.json").read_text())["botanical_ingredients"]
                     if r["id"] == "tart_cherry_fruit")
    assert botanical.get("rxcui") != "1012134"
    records = json.loads((DATA / "literature_evidence_records.json").read_text())["literature_evidence_records"]
    assert {r["canonical_id"] for r in records} & {"tart_cherry", "tart_cherry_fruit"} == {"tart_cherry"}


def _scored(pipeline, pid):
    import copy
    from scoring_v4.scored_artifact import build_scored_artifact
    normalizer, enricher = pipeline
    raw = json.loads((FIXTURES / f"tart_cherry_one_brain_{pid}_raw.json").read_text())
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
    return enriched, build_scored_artifact(copy.deepcopy(enriched))


@pytest.mark.parametrize("pid", ["58997", "330869", "63892"])
def test_juice_trials_do_not_credit_a_dry_extract(pipeline, pid):
    """One evidence policy for tart cherry: INGR_TART_CHERRY's positive trial
    is juice concentrate (PMID 22038497), like the literature record's juice
    RCT (PMID 20459662). An extract label earns no Evidence from them."""
    _, artifact = _scored(pipeline, pid)
    (row,) = [x for x in artifact["assessment_readiness"]["evidence"]["ingredient_assessments"]
              if x.get("canonical_id") == "tart_cherry"]
    assert row["reason_code"] == "clinical_form_mismatch"
    assert artifact["quality_pillars_v4"]["evidence"]["score"] == 0.0


@pytest.mark.parametrize("text, status, reason", [
    ("Tart Cherry Juice Concentrate", "unresolved", "invalid_applicability_contract"),
    ("Montmorency Tart Cherry Juice", "unresolved", "invalid_applicability_contract"),
    ("Tart Cherry Juice Powder", "not_applicable", "clinical_form_excluded"),
    ("Tart Cherry Extract", "not_applicable", "clinical_form_excluded"),
    ("Tart Cherry", "not_applicable", "clinical_form_mismatch"),
])
def test_ingr_tart_cherry_applies_to_juice_only(text, status, reason):
    from clinical_applicability import assess_clinical_applicability
    row = {"name": text, "raw_source_text": text, "canonical_id": "tart_cherry",
           "raw_source_path": "ingredientRows[0]", "quantity": 30, "unit": "mL", "mapped": True}
    product = {"activeIngredients": [row],
               "ingredient_quality_data": {"ingredients": [row], "ingredients_scorable": [row]}}
    entry = {"id": "INGR_TART_CHERRY", "ingredient": "Tart Cherry", "matched_canonical_ids": ["tart_cherry"],
             "matched_source_row_refs": ["ingredientRows[0]"]}
    decision = assess_clinical_applicability(product, entry, assess_amount=False)
    assert decision["status"] == status
    # Exact juice preparation still needs a qualified reviewed outcome. A
    # preparation mismatch remains independently disqualifying.
    assert decision["reason_code"] == reason


def test_gnc_cherry_puree_powder_is_no_longer_called_sweet_cherry(pipeline):
    """27203 GNC Ultra Mega Green Berry: "Cherry Puree Powder" names no species.
    It resolved to dark_sweet_cherry through an alias both cherry records
    carried; it is now honestly unresolved."""
    enriched, _ = _scored(pipeline, "27203")
    (row,) = [r for r in enriched["ingredient_quality_data"]["ingredients"] if r["name"] == "Cherry Puree Powder"]
    assert row.get("canonical_id") is None
