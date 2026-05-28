from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Dict, Iterable, List, Optional

from .resolve import IdentityResult


@dataclass(frozen=True)
class SafetyFlag:
    entry_id: str
    source_db: str
    status: str
    severity: str
    match_type: str
    matched_variant: str
    evidence_text: str
    confidence: str

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


_SAFETY_PUNCT_TRANSLATION = str.maketrans({
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
})


def safety_normalize_text(text: Any) -> str:
    """Normalize safety evidence without erasing form/dose qualifiers.

    The identity normalizer intentionally broadens terms for recall and
    canonical-name lookup. Safety matching needs the opposite bias: keep
    valence, dose, form, and regulatory qualifiers visible so a qualified
    hazard cannot collapse into a generic nutrient identity.
    """
    if text is None:
        return ""
    normalized = str(text).lower().translate(_SAFETY_PUNCT_TRANSLATION)
    normalized = re.sub(r"[\u00ae\u2122\u00a9]", " ", normalized)
    normalized = re.sub(r"[^a-z0-9()+/\\-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _normalize_safety_enum(value: Any) -> str:
    normalized = "" if value is None else str(value).strip().lower()
    normalized = normalized.translate(_SAFETY_PUNCT_TRANSLATION)
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


def has_explicit_form_evidence(texts: Iterable[Any], patterns: Iterable[str]) -> Optional[str]:
    for text in texts:
        raw = "" if text is None else str(text)
        if not raw.strip():
            continue
        for pattern in patterns or []:
            if re.search(pattern, raw, flags=re.IGNORECASE):
                return raw
    return None


_STATUS_SEVERITY = {
    "banned": "critical",
    "recalled": "critical",
    "high_risk": "high",
    "caution": "moderate",
    "watchlist": "low",
}

SAFETY_STATUS_PRIORITY = {
    "banned": 0,
    "recalled": 1,
    "high_risk": 2,
    "caution": 3,
    "watchlist": 4,
}

_MATCH_CONFIDENCE = {
    "exact": "high",
    "alias": "high",
    "explicit_form_evidence": "high",
    "token_bounded": "medium",
    "legacy_projection": "medium",
}


def safety_status_priority(status: Any) -> int:
    return SAFETY_STATUS_PRIORITY.get(_normalize_safety_enum(status), 99)


def top_safety_flag(flags: Iterable[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    valid = [flag for flag in flags or [] if isinstance(flag, dict)]
    if not valid:
        return None
    return sorted(valid, key=lambda f: safety_status_priority(f.get("status")))[0]


def safety_flag_matches_status(flag: Dict[str, Any], statuses: Iterable[str]) -> bool:
    wanted = {_normalize_safety_enum(status) for status in statuses}
    return _normalize_safety_enum(flag.get("status")) in wanted


def normalize_safety_source(source: Any) -> str:
    normalized = _normalize_safety_enum(source)
    if normalized == "banned_recalled":
        return "banned_recalled_ingredients"
    return normalized


def safety_severity_for_status(status: Any, fallback: Any = None) -> str:
    normalized_status = _normalize_safety_enum(status)
    return _STATUS_SEVERITY.get(normalized_status) or _normalize_safety_enum(fallback) or "moderate"


def safety_flag_from_banned_match(
    entry: Dict[str, Any],
    *,
    match_type: str,
    matched_variant: Any,
    evidence_text: Any,
    confidence: Any = None,
) -> SafetyFlag:
    normalized_match_type = _normalize_safety_enum(match_type) or "exact"
    status = _normalize_safety_enum(entry.get("status") or entry.get("recall_status"))
    confidence_text = (
        str(confidence).strip().lower()
        if isinstance(confidence, str) and confidence.strip()
        else _MATCH_CONFIDENCE.get(normalized_match_type, "medium")
    )
    return SafetyFlag(
        entry_id=str(entry.get("id") or entry.get("rule_id") or ""),
        source_db="banned_recalled_ingredients",
        status=status,
        severity=safety_severity_for_status(status, entry.get("severity_level") or entry.get("severity")),
        match_type=normalized_match_type,
        matched_variant=str(matched_variant or entry.get("standard_name") or ""),
        evidence_text=str(evidence_text or matched_variant or ""),
        confidence=confidence_text,
    )


def build_safety_exact_index(entries: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Build a strict safety lookup that preserves qualified variants.

    Values are lists because multiple safety rules can intentionally share a
    label variant. This index is for candidate discovery only; evidence gates
    and negative-match policy still run in the classifier/caller.
    """
    index: Dict[str, List[Dict[str, Any]]] = {}
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        variants = [entry.get("standard_name")] + list(entry.get("aliases") or [])
        for variant in variants:
            key = safety_normalize_text(variant)
            if not key:
                continue
            index.setdefault(key, []).append(entry)
    return index


def classify_safety(
    identity: IdentityResult,
    raw_source_text: Optional[str],
    name: Optional[str],
    forms: List[Dict[str, Any]],
    label_text: Optional[str],
    ingredient_role: Optional[str],
    *,
    banned_recalled_entries: Optional[List[Dict[str, Any]]] = None,
) -> List[SafetyFlag]:
    """Classify safety without mutating identity fields.

    This first implementation supports explicit-form evidence rules used by
    banned/recalled entries. Legacy build paths still project older safety
    fields, but this gives them a canonical flag shape to converge on.
    """
    del ingredient_role  # Reserved for source-specific policy refinements.

    evidence_texts: List[Any] = [raw_source_text, name]
    for form in forms or []:
        if isinstance(form, dict):
            evidence_texts.extend([form.get("name"), form.get("prefix")])
        elif form:
            evidence_texts.append(form)
    evidence_texts.append(label_text)

    flags: List[SafetyFlag] = []
    identity_norm = safety_normalize_text(identity.canonical_name)
    evidence_norms = [safety_normalize_text(v) for v in evidence_texts if safety_normalize_text(v)]

    for entry in banned_recalled_entries or []:
        if not isinstance(entry, dict):
            continue
        status = _normalize_safety_enum(entry.get("status"))
        if not status:
            continue

        patterns = entry.get("form_evidence_patterns") or []
        if entry.get("requires_explicit_form_evidence"):
            evidence = has_explicit_form_evidence(evidence_texts, patterns)
            if not evidence:
                continue
            matched_variant = evidence
            match_type = "explicit_form_evidence"
        else:
            variants = [entry.get("standard_name")] + list(entry.get("aliases") or [])
            matched_variant = ""
            for variant in variants:
                variant_norm = safety_normalize_text(variant)
                if not variant_norm:
                    continue
                if variant_norm == identity_norm or variant_norm in evidence_norms:
                    matched_variant = str(variant)
                    break
            if not matched_variant:
                continue
            match_type = "exact"

        flags.append(safety_flag_from_banned_match(
            entry,
            match_type=match_type,
            matched_variant=matched_variant,
            evidence_text=matched_variant,
        ))

    return flags
