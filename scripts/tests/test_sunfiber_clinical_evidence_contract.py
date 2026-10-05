"""PHGG source attribution and bounded clinical claims; no numerical calibration pins."""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "backed_clinical_studies.json"

def entry():
    return next(e for e in json.loads(DATA.read_text())["backed_clinical_studies"] if e["id"] == "BRAND_SUNFIBER")

def test_indexed_sunfiber_trials_have_explicit_brand_and_correct_authors():
    e = entry()
    assert "inferential" not in e["notable_studies"]
    assert "explicitly" in e["notes"] and "Sunfiber" in e["notes"]
    assert "Yasukawa" in e["notable_studies"]
    assert "Takahashi et al. (2019" not in e["notable_studies"]
    refs = {r["pmid"]: r for r in e["references_structured"]}
    assert refs["26855665"]["published_date"] == "2016-02-06"

def test_sunfiber_claims_do_not_borrow_immune_or_stress_outcomes():
    e = entry()
    assert e["health_goals_supported"] == ["Digestive Health"]
    assert e["endpoint_relevance_tags"] == ["digestive_health"]
    assert e["published_studies"] == ["RCT"]
    assert e["total_enrollment"] == 121  # largest randomized trial; not pooled across populations
    assert e["effect_direction"] == "mixed"
    assert "not" in e["effect_direction_rationale"].lower()
    assert "SCFA production ↑" not in e["key_endpoints"]
    assert "IBS symptoms ↓" not in e["key_endpoints"]

def test_sunfiber_references_retain_positive_and_null_outcome_scope():
    e = entry()
    refs = {r["pmid"]: set(r["supports_claims"]) for r in e["references_structured"]}
    assert {"ibs_bloating_and_gas", "not_overall_ibs_severity_or_quality_of_life"} <= refs["26855665"]
    assert {"loose_stool_form", "microbiome_secondary_surrogate", "not_stool_frequency"} <= refs["31509971"]
    assert "Taiyo" in e["notes"] and "fund" in e["notes"].lower()

def test_unqualified_guar_fiber_cannot_identify_hydrolyzed_preparation():
    assert "guar fiber" not in entry()["aliases"]
    assert "sunfiber" in entry()["aliases"]
    assert "partially hydrolyzed guar gum" in entry()["aliases"]
