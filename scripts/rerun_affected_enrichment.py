#!/usr/bin/env python3
"""
Build an affected-only subset after interaction rule changes and optionally rerun enrich/score.

Typical usage:
  python rerun_affected_enrichment.py \
    --prefix output_Thorne \
    --changed-canonical-ids vitamin_e,vitamin_c,dong_quai,yohimbe \
    --run-enrich --run-score
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Set, Tuple, Dict


def _load_json_file(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _iter_json_files(path: Path) -> Iterable[Path]:
    if not path.exists():
        return []
    return sorted(p for p in path.glob("*.json") if p.is_file())


def _normalize_db_key(value: str) -> str:
    return str(value or "").strip().lower()


def _row_subject_refs(row: dict) -> Set[Tuple[str, str]]:
    refs: Set[Tuple[str, str]] = set()
    canonical = str(row.get("canonical_id") or "").strip()
    if canonical:
        refs.add(("ingredient_quality_map", canonical))

    source = _normalize_db_key(row.get("recognition_source"))
    matched = str(
        row.get("matched_entry_id")
        or row.get("recognized_entry_id")
        or ""
    ).strip()
    if source and matched:
        refs.add((source, matched))
    return refs


def _product_hit(
    product: dict,
    changed_ids: Set[str],
    changed_subject_refs: Set[Tuple[str, str]],
) -> bool:
    iq = (product or {}).get("ingredient_quality_data") or {}
    rows: List[dict] = []
    for key in ("ingredients", "ingredients_skipped"):
        value = iq.get(key)
        if isinstance(value, list):
            rows.extend(x for x in value if isinstance(x, dict))
    for row in rows:
        refs = _row_subject_refs(row)
        if refs & changed_subject_refs:
            return True
        # Legacy/manual mode: allow matching by raw id token only.
        row_ids = {ref_id for _, ref_id in refs if ref_id}
        if row_ids & changed_ids:
            return True
    return False


def _product_id(record: dict) -> str:
    return str(record.get("dsld_id") or record.get("id") or "").strip()


def _collect_affected_ids(
    enriched_dir: Path,
    changed_ids: Set[str],
    changed_subject_refs: Set[Tuple[str, str]],
) -> Tuple[Set[str], List[str]]:
    affected: Set[str] = set()
    warnings: List[str] = []
    for file_path in _iter_json_files(enriched_dir):
        try:
            data = _load_json_file(file_path)
        except Exception as exc:
            warnings.append(f"Failed reading {file_path.name}: {exc}")
            continue
        if not isinstance(data, list):
            warnings.append(f"Skipped non-list JSON: {file_path.name}")
            continue
        for product in data:
            if not isinstance(product, dict):
                continue
            if _product_hit(product, changed_ids, changed_subject_refs):
                pid = _product_id(product)
                if pid:
                    affected.add(pid)
    return affected, warnings


def _build_cleaned_subset(cleaned_dir: Path, subset_cleaned_dir: Path, affected_ids: Set[str]) -> Tuple[int, int, int, List[str]]:
    subset_cleaned_dir.mkdir(parents=True, exist_ok=True)
    scanned_files = 0
    written_files = 0
    written_products = 0
    warnings: List[str] = []

    for file_path in _iter_json_files(cleaned_dir):
        scanned_files += 1
        try:
            data = _load_json_file(file_path)
        except Exception as exc:
            warnings.append(f"Failed reading {file_path.name}: {exc}")
            continue
        if not isinstance(data, list):
            warnings.append(f"Skipped non-list JSON: {file_path.name}")
            continue

        subset = [
            product
            for product in data
            if isinstance(product, dict) and _product_id(product) in affected_ids
        ]
        if not subset:
            continue

        out_path = subset_cleaned_dir / file_path.name
        out_path.write_text(json.dumps(subset, indent=2) + "\n", encoding="utf-8")
        written_files += 1
        written_products += len(subset)

    return scanned_files, written_files, written_products, warnings


def _run_command(cmd: List[str]) -> int:
    print("Executing:", " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    return result.returncode


def _load_rules_by_id(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    data = _load_json_file(path)
    raw = data.get("interaction_rules", []) if isinstance(data, dict) else []
    out: Dict[str, Dict[str, str]] = {}
    if not isinstance(raw, list):
        return out
    for rule in raw:
        if not isinstance(rule, dict):
            continue
        rule_id = str(rule.get("id") or "").strip()
        subject = rule.get("subject_ref") if isinstance(rule.get("subject_ref"), dict) else {}
        db_key = str(subject.get("db") or "").strip()
        canonical = str(subject.get("canonical_id") or "").strip()
        if not rule_id:
            continue
        out[rule_id] = {"db": db_key, "canonical_id": canonical}
    return out


def _auto_changed_subject_refs_from_git(scripts_root: Path, rules_path: Path) -> Set[Tuple[str, str]]:
    repo_root = scripts_root.parent.resolve()
    current_rules = _load_rules_by_id(rules_path)
    current_all = {
        (_normalize_db_key(v.get("db")), str(v.get("canonical_id") or "").strip())
        for v in current_rules.values()
        if str(v.get("canonical_id") or "").strip()
    }

    rel_rules = rules_path.resolve().relative_to(repo_root).as_posix()
    old_rules: Dict[str, Dict[str, str]] = {}
    try:
        old_raw = subprocess.check_output(
            ["git", "-C", str(repo_root), "show", f"HEAD:{rel_rules}"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        old_data = json.loads(old_raw)
        raw = old_data.get("interaction_rules", []) if isinstance(old_data, dict) else []
        if isinstance(raw, list):
            for rule in raw:
                if not isinstance(rule, dict):
                    continue
                rule_id = str(rule.get("id") or "").strip()
                subject = rule.get("subject_ref") if isinstance(rule.get("subject_ref"), dict) else {}
                db_key = str(subject.get("db") or "").strip()
                canonical = str(subject.get("canonical_id") or "").strip()
                if rule_id:
                    old_rules[rule_id] = {"db": db_key, "canonical_id": canonical}
    except Exception:
        # If no git baseline is available, conservatively rerun by all current subjects.
        return current_all

    changed: Set[Tuple[str, str]] = set()
    for rule_id, ref in current_rules.items():
        old_ref = old_rules.get(rule_id)
        if old_ref != ref:
            db_key = _normalize_db_key(ref.get("db"))
            canonical = str(ref.get("canonical_id", "")).strip()
            if db_key and canonical:
                changed.add((db_key, canonical))
    for rule_id, ref in old_rules.items():
        if rule_id not in current_rules:
            db_key = _normalize_db_key(ref.get("db"))
            canonical = str(ref.get("canonical_id", "")).strip()
            if db_key and canonical:
                changed.add((db_key, canonical))
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild affected-only subset and optionally rerun enrichment/scoring."
    )
    parser.add_argument(
        "--prefix",
        required=True,
        help="Dataset prefix under scripts/ (e.g., output_Thorne, output_Capsules)",
    )
    parser.add_argument(
        "--changed-canonical-ids",
        required=False,
        help="Comma-separated canonical IDs changed in rules (e.g., vitamin_e,vitamin_c)",
    )
    parser.add_argument(
        "--auto-changed-from-git",
        action="store_true",
        help="Auto-detect changed canonical IDs in interaction rules by comparing working tree vs HEAD",
    )
    parser.add_argument(
        "--scripts-root",
        default=None,
        help="Scripts root directory (defaults to folder containing this script)",
    )
    parser.add_argument(
        "--subset-root",
        default=None,
        help="Subset workspace root (default: <scripts-root>/tmp_reenrich)",
    )
    parser.add_argument(
        "--run-enrich",
        action="store_true",
        help="Run enrich_supplements_v3.py on subset cleaned output",
    )
    parser.add_argument(
        "--run-score",
        action="store_true",
        help="Run score_supplements.py on subset enriched output",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build subset and print commands without running enrich/score",
    )
    args = parser.parse_args()

    scripts_root = Path(args.scripts_root).resolve() if args.scripts_root else Path(__file__).parent.resolve()
    subset_root = Path(args.subset_root).resolve() if args.subset_root else (scripts_root / "tmp_reenrich")

    prefix = args.prefix.strip()
    cleaned_dir = scripts_root / prefix / "cleaned"
    enriched_dir = scripts_root / f"{prefix}_enriched" / "enriched"
    rules_path = scripts_root / "data" / "ingredient_interaction_rules.json"

    subset_cleaned_dir = subset_root / prefix / "cleaned"
    subset_enriched_root = subset_root / f"{prefix}_enriched"
    subset_enriched_dir = subset_enriched_root / "enriched"
    subset_scored_dir = subset_root / f"{prefix}_scored"

    if not cleaned_dir.exists():
        print(f"Missing cleaned dir: {cleaned_dir}", file=sys.stderr)
        return 2
    if not enriched_dir.exists():
        print(f"Missing enriched dir (used for impact detection): {enriched_dir}", file=sys.stderr)
        return 2
    if not rules_path.exists():
        print(f"Missing interaction rules file: {rules_path}", file=sys.stderr)
        return 2

    changed_ids: Set[str] = set()
    changed_subject_refs: Set[Tuple[str, str]] = set()
    if args.changed_canonical_ids:
        changed_ids |= {
            token.strip()
            for token in args.changed_canonical_ids.split(",")
            if token.strip()
        }
        # Backward-compatible default interpretation: manual IDs target IQM canonicals.
        changed_subject_refs |= {("ingredient_quality_map", token) for token in changed_ids}
    if args.auto_changed_from_git:
        auto_refs = _auto_changed_subject_refs_from_git(scripts_root=scripts_root, rules_path=rules_path)
        auto_display = ",".join(sorted(f"{db}:{cid}" for db, cid in auto_refs)) or "(none)"
        print(f"Auto-detected subject refs from git: {auto_display}")
        changed_subject_refs |= auto_refs
        changed_ids |= {cid for _, cid in auto_refs if cid}

    if not changed_ids and not changed_subject_refs:
        print(
            "No canonical IDs provided. Use --changed-canonical-ids and/or --auto-changed-from-git.",
            file=sys.stderr,
        )
        return 2

    print(f"scripts_root={scripts_root}")
    print(f"prefix={prefix}")
    print(f"changed_ids={sorted(changed_ids)}")
    print(f"changed_subject_refs={sorted(changed_subject_refs)}")
    print(f"source cleaned={cleaned_dir}")
    print(f"source enriched={enriched_dir}")
    print(f"subset root={subset_root}")

    affected_ids, warnings_a = _collect_affected_ids(
        enriched_dir=enriched_dir,
        changed_ids=changed_ids,
        changed_subject_refs=changed_subject_refs,
    )
    for warning in warnings_a:
        print("WARN:", warning)
    print(f"Affected products: {len(affected_ids)}")
    if not affected_ids:
        print("No affected products detected; nothing to rerun.")
        return 0

    scanned, written_files, written_products, warnings_b = _build_cleaned_subset(
        cleaned_dir=cleaned_dir,
        subset_cleaned_dir=subset_cleaned_dir,
        affected_ids=affected_ids,
    )
    for warning in warnings_b:
        print("WARN:", warning)
    print(f"Scanned cleaned batch files: {scanned}")
    print(f"Wrote subset cleaned files: {written_files}")
    print(f"Wrote subset products: {written_products}")
    print(f"Subset cleaned dir: {subset_cleaned_dir}")

    if args.run_score and not args.run_enrich and not subset_enriched_dir.exists():
        print(
            f"Cannot run --run-score without subset enriched data. Missing: {subset_enriched_dir}",
            file=sys.stderr,
        )
        return 2

    if args.run_enrich:
        enrich_cmd = [
            sys.executable,
            str(scripts_root / "enrich_supplements_v3.py"),
            "--input-dir",
            str(subset_cleaned_dir),
            "--output-dir",
            str(subset_enriched_root),
        ]
        if args.dry_run:
            print("DRY RUN:", " ".join(enrich_cmd))
        else:
            code = _run_command(enrich_cmd)
            if code != 0:
                return code

    if args.run_score:
        score_cmd = [
            sys.executable,
            str(scripts_root / "score_supplements.py"),
            "--input-dir",
            str(subset_enriched_dir),
            "--output-dir",
            str(subset_scored_dir),
        ]
        if args.dry_run:
            print("DRY RUN:", " ".join(score_cmd))
        else:
            code = _run_command(score_cmd)
            if code != 0:
                return code

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
