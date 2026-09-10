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
from collections import Counter
import fcntl
import hashlib
import json
import math
import os
import re
import sys
import statistics
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .envelope import LabelDraftError, validate_label_draft_v1
from ..gtin import canonical_gtin14_candidates

MANIFEST_SCHEMA = "submission_holdout_v1"
GOLD_SCHEMA = "gold_label_v1"
FAILURE_SCHEMA = "extraction_failure_v1"
SPLITS = ("development", "holdout")

#: Reported separately because an aggregate hides them. A run can read ninety
#: per cent of a label correctly and still have put every dose in the wrong
#: unit: those are not the same failure and they do not carry the same risk.
DIMENSIONS = (
    "identity", "serving", "row_presence", "dose", "unit",
    "blend_nesting", "printed_detail", "other_ingredients", "statements",
)

# Frozen gates (HOLDOUT.md). Change only through a dated amendment there.
GATES: dict[str, Any] = {
    "schema_safe_rate": 1.0,
    "row_recall": 0.99,
    "tuple_exact_rate": 0.99,
    "field_fidelity": 0.99,
    # A wrong dose, a wrong unit and a row hung under the wrong blend header
    # are the three errors a reviewer is least likely to catch by eye and the
    # three that change what a person swallows. They admit no error budget.
    "dose_accuracy": 1.0,
    "unit_accuracy": 1.0,
    "blend_nesting_accuracy": 1.0,
    "invented_actives": 0,
    "wrong_product_substitutions": 0,
    "magnitude_errors": 0,
    "unit_mismatches": 0,
    "expected_abstentions_honoured_rate": 1.0,
    "latency_p95_seconds": 60.0,
    "critical_post_review_errors": 0,
    "reviewer_median_time_reduction": 0.30,
    "reviewer_p95_time_ratio": 1.0,
}

REQUIRED_CASES = frozenset({
    "glare", "curved_bottle", "tiny_print", "split_facts", "combined_facts_other",
    "wrong_slot", "mismatched_bottle", "ambiguous_serving", "nested_blend", "multiple_forms",
    "unit_mg", "unit_mcg", "unit_g", "unit_IU", "unit_CFU", "unit_AFU", "dv_only",
    "serving_range", "foreign_language", "handwritten", "expired_date", "unreadable",
})
PROTOCOL_PATH = Path(__file__).parents[1] / "HOLDOUT.md"
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")


class BenchmarkError(ValueError):
    """The holdout set or the run violates the frozen protocol."""


def _norm(text: Any) -> str:
    return " ".join(unicodedata.normalize("NFC", str(text if text is not None else "")).casefold().split())


def _unit(text: Any) -> str:
    # Only printed spelling equivalence; this evaluator never converts doses.
    value = _norm(text)
    return "mcg" if value in ("µg", "μg", "mcg") else value


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BenchmarkError(f"cannot read {path.name}: {exc}") from exc


def _sha(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise BenchmarkError(f"missing frozen or run file: {path}") from exc


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def _inside(root: Path, relative: Any) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise BenchmarkError("file path must be relative to its set or run")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise BenchmarkError("file path leaves its set or run")
    return path


def _timestamp(value: Any) -> bool:
    try:
        return isinstance(value, str) and datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


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


def _gold_amount(value: Any) -> None:
    if value is None:
        return
    if (not isinstance(value, dict) or set(value) != {"value", "unit_text"}
            or not _measurement(value["value"])
            or not isinstance(value["unit_text"], str) or not value["unit_text"].strip()):
        raise BenchmarkError("gold amount must be a printed numeric amount/unit or explicit null")


def _gold_text(value: Any) -> None:
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise BenchmarkError("gold text must be nonempty text or explicit null")


def load_gold(holdout_dir: Path, entry: dict[str, Any]) -> dict[str, Any]:
    path = _inside(holdout_dir, entry.get("gold"))
    if _sha(path) != entry.get("gold_sha256"):
        raise BenchmarkError(f"{entry['product_key']}: gold checksum changed")
    gold = _load_json(path)
    if not isinstance(gold, dict):
        raise BenchmarkError("gold must be an object")
    if gold.get("schema_version") != GOLD_SCHEMA:
        raise BenchmarkError(f"{entry['product_key']}: gold schema must be {GOLD_SCHEMA}")
    if gold.get("product_key") != entry["product_key"]:
        raise BenchmarkError(f"{entry['product_key']}: gold product_key mismatch")
    checkers = gold.get("checked_by") or []
    if not isinstance(checkers, list) or any(not isinstance(c, dict) for c in checkers):
        raise BenchmarkError("gold needs two distinct human checkers")
    names = {_norm(c.get("checker")) for c in checkers}
    if len(checkers) < 2 or len(names) < 2 or "" in names:
        raise BenchmarkError(f"{entry['product_key']}: gold needs two distinct human checkers")
    for checker in checkers:
        if (any(key in checker for key in ("model", "provider", "generated_by"))
                or checker.get("human") is not True or checker.get("independent") is not True
                or checker.get("model_output_seen") is not False or not _timestamp(checker.get("checked_at"))):
            raise BenchmarkError(f"{entry['product_key']}: gold must be human-checked")
    if gold.get("expected") not in ("draft", "abstain"):
        raise BenchmarkError(f"{entry['product_key']}: gold expected must be draft|abstain")
    for section, keys in (("identity", {"brand", "product_name", "barcode_digits_seen"}),
                          ("serving", {"size", "amount", "basis_text", "servings_per_container"}),
                          ("other_ingredients", {"text", "disclosure_hint"})):
        if not isinstance(gold.get(section), dict) or not keys <= gold[section].keys():
            raise BenchmarkError(f"gold {section} needs all fields (explicit null for unknown)")
        for key in keys - {"amount"}:
            field = gold[section][key]
            if section == "serving" and _measurement(field):
                continue
            _gold_text(field)
    _gold_amount(gold["serving"]["amount"])
    statements = gold.get("statements")
    if not isinstance(statements, list):
        raise BenchmarkError("gold needs statements (an explicit empty array when none are printed)")
    for statement in statements:
        _gold_text(statement)
    rows = gold.get("rows")
    if not isinstance(rows, list):
        raise BenchmarkError("gold rows must be an array")
    for index, row in enumerate(rows):
        keys = {"display_name", "amount", "parent_index", "is_blend_header", "readable", "form_text", "percent_dv"}
        if not isinstance(row, dict) or not keys <= row.keys():
            raise BenchmarkError("gold rows require printed fields and explicit unknowns")
        if not isinstance(row["readable"], bool) or not isinstance(row["is_blend_header"], bool):
            raise BenchmarkError("gold row readable/is_blend_header must be boolean")
        _gold_text(row["display_name"])
        _gold_text(row["form_text"])
        if row["readable"] and row["display_name"] is None:
            raise BenchmarkError("readable gold row needs its printed name")
        if row["percent_dv"] is not None and not _measurement(row["percent_dv"]):
            raise BenchmarkError("gold percent_dv must be numeric or explicit null")
        parent = row["parent_index"]
        if parent is not None and (type(parent) is not int or parent < 0 or parent >= index or not rows[parent]["is_blend_header"]):
            raise BenchmarkError("gold parent_index must reference an earlier blend header")
        _gold_amount(row["amount"])
    if gold["expected"] == "draft" and not any(row["readable"] for row in rows):
        raise BenchmarkError("readable gold product needs at least one readable row")
    return gold


def _validate_set(holdout_dir: Path, *, synthetic: bool) -> dict[str, Any]:
    manifest = _load_json(holdout_dir / "manifest.json")
    if not isinstance(manifest, dict) or manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise BenchmarkError(f"manifest schema must be {MANIFEST_SCHEMA}")
    if not _timestamp(manifest.get("frozen_at")):
        raise BenchmarkError("manifest is not frozen (frozen_at missing)")
    products = manifest.get("products")
    if not isinstance(products, list) or not products:
        raise BenchmarkError("manifest needs products")
    seen, photos_seen, files, photo_owners = set(), set(), {}, {}
    barcodes_seen, identities_seen = set(), set()
    groups = {split: {"brand": set(), "family": set()} for split in SPLITS}
    cases = Counter()
    abstentions = 0
    for entry in products:
        if not isinstance(entry, dict) or entry.get("split") not in SPLITS:
            raise BenchmarkError("invalid product split")
        key = entry.get("product_key")
        if not isinstance(key, str) or not _TOKEN.fullmatch(key) or key in seen:
            raise BenchmarkError("product keys must be unique path-safe tokens")
        seen.add(key)
        for group in ("brand", "family"):
            if not isinstance(entry.get(group), str) or not _norm(entry[group]):
                raise BenchmarkError(f"product requires {group}")
            groups[entry["split"]][group].add(_norm(entry[group]))
        labels = entry.get("cases")
        if not isinstance(labels, list) or any(not isinstance(c, str) or c not in REQUIRED_CASES for c in labels):
            raise BenchmarkError("unknown or malformed case coverage")
        gold = load_gold(holdout_dir, entry)
        identity = gold["identity"]
        actual_brand = _norm(identity["brand"])
        if actual_brand and actual_brand != _norm(entry["brand"]):
            raise BenchmarkError("manifest brand must equal the independently checked gold brand")
        brand_name = (actual_brand, _norm(identity["product_name"]))
        if all(brand_name):
            if brand_name in identities_seen:
                raise BenchmarkError("duplicate known brand/product-name identity")
            identities_seen.add(brand_name)
        barcode = identity["barcode_digits_seen"]
        if barcode is not None:
            identities = canonical_gtin14_candidates(barcode) | {"raw:" + barcode}
            if identities & barcodes_seen:
                raise BenchmarkError("duplicate known barcode identity")
            barcodes_seen.update(identities)
        files[entry["gold"]] = entry["gold_sha256"]
        if entry["split"] == "holdout":
            cases.update(set(labels))
            abstentions += int(gold["expected"] == "abstain")
        photos = entry.get("photos")
        if not isinstance(photos, list) or not photos:
            raise BenchmarkError("each product needs its source photos")
        for photo in photos:
            if not isinstance(photo, dict):
                raise BenchmarkError("invalid photo entry")
            photo_id = photo.get("photo_id")
            if not isinstance(photo_id, str) or not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", photo_id) or photo_id in photos_seen:
                raise BenchmarkError("photo ids must be unique UUIDs")
            photos_seen.add(photo_id)
            photo_path = _inside(holdout_dir, photo.get("path"))
            if photo["path"] in files or _sha(photo_path) != photo.get("sha256"):
                raise BenchmarkError("source photo checksum changed or path reused")
            if photo_owners.get(photo["sha256"], key) != key:
                raise BenchmarkError("same source photo appears in multiple products")
            photo_owners[photo["sha256"]] = key
            files[photo["path"]] = photo["sha256"]
    for group in ("brand", "family"):
        if groups["development"][group] & groups["holdout"][group]:
            raise BenchmarkError(f"{group} appears in both splits")
    if not synthetic:
        if Counter(p["split"] for p in products) != {"development": 20, "holdout": 40}:
            raise BenchmarkError("qualification needs 20 development and 40 holdout products")
        if any(cases[c] < 2 for c in REQUIRED_CASES) or abstentions < 2:
            raise BenchmarkError("each required case needs two holdout products, including expected abstentions")
    candidates = manifest.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise BenchmarkError("predeclared candidates required")
    candidate_ids, candidate_digests = set(), set()
    for candidate in candidates:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("id"), str) or not _TOKEN.fullmatch(candidate["id"]) or candidate["id"] in candidate_ids:
            raise BenchmarkError("predeclared candidate ids must be unique tokens")
        candidate_ids.add(candidate["id"])
        config = candidate.get("configuration")
        if not isinstance(config, dict) or any(not isinstance(config.get(k), str) or not config[k] for k in ("provider", "model", "prompt_version")) or not isinstance(config.get("preparation"), dict):
            raise BenchmarkError("candidate requires provider/model/prompt_version/preparation")
        if any(not isinstance(config.get(k), str) or not re.fullmatch(r"[0-9a-f]{64}", config[k]) for k in ("model_digest", "prompt_sha256")):
            raise BenchmarkError("candidate requires immutable model and prompt digests")
        digest = hashlib.sha256(_canonical(config)).hexdigest()
        if digest in candidate_digests:
            raise BenchmarkError("duplicate candidate configuration under another id")
        candidate_digests.add(digest)
    return {"schema_version": "submission_freeze_v1", "mode": "synthetic" if synthetic else "qualification",
            "manifest_sha256": _sha(holdout_dir / "manifest.json"), "protocol_sha256": _sha(PROTOCOL_PATH), "files": files}


def freeze_holdout(holdout_dir: Path, *, synthetic: bool = False) -> dict[str, Any]:
    """Validate operator-assembled evidence; never create gold or human attestations."""
    if (holdout_dir / "holdout_runs.jsonl").exists():
        raise BenchmarkError("cannot freeze an exposed evaluation set")
    receipt = _validate_set(holdout_dir, synthetic=synthetic)
    try:
        with (holdout_dir / "freeze.json").open("xb") as handle:
            handle.write(_canonical(receipt) + b"\n")
    except FileExistsError as exc:
        raise BenchmarkError("freeze receipt already exists") from exc
    return receipt


def load_manifest(holdout_dir: Path, split: str) -> list[dict[str, Any]]:
    receipt = _load_json(holdout_dir / "freeze.json")
    if not isinstance(receipt, dict) or receipt.get("mode") not in ("synthetic", "qualification"):
        raise BenchmarkError("invalid freeze receipt")
    if receipt != _validate_set(holdout_dir, synthetic=receipt["mode"] == "synthetic"):
        raise BenchmarkError("frozen manifest, gold, source bytes or protocol changed")
    products = [p for p in _load_json(holdout_dir / "manifest.json")["products"] if p["split"] == split]
    if not products:
        raise BenchmarkError(f"no products in split {split}")
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
                "parent_index": parent,
                "form_text": _value(row.get("form_text")),
                "percent_dv": _value(row.get("percent_dv")),
                "is_blend_header": bool(row.get("is_blend_header")),
            }
        )
    return rows


def _value(field: Any) -> Any:
    return field.get("value") if isinstance(field, dict) and field.get("status") == "read" else None


def _amount_exact(gold: Any, draft: Any) -> bool:
    if gold is None or draft is None:
        return gold is None and draft is None
    if gold.get("value") is None or draft.get("value") is None:
        return False
    return _unit(gold.get("unit_text")) == _unit(draft.get("unit_text")) and gold["value"] == draft["value"]


def _same(gold: Any, draft: Any) -> bool:
    return _norm(gold) == _norm(draft) if isinstance(gold, str) and isinstance(draft, str) else gold == draft


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
        "unit_mismatches": [],
        "expected_abstention_honoured": None,
        "field_checks": 0,
        "field_exact": 0,
        "serving_exact": False,
        "dimensions": {name: {"checks": 0, "exact": 0} for name in DIMENSIONS},
    }

    def tally(dimension: str, correct: Any, count: int = 1) -> None:
        counts = result["dimensions"][dimension]
        counts["checks"] += count
        counts["exact"] += count if correct else 0
    if gold["expected"] == "abstain":
        result["expected_abstention_honoured"] = kind in ("abstain", "failure")
        return result
    gold_rows = gold.get("rows", [])
    readable = [r for r in gold_rows if r.get("readable", True)]
    result["readable_rows"] = len(readable)
    # Known identity/disclosure/serving fields and row form/%DV fields are also
    # reported explicitly; unreadable gold values remain unknown, not invented.
    product_fields = [(section, key, value) for section in ("identity", "serving", "other_ingredients")
                      for key, value in gold.get(section, {}).items() if value is not None]
    result["field_checks"] = len(product_fields) + sum(
        r.get(key) is not None for r in readable for key in ("form_text", "percent_dv"))
    if kind != "draft" or draft is None:
        return result

    draft_rows = _draft_rows(draft)
    used: set[int] = set()
    matched: dict[int, int] = {}
    serving_match = True
    for section, field, expected in product_fields:
        actual = draft.get(section, {}).get(field)
        observed = actual if section == "other_ingredients" and field == "disclosure_hint" else _value(actual)
        exact = _amount_exact(expected, observed) if section == "serving" and field == "amount" else _same(expected, observed)
        result["field_exact"] += int(exact)
        tally(section, exact)
        if section == "serving":
            serving_match &= exact
        asserted = actual.get("value") if isinstance(actual, dict) and actual.get("status") in ("read", "partial") else None
        if section == "identity" and asserted is not None and not _same(expected, asserted):
            result["wrong_product"] = True
    result["serving_exact"] = serving_match

    printed = [_norm(_value(statement)) for statement in draft.get("statements", [])]
    for statement in gold.get("statements", []):
        tally("statements", _norm(statement) in printed)

    def owner_matches(gold_row, row):
        if "parent_index" in gold_row:
            parent = row["parent_index"]
            return (parent is None and gold_row["parent_index"] is None) or (
                parent is not None and parent in matched and matched[parent] == gold_row["parent_index"])
        return _same(gold_row.get("owner"), row["owner"])

    for row in draft_rows:
        key = _norm(row["name"])
        if not key:
            continue
        candidates = [i for i, candidate in enumerate(gold_rows) if i not in used and _norm(candidate["display_name"]) == key]
        if not candidates:
            result["invented"].append(row["name"])
            continue
        # Match each printed occurrence at most once, preferring its ownership
        # and amount. No name dictionary may collapse repeated headers/rows.
        gold_index = max(candidates, key=lambda i: (
            owner_matches(gold_rows[i], row),
            _amount_exact(gold_rows[i].get("amount"), row["amount"]),
            _same(gold_rows[i].get("form_text"), row["form_text"]),
        ))
        gold_row = gold_rows[gold_index]
        used.add(gold_index)
        matched[row["index"]] = gold_index
        g_amount = gold_row.get("amount")
        d_amount = row["amount"]
        owner_match = owner_matches(gold_row, row)
        unit_match = g_amount is not None and d_amount is not None and _unit(g_amount.get("unit_text")) == _unit(d_amount.get("unit_text"))
        if g_amount is not None and d_amount is not None and d_amount.get("unit_text") is not None and not unit_match:
            result["unit_mismatches"].append(row["name"])
        g_value = (g_amount or {}).get("value")
        d_value = (d_amount or {}).get("value")
        if unit_match and _measurement(g_value) and _measurement(d_value) and g_value != d_value:
            ratio = d_value / g_value if g_value else math.inf
            if ratio >= 10 or ratio <= 0.1:
                result["magnitude_errors"].append(row["name"])
        # Uncertainty removes recall credit; it never conceals a contradictory
        # amount the model explicitly asserted against a matched gold row.
        if not gold_row.get("readable", True) or row["name_status"] != "read":
            continue
        result["recalled_rows"] += 1
        if g_amount is not None:
            # A dose is right only when its number and its unit are both
            # right, so `dose` is the strict pair and `unit` isolates which
            # half failed. An unread amount fails both: a missing dose reads
            # as an absent ingredient.
            tally("unit", unit_match)
            tally("dose", _amount_exact(g_amount, d_amount))
        tally("blend_nesting",
              owner_match and gold_row.get("is_blend_header", False) == row["is_blend_header"])
        fidelity = True
        for field in ("form_text", "percent_dv"):
            if gold_row.get(field) is not None:
                exact = _same(gold_row[field], row[field])
                result["field_exact"] += int(exact)
                tally("printed_detail", exact)
                fidelity &= exact
        exact = (_amount_exact(g_amount, d_amount) and owner_match and serving_match and fidelity
                 and gold_row.get("is_blend_header", False) == row["is_blend_header"]
                 and row["row_status"] == "read" and (d_amount is None or row["amount_status"] == "read"))
        result["tuple_exact"] += int(exact)
    tally("row_presence", True, result["recalled_rows"])
    tally("row_presence", False, result["readable_rows"] - result["recalled_rows"])
    return result


def _measurement(value: Any, *, positive: bool = False) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and (value > 0 if positive else value >= 0)


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(0, math.ceil(pct / 100 * len(ordered)) - 1)
    return ordered[rank]


def _validate_run_sources(entry: dict, draft: dict, meta: dict, run_dir: Path, configuration: dict) -> None:
    snapshot = {p["photo_id"]: p["sha256"] for p in entry["photos"]}
    if draft["evidence_snapshot"] != snapshot:
        raise BenchmarkError("draft snapshot does not belong to this product's frozen source photos")
    if draft["draft_origin"] != "model" or any(draft[k] != configuration[k] for k in ("provider", "model", "prompt_version")):
        raise BenchmarkError("draft does not match the predeclared model configuration")
    inputs = meta.get("sent_inputs")
    if not isinstance(inputs, list) or any(not isinstance(i, dict) or not isinstance(i.get("input_id"), str) for i in inputs):
        raise BenchmarkError("run must retain each actually sent input's bytes")
    by_id = {i["input_id"]: i for i in inputs}
    if len(by_id) != len(inputs) or set(by_id) != {i["input_id"] for i in draft["sent_inputs"]}:
        raise BenchmarkError("retained sent inputs must exactly match the draft")
    for sent in draft["sent_inputs"]:
        if _sha(_inside(run_dir, by_id[sent["input_id"]].get("path"))) != sent["sent_sha256"]:
            raise BenchmarkError("actually sent bytes checksum does not match draft")


def _review_measurement(meta: dict, output_sha256: str) -> dict | None:
    review = meta.get("review")
    if (not isinstance(review, dict) or review.get("completed") is not True
            or not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip()
            or not _timestamp(review.get("checked_at"))
            or review.get("reviewed_output_sha256") != output_sha256
            or type(review.get("critical_errors")) is not int or review["critical_errors"] < 0
            or not _measurement(review.get("manual_seconds"), positive=True)
            or not _measurement(review.get("assisted_seconds"), positive=True)):
        return None
    return review


def evaluate(holdout_dir: Path, run_dir: Path, split: str, configuration: str | None = None) -> dict[str, Any]:
    if split not in SPLITS:
        raise BenchmarkError(f"split must be one of {SPLITS}")
    products = load_manifest(holdout_dir, split)
    freeze_sha256 = _sha(holdout_dir / "freeze.json")
    receipt = _load_json(holdout_dir / "freeze.json")
    run_config = _load_json(run_dir / "configuration.json")
    candidates = {c["id"]: c["configuration"] for c in _load_json(holdout_dir / "manifest.json")["candidates"]}
    candidate_id = run_config.get("candidate_id") if isinstance(run_config, dict) else None
    if (not isinstance(candidate_id, str) or candidate_id not in candidates
            or run_config.get("configuration") != candidates[candidate_id]
            or (configuration is not None and configuration != candidate_id)):
        raise BenchmarkError("run must use an unchanged predeclared candidate configuration")
    per_product: list[dict[str, Any]] = []
    families: dict[str, dict[str, int]] = {}
    latencies: list[float] = []
    cold_latencies: list[float] = []
    cost_microcents = 0
    reviews: list[dict] = []
    run_files = {"configuration.json": _sha(run_dir / "configuration.json")}
    for entry in products:
        gold = load_gold(holdout_dir, entry)
        out_path = run_dir / f"{entry['product_key']}.json"
        kind, draft, error = classify_output(out_path)
        output_sha256 = _sha(out_path) if out_path.exists() else None
        run_files[out_path.name] = output_sha256
        meta_path = run_dir / f"{entry['product_key']}.meta.json"
        meta = _load_json(meta_path) if meta_path.exists() else {}
        if not isinstance(meta, dict):
            raise BenchmarkError("run measurements must be an object")
        run_files[meta_path.name] = _sha(meta_path) if meta_path.exists() else None
        retained_inputs = meta.get("sent_inputs", [])
        if isinstance(retained_inputs, list):
            for item in retained_inputs:
                try:
                    input_path = _inside(run_dir, item.get("path") if isinstance(item, dict) else None)
                    run_files[str(input_path.relative_to(run_dir.resolve()))] = _sha(input_path) if input_path.exists() else None
                except BenchmarkError:
                    pass  # _validate_run_sources records the per-product failure.
        if kind in ("draft", "abstain"):
            try:
                _validate_run_sources(entry, draft, meta, run_dir, candidates[candidate_id])
            except BenchmarkError as exc:
                kind, draft, error = "invalid", None, str(exc)
        scored = score_product(gold, kind, draft)
        scored["family"] = entry["family"]
        scored["cases"] = entry.get("cases", [])
        scored["error"] = error
        latency = meta.get("latency_seconds")
        if _measurement(latency):
            latencies.append(float(latency))
            if meta.get("cold_start"):
                cold_latencies.append(float(latency))
        cost = meta.get("cost_microcents")
        if type(cost) is int and cost >= 0:
            cost_microcents += cost
        if gold["expected"] == "draft" and kind == "draft":
            review = _review_measurement(meta, output_sha256)
            if review:
                reviews.append(review)
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
    readable_total = sum(p["readable_rows"] for p in expected_draft)
    recalled_total = sum(p["recalled_rows"] for p in drafted)
    metrics = {
        "schema_safe_rate": _rate(sum(p["schema_safe"] for p in per_product), len(per_product)),
        "coverage": _rate(len(drafted), len(expected_draft)),
        "row_recall": _rate(recalled_total, readable_total),
        "row_recall_including_missing_coverage": _rate(
            recalled_total, sum(p["readable_rows"] for p in expected_draft)
        ),
        "tuple_exact_rate": _rate(sum(p["tuple_exact"] for p in drafted), readable_total),
        "field_fidelity": _rate(sum(p["field_exact"] for p in drafted), sum(p["field_checks"] for p in expected_draft)),
        "invented_actives": sum(len(p["invented"]) for p in drafted),
        "wrong_product_substitutions": sum(p["wrong_product"] for p in drafted),
        "magnitude_errors": sum(len(p["magnitude_errors"]) for p in drafted),
        "unit_mismatches": sum(len(p["unit_mismatches"]) for p in drafted),
        "expected_abstentions_honoured_rate": _rate(
            sum(bool(p["expected_abstention_honoured"]) for p in expected_abstain),
            len(expected_abstain),
        ),
        "missing_coverage": [
            {"product_key": p["product_key"], "output": p["output"], "error": p["error"]}
            for p in expected_draft
            if p["output"] != "draft"
        ],
        "latency_p95_seconds": _percentile(latencies, 95) if len(latencies) == len(products) else None,
        "latency_measurements": len(latencies),
        "cold_start_latency_seconds": cold_latencies,
        "cost_microcents_total": cost_microcents,
        "review_measurements": len(reviews),
        "critical_post_review_errors": None,
        "reviewer_median_time_reduction": None,
        "reviewer_p95_time_ratio": None,
    }
    if reviews and len(reviews) == len(expected_draft):
        manual = [r["manual_seconds"] for r in reviews]
        assisted = [r["assisted_seconds"] for r in reviews]
        metrics["critical_post_review_errors"] = sum(r["critical_errors"] for r in reviews)
        metrics["reviewer_median_time_reduction"] = 1 - statistics.median(assisted) / statistics.median(manual)
        metrics["reviewer_p95_time_ratio"] = _percentile(assisted, 95) / _percentile(manual, 95)
    # Per dimension, two denominators. The observation rate answers "how often
    # was this field right"; the product rate answers "on how many labels was
    # it right everywhere". Only the second has independent samples — fields
    # within one label fail together (one bad photograph, one misread panel),
    # so an interval computed over observations is narrower than the evidence
    # supports. Read the product interval when deciding whether a candidate
    # qualifies; read the observation rate to see how bad a failure is.
    per_field: dict[str, Any] = {}
    for dimension in DIMENSIONS:
        counts = [p["dimensions"][dimension] for p in drafted]
        contributing = [c for c in counts if c["checks"]]
        per_field[dimension] = {
            "observations": _rate(sum(c["exact"] for c in counts), sum(c["checks"] for c in counts)),
            "products_without_error": _rate(
                sum(c["exact"] == c["checks"] for c in contributing), len(contributing)
            ),
        }
    metrics["per_field"] = per_field
    for dimension in ("dose", "unit", "blend_nesting"):
        metrics[f"{dimension}_accuracy"] = per_field[dimension]["observations"]

    gates = _apply_gates(metrics)
    gates["frozen_qualification_set"] = {"threshold": True, "observed": receipt["mode"],
                                         "passed": True if receipt["mode"] == "qualification" and split == "holdout" else None}
    report = {
        "schema_version": "submission_benchmark_report_v1",
        "split": split,
        "run_dir": str(run_dir),
        "run_sha256": hashlib.sha256(_canonical({"freeze_sha256": freeze_sha256, "configuration": run_config,
                                                  "split": split, "files": run_files})).hexdigest(),
        "freeze_sha256": freeze_sha256,
        "configuration": candidate_id,
        "configuration_sha256": hashlib.sha256(_canonical(candidates[candidate_id])).hexdigest(),
        "evaluation_mode": receipt["mode"],
        "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "products": len(per_product),
        "metrics": metrics,
        "families": {
            name: {**counts, "row_recall": _rate(counts["recalled_rows"], counts["readable_rows"])}
            for name, counts in sorted(families.items())
        },
        "gates": gates,
        "verdict": _verdict(gates),
        "per_product": per_product,
    }
    if split == "holdout":
        record_holdout_run(holdout_dir, report, candidate_id)
    return report


def _verdict(gates: dict[str, dict]) -> str:
    if any(g["passed"] is False for g in gates.values()):
        return "does_not_qualify"
    return "qualifies" if all(g["passed"] is True for g in gates.values()) else "not_evaluated"


def _apply_gates(metrics: dict[str, Any]) -> dict[str, dict[str, Any]]:
    gates: dict[str, dict[str, Any]] = {}
    for name, threshold in GATES.items():
        observed = metrics[name]
        if isinstance(observed, dict):  # a rate with denominator
            value = observed["rate"]
            passed = observed["n"] / observed["N"] >= threshold if observed["N"] else None
            if observed["N"] == 0:
                passed = name == "expected_abstentions_honoured_rate"
        elif observed is None:
            value = observed
            passed = None
        elif name == "reviewer_median_time_reduction":
            value = observed
            passed = value >= threshold
        else:
            value = observed
            passed = value <= threshold
        gates[name] = {"threshold": threshold, "observed": value, "passed": passed,
                       "status": "not_evaluated" if passed is None else "passed" if passed else "failed"}
    return gates


def record_holdout_run(holdout_dir: Path, report: dict[str, Any], configuration: str) -> int:
    """Consume each predeclared candidate once, under a process-safe ledger lock."""
    ledger = holdout_dir / "holdout_runs.jsonl"
    with ledger.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.seek(0)
        try:
            previous = [json.loads(line) for line in handle if line.strip()]
        except ValueError as exc:
            raise BenchmarkError("holdout ledger is malformed") from exc
        if any(r.get("freeze_sha256") != report["freeze_sha256"] for r in previous):
            raise BenchmarkError("freeze receipt changed after holdout exposure")
        earlier = sum(r.get("configuration_sha256") == report["configuration_sha256"] for r in previous)
        report["holdout_consumed"] = earlier > 0
        if earlier:
            report["gates"]["unused_predeclared_candidate"] = {"threshold": 0, "observed": earlier, "passed": False}
            report["verdict"] = "does_not_qualify"
        entry = {k: report[k] for k in ("evaluated_at", "configuration", "configuration_sha256", "freeze_sha256", "run_sha256", "verdict")}
        entry["earlier_runs_of_this_configuration"] = earlier
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return earlier


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--holdout", type=Path, default=Path("reports/submission_holdout"))
    parser.add_argument("--run", type=Path, help="run directory (absolute or under --holdout)")
    parser.add_argument("--freeze", action="store_true", help="verify operator-assembled set and create an exclusive receipt")
    parser.add_argument("--synthetic", action="store_true", help="freeze a miniature test set that can never qualify")
    parser.add_argument("--split", choices=SPLITS, default="development")
    parser.add_argument("--configuration", default=None,
                        help="predeclared candidate id, matching run/configuration.json")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.freeze:
        try:
            freeze_holdout(args.holdout, synthetic=args.synthetic)
        except BenchmarkError as exc:
            print(f"benchmark refused: {exc}", file=sys.stderr)
            return 2
        return 0
    if args.run is None:
        parser.error("--run is required for evaluation")
    run_dir = args.run if args.run.is_absolute() else args.holdout / args.run
    if args.split == "holdout" and not args.configuration:
        parser.error("--configuration is required for a holdout evaluation")
    try:
        report = evaluate(args.holdout, run_dir, args.split, args.configuration)
    except BenchmarkError as exc:
        print(f"benchmark refused: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
