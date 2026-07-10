"""Semantic contract helpers for the canonical RDA/UL reference artifact.

The Flutter asset is a generated copy of ``scripts/data/rda_optimal_uls.json``.
This module fingerprints clinical semantics, not JSON bytes, so whitespace,
key order, and equivalent numeric formatting cannot mask a real UL/RDA drift.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


class ReferenceDataContractError(ValueError):
    """Raised when a reference artifact is missing or violates its contract."""


def _normalized_text(value: Any) -> str | None:
    if value is None:
        return None
    return " ".join(str(value).strip().casefold().split()) or None


def _normalized_number(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value).strip() or None
    if not decimal.is_finite():
        return str(value).strip() or None
    normalized = decimal.normalize()
    rendered = format(normalized, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def semantic_rda_ul_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return canonical clinical fields for deterministic RDA/UL comparison."""
    raw_entries = data.get("nutrient_recommendations")
    if not isinstance(raw_entries, list):
        raise ReferenceDataContractError(
            "rda_optimal_uls.json must contain a nutrient_recommendations list"
        )

    entries: list[dict[str, Any]] = []
    for raw in raw_entries:
        if not isinstance(raw, Mapping):
            raise ReferenceDataContractError("nutrient_recommendations contains a non-object row")
        raw_groups = raw.get("data")
        if not isinstance(raw_groups, list):
            raise ReferenceDataContractError(
                f"nutrient {raw.get('id')!r} is missing its demographic data list"
            )
        groups = [
            {
                "group": _normalized_text(group.get("group")),
                "age_range": _normalized_text(group.get("age_range")),
                "rda_ai": _normalized_number(
                    group.get("rda_ai", group.get("rda", group.get("ai")))
                ),
                "ul": _normalized_number(group.get("ul")),
            }
            for group in raw_groups
            if isinstance(group, Mapping)
        ]
        if len(groups) != len(raw_groups):
            raise ReferenceDataContractError(
                f"nutrient {raw.get('id')!r} has a non-object demographic row"
            )
        groups.sort(
            key=lambda group: (
                group["group"] or "",
                group["age_range"] or "",
                group["rda_ai"] or "",
                group["ul"] or "",
            )
        )
        entries.append(
            {
                "id": _normalized_text(raw.get("id")),
                "standard_name": _normalized_text(raw.get("standard_name")),
                "unit": _normalized_text(raw.get("unit")),
                "ul_status": _normalized_text(raw.get("ul_status")),
                "ul_basis": _normalized_text(raw.get("ul_basis")),
                "data": groups,
            }
        )

    entries.sort(key=lambda entry: (entry["id"] or "", entry["standard_name"] or ""))
    return {"nutrient_recommendations": entries}


def semantic_rda_ul_fingerprint(data: Mapping[str, Any]) -> str:
    """Return a stable sha256 fingerprint of clinical RDA/UL semantics."""
    payload = semantic_rda_ul_payload(data)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def reference_stamp(data: Mapping[str, Any]) -> dict[str, str]:
    """Read the declared version and compute the authoritative fingerprint."""
    metadata = data.get("_metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    contract = metadata.get("reference_data_contract")
    contract = contract if isinstance(contract, Mapping) else {}
    version = contract.get("reference_version")
    if not isinstance(version, str) or not version.strip():
        raise ReferenceDataContractError(
            "RDA/UL reference metadata is missing reference_data_contract.reference_version"
        )
    return {
        "reference_data_version": version.strip(),
        "reference_data_fingerprint": semantic_rda_ul_fingerprint(data),
    }


def validate_declared_reference_stamp(data: Mapping[str, Any]) -> dict[str, str]:
    """Validate that the stored canonical stamp represents this exact data."""
    stamp = reference_stamp(data)
    metadata = data.get("_metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    contract = metadata.get("reference_data_contract")
    contract = contract if isinstance(contract, Mapping) else {}
    declared = contract.get("semantic_fingerprint")
    if declared != stamp["reference_data_fingerprint"]:
        raise ReferenceDataContractError(
            "RDA/UL reference semantic fingerprint is stale or missing: "
            f"declared={declared!r}, computed={stamp['reference_data_fingerprint']!r}"
        )
    return stamp


def assert_emitted_reference_stamp(
    emitted: Mapping[str, Any],
    expected: Mapping[str, str],
) -> None:
    """Fail when a product's emitted UL payload is not from this reference."""
    actual = {
        "reference_data_version": emitted.get("reference_data_version"),
        "reference_data_fingerprint": emitted.get("reference_data_fingerprint"),
    }
    expected_stamp = {
        "reference_data_version": expected.get("reference_data_version"),
        "reference_data_fingerprint": expected.get("reference_data_fingerprint"),
    }
    if actual != expected_stamp:
        raise ReferenceDataContractError(
            "emitted RDA/UL reference stamp differs from canonical: "
            f"expected={expected_stamp}, actual={actual}"
        )


def assert_semantic_parity(
    canonical: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> None:
    """Fail when a generated app copy differs in clinical meaning."""
    canonical_fingerprint = semantic_rda_ul_fingerprint(canonical)
    candidate_fingerprint = semantic_rda_ul_fingerprint(candidate)
    if canonical_fingerprint != candidate_fingerprint:
        raise ReferenceDataContractError(
            "RDA/UL semantic fingerprints differ: "
            f"canonical={canonical_fingerprint}, candidate={candidate_fingerprint}"
        )
