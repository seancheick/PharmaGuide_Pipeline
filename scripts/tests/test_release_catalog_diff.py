"""The release gate that compares the candidate catalog with the app's bundle.

A change that weakens what a user is told (a milder verdict, a warned product
leaving the catalog, a big score drop) stops the release unless a reviewed
approval names that exact change.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from release_safety import catalog_diff  # noqa: E402
from scoring_v4.scored_artifact import PUBLIC_VERDICT_PRECEDENCE, _public_verdict  # noqa: E402


COLUMNS = (
    "dsld_id", "product_name", "brand_name", "verdict",
    "quality_score_v4_100", "quality_score_status", "blocking_reason",
)


def make_db(path: Path, rows: list[tuple]) -> Path:
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    con.execute(f"create table products_core ({', '.join(COLUMNS)})")
    con.executemany(f"insert into products_core values ({', '.join('?' * len(COLUMNS))})", rows)
    con.commit()
    con.close()
    return path


def row(pid, verdict="SAFE", score=70.0, name=None, status="scored", reason=None):
    return (pid, name or f"Product {pid}", "Brand", verdict, score, status, reason)


def diff(tmp_path, before, after, approvals=()):
    return catalog_diff.diff_catalogs(
        make_db(tmp_path / "baseline.db", before),
        make_db(tmp_path / "candidate.db", after),
        list(approvals),
    )


def gated(result):
    return {(c["dsld_id"], c["kind"], c["from"], c["to"]) for c in result["gated"]}


def approval(changes, reason="Reviewed: dose calibration", approved_by="Sean"):
    return {"reason": reason, "approved_by": approved_by, "date": "2026-10-01", "changes": changes}


def test_unchanged_catalog_passes(tmp_path):
    rows = [row("1"), row("2", "BLOCKED", None, status="suppressed_safety", reason="recall")]
    result = diff(tmp_path, rows, rows)
    assert result["gated"] == [] and result["unapproved"] == 0
    assert result["shared"] == 2 and result["added"] == 0 and result["removed"] == 0


def test_milder_verdicts_are_gated_and_stricter_ones_are_not(tmp_path):
    before = [row("1", "BLOCKED", None, status="suppressed_safety"), row("2", "POOR", 40.0),
              row("3", "SAFE"), row("4", "CAUTION")]
    after = [row("1", "CAUTION"), row("2", "SAFE", 40.0), row("3", "POOR", 70.0), row("4", "UNSAFE", None)]
    result = diff(tmp_path, before, after)
    assert gated(result) == {("1", "milder_verdict", "BLOCKED", "CAUTION"),
                             ("2", "milder_verdict", "POOR", "SAFE")}
    transitions = {(t["from"], t["to"]): (t["products"], t["milder"]) for t in result["verdict_transitions"]}
    assert transitions[("SAFE", "POOR")] == (1, False)
    assert transitions[("CAUTION", "UNSAFE")] == (1, False)
    assert result["unapproved"] == 2


def test_a_warned_product_leaving_the_catalog_is_gated_but_a_safe_one_is_not(tmp_path):
    before = [row("1", "BLOCKED", None), row("2", "CAUTION"), row("3", "SAFE"), row("4")]
    after = [row("4"), row("5", "BLOCKED", None)]
    result = diff(tmp_path, before, after)
    assert gated(result) == {("1", "removed", "BLOCKED", None), ("2", "removed", "CAUTION", None)}
    assert result["removed"] == 3 and result["added"] == 1
    assert result["added_by_verdict"] == {"BLOCKED": 1}


def test_score_drops_are_gated_from_the_limit_and_rises_are_only_reported(tmp_path):
    before = [row("1", score=72.3), row("2", score=72.3), row("3", score=50.0), row("4", score=None)]
    after = [row("1", score=62.3), row("2", score=62.4), row("3", score=75.0), row("4", score=20.0)]
    result = diff(tmp_path, before, after)
    # 72.3 - 62.3 is 9.999... in floating point; the gate still counts it as 10.
    assert gated(result) == {("1", "score_drop", 72.3, 62.3)}
    assert result["score_changes"] == {"down": 2, "up": 1}
    assert [r["dsld_id"] for r in result["biggest_rises"]] == ["3"]


def test_a_score_suppressed_by_a_safety_verdict_is_not_a_score_drop(tmp_path):
    result = diff(tmp_path, [row("1", score=80.0)],
                  [row("1", "BLOCKED", None, status="suppressed_safety")])
    assert result["gated"] == []


def test_an_approval_covers_only_the_exact_change_it_names(tmp_path):
    before = [row("1", "POOR", 40.0), row("2", "POOR", 40.0)]
    after = [row("1", "SAFE", 40.0), row("2", "SAFE", 40.0)]
    approvals = [approval([
        {"dsld_id": "1", "kind": "milder_verdict", "from": "POOR", "to": "SAFE"},
        {"dsld_id": "2", "kind": "milder_verdict", "from": "CAUTION", "to": "SAFE"},
    ])]
    result = diff(tmp_path, before, after, approvals)
    by_id = {c["dsld_id"]: c for c in result["gated"]}
    assert by_id["1"]["approval"]["approved_by"] == "Sean"
    assert by_id["2"]["approval"] is None
    assert result["unapproved"] == 1
    assert result["stale_approvals"] == [
        {"dsld_id": "2", "kind": "milder_verdict", "from": "CAUTION", "to": "SAFE"}
    ]


@pytest.mark.parametrize("bad", [
    approval([], reason="x"),
    approval([{"dsld_id": "1", "kind": "milder_verdict", "from": "POOR", "to": "SAFE"}], reason=" "),
    approval([{"dsld_id": "1", "kind": "milder_verdict", "from": "POOR", "to": "SAFE"}], approved_by=""),
    approval([{"dsld_id": "1", "kind": "made_up", "from": "POOR", "to": "SAFE"}]),
    approval([{"dsld_id": "1", "kind": "milder_verdict", "form": "POOR", "to": "SAFE"}]),
    {**approval([{"dsld_id": "1", "kind": "removed", "from": "CAUTION", "to": None}]), "date": "yesterday"},
])
def test_an_approval_without_a_reason_approver_date_or_exact_change_is_refused(tmp_path, bad):
    path = tmp_path / "approvals.json"
    path.write_text(json.dumps({"approvals": [bad]}))
    with pytest.raises(ValueError):
        catalog_diff.load_approvals(path)


def test_an_unknown_verdict_fails_closed(tmp_path):
    with pytest.raises(ValueError, match="MAYBE"):
        diff(tmp_path, [row("1")], [row("1", "MAYBE")])


def test_the_committed_approvals_file_loads():
    catalog_diff.load_approvals()


def test_precedence_names_every_public_verdict():
    seen = {
        _public_verdict({"quality_score_status": status, "v4_verdict": verdict}, coverage)
        for status in ("scored", "not_scored", "suppressed_safety", "", "other")
        for verdict in (*PUBLIC_VERDICT_PRECEDENCE, "", "junk")
        for coverage in (0.0, 1.0)
    }
    assert seen <= set(PUBLIC_VERDICT_PRECEDENCE)


def test_the_cutover_audit_ranks_verdicts_by_the_shared_precedence():
    sys.path.insert(0, str(SCRIPTS / "api_audit"))
    from api_audit.audit_v4_profile_cutover_impact import VERDICT_RANK

    assert sorted(VERDICT_RANK, key=VERDICT_RANK.get, reverse=True) == list(PUBLIC_VERDICT_PRECEDENCE)


def test_report_and_draft_approvals_close_the_loop(tmp_path):
    before = [row("1", "POOR", 40.0, name="Iron Plus"), row("2", "CAUTION", name="Two |\nLines"),
              row("3", score=90.0)]
    after = [row("1", "SAFE", 40.0, name="Iron Plus"), row("3", score=60.0)]
    result = diff(tmp_path, before, after)

    report = catalog_diff.render_markdown(result)
    assert "STOPS THE RELEASE" in report and "Iron Plus" in report
    assert "POOR → SAFE" in report and "-30.0" in report
    assert "| 2 | Two / Lines | Brand | CAUTION → not in catalog |" in report

    draft = catalog_diff.draft_approvals(result)
    for group in draft["approvals"]:
        group.update(reason="Reviewed", approved_by="Sean", date="2026-10-01")
    path = tmp_path / "approvals.json"
    path.write_text(json.dumps(draft))
    approved = diff(tmp_path, before, after, catalog_diff.load_approvals(path))
    assert approved["unapproved"] == 0 and len(approved["gated"]) == 3
    assert "Release can proceed" in catalog_diff.render_markdown(approved)


# --- CLI: the baseline must be the bundle committed on the app's main --------


def fake_flutter_repo(tmp_path: Path, rows: list[tuple], *, commit_checksum=True) -> Path:
    repo = tmp_path / "flutter"
    (repo / "assets/db").mkdir(parents=True)
    db = make_db(repo / "assets/db/pharmaguide_core.db", rows)
    digest = hashlib.sha256(db.read_bytes()).hexdigest()
    manifest = {"db_version": "2026.09.22", "checksum_sha256": digest if commit_checksum else "0" * 64}
    (repo / "assets/db/export_manifest.json").write_text(json.dumps(manifest))
    git = ["git", "-C", str(repo)]
    subprocess.run([*git, "init", "-q", "-b", "main"], check=True)
    subprocess.run([*git, "add", "assets/db/export_manifest.json"], check=True)
    subprocess.run([*git, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "bundle"], check=True)
    return repo


def run_cli(tmp_path, repo, candidate_rows, approvals=None):
    candidate = make_db(tmp_path / "candidate.db", candidate_rows)
    approvals_path = tmp_path / "approvals.json"
    approvals_path.write_text(json.dumps({"approvals": approvals or []}))
    out = tmp_path / "out"
    code = catalog_diff.main([
        "--flutter-repo", str(repo), "--candidate-db", str(candidate),
        "--approvals", str(approvals_path),
        "--report", str(out / "report.md"), "--draft-approvals", str(out / "draft.json"),
    ])
    return code, out


def test_cli_passes_when_nothing_weakens(tmp_path):
    repo = fake_flutter_repo(tmp_path, [row("1", "POOR", 40.0)])
    code, out = run_cli(tmp_path, repo, [row("1", "CAUTION", 40.0)])
    assert code == 0
    assert "2026.09.22" in (out / "report.md").read_text()
    assert not (out / "draft.json").exists()


def test_cli_stops_on_an_unapproved_change_and_writes_a_draft(tmp_path):
    repo = fake_flutter_repo(tmp_path, [row("1", "POOR", 40.0)])
    code, out = run_cli(tmp_path, repo, [row("1", "SAFE", 40.0)])
    assert code == 1
    draft = json.loads((out / "draft.json").read_text())
    assert draft["approvals"][0]["changes"][0]["dsld_id"] == "1"


def test_cli_refuses_a_bundle_that_is_not_the_one_committed_on_main(tmp_path):
    repo = fake_flutter_repo(tmp_path, [row("1")], commit_checksum=False)
    code, _ = run_cli(tmp_path, repo, [row("1")])
    assert code == 2
