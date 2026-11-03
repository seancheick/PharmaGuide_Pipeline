"""A9: which open Evidence reviews can hold a product's assessment.

A finished review that found little is complete and low-evidence. A review never
performed stays recorded as unreviewed. It holds the product only when its row
could change the Evidence answer: the route's nutrient panel, a claim-named or
materially dosed owner, or a member of such a blend. Supporting rows don't hold, and
this is never a reason to relabel them as reviewed (Sean, November 3, 2026).

Every label here is a real DSLD label, measured on the code before this rule
(all read partial) and after it.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
EVIDENCE = ["evidence_assessment_incomplete"]

# Label, and the rows left open on it where the review was never performed.
COMPLETES = [
    pytest.param("a9_partial_full_evidence_328830_raw.json", True, id="multi_panel_read_addin_open"),
    pytest.param("a9_completion_180213_raw.json", True, id="multi_panel_read_addins_open"),
    pytest.param("a9_completion_2715_raw.json", True, id="sports_adjunct_by_materiality"),
    pytest.param("a9_completion_252445_raw.json", False, id="finished_review_outside_scope"),
    pytest.param("raw_bamboo_252349.json", False, id="finished_authority_no_credit"),
    pytest.param("a9_finished_authority_no_credit_216405_raw.json", False, id="finished_authority_silica"),
    pytest.param("a9_completion_256991_raw.json", True, id="multi_panel_finished_beetroot"),
]
HELD = [
    pytest.param("a9_completion_12147_raw.json", EVIDENCE, id="title_owner_lcarnitine"),
    pytest.param("a9_completion_12853_raw.json", EVIDENCE, id="title_owner_valerian"),
    pytest.param("a9_completion_1055_raw.json", EVIDENCE, id="retained_credit_owner_open"),
    pytest.param("a9_completion_293417_raw.json", EVIDENCE, id="elderberry_owner_retained_credit"),
    pytest.param("a9_completion_322514_raw.json", EVIDENCE, id="enzyme_owner_behind_product_row"),
    pytest.param("a9_completion_252753_raw.json", EVIDENCE, id="triphala_owner"),
    pytest.param("a9_completion_232321_raw.json", EVIDENCE, id="named_blend_member"),
    pytest.param("a9_completion_256990_raw.json", EVIDENCE, id="member_of_a_heavy_blend"),
    pytest.param("a9_completion_312441_raw.json", EVIDENCE, id="sports_whole_product_blend"),
    pytest.param("a9_evidence_identity_gap_307560_raw.json", EVIDENCE, id="evidence_identity_gap"),
    pytest.param("a9_omega_identity_gap_252496_raw.json", ["omega_evidence_assessment_incomplete"], id="omega"),
    pytest.param("probiotic_cfu_guarantee_12091_raw.json", ["probiotic_evidence_assessment_incomplete"], id="probiotic"),
]


@pytest.fixture(scope="module")
def pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


def _enrich(pipeline, label):
    normalizer, enricher = pipeline
    raw = json.loads((FIXTURES / label).read_text())
    return enricher.enrich_product(normalizer.normalize_product(raw))[0]


def _unreviewed_rows(scored):
    rows = scored["assessment_readiness"]["evidence"]["ingredient_assessments"]
    return [row for row in rows if row["state"] == "not_yet_evaluated"]


@pytest.mark.parametrize("label, open_rows", COMPLETES)
def test_a_review_that_cant_change_the_answer_doesnt_hold_the_product(pipeline, label, open_rows):
    from scoring_v4.scored_artifact import build_scored_artifact

    scored = build_scored_artifact(_enrich(pipeline, label))
    assert scored["quality_assessment_status"] == "complete"
    assert scored["assessment_readiness"]["release_assessment"]["blockers"] == []
    assert scored["quality_pillars_v4"]["evidence"]["display_state"] != "not_yet_reviewed"
    # Completing the product says nothing about rows nobody read, and neither does its copy.
    assert bool(_unreviewed_rows(scored)) is open_rows
    assert ("weren't individually reviewed" in scored["quality_pillars_v4"]["evidence"]["reason"]) is open_rows


@pytest.mark.parametrize("label, blockers", HELD)
def test_an_open_review_that_could_change_the_answer_still_holds(pipeline, label, blockers):
    from scoring_v4.scored_artifact import build_scored_artifact

    scored = build_scored_artifact(_enrich(pipeline, label))
    assert scored["quality_assessment_status"] == "partial"
    assert scored["assessment_readiness"]["release_assessment"]["blockers"] == blockers
    assert scored["quality_pillars_v4"]["evidence"]["display_state"] != "assessed"


def test_a_blend_member_completes_only_on_its_own_reviewed_decision(pipeline):
    from evidence_resolver import resolve_product_evidence
    from scoring_input_contract import score_eligible_identity_view
    from scoring_v4.scored_artifact import build_scored_artifact

    # 221423 prints whey isolate inside its protein blend, with no amount of its own.
    # The Evidence credit comes from whey's finished review, not an unread row.
    enriched = _enrich(pipeline, "a9_completion_221423_raw.json")
    scored = build_scored_artifact(enriched)
    assert scored["quality_assessment_status"] == "complete"
    assert _unreviewed_rows(scored) == []
    whey = next(row for row in scored["assessment_readiness"]["evidence"]["ingredient_assessments"]
                if row["canonical_id"] == "whey_protein")
    assert ".nestedRows[" in whey["source_row_ref"]
    assert whey["state"] == "evaluated_supported"
    resolutions = resolve_product_evidence(
        score_eligible_identity_view(enriched), owner_scoped=True, module="sports").resolutions
    assert {r.canonical_id: r.reason_code for r in resolutions}["whey_protein"] == (
        "reviewed_human_clinical_evidence_matched")
    evidence = scored["_v4_module_breakdown"]["dimensions"]["evidence"]["metadata"]
    assert any("WHEY" in str(entry) for entry in evidence["recovered_matches"])

    # 256990 is the control: unread members of its heavy blend keep it held, though
    # magnesium already earned credit.
    held = build_scored_artifact(_enrich(pipeline, "a9_completion_256990_raw.json"))
    assert held["quality_assessment_status"] == "partial"
    assert {"chamomile", "lemon_balm"} <= {row["canonical_id"] for row in _unreviewed_rows(held)}


def test_required_owners_are_the_ones_that_can_move_the_answer(pipeline):
    from evidence_resolver import evidence_owner_canonicals, evidence_required_canonicals

    elderberry = _enrich(pipeline, "a9_completion_293417_raw.json")
    assert evidence_owner_canonicals(elderberry, module="generic") >= {"elderberry", "vitamin_c", "zinc"}
    assert evidence_required_canonicals(elderberry, module="generic") == {"elderberry"}
    # With nothing material to point at, every owner stays required.
    valerian = _enrich(pipeline, "a9_completion_12853_raw.json")
    assert evidence_required_canonicals(valerian, module="generic") == {"valerian"}


@pytest.mark.parametrize("open_rows, refs, held", [
    ([{"canonical_id": "beta-alanine", "source_row_ref": "r0"}], ["r0"], True),
    ([{"canonical_id": "taurine", "source_row_ref": "r0"}], ["r0"], False),
    ([{"canonical_id": "taurine", "source_row_ref": "r0"}], ["r0", "r1"], True),
    ([], ["r0"], True),
    ([], [], True),
])
def test_only_a_required_or_unknown_open_row_holds(open_rows, refs, held, monkeypatch):
    import evidence_resolver
    from assessment_readiness import _required_evidence_review_open

    monkeypatch.setattr(evidence_resolver, "evidence_required_canonicals", lambda *a, **k: {"beta-alanine"})
    readiness = {"evidence": {"readiness": "incomplete", "ingredient_assessments": open_rows,
                              "not_yet_evaluated_row_refs": refs}}
    assert _required_evidence_review_open({}, readiness, "sports") is held
    # Outside the owner-scoped routes, every open row holds.
    assert _required_evidence_review_open({}, readiness, "other") is True


@pytest.mark.parametrize("label", ["a9_partial_full_evidence_328830_raw.json", "a9_completion_2715_raw.json",
                                   "a9_completion_12147_raw.json"])
def test_completion_moves_no_score_tier_or_safety_outcome(pipeline, label, monkeypatch):
    from scoring_v4.scored_artifact import build_scored_artifact
    import assessment_readiness

    enriched = _enrich(pipeline, label)
    scored = build_scored_artifact(enriched)
    owner = assessment_readiness.evaluate_release_assessment

    def held_on_evidence(*args, **kwargs):
        return {**owner(*args, **kwargs), "is_complete": False, "blockers": EVIDENCE}

    monkeypatch.setattr(assessment_readiness, "evaluate_release_assessment", held_on_evidence)
    held = build_scored_artifact(enriched)
    assert held["quality_assessment_status"] == "partial"
    for field in ("quality_score_v4_100", "quality_score_status", "quality_tier", "product_safety_status",
                  "safety_assessment_status", "verdict"):
        assert scored[field] == held[field], field
    assert ({name: pillar["score"] for name, pillar in scored["quality_pillars_v4"].items()
             if isinstance(pillar, dict) and "score" in pillar}
            == {name: pillar["score"] for name, pillar in held["quality_pillars_v4"].items()
                if isinstance(pillar, dict) and "score" in pillar})


@pytest.mark.parametrize("label, safety", [
    ("a9_partial_full_evidence_328830_raw.json", "complete"),
    ("a9_completion_12147_raw.json", "complete"),
    ("a9_evidence_identity_gap_307560_raw.json", "incomplete"),
    ("a9_omega_identity_gap_252496_raw.json", "incomplete"),
])
def test_quality_completion_and_the_safety_checks_stay_separate_facts(pipeline, label, safety):
    from scoring_v4.scored_artifact import build_scored_artifact

    assert build_scored_artifact(_enrich(pipeline, label))["safety_assessment_status"] == safety


def _with_evidence_blocker_lifted(monkeypatch):
    import assessment_readiness

    monkeypatch.setattr(assessment_readiness, "_required_evidence_review_open", lambda *a: False)
    monkeypatch.setattr(assessment_readiness, "_evidence_presents_as_unreviewed", lambda *a: False)


def test_a_label_hold_stands_while_its_evidence_review_is_open(pipeline, monkeypatch):
    from scoring_v4.scored_artifact import build_scored_artifact

    enriched = _enrich(pipeline, "raw_held_assessment_328831.json")
    _with_evidence_blocker_lifted(monkeypatch)
    scored = build_scored_artifact(enriched)
    assert scored["quality_score_status"] == "not_scored"
    assert scored["quality_score_v4_100"] is None
    assert set(scored["assessment_readiness"]["release_assessment"]["blockers"]) == {
        "dose_benchmark_identity_unresolved", "evidence_assessment_incomplete"}


def test_finishing_the_review_is_what_lifts_a_label_hold(pipeline, monkeypatch):
    from score_supplements_v4 import score_product_v4
    from scoring_v4.scored_artifact import assemble_scored_artifact

    enriched = _enrich(pipeline, "raw_held_assessment_328831.json")
    v4 = score_product_v4(enriched)
    for row in v4["v4_breakdown"]["assessment_readiness"]["evidence"]["ingredient_assessments"]:
        row["state"] = "evaluated_limited_or_negative"
    _with_evidence_blocker_lifted(monkeypatch)
    blockers = assemble_scored_artifact(enriched, v4)["assessment_readiness"]["release_assessment"]["blockers"]
    assert "evidence_assessment_incomplete" not in blockers


def test_a_finished_label_stays_complete(pipeline):
    from scoring_v4.scored_artifact import build_scored_artifact

    scored = build_scored_artifact(_enrich(pipeline, "form_association_12012_raw.json"))
    assert scored["quality_assessment_status"] == "complete"
    assert scored["assessment_readiness"]["release_assessment"]["blockers"] == []
