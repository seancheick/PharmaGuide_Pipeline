#!/usr/bin/env python3
"""Curated-data batches: canonical save, _metadata recount, landed check.

A batch edits several related entries of one data file together. Each entry is
still researched and verified on its own (the data-fix skill); this module makes
the mechanical part safe and repeatable:

  load(path)          parse, refusing duplicate keys (json keeps the last one)
  save(path, blob)    recount _metadata, bump last_updated when an entry
                      changed, write canonical JSON (run_artifacts.json_text)
  recount(name, blob) the one owner of _metadata.total_entries and the IQM
                      statistics; the metadata tests import it
  entries(blob)       {entry key: entry} for any data-file shape
  changed_keys(a, b)  added, removed and modified keys of two entry maps

CLI, from the repo root with $PG_PYTHON (source scripts/python_env.sh):

  data_batch.py check FILE --since REF [--expect K1,K2 | --expect-file F]
      One line per changed entry. Exit 1 if an expected entry did not change,
      an unexpected one did, or _metadata no longer matches the entries.
      Without --expect it only lists the changed keys.
  data_batch.py recount FILE...   rewrite the _metadata counts owned here
  data_batch.py format FILE...    canonical JSON; the parsed content must not change
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Optional

from run_artifacts import atomic_write_json, json_text

REPO = Path(__file__).resolve().parent.parent
IQM_FILE = "ingredient_quality_map.json"

# Files whose shape doesn't match the universal classifier OR whose
# total_entries means something file-specific. Each entry MUST cite the
# bespoke per-file test that pins the semantic (no silent skips).
INTENTIONAL_EXCEPTIONS: dict[str, str] = {
    "catalog_brand_registry.json":
        "total_entries tracks canonical brand-family records; wave_1 is an "
        "execution manifest, not another brand catalog. Pinned by "
        "test_brand_identity.py.",
    "ingredient_weights.json":
        "total_entries tracks dosage_weights tier count (4 — therapeutic / "
        "optimal / maintenance / trace), not the sum across multi-section "
        "payload. Pinned by test_ingredient_weights_contract.py.",
    "unit_conversions.json":
        "total_entries tracks vitamin_conversions only; mass_conversions "
        "and form_detection_patterns are static rule config, not vitamin "
        "entries. Pinned by "
        "test_unit_conversions_contract.py.",
    "cert_claim_rules.json":
        "total_entries = Σ(non-_-prefixed rule keys across rules.*), "
        "excluding each category's _metadata config sub-key. Pinned by "
        "test_cert_claim_rules_contract.py.",
    "manufacture_deduction_expl.json":
        "Structural config file (1 scalar total_deduction_cap + 4 nested "
        "dicts for violation_categories / modifiers / calculation_rules / "
        "score_thresholds). total_entries=5 tracks count of top-level "
        "non-_metadata sub-sections — meaningful but not entry-shaped. "
        "Pinned by test_manufacture_deduction_expl_contract.py.",
    "banned_match_allowlist.json":
        "total_entries tracks allowlist only; denylist is auxiliary and "
        "tracked separately. Pinned by "
        "test_banned_match_allowlist_contract.py.",
    "clinical_risk_taxonomy.json":
        "UNIQUE convention — total_entries = SUM of all 7 taxonomy arrays "
        "(conditions + drug_classes + severity_levels + evidence_levels + "
        "profile_flags + product_forms + sources). Pinned by "
        "test_clinical_risk_taxonomy_contract.py.",
    "color_indicators.json":
        "total_entries tracks natural_indicators only; artificial_indicators "
        "+ explicit_natural_dyes + explicit_artificial_dyes are auxiliary. "
        "Pinned by test_color_indicators_contract.py.",
    "functional_ingredient_groupings.json":
        "total_entries tracks functional_groupings only; vague_terms_to_flag "
        "+ transparency_bonuses are auxiliary. Pinned by "
        "test_functional_ingredient_groupings_contract.py.",
    "migration_report.json":
        "total_entries tracks alias_collisions_resolved (the headline number "
        "of this migration); other arrays/dicts are scaffolding. Pinned by "
        "test_migration_report_contract.py.",
    "fda_unii_cache.json":
        "Runtime cache file (name_to_unii + unii_to_name lookups, 170K+ "
        "entries each) populated by scripts/api_audit/fda_weekly_sync.py. "
        "Size fluctuates with each FDA UNII sync — a static total_entries "
        "would be meaningless and forced bumps per sync. Intentionally "
        "carries no total_entries; the cache file's freshness is tracked "
        "by _metadata.last_updated instead.",
}


def classify_shape(blob: dict) -> Optional[tuple[str, int]]:
    """Return ``(shape_name, entry_count)`` for the three universal shapes,
    ``None`` when the file needs a bespoke per-file test.

    1. ``single_array``: exactly one top-level array besides ``_metadata``
       (auxiliary top-level dicts allowed). Count = ``len(array)``.
    2. ``single_payload_dict``: one top-level dict and nothing else besides
       ``_metadata``. Count = keys of that wrapping dict.
    3. ``top_level_dict_of_dicts``: every non-``_metadata`` value is a dict and
       there are no arrays. Count = non-``_metadata`` keys.
    """
    non_meta = {k: v for k, v in blob.items() if k != "_metadata"}
    arrays = [(k, v) for k, v in non_meta.items() if isinstance(v, list)]
    dicts = [(k, v) for k, v in non_meta.items() if isinstance(v, dict)]
    if len(arrays) == 1:
        return ("single_array", len(arrays[0][1]))
    if len(dicts) == 1 and not arrays and len(non_meta) == 1:
        return ("single_payload_dict", len(dicts[0][1]))
    if not arrays and dicts and len(non_meta) == len(dicts):
        return ("top_level_dict_of_dicts", len(non_meta))
    return None


def iqm_statistics(parents: dict) -> dict[str, int]:
    """The IQM ``_metadata.statistics`` counts for a {parent_id: parent} map."""
    stats = dict.fromkeys(
        ("total_parents", "total_forms", "total_form_aliases",
         "parents_with_parent_aliases", "parents_with_contains_aliases",
         "parents_with_pattern_aliases"), 0)
    for parent in parents.values():
        if not isinstance(parent, dict):
            continue
        stats["total_parents"] += 1
        stats["parents_with_parent_aliases"] += bool(parent.get("aliases"))
        stats["parents_with_contains_aliases"] += bool(parent.get("contains_aliases"))
        stats["parents_with_pattern_aliases"] += bool(parent.get("pattern_aliases"))
        forms = parent.get("forms", {})
        if isinstance(forms, dict):
            for form in forms.values():
                stats["total_forms"] += 1
                if isinstance(form, dict):
                    stats["total_form_aliases"] += len(form.get("aliases", []))
    return stats


def _records(blob: dict, key: str) -> list:
    value = blob.get(key)
    values = value.values() if isinstance(value, dict) else value or []
    return [v for v in values if isinstance(v, dict)]


def _size(key: str):
    return lambda blob: len(blob.get(key) or ())


def _tally(key: str, field: str):
    """{value: count} of ``field`` over the records under ``key``."""
    def count(blob: dict) -> dict[str, int]:
        c = Counter(str(r[field]) for r in _records(blob, key) if r.get(field) is not None)
        return dict(sorted(c.items()))
    return count


def _where(key: str, predicate):
    return lambda blob: sum(1 for r in _records(blob, key) if predicate(r))


def _iqm_categories(blob: dict) -> dict[str, int]:
    c = Counter(str(p["category"]) for k, p in blob.items()
                if k != "_metadata" and isinstance(p, dict) and p.get("category"))
    return dict(sorted(c.items()))


def _cert_claim_statistics(blob: dict) -> dict[str, int]:
    """Rules per category (non-underscore keys) and their total."""
    rules = blob.get("rules") or {}
    per = {name: sum(1 for k in body if not k.startswith("_"))
           for name, body in rules.items() if isinstance(body, dict)}
    return {**per, "total_rules": sum(per.values())}


# Every other count a data file stores in _metadata, with the one definition the
# data proves (each matched the stored value, or the stored value had drifted).
# recount writes only fields a file already has; a field whose meaning cannot
# be derived from its own file (color_indicators totals, cross-file timing
# counts, literature evidence counts) is not listed and stays hand-maintained.
# cert_claim_rules statistics (one count per rule category) are handled in recount.
DERIVED_COUNTS: dict[str, dict[tuple, Any]] = {
    "banned_recalled_ingredients.json": {("risk_breakdown",): _tally("ingredients", "clinical_risk_enum")},
    "harmful_additives.json": {
        ("risk_breakdown",): _tally("harmful_additives", "severity_level"),
        ("categories_count",): lambda b: len(b["_metadata"].get("category_enum") or ()),
    },
    IQM_FILE: {("categories",): _iqm_categories},
    "standardized_botanicals.json": {
        ("categories",): _tally("standardized_botanicals", "category"),
        ("statistics", "total_aliases"): lambda b: sum(len(r.get("aliases") or ()) for r in _records(b, "standardized_botanicals")),
    },
    "ingredient_interaction_rules.json": {
        ("total_rules",): _size("interaction_rules"),
        ("rules_with_dose_thresholds",): _where("interaction_rules", lambda r: bool(r.get("dose_thresholds"))),
    },
    "canonical_equivalences.json": {("total_relationships",): _size("relationships")},
    "clinical_risk_taxonomy.json": {("drug_classes_count",): _size("drug_classes")},
    "cert_verification_overrides.json": {("total_overrides",): _size("overrides")},
    "upc_overrides.json": {("total_overrides",): _size("overrides")},
    "drug_class_vocab.json": {
        ("user_selectable_count",): _where("drug_classes", lambda r: r.get("user_selectable") is True),
        ("rule_only_count",): _where("drug_classes", lambda r: r.get("user_selectable") is False),
    },
    "drug_classes.json": {
        ("total_classes",): _size("classes"),
        ("total_members",): lambda b: sum(len(r.get("member_rxcuis") or ()) for r in _records(b, "classes")),
    },
    "form_keywords_vocab.json": {("total_categories",): _size("categories")},
    "synergy_cluster.json": {
        ("total_clusters",): _size("synergy_clusters"),
        ("citation_coverage", "total_clusters"): _size("synergy_clusters"),
        ("citation_coverage", "clusters_with_sources"): _where("synergy_clusters", lambda r: bool(r.get("sources"))),
    },
    "manufacturer_violations.json": {
        **{("statistics", f"{level}_violations"): _where("manufacturer_violations", lambda r, lv=level: r.get("severity_level") == lv)
           for level in ("critical", "high", "moderate", "low")},
        ("statistics", "resolved_count"): _where("manufacturer_violations", lambda r: r.get("is_resolved") is True),
        ("statistics", "unresolved_count"): _where("manufacturer_violations", lambda r: not r.get("is_resolved")),
    },
    "cert_registry.json": {("total_verified_records",): _size("verified_records")},
    "caers_adverse_event_signals.json": {("total_ingredients_with_signals",): _size("signals")},
    "profile_gate_test_cases.json": {("case_count",): _size("test_cases")},
    "unit_conversions.json": {("statistics", "vitamin_conversions"): _size("vitamin_conversions")},
}


def recount(name: str, blob: dict) -> dict[str, tuple[Any, Any]]:
    """Recompute the counts owned here, in place. Only fields that already exist
    are written. Returns {field: (old, new)} for each field that changed."""
    meta = blob.get("_metadata")
    if not isinstance(meta, dict):
        return {}
    changes: dict[str, tuple[Any, Any]] = {}

    def put(container: Any, key: str, value: Any, label: str) -> None:
        if isinstance(container, dict) and key in container and container[key] != value:
            changes[label] = (container[key], value)
            container[key] = value

    if name not in INTENTIONAL_EXCEPTIONS:
        shape = classify_shape(blob)
        if shape:
            put(meta, "total_entries", shape[1], "total_entries")
    if name == IQM_FILE and isinstance(meta.get("statistics"), dict):
        parents = {k: v for k, v in blob.items() if k != "_metadata"}
        for key, value in iqm_statistics(parents).items():
            put(meta["statistics"], key, value, f"statistics.{key}")
    if name == "cert_claim_rules.json" and isinstance(meta.get("statistics"), dict):
        for key, value in _cert_claim_statistics(blob).items():
            put(meta["statistics"], key, value, f"statistics.{key}")
    for path, derive in DERIVED_COUNTS.get(name, {}).items():
        container = meta
        for step in path[:-1]:
            container = container.get(step) if isinstance(container, dict) else None
        put(container, path[-1], derive(blob), ".".join(path))
    return changes


def _refuse_duplicates(pairs: list[tuple[str, Any]]) -> dict:
    counts = Counter(key for key, _ in pairs)
    duplicates = sorted(key for key, n in counts.items() if n > 1)
    if duplicates:
        raise ValueError(f"duplicate JSON keys (all but the last would be lost): {duplicates}")
    return dict(pairs)


def loads(text: str) -> Any:
    return json.loads(text, object_pairs_hook=_refuse_duplicates)


def load(path: Path) -> Any:
    return loads(Path(path).read_text(encoding="utf-8"))


def entries(blob: dict) -> dict[str, Any]:
    """{entry key: entry}. List items are keyed ``list/id`` (``list[index]``
    without an id); a single wrapping dict's items ``wrapper/key``; any other
    top-level value by its own key (an IQM parent is ``parent_id``)."""
    shape = classify_shape(blob)
    out: dict[str, Any] = {}
    for key, value in blob.items():
        if key == "_metadata":
            continue
        if isinstance(value, list):
            seen: Counter = Counter()
            for index, item in enumerate(value):
                ident = item.get("id") if isinstance(item, dict) else None
                name = f"{key}/{ident}" if ident is not None else f"{key}[{index}]"
                seen[name] += 1
                out[name if seen[name] == 1 else f"{name}#{seen[name]}"] = item
        elif isinstance(value, dict) and shape and shape[0] == "single_payload_dict":
            for sub, item in value.items():
                out[f"{key}/{sub}"] = item
        else:
            out[key] = value
    return out


def _dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def changed_keys(before: dict, after: dict) -> tuple[list[str], list[str], list[str]]:
    """(added, removed, modified) keys between two {key: entry} maps."""
    shared = before.keys() & after.keys()
    return (sorted(after.keys() - before.keys()),
            sorted(before.keys() - after.keys()),
            sorted(k for k in shared if _dump(before[k]) != _dump(after[k])))


_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def save(path: Path, blob: dict) -> dict[str, tuple[Any, Any]]:
    """Recount, bump a date-only ``last_updated`` when an entry changed, write
    canonical JSON. Returns the recount changes. Refuses a file that is not yet
    canonical, so a content batch never hides inside a formatting diff."""
    path = Path(path)
    meta = blob.get("_metadata")
    if path.exists():
        text = path.read_text(encoding="utf-8")
        on_disk = loads(text)
        if text != json_text(on_disk):
            raise ValueError(f"{path} is not canonical JSON: run `data_batch.py format` "
                             "and commit that alone before editing entries")
        if isinstance(meta, dict) and _DATE.match(str(meta.get("last_updated", ""))):
            if any(changed_keys(entries(on_disk), entries(blob))):
                meta["last_updated"] = date.today().isoformat()
    changes = recount(path.name, blob)
    atomic_write_json(path, blob)
    return changes


def at_ref(ref: str, path: Path) -> Any:
    """The file's parsed content at a git ref, or None when the file did not
    exist there. A ref git cannot resolve raises: a typo must not turn every
    entry into an "added" one."""
    rel = Path(path).resolve().relative_to(REPO).as_posix()
    proc = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=REPO,
                          capture_output=True, text=True)
    if proc.returncode == 0:
        return json.loads(proc.stdout)
    if "does not exist in" in proc.stderr or "exists on disk, but not in" in proc.stderr:
        return None
    raise ValueError(f"git show {ref}:{rel} failed: {proc.stderr.strip()}")


def landed(name: str, before: Optional[dict], after: dict,
           expected: Optional[set[str]]) -> tuple[list[str], int]:
    """Report lines and problem count for a batch: every expected entry changed,
    nothing else did, and the counts owned here match the entries."""
    added, removed, modified = changed_keys(entries(before or {}), entries(after))
    kind = {**dict.fromkeys(added, "added"), **dict.fromkeys(removed, "removed"),
            **dict.fromkeys(modified, "changed")}
    lines, problems = [], 0
    for key in sorted(kind):
        unexpected = expected is not None and key not in expected
        problems += unexpected
        lines.append(f"{kind[key]:<8} {key}" + ("  UNEXPECTED" if unexpected else ""))
    for key in sorted((expected or set()) - kind.keys()):
        problems += 1
        lines.append(f"MISSING  {key}  (expected to change)")
    for field, (old, new) in recount(name, copy.deepcopy(after)).items():
        problems += 1
        lines.append(f"METADATA {field} is {old}, entries give {new}")
    lines.append(f"{len(kind)} entries changed, {problems} problem(s)")
    return lines, problems


def format_file(path: Path) -> bool:
    """Rewrite as canonical JSON. True when the file changed."""
    text = Path(path).read_text(encoding="utf-8")
    blob = loads(text)
    new = json_text(blob)
    if new == text:
        return False
    if json.loads(new) != blob:
        raise ValueError(f"{path}: canonical text would change the content")
    atomic_write_json(Path(path), blob)
    return True


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    check_p = sub.add_parser("check", help="landed check against a git ref")
    check_p.add_argument("file", type=Path)
    check_p.add_argument("--since", required=True, help="git ref before the batch, e.g. origin/main")
    group = check_p.add_mutually_exclusive_group()
    group.add_argument("--expect", help="comma-separated entry keys the batch changes")
    group.add_argument("--expect-file", type=Path, help="entry keys, one per line")
    for command in ("recount", "format"):
        sub.add_parser(command).add_argument("files", type=Path, nargs="+")
    args = parser.parse_args(argv)

    if args.command == "check":
        expected = None
        if args.expect is not None:
            expected = {k.strip() for k in args.expect.split(",") if k.strip()}
        elif args.expect_file is not None:
            expected = {line.strip() for line in args.expect_file.read_text().splitlines() if line.strip()}
        lines, problems = landed(args.file.name, at_ref(args.since, args.file), load(args.file), expected)
        print("\n".join(lines))
        return 1 if problems else 0
    for path in args.files:
        if args.command == "format":
            print(f"{'formatted' if format_file(path) else 'canonical'} {path}")
        else:
            changes = save(path, load(path))
            print(f"{path}: " + (", ".join(f"{f} {o}->{n}" for f, (o, n) in changes.items()) or "counts match"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
