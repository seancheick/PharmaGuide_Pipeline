#!/usr/bin/env python3
from __future__ import annotations
"""
UNII backfill proposal + per-entry --apply tool (Sprint 2).

Walks the 4 reference DBs (IQM, botanicals, other_ingredients,
standardized_botanicals), finds entries that are missing a UNII (and aren't
explicitly governed_null), and proposes candidate UNIIs from two evidence
sources:

  1. FDA UNII cache (`scripts/data/fda_unii_cache.json`) — the offline FDA
     OpenFDA bulk snapshot. The canonical name→UNII map (172K+ entries).
  2. DSLD consensus — walking raw DSLD label JSON in
     `/Users/seancheick/Documents/DataSetDsld/staging/brands/*/` to count
     `(ingredient_name, uniiCode) → product_count`. When ≥5 distinct
     products consistently tag the same ingredient name with the same UNII
     across multiple brands, that's strong corroboration.

Confidence tiers per proposal:
  * HIGH:   FDA cache exact-match for standard_name AND ≥5 DSLD products
            consensus on the same UNII
  * MEDIUM: FDA cache match (standard_name OR any alias) OR ≥5 DSLD
            consensus (not both)
  * LOW:    Weak signals only — single DSLD product, fuzzy FDA match, etc.

Pre-apply regression guard:
  Per pre-Sprint-1 blocker rule (docs/UNII_TRIAGE_2026_05_14.md), the
  audit's SAME_UNII_DIFFERENT_NAMES critical bucket must remain at 0
  (or only allowlisted). Before applying a backfill, this script
  simulates the post-apply state and runs the audit's
  find_same_unii_different_names against it. If the simulated state
  introduces ANY new critical finding that is not in the allowlist,
  the apply is refused with a clear diagnostic — the backfill system
  must not be able to silently create new identity collisions.

CLI contract (per approved plan):
  * Dry-run by default (no file writes)
  * --apply MUST be combined with --entry-ids ID1,ID2,...
  * NO --apply-all flag exists
  * NO --confidence-high shortcut for bulk-applying high-confidence items
  * Each --apply mutates exactly the named entries' external_ids.unii;
    `last_updated` is bumped to today; nothing else changes

Operator runbook:
  # 1. Dry run — produces reports/unii_backfill_proposals_<ts>.json
  python3 scripts/api_audit/backfill_unii_from_cache.py

  # 2. Inspect the JSON, pick the entries you want to apply
  # 3. Apply one or a few at a time (one atomic git commit per apply)
  python3 scripts/api_audit/backfill_unii_from_cache.py --apply --entry-ids NHA_FOO
  git add scripts/data/other_ingredients.json
  git commit -m "fix(data): backfill UNII for NHA_FOO ..."

  # 4. Re-run the data-quality audit after each apply
  python3 scripts/api_audit/audit_unii_data_quality.py
"""

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Reuse audit script's helpers — single source of truth for normalization,
# loading, and the SAME_UNII_DIFFERENT_NAMES finder used by the pre-apply guard.
_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))
from audit_unii_data_quality import (  # noqa: E402
    REFERENCE_FILES,
    _normalize_unii,
    _extract_entry_unii,
    load_reference_data,
    load_fda_unii_cache,
    load_exoneration_allowlist,
    build_unii_to_fda_names,
    find_same_unii_different_names,
    _load_iqm_entries,
    _load_list_entries,
)


# ---------------------------------------------------------------------------
# DSLD raw-label staging
# ---------------------------------------------------------------------------
DSLD_STAGING_ROOT = Path("/Users/seancheick/Documents/DataSetDsld/staging/brands")

# Entries with explicit cui_status='governed_null' are intentional no-UNII
# (polymer classes, blend descriptors). Skip them — they're not bugs.
GOVERNED_NULL_MARKERS = {"governed_null"}

# Minimum DSLD products that must consistently tag (name, unii) for the
# consensus signal to count as "≥5 products consensus" per the plan.
DSLD_CONSENSUS_THRESHOLD = 5


@dataclass
class Proposal:
    """One UNII-backfill proposal for one reference-data entry."""

    entry_id: str
    file: str
    standard_name: str
    current_unii: Optional[str]
    current_cui: Optional[str]
    current_cui_status: Optional[str]
    proposed_unii: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    confidence: str = "low"            # "high" | "medium" | "low"
    rationale: str = ""
    pre_apply_guard: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# DSLD consensus index
# ---------------------------------------------------------------------------


def build_dsld_consensus_index(
    staging_root: Path = DSLD_STAGING_ROOT,
) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """Walk all DSLD raw JSONs under `staging_root` and build:

        (normalized_ingredient_name, canonical_unii) → {
          "count": <int>,
          "brands": set[str],
          "sample_label_names": list[str],
        }

    Returns an empty dict if the staging tree is missing (test mode or
    early dev).
    """
    if not staging_root.exists():
        print(
            f"[warn] DSLD staging not found at {staging_root} — "
            f"DSLD-consensus evidence will be empty",
            file=sys.stderr,
        )
        return {}

    idx: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "brands": set(), "sample_label_names": []}
    )

    for brand_dir in sorted(staging_root.iterdir()):
        if not brand_dir.is_dir():
            continue
        brand_name = brand_dir.name
        for product_file in brand_dir.iterdir():
            if not product_file.is_file() or product_file.suffix != ".json":
                continue
            try:
                with open(product_file, encoding="utf-8") as f:
                    raw = json.load(f)
            except Exception:
                continue
            rows = raw.get("ingredientRows") or []
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                # Top-level row
                _index_row(idx, row, brand_name)
                # Per-form (nested) rows
                for form in row.get("forms") or []:
                    if isinstance(form, dict):
                        _index_row(idx, form, brand_name)
    return dict(idx)


def _index_row(
    idx: Dict[Tuple[str, str], Dict[str, Any]],
    row: Dict[str, Any],
    brand_name: str,
) -> None:
    """Add one (name, unii) pair to the index if both are present."""
    raw_name = (row.get("name") or "").strip()
    if not raw_name:
        return
    unii = _normalize_unii(row.get("uniiCode"))
    if not unii:
        return
    key = (raw_name.lower(), unii)
    bucket = idx[key]
    bucket["count"] += 1
    bucket["brands"].add(brand_name)
    if len(bucket["sample_label_names"]) < 3 and raw_name not in bucket["sample_label_names"]:
        bucket["sample_label_names"].append(raw_name)


def query_dsld_consensus(
    dsld_index: Dict[Tuple[str, str], Dict[str, Any]],
    candidate_names: List[str],
) -> Dict[str, Dict[str, Any]]:
    """For each candidate name (standard_name + aliases, lowercased), return
    the UNII -> count mapping seen in DSLD. Returns:
        {unii: {"count": int, "brands": set, "matched_via": list[str]}}
    Aggregates counts across all name variants pointing to the same UNII.
    """
    result: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "brands": set(), "matched_via": []}
    )
    for name in candidate_names:
        if not name:
            continue
        nm_lower = name.strip().lower()
        for (idx_name, unii), bucket in dsld_index.items():
            if idx_name == nm_lower:
                result[unii]["count"] += bucket["count"]
                result[unii]["brands"].update(bucket["brands"])
                if name not in result[unii]["matched_via"]:
                    result[unii]["matched_via"].append(name)
    return dict(result)


# ---------------------------------------------------------------------------
# FDA cache lookup
# ---------------------------------------------------------------------------


def query_fda_cache(
    name_to_unii: Dict[str, str],
    candidate_names: List[str],
) -> Dict[str, Dict[str, Any]]:
    """For each candidate name, look up in FDA name_to_unii (lowercased keys).
    Returns:
        {unii: {"fda_name": fda_canonical_name, "matched_via": list[str]}}
    """
    result: Dict[str, Dict[str, Any]] = {}
    for name in candidate_names:
        if not name:
            continue
        nm_lower = name.strip().lower()
        unii = name_to_unii.get(nm_lower)
        if not unii:
            continue
        unii_canon = _normalize_unii(unii)
        if not unii_canon:
            continue
        bucket = result.setdefault(
            unii_canon, {"fda_name": nm_lower, "matched_via": []}
        )
        if name not in bucket["matched_via"]:
            bucket["matched_via"].append(name)
    return result


# ---------------------------------------------------------------------------
# Candidate identification + proposal generation
# ---------------------------------------------------------------------------


def is_backfill_candidate(entry: Dict[str, Any]) -> bool:
    """Entry is a candidate for UNII backfill if:
      - It has no current UNII (or only placeholder)
      - It's not explicitly governed_null
    """
    if not isinstance(entry, dict):
        return False
    if _extract_entry_unii(entry):
        return False  # already has a valid UNII
    if entry.get("cui_status") in GOVERNED_NULL_MARKERS:
        return False  # explicit "no UNII applies" marker
    return True


def _collect_entry_names(entry: Dict[str, Any]) -> List[str]:
    """Return [standard_name] + aliases as a deduplicated list of strings."""
    out: List[str] = []
    seen: Set[str] = set()
    for s in [entry.get("standard_name")] + (entry.get("aliases") or []):
        if isinstance(s, str) and s.strip():
            key = s.strip().lower()
            if key not in seen:
                seen.add(key)
                out.append(s.strip())
    return out


def _score_confidence(
    fda_results: Dict[str, Dict[str, Any]],
    dsld_results: Dict[str, Dict[str, Any]],
    proposed_unii: str,
    entry_standard_name: str,
) -> Tuple[str, str]:
    """Return (confidence_tier, rationale).

    HIGH:   FDA cache exact-match for standard_name AND ≥5 DSLD products
    MEDIUM: FDA cache match (any name) OR ≥5 DSLD consensus (not both)
    LOW:    weak signals only
    """
    fda_hit = fda_results.get(proposed_unii, {})
    dsld_hit = dsld_results.get(proposed_unii, {})

    fda_matched_via = fda_hit.get("matched_via", [])
    fda_exact_on_standard = entry_standard_name in fda_matched_via
    fda_matched_any = bool(fda_matched_via)
    dsld_count = int(dsld_hit.get("count", 0))
    dsld_consensus_met = dsld_count >= DSLD_CONSENSUS_THRESHOLD

    if fda_exact_on_standard and dsld_consensus_met:
        return (
            "high",
            f"FDA cache exact match on standard_name {entry_standard_name!r} "
            f"AND {dsld_count} DSLD products consensus "
            f"({len(dsld_hit.get('brands', set()))} distinct brands).",
        )
    if fda_matched_any and dsld_consensus_met:
        return (
            "high",
            f"FDA cache match via alias(es) {fda_matched_via} AND {dsld_count} "
            f"DSLD products consensus "
            f"({len(dsld_hit.get('brands', set()))} brands).",
        )
    if fda_exact_on_standard:
        return (
            "medium",
            f"FDA cache exact match on standard_name {entry_standard_name!r}. "
            f"DSLD consensus weak ({dsld_count} products).",
        )
    if dsld_consensus_met:
        return (
            "medium",
            f"DSLD products consensus only ({dsld_count} products, "
            f"{len(dsld_hit.get('brands', set()))} brands). FDA cache match "
            f"weak (matched via {fda_matched_via or '(none)'}).",
        )
    if fda_matched_any:
        return (
            "low",
            f"FDA cache match via alias only {fda_matched_via}. DSLD consensus "
            f"weak ({dsld_count} products).",
        )
    return (
        "low",
        f"Weak signals only: {dsld_count} DSLD products, FDA matched_via {fda_matched_via}.",
    )


def propose_for_entry(
    file_label: str,
    entry_id: str,
    entry: Dict[str, Any],
    fda_name_to_unii: Dict[str, str],
    dsld_index: Dict[Tuple[str, str], Dict[str, Any]],
) -> Optional[Proposal]:
    """Build a Proposal for one entry, or None if no candidate UNII surfaces.
    When multiple UNIIs surface (e.g., FDA cache hits two different ones via
    different aliases), the one with the highest combined signal wins.
    """
    if not is_backfill_candidate(entry):
        return None

    candidate_names = _collect_entry_names(entry)
    if not candidate_names:
        return None

    fda_results = query_fda_cache(fda_name_to_unii, candidate_names)
    dsld_results = query_dsld_consensus(dsld_index, candidate_names)

    # Combine: every UNII surfaced by EITHER source is a candidate
    all_uniis = set(fda_results.keys()) | set(dsld_results.keys())
    if not all_uniis:
        return None

    # Score each candidate UNII: prefer FDA-on-standard + high DSLD count
    standard_name = entry.get("standard_name", entry_id)

    def _signal_strength(unii: str) -> Tuple[int, int, int]:
        fda_hit = fda_results.get(unii, {})
        dsld_hit = dsld_results.get(unii, {})
        fda_exact_on_std = standard_name in fda_hit.get("matched_via", [])
        fda_any = 1 if fda_hit else 0
        dsld_count = int(dsld_hit.get("count", 0))
        # Tuple sorts lexicographically: prefer FDA-exact-standard, then any
        # FDA match, then highest DSLD count.
        return (int(fda_exact_on_std), fda_any, dsld_count)

    proposed_unii = max(all_uniis, key=_signal_strength)
    confidence, rationale = _score_confidence(
        fda_results, dsld_results, proposed_unii, standard_name
    )

    fda_evidence = fda_results.get(proposed_unii, {})
    dsld_evidence = dsld_results.get(proposed_unii, {})

    evidence = {
        "fda_cache_match": {
            "fda_canonical_name": fda_evidence.get("fda_name"),
            "matched_via": fda_evidence.get("matched_via", []),
        }
        if fda_evidence
        else None,
        "dsld_consensus": {
            "count": int(dsld_evidence.get("count", 0)),
            "brand_spread": sorted(list(dsld_evidence.get("brands", set()))),
            "matched_via": dsld_evidence.get("matched_via", []),
        }
        if dsld_evidence
        else None,
        "alternate_uniis_seen": sorted(all_uniis - {proposed_unii}),
    }

    return Proposal(
        entry_id=entry_id,
        file=file_label,
        standard_name=standard_name,
        current_unii=_extract_entry_unii(entry),  # None for candidates
        current_cui=entry.get("cui"),
        current_cui_status=entry.get("cui_status"),
        proposed_unii=proposed_unii,
        evidence=evidence,
        confidence=confidence,
        rationale=rationale,
    )


# ---------------------------------------------------------------------------
# Pre-apply regression guard
# ---------------------------------------------------------------------------


def simulate_apply(
    entries: List[Tuple[str, str, Dict[str, Any]]],
    target_file: str,
    target_id: str,
    proposed_unii: str,
) -> List[Tuple[str, str, Dict[str, Any]]]:
    """Return a SHALLOW-COPIED entries list where the named entry's
    external_ids.unii is set to `proposed_unii`. Original objects untouched."""
    out: List[Tuple[str, str, Dict[str, Any]]] = []
    for file_label, eid, edict in entries:
        if file_label == target_file and eid == target_id:
            new_e = dict(edict)
            existing_ext = new_e.get("external_ids") or {}
            if not isinstance(existing_ext, dict):
                existing_ext = {}
            new_ext = dict(existing_ext)
            new_ext["unii"] = proposed_unii
            new_e["external_ids"] = new_ext
            out.append((file_label, eid, new_e))
        else:
            out.append((file_label, eid, edict))
    return out


def pre_apply_guard(
    entries: List[Tuple[str, str, Dict[str, Any]]],
    proposal: Proposal,
    unii_to_fda_names: Dict[str, set],
    exoneration_allowlist: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Simulate applying this proposal and run the audit's
    SAME_UNII_DIFFERENT_NAMES check. Refuse the apply if it introduces a
    NEW critical finding (one not in the allowlist and not present in the
    baseline).

    Returns a dict describing the guard outcome; never raises.
    """
    # Baseline critical UNIIs
    baseline = find_same_unii_different_names(
        entries, unii_to_fda_names, exoneration_allowlist
    )
    baseline_critical_uniis = {
        u for u, info in baseline.items() if info["severity"] == "critical"
    }

    # Simulated state
    simulated_entries = simulate_apply(
        entries, proposal.file, proposal.entry_id, proposal.proposed_unii
    )
    post = find_same_unii_different_names(
        simulated_entries, unii_to_fda_names, exoneration_allowlist
    )
    post_critical_uniis = {
        u for u, info in post.items() if info["severity"] == "critical"
    }

    newly_introduced = sorted(post_critical_uniis - baseline_critical_uniis)
    would_block = bool(newly_introduced)

    # Detailed reason: for each newly-introduced critical UNII, list which
    # entries are now colliding under it.
    collision_detail: List[Dict[str, Any]] = []
    if would_block:
        for u in newly_introduced:
            info = post.get(u, {})
            collision_detail.append(
                {
                    "unii": u,
                    "colliding_entries": [
                        {"file": loc[0], "entry_id": loc[1], "standard_name": loc[2]}
                        for loc in info.get("locations", [])
                    ],
                }
            )

    return {
        "would_create_new_critical_finding": would_block,
        "newly_introduced_critical_uniis": newly_introduced,
        "baseline_critical_count": len(baseline_critical_uniis),
        "post_apply_critical_count": len(post_critical_uniis),
        "collision_detail": collision_detail,
        "verdict": "BLOCKED" if would_block else "SAFE",
    }


# ---------------------------------------------------------------------------
# Apply (mutate one entry in one file)
# ---------------------------------------------------------------------------


class ApplyRefused(RuntimeError):
    """Raised when the pre-apply guard refuses the change."""

    pass


def apply_one_entry(
    repo_root: Path,
    proposal: Proposal,
    guard_result: Dict[str, Any],
    today_str: Optional[str] = None,
) -> Path:
    """Mutate the named entry's external_ids.unii in its source JSON file.
    Bumps `last_updated` if the entry already has that field. Writes the
    file with stable 2-space indentation + trailing newline.

    Refuses if guard_result["would_create_new_critical_finding"] is True.

    Returns the path of the modified file.
    """
    if guard_result.get("would_create_new_critical_finding"):
        raise ApplyRefused(
            f"Refused: backfilling UNII {proposal.proposed_unii} on "
            f"{proposal.file}::{proposal.entry_id} would introduce new critical "
            f"finding(s): {guard_result['newly_introduced_critical_uniis']}. "
            f"Collisions: {guard_result['collision_detail']}"
        )

    today_str = today_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    file_path = repo_root / "scripts/data" / proposal.file
    # Read the raw file text once so we can detect its existing convention
    # for non-ASCII characters. The 4 reference files differ:
    #   - other_ingredients.json: raw UTF-8 (no \u escapes)
    #   - ingredient_quality_map.json + standardized_botanicals.json: ASCII-
    #     escaped (\uXXXX)
    #   - botanical_ingredients.json: mixed (older entries escaped, newer raw)
    # We default to ASCII-escaping when ≥10 \u escapes appear in the file
    # OR when zero non-ASCII chars appear (pure ASCII files). Otherwise we
    # preserve raw UTF-8. This keeps the apply diff minimal in every case.
    with open(file_path, encoding="utf-8") as f:
        raw_text = f.read()
    blob = json.loads(raw_text)
    escape_count = raw_text.count("\\u")
    has_raw_utf8 = any(ord(c) > 127 for c in raw_text[:50000])
    # ascii-escape the output if the file is conventionally escape-style
    file_uses_ascii_escapes = escape_count >= 10 or not has_raw_utf8

    # Find the list_key for this file. REFERENCE_FILES is keyed by full
    # repo-relative path ("scripts/data/<file>.json") but proposals carry
    # only the basename (Path(rel_path).name). Resolve by basename match.
    list_key_map = {Path(rel_path).name: lk for rel_path, lk in REFERENCE_FILES}
    if proposal.file not in list_key_map:
        raise RuntimeError(
            f"Apply failed: unknown reference file {proposal.file!r}. "
            f"Known files: {sorted(list_key_map.keys())}"
        )
    list_key = list_key_map[proposal.file]

    # IQM-style top-level dict-of-dicts (list_key=None) vs list-of-dicts
    if list_key is None:
        entry = blob.get(proposal.entry_id)
        if not isinstance(entry, dict):
            raise RuntimeError(
                f"Apply failed: entry {proposal.entry_id!r} not found in {proposal.file}"
            )
        _mutate_entry(entry, proposal.proposed_unii, today_str)
    else:
        entries = blob.get(list_key, [])
        if not isinstance(entries, list):
            raise RuntimeError(f"Apply failed: {proposal.file} has no list at {list_key!r}")
        target_idx = None
        for i, e in enumerate(entries):
            if isinstance(e, dict) and e.get("id") == proposal.entry_id:
                target_idx = i
                break
        if target_idx is None:
            raise RuntimeError(
                f"Apply failed: entry id {proposal.entry_id!r} not found in {proposal.file}"
            )
        _mutate_entry(entries[target_idx], proposal.proposed_unii, today_str)

    # Bump _metadata.last_updated for the file (light-touch)
    md = blob.get("_metadata")
    if isinstance(md, dict):
        md["last_updated"] = today_str

    # Write back with stable formatting, preserving the file's existing
    # non-ASCII convention (ASCII-escaped vs raw UTF-8).
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(blob, f, indent=2, ensure_ascii=file_uses_ascii_escapes)
        f.write("\n")

    return file_path


def _mutate_entry(entry: Dict[str, Any], proposed_unii: str, today_str: str) -> None:
    """In-place mutation: set external_ids.unii, bump last_updated if present."""
    ext = entry.get("external_ids")
    if not isinstance(ext, dict):
        ext = {}
        entry["external_ids"] = ext
    ext["unii"] = proposed_unii

    # If entry has a last_updated field, bump it. Don't introduce one if absent
    # (would be schema drift on entries that don't carry the field).
    if "last_updated" in entry:
        entry["last_updated"] = today_str


# ---------------------------------------------------------------------------
# Proposal report
# ---------------------------------------------------------------------------


def _proposal_to_dict(p: Proposal) -> Dict[str, Any]:
    d = asdict(p)
    # Convert any sets (e.g., brand_spread should already be lists, but defensively)
    def _serialize(v: Any) -> Any:
        if isinstance(v, set):
            return sorted(v)
        if isinstance(v, dict):
            return {k: _serialize(vv) for k, vv in v.items()}
        if isinstance(v, list):
            return [_serialize(x) for x in v]
        return v
    return _serialize(d)


def render_proposal_report(proposals: List[Proposal], output_path: Path) -> None:
    """Write proposals as JSON. Sorted by confidence tier (high→low), then file, then entry_id."""
    tier_order = {"high": 0, "medium": 1, "low": 2}

    proposals_sorted = sorted(
        proposals,
        key=lambda p: (tier_order.get(p.confidence, 9), p.file, p.entry_id),
    )

    blob = {
        "_metadata": {
            "schema_version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "total_proposals": len(proposals_sorted),
            "by_confidence": {
                tier: sum(1 for p in proposals_sorted if p.confidence == tier)
                for tier in ("high", "medium", "low")
            },
            "purpose": (
                "Dry-run UNII backfill proposals. EACH MUST BE HUMAN-VERIFIED "
                "before --apply. The pre_apply_guard.verdict field shows "
                "whether applying the proposal would introduce a new "
                "SAME_UNII_DIFFERENT_NAMES critical finding (BLOCKED) or not (SAFE)."
            ),
            "operator_runbook": (
                "1. Read proposals sorted high→low confidence. "
                "2. For each you want to apply: verify the evidence (FDA cache, "
                "DSLD consensus). "
                "3. Apply per-entry: python3 backfill_unii_from_cache.py --apply "
                "--entry-ids NHA_FOO,IQM_BAR (verify diff, then commit). "
                "4. Re-run audit_unii_data_quality.py after each apply."
            ),
        },
        "proposals": [_proposal_to_dict(p) for p in proposals_sorted],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(blob, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ---------------------------------------------------------------------------
# CLI / main
# ---------------------------------------------------------------------------


def build_proposals(
    entries: List[Tuple[str, str, Dict[str, Any]]],
    fda_name_to_unii: Dict[str, str],
    dsld_index: Dict[Tuple[str, str], Dict[str, Any]],
    unii_to_fda_names: Dict[str, set],
    exoneration_allowlist: Dict[str, Dict[str, Any]],
    target_entry_ids: Optional[Set[str]] = None,
) -> List[Proposal]:
    """Return Proposals for every candidate (or for the named subset).
    Each proposal carries its pre_apply_guard verdict."""
    proposals: List[Proposal] = []
    for file_label, eid, edict in entries:
        if target_entry_ids and eid not in target_entry_ids:
            continue
        p = propose_for_entry(file_label, eid, edict, fda_name_to_unii, dsld_index)
        if p is None:
            continue
        p.pre_apply_guard = pre_apply_guard(
            entries, p, unii_to_fda_names, exoneration_allowlist
        )
        proposals.append(p)
    return proposals


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "UNII backfill proposal + per-entry --apply tool. Dry-run by "
            "default. --apply requires --entry-ids. NO --apply-all flag."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Apply backfills for the entries named in --entry-ids. "
            "Mutates JSON files in place. Per CLAUDE.md 'no batch fixes': "
            "use one --entry-ids at a time and commit atomically."
        ),
    )
    parser.add_argument(
        "--entry-ids",
        default="",
        help=(
            "Comma-separated entry IDs to operate on. REQUIRED for --apply. "
            "Optional for dry-run (filters the proposal set)."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="reports",
        help="Where to write the proposals JSON (default: reports/).",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repo root (default: cwd).",
    )
    parser.add_argument(
        "--dsld-staging",
        default=str(DSLD_STAGING_ROOT),
        help=(
            "DSLD raw-label staging directory. Defaults to the user's local path. "
            "Override for test mode."
        ),
    )
    args = parser.parse_args(argv)

    target_entry_ids: Set[str] = set()
    if args.entry_ids:
        target_entry_ids = {
            x.strip() for x in args.entry_ids.split(",") if x.strip()
        }

    if args.apply:
        if not target_entry_ids:
            print(
                "REFUSED: --apply requires --entry-ids ID1,ID2,... "
                "Per CLAUDE.md 'no batch fixes': pick one or a few entries "
                "and commit atomically. No bulk apply mode exists.",
                file=sys.stderr,
            )
            return 2

    repo_root = Path(args.repo_root).resolve()
    output_dir = repo_root / args.output_dir

    # Load reference data + audit machinery
    entries = load_reference_data(repo_root)
    name_to_unii, _unii_to_name = load_fda_unii_cache(repo_root)
    unii_to_fda_names = build_unii_to_fda_names(name_to_unii)
    exoneration_allowlist = load_exoneration_allowlist(repo_root)

    # Build DSLD consensus index (slow — but only once per invocation)
    print(f"Building DSLD consensus index from {args.dsld_staging} ...", file=sys.stderr)
    dsld_index = build_dsld_consensus_index(Path(args.dsld_staging))
    print(
        f"DSLD index: {len(dsld_index)} unique (name, unii) pairs across staging",
        file=sys.stderr,
    )

    # Generate proposals
    proposals = build_proposals(
        entries,
        name_to_unii,
        dsld_index,
        unii_to_fda_names,
        exoneration_allowlist,
        target_entry_ids=target_entry_ids if not args.apply else None,
    )

    if args.apply:
        # Apply mode: refuse anything not in the proposed set
        proposed_ids = {p.entry_id for p in proposals}
        unknown = target_entry_ids - proposed_ids
        if unknown:
            print(
                f"REFUSED: requested --entry-ids include IDs that are not "
                f"backfill candidates (already have UNII, or governed_null, "
                f"or no FDA/DSLD signal): {sorted(unknown)}",
                file=sys.stderr,
            )
            return 3

        applied: List[str] = []
        for p in proposals:
            if p.entry_id not in target_entry_ids:
                continue
            verdict = p.pre_apply_guard.get("verdict")
            if verdict == "BLOCKED":
                print(
                    f"REFUSED apply for {p.entry_id}: regression guard "
                    f"BLOCKED. Newly-critical UNIIs: "
                    f"{p.pre_apply_guard['newly_introduced_critical_uniis']}. "
                    f"Collisions: {p.pre_apply_guard['collision_detail']}",
                    file=sys.stderr,
                )
                return 4
            try:
                path = apply_one_entry(repo_root, p, p.pre_apply_guard)
                applied.append(f"{p.file}::{p.entry_id} -> {p.proposed_unii}")
                print(f"Applied: {p.file}::{p.entry_id} → unii={p.proposed_unii} ({path})")
            except ApplyRefused as e:
                print(f"REFUSED apply for {p.entry_id}: {e}", file=sys.stderr)
                return 4

        print(f"\nApplied {len(applied)} entries. Review the diff and commit atomically.")
        return 0

    # Dry run: write proposals JSON
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"unii_backfill_proposals_{ts}.json"
    render_proposal_report(proposals, output_path)
    print(f"Proposals written: {output_path}")
    print(
        f"Total proposals: {len(proposals)} "
        f"(high={sum(1 for p in proposals if p.confidence=='high')}, "
        f"medium={sum(1 for p in proposals if p.confidence=='medium')}, "
        f"low={sum(1 for p in proposals if p.confidence=='low')})"
    )
    blocked = sum(
        1 for p in proposals if p.pre_apply_guard.get("verdict") == "BLOCKED"
    )
    if blocked:
        print(
            f"Regression-guard BLOCKED on {blocked} proposals — these would "
            f"introduce new SAME_UNII_DIFFERENT_NAMES critical findings if "
            f"applied. See pre_apply_guard.collision_detail in the JSON."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
