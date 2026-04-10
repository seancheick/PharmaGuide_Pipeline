from __future__ import annotations

from typing import Any


ALLOWED_DOMAINS = {
    "clinical_refresh",
    "iqm_gap_scan",
    "harmful_refresh",
    "recall_refresh",
}

ALLOWED_SIGNAL_TYPES = {
    "possible_upgrade",
    "possible_contradiction",
    "missing_evidence",
    "possible_safety_change",
    "possible_recall_change",
    "low_confidence_noise",
}


def _safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def normalize_signal_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    normalized["domain"] = str(normalized.get("domain") or "").strip()
    normalized["entity_name"] = str(normalized.get("entity_name") or "").strip()
    normalized["signal_type"] = str(normalized.get("signal_type") or "").strip()
    normalized["candidate_sources"] = _safe_list(normalized.get("candidate_sources"))
    normalized["candidate_references"] = _safe_list(normalized.get("candidate_references"))
    normalized["supporting_summary"] = str(normalized.get("supporting_summary") or "")
    normalized["requires_human_review"] = True
    normalized["auto_apply_allowed"] = False

    if normalized["domain"] not in ALLOWED_DOMAINS:
        raise ValueError(f"Unsupported domain: {normalized['domain']}")
    if normalized["signal_type"] not in ALLOWED_SIGNAL_TYPES:
        raise ValueError(f"Unsupported signal_type: {normalized['signal_type']}")
    if not normalized["entity_name"]:
        raise ValueError("entity_name is required")

    return normalized
