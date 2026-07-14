from __future__ import annotations

from dataclasses import asdict, dataclass, field
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


def safety_jurisdiction_projection(
    entry: Dict[str, Any], market_code: str = "US"
) -> Dict[str, Any]:
    """Project one safety rule into market applicability plus advisories.

    Legacy rules without structured jurisdictions retain their historic US
    applicability. Once jurisdictions are declared, only matching country or
    subdivision codes may drive the market verdict; all others remain visible
    as regional advisories.
    """
    jurisdictions = [
        dict(item)
        for item in (entry.get("jurisdictions") or [])
        if isinstance(item, dict)
    ]
    market = str(market_code or "US").upper().strip()

    def _applies(item: Dict[str, Any]) -> bool:
        code = str(item.get("jurisdiction_code") or "").upper().strip()
        return code == market or code.startswith(f"{market}-")

    applicable = [item for item in jurisdictions if _applies(item)]
    regional = [item for item in jurisdictions if not _applies(item)]
    return {
        "jurisdictions": jurisdictions,
        "us_applicable": bool(applicable) if jurisdictions else True,
        "regional_advisories": regional,
    }


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


# --------------------------------------------------------------------------- #
# SafetySignal v1 — the canonical safety contract between enrichment and
# scoring. This is the ONLY place that knows raw matcher implementation names
# (exact / alias / token_bounded / fuzzy / ...). Scorers consume the stable
# `match_resolution` enum and NEVER branch on raw match_type. Adding a new
# matcher method only touches this module, not any scorer.
#
#   match_resolution semantics:
#     confirmed     high-trust identity match (exact / alias / explicit form).
#                   Eligible for hard verdicts (BLOCKED / UNSAFE) and CAUTION.
#     likely        resolved medium-trust match (token_bounded / legacy with a
#                   populated entry_id). Eligible for CAUTION; a likely BANNED/
#                   RECALLED hit becomes CAUTION+review, never a hard block —
#                   a false hard-block is worse than a false caution.
#     review_only   weak / fuzzy / unresolved hit. No verdict; routes to the
#                   safety review queue.
#     low_confidence numeric confidence below the likely floor. Audit flag only.
# --------------------------------------------------------------------------- #

_CONFIRMED_MATCH_TYPES = frozenset({"exact", "alias", "explicit_form_evidence"})
_LIKELY_MATCH_TYPES = frozenset({"token_bounded", "legacy_projection"})

# Resolution strength ordering. When two raw shapes resolve to the same
# (entry_id, status, role) the STRONGEST resolution wins — a confirmed
# safety_flag must never be suppressed by a likely substance processed
# earlier. confirmed > likely > review_only > low_confidence.
_RESOLUTION_STRENGTH = {
    "confirmed": 3,
    "likely": 2,
    "review_only": 1,
    "low_confidence": 0,
}


def resolution_strength(resolution: Any) -> int:
    return _RESOLUTION_STRENGTH.get(str(resolution or "").strip().lower(), -1)

# Numeric-confidence fallback thresholds when match_type is unknown/absent.
_CONFIDENCE_CONFIRMED_FLOOR = 0.85
_CONFIDENCE_LIKELY_FLOOR = 0.5


@dataclass(frozen=True)
class SafetySignal:
    """Normalized safety signal consumed by v3/v4 safety gates.

    Stable contract: scorers branch on `match_resolution` + `status` only.
    """
    entry_id: str
    source_db: str
    status: str            # banned / recalled / high_risk / watchlist / caution / ""
    severity: str
    subject_role: str      # active / inactive / unknown
    match_resolution: str  # confirmed / likely / review_only / low_confidence
    match_confidence: Optional[float]
    policy_eligible: bool   # match_resolution in {confirmed, likely}
    review_required: bool   # match_resolution == review_only
    inactive_policy: str    # e.g. "excipient_acceptable" / ""
    evidence_text: str
    us_applicable: bool = True
    jurisdictions: List[Dict[str, Any]] = field(default_factory=list)
    regional_advisories: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _coerce_confidence(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        txt = value.strip().lower()
        named = {"high": 0.95, "medium": 0.7, "low": 0.4}
        if txt in named:
            return named[txt]
        try:
            return float(txt)
        except ValueError:
            return None
    return None


def match_resolution_for(
    match_type: Any,
    entry_id: Any,
    confidence: Any = None,
) -> str:
    """Map a raw matcher result to the stable match_resolution enum.

    This is the single chokepoint for matcher-internal knowledge. Rules:
      - exact / alias / explicit_form_evidence            -> confirmed
      - token_bounded / legacy_projection WITH entry_id   -> likely
      - token_bounded / legacy_projection WITHOUT entry_id -> review_only
      - else: fall back to numeric confidence bands, then review_only
    """
    mt = _normalize_safety_enum(match_type)
    has_id = bool(str(entry_id or "").strip())
    if mt in _CONFIRMED_MATCH_TYPES:
        return "confirmed"
    if mt in _LIKELY_MATCH_TYPES:
        return "likely" if has_id else "review_only"
    conf = _coerce_confidence(confidence)
    if conf is not None:
        if conf >= _CONFIDENCE_CONFIRMED_FLOOR:
            return "confirmed"
        if conf >= _CONFIDENCE_LIKELY_FLOOR:
            return "likely" if has_id else "review_only"
        return "low_confidence"
    return "review_only"


def build_safety_signal(
    *,
    entry_id: Any,
    source_db: Any,
    status: Any,
    match_type: Any = None,
    confidence: Any = None,
    severity: Any = None,
    subject_role: Any = "unknown",
    inactive_policy: Any = "",
    evidence_text: Any = "",
    us_applicable: Any = True,
    jurisdictions: Any = None,
    regional_advisories: Any = None,
) -> SafetySignal:
    status_norm = _normalize_safety_enum(status)
    resolution = match_resolution_for(match_type, entry_id, confidence)
    return SafetySignal(
        entry_id=str(entry_id or ""),
        source_db=normalize_safety_source(source_db),
        status=status_norm,
        severity=safety_severity_for_status(status_norm, severity),
        subject_role=_normalize_safety_enum(subject_role) or "unknown",
        match_resolution=resolution,
        match_confidence=_coerce_confidence(confidence),
        policy_eligible=resolution in ("confirmed", "likely"),
        review_required=resolution == "review_only",
        inactive_policy=_normalize_safety_enum(inactive_policy),
        evidence_text=str(evidence_text or ""),
        us_applicable=us_applicable is not False,
        jurisdictions=[dict(v) for v in (jurisdictions or []) if isinstance(v, dict)],
        regional_advisories=[
            dict(v) for v in (regional_advisories or []) if isinstance(v, dict)
        ],
    )


def normalize_safety_signals(
    product: Dict[str, Any],
    *,
    resolver_hits: Optional[List[Dict[str, Any]]] = None,
) -> List[SafetySignal]:
    """Convert every legacy safety shape on an enriched product into the
    canonical SafetySignal[] contract. This is the ONE normalizer; scorers
    consume its output and never touch raw match_type.

    Sources consumed (deduped by (entry_id|evidence, status, role)):
      1. contaminant_data.banned_substances.substances
      2. contaminant_data.banned_substances.safety_flags + per-substance
         safety_flag sub-dicts (banned_recalled source only)
      3. resolver_hits (active+inactive banned_recalled hits) — passed in by
         the caller to keep the heavy InactiveIngredientResolver dependency
         out of this kernel module
      4. top-level has_banned_substance / has_recalled_ingredient booleans
         (defense-in-depth for older blob shapes)
    """
    product = product if isinstance(product, dict) else {}
    signals: List[SafetySignal] = []
    seen: Dict[tuple, int] = {}  # dedup key -> index into signals

    def _dedup_key(sig: SafetySignal) -> tuple:
        return (sig.entry_id or sig.evidence_text, sig.status, sig.subject_role)

    def _add(sig: SafetySignal) -> None:
        key = _dedup_key(sig)
        idx = seen.get(key)
        if idx is None:
            seen[key] = len(signals)
            signals.append(sig)
            return
        # Duplicate (entry_id, status, role): keep the STRONGEST resolution so a
        # confirmed signal is never suppressed by an earlier likely one.
        if resolution_strength(sig.match_resolution) > resolution_strength(signals[idx].match_resolution):
            signals[idx] = sig

    cd = product.get("contaminant_data")
    bs = cd.get("banned_substances") if isinstance(cd, dict) else None
    bs = bs if isinstance(bs, dict) else {}

    # 1. substances
    for s in bs.get("substances") or []:
        if not isinstance(s, dict):
            continue
        _add(build_safety_signal(
            entry_id=s.get("banned_id") or s.get("entry_id") or s.get("id"),
            source_db=s.get("source_db") or s.get("matched_source") or "banned_recalled_ingredients",
            status=s.get("status") or s.get("recall_status"),
            match_type=s.get("match_type") or s.get("match_method"),
            confidence=s.get("confidence"),
            severity=s.get("severity_level") or s.get("severity"),
            subject_role=s.get("source_section") or s.get("role") or "active",
            evidence_text=(s.get("banned_name") or s.get("ingredient") or s.get("name") or ""),
            us_applicable=s.get("us_applicable", True),
            jurisdictions=s.get("jurisdictions"),
            regional_advisories=s.get("regional_advisories"),
        ))

    # 2. safety_flags (top-level + per-substance), banned_recalled source only
    flags = [f for f in (bs.get("safety_flags") or []) if isinstance(f, dict)]
    for s in bs.get("substances") or []:
        if isinstance(s, dict) and isinstance(s.get("safety_flag"), dict):
            flags.append(s["safety_flag"])
    for f in flags:
        if normalize_safety_source(f.get("source_db") or f.get("matched_source")) != "banned_recalled_ingredients":
            continue
        _add(build_safety_signal(
            entry_id=f.get("entry_id") or f.get("matched_variant"),
            source_db="banned_recalled_ingredients",
            status=f.get("status"),
            match_type=f.get("match_type"),
            confidence=f.get("confidence"),
            severity=f.get("severity"),
            subject_role=f.get("subject_role") or "active",
            evidence_text=(f.get("matched_variant") or f.get("evidence_text") or f.get("entry_id") or ""),
            us_applicable=f.get("us_applicable", True),
            jurisdictions=f.get("jurisdictions"),
            regional_advisories=f.get("regional_advisories"),
        ))

    # 3. resolver hits (already canonical-resolved → treat as confirmed)
    for hit in resolver_hits or []:
        if not isinstance(hit, dict):
            continue
        _add(build_safety_signal(
            entry_id=hit.get("matched_rule_id") or hit.get("name"),
            source_db="banned_recalled_ingredients",
            status=hit.get("status"),
            match_type="alias",  # resolver hits are canonical matches → confirmed
            severity=hit.get("severity"),
            subject_role=hit.get("role") or "unknown",
            inactive_policy=hit.get("inactive_policy") or "",
            evidence_text=hit.get("name") or "",
        ))

    # 4. top-level booleans (defense in depth; confirmed by construction)
    if product.get("has_banned_substance"):
        _add(build_safety_signal(
            entry_id="", source_db="banned_recalled_ingredients", status="banned",
            match_type="exact", evidence_text="has_banned_substance_flag",
        ))
    if product.get("has_recalled_ingredient"):
        _add(build_safety_signal(
            entry_id="", source_db="banned_recalled_ingredients", status="recalled",
            match_type="exact", evidence_text="has_recalled_ingredient_flag",
        ))

    return signals


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


def safety_flag_from_harmful_additive(
    entry: Dict[str, Any],
    *,
    match_type: str,
    matched_variant: Any,
    evidence_text: Any,
    confidence: Any = None,
) -> SafetyFlag:
    normalized_match_type = _normalize_safety_enum(match_type) or "exact"
    additive_severity = _normalize_safety_enum(entry.get("severity_level") or entry.get("severity"))
    if additive_severity in {"critical", "high"}:
        status = "high_risk"
        severity = additive_severity
    elif additive_severity == "moderate":
        status = "caution"
        severity = "moderate"
    elif additive_severity == "low":
        status = "watchlist"
        severity = "low"
    else:
        status = "caution"
        severity = additive_severity or "moderate"
    confidence_text = (
        str(confidence).strip().lower()
        if isinstance(confidence, str) and confidence.strip()
        else _MATCH_CONFIDENCE.get(normalized_match_type, "medium")
    )
    return SafetyFlag(
        entry_id=str(entry.get("id") or entry.get("rule_id") or ""),
        source_db="harmful_additives",
        status=status,
        severity=severity,
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
