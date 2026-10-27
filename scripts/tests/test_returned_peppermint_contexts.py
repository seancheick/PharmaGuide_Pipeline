"""The signed peppermint return preserves preparation-specific mixed findings."""
import json
from pathlib import Path

from clinical_applicability import assess_clinical_source_review, reviewed_entries
from clinical_evidence_schema import validate_ingredient_context


def _record():
    data = json.loads((Path(__file__).resolve().parents[1] / "data" / "backed_clinical_studies.json").read_text())
    return next(row for row in data["backed_clinical_studies"] if row["id"] == "INGR_PEPPERMINT_OIL")


def test_signed_peppermint_source_contexts_retain_preparation_and_primary_nulls():
    contexts = _record().get("study_contexts", [])
    assert len(contexts) == 4
    nee = next(context for context in contexts if context["source_pmids"] == ["34319275"])
    assert nee["dose"]["values"] == [540]
    assert nee["dose"]["duration_days"] == 42
    assert nee["outcomes"][0]["hierarchy"] == "primary"
    assert nee["outcomes"][0]["direction"] == "null"
    assert nee["scoring_eligible"] is False
    weerts = [context for context in contexts if context["source_pmids"] == ["31470006"]]
    assert len(weerts) == 2
    assert {context["identity"]["chemical_form"] for context in weerts} == {
        "small-intestinal-release peppermint oil (Tempocol)",
        "ileocolonic-release peppermint oil (Tempocol)",
    }
    assert all(context["dose"]["values"] == [546] for context in weerts)
    assert all(context["dose"]["duration_days"] == 56 for context in weerts)
    assert all(context["outcomes"][0]["direction"] == "null" for context in weerts)
    assert next(context for context in weerts if "ileocolonic" in context["identity"]["chemical_form"])["scoring_eligible"] is False


def test_peppermint_pooled_signal_does_not_invent_a_universal_dose_or_label_conversion():
    record = _record()
    contexts = record.get("study_contexts", [])
    assert contexts
    pooled = next(context for context in contexts if context["source_pmids"] == ["35942669"])
    assert pooled["dose"]["values"] == []
    assert pooled["dose"]["dose_basis"] == "not_applicable"
    assert len(pooled["included_study_pmids"]) == 9
    assert "very low" in " ".join(pooled["limitations"]).lower()
    assert "Capanni" in " ".join(pooled["limitations"])
    assert record["effect_direction"] == "mixed"
    assert record["score_contribution"] == "tier_1"
    assert "minimum_daily_dose" not in record["applicability"]
    assert "mL-to-mg" in record["notes"]
    refs = {reference["pmid"]: reference for reference in record["references_structured"]}
    assert refs["26319955"]["scoring_eligible"] is False
    assert "IBgard" in refs["26319955"]["notes"]
    assert refs["24100754"]["scoring_eligible"] is False
    assert refs["31470006"]["scoring_eligible"] is False
    assert refs["34319275"]["scoring_eligible"] is False


def test_peppermint_signed_source_contexts_validate_without_clearing_product_matching():
    record = _record()
    contexts = record.get("study_contexts", [])
    assert contexts
    for context in contexts:
        assert validate_ingredient_context(context) == []
        assert context["clinical_review"] == {
            "reviewer": "Dr. Pham", "reviewed_at": "2026-10-26",
            "scope": "identity_dose_outcome_applicability",
        }
        assert "saved-label" in " ".join(context["limitations"])
    reviewed_entries.cache_clear()
    assert assess_clinical_source_review(record)["is_complete"] is True
