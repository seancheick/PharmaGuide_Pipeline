"""Score a candidate extraction configuration against the frozen holdout.

Protocol: scripts/submission_review/HOLDOUT.md. The set itself (manifest,
gold labels, photos, runs) lives outside git under reports/submission_holdout
by default. This module only scores files; it never calls a provider.

    python3 -m scripts.submission_review.extraction.benchmark \
        --holdout reports/submission_holdout --run runs/2026-09-10-gemma4 \
        --split development
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .envelope import LabelDraftError, validate_label_draft_v1

MANIFEST_SCHEMA = "submission_holdout_v1"
GOLD_SCHEMA = "gold_label_v1"
FAILURE_SCHEMA = "extraction_failure_v1"
SPLITS = ("development", "holdout")

# Frozen gates (HOLDOUT.md). Change only through a dated amendment there.
GATES: dict[str, Any] = {
    "schema_safe_rate": 1.0,
    "row_recall": 0.99,
    "tuple_exact_rate": 0.99,
    "invented_actives": 0,
    "wrong_product_substitutions": 0,
    "magnitude_errors": 0,
    "expected_abstentions_honoured_rate": 1.0,
    "latency_p95_seconds": 60.0,
}

_NORMALIZE = re.compile(r"[^a-z0-9]+")


class BenchmarkError(ValueError):
    """The holdout set or the run violates the frozen protocol."""


def _norm(text: Any) -> str:
    return _NORMALIZE.sub(" ", str(text or "").casefold()).strip()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float] | None:
    if total <= 0:
        return None
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4))


def _rate(successes: int, total: int) -> dict[str, Any]:
    return {
        "n": successes,
        "N": total,
        "rate": round(successes / total, 4) if total else None,
        "ci95": _wilson(successes, total),
    }


def load_gold(holdout_dir: Path, entry: dict[str, Any]) -> dict[str, Any]:
    gold = _load_json(holdout_dir / entry["gold"])
    if gold.get("schema_version") != GOLD_SCHEMA:
        raise BenchmarkError(f"{entry['product_key']}: gold schema must be {GOLD_SCHEMA}")
    if gold.get("product_key") != entry["product_key"]:
        raise BenchmarkError(f"{entry['product_key']}: gold product_key mismatch")
    checkers = gold.get("checked_by") or []
    names = {str(c.get("checker", "")).strip() for c in checkers}
    if len(checkers) < 2 or len(names) < 2 or "" in names:
        raise BenchmarkError(f"{entry['product_key']}: gold needs two distinct human checkers")
    for checker in checkers:
        if any(key in checker for key in ("model", "provider", "generated_by")):
            raise BenchmarkError(f"{entry['product_key']}: gold must be human-checked")
    if gold.get("expected") not in ("draft", "abstain"):
        raise BenchmarkError(f"{entry['product_key']}: gold expected must be draft|abstain")
    return gold


def load_manifest(holdout_dir: Path, split: str) -> list[dict[str, Any]]:
    manifest = _load_json(holdout_dir / "manifest.json")
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise BenchmarkError(f"manifest schema must be {MANIFEST_SCHEMA}")
    if not manifest.get("frozen_at"):
        raise BenchmarkError("manifest is not frozen (frozen_at missing)")
    products = [p for p in manifest.get("products", []) if p.get("split") == split]
    if not products:
        raise BenchmarkError(f"no products in split {split!r}")
    families_other = {
        p["family"] for p in manifest["products"] if p.get("split") != split
    }
    leaked = sorted({p["family"] for p in products} & families_other)
    if leaked:
        raise BenchmarkError(f"family appears in both splits: {leaked}")
    return products


def classify_output(path: Path) -> tuple[str, dict[str, Any] | None, str | None]:
    """Return (kind, payload, error) where kind is draft|failure|abstain|invalid|missing."""
    if not path.exists():
        return "missing", None, "no output file"
    try:
        payload = _load_json(path)
    except (OSError, ValueError) as exc:
        return "invalid", None, f"unreadable output: {exc}"
    if isinstance(payload, dict) and payload.get("schema_version") == FAILURE_SCHEMA:
        if isinstance(payload.get("code"), str) and payload["code"]:
            return "failure", payload, None
        return "invalid", None, "typed failure without a code"
    try:
        draft = validate_label_draft_v1(payload)
    except LabelDraftError as exc:
        return "invalid", None, str(exc)
    if draft.get("abstained"):
        return "abstain", draft, None
    return "draft", draft, None


def _draft_rows(draft: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for index, row in enumerate(draft.get("ingredient_rows", [])):
        name = row.get("display_name") or {}
        amount = row.get("amount")
        parent = row.get("parent_index")
        owner = None
        if parent is not None:
            owner_row = draft["ingredient_rows"][parent].get("display_name") or {}
            owner = owner_row.get("value")
        rows.append(
            {
                "index": index,
                "name": name.get("value"),
                "name_status": name.get("status"),
                "row_status": row.get("status"),
                "amount": (amount or {}).get("value") if amount else None,
                "amount_status": (amount or {}).get("status") if amount else None,
                "owner": owner,
                "is_blend_header": bool(row.get("is_blend_header")),
            }
        )
    return rows


def score_product(gold: dict[str, Any], kind: str, draft: dict[str, Any] | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "product_key": gold["product_key"],
        "expected": gold["expected"],
        "output": kind,
        "schema_safe": kind in ("draft", "failure", "abstain"),
        "readable_rows": 0,
        "recalled_rows": 0,
        "tuple_exact": 0,
        "invented": [],
        "wrong_product": False,
        "magnitude_errors": [],
        "expected_abstention_honoured": None,
    }
    if gold["expected"] == "abstain":
        result["expected_abstention_honoured"] = kind in ("abstain", "failure")
        return result
    gold_rows = gold.get("rows", [])
    readable = [r for r in gold_rows if r.get("readable", True)]
    result["readable_rows"] = len(readable)
    if kind != "draft" or draft is None:
        return result

    gold_by_name = {_norm(r["display_name"]): r for r in gold_rows}
    draft_rows = _draft_rows(draft)
    seen: set[str] = set()
    for row in draft_rows:
        key = _norm(row["name"])
        if row["name_status"] != "read" or not key:
            continue
        gold_row = gold_by_name.get(key)
        if gold_row is None:
            result["invented"].append(row["name"])
            continue
        if key in seen:
            continue
        seen.add(key)
        if not gold_row.get("readable", True):
            continue
        result["recalled_rows"] += 1
        g_amount = gold_row.get("amount")
        d_amount = row["amount"]
        owner_match = _norm(gold_row.get("owner")) == _norm(row["owner"])
        if g_amount is None and d_amount is None:
            result["tuple_exact"] += int(owner_match)
            continue
        if g_amount is None or d_amount is None:
            continue
        unit_match = _norm(g_amount.get("unit_text")) == _norm(d_amount.get("unit_text"))
        g_value, d_value = float(g_amount["value"]), float(d_amount["value"])
        if unit_match and g_value > 0 and d_value > 0:
            ratio = d_value / g_value
            if ratio >= 10 or ratio <= 0.1:
                result["magnitude_errors"].append(row["name"])
        if unit_match and owner_match and math.isclose(g_value, d_value, rel_tol=0, abs_tol=1e-9):
            result["tuple_exact"] += 1

    identity = draft.get("identity", {})
    gold_identity = gold.get("identity", {})
    for field in ("brand", "product_name"):
        value = identity.get(field) or {}
        if value.get("status") == "read" and gold_identity.get(field):
            if _norm(value.get("value")) != _norm(gold_identity[field]):
                result["wrong_product"] = True
    return result


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(0, math.ceil(pct / 100 * len(ordered)) - 1)
    return ordered[rank]


def evaluate(holdout_dir: Path, run_dir: Path, split: str) -> dict[str, Any]:
    if split not in SPLITS:
        raise BenchmarkError(f"split must be one of {SPLITS}")
    products = load_manifest(holdout_dir, split)
    per_product: list[dict[str, Any]] = []
    families: dict[str, dict[str, int]] = {}
    latencies: list[float] = []
    cold_latencies: list[float] = []
    cost_microcents = 0
    digest = hashlib.sha256()
    for entry in products:
        gold = load_gold(holdout_dir, entry)
        out_path = run_dir / f"{entry['product_key']}.json"
        kind, draft, error = classify_output(out_path)
        if out_path.exists():
            digest.update(out_path.read_bytes())
        scored = score_product(gold, kind, draft)
        scored["family"] = entry["family"]
        scored["cases"] = entry.get("cases", [])
        scored["error"] = error
        meta_path = run_dir / f"{entry['product_key']}.meta.json"
        if meta_path.exists():
            meta = _load_json(meta_path)
            latency = meta.get("latency_seconds")
            if isinstance(latency, (int, float)):
                (cold_latencies if meta.get("cold_start") else latencies).append(float(latency))
            cost = meta.get("cost_microcents")
            if isinstance(cost, int):
                cost_microcents += cost
        per_product.append(scored)
        fam = families.setdefault(
            entry["family"], {"products": 0, "drafted": 0, "readable_rows": 0, "recalled_rows": 0}
        )
        fam["products"] += 1
        fam["drafted"] += int(kind == "draft")
        fam["readable_rows"] += scored["readable_rows"]
        fam["recalled_rows"] += scored["recalled_rows"]

    expected_draft = [p for p in per_product if p["expected"] == "draft"]
    drafted = [p for p in expected_draft if p["output"] == "draft"]
    expected_abstain = [p for p in per_product if p["expected"] == "abstain"]
    readable_total = sum(p["readable_rows"] for p in drafted)
    recalled_total = sum(p["recalled_rows"] for p in drafted)
    metrics = {
        "schema_safe_rate": _rate(sum(p["schema_safe"] for p in per_product), len(per_product)),
        "coverage": _rate(len(drafted), len(expected_draft)),
        "row_recall": _rate(recalled_total, readable_total),
        "row_recall_including_missing_coverage": _rate(
            recalled_total, sum(p["readable_rows"] for p in expected_draft)
        ),
        "tuple_exact_rate": _rate(sum(p["tuple_exact"] for p in drafted), recalled_total),
        "invented_actives": sum(len(p["invented"]) for p in drafted),
        "wrong_product_substitutions": sum(p["wrong_product"] for p in drafted),
        "magnitude_errors": sum(len(p["magnitude_errors"]) for p in drafted),
        "expected_abstentions_honoured_rate": _rate(
            sum(bool(p["expected_abstention_honoured"]) for p in expected_abstain),
            len(expected_abstain),
        ),
        "missing_coverage": [
            {"product_key": p["product_key"], "output": p["output"], "error": p["error"]}
            for p in expected_draft
            if p["output"] != "draft"
        ],
        "latency_p95_seconds": _percentile(latencies, 95),
        "cold_start_latency_seconds": cold_latencies,
        "cost_microcents_total": cost_microcents,
    }
    gates = _apply_gates(metrics)
    return {
        "schema_version": "submission_benchmark_report_v1",
        "split": split,
        "run_dir": str(run_dir),
        "run_sha256": digest.hexdigest(),
        "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "products": len(per_product),
        "metrics": metrics,
        "families": {
            name: {**counts, "row_recall": _rate(counts["recalled_rows"], counts["readable_rows"])}
            for name, counts in sorted(families.items())
        },
        "gates": gates,
        "verdict": "qualifies" if all(g["passed"] for g in gates.values()) else "does_not_qualify",
        "per_product": per_product,
    }


def _apply_gates(metrics: dict[str, Any]) -> dict[str, dict[str, Any]]:
    gates: dict[str, dict[str, Any]] = {}
    for name, threshold in GATES.items():
        observed = metrics[name]
        if isinstance(observed, dict):  # a rate with denominator
            value = observed["rate"]
            passed = value is not None and value >= threshold
            if observed["N"] == 0:
                passed = name == "expected_abstentions_honoured_rate"
        elif name == "latency_p95_seconds":
            value = observed
            passed = value is None or value <= threshold
        else:
            value = observed
            passed = value <= threshold
        gates[name] = {"threshold": threshold, "observed": value, "passed": bool(passed)}
    return gates


def record_holdout_run(holdout_dir: Path, report: dict[str, Any], configuration: str) -> int:
    """Append to the ledger; return how many earlier runs used this configuration."""
    ledger = holdout_dir / "holdout_runs.jsonl"
    earlier = 0
    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if line.strip() and json.loads(line).get("configuration") == configuration:
                earlier += 1
    entry = {
        "evaluated_at": report["evaluated_at"],
        "configuration": configuration,
        "run_sha256": report["run_sha256"],
        "verdict": report["verdict"],
        "earlier_runs_of_this_configuration": earlier,
    }
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return earlier


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--holdout", type=Path, default=Path("reports/submission_holdout"))
    parser.add_argument("--run", type=Path, required=True, help="run directory (absolute or under --holdout)")
    parser.add_argument("--split", choices=SPLITS, default="development")
    parser.add_argument("--configuration", default=None,
                        help="provider:model_digest:prompt_version:prep_config; required for holdout")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    run_dir = args.run if args.run.is_absolute() else args.holdout / args.run
    if args.split == "holdout" and not args.configuration:
        parser.error("--configuration is required for a holdout evaluation")
    try:
        report = evaluate(args.holdout, run_dir, args.split)
    except BenchmarkError as exc:
        print(f"benchmark refused: {exc}", file=sys.stderr)
        return 2
    if args.split == "holdout":
        earlier = record_holdout_run(args.holdout, report, args.configuration)
        report["holdout_consumed"] = earlier > 0
        if earlier:
            print(
                f"warning: holdout already evaluated {earlier}x for this configuration; "
                "a fresh untouched set is required before tuning",
                file=sys.stderr,
            )
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
