"""The signed BCM-95 return must reach its canonical source contexts."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clinical_applicability import assess_clinical_source_review, reviewed_entries
from clinical_evidence_schema import validate_ingredient_context


def _record():
    data = json.loads((Path(__file__).resolve().parents[1] / "data" / "backed_clinical_studies.json").read_text())
    return next(row for row in data["backed_clinical_studies"] if row["id"] == "BRAND_BCM95")


def test_bcm95_return_covers_both_retained_sources_without_inventing_dose_curve():
    record = _record()
    contexts = record.get("study_contexts", [])
    assert len(contexts) == 2
    assert {pmid for context in contexts for pmid in context["source_pmids"]} == {
        ref["pmid"] for ref in record["references_structured"]
    } == {"30975196", "33516238"}
    assert {tuple(c["dose"]["values"]) for c in contexts} == {(1500,), (1000,)}
    assert {c["dose"]["duration_days"] for c in contexts} == {28, 42}
    assert all(c["identity"]["branded_material"] == "BCM-95/Curcugreen" for c in contexts)
    assert all(c["dose"]["dose_basis"] == "nominal_assigned_arm" for c in contexts)
    assert "minimum_daily_dose" not in record.get("applicability", {})
    assert record["total_enrollment"] is None
    assert "149 enrolled and 139 analyzed" in record["notes"]
    assert "139 randomized" not in record["notes"]
    assert record["score_contribution"] == "tier_1"  # source extraction cannot invent a grade


def test_bcm95_source_contexts_keep_active_comparator_and_scope_limits():
    contexts = _record().get("study_contexts", [])
    assert contexts
    for context in contexts:
        assert validate_ingredient_context(context) == []
        assert context["clinical_review"] == {
            "reviewer": "Dr. Pham", "reviewed_at": "2026-10-26",
            "scope": "identity_dose_outcome_applicability",
        }
        assert context["review_status"] == "clinician_approved"
        assert context["outcomes"][0]["direction"] in {"null", "mixed"}
        assert "not placebo superiority" in " ".join(context["limitations"])
        assert "product matching" in " ".join(context["limitations"])
    reviewed_entries.cache_clear()
    assert assess_clinical_source_review(_record())["is_complete"] is True


def test_magtein_signed_return_keeps_three_trial_families_and_one_correction():
    record = reviewed_entries()["BRAND_MAGTEIN"]
    contexts = record.get("study_contexts", [])
    assert len(contexts) == 3
    assert {pmid for c in contexts for pmid in c["source_pmids"]} == {
        "39252819", "40567408", "41601871", "36558392"
    }
    isolated = [c for c in contexts if c.get("scoring_eligible") is not False]
    assert len(isolated) == 2
    assert {tuple(c["dose"]["values"]) for c in isolated} == {(1000,), (2000,)}
    assert {c["dose"]["duration_days"] for c in isolated} == {21, 42}
    correction_context = next(c for c in contexts if "40567408" in c["source_pmids"])
    assert correction_context["source_pmids"] == ["39252819", "40567408"]
    assert correction_context["source_integrity"] == "corrected"
    combo = next(c for c in contexts if "36558392" in c["source_pmids"])
    assert combo["scoring_eligible"] is False
    assert combo["identity_scope"] == "combination"
    assert len(combo["components"]) == 5
    assert next(r for r in record["references_structured"] if r["pmid"] == "36558392")["scoring_eligible"] is False
    assert "cognitive age ↓" not in record["key_endpoints"]
    assert "Healthy Aging/Longevity" not in record["health_goals_supported"]
    assert set(record["health_goals_supported"]) == {"Focus & Mental Clarity", "Sleep Quality"}
    assert reviewed_entries()["BRAND_BCM95"]["health_goals_supported"] == ["Joint & Bone Health"]


def test_magtein_contexts_apply_current_publisher_correction_without_altering_p_values():
    record = reviewed_entries()["BRAND_MAGTEIN"]
    contexts = record.get("study_contexts", [])
    assert contexts
    cognition = next(c for c in contexts if c["source_pmids"] == ["41601871"])
    assert cognition["source_integrity"] == "corrected"
    assert "two-tailed" in " ".join(cognition["limitations"])
    assert "results unchanged" in " ".join(cognition["limitations"])
    for context in contexts:
        assert validate_ingredient_context(context) == []
        assert context["clinical_review"]["reviewed_at"] == "2026-10-26"
    assert assess_clinical_source_review(record)["is_complete"] is True


def test_scoped_approvals_do_not_validate_provisional_record_grades_or_claim_no_review():
    for key in ("BRAND_BCM95", "BRAND_MAGTEIN"):
        record = reviewed_entries()[key]
        assert record["effect_direction"] == "mixed"
        rationale = record["effect_direction_rationale"]
        assert "2026-10-26" in rationale
        assert "provisional" in rationale
        assert "does not validate" in rationale
        assert "This is not attributable clinician approval" not in rationale
        assert "None of these facts supplies clinician approval" not in record["notes"]
