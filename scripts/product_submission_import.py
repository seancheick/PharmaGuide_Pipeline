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
from normalization import QUANTITY_OPERATORS, parse_servings_per_container
from PIL import Image, ImageOps
from submission_review.gtin import (
    canonical_normalized_gtin14,
    is_valid_gtin as _is_valid_gtin,
)


SCHEMA_VERSION = "manual_label_v1"
RECEIPT_FILE = ".product_submission_import_receipts"
RECEIPT_SCHEMA_VERSION = 2
PROMOTED_HISTORY_DIR = ".product_submission_promoted"
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
        "ceilingDailyServings",
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
    if value.get("operator") not in QUANTITY_OPERATORS | {None, "="}:
        raise SubmissionImportError(f"{path}.operator is not a printed qualifier")
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
    for field in ("minDailyServings", "maxDailyServings", "ceilingDailyServings"):
        if value.get(field) is not None:
            _finite_number(
                value[field],
                f"{path}.{field}",
                minimum=_POSITIVE_NUMBER_MINIMUM,
            )
    directed = [value[field] for field in ("minDailyServings", "maxDailyServings")
                if value.get(field) is not None]
    if value.get("ceilingDailyServings") is not None and directed and value["ceilingDailyServings"] < max(directed):
        # A printed "not to exceed" limit below the directions is a misreading.
        raise SubmissionImportError(f"{path}.ceilingDailyServings must be >= the directed daily servings")
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
    """A positive count, as a number or the printed text ("60", "about 17")."""
    if isinstance(value, str):
        _required_string(value, "servingsPerContainer", max_length=40)
    elif isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SubmissionImportError("servingsPerContainer must be positive")
    number, _ = parse_servings_per_container(value)
    if number is None:
        raise SubmissionImportError("servingsPerContainer must be positive")
    _finite_number(number, "servingsPerContainer", minimum=_POSITIVE_NUMBER_MINIMUM)


def _validate_nutritional_info(value: object) -> None:
    """Typed Nutrition Facts: Clean owns the values; a qualifier must be known."""
    if not isinstance(value, dict):
        raise SubmissionImportError("nutritionalInfo must be an object")
    for key, entry in value.items():
        if isinstance(entry, dict) and entry.get("operator") not in QUANTITY_OPERATORS | {None, "="}:
            raise SubmissionImportError(f"nutritionalInfo.{key}.operator is not a printed qualifier")


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
    if payload.get("nutritionalInfo") is not None:
        _validate_nutritional_info(payload["nutritionalInfo"])

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


def _pipeline_other_ingredient_rows(label_text: str) -> list[dict[str, Any]]:
    """Adapt the shared cleaner's disclosure parser to the import error contract."""
    from enhanced_normalizer import parse_other_ingredient_disclosure

    try:
        return parse_other_ingredient_disclosure(label_text)
    except ValueError as error:
        raise SubmissionImportError(str(error)) from error


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


def _catalog_relation(export_row: dict[str, Any]) -> tuple[str, str] | None:
    """Which catalog record this approval decided about, and how.

    ``correction_target_dsld_id`` rewrites that record; ``edition_of_dsld_id``
    leaves it alone and stands beside it. They are different decisions with
    different consequences for anyone who already has the product, so a
    submission may carry at most one.
    """
    present = [
        (field, export_row.get(field))
        for field in ("correction_target_dsld_id", "edition_of_dsld_id")
        if export_row.get(field) is not None
    ]
    if not present:
        return None
    if len(present) > 1:
        raise SubmissionImportError(
            "a submission is either a correction or a separate edition"
        )
    field, value = present[0]
    catalog_id = _required_string(value, field, max_length=39)
    if not re.fullmatch(r"(?:[0-9]{1,30}|PG_SUB_[0-9A-F]{32})", catalog_id):
        raise SubmissionImportError(f"{field} must be a catalog id")
    return field, catalog_id


def _edition_of(export_row: dict[str, Any]) -> str | None:
    relation = _catalog_relation(export_row)
    return relation[1] if relation and relation[0] == "edition_of_dsld_id" else None


def _catalog_lineage(product_id: str) -> str:
    if product_id.startswith("PG_SUB_"):
        return f"pharmaguide_submission:{str(UUID(product_id[7:]))}"
    return f"dsld:{product_id}"


def _validate_identity_envelope(value: object, row: dict[str, Any]) -> object:
    """Validate the frozen private commitment, returning only its public label."""
    if not isinstance(value, dict) or set(value) != {"label", "identity"}:
        raise SubmissionImportError("invalid v2 envelope")
    identity = value["identity"]
    keys = {"observed", "decision", "identity_method", "outcome", "matched_dsld_id",
            "correction_target_dsld_id", "edition_of_dsld_id", "evidence_revision",
            "evidence_manifest_sha256", "match_check_id"}
    if not isinstance(identity, dict) or set(identity) != keys:
        raise SubmissionImportError("invalid v2 identity")
    method = identity["identity_method"]
    if not isinstance(method, str) or method not in {"gtin", "label_review"}:
        raise SubmissionImportError("invalid identity method")
    decision = identity["decision"]
    if not isinstance(decision, dict) or set(decision) != {"code_type", "issuer", "verified_gtin", "package", "reason"}:
        raise SubmissionImportError("invalid reviewed identifier decision")
    types = {"other", "amazon_fnsku", "amazon_asin", "manufacturer_sku", "retailer_sku", "lot", "none"}
    if not isinstance(decision["code_type"], str) or decision["code_type"] not in types:
        raise SubmissionImportError("invalid reviewed code type")
    for key, maximum in (("issuer", 200), ("package", 300), ("reason", 2000)):
        text = decision[key]
        if text is not None and (not isinstance(text, str) or len(text) > maximum or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in text)):
            raise SubmissionImportError(f"invalid decision {key}")
    if decision["issuer"] is not None and not decision["issuer"].strip():
        raise SubmissionImportError("optional decision issuer must be canonical null when empty")
    if not isinstance(decision["reason"], str) or len(decision["reason"].strip()) < 5:
        raise SubmissionImportError("v2 identity requires a substantive reviewed rationale")
    if method == "label_review" and (not decision["package"] or not decision["package"].strip() or not decision["reason"] or len(decision["reason"].strip()) < 5):
        raise SubmissionImportError("label review requires package and rationale")
    verified = decision["verified_gtin"]
    exported = row["normalized_upc"]
    if (verified is None) != (exported is None) or (verified is not None and (
        canonical_normalized_gtin14(verified) is None or
        canonical_normalized_gtin14(verified) != canonical_normalized_gtin14(exported)
    )):
        raise SubmissionImportError("verified GTIN contradicts normalized_upc")
    if method == "gtin" and verified is None:
        raise SubmissionImportError("GTIN review requires verified GTIN")
    outcomes = {"no_match_verified", "new_product_verified", "catalog_match", "dsld_match"}
    if not isinstance(identity["outcome"], str) or identity["outcome"] not in outcomes or (verified is None and identity["outcome"] == "no_match_verified"):
        raise SubmissionImportError("unresolved identity cannot import")
    revision = identity["evidence_revision"]
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise SubmissionImportError("invalid evidence revision")
    if not isinstance(identity["evidence_manifest_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", identity["evidence_manifest_sha256"]):
        raise SubmissionImportError("invalid evidence manifest")
    if isinstance(identity["match_check_id"], bool) or not isinstance(identity["match_check_id"], int) or identity["match_check_id"] < 1:
        raise SubmissionImportError("invalid match check id")
    for key in ("matched_dsld_id", "correction_target_dsld_id", "edition_of_dsld_id"):
        target = identity[key]
        if target is not None and (not isinstance(target, str) or not re.fullmatch(r"(?:[0-9]{1,30}|PG_SUB_[0-9A-F]{32})", target)):
            raise SubmissionImportError("invalid identity association")
        if key != "matched_dsld_id" and target != row.get(key):
            raise SubmissionImportError("identity association contradicts export")
    relation = _catalog_relation(row)
    relation_target = relation[1] if relation else row.get("target_dsld_id")
    outcome = identity["outcome"]
    matched = identity["matched_dsld_id"]
    # Matching a reference row is not an approval of a new product. Every
    # approved association must explicitly select its correction/edition owner;
    # otherwise a catalog match could silently manufacture a second PG_SUB.
    if outcome == "dsld_match":
        raise SubmissionImportError("DSLD match does not authorize label import")
    if outcome == "catalog_match":
        if matched is None or relation_target is None or matched != relation_target:
            raise SubmissionImportError("catalog match requires its explicit reviewed association")
    else:
        expected_method = "gtin" if outcome == "no_match_verified" else "label_review"
        if method != expected_method or matched is not None or relation_target is not None or (outcome == "new_product_verified" and verified is not None):
            raise SubmissionImportError("new product identity contradicts method or association")
    if row["kind"] == "label_mismatch" and (outcome != "catalog_match" or matched != row.get("target_dsld_id") or relation is not None):
        raise SubmissionImportError("label mismatch requires the matched correction target")
    observed = identity["observed"]
    if observed is not None:
        fields = {"observed_code", "code_type", "issuer", "brandName", "fullName", "listing_url", "no_code"}
        if not isinstance(observed, dict) or set(observed) != fields or not isinstance(observed["code_type"], str) or observed["code_type"] not in types or not isinstance(observed["no_code"], bool):
            raise SubmissionImportError("invalid observed identifier")
        for key, limit in (("observed_code", 128), ("issuer", 200), ("brandName", 300), ("fullName", 300), ("listing_url", 2048)):
            text = observed[key]
            if text is not None and (not isinstance(text, str) or len(text) > limit or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in text)):
                raise SubmissionImportError("invalid observed identifier text")
        for key in ("issuer", "listing_url"):
            if observed[key] is not None and not observed[key].strip():
                raise SubmissionImportError(f"optional observed {key} must be canonical null when empty")
        if not observed["brandName"] or not observed["brandName"].strip() or not observed["fullName"] or not observed["fullName"].strip():
            raise SubmissionImportError("identifier brand/name required")
        if observed["no_code"]:
            if observed["observed_code"] is not None or observed["code_type"] != "none":
                raise SubmissionImportError("contradictory no-code declaration")
        elif not observed["observed_code"] or observed["code_type"] == "none":
            raise SubmissionImportError("observed code required")
        if observed["listing_url"] is not None:
            parsed = urllib.parse.urlparse(observed["listing_url"])
            if parsed.scheme not in {"https", "http"} or not parsed.netloc:
                raise SubmissionImportError("invalid listing URL")
    elif method == "label_review" and verified is None:
        raise SubmissionImportError("no-GTIN review requires frozen observed identity")
    return value["label"]


def build_manual_label(export_row: object) -> dict[str, Any]:
    """Validate one service export and build its pipeline-owned label."""
    if not isinstance(export_row, dict):
        raise SubmissionImportError("approved export row must be an object")
    required_export_fields = {
        "approval_revision",
        "approved_at",
        "approved_payload_canonical",
        "kind",
        "normalized_upc",
        "payload_sha256",
        "reviewer_id",
        "schema_version",
        "submission_id",
    }
    optional_export_fields = {
        "target_dsld_id",
        "correction_target_dsld_id",
        "edition_of_dsld_id",
    }
    unknown_export_fields = (
        set(export_row) - required_export_fields - optional_export_fields
    )
    missing_export_fields = required_export_fields - set(export_row)
    if unknown_export_fields or missing_export_fields:
        raise SubmissionImportError(
            "approved export fields do not match the pinned schema"
        )

    submission_id = _required_uuid(export_row["submission_id"], "submission_id")
    approval_revision = export_row["approval_revision"]
    if (
        isinstance(approval_revision, bool)
        or not isinstance(approval_revision, int)
        or approval_revision < 1
    ):
        raise SubmissionImportError("approval_revision must be a positive integer")
    # An approval must name a real reviewer, so the id is still required and
    # validated — it just does not travel into the label. Nothing downstream
    # reads it, and the shipped catalog and this repository are public.
    _required_uuid(export_row["reviewer_id"], "reviewer_id")
    kind = _required_string(export_row["kind"], "kind", max_length=30)
    if kind not in _ALLOWED_KINDS:
        raise SubmissionImportError("kind is unsupported")
    if export_row["schema_version"] not in {SCHEMA_VERSION, "manual_label_v2"}:
        raise SubmissionImportError("schema_version is unsupported")

    raw_upc = export_row["normalized_upc"]
    if raw_upc is not None:
        upc = _required_string(raw_upc, "normalized_upc", max_length=14)
        if not _is_valid_gtin(upc):
            raise SubmissionImportError("normalized_upc is not a valid GTIN")
    else:
        if kind == "missing_product" and export_row["schema_version"] == SCHEMA_VERSION:
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
    if export_row["schema_version"] == "manual_label_v2":
        decoded_payload = _validate_identity_envelope(decoded_payload, export_row)
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
            max_length=39,
        )
        if not re.fullmatch(r"(?:[0-9]{1,30}|PG_SUB_[0-9A-F]{32})", target_id):
            raise SubmissionImportError("target_dsld_id must be numeric")
        product_id = target_id
        lineage_key = _catalog_lineage(target_id)
        if _catalog_relation(export_row) is not None:
            raise SubmissionImportError(
                "a correction cannot also carry a catalog relation"
            )
    else:
        if export_row.get("target_dsld_id") is not None:
            raise SubmissionImportError(
                "missing-product export cannot specify target_dsld_id"
            )
        relation = _catalog_relation(export_row)
        if relation is not None and relation[0] == "correction_target_dsld_id":
            # The reviewer verified that the catalog record is this label
            # transcribed wrongly, so it is rewritten in place and keeps its
            # id: anyone who already has it in a stack keeps the same product.
            product_id = relation[1]
            lineage_key = _catalog_lineage(product_id)
        else:
            product_id = "PG_SUB_" + submission_id.replace("-", "").upper()
            lineage_key = f"pharmaguide_submission:{submission_id}"

    return {
        "id": product_id,
        **pipeline_payload,
        "upcSku": upc,
        "src": f"local/manual_labels/product_submissions/{product_id}",
        "source_type": "external_manual",
        "manual_product_provenance": {
            "approval_revision": approval_revision,
            "approval_payload_sha256": payload_hash,
            "source_kind": "private_product_submission",
            "source_record_id": submission_id,
            "label_verified_at": verified_date,
            "review_status": "verified",
            "reviewer": REVIEWER_DISPLAY_NAME,
        },
        "label_record_metadata": {
            "approval_revision": approval_revision,
            "approval_payload_sha256": payload_hash,
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
            # A different formula sold under a barcode the catalog already
            # uses. The record it names is left alone — nobody's bottle
            # changes contents — and this label becomes its own product.
            **(
                {"edition_of_dsld_id": edition_of}
                if (edition_of := _edition_of(export_row))
                else {}
            ),
        },
    }


def _read_receipts(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": RECEIPT_SCHEMA_VERSION, "submissions": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SubmissionImportError("import receipt file is unreadable") from exc
    if (
        not isinstance(value, dict)
        or value.get("schema_version") not in {1, RECEIPT_SCHEMA_VERSION}
        or not isinstance(value.get("submissions"), dict)
    ):
        raise SubmissionImportError("import receipt file has an unknown schema")
    if value["schema_version"] == 1:
        for receipt in value["submissions"].values():
            if not isinstance(receipt, dict):
                continue
            receipt.setdefault("approval_revision", 1)
            receipt.setdefault(
                "promoted_approval_revision",
                1 if receipt.get("promoted_catalog_version") else 0,
            )
        value["schema_version"] = RECEIPT_SCHEMA_VERSION
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


def _freeze_promoted_label(
    destination: Path,
    submission_id: str,
    receipt: dict[str, Any],
    *,
    prior_payload: bytes | None = None,
) -> None:
    """Retain the exact promoted input before a newer approval replaces it."""
    current_revision = int(receipt.get("approval_revision") or 0)
    promoted_revision = int(
        receipt.get("promoted_approval_revision")
        or (current_revision if receipt.get("promoted_catalog_version") else 0)
    )
    if promoted_revision > 0:
        receipt["promoted_approval_revision"] = promoted_revision
    if promoted_revision <= 0 or promoted_revision != current_revision:
        return
    output_name = receipt.get("output_file")
    label_hash = receipt.get("label_sha256")
    if not isinstance(output_name, str) or Path(output_name).name != output_name:
        raise SubmissionImportError("promoted import receipt output is malformed")
    source = destination / output_name
    relative = Path(PROMOTED_HISTORY_DIR) / submission_id / f"{promoted_revision}.json"
    frozen = destination / relative
    if frozen.is_file():
        source = frozen
        label_hash = receipt.get("promoted_label_sha256") or label_hash
        prior_payload = None
    if (not source.is_file() and prior_payload is None) or not isinstance(label_hash, str):
        raise SubmissionImportError("promoted manual label is unavailable")
    payload = prior_payload if prior_payload is not None else source.read_bytes()
    if hashlib.sha256(payload).hexdigest() != label_hash:
        raise SubmissionImportError("promoted manual label changed after import")
    relative = Path(PROMOTED_HISTORY_DIR) / submission_id / f"{promoted_revision}.json"
    frozen = destination / relative
    if frozen.exists() and frozen.read_bytes() != payload:
        raise SubmissionImportError("promoted approval artifact changed")
    if not frozen.exists():
        _atomic_write_bytes(frozen, payload)
    receipt.update({
        "promoted_label_artifact": relative.as_posix(),
        "promoted_label_sha256": label_hash,
        "promoted_approval_payload_sha256": receipt.get(
            "approval_payload_sha256"
        ),
        "promoted_product_id": receipt.get("product_id"),
        "promoted_output_file": output_name,
    })


def _restore_promoted_label(
    destination: Path,
    receipt_rows: dict[str, dict[str, Any]],
    receipt: dict[str, Any],
) -> str | None:
    owner_id = str(receipt.get("fallback_promoted_submission_id") or "")
    owner = receipt_rows.get(owner_id) if owner_id else receipt
    if not isinstance(owner, dict):
        return None
    relative = owner.get("promoted_label_artifact")
    expected_hash = owner.get("promoted_label_sha256")
    output_name = receipt.get("output_file") or owner.get("promoted_output_file")
    if not isinstance(relative, str) or Path(relative).is_absolute():
        return None
    if not isinstance(output_name, str) or Path(output_name).name != output_name:
        raise SubmissionImportError("promoted restore output is malformed")
    artifact = destination / relative
    if not artifact.is_file() or not isinstance(expected_hash, str):
        raise SubmissionImportError("promoted approval artifact is unavailable")
    payload = artifact.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected_hash:
        raise SubmissionImportError("promoted approval artifact changed")
    _atomic_write_bytes(destination / output_name, payload)
    return owner_id or next(
        (key for key, value in receipt_rows.items() if value is owner), ""
    )


def materialize_approved_submissions(
    export_rows: Iterable[object],
    *,
    output_dir: str | Path,
    authoritative: bool = False,
) -> ImportResult:
    """Atomically materialize validated labels and immutable import receipts."""
    destination = Path(output_dir)
    receipt_path = destination / RECEIPT_FILE
    receipts = _read_receipts(receipt_path)
    receipt_needs_schema_write = (
        receipt_path.exists()
        and json.loads(receipt_path.read_text(encoding="utf-8")).get("schema_version") == 1
    )
    receipt_rows: dict[str, dict[str, Any]] = receipts["submissions"]
    pending_fences: dict[str, dict[str, Any]] = {}
    for submission_id, receipt in list(receipt_rows.items()):
        if not isinstance(receipt, dict) or "pending_import" not in receipt:
            continue
        pending = receipt["pending_import"]
        if (
            not isinstance(pending, dict)
            or not isinstance(pending.get("approval_revision"), int)
            or pending["approval_revision"] < 1
            or not isinstance(pending.get("output_file"), str)
            or Path(pending["output_file"]).name != pending["output_file"]
            or any(not isinstance(pending.get(key), str)
                   or not re.fullmatch(r"[0-9a-f]{64}", pending[key])
                   for key in ("label_sha256", "approval_payload_sha256"))
        ):
            raise SubmissionImportError("pending import receipt is malformed")
        pending_fences[submission_id] = pending
        previous = receipt.get("pending_previous", {
            "submission_id": submission_id,
            "label_sha256": receipt.get("label_sha256"),
        })
        if not isinstance(previous, dict):
            raise SubmissionImportError("pending previous owner is malformed")
        previous_hash = previous.get("label_sha256")
        previous_owner_id = previous.get("submission_id")
        previous_owner = receipt_rows.get(previous_owner_id) if previous_owner_id else None
        if previous_hash is not None and (
            not isinstance(previous_hash, str)
            or not re.fullmatch(r"[0-9a-f]{64}", previous_hash)
            or not isinstance(previous_owner, dict)
            or previous_owner.get("label_sha256") != previous_hash
        ):
            raise SubmissionImportError("pending previous owner changed")
        output_path = destination / pending["output_file"]
        actual_hash = (hashlib.sha256(output_path.read_bytes()).hexdigest()
                       if output_path.is_file() else None)
        if actual_hash == pending["label_sha256"]:
            # The durable intent proves which authoritative bytes replaced the
            # label, even if the server has approved another revision meanwhile.
            if isinstance(previous_owner, dict):
                _freeze_promoted_label(destination, previous_owner_id, previous_owner)
            receipt_rows[submission_id] = pending
        elif actual_hash == previous_hash:
            receipt.pop("pending_import")
            receipt.pop("pending_previous", None)
            if not receipt:
                del receipt_rows[submission_id]
        else:
            raise SubmissionImportError("manual label changed during pending import")
        receipt_needs_schema_write = True

    prepared: list[tuple[str, int, str, dict[str, Any], str, Path]] = []
    fallback_promoted_owners: dict[str, str] = {}
    seen_submission_ids: set[str] = set()
    seen_product_ids: set[str] = set()
    upc_owners: dict[str, set[tuple[str, str]]] = {}
    removed_unpromoted = False
    for submission_id, value in receipt_rows.items():
        if not isinstance(value, dict):
            continue
        gtin14 = canonical_normalized_gtin14(value.get("upc"))
        if gtin14 is not None:
            upc_owners.setdefault(gtin14, set()).add(
                (submission_id, str(value.get("product_id") or ""))
            )
    already_imported: list[str] = []

    for raw_row in export_rows:
        label = build_manual_label(raw_row)
        assert isinstance(raw_row, dict)  # Established by build_manual_label.
        submission_id = str(raw_row["submission_id"]).lower()
        approval_revision = int(raw_row["approval_revision"])
        approval_payload_sha256 = str(raw_row["payload_sha256"]).lower()
        if submission_id in seen_submission_ids:
            raise SubmissionImportError("duplicate submission_id in export")
        seen_submission_ids.add(submission_id)
        product_id = str(label["id"])
        if product_id in seen_product_ids:
            raise SubmissionImportError("duplicate product identity in export")
        seen_product_ids.add(product_id)

        upc = str(label["upcSku"])
        gtin14 = canonical_normalized_gtin14(upc)
        # A barcode names one product unless a reviewer decided otherwise.
        # The collision exists to stop the same product being imported twice
        # under two ids. An edition or a correction is a recorded decision that
        # a second record on this barcode is intended, backed by a catalog match
        # the approval gate verified, so it is not a collision.
        # An exact existing receipt is checked below. Its unchanged replay is
        # not a new competing identity when another reviewed edition arrived.
        if (gtin14 is not None and submission_id not in receipt_rows
                and _catalog_relation(raw_row) is None):
            for owner_submission_id, owner_product_id in sorted(
                upc_owners.get(gtin14, ())
            ):
                if (
                    owner_submission_id != submission_id
                    and owner_product_id != product_id
                ):
                    raise SubmissionImportError(
                        f"UPC {upc} is already owned by submission "
                        f"{owner_submission_id}"
                    )
        if gtin14 is not None:
            upc_owners.setdefault(gtin14, set()).add((submission_id, product_id))

        serialized = json.dumps(label, ensure_ascii=False, indent=2) + "\n"
        label_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        output_path = destination / f"{product_id}.json"
        pending = pending_fences.get(submission_id)
        if pending:
            if approval_revision < pending["approval_revision"]:
                raise SubmissionImportError("an older approval revision cannot replace the pending one")
            if approval_revision == pending["approval_revision"] and (
                approval_payload_sha256 != pending["approval_payload_sha256"]
                or label_hash != pending["label_sha256"]
            ):
                raise SubmissionImportError("same approval revision changed after approval")
        existing_receipt = receipt_rows.get(submission_id)
        if existing_receipt is not None:
            receipt_revision = int(existing_receipt.get("approval_revision") or 1)
            if approval_revision < receipt_revision:
                raise SubmissionImportError("an older approval revision cannot replace the current one")
            existing_hash = (
                hashlib.sha256(output_path.read_bytes()).hexdigest()
                if output_path.exists() else None
            )
            if (
                approval_revision == receipt_revision
                and existing_receipt.get("approval_payload_sha256", approval_payload_sha256)
                != approval_payload_sha256
            ):
                raise SubmissionImportError("same approval revision changed after approval")
            if existing_receipt.get("label_sha256") == label_hash and existing_hash == label_hash:
                already_imported.append(submission_id)
                continue
            # Recreate exactly the previous serializer's private-account field.
            # Only this known privacy-only transition may change an immutable
            # receipt. No normalization or clinical-field edits are accepted.
            legacy_label = {
                **label,
                "manual_product_provenance": {
                    **label["manual_product_provenance"],
                    "reviewer_record_id": _required_uuid(raw_row["reviewer_id"], "reviewer_id"),
                },
            }
            legacy_hash = hashlib.sha256(
                (json.dumps(legacy_label, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            ).hexdigest()
            pre_revision_label = json.loads(json.dumps(label))
            pre_revision_label["manual_product_provenance"].pop(
                "approval_revision", None
            )
            pre_revision_label["manual_product_provenance"].pop(
                "approval_payload_sha256", None
            )
            pre_revision_label["label_record_metadata"].pop(
                "approval_revision", None
            )
            pre_revision_label["label_record_metadata"].pop(
                "approval_payload_sha256", None
            )
            pre_revision_hash = hashlib.sha256(
                (json.dumps(pre_revision_label, ensure_ascii=False, indent=2) + "\n")
                .encode("utf-8")
            ).hexdigest()
            pre_revision_label["manual_product_provenance"][
                "reviewer_record_id"
            ] = _required_uuid(raw_row["reviewer_id"], "reviewer_id")
            pre_revision_private_hash = hashlib.sha256(
                (json.dumps(pre_revision_label, ensure_ascii=False, indent=2) + "\n")
                .encode("utf-8")
            ).hexdigest()
            if (
                approval_revision == receipt_revision
                and existing_receipt.get("label_sha256") in {
                    legacy_hash, pre_revision_hash, pre_revision_private_hash
                }
                and existing_hash in {
                    legacy_hash, pre_revision_hash, pre_revision_private_hash,
                    label_hash,
                }
                and existing_receipt.get("output_file") == output_path.name
                and existing_receipt.get("product_id") == product_id
            ):
                # The privacy-only serializer transition still replaces promoted
                # input bytes. Freeze the verified historical serializer before
                # journaling, including recovery of pre-journal interrupted work.
                previous_label = legacy_label
                if existing_receipt["label_sha256"] != legacy_hash:
                    previous_label = json.loads(json.dumps(pre_revision_label))
                    if existing_receipt["label_sha256"] == pre_revision_hash:
                        previous_label["manual_product_provenance"].pop("reviewer_record_id", None)
                prior_payload = (json.dumps(previous_label, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
                _freeze_promoted_label(destination, submission_id, existing_receipt,
                                       prior_payload=prior_payload)
                prepared.append((submission_id, approval_revision, approval_payload_sha256,
                                 label, serialized, output_path))
                continue
            if approval_revision == receipt_revision:
                displacing = [
                    row
                    for owner_id, row in receipt_rows.items()
                    if owner_id != submission_id
                    and isinstance(row, dict)
                    and row.get("label_sha256") == existing_hash
                    and row.get("fallback_promoted_submission_id")
                        == submission_id
                ]
                if authoritative and len(displacing) == 1:
                    _restore_promoted_label(
                        destination, receipt_rows, displacing[0]
                    )
                    already_imported.append(submission_id)
                    continue
                raise SubmissionImportError("same approval revision changed after approval")
            promoted_revision = int(
                existing_receipt.get("promoted_approval_revision")
                or (1 if existing_receipt.get("promoted_catalog_version") else 0)
            )
            if promoted_revision < receipt_revision and not authoritative:
                raise SubmissionImportError(
                    "refusing to replace an unpromoted approval revision"
                )
            if existing_hash not in {existing_receipt.get("label_sha256"), label_hash}:
                raise SubmissionImportError("manual label changed after import")
            _freeze_promoted_label(destination, submission_id, existing_receipt)
            if promoted_revision:
                fallback_promoted_owners[submission_id] = submission_id
            # The new bytes with the old receipt also recover a crash between
            # the two atomic replacements. Preserve promotion state below.
            prepared.append((submission_id, approval_revision, approval_payload_sha256,
                             label, serialized, output_path))
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
                exact_promoted_owners = [
                    (owner_id, owner)
                    for owner_id, owner in receipt_rows.items()
                    if isinstance(owner, dict)
                    and owner.get("product_id") == product_id
                    and owner.get("output_file") == output_path.name
                    and owner.get("label_sha256") == existing_label_hash
                    and int(
                        owner.get("promoted_approval_revision")
                        or (owner.get("approval_revision")
                            if owner.get("promoted_catalog_version") else 0)
                    )
                        == int(owner.get("approval_revision") or 0)
                    and bool(owner.get("promoted_catalog_version"))
                ]
                if len(exact_promoted_owners) != 1:
                    raise SubmissionImportError(
                        "promoted replacement owner is ambiguous"
                    )
                owner_id, owner = exact_promoted_owners[0]
                _freeze_promoted_label(destination, owner_id, owner)
                fallback_promoted_owners[submission_id] = owner_id
            # A crash can occur after the atomic label replace but before the
            # receipt replace. Exact bytes prove this is the same approval, so
            # safely recreate the receipt and refresh mtime for the pipeline.
            # A later correction may also replace the current bytes, but only
            # after the receipt owning those exact bytes was promoted.
        prepared.append((submission_id, approval_revision, approval_payload_sha256,
                         label, serialized, output_path))

    # The service export is authoritative for approvals that have never
    # shipped. A reopened approval disappears immediately; remove only the
    # unpromoted materialization. The last promoted revision remains the
    # catalog source while its correction is reviewed.
    for submission_id in sorted(
        set(receipt_rows) - seen_submission_ids if authoritative else ()
    ):
        receipt = receipt_rows[submission_id]
        if not isinstance(receipt, dict):
            continue
        output_file = receipt.get("output_file")
        label_sha256 = receipt.get("label_sha256")
        if (
            not isinstance(output_file, str)
            or Path(output_file).name != output_file
            or not output_file.endswith(".json")
            or not isinstance(label_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", label_sha256)
        ):
            raise SubmissionImportError("unpromoted import receipt is malformed")
        output_path = destination / output_file
        promoted_revision = int(
            receipt.get("promoted_approval_revision")
            or (receipt.get("approval_revision")
                if receipt.get("promoted_catalog_version") else 0)
        )
        current_revision = int(receipt.get("approval_revision") or 0)
        restored_owner = None
        if current_revision > promoted_revision:
            restored_owner = _restore_promoted_label(
                destination, receipt_rows, receipt
            )
        if restored_owner:
            if restored_owner == submission_id:
                receipt.update({
                    "approval_revision": promoted_revision,
                    "approval_payload_sha256": receipt.get(
                        "promoted_approval_payload_sha256"
                    ),
                    "label_sha256": receipt.get("promoted_label_sha256"),
                    "product_id": receipt.get("promoted_product_id"),
                    "output_file": receipt.get("promoted_output_file"),
                })
                receipt.pop("fallback_promoted_submission_id", None)
            else:
                del receipt_rows[submission_id]
            removed_unpromoted = True
            continue
        if promoted_revision > 0:
            continue
        if output_path.is_file():
            current_hash = hashlib.sha256(output_path.read_bytes()).hexdigest()
            if current_hash != label_sha256:
                raise SubmissionImportError(
                    "withdrawn unpromoted label changed after import"
                )
            output_path.unlink()
        del receipt_rows[submission_id]
        removed_unpromoted = True

    imported: list[str] = []
    output_paths: list[Path] = []
    for (submission_id, approval_revision, approval_payload_sha256,
         label, serialized, output_path) in prepared:
        label_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        candidate_receipt = {
            **receipt_rows.get(submission_id, {}),
            "label_sha256": label_hash,
            "approval_revision": approval_revision,
            "approval_payload_sha256": approval_payload_sha256,
            "promoted_approval_revision": int(
                receipt_rows.get(submission_id, {}).get("promoted_approval_revision") or 0
            ),
            "output_file": output_path.name,
            "product_id": label["id"],
            "upc": label["upcSku"],
        }
        fallback_owner = fallback_promoted_owners.get(submission_id)
        if fallback_owner:
            candidate_receipt["fallback_promoted_submission_id"] = fallback_owner
        candidate_receipt.pop("pending_import", None)
        candidate_receipt.pop("pending_previous", None)
        # Journal the complete candidate in the existing receipt owner before
        # replacing the label. The final receipt commit clears this intent.
        prior_receipt = receipt_rows.get(submission_id, {})
        previous_owner_id = submission_id if prior_receipt.get("label_sha256") else fallback_owner
        previous_owner = receipt_rows.get(previous_owner_id, {})
        receipt_rows[submission_id] = {
            **prior_receipt,
            "pending_import": candidate_receipt,
            "pending_previous": {
                "submission_id": previous_owner_id,
                "label_sha256": previous_owner.get("label_sha256"),
            },
        }
        _atomic_write_text(receipt_path, json.dumps(receipts, indent=2, sort_keys=True) + "\n")
        _atomic_write_text(output_path, serialized)
        receipt_rows[submission_id] = candidate_receipt
        imported.append(submission_id)
        output_paths.append(output_path)

    if (
        prepared
        or removed_unpromoted
        or receipt_needs_schema_write
        or not receipt_path.exists()
    ):
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
    receipt_path = Path(output_dir) / RECEIPT_FILE
    receipt_document = _read_receipts(receipt_path)
    receipts = receipt_document["submissions"]
    image_dir = Path(product_images_dir)
    index_path = image_dir / "product_image_index.json"
    image_index = _load_product_image_index(index_path)
    catalog_path = Path(catalog_db)
    if not catalog_path.is_file():
        raise SubmissionImportError("catalog database is missing")
    manifest = _load_catalog_manifest(catalog_path) or {}
    catalog_version = str(manifest.get("db_version") or "").strip()
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
            remote_path = (
                f"v{catalog_version}/{filename}" if catalog_version else filename
            )
            expected_url = f"product-images/{remote_path}"
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
                and indexed.get("remote_path") == remote_path
                and webp_path.is_file()
                and indexed.get("sha256")
                == hashlib.sha256(webp_path.read_bytes()).hexdigest()
                and receipt.get("image_approval_revision")
                == receipt.get("approval_revision")
            ):
                skipped += 1
                continue
            try:
                payload_hash = receipt.get("approval_payload_sha256")
                if payload_hash:
                    lookup: dict[str, object] = {
                        "p_submission_id": submission_id,
                        "p_approval_revision": int(receipt["approval_revision"]),
                        "p_payload_sha256": str(payload_hash),
                    }
                elif (int(receipt.get("promoted_approval_revision") or 0)
                        >= int(receipt.get("approval_revision") or 0)):
                    # Receipts written before the revision-aware importer
                    # recorded no payload hash. Their approvals are promoted
                    # and immutable on the server, which derives the exact
                    # revision and hash itself and still runs the same
                    # approval assertion before returning the image.
                    lookup = {"p_submission_id": submission_id}
                else:
                    raise SubmissionImportError(
                        f"import receipt {submission_id} has no approval payload hash"
                    )
                response = rpc("get_approved_product_submission_image", lookup)
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
                    "remote_path": remote_path,
                    "size_bytes": len(webp_bytes),
                    "sha256": webp_hash,
                }
                receipt["image_approval_revision"] = int(
                    receipt["approval_revision"]
                )
                receipt["image_source_sha256"] = expected_hash
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
        _atomic_write_text(
            receipt_path,
            json.dumps(receipt_document, indent=2, sort_keys=True) + "\n",
        )
    if copied or skipped:
        _refresh_catalog_manifest_checksum(catalog_path)
    return {"copied": copied, "failed": failed, "skipped": skipped}


def build_release_activation_approvals(
    *,
    output_dir: str | Path,
    catalog_db: str | Path,
    detail_blobs_dir: str | Path,
)-> list[dict[str, object]]:
    """Prove exact approvals and identify which ones this catalog represents.

    Product-ID presence alone is insufficient for a label correction because
    its numeric DSLD identity already existed before the correction. The core
    row's pinned detail-blob hash and the blob's submission lineage jointly
    prove that the reviewed label, rather than the prior catalog row, ships.
    Rows absent from the catalog remain exact assertions without a promotion.
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
    approvals: list[dict[str, object]] = []
    for submission_id in sorted(receipt_rows):
        receipt = receipt_rows[submission_id]
        approval_revision = int(receipt.get("approval_revision") or 0)
        if int(receipt.get("promoted_approval_revision") or 0) >= approval_revision:
            continue
        product_id = str(receipt.get("product_id") or "")
        candidate: dict[str, object] = {
            "submission_id": submission_id,
            "approval_revision": approval_revision,
            "payload_sha256": str(receipt.get("approval_payload_sha256") or ""),
        }
        if product_id not in released_products:
            approvals.append(candidate)
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
            or label_record.get("approval_revision")
            != int(receipt.get("approval_revision") or 0)
            or label_record.get("approval_payload_sha256")
            != receipt.get("approval_payload_sha256")
        ):
            raise SubmissionImportError(
                f"released product {product_id} does not carry submission "
                f"lineage {submission_id}"
            )
        candidate["resolved_dsld_id"] = product_id
        approvals.append(candidate)
    return approvals


def mark_released_submissions_promoted(
    *,
    output_dir: str | Path,
    catalog_db: str | Path,
    detail_blobs_dir: str | Path,
    rpc: Callable[[str, dict[str, object]], object] = _service_rpc,
) -> list[str]:
    """Reconcile local receipts after atomic catalog activation.

    The activation transaction has already validated every exact approval and
    stamped represented rows. This idempotent call verifies the same local
    artifact proof and records the result in the private import receipt.
    """
    destination = Path(output_dir)
    receipt_path = destination / RECEIPT_FILE
    receipts = _read_receipts(receipt_path)
    receipt_rows: dict[str, dict[str, Any]] = receipts["submissions"]
    catalog_path = Path(catalog_db)
    with sqlite3.connect(f"file:{catalog_path}?mode=ro", uri=True) as connection:
        version_row = connection.execute(
            "select value from export_manifest where key = 'db_version'"
        ).fetchone()
    if not version_row or not str(version_row[0] or "").strip():
        raise SubmissionImportError("released catalog version is unavailable")
    catalog_version = str(version_row[0]).strip()
    candidates = build_release_activation_approvals(
        output_dir=output_dir,
        catalog_db=catalog_db,
        detail_blobs_dir=detail_blobs_dir,
    )
    promoted: list[str] = []
    for candidate in candidates:
        product_id = candidate.get("resolved_dsld_id")
        if not isinstance(product_id, str):
            continue
        submission_id = str(candidate["submission_id"])
        receipt = receipt_rows[submission_id]
        response = rpc(
            "mark_product_submission_promoted",
            {
                "p_catalog_version": catalog_version,
                # The locally verified released identity: the service stamps
                # it as resolved_dsld_id on the submission and cascades it to
                # duplicates, giving submitters a product to open.
                "p_resolved_dsld_id": product_id,
                "p_submission_id": submission_id,
                "p_approval_revision": int(candidate["approval_revision"]),
                "p_payload_sha256": str(candidate["payload_sha256"]),
            },
        )
        if response is not True:
            raise SubmissionImportError(
                f"promotion RPC did not confirm {submission_id}"
            )
        receipt["promoted_catalog_version"] = catalog_version
        receipt["promoted_approval_revision"] = int(receipt["approval_revision"])
        _freeze_promoted_label(destination, submission_id, receipt)
        receipt.pop("fallback_promoted_submission_id", None)
        promoted.append(submission_id)

    if promoted:
        _atomic_write_text(
            receipt_path,
            json.dumps(receipts, indent=2, sort_keys=True) + "\n",
        )
    return promoted


def check_import_receipts(*, output_dir: str | Path) -> dict[str, int]:
    """Prove offline that every receipt can carry its label through a release.

    The copy-images and promotion steps run hours into a release. This check
    runs at preflight, reads nothing from the network, and fails on exactly the
    receipt states those steps cannot handle: a malformed row, a label file
    that drifted from its receipt, or an unpromoted approval without the exact
    payload hash the server lookups require. Promoted receipts written before
    the revision-aware importer carry no hash; they are reported, not refused,
    because the server derives their exact approval itself.
    """
    destination = Path(output_dir)
    receipts = _read_receipts(destination / RECEIPT_FILE)["submissions"]
    problems: list[str] = []
    counts = {"rows": 0, "promoted": 0, "pending": 0, "legacy_without_payload_hash": 0}
    # A correction of a promoted product rewrites the owner's file after
    # freezing the owner's exact bytes; the correction's receipt owns the file.
    file_claims = {
        (row.get("output_file"), str(row.get("product_id") or ""), row.get("label_sha256"))
        for row in receipts.values() if isinstance(row, dict)
    }

    def frozen_promoted_label_is_intact(receipt: dict[str, Any], label_sha256: str) -> bool:
        relative = receipt.get("promoted_label_artifact")
        if (not isinstance(relative, str) or Path(relative).is_absolute()
                or receipt.get("promoted_label_sha256") != label_sha256):
            return False
        artifact = destination / relative
        return artifact.is_file() and hashlib.sha256(artifact.read_bytes()).hexdigest() == label_sha256
    for submission_id, receipt in sorted(receipts.items()):
        counts["rows"] += 1
        if not isinstance(receipt, dict):
            problems.append(f"{submission_id}: receipt row is not an object")
            continue
        product_id = str(receipt.get("product_id") or "")
        if not re.fullmatch(r"[0-9]{1,30}|PG_SUB_[0-9A-F]{32}", product_id):
            problems.append(f"{submission_id}: product_id is malformed")
        try:
            approval_revision = int(receipt.get("approval_revision") or 0)
            promoted_revision = int(receipt.get("promoted_approval_revision") or 0)
        except (TypeError, ValueError):
            problems.append(f"{submission_id}: approval revisions are not integers")
            continue
        if approval_revision < 1 or promoted_revision < 0:
            problems.append(f"{submission_id}: approval revisions are out of range")
        output_file = receipt.get("output_file")
        label_sha256 = receipt.get("label_sha256")
        if (
            not isinstance(output_file, str)
            or Path(output_file).name != output_file
            or not output_file.endswith(".json")
            or not isinstance(label_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", label_sha256)
        ):
            problems.append(f"{submission_id}: output_file or label_sha256 is malformed")
        else:
            label_path = destination / output_file
            if not label_path.is_file():
                problems.append(f"{submission_id}: label file {output_file} is missing")
            elif (current_sha256 := hashlib.sha256(label_path.read_bytes()).hexdigest()) != label_sha256 and not (
                (output_file, product_id, current_sha256) in file_claims
                and frozen_promoted_label_is_intact(receipt, label_sha256)
            ):
                problems.append(f"{submission_id}: label file {output_file} changed after import")
        payload_hash = receipt.get("approval_payload_sha256")
        if payload_hash is not None and not (
            isinstance(payload_hash, str) and re.fullmatch(r"[0-9a-f]{64}", payload_hash)
        ):
            problems.append(f"{submission_id}: approval_payload_sha256 is malformed")
        if promoted_revision >= approval_revision:
            counts["promoted"] += 1
            if payload_hash is None:
                counts["legacy_without_payload_hash"] += 1
        else:
            counts["pending"] += 1
            if payload_hash is None:
                problems.append(f"{submission_id}: unpromoted approval has no approval payload hash")
    if problems:
        raise SubmissionImportError(
            "import receipts cannot carry a release: " + "; ".join(problems)
        )
    return counts


def verify_current_approval_revisions(
    *,
    output_dir: str | Path,
    rpc: Callable[[str, dict[str, object]], object] = _service_rpc,
) -> int:
    """Fence publication against approvals reopened after the pipeline run."""
    receipts = _read_receipts(Path(output_dir) / RECEIPT_FILE)["submissions"]
    checked = 0
    for submission_id, receipt in sorted(receipts.items()):
        if not isinstance(receipt, dict):
            raise SubmissionImportError("import receipt row is malformed")
        revision = int(receipt.get("approval_revision") or 0)
        promoted_revision = int(receipt.get("promoted_approval_revision") or 0)
        if promoted_revision >= revision:
            continue
        response = rpc(
            "assert_product_submission_approval_revision",
            {
                "p_submission_id": submission_id,
                "p_approval_revision": revision,
                "p_payload_sha256": str(receipt.get("approval_payload_sha256") or ""),
            },
        )
        if response is not True:
            raise SubmissionImportError(
                f"approval revision changed before release: {submission_id}"
            )
        checked += 1
    return checked


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
    source.add_argument("--verify-current-approvals", action="store_true")
    source.add_argument("--check-receipts", action="store_true")
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
        if args.check_receipts:
            counts = check_import_receipts(output_dir=args.output_dir)
            print(json.dumps(counts, sort_keys=True))
            return 0
        if args.verify_current_approvals:
            checked = verify_current_approval_revisions(output_dir=args.output_dir)
            print(json.dumps({"verified": checked}, sort_keys=True))
            return 0
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
        result = materialize_approved_submissions(
            rows, output_dir=args.output_dir, authoritative=True
        )
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
