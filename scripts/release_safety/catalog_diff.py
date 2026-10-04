#!/usr/bin/env python3
"""Release gate: what changes for users between the catalogs they have and the candidate.

Users have the app bundle (committed on the app's main) and, through the in-app
updater, the live catalog on Supabase (export_manifest is_current). The gate
compares the candidate with each of them, product by product, and stops the
release on milder safety or removal of a warned product unless an exact reviewed
approval covers it. Ordinary score/tier movement is reported for cause-based review,
not individually approved. The historical 10-point score / 5-point tier-rise limits
select report details; they are not safety thresholds or clinical judgments.

The report retains all safety transitions, movement counts and baseline/candidate
hashes. Passing this comparison does not establish clinical correctness, contract
parity or publication authorization; those remain separate release requirements.
Approvals use the existing catalog_change_approvals.json owner for safety exceptions.

Usage:
    python3 scripts/release_safety/catalog_diff.py \\
        --flutter-repo "/path/to/PharmaGuide ai" \\
        --candidate-db scripts/dist/pharmaguide_core.db \\
        --report scripts/reports/release_catalog_diff.md \\
        --draft-approvals scripts/reports/release_catalog_diff_draft_approvals.json

Exit codes: 0 release may proceed, 1 unapproved changes, 2 unusable input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import sys
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from release_safety.bundle_alignment import BundleAlignmentError, read_flutter_bundle_manifest  # noqa: E402
from scoring_v4.gate_safety import SAFETY_VERDICT_PRECEDENCE, safety_verdict_rank  # noqa: E402
from scoring_v4.quality_score_config import config as quality_score_config  # noqa: E402
from scoring_v4.scored_artifact import PUBLIC_VERDICT_PRECEDENCE  # noqa: E402
from supabase_client import STORAGE_BUCKET, core_db_remote_path, fetch_current_manifest, get_supabase_client  # noqa: E402

APPROVALS_PATH = Path(__file__).with_name("catalog_change_approvals.json")
BUNDLED_DB = Path("assets/db/pharmaguide_core.db")
#: A score move of this many points, either way, is detailed in the report.
SCORE_MOVE_LIMIT = 10.0
#: A grade up is detailed when the score rose at least this much.
TIER_UP_MIN_RISE = 5.0
KINDS = ("milder_safety", "removed", "score_drop", "score_rise", "tier_up")
COLUMNS = ("dsld_id", "product_name", "brand_name", "verdict", "quality_score_v4_100",
           "quality_tier", "quality_score_status", "blocking_reason", "product_safety_status")
STATE_KEYS = ("verdict", "tier", "score")
NO_WARNING = len(SAFETY_VERDICT_PRECEDENCE)


def _tiers() -> list[str]:
    """Quality grades, lowest first."""
    return [band["name"] for band in reversed(quality_score_config()["tiers"])]


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _score(value) -> float | None:
    if value is None:
        return None
    score = float(value)
    if not math.isfinite(score) or not 0 <= score <= 100:
        raise ValueError(f"Invalid catalog quality score: {value!r}")
    return round(score, 1)


def _products(db: Path) -> dict[str, dict]:
    if not db.is_file():
        raise ValueError(f"Catalog not found: {db}")
    con = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
    try:
        present = {r[1] for r in con.execute("pragma table_info(products_core)")}
        missing = [c for c in COLUMNS if c not in present]
        if missing:
            raise ValueError(f"{db}: products_core lacks {', '.join(missing)}")
        rows = con.execute(f"select {', '.join(COLUMNS)} from products_core").fetchall()
    finally:
        con.close()
    if not rows:
        raise ValueError(f"{db}: empty catalog cannot establish comparison")
    tiers = set(_tiers())
    products = {}
    for values in rows:
        product = dict(zip(COLUMNS, values))
        if product["dsld_id"] is None or not str(product["dsld_id"]).strip():
            raise ValueError(f"{db}: missing product identity")
        pid = str(product["dsld_id"])
        if pid in products:
            raise ValueError(f"{db}: duplicate product identity {pid}")
        if product["verdict"] not in PUBLIC_VERDICT_PRECEDENCE:
            raise ValueError(f"{db}: product {pid} has unknown verdict {product['verdict']!r}")
        if product["quality_tier"] is not None and product["quality_tier"] not in tiers:
            raise ValueError(f"{db}: product {pid} has unknown grade {product['quality_tier']!r}")
        safety_status = product["product_safety_status"]
        if safety_status not in {"blocked", "unsafe", "caution", "no_known_catalog_concern", "not_assessed"}:
            raise ValueError(f"{db}: product {pid} has unknown catalog safety status {safety_status!r}")
        # The existing approval-state key is a safety disposition, never the
        # legacy combined quality/coverage verdict. No scorer runs here.
        product["state"] = {"verdict": safety_status.upper(), "tier": product["quality_tier"],
                            "score": _score(product["quality_score_v4_100"])}
        products[pid] = product
    return products


def _state_key(state) -> tuple | None:
    return None if state is None else (state["verdict"], state["tier"], _score(state["score"]))


def _key(change: dict) -> tuple:
    return str(change["dsld_id"]), _state_key(change["from"]), _state_key(change["to"])


def _is_state(value) -> bool:
    return isinstance(value, dict) and set(STATE_KEYS) <= value.keys()


def load_approvals(path: Path = APPROVALS_PATH) -> list[dict]:
    """Read reviewed approvals; refuse any group that is not fully signed."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    groups = payload.get("approvals") if isinstance(payload, dict) else None
    if not isinstance(groups, list):
        raise ValueError(f"{path}: expected an object with an 'approvals' list")
    for number, group in enumerate(groups, 1):
        where = f"{path}: approval group {number}"
        if not isinstance(group, dict):
            raise ValueError(f"{where} is not an object")
        for field in ("reason", "approved_by", "date"):
            if not isinstance(group.get(field), str) or not group[field].strip():
                raise ValueError(f"{where} needs a non-empty {field!r}")
        try:
            date.fromisoformat(group["date"])
        except ValueError:
            raise ValueError(f"{where}: date must be YYYY-MM-DD, got {group['date']!r}") from None
        changes = group.get("changes")
        if not isinstance(changes, list) or not changes:
            raise ValueError(f"{where} names no changes")
        for change in changes:
            if (not isinstance(change, dict) or "dsld_id" not in change or not _is_state(change.get("from"))
                    or "to" not in change or not (change["to"] is None or _is_state(change["to"]))):
                raise ValueError(
                    f"{where}: each change needs dsld_id, a 'from' state and a 'to' state or null "
                    f"(a state has {', '.join(STATE_KEYS)}): {change!r}")
    return groups


def _reasons(old: dict, new: dict | None, tiers: list[str]) -> list[dict]:
    """Classify safety exceptions and reportable quality changes, in KINDS order."""
    if new is None:
        if safety_verdict_rank(old["verdict"]) < NO_WARNING:
            return [{"kind": "removed", "text": f"left the catalog while showing {old['verdict']}"}]
        return []
    reasons = []
    if safety_verdict_rank(new["verdict"]) > safety_verdict_rank(old["verdict"]):
        now = new["verdict"] if safety_verdict_rank(new["verdict"]) < NO_WARNING else "no safety warning"
        reasons.append({"kind": "milder_safety", "text": f"safety: {old['verdict']} → {now}"})
    if old["score"] is not None and new["score"] is not None:
        move = round(new["score"] - old["score"], 1)
        if move <= -SCORE_MOVE_LIMIT:
            reasons.append({"kind": "score_drop", "text": f"score {move:+.1f}"})
        if move >= SCORE_MOVE_LIMIT:
            reasons.append({"kind": "score_rise", "text": f"score {move:+.1f}"})
        if (old["tier"] and new["tier"] and tiers.index(new["tier"]) > tiers.index(old["tier"])
                and move >= TIER_UP_MIN_RISE):
            reasons.append({"kind": "tier_up", "text": f"grade {old['tier']} → {new['tier']} ({move:+.1f})"})
    return reasons


def _severity(change: dict) -> float:
    """Sort key within a kind: worst first."""
    old, new = change["from"], change["to"]
    if change["kind"] in ("milder_safety", "removed"):
        return safety_verdict_rank(old["verdict"])
    move = new["score"] - old["score"]
    return move if change["kind"] == "score_drop" else -move


def diff_catalogs(baseline_db: Path, candidate_db: Path, approvals: list[dict]) -> dict:
    """Compare two catalogs; the result is plain JSON for reports and the gate."""
    tiers = _tiers()
    before, after = _products(Path(baseline_db)), _products(Path(candidate_db))
    shared = before.keys() & after.keys()
    removed = before.keys() - after.keys()
    added = after.keys() - before.keys()

    gated, reported, verdicts, grades, stopping = [], [], Counter(), Counter(), Counter()
    score_changes = {"down": 0, "up": 0}
    column_changes = {"blocking_reason": 0, "quality_score_status": 0}
    for pid in sorted(shared | removed):
        old = before[pid]["state"]
        new = after[pid]["state"] if pid in after else None
        if new is not None:
            for column in column_changes:
                column_changes[column] += before[pid][column] != after[pid][column]
            if old["verdict"] != new["verdict"]:
                verdicts[(old["verdict"], new["verdict"])] += 1
            if old["tier"] and new["tier"] and old["tier"] != new["tier"]:
                grades[(old["tier"], new["tier"])] += 1
            if old["score"] is not None and new["score"] is not None and old["score"] != new["score"]:
                score_changes["down" if new["score"] < old["score"] else "up"] += 1
        reasons = _reasons(old, new, tiers)
        if not reasons:
            continue
        needs_review = any(r["kind"] in {"milder_safety", "removed"} for r in reasons)
        if needs_review and new is not None and old["tier"] and new["tier"] and old["tier"] != new["tier"]:
            stopping[(old["tier"], new["tier"])] += 1
        product = after.get(pid) or before[pid]
        (gated if needs_review else reported).append({"dsld_id": pid, "product_name": product["product_name"],
                      "brand_name": product["brand_name"], "from": old, "to": new,
                      "reasons": reasons, "kind": reasons[0]["kind"]})

    approved = {}
    for group in approvals:
        for change in group["changes"]:
            approved[_key(change)] = (change, group)
    for change in gated:
        match = approved.pop(_key(change), None)
        change["approval"] = None if match is None else {
            k: match[1][k] for k in ("reason", "approved_by", "date")}
    order = {kind: i for i, kind in enumerate(KINDS)}
    for changes in (gated, reported):
        changes.sort(key=lambda c: (order[c["kind"]], _severity(c), c["dsld_id"]))

    def safety(old, new):
        moved = safety_verdict_rank(new) - safety_verdict_rank(old)
        return "milder" if moved > 0 else "stricter" if moved < 0 else "none"

    return {
        "baseline": {"path": str(baseline_db), "sha256": _sha256(Path(baseline_db)), "products": len(before)},
        "candidate": {"path": str(candidate_db), "sha256": _sha256(Path(candidate_db)), "products": len(after)},
        "shared": len(shared),
        "added": len(added),
        "removed": len(removed),
        "added_by_verdict": dict(Counter(after[p]["state"]["verdict"] for p in added)),
        "removed_by_verdict": dict(Counter(before[p]["state"]["verdict"] for p in removed)),
        "verdict_transitions": [
            {"from": old, "to": new, "products": n, "safety": safety(old, new)}
            for (old, new), n in sorted(verdicts.items(), key=lambda t: (-t[1], t[0]))
        ],
        "tier_transitions": [
            {"from": old, "to": new, "products": n, "up": tiers.index(new) > tiers.index(old),
             "stopping": stopping[(old, new)]}
            for (old, new), n in sorted(grades.items(), key=lambda t: (-t[1], t[0]))
        ],
        "score_changes": score_changes,
        "column_changes": column_changes,
        "limits": {"score_move": SCORE_MOVE_LIMIT, "tier_up_min_rise": TIER_UP_MIN_RISE},
        "gated": gated,
        "reported": reported,
        "unapproved": sum(c["approval"] is None for c in gated),
        "stale_approvals": [c for c, _ in approved.values()],
    }


KIND_TITLES = {
    "milder_safety": "Safety warning got milder",
    "removed": "Products with a safety warning that left the catalog (a scan would say \"not found\")",
    "score_drop": f"Score fell {SCORE_MOVE_LIMIT:g}+ points",
    "score_rise": f"Score rose {SCORE_MOVE_LIMIT:g}+ points",
    "tier_up": f"Quality grade went up with a {TIER_UP_MIN_RISE:g}+ point rise",
}


def _state_text(state) -> str:
    if state is None:
        return "not in catalog"
    score = "no score" if state["score"] is None else f"{state['score']:g}"
    return f"{state['verdict']} · {state['tier'] or '—'} · {score}"


def _row(cells: list) -> str:
    return "| " + " | ".join(" ".join(str(x or "").split()).replace("|", "/") for x in cells) + " |"


def _table(changes: list[dict], with_approval: bool) -> list[str]:
    head = "| DSLD ID | Product | Brand | Before | After | Change |"
    head += " Approved by | Reason |" if with_approval else ""
    lines = [head, "|" + "---|" * head.count(" |")]
    for c in changes:
        cells = [c["dsld_id"], c["product_name"], c["brand_name"], _state_text(c["from"]),
                 _state_text(c["to"]), "; ".join(r["text"] for r in c["reasons"])]
        if with_approval:
            cells += [c["approval"]["approved_by"], c["approval"]["reason"]]
        lines.append(_row(cells))
    return lines


def render_markdown(result: dict) -> str:
    base, cand = result["baseline"], result["candidate"]
    unapproved = [c for c in result["gated"] if c["approval"] is None]
    approved = [c for c in result["gated"] if c["approval"] is not None]
    if unapproved:
        counts = Counter(c["kind"] for c in unapproved)
        verdict = (f"**STOPS THE RELEASE: {len(unapproved):,} product(s) changed in a way nobody has approved yet** ("
                   + ", ".join(f"{counts[k]:,} {KIND_TITLES[k].split(' (')[0].lower()}" for k in KINDS if counts[k])
                   + ").")
    else:
        verdict = "**Catalog comparison passed:** no unapproved safety exception. Other release gates and publication authorization still apply."

    def label(side):
        version = f"{side['db_version']}, " if side.get("db_version") else ""
        return f"`{side['path']}` ({version}{side['products']:,} products, sha256 {side['sha256'][:12]})"

    lines = [
        f"# Catalog changes: {base.get('source', 'baseline')} → release candidate", "",
        f"- What users have now ({base.get('source', 'baseline')}): {label(base)}",
        f"- Release candidate: {label(cand)}", "",
        verdict, "",
        "Ordinary score/tier movements are report-only: review shared causes with source traces "
        "and representative controls. A numerical delta does not prove its cause or clinical correctness. "
        "Clinical applicability, identity, exposure, warning retention and app contracts must pass "
        "their existing checks; this report does not replace them.", "",
        "## Summary", "",
        "| | Products |", "|---|---|",
        f"| In both | {result['shared']:,} |",
        f"| New in the candidate | {result['added']:,} |",
        f"| Gone from the candidate | {result['removed']:,} |",
        f"| Score went down | {result['score_changes']['down']:,} |",
        f"| Score went up | {result['score_changes']['up']:,} |",
        f"| Blocking reason changed | {result['column_changes']['blocking_reason']:,} |",
        f"| Score status changed | {result['column_changes']['quality_score_status']:,} |", "",
        "## Catalog safety changes", "",
        "Safety uses product_safety_status only: BLOCKED > UNSAFE > CAUTION > no catalog concern. "
        "Quality ratings appear in the separate table below; a quality change cannot change safety.", "",
    ]
    stops = {"milder": "yes, unless approved", "stricter": "no (stricter)", "none": "no: safety severity unchanged"}
    if result["verdict_transitions"]:
        lines += ["| Change | Products | Stops the release? |", "|---|---|---|"]
        lines += [f"| {t['from']} → {t['to']} | {t['products']:,} | {stops[t['safety']]} |"
                  for t in result["verdict_transitions"]]
    else:
        lines.append("No product changed catalog safety status.")
    lines += ["", "## Quality grade changes", ""]
    if result["tier_transitions"]:
        lines += ["| Change | Products | Also has a safety exception |",
                  "|---|---|---|"]
        for t in result["tier_transitions"]:
            stop = f"{t['stopping']:,}"
            lines.append(f"| {t['from']} → {t['to']} | {t['products']:,} | {stop} |")
    else:
        lines.append("No product changed grade.")
    for side, name in (("removed_by_verdict", "Gone"), ("added_by_verdict", "New")):
        if result[side]:
            lines += ["", f"{name} products by catalog safety status: "
                      + ", ".join(f"{v} {n:,}" for v, n in sorted(result[side].items()))]

    lines += ["", f"## Quality movements — report-only ({len(result['reported']):,} products)", ""]
    for kind in KINDS:
        rows = [c for c in result["reported"] if c["kind"] == kind]
        if rows:
            lines += [f"### {KIND_TITLES[kind]} ({len(rows):,})", "", *_table(rows, False), ""]
    lines += ["", f"## Safety exceptions needing approval ({len(unapproved):,} products)", ""]
    if not unapproved:
        lines.append("Nothing.")
    for kind in KINDS:
        rows = [c for c in unapproved if c["kind"] == kind]
        if rows:
            lines += [f"### {KIND_TITLES[kind]} ({len(rows):,})", "", *_table(rows, False), ""]
    if approved:
        lines += [f"## Already approved ({len(approved):,})", "", *_table(approved, True), ""]
    if result["stale_approvals"]:
        lines += [f"## Approvals that match nothing in this comparison ({len(result['stale_approvals']):,})", "",
                  "They were written for another release and can be deleted.", ""]
        lines += [f"- {a['dsld_id']}: {_state_text(a['from'])} → {_state_text(a['to'])}"
                  for a in result["stale_approvals"]]
        lines.append("")
    lines += ["## How to approve", "",
              "Investigate safety exceptions by shared cause, retaining the exact affected products and "
              "before/after states in each reviewed group. Ordinary quality movements need no signatures. "
              "To accept reviewed safety exceptions, copy their groups from the draft "
              f"approvals file into `{APPROVALS_PATH.relative_to(SCRIPTS_DIR.parent)}`, fill in `reason`, "
              "`approved_by` and `date` (YYYY-MM-DD), commit, and rerun the release. An approval covers "
              "only the exact before and after it names.", ""]
    return "\n".join(lines)


def draft_approvals(results: dict | list[dict]) -> dict:
    """The unapproved changes as approval groups, one per kind, still unsigned."""
    seen, groups = set(), {}
    for result in results if isinstance(results, list) else [results]:
        for c in result["gated"]:
            if c["approval"] is None and _key(c) not in seen:
                seen.add(_key(c))
                groups.setdefault(c["kind"], []).append({
                    "dsld_id": c["dsld_id"], "from": c["from"], "to": c["to"],
                    "product_name": c["product_name"], "why": "; ".join(r["text"] for r in c["reasons"]),
                })
    return {"approvals": [{"reason": "", "approved_by": "", "date": "", "changes": groups[k]}
                          for k in KINDS if k in groups]}


def _bundled_baseline(flutter_repo: Path) -> tuple[Path, dict]:
    """The app's bundled catalog, proven to be the one committed on its main branch."""
    snapshot = read_flutter_bundle_manifest(flutter_repo)
    db = flutter_repo / BUNDLED_DB
    if not db.is_file():
        raise ValueError(f"App catalog not found: {db}")
    digest = _sha256(db)
    if digest != snapshot.db_checksum_sha256:
        raise ValueError(
            f"{db} is not the catalog committed on {snapshot.branch} ({snapshot.commit_sha[:12]}): "
            f"its sha256 {digest[:12]} differs from the committed manifest's "
            f"{str(snapshot.db_checksum_sha256)[:12]}. Restore it with "
            f"`git -C \"{flutter_repo}\" checkout {snapshot.branch} -- {BUNDLED_DB}` "
            "(and `git lfs pull`), then rerun.")
    return db, {"db_version": snapshot.db_version, "source": "app bundle"}


def _live_baseline(bundle_sha256: str, workdir: Path) -> tuple[Path, dict] | None:
    """The catalog the in-app updater downloads, when it is not the bundled one."""
    client = get_supabase_client()
    current = fetch_current_manifest(client)
    if not current or not current.get("db_version") or not current.get("checksum"):
        raise ValueError(f"Supabase has no current catalog row with db_version and checksum: {current!r}")
    if current["checksum"] == f"sha256:{bundle_sha256}":
        return None
    db = workdir / "live_pharmaguide_core.db"
    db.write_bytes(client.storage.from_(STORAGE_BUCKET).download(core_db_remote_path(current["db_version"])))
    if f"sha256:{_sha256(db)}" != current["checksum"]:
        raise ValueError(f"Live catalog {current['db_version']} does not match its manifest checksum")
    return db, {"db_version": current["db_version"], "source": "live catalog on Supabase"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--flutter-repo", required=True, type=Path)
    parser.add_argument("--candidate-db", required=True, type=Path)
    parser.add_argument("--approvals", type=Path, default=APPROVALS_PATH)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--draft-approvals", required=True, type=Path)
    args = parser.parse_args(argv)
    # Never leave an earlier run's verdict behind for this run's reader.
    args.report.unlink(missing_ok=True)
    args.draft_approvals.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory() as workdir:
        try:
            approvals = load_approvals(args.approvals)
            baselines = [_bundled_baseline(args.flutter_repo)]
        except (BundleAlignmentError, ValueError, OSError) as exc:
            print(f"catalog diff: cannot compare: {exc}", file=sys.stderr)
            return 2
        try:
            live = _live_baseline(_sha256(baselines[0][0]), Path(workdir))
        except Exception as exc:  # network, credentials, storage: all fail closed
            print(f"catalog diff: cannot read the live catalog users download: {type(exc).__name__}: {exc}",
                  file=sys.stderr)
            return 2
        if live:
            baselines.append(live)
        else:
            print("catalog diff: the live Supabase catalog is the app bundle; one comparison")
        try:
            results = []
            for db, info in baselines:
                results.append(diff_catalogs(db, args.candidate_db, approvals))
                results[-1]["baseline"].update(info)
        except (ValueError, OSError, sqlite3.Error) as exc:
            print(f"catalog diff: cannot compare: {exc}", file=sys.stderr)
            return 2

    # An approval is stale only when it matches nothing in any comparison.
    stale = [a for a in results[0]["stale_approvals"]
             if all(any(_key(a) == _key(b) for b in r["stale_approvals"]) for r in results)]
    for result in results:
        result["stale_approvals"] = stale
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n\n---\n\n".join(render_markdown(r) for r in results), encoding="utf-8")

    unapproved = 0
    for r in results:
        base = r["baseline"]
        print(f"catalog diff vs {base['source']} {base['db_version']} ({base['products']:,} products) → "
              f"candidate ({r['candidate']['products']:,}): {r['shared']:,} in both, {r['added']:,} new, "
              f"{r['removed']:,} gone")
        counts = Counter(c["kind"] for c in r["gated"] if c["approval"] is None)
        if counts:
            print("  unapproved: " + ", ".join(f"{kind} {counts[kind]:,}" for kind in KINDS if counts[kind]))
        unapproved += r["unapproved"]
    print(f"  report: {args.report}")
    if stale:
        print(f"  {len(stale)} approval(s) match nothing in this diff and can be deleted")
    if not unapproved:
        print("  catalog comparison passed; other gates and publication authorization still apply")
        return 0
    args.draft_approvals.parent.mkdir(parents=True, exist_ok=True)
    args.draft_approvals.write_text(json.dumps(draft_approvals(results), indent=2) + "\n", encoding="utf-8")
    print(f"  STOP: {unapproved:,} unapproved product change(s). Review the report, then complete and "
          f"commit approvals from: {args.draft_approvals}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
