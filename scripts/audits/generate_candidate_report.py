#!/usr/bin/env python3
"""Generate the scoring-integrity candidate report from the artifacts.

Both the human-readable markdown and the machine-readable JSON come out of this
one script, read from the built catalog, the git heads and a verification
results file. Nothing is typed by hand, so the two cannot disagree with each
other or with the artifact they describe.

Usage:
    python3 scripts/audits/generate_candidate_report.py \
        --dist scripts/dist \
        --baseline-db /path/to/shipped/pharmaguide_core.db \
        --flutter-repo "/path/to/PharmaGuide ai/.worktrees/<branch>" \
        --verification docs/release_candidates/verification_results.json \
        --out-md docs/release_candidates/scoring_readiness_candidate_2026_08_22.md \
        --out-json docs/release_candidates/scoring_integrity_candidate_2026_08_22.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

REQUIRED_VERIFICATION_GATES = (
    "full_corpus_pipeline",
    "pipeline_fast_suite",
    "pipeline_release_suite",
    "pipeline_full_suite",
    "flutter_analyze",
    "flutter_suite",
    "interaction_parity",
    "candidate_import_preflight",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repo: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return ""


def _head_is_pushed(repo: Path) -> bool:
    return bool(_git(repo, "branch", "-r", "--contains", "HEAD"))


def _validated_verification(path: Path) -> dict:
    """Load command evidence and reject hand-typed green summaries.

    A pytest count alone is not a successful release command: the runner can
    fail in a later audit, which is exactly what happened in the first 2.4
    candidate.  Every required gate therefore records the complete command's
    exit code and a preserved log whose hash is calculated here.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    gates = payload.get("gates")
    if not isinstance(gates, dict):
        raise ValueError("verification file must contain a gates object")
    for name in REQUIRED_VERIFICATION_GATES:
        gate = gates.get(name)
        if not isinstance(gate, dict):
            raise ValueError(f"verification missing required gate: {name}")
        if gate.get("exit_code") != 0:
            raise ValueError(
                f"verification gate {name} did not pass: "
                f"exit_code={gate.get('exit_code')!r}"
            )
        log_value = gate.get("log")
        log_path = Path(str(log_value or ""))
        if not log_value or not log_path.is_file():
            raise ValueError(f"verification gate {name} has no preserved log")
        gate["log_sha256"] = _sha256(log_path)
    payload["verification_file_sha256"] = _sha256(path)
    return payload


def _artifact_hashes(dist: Path) -> dict:
    paths = {
        "candidate_database_sha256": dist / "pharmaguide_core.db",
        "export_manifest_sha256": dist / "export_manifest.json",
        "detail_index_sha256": dist / "detail_index.json",
        "interaction_database_sha256": dist / "interaction_db.sqlite",
        "interaction_database_manifest_sha256": dist / "interaction_db_manifest.json",
    }
    return {
        name: _sha256(path)
        for name, path in paths.items()
        if path.is_file()
    }


def _counts(db: Path, column: str) -> dict:
    con = sqlite3.connect(str(db))
    try:
        cols = {r[1] for r in con.execute("pragma table_info(products_core)")}
        if column not in cols:
            return {}
        return {
            str(k): v
            for k, v in sorted(
                con.execute(
                    f"select {column}, count(*) from products_core group by 1"
                )
            )
        }
    finally:
        con.close()


def _product_count(db: Path) -> int:
    con = sqlite3.connect(str(db))
    try:
        return con.execute("select count(*) from products_core").fetchone()[0]
    finally:
        con.close()


def _quarantine(manifest: dict) -> dict:
    groups: dict[str, int] = {}
    ids: dict[str, list[str]] = {}
    for entry in manifest.get("excluded_by_gate") or []:
        err = str(entry.get("error") or "")
        reason = re.search(r"reason=([a-z_]+)", err)
        dims = re.search(r"incomplete_dimensions=([a-z_,]+)", err)
        key = reason.group(1) if reason else "unknown"
        if dims:
            key = f"{key}:{dims.group(1)}"
        groups[key] = groups.get(key, 0) + 1
        ids.setdefault(key, []).append(str(entry.get("dsld_id")))
    return {"total": sum(groups.values()), "groups": dict(sorted(groups.items()))}


def _shared_diff(baseline: Path, candidate: Path) -> dict:
    def rows(db: Path) -> tuple[dict, set]:
        con = sqlite3.connect(str(db))
        try:
            cols = [r[1] for r in con.execute("pragma table_info(products_core)")]
            wanted = [c for c in ("dsld_id", "verdict", "blocking_reason",
                                  "quality_score_status") if c in cols]
            data = {
                str(r[0]): dict(zip(wanted, r))
                for r in con.execute(f"select {','.join(wanted)} from products_core")
            }
            return data, set(wanted)
        finally:
            con.close()

    base, base_cols = rows(baseline)
    cand, cand_cols = rows(candidate)
    common = sorted((base_cols & cand_cols) - {"dsld_id"})
    shared = set(base) & set(cand)
    changed = {c: 0 for c in common}
    for pid in shared:
        for col in common:
            if base[pid].get(col) != cand[pid].get(col):
                changed[col] += 1
    return {
        "shared": len(shared),
        "added_live": len(set(cand) - set(base)),
        "removed_live": len(set(base) - set(cand)),
        "comparable_columns": common,
        "changed": changed,
    }


def _policy_holds() -> list[dict]:
    path = REPO / "scripts" / "data" / "banned_recalled_ingredients.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for entry in payload.get("ingredients") or []:
        hold = entry.get("pending_us_policy_signoff") if isinstance(entry, dict) else None
        if isinstance(hold, dict):
            out.append({
                "rule_id": entry.get("id"),
                "held_status": hold.get("previous_status"),
                "proposed_status": hold.get("proposed_status"),
                "affected_live_products": hold.get("affected_live_products"),
                "approved": bool(hold.get("approved")),
                "packet": hold.get("packet"),
            })
    return out


def _withheld_clinical() -> dict:
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    from build_medication_depletions_artifact import build_artifact
    from sync_flutter_reference_data import publishable_timing_rules

    data = REPO / "scripts" / "data"
    dep = build_artifact(
        json.loads((data / "medication_depletions.json").read_text()),
        content_version="report",
    )["_metadata"]
    tim = publishable_timing_rules(
        json.loads((data / "timing_rules.json").read_text())
    )["_metadata"]
    return {
        "medication_depletions": {
            "published": dep["total_entries"],
            "withheld": dep["withheld_entries"],
            "withheld_by_review_status": dep["withheld_by_review_status"],
        },
        "timing_rules": {
            "published": tim["total_entries"],
            "withheld": tim["withheld_entries"],
            "withheld_by_review_status": tim["withheld_by_review_status"],
        },
    }


def _manifest_report_date(manifest: dict) -> str:
    """Return the candidate build date from the canonical manifest timestamp.

    Schema 2.4 manifests publish ``generated_at``.  ``exported_at`` remains a
    migration-boundary fallback for older candidate artifacts.
    """
    timestamp = manifest.get("generated_at") or manifest.get("exported_at")
    return str(timestamp or "unknown")[:10]


def build_report(args) -> dict:
    dist = Path(args.dist)
    db = dist / "pharmaguide_core.db"
    manifest = json.loads((dist / "export_manifest.json").read_text())

    report = {
        "report_schema_version": "2.0.0",
        "report_name": "PharmaGuide scoring integrity 2.4 candidate",
        "report_date": _manifest_report_date(manifest),
        "candidate_status": "technically_verified_preproduction_not_approved_for_publish",
        "generated_by": "scripts/audits/generate_candidate_report.py",
        "repositories": {
            "pipeline": {
                "source_head_at_generation": _git(REPO, "rev-parse", "HEAD"),
                "branch": _git(REPO, "rev-parse", "--abbrev-ref", "HEAD"),
                "merge_base_origin_main": _git(REPO, "merge-base", "origin/main", "HEAD"),
                "dirty": bool(_git(REPO, "status", "--porcelain")),
                "source_head_pushed": _head_is_pushed(REPO),
            },
        },
        "release_contract": {
            "export_schema_version": manifest.get("schema_version"),
            "scoring_version": manifest.get("scoring_version"),
            "pipeline_version": manifest.get("pipeline_version"),
            "db_version": manifest.get("db_version"),
        },
        "artifact_hashes": _artifact_hashes(dist),
        "candidate": {
            "live_product_count": _product_count(db),
            "detail_blob_count": len(list((dist / "detail_blobs").glob("*.json"))),
            "core_database_bytes": db.stat().st_size,
            "verdict_counts": _counts(db, "verdict"),
            "quality_score_status_counts": _counts(db, "quality_score_status"),
            "product_safety_status_counts": _counts(db, "product_safety_status"),
        },
        "quarantine": _quarantine(manifest),
        "pending_clinical_signoff": {
            "us_policy_holds": _policy_holds(),
            "withheld_clinical_records": _withheld_clinical(),
        },
        "publication_boundary": {
            "production_published": False,
            "supabase_uploaded": False,
            "flutter_candidate_assets_imported": bool(
                getattr(args, "flutter_candidate_assets_imported", False)
            ),
            "actual_publish_owner": "operator",
        },
    }

    if args.flutter_repo:
        fr = Path(args.flutter_repo)
        report["repositories"]["flutter"] = {
            "source_head_at_generation": _git(fr, "rev-parse", "HEAD"),
            "branch": _git(fr, "rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(_git(fr, "status", "--porcelain")),
            "source_head_pushed": _head_is_pushed(fr),
        }
    if args.baseline_db:
        baseline = Path(args.baseline_db)
        report["baseline"] = {
            "database_sha256": _sha256(baseline),
            "product_count": _product_count(baseline),
        }
        report["baseline_candidate_diff"] = _shared_diff(baseline, db)
    if args.verification:
        report["verification"] = _validated_verification(Path(args.verification))

    body = {k: v for k, v in report.items() if k != "integrity"}
    canon = json.dumps(body, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    report["integrity"] = {
        "algorithm": "sha256",
        "scope": "canonical JSON excluding integrity",
        "signature_type": "self-integrity hash; not an identity signature",
        "sha256": hashlib.sha256(canon.encode("utf-8")).hexdigest(),
    }
    return report


def _counts_text(counts: dict) -> str:
    return ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))


def render_markdown(r: dict) -> str:
    pipe = r["repositories"]["pipeline"]
    flut = r["repositories"].get("flutter") or {}
    cand = r["candidate"]
    lines = [
        f"# Scoring integrity 2.4 candidate — {r['report_date']}",
        "",
        "Status: **technically verified preproduction candidate; "
        "not approved, not published**",
        "",
        "Generated by `scripts/audits/generate_candidate_report.py` from the built",
        "artifact and the generation-time source heads. The report commit itself",
        "can be later. Do not hand-edit: regenerate.",
        "",
        "## Heads",
        "",
        f"- pipeline `{pipe['branch']}` @ `{pipe['source_head_at_generation'][:12]}`"
        f"{' (dirty)' if pipe['dirty'] else ''}",
    ]
    if flut:
        lines.append(
            f"- flutter `{flut['branch']}` @ `{flut['source_head_at_generation'][:12]}`"
            f"{' (dirty)' if flut['dirty'] else ''}"
        )
    contract = r["release_contract"]
    lines += [
        "",
        "## Candidate",
        "",
        "| Measure | Value |",
        "|---|---:|",
        f"| Export schema | {contract['export_schema_version']} |",
        f"| Scoring version | {contract['scoring_version']} |",
        f"| DB version | {contract['db_version']} |",
        f"| Live products | {cand['live_product_count']} |",
        f"| Detail blobs | {cand['detail_blob_count']} |",
        f"| Quarantined | {r['quarantine']['total']} |",
        "",
        f"Database SHA-256: `{r['artifact_hashes']['candidate_database_sha256']}`",
        "",
        "### Verdicts",
        "",
        "| Verdict | Products |",
        "|---|---:|",
    ]
    for verdict, count in cand["verdict_counts"].items():
        lines.append(f"| {verdict} | {count} |")

    lines += ["", "### Quarantine", "", "| Reason | Products |", "|---|---:|"]
    for key, count in r["quarantine"]["groups"].items():
        lines.append(f"| `{key}` | {count} |")

    lines += [
        "",
        "Every quarantined product is excluded from the app catalog. These are",
        "remediation backlog, not completed work.",
        "",
        "## Awaiting clinical sign-off",
        "",
    ]
    holds = r["pending_clinical_signoff"]["us_policy_holds"]
    if holds:
        lines += [
            "| Rule | Held at | Proposed | Live products | Approved |",
            "|---|---|---|---:|---|",
        ]
        for hold in holds:
            lines.append(
                f"| `{hold['rule_id']}` | {hold['held_status']} | "
                f"{hold['proposed_status']} | {hold['affected_live_products']} | "
                f"{'yes' if hold['approved'] else '**no**'} |"
            )
    else:
        # An empty table reads as a missing section rather than as "nothing is
        # held", which is the actual and load-bearing fact.
        lines.append(
            "No safety rule is held. `pending_us_policy_signoff` exists and is "
            "tested; the two findings that were investigated as policy "
            "transitions, and why neither is one, are in "
            "`safety_signoff_packet_2026_08_22.md`."
        )
        safety_review_products = sum(
            count
            for reason, count in r["quarantine"]["groups"].items()
            if reason.startswith("safety_policy_review_required")
        )
        if safety_review_products:
            lines.append(
                f"{safety_review_products} products remain conservatively "
                "quarantined for an explicit operator policy disposition; "
                "none are present in the app catalog."
            )
    withheld = r["pending_clinical_signoff"]["withheld_clinical_records"]
    lines += [
        "",
        "Unreviewed clinical guidance is withheld from the bundle entirely:",
        "",
        f"- `medication_depletions`: {withheld['medication_depletions']['published']} "
        f"published, {withheld['medication_depletions']['withheld']} withheld "
        f"({_counts_text(withheld['medication_depletions']['withheld_by_review_status'])})",
        f"- `timing_rules`: {withheld['timing_rules']['published']} published, "
        f"{withheld['timing_rules']['withheld']} withheld "
        f"({_counts_text(withheld['timing_rules']['withheld_by_review_status'])})",
        "",
    ]

    if "baseline_candidate_diff" in r:
        d = r["baseline_candidate_diff"]
        lines += [
            "## Against the shipped baseline",
            "",
            f"- shared products: {d['shared']}",
            f"- added live: {d['added_live']}",
            f"- removed live: {d['removed_live']}",
            "",
            "Changes on shared products, over the columns present in both schemas "
            f"({', '.join(d['comparable_columns'])}):",
            "",
        ]
        for col, count in d["changed"].items():
            lines.append(f"- `{col}`: {count}")
        lines.append("")

    if "verification" in r:
        lines += ["## Verification", ""]
        for name, result in r["verification"].items():
            lines.append(f"- **{name}**: {json.dumps(result)}")
        lines.append("")

    lines += [
        "## Publication boundary",
        "",
        "No Supabase upload, no production merge, no store release, and no remote",
        "cleanup. Candidate branch pushes and local app-asset verification do not",
        "publish production. Publication is a separately",
        "authorized operator action.",
        "",
        f"Report self-integrity SHA-256: `{r['integrity']['sha256']}`",
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", required=True)
    ap.add_argument("--baseline-db")
    ap.add_argument("--flutter-repo")
    ap.add_argument("--verification")
    ap.add_argument("--flutter-candidate-assets-imported", action="store_true")
    ap.add_argument("--out-md", required=True, type=Path)
    ap.add_argument("--out-json", required=True, type=Path)
    args = ap.parse_args(argv)

    report = build_report(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.out_md.write_text(render_markdown(report), encoding="utf-8")
    print(f"wrote {args.out_md}")
    print(f"wrote {args.out_json}")
    print(f"integrity sha256: {report['integrity']['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
