"""
Audit script: inactive-ingredient safety gap detector.

Runs three independent checks against any build directory:

  CHECK 1 — Banned in inactives, no safety signal
    Every standard_name + alias in banned_recalled_ingredients.json
    (excluding match_mode in {disabled, historical}) MUST produce a
    safety signal when it appears in inactive_ingredients[]. If a
    matching inactive row has is_safety_concern=False AND is_banned=False
    AND severity_status='n/a', that's a silent ship — a blocker.

  CHECK 2 — Notes-only match catcher (false-positive risk)
    Spot-check a small set of high-risk strings that only appear in
    NOTES / DESCRIPTION text of source entries (e.g. 'genotoxicity',
    'nanoparticle'). The resolver must NOT match these to any source.

  CHECK 3 — Unknown inactive roles
    Inactive ingredients where matched_source is None AND
    display_role_label is None — neither classified nor labelled.
    These are upstream data-gap follow-ups (cleaner / other_ingredients
    entries needed). Counted, top-N reported, NEVER fail the build.

Run:
  python3 scripts/audit_inactive_safety.py \
      --build-dir /tmp/pharmaguide_release_build_inactives \
      --out reports/audit_inactive_safety.json

Exit codes:
  0 — clean (no banned-in-inactive gaps, no notes-only matches)
  1 — CHECK 1 or CHECK 2 failed (gap detected)
  2 — script error
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

from inactive_ingredient_resolver import InactiveIngredientResolver, _normalize  # noqa


# Notes-only strings: tokens that appear in editorial text of source
# entries but should NEVER be label names. The resolver must not return
# any match for these. Bleed-through here means we're indexing notes/
# mechanism_of_harm/safety_summary by mistake.
NOTES_ONLY_PROBES = (
    "genotoxicity",
    "nanoparticle",
    "EFSA Journal",
    "regulatory enforcement",
    "carcinogenic risk",
    "DNA damage",
    "intestinal absorption",
)


def _scan_build(build_dir: Path) -> list[dict]:
    """Yield every inactive_ingredient entry across the build, with
    its product dsld_id attached."""
    blob_dir = build_dir / "detail_blobs"
    if not blob_dir.is_dir():
        raise SystemExit(f"build_dir {build_dir} has no detail_blobs/")
    rows = []
    for p in sorted(blob_dir.glob("*.json")):
        try:
            b = json.loads(p.read_text())
        except Exception:
            continue
        did = b.get("dsld_id") or p.stem
        for ing in b.get("inactive_ingredients") or []:
            if isinstance(ing, dict):
                rows.append({"dsld_id": did, "ing": ing})
    return rows


def check_banned_in_inactives_have_safety_signal(
    rows: list[dict], resolver: InactiveIngredientResolver
) -> tuple[list[dict], int]:
    """CHECK 1. For every inactive whose name matches a banned_recalled
    rule, verify the blob carries the right safety signal. Returns
    (violations, total_banned_inactives_seen)."""
    # Build the same banned-name set the resolver uses.
    banned_names: set[str] = set()
    banned_status_by_name: dict[str, str] = {}
    for e in resolver.iter_banned_recalled_entries_for_audit():
        for n in [e.get("standard_name")] + (e.get("aliases") or []):
            if not isinstance(n, str):
                continue
            key = _normalize(n)
            if key:
                banned_names.add(key)
                banned_status_by_name[key] = (e.get("status") or "").lower()

    violations = []
    banned_seen = 0
    for r in rows:
        ing = r["ing"]
        terms = [
            _normalize(ing.get("name")),
            _normalize(ing.get("raw_source_text")),
            _normalize(ing.get("standard_name")),
        ]
        matched_status: str = ""
        for t in terms:
            if t and t in banned_names:
                matched_status = banned_status_by_name[t]
                break
        if not matched_status:
            continue
        banned_seen += 1
        # This inactive matches a banned_recalled rule. Verify safety
        # signal is appropriately set.
        severity = ing.get("severity_status")
        is_sc = bool(ing.get("is_safety_concern"))
        is_banned = bool(ing.get("is_banned"))
        matched_source = ing.get("matched_source")

        # Expected severity by status:
        if matched_status == "watchlist":
            expected_severity = "informational"
            expected_safety_concern = False
        else:
            # banned / high_risk / recalled
            expected_severity = "critical"
            expected_safety_concern = True

        # Banned-flag check: only status=banned should set is_banned=True
        expected_is_banned = matched_status == "banned"

        problems = []
        if severity != expected_severity:
            problems.append(f"severity_status={severity!r} (expected {expected_severity!r})")
        if is_sc != expected_safety_concern:
            problems.append(f"is_safety_concern={is_sc!r} (expected {expected_safety_concern!r})")
        if is_banned != expected_is_banned:
            problems.append(f"is_banned={is_banned!r} (expected {expected_is_banned!r})")
        if matched_source != "banned_recalled":
            problems.append(f"matched_source={matched_source!r} (expected 'banned_recalled')")

        if problems:
            violations.append({
                "dsld_id": r["dsld_id"],
                "ingredient_name": ing.get("name") or ing.get("raw_source_text"),
                "matched_banned_status": matched_status,
                "problems": problems,
            })
    return violations, banned_seen


def check_no_notes_only_matches(
    resolver: InactiveIngredientResolver,
) -> list[dict]:
    """CHECK 2. Each probe string lives only in notes/description text
    of some source entry. resolver.resolve() must return matched_source
    None — otherwise we're indexing editorial text."""
    violations = []
    for probe in NOTES_ONLY_PROBES:
        r = resolver.resolve(raw_name=probe)
        if r.matched_source is not None:
            violations.append({
                "probe": probe,
                "matched_source": r.matched_source,
                "matched_rule_id": r.matched_rule_id,
            })
    return violations


def check_unknown_inactive_roles(rows: list[dict]) -> dict:
    """CHECK 3. Count + report inactives where the resolver returned
    matched_source=None AND display_role_label is None. These are
    upstream gaps (cleaner / other_ingredients entries missing).
    Informational only — never fails the build."""
    unknown_counter: collections.Counter[str] = collections.Counter()
    for r in rows:
        ing = r["ing"]
        if ing.get("matched_source") is None and not ing.get("display_role_label"):
            name = (ing.get("name") or ing.get("raw_source_text") or "?").strip()
            unknown_counter[name] += 1
    return {
        "total_unknown_inactives": sum(unknown_counter.values()),
        "distinct_names": len(unknown_counter),
        "top_50": unknown_counter.most_common(50),
    }


def check_matched_source_distribution(rows: list[dict]) -> dict:
    """CHECK 4 (informational). Distribution of matched_source across
    all inactives. Useful for tracking the architectural fix's impact
    over time."""
    c = collections.Counter()
    severity_c = collections.Counter()
    for r in rows:
        ing = r["ing"]
        src = ing.get("matched_source") or "<unmatched>"
        c[src] += 1
        severity_c[ing.get("severity_status") or "<missing>"] += 1
    return {
        "by_matched_source": dict(c),
        "by_severity_status": dict(severity_c),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build-dir", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()

    print(f"[audit_inactive_safety] scanning {args.build_dir}", file=sys.stderr)
    resolver = InactiveIngredientResolver()
    rows = _scan_build(args.build_dir)
    print(f"[audit_inactive_safety] {len(rows)} inactive entries across "
          f"{len({r['dsld_id'] for r in rows})} products", file=sys.stderr)

    # CHECK 1 — banned in inactives have safety signal
    banned_violations, banned_seen = check_banned_in_inactives_have_safety_signal(rows, resolver)

    # CHECK 2 — notes-only probes
    notes_violations = check_no_notes_only_matches(resolver)

    # CHECK 3 — unknown roles (informational)
    unknown = check_unknown_inactive_roles(rows)

    # CHECK 4 — source distribution (informational)
    distribution = check_matched_source_distribution(rows)

    report = {
        "schema": "audit_inactive_safety_v1",
        "build_dir": str(args.build_dir),
        "summary": {
            "total_inactive_entries": len(rows),
            "banned_in_inactives_seen": banned_seen,
            "banned_signal_violations": len(banned_violations),
            "notes_only_false_positives": len(notes_violations),
            "unknown_inactive_roles_total": unknown["total_unknown_inactives"],
            "unknown_distinct_names": unknown["distinct_names"],
        },
        "check_1_banned_signal_violations": banned_violations,
        "check_2_notes_only_false_positives": notes_violations,
        "check_3_unknown_inactive_roles": unknown,
        "check_4_source_distribution": distribution,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    print(f"[audit_inactive_safety] wrote {args.out}", file=sys.stderr)

    # Verdict
    print("\n--- AUDIT VERDICT ---")
    print(f"  total inactive entries:               {len(rows)}")
    print(f"  banned-in-inactive entries:           {banned_seen}")
    print(f"  CHECK 1 (banned signal violations):   {len(banned_violations)}")
    print(f"  CHECK 2 (notes-only false positives): {len(notes_violations)}")
    print(f"  CHECK 3 (unknown inactive roles):     {unknown['total_unknown_inactives']} "
          f"({unknown['distinct_names']} distinct names)")
    print(f"  source distribution: {distribution['by_matched_source']}")

    fail = len(banned_violations) > 0 or len(notes_violations) > 0
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
