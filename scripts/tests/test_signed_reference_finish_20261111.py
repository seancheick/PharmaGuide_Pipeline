"""Signed "does not score" records finish as reference-only (Sean, 2026-11-11; ADR-0007).

Receipts: scripts/audits/signed_reference_finish_20261111/research.md.
"""
import json
import logging
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "data" / "backed_clinical_studies.json"
FINISHED = ["INGR_ELDERBERRY", "INGR_L_CARNITINE", "INGR_VITAMIN_D3", "BRAND_ASTAREAL", "BRAND_TESTOFEN"]
TEXT_FIELDS = ("notes", "notable_studies", "effect_direction_rationale", "key_endpoints")
# Phrases from the superseded benefit readings; none may survive the rewrite.
OBSOLETE = ("↑", "↓", "promising", "positive_strong", "supports reduced acute respiratory",
            "explicit human evidence for skin", "randomized evidence for libido", "remains pending")


@pytest.fixture(scope="module")
def records():
    return {r["id"]: r for r in json.loads(DATA.read_text())["backed_clinical_studies"]}


@pytest.mark.parametrize("rid", FINISHED)
def test_signed_noncredit_record_is_finished_reference(records, rid):
    from clinical_applicability import assess_clinical_source_review
    from clinical_evidence_schema import is_reference_only
    rec = records[rid]
    assert is_reference_only(rec)
    assert rec["study_type"] == rec["evidence_level"] == "reference"
    assert rec["health_goals_supported"] == [] and rec["endpoint_relevance_tags"] == []
    assert all(c["scoring_eligible"] is False for c in rec["study_contexts"])
    assert assess_clinical_source_review({"id": rid})["is_complete"] is True
    assert "not clinician review" in rec["notes"]
    text = json.dumps([rec.get(f) for f in TEXT_FIELDS] + [c.get("limitations") for c in rec["study_contexts"]],
                      ensure_ascii=False)
    for phrase in OBSOLETE:
        assert phrase not in text, (rid, phrase)


def test_omega3_stays_held(records):
    from clinical_evidence_schema import is_reference_only
    assert not is_reference_only(records["INGR_OMEGA3"])


def test_vitamin_d3_record_drops_superseded_benefit_scope(records):
    rec = records["INGR_VITAMIN_D3"]
    assert "applicability" not in rec
    assert "39993397" in rec["notes"] and "OWNERSHIP" in rec["notes"]


@pytest.mark.parametrize("rid", FINISHED)
def test_every_declared_source_has_its_own_context(records, rid):
    # Reference-only skips the per-source coverage check, so guard this batch here.
    rec = records[rid]
    declared = {ref["pmid"] for ref in rec["references_structured"]}
    assert declared == {p for c in rec["study_contexts"] for p in c["source_pmids"]}


@pytest.mark.parametrize("name, canonical, form", [
    ("Elderberry", "elderberry", None),
    ("L-Carnitine", "l_carnitine", "l-carnitine base (free form)"),
    ("L-Carnitine Fumarate", "l_carnitine", "l-carnitine fumarate"),
    ("Acetyl L-Carnitine", "l_carnitine", "acetyl-l-carnitine (alcar)"),
])
def test_label_rows_finish_at_no_credit(name, canonical, form):
    from assessment_readiness import _resolved_evidence_assessment
    from evidence_resolver import resolve_evidence_for_row
    from test_evidence_resolver import _excluded_preparation_product
    logging.disable(logging.WARNING)
    row, product = _excluded_preparation_product(name, canonical, form)
    resolution = resolve_evidence_for_row(row, product)
    assert resolution.points_eligible is False
    assert resolution.blocking_reasons == []
    assert _resolved_evidence_assessment(resolution)[0] == "evaluated_limited_or_negative"


def test_generic_astaxanthin_stays_held_by_its_own_unfinished_record():
    # PRECLIN_ASTAXANTHIN_GENERIC has declared sources with no context; AstaREAL finishing
    # cannot close that separate review.
    from assessment_readiness import _resolved_evidence_assessment
    from evidence_resolver import resolve_evidence_for_row
    from test_evidence_resolver import _excluded_preparation_product
    logging.disable(logging.WARNING)
    for name in ("Astaxanthin", "AstaREAL Astaxanthin"):
        row, product = _excluded_preparation_product(name, "astaxanthin", None)
        resolution = resolve_evidence_for_row(row, product)
        assert resolution.blocking_reasons == ["clinical_sources_ineligible"]
        assert _resolved_evidence_assessment(resolution)[0] == "not_yet_evaluated"


@pytest.mark.parametrize("canonical, name, expected", [
    ("fish_oil", "Fish Oil", "not_yet_evaluated"),
    ("vitamin_d", "Vitamin D3", "evaluated_supported"),
])
def test_controls_keep_their_state(canonical, name, expected):
    from assessment_readiness import _resolved_evidence_assessment
    from evidence_resolver import resolve_evidence_for_canonical
    logging.disable(logging.WARNING)
    assert _resolved_evidence_assessment(resolve_evidence_for_canonical(canonical, name=name))[0] == expected


@pytest.mark.parametrize("label", [
    "a9_completion_293417_raw.json",
    "a9_title_subject_293389_raw.json",
    "a9_title_subject_251695_raw.json",
    "a9_panel_primary_250328_raw.json",
])
def test_real_elderberry_labels_finish_their_elderberry_row(label):
    # These fixtures pinned elderberry as unread before 2026-11-11.
    from test_a9_completion_scope import _enrich, _unreviewed_rows
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact
    logging.disable(logging.INFO)
    scored = build_scored_artifact(_enrich((EnhancedDSLDNormalizer(), SupplementEnricherV3()), label))
    rows = [r for r in scored["assessment_readiness"]["evidence"]["ingredient_assessments"]
            if r["canonical_id"] == "elderberry"]
    assert rows and all(r["state"] == "evaluated_limited_or_negative" for r in rows)
    assert "elderberry" not in {r["canonical_id"] for r in _unreviewed_rows(scored)}
