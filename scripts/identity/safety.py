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
        status = str(entry.get("status") or "").strip().lower()
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

        flags.append(SafetyFlag(
            entry_id=str(entry.get("id") or entry.get("rule_id") or ""),
            source_db="banned_recalled_ingredients",
            status=status,
            severity=_STATUS_SEVERITY.get(status, str(entry.get("severity") or "moderate")),
            match_type=match_type,
            matched_variant=matched_variant,
            evidence_text=matched_variant,
            confidence="high" if match_type == "explicit_form_evidence" else "medium",
        ))

    return flags
