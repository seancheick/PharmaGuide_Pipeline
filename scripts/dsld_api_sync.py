#!/usr/bin/env python3
"""CLI tool for syncing DSLD label data via the NIH API."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from dsld_api_client import (
    DSLDApiClient,
    SUPPLEMENT_FORM_CODE_TO_BUCKET,
    load_dsld_config,
    normalize_api_label,
)  # noqa: F401

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

__version__ = "0.1.0"

# Keys excluded from parity comparison (provenance differs by design).
_PARITY_IGNORE_KEYS = frozenset({"_source", "src"})
_STATE_VERSION = "1.0"
_CANONICAL_HASH_EXCLUDE_KEYS = frozenset({"_source", "src"})
_FORM_DESCRIPTION_HINTS = (
    ("gummy", "gummies"),
    ("jelly", "gummies"),
    ("softgel", "softgels"),
    ("capsule", "capsules"),
    ("bar", "bars"),
    ("powder", "powders"),
    ("lozenge", "lozenges"),
    ("tablet", "tablets-pills"),
    ("pill", "tablets-pills"),
    ("liquid", "liquids"),
)
_SAFE_PRODUCT_TYPE_TO_FORM: dict[str, str] = {}


# ---------------------------------------------------------------------------
# parity_check
# ---------------------------------------------------------------------------


def parity_check(api_label: dict, reference_label: dict) -> dict:
    """Compare *api_label* against *reference_label* and return a report.

    Keys listed in :data:`_PARITY_IGNORE_KEYS` (``_source``, ``src``) are
    excluded from the comparison because they differ by design between
    API-fetched and manually-downloaded labels.

    Returns a dict with:
      - ``keys_only_in_api``
      - ``keys_only_in_reference``
      - ``type_mismatches``
      - ``value_mismatches``
      - ``nested_diffs``
      - ``identical_keys``
      - ``parity_score`` (0.0 -- 1.0)
    """
    api_keys = set(api_label.keys()) - _PARITY_IGNORE_KEYS
    ref_keys = set(reference_label.keys()) - _PARITY_IGNORE_KEYS

    keys_only_in_api = sorted(api_keys - ref_keys)
    keys_only_in_reference = sorted(ref_keys - api_keys)
    common_keys = sorted(api_keys & ref_keys)

    type_mismatches: dict[str, dict[str, str]] = {}
    value_mismatches: dict[str, dict[str, Any]] = {}
    nested_diffs: dict[str, dict[str, Any]] = {}
    identical_keys: list[str] = []

    for key in common_keys:
        api_val = api_label[key]
        ref_val = reference_label[key]

        api_type = type(api_val).__name__
        ref_type = type(ref_val).__name__

        if api_type != ref_type:
            type_mismatches[key] = {"api": api_type, "reference": ref_type}
            continue

        # Nested structures: compare types and key sets of first element
        if isinstance(api_val, list) and isinstance(ref_val, list):
            if api_val == ref_val:
                identical_keys.append(key)
            elif api_val and ref_val and isinstance(api_val[0], dict) and isinstance(ref_val[0], dict):
                api_first_keys = sorted(api_val[0].keys())
                ref_first_keys = sorted(ref_val[0].keys())
                if api_first_keys != ref_first_keys or len(api_val) != len(ref_val):
                    nested_diffs[key] = {
                        "api_first_keys": api_first_keys,
                        "reference_first_keys": ref_first_keys,
                        "api_length": len(api_val),
                        "reference_length": len(ref_val),
                    }
                else:
                    # Same structure but possibly different values
                    if api_val == ref_val:
                        identical_keys.append(key)
                    else:
                        nested_diffs[key] = {
                            "api_first_keys": api_first_keys,
                            "reference_first_keys": ref_first_keys,
                            "api_length": len(api_val),
                            "reference_length": len(ref_val),
                            "note": "same structure, different values",
                        }
            else:
                value_mismatches[key] = {"api": api_val, "reference": ref_val}
            continue

        if isinstance(api_val, dict) and isinstance(ref_val, dict):
            if api_val == ref_val:
                identical_keys.append(key)
            else:
                api_d_keys = sorted(api_val.keys())
                ref_d_keys = sorted(ref_val.keys())
                nested_diffs[key] = {
                    "api_keys": api_d_keys,
                    "reference_keys": ref_d_keys,
                }
            continue

        # Scalar comparison
        if api_val == ref_val:
            identical_keys.append(key)
        else:
            value_mismatches[key] = {"api": api_val, "reference": ref_val}

    # Parity score: fraction of common keys that are identical
    total_keys = len(common_keys) + len(keys_only_in_api) + len(keys_only_in_reference)
    if total_keys == 0:
        score = 1.0
    else:
        score = len(identical_keys) / total_keys

    return {
        "keys_only_in_api": keys_only_in_api,
        "keys_only_in_reference": keys_only_in_reference,
        "type_mismatches": type_mismatches,
        "value_mismatches": value_mismatches,
        "nested_diffs": nested_diffs,
        "identical_keys": identical_keys,
        "parity_score": round(score, 4),
    }


# ---------------------------------------------------------------------------
# write_raw_label
# ---------------------------------------------------------------------------


def _extract_ids_from_response(response: Any) -> list[int]:
    """Extract DSLD label IDs from an API search/browse response.

    Handles multiple response shapes:
    - ``{"hits": [{"_source": {"id": N}}, ...]}``  (search-filter, brand-products)
    - ``{"data": [{"id": N}, ...]}``                (legacy/alternative)
    - ``[{"id": N}, ...]``                          (plain list)
    """
    if isinstance(response, list):
        return [item["id"] for item in response if "id" in item]

    if not isinstance(response, dict):
        return []

    # search-filter and brand-products return {hits: [{_source: {id: ...}}]}
    hits = response.get("hits", [])
    if hits and isinstance(hits, list):
        ids = []
        for hit in hits:
            if isinstance(hit, dict):
                source = hit.get("_source", hit)
                if "id" in source:
                    ids.append(source["id"])
                elif "_id" in hit:
                    try:
                        ids.append(int(hit["_id"]))
                    except (TypeError, ValueError):
                        continue
        if ids:
            return ids

    # Fallback: {data: [{id: ...}]} or {list: [{id: ...}]}
    items = response.get("data", response.get("list", []))
    if isinstance(items, list):
        return [item["id"] for item in items if isinstance(item, dict) and "id" in item]

    return []


def canonical_payload_sha256(label: dict) -> str:
    """Hash the canonical raw label payload, excluding adapter metadata."""
    payload = {key: value for key, value in label.items() if key not in _CANONICAL_HASH_EXCLUDE_KEYS}
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def route_label_to_form(label: dict, filter_form_code: str | None = None) -> str:
    """Route a normalized DSLD label into a canonical form bucket."""
    physical_state = label.get("physicalState") or {}
    code = str(physical_state.get("langualCode", "")).strip().lower()
    if code in SUPPLEMENT_FORM_CODE_TO_BUCKET:
        return SUPPLEMENT_FORM_CODE_TO_BUCKET[code]

    description = str(physical_state.get("langualCodeDescription", "")).strip().lower()
    for term, bucket in _FORM_DESCRIPTION_HINTS:
        if term in description:
            return bucket

    product_type = label.get("productType") or {}
    product_code = str(product_type.get("langualCode", "")).strip().lower()
    if product_code in _SAFE_PRODUCT_TYPE_TO_FORM:
        return _SAFE_PRODUCT_TYPE_TO_FORM[product_code]
    product_desc = str(product_type.get("langualCodeDescription", "")).strip().lower()
    if product_desc in _SAFE_PRODUCT_TYPE_TO_FORM:
        return _SAFE_PRODUCT_TYPE_TO_FORM[product_desc]

    filter_code = str(filter_form_code or "").strip().lower()
    if filter_code in SUPPLEMENT_FORM_CODE_TO_BUCKET:
        return SUPPLEMENT_FORM_CODE_TO_BUCKET[filter_code]

    return "other"


def classify_label_change(
    label: dict,
    *,
    existing_state: dict | None,
    canonical_form: str,
) -> dict[str, Any]:
    """Classify a fetched label as new, changed, or unchanged."""
    payload_sha256 = canonical_payload_sha256(label)
    if not existing_state:
        return {"status": "new", "payload_sha256": payload_sha256, "changed_fields": ["new_label"]}

    changed_fields: list[str] = []
    if existing_state.get("product_version_code") != label.get("productVersionCode"):
        changed_fields.append("productVersionCode")
    if bool(existing_state.get("off_market")) != bool(label.get("offMarket")):
        changed_fields.append("offMarket")
    if existing_state.get("canonical_form") != canonical_form:
        changed_fields.append("canonical_form")
    if existing_state.get("payload_sha256") != payload_sha256:
        changed_fields.append("payload_sha256")

    if changed_fields:
        return {"status": "changed", "payload_sha256": payload_sha256, "changed_fields": changed_fields}
    return {"status": "unchanged", "payload_sha256": payload_sha256, "changed_fields": []}


def load_sync_state(path: str | Path | None) -> dict[str, dict]:
    """Load a shared DSLD sync state file."""
    if not path:
        return {}
    state_path = Path(path)
    if not state_path.exists():
        return {}
    data = json.loads(state_path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("labels"), dict):
        return data["labels"]
    return data if isinstance(data, dict) else {}


def save_sync_state(path: str | Path | None, labels: dict[str, dict]) -> None:
    """Persist the shared DSLD sync state file."""
    if not path:
        return
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "_metadata": {
                    "version": _STATE_VERSION,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "total_labels": len(labels),
                },
                "labels": dict(sorted(labels.items(), key=lambda item: item[0])),
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _build_state_record(
    label: dict,
    *,
    canonical_form: str,
    payload_sha256: str,
    current_raw_path: str | None,
    last_sync_source: str,
    last_status_filter: int | None = None,
    last_query_context: dict[str, Any] | None = None,
    existing_state: dict | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    first_seen_at = (existing_state or {}).get("first_seen_at", now)
    return {
        "id": label.get("id"),
        "brand_name": label.get("brandName"),
        "product_version_code": label.get("productVersionCode"),
        "off_market": bool(label.get("offMarket")),
        "entry_date": label.get("entryDate"),
        "canonical_form": canonical_form,
        "payload_sha256": payload_sha256,
        "current_raw_path": current_raw_path or (existing_state or {}).get("current_raw_path"),
        "first_seen_at": first_seen_at,
        "last_seen_at": now,
        "last_sync_source": last_sync_source,
        "last_status_filter": last_status_filter,
        "last_query_context": last_query_context or {},
    }


def _write_canonical_label(label: dict, canonical_root: str | Path, canonical_form: str) -> Path:
    bucket_dir = Path(canonical_root) / canonical_form
    return write_raw_label(label, bucket_dir, snapshot=False)


def _make_run_stamp() -> str:
    """Return a filesystem-safe run timestamp."""
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _resolve_delta_output_dir(base_dir: str | Path | None, *, dated_delta: bool, run_stamp: str | None = None) -> str | None:
    """Resolve the effective delta output directory for a sync run."""
    if not base_dir:
        return None
    if not dated_delta:
        return str(base_dir)
    stamp = run_stamp or _make_run_stamp()
    return str(Path(base_dir) / stamp)


def _resolve_report_path(report_dir: str | Path | None, *, run_stamp: str) -> Path | None:
    """Resolve the report file path for a sync run."""
    if not report_dir:
        return None
    return Path(report_dir) / f"{run_stamp}.json"


def _write_sync_report(
    report_path: str | Path | None,
    *,
    command: str,
    filters: dict[str, Any],
    counts: dict[str, Any],
    candidate_ids: list[int],
    canonical_root: str | None,
    state_file: str | None,
    delta_output_dir: str | None,
) -> Path | None:
    """Write a JSON sync report for operator review and auditing."""
    if not report_path:
        return None
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "filters": filters,
        "canonical_root": canonical_root,
        "state_file": state_file,
        "delta_output_dir": delta_output_dir,
        "summary": {
            "candidate_count": len(candidate_ids),
            "written": counts["written"],
            "canonical_written": counts["canonical_written"],
            "delta_written": counts["delta_written"],
            "staging_written": counts["staging_written"],
            "skipped": counts["skipped"],
            "failed": len(counts["failed_ids"]),
            "new_count": len(counts["new_ids"]),
            "changed_count": len(counts["changed_ids"]),
            "unchanged_count": len(counts["unchanged_ids"]),
            "off_market_count": len(counts["off_market_ids"]),
        },
        "candidate_ids": candidate_ids,
        "new_ids": counts["new_ids"],
        "changed_ids": counts["changed_ids"],
        "unchanged_ids": counts["unchanged_ids"],
        "skipped_ids": counts["skipped_ids"],
        "failed_ids": counts["failed_ids"],
        "off_market_ids": counts["off_market_ids"],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def _empty_sync_counts() -> dict[str, Any]:
    """Create a fresh sync counters payload."""
    return {
        "written": 0,
        "canonical_written": 0,
        "delta_written": 0,
        "staging_written": 0,
        "skipped": 0,
        "new_ids": [],
        "changed_ids": [],
        "unchanged_ids": [],
        "skipped_ids": [],
        "failed_ids": [],
        "off_market_ids": [],
    }


def _discover_ids_paginated(
    fetch_page: Any,
    *,
    limit: int | None = None,
    page_size: int = 1000,
) -> list[int]:
    """Discover IDs across paginated API responses.

    ``limit=None`` means "fetch until the API stops returning IDs".
    Some DSLD endpoints may return fewer results than requested on a page while
    still having more results available, so pagination advances by the number of
    IDs actually returned and stops only on an empty page or when no new IDs are
    observed.
    """
    discovered: list[int] = []
    seen: set[int] = set()
    offset = 0
    remaining = None if limit is None else max(limit, 0)

    while remaining is None or remaining > 0:
        request_size = page_size if remaining is None else min(page_size, remaining)
        response = fetch_page(size=request_size, from_=offset)
        ids = _extract_ids_from_response(response)
        if not ids:
            break

        new_ids = [dsld_id for dsld_id in ids if dsld_id not in seen]
        if not new_ids:
            break
        if remaining is not None:
            new_ids = new_ids[:remaining]
            if not new_ids:
                break

        discovered.extend(new_ids)
        seen.update(new_ids)
        offset += len(ids)
        if remaining is not None:
            remaining -= len(new_ids)

    return discovered


def _discover_filter_ids(client: DSLDApiClient, *, limit: int | None = None, **filters: Any) -> list[int]:
    return _discover_ids_paginated(
        lambda *, size, from_: client.search_filter(size=size, from_=from_, **filters),
        limit=limit,
    )


def _discover_brand_ids(client: DSLDApiClient, brand: str, *, limit: int | None = None) -> list[int]:
    return _discover_ids_paginated(
        lambda *, size, from_: client.search_brand(brand, size=size, from_=from_),
        limit=limit,
    )


def _normalize_local_label(raw_label: dict, *, source_path: Path, input_root: Path) -> dict:
    """Normalize a local manual/raw JSON label into canonical raw-label shape."""
    if not isinstance(raw_label, dict):
        raise ValueError("Local label file must contain a JSON object")
    original = raw_label.get("data", raw_label)
    if not isinstance(original, dict):
        raise ValueError("Local label file envelope must contain an object in 'data'")

    normalized = normalize_api_label(raw_label)
    relative_path = source_path.relative_to(input_root).as_posix()
    normalized["_source"] = original.get("_source") or "local"
    normalized["src"] = original.get("src") or f"local/{relative_path}"
    return normalized


def _iter_local_json_files(input_dir: str | Path) -> list[Path]:
    """Return sorted JSON files recursively under the given input directory."""
    root = Path(input_dir)
    return sorted(path for path in root.rglob("*.json") if path.is_file())


def _apply_synced_label(
    label: dict,
    *,
    state: dict[str, dict],
    counts: dict[str, Any],
    canonical_root: str | None = None,
    staging_dir: str | None = None,
    snapshot: bool = False,
    filter_form_code: str | None = None,
    sync_source: str,
    status_filter: int | None = None,
    query_context: dict[str, Any] | None = None,
    delta_output_dir: str | None = None,
    delta_only: bool = False,
    force_refetch: bool = False,
) -> None:
    """Apply sync classification/writes/state updates for one normalized label."""
    dsld_id = label.get("id")
    canonical_form = route_label_to_form(label, filter_form_code=filter_form_code)
    existing_state = state.get(str(dsld_id))
    classification = classify_label_change(
        label,
        existing_state=existing_state,
        canonical_form=canonical_form,
    )
    if classification["status"] == "new":
        counts["new_ids"].append(dsld_id)
    elif classification["status"] == "changed":
        counts["changed_ids"].append(dsld_id)
    else:
        counts["unchanged_ids"].append(dsld_id)
    if bool(label.get("offMarket")):
        counts["off_market_ids"].append(dsld_id)
    is_changed = force_refetch or classification["status"] in {"new", "changed"}

    canonical_path: Path | None = None
    if staging_dir:
        path = write_raw_label(label, staging_dir, snapshot=snapshot)
        logger.info("wrote staging label %s", path)
        counts["staging_written"] += 1
        counts["written"] += 1

    if canonical_root and (is_changed or not existing_state):
        canonical_path = _write_canonical_label(label, canonical_root, canonical_form)
        logger.info("wrote canonical label %s", canonical_path)
        counts["canonical_written"] += 1
        counts["written"] += 1
    elif canonical_root and not is_changed:
        counts["skipped"] += 1
        counts["skipped_ids"].append(dsld_id)

    if delta_output_dir and is_changed:
        delta_path = write_raw_label(label, delta_output_dir, snapshot=False)
        logger.info("wrote delta label %s", delta_path)
        counts["delta_written"] += 1
        counts["written"] += 1

    if not delta_only or canonical_root or is_changed:
        state[str(dsld_id)] = _build_state_record(
            label,
            canonical_form=canonical_form,
            payload_sha256=classification["payload_sha256"],
            current_raw_path=str(canonical_path) if canonical_path else None,
            last_sync_source=sync_source,
            last_status_filter=status_filter,
            last_query_context=query_context,
            existing_state=existing_state,
        )


def _sync_labels(
    ids: list[int],
    *,
    client: DSLDApiClient,
    canonical_root: str | None = None,
    staging_dir: str | None = None,
    snapshot: bool = False,
    state_file: str | None = None,
    filter_form_code: str | None = None,
    sync_source: str,
    status_filter: int | None = None,
    query_context: dict[str, Any] | None = None,
    delta_output_dir: str | None = None,
    delta_only: bool = False,
    force_refetch: bool = False,
) -> dict[str, int]:
    state = load_sync_state(state_file)
    counts = _empty_sync_counts()

    for dsld_id in ids:
        try:
            label = client.fetch_label(dsld_id)
            _apply_synced_label(
                label,
                state=state,
                counts=counts,
                canonical_root=canonical_root,
                staging_dir=staging_dir,
                snapshot=snapshot,
                filter_form_code=filter_form_code,
                sync_source=sync_source,
                status_filter=status_filter,
                query_context=query_context,
                delta_output_dir=delta_output_dir,
                delta_only=delta_only,
                force_refetch=force_refetch,
            )
        except Exception as exc:
            logger.warning("Failed to fetch label %s: %s", dsld_id, exc)
            print(f"  SKIP {dsld_id}: {exc}", file=sys.stderr)
            counts["failed_ids"].append(dsld_id)

    save_sync_state(state_file, state)
    return counts


def write_raw_label(label: dict, output_dir: str | Path, *, snapshot: bool = False) -> Path:
    """Write a normalized label to ``{output_dir}/{dsld_id}.json``.

    Uses compact JSON (no indent, ``ensure_ascii=False``) to match manual
    download files.  When *snapshot* is True, files are written under a
    timestamped ``_snapshots/`` subdirectory.

    Returns the path to the written file.
    """
    dsld_id = label.get("id")
    if dsld_id is None:
        raise ValueError("Label is missing 'id' — cannot write")

    out = Path(output_dir)
    if snapshot:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out = out / "_snapshots" / ts

    out.mkdir(parents=True, exist_ok=True)
    file_path = out / f"{dsld_id}.json"
    file_path.write_text(
        json.dumps(label, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return file_path


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def _print_label_summary(label: dict) -> None:
    """Print a one-line summary of a label."""
    print(f"  ID: {label.get('id')}  |  {label.get('fullName', '?')}  |  brand={label.get('brandName', '?')}")


def _print_parity_report(report: dict) -> None:
    """Pretty-print a parity report."""
    print(f"\n  Parity score: {report['parity_score']:.2%}")
    if report["keys_only_in_api"]:
        print(f"  Keys only in API:       {report['keys_only_in_api']}")
    if report["keys_only_in_reference"]:
        print(f"  Keys only in reference: {report['keys_only_in_reference']}")
    if report["type_mismatches"]:
        print(f"  Type mismatches:        {len(report['type_mismatches'])}")
        for k, v in report["type_mismatches"].items():
            print(f"    {k}: api={v['api']}  ref={v['reference']}")
    if report["value_mismatches"]:
        print(f"  Value mismatches:       {len(report['value_mismatches'])}")
        for k, v in report["value_mismatches"].items():
            api_repr = repr(v["api"])[:80]
            ref_repr = repr(v["reference"])[:80]
            print(f"    {k}: api={api_repr}  ref={ref_repr}")
    if report["nested_diffs"]:
        print(f"  Nested diffs:           {len(report['nested_diffs'])}")
        for k, v in report["nested_diffs"].items():
            print(f"    {k}: {v}")
    print(f"  Identical keys:         {len(report['identical_keys'])}")


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def _cmd_probe(args: argparse.Namespace) -> int:
    """Handle the ``probe`` subcommand."""
    client = DSLDApiClient()
    print(f"Fetching label {args.id} ...")
    label = client.fetch_label(args.id)
    _print_label_summary(label)

    if args.reference:
        ref_path = Path(args.reference)
        if not ref_path.exists():
            print(f"ERROR: reference file not found: {ref_path}", file=sys.stderr)
            return 1
        ref_label = json.loads(ref_path.read_text(encoding="utf-8"))
        report = parity_check(label, ref_label)
        _print_parity_report(report)
        if report["parity_score"] < 1.0:
            print("\nParity check FAILED.")
            return 1
        print("\nParity check PASSED.")
    return 0


def _cmd_sync_brand(args: argparse.Namespace) -> int:
    """Handle the ``sync-brand`` subcommand."""
    if not args.output_dir and not args.canonical_root:
        print("ERROR: sync-brand requires --output-dir and/or --canonical-root", file=sys.stderr)
        return 1
    client = DSLDApiClient()
    limit_text = args.limit if args.limit is not None else "all"
    print(f"Searching brand: {args.brand} (limit={limit_text}) ...")
    if args.status != 2:
        ids = _discover_filter_ids(
            client,
            brand=args.brand,
            status=args.status,
            limit=args.limit,
        )
    else:
        ids = _discover_brand_ids(client, args.brand, limit=args.limit)
    if not ids:
        print("No labels found for that brand.")
        return 0
    print(f"Found {len(ids)} label(s). Fetching ...")
    counts = _sync_labels(
        ids,
        client=client,
        canonical_root=args.canonical_root,
        staging_dir=args.output_dir,
        snapshot=args.snapshot,
        state_file=args.state_file,
        sync_source="sync-brand",
        status_filter=args.status,
        query_context={"brand": args.brand},
    )
    destination = args.canonical_root or args.output_dir
    print(f"\nDone. Wrote {counts['written']} artifacts for {len(ids)} labels to {destination}")
    return 0


def _cmd_refresh_ids(args: argparse.Namespace) -> int:
    """Handle the ``refresh-ids`` subcommand."""
    client = DSLDApiClient()
    written = 0
    for dsld_id in args.ids:
        try:
            label = client.fetch_label(dsld_id)
            path = write_raw_label(label, args.output_dir, snapshot=args.snapshot)
            print(f"  wrote {path}")
            written += 1
        except Exception as exc:
            logger.warning("Failed to fetch label %s: %s", dsld_id, exc)
            print(f"  SKIP {dsld_id}: {exc}", file=sys.stderr)

    print(f"\nDone. Wrote {written}/{len(args.ids)} labels to {args.output_dir}")
    return 0


def _cmd_verify_db(args: argparse.Namespace) -> int:
    """Handle the ``verify-db`` subcommand.

    Samples *N* files from *input_dir*, fetches the same IDs from the API,
    runs :func:`parity_check` on each, and prints an aggregate report.
    **Never writes to input_dir.**
    """
    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        print(f"ERROR: {input_dir} is not a directory", file=sys.stderr)
        return 1

    json_files = sorted(input_dir.glob("*.json"))
    if not json_files:
        print("No JSON files found in input directory.")
        return 0

    sample_size = min(args.sample_size, len(json_files))
    sampled = random.sample(json_files, sample_size)

    client = DSLDApiClient()
    scores: list[float] = []
    failures: list[str] = []

    print(f"Verifying {sample_size} labels from {input_dir} ...")
    for file_path in sampled:
        try:
            ref_label = json.loads(file_path.read_text(encoding="utf-8"))
            dsld_id = ref_label.get("id")
            if dsld_id is None:
                # Try filename
                dsld_id = file_path.stem
            api_label = client.fetch_label(dsld_id)
            report = parity_check(api_label, ref_label)
            scores.append(report["parity_score"])
            status = "PASS" if report["parity_score"] >= 1.0 else "DRIFT"
            print(f"  {file_path.name}: {status} (score={report['parity_score']:.2%})")
            if report["value_mismatches"]:
                for k in sorted(report["value_mismatches"].keys()):
                    print(f"    mismatch: {k}")
        except Exception as exc:
            failures.append(f"{file_path.name}: {exc}")
            print(f"  {file_path.name}: ERROR — {exc}", file=sys.stderr)

    print(f"\n--- Aggregate ---")
    if scores:
        avg = sum(scores) / len(scores)
        perfect = sum(1 for s in scores if s >= 1.0)
        print(f"  Checked:  {len(scores)}")
        print(f"  Perfect:  {perfect}/{len(scores)}")
        print(f"  Avg score: {avg:.2%}")
    if failures:
        print(f"  Errors:   {len(failures)}")
        for f in failures:
            print(f"    {f}")
    return 0


def _cmd_sync_query(args: argparse.Namespace) -> int:
    """Handle the ``sync-query`` subcommand."""
    client = DSLDApiClient()
    print(f"Searching: {args.query} (limit={args.limit}) ...")
    results = client.search_query(args.query, size=args.limit)

    ids = _extract_ids_from_response(results)
    if not ids:
        print("No labels found for that query.")
        return 0
    print(f"Found {len(ids)} label(s). Fetching ...")
    written = 0
    for dsld_id in ids:
        try:
            label = client.fetch_label(dsld_id)
            path = write_raw_label(label, args.output_dir, snapshot=args.snapshot)
            print(f"  wrote {path}")
            written += 1
        except Exception as exc:
            logger.warning("Failed to fetch label %s: %s", dsld_id, exc)
            print(f"  SKIP {dsld_id}: {exc}", file=sys.stderr)

    print(f"\nDone. Wrote {written}/{len(ids)} labels to {args.output_dir}")
    return 0


def _cmd_sync_filter(args: argparse.Namespace) -> int:
    """Handle the ``sync-filter`` subcommand."""
    if not args.canonical_root and not args.staging_dir:
        print("ERROR: sync-filter requires --canonical-root and/or --staging-dir", file=sys.stderr)
        return 1

    client = DSLDApiClient()
    filters = {
        "supplement_form": args.supplement_form,
        "ingredient_name": args.ingredient_name,
        "ingredient_category": args.ingredient_category,
        "brand": args.brand,
        "status": args.status,
        "date_start": args.date_start,
        "date_end": args.date_end,
    }
    limit_text = args.limit if args.limit is not None else "all"
    print(f"Searching filtered labels (limit={limit_text}) ...")
    ids = _discover_filter_ids(client, limit=args.limit, **filters)
    if not ids:
        print("No labels found for those filters.")
        return 0
    print(f"Found {len(ids)} label(s). Fetching ...")
    counts = _sync_labels(
        ids,
        client=client,
        canonical_root=args.canonical_root,
        staging_dir=args.staging_dir,
        snapshot=args.snapshot,
        state_file=args.state_file,
        filter_form_code=args.supplement_form,
        sync_source="sync-filter",
        status_filter=args.status,
        query_context=filters,
    )
    print(
        f"\nDone. Wrote {counts['written']} artifacts "
        f"(canonical={counts['canonical_written']}, staging={counts['staging_written']})."
    )
    return 0


def _cmd_sync_delta(args: argparse.Namespace) -> int:
    """Handle the ``sync-delta`` subcommand."""
    if not args.canonical_root:
        print("ERROR: sync-delta requires --canonical-root", file=sys.stderr)
        return 1
    if not args.state_file:
        print("ERROR: sync-delta requires --state-file", file=sys.stderr)
        return 1

    client = DSLDApiClient()
    filters = {
        "supplement_form": args.supplement_form,
        "ingredient_name": args.ingredient_name,
        "ingredient_category": args.ingredient_category,
        "brand": args.brand,
        "status": args.status,
        "date_start": args.date_start,
        "date_end": args.date_end,
    }
    print("Discovering delta candidates ...")
    ids = _discover_filter_ids(client, limit=args.limit, **filters)
    if not ids:
        print("No labels found for those filters.")
        return 0
    run_stamp = _make_run_stamp()
    delta_output_dir = _resolve_delta_output_dir(args.delta_output_dir, dated_delta=args.dated_delta, run_stamp=run_stamp)
    print(f"Found {len(ids)} candidate label(s). Fetching changed/new labels ...")
    counts = _sync_labels(
        ids,
        client=client,
        canonical_root=args.canonical_root,
        staging_dir=None,
        snapshot=False,
        state_file=args.state_file,
        filter_form_code=args.supplement_form,
        sync_source="sync-delta",
        status_filter=args.status,
        query_context=filters,
        delta_output_dir=delta_output_dir,
        delta_only=True,
        force_refetch=args.force_refetch,
    )
    print(
        f"\nDone. canonical={counts['canonical_written']} "
        f"delta={counts['delta_written']} skipped={counts['skipped']}"
    )
    if delta_output_dir:
        print(f"Delta directory: {delta_output_dir}")
    report_path = _resolve_report_path(getattr(args, "report_dir", None), run_stamp=run_stamp)
    written_report = _write_sync_report(
        report_path,
        command="sync-delta",
        filters=filters,
        counts=counts,
        candidate_ids=ids,
        canonical_root=args.canonical_root,
        state_file=args.state_file,
        delta_output_dir=delta_output_dir,
    )
    if written_report:
        print(f"Report: {written_report}")
    return 0


def _cmd_import_local(args: argparse.Namespace) -> int:
    """Handle the ``import-local`` subcommand."""
    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        print(f"ERROR: input dir not found: {input_dir}", file=sys.stderr)
        return 1
    if not args.canonical_root:
        print("ERROR: import-local requires --canonical-root", file=sys.stderr)
        return 1
    if not args.state_file:
        print("ERROR: import-local requires --state-file", file=sys.stderr)
        return 1

    json_files = _iter_local_json_files(input_dir)
    if not json_files:
        print("No JSON files found in input directory.")
        return 0

    state = load_sync_state(args.state_file)
    counts = _empty_sync_counts()
    run_stamp = _make_run_stamp()
    delta_output_dir = _resolve_delta_output_dir(args.delta_output_dir, dated_delta=args.dated_delta, run_stamp=run_stamp)
    seen_ids: set[int] = set()
    candidate_ids: list[int] = []

    print(f"Importing local labels from {input_dir} ...")
    for file_path in json_files:
        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
            label = _normalize_local_label(raw, source_path=file_path, input_root=input_dir)
            dsld_id = int(label["id"])
            if dsld_id in seen_ids:
                logger.warning("Duplicate local label ID %s encountered at %s; skipping later duplicate", dsld_id, file_path)
                print(f"  SKIP duplicate ID {dsld_id}: {file_path}", file=sys.stderr)
                counts["skipped"] += 1
                counts["skipped_ids"].append(dsld_id)
                continue
            seen_ids.add(dsld_id)
            candidate_ids.append(dsld_id)
            _apply_synced_label(
                label,
                state=state,
                counts=counts,
                canonical_root=args.canonical_root,
                staging_dir=None,
                snapshot=False,
                filter_form_code=None,
                sync_source="import-local",
                status_filter=None,
                query_context={"input_dir": str(input_dir)},
                delta_output_dir=delta_output_dir,
                delta_only=True,
                force_refetch=args.force_refetch,
            )
        except Exception as exc:
            logger.warning("Failed to import local label %s: %s", file_path, exc)
            print(f"  SKIP {file_path}: {exc}", file=sys.stderr)
            counts["failed_ids"].append(file_path.stem)

    save_sync_state(args.state_file, state)
    print(
        f"\nDone. canonical={counts['canonical_written']} "
        f"delta={counts['delta_written']} skipped={counts['skipped']}"
    )
    if delta_output_dir:
        print(f"Delta directory: {delta_output_dir}")
    report_path = _resolve_report_path(getattr(args, "report_dir", None), run_stamp=run_stamp)
    written_report = _write_sync_report(
        report_path,
        command="import-local",
        filters={"input_dir": str(input_dir)},
        counts=counts,
        candidate_ids=candidate_ids,
        canonical_root=args.canonical_root,
        state_file=args.state_file,
        delta_output_dir=delta_output_dir,
    )
    if written_report:
        print(f"Report: {written_report}")
    return 0


def _cmd_check_version(args: argparse.Namespace) -> int:
    """Handle the ``check-version`` subcommand."""
    print(f"dsld_api_sync v{__version__}")
    print("Checking DSLD API version ...")
    try:
        client = DSLDApiClient()
        version_info = client.get_version()
        print("  OK")
        for key in ("title", "config", "version", "versionTimeStamp", "esIndexProcessed"):
            value = version_info.get(key)
            if value is not None:
                print(f"  {key}: {value}")
        return 0
    except Exception as exc:
        print(f"  FAILED — {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="dsld_api_sync",
        description="CLI tool for syncing DSLD label data via the NIH API.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # -- probe ---------------------------------------------------------------
    p_probe = subparsers.add_parser("probe", help="Fetch and inspect a single label")
    p_probe.add_argument("--id", required=True, type=int, help="DSLD label ID to fetch")
    p_probe.add_argument("--reference", type=str, default=None, help="Path to reference JSON for parity check")

    # -- sync-brand ----------------------------------------------------------
    p_brand = subparsers.add_parser("sync-brand", help="Sync all labels for a brand")
    p_brand.add_argument("--brand", required=True, help="Brand name to search")
    p_brand.add_argument("--output-dir", help="Directory to write flat staging labels")
    p_brand.add_argument("--canonical-root", help="Canonical raw root to route labels by form")
    p_brand.add_argument("--state-file", help="Shared DSLD sync state file")
    p_brand.add_argument("--status", type=int, choices=[0, 1, 2], default=2, help="Market status filter (default 2=all)")
    p_brand.add_argument("--limit", type=int, default=None, help="Max discovery results (default all)")
    p_brand.add_argument("--snapshot", action="store_true", help="Write to timestamped snapshot subdir")

    # -- refresh-ids ---------------------------------------------------------
    p_refresh = subparsers.add_parser("refresh-ids", help="Re-fetch specific label IDs")
    p_refresh.add_argument("--ids", required=True, nargs="+", type=int, help="DSLD label IDs to fetch")
    p_refresh.add_argument("--output-dir", required=True, help="Directory to write labels")
    p_refresh.add_argument("--snapshot", action="store_true", help="Write to timestamped snapshot subdir")

    # -- verify-db -----------------------------------------------------------
    p_verify = subparsers.add_parser("verify-db", help="Sample-verify local labels against API")
    p_verify.add_argument("--input-dir", required=True, help="Directory with local JSON labels")
    p_verify.add_argument("--sample-size", type=int, default=10, help="Number of labels to sample (default 10)")

    # -- sync-query ----------------------------------------------------------
    p_query = subparsers.add_parser("sync-query", help="Sync labels matching a query")
    p_query.add_argument("--query", required=True, help="Search query")
    p_query.add_argument("--output-dir", required=True, help="Directory to write labels")
    p_query.add_argument("--limit", type=int, default=100, help="Max results (default 100)")
    p_query.add_argument("--snapshot", action="store_true", help="Write to timestamped snapshot subdir")

    # -- sync-filter ---------------------------------------------------------
    p_filter = subparsers.add_parser("sync-filter", help="Sync labels using DSLD search filters")
    p_filter.add_argument("--supplement-form", help="DSLD supplement_form code (e.g. e0176)")
    p_filter.add_argument("--ingredient-name", help="Ingredient name filter")
    p_filter.add_argument("--ingredient-category", help="Ingredient category filter")
    p_filter.add_argument("--brand", help="Brand filter")
    p_filter.add_argument("--status", type=int, choices=[0, 1, 2], default=2, help="Market status filter (default 2=all)")
    p_filter.add_argument("--date-start", help="Entry date start (YYYY-MM-DD)")
    p_filter.add_argument("--date-end", help="Entry date end (YYYY-MM-DD)")
    p_filter.add_argument("--limit", type=int, default=None, help="Max discovery results (default all)")
    p_filter.add_argument("--snapshot", action="store_true", help="Write staging labels to timestamped snapshot subdir")
    p_filter.add_argument("--staging-dir", help="Optional flat staging directory")
    p_filter.add_argument("--canonical-root", help="Canonical raw root to route labels by form")
    p_filter.add_argument("--state-file", help="Shared DSLD sync state file")

    # -- sync-delta ----------------------------------------------------------
    p_delta = subparsers.add_parser("sync-delta", help="Sync only new/changed labels from DSLD search filters")
    p_delta.add_argument("--supplement-form", help="DSLD supplement_form code (e.g. e0176)")
    p_delta.add_argument("--ingredient-name", help="Ingredient name filter")
    p_delta.add_argument("--ingredient-category", help="Ingredient category filter")
    p_delta.add_argument("--brand", help="Brand filter")
    p_delta.add_argument("--status", type=int, choices=[0, 1, 2], default=2, help="Market status filter (default 2=all)")
    p_delta.add_argument("--date-start", help="Entry date start (YYYY-MM-DD)")
    p_delta.add_argument("--date-end", help="Entry date end (YYYY-MM-DD)")
    p_delta.add_argument("--limit", type=int, default=None, help="Max discovery results (default all)")
    p_delta.add_argument("--canonical-root", required=True, help="Canonical raw root to route labels by form")
    p_delta.add_argument("--state-file", required=True, help="Shared DSLD sync state file")
    p_delta.add_argument("--delta-output-dir", help="Optional flat delta directory for downstream incremental runs")
    p_delta.add_argument(
        "--dated-delta",
        action="store_true",
        help="Write delta files into a fresh timestamped subdirectory under --delta-output-dir",
    )
    p_delta.add_argument("--report-dir", help="Optional directory to write a JSON sync report for this run")
    p_delta.add_argument("--force-refetch", action="store_true", help="Write labels even when unchanged in state")

    # -- import-local --------------------------------------------------------
    p_import = subparsers.add_parser("import-local", help="Import local manual DSLD JSON into canonical forms/state/delta")
    p_import.add_argument("--input-dir", required=True, help="Directory containing local DSLD JSON files (flat or nested)")
    p_import.add_argument("--canonical-root", required=True, help="Canonical raw root to route labels by form")
    p_import.add_argument("--state-file", required=True, help="Shared DSLD sync state file")
    p_import.add_argument("--delta-output-dir", help="Optional flat delta directory for downstream incremental runs")
    p_import.add_argument(
        "--dated-delta",
        action="store_true",
        help="Write delta files into a fresh timestamped subdirectory under --delta-output-dir",
    )
    p_import.add_argument("--report-dir", help="Optional directory to write a JSON import report for this run")
    p_import.add_argument("--force-refetch", action="store_true", help="Write labels even when unchanged in state")

    # -- check-version -------------------------------------------------------
    subparsers.add_parser("check-version", help="Print structured DSLD API version metadata")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the correct subcommand."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    handlers = {
        "probe": _cmd_probe,
        "sync-brand": _cmd_sync_brand,
        "refresh-ids": _cmd_refresh_ids,
        "verify-db": _cmd_verify_db,
        "sync-query": _cmd_sync_query,
        "sync-filter": _cmd_sync_filter,
        "sync-delta": _cmd_sync_delta,
        "import-local": _cmd_import_local,
        "check-version": _cmd_check_version,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
