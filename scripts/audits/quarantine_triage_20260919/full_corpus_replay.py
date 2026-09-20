#!/usr/bin/env python3
"""Full frozen-corpus cleaner replay — Phase-3 integration gate (2026-09-20).

Run one ARM of the cleaner over the complete frozen raw DSLD ingest corpus and
emit a compact per-product signature as JSONL. Two arms are compared with
``--compare``; both arms must read byte-identical raw records so every delta is
code-induced (team instruction #9: never compare two differently refreshed
sources).

The arm's code is selected with ``--scripts-dir`` so the same harness file can
run the base worktree and the integration worktree without being copied:

    --arm base        --scripts-dir /path/to/base/scripts
    --arm integrated  --scripts-dir /path/to/integration/scripts

Every import inside the cleaner (``form_vocab``, ``scoring_input_contract``,
``identity``, ...) and every data file it loads resolves relative to the arm's
own ``scripts/`` tree, because that directory is prepended to ``sys.path`` and
the module is imported from it.

Usage:
    "$PG_PYTHON" full_corpus_replay.py --arm base \
        --scripts-dir /tmp/pg_base/scripts \
        --raw-root "$HOME/Downloads/PharmaGuide_Datasets/staging/brands" \
        --out /tmp/replay_base.jsonl [--workers 8] [--limit N] [--ids a,b]

    "$PG_PYTHON" full_corpus_replay.py --compare /tmp/replay_base.jsonl \
        --against /tmp/replay_integrated.jsonl --out /tmp/replay_diff.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# Populated in the parent, inherited by fork-based workers, and re-set by
# _worker_init when the platform uses spawn.
SCRIPTS_DIR = ""
NORMALIZER_CLASS = None
_NORMALIZER = None


def _normalizer():
    """One normalizer per worker process, exactly like the production batch
    processor (batch_processor.init_worker: "initialize normalizer once per
    worker, not per file"), so the replay mirrors production state handling.
    """
    global _NORMALIZER
    if _NORMALIZER is None:
        _NORMALIZER = NORMALIZER_CLASS()
    return _NORMALIZER


# Standardization-marker identities introduced by the accepted remediation
# (IQM entries + cleaner role). Used only to bucket replay deltas, never to
# change pipeline behaviour.
MARKER_IDENTITIES = {"withaferin_a", "miroestrol"}


def _load_arm(scripts_dir: str):
    """Import the arm's enhanced_normalizer with its own sibling modules."""
    resolved = str(Path(scripts_dir).resolve())
    if resolved in sys.path:
        sys.path.remove(resolved)
    sys.path.insert(0, resolved)
    for name in list(sys.modules):
        if name == "enhanced_normalizer" or name.startswith(
            ("form_vocab", "scoring_input_contract", "identity", "constants")
        ):
            del sys.modules[name]
    import enhanced_normalizer  # noqa: PLC0415

    if Path(enhanced_normalizer.__file__).resolve().parent != Path(resolved):
        raise SystemExit(
            f"arm import resolved to {enhanced_normalizer.__file__}, not {resolved}"
        )
    return enhanced_normalizer.EnhancedDSLDNormalizer


def _worker_init(scripts_dir: str) -> None:
    global NORMALIZER_CLASS, SCRIPTS_DIR
    SCRIPTS_DIR = scripts_dir
    NORMALIZER_CLASS = _load_arm(scripts_dir)


def _norm(value):
    """Freeze a scalar/simple structure into a JSON-stable primitive."""
    if isinstance(value, float) and value == int(value):
        return value
    return value


def _row_signature(row: dict, *, active: bool) -> dict:
    forms = row.get("forms")
    form_names = []
    if isinstance(forms, list):
        for form in forms:
            if isinstance(form, dict):
                form_names.append(str(form.get("name") or ""))
            else:
                form_names.append(str(form))
    sig = {
        "name": str(row.get("name") or ""),
        "raw": str(row.get("raw_source_text") or ""),
        "cid": row.get("canonical_id"),
        "norm": row.get("normalized_key"),
        "q": _norm(row.get("quantity")),
        "u": row.get("unit"),
        "forms": form_names,
    }
    if active:
        sig.update(
            {
                "role": row.get("cleaner_row_role"),
                "elig": row.get("score_eligible_by_cleaner"),
                "excl": row.get("score_exclusion_reason"),
                "dose_class": row.get("dose_class"),
                "pb": row.get("parentBlend"),
                "pbm": _norm(row.get("parentBlendMass")),
                "pbu": row.get("parentBlendUnit"),
                "nested": row.get("isNestedIngredient"),
                "dv": _norm(row.get("dailyValue")),
                "path": row.get("raw_source_path"),
                "mapped": row.get("mapped"),
                "match": row.get("cleaner_match_method"),
                "display": row.get("label_display_name"),
                "pctdv": row.get("percentDailyValue"),
            }
        )
    else:
        sig.update(
            {
                "role": row.get("cleaner_row_role"),
                "elig": row.get("score_eligible_by_cleaner"),
                "excl": row.get("score_exclusion_reason"),
            }
        )
    return sig


def _display_signature(cleaned: dict) -> list:
    rows = []
    for row in cleaned.get("display_ingredients") or []:
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                "dn": str(row.get("display_name") or ""),
                "dt": row.get("display_type"),
                "si": row.get("score_included"),
                "cid": row.get("canonical_id"),
                "sec": row.get("source_section"),
            }
        )
    return rows


def _nutrition_signature(cleaned: dict) -> dict:
    info = cleaned.get("nutritionalInfo")
    if not isinstance(info, dict):
        return {}
    out = {}
    for key, value in sorted(info.items()):
        if isinstance(value, dict):
            out[key] = {
                k: _norm(v)
                for k, v in sorted(value.items())
                if isinstance(v, (int, float, str, bool, type(None)))
            }
        elif isinstance(value, (int, float, str, bool, type(None))):
            out[key] = _norm(value)
    return out


def signature(path_str: str) -> dict:
    path = Path(path_str)
    raw_bytes = path.read_bytes()
    fingerprint = hashlib.sha1(raw_bytes).hexdigest()
    try:
        raw = json.loads(raw_bytes)
    except Exception as exc:  # unreadable ingest file — recorded, never skipped
        return {
            "id": path.stem,
            "file": path.name,
            "sha1": fingerprint,
            "load_error": f"{type(exc).__name__}: {exc}",
        }
    dsld_id = str(raw.get("id") or path.stem)
    try:
        normalizer = _normalizer()
        cleaned = normalizer.normalize_product(raw)
    except Exception:
        return {
            "id": dsld_id,
            "file": path.name,
            "sha1": fingerprint,
            "crash": traceback.format_exc(limit=8),
        }
    return _assemble(dsld_id, path.name, fingerprint, raw, cleaned)


def signature_from_stored(path_str: str) -> dict:
    """Signature for a record already stored in the frozen corpus.

    A stored ``cleaned_batch_*.json`` entry carries the cleaner's own output
    fields, so the same signature can be built without re-running any cleaner.
    This is what lets the frozen production corpus be the ``before`` arm.
    """
    path = Path(path_str)
    try:
        cleaned = json.loads(path.read_bytes())
    except Exception as exc:
        return {
            "id": path.stem,
            "file": path.name,
            "sha1": None,
            "load_error": f"{type(exc).__name__}: {exc}",
        }
    dsld_id = str(cleaned.get("id") or path.stem)
    return _assemble(dsld_id, path.name, None, cleaned, cleaned)


def _assemble(dsld_id: str, file_name: str, fingerprint, raw: dict, cleaned: dict) -> dict:
    actives = [
        _row_signature(row, active=True)
        for row in (cleaned.get("activeIngredients") or [])
        if isinstance(row, dict)
    ]
    inactives = [
        _row_signature(row, active=False)
        for row in (cleaned.get("inactiveIngredients") or [])
        if isinstance(row, dict)
    ]
    display = _display_signature(cleaned)
    eligible = [row for row in actives if row.get("elig")]
    dosed = [
        row
        for row in eligible
        if isinstance(row.get("q"), (int, float))
        and row["q"] > 0
        and str(row.get("u") or "").strip().lower()
        not in {"", "unspecified", "none", "n/a"}
    ]
    return {
        "id": dsld_id,
        "file": file_name,
        "sha1": fingerprint,
        "name": str(cleaned.get("fullName") or raw.get("fullName") or ""),
        "brand": str(cleaned.get("brandName") or raw.get("brandName") or ""),
        "actives": actives,
        "inactives": inactives,
        "display": display,
        "nutrition": _nutrition_signature(cleaned),
        # The label ledger enumerates every source row the cleaner saw. Keeping
        # its paths in the signature is what makes "no source row silently
        # disappeared" a checkable invariant rather than an assertion.
        "source_paths": sorted(
            {
                str(row.get("raw_source_path") or "")
                for row in (cleaned.get("label_source_rows") or [])
                if isinstance(row, dict)
            }
        ),
        "omissions": sorted(
            (
                str(row.get("raw_source_path") or ""),
                str(row.get("omission_reason") or ""),
                str(row.get("raw_source_text") or ""),
            )
            for row in (cleaned.get("label_ledger_omissions") or [])
            if isinstance(row, dict)
        ),
        "counts": {
            "actives": len(actives),
            "inactives": len(inactives),
            "eligible": len(eligible),
            "dosed_eligible": len(dosed),
            "display": len(display),
            "source_rows": len(cleaned.get("label_source_rows") or []),
            "ledger_omissions": len(cleaned.get("label_ledger_omissions") or []),
            "raw_actives": cleaned.get("raw_actives_count"),
            "raw_inactives": cleaned.get("raw_inactives_count"),
        },
        "display_types": _count_types(display),
        "roles": _count_roles(actives),
    }


def _count_types(display: list) -> dict:
    counts: dict = {}
    for row in display:
        key = str(row.get("dt"))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _count_roles(actives: list) -> dict:
    counts: dict = {}
    for row in actives:
        key = str(row.get("role"))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def discover(raw_root: Path, limit: int | None, ids: set) -> list:
    files = sorted(raw_root.glob("*/*.json"))
    files = [f for f in files if not f.name.startswith(".")]
    if ids:
        files = [f for f in files if f.stem in ids]
    if limit:
        files = files[:limit]
    return files


def discover_stored(products_root: Path) -> list:
    return sorted(products_root.glob("output_*/cleaned/cleaned_batch_*.json"))


def run_arm(args) -> int:
    global NORMALIZER_CLASS, SCRIPTS_DIR
    ids = {token.strip() for token in (args.ids or "").split(",") if token.strip()}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if args.from_stored:
        products_root = Path(args.products_root).expanduser()
        batches = discover_stored(products_root)
        print(f"[stored] {len(batches)} cleaned batches under {products_root}", flush=True)
        written = crashes = 0
        with out.open("w", encoding="utf-8") as handle:
            for path in batches:
                for record in json.loads(path.read_bytes()):
                    sig = signature_from_stored_record(record, path.name)
                    if sig.get("crash"):
                        crashes += 1
                    handle.write(json.dumps(sig, sort_keys=True) + "\n")
                    written += 1
        print(f"[stored] wrote {written} signatures to {out} (crashes={crashes})")
        return 0

    SCRIPTS_DIR = args.scripts_dir
    NORMALIZER_CLASS = _load_arm(args.scripts_dir)
    raw_root = Path(args.raw_root).expanduser()
    files = discover(raw_root, args.limit, ids)
    print(f"[{args.arm}] {len(files)} raw records from {raw_root}", flush=True)

    written = 0
    crashes = 0
    with out.open("w", encoding="utf-8") as handle:
        if args.workers > 1:
            with ProcessPoolExecutor(
                max_workers=args.workers,
                initializer=_worker_init,
                initargs=(args.scripts_dir,),
            ) as pool:
                futures = {pool.submit(signature, str(f)): f for f in files}
                for index, future in enumerate(as_completed(futures), 1):
                    record = future.result()
                    if record.get("crash"):
                        crashes += 1
                    handle.write(json.dumps(record, sort_keys=True) + "\n")
                    written += 1
                    if index % 500 == 0:
                        print(
                            f"[{args.arm}] {index}/{len(files)} (crashes={crashes})",
                            flush=True,
                        )
        else:
            for index, path in enumerate(files, 1):
                record = signature(str(path))
                if record.get("crash"):
                    crashes += 1
                handle.write(json.dumps(record, sort_keys=True) + "\n")
                written += 1
                if index % 500 == 0:
                    print(
                        f"[{args.arm}] {index}/{len(files)} (crashes={crashes})",
                        flush=True,
                    )
    print(f"[{args.arm}] wrote {written} signatures to {out} (crashes={crashes})")
    return 0


def signature_from_stored_record(record: dict, file_name: str) -> dict:
    dsld_id = str(record.get("id") or "")
    return _assemble(dsld_id, file_name, None, record, record)


def _load_jsonl(path: Path) -> dict:
    out = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            out[str(record.get("id"))] = record
    return out


def _row_key(row: dict) -> tuple:
    """Identity of a source row, deliberately NOT including its role.

    Keying on the role would turn every role change into a remove+add pair and
    hide the delta that actually matters (role/eligibility/dose per row).
    """
    return (
        str(row.get("path")),
        str(row.get("cid")),
        str(row.get("name")),
        str(row.get("u")),
    )


def _diff_rows(before: list, after: list) -> list:
    """Row-level diff keyed by identity/role, tolerant of reordering."""
    b = {_row_key(r): r for r in before}
    a = {_row_key(r): r for r in after}
    changes = []
    for key in sorted(set(b) | set(a)):
        left, right = b.get(key), a.get(key)
        if left is None:
            changes.append({"op": "added", "after": right})
        elif right is None:
            changes.append({"op": "removed", "before": left})
        elif left != right:
            delta = {
                field: {"before": left.get(field), "after": right.get(field)}
                for field in set(left) | set(right)
                if left.get(field) != right.get(field)
            }
            changes.append({"op": "changed", "before": left, "after": right, "delta": delta})
    return changes


def classify(changes: list, before: dict, after: dict) -> list:
    """Bucket a product's row deltas into the expected defect families."""
    reasons = set()
    for change in changes:
        row = change.get("after") or change.get("before") or {}
        name = str(row.get("name") or "").lower()
        unit = str(row.get("u") or "").lower()
        before_role = str((change.get("before") or {}).get("role") or "")
        after_role = str((change.get("after") or {}).get("role") or "")
        if after_role == "specification_limit" or before_role == "specification_limit":
            reasons.add("specification_limit")
        if after_role == "daily_value_no_amount" or before_role == "daily_value_no_amount":
            reasons.add("daily_value_no_amount")
        if after_role == "standardization_marker" or before_role == "standardization_marker":
            reasons.add("standardization_marker")
        if "omega" in name or row.get("cid") in {"epa", "dha", "dpa", "ala"} or "omega" in str(
            row.get("pb") or ""
        ).lower():
            reasons.add("omega_aggregate_owner")
        if unit in {"ppm", "ppb", "parts per million", "parts per billion"} or "ginkgolic" in name:
            reasons.add("ppm_ppb_row")
    # Identity-resolution changes are the standardization-marker family's second
    # half: the row keeps its dose and role but gains a canonical identity
    # (withaferin_a / miroestrol resolving through the new IQM entries).
    for change in changes:
        before_cid = str((change.get("before") or {}).get("cid") or "")
        after_cid = str((change.get("after") or {}).get("cid") or "")
        if before_cid != after_cid and ({before_cid, after_cid} & MARKER_IDENTITIES):
            reasons.add("standardization_marker")
    if not reasons:
        reasons.add("outside_expected_families")
    return sorted(reasons)


def compare(args) -> int:
    base = _load_jsonl(Path(args.compare))
    after = _load_jsonl(Path(args.against))
    only_base = sorted(set(base) - set(after))
    only_after = sorted(set(after) - set(base))

    changed = []
    unchanged = 0
    crashed_before = []
    crashed_after = []
    fingerprint_mismatch = []
    control_unchanged = 0

    for dsld_id in sorted(set(base) & set(after)):
        left, right = base[dsld_id], after[dsld_id]
        if left.get("sha1") and right.get("sha1") and left.get("sha1") != right.get("sha1"):
            fingerprint_mismatch.append(dsld_id)
        if left.get("crash"):
            crashed_before.append(dsld_id)
        if right.get("crash"):
            crashed_after.append(dsld_id)
        if left.get("crash") or right.get("crash"):
            changed.append(
                {
                    "id": dsld_id,
                    "name": right.get("name") or left.get("name"),
                    "crash_before": bool(left.get("crash")),
                    "crash_after": bool(right.get("crash")),
                }
            )
            continue
        # ``file`` is the batch file the record happened to live in, and ``sha1``
        # identifies the input file for the raw arms only; neither is a property
        # of the cleaned representation.
        left_body = {k: v for k, v in left.items() if k not in ("file", "sha1")}
        right_body = {k: v for k, v in right.items() if k not in ("file", "sha1")}
        if left_body == right_body:
            unchanged += 1
            continue
        row_changes = _diff_rows(left.get("actives") or [], right.get("actives") or [])
        inactive_changes = _diff_rows(
            left.get("inactives") or [], right.get("inactives") or []
        )
        display_changes = _diff_rows(left.get("display") or [], right.get("display") or [])
        reasons = classify(row_changes, left, right)
        changed.append(
            {
                "id": dsld_id,
                "name": right.get("name") or left.get("name"),
                "brand": right.get("brand") or left.get("brand"),
                "reasons": reasons,
                "counts_before": left.get("counts"),
                "counts_after": right.get("counts"),
                "roles_before": left.get("roles"),
                "roles_after": right.get("roles"),
                "display_types_before": left.get("display_types"),
                "display_types_after": right.get("display_types"),
                "row_changes": row_changes,
                "inactive_changes": inactive_changes,
                "display_changes": display_changes,
                "display_changed": left.get("display") != right.get("display"),
                "nutrition_changed": left.get("nutrition") != right.get("nutrition"),
            }
        )

    families: dict = {}
    for item in changed:
        for reason in item.get("reasons") or ["crash"]:
            families.setdefault(reason, []).append(item["id"])

    summary = {
        "records_compared": len(set(base) & set(after)),
        "records_unchanged": unchanged,
        "records_changed": len(changed),
        "crashes_after": len(crashed_after),
        "crash_ids_after": crashed_after[:200],
        "crashes_before": len(crashed_before),
        "crash_ids_before": crashed_before[:200],            "input_fingerprint_mismatches": fingerprint_mismatch,
            "fingerprint_verified": bool(
                not fingerprint_mismatch and all(base[i].get("sha1") for i in set(base) & set(after))
            ),
        "only_in_base": only_base,
        "only_in_after": only_after,
        "family_counts": {k: len(v) for k, v in sorted(families.items())},
        "families": {k: v for k, v in sorted(families.items())},
        "changed_ids": [item["id"] for item in changed],
        "changed": changed,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in (
        "records_compared",
        "records_unchanged",
        "records_changed",
        "crashes_after",
        "crashes_before",
        "input_fingerprint_mismatches",
        "only_in_base",
        "only_in_after",
        "family_counts",
    )}, indent=1))
    print(f"detail -> {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", help="label for this arm (run mode)")
    parser.add_argument("--scripts-dir", help="path to the arm's scripts/ directory")
    parser.add_argument(
        "--raw-root",
        default=os.environ.get(
            "PHARMAGUIDE_RAW_CORPUS",
            str(Path.home() / "Downloads" / "PharmaGuide_Datasets" / "staging" / "brands"),
        ),
        help="root holding <Brand>/<dsld_id>.json raw ingest records",
    )
    parser.add_argument("--out")
    parser.add_argument(
        "--from-stored",
        action="store_true",
        help="build signatures from the frozen corpus itself (the before arm)",
    )
    parser.add_argument(
        "--products-root",
        default="scripts/products",
        help="frozen per-brand pipeline output root",
    )
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ids", help="comma-separated DSLD ids")
    parser.add_argument("--compare", help="base JSONL (compare mode)")
    parser.add_argument("--against", help="other arm JSONL (compare mode)")
    args = parser.parse_args()

    if args.compare and args.against:
        return compare(args)
    if args.from_stored:
        if not args.out:
            parser.error("stored mode needs --out")
        return run_arm(args)
    if not (args.arm and args.scripts_dir and args.out):
        parser.error("run mode needs --arm/--scripts-dir/--out")
    return run_arm(args)


if __name__ == "__main__":
    raise SystemExit(main())
