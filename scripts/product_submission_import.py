#!/usr/bin/env python3
"""Import human-approved product submissions into the manual-label contract.

This adapter never scores, enriches, or publishes a product. It converts the
service-only approval export into the same ``manual_labels`` shape already
consumed by ``dsld_api_sync.py import-local``. The existing Clean → Enrich →
Score → Release train remains the sole publication authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable
from uuid import UUID

import env_loader  # noqa: F401  # Load the project .env without overriding shell vars.


SCHEMA_VERSION = "manual_label_v1"
RECEIPT_FILE = ".product_submission_import_receipts"
REVIEWER_DISPLAY_NAME = "PharmaGuide Clinical Team"
MAX_CANONICAL_BYTES = 512 * 1024
_ALLOWED_KINDS = frozenset({"label_mismatch", "missing_product"})
_ALLOWED_TOP_LEVEL_FIELDS = frozenset(
    {
        "brandName",
        "fullName",
        "ingredientRows",
        "nutritionalInfo",
        "offMarket",
        "otherIngredients",
        "physicalState",
        "productType",
        "servingSizes",
        "servingsPerContainer",
        "statements",
    }
)
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class SubmissionImportError(ValueError):
    """An approval export is unsafe or incompatible with the label contract."""


@dataclass(frozen=True)
class ImportResult:
    imported_submission_ids: list[str]
    already_imported_submission_ids: list[str]
    output_paths: list[Path]


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _required_string(
    value: object,
    field: str,
    *,
    max_length: int = 300,
) -> str:
    if not isinstance(value, str):
        raise SubmissionImportError(f"{field} must be a string")
    normalized = value.strip()
    if not normalized or len(normalized) > max_length:
        raise SubmissionImportError(f"{field} is missing or too long")
    return normalized


def _required_uuid(value: object, field: str) -> str:
    normalized = _required_string(value, field, max_length=36).lower()
    if not _UUID_PATTERN.fullmatch(normalized):
        raise SubmissionImportError(f"{field} must be a UUID")
    try:
        UUID(normalized)
    except ValueError as exc:
        raise SubmissionImportError(f"{field} must be a UUID") from exc
    return normalized


def _is_valid_gtin(value: str) -> bool:
    if len(value) not in {8, 12, 13, 14} or not value.isdigit():
        return False
    body = value[:-1]
    weighted_sum = sum(
        int(body[-position]) * (3 if position % 2 else 1)
        for position in range(1, len(body) + 1)
    )
    return (10 - weighted_sum % 10) % 10 == int(value[-1])


def _validate_label_payload(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SubmissionImportError("approved payload must be an object")
    unknown = sorted(set(payload) - _ALLOWED_TOP_LEVEL_FIELDS)
    if unknown:
        raise SubmissionImportError(
            "approved payload contains forbidden field(s): " + ", ".join(unknown)
        )

    normalized = dict(payload)
    normalized["fullName"] = _required_string(
        payload.get("fullName"),
        "approved payload fullName",
    )
    normalized["brandName"] = _required_string(
        payload.get("brandName"),
        "approved payload brandName",
    )
    ingredient_rows = payload.get("ingredientRows")
    if (
        not isinstance(ingredient_rows, list)
        or not ingredient_rows
        or len(ingredient_rows) > 200
        or not all(isinstance(row, dict) for row in ingredient_rows)
    ):
        raise SubmissionImportError(
            "approved payload ingredientRows must contain 1..200 objects"
        )
    serving_sizes = payload.get("servingSizes")
    if (
        not isinstance(serving_sizes, list)
        or not serving_sizes
        or len(serving_sizes) > 20
        or not all(isinstance(row, dict) for row in serving_sizes)
    ):
        raise SubmissionImportError(
            "approved payload servingSizes must contain 1..20 objects"
        )
    off_market = payload.get("offMarket", 0)
    if off_market not in {0, 1, False, True}:
        raise SubmissionImportError("approved payload offMarket must be 0 or 1")
    normalized["offMarket"] = int(bool(off_market))
    return normalized


def _parse_approved_at(value: object) -> tuple[str, str]:
    text = _required_string(value, "approved_at", max_length=40)
    try:
        parsed = datetime.fromisoformat(
            text[:-1] + "+00:00" if text.endswith("Z") else text
        )
    except ValueError as exc:
        raise SubmissionImportError("approved_at must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise SubmissionImportError("approved_at must include a timezone")
    return text, parsed.date().isoformat()


def build_manual_label(export_row: object) -> dict[str, Any]:
    """Validate one service export and build its pipeline-owned label."""
    if not isinstance(export_row, dict):
        raise SubmissionImportError("approved export row must be an object")
    required_export_fields = {
        "approved_at",
        "approved_payload_canonical",
        "kind",
        "normalized_upc",
        "payload_sha256",
        "reviewer_id",
        "schema_version",
        "submission_id",
    }
    optional_export_fields = {"target_dsld_id"}
    unknown_export_fields = (
        set(export_row) - required_export_fields - optional_export_fields
    )
    missing_export_fields = required_export_fields - set(export_row)
    if unknown_export_fields or missing_export_fields:
        raise SubmissionImportError(
            "approved export fields do not match the pinned schema"
        )

    submission_id = _required_uuid(export_row["submission_id"], "submission_id")
    reviewer_id = _required_uuid(export_row["reviewer_id"], "reviewer_id")
    kind = _required_string(export_row["kind"], "kind", max_length=30)
    if kind not in _ALLOWED_KINDS:
        raise SubmissionImportError("kind is unsupported")
    if export_row["schema_version"] != SCHEMA_VERSION:
        raise SubmissionImportError("schema_version is unsupported")

    raw_upc = export_row["normalized_upc"]
    if raw_upc is not None:
        upc = _required_string(raw_upc, "normalized_upc", max_length=14)
        if not _is_valid_gtin(upc):
            raise SubmissionImportError("normalized_upc is not a valid GTIN")
    else:
        if kind == "missing_product":
            raise SubmissionImportError("normalized_upc is required")
        upc = ""

    canonical = _required_string(
        export_row["approved_payload_canonical"],
        "approved_payload_canonical",
        max_length=MAX_CANONICAL_BYTES,
    )
    if len(canonical.encode("utf-8")) > MAX_CANONICAL_BYTES:
        raise SubmissionImportError("approved payload is too large")
    payload_hash = _required_string(
        export_row["payload_sha256"],
        "payload_sha256",
        max_length=64,
    ).lower()
    actual_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if not re.fullmatch(r"[0-9a-f]{64}", payload_hash) or actual_hash != payload_hash:
        raise SubmissionImportError("approved payload hash does not match")
    try:
        decoded_payload = json.loads(canonical)
    except json.JSONDecodeError as exc:
        raise SubmissionImportError("approved payload is not JSON") from exc
    if _canonical_json(decoded_payload) != canonical:
        raise SubmissionImportError("approved payload is not canonical JSON")
    payload = _validate_label_payload(decoded_payload)

    approved_at, verified_date = _parse_approved_at(export_row["approved_at"])
    if kind == "label_mismatch":
        target_id = _required_string(
            export_row.get("target_dsld_id"),
            "target_dsld_id",
            max_length=30,
        )
        if not target_id.isdigit():
            raise SubmissionImportError("target_dsld_id must be numeric")
        product_id = target_id
        lineage_key = f"dsld:{target_id}"
        source_record_id = target_id
    else:
        if export_row.get("target_dsld_id") is not None:
            raise SubmissionImportError(
                "missing-product export cannot specify target_dsld_id"
            )
        product_id = "PG_SUB_" + submission_id.replace("-", "").upper()
        lineage_key = f"pharmaguide_submission:{submission_id}"
        source_record_id = submission_id

    return {
        "id": product_id,
        **payload,
        "upcSku": upc,
        "src": f"local/manual_labels/product_submissions/{product_id}",
        "source_type": "external_manual",
        "manual_product_provenance": {
            "source_kind": "private_product_submission",
            "source_record_id": submission_id,
            "label_verified_at": verified_date,
            "review_status": "verified",
            "reviewer": REVIEWER_DISPLAY_NAME,
            "reviewer_record_id": reviewer_id,
        },
        "label_record_metadata": {
            "source_name": "PharmaGuide verified product submission",
            "source_record_id": source_record_id,
            "source_date": verified_date,
            "source_updated_date": verified_date,
            "product_status": "discontinued"
            if payload["offMarket"]
            else "active",
            "lineage_key": lineage_key,
            "reviewed_at": approved_at,
        },
    }


def _read_receipts(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 1, "submissions": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SubmissionImportError("import receipt file is unreadable") from exc
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != 1
        or not isinstance(value.get("submissions"), dict)
    ):
        raise SubmissionImportError("import receipt file has an unknown schema")
    return value


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def materialize_approved_submissions(
    export_rows: Iterable[object],
    *,
    output_dir: str | Path,
) -> ImportResult:
    """Atomically materialize validated labels and immutable import receipts."""
    destination = Path(output_dir)
    receipt_path = destination / RECEIPT_FILE
    receipts = _read_receipts(receipt_path)
    receipt_rows: dict[str, dict[str, Any]] = receipts["submissions"]

    prepared: list[tuple[str, dict[str, Any], str, Path]] = []
    seen_submission_ids: set[str] = set()
    seen_product_ids: set[str] = set()
    upc_owner = {
        str(value.get("upc")): submission_id
        for submission_id, value in receipt_rows.items()
        if isinstance(value, dict) and value.get("upc")
    }
    already_imported: list[str] = []

    for raw_row in export_rows:
        label = build_manual_label(raw_row)
        assert isinstance(raw_row, dict)  # Established by build_manual_label.
        submission_id = str(raw_row["submission_id"]).lower()
        if submission_id in seen_submission_ids:
            raise SubmissionImportError("duplicate submission_id in export")
        seen_submission_ids.add(submission_id)
        product_id = str(label["id"])
        if product_id in seen_product_ids:
            raise SubmissionImportError("duplicate product identity in export")
        seen_product_ids.add(product_id)

        upc = str(label["upcSku"])
        if upc:
            existing_upc_owner = upc_owner.get(upc)
            if existing_upc_owner is not None and existing_upc_owner != submission_id:
                raise SubmissionImportError(
                    f"UPC {upc} is already owned by submission {existing_upc_owner}"
                )
            upc_owner[upc] = submission_id

        serialized = json.dumps(label, ensure_ascii=False, indent=2) + "\n"
        label_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        output_path = destination / f"{product_id}.json"
        existing_receipt = receipt_rows.get(submission_id)
        if existing_receipt is not None:
            if (
                existing_receipt.get("label_sha256") != label_hash
                or not output_path.exists()
                or hashlib.sha256(output_path.read_bytes()).hexdigest() != label_hash
            ):
                raise SubmissionImportError(
                    "an imported submission changed after approval"
                )
            already_imported.append(submission_id)
            continue
        if output_path.exists():
            try:
                existing_label_hash = hashlib.sha256(
                    output_path.read_bytes()
                ).hexdigest()
            except OSError as exc:
                raise SubmissionImportError(
                    f"existing manual label is unreadable: {output_path.name}"
                ) from exc
            if existing_label_hash != label_hash:
                raise SubmissionImportError(
                    "refusing to overwrite changed manual label "
                    f"{output_path.name}"
                )
            # A crash can occur after the atomic label replace but before the
            # receipt replace. Exact bytes prove this is the same approval, so
            # safely recreate the receipt and refresh mtime for the pipeline.
        prepared.append((submission_id, label, serialized, output_path))

    imported: list[str] = []
    output_paths: list[Path] = []
    for submission_id, label, serialized, output_path in prepared:
        _atomic_write_text(output_path, serialized)
        label_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        receipt_rows[submission_id] = {
            "label_sha256": label_hash,
            "output_file": output_path.name,
            "product_id": label["id"],
            "upc": label["upcSku"],
        }
        imported.append(submission_id)
        output_paths.append(output_path)

    if prepared or not receipt_path.exists():
        receipt_content = json.dumps(receipts, indent=2, sort_keys=True) + "\n"
        _atomic_write_text(receipt_path, receipt_content)
    return ImportResult(imported, already_imported, output_paths)


def fetch_approved_submissions(*, limit: int = 100) -> list[dict[str, Any]]:
    """Read the service-only approval export without exposing user evidence."""
    if not 1 <= limit <= 500:
        raise SubmissionImportError("fetch limit must be between 1 and 500")
    base_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base_url or not service_key:
        raise SubmissionImportError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required"
        )
    request = urllib.request.Request(
        f"{base_url}/rest/v1/rpc/export_approved_product_submissions",
        data=json.dumps({"p_limit": limit}).encode("utf-8"),
        headers={
            "apikey": service_key,
            "authorization": f"Bearer {service_key}",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            decoded = json.loads(response.read())
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise SubmissionImportError("approved submission fetch failed") from exc
    if not isinstance(decoded, list) or not all(
        isinstance(row, dict) for row in decoded
    ):
        raise SubmissionImportError("approval export response is malformed")
    return decoded


def _service_rpc(function_name: str, payload: dict[str, object]) -> object:
    base_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base_url or not service_key:
        raise SubmissionImportError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required"
        )
    request = urllib.request.Request(
        f"{base_url}/rest/v1/rpc/{function_name}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "apikey": service_key,
            "authorization": f"Bearer {service_key}",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise SubmissionImportError(f"{function_name} RPC failed") from exc


def mark_released_submissions_promoted(
    *,
    output_dir: str | Path,
    catalog_db: str | Path,
    detail_blobs_dir: str | Path,
    rpc: Callable[[str, dict[str, object]], object] = _service_rpc,
) -> list[str]:
    """Mark only receipts proven to own the released catalog representation.

    Product-ID presence alone is insufficient for a label correction because
    its numeric DSLD identity already existed before the correction. The core
    row's pinned detail-blob hash and the blob's submission lineage jointly
    prove that the reviewed label, rather than the prior catalog row, shipped.
    """
    destination = Path(output_dir)
    receipt_path = destination / RECEIPT_FILE
    receipts = _read_receipts(receipt_path)
    receipt_rows: dict[str, dict[str, Any]] = receipts["submissions"]
    if not receipt_rows:
        return []

    catalog_path = Path(catalog_db)
    if not catalog_path.is_file():
        raise SubmissionImportError("released catalog database is missing")
    try:
        with sqlite3.connect(f"file:{catalog_path}?mode=ro", uri=True) as connection:
            version_row = connection.execute(
                "select value from export_manifest where key = 'db_version'"
            ).fetchone()
            released_products = {
                str(row[0]): str(row[1] or "")
                for row in connection.execute(
                    "select dsld_id, detail_blob_sha256 from products_core"
                )
            }
    except sqlite3.Error as exc:
        raise SubmissionImportError("released catalog database is malformed") from exc
    if (
        not version_row
        or not isinstance(version_row[0], str)
        or not version_row[0].strip()
    ):
        raise SubmissionImportError("released catalog version is unavailable")
    catalog_version = version_row[0].strip()

    detail_root = Path(detail_blobs_dir)
    promoted: list[str] = []
    for submission_id in sorted(receipt_rows):
        receipt = receipt_rows[submission_id]
        if receipt.get("promoted_catalog_version"):
            continue
        product_id = str(receipt.get("product_id") or "")
        if product_id not in released_products:
            continue
        expected_blob_hash = released_products[product_id]
        if not re.fullmatch(r"[0-9a-f]{64}", expected_blob_hash):
            raise SubmissionImportError(
                f"released product {product_id} has no valid detail-blob hash"
            )
        detail_path = detail_root / f"{product_id}.json"
        try:
            detail_bytes = detail_path.read_bytes()
            detail_blob = json.loads(detail_bytes)
        except (OSError, json.JSONDecodeError) as exc:
            raise SubmissionImportError(
                f"released detail blob is unavailable for {product_id}"
            ) from exc
        if hashlib.sha256(detail_bytes).hexdigest() != expected_blob_hash:
            raise SubmissionImportError(
                f"released detail blob hash does not match for {product_id}"
            )
        label_record = (
            detail_blob.get("label_record")
            if isinstance(detail_blob, dict)
            else None
        )
        if (
            not isinstance(label_record, dict)
            or label_record.get("source_record_id") != submission_id
        ):
            raise SubmissionImportError(
                f"released product {product_id} does not carry submission "
                f"lineage {submission_id}"
            )
        response = rpc(
            "mark_product_submission_promoted",
            {
                "p_catalog_version": catalog_version,
                "p_submission_id": submission_id,
            },
        )
        if response is not True:
            raise SubmissionImportError(
                f"promotion RPC did not confirm {submission_id}"
            )
        receipt["promoted_catalog_version"] = catalog_version
        promoted.append(submission_id)

    if promoted:
        _atomic_write_text(
            receipt_path,
            json.dumps(receipts, indent=2, sort_keys=True) + "\n",
        )
    return promoted


def _load_export_file(path: Path) -> list[dict[str, Any]]:
    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SubmissionImportError("approval export file is unreadable") from exc
    if not isinstance(decoded, list) or not all(
        isinstance(row, dict) for row in decoded
    ):
        raise SubmissionImportError("approval export file must contain an array")
    return decoded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--fetch", action="store_true")
    source.add_argument("--input", type=Path)
    source.add_argument("--mark-promoted", action="store_true")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("manual_labels/product_submissions"),
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--catalog-db",
        type=Path,
        default=Path("scripts/dist/pharmaguide_core.db"),
    )
    parser.add_argument(
        "--detail-blobs-dir",
        type=Path,
        default=Path("scripts/dist/detail_blobs"),
    )
    args = parser.parse_args(argv)

    try:
        if args.mark_promoted:
            promoted = mark_released_submissions_promoted(
                output_dir=args.output_dir,
                catalog_db=args.catalog_db,
                detail_blobs_dir=args.detail_blobs_dir,
            )
            print(
                json.dumps(
                    {
                        "catalog_db": str(args.catalog_db),
                        "promoted": len(promoted),
                    },
                    sort_keys=True,
                )
            )
            return 0
        rows = (
            fetch_approved_submissions(limit=args.limit)
            if args.fetch
            else _load_export_file(args.input)
        )
        result = materialize_approved_submissions(rows, output_dir=args.output_dir)
    except SubmissionImportError as exc:
        parser.error(str(exc))
    print(
        json.dumps(
            {
                "already_imported": len(result.already_imported_submission_ids),
                "imported": len(result.imported_submission_ids),
                "output_dir": str(args.output_dir),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
