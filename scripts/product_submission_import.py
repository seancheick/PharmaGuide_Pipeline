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
import io
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable
from uuid import UUID

import env_loader  # noqa: F401  # Load the project .env without overriding shell vars.
from PIL import Image, ImageOps


SCHEMA_VERSION = "manual_label_v1"
RECEIPT_FILE = ".product_submission_import_receipts"
REVIEWER_DISPLAY_NAME = "PharmaGuide Clinical Team"
MAX_CANONICAL_BYTES = 512 * 1024
MAX_EXPORT_PAGES = 1000
MAX_PRODUCT_IMAGE_BYTES = 10 * 1024 * 1024
MAX_PRODUCT_IMAGE_PIXELS = 40_000_000
PRODUCT_IMAGE_MAX_EDGE = 900
PRODUCT_IMAGE_WEBP_QUALITY = 88
APPROVAL_FETCH_RETRY_DELAYS_SECONDS = (0.5, 1.5)
_RETRYABLE_HTTP_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})
_ALLOWED_KINDS = frozenset({"label_mismatch", "missing_product"})
_ALLOWED_TOP_LEVEL_FIELDS = frozenset(
    {
        "brandName",
        "fullName",
        "ingredientRows",
        "nutritionalInfo",
        "offMarket",
        "otherIngredients",
        "otherIngredientsDisclosure",
        "physicalState",
        "productType",
        "servingSizes",
        "servingsPerContainer",
        "statements",
    }
)
_ALLOWED_INGREDIENT_FIELDS = frozenset(
    {
        "alternateNames",
        "category",
        "description",
        "forms",
        "ingredientGroup",
        "ingredientId",
        "name",
        "nestedRows",
        "notes",
        "order",
        "quantity",
        "uniiCode",
    }
)
_ALLOWED_QUANTITY_FIELDS = frozenset(
    {
        "dailyValueTargetGroup",
        "operator",
        "quantity",
        "servingSizeOrder",
        "servingSizeQuantity",
        "servingSizeUnit",
        "unit",
    }
)
_ALLOWED_FORM_FIELDS = frozenset(
    {
        "category",
        "ingredientGroup",
        "ingredientId",
        "name",
        "order",
        "percent",
        "prefix",
        "uniiCode",
    }
)
_ALLOWED_SERVING_FIELDS = frozenset(
    {
        "inSFB",
        "maxDailyServings",
        "maxQuantity",
        "minDailyServings",
        "minQuantity",
        "notes",
        "order",
        "unit",
    }
)
_ALLOWED_STATEMENT_FIELDS = frozenset({"notes", "type"})
_ALLOWED_CLASSIFICATION_FIELDS = frozenset(
    {"langualCode", "langualCodeDescription", "name"}
)
_RESOLVED_OTHER_INGREDIENT_DISCLOSURES = frozenset(
    {"present", "declared_none", "included_on_facts_panel"}
)
_MAX_INGREDIENT_DEPTH = 5
_MAX_TOTAL_INGREDIENT_ROWS = 500
_POSITIVE_NUMBER_MINIMUM = 2.220446049250313e-16
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


def _reject_unknown_keys(
    value: dict[str, Any],
    allowed: frozenset[str],
    field: str,
) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise SubmissionImportError(f"{field} contains unknown field {unknown[0]}")


def _optional_string(
    value: object,
    field: str,
    *,
    max_length: int,
) -> None:
    if value is None:
        return
    if not isinstance(value, str) or len(value) > max_length:
        raise SubmissionImportError(f"{field} must be a string")


def _finite_number(value: object, field: str, *, minimum: float) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not float(value) >= minimum
        or not float("-inf") < float(value) < float("inf")
    ):
        raise SubmissionImportError(
            f"{field} must be a finite number >= {minimum}"
        )
    return float(value)


def _optional_positive_integer(value: object, field: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SubmissionImportError(f"{field} must be a positive integer")


def _validate_quantity(value: object, path: str) -> None:
    if not isinstance(value, dict):
        raise SubmissionImportError(f"{path} must be an object")
    _reject_unknown_keys(value, _ALLOWED_QUANTITY_FIELDS, path)
    _finite_number(value.get("quantity"), f"{path}.quantity", minimum=0)
    _required_string(value.get("unit"), f"{path}.unit", max_length=80)
    _optional_positive_integer(
        value.get("servingSizeOrder"), f"{path}.servingSizeOrder"
    )
    if value.get("servingSizeQuantity") is not None:
        _finite_number(
            value["servingSizeQuantity"],
            f"{path}.servingSizeQuantity",
            minimum=0,
        )
    _optional_string(value.get("operator"), f"{path}.operator", max_length=20)
    _optional_string(
        value.get("servingSizeUnit"),
        f"{path}.servingSizeUnit",
        max_length=80,
    )
    targets = value.get("dailyValueTargetGroup")
    if targets is not None and (not isinstance(targets, list) or len(targets) > 30):
        raise SubmissionImportError(
            f"{path}.dailyValueTargetGroup must be an array"
        )


def _validate_form(value: object, path: str) -> None:
    if not isinstance(value, dict):
        raise SubmissionImportError(f"{path} must be an object")
    _reject_unknown_keys(value, _ALLOWED_FORM_FIELDS, path)
    _required_string(value.get("name"), f"{path}.name", max_length=300)
    _optional_positive_integer(value.get("order"), f"{path}.order")
    _optional_positive_integer(value.get("ingredientId"), f"{path}.ingredientId")
    _optional_string(value.get("prefix"), f"{path}.prefix", max_length=80)
    _optional_string(value.get("category"), f"{path}.category", max_length=120)
    _optional_string(
        value.get("ingredientGroup"), f"{path}.ingredientGroup", max_length=300
    )
    _optional_string(value.get("uniiCode"), f"{path}.uniiCode", max_length=80)
    if value.get("percent") is not None:
        percent = _finite_number(value["percent"], f"{path}.percent", minimum=0)
        if percent > 100:
            raise SubmissionImportError(f"{path}.percent must be <= 100")


def _validate_ingredient_row(
    value: object,
    path: str,
    *,
    depth: int,
    row_counter: list[int],
) -> None:
    if depth > _MAX_INGREDIENT_DEPTH:
        raise SubmissionImportError(f"{path} exceeds maximum nesting depth")
    row_counter[0] += 1
    if row_counter[0] > _MAX_TOTAL_INGREDIENT_ROWS:
        raise SubmissionImportError("ingredient rows exceed maximum total")
    if not isinstance(value, dict):
        raise SubmissionImportError(f"{path} must be an object")
    _reject_unknown_keys(value, _ALLOWED_INGREDIENT_FIELDS, path)
    _required_string(value.get("name"), f"{path}.name", max_length=300)
    _required_string(
        value.get("ingredientGroup"), f"{path}.ingredientGroup", max_length=300
    )
    _optional_positive_integer(value.get("order"), f"{path}.order")
    _optional_positive_integer(value.get("ingredientId"), f"{path}.ingredientId")
    _optional_string(value.get("category"), f"{path}.category", max_length=120)
    _optional_string(
        value.get("description"), f"{path}.description", max_length=2000
    )
    _optional_string(value.get("notes"), f"{path}.notes", max_length=2000)
    _optional_string(value.get("uniiCode"), f"{path}.uniiCode", max_length=80)

    quantities = value.get("quantity")
    if not isinstance(quantities, list) or len(quantities) > 20:
        raise SubmissionImportError(f"{path}.quantity must contain 0..20 rows")
    for index, quantity in enumerate(quantities):
        _validate_quantity(quantity, f"{path}.quantity[{index}]")

    forms = value.get("forms")
    if not isinstance(forms, list) or len(forms) > 20:
        raise SubmissionImportError(f"{path}.forms must contain 0..20 rows")
    for index, form in enumerate(forms):
        _validate_form(form, f"{path}.forms[{index}]")

    nested_rows = value.get("nestedRows")
    if not isinstance(nested_rows, list) or len(nested_rows) > 100:
        raise SubmissionImportError(f"{path}.nestedRows must contain 0..100 rows")
    for index, nested in enumerate(nested_rows):
        _validate_ingredient_row(
            nested,
            f"{path}.nestedRows[{index}]",
            depth=depth + 1,
            row_counter=row_counter,
        )

    alternate_names = value.get("alternateNames")
    if alternate_names is not None:
        if not isinstance(alternate_names, list) or len(alternate_names) > 50:
            raise SubmissionImportError(
                f"{path}.alternateNames must contain valid strings"
            )
        for index, name in enumerate(alternate_names):
            _required_string(
                name, f"{path}.alternateNames[{index}]", max_length=300
            )


def _validate_serving_size(value: object, path: str) -> None:
    if not isinstance(value, dict):
        raise SubmissionImportError(f"{path} must be an object")
    _reject_unknown_keys(value, _ALLOWED_SERVING_FIELDS, path)
    min_quantity = _finite_number(
        value.get("minQuantity"),
        f"{path}.minQuantity",
        minimum=_POSITIVE_NUMBER_MINIMUM,
    )
    max_quantity = _finite_number(
        value.get("maxQuantity"),
        f"{path}.maxQuantity",
        minimum=_POSITIVE_NUMBER_MINIMUM,
    )
    _required_string(value.get("unit"), f"{path}.unit", max_length=80)
    _optional_positive_integer(value.get("order"), f"{path}.order")
    _optional_string(value.get("notes"), f"{path}.notes", max_length=1000)
    for field in ("minDailyServings", "maxDailyServings"):
        if value.get(field) is not None:
            _finite_number(
                value[field],
                f"{path}.{field}",
                minimum=_POSITIVE_NUMBER_MINIMUM,
            )
    if value.get("inSFB") is not None and not isinstance(value["inSFB"], bool):
        raise SubmissionImportError(f"{path}.inSFB must be a boolean")
    if max_quantity < min_quantity:
        raise SubmissionImportError(f"{path}.maxQuantity must be >= minQuantity")


def _validate_classification(value: object, field: str) -> None:
    if not isinstance(value, dict):
        raise SubmissionImportError(f"{field} must be an object")
    _reject_unknown_keys(value, _ALLOWED_CLASSIFICATION_FIELDS, field)
    _optional_string(value.get("langualCode"), f"{field}.langualCode", max_length=40)
    _optional_string(
        value.get("langualCodeDescription"),
        f"{field}.langualCodeDescription",
        max_length=300,
    )
    _optional_string(value.get("name"), f"{field}.name", max_length=300)
    _required_string(
        value.get("name") or value.get("langualCodeDescription"),
        f"{field} display name",
        max_length=300,
    )


def _validate_statements(value: object) -> None:
    if not isinstance(value, list) or len(value) > 100:
        raise SubmissionImportError("statements must contain 0..100 rows")
    for index, statement in enumerate(value):
        path = f"statements[{index}]"
        if not isinstance(statement, dict):
            raise SubmissionImportError(f"{path} must be an object")
        _reject_unknown_keys(statement, _ALLOWED_STATEMENT_FIELDS, path)
        _required_string(statement.get("type"), f"{path}.type", max_length=200)
        _required_string(statement.get("notes"), f"{path}.notes", max_length=5000)


def _validate_servings_per_container(value: object) -> None:
    if isinstance(value, bool):
        raise SubmissionImportError("servingsPerContainer must be positive")
    if isinstance(value, (int, float)):
        _finite_number(
            value,
            "servingsPerContainer",
            minimum=_POSITIVE_NUMBER_MINIMUM,
        )
        return
    text = _required_string(value, "servingsPerContainer", max_length=40)
    try:
        parsed = float(text)
    except ValueError as exc:
        raise SubmissionImportError(
            "servingsPerContainer must be positive"
        ) from exc
    _finite_number(
        parsed,
        "servingsPerContainer",
        minimum=_POSITIVE_NUMBER_MINIMUM,
    )


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
    ):
        raise SubmissionImportError(
            "approved payload ingredientRows must contain 1..200 rows"
        )
    row_counter = [0]
    for index, row in enumerate(ingredient_rows):
        _validate_ingredient_row(
            row,
            f"ingredientRows[{index}]",
            depth=1,
            row_counter=row_counter,
        )
    serving_sizes = payload.get("servingSizes")
    if (
        not isinstance(serving_sizes, list)
        or not serving_sizes
        or len(serving_sizes) > 20
    ):
        raise SubmissionImportError(
            "approved payload servingSizes must contain 1..20 rows"
        )
    for index, serving_size in enumerate(serving_sizes):
        _validate_serving_size(serving_size, f"servingSizes[{index}]")
    off_market = payload.get("offMarket", 0)
    if off_market not in {0, 1, False, True}:
        raise SubmissionImportError("approved payload offMarket must be 0 or 1")
    normalized["offMarket"] = int(bool(off_market))

    if payload.get("servingsPerContainer") is not None:
        _validate_servings_per_container(payload["servingsPerContainer"])
    if payload.get("physicalState") is not None:
        _validate_classification(payload["physicalState"], "physicalState")
    if payload.get("productType") is not None:
        _validate_classification(payload["productType"], "productType")
    if payload.get("statements") is not None:
        _validate_statements(payload["statements"])
    if payload.get("nutritionalInfo") is not None and not isinstance(
        payload["nutritionalInfo"], dict
    ):
        raise SubmissionImportError("nutritionalInfo must be an object")

    disclosure = _required_string(
        payload.get("otherIngredientsDisclosure"),
        "otherIngredientsDisclosure",
        max_length=40,
    )
    if disclosure not in _RESOLVED_OTHER_INGREDIENT_DISCLOSURES:
        raise SubmissionImportError(
            "otherIngredientsDisclosure is unresolved or invalid"
        )
    other_ingredients = payload.get("otherIngredients", "")
    if not isinstance(other_ingredients, str) or len(other_ingredients) > 20_000:
        raise SubmissionImportError("otherIngredients must be a string")
    normalized_other_ingredients = other_ingredients.strip()
    if disclosure == "present" and not normalized_other_ingredients:
        raise SubmissionImportError("present other ingredients require text")
    if disclosure != "present" and normalized_other_ingredients:
        raise SubmissionImportError(
            f"{disclosure} requires empty otherIngredients"
        )
    return normalized


def _pipeline_other_ingredient_rows(label_text: str) -> list[dict[str, str]]:
    """Convert reviewed disclosure text into the cleaner's supported row shape.

    The approval contract intentionally stores the disclosure exactly as the
    reviewer read it. The cleaner contract, however, accepts a list of rows.
    Split only on top-level commas/semicolons so parenthesized source details
    remain attached to their ingredient. Ambiguous, unbalanced grouping fails
    closed instead of silently changing label meaning.
    """
    if not label_text:
        return []

    matching = {")": "(", "]": "[", "}": "{"}
    openings = set(matching.values())
    stack: list[str] = []
    parts: list[str] = []
    start = 0

    for index, character in enumerate(label_text):
        if character in openings:
            stack.append(character)
        elif character in matching:
            if not stack or stack[-1] != matching[character]:
                raise SubmissionImportError(
                    "otherIngredients has unbalanced grouping punctuation"
                )
            stack.pop()
        elif character in {",", ";"} and not stack:
            part = label_text[start:index].strip()
            if not part:
                raise SubmissionImportError(
                    "otherIngredients contains an empty ingredient segment"
                )
            parts.append(part)
            start = index + 1

    if stack:
        raise SubmissionImportError(
            "otherIngredients has unbalanced grouping punctuation"
        )
    final_part = label_text[start:].strip()
    if not final_part:
        raise SubmissionImportError(
            "otherIngredients contains an empty ingredient segment"
        )
    parts.append(final_part)
    return [{"name": part} for part in parts]


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
    pipeline_payload = dict(payload)
    pipeline_payload["otherIngredients"] = {
        "ingredients": _pipeline_other_ingredient_rows(
            str(payload.get("otherIngredients") or "")
        )
    }

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
    else:
        if export_row.get("target_dsld_id") is not None:
            raise SubmissionImportError(
                "missing-product export cannot specify target_dsld_id"
            )
        product_id = "PG_SUB_" + submission_id.replace("-", "").upper()
        lineage_key = f"pharmaguide_submission:{submission_id}"

    return {
        "id": product_id,
        **pipeline_payload,
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
            # The reviewed submission is the source record for both new
            # products and corrections. Existing-product identity remains in
            # ``id``/``lineage_key``; using the old DSLD id here would make a
            # correction indistinguishable from the label it replaced and
            # would fail the post-release provenance proof.
            "source_record_id": submission_id,
            "source_date": verified_date,
            "source_updated_date": verified_date,
            "product_status": "discontinued"
            if pipeline_payload["offMarket"]
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


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
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
        str(value.get("upc")): (
            submission_id,
            str(value.get("product_id") or ""),
        )
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
            if (
                existing_upc_owner is not None
                and existing_upc_owner[0] != submission_id
                and existing_upc_owner[1] != product_id
            ):
                raise SubmissionImportError(
                    f"UPC {upc} is already owned by submission "
                    f"{existing_upc_owner[0]}"
                )
            upc_owner[upc] = (submission_id, product_id)

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
                prior_receipts = [
                    row
                    for row in receipt_rows.values()
                    if isinstance(row, dict)
                    and row.get("product_id") == product_id
                    and row.get("output_file") == output_path.name
                    and row.get("label_sha256") == existing_label_hash
                ]
                if not prior_receipts:
                    raise SubmissionImportError(
                        "refusing to overwrite a manual label without an "
                        f"import receipt: {output_path.name}"
                    )
                if not all(
                    row.get("promoted_catalog_version") for row in prior_receipts
                ):
                    raise SubmissionImportError(
                        "refusing to replace an unpromoted manual label "
                        f"{output_path.name}"
                    )
            # A crash can occur after the atomic label replace but before the
            # receipt replace. Exact bytes prove this is the same approval, so
            # safely recreate the receipt and refresh mtime for the pipeline.
            # A later correction may also replace the current bytes, but only
            # after the receipt owning those exact bytes was promoted.
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


def _supabase_admin_headers() -> dict[str, str]:
    """Build REST headers for current secret keys or legacy service JWTs.

    Opaque ``sb_secret_`` keys are API keys, not JWTs, and must never be sent
    as bearer tokens. The legacy service-role key remains supported until the
    project finishes its key migration.
    """
    secret_key = os.environ.get("SUPABASE_SECRET_KEY", "").strip()
    legacy_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    admin_key = secret_key or legacy_key
    if not admin_key:
        raise SubmissionImportError(
            "SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY is required"
        )
    headers = {
        "apikey": admin_key,
        "content-type": "application/json",
    }
    if not admin_key.startswith("sb_secret_"):
        headers["authorization"] = f"Bearer {admin_key}"
    return headers


def _export_cursor(
    row: dict[str, Any],
) -> tuple[tuple[datetime, int], str, str]:
    approved_at = _required_string(
        row.get("approved_at"),
        "approved export cursor approved_at",
        max_length=40,
    )
    try:
        parsed_at = datetime.fromisoformat(
            approved_at[:-1] + "+00:00"
            if approved_at.endswith("Z")
            else approved_at
        )
    except ValueError as exc:
        raise SubmissionImportError(
            "approved export cursor timestamp is invalid"
        ) from exc
    if parsed_at.tzinfo is None:
        raise SubmissionImportError(
            "approved export cursor timestamp requires a timezone"
        )
    submission_id = _required_uuid(
        row.get("submission_id"),
        "approved export cursor submission_id",
    )
    return (parsed_at, UUID(submission_id).int), approved_at, submission_id


def fetch_approved_submissions(*, limit: int = 100) -> list[dict[str, Any]]:
    """Read every approval through a bounded, stable service-only cursor.

    ``limit`` is the page size, not a total cap. Already-materialized approvals
    remain unpromoted until a release completes, so stopping after the oldest
    page would permanently starve newer work.
    """
    if not 1 <= limit <= 500:
        raise SubmissionImportError("fetch limit must be between 1 and 500")
    base_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    if not base_url:
        raise SubmissionImportError("SUPABASE_URL is required")
    rows: list[dict[str, Any]] = []
    seen_submission_ids: set[str] = set()
    prior_sort_key: tuple[datetime, int] | None = None
    after_approved_at: str | None = None
    after_submission_id: str | None = None

    for _page_number in range(MAX_EXPORT_PAGES):
        request = urllib.request.Request(
            f"{base_url}/rest/v1/rpc/export_approved_product_submissions",
            data=json.dumps(
                {
                    "p_after_approved_at": after_approved_at,
                    "p_after_submission_id": after_submission_id,
                    "p_limit": limit,
                }
            ).encode("utf-8"),
            headers=_supabase_admin_headers(),
            method="POST",
        )
        decoded: Any = None
        for attempt in range(len(APPROVAL_FETCH_RETRY_DELAYS_SECONDS) + 1):
            failure_detail = ""
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    decoded = json.loads(response.read())
                break
            except urllib.error.HTTPError as exc:
                failure_detail = f"HTTP {exc.code}"
                if exc.code not in _RETRYABLE_HTTP_STATUSES:
                    raise SubmissionImportError(
                        f"approved submission fetch failed: {failure_detail}"
                    ) from exc
            except (OSError, urllib.error.URLError) as exc:
                failure_detail = f"network error ({type(exc).__name__})"
            except json.JSONDecodeError:
                failure_detail = "invalid JSON response"

            if attempt >= len(APPROVAL_FETCH_RETRY_DELAYS_SECONDS):
                raise SubmissionImportError(
                    "approved submission fetch failed after "
                    f"{attempt + 1} attempts: {failure_detail}"
                )
            time.sleep(APPROVAL_FETCH_RETRY_DELAYS_SECONDS[attempt])
        if (
            not isinstance(decoded, list)
            or len(decoded) > limit
            or not all(isinstance(row, dict) for row in decoded)
        ):
            raise SubmissionImportError("approval export response is malformed")
        if not decoded:
            return rows

        for row in decoded:
            sort_key, cursor_approved_at, cursor_submission_id = _export_cursor(
                row
            )
            if prior_sort_key is not None and sort_key <= prior_sort_key:
                raise SubmissionImportError(
                    "approval export cursor did not advance"
                )
            if cursor_submission_id in seen_submission_ids:
                raise SubmissionImportError(
                    "approval export repeated a submission"
                )
            prior_sort_key = sort_key
            after_approved_at = cursor_approved_at
            after_submission_id = cursor_submission_id
            seen_submission_ids.add(cursor_submission_id)
            rows.append(row)

        if len(decoded) < limit:
            return rows

    raise SubmissionImportError("approval export exceeded the page safety limit")


def _service_rpc(function_name: str, payload: dict[str, object]) -> object:
    base_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    if not base_url:
        raise SubmissionImportError("SUPABASE_URL is required")
    request = urllib.request.Request(
        f"{base_url}/rest/v1/rpc/{function_name}",
        data=json.dumps(payload).encode("utf-8"),
        headers=_supabase_admin_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise SubmissionImportError(f"{function_name} RPC failed") from exc


def _download_private_storage_object(bucket_id: str, object_path: str) -> bytes:
    if bucket_id not in {
        "product-submission-photos",
        "product-submission-reviewer-images",
    }:
        raise SubmissionImportError("approved product image bucket is invalid")
    base_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    if not base_url:
        raise SubmissionImportError("SUPABASE_URL is required")
    encoded_path = urllib.parse.quote(object_path, safe="/")
    request = urllib.request.Request(
        f"{base_url}/storage/v1/object/authenticated/{bucket_id}/{encoded_path}",
        headers=_supabase_admin_headers(),
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            content = response.read(MAX_PRODUCT_IMAGE_BYTES + 1)
    except (OSError, urllib.error.URLError) as exc:
        raise SubmissionImportError("approved product image download failed") from exc
    if not 0 < len(content) <= MAX_PRODUCT_IMAGE_BYTES:
        raise SubmissionImportError("approved product image size is invalid")
    return content


def _render_catalog_webp(content: bytes, expected_content_type: str) -> bytes:
    expected_formats = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
    }
    expected_format = expected_formats.get(expected_content_type)
    if expected_format is None:
        raise SubmissionImportError("approved product image type is invalid")
    try:
        with Image.open(io.BytesIO(content)) as opened:
            if opened.format != expected_format:
                raise SubmissionImportError(
                    "approved product image type does not match its bytes"
                )
            if opened.width * opened.height > MAX_PRODUCT_IMAGE_PIXELS:
                raise SubmissionImportError(
                    "approved product image dimensions are too large"
                )
            image = ImageOps.exif_transpose(opened)
            image.load()
            if image.mode in {"RGBA", "LA", "P"}:
                alpha = image.convert("RGBA")
                background = Image.new("RGBA", alpha.size, "white")
                image = Image.alpha_composite(background, alpha).convert("RGB")
            else:
                image = image.convert("RGB")
            image.thumbnail(
                (PRODUCT_IMAGE_MAX_EDGE, PRODUCT_IMAGE_MAX_EDGE),
                Image.Resampling.LANCZOS,
            )
            rendered = io.BytesIO()
            image.save(
                rendered,
                format="WEBP",
                quality=PRODUCT_IMAGE_WEBP_QUALITY,
                method=6,
            )
            return rendered.getvalue()
    except SubmissionImportError:
        raise
    except (OSError, Image.DecompressionBombError) as exc:
        raise SubmissionImportError("approved product image cannot be decoded") from exc


def _load_product_image_index(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SubmissionImportError("product image index is unreadable") from exc
    if not isinstance(decoded, dict) or not all(
        isinstance(product_id, str) and isinstance(entry, dict)
        for product_id, entry in decoded.items()
    ):
        raise SubmissionImportError("product image index is malformed")
    return decoded


def _load_catalog_manifest(catalog_db: Path) -> dict | None:
    manifest_path = catalog_db.parent / "export_manifest.json"
    if not manifest_path.exists():
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SubmissionImportError("catalog export manifest is unreadable") from exc
    if not isinstance(manifest, dict):
        raise SubmissionImportError("catalog export manifest is malformed")
    return manifest


def _refresh_catalog_manifest_checksum(catalog_db: Path) -> None:
    manifest = _load_catalog_manifest(catalog_db)
    if manifest is None:
        return
    manifest_path = catalog_db.parent / "export_manifest.json"
    digest = hashlib.sha256(catalog_db.read_bytes()).hexdigest()
    manifest["checksum"] = f"sha256:{digest}"
    manifest["checksum_sha256"] = digest
    _atomic_write_text(
        manifest_path,
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )


def copy_approved_product_images(
    *,
    output_dir: str | Path,
    catalog_db: str | Path,
    product_images_dir: str | Path,
    rpc: Callable[[str, dict[str, object]], object] = _service_rpc,
    download: Callable[[str, str], bytes] = _download_private_storage_object,
) -> dict[str, int]:
    """Copy approved missing-product imagery into the canonical release bundle.

    Image failures are isolated from label publication. Each failed object stays
    eligible for a later release retry until the submission evidence retention
    window closes.
    """
    receipts = _read_receipts(Path(output_dir) / RECEIPT_FILE)["submissions"]
    image_dir = Path(product_images_dir)
    index_path = image_dir / "product_image_index.json"
    image_index = _load_product_image_index(index_path)
    catalog_path = Path(catalog_db)
    if not catalog_path.is_file():
        raise SubmissionImportError("catalog database is missing")
    manifest = _load_catalog_manifest(catalog_path) or {}
    excluded = manifest.get("excluded_by_gate") or []
    held_ids = {
        row.get("dsld_id") for row in excluded
        if isinstance(row, dict) and isinstance(row.get("dsld_id"), str)
    } if isinstance(excluded, list) else set()

    copied = 0
    failed = 0
    skipped = 0
    try:
        connection = sqlite3.connect(catalog_path)
        connection.execute(
            "select image_thumbnail_url from products_core limit 0"
        )
    except sqlite3.Error as exc:
        raise SubmissionImportError("catalog image schema is unavailable") from exc

    try:
        for submission_id, receipt in sorted(receipts.items()):
            if not isinstance(receipt, dict):
                raise SubmissionImportError("import receipt row is malformed")
            product_id = str(receipt.get("product_id") or "")
            if not product_id.startswith("PG_SUB_"):
                continue
            filename = f"{product_id}.webp"
            webp_path = image_dir / filename
            expected_url = f"product-images/{filename}"
            existing = connection.execute(
                "select image_thumbnail_url from products_core where dsld_id = ?",
                (product_id,),
            ).fetchone()
            if existing is None:
                if product_id in held_ids:
                    # The scorer's explicit exclusion is authoritative. Label
                    # approval does not guarantee readiness for catalog release.
                    skipped += 1
                    print(f"INFO: approved image deferred; catalog review hold: {product_id}", file=sys.stderr)
                    continue
                failed += 1
                print(
                    f"WARNING: approved image skipped; catalog row missing: {product_id}",
                    file=sys.stderr,
                )
                continue
            indexed = image_index.get(product_id)
            if (
                existing[0] == expected_url
                and isinstance(indexed, dict)
                and indexed.get("filename") == filename
                and webp_path.is_file()
                and indexed.get("sha256")
                == hashlib.sha256(webp_path.read_bytes()).hexdigest()
            ):
                skipped += 1
                continue
            try:
                response = rpc(
                    "get_approved_product_submission_image",
                    {"p_submission_id": submission_id},
                )
                if (
                    not isinstance(response, list)
                    or len(response) != 1
                    or not isinstance(response[0], dict)
                ):
                    raise SubmissionImportError(
                        "approval has no singular product image"
                    )
                source = response[0]
                if set(source) != {
                    "bucket_id",
                    "object_path",
                    "content_type",
                    "content_sha256",
                }:
                    raise SubmissionImportError(
                        "approved product image manifest is malformed"
                    )
                bucket_id = _required_string(
                    source["bucket_id"], "image bucket", max_length=100
                )
                object_path = _required_string(
                    source["object_path"], "image object path", max_length=500
                )
                content_type = _required_string(
                    source["content_type"], "image content type", max_length=40
                )
                expected_hash = _required_string(
                    source["content_sha256"], "image hash", max_length=64
                ).lower()
                if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
                    raise SubmissionImportError("approved product image hash is invalid")
                source_bytes = download(bucket_id, object_path)
                if hashlib.sha256(source_bytes).hexdigest() != expected_hash:
                    raise SubmissionImportError(
                        "approved product image hash does not match"
                    )
                webp_bytes = _render_catalog_webp(source_bytes, content_type)
                _atomic_write_bytes(webp_path, webp_bytes)
                webp_hash = hashlib.sha256(webp_bytes).hexdigest()
                updated = connection.execute(
                    "update products_core set image_thumbnail_url = ? "
                    "where dsld_id = ?",
                    (expected_url, product_id),
                ).rowcount
                if updated != 1:
                    raise SubmissionImportError(
                        "approved product image catalog binding failed"
                    )
                image_index[product_id] = {
                    "filename": filename,
                    "size_bytes": len(webp_bytes),
                    "sha256": webp_hash,
                }
                copied += 1
            except (OSError, sqlite3.Error, SubmissionImportError) as exc:
                failed += 1
                print(
                    f"WARNING: approved image copy failed for {product_id}: {exc}",
                    file=sys.stderr,
                )
        connection.commit()
    finally:
        connection.close()

    if copied:
        _atomic_write_text(
            index_path,
            json.dumps(image_index, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
        )
    if copied or skipped:
        _refresh_catalog_manifest_checksum(catalog_path)
    return {"copied": copied, "failed": failed, "skipped": skipped}


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
                # The locally verified released identity: the service stamps
                # it as resolved_dsld_id on the submission and cascades it to
                # duplicates, giving submitters a product to open.
                "p_resolved_dsld_id": product_id,
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
    source.add_argument("--copy-images", action="store_true")
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
    parser.add_argument(
        "--product-images-dir",
        type=Path,
        default=Path("scripts/dist/product_images"),
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
        if args.copy_images:
            result = copy_approved_product_images(
                output_dir=args.output_dir,
                catalog_db=args.catalog_db,
                product_images_dir=args.product_images_dir,
            )
            print(json.dumps(result, sort_keys=True))
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
