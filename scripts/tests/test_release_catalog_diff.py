"""Catalog comparison: safety exceptions gate, ordinary quality movements report.

All baselines remain checked; exact safety approvals cannot cover changed states.
Clinical correctness and external publication authorization are separate gates.
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
from scoring_v4.gate_safety import SAFETY_VERDICT_PRECEDENCE  # noqa: E402
from scoring_v4.scored_artifact import PUBLIC_VERDICT_PRECEDENCE, _public_verdict  # noqa: E402


def make_db(path: Path, rows: list[tuple]) -> Path:
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    con.execute(f"create table products_core ({', '.join(catalog_diff.COLUMNS)})")
    con.executemany(
        f"insert into products_core values ({', '.join('?' * len(catalog_diff.COLUMNS))})", rows)
    con.commit()
    con.close()
    return path


def row(pid, verdict="SAFE", score=72.0, tier="Good", name=None, status="scored", reason=None, safety=None):
    safety = safety or {"BLOCKED": "blocked", "UNSAFE": "unsafe", "CAUTION": "caution"}.get(verdict, "no_known_catalog_concern")
    return (pid, name or f"Product {pid}", "Brand", verdict, score, tier, status, reason, safety)


def blocked(pid, name=None):
    return row(pid, "BLOCKED", None, None, name=name, status="suppressed_safety", reason="recall")


def diff(tmp_path, before, after, approvals=()):
    return catalog_diff.diff_catalogs(
        make_db(tmp_path / "baseline.db", before),
        make_db(tmp_path / "candidate.db", after),
        list(approvals),
    )


def gated(result):
    return {c["dsld_id"]: [r["kind"] for r in c["reasons"]] for c in result["gated"]}


def state(verdict="SAFE", tier="Good", score=72.0):
    return {"verdict": "NO_KNOWN_CATALOG_CONCERN" if verdict in {"SAFE", "POOR"} else verdict, "tier": tier, "score": score}


def approval(changes, reason="Reviewed: dose calibration", approved_by="Sean"):
    return {"reason": reason, "approved_by": approved_by, "date": "2026-10-01", "changes": changes}


def test_unchanged_catalog_passes(tmp_path):
    rows = [row("1"), blocked("2")]
    result = diff(tmp_path, rows, rows)
    assert result["gated"] == [] and result["unapproved"] == 0
    assert result["shared"] == 2 and result["added"] == 0 and result["removed"] == 0


def test_a_milder_safety_warning_stops_and_poor_counts_as_no_warning(tmp_path):
    before = [blocked("1"), row("2", "CAUTION"), row("3", "CAUTION"), row("4", "UNSAFE", None, None),
              row("5"), row("6", "POOR", 50.0, "Poor")]
    after = [row("1", "CAUTION"), row("2", "SAFE"), row("3", "POOR", 72.0), blocked("4"),
             row("5", "CAUTION"), row("6", "SAFE", 50.0, "Poor")]
    result = diff(tmp_path, before, after)
    assert gated(result) == {"1": ["milder_safety"], "2": ["milder_safety"], "3": ["milder_safety"]}
    rows = {(t["from"], t["to"]): t["safety"] for t in result["verdict_transitions"]}
    assert rows[("CAUTION", "NO_KNOWN_CATALOG_CONCERN")] == "milder"
    assert rows[("NO_KNOWN_CATALOG_CONCERN", "CAUTION")] == "stricter"
    assert not any("POOR" in pair for pair in rows)


def test_a_warned_product_leaving_the_catalog_stops_but_a_safe_or_poor_one_does_not(tmp_path):
    before = [blocked("1"), row("2", "CAUTION"), row("3"), row("4", "POOR", 40.0, "Poor"), row("5")]
    after = [row("5"), blocked("6")]
    result = diff(tmp_path, before, after)
    assert gated(result) == {"1": ["removed"], "2": ["removed"]}
    assert result["removed"] == 4 and result["added"] == 1
    assert result["added_by_verdict"] == {"BLOCKED": 1}


def test_a_grade_up_is_reported_with_a_rise_of_five_points(tmp_path):
    before = [row("1", score=72.0, tier="Good"), row("2", score=68.0, tier="Needs improvement"),
              row("3", "POOR", 50.0, "Poor"), row("4", score=81.0, tier="Very good")]
    after = [row("1", score=81.0, tier="Very good"), row("2", score=71.0, tier="Good"),
             row("3", "SAFE", 56.0, "Needs improvement"), row("4", score=79.0, tier="Good")]
    result = diff(tmp_path, before, after)
    assert gated(result) == {}
    assert {c["dsld_id"]: [r["kind"] for r in c["reasons"]] for c in result["reported"]} == {"1": ["tier_up"], "3": ["tier_up"]}
    tiers = {(t["from"], t["to"]): (t["products"], t["stopping"]) for t in result["tier_transitions"]}
    assert tiers[("Needs improvement", "Good")] == (1, 0)
    assert tiers[("Very good", "Good")] == (1, 0)


def test_a_score_move_of_ten_points_is_reported_either_way(tmp_path):
    before = [row("1", score=72.3), row("2", score=72.3), row("3", score=50.0, tier="Poor"),
              row("4", score=60.0, tier="Needs improvement")]
    after = [row("1", score=62.3), row("2", score=62.4), row("3", score=59.9, tier="Poor"),
             row("4", score=70.0, tier="Needs improvement")]
    result = diff(tmp_path, before, after)
    # 72.3 - 62.3 is 9.999... in floating point; the gate still counts it as 10.
    assert gated(result) == {}
    assert {c["dsld_id"]: [r["kind"] for r in c["reasons"]] for c in result["reported"]} == {"1": ["score_drop"], "4": ["score_rise"]}
    assert result["score_changes"] == {"down": 2, "up": 2}


def test_one_product_is_one_row_with_every_reason(tmp_path):
    result = diff(tmp_path, [row("1", "CAUTION", 70.0, "Good")], [row("1", "SAFE", 85.0, "Very good")])
    assert gated(result) == {"1": ["milder_safety", "score_rise", "tier_up"]}
    assert result["gated"][0]["kind"] == "milder_safety"


def test_a_score_suppressed_by_a_safety_verdict_is_not_a_score_move(tmp_path):
    result = diff(tmp_path, [row("1", score=80.0)], [blocked("1")])
    assert result["gated"] == []


def test_an_approval_covers_only_the_exact_before_and_after(tmp_path):
    before = [row("1", "CAUTION"), row("2", "CAUTION")]
    after = [row("1"), row("2")]
    approvals = [approval([
        {"dsld_id": "1", "from": state("CAUTION"), "to": state()},
        {"dsld_id": 2, "from": state("CAUTION"), "to": state(score=73.0)},
    ])]
    result = diff(tmp_path, before, after, approvals)
    by_id = {c["dsld_id"]: c for c in result["gated"]}
    assert by_id["1"]["approval"]["approved_by"] == "Sean"
    assert by_id["2"]["approval"] is None
    assert result["unapproved"] == 1
    assert [a["dsld_id"] for a in result["stale_approvals"]] == [2]


@pytest.mark.parametrize("bad", [
    approval([], reason="x"),
    approval([{"dsld_id": "1", "from": state(), "to": None}], reason=" "),
    approval([{"dsld_id": "1", "from": state(), "to": None}], approved_by=""),
    approval([{"dsld_id": "1", "from": {"verdict": "SAFE"}, "to": None}]),
    approval([{"dsld_id": "1", "form": state(), "to": None}]),
    approval([{"dsld_id": "1", "from": None, "to": state()}]),
    {**approval([{"dsld_id": "1", "from": state(), "to": None}]), "date": "yesterday"},
])
def test_an_approval_without_a_reason_approver_date_or_exact_change_is_refused(tmp_path, bad):
    path = tmp_path / "approvals.json"
    path.write_text(json.dumps({"approvals": [bad]}))
    with pytest.raises(ValueError):
        catalog_diff.load_approvals(path)


@pytest.mark.parametrize("bad_row", [row("1", "MAYBE"), row("1", tier="Okay")])
def test_an_unknown_verdict_or_grade_fails_closed(tmp_path, bad_row):
    with pytest.raises(ValueError, match="MAYBE|Okay"):
        diff(tmp_path, [row("1")], [bad_row])


def test_the_committed_approvals_file_loads():
    catalog_diff.load_approvals()


def test_the_safety_ladder_follows_the_public_precedence():
    assert [v for v in PUBLIC_VERDICT_PRECEDENCE if v in SAFETY_VERDICT_PRECEDENCE] == list(SAFETY_VERDICT_PRECEDENCE)
    assert "POOR" not in SAFETY_VERDICT_PRECEDENCE


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
    before = [row("1", "CAUTION", name="Iron Plus"), row("2", "CAUTION", name="Two |\nLines"),
              row("3", score=90.0, tier="Excellent"), row("4", "POOR", 50.0, "Poor")]
    after = [row("1", name="Iron Plus"), row("3", score=60.0, tier="Needs improvement"),
             row("4", "SAFE", 58.0, "Needs improvement")]
    result = diff(tmp_path, before, after)

    report = catalog_diff.render_markdown(result)
    assert "STOPS THE RELEASE" in report and "Iron Plus" in report
    assert "CAUTION → no safety warning" in report
    assert "| 2 | Two / Lines | Brand | CAUTION · Good · 72 | not in catalog |" in report
    assert "score -30.0" in report and "grade Poor → Needs improvement (+8.0)" in report
    assert "POOR → SAFE" not in report
    assert "Catalog safety changes" in report

    draft = catalog_diff.draft_approvals(result)
    for group in draft["approvals"]:
        group.update(reason="Reviewed", approved_by="Sean", date="2026-10-01")
    path = tmp_path / "approvals.json"
    path.write_text(json.dumps(draft))
    approved = diff(tmp_path, before, after, catalog_diff.load_approvals(path))
    assert approved["unapproved"] == 0 and len(approved["gated"]) == 2 and len(approved["reported"]) == 2
    assert "Catalog comparison passed" in catalog_diff.render_markdown(approved)


# --- Live catalog: what the in-app updater downloads -------------------------


class FakeStorage:
    def __init__(self, files):
        self.files, self.requests = files, []

    def from_(self, bucket):
        self.bucket = bucket
        return self

    def download(self, path):
        self.requests.append((self.bucket, path))
        return self.files[path]


class FakeClient:
    def __init__(self, files):
        self.storage = FakeStorage(files)


def live(monkeypatch, row_, files=None):
    client = FakeClient(files or {})
    monkeypatch.setattr(catalog_diff, "get_supabase_client", lambda: client)
    monkeypatch.setattr(catalog_diff, "fetch_current_manifest", lambda c: row_)
    return client


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def test_the_live_catalog_is_skipped_when_it_is_the_bundled_one(tmp_path, monkeypatch):
    client = live(monkeypatch, {"db_version": "v1", "checksum": sha(b"bundle")})
    assert catalog_diff._live_baseline(hashlib.sha256(b"bundle").hexdigest(), tmp_path) is None
    assert client.storage.requests == []


def test_a_newer_live_catalog_is_downloaded_and_checksum_verified(tmp_path, monkeypatch):
    client = live(monkeypatch, {"db_version": "2026.09.30", "checksum": sha(b"live")},
                  {"v2026.09.30/pharmaguide_core.db": b"live"})
    db, info = catalog_diff._live_baseline("0" * 64, tmp_path)
    assert db.read_bytes() == b"live" and info["db_version"] == "2026.09.30"
    assert client.storage.requests == [("pharmaguide", "v2026.09.30/pharmaguide_core.db")]


@pytest.mark.parametrize("row_, files", [
    (None, {}),
    ({"db_version": "x"}, {}),
    ({"db_version": "x", "checksum": sha(b"expected")}, {"vx/pharmaguide_core.db": b"tampered"}),
])
def test_an_unreadable_or_mismatched_live_catalog_fails_closed(tmp_path, monkeypatch, row_, files):
    live(monkeypatch, row_, files)
    with pytest.raises(ValueError):
        catalog_diff._live_baseline("0" * 64, tmp_path)


# --- CLI: compare with every catalog users can have ---------------------------


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


def run_cli(tmp_path, monkeypatch, repo, candidate_rows, live_rows=None):
    def fake_live(bundle_sha, workdir):
        if live_rows is None:
            return None
        return make_db(workdir / "live.db", live_rows), {"db_version": "2026.09.30", "source": "live"}

    monkeypatch.setattr(catalog_diff, "_live_baseline", fake_live)
    candidate = make_db(tmp_path / "candidate.db", candidate_rows)
    approvals_path = tmp_path / "approvals.json"
    approvals_path.write_text(json.dumps({"approvals": []}))
    out = tmp_path / "out"
    code = catalog_diff.main([
        "--flutter-repo", str(repo), "--candidate-db", str(candidate),
        "--approvals", str(approvals_path),
        "--report", str(out / "report.md"), "--draft-approvals", str(out / "draft.json"),
    ])
    return code, out


def test_cli_passes_when_nothing_weakens(tmp_path, monkeypatch):
    repo = fake_flutter_repo(tmp_path, [row("1", "POOR", 40.0, "Poor")])
    code, out = run_cli(tmp_path, monkeypatch, repo, [row("1", "CAUTION", 40.0, "Poor")])
    assert code == 0
    assert "2026.09.22" in (out / "report.md").read_text()
    assert not (out / "draft.json").exists()


def test_cli_stops_on_an_unapproved_change_and_writes_a_draft(tmp_path, monkeypatch):
    repo = fake_flutter_repo(tmp_path, [row("1", "CAUTION")])
    code, out = run_cli(tmp_path, monkeypatch, repo, [row("1")])
    assert code == 1
    draft = json.loads((out / "draft.json").read_text())
    assert draft["approvals"][0]["changes"][0]["dsld_id"] == "1"


def test_cli_also_compares_with_a_newer_live_catalog(tmp_path, monkeypatch):
    # A Supabase-only release added Q as BLOCKED; the bundle never had it.
    repo = fake_flutter_repo(tmp_path, [row("1")])
    code, out = run_cli(tmp_path, monkeypatch, repo, [row("1")], live_rows=[row("1"), blocked("Q")])
    assert code == 1
    report = (out / "report.md").read_text()
    assert "2026.09.30" in report and "| Q |" in report


def test_cli_refuses_a_bundle_that_is_not_the_one_committed_on_main(tmp_path, monkeypatch):
    repo = fake_flutter_repo(tmp_path, [row("1")], commit_checksum=False)
    code, _ = run_cli(tmp_path, monkeypatch, repo, [row("1")])
    assert code == 2


def test_cli_fails_closed_when_the_live_catalog_cannot_be_read(tmp_path, monkeypatch):
    repo = fake_flutter_repo(tmp_path, [row("1")])
    monkeypatch.setattr(catalog_diff, "_live_baseline", lambda *a: (_ for _ in ()).throw(OSError("offline")))
    candidate = make_db(tmp_path / "candidate.db", [row("1")])
    approvals_path = tmp_path / "approvals.json"
    approvals_path.write_text(json.dumps({"approvals": []}))
    code = catalog_diff.main([
        "--flutter-repo", str(repo), "--candidate-db", str(candidate), "--approvals", str(approvals_path),
        "--report", str(tmp_path / "r.md"), "--draft-approvals", str(tmp_path / "d.json"),
    ])
    assert code == 2


@pytest.mark.parametrize('legacy_before,safety_before,expected_gate', [
    ('CAUTION', 'no_known_catalog_concern', []),
    ('POOR', 'caution', ['milder_safety']),
])
def test_release_safety_uses_independent_catalog_status(tmp_path, legacy_before, safety_before, expected_gate):
    before = make_db(tmp_path / 'baseline.db', [row('1', legacy_before)])
    after = make_db(tmp_path / 'candidate.db', [row('1', 'SAFE')])
    for path, safety in [(before, safety_before), (after, 'no_known_catalog_concern')]:
        con = sqlite3.connect(path)
        if 'product_safety_status' not in {r[1] for r in con.execute('pragma table_info(products_core)')}:
            con.execute('alter table products_core add column product_safety_status TEXT')
        con.execute('update products_core set product_safety_status = ?', (safety,))
        con.commit()
        con.close()
    result = catalog_diff.diff_catalogs(before, after, [])
    assert gated(result).get('1', []) == expected_gate
    assert all('POOR' not in (t['from'], t['to']) for t in result['verdict_transitions'])


@pytest.mark.parametrize('safety', [None, '', 'safe', 'poor', 'unrecognized'])
def test_release_gate_refuses_missing_or_unknown_typed_safety(tmp_path, safety):
    before = make_db(tmp_path / 'baseline.db', [row('1')])
    after = make_db(tmp_path / 'candidate.db', [row('1')])
    con = sqlite3.connect(after)
    con.execute('update products_core set product_safety_status = ?', (safety,))
    con.commit()
    con.close()
    with pytest.raises(ValueError, match='unknown catalog safety status'):
        catalog_diff.diff_catalogs(before, after, [])


def test_release_gate_refuses_a_catalog_without_independent_safety_column(tmp_path):
    before = make_db(tmp_path / 'baseline.db', [row('1')])
    after = tmp_path / 'candidate.db'
    con = sqlite3.connect(after)
    con.execute(f"create table products_core ({', '.join(catalog_diff.COLUMNS[:-1])})")
    con.execute(f"insert into products_core values ({', '.join('?' * (len(catalog_diff.COLUMNS) - 1))})", row('1')[:-1])
    con.commit()
    con.close()
    with pytest.raises(ValueError, match='lacks product_safety_status'):
        catalog_diff.diff_catalogs(before, after, [])


def test_development_quality_movements_are_reported_without_approval(tmp_path):
    result = diff(tmp_path, [row('up', score=60, tier='Needs improvement'), row('down', score=90, tier='Excellent')],
                  [row('up', score=90, tier='Excellent'), row('down', score=60, tier='Needs improvement')])
    assert result['unapproved'] == 0
    assert result['gated'] == []
    assert {c['dsld_id'] for c in result['reported']} == {'up', 'down'}
    assert catalog_diff.draft_approvals(result) == {'approvals': []}
    report = catalog_diff.render_markdown(result)
    assert 'report-only' in report
    assert '| up |' in report and '| down |' in report
    assert 'clinical correctness' in report


def test_score_movement_never_hides_safety_review_or_warned_removal(tmp_path):
    result = diff(tmp_path, [row('safety', 'CAUTION', 60, 'Needs improvement'), blocked('gone'), row('ordinary', score=50, tier='Poor')],
                  [row('safety', score=90, tier='Excellent'), row('ordinary', score=80, tier='Very good')])
    assert result['unapproved'] == 2
    assert set(gated(result)) == {'safety', 'gone'}
    assert {c['dsld_id'] for c in result['reported']} == {'ordinary'}
    drafts = catalog_diff.draft_approvals(result)['approvals']
    assert {c['dsld_id'] for g in drafts for c in g['changes']} == {'safety', 'gone'}


@pytest.mark.parametrize('rows', [[], [row('duplicate'), row('duplicate')], [row('bad', score=float('inf'))]])
def test_unusable_catalog_cannot_pass_movement_review(tmp_path, rows):
    with pytest.raises(ValueError):
        diff(tmp_path, [row('control')], rows)


def test_cli_quality_only_movements_pass_for_both_baselines_without_drafts(tmp_path, monkeypatch):
    repo = fake_flutter_repo(tmp_path, [row('1', score=40, tier='Poor')])
    code, out = run_cli(tmp_path, monkeypatch, repo, [row('1', score=90, tier='Excellent')],
                        live_rows=[row('1', score=60, tier='Needs improvement')])
    assert code == 0
    report = (out / 'report.md').read_text()
    assert report.count('Quality movements — report-only (1 products)') == 2
    assert not (out / 'draft.json').exists()


def test_safety_exception_is_counted_even_with_quality_downgrade(tmp_path):
    result = diff(tmp_path, [row('1', 'CAUTION', 90, 'Excellent')],
                  [row('1', score=60, tier='Needs improvement')])
    assert result['tier_transitions'][0]['stopping'] == 1
    assert result['unapproved'] == 1


def test_old_quality_approval_cannot_approve_new_safety_exception(tmp_path):
    old = approval([{'dsld_id': '1', 'from': state(score=60, tier='Needs improvement'),
                     'to': state(score=90, tier='Excellent')}])
    result = diff(tmp_path, [row('1', 'CAUTION', 60, 'Needs improvement')],
                  [row('1', score=90, tier='Excellent')], [old])
    assert result['unapproved'] == 1
    assert result['gated'][0]['approval'] is None
