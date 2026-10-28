"""Study contexts are source-bound assessments, not automatic efficacy credit."""
from copy import deepcopy

import pytest

import probiotic_measurements as pm
import studied_formulas
from test_probiotic_applicability_rubric import strain_product


def context(**changes):
    row = {
        "context_id": "synthetic-context", "source_pmids": ["synthetic-source"],
        "identity_scope": "exact_strain", "components": ["STRAIN_LGG"],
        "population": {"age_group": "adult", "description": "Synthetic adult population"},
        "purpose": "treatment", "condition": "constipation",
        "dose": {"basis": "discrete_daily_arms", "unit": "CFU", "values": [1e9, 1e10],
                 "dosage_forms": ["capsule"], "duration_days": 28, "co_therapies": []},
        "outcomes": [{"name": "stool_frequency", "hierarchy": "primary",
                      "kind": "patient_important", "direction": "null"}],
        "trial_family": "synthetic-trial", "limitations": ["Synthetic test only"],
        "review_status": "source_verified_pending_clinical_review",
    }
    row.update(changes)
    return row


@pytest.fixture
def registry(monkeypatch):
    rows = deepcopy(studied_formulas._clinical_strain_registry())
    rows["STRAIN_LGG"]["study_contexts"] = [context()]
    # Real combination contexts owned by other identities join STRAIN_LGG at
    # assessment time (Wave 2 curation). These unit tests isolate the bridge on
    # the synthetic LGG context above; the cross-owner join keeps its own test.
    for rid, row in rows.items():
        if rid != "STRAIN_LGG" and row.get("study_contexts"):
            row["study_contexts"] = [c for c in row["study_contexts"]
                                     if "STRAIN_LGG" not in c.get("components", [])]
    monkeypatch.setattr(studied_formulas, "_clinical_strain_registry", lambda: rows)
    return rows


def assessment(product):
    return studied_formulas.assess_probiotic_evidence(product)["strain_assessments"][0]


def test_context_uses_current_registry_not_a_caller_stamp(registry):
    p = strain_product(dose=1e9)
    p["probiotic_data"]["clinical_strains"][0]["study_contexts"] = [context(condition="ibs")]
    row = assessment(p)
    result = row["study_contexts"][0]
    assert result["condition"] == "constipation"
    assert result["dose_comparison"] == "matches_tested_daily_dose"
    assert result["outcomes"][0]["direction"] == "null"
    assert result["clinical_applicability"] == "not_established"
    assert row["dose_applicable"] is False


@pytest.mark.parametrize("dose,expected", [(1e9, "matches_tested_daily_dose"),
    (5e9, "outside_tested_daily_doses"), (1e10, "matches_tested_daily_dose"),
    (None, "label_dose_unknown")])
def test_discrete_arms_do_not_create_an_interpolated_window(registry, dose, expected):
    assert assessment(strain_product(dose=dose))["study_contexts"][0]["dose_comparison"] == expected


@pytest.mark.parametrize("basis", ["measured_viability", "single_challenge", "unresolved"])
def test_other_measurements_never_become_daily_dose_thresholds(registry, basis):
    registry["STRAIN_LGG"]["study_contexts"][0]["dose"]["basis"] = basis
    if basis == "unresolved":
        registry["STRAIN_LGG"]["study_contexts"][0]["dose"]["values"] = []
    assert assessment(strain_product(dose=1e9))["study_contexts"][0]["dose_comparison"] == "study_daily_dose_unresolved"


def test_pending_canonical_per_strain_dose_is_unresolved_not_outside_range(registry):
    dose = registry["STRAIN_LGG"]["study_contexts"][0]["dose"]
    dose.update(
        basis="unresolved",
        dose_basis="per_strain_daily",
        dose_status="extraction_pending",
        values=[],
    )
    result = assessment(strain_product(dose=1e9))["study_contexts"][0]
    assert result["dose_comparison"] == "study_daily_dose_unresolved"
    assert result["clinical_applicability"] == "not_established"


def test_spore_counts_never_match_a_cfu_label_dose(registry):
    row = registry["STRAIN_LGG"]["study_contexts"][0]
    row["dose"].update(measurement_type="spores", unit="spores", values=[1e9])
    result = assessment(strain_product(dose=1e9))["study_contexts"][0]
    assert result["dose_comparison"] == "study_dose_not_viable_count"
    assert result["clinical_applicability"] == "not_established"


def test_combination_and_species_context_cannot_become_individual_efficacy(registry):
    c = registry["STRAIN_LGG"]["study_contexts"][0]
    c.update(identity_scope="combination", components=["STRAIN_LGG", "STRAIN_LACTIS_BI07"])
    result = assessment(strain_product(dose=1e9))["study_contexts"][0]
    assert result["dose_comparison"] == "combination_not_individual_dose"
    assert result["clinical_applicability"] == "not_established"
    c.update(identity_scope="species_general", components=["STRAIN_LGG"])
    assert assessment(strain_product(dose=1e9))["study_contexts"][0]["dose_comparison"] == "species_not_exact_strain"


def test_context_never_borrows_blend_total(registry):
    p = strain_product(dose=1e9)
    p["probiotic_data"]["probiotic_blends"][0]["strains"].append("Another organism")
    assert assessment(p)["study_contexts"][0]["dose_comparison"] == "label_dose_unknown"


def test_marketing_cannot_prove_patient_condition_or_regimen(registry):
    p = strain_product(dose=1e9)
    before = assessment(p)["study_contexts"]
    p.update(product_name="Treat constipation in adults for 28 days", statements=["constipation"])
    after = assessment(p)["study_contexts"]
    # A claimed purpose can change, but it cannot establish patient diagnosis,
    # dose applicability or the source trial facts.
    assert [{k: v for k, v in c.items() if k != "claimed_purpose_assessment"} for c in after] == [
        {k: v for k, v in c.items() if k != "claimed_purpose_assessment"} for c in before]
    assert after[0]["clinical_applicability"] == "not_established"
    assert before[0]["clinical_applicability"] == "not_established"


@pytest.mark.parametrize("field,value", [("source_pmids", []), ("outcomes", []),
    ("components", ["NONEXISTENT"]), ("review_status", "approved"), ("population", {}),
    ("purpose", "anything"), ("dose", {"basis": "discrete_daily_arms", "values": [True]})])
def test_invalid_context_is_explicit_and_cannot_crash_scoring(registry, field, value):
    registry["STRAIN_LGG"]["study_contexts"][0][field] = value
    row = assessment(strain_product(dose=1e9))
    assert row["study_contexts"][0]["status"] == "invalid_context"
    assert row["dose_applicable"] is False


def test_source_review_hold_does_not_hide_a_context_or_approve_it(registry):
    registry["STRAIN_LGG"]["cfu_thresholds"]["dr_pham_signoff"] = False
    row = assessment(strain_product(dose=1e9))
    assert row["research_accepted"] is False
    assert row["study_contexts"][0]["review_status"] == "source_verified_pending_clinical_review"
    assert row["dose_applicable"] is False


def test_context_requires_real_label_ownership(registry):
    p = strain_product(dose=1e9)
    p["activeIngredients"][0]["name"] = "Unrelated label row"
    row = assessment(p)
    assert row["study_contexts"][0]["dose_comparison"] == "identity_owner_unresolved"
    assert row["dose_applicable"] is False


def test_pending_context_cannot_be_bypassed_by_an_old_universal_range(registry):
    registry["STRAIN_LGG"]["applicability"] = {
        "minimum_daily_dose": 1e9, "maximum_daily_dose": 1e10, "dose_unit": "CFU",
        "source_pmids": ["synthetic-source"], "supported_outcomes": ["digestive"],
        "dosage_forms": ["capsule"], "target_population": "adult",
        "studied_population": "Synthetic adults",
    }
    assert assessment(strain_product(dose=1e9))["dose_applicable"] is False


def test_unknown_endpoint_hierarchy_is_not_invented(registry):
    registry["STRAIN_LGG"]["study_contexts"][0]["outcomes"][0]["hierarchy"] = "unresolved"
    result = assessment(strain_product(dose=1e9))["study_contexts"][0]
    assert result["status"] == "source_context_recorded"
    assert result["outcomes"][0]["hierarchy"] == "unresolved"


def test_returned_context_cannot_mutate_canonical_research(registry):
    result = assessment(strain_product(dose=1e9))["study_contexts"][0]
    result["outcomes"][0]["direction"] = "positive"
    result["dose"]["values"].append(5e9)
    fresh = assessment(strain_product(dose=5e9))["study_contexts"][0]
    assert fresh["outcomes"][0]["direction"] == "null"
    assert fresh["dose_comparison"] == "outside_tested_daily_doses"


def test_combination_context_has_one_owner_but_matches_each_component(registry):
    c = registry["STRAIN_LGG"].pop("study_contexts")[0]
    c.update(identity_scope="combination", components=["STRAIN_LGG", "STRAIN_LACTIS_BI07"])
    registry["STRAIN_LACTIS_BI07"]["study_contexts"] = [c]
    result = assessment(strain_product(dose=1e9))["study_contexts"]
    assert len(result) == 1
    assert result[0]["dose_comparison"] == "combination_not_individual_dose"
    assert assessment(strain_product(dose=1e9))["dose_applicable"] is False


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 0, True])
def test_nonpositive_and_nonfinite_study_dose_is_invalid(registry, value):
    registry["STRAIN_LGG"]["study_contexts"][0]["dose"]["values"] = [value]
    assert assessment(strain_product(dose=1e9))["study_contexts"][0]["status"] == "invalid_context"


def test_shared_guideline_has_one_study_family_across_native_contexts():
    registry = studied_formulas._clinical_strain_registry()
    contexts = [context for cid in ("STRAIN_LGG", "STRAIN_SACCHAROMYCES")
                for context in registry[cid]["study_contexts"]
                if "26756877" in context["source_pmids"]]
    assert len(contexts) == 2
    assert len({context["context_id"] for context in contexts}) == 2
    assert len({context["trial_family"] for context in contexts}) == 1


def test_priority_native_contexts_are_curated_without_new_approval():
    registry = studied_formulas._clinical_strain_registry()
    expected = {
        "STRAIN_LGG": {"26756877", "17229242"},
        "STRAIN_LACTIS_BB12": {"26382580"},
        "STRAIN_LACTIS_BI07": {"21436726", "36149331"},
        "STRAIN_LACTIS_HN019": {"39356506", "40320938"},
        "STRAIN_SACCHAROMYCES": {"26756877", "22472744", "41675330"},
        "STRAIN_ACIDOPHILUS_NCFM": {"28082816", "19651563"},
        "STRAIN_LACTIS_BL04": {"24268677", "28343401"},
        "STRAIN_PARACASEI_LPC37": {"33385020", "37662485"},
    }
    seen = set()
    for cid, pmids in expected.items():
        contexts = registry[cid].get("study_contexts", [])
        # 2026-09-13 Wave 1 added contexts on top; the 2026-09-04 sources must
        # still be present, valid and unapproved (nothing below borrows approval).
        assert pmids <= {p for c in contexts for p in c["source_pmids"]}
        # 2026-09-14: the owner approved the reviewed contexts; every approval
        # must carry attributable review provenance, nothing borrows approval.
        for c in contexts:
            assert c["review_status"] in {"source_verified_pending_clinical_review",
                                          "clinician_approved", "adjudication_required",
                                          "rejected_source"}
            if c["review_status"] == "clinician_approved":
                assert pm.clinical_review_provenance_valid(c)
        for c in contexts:
            assert studied_formulas.valid_native_study_context(c, cid)
            assert all(p.isdigit() for p in c["source_pmids"])
            assert c["context_id"] not in seen
            seen.add(c["context_id"])
    # 40 until Dr Pham's 2026-09-22 review: she restored Bi-07 and BB-12 (suspended
    # 2026-09-04) and withdrew six citations as single-strain evidence.
    assert sum(r.get("cfu_thresholds", {}).get("dr_pham_signoff") is True
               for r in registry.values()) == 36
    for cid in ("STRAIN_LACTIS_BI07", "STRAIN_LACTIS_BB12"):
        assert registry[cid]["cfu_thresholds"]["dr_pham_signoff_verified_by"].startswith("Dr Pham (2026-09-22")
    for cid in ("STRAIN_ACIDOPHILUS_NCFM", "STRAIN_LACTIS_BL04"):
        assert "Best-available PubMed hit" not in registry[cid]["cfu_thresholds"]["notes"]


def test_real_study_doses_preserve_ambiguity_and_separate_arms():
    registry = studied_formulas._clinical_strain_registry()
    def study(cid, pmid):
        return next(c for c in registry[cid]["study_contexts"] if pmid in c["source_pmids"])
    assert study("STRAIN_LGG", "17229242")["dose"]["basis"] == "unresolved"
    assert study("STRAIN_LACTIS_BB12", "26382580")["dose"]["values"] == [1e9, 1e10]
    assert study("STRAIN_LACTIS_HN019", "39356506")["dose"]["basis"] == "measured_viability"
    assert study("STRAIN_LACTIS_BI07", "36149331")["dose"]["basis"] == "single_challenge"
    assert study("STRAIN_LACTIS_BI07", "21436726")["identity_scope"] == "combination"
    assert study("STRAIN_SACCHAROMYCES", "26756877")["identity_scope"] == "species_general"


def test_lpc37_primary_null_results_and_viability_are_not_positive_dose_arms():
    entry = studied_formulas._clinical_strain_registry()["STRAIN_PARACASEI_LPC37"]
    contexts = {c["source_pmids"][0]: c for c in entry.get("study_contexts", [])}
    assert set(contexts) == {"33385020", "37662485"}
    for pmid, values, days in (("33385020", [1.75e10, 1.68e10], 35),
                               ("37662485", [1.56e10, 1.35e10], 70)):
        context_row = contexts[pmid]
        assert context_row["dose"]["basis"] == "measured_viability"
        assert context_row["dose"]["values"] == values
        assert context_row["dose"]["duration_days"] == days
        assert context_row["review_status"] == "clinician_approved"  # 2026-09-14 owner approval
        assert pm.clinical_review_provenance_valid(context_row)
        assert [o["direction"] for o in context_row["outcomes"]
                if o["hierarchy"] == "primary"] == ["null"]
    evidence = entry["cfu_thresholds"]["evidence"]
    assert evidence["pmid"] == "33385020"  # No approval borrowed by the new paper.
    assert evidence["effect_direction"] == "null"
    assert evidence["clinical_validation"]["q1_strain_explicit"] == "YES"
    assert evidence["clinical_validation"]["q4_dose_mentioned"] == "YES"
    assert entry["cfu_thresholds"]["dr_pham_signoff"] is True  # Historical record only.


def test_lpc37_sources_join_without_new_approval_or_interpolated_dose():
    from scoring_v4.modules.probiotic_evidence import score_evidence

    product = strain_product(clinical_id="STRAIN_PARACASEI_LPC37",
                             name="Lactobacillus paracasei Lpc-37", dose=1.56e10)
    product["product_name"] = "Stress support probiotic"
    result = assessment(product)
    # Exact-strain sources plus the Wave 1 combination contexts that join Lpc-37
    # through `components`; joining never lends approval or an individual dose.
    assert {"33385020", "37662485"} <= set(result["source_pmids"])
    assert result["scoring_source_pmids"] == []  # Shared assessment awards no Evidence.
    assert result["dose_applicable"] is False
    assert {c["dose_comparison"] for c in result["study_contexts"]} == {
        "study_daily_dose_unresolved", "combination_not_individual_dose"}
    assert all(c["clinical_applicability"] == "not_established" for c in result["study_contexts"])
    evidence = score_evidence(product)
    # Its contexts are clinician-approved: a finished review, not pending work.
    assert evidence["metadata"]["evidence_assessment"]["native_context_review"]["status"] == "clinically_reviewed"
    assert evidence["metadata"]["evidence_result_state"] == "evaluated_null"
    unrelated = deepcopy(product)
    unrelated["product_name"] = "Digestive support probiotic"
    assert score_evidence(unrelated)["score"] == 0
    assert score_evidence(unrelated)["metadata"]["evidence_result_state"] == "research_present_applicability_unestablished"


@pytest.mark.parametrize("stale_field", ["indication_primary", "indication_secondary", "clinical_support_level"])
def test_native_indication_copy_uses_current_registry_not_old_artifact(stale_field):
    from scoring_v4.modules.probiotic_evidence import score_evidence

    product = strain_product(clinical_id="STRAIN_PARACASEI_LPC37",
                             name="Lactobacillus paracasei Lpc-37", dose=1.56e10)
    product["product_name"] = "Stress support probiotic"
    clinical = product["probiotic_data"]["clinical_strains"][0]
    clinical[stale_field] = "digestive immune support"
    before = deepcopy(product)
    evidence = score_evidence(product)
    categories = evidence["metadata"]["claim_alignment"]["strain_categories"]
    assert not {"digestive", "immune"}.intersection(categories)
    assert evidence["metadata"]["evidence_result_state"] == "evaluated_null"
    assert product == before


def _with_contexts_pending(monkeypatch, cid):
    rows = deepcopy(studied_formulas._clinical_strain_registry())
    for context in rows[cid].get("study_contexts") or []:
        context["review_status"] = "source_verified_pending_clinical_review"
    monkeypatch.setattr(studied_formulas, "_clinical_strain_registry", lambda: rows)


def test_source_verified_pending_research_is_not_called_no_human_evidence(monkeypatch):
    from scoring_v4.modules.probiotic_evidence import score_evidence
    from scoring_v4.confidence import _evidence_confidence

    p = strain_product(clinical_id="STRAIN_ACIDOPHILUS_NCFM", name="Lactobacillus acidophilus NCFM", dose=1e9)
    _with_contexts_pending(monkeypatch, "STRAIN_ACIDOPHILUS_NCFM")
    evidence = score_evidence(p)
    assert evidence["score"] == 0  # No new approval or numeric credit.
    assert evidence["metadata"]["evidence_result_state"] == "native_research_review_incomplete"
    confidence, reasons = _evidence_confidence(p, {"dimensions": {"evidence": evidence}},
        evidence_assessment={"readiness": "complete"})
    assert confidence == "moderate"
    assert reasons == ["evidence_review_incomplete"]


def test_clinician_approved_research_is_a_finished_review_even_without_credit():
    """NCFM has 10 clinician-approved human contexts; none applies to this label.

    Until 2026-09-21 any recorded context read as 'pending_clinical_review', so a
    finished review kept products incomplete. The conclusion is terminal and earns
    nothing new: approval records review provenance, it grants no points. Its own
    exact-strain trials own its human evidence and are null, so the finished
    review reads as a reviewed null.
    """
    from scoring_v4.modules.probiotic_evidence import score_evidence

    for dose in (None, 1e9):
        p = strain_product(clinical_id="STRAIN_ACIDOPHILUS_NCFM",
                           name="Lactobacillus acidophilus NCFM", dose=dose)
        p['product_name'] = 'Probiotic for irritable bowel syndrome'
        review = studied_formulas.assess_probiotic_evidence(p)["native_context_review"]
        evidence = score_evidence(p)
        assert review["status"] == "clinically_reviewed" and review["pending_context_ids"] == []
        assert evidence["score"] == 0
        assert evidence["metadata"]["evidence_result_state"] == "evaluated_null"


def test_a_context_awaiting_adjudication_is_still_pending(monkeypatch):
    # Dr Pham approved the two held LA-5 + BB-12 trials on 2026-09-22; a context put
    # back on hold must read as pending again.
    p = strain_product(clinical_id="STRAIN_ACIDOPHILUS_LA5", name="Lactobacillus acidophilus LA-5", dose=1e9)
    assert studied_formulas.assess_probiotic_evidence(p)["native_context_review"]["status"] == "clinically_reviewed"
    rows = deepcopy(studied_formulas._clinical_strain_registry())
    held = next(c for c in rows["STRAIN_ACIDOPHILUS_LA5"]["study_contexts"]
                if c["context_id"] == "la5_bb12_lc01_yogurt_aad_30439760")
    held["review_status"] = "adjudication_required"
    monkeypatch.setattr(studied_formulas, "_clinical_strain_registry", lambda: rows)
    review = studied_formulas.assess_probiotic_evidence(p)["native_context_review"]
    assert review["status"] == "pending_clinical_review"
    assert review["pending_context_ids"] == ["la5_bb12_lc01_yogurt_aad_30439760"]


def test_an_uncurated_strain_stub_stays_incomplete(monkeypatch):
    from scoring_v4.modules.probiotic_evidence import score_evidence
    from test_evidence_completeness_closure_20260921 import unreview_strain

    unreview_strain(monkeypatch, "STRAIN_ACIDOPHILUS_LA14")
    p = strain_product(clinical_id="STRAIN_ACIDOPHILUS_LA14", name="Lactobacillus acidophilus La-14", dose=1e9)
    assert score_evidence(p)["metadata"]["evidence_result_state"] == "native_research_review_incomplete"


def test_unaccepted_strain_review_is_not_reported_as_a_dose_gap(registry):
    """An unaccepted identity review outranks a missing dose: it is unfinished work."""
    registry["STRAIN_LGG"]["cfu_thresholds"]["review_status"] = "pending_review"
    registry["STRAIN_LGG"]["cfu_thresholds"]["dr_pham_signoff"] = False
    p = strain_product(clinical_id="STRAIN_LGG", name="Lactobacillus rhamnosus GG", dose=None)
    assert assessment(p)["status"] == "strain_identity_or_review_unresolved"


def test_undisclosed_cfu_with_accepted_human_research_is_terminal_contextual_credit():
    """An amount cannot change the finished but inapplicable research determination."""
    from scoring_v4.modules.probiotic_evidence import score_evidence

    p = strain_product(clinical_id="STRAIN_LGG", name="Lactobacillus rhamnosus GG", dose=None)
    p["product_name"] = "Sleep support probiotic"  # Unrelated to every LGG context.
    evidence = score_evidence(p)
    assert evidence["metadata"]["evidence_result_state"] == "research_present_applicability_unestablished"
    assert evidence["score"] == 0
    assert "dose_applicability" not in evidence["components"]
    dosed = strain_product(clinical_id="STRAIN_LGG", name="Lactobacillus rhamnosus GG", dose=1e9)
    dosed["product_name"] = p["product_name"]
    assert score_evidence(dosed)["components"] == evidence["components"]
    # A claim-free label earns the same scoped credit with or without an amount.
    assert score_evidence(strain_product(clinical_id="STRAIN_LGG", name="Lactobacillus rhamnosus GG", dose=None))[
        "components"] == score_evidence(strain_product(clinical_id="STRAIN_LGG",
        name="Lactobacillus rhamnosus GG", dose=1e9))["components"]


@pytest.mark.parametrize("cid,name", [
    ("STRAIN_LGG", "Lactobacillus rhamnosus GG"),
    ("STRAIN_LACTIS_HN019", "Bifidobacterium lactis HN019"),
    ("STRAIN_SACCHAROMYCES", "Saccharomyces boulardii"),
])
def test_pending_review_is_independent_of_existing_positive_or_null_credit(monkeypatch, cid, name):
    """Review incompleteness stays visible even when a finished label earns zero.

    These labels lack an applicable positive primary family. A review hold must
    not be disguised as a missing amount or a finished null determination.
    """
    from scoring_v4.modules.probiotic_evidence import score_evidence
    from scoring_v4.confidence import _evidence_confidence

    p = strain_product(clinical_id=cid, name=name, dose=1e9)
    if cid == 'STRAIN_LACTIS_HN019':
        p['product_name'] = 'Probiotic for functional constipation'
    elif cid == 'STRAIN_LGG':
        # Claim-free LGG now earns its scoped GI/respiratory credit; an
        # unrelated label keeps the finished-but-zero scenario this tests.
        p['product_name'] = 'Sleep support probiotic'
    reviewed = score_evidence(p)
    assert reviewed["metadata"]["evidence_assessment"]["native_context_review"]["status"] == "clinically_reviewed"
    assert reviewed["score"] == 0  # These adult labels have no eligible positive primary family.

    _with_contexts_pending(monkeypatch, cid)
    pending = score_evidence(p)
    assert pending["metadata"]["evidence_assessment"]["native_context_review"]["status"] == "pending_clinical_review"
    assert pending["score"] == reviewed["score"]
    assert pending["metadata"]["evidence_result_state"] == "native_research_review_incomplete"
    assert _evidence_confidence(p, {"dimensions": {"evidence": pending}},
        evidence_assessment={"readiness": "complete"}) == ("moderate", ["evidence_review_incomplete"])
    if cid == "STRAIN_LACTIS_HN019":
        assert reviewed["metadata"]["evidence_result_state"] == "evaluated_null"


def test_research_summary_includes_new_sources_without_lending_them_approval():
    from scoring_v4.modules.probiotic_evidence import score_evidence
    p = strain_product(clinical_id="STRAIN_ACIDOPHILUS_NCFM", name="Lactobacillus acidophilus NCFM")
    row = assessment(p)
    assert {"28082816", "19651563", "21436726"} <= set(row["source_pmids"])
    # The shared assessment inventories reviewed research but awards no points.
    # Actual scoring provenance is selected by the Evidence owner below.
    from probiotic_measurements import derived_context_evidence
    human = derived_context_evidence(studied_formulas._clinical_strain_registry()["STRAIN_ACIDOPHILUS_NCFM"])
    assert {human["pmid"], *human["additional_pmids"]} <= set(row["source_pmids"])
    assert row["scoring_source_pmids"] == []
    assert "21436726" not in row["scoring_source_pmids"] and "24717228" not in row["scoring_source_pmids"]
    evidence = score_evidence(p)
    assert evidence["score"] == 0  # the approved trials are null


def test_legacy_native_range_cannot_become_a_second_applicability_engine(registry):
    registry["STRAIN_LGG"].pop("study_contexts")
    registry["STRAIN_LGG"]["applicability"] = {
        "dose_unit": "CFU", "minimum_daily_dose": 1e9, "maximum_daily_dose": 2e10,
        "dosage_forms": ["capsule"], "target_population": "adult",
        "studied_population": "Synthetic adults", "supported_outcomes": ["digestive"],
        "source_pmids": ["synthetic-source"]}
    row = assessment(strain_product(dose=1e9))
    assert row["dose_applicable"] is False
    assert row["status"] == "strain_dose_reference_unreviewed"


def test_exact_formula_confidence_does_not_inherit_individual_review_gaps():
    from scoring_v4.modules.probiotic_evidence import score_evidence
    from scoring_v4.confidence import _evidence_confidence
    from test_studied_formula_assessment import seed_label
    p = seed_label()
    evidence = score_evidence(p)
    assert evidence["metadata"]["studied_formula_assessment"]["status"] == "assessed_studied_formula"
    # Independent members may have an unfinished native review while the
    # complete formula already has its own source-owned assessment.
    evidence["metadata"]["evidence_assessment"]["native_context_review"] = {
        "status": "pending_clinical_review", "context_ids": ["synthetic-member-review"]}
    _, reasons = _evidence_confidence(p, {"dimensions": {"evidence": evidence}},
        evidence_assessment={"readiness": "complete"})
    assert "evidence_review_incomplete" not in reasons


@pytest.mark.parametrize("field,value", [
    ("components", None), ("components", 5), ("components", [{"id": "STRAIN_LGG"}]),
    ("source_pmids", None),
])
def test_frozen_stamped_malformed_context_is_invalid_and_cannot_crash_scoring(registry, field, value):
    from scoring_v4.modules.probiotic_evidence import score_evidence
    row = registry["STRAIN_LGG"]["study_contexts"][0]
    row.update(context_schema_version="1.1.0", evidence_role="direct_rct",
               component_registration_status="fully_registered")
    row["dose"].update(dose_status="verified", dose_basis="per_strain_daily",
                       duration_basis="fixed_protocol",
                       source_provenance={"pmid": "synthetic-source", "location": "abstract"})
    row[field] = value
    assert studied_formulas.valid_native_study_context(row, "STRAIN_LGG") is False
    result = assessment(strain_product(dose=1e9))
    assert result["study_contexts"][0]["status"] == "invalid_context"
    assert result["dose_applicable"] is False
    assert score_evidence(strain_product(dose=1e9))["score"] == 0
    from scoring_v4.modules.probiotic_dose import score_dose
    retained = score_dose(strain_product(dose=1e9))["metadata"]["evidence_assessment"]
    assert retained["strain_assessments"][0]["study_contexts"][0]["status"] == "invalid_context"


@pytest.mark.parametrize("value", [0, 1, "false", "no", "true"])
def test_scoring_eligible_must_be_a_boolean_on_every_context(registry, value):
    registry["STRAIN_LGG"]["study_contexts"][0]["scoring_eligible"] = value
    assert assessment(strain_product(dose=1e9))["study_contexts"][0]["status"] == "invalid_context"


def test_dose_comparison_wording_agrees_with_the_credited_class(registry):
    label = 1.07 * 1e9  # float rounding: not bit-identical to the tested arm below
    assert label != 1070000000
    registry["STRAIN_LGG"]["study_contexts"][0]["dose"]["values"] = [1070000000]
    result = assessment(strain_product(dose=label))["study_contexts"][0]
    assert result["dose_applicability_class"] == "EXACT_TESTED_DOSE"
    assert result["dose_comparison"] == "matches_tested_daily_dose"


@pytest.mark.parametrize("strain_id,context_id,pmid,values", [
    ("STRAIN_PLANTARUM_299V", "p299v_ibs_rome3_22912552", "22912552", [1e10]),
    ("STRAIN_INFANTIS_35624", "b35624_ibs_women_dose_ranging_16863564", "16863564", [1e6, 1e8, 1e10]),
])
def test_reviewed_ibs_source_regimens_preserve_discrete_arms(strain_id, context_id, pmid, values):
    entry = studied_formulas._clinical_strain_registry()[strain_id]
    ctx = next(c for c in entry["study_contexts"] if c["context_id"] == context_id)
    dose = ctx["dose"]
    assert dose["dose_status"] == "verified"
    assert dose["basis"] == "discrete_daily_arms"
    assert dose["values"] == values
    assert dose["administration_frequency"] == "once_daily"
    assert dose["duration_days"] == 28
    assert dose["dosage_forms"] == ["capsule"]
    assert dose["source_provenance"]["pmid"] == pmid
    assert dose["source_provenance"]["location"]
    assert ctx["condition"] == "irritable_bowel_syndrome"
    # Completing source extraction cannot invent a monotonic efficacy curve.
    assert entry["reference_semantics"]["curve"] == "completed_no_benchmark_neutral"
    if strain_id == "STRAIN_INFANTIS_35624":
        assert {o["direction"] for o in ctx["outcomes"]} == {"positive", "null"}
    else:
        assert next(o for o in ctx["outcomes"] if o["name"] == "abdominal_pain_frequency")["hierarchy"] == "primary"
        assert ctx["funding"] == "industry"
        assert "no 299v RCT is separately recorded" not in str(entry)


def test_specific_35624_clinical_lock_survives_source_extraction():
    entry = studied_formulas._clinical_strain_registry()["STRAIN_INFANTIS_35624"]
    assert "No positive IBS credit" in entry["cfu_thresholds"]["dr_pham_signoff_verification_note"]
    ctx = next(c for c in entry["study_contexts"]
               if c["context_id"] == "b35624_ibs_women_dose_ranging_16863564")
    assert pm.context_accepted_for_scoring(ctx) is False
    assert {o["direction"] for o in ctx["outcomes"]} == {"positive", "null"}


@pytest.mark.parametrize('case,expected', [
    ('broad_claim', 'not_applicable'), ('exact_condition', 'applicable'),
    # No claim is required (October 28 rulings); warnings and negations are not claims.
    ('no_claim', 'applicable'), ('warning_only', 'applicable'),
    ('negated_claim', 'applicable'), ('foreign_source', 'unresolved'),
    ('unsigned', 'unresolved'), ('unsupported_constraint', 'unresolved'),
])
def test_reviewed_native_claim_exclusion_is_source_bound_and_condition_specific(case, expected):
    from clinical_applicability import assess_native_claimed_purpose
    row = deepcopy(next(c for c in studied_formulas._clinical_strain_registry()[
        'STRAIN_PLANTARUM_299V']['study_contexts'] if c['source_pmids'] == ['22912552']))
    row['applicability'] = {'scope': 'ingredient', 'source_pmids': ['22912552'],
                            'excluded_claim_terms': ['digestive balance', 'digestive health']}
    product = {'product_name': 'Digestive health probiotic'}
    if case == 'exact_condition':
        product['product_name'] = 'Irritable bowel syndrome and digestive health'
    elif case == 'no_claim':
        product['product_name'] = 'Probiotic'
    elif case == 'warning_only':
        product = {'product_name': 'Probiotic', 'warnings': 'Digestive health'}
    elif case == 'negated_claim':
        product['product_name'] = 'Not for digestive health'
    elif case == 'foreign_source':
        row['applicability']['source_pmids'] = ['25194614']
    elif case == 'unsigned':
        row.pop('clinical_review')
    elif case == 'unsupported_constraint':
        row['applicability']['minimum_daily_dose'] = 1
        row['applicability']['dose_unit'] = 'mg'
    result = assess_native_claimed_purpose(product, row)
    assert result['status'] == expected
    if case == 'broad_claim':
        assert result['reason_code'] == 'label_purpose_evidence_mismatch'


def test_native_validator_rejects_unbound_or_unimplemented_applicability_fields():
    row = deepcopy(next(c for c in studied_formulas._clinical_strain_registry()[
        'STRAIN_PLANTARUM_299V']['study_contexts'] if c['source_pmids'] == ['22912552']))
    row['applicability'] = {'scope': 'ingredient', 'source_pmids': ['25194614'],
                            'excluded_claim_terms': ['digestive health']}
    assert not studied_formulas.valid_native_study_context(row, 'STRAIN_PLANTARUM_299V')


@pytest.mark.parametrize('case,complete', [('reviewed_exclusions', True), ('unscoped_sibling', False),
                                          ('pending_sibling', False), ('unsigned', False)])
def test_native_completed_zero_needs_every_used_scope_reviewed(monkeypatch, case, complete):
    from test_probiotic_applicability_rubric import strain_product
    from scoring_v4.modules.probiotic_evidence import score_evidence
    registry = deepcopy(studied_formulas._clinical_strain_registry())
    key = 'STRAIN_PLANTARUM_299V'
    contexts = [c for c in registry[key]['study_contexts']
                if c['source_pmids'] in (['22912552'], ['25194614'])]
    for c in contexts:
        c['applicability'] = {'scope': 'ingredient', 'source_pmids': c['source_pmids'],
                              'excluded_claim_terms': ['digestive health']}
    if case == 'unscoped_sibling':
        contexts[1].pop('applicability')
    elif case == 'pending_sibling':
        contexts[1]['review_status'] = 'source_verified_pending_clinical_review'
        contexts[1]['scoring_eligible'] = False
    elif case == 'unsigned':
        contexts[1].pop('clinical_review')
    registry[key]['study_contexts'] = contexts
    monkeypatch.setattr(studied_formulas, '_clinical_strain_registry', lambda: registry)
    product = strain_product(clinical_id=key, name='Lactobacillus plantarum 299v', dose=1e10)
    product['product_name'] = 'Digestive health probiotic'
    result = score_evidence(product)
    assert result['score'] == 0
    assert (result['metadata']['evidence_result_state'] == 'no_qualifying_human_evidence') is complete


def test_pending_source_bibliographies_do_not_claim_all_citations_are_included_trials():
    import json
    from pathlib import Path
    rows = json.loads((Path(__file__).parents[1] / 'data/backed_clinical_studies.json').read_text())['backed_clinical_studies']
    for rid, pmid in [('INGR_GLUCOSAMINE_SULFATE', '40005447'), ('INGR_L_THEANINE', '40314930')]:
        context = next(c for r in rows if r['id'] == rid for c in r['study_contexts'] if pmid in c['source_pmids'])
        # Actual source tables now establish publication membership. This
        # never turns every included intervention into this ingredient or an
        # independently approved cohort.
        assert context['included_study_pmids']
        assert all(pmid.isdigit() for pmid in context['included_study_pmids'])
        assert any('included-study' in note.lower() for note in context['limitations'])
        # Both contexts are now approved (Dr. Pham, 2026-10-28). Glucosamine is
        # a completed no-credit decision; L-theanine credits only the reviewed
        # pooled source, scoped to Focus & Mental Clarity. Neither approval
        # makes the bibliography's included trials independent credit.
        assert context['review_status'] == 'clinician_approved'
        record = next(r for r in rows if r['id'] == rid)
        if rid == 'INGR_GLUCOSAMINE_SULFATE':
            assert context['scoring_eligible'] is False
            assert record['study_type'] == 'reference'
            assert '11789591' in context['included_study_pmids']
            assert any('SKI306X' in note and 'must not' in note for note in context['limitations'])
        else:
            assert context['scoring_eligible'] is True
            assert record['applicability']['source_pmids'] == [pmid]
            assert record['applicability']['supported_outcomes'] == ['Focus & Mental Clarity']
            assert not set(context['included_study_pmids']) & set(record['applicability']['source_pmids'])
            assert '33260552' in context['included_study_pmids']
            assert any('tea' in note.lower() and 'isolated' in note.lower() for note in context['limitations'])


def test_pending_bibliography_sentinel_is_not_expanded_into_invented_pmids():
    import json
    from pathlib import Path
    rows = json.loads((Path(__file__).parents[1] / 'data/backed_clinical_studies.json').read_text())['backed_clinical_studies']
    for record in rows:
        for context in record.get('study_contexts', []):
            for limitation in context.get('limitations', []):
                assert 'e, x, t, r, a, c, t, i, o, n' not in limitation
