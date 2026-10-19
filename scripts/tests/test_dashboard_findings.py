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
    vzero = scored_product("vzero")
    vzero["quality_pillars_v4"]["verification"].update(score=0.0, receipt={"entries": [], "nominal_deductions": 0,
                                                                         "realized_deductions": 0, "unawarded": 15.0})
    vzero["quality_score_v4_100"] = round(vzero["quality_score_v4_100"] - 10.0, 1)
    gap = scored_product("gap", evidence_state="applicability_unestablished")
    gap["quality_pillars_v4"]["evidence"]["display_state"] = "assessed"
    write_batch(paths.scan_dir, "A", [clean, *audit_states, mismatch, no_receipt, negative, realized, range_,
                                      visible, no_reason, no_config, wrong_pillar, two_caps, gap, vzero])
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
        "vzero": {"verification_zero_unexplained"},
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
    severity = {(r.dsld_id, r.rule_id): r.severity for r in findings.itertuples()}
    assert severity[("safe_quiet", "safety_change_unexplained")] == "critical"
    assert severity[("safe_signal", "safety_change_review")] == "high"
    assert severity[("moved", "unexplained_mover")] == "critical"
    assert "safety_change_unexplained" not in _rules_for(findings, "safe_signal")
    assert _rules_for(findings, "same") == set()

    reader = si.IndexReader(paths)
    previous = next(r for r in reader.runs() if r["plane"] == "candidate" and r["run_key"] != meta["latest"]["candidate"])
    deltas = run_compare.compare(lambda key, table, columns=None: reader.frame(key, table, columns),
                                 previous, reader.run(meta["latest"]["candidate"]))
    rows = deltas.set_index("dsld_id")
    assert rows.loc["added", "presence"] == "added"
    assert rows.loc["moved", "delta"] == pytest.approx(-6.0)
    assert rows.loc["moved", "changed_pillars"] == ["dose"]
    assert json.loads(rows.loc["moved", "reason_codes"])[0]["causes"] == ["unattributed"]
    assert bool(rows.loc["moved", "explained"]) is False
    assert run_compare.summarize(deltas)["unexplained"] == 1


def test_run_change_never_silences_an_unattributed_mover(paths):
    """Between two full-receipt runs a code change is shown, but the mover stays flagged (high, not critical)."""
    write_batch(paths.scan_dir, "A", [scored_product("p")], stage_code="c1")
    si.refresh(paths)
    write_batch(paths.scan_dir, "A", [_set_pillar(scored_product("p"), "dose", 8.0)], stage_code="c2")
    si.refresh(paths)
    findings = _findings(paths)
    rules = _rules_for(findings, "p")
    assert "unexplained_mover" not in rules
    assert "unattributed_mover_under_run_change" in rules
    row = findings[findings["rule_id"] == "unattributed_mover_under_run_change"].iloc[0]
    assert row["severity"] == "high" and "stage_code" in row["current_value"]


def test_cross_plane_totals_compare_on_the_shipped_basis(paths):
    """A candidate 69.6 ships as 70: identical pillars against the release are not a movement."""
    product = _set_pillar(scored_product("r"), "transparency", 12.6)
    assert product["quality_score_v4_100"] == 69.6
    write_batch(paths.scan_dir, "A", [product])
    write_release(paths.build_root, [product])
    meta = si.refresh(paths)
    reader = si.IndexReader(paths)
    release = reader.frame(meta["latest"]["release"], "products").set_index("dsld_id")
    assert release.loc["r", "total"] == 70.0 and release.loc["r", "pillar_sum_mismatch"] == 0.0
    deltas = run_compare.compare(lambda key, table, columns=None: reader.frame(key, table, columns),
                                 reader.run(meta["latest"]["release"]), reader.run(meta["latest"]["candidate"]))
    row = deltas.set_index("dsld_id").loc["r"]
    assert row["delta"] == 0 and not row["moved"] and row["delta_basis"] == "shipped whole score"
    assert "plane" not in " ".join(row["run_causes"])


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


def test_release_side_and_distribution_rules(paths):
    low_route = scored_product("lowroute")
    low_route["route_confidence"] = "low"
    quiet = scored_product("relquiet", safety="caution")              # differs from release, nothing recorded
    signal = scored_product("relsignal", safety="caution", signals=["DOSE_OVER_UL_CAUTION"])
    write_batch(paths.scan_dir, "A", [low_route, quiet, signal])
    write_release(paths.build_root, [scored_product("lowroute"), scored_product("relquiet"), scored_product("relsignal")])
    si.refresh(paths)
    findings = _findings(paths)
    severity = {(r.dsld_id, r.rule_id): r.severity for r in findings.itertuples()}
    assert severity[("lowroute", "low_route_confidence_ranked")] == "medium"
    assert severity[("relquiet", "safety_change_unexplained_vs_release")] == "critical"
    assert severity[("relsignal", "safety_change_review_vs_release")] == "high"
    assert ("relsignal", "safety_change_unexplained_vs_release") not in severity


def test_pillar_drift_rule_fires_only_above_the_limit():
    ctx = fr.Context({}, {}, {}, {}, {}, {}, {}, [{"pillar": "dose", "base": "release", "cand": "candidate", "psi": 0.3},
                                               {"pillar": "evidence", "base": "release", "cand": "candidate", "psi": 0.1}],
                     [], {})
    hits = fr._pillar_drift(ctx)
    assert list(hits["pillar"]) == ["dose"]


def test_absorption_view_ignores_rounding_residue():
    from scripts.dashboard import saved_views as sv

    frame = pd.DataFrame({"dsld_id": ["noise", "floor"], "absorbed_points": [0.05, 3.0], "has_floor": [False, True]})
    assert list(sv.apply_filters(frame, sv.SAVED_VIEWS["Floors absorbing deductions"])["dsld_id"]) == ["floor"]


def test_calibration_rules():
    ctx = fr.Context({}, {}, {}, {}, {}, {}, {}, [], calibration=[
        {"path": "ok", "approval_status": "approved_sean", "source_ids": ["u"], "owner": "scripts/dashboard/findings_rules.py::owner_symbol_exists",
         "rationale": "r", "review_date": date.today().isoformat()},
        {"path": "prov", "approval_status": "provisional", "source_ids": [], "owner": "scripts/nope.py::x",
         "rationale": "", "review_date": "2020-01-01"},
    ], pillar_max={})
    incomplete = fr._calibration_incomplete(ctx).set_index("subject")
    assert list(incomplete.index) == ["prov"]
    assert "provisional" in incomplete.loc["prov", "current_value"] and "days old" in incomplete.loc["prov", "current_value"]
    assert list(fr._calibration_owner(ctx)["subject"]) == ["prov"]
    assert fr.calibration_records(), "the production config carries calibration records"


def _golden_doc(**overrides):
    canary = {"dsld_id": "g1", "product_name": "Product g1", "expected_v4_module": "generic",
              "expected_quality_score_status": "scored", "expected_quality_assessment_status": "complete",
              "expected_product_safety_status": "no_known_catalog_concern",
              "expected_quality_tier_band": ["Needs improvement", "Needs improvement"],
              "expected_pillar_invariants": [], **overrides}
    return {"canaries": [canary, {**canary, "dsld_id": "absent"}]}


def test_golden_set_uses_its_own_evaluator_and_flags_each_broken_check():
    record = scored_product("g1")                       # 69.0 -> Needs improvement
    rows = {r["dsld_id"]: r for r in fr.golden_set_results(_golden_doc(), {"g1": record}, {"g1"})}
    assert all(ok for _, ok, _ in rows["g1"]["checks"]) and rows["g1"]["in_core_catalog"]
    assert rows["absent"]["checks"] == [("present", False, "missing from scored output")]
    broken = fr.golden_set_results(_golden_doc(expected_product_safety_status="caution"), {"g1": record}, set())
    ctx = fr.Context({}, {}, {}, {}, {}, {}, {}, [], [], {}, golden=broken)
    hits = fr._canary_expectations(ctx)
    assert set(zip(hits["dsld_id"], hits["subject"])) == {("g1", "expected_product_safety_status"), ("absent", "present")}
    ctx.plane = "release"
    assert fr._canary_expectations(ctx).empty         # full scored records exist on candidate runs only


def test_psi():
    same = pd.Series([1.0, 5.0, 10.0, 15.0] * 10)
    assert fr.psi(same, same) == pytest.approx(0.0, abs=1e-6)
    assert fr.psi(same, same + 8) > fr.PSI_LIMIT


def test_peer_outlier_needs_complete_cohort():
    rows = [{"dsld_id": str(i), "total": 60.0 + (i % 3), "category": "c", "quality_score_status": "scored",
             "quality_assessment_status": "complete"} for i in range(40)]
    rows.append({"dsld_id": "hi", "total": 100.0, "category": "c", "quality_score_status": "scored",
                 "quality_assessment_status": "complete"})
    small = [{**row, "category": "tiny"} for row in rows[:10]] + [{**rows[-1], "dsld_id": "hi2", "category": "tiny"}]
    ctx = fr.Context({"candidate": pd.DataFrame(rows + small)}, {}, {}, {}, {}, {}, {}, [], [], {})
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


def test_exception_scope_uses_each_findings_run_fingerprint(tmp_path):
    db = tmp_path / "triage.sqlite"
    triage.set_status("a", "r", 1, "Accepted exception", config_scope="fp-old", path=db)
    triage.set_status("b", "r", 1, "Accepted exception", config_scope="fp-release", path=db)
    findings = pd.DataFrame([{"finding_id": "a", "rule_id": "r", "rule_version": 1, "run_key": "candidate"},
                             {"finding_id": "b", "rule_id": "r", "rule_version": 1, "run_key": "release"}])
    result = triage.merge(findings, config_versions=[], path=db,
                         run_configs={"candidate": ["fp-new"], "release": ["fp-release"]}).set_index("finding_id")
    assert result.loc["a", "triage_status"] == "Open"
    assert result.loc["b", "triage_status"] == "Accepted exception"


def test_config_diff_compares_verified_values_and_keeps_missing_history_explicit(monkeypatch):
    snapshots = {"old": {"calibration": {"limit": 1}}, "new": {"calibration": {"limit": 2}}}
    monkeypatch.setattr(run_compare, "config_snapshot", lambda name, version, fp: snapshots.get(fp))
    run = lambda fp: {"config_fingerprints": [json.dumps({"quality_score": {"version": "v", "fingerprint": fp}})]}
    diff, missing = run_compare.config_diff(run("old"), run("new"))
    assert not missing
    assert diff.to_dict("records") == [{"config": "quality_score", "setting": "calibration.limit", "baseline": "1", "candidate": "2"}]
    diff, missing = run_compare.config_diff(run("absent"), run("new"))
    assert diff.empty and missing == ["baseline quality_score: verified config snapshot unavailable"]


def test_peer_outliers_do_not_mix_config_fingerprints():
    rows = [{"dsld_id": str(i), "total": 60.0 + (i % 3), "category": "c", "quality_score_status": "scored",
             "quality_assessment_status": "complete", "config_fingerprint": "a" if i < 20 else "b"} for i in range(40)]
    rows.append({**rows[-1], "dsld_id": "hi", "total": 100.0})
    ctx = fr.Context({"candidate": pd.DataFrame(rows)}, {}, {}, {}, {}, {}, {}, [], [], {})
    assert fr._peer_outlier(ctx).empty


def test_legacy_unscoped_exception_cannot_remain_closed():
    assert triage.effective_status({"status": "Accepted exception", "rule_version": 1,
                                    "finding_rule_version": 1, "config_scope": None},
                                   config_versions=["fp-current"]) == "Open"


def test_config_snapshot_requires_matching_content_hash(tmp_path, monkeypatch):
    import hashlib
    from scoring_v4 import config_registry
    raw = b'{"version": "same", "calibration": 2}'
    config = tmp_path / "config.json"
    config.write_bytes(raw)
    monkeypatch.setattr(run_compare, "REPO_ROOT", tmp_path)
    monkeypatch.setitem(config_registry._PROVENANCE_CONFIGS, "test_snapshot", config)
    run_compare.config_snapshot.cache_clear()
    assert run_compare.config_snapshot("test_snapshot", "same", hashlib.sha256(raw).hexdigest()[:16]) == json.loads(raw)
    assert run_compare.config_snapshot("test_snapshot", "same", "wrong-fingerprint") is None
    run_compare.config_snapshot.cache_clear()


def test_product_exception_reopens_when_its_config_changes_inside_mixed_run(tmp_path):
    db = tmp_path / "triage.sqlite"
    triage.set_status("f", "r", 1, "Accepted exception", config_scope="A", path=db)
    finding = pd.DataFrame([{"finding_id": "f", "rule_id": "r", "rule_version": 1,
                             "run_key": "mixed", "dsld_id": "P", "config_fingerprint": "B"}])
    result = triage.merge(finding, config_versions=[], run_configs={"mixed": ["A", "B"]}, path=db)
    assert result.iloc[0]["triage_status"] == "Open"
