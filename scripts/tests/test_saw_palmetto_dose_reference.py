"""Saw palmetto's dose record states its studied regimen, not a benchmark or a limit.

320 mg/day (160 mg twice daily) is the EMA well-established-use posology for the
hexane soft extract and the usual trial regimen. It is not an efficacy
threshold: the 2023 Cochrane review (PMID 37345871) finds little to no benefit
over placebo, and CAMUS (PMID 21954478) found no benefit at 320, 640 or
960 mg/day. No upper limit is established; 960 mg/day was the highest dose
studied. The record had a bare "640" upper limit and a note claiming no
benefit above 320 mg.
"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
EMA = ("https://www.ema.europa.eu/en/documents/herbal-monograph/"
       "final-european-union-herbal-monograph-serenoa-repens-w-bartram-small-fructus_en.pdf")


def _row():
    rows = json.loads((DATA / "rda_therapeutic_dosing.json").read_text())["therapeutic_dosing"]
    [row] = [r for r in rows if r["id"] == "saw_palmetto_extract"]
    return row


def test_record_is_a_discrete_studied_regimen_with_its_sources():
    row = _row()
    semantics = row["reference_semantics"]
    assert semantics["reference_type"] == "discrete_studied_regimen"
    assert semantics["curve"] == "completed_no_benchmark_neutral"
    assert semantics["approval_status"].startswith("approved_existing_neutral_")
    assert {"42157952", "37345871", "21954478"} <= set(row["references"])
    assert EMA in semantics["source_ids"]
    assert "https://pubmed.ncbi.nlm.nih.gov/37345871/" in semantics["source_ids"]
    assert "https://pubmed.ncbi.nlm.nih.gov/21954478/" in semantics["source_ids"]


def test_no_unsupported_upper_limit_or_benefit_claim():
    row = _row()
    assert "upper_limit" not in row
    assert "not established" in row["notes"].lower()
    text = json.dumps(row)
    assert "640" not in row["notes"]
    assert "show no additional benefit" not in text
    assert "need underlying trial/form-specific receipt" not in text


def test_dose_stays_neutral_for_saw_palmetto():
    from scoring_v4.modules.botanical_profile import _botanical_benchmark

    row = {"canonical_id": "saw_palmetto", "name": "Saw Palmetto", "standard_name": "Saw Palmetto"}
    assert _botanical_benchmark(row) == "absent"
