"""The tart cherry literature record states only what PMID 20459662 reports.

Kuehl 2010 (J Int Soc Sports Nutr): 54 runners drank 355 mL tart cherry juice
or placebo twice daily for 7 days before and on race day; the juice group had a
smaller rise in post-run muscle pain. The record had said "480 mg tart cherry
anthocyanins equivalent", a "standardized extract", an inflammation outcome and
">= 480 mg standardized anthocyanin extract" applicability, none of which the
paper reports. As with goji, juice trials do not transfer to powder or extract
without bioequivalence.
"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "literature_evidence_records.json"


def _record():
    return next(r for r in json.loads(DATA.read_text())["literature_evidence_records"]
                if r.get("canonical_id") in ("tart_cherry", "tart_cherry_fruit"))


def test_the_record_describes_the_juice_trial_it_cites():
    record = _record()
    study = next(s for s in record["qualifying_human_studies"] if s["pmid"] == "20459662")
    assert "juice" in record["material_form"].lower() and "extract" not in record["material_form"].lower()
    assert "355 mL" in study["dose"] and "480" not in study["dose"]
    assert "inflammation" not in study["outcome"].lower()
    assert "studied_dose_exposure" not in record


def test_juice_evidence_does_not_transfer_to_powder_or_extract():
    record = _record()
    assert record["applicability_status"] == "applicability_unestablished"
    assert "480" not in record["applicability_decision"]
    assert "bioequivalence" in record["applicability_decision"]
