"""INGR_TART_CHERRY describes its own evidence correctly.

- PMID 35790450 is a 30-day RCT that found no effect of Montmorency tart cherry
  juice or powdered capsules on sleep, body composition, cellular health or
  blood pressure; it is not recovery/soreness systematic-review evidence.
- UNII BUC5I9595W is GSRS "CHERRY", an unspecified mixture; sour (tart) cherry
  is 1L29G6428X (parent PRUNUS CERASUS WHOLE).
- The evidence is juice and powder, not an extract, so the record is "Tart
  Cherry"; "tart cherry extract" stays an alias so existing matches hold.
"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "backed_clinical_studies.json"


def _record():
    return next(r for r in json.loads(DATA.read_text())["backed_clinical_studies"] if r["id"] == "INGR_TART_CHERRY")


def test_the_record_names_sour_cherry_not_a_cherry_mixture():
    assert _record()["external_ids"]["unii"] == "1L29G6428X"


def test_the_record_is_tart_cherry_and_keeps_the_extract_alias():
    record = _record()
    assert record["standard_name"] == "Tart Cherry"
    assert "tart cherry extract" in [a.lower() for a in record["aliases"]]


def test_pmid_35790450_is_described_as_the_null_rct_it_is():
    text = _record()["notable_studies"]
    assert "systematic reviews such as PMID 35790450" not in text
    assert "PMID 35790450" in text and "no effect" in text
    assert "PMID 33440334" in text  # the recovery meta-analysis the notes rely on
