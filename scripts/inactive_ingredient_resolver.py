"""
Unified inactive ingredient resolver.

Replaces the scattered safety + role classification logic in build_final_db.py
with a single, testable, deterministic module. For every inactive label
entry, the resolver consults three sources of truth IN PRIORITY ORDER:

  1. ``banned_recalled_ingredients.json``  (status: banned / high_risk /
     recalled / watchlist). Sourced from FDA enforcement actions, EFSA
     decisions, GSRS, and regulatory bans. THIS WAS THE GAP — previously
     consulted only by the active-ingredient path via the enricher's
     contaminant_lookup, leaving banned inactives (Titanium Dioxide × 1178
     occurrences, Talc × 311) shipping as severity_status='n/a',
     is_safety_concern=False. A clinical-grade contract violation.

  2. ``harmful_additives.json``  (severity_level: high / moderate / low).
     The penalty-scoring excipient database — already consulted by the
     old path but now flowing through a single contract.

  3. ``other_ingredients.json``  (679 excipient role classifications).
     Carrier oils, fillers, colorants, preservative-grade tocopherols,
     etc. The legitimate-excipient lookup.

Matching rules
--------------
  - Match on ``standard_name`` + ``aliases`` ONLY. Never on
    ``notes``/``mechanism_of_harm``/``safety_summary``/``reason`` text.
    The Candurin Silver entry has "titanium dioxide" in its description;
    a notes-aware match would have shadowed-banned every Candurin label.
  - Normalized exact match. No broad fuzzy.
  - banned_recalled entries with ``match_mode`` in {disabled, historical}
    are skipped — those were once-banned-now-released ingredients that
    must not produce a current safety signal.

Severity contract
-----------------
  banned_recalled.status='banned'    → severity_status='critical', is_banned=True
  banned_recalled.status='high_risk' → severity_status='critical', is_banned=False
  banned_recalled.status='recalled'  → severity_status='critical', is_banned=False
  banned_recalled.status='watchlist' → severity_status='informational', is_banned=False
  harmful_additives.severity={high,critical,moderate} → severity_status='critical'
  harmful_additives.severity='low'   → severity_status='suppress'   (transparency)
  other_ingredients (role match)     → severity_status='n/a'         (no safety concern)
  unmatched                          → severity_status='n/a', all flags False

Output
------
A single :class:`InactiveResolution` dataclass per call. The build-final-db
inactive blob builder reads it directly — no further interpretation in
build_final_db.py.

Provenance: every resolution carries ``matched_source`` (which file) and
``matched_rule_id`` (which entry). The audit script uses these to prove
that every banned ingredient in inactives produces a safety signal, and
that no match was caused by notes-text bleed-through.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

_REPO_ROOT = Path(__file__).resolve().parent
_DEFAULT_DATA_DIR = _REPO_ROOT / "data"

# Severity status enum constants (must match FINAL_EXPORT_SCHEMA_V1.md).
SEVERITY_CRITICAL = "critical"
SEVERITY_SUPPRESS = "suppress"
SEVERITY_INFORMATIONAL = "informational"
SEVERITY_NA = "n/a"

# Source name enum constants (used in matched_source).
SOURCE_BANNED_RECALLED = "banned_recalled"
SOURCE_HARMFUL_ADDITIVES = "harmful_additives"
SOURCE_OTHER_INGREDIENTS = "other_ingredients"


def _normalize(text: Any) -> str:
    """Cheap normalization for label matching. Lowercase, collapse
    whitespace, strip surrounding punctuation. Same shape the rest of
    the pipeline uses (matches build_final_db.normalize_text)."""
    if not text:
        return ""
    s = str(text).lower().strip()
    # Collapse internal whitespace
    s = " ".join(s.split())
    # Strip surrounding punctuation that won't be on a label
    return s.strip(".,;:()[]{}\"'")


def _collect_terms(*values: Any) -> list[str]:
    """Dedupe + normalize candidate terms in order of preference."""
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        n = _normalize(v)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InactiveResolution:
    """Single canonical representation for a resolved inactive ingredient.

    All fields are populated even on unmatched names so Flutter / the
    blob builder / the audit script don't have to null-check.

    Fields with default values:
      - functional_roles, population_warnings, common_uses → []
      - identifiers, notes_dict → {}
      - All Optional[str] fields → None
    """
    # Identity
    raw_name: str
    display_label: str
    standard_name: Optional[str]
    # Provenance
    matched_source: Optional[str]
    matched_rule_id: Optional[str]
    # Role
    display_role_label: Optional[str]
    functional_roles: list[str]
    additive_type: Optional[str]
    category: Optional[str]
    # Safety contract
    severity_status: str
    is_safety_concern: bool
    is_banned: bool
    safety_reason: Optional[str]
    # Harmful-additive metadata (when sourced from harmful_additives.json)
    harmful_severity: Optional[str]
    harmful_notes: Optional[str]
    mechanism_of_harm: Optional[str]
    population_warnings: list[str]
    # Other-ingredient metadata
    common_uses: list[str]
    is_additive: bool
    is_label_descriptor: bool
    is_active_only: bool
    # Misc
    notes: str
    identifiers: dict
    # Optional structured evidence (PubMed, EFSA refs) — copied through
    # from the matched entry when available.
    references: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers — build a name-index from one source file
# ---------------------------------------------------------------------------

def _entry_terms(entry: dict) -> Iterable[str]:
    """Yield normalized lookup terms for a single source entry.
    standard_name + aliases ONLY — never notes / description text."""
    sn = entry.get("standard_name")
    if sn:
        yield _normalize(sn)
    for alias in (entry.get("aliases") or []):
        if isinstance(alias, str):
            n = _normalize(alias)
            if n:
                yield n


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------

class InactiveIngredientResolver:
    """Stateless-after-init resolver. Build once, call ``resolve()`` per
    inactive ingredient encountered.

    Cost: O(total_aliases) on init, then O(1) lookup per resolve."""

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        banned_recalled_path: Optional[Path] = None,
        harmful_additives_path: Optional[Path] = None,
        other_ingredients_path: Optional[Path] = None,
    ) -> None:
        d = data_dir or _DEFAULT_DATA_DIR
        self._banned_path = banned_recalled_path or d / "banned_recalled_ingredients.json"
        self._harmful_path = harmful_additives_path or d / "harmful_additives.json"
        self._other_path = other_ingredients_path or d / "other_ingredients.json"

        self._banned_entries: list[dict] = []
        self._harmful_entries: list[dict] = []
        self._other_entries: list[dict] = []

        self._banned_index: dict[str, dict] = {}
        self._harmful_index: dict[str, dict] = {}
        self._other_index: dict[str, dict] = {}

        self._build_indices()

    # ----- Index construction -----

    def _build_indices(self) -> None:
        # banned_recalled — filter out historical/disabled match_modes
        br = _load_json(self._banned_path).get("ingredients") or []
        for e in br:
            if not isinstance(e, dict):
                continue
            mm = (e.get("match_mode") or "").strip().lower()
            if mm in {"disabled", "historical"}:
                continue
            self._banned_entries.append(e)
            for term in _entry_terms(e):
                # First-match wins; later entries don't shadow earlier ones.
                self._banned_index.setdefault(term, e)

        # harmful_additives — accept all entries
        ha = _load_json(self._harmful_path).get("harmful_additives") or []
        for e in ha:
            if not isinstance(e, dict):
                continue
            self._harmful_entries.append(e)
            for term in _entry_terms(e):
                self._harmful_index.setdefault(term, e)

        # other_ingredients — accept all entries
        oi = _load_json(self._other_path).get("other_ingredients") or []
        for e in oi:
            if not isinstance(e, dict):
                continue
            self._other_entries.append(e)
            for term in _entry_terms(e):
                self._other_index.setdefault(term, e)

    # ----- Public API -----

    def resolve(
        self,
        raw_name: str,
        standard_name: Optional[str] = None,
        additional_terms: Optional[Iterable[str]] = None,
    ) -> InactiveResolution:
        """Resolve a single inactive ingredient. Never raises, never
        returns None.

        Args:
          raw_name: the label text as it appeared on the bottle.
          standard_name: optional pipeline-resolved standard form
            (e.g. from earlier stages).
          additional_terms: optional extra match terms (aliases the
            cleaner may have surfaced).

        Returns:
          InactiveResolution — see class docstring.
        """
        terms = _collect_terms(raw_name, standard_name, *(additional_terms or []))

        # 1. banned_recalled  (highest authority)
        for t in terms:
            entry = self._banned_index.get(t)
            if entry:
                return self._from_banned(raw_name, entry)

        # 2. harmful_additives
        for t in terms:
            entry = self._harmful_index.get(t)
            if entry:
                return self._from_harmful(raw_name, entry)

        # 3. other_ingredients
        for t in terms:
            entry = self._other_index.get(t)
            if entry:
                return self._from_other(raw_name, entry)

        # 4. unmatched — well-formed unknown
        return self._unmatched(raw_name)

    # ----- Audit hooks (no internal state mutation) -----

    def iter_banned_recalled_entries_for_audit(self) -> Iterator[dict]:
        yield from self._banned_entries

    def iter_harmful_additives_entries_for_audit(self) -> Iterator[dict]:
        yield from self._harmful_entries

    def iter_other_ingredients_entries_for_audit(self) -> Iterator[dict]:
        yield from self._other_entries

    # ----- Builders for the four resolution branches -----

    @staticmethod
    def _from_banned(raw_name: str, entry: dict) -> InactiveResolution:
        status = (entry.get("status") or "").strip().lower()
        is_banned = status == "banned"
        if status == "watchlist":
            severity_status = SEVERITY_INFORMATIONAL
            is_safety_concern = False
        else:
            # banned / high_risk / recalled all surface as critical
            severity_status = SEVERITY_CRITICAL
            is_safety_concern = True
        safety_reason = (
            entry.get("safety_warning_one_liner")
            or entry.get("reason")
            or f"Listed as {status} in banned_recalled_ingredients.json"
        )
        return InactiveResolution(
            raw_name=raw_name,
            display_label=entry.get("standard_name") or raw_name,
            standard_name=entry.get("standard_name"),
            matched_source=SOURCE_BANNED_RECALLED,
            matched_rule_id=entry.get("id"),
            display_role_label=None,  # banned items don't need a role label
            functional_roles=list(entry.get("functional_roles") or []),
            additive_type=None,
            category=entry.get("source_category"),
            severity_status=severity_status,
            is_safety_concern=is_safety_concern,
            is_banned=is_banned,
            safety_reason=str(safety_reason)[:500] if safety_reason else None,
            harmful_severity=(entry.get("clinical_risk_enum") or None),
            harmful_notes=entry.get("safety_warning") or entry.get("reason"),
            mechanism_of_harm=None,
            population_warnings=list(entry.get("population_warnings") or []),
            common_uses=[],
            is_additive=False,
            is_label_descriptor=False,
            is_active_only=False,
            notes=str(entry.get("ban_context") or "")[:500],
            identifiers={
                k: entry.get(k)
                for k in ("cui", "rxcui", "gsrs", "external_ids")
                if entry.get(k) is not None
            },
            references=list(entry.get("references_structured") or []),
        )

    @staticmethod
    def _from_harmful(raw_name: str, entry: dict) -> InactiveResolution:
        sev = (entry.get("severity_level") or "").strip().lower()
        if sev in {"high", "critical", "moderate"}:
            severity_status = SEVERITY_CRITICAL
            is_safety_concern = True
        elif sev == "low":
            severity_status = SEVERITY_SUPPRESS
            is_safety_concern = False
        else:
            severity_status = SEVERITY_NA
            is_safety_concern = False
        functional_roles = list(entry.get("functional_roles") or [])
        # Derive a friendly display_role_label from the first functional role
        # (the build's existing _INACTIVE_ROLE_LABELS table now maps these).
        display_role_label = _pretty_role(functional_roles[0]) if functional_roles else None
        return InactiveResolution(
            raw_name=raw_name,
            display_label=entry.get("standard_name") or raw_name,
            standard_name=entry.get("standard_name"),
            matched_source=SOURCE_HARMFUL_ADDITIVES,
            matched_rule_id=entry.get("id"),
            display_role_label=display_role_label,
            functional_roles=functional_roles,
            additive_type=entry.get("category"),
            category=entry.get("category"),
            severity_status=severity_status,
            is_safety_concern=is_safety_concern,
            is_banned=False,
            safety_reason=entry.get("safety_summary_one_liner") or entry.get("safety_summary"),
            harmful_severity=entry.get("severity_level"),
            harmful_notes=entry.get("notes"),
            mechanism_of_harm=entry.get("mechanism_of_harm"),
            population_warnings=list(entry.get("population_warnings") or []),
            common_uses=[],
            is_additive=True,
            is_label_descriptor=False,
            is_active_only=False,
            notes=str(entry.get("notes") or "")[:500],
            identifiers={
                k: entry.get(k)
                for k in ("cui", "rxcui", "gsrs", "external_ids")
                if entry.get(k) is not None
            },
            references=list(entry.get("references_structured") or []),
        )

    @staticmethod
    def _from_other(raw_name: str, entry: dict) -> InactiveResolution:
        functional_roles = list(entry.get("functional_roles") or [])
        # Precedence: prefer the more-specific additive_type (e.g.
        # "gelatin_capsule" → "Gelatin capsule") over the generic
        # functional_roles[0] (which might be "coating"). The old build
        # path used the same precedence; preserve it so Gelatin keeps
        # rendering as "Gelatin capsule" not "Coating".
        display_role_label = _pretty_role(entry.get("additive_type"))
        if not display_role_label:
            display_role_label = _pretty_role(functional_roles[0]) if functional_roles else None
        if not display_role_label:
            display_role_label = _pretty_role(entry.get("category"))
        return InactiveResolution(
            raw_name=raw_name,
            display_label=entry.get("standard_name") or raw_name,
            standard_name=entry.get("standard_name"),
            matched_source=SOURCE_OTHER_INGREDIENTS,
            matched_rule_id=entry.get("id"),
            display_role_label=display_role_label,
            functional_roles=functional_roles,
            additive_type=entry.get("additive_type"),
            category=entry.get("category"),
            severity_status=SEVERITY_NA,
            is_safety_concern=False,
            is_banned=False,
            safety_reason=None,
            harmful_severity=None,
            harmful_notes=None,
            mechanism_of_harm=None,
            population_warnings=[],
            common_uses=list(entry.get("common_uses") or []),
            is_additive=bool(entry.get("is_additive")),
            is_label_descriptor=bool(entry.get("is_label_descriptor")),
            is_active_only=bool(entry.get("is_active_only")),
            notes=str(entry.get("notes") or "")[:500],
            identifiers={
                k: entry.get(k)
                for k in ("cui", "rxcui", "gsrs", "external_ids")
                if entry.get(k) is not None
            },
            references=[],
        )

    @staticmethod
    def _unmatched(raw_name: str) -> InactiveResolution:
        return InactiveResolution(
            raw_name=raw_name,
            display_label=raw_name,
            standard_name=None,
            matched_source=None,
            matched_rule_id=None,
            display_role_label=None,
            functional_roles=[],
            additive_type=None,
            category=None,
            severity_status=SEVERITY_NA,
            is_safety_concern=False,
            is_banned=False,
            safety_reason=None,
            harmful_severity=None,
            harmful_notes=None,
            mechanism_of_harm=None,
            population_warnings=[],
            common_uses=[],
            is_additive=False,
            is_label_descriptor=False,
            is_active_only=False,
            notes="",
            identifiers={},
            references=[],
        )


# ---------------------------------------------------------------------------
# Display-role-label prettifier (mirrors _INACTIVE_ROLE_LABELS in build_final_db)
# Kept here so the resolver is self-contained.
# ---------------------------------------------------------------------------

_ROLE_LABEL_TABLE: dict[str, str] = {
    "anti_caking_agent": "Anti-caking agent",
    "anticaking_agent": "Anti-caking agent",
    "flow_agent_anticaking": "Anti-caking / flow agent",
    "flow_agent": "Flow agent",
    "glidant": "Glidant",
    "lubricant": "Lubricant",
    "binder": "Binder",
    "disintegrant": "Disintegrant",
    "filler": "Filler",
    "diluent": "Filler / diluent",
    "capsule_shell": "Capsule shell",
    "capsule_coating": "Capsule coating",
    "coating": "Coating",
    "release_agent": "Release agent",
    "emulsifier": "Emulsifier",
    "lecithin": "Lecithin (emulsifier)",
    "humectant": "Humectant",
    "thickener": "Thickener",
    "stabilizer": "Stabilizer",
    "preservative": "Preservative",
    "preservative_antioxidant": "Preservative (antioxidant)",
    "antioxidant": "Antioxidant",
    "sweetener": "Sweetener",
    "sweetener_artificial": "Sweetener (artificial)",
    "sweetener_natural": "Sweetener (natural)",
    "sweetener_sugar_alcohol": "Sweetener (sugar alcohol)",
    "colorant": "Colorant",
    "colorant_artificial": "Colorant (artificial)",
    "colorant_natural": "Colorant (natural)",
    "color": "Color",
    "flavoring": "Flavoring",
    "flavor": "Flavor",
    "flavor_artificial": "Flavor (artificial)",
    "flavor_natural": "Flavor (natural)",
    "surfactant": "Surfactant",
    "ph_adjuster": "pH adjuster",
    "acidulant": "Acidulant",
    "carrier_oil": "Carrier oil",
    "softgel_fill": "Softgel fill",
    "oil_base": "Oil base",
}

_SENTINELS = frozenset({"(none)", "none", "unknown", ""})


def _pretty_role(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    key = token.strip().lower()
    if not key or key in _SENTINELS:
        return None
    if key in _ROLE_LABEL_TABLE:
        return _ROLE_LABEL_TABLE[key]
    # Generic snake_case → Title case for uncurated values.
    return key.replace("_", " ").capitalize()
