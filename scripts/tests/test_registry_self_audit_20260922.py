"""The strain card and registry copies agree with Dr Pham's reviewed evidence.

The app prints each strain as "<support> support · <indication>". Before
2026-09-22 the support level was the evidence strength alone, so HN019's null
trials read "High support", and five packet identities named benefits their own
reviewed evidence does not show. Audit: scripts/audits/closure_20260921/
pham_registry_reconcile_20260922.py; fixes: registry_self_audit_20260922.py.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from enrich_supplements_v3 import (_PROBIOTIC_RESULT_STATED, _derive_clinical_support_level,
                                   _probiotic_research_presentation)
from probiotic_measurements import derived_context_evidence, effective_strain_evidence

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "scripts/data/clinically_relevant_strains.json"


def _registry() -> dict:
    return {e["id"]: e for e in json.loads(REGISTRY.read_text())["clinically_relevant_strains"]}


def _direction(entry) -> str | None:
    return (effective_strain_evidence(entry) or {}).get("effect_direction")


@pytest.mark.parametrize("sid", ["STRAIN_LACTIS_HN019", "STRAIN_INFANTIS_35624", "STRAIN_CASEI_SHIROTA",
                                 "STRAIN_LONGUM_BB536", "STRAIN_LACTIS_BI07", "STRAIN_NISSLE_1917"])
def test_reviewed_evidence_without_a_positive_result_claims_no_support(sid):
    entry = _registry()[sid]
    assert _direction(entry) in {"null", "unresolved"}
    assert _derive_clinical_support_level(entry) is None
    assert _PROBIOTIC_RESULT_STATED.search(_probiotic_research_presentation(entry)["indication_primary"])


def test_mixed_evidence_is_weak_support_at_most():
    bb12 = _registry()["STRAIN_LACTIS_BB12"]
    assert _direction(bb12) == "mixed"
    assert _derive_clinical_support_level(bb12) == "weak"


@pytest.mark.parametrize("sid,level", [("STRAIN_LGG", "moderate"), ("STRAIN_PLANTARUM_299V", "moderate"),
                                       ("STRAIN_K12", "high")])
def test_positive_evidence_keeps_its_reviewed_strength(sid, level):
    assert _derive_clinical_support_level(_registry()[sid]) == level


@pytest.mark.parametrize("sid", ["STRAIN_ACIDOPHILUS_LA5", "STRAIN_RHAMNOSUS_GR1", "STRAIN_FERMENTUM_RC14",
                                 "STRAIN_HELVETICUS_R0052", "STRAIN_LONGUM_R0175"])
def test_no_qualifying_single_strain_evidence_names_no_indication(sid):
    presentation = _probiotic_research_presentation(_registry()[sid])
    assert presentation["review_status"] == "literature_reviewed_no_qualifying_evidence"
    assert presentation["indication_primary"] == ""


def test_every_strain_card_line_agrees_with_its_direction():
    for sid, entry in _registry().items():
        direction = _direction(entry)
        support = _derive_clinical_support_level(entry)
        shown = _probiotic_research_presentation(entry)["indication_primary"]
        if direction not in {"positive_strong", "positive_weak"}:
            assert support in (None, "weak") and (support is None or direction == "mixed"), sid
            assert not shown or _PROBIOTIC_RESULT_STATED.search(shown), (sid, shown)


def test_a_missing_direction_claims_no_support():
    entry = deepcopy(_registry()["STRAIN_K12"])
    del entry["cfu_thresholds"]["evidence"]["effect_direction"]
    assert _derive_clinical_support_level(entry) is None
    assert _probiotic_research_presentation(entry)["indication_primary"].endswith("(benefit not established)")


def test_bi07_single_strain_record_is_an_acute_crossover_surrogate():
    bi07 = _registry()["STRAIN_LACTIS_BI07"]
    contexts = {c["context_id"]: c for c in bi07["study_contexts"]}
    single = contexts["bi07_lactose_challenges_36149331"]
    assert single["study_design"] == "crossover_rct" and single["components"] == ["STRAIN_LACTIS_BI07"]
    assert single["dose"]["dose_basis"] == "single_challenge"
    assert all(2e12 <= v <= 2.5e12 for v in single["dose"]["values"])
    by_kind = {(o["hierarchy"], o["kind"], o["direction"]) for o in single["outcomes"]}
    assert ("primary", "surrogate", "positive") in by_kind
    assert ("secondary", "patient_important", "null") in by_kind          # GI symptoms
    assert ("secondary", "patient_important", "negative") in by_kind      # nausea
    combination = contexts["ncfm_bi07_bloating_21436726"]
    assert combination["identity_scope"] == "combination" and len(combination["components"]) == 2
    derived = derived_context_evidence(bi07)
    assert derived["effect_direction"] == "unresolved"                    # zero efficacy credit
    assert "ncfm_bi07_bloating_21436726" not in derived["derived_from_contexts"]
    assert bi07["cfu_thresholds"]["dr_pham_signoff"] is True


def test_bb12_reads_mixed_limited_not_strongly_positive():
    bb12 = _registry()["STRAIN_LACTIS_BB12"]
    contexts = {c["context_id"]: c for c in bb12["study_contexts"]}
    adult = contexts["bb12_low_stool_frequency_26382580"]
    assert adult["study_design"] == "rct"
    assert [o["direction"] for o in adult["outcomes"] if o["hierarchy"] == "primary"] == ["null", "null"]
    assert "not met" in bb12["cfu_thresholds"]["indication_primary"]
    assert _derive_clinical_support_level(bb12) == "weak"


def test_cu1_copy_keeps_the_primary_null_and_the_post_hoc_subset_apart():
    context = _registry()["STRAIN_SUBTILIS_CU1"]["study_contexts"][0]
    limitations = " ".join(context["limitations"])
    assert "was not reduced" in limitations
    assert "post hoc analysis of the 44-participant" in limitations
    assert "27825987 is the safety characterization" in limitations
    assert "fewer respiratory infections" not in json.dumps(context).lower()
    assert [o["direction"] for o in context["outcomes"] if o["hierarchy"] == "primary"] == ["null"]
    assert derived_context_evidence(_registry()["STRAIN_SUBTILIS_CU1"])["effect_direction"] == "null"


def test_evidence_level_is_the_effective_strength():
    from db_integrity_sanity_check import check_clinically_relevant_strains

    data = json.loads(REGISTRY.read_text())
    findings = []
    check_clinically_relevant_strains(findings, data, "registry")
    assert [f for f in findings if f.issue == "evidence_level_disagrees_with_owner"] == []
    lgg = next(e for e in data["clinically_relevant_strains"] if e["id"] == "STRAIN_LGG")
    lgg["evidence_level"] = "high"                                        # medium evidence
    findings = []
    check_clinically_relevant_strains(findings, data, "registry")
    assert [f.expected for f in findings if f.issue == "evidence_level_disagrees_with_owner"] == ["moderate"]


def test_no_identity_lists_an_alias_twice():
    for sid, entry in _registry().items():
        lowered = [a.strip().lower() for a in entry["aliases"]]
        assert len(lowered) == len(set(lowered)), sid


def test_the_registry_reconciliation_audit_passes():
    """The packet reconciliation is a standing gate, not a one-off script."""
    import runpy

    with pytest.raises(SystemExit) as done:
        runpy.run_path(str(ROOT / "scripts/audits/closure_20260921/pham_registry_reconcile_20260922.py"),
                       run_name="__main__")
    assert done.value.code == 0
