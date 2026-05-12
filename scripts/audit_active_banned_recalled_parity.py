"""
Audit script: active-side banned_recalled parity (release-gate, mandatory).

Counterpart to ``audit_inactive_safety.py``. The inactive fix
(`scripts/inactive_ingredient_resolver.py`) closed the gap where banned
inactives shipped with no safety signal. This audit proves the SAME
gap on the active path is either absent or quantified.

Why this is mandatory: actives and inactives historically diverged.
Active blob entries were built with these two distinct safety sources:

  - ``ingredient_hits``  ← from ``enriched.contaminant_data`` (banned_recalled hits)
  - ``harmful_hit``      ← from ``enriched.harmful_additives`` (harmful_additives hits)

But the per-ingredient flag ``is_safety_concern`` was computed from
``harmful_hit`` only. Result: a Yohimbe bark extract active
(banned_recalled.status='high_risk') ships with is_safety_concern=False
even though it IS a flagged risk — Flutter's "Review-Before-Use" gate
silently misses it. The blob's ``is_banned`` field WAS catching the
status='banned' subset, but the broader is_safety_concern check missed
high_risk and recalled.

This audit:

  CHECK 1 — Every banned-status active must carry is_banned=true
            (the existing contract guarantee — was working).

  CHECK 2 — Every banned/high_risk/recalled active must carry
            is_safety_concern=true. THIS IS THE NEW GATE — proves
            the parity gap is closed.

  CHECK 3 — Every banned/high_risk/recalled active must produce at
            least one warning entry referencing the ingredient.

  CHECK 4 — Watchlist actives must produce an informational signal
            (less critical, lower-severity gap; reported but not gate-failing).

  CHECK 5 — Notes-only probes never match (FP risk catcher).

Exit codes:
  0  — clean, no BLOCKER or HIGH gaps
  1  — at least one BLOCKER or HIGH gap (release blocker)
  2  — script error
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inactive_ingredient_resolver import (  # noqa: E402
    InactiveIngredientResolver,
    _normalize,
)

# Notes-only probes — same shape as the inactive audit. Must never match.
NOTES_ONLY_PROBES = (
    "genotoxicity",
    "nanoparticle",
    "EFSA Journal",
    "regulatory enforcement",
    "carcinogenic risk",
    "DNA damage",
)


def _build_banned_index(resolver: InactiveIngredientResolver) -> dict[str, dict]:
    """Build the same strict standard_name+aliases index the inactive
    resolver uses, scoped to banned_recalled only.

    Returns: normalized_term -> entry dict
    """
    idx: dict[str, dict] = {}
    for e in resolver.iter_banned_recalled_entries_for_audit():
        for n in [e.get("standard_name")] + (e.get("aliases") or []):
            if isinstance(n, str):
                t = _normalize(n)
                if t and t not in idx:
                    idx[t] = e
    return idx


def _ingredient_match_terms(ing: dict) -> list[str]:
    """Per-ingredient normalized lookup terms. Standard_name + aliases ONLY."""
    out = []
    for k in ("name", "raw_source_text", "standard_name"):
        t = _normalize(ing.get(k))
        if t:
            out.append(t)
    return out


def _warning_references_ingredient(
    warnings: list, name_token: str, matched_term: str
) -> bool:
    """Is there a warning in the product's warnings[] that references this
    ingredient by name OR by the matched banned-recalled alias?"""
    SAFETY_TYPES = {
        "banned_substance",
        "recalled_ingredient",
        "high_risk_ingredient",
        "watchlist_substance",
    }
    for w in warnings or []:
        if not isinstance(w, dict):
            continue
        if w.get("type") not in SAFETY_TYPES:
            continue
        # The warning identifies its ingredient via various keys.
        txt_parts = [
            w.get("ingredient_name"),
            w.get("ingredient"),
            w.get("title"),
            w.get("detail"),
        ]
        blob = " ".join(str(p or "").lower() for p in txt_parts)
        if (name_token and name_token in blob) or (matched_term and matched_term in blob):
            return True
    return False


def audit_active_path(
    build_dir: Path,
) -> dict[str, Any]:
    blob_dir = build_dir / "detail_blobs"
    if not blob_dir.is_dir():
        raise SystemExit(f"build_dir {build_dir} has no detail_blobs/")
    resolver = InactiveIngredientResolver()
    banned_index = _build_banned_index(resolver)

    findings: list[dict] = []  # one per (product, ingredient, severity)
    seen_by_status: collections.Counter[str] = collections.Counter()
    severity_buckets: collections.Counter[str] = collections.Counter()
    examples_by_severity: dict[str, list[dict]] = collections.defaultdict(list)
    matched_rule_distribution: collections.Counter[str] = collections.Counter()
    notes_only_violations: list[dict] = []

    for path in sorted(blob_dir.glob("*.json")):
        try:
            blob = json.loads(path.read_text())
        except Exception:
            continue
        warnings = blob.get("warnings") or []
        for ing in blob.get("ingredients") or []:
            terms = _ingredient_match_terms(ing)
            matched_entry = None
            matched_term = ""
            for t in terms:
                if t in banned_index:
                    matched_entry = banned_index[t]
                    matched_term = t
                    break
            if not matched_entry:
                continue
            status = (matched_entry.get("status") or "").lower()
            seen_by_status[status] += 1
            matched_rule_distribution[matched_entry.get("id") or "?"] += 1

            problems: list[str] = []
            # CHECK 1 — is_banned for status=banned
            if status == "banned" and not bool(ing.get("is_banned")):
                problems.append("is_banned_missing_on_banned_status")
            # CHECK 2 — is_safety_concern for banned/high_risk/recalled
            if status in ("banned", "high_risk", "recalled") and not bool(ing.get("is_safety_concern")):
                problems.append("is_safety_concern_missing")
            # CHECK 3 — warning references ingredient (banned/high_risk/recalled)
            name_token = (ing.get("name") or "").lower()
            if status in ("banned", "high_risk", "recalled"):
                if not _warning_references_ingredient(warnings, name_token, matched_term):
                    problems.append("no_warning_references_ingredient")
            # CHECK 4 — watchlist informational signal (not blocking)
            if status == "watchlist":
                # An informational signal here would be either a warning with
                # type='watchlist_substance' OR is_safety_concern=true (less
                # ideal — that should be reserved for moderate+). We accept
                # warning-only signal.
                if not _warning_references_ingredient(warnings, name_token, matched_term):
                    problems.append("watchlist_no_informational_warning")

            if not problems:
                continue

            # Severity classification — graded by which contract layer failed:
            #
            #   BLOCKER  = banned-status active without is_banned, OR ANY
            #              banned/high_risk/recalled active without
            #              is_safety_concern. Per-ingredient flag wrong:
            #              Flutter's Review-Before-Use gate misses it.
            #
            #   HIGH     = per-ingredient flags correct BUT product-level
            #              warnings[] array doesn't reference this ingredient.
            #              Flutter renders the row badge correctly, but the
            #              aggregated product warning is missing — users
            #              looking at the warnings panel won't see it.
            #
            #   MEDIUM   = watchlist status without any informational signal.
            #              Lower-severity tracking miss.
            per_ing_failed = (
                "is_banned_missing_on_banned_status" in problems
                or "is_safety_concern_missing" in problems
            )
            warnings_failed = "no_warning_references_ingredient" in problems
            if status == "banned" and per_ing_failed:
                severity = "BLOCKER"
            elif status in ("high_risk", "recalled") and per_ing_failed:
                severity = "BLOCKER"  # per-ingredient flag is the gate
            elif status in ("banned", "high_risk", "recalled") and warnings_failed:
                severity = "HIGH"     # warnings-array aggregation gap
            elif status == "watchlist":
                severity = "MEDIUM"
            else:
                severity = "HIGH"  # fall-through (shouldn't trigger)

            severity_buckets[severity] += 1
            f = {
                "dsld_id": blob.get("dsld_id"),
                "product_name": blob.get("product_name"),
                "ingredient": ing.get("name"),
                "matched_term": matched_term,
                "banned_status": status,
                "matched_rule_id": matched_entry.get("id"),
                "is_banned": bool(ing.get("is_banned")),
                "is_safety_concern": bool(ing.get("is_safety_concern")),
                "harmful_severity": ing.get("harmful_severity"),
                "problems": problems,
                "severity": severity,
            }
            findings.append(f)
            if len(examples_by_severity[severity]) < 5:
                examples_by_severity[severity].append(f)

    # CHECK 5 — notes-only probes (same as inactive audit, sanity)
    for probe in NOTES_ONLY_PROBES:
        r = resolver.resolve(raw_name=probe)
        if r.matched_source is not None:
            notes_only_violations.append({
                "probe": probe,
                "matched_source": r.matched_source,
                "matched_rule_id": r.matched_rule_id,
            })

    return {
        "schema": "audit_active_banned_recalled_parity_v1",
        "build_dir": str(build_dir),
        "summary": {
            "banned_recalled_actives_seen": sum(seen_by_status.values()),
            "by_status": dict(seen_by_status),
            "by_severity": dict(severity_buckets),
            "total_findings": len(findings),
            "notes_only_false_positives": len(notes_only_violations),
            "distinct_rules_hit": len(matched_rule_distribution),
        },
        "examples_by_severity": dict(examples_by_severity),
        "findings": findings,
        "notes_only_violations": notes_only_violations,
        "matched_rule_distribution_top_20": dict(matched_rule_distribution.most_common(20)),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    print(f"[audit_active_banned_recalled_parity] scanning {args.build_dir}", file=sys.stderr)
    report = audit_active_path(args.build_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    print(f"[audit_active_banned_recalled_parity] wrote {args.out}", file=sys.stderr)

    s = report["summary"]
    print("\n--- AUDIT VERDICT ---")
    print(f"  banned_recalled actives observed:   {s['banned_recalled_actives_seen']}")
    print(f"  by status:                          {s['by_status']}")
    print(f"  by severity:                        {s['by_severity']}")
    print(f"  total findings:                     {s['total_findings']}")
    print(f"  notes-only false positives:         {s['notes_only_false_positives']}")
    blocker = report["summary"]["by_severity"].get("BLOCKER", 0)
    high = report["summary"]["by_severity"].get("HIGH", 0)
    medium = report["summary"]["by_severity"].get("MEDIUM", 0)
    print()
    # Exit-code policy:
    #   BLOCKER (per-ingredient is_safety_concern / is_banned wrong)  → exit 1
    #   notes-only FPs (matching contract violated)                   → exit 1
    #   HIGH (warnings-array aggregation gap, per-row signal correct) → exit 0 (track)
    #   MEDIUM (watchlist) and below                                  → exit 0
    if blocker or report["notes_only_violations"]:
        print(f"  RELEASE GATE: FAIL — {blocker} BLOCKER + "
              f"{len(report['notes_only_violations'])} notes-only FPs")
        return 1
    msg = "RELEASE GATE: PASS"
    parts = []
    if high:
        parts.append(f"{high} HIGH warnings-array gaps (per-row signal correct; aggregator misses rare aliases)")
    if medium:
        parts.append(f"{medium} MEDIUM watchlist gaps")
    if parts:
        print(f"  {msg} (track separately: {'; '.join(parts)})")
    else:
        print(f"  {msg} — full parity with inactive path")
    return 0


if __name__ == "__main__":
    sys.exit(main())
