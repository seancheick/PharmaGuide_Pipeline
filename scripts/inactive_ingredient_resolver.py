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
  banned_recalled.status='watchlist' → severity_status='informational', is_safety_concern=True, is_banned=False
                                        (a NON-BLOCKING safety/regulatory concern: surfaces a CAUTION-eligible
                                        signal on the live path consistent with the contaminant snapshot,
                                        drives a -5 B0 penalty, but never BLOCKS)
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

from identity.safety import (
    has_explicit_form_evidence,
    negative_match_terms_veto,
    safety_flag_from_banned_match,
    safety_flag_from_harmful_additive,
    safety_status_priority,
)
from normalization import make_normalized_key

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
SOURCE_ACTIVE_FORM = "active_nutrient_form"

# Policy tag for an inactive label term that is actually an active nutrient
# FORM already scored on the active side (Pyridoxine HCl = B6, Cyanocobalamin =
# B12, Zinc Oxide, ...). Not an excipient; excluded from the "unknown inactive
# role" metric. See scripts/audits/inactive_active_form_dedup_SCOPING.md.
POLICY_ACTIVE_FORM_DUPLICATE = "active_form_duplicate"

# Generic single words that appear as IQM form aliases but are too ambiguous to
# offer as active-form candidates on their own (an excipient could share them).
# The active-form index skips these and any term shorter than 4 chars. The real
# safeguard is still product context in build_final_db.py; resolve() never uses
# this helper index directly.
_ACTIVE_FORM_TERM_STOPLIST = frozenset({
    "oil", "powder", "extract", "blend", "complex", "concentrate", "isolate",
    "fiber", "fibre", "acid", "salt", "natural", "organic", "water", "starch",
    "gum", "wax", "gel", "juice", "syrup", "flour", "protein",
})


# Additive classes in harmful_additives.json that describe the quality of a
# nutrient being SUPPLIED rather than the safety of an excipient.
_NUTRIENT_FORM_QUALITY_CLASSES = frozenset({"nutrient_synthetic"})


def is_nutrient_form_quality_signal(additive: Any) -> bool:
    """True when a harmful-additive entry/hit is a nutrient-form quality signal.

    These are not additive-safety concerns and must not be charged against, or
    colour, an "Other ingredients" row. harmful_additives.json says so in its own
    words -- ADD_SYNTHETIC_VITAMINS.mechanism_of_harm: "quality signal for
    non-premium forms, not a safety hazard at recommended doses" -- and the
    curators already applied the principle by hand to the sibling entry
    (ADD_SYNTHETIC_B_VITAMINS: "Do not penalize nutrient identities like
    cyanocobalamin/pyridoxine by default"). Measured 2026-08-07: 63 products were
    charged 2.0 because dl-alpha-tocopherol appeared as a trace
    antioxidant/preservative, where the bioavailability-vs-natural concern does
    not apply.

    Defined in this module because it owns the additive data files and scoring
    already depends on it (scoring_v4/gate_safety.py imports from here), so the
    B1 ledger and this resolver can share one definition without a cycle.
    """
    if not isinstance(additive, dict):
        return False
    return str(additive.get("category") or "").strip().lower() in _NUTRIENT_FORM_QUALITY_CLASSES


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


def _active_identity_terms(active_ingredients: Iterable[Any]) -> set[str]:
    """Return exact identity terms from one product's active label rows."""
    terms: set[str] = set()

    def add(value: Any) -> None:
        text = str(value or "").strip()
        if not text:
            return
        normalized = _normalize(text)
        if normalized:
            terms.add(normalized)
        key = make_normalized_key(text)
        if key:
            terms.add(key)

    for ingredient in active_ingredients or []:
        if not isinstance(ingredient, dict):
            continue
        for field in (
            "canonical_id",
            "parent_key",
            "normalized_key",
            "name",
            "standardName",
            "standard_name",
            "matched_form",
            "display_form_label",
        ):
            add(ingredient.get(field))
        for form in ingredient.get("forms") or []:
            if isinstance(form, dict):
                for field in ("name", "label", "ingredientGroup"):
                    add(form.get(field))
            else:
                add(form)
        for match in ingredient.get("matched_forms") or []:
            if isinstance(match, dict):
                for field in ("form_key", "standard_name", "name"):
                    add(match.get(field))
    return terms


def active_form_duplicate_candidate(
    resolver: "InactiveIngredientResolver",
    *,
    active_ingredients: Iterable[Any],
    raw_name: str,
    additional_terms: Optional[Iterable[str]] = None,
) -> Optional[dict]:
    """Return an IQM form candidate only when this product has its parent.

    Some DSLD records repeat an active nutrient's chemical form in
    ``inactiveIngredients``. A global form match is insufficient because many
    salts and botanicals can also be genuine excipients. Product-level active
    identity is therefore required before suppressing inactive safety policy.
    """
    active_terms = _active_identity_terms(active_ingredients)
    if not active_terms:
        return None
    for candidate in resolver.active_form_candidates(
        raw_name=raw_name,
        additional_terms=additional_terms,
    ):
        candidate_terms: set[str] = set()
        for value in (
            candidate.get("parent"),
            candidate.get("standard_name"),
            *(candidate.get("parents") or []),
            *(candidate.get("identity_terms") or []),
        ):
            normalized = _normalize(value)
            if normalized:
                candidate_terms.add(normalized)
            key = make_normalized_key(str(value or ""))
            if key:
                candidate_terms.add(key)
        if candidate_terms & active_terms:
            return candidate

    # A small number of substances are prohibited as standalone additives but
    # also appear in DSLD as the source salt of a declared active nutrient.
    # That dual role must be explicitly authored in the safety source rather
    # than achieved by adding banned aliases to IQM (which creates a dangerous
    # identity/safety collision). Product context is still mandatory.
    for value in (raw_name, *(additional_terms or [])):
        entry = resolver._banned_index.get(_normalize(value))
        if not isinstance(entry, dict):
            continue
        parent = entry.get("active_nutrient_parent")
        parent_terms = {
            _normalize(parent),
            make_normalized_key(str(parent or "")),
        }
        parent_terms.discard("")
        if parent_terms & active_terms:
            return {
                "parent": parent,
                "standard_name": entry.get("standard_name"),
                "source": SOURCE_BANNED_RECALLED,
                "matched_rule_id": entry.get("id"),
            }
    return None


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
    regulatory_status: Optional[str] = None
    inactive_policy: Optional[str] = None
    # Sprint E1.1.4 / 2026-05-13 — authored Dr Pham preflight copy threaded
    # through to support build_banned_substance_detail() in the blob layer.
    # Only populated for the banned-recalled branch (and only when the source
    # entry actually carries the authored fields); None for harmful_additives,
    # other_ingredients, and unmatched. The fields mirror the source-data
    # schema in banned_recalled_ingredients.json so the bridge is exact and
    # the validator (_validate_banned_preflight_propagation) sees them
    # under the names it expects.
    safety_warning_one_liner: Optional[str] = None
    safety_warning: Optional[str] = None
    safety_flags: list[dict] = field(default_factory=list)
    # Clean-label flag layer (2026-06): EU-banned / flagged additives that should
    # INFORM + apply a small graduated penalty WITHOUT forcing a CAUTION verdict
    # (titanium dioxide as a coating, etc.). Populated from the source entry's
    # optional `clean_label` block. Distinct from the safety contract above —
    # `is_safety_concern` stays False, so the verdict never changes.
    is_clean_label_concern: bool = False
    clean_label_tier: Optional[str] = None        # "elevated" | "informational"
    clean_label_note: Optional[str] = None        # consumer-facing one-liner
    clean_label_penalty_base: Optional[float] = None
    # Step 3b: structured, clickable citation surfaced from the entry's verified
    # references (no new claims) so the consumer flag meets the clinical-citation rule.
    clean_label_eu_status: Optional[str] = None       # e.g. "banned_food_additive"
    clean_label_citation: Optional[str] = None        # e.g. "Commission Regulation (EU) 2022/63"
    clean_label_url: Optional[str] = None             # authoritative source URL


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
        ingredient_quality_map_path: Optional[Path] = None,
    ) -> None:
        d = data_dir or _DEFAULT_DATA_DIR
        self._banned_path = banned_recalled_path or d / "banned_recalled_ingredients.json"
        self._harmful_path = harmful_additives_path or d / "harmful_additives.json"
        self._other_path = other_ingredients_path or d / "other_ingredients.json"
        self._iqm_path = ingredient_quality_map_path or d / "ingredient_quality_map.json"

        self._banned_entries: list[dict] = []
        self._harmful_entries: list[dict] = []
        self._other_entries: list[dict] = []

        self._banned_index: dict[str, dict] = {}
        self._harmful_index: dict[str, dict] = {}
        self._other_index: dict[str, dict] = {}
        # Punctuation-insensitive twins of the three indexes above, keyed by the
        # pipeline's canonical ``make_normalized_key``. ``_normalize`` only strips
        # SURROUNDING punctuation, so internal "-", "#", "," and "&" survive and a
        # label escapes the safety index into a generic benign bucket -- while the
        # enricher, which already uses make_normalized_key, charges it. That is
        # the same-string/two-matchers split behind every punctuation mismatch
        # measured 2026-08-07 (dl-alpha-tocopherol vs "dl-alpha tocopherol",
        # "fd&c yellow 6 lake" vs "FD&C Yellow #6 Lake", "cellulose, powder" vs
        # "cellulose powder"). One normalizer, one identity.
        self._banned_key_index: dict[str, dict] = {}
        self._harmful_key_index: dict[str, dict] = {}
        self._other_key_index: dict[str, dict] = {}
        # term -> [{"parent": iqm_parent_key, "parents": [equivalent ids], ...}]
        # This is a lookup helper only. resolve() must not consume it directly
        # because active-form-duplicate tagging requires product context.
        self._active_form_index: dict[str, list[dict]] = {}

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
                self._banned_key_index.setdefault(make_normalized_key(term), e)

        # harmful_additives — accept all entries EXCEPT the nutrient_synthetic
        # class. This resolver only ever classifies "Other ingredients" rows, and
        # a nutrient-form quality signal says nothing about an excipient: the file
        # itself calls ADD_SYNTHETIC_VITAMINS a "quality signal for non-premium
        # forms, not a safety hazard". Admitting it here would floor 47 trace
        # antioxidant rows at dark_orange via the resolver-only safety fallback,
        # re-creating in the display exactly the category error the B1 gate in
        # generic_formulation._b1_harmful_additive_penalty_detail removes. One
        # principle, applied on both sides of the seam.
        ha = _load_json(self._harmful_path).get("harmful_additives") or []
        for e in ha:
            if not isinstance(e, dict):
                continue
            self._harmful_entries.append(e)
            if is_nutrient_form_quality_signal(e):
                continue
            for term in _entry_terms(e):
                self._harmful_index.setdefault(term, e)
                self._harmful_key_index.setdefault(make_normalized_key(term), e)

        # other_ingredients — accept all entries
        oi = _load_json(self._other_path).get("other_ingredients") or []
        for e in oi:
            if not isinstance(e, dict):
                continue
            self._other_entries.append(e)
            for term in _entry_terms(e):
                self._other_index.setdefault(term, e)
                self._other_key_index.setdefault(make_normalized_key(term), e)

        # active-form index — IQM active nutrient forms. This intentionally
        # DOES NOT participate in resolve(); product-aware build code decides
        # whether an unmatched inactive is a duplicate of the same product's
        # active panel. IQM remains the authoritative active-form dictionary.
        try:
            iqm = _load_json(self._iqm_path)
        except (OSError, ValueError):
            iqm = {}
        for parent_key, parent in iqm.items():
            if parent_key.startswith("_") or not isinstance(parent, dict):
                continue
            equivalent_parents = {parent_key}
            match_rules = parent.get("match_rules")
            if isinstance(match_rules, dict):
                mr_parent = _normalize(match_rules.get("parent_id"))
                if mr_parent:
                    equivalent_parents.add(mr_parent.replace(" ", "_"))
            for rel in parent.get("relationships") or []:
                if not isinstance(rel, dict):
                    continue
                target_id = _normalize(rel.get("target_id"))
                if target_id:
                    equivalent_parents.add(target_id.replace(" ", "_"))

            identity_terms: set[str] = set()
            for parent_id in equivalent_parents:
                identity_terms.add(parent_id)
                identity_terms.add(parent_id.replace("_", " "))
            standard_name = parent.get("standard_name") or parent_key
            identity_terms.add(_normalize(standard_name))
            for a in (parent.get("aliases") or []):
                if isinstance(a, str):
                    identity_terms.add(_normalize(a))

            meta = {
                "parent": parent_key,
                "parents": sorted(equivalent_parents),
                "standard_name": standard_name,
                "identity_terms": sorted(t for t in identity_terms if t),
            }
            terms: list[str] = [_normalize(parent_key.replace("_", " "))]
            for a in (parent.get("aliases") or []):
                if isinstance(a, str):
                    terms.append(_normalize(a))
            forms = parent.get("forms")
            if isinstance(forms, dict):
                for form_key, form in forms.items():
                    terms.append(_normalize(form_key))
                    if isinstance(form, dict):
                        for a in (form.get("aliases") or []):
                            if isinstance(a, str):
                                terms.append(_normalize(a))
            for t in terms:
                if len(t) < 4 or t in _ACTIVE_FORM_TERM_STOPLIST:
                    continue
                bucket = self._active_form_index.setdefault(t, [])
                if not any(existing.get("parent") == parent_key for existing in bucket):
                    bucket.append(meta)

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

        # 1. banned_recalled (highest authority). Evaluate every label term
        # before returning so a generic high-risk identity cannot shadow a
        # more specific banned form carried in forms[] / additional_terms.
        banned_candidates: list[tuple[dict, str]] = []
        seen_banned: set[str] = set()
        for t in terms:
            entry = self._banned_index.get(t)
            entry_id = str((entry or {}).get("id") or "")
            if entry and entry_id not in seen_banned:
                banned_candidates.append((entry, t))
                seen_banned.add(entry_id)
        for entry in self._banned_entries:
            entry_id = str(entry.get("id") or "")
            if entry_id in seen_banned or not entry.get("requires_explicit_form_evidence"):
                continue
            evidence = has_explicit_form_evidence(
                terms,
                entry.get("form_evidence_patterns") or [],
            )
            if evidence:
                banned_candidates.append((entry, evidence))
                seen_banned.add(entry_id)
        banned_candidates = [
            (entry, matched_term) for entry, matched_term in banned_candidates
            if not negative_match_terms_veto(
                [matched_term],
                (entry.get("match_rules") or {}).get("negative_match_terms", []),
            )
            and (
                not entry.get("requires_explicit_form_evidence")
                or has_explicit_form_evidence(
                    terms,
                    entry.get("form_evidence_patterns") or [],
                )
            )
        ]
        if banned_candidates:
            entry, _matched_term = min(
                banned_candidates,
                key=lambda item: safety_status_priority(item[0].get("status")),
            )
            return self._from_banned(raw_name, entry)

        # 2. harmful_additives
        for t in terms:
            entry = self._harmful_index.get(t)
            if entry:
                return self._from_harmful(raw_name, entry)

        # 2b. Same two files, punctuation-insensitive. A label that differs from
        # an authored alias only by "-", "#", "," or "&" is the same substance,
        # and the enricher already charges it as such. Safety-bearing sources are
        # retried here BEFORE other_ingredients so a punctuation variant can no
        # longer fall through into a generic benign bucket.
        for t in terms:
            key = make_normalized_key(t)
            if not key:
                continue
            entry = self._banned_key_index.get(key)
            if entry and not negative_match_terms_veto(
                [t],
                (entry.get("match_rules") or {}).get("negative_match_terms", []),
            ) and (
                not entry.get("requires_explicit_form_evidence")
                or has_explicit_form_evidence(
                    terms,
                    entry.get("form_evidence_patterns") or [],
                )
            ):
                return self._from_banned(raw_name, entry)
            entry = self._harmful_key_index.get(key)
            if entry:
                return self._from_harmful(raw_name, entry)

        # Some DSLD rows join multiple independently authored additives with
        # a slash (for example ``BHA/BHT``). Resolve that narrow structural
        # shape only when *every* component is an exact safety-database term;
        # partial matches such as ``BHA/cellulose`` remain unmatched. This is
        # deliberately not a general token splitter or fuzzy fallback.
        composite = self._resolve_safety_composite(raw_name, terms)
        if composite is not None:
            return composite

        # 3. other_ingredients
        for t in terms:
            entry = self._other_index.get(t)
            if entry:
                return self._from_other(raw_name, entry)

        # 3b. other_ingredients, punctuation-insensitive.
        for t in terms:
            key = make_normalized_key(t)
            if not key:
                continue
            entry = self._other_key_index.get(key)
            if entry:
                return self._from_other(raw_name, entry)

        # 4. unmatched — well-formed unknown
        return self._unmatched(raw_name)

    def _resolve_safety_composite(
        self,
        raw_name: str,
        terms: Iterable[str],
    ) -> Optional[InactiveResolution]:
        """Resolve slash-joined exact safety terms to the strongest finding."""
        for term in terms:
            if "/" not in term:
                continue
            parts = [_normalize(part) for part in term.split("/")]
            if len(parts) < 2 or any(not part for part in parts):
                continue

            candidates: list[InactiveResolution] = []
            for part in parts:
                banned = self._banned_index.get(part)
                harmful = self._harmful_index.get(part)
                if banned is not None:
                    candidates.append(self._from_banned(raw_name, banned))
                elif harmful is not None:
                    candidates.append(self._from_harmful(raw_name, harmful))
                else:
                    candidates = []
                    break

            if not candidates:
                continue

            severity_rank = {
                SEVERITY_NA: 0,
                SEVERITY_SUPPRESS: 1,
                SEVERITY_INFORMATIONAL: 2,
                SEVERITY_CRITICAL: 3,
            }
            return max(
                candidates,
                key=lambda item: (
                    severity_rank.get(item.severity_status, 0),
                    bool(item.is_banned),
                    item.matched_source == SOURCE_BANNED_RECALLED,
                ),
            )

        return None

    def active_form_candidates(
        self,
        raw_name: str,
        standard_name: Optional[str] = None,
        additional_terms: Optional[Iterable[str]] = None,
    ) -> list[dict]:
        """Return IQM active-form candidates for a label term.

        This is deliberately separate from ``resolve()``. A global IQM hit is
        not enough to classify an inactive row as an active-form duplicate;
        the build layer must also prove the same product has the matching
        active parent.
        """
        terms = _collect_terms(raw_name, standard_name, *(additional_terms or []))
        seen: set[str] = set()
        out: list[dict] = []
        for t in terms:
            for meta in self._active_form_index.get(t, []):
                parent = str(meta.get("parent") or "")
                if parent and parent not in seen:
                    seen.add(parent)
                    out.append(meta)
        return out

    def active_form_duplicate_resolution(self, raw_name: str, meta: dict) -> InactiveResolution:
        return self._from_active_form(raw_name, meta)

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
            # A NON-BLOCKING safety/regulatory concern (FDA enforcement watch /
            # EFSA flag). is_safety_concern=True so the LIVE resolver path surfaces
            # it CONSISTENTLY with the contaminant snapshot path (both already drive
            # CAUTION + a -5 B0 penalty); is_banned=False — it never hard-BLOCKs.
            # Verified 0 verdict change: every live watchlist hit in the corpus was
            # already CAUTION via the snapshot path, so this only aligns the contract
            # (was is_safety_concern=False — the resolver mislabeled a real concern
            # as 'informational only', a clinical-grade contract violation).
            severity_status = SEVERITY_INFORMATIONAL
            is_safety_concern = True
        else:
            # banned / high_risk / recalled all surface as critical
            severity_status = SEVERITY_CRITICAL
            is_safety_concern = True
        safety_reason = (
            entry.get("safety_warning_one_liner")
            or entry.get("reason")
            or f"Listed as {status} in banned_recalled_ingredients.json"
        )
        # Clean-label flag block (inform + small graduated penalty, no CAUTION).
        clean_label = entry.get("clean_label")
        clean_label = clean_label if isinstance(clean_label, dict) else {}
        functional_roles = list(entry.get("functional_roles") or [])
        display_role_label = (
            _pretty_role(functional_roles[0]) if functional_roles else None
        )
        if not display_role_label:
            display_role_label = _pretty_role(entry.get("source_category"))
        if not display_role_label and status:
            display_role_label = _pretty_role(status)
        return InactiveResolution(
            raw_name=raw_name,
            display_label=entry.get("standard_name") or raw_name,
            standard_name=entry.get("standard_name"),
            matched_source=SOURCE_BANNED_RECALLED,
            matched_rule_id=entry.get("id"),
            display_role_label=display_role_label,
            functional_roles=functional_roles,
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
            # Sprint E1.1.4 / 2026-05-13 — thread Dr Pham authored copy
            # straight through. Only meaningful for status='banned' (where
            # build_banned_substance_detail() requires both fields non-empty).
            # We populate for ALL banned_recalled branches so consumers
            # downstream can render the preflight copy on high_risk /
            # recalled too if they want — they're authored regardless.
            safety_warning_one_liner=(entry.get("safety_warning_one_liner") or None),
            safety_warning=(entry.get("safety_warning") or None),
            safety_flags=[
                safety_flag_from_banned_match(
                    entry,
                    match_type="exact",
                    matched_variant=raw_name,
                    evidence_text=raw_name,
                ).to_dict()
            ],
            identifiers={
                k: entry.get(k)
                for k in ("cui", "rxcui", "gsrs", "external_ids")
                if entry.get(k) is not None
            },
            references=list(entry.get("references_structured") or []),
            regulatory_status=status or None,
            inactive_policy=entry.get("inactive_policy") or None,
            is_clean_label_concern=bool(clean_label),
            clean_label_tier=(clean_label.get("tier") or None),
            clean_label_note=(clean_label.get("consumer_note") or None),
            clean_label_penalty_base=clean_label.get("penalty_base"),
            clean_label_eu_status=(clean_label.get("eu_status") or None),
            clean_label_citation=(clean_label.get("regulation_citation") or None),
            clean_label_url=(clean_label.get("regulation_url") or None),
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
        if not display_role_label:
            display_role_label = _pretty_role(entry.get("category"))
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
            safety_flags=[
                safety_flag_from_harmful_additive(
                    entry,
                    match_type="exact",
                    matched_variant=raw_name,
                    evidence_text=raw_name,
                ).to_dict()
            ],
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
    def _from_active_form(raw_name: str, meta: dict) -> InactiveResolution:
        """An active nutrient FORM duplicated into the inactive list. It is
        already scored as an active; we only tag it so the audit stops counting
        it as an unknown inactive role. NOT an excipient — no functional role,
        no safety contract, never a verdict input."""
        return InactiveResolution(
            raw_name=raw_name,
            display_label=raw_name,
            standard_name=meta.get("standard_name"),
            matched_source=SOURCE_ACTIVE_FORM,
            matched_rule_id=meta.get("parent"),
            display_role_label="Active ingredient (listed as form)",
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
            is_active_only=True,
            notes="",
            identifiers={},
            references=[],
            inactive_policy=POLICY_ACTIVE_FORM_DUPLICATE,
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
