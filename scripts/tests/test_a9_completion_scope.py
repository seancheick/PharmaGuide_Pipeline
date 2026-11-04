"""A9: which open Evidence reviews can hold a product's assessment.

A finished review that found little is complete and low-evidence. A review never
performed stays recorded as unreviewed. It holds the product only when its row
could change the Evidence answer: the route's nutrient panel, a claim-named or
materially dosed owner, a member of such a blend, or the ingredient the title names. It
also holds while Dose rests on an amount the label hides. Other supporting rows don't
hold, and this is never a reason to relabel them as reviewed (Sean, November 3, 2026).

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


@pytest.mark.parametrize("label, open_row", [
    pytest.param("a9_title_subject_293389_raw.json", "elderberry", id="genus_sambucus"),
    pytest.param("a9_title_subject_251695_raw.json", "elderberry", id="genus_sambucus_with_vitamin_c_credit"),
    pytest.param("a9_title_subject_178674_raw.json", "fish_oil", id="source_fish"),
    pytest.param("a9_title_subject_221657_raw.json", "epa", id="class_omega"),
    pytest.param("a9_title_subject_243141_raw.json", "reishi", id="class_mushroom"),
    pytest.param("a9_title_subject_25921_raw.json", "maca", id="brand_reparagen"),
])
def test_an_unread_ingredient_the_title_names_holds_the_product(pipeline, label, open_row, monkeypatch):
    import assessment_readiness
    from scoring_v4.scored_artifact import build_scored_artifact

    enriched = _enrich(pipeline, label)
    held = build_scored_artifact(json.loads(json.dumps(enriched)))
    assert held["quality_assessment_status"] == "partial"
    assert "evidence_assessment_incomplete" in held["assessment_readiness"]["release_assessment"]["blockers"]
    assert open_row in {row["canonical_id"] for row in _unreviewed_rows(held)}

    # The title word decides completion alone: its role and points stay where they were.
    from evidence_resolver import evidence_required_canonicals
    assert open_row not in evidence_required_canonicals(
        enriched, module=held["_v4_module_breakdown"]["module"])
    original = assessment_readiness._title_names_an_open_row
    monkeypatch.setattr(assessment_readiness, "_title_names_an_open_row", lambda *_: False)
    # 178674 also hides its borage amount, which holds it on its own.
    monkeypatch.setattr(assessment_readiness, "_dose_rests_on_a_hidden_amount", lambda *_: False)
    unheld = build_scored_artifact(json.loads(json.dumps(enriched)))
    monkeypatch.setattr(assessment_readiness, "_title_names_an_open_row", original)
    assert unheld["quality_assessment_status"] == "complete"
    for field in ("quality_score_v4_100", "quality_tier", "quality_score_status", "product_safety_status",
                  "safety_assessment_status", "verdict"):
        assert held[field] == unheld[field]
    assert ({key: pillar["score"] for key, pillar in held["quality_pillars_v4"].items()}
            == {key: pillar["score"] for key, pillar in unheld["quality_pillars_v4"].items()})


@pytest.mark.parametrize("title, canonical, named", [
    ("Sambucus Nighttime Syrup", "elderberry", True),
    ("Omega Curcumin", "dha", True),
    ("Mushrooms + Immune", "chaga", True),
    # A subject word names only its own ingredients, and a role never reads it.
    ("Omega Curcumin", "curcumin", True),
    ("Sambucus Nighttime Syrup", "melatonin", False),
    ("Fish Collagen", "collagen", True),
    ("Fish Collagen", "reishi", False),
])
def test_a_subject_word_names_only_its_own_ingredient(title, canonical, named):
    from scoring_input_contract import _named_in_title

    row = {"canonical_id": canonical, "name": canonical}
    assert _named_in_title(row, title.lower(), subject_words=True) is named


@pytest.mark.parametrize("title, canonical", [
    ("sambucus nighttime syrup", "elderberry"), ("omega curcumin", "epa"), ("mushroom blend", "reishi"),
])
def test_a_role_doesnt_read_a_subject_word(title, canonical):
    from scoring_input_contract import _named_in_title

    assert _named_in_title({"canonical_id": canonical, "name": canonical}, title) is False


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


@pytest.mark.parametrize("label, open_row, hidden", [
    ("a9_hidden_amount_2219_raw.json", "l_phenylalanine", "creatine"),
    ("a9_hidden_amount_2221_raw.json", "tmg_betaine", "creatine"),
    ("a9_hidden_amount_25712_raw.json", "l_isoleucine", "bcaa"),
])
def test_an_unread_row_holds_while_a_hidden_amount_could_move_dose(pipeline, label, open_row, hidden, monkeypatch):
    import assessment_readiness
    from scoring_v4.scored_artifact import build_scored_artifact

    enriched = _enrich(pipeline, label)
    held = build_scored_artifact(json.loads(json.dumps(enriched)))
    assert held["quality_assessment_status"] == "partial"
    assert "evidence_assessment_incomplete" in held["assessment_readiness"]["release_assessment"]["blockers"]
    assert open_row in {row["canonical_id"] for row in _unreviewed_rows(held)}
    dose = held["_v4_module_breakdown"]["dimensions"]["dose"]["metadata"]["dose_contributions"]
    assert {"ingredient": hidden, "assessment": "hidden_amount_neutral"}.items() <= next(
        entry for entry in dose if entry["ingredient"] == hidden).items()

    # The hold is status alone: the hidden amount keeps its neutral Dose either way.
    monkeypatch.setattr(assessment_readiness, "_dose_rests_on_a_hidden_amount", lambda *_: False)
    unheld = build_scored_artifact(json.loads(json.dumps(enriched)))
    assert unheld["quality_assessment_status"] == "complete"
    for field in ("quality_score_v4_100", "quality_tier", "quality_score_status", "product_safety_status",
                  "safety_assessment_status", "verdict"):
        assert held[field] == unheld[field]
    assert ({key: pillar["score"] for key, pillar in held["quality_pillars_v4"].items()}
            == {key: pillar["score"] for key, pillar in unheld["quality_pillars_v4"].items()})


def test_every_row_read_keeps_a_hidden_amount_complete(pipeline):
    from scoring_v4.scored_artifact import build_scored_artifact

    # Neutral Dose on a finished label is the accepted policy, and this doesn't reopen it.
    scored = build_scored_artifact(_enrich(pipeline, "a9_hidden_amount_74586_raw.json"))
    labels = {entry["assessment"] for entry in scored["_v4_module_breakdown"]["dimensions"]["dose"]["metadata"]["dose_contributions"]}
    assert "hidden_amount_neutral" in labels
    assert not _unreviewed_rows(scored)
    assert scored["quality_assessment_status"] == "complete"


def test_a_missing_amount_with_no_benchmark_cant_hold_the_product(pipeline):
    from scoring_v4.scored_artifact import build_scored_artifact

    # Lemon prints no amount inside its 1 g blend. It adds no Dose line, and the
    # vinegar it sits beside has no benchmark an amount could be read against.
    scored = build_scored_artifact(_enrich(pipeline, "a9_hidden_amount_243303_raw.json"))
    dose = scored["_v4_module_breakdown"]["dimensions"]["dose"]["metadata"]
    assert "lemon" not in {entry["ingredient"] for entry in dose["dose_contributions"]}
    assert {item["metadata"]["benchmark"] for item in dose["specialized_purpose_assessments"]} == {"absent"}
    assert scored["quality_assessment_status"] == "complete"


@pytest.mark.parametrize("label, open_row", [
    pytest.param("a9_panel_primary_250328_raw.json", "elderberry", id="title_names_elderberry"),
    pytest.param("a9_panel_primary_49568_raw.json", "keratin", id="title_names_keratin"),
    pytest.param("a9_panel_primary_204802_raw.json", "fish_oil", id="title_names_omega3"),
])
def test_a_panel_label_holds_on_an_unread_ingredient_it_is_about(pipeline, label, open_row):
    from scoring_v4.scored_artifact import build_scored_artifact

    enriched = _enrich(pipeline, label)
    scored = build_scored_artifact(enriched)

    assert scored["_v4_module_breakdown"]["module"] in {"multi_or_prenatal", "b_complex"}
    assert open_row in {row["canonical_id"] for row in _unreviewed_rows(scored)}
    assert scored["quality_assessment_status"] == "partial"
    assert "evidence_assessment_incomplete" in scored["assessment_readiness"]["release_assessment"]["blockers"]


@pytest.mark.parametrize("label", ["a9_review_pending_312894_raw.json", "a9_review_pending_2505_raw.json"])
def test_an_unfinished_label_keeps_saying_the_review_is_pending(pipeline, label):
    from scoring_v4.quality_score import _EVIDENCE_ZERO_REASON
    from scoring_v4.scored_artifact import build_scored_artifact

    # Dropping the open row from scope can't turn an unfinished review into a finding.
    scored = build_scored_artifact(_enrich(pipeline, label))
    evidence = scored["quality_pillars_v4"]["evidence"]
    assert scored["quality_assessment_status"] == "partial"
    assert evidence["display_state"] == "not_yet_reviewed"
    assert evidence["reason"] == _EVIDENCE_ZERO_REASON["clinical_review_not_covered"]


def test_a_recorded_applicability_finding_stays_on_an_unfinished_label(pipeline):
    from scoring_v4.quality_score import _EVIDENCE_ZERO_REASON
    from scoring_v4.scored_artifact import build_scored_artifact

    # Nothing fell out of scope here. Splitting this sentence belongs to the Evidence work.
    scored = build_scored_artifact(_enrich(pipeline, "a9_review_pending_252468_raw.json"))
    evidence = scored["quality_pillars_v4"]["evidence"]
    assert scored["quality_assessment_status"] == "partial"
    assert evidence["display_state"] == "applicability_unestablished"
    assert evidence["reason"] == _EVIDENCE_ZERO_REASON["applicability_unestablished"]
