"""Defensible product-label provenance and formula-version contract.

This module deliberately consumes only source metadata and the canonical label
ledger. Scoring output, enrichment timestamps, filenames, and product names are
not provenance and never participate in dates, lineage, history, or formula
fingerprints.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse


_WHITESPACE_RE = re.compile(r"\s+")
_PRODUCT_STATUSES = frozenset(
    {
        "active",
        "discontinued",
        "off_market",
        "reformulated",
        "limited_availability",
        "seasonal",
        "recalled",
    }
)


def _canonical_text(value: Any, *, field: str, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise ValueError(f"label_record malformed {field}: value is missing")
        return None
    if not isinstance(value, str):
        raise ValueError(f"label_record malformed {field}: expected string")
    normalized = _WHITESPACE_RE.sub(
        " ", unicodedata.normalize("NFKC", value).strip()
    )
    if required and not normalized:
        raise ValueError(f"label_record malformed {field}: value is blank")
    return normalized or None


def _canonical_folded_components(value: Any, *, row_index: int) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(
            "label_record malformed display_ingredients"
            f"[{row_index}].folded_label_components: expected list"
        )
    components: list[dict[str, Any]] = []
    for component_index, component in enumerate(value):
        if not isinstance(component, dict):
            raise ValueError(
                "label_record malformed display_ingredients"
                f"[{row_index}].folded_label_components[{component_index}]: "
                "expected object"
            )
        prefix = (
            f"display_ingredients[{row_index}]"
            f".folded_label_components[{component_index}]"
        )
        components.append(
            {
                "label_display_name": _canonical_text(
                    component.get("label_display_name"),
                    field=f"{prefix}.label_display_name",
                    required=True,
                ),
                "label_display_form": _canonical_text(
                    component.get("label_display_form"),
                    field=f"{prefix}.label_display_form",
                ),
                "exact_dose_text": _canonical_text(
                    component.get("exact_dose_text"),
                    field=f"{prefix}.exact_dose_text",
                ),
                "parent_label": _canonical_text(
                    component.get("parent_label"),
                    field=f"{prefix}.parent_label",
                ),
            }
        )
    return components


def canonical_label_ledger(display_ingredients: Any) -> list[dict[str, Any]]:
    """Return the stable formula-identity projection of a canonical ledger."""
    if display_ingredients is None:
        return []
    if not isinstance(display_ingredients, list):
        raise ValueError("label_record malformed display_ingredients: expected list")

    canonical: list[dict[str, Any]] = []
    seen_orders: set[int] = set()
    for row_index, row in enumerate(display_ingredients):
        if not isinstance(row, dict):
            raise ValueError(
                f"label_record malformed display_ingredients[{row_index}]: expected object"
            )
        raw_order = row.get("label_order")
        if isinstance(raw_order, bool) or not isinstance(raw_order, (int, float)):
            raise ValueError(
                "label_record malformed display_ingredients"
                f"[{row_index}].label_order: expected integer"
            )
        order = int(raw_order)
        if raw_order != order or order < 0 or order in seen_orders:
            raise ValueError(
                "label_record malformed display_ingredients"
                f"[{row_index}].label_order: expected unique non-negative integer"
            )
        seen_orders.add(order)

        raw_depth = row.get("nested_depth", 0)
        if isinstance(raw_depth, bool) or not isinstance(raw_depth, (int, float)):
            raise ValueError(
                "label_record malformed display_ingredients"
                f"[{row_index}].nested_depth: expected integer"
            )
        depth = int(raw_depth)
        if raw_depth != depth or depth < 0:
            raise ValueError(
                "label_record malformed display_ingredients"
                f"[{row_index}].nested_depth: expected non-negative integer"
            )

        prefix = f"display_ingredients[{row_index}]"
        canonical.append(
            {
                "label_order": order,
                "nested_depth": depth,
                "label_display_name": _canonical_text(
                    row.get("label_display_name"),
                    field=f"{prefix}.label_display_name",
                    required=True,
                ),
                "label_display_form": _canonical_text(
                    row.get("label_display_form"),
                    field=f"{prefix}.label_display_form",
                ),
                "exact_dose_text": _canonical_text(
                    row.get("exact_dose_text"),
                    field=f"{prefix}.exact_dose_text",
                ),
                "parenthetical_dose_text": _canonical_text(
                    row.get("parenthetical_dose_text"),
                    field=f"{prefix}.parenthetical_dose_text",
                ),
                "parent_label": _canonical_text(
                    row.get("parent_label"),
                    field=f"{prefix}.parent_label",
                ),
                "source_section": _canonical_text(
                    row.get("source_section"),
                    field=f"{prefix}.source_section",
                ),
                "folded_label_components": _canonical_folded_components(
                    row.get("folded_label_components"),
                    row_index=row_index,
                ),
            }
        )

    canonical.sort(key=lambda row: row["label_order"])
    return canonical


def formula_fingerprint(display_ingredients: Any) -> str | None:
    """Hash stable label identity; return unavailable for an empty label panel."""
    canonical = canonical_label_ledger(display_ingredients)
    if not canonical:
        return None
    serialized = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _optional_scalar(value: Any, *, field: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool) or isinstance(value, (dict, list, tuple, set)):
        raise ValueError(f"label_record malformed {field}: expected scalar")
    text = str(value).strip()
    return text or None


def _resolve_value(field: str, *values: Any) -> str | None:
    present = [
        value
        for value in (_optional_scalar(value, field=field) for value in values)
        if value is not None
    ]
    if not present:
        return None
    if any(value != present[0] for value in present[1:]):
        raise ValueError(f"label_record malformed {field}: conflicting values")
    return present[0]


def _validated_date(value: Any, *, field: str) -> str | None:
    text = _optional_scalar(value, field=field)
    if text is None:
        return None
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            date.fromisoformat(text)
        else:
            datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError as exc:
        raise ValueError(f"label_record malformed {field}: expected ISO date") from exc
    return text


def _validated_url(value: Any, *, field: str) -> str | None:
    text = _optional_scalar(value, field=field)
    if text is None:
        return None
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"label_record malformed {field}: expected real http(s) URL")
    return text


def _canonical_product_status(value: Any, *, field: str) -> str | None:
    text = _canonical_text(value, field=field)
    if text is None:
        return None
    canonical = re.sub(r"[\s-]+", "_", text.casefold())
    if canonical not in _PRODUCT_STATUSES:
        raise ValueError(
            f"label_record malformed {field}: unsupported product status"
        )
    return canonical


def _history_entries(
    snapshots: Any,
    *,
    current_lineage_key: str | None,
    current_source_record_id: str | None,
) -> list[dict[str, Any]]:
    if snapshots is None:
        return []
    if not isinstance(snapshots, list):
        raise ValueError("label_record malformed label_record_snapshots: expected list")

    history: list[dict[str, Any]] = []
    seen_snapshot_ids: set[str] = set()
    for index, snapshot in enumerate(snapshots):
        if not isinstance(snapshot, dict):
            raise ValueError(
                f"label_record malformed label_record_snapshots[{index}]: expected object"
            )
        lineage_key = _optional_scalar(
            snapshot.get("lineage_key"),
            field=f"label_record_snapshots[{index}].lineage_key",
        )
        snapshot_id = _optional_scalar(
            snapshot.get("snapshot_id"),
            field=f"label_record_snapshots[{index}].snapshot_id",
        )
        if snapshot_id:
            if snapshot_id in seen_snapshot_ids:
                raise ValueError(
                    "label_record malformed label_record_snapshots: "
                    f"duplicate snapshot_id {snapshot_id!r}"
                )
            seen_snapshot_ids.add(snapshot_id)
        source_record_id = _optional_scalar(
            snapshot.get("source_record_id"),
            field=f"label_record_snapshots[{index}].source_record_id",
        )
        if (
            not current_lineage_key
            or not current_source_record_id
            or lineage_key != current_lineage_key
            or not snapshot_id
            or not source_record_id
            or source_record_id != current_source_record_id
        ):
            continue
        if "display_ingredients" not in snapshot:
            raise ValueError(
                "label_record malformed "
                f"label_record_snapshots[{index}].display_ingredients: missing"
            )
        fingerprint = formula_fingerprint(snapshot.get("display_ingredients"))
        if fingerprint is None:
            continue
        history.append(
            {
                "snapshot_id": snapshot_id,
                "source_record_id": source_record_id,
                "lineage_key": lineage_key,
                "catalog_version": _optional_scalar(
                    snapshot.get("catalog_version"),
                    field=f"label_record_snapshots[{index}].catalog_version",
                ),
                "formula_fingerprint": fingerprint,
                "source_date": _validated_date(
                    snapshot.get("source_date"),
                    field=f"label_record_snapshots[{index}].source_date",
                ),
                "source_updated_date": _validated_date(
                    snapshot.get("source_updated_date"),
                    field=f"label_record_snapshots[{index}].source_updated_date",
                ),
                "product_status": _canonical_product_status(
                    snapshot.get("product_status"),
                    field=f"label_record_snapshots[{index}].product_status",
                ),
                "label_source_url": _validated_url(
                    snapshot.get("label_source_url"),
                    field=f"label_record_snapshots[{index}].label_source_url",
                ),
            }
        )
    history.sort(
        key=lambda entry: (
            (entry["source_updated_date"] or entry["source_date"]) is None,
            entry["source_updated_date"] or entry["source_date"] or "",
            entry["source_date"] or "",
            entry["source_updated_date"] or "",
            entry["snapshot_id"],
        )
    )
    return history


def build_label_record_contract(
    enriched: dict[str, Any],
    display_ingredients: Any,
) -> dict[str, Any]:
    """Build app-facing label provenance without inventing source history."""
    metadata_value = enriched.get("label_record_metadata")
    if metadata_value is not None and not isinstance(metadata_value, dict):
        raise ValueError("label_record malformed label_record_metadata: expected object")
    metadata = metadata_value or {}
    provenance_value = enriched.get("manual_product_provenance")
    if provenance_value is not None and not isinstance(provenance_value, dict):
        raise ValueError(
            "label_record malformed manual_product_provenance: expected object"
        )
    provenance = provenance_value or {}

    source_type = _optional_scalar(enriched.get("source_type"), field="source_type")
    normalized_source_type = source_type.casefold() if source_type else None
    is_external_manual = normalized_source_type == "external_manual"
    dsld_id = _optional_scalar(enriched.get("dsld_id"), field="dsld_id")
    is_dsld_catalog_source = bool(
        dsld_id
        and dsld_id.isdigit()
        and normalized_source_type in {None, "api", "dsld", "nih_dsld", "local", "manual"}
    )
    source_record_id = _resolve_value(
        "source_record_id",
        metadata.get("source_record_id"),
        dsld_id if is_dsld_catalog_source else None,
    )
    source_name = _resolve_value(
        "source_name",
        metadata.get("source_name"),
        provenance.get("source_name"),
    )
    if source_name is None and source_record_id and is_dsld_catalog_source:
        source_name = "NIH DSLD"

    catalog_version = _resolve_value(
        "catalog_version",
        metadata.get("catalog_version"),
        enriched.get("productVersionCode"),
    )
    source_date = _validated_date(
        _resolve_value(
            "source_date",
            metadata.get("source_date"),
            enriched.get("entryDate"),
        ),
        field="source_date",
    )
    source_updated_date = _validated_date(
        _resolve_value(
            "source_updated_date",
            metadata.get("source_updated_date"),
            enriched.get("updatedDate"),
        ),
        field="source_updated_date",
    )
    product_status = _canonical_product_status(
        metadata.get("product_status"),
        field="product_status",
    )
    if product_status is None:
        off_market = enriched.get("offMarket")
        discontinued_date = _validated_date(
            enriched.get("discontinuedDate"),
            field="discontinuedDate",
        )
        if off_market is True or (
            not isinstance(off_market, bool) and off_market == 1
        ) or discontinued_date is not None:
            product_status = "discontinued"
    label_source_url = _validated_url(
        _resolve_value(
            "label_source_url",
            metadata.get("label_source_url"),
            enriched.get("label_source_url"),
            provenance.get("source_url"),
        ),
        field="label_source_url",
    )
    lineage_key = _resolve_value("lineage_key", metadata.get("lineage_key"))
    if lineage_key is None and source_record_id and is_dsld_catalog_source:
        lineage_key = f"dsld:{source_record_id}"

    fingerprint = formula_fingerprint(display_ingredients)
    formula_history = _history_entries(
        enriched.get("label_record_snapshots"),
        current_lineage_key=lineage_key,
        current_source_record_id=source_record_id,
    )
    fields = {
        "source_name": source_name,
        "source_record_id": source_record_id,
        "catalog_version": catalog_version,
        "formula_fingerprint": fingerprint,
        "source_date": source_date,
        "source_updated_date": source_updated_date,
        "product_status": product_status,
        "label_source_url": label_source_url,
        "lineage_key": lineage_key,
    }
    field_statuses = {
        field: "available" if value is not None else "unavailable"
        for field, value in fields.items()
    }
    available_count = sum(value == "available" for value in field_statuses.values())
    metadata_status = (
        "available"
        if available_count == len(field_statuses)
        else "unavailable"
        if available_count == 0
        else "partial"
    )

    return {
        **fields,
        "metadata_status": metadata_status,
        "metadata_issues": [
            f"unavailable:{field}"
            for field, status in field_statuses.items()
            if status == "unavailable"
        ],
        "field_statuses": field_statuses,
        "formula_history": formula_history,
        "history_status": "available" if formula_history else "unavailable",
    }
