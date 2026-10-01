#!/usr/bin/env python3
"""Release gate: what changes for app users between the app's catalog and the candidate.

Compares the candidate catalog with the one the app ships (the Flutter bundle
committed on main), product by product. A change that weakens what a user is
told stops the release unless a reviewed approval names that exact change:

    milder_verdict  the verdict moves down PUBLIC_VERDICT_PRECEDENCE (POOR -> SAFE)
    removed         a product whose verdict was above SAFE leaves the catalog, so
                    a scan answers "not found" where it used to warn
    score_drop      the score falls by SCORE_DROP_LIMIT points or more

Stricter verdicts, new products and score rises are reported, never gated.
Approvals live in catalog_change_approvals.json; every group needs a reason,
an approver and a date. On a stop the gate writes a draft of the missing
approvals for the reviewer to complete.

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
import sqlite3
import sys
from collections import Counter
from datetime import date
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from release_safety.bundle_alignment import BundleAlignmentError, read_flutter_bundle_manifest  # noqa: E402
from scoring_v4.scored_artifact import PUBLIC_VERDICT_PRECEDENCE  # noqa: E402

APPROVALS_PATH = Path(__file__).with_name("catalog_change_approvals.json")
BUNDLED_DB = Path("assets/db/pharmaguide_core.db")
KINDS = ("milder_verdict", "removed", "score_drop")
#: A 10-point fall on the /100 scale is a full grade step.
SCORE_DROP_LIMIT = 10.0
COLUMNS = ("dsld_id", "product_name", "brand_name", "verdict",
           "quality_score_v4_100", "quality_score_status", "blocking_reason")
RISES_SHOWN = 20


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


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
    products = {}
    for values in rows:
        product = dict(zip(COLUMNS, values))
        if product["verdict"] not in PUBLIC_VERDICT_PRECEDENCE:
            raise ValueError(f"{db}: product {product['dsld_id']} has unknown verdict {product['verdict']!r}")
        products[str(product["dsld_id"])] = product
    return products


def _rank(verdict: str) -> int:
    """Higher is more restrictive."""
    return len(PUBLIC_VERDICT_PRECEDENCE) - PUBLIC_VERDICT_PRECEDENCE.index(verdict)


def _score(value) -> float | None:
    return None if value is None else round(float(value), 1)


def _key(change: dict) -> tuple:
    value = lambda v: _score(v) if isinstance(v, (int, float)) else v  # noqa: E731
    return str(change["dsld_id"]), change["kind"], value(change["from"]), value(change["to"])


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
            if not isinstance(change, dict) or not {"dsld_id", "kind", "from", "to"} <= change.keys():
                raise ValueError(f"{where}: each change needs dsld_id, kind, from and to: {change!r}")
            if change["kind"] not in KINDS:
                raise ValueError(f"{where}: unknown kind {change['kind']!r}; use one of {', '.join(KINDS)}")
    return groups


def diff_catalogs(baseline_db: Path, candidate_db: Path, approvals: list[dict]) -> dict:
    """Compare two catalogs; the result is plain JSON for reports and the gate."""
    before, after = _products(Path(baseline_db)), _products(Path(candidate_db))
    shared = before.keys() & after.keys()
    removed = before.keys() - after.keys()
    added = after.keys() - before.keys()

    gated, transitions, rises = [], Counter(), []
    score_changes = {"down": 0, "up": 0}
    column_changes = {"blocking_reason": 0, "quality_score_status": 0}

    def gate(product: dict, kind: str, old, new):
        gated.append({
            "dsld_id": str(product["dsld_id"]), "product_name": product["product_name"],
            "brand_name": product["brand_name"], "kind": kind, "from": old, "to": new,
        })

    for pid in sorted(shared):
        old, new = before[pid], after[pid]
        for column in column_changes:
            column_changes[column] += old[column] != new[column]
        if old["verdict"] != new["verdict"]:
            transitions[(old["verdict"], new["verdict"])] += 1
            if _rank(new["verdict"]) < _rank(old["verdict"]):
                gate(new, "milder_verdict", old["verdict"], new["verdict"])
        old_score, new_score = _score(old["quality_score_v4_100"]), _score(new["quality_score_v4_100"])
        if old_score is None or new_score is None or old_score == new_score:
            continue
        change = round(new_score - old_score, 1)
        score_changes["down" if change < 0 else "up"] += 1
        if -change >= SCORE_DROP_LIMIT:
            gate(new, "score_drop", old_score, new_score)
        elif change > 0:
            rises.append({"dsld_id": pid, "product_name": new["product_name"],
                          "brand_name": new["brand_name"], "from": old_score, "to": new_score})
    for pid in sorted(removed):
        if before[pid]["verdict"] != "SAFE":
            gate(before[pid], "removed", before[pid]["verdict"], None)

    approved = {}
    for group in approvals:
        for change in group["changes"]:
            approved[_key(change)] = (change, group)
    for change in gated:
        match = approved.pop(_key(change), None)
        change["approval"] = None if match is None else {
            k: match[1][k] for k in ("reason", "approved_by", "date")}

    order = {kind: i for i, kind in enumerate(KINDS)}

    def severity(change):
        if change["kind"] == "score_drop":
            return change["to"] - change["from"]
        return -_rank(change["from"])
    gated.sort(key=lambda c: (order[c["kind"]], severity(c), c["dsld_id"]))
    rises.sort(key=lambda r: (r["from"] - r["to"], r["dsld_id"]))

    return {
        "baseline": {"path": str(baseline_db), "sha256": _sha256(Path(baseline_db)), "products": len(before)},
        "candidate": {"path": str(candidate_db), "sha256": _sha256(Path(candidate_db)), "products": len(after)},
        "shared": len(shared),
        "added": len(added),
        "removed": len(removed),
        "added_by_verdict": dict(Counter(after[p]["verdict"] for p in added)),
        "removed_by_verdict": dict(Counter(before[p]["verdict"] for p in removed)),
        "verdict_transitions": [
            {"from": old, "to": new, "products": n, "milder": _rank(new) < _rank(old)}
            for (old, new), n in sorted(transitions.items(), key=lambda t: (-t[1], t[0]))
        ],
        "score_changes": score_changes,
        "column_changes": column_changes,
        "score_drop_limit": SCORE_DROP_LIMIT,
        "gated": gated,
        "unapproved": sum(c["approval"] is None for c in gated),
        "stale_approvals": [{k: c[k] for k in ("dsld_id", "kind", "from", "to")} for c, _ in approved.values()],
        "biggest_rises": rises[:RISES_SHOWN],
    }


KIND_TITLES = {
    "milder_verdict": "Verdicts that got milder",
    "removed": "Products with a warning that left the catalog (a scan would say \"not found\")",
    "score_drop": f"Scores that dropped {SCORE_DROP_LIMIT:g} points or more",
}


def _change_text(change: dict) -> str:
    if change["kind"] == "score_drop":
        return f"{change['from']:g} → {change['to']:g} ({change['to'] - change['from']:+.1f})"
    if change["kind"] == "removed":
        return f"{change['from']} → not in catalog"
    return f"{change['from']} → {change['to']}"


def _row(cells: list) -> str:
    return "| " + " | ".join(" ".join(str(x or "").split()).replace("|", "/") for x in cells) + " |"


def _table(changes: list[dict], with_approval: bool) -> list[str]:
    head = "| DSLD ID | Product | Brand | Change |" + (" Approved by | Reason |" if with_approval else "")
    lines = [head, "|" + "---|" * head.count(" |")]
    for c in changes:
        cells = [c["dsld_id"], c["product_name"], c["brand_name"], _change_text(c)]
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
        verdict = (f"**STOPS THE RELEASE: {len(unapproved)} change(s) nobody has approved yet** ("
                   + ", ".join(f"{counts[k]} {KIND_TITLES[k].split(' (')[0].lower()}" for k in KINDS if counts[k]) + ").")
    else:
        verdict = "**Release can proceed:** nothing weakens what users are told, or every such change is approved."

    def label(side):
        version = f"{side['db_version']}, " if side.get("db_version") else ""
        return f"`{side['path']}` ({version}{side['products']:,} products, sha256 {side['sha256'][:12]})"

    lines = [
        "# Catalog changes: app bundle → release candidate", "",
        f"- App bundle (what users have now): {label(base)}",
        f"- Release candidate: {label(cand)}", "",
        verdict, "",
        "## Summary", "",
        "| | Products |", "|---|---|",
        f"| In both | {result['shared']:,} |",
        f"| New in the candidate | {result['added']:,} |",
        f"| Gone from the candidate | {result['removed']:,} |",
        f"| Score went down | {result['score_changes']['down']:,} |",
        f"| Score went up | {result['score_changes']['up']:,} |",
        f"| Blocking reason changed | {result['column_changes']['blocking_reason']:,} |",
        f"| Score status changed | {result['column_changes']['quality_score_status']:,} |", "",
        "## Verdict changes", "",
    ]
    if result["verdict_transitions"]:
        lines += ["| Change | Products | Stops the release? |", "|---|---|---|"]
        lines += [f"| {t['from']} → {t['to']} | {t['products']:,} | {'yes, unless approved' if t['milder'] else 'no (stricter)'} |"
                  for t in result["verdict_transitions"]]
    else:
        lines.append("No product changed verdict.")
    for side, name in (("removed_by_verdict", "Gone"), ("added_by_verdict", "New")):
        if result[side]:
            lines += ["", f"{name} products by verdict: "
                      + ", ".join(f"{v} {n:,}" for v, n in sorted(result[side].items()))]

    lines += ["", f"## Needs approval ({len(unapproved):,})", ""]
    if not unapproved:
        lines.append("Nothing.")
    for kind in KINDS:
        rows = [c for c in unapproved if c["kind"] == kind]
        if rows:
            lines += [f"### {KIND_TITLES[kind]} ({len(rows):,})", "", *_table(rows, False), ""]
    if approved:
        lines += [f"## Already approved ({len(approved):,})", "", *_table(approved, True), ""]
    if result["stale_approvals"]:
        lines += [f"## Approvals that match nothing in this diff ({len(result['stale_approvals']):,})", "",
                  "They were written for another release and can be deleted.", ""]
        lines += [f"- {a['dsld_id']} {a['kind']}: {a['from']} → {a['to']}" for a in result["stale_approvals"]]
        lines.append("")
    if result["biggest_rises"]:
        lines += [f"## Biggest score rises (report only, top {RISES_SHOWN})", "",
                  "| DSLD ID | Product | Brand | Change |", "|---|---|---|---|"]
        lines += [_row([r["dsld_id"], r["product_name"], r["brand_name"],
                        f"{r['from']:g} → {r['to']:g} ({r['to'] - r['from']:+.1f})"])
                  for r in result["biggest_rises"]]
        lines.append("")
    lines += ["## How to approve", "",
              f"Review each change above. To let reviewed changes ship, copy their groups from the draft "
              f"approvals file into `{APPROVALS_PATH.relative_to(SCRIPTS_DIR.parent)}`, fill in `reason`, "
              "`approved_by` and `date` (YYYY-MM-DD), commit, and rerun the release. An approval covers only "
              "the exact change it names.", ""]
    return "\n".join(lines)


def draft_approvals(result: dict) -> dict:
    """The unapproved changes as approval groups, one per kind, still unsigned."""
    groups = []
    for kind in KINDS:
        changes = [{k: c[k] for k in ("dsld_id", "kind", "from", "to", "product_name")}
                   for c in result["gated"] if c["kind"] == kind and c["approval"] is None]
        if changes:
            groups.append({"reason": "", "approved_by": "", "date": "", "changes": changes})
    return {"approvals": groups}


def _bundled_baseline(flutter_repo: Path) -> tuple[Path, dict]:
    """The app's catalog, proven to be the one committed on its main branch."""
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
    return db, {"db_version": snapshot.db_version, "commit": snapshot.commit_sha}


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

    try:
        baseline, bundle = _bundled_baseline(args.flutter_repo)
        result = diff_catalogs(baseline, args.candidate_db, load_approvals(args.approvals))
    except (BundleAlignmentError, ValueError, OSError, sqlite3.Error) as exc:
        print(f"catalog diff: cannot compare: {exc}", file=sys.stderr)
        return 2
    result["baseline"].update(bundle)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_markdown(result), encoding="utf-8")
    print(f"catalog diff: app bundle {bundle['db_version']} ({result['baseline']['products']:,} products) "
          f"→ candidate ({result['candidate']['products']:,} products): {result['shared']:,} in both, "
          f"{result['added']:,} new, {result['removed']:,} gone")
    for t in result["verdict_transitions"]:
        print(f"  {t['from']} → {t['to']}: {t['products']:,}{'  (milder)' if t['milder'] else ''}")
    print(f"  report: {args.report}")
    if result["stale_approvals"]:
        print(f"  {len(result['stale_approvals'])} approval(s) match nothing in this diff and can be deleted")
    if not result["unapproved"]:
        print("  nothing unapproved weakens what users are told")
        return 0
    args.draft_approvals.parent.mkdir(parents=True, exist_ok=True)
    args.draft_approvals.write_text(json.dumps(draft_approvals(result), indent=2) + "\n", encoding="utf-8")
    counts = Counter(c["kind"] for c in result["gated"] if c["approval"] is None)
    print(f"  STOP: {result['unapproved']:,} unapproved change(s): "
          + ", ".join(f"{kind} {counts[kind]:,}" for kind in KINDS if counts[kind]))
    print(f"  review the report, then complete and commit approvals from: {args.draft_approvals}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
