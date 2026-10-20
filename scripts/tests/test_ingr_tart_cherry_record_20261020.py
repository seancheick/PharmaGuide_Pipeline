"""INGR_TART_CHERRY describes its own evidence correctly.

- PMID 35790450 is a 30-day RCT that found no effect of Montmorency tart cherry
  juice or powdered capsules on sleep, body composition, cellular health or
  blood pressure; it is not recovery/soreness systematic-review evidence.
- UNII BUC5I9595W is GSRS "CHERRY", an unspecified mixture; sour (tart) cherry
  is 1L29G6428X (parent PRUNUS CERASUS WHOLE).
- The record keeps its name "Tart Cherry Extract" for now: renaming it to
  "Tart Cherry" (the evidence is juice and powder) would let undosed blend rows
  match by name and earn credit. It is re-applied after the Evidence
  materiality fix lands.
- PMID 33440334 (the recovery meta-analysis the notes rely on) is a listed
  reference, and PMID 40964149 is graded as the systematic review it is.
"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "backed_clinical_studies.json"


def _record():
    return next(r for r in json.loads(DATA.read_text())["backed_clinical_studies"] if r["id"] == "INGR_TART_CHERRY")


def test_the_record_names_sour_cherry_not_a_cherry_mixture():
    assert _record()["external_ids"]["unii"] == "1L29G6428X"


def test_the_record_keeps_its_name_until_the_evidence_fix():
    record = _record()
    assert record["standard_name"] == "Tart Cherry Extract"
    assert "tart cherry" not in [a.lower() for a in record["aliases"]]


def test_the_recovery_and_sleep_reviews_are_listed_and_graded():
    refs = {r["pmid"]: r for r in _record()["references_structured"]}
    assert refs["33440334"]["evidence_grade"] == "systematic_review"
    assert refs["33440334"]["retracted"] is False
    assert refs["40964149"]["evidence_grade"] == "systematic_review"


def test_pmid_35790450_is_described_as_the_null_rct_it_is():
    text = _record()["notable_studies"]
    assert "systematic reviews such as PMID 35790450" not in text
    assert "PMID 35790450" in text and "no effect" in text
    assert "PMID 33440334" in text  # the recovery meta-analysis the notes rely on
