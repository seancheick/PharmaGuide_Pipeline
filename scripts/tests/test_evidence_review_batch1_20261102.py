"""First Evidence review batch: reviews stay source-bound, earn no credit and close only what the owners allow."""
import importlib.util
import json
import logging
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "audits" / "evidence_review_batch1_20261102"
DATA = ROOT / "data" / "literature_evidence_records.json"


@pytest.fixture(scope="module")
def records():
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    return {r["canonical_id"]: r for r in payload["literature_evidence_records"]}


@pytest.fixture(scope="module")
def spec():
    loaded = importlib.util.spec_from_file_location("evidence_review_spec", AUDIT / "spec.py")
    module = importlib.util.module_from_spec(loaded)
    loaded.loader.exec_module(module)
    return module.RECORDS


@pytest.fixture(scope="module")
def receipts():
    return json.loads((AUDIT / "receipts.json").read_text(encoding="utf-8"))


def _resolve_label_row(cid, name):
    from evidence_resolver import resolve_evidence_for_row
    logging.disable(logging.WARNING)
    row = {"canonical_id": cid, "name": name, "raw_source_text": name, "source_label_name": name,
           "raw_source_path": "activeIngredients[0]", "source_section": "activeIngredients"}
    return resolve_evidence_for_row(row, {"activeIngredients": [row], "ingredients_scorable": [row]})


def test_reviewed_null_closes_the_question_without_credit():
    resolution = _resolve_label_row("methionine", "L-Methionine")
    assert resolution.disposition == "reviewed_null_unfavorable"
    assert resolution.reason_code == "literature_reviewed_null_or_unfavorable"
    assert resolution.points_eligible is False
    assert not resolution.blocking_reasons
    assert _review_state(resolution) == "evaluated_limited_or_negative"


def _review_state(resolution):
    from assessment_readiness import _resolved_evidence_assessment
    return _resolved_evidence_assessment(resolution)[0]


@pytest.mark.parametrize("cid, name", [
    ("turmeric", "Turmeric Root Extract"),
    ("turmeric", "Turmeric Rhizome Extract"),
    ("ginkgo", "Ginkgo Flavone Glycosides"),
    ("ginkgo", "Ginkgo Biloba Extract Powder (24% Flavone Glycosides)"),
    ("ginkgo", "EGb 761 Ginkgo extract powder"),
    ("collagen", "Collagen, Hydrolyzed"),
])
def test_documented_review_finishes_a_declared_preparation_at_no_credit(cid, name):
    resolution = _resolve_label_row(cid, name)
    # These records state no effect direction and say a declared preparation finishes.
    assert resolution.owner_facts["literature_evidence"]["effect_direction"] is None
    assert resolution.disposition == "resolved_by_reviewed_clinical_evidence"
    assert resolution.applicability_status == "applicable_reviewed_trials"
    assert resolution.points_eligible is False
    assert resolution.reason_code == "literature_reviewed_human_clinical_evidence"
    assert _review_state(resolution) == "evaluated_limited_or_negative"


@pytest.mark.parametrize("cid, name", [
    ("lactase", "Lactase"),
    ("mct_oil", "MCT Oil"),
])
def test_documented_positive_review_waits_for_its_scoring_path(cid, name):
    resolution = _resolve_label_row(cid, name)
    # The source review remains positive and applicable; its unimplemented
    # credit path cannot become a completed limited/negative assessment.
    assert str(resolution.owner_facts["literature_evidence"]["effect_direction"]).startswith("positive_")
    assert resolution.disposition == "resolved_by_reviewed_clinical_evidence"
    assert resolution.applicability_status == "applicable_reviewed_trials"
    assert resolution.points_eligible is False
    assert resolution.reason_code == "literature_reviewed_human_clinical_evidence"
    assert _review_state(resolution) == "not_yet_evaluated"


@pytest.mark.parametrize("cid, name", [
    ("maitake", "Maitake"),
])
def test_a_finished_mixed_review_stays_closed(cid, name):
    resolution = _resolve_label_row(cid, name)
    assert resolution.owner_facts["literature_evidence"]["effect_direction"] == "mixed"
    assert resolution.reason_code == "literature_reviewed_human_clinical_evidence"
    assert resolution.points_eligible is False
    assert _review_state(resolution) == "evaluated_limited_or_negative"


@pytest.mark.parametrize("cid, name", [
    ("turmeric", "Turmeric Root Powder"),
    ("turmeric", "Turmeric Root 4:1 Extract"),
    ("ginkgo", "Ginkgo Biloba, Powder"),
    ("collagen", "BioCell Collagen Hydrolyzed Collagen Complex"),
    ("collagen", "Undenatured Type II Collagen"),
])
def test_declared_preparation_outside_the_review_is_a_conclusion(cid, name):
    resolution = _resolve_label_row(cid, name)
    assert resolution.reason_code == "clinical_form_excluded"
    assert resolution.points_eligible is False
    assert _review_state(resolution) == "evaluated_limited_or_negative"


UNDECLARED_PREPARATIONS = [
    ("turmeric", "Turmeric"),
    ("turmeric", "Organic Turmeric"),
    ("ginkgo", "Ginkgo Biloba Leaf Extract"),
    ("ginkgo", "Ginkgo Biloba"),
    ("collagen", "Collagen"),
    ("collagen", "Gelatin"),
]


@pytest.mark.parametrize("cid, name", UNDECLARED_PREPARATIONS)
def test_undeclared_preparation_finishes_on_the_attested_no_credit_conclusion(cid, name):
    """ADR-0007 rule 3: every preparation this review covers ends at no credit, and the
    record attests that, so an unnamed preparation finishes at zero instead of waiting."""
    resolution = _resolve_label_row(cid, name)
    assert resolution.reason_code == "clinical_source_label_unresolved"
    assert resolution.points_eligible is False
    assert not resolution.blocking_reasons
    assert resolution.owner_facts["literature_evidence"]["preparation_uncertainty_reviewed"] is True
    assert _review_state(resolution) == "evaluated_limited_or_negative"


@pytest.mark.parametrize("attestation", ["absent", "true", 1, False])
@pytest.mark.parametrize("cid, name", UNDECLARED_PREPARATIONS)
def test_undeclared_preparation_stays_open_without_a_valid_attestation(monkeypatch, cid, name, attestation):
    """An unresolved preparation match cannot be renamed a finished non-applicability."""
    import copy
    import evidence_resolver
    records = copy.deepcopy(evidence_resolver._load_literature_evidence())
    scope = records[cid]["documented_review_scope"]
    scope.pop("preparation_uncertainty_reviewed", None)
    if attestation != "absent":
        scope["preparation_uncertainty_reviewed"] = attestation
    monkeypatch.setattr(evidence_resolver, "_load_literature_evidence", lambda: records)
    resolution = _resolve_label_row(cid, name)
    assert resolution.reason_code == "literature_applicability_unestablished"
    assert resolution.points_eligible is False
    assert resolution.blocking_reasons
    assert _review_state(resolution) == "not_yet_evaluated"


def test_positive_sprout_review_is_not_attested_and_stays_open(records):
    """A sprout beverage could earn credit, so an unnamed broccoli preparation is undecided."""
    assert "preparation_uncertainty_reviewed" not in records["broccoli"]["documented_review_scope"]
    resolution = _resolve_label_row("broccoli", "Broccoli")
    assert resolution.blocking_reasons
    assert _review_state(resolution) == "not_yet_evaluated"


def test_finished_collagen_literature_cannot_grant_held_clinical_credit():
    resolution = _resolve_label_row("collagen", "Hydrolyzed Collagen")
    assert resolution.reason_code == "literature_reviewed_human_clinical_evidence"
    assert resolution.points_eligible is False
    assert _review_state(resolution) == "evaluated_limited_or_negative"


def test_documented_scope_needs_a_source_this_review_read(records):
    """Citing a paper outside the record's verified studies leaves the row open."""
    from clinical_applicability import assess_clinical_applicability
    record = records["turmeric"]
    scope = {**record["documented_review_scope"], "source_pmids": ["1"]}
    row = {"canonical_id": "turmeric", "name": "Turmeric Root Extract", "raw_source_text": "Turmeric Root Extract",
           "source_label_name": "Turmeric Root Extract", "raw_source_path": "activeIngredients[0]",
           "source_section": "activeIngredients"}
    decision = assess_clinical_applicability(
        {"activeIngredients": [row], "ingredients_scorable": [row]},
        {**record, "documented_review_scope": scope, "applicability": scope, "ingredient": row["name"],
         "matched_canonical_ids": ["turmeric"], "matched_source_row_refs": [row["raw_source_path"]]},
        assess_amount=False)
    assert decision["reason_code"] == "invalid_applicability_contract"


def test_documented_scope_does_not_reach_the_signed_scope_key(records):
    """Dose reads ``applicability``, so an Evidence review's scope stays out of it."""
    for cid in ("turmeric", "ginkgo", "collagen"):
        assert "applicability" not in records[cid]
        assert records[cid]["documented_review_scope"]["source_pmids"]


def test_no_agent_review_is_recorded_as_a_clinician(records):
    for cid in ("turmeric", "ginkgo", "methionine", "collagen"):
        blob = json.dumps(records[cid]).lower()
        assert "clinician_approved" not in blob
        assert "dr. pham" not in blob and "dr pham" not in blob


def test_fiber_review_stays_out_of_the_data():
    """Applied, it would finish 59635, 241707 and 276704 through a fiber row nobody signed."""
    resolution = _resolve_label_row("fiber", "Dietary Fiber")
    assert resolution.disposition == "literature_resolution_required"
    assert resolution.reason_code == "unverified_generated_record_cannot_complete_evidence"


@pytest.mark.parametrize("cid, name, reason", [
    # The L-carnitine base record finished as reference-only on 2026-11-11, but a
    # canonical query has no printed salt, so the Carnipure tartrate source stays open.
    ("l_carnitine", "L-Carnitine", "clinical_source_row_unresolved"),
    # Finished source transfer still requires a physical retail row.
    ("phytosterols", "Plant Sterols", "clinical_source_row_unresolved"),
])
def test_canonical_queries_without_qualifying_source_rows_stay_held(cid, name, reason):
    from evidence_resolver import resolve_evidence_for_canonical
    logging.disable(logging.WARNING)
    resolution = resolve_evidence_for_canonical(cid, name=name)
    assert resolution.reason_code == reason
    assert resolution.points_eligible is False
    assert resolution.blocking_reasons
    assert _review_state(resolution) == "not_yet_evaluated"


@pytest.mark.parametrize("cid, name, reason, state, points", [
    # Finished by the 2026-11-10 four-group batch (independently checked source reviews):
    # grape seed finishes without credit; taurine qualifies its adult blood-pressure
    # context only.
    ("grape_seed_extract", "Grape Seed Extract", "reference_only_clinical_record",
     "evaluated_limited_or_negative", False),
    ("taurine", "Taurine", "reviewed_human_clinical_evidence_matched", "evaluated_supported", True),
    # Finished as reference-only on 2026-11-11 (Sean's request; supersedes the hold kept
    # in 13179d11b): no credit.
    ("elderberry", "Elderberry", "reference_only_clinical_record", "evaluated_limited_or_negative", False),
])
def test_four_group_batch_finished_source_reviews(cid, name, reason, state, points):
    from evidence_resolver import resolve_evidence_for_canonical
    logging.disable(logging.WARNING)
    resolution = resolve_evidence_for_canonical(cid, name=name)
    assert resolution.reason_code == reason
    assert resolution.points_eligible is points
    assert not resolution.blocking_reasons
    assert _review_state(resolution) == state


def test_source_qualified_tmg_supersedes_the_older_unfinished_literature_review():
    from clinical_applicability import reviewed_entries
    from evidence_resolver import resolve_evidence_for_canonical

    record = reviewed_entries()["PRECLIN_BETAINE_ANHYDROUS"]
    source = next(c for c in record["study_contexts"] if c["source_pmids"] == ["39514262"])
    assert source["scoring_eligible"] is True
    assert record["effect_direction"] == "positive_weak"
    assert record["effect_direction_confidence"] == "low"
    resolution = resolve_evidence_for_canonical("tmg_betaine", name="Betaine Anhydrous")
    assert resolution.reason_code == "reviewed_human_clinical_evidence_matched"
    assert resolution.points_eligible is True
    assert _review_state(resolution) == "evaluated_supported"


@pytest.mark.parametrize("cid, pmid", [("ginkgo", "19017911"), ("collagen", "31919527")])
def test_paper_with_an_unread_correction_stays_retired(records, cid, pmid):
    assert pmid not in {study["pmid"] for study in records[cid]["qualifying_human_studies"]}
    assert pmid not in records[cid]["applicability_decision"]
    assert pmid in records[cid]["notes"]
    if cid == "collagen":
        assert "33301004" in records[cid]["notes"]
        assert "no changed study methods, outcomes or effect estimates" in records[cid]["notes"]
        assert "remains outside qualifying_human_studies" in records[cid]["notes"]
    else:
        assert "retired from qualifying_human_studies" in records[cid]["notes"]


def test_no_review_claims_clinician_approval_or_credit(records, spec):
    for cid in spec:
        text = json.dumps(records[cid]).lower()
        assert "clinician_approved" not in text and "dr. pham" not in text, cid
        assert "scoring_eligible" not in text, cid
        provenance = records[cid]["verification_provenance"]
        assert "scripts/api_audit" not in provenance["verified_by"], cid
        assert "no clinician approval" in provenance["verified_by"], cid
        assert "no evidence credit" in records[cid]["applicability_decision"].lower(), cid


def test_every_study_is_the_read_paper_and_says_what_was_read(records, spec, receipts):
    for cid, entry in spec.items():
        stored = {s["pmid"]: s for s in records[cid]["qualifying_human_studies"]}
        assert set(stored) == {s["pmid"] for s in entry["studies"]}, cid
        for study in entry["studies"]:
            receipt = receipts["articles"][study["pmid"]]
            saved = stored[study["pmid"]]
            assert saved["title"] == receipt["title"]
            assert saved["verification_provenance"]["authoritative_live_title"] == receipt["title"]
            assert saved["verification_provenance"]["abstract_evidence_quote"] == study["quote"]
            assert study["quote"] in receipt["quotes"], study["pmid"]
            assert receipt["human_mesh"] is True and receipt["retracted"] is False
            assert len(study["quote"].split()) < 15


def test_search_counts_match_the_retained_searches(records, spec, receipts):
    for cid in spec:
        assert records[cid]["records_screened"] == receipts["searches"][cid]["records_screened"]
        assert records[cid]["search_query"] == receipts["searches"][cid]["search_query"]


def test_turmeric_keeps_its_dose_reference(records):
    semantics = records["turmeric"]["reference_semantics"]
    assert semantics["curve"] == "completed_no_benchmark_neutral"
    assert semantics["source_ids"] == ["PMID:38576215", "PMID:38945354", "PMID:40615851"]
    assert records["turmeric"]["verification_provenance"]["reference_citations"]["is_complete"] is True


@pytest.mark.parametrize("cid, name", UNDECLARED_PREPARATIONS)
def test_attested_literature_cannot_close_a_row_with_a_held_backed_source(monkeypatch, cid, name):
    """A held clinical source outside the literature review is an unresolved fact, not a zero."""
    import evidence_resolver
    held = {"id": "TEST_HELD_UNREVIEWED_SOURCE", "ingredient": name, "canonical_id": cid,
            "standard_name": name, "study_type": "rct_single", "evidence_level": "ingredient-human",
            "effect_direction": "positive_weak", "scoring_eligible": False,
            "references_structured": [{"pmid": "99999999", "scoring_eligible": False}]}
    index = {key: list(studies) for key, studies in evidence_resolver._backed_studies_index().items()}
    for key in {cid, name.lower(), cid.replace("_", " ")}:
        index.setdefault(key, []).append(held)
    monkeypatch.setattr(evidence_resolver, "_backed_studies_index", lambda: index)
    resolution = _resolve_label_row(cid, name)
    assert resolution.points_eligible is False
    assert resolution.blocking_reasons
    assert "preparation_uncertainty_reviewed" not in (resolution.owner_facts.get("literature_evidence") or {})
    assert _review_state(resolution) == "not_yet_evaluated"
