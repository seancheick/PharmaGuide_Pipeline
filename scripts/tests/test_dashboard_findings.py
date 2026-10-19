"""Dashboard findings, run comparison and triage. Hermetic fixtures, CI-safe.

Each rule has a positive case; the shared clean control proves its negative. Audit
states (Evidence 0 reviewed-null, Dose neutral, Verification neutral) must never
become findings.
"""

from __future__ import annotations

import copy
import json
from datetime import date

import pandas as pd
import pytest

from dashboard_index_fixtures import scored_product, write_batch, write_release
from scripts.dashboard import findings_rules as fr
from scripts.dashboard import run_compare, triage
from scripts.dashboard import score_index as si


def _set_pillar(product: dict, pillar: str, score: float) -> dict:
    """Move one pillar to ``score`` with a consistent receipt and total (components untouched)."""
    product = copy.deepcopy(product)
    p = product["quality_pillars_v4"][pillar]
    delta = score - p["score"]
    p["score"] = score
    p["receipt"]["entries"].append({"id": "rounding", "kind": "rounding", "source": "x", "points": delta})
    p["receipt"]["unawarded"] = round(p["receipt"]["unawarded"] - delta, 4)
    product["quality_score_v4_100"] = round(product["quality_score_v4_100"] + delta, 1)
    return product


def _findings(paths) -> pd.DataFrame:
    return si.IndexReader(paths).findings()


def _rules_for(findings: pd.DataFrame, pid: str, plane: str = "candidate") -> set[str]:
    sub = findings[(findings["dsld_id"] == pid) & (findings["plane"] == plane)]
    return set(sub["rule_id"])


@pytest.fixture
def paths(tmp_path):
    return si.default_paths(tmp_path / "products", tmp_path / "dist", tmp_path / "cache")


def test_product_rules_fire_on_defects_and_not_on_audit_states(paths):
    clean = scored_product("ok")
    audit_states = [
        scored_product("ev0", evidence_score=0.0, evidence_state="evaluated_null"),
        scored_product("neutral", dose_neutral=True, verification_neutral=True),
        scored_product("floor", deduction=4.0, floor=True),
        scored_product("partial", assessment="partial"),
    ]
    mismatch = scored_product("mismatch", mismatch=0.5)
    no_receipt = scored_product("noreceipt")
    del no_receipt["quality_pillars_v4"]["dose"]["receipt"]
    negative = scored_product("neg")
    negative["quality_pillars_v4"]["dose"]["receipt"]["unawarded"] = -1.0
    realized = scored_product("realized")
    realized["quality_pillars_v4"]["formulation"]["receipt"].update(nominal_deductions=-1.0, realized_deductions=-3.0)
    range_ = scored_product("range")
    range_["quality_pillars_v4"]["safety_hygiene"]["score"] = 12.0
    range_["quality_pillars_v4"]["safety_hygiene"]["receipt"]["entries"][0]["points"] = 12.0
    range_["quality_score_v4_100"] += 2.0
    visible = scored_product("visible", status="not_scored", assessment="partial")
    visible.update(quality_score_v4_100=50.0, quality_tier="Poor")
    no_reason = scored_product("noreason", status="suppressed_safety", safety="blocked")
    no_reason.update(blocking_reason=None, quality_score_suppressed_reason=None)
    no_config = scored_product("noconfig")
    no_config["_v4_config_fingerprint"] = None
    wrong_pillar = scored_product("wrongpillar", extra_receipt=[
        ("formulation", {"id": "B5_proprietary_blend_opacity", "kind": "deduction", "source": "x", "points": 0.0})])
    two_caps = scored_product("twocaps", extra_receipt=[
        ("dose", {"id": "dose_safety_ceiling", "kind": "cap", "source": "x", "points": 0.0}),
        ("dose", {"id": "dose_safety_ceiling", "kind": "cap", "source": "x", "points": 0.0})])
    gap = scored_product("gap", evidence_state="applicability_unestablished")
    gap["quality_pillars_v4"]["evidence"]["display_state"] = "assessed"
    write_batch(paths.scan_dir, "A", [clean, *audit_states, mismatch, no_receipt, negative, realized, range_,
                                      visible, no_reason, no_config, wrong_pillar, two_caps, gap])
    si.refresh(paths)
    findings = _findings(paths)
    expected = {
        "mismatch": {"receipt_reconcile", "pillar_sum"},
        "noreceipt": {"scored_pillar_without_receipt"},
        "neg": {"negative_unawarded"},
        "realized": {"realized_exceeds_nominal"},
        "range": {"score_out_of_range"},
        "visible": {"unscored_has_score"},
        "noreason": {"blocked_without_reason"},
        "noconfig": {"config_fingerprint_missing"},
        "wrongpillar": {"penalty_wrong_pillar"},
        "twocaps": {"dose_ceiling_repeated"},
        "gap": {"evidence_gap_shown_assessed"},
    }
    for pid, rules in expected.items():
        assert rules <= _rules_for(findings, pid), (pid, _rules_for(findings, pid))
    for pid in ("ok", "ev0", "neutral", "floor", "partial"):
        assert _rules_for(findings, pid) == set(), (pid, _rules_for(findings, pid))
    assert findings["finding_id"].is_unique
    assert set(findings["rule_version"]) == {1}


def test_release_copy_contradictions(paths):
    ev = scored_product("ev", evidence_score=0.0, evidence_state="evaluated_null")
    ev["v4_score_explanation"] = {"strengths": [{"pillar": "evidence", "reason": "Strong research."}], "drags": []}
    ver = scored_product("ver", verification_neutral=True)
    ver["v4_score_explanation"] = {"strengths": [{"pillar": "verification", "reason": "Independently verified."}]}
    dose = scored_product("dose", dose_neutral=True)
    dose["v4_score_explanation"] = {"strengths": [{"pillar": "dose", "reason": "Clinically dosed."}]}
    fine = scored_product("fine")
    fine["v4_score_explanation"] = {"strengths": [{"pillar": "evidence", "reason": "Some research."}]}
    write_batch(paths.scan_dir, "A", [scored_product("x")])
    write_release(paths.build_root, [ev, ver, dose, fine])
    si.refresh(paths)
    findings = _findings(paths)
    assert "evidence_strength_contradiction" in _rules_for(findings, "ev", "release")
    assert "verification_neutral_claimed" in _rules_for(findings, "ver", "release")
    assert "dose_neutral_strength" in _rules_for(findings, "dose", "release")
    assert _rules_for(findings, "fine", "release") == set()


def test_compare_rules_explained_vs_unexplained(paths):
    base = [scored_product("same"), scored_product("moved"), scored_product("safe_quiet"),
            scored_product("safe_signal")]
    write_batch(paths.scan_dir, "A", base)
    si.refresh(paths)
    after = [
        scored_product("same"),
        _set_pillar(scored_product("moved"), "dose", 9.0),            # pillar moved, no input changed
        scored_product("safe_quiet", safety="caution"),                 # status changed, nothing recorded
        scored_product("safe_signal", safety="caution", signals=["DOSE_OVER_UL_CAUTION"]),
        scored_product("added"),
    ]
    write_batch(paths.scan_dir, "A", after)  # same stage code / reference / config
    meta = si.refresh(paths)
    findings = _findings(paths)
    assert "unexplained_mover" in _rules_for(findings, "moved")
    assert "safety_change_unexplained" in _rules_for(findings, "safe_quiet")
    assert "safety_change_review" in _rules_for(findings, "safe_signal")
    assert "safety_change_unexplained" not in _rules_for(findings, "safe_signal")
    assert _rules_for(findings, "same") == set()

    reader = si.IndexReader(paths)
    deltas = run_compare.compare(lambda key, table, columns=None: reader.frame(key, table, columns),
                                 reader.run(reader.previous_candidate()), reader.run(meta["latest"]["candidate"]))
    rows = deltas.set_index("dsld_id")
    assert rows.loc["added", "presence"] == "added"
    assert rows.loc["moved", "delta"] == pytest.approx(-6.0)
    assert rows.loc["moved", "changed_pillars"] == ["dose"]
    assert json.loads(rows.loc["moved", "reason_codes"])[0]["causes"] == ["unattributed"]
    assert bool(rows.loc["moved", "explained"]) is False
    assert run_compare.summarize(deltas)["unexplained"] == 1


def test_run_level_cause_explains_movement(paths):
    write_batch(paths.scan_dir, "A", [scored_product("p")], stage_code="c1")
    si.refresh(paths)
    write_batch(paths.scan_dir, "A", [_set_pillar(scored_product("p"), "dose", 8.0)], stage_code="c2")
    si.refresh(paths)
    findings = _findings(paths)
    rules = _rules_for(findings, "p")
    assert "unexplained_mover" not in rules
    assert "tier_or_large_move" in rules  # explained, but ≥5 points: review by cause


def test_pillar_only_history_never_invents_causes():
    base = {"run_key": "b", "plane": "backfill", "fidelity": si.FIDELITY_PILLARS, "config_versions": ["1.20"]}
    cand = {"run_key": "c", "plane": "candidate", "fidelity": si.FIDELITY_FULL, "config_versions": ["1.29"]}
    frames = {
        ("b", "products"): pd.DataFrame([{**{c: None for c in run_compare._PRODUCT_COLUMNS}, "dsld_id": "1",
                                          "total": 50.0, "pillar_dose": 10.0, "receipt_entry_ids": []}]),
        ("c", "products"): pd.DataFrame([{**{c: None for c in run_compare._PRODUCT_COLUMNS}, "dsld_id": "1",
                                          "total": 55.0, "pillar_dose": 15.0, "receipt_entry_ids": ["x"]}]),
        ("c", "slim"): pd.DataFrame([{"dsld_id": "1", "slim_json": json.dumps({"pillars": {}, "dims": {}})}]),
    }
    deltas = run_compare.compare(lambda key, table, columns=None: frames[(key, table)], base, cand)
    row = deltas.iloc[0]
    assert row["reason_codes"] == "[]"
    assert row["cause_fidelity"] == "run_only" and "config" in row["run_causes"]


def test_calibration_rules():
    ctx = fr.Context({}, {}, {}, {}, {}, {}, {}, [], calibration=[
        {"path": "ok", "approval_status": "approved_sean", "source_ids": ["u"], "owner": "scripts/dashboard/findings_rules.py::owner_symbol_exists",
         "rationale": "r", "review_date": date.today().isoformat()},
        {"path": "prov", "approval_status": "provisional", "source_ids": [], "owner": "scripts/nope.py::x",
         "rationale": "", "review_date": "2020-01-01"},
    ], canaries=[], pillar_max={})
    incomplete = fr._calibration_incomplete(ctx).set_index("subject")
    assert list(incomplete.index) == ["prov"]
    assert "provisional" in incomplete.loc["prov", "current_value"] and "days old" in incomplete.loc["prov", "current_value"]
    assert list(fr._calibration_owner(ctx)["subject"]) == ["prov"]
    assert fr.calibration_records(), "the production config carries calibration records"


def test_canary_missing_and_psi():
    products = pd.DataFrame({"dsld_id": ["1"]})
    ctx = fr.Context({"candidate": products}, {}, {}, {}, {}, {}, {}, [], [], canaries=[{"dsld_id": "1"}, {"dsld_id": "2"}],
                     pillar_max={})
    assert list(fr._canary_missing(ctx)["dsld_id"]) == ["2"]
    same = pd.Series([1.0, 5.0, 10.0, 15.0] * 10)
    assert fr.psi(same, same) == pytest.approx(0.0, abs=1e-6)
    assert fr.psi(same, same + 8) > fr.PSI_LIMIT


def test_peer_outlier_needs_complete_cohort():
    rows = [{"dsld_id": str(i), "total": 60.0 + (i % 3), "category": "c", "quality_score_status": "scored",
             "quality_assessment_status": "complete"} for i in range(40)]
    rows.append({"dsld_id": "hi", "total": 100.0, "category": "c", "quality_score_status": "scored",
                 "quality_assessment_status": "complete"})
    small = [{**row, "category": "tiny"} for row in rows[:10]] + [{**rows[-1], "dsld_id": "hi2", "category": "tiny"}]
    ctx = fr.Context({"candidate": pd.DataFrame(rows + small)}, {}, {}, {}, {}, {}, {}, [], [], [], {})
    assert set(fr._peer_outlier(ctx)["dsld_id"]) == {"hi"}


def test_triage_scoping_and_resolution(tmp_path):
    db = tmp_path / "triage.sqlite"
    findings = pd.DataFrame([{"finding_id": "f1", "rule_id": "r", "rule_version": 2, "message": "m"},
                             {"finding_id": "f2", "rule_id": "r", "rule_version": 1, "message": "m"}])
    triage.set_status("f1", "r", 1, "Accepted exception", path=db)  # accepted under the old rule version
    triage.set_status("f2", "r", 1, "Accepted exception", config_scope="1.29.1", path=db)
    triage.set_status("f3", "r", 1, "Investigating", path=db)        # absent from the newest run
    merged = triage.merge(findings, config_versions=["1.29.1"], path=db).set_index("finding_id")
    assert merged.loc["f1", "triage_status"] == "Open"
    assert merged.loc["f2", "triage_status"] == "Accepted exception"
    assert merged.loc["f3", "triage_status"] == triage.RESOLVED_BY_RUN
    assert triage.merge(findings, config_versions=["1.30.0"], path=db).set_index("finding_id").loc["f2", "triage_status"] == "Open"
    triage.set_status("f2", "r", 1, "Accepted exception", review_by="2000-01-01", path=db)
    assert triage.merge(findings, config_versions=["1.29.1"], path=db).set_index("finding_id").loc["f2", "triage_status"] == "Open"
    with pytest.raises(ValueError):
        triage.set_status("f1", "r", 1, "Whatever", path=db)


def test_triage_survives_index_rebuild(paths, tmp_path, monkeypatch):
    monkeypatch.setenv("PG_DASHBOARD_REVIEW", str(tmp_path / "review"))
    write_batch(paths.scan_dir, "A", [scored_product("m", mismatch=0.5)])
    si.refresh(paths)
    finding = _findings(paths).iloc[0]
    triage.set_status(finding["finding_id"], finding["rule_id"], int(finding["rule_version"]), "Investigating")
    si.refresh(paths)
    si.gc(paths, keep=1)
    merged = triage.merge(_findings(paths), config_versions=[])
    assert "Investigating" in set(merged["triage_status"])


def test_first_and_last_seen_follow_run_chronology(paths):
    write_batch(paths.scan_dir, "A", [scored_product("m", mismatch=0.5)], stage_code="c1")
    si.refresh(paths)
    write_batch(paths.scan_dir, "A", [scored_product("m", mismatch=0.5), scored_product("n")], stage_code="c2")
    # second run is later in source time
    manifest = paths.scan_dir / "output_A_scored" / "scored" / ".stage_manifest.json"
    data = json.loads(manifest.read_text())
    data["generated_at"] = "2026-10-20T00:00:00Z"
    manifest.write_text(json.dumps(data))
    si.refresh(paths)
    reader = si.IndexReader(paths)
    seen = fr.with_seen(reader.findings(), reader.build, reader.runs())
    row = seen[(seen["rule_id"] == "receipt_reconcile")].iloc[0]
    assert row["first_seen"] == "2026-10-19T00:00:00Z" and row["last_seen"] == "2026-10-20T00:00:00Z"
