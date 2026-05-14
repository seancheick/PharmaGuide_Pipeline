#!/usr/bin/env python3
from __future__ import annotations
"""
UNII data-quality audit for PharmaGuide reference files.

What this script does:
  Read-only audit that surfaces UNII conflicts BEFORE the UNII-first match
  path (Sprint 1) ships. The matcher uses UNII as a primary identity anchor;
  any wrong UNII in reference data would propagate deterministically.
  Running this audit first lets us catch and fix data-quality bugs before
  they become amplified.

Findings reported (no edits, report only):
  - DUPLICATE_UNII_CROSS_FILE — same UNII appears in entries across two
    different reference files (e.g., IQM and other_ingredients). Higher-
    priority tier will win at runtime, but the same chemistry shouldn't
    be modeled in two files simultaneously.
  - SAME_UNII_DIFFERENT_NAMES — one UNII maps to entries with different
    `standard_name`s (e.g., "glucose" and "dextrose"). Suspicious — likely
    one entry has the wrong UNII.
  - SAME_NAME_DIFFERENT_UNIIS — one `standard_name` appears with different
    UNIIs across files. Either source-form differences (e.g. amylopectin-
    corn vs amylopectin-wheat) or a data bug.
  - FDA_CACHE_NAME_MISMATCH — entry's UNII looks up to a name in
    `fda_unii_cache.unii_to_name` that does NOT match the entry's
    `standard_name` or any alias. Flag for human review.

Output:
  reports/unii_data_quality_<timestamp>.md — markdown report with one
  section per finding type, listing affected entry IDs with file paths.

Operator runbook:
  python3 scripts/api_audit/audit_unii_data_quality.py
  python3 scripts/api_audit/audit_unii_data_quality.py --output-dir reports/

Exit codes:
  0 — audit completed; report written
  1 — audit found warnings (cross-file duplicates, name mismatches);
      review the report before trusting UNII-first matching at scale
  2 — audit found critical conflicts (same UNII pointing to different
      compounds); MUST fix before Sprint 1 ships
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Files to audit. Each entry: (path, list_key | None for top-level-dict)
REFERENCE_FILES = [
    ("scripts/data/ingredient_quality_map.json", None),  # top-level dict-of-dicts
    ("scripts/data/botanical_ingredients.json", "botanical_ingredients"),
    ("scripts/data/other_ingredients.json", "other_ingredients"),
    ("scripts/data/standardized_botanicals.json", "standardized_botanicals"),
]

_PLACEHOLDER_UNIIS = frozenset({"", "0", "1"})


def _normalize_unii(value: Any) -> Optional[str]:
    """Canonicalize a UNII string. Returns None for placeholders/garbage.

    FDA UNIIs are exactly 10 alphanumeric characters. We strip whitespace,
    uppercase, and reject DSLD's placeholder values (`"0"`, `"1"`, `""`).
    """
    if not isinstance(value, str):
        return None
    canon = value.strip().upper()
    if not canon or canon in _PLACEHOLDER_UNIIS:
        return None
    if len(canon) != 10 or not canon.isalnum():
        return None
    return canon


def _extract_entry_unii(entry: Dict) -> Optional[str]:
    """Extract a UNII from a reference entry. Checks external_ids.unii and
    top-level unii (older format). Returns normalized UNII or None."""
    if not isinstance(entry, dict):
        return None
    eid = entry.get("external_ids") or {}
    if isinstance(eid, dict):
        u = _normalize_unii(eid.get("unii"))
        if u:
            return u
    return _normalize_unii(entry.get("unii"))


def _load_iqm_entries(blob: Dict) -> List[Tuple[str, Dict]]:
    """IQM is a top-level dict-of-dicts (parent_key → entry).
    Skip _metadata-style entries (keys starting with _)."""
    return [(k, v) for k, v in blob.items() if not k.startswith("_") and isinstance(v, dict)]


def _load_list_entries(blob: Dict, list_key: str) -> List[Tuple[str, Dict]]:
    """Standard list-shaped reference files. Returns (entry_id, entry_dict)."""
    arr = blob.get(list_key, [])
    if not isinstance(arr, list):
        return []
    out = []
    for e in arr:
        if not isinstance(e, dict):
            continue
        eid = e.get("id") or e.get("standard_name") or f"<unnamed-{id(e)}>"
        out.append((eid, e))
    return out


def load_reference_data(repo_root: Path) -> List[Tuple[str, str, Dict]]:
    """Return list of (file_label, entry_id, entry_dict) across all reference files."""
    out: List[Tuple[str, str, Dict]] = []
    for rel_path, list_key in REFERENCE_FILES:
        path = repo_root / rel_path
        if not path.exists():
            print(f"[warn] missing file: {path}", file=sys.stderr)
            continue
        with open(path, encoding="utf-8") as f:
            blob = json.load(f)
        file_label = Path(rel_path).name
        if list_key is None:
            entries = _load_iqm_entries(blob)
        else:
            entries = _load_list_entries(blob, list_key)
        for eid, edict in entries:
            out.append((file_label, eid, edict))
    return out


def load_fda_unii_cache(repo_root: Path) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Returns (name_to_unii, unii_to_name) maps from fda_unii_cache.json.
    Both maps are lowercased on keys to match cache convention."""
    cache_path = repo_root / "scripts/data/fda_unii_cache.json"
    if not cache_path.exists():
        print(f"[warn] missing fda_unii_cache.json — FDA_CACHE_NAME_MISMATCH check skipped", file=sys.stderr)
        return {}, {}
    with open(cache_path, encoding="utf-8") as f:
        blob = json.load(f)
    return blob.get("name_to_unii", {}), blob.get("unii_to_name", {})


def load_exoneration_allowlist(repo_root: Path) -> Dict[str, Dict[str, Any]]:
    """Load scripts/data/unii_exoneration_allowlist.json into {UNII → entry}.
    Returns empty dict if the file doesn't exist (allowlist is optional —
    the test suite enforces its existence and contract independently)."""
    path = repo_root / "scripts/data/unii_exoneration_allowlist.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        blob = json.load(f)
    return {
        entry["unii"].strip().upper(): entry
        for entry in blob.get("exonerations", [])
        if isinstance(entry, dict) and entry.get("unii")
    }


def build_unii_to_fda_names(name_to_unii: Dict[str, str]) -> Dict[str, set]:
    """Inverse the name_to_unii map: UNII → set of all FDA names that resolve
    to it. Used to check if an entry's names match the FDA's known synonyms
    for that UNII (legitimate-synonym detection)."""
    inverse: Dict[str, set] = defaultdict(set)
    for name, unii in name_to_unii.items():
        if isinstance(unii, str):
            inverse[unii.strip().upper()].add(name.strip().lower())
    return inverse


def _extract_entry_cui(entry: Dict) -> Optional[str]:
    """Extract a UMLS CUI from a reference entry. Checks both flat `cui` and
    nested `external_ids.cui` / `external_ids.umls_cui`. Returns the CUI or None.

    Note: entries can have `cui_status='governed_null'` meaning intentional
    no-CUI; we still return None for those (no CUI to compare against)."""
    if not isinstance(entry, dict):
        return None
    if entry.get("cui_status") == "governed_null":
        return None
    direct = entry.get("cui")
    if isinstance(direct, str) and direct.strip():
        return direct.strip().upper()
    eid = entry.get("external_ids") or {}
    if isinstance(eid, dict):
        for key in ("cui", "umls_cui"):
            v = eid.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip().upper()
    return None


def _collect_entry_name_tokens(entry: Dict) -> set:
    """Return a set of all name-strings (standard_name + aliases) lowercased
    and stripped of parenthetical/comma decoration, for matching against the
    FDA cache's known names for a given UNII."""
    out: set = set()
    if not isinstance(entry, dict):
        return out

    def clean(s: str) -> str:
        s = re.sub(r"\([^)]*\)", " ", s.lower())
        s = re.sub(r",\s*", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    for raw in [entry.get("standard_name")] + (entry.get("aliases") or []):
        if isinstance(raw, str) and raw.strip():
            cleaned = clean(raw)
            if cleaned:
                out.add(cleaned)
    return out


def find_duplicate_unii_cross_file(
    entries: List[Tuple[str, str, Dict]],
) -> Dict[str, List[Tuple[str, str, str]]]:
    """Returns {unii: [(file, entry_id, standard_name), ...]} for UNIIs that
    appear in 2+ DIFFERENT files."""
    by_unii: Dict[str, List[Tuple[str, str, str]]] = defaultdict(list)
    for file_label, eid, edict in entries:
        unii = _extract_entry_unii(edict)
        if unii:
            std = edict.get("standard_name", eid)
            by_unii[unii].append((file_label, eid, std))
    # Keep only UNIIs spanning 2+ distinct files
    return {
        u: locations
        for u, locations in by_unii.items()
        if len({loc[0] for loc in locations}) >= 2
    }


def find_same_unii_different_names(
    entries: List[Tuple[str, str, Dict]],
    unii_to_fda_names: Optional[Dict[str, set]] = None,
    exoneration_allowlist: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Returns {unii: {locations, severity, exoneration}} for UNIIs that
    map to entries with materially different `standard_name`s.

    Refined classification (per user direction 2026-05-14):
      Severity escalates only when NONE of these synonym-exoneration signals apply:
        a) Substring-related names (e.g., 'Vitamin C' / 'Vitamin C, ascorbic acid')
        b) FDA cache confirms at least 2 of the entry names are in the UNII's
           known FDA synonym set
        c) Entries share a UMLS CUI (same compound by clinical authority)
        d) Explicit exoneration allowlist entry (scripts/data/unii_exoneration_allowlist.json)

    Output shape per UNII:
      {
        "locations": [(file, entry_id, standard_name, cui), ...],
        "severity": "critical" | "review" | "allowlist_exonerated",
        "exoneration": list of strings explaining why severity is not 'critical',
      }
    """
    unii_to_fda_names = unii_to_fda_names or {}
    exoneration_allowlist = exoneration_allowlist or {}
    by_unii: Dict[str, List[Tuple[str, str, str, Optional[str], Dict]]] = defaultdict(list)
    for file_label, eid, edict in entries:
        unii = _extract_entry_unii(edict)
        if unii:
            std = edict.get("standard_name", eid)
            cui = _extract_entry_cui(edict)
            by_unii[unii].append((file_label, eid, std, cui, edict))

    flagged: Dict[str, Dict[str, Any]] = {}
    for unii, locations in by_unii.items():
        if len(locations) < 2:
            continue
        names = [loc[2].strip().lower() for loc in locations]
        uniq = list({n for n in names})
        if len(uniq) < 2:
            continue

        # Signal A: substring-related
        def related(a: str, b: str) -> bool:
            return a in b or b in a
        unrelated = any(
            not related(uniq[i], uniq[j])
            for i in range(len(uniq))
            for j in range(i + 1, len(uniq))
        )
        if not unrelated:
            continue  # substring-related, not flagged at all

        # Signal B: FDA cache synonym exoneration
        fda_known_names = unii_to_fda_names.get(unii, set())
        entries_matching_fda = 0
        for _, _, _, _, edict in locations:
            tokens = _collect_entry_name_tokens(edict)
            if tokens & fda_known_names:
                entries_matching_fda += 1

        # Signal C: shared UMLS CUI
        cuis = {loc[3] for loc in locations if loc[3]}
        shared_cui = len(cuis) == 1 and len(locations) >= 2 and all(
            loc[3] == list(cuis)[0] for loc in locations if loc[3]
        )

        exoneration: List[str] = []
        if entries_matching_fda >= 2:
            exoneration.append(
                f"FDA cache confirms {entries_matching_fda}/{len(locations)} entry "
                f"names appear in UNII's FDA synonym list (legitimate synonyms)"
            )
        if shared_cui:
            exoneration.append(f"All entries share UMLS CUI {list(cuis)[0]}")

        # Signal D: explicit allowlist (HIGHEST priority — overrides all others)
        allowlist_entry = exoneration_allowlist.get(unii)
        if allowlist_entry:
            exoneration.append(
                f"Allowlisted (unii_exoneration_allowlist.json): "
                f"{allowlist_entry.get('rationale','(no rationale)')[:200]}"
            )
            severity = "allowlist_exonerated"
        elif exoneration:
            severity = "review"
        else:
            severity = "critical"

        flagged[unii] = {
            "locations": [(loc[0], loc[1], loc[2], loc[3]) for loc in locations],
            "severity": severity,
            "exoneration": exoneration,
        }
    return flagged


def find_same_name_different_uniis(
    entries: List[Tuple[str, str, Dict]],
) -> Dict[str, List[Tuple[str, str, str]]]:
    """Returns {normalized_name: [(file, entry_id, unii), ...]} for names
    appearing with 2+ different UNIIs.

    NOTE: legitimate source-form differences exist (e.g., amylopectin has
    8 source-specific UNIIs). We flag the cluster so a human can confirm
    whether each entry is intentionally using its source-specific UNII.
    """
    by_name: Dict[str, List[Tuple[str, str, str]]] = defaultdict(list)
    for file_label, eid, edict in entries:
        unii = _extract_entry_unii(edict)
        if not unii:
            continue
        std = (edict.get("standard_name") or eid).strip().lower()
        if not std:
            continue
        by_name[std].append((file_label, eid, unii))
    return {
        nm: locations
        for nm, locations in by_name.items()
        if len({loc[2] for loc in locations}) >= 2
    }


def find_fda_cache_name_mismatches(
    entries: List[Tuple[str, str, Dict]],
    unii_to_name: Dict[str, str],
) -> List[Tuple[str, str, str, str, str]]:
    """Returns [(file, entry_id, our_unii, our_standard_name, fda_cache_name), ...]
    where an entry's UNII looks up to a name in FDA cache that does NOT match
    the entry's standard_name or any alias (case-insensitive, substring-fuzzy).
    """
    if not unii_to_name:
        return []
    out = []
    for file_label, eid, edict in entries:
        unii = _extract_entry_unii(edict)
        if not unii:
            continue
        fda_name = unii_to_name.get(unii)
        if not fda_name:
            continue
        std = (edict.get("standard_name") or eid).strip().lower()
        aliases = [a.strip().lower() for a in (edict.get("aliases") or []) if isinstance(a, str)]
        candidates = [std] + aliases
        # Strip common parenthetical / source qualifiers from FDA name and entry names
        # before substring comparison
        def simplify(s: str) -> str:
            s = re.sub(r"\([^)]*\)", " ", s.lower())
            s = re.sub(r",\s*", " ", s)
            s = re.sub(r"\s+", " ", s).strip()
            return s

        fda_simplified = simplify(fda_name)
        matched = False
        for cand in candidates:
            if not cand:
                continue
            cs = simplify(cand)
            if cs == fda_simplified:
                matched = True
                break
            if cs and (cs in fda_simplified or fda_simplified in cs):
                matched = True
                break
        if not matched:
            out.append((file_label, eid, unii, edict.get("standard_name", eid), fda_name))
    return out


def render_report(
    duplicate_cross_file: Dict[str, List[Tuple[str, str, str]]],
    same_unii_diff_names: Dict[str, Dict[str, Any]],
    same_name_diff_uniis: Dict[str, List[Tuple[str, str, str]]],
    fda_mismatches: List[Tuple[str, str, str, str, str]],
    total_entries: int,
    entries_with_unii: int,
) -> str:
    """Render the markdown report."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines: List[str] = []
    # Split same_unii_diff_names into critical, review-exonerated, and allowlist-exonerated buckets
    critical_same_unii = {k: v for k, v in same_unii_diff_names.items() if v["severity"] == "critical"}
    review_same_unii = {k: v for k, v in same_unii_diff_names.items() if v["severity"] == "review"}
    allowlist_same_unii = {k: v for k, v in same_unii_diff_names.items() if v["severity"] == "allowlist_exonerated"}

    lines.append("# UNII Data-Quality Audit Report")
    lines.append("")
    lines.append(f"Generated: {now}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total reference entries scanned: **{total_entries}**")
    lines.append(f"- Entries carrying a UNII: **{entries_with_unii}** ({entries_with_unii/total_entries*100:.1f}%)" if total_entries else "")
    lines.append("")
    lines.append("| Finding type | Count | Severity |")
    lines.append("|---|---|---|")
    lines.append(f"| DUPLICATE_UNII_CROSS_FILE | {len(duplicate_cross_file)} | warn |")
    lines.append(f"| SAME_UNII_DIFFERENT_NAMES (critical) | {len(critical_same_unii)} | **critical** |")
    lines.append(f"| SAME_UNII_DIFFERENT_NAMES (exonerated by FDA/CUI) | {len(review_same_unii)} | review |")
    lines.append(f"| SAME_UNII_DIFFERENT_NAMES (allowlist-exonerated) | {len(allowlist_same_unii)} | info |")
    lines.append(f"| SAME_NAME_DIFFERENT_UNIIS | {len(same_name_diff_uniis)} | review |")
    lines.append(f"| FDA_CACHE_NAME_MISMATCH | {len(fda_mismatches)} | review |")
    lines.append("")

    def _section_for_dict(
        title: str,
        rationale: str,
        data: Dict[str, List[Tuple[str, str, str]]],
        key_label: str = "UNII",
    ) -> None:
        lines.append(f"## {title}")
        lines.append("")
        lines.append(rationale)
        lines.append("")
        if not data:
            lines.append("_None found._")
            lines.append("")
            return
        for key, locations in sorted(data.items()):
            lines.append(f"### {key_label}: `{key}`")
            for file_label, eid, third in locations:
                lines.append(f"- `{file_label}` → `{eid}` ({third})")
            lines.append("")

    _section_for_dict(
        "DUPLICATE_UNII_CROSS_FILE",
        "Same UNII appears in entries across two or more reference files. "
        "The matcher's priority order resolves this at runtime, but the "
        "same chemistry should not be modeled in two places. Review and "
        "consolidate to a single authoritative entry.",
        duplicate_cross_file,
        key_label="UNII",
    )

    # SAME_UNII_DIFFERENT_NAMES — render critical and review buckets separately
    def _render_same_unii_diff_names_bucket(
        title: str, rationale: str, bucket: Dict[str, Dict[str, Any]]
    ) -> None:
        lines.append(f"## {title}")
        lines.append("")
        lines.append(rationale)
        lines.append("")
        if not bucket:
            lines.append("_None found._")
            lines.append("")
            return
        for unii, info in sorted(bucket.items()):
            lines.append(f"### UNII: `{unii}`")
            for file_label, eid, std_name, cui in info["locations"]:
                cui_str = f", CUI={cui}" if cui else ""
                lines.append(f"- `{file_label}` → `{eid}` ({std_name}{cui_str})")
            if info["exoneration"]:
                lines.append(f"  - Exoneration: {'; '.join(info['exoneration'])}")
            lines.append("")

    _render_same_unii_diff_names_bucket(
        "SAME_UNII_DIFFERENT_NAMES (critical)",
        "**CRITICAL** — a single FDA UNII maps to entries whose `standard_name`s "
        "are materially different AND no exoneration signal applies (FDA cache "
        "synonyms, shared UMLS CUI). One of these entries likely has a wrong "
        "UNII. MUST fix before Sprint 1 UNII-first matching ships.",
        critical_same_unii,
    )
    _render_same_unii_diff_names_bucket(
        "SAME_UNII_DIFFERENT_NAMES (review — exonerated by FDA cache / CUI)",
        "Same UNII across entries with different names, BUT at least one "
        "exoneration signal applies (FDA cache confirms the names as legitimate "
        "synonyms, or all entries share a UMLS CUI). Review to confirm; runtime "
        "priority order (banned > IQM > botanical > other) resolves correctly.",
        review_same_unii,
    )
    _render_same_unii_diff_names_bucket(
        "SAME_UNII_DIFFERENT_NAMES (allowlist-exonerated)",
        "Same UNII across entries with different names, BUT the UNII is in the "
        "explicit exoneration allowlist (`scripts/data/unii_exoneration_allowlist.json`). "
        "Each allowlist entry carries rationale + FDA canonical name + regression "
        "test coverage. These satisfy the pre-Sprint-1 blocker rule and do NOT "
        "block Sprint 1 from shipping.",
        allowlist_same_unii,
    )

    _section_for_dict(
        "SAME_NAME_DIFFERENT_UNIIS",
        "Same `standard_name` appears across files carrying different "
        "UNIIs. May be legitimate (source-form variants like amylopectin-"
        "corn vs amylopectin-wheat) or a data bug — human review needed.",
        same_name_diff_uniis,
        key_label="Name",
    )

    # FDA cache mismatches section
    lines.append("## FDA_CACHE_NAME_MISMATCH")
    lines.append("")
    lines.append(
        "Entry's UNII resolves in `fda_unii_cache.json` to a name that does "
        "NOT match the entry's `standard_name` or any alias (case-"
        "insensitive, substring-fuzzy after stripping parens and commas). "
        "Common cause: source-form variant (e.g., entry says 'Phenylalanine' "
        "but UNII is for 'L-Phenylalanine'). Review individually."
    )
    lines.append("")
    if not fda_mismatches:
        lines.append("_None found._")
    else:
        lines.append("| File | Entry ID | UNII | Our standard_name | FDA cache name |")
        lines.append("|---|---|---|---|---|")
        for file_label, eid, unii, our_name, fda_name in sorted(fda_mismatches):
            lines.append(f"| `{file_label}` | `{eid}` | `{unii}` | {our_name} | {fda_name} |")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only UNII data-quality audit. Surfaces duplicates, "
            "conflicts, and FDA-cache mismatches BEFORE the UNII-first "
            "match path is enabled."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--output-dir",
        default="reports",
        help="Where to write the markdown report (default: reports/)",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repo root (default: cwd)",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    out_dir = repo_root / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    entries = load_reference_data(repo_root)
    entries_with_unii = sum(1 for _, _, e in entries if _extract_entry_unii(e))
    name_to_unii, unii_to_name = load_fda_unii_cache(repo_root)
    unii_to_fda_names = build_unii_to_fda_names(name_to_unii)
    exoneration_allowlist = load_exoneration_allowlist(repo_root)

    duplicate_cross_file = find_duplicate_unii_cross_file(entries)
    same_unii_diff_names = find_same_unii_different_names(
        entries, unii_to_fda_names, exoneration_allowlist
    )
    same_name_diff_uniis = find_same_name_different_uniis(entries)
    fda_mismatches = find_fda_cache_name_mismatches(entries, unii_to_name)

    report = render_report(
        duplicate_cross_file,
        same_unii_diff_names,
        same_name_diff_uniis,
        fda_mismatches,
        total_entries=len(entries),
        entries_with_unii=entries_with_unii,
    )

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"unii_data_quality_{ts}.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"Report written: {out_path}")

    # Exit codes — escalate only on POST-EXONERATION critical findings
    critical_count = sum(
        1 for info in same_unii_diff_names.values() if info["severity"] == "critical"
    )
    review_count = sum(
        1 for info in same_unii_diff_names.values() if info["severity"] == "review"
    )
    allowlist_count = sum(
        1 for info in same_unii_diff_names.values() if info["severity"] == "allowlist_exonerated"
    )

    print(
        f"Findings: {critical_count} critical, {review_count} review-exonerated, "
        f"{allowlist_count} allowlist-exonerated, "
        f"{len(duplicate_cross_file)} cross-file duplicates, "
        f"{len(same_name_diff_uniis)} same-name-different-uniis, "
        f"{len(fda_mismatches)} fda cache mismatches.",
        file=sys.stderr,
    )

    if critical_count:
        print(
            f"CRITICAL: {critical_count} SAME_UNII_DIFFERENT_NAMES findings "
            "with no FDA/CUI/allowlist exoneration — fix BEFORE enabling UNII-first matching.",
            file=sys.stderr,
        )
        return 2
    if duplicate_cross_file or fda_mismatches:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
