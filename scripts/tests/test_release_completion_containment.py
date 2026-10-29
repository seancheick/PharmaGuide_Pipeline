"""Release completion preserves existing export containment, without score amnesty."""
from __future__ import annotations

import pytest

import audit_source_of_truth_contract as audit
import build_final_db as builder
from scripts.tests.test_scoring_source_of_truth_audit import _args, _scored, _write


@pytest.fixture
def contained_pair(monkeypatch):
    scored = _scored(quality_score_status="not_scored", verdict="NOT_SCORED",
                     quality_score_v4_100=None, score_100_equivalent=None)
    scored["assessment_readiness"]["release_assessment"] = {
        "is_complete": False, "blockers": ["dose_assessment_incomplete"],
        "unfinished_source_assessment": None,
    }
    enriched = {"dsld_id": "P1", "product_name": "Known source label"}
    monkeypatch.setattr(audit, "_scoring_enriched_source", lambda *_: enriched)
    monkeypatch.setattr(builder, "validate_export_contract", lambda e, s: [])
    monkeypatch.setattr(audit, "verified_contract_quarantines", lambda _: {})
    monkeypatch.setattr(audit, "verified_warning_only_products",
                        lambda _, blocked_only=False: set() if blocked_only else {"P1"})
    return scored, enriched


@pytest.mark.parametrize("pid,blocker,blocked", [
    ("252358", "identity_assessment_incomplete", True),
    ("252426", "identity_assessment_incomplete", True),
    ("246324", "identity_assessment_incomplete", True),
    ("252767", "dose_assessment_incomplete", False),
    ("252769", "dose_assessment_incomplete", False),
])
def test_completion_preflight_defers_existing_warning_label_contract(
    tmp_path, monkeypatch, contained_pair, pid, blocker, blocked,
):
    scored, enriched = contained_pair
    scored["dsld_id"] = enriched["dsld_id"] = pid
    scored["assessment_readiness"]["release_assessment"]["blockers"] = [blocker]
    if blocked:
        scored.update(quality_score_status="suppressed_safety", verdict="BLOCKED")
    monkeypatch.setattr(audit, "is_confirmed_ban_or_recall", lambda _: blocked)
    path = tmp_path / "scored.json"
    _write(path, scored)
    args = _args(path)
    args.completion_only = True
    assert audit.audit_scoring(args) == []
    assert scored["assessment_readiness"]["release_assessment"]["is_complete"] is False


@pytest.mark.parametrize("proof", ["warning", "quarantine", "wrong_issue", "absent"])
def test_final_completion_requires_current_export_or_absence_proof(
    tmp_path, monkeypatch, contained_pair, proof,
):
    scored, _ = contained_pair
    issue = "review_queue: identity integrity ingredientRows[0]:unresolved_identity_conflict"
    if proof in {"quarantine", "wrong_issue"}:
        monkeypatch.setattr(builder, "validate_export_contract", lambda *_: [issue])
    monkeypatch.setattr(audit, "verified_warning_only_products",
                        lambda _, blocked_only=False: {"P1"} if proof == "warning" and not blocked_only else set())
    monkeypatch.setattr(audit, "verified_contract_quarantines",
                        lambda _: {"P1": (issue,)} if proof == "quarantine" else {"P1": ("review_queue: other defect",)} if proof == "wrong_issue" else {})
    path = tmp_path / "scored.json"
    _write(path, scored)
    args = _args(path)
    args.dist_dir = str(tmp_path)
    codes = {f.code for f in audit.audit_scoring(args)}
    assert ("SCORING_RELEASE_ASSESSMENT_INCOMPLETE" in codes) == (proof in {"absent", "wrong_issue"})


@pytest.mark.parametrize("defect", ["stale_lineage", "scored", "unsafe", "score_leak", "malformed", "hard_error"])
def test_completion_containment_never_amnesties_unqualified_candidate(
    tmp_path, monkeypatch, contained_pair, defect,
):
    scored, _ = contained_pair
    if defect == "stale_lineage":
        monkeypatch.setattr(audit, "_scoring_enriched_source", lambda *_: None)
    elif defect == "scored":
        scored["quality_score_status"] = "scored"
    elif defect == "unsafe":
        scored.update(quality_score_status="suppressed_safety", verdict="UNSAFE")
        monkeypatch.setattr(audit, "is_confirmed_ban_or_recall", lambda _: False)
    elif defect == "score_leak":
        scored["quality_score_v4_100"] = 60
    elif defect == "malformed":
        scored["assessment_readiness"]["release_assessment"]["blockers"] = [None]
    else:
        monkeypatch.setattr(builder, "validate_export_contract", lambda *_: ["missing scored.strict_scoring_contract"])
    path = tmp_path / "scored.json"
    _write(path, scored)
    args = _args(path)
    args.completion_only = True
    assert "SCORING_RELEASE_ASSESSMENT_INCOMPLETE" in {f.code for f in audit.audit_scoring(args)}


@pytest.fixture
def actual_source_pairs():
    """Portable source projections, retaining real safety/identity/NP facts."""
    import json
    from pathlib import Path

    path = Path(__file__).parent / "fixtures" / "release_completion_source_contracts.json"
    return json.loads(path.read_text())["products"]


@pytest.mark.parametrize("pid", ["252358", "252426", "252767", "246324"])
def test_real_source_contract_preserves_warning_label_without_claiming_completion(actual_source_pairs, pid):
    from audit_source_of_truth_contract import _release_assessment_export_contained

    pair = actual_source_pairs[pid]
    scored, enriched = pair["scored"], pair["enriched"]
    assert builder.validate_export_contract(enriched, scored) == []
    assert audit.is_confirmed_ban_or_recall(scored) == (pid != "252767")
    receipt = dict(scored["assessment_readiness"]["release_assessment"])
    proof = dict(warning_only=set(), blocked_warning_only=set(), quarantines={})
    assert _release_assessment_export_contained(scored, enriched, completion_only=True, **proof)
    assert not _release_assessment_export_contained(scored, enriched, completion_only=False, **proof)
    proof["warning_only"] = {pid}
    if pid != "252767":
        proof["blocked_warning_only"] = {pid}
    assert _release_assessment_export_contained(scored, enriched, completion_only=False, **proof)
    assert scored["assessment_readiness"]["release_assessment"] == receipt
    assert receipt["is_complete"] is False


@pytest.mark.parametrize("defect", ["score_leak", "missing_schema", "missing_label", "wrong_warning_kind"])
def test_real_source_containment_rejects_score_schema_or_provenance_regressions(actual_source_pairs, defect):
    from audit_source_of_truth_contract import _release_assessment_export_contained

    pid = "252767" if defect == "missing_label" else "252358"
    pair = actual_source_pairs[pid]
    scored, enriched = pair["scored"], pair["enriched"]
    if defect == "score_leak":
        scored["quality_score_v4_100"] = 60
    elif defect == "missing_schema":
        scored.pop("scoring_metadata")
    elif defect == "missing_label":
        enriched["display_ingredients"] = []
    proof = dict(warning_only={pid}, blocked_warning_only=set() if defect == "wrong_warning_kind" else {pid}, quarantines={})
    assert not _release_assessment_export_contained(scored, enriched, completion_only=False, **proof)


@pytest.mark.parametrize("pid", ["252358", "252426", "252767", "246324"])
def test_actual_source_completion_preflight_reaches_existing_export_policy(
    tmp_path, monkeypatch, actual_source_pairs, pid,
):
    pair = actual_source_pairs[pid]
    # Lineage has its independent manifest tests; this portable boundary test
    # supplies its real source projection and exercises the production builder.
    monkeypatch.setattr(audit, "_scoring_enriched_source", lambda *_: pair["enriched"])
    path = tmp_path / "scored.json"
    _write(path, pair["scored"])
    args = _args(path)
    args.completion_only = True
    assert audit.audit_scoring(args) == []
