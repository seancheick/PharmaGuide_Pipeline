#!/usr/bin/env python3
"""Reproducibly classify content-addressed detail-blob churn between releases.

The report is intentionally backed by a complete pair ledger.  Every changed
product records the old/new content hashes, byte sizes, classification, and
semantic field paths.  Both downloaded indexes and every downloaded blob are
SHA-256 verified before a result can be emitted.

This tool is read-only.  It never uploads, copies, moves, or deletes storage
objects.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from release_safety.transient import retry_transient


BUCKET = "pharmaguide"
ACTIVE_BLOB_PREFIX = "shared/details/sha256"
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class ChurnAnalysisError(RuntimeError):
    """Base error for a refused or incomplete churn analysis."""


class DetailIndexError(ChurnAnalysisError):
    """A version detail index does not satisfy the content-addressed contract."""


class BlobIntegrityError(ChurnAnalysisError):
    """Downloaded bytes do not match the hash frozen in the detail index."""


@dataclass(frozen=True)
class ChangedPair:
    product_id: str
    old_blob_sha256: str
    new_blob_sha256: str
    old_storage_path: str
    new_storage_path: str


@dataclass(frozen=True)
class ChangeClassification:
    classification: str
    changed_fields: tuple[str, ...] = ()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _expected_blob_path(digest: str) -> str:
    return f"{ACTIVE_BLOB_PREFIX}/{digest[:2]}/{digest}.json"


def _validated_index_entry(product_id: str, entry: object) -> tuple[str, str]:
    if not isinstance(entry, dict):
        raise DetailIndexError(f"detail index entry {product_id!r} is not an object")
    digest = entry.get("blob_sha256")
    storage_path = entry.get("storage_path")
    if not isinstance(digest, str) or not _HASH_RE.fullmatch(digest):
        raise DetailIndexError(f"detail index entry {product_id!r} has invalid blob_sha256")
    expected_path = _expected_blob_path(digest)
    if storage_path != expected_path:
        raise DetailIndexError(
            f"detail index entry {product_id!r} path mismatch: "
            f"expected {expected_path!r}, got {storage_path!r}"
        )
    return digest, storage_path


def parse_detail_index(payload: bytes, *, label: str) -> dict[str, dict[str, object]]:
    try:
        parsed = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DetailIndexError(f"{label} detail index is not valid UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise DetailIndexError(f"{label} detail index is not a JSON object")
    for product_id, entry in parsed.items():
        if not isinstance(product_id, str) or not product_id:
            raise DetailIndexError(f"{label} detail index has an invalid product ID")
        _validated_index_entry(product_id, entry)
    return parsed


def build_changed_pairs(
    old_index: Mapping[str, object],
    new_index: Mapping[str, object],
) -> tuple[list[ChangedPair], str]:
    """Return all changed common-product pairs and a stable pair fingerprint."""

    pairs: list[ChangedPair] = []
    for product_id in sorted(set(old_index) & set(new_index)):
        old_hash, old_path = _validated_index_entry(product_id, old_index[product_id])
        new_hash, new_path = _validated_index_entry(product_id, new_index[product_id])
        if old_hash == new_hash:
            continue
        pairs.append(
            ChangedPair(
                product_id=product_id,
                old_blob_sha256=old_hash,
                new_blob_sha256=new_hash,
                old_storage_path=old_path,
                new_storage_path=new_path,
            )
        )

    frozen = "\n".join(
        f"{pair.product_id}\t{pair.old_blob_sha256}\t{pair.new_blob_sha256}"
        for pair in pairs
    ).encode()
    return pairs, _sha256(frozen)


def _normalize_lists(value: Any, *, sources_only: bool, parent_key: str = "") -> Any:
    if isinstance(value, dict):
        return {
            key: _normalize_lists(child, sources_only=sources_only, parent_key=key)
            for key, child in value.items()
        }
    if isinstance(value, list):
        children = [
            _normalize_lists(child, sources_only=sources_only)
            for child in value
        ]
        if not sources_only or parent_key == "sources":
            return sorted(children, key=_canonical_json)
        return children
    return value


def _changed_fields(old: Any, new: Any, path: str = "") -> set[str]:
    if type(old) is not type(new):
        return {path or "<root>"}
    if isinstance(old, dict):
        changed: set[str] = set()
        for key in sorted(set(old) | set(new)):
            child_path = f"{path}.{key}" if path else key
            if key not in old or key not in new:
                changed.add(child_path)
            else:
                changed.update(_changed_fields(old[key], new[key], child_path))
        return changed
    if isinstance(old, list):
        changed = set()
        item_path = f"{path}[]" if path else "[]"
        if len(old) != len(new):
            changed.add(f"{item_path}(len)")
        for old_item, new_item in zip(old, new):
            changed.update(_changed_fields(old_item, new_item, item_path))
        return changed
    return set() if old == new else {path or "<root>"}


def classify_payload_change(old: Any, new: Any) -> ChangeClassification:
    if old == new:
        return ChangeClassification("serialization_only")
    if _normalize_lists(old, sources_only=True) == _normalize_lists(
        new, sources_only=True
    ):
        return ChangeClassification("sources_order_only")
    if _normalize_lists(old, sources_only=False) == _normalize_lists(
        new, sources_only=False
    ):
        return ChangeClassification("other_order_only")
    return ChangeClassification("semantic", tuple(sorted(_changed_fields(old, new))))


def _verified_json(payload: bytes, expected_hash: str, *, label: str) -> Any:
    actual_hash = _sha256(payload)
    if actual_hash != expected_hash:
        raise BlobIntegrityError(
            f"{label} blob hash mismatch: expected {expected_hash}, got {actual_hash}"
        )
    try:
        parsed = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BlobIntegrityError(f"{label} blob is not valid UTF-8 JSON") from exc
    return parsed


def analyze_changed_pairs(
    pairs: Sequence[ChangedPair],
    *,
    pair_fingerprint: str,
    fetch_payload: Callable[[str], bytes],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    classifications: Counter[str] = Counter()
    semantic_fields: Counter[str] = Counter()
    bytes_by_classification: Counter[str] = Counter()
    ledger: list[dict[str, object]] = []

    for pair in pairs:
        old_payload = fetch_payload(pair.old_storage_path)
        new_payload = fetch_payload(pair.new_storage_path)
        old = _verified_json(old_payload, pair.old_blob_sha256, label="old")
        new = _verified_json(new_payload, pair.new_blob_sha256, label="new")
        result = classify_payload_change(old, new)
        classifications[result.classification] += 1
        bytes_by_classification[result.classification] += len(new_payload)
        if result.classification == "semantic":
            semantic_fields.update(set(result.changed_fields))
        ledger.append(
            {
                **asdict(pair),
                "old_bytes": len(old_payload),
                "new_bytes": len(new_payload),
                "classification": result.classification,
                "changed_fields": list(result.changed_fields),
            }
        )

    report: dict[str, object] = {
        "population": "ALL changed common-product pairs (no sampling)",
        "changed_pairs": len(pairs),
        "pair_fingerprint_sha256": pair_fingerprint,
        "sources_order_only": classifications["sources_order_only"],
        "other_order_only": classifications["other_order_only"],
        "serialization_only": classifications["serialization_only"],
        "semantic": classifications["semantic"],
        "errors": 0,
        "avoidable_new_bytes_exact": (
            bytes_by_classification["sources_order_only"]
            + bytes_by_classification["serialization_only"]
        ),
        "other_order_only_new_bytes": bytes_by_classification["other_order_only"],
        "semantic_new_bytes": bytes_by_classification["semantic"],
        "top_semantic_fields": [
            [field, count] for field, count in semantic_fields.most_common()
        ],
    }
    return report, ledger


class StoragePayloadFetcher:
    def __init__(
        self,
        bucket_proxy: Any,
        *,
        quarantine_dates: Iterable[str] = (),
    ) -> None:
        self._bucket = bucket_proxy
        self._quarantine_dates = tuple(quarantine_dates)

    def __call__(self, active_path: str) -> bytes:
        digest = Path(active_path).stem
        paths = [active_path]
        paths.extend(
            f"shared/quarantine/{date}/{digest[:2]}/{digest}.json"
            for date in self._quarantine_dates
        )
        errors: list[str] = []
        for path in paths:
            try:
                payload = retry_transient(
                    lambda path=path: self._bucket.download(path),
                )
                if isinstance(payload, str):
                    return payload.encode()
                return bytes(payload)
            except Exception as exc:  # storage client error types vary by version
                errors.append(f"{path}: {exc}")
        raise ChurnAnalysisError(
            f"could not fetch indexed blob {digest}; tried: {' | '.join(errors)}"
        )


def _download(bucket_proxy: Any, path: str) -> bytes:
    payload = retry_transient(
        lambda: bucket_proxy.download(path),
    )
    return payload.encode() if isinstance(payload, str) else bytes(payload)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-version", required=True)
    parser.add_argument("--new-version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pair-ledger", type=Path, required=True)
    parser.add_argument("--bucket", default=BUCKET)
    parser.add_argument(
        "--quarantine-date",
        action="append",
        default=[],
        help="Fallback quarantine date for indexed blobs absent from the active prefix.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    from supabase_client import get_supabase_client

    client = get_supabase_client()
    bucket = client.storage.from_(args.bucket)
    old_index_path = f"v{args.old_version}/detail_index.json"
    new_index_path = f"v{args.new_version}/detail_index.json"
    old_index_bytes = _download(bucket, old_index_path)
    new_index_bytes = _download(bucket, new_index_path)
    old_index = parse_detail_index(old_index_bytes, label=args.old_version)
    new_index = parse_detail_index(new_index_bytes, label=args.new_version)
    pairs, pair_fingerprint = build_changed_pairs(old_index, new_index)
    report, ledger = analyze_changed_pairs(
        pairs,
        pair_fingerprint=pair_fingerprint,
        fetch_payload=StoragePayloadFetcher(
            bucket,
            quarantine_dates=args.quarantine_date,
        ),
    )
    report.update(
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "old_version": args.old_version,
            "new_version": args.new_version,
            "old_index_path": old_index_path,
            "new_index_path": new_index_path,
            "old_index_sha256": _sha256(old_index_bytes),
            "new_index_sha256": _sha256(new_index_bytes),
            "old_index_entries": len(old_index),
            "new_index_entries": len(new_index),
            "common_products": len(set(old_index) & set(new_index)),
            "added_products": sorted(set(new_index) - set(old_index)),
            "removed_products": sorted(set(old_index) - set(new_index)),
            "pair_ledger": str(args.pair_ledger),
            "classification_notes": (
                "sources_order_only normalizes only lists stored under a sources key; "
                "other_order_only sorts every list and is diagnostic only because some "
                "non-source list order can be semantic"
            ),
        }
    )
    ledger_artifact = {
        "schema_version": 1,
        "old_version": args.old_version,
        "new_version": args.new_version,
        "old_index_sha256": _sha256(old_index_bytes),
        "new_index_sha256": _sha256(new_index_bytes),
        "pair_fingerprint_sha256": pair_fingerprint,
        "pair_count": len(ledger),
        "pairs": ledger,
    }
    _write_json(args.output, report)
    _write_json(args.pair_ledger, ledger_artifact)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ChurnAnalysisError as exc:
        print(f"[refused] {exc}", file=sys.stderr)
        raise SystemExit(2)
