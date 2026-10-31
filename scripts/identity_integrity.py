"""Pure label-first ingredient identity and display-fidelity contract."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from identity.interaction import BOTANICAL_INTERACTION_TWIN, INTERACTION_SUBJECT_FAMILY
from normalization import strip_label_identity_qualifiers
from probiotic_measurements import is_probiotic_source_header as _is_structural_blend_header


IdentityDisposition = Literal[
    "clean",
    "repaired",
    "taxonomy_only",
    "identity_conflict",
    "missing_display_label",
]
EvidenceKind = Literal["source_name", "structured_identity", "source_form"]
CandidateResolver = Callable[[str], str | None]
CanonicalParentPredicate = Callable[[str, str], bool]

IDENTITY_DISPOSITIONS: tuple[IdentityDisposition, ...] = (
    "clean",
    "repaired",
    "taxonomy_only",
    "identity_conflict",
    "missing_display_label",
)
_SCOREABLE_DISPOSITIONS = frozenset({"clean", "repaired", "taxonomy_only"})
# The catch-all proprietary-blend owner names no specific identity of its own.
_GENERAL_BLEND_ID = "BLEND_GENERAL"
# Cleaner matches made from one declared form rather than the row's own name.
_FORM_DERIVED_MATCH_METHODS = frozenset({
    "unii_form_exact_match", "single_declared_marker_form", "single_declared_nutrient_form",
})
NON_SCORABLE_NO_IDENTITY_RATIONALE = (
    "The row was intentionally classified as non-scorable; no canonical "
    "identity was inferred from raw label or form text."
)
NON_SCORING_IDENTITY_RATIONALE = (
    "The row was intentionally classified as non-scorable; the cleaner's standard "
    "name proves its identity, which is retained for interactions only and never "
    "owns Evidence or Dose."
)


def safety_only_conflict_paths(rows: Iterable[Mapping[str, Any]]) -> set[str]:
    """Identify intact label rows whose only unresolved identity is safety-only.

    This does not make a row scoreable. Export/release may contain this finding
    only when the product actually ships a BLOCKED/UNSAFE warning and no score.
    Paths must be nonempty and unique so one row cannot excuse another.
    """
    rows = [row for row in rows if isinstance(row, Mapping)]
    paths = Counter(
        row["raw_source_path"] for row in rows
        if isinstance(row.get("raw_source_path"), str)
    )
    return {
        row["raw_source_path"] for row in rows
        if isinstance(row.get("raw_source_path"), str)
        and row["raw_source_path"].strip()
        and paths[row["raw_source_path"]] == 1
        and row.get("identity_disposition") == "identity_conflict"
        and row.get("identity_decision_reason") == "safety_recognition_without_primary_identity"
        and row.get("recognition_source") in {"banned_recalled_ingredients", "harmful_additives"}
        and isinstance(row.get("safety_identity_id"), str)
        and row["safety_identity_id"].strip()
        and row.get("scoreable_identity") is False
        and not row.get("canonical_id")
        and not row.get("canonical_id_before")
        and not row.get("canonical_id_after")
        and isinstance(row.get("source_label_name"), str)
        and row["source_label_name"].strip()
        and row.get("label_display_name") == normalize_label_display(row["source_label_name"])
    }


_PARENTHESIZED_MARKER_RE = re.compile(r"\((?:tm|r|sm)\)", re.IGNORECASE)
_PARENTHESIZED_IDENTITY_RE = re.compile(r"^(.+?)\s*\(([^()]*)\)\s*$")
_LITERAL_PARENTHESIZED_IDENTITY_RE = re.compile(
    r"^(.+?)\s*[\(（]([^()（）]*)[\)）]\s*$"
)
_FORM_IDENTITY_PREFIX_RE = re.compile(r"^(?:as|from)\s+", re.IGNORECASE)
_MICROBIAL_SOURCE_RE = re.compile(
    r"\b(?:yeast|bacteria|saccharomyces|lactobacillus|bifidobacterium|"
    r"streptococcus|bacillus|limosilactobacillus|lacticaseibacillus|"
    r"lactiplantibacillus|lactococcus|s\.\s*(?:cerevisiae|boulardii)|"
    r"l\.\s*(?:acidophilus|reuteri|rhamnosus|plantarum|casei|salivarius)|"
    r"b\.\s*(?:lactis|longum|bifidum|breve|infantis|animalis|coagulans|subtilis))\b",
    re.IGNORECASE,
)
_MICROBIAL_PREPARATION_RE = re.compile(
    r"\b(?:extracts?|(?:hydro)?lysates?|fermentates?|fractions?|cell[-\s]+wall(?:s)?|"
    r"(?:heat[-\s]+(?:killed|inactivated|treated)|inactivated|non[-\s]*viable|"
    r"tyndalli[sz]ed)(?:\s+(?:cells?|cultures?))?|postbiotics?)\b",
    re.IGNORECASE,
)
_MICROBIAL_COMPONENT_RE = re.compile(
    r"\b(?:cell[-\s]+wall(?:s)?|(?:beta|β)[-\s\d,./]+(?:beta[-\s\d,./]+)?"
    r"glucans?|manno[-\s]*oligosaccharides?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class CanonicalIdentityRegistry:
    preferred_index: Mapping[str, tuple[str, str]]
    normalized_preferred_index: Mapping[str, tuple[str, str]]
    verified_preferred_index: Mapping[str, tuple[str, str]]
    candidates_index: Mapping[str, tuple[str, ...]]
    canonical_redirects: Mapping[tuple[str, str], tuple[str, str]]
    standard_names: Mapping[tuple[str, str], str]
    source_form_aliases: Mapping[tuple[str, str], frozenset[str]]
    negative_match_terms: Mapping[str, tuple[Any, ...]] = field(default_factory=dict)
    verified_uniis: Mapping[str, frozenset[str]] = field(default_factory=dict)

    @staticmethod
    def _key(value: Any) -> str:
        return normalize_label_display(value).casefold()

    def resolve_preferred(self, value: Any) -> tuple[str, str] | None:
        return self.normalized_preferred_index.get(self._key(value))

    def resolve_unambiguous(self, value: Any) -> str | None:
        candidates = self.candidates_index.get(self._key(value), ())
        return candidates[0] if len(candidates) == 1 else None

    def resolve_verified_preferred(self, value: Any) -> tuple[str, str] | None:
        return self.verified_preferred_index.get(self._key(value))

    def literal_identity_matches(self, value: Any, canonical_id: str) -> bool:
        """Curated literal ownership, without preparation-stripping derivatives."""
        literal = self.resolve_preferred(value)
        if literal is None:
            literal = self.resolve_preferred(strip_label_identity_qualifiers(str(value or "")))
        return literal is not None and literal[0] == canonical_id

    def names_identity(self, value: Any, canonical_id: str) -> bool:
        """A curated name of this identity in any owned registry, even one it
        shares with related records ("Hordeum vulgare" is barley grass, its
        powder and its juice)."""
        return canonical_id in self.candidates_index.get(self._key(value), ())

    def preparation_identity_matches(
        self, value: Any, canonical_id: str, source_db: str,
    ) -> bool:
        """Require the declared preparation, never a stripped oil or constituent form.

        Whole-material form promotion belongs to the existing structured
        complete-source-form owner, which retains quantity and composition.
        Flattened form names cannot establish the identity of the full row.
        """
        standard = self.standard_names.get((source_db, canonical_id), "")
        if source_db != "other_ingredients" or not re.search(r"\bextract\b", standard, re.I):
            return True
        # Recognition may retain an authored non-scoring preparation beside
        # a higher-priority IQM primary owner. Both are literal source owners;
        # preferred-index priority is not proof that the preparation is absent.
        return any(self.names_identity(label, canonical_id)
                   for label in (value, strip_label_identity_qualifiers(str(value or ""))))

    def standard_names_of(self, canonical_id: str) -> tuple[str, ...]:
        return tuple(name for (_, cid), name in self.standard_names.items() if cid == canonical_id)

    def is_role_record(self, canonical_id: str) -> bool:
        """Held only by a role/catch-all registry (other ingredients, proprietary blends)."""
        registries = {db for db, cid in self.standard_names if cid == canonical_id}
        return bool(registries) and registries <= {"other_ingredients", "proprietary_blends"}

    def canonicalize(
        self,
        canonical_id: str,
        source_db: str,
    ) -> tuple[str, str]:
        seen: set[tuple[str, str]] = set()
        current = (source_db, canonical_id)
        while current in self.canonical_redirects:
            if current in seen:
                raise ValueError(f"cyclic canonical redirect at {current!r}")
            seen.add(current)
            current = self.canonical_redirects[current]
        return current[1], current[0]


def build_canonical_identity_registry(
    databases: Mapping[str, Any],
) -> CanonicalIdentityRegistry:
    """Build the shared cleaner/enricher identity index from owned registries."""
    literal_ranked: dict[str, list[tuple[tuple[int, int], str, str]]] = {}
    normalized_ranked: dict[str, list[tuple[tuple[int, int], str, str]]] = {}
    candidates: dict[str, set[str]] = {}
    standard_names: dict[tuple[str, str], str] = {}
    source_form_aliases: dict[tuple[str, str], set[str]] = {}
    negative_match_terms: dict[str, tuple[Any, ...]] = {}
    verified_uniis: dict[str, set[str]] = {}

    def record_unii(canonical_id: str, entry: Mapping[str, Any]) -> None:
        external_ids = entry.get("external_ids")
        unii = external_ids.get("unii") if isinstance(external_ids, Mapping) else None
        if isinstance(unii, str) and unii.strip():
            verified_uniis.setdefault(str(canonical_id), set()).add(unii.strip().upper())
    source_priority = {
        "ingredient_quality_map": 0,
        "standardized_botanicals": 1,
        "botanical_ingredients": 2,
        "other_ingredients": 3,
        "proprietary_blends": 4,
    }
    quality_map = databases.get("ingredient_quality_map")
    canonical_redirects = _validated_equivalence_redirects(databases)
    if isinstance(quality_map, Mapping):
        for canonical_id, entry in quality_map.items():
            if str(canonical_id).startswith("_") or not isinstance(entry, Mapping):
                continue
            record_unii(str(canonical_id), entry)
            match_rules = entry.get("match_rules")
            target_id = (
                match_rules.get("target_id")
                if isinstance(match_rules, Mapping)
                else None
            )
            if isinstance(target_id, str) and target_id in quality_map:
                key = ("ingredient_quality_map", str(canonical_id))
                target = ("ingredient_quality_map", target_id)
                existing = canonical_redirects.get(key)
                if existing is not None and existing != target:
                    raise ValueError(
                        f"conflicting canonical redirect for {key!r}: "
                        f"{existing!r} vs {target!r}"
                    )
                canonical_redirects[key] = target

    def canonical_owner(canonical_id: str, source_db: str) -> tuple[str, str]:
        seen: set[tuple[str, str]] = set()
        current = (source_db, canonical_id)
        while current in canonical_redirects:
            if current in seen:
                raise ValueError(f"cyclic canonical equivalence at {current!r}")
            seen.add(current)
            target_db, target_id = canonical_redirects[current]
            current = (target_db, target_id)
        return current[1], current[0]

    def put(
        value: Any,
        canonical_id: Any,
        source_db: str,
        target_priority: int,
    ) -> None:
        literal_key = str(value or "").lower().strip()
        key = CanonicalIdentityRegistry._key(value)
        canonical = str(canonical_id or "").strip()
        if not literal_key or not key or not canonical:
            return
        owner = canonical_owner(canonical, source_db)
        if target_priority == 0 and owner == (canonical, source_db):
            standard_names[(source_db, canonical)] = str(value)
        canonical, source_db = owner
        rank = (source_priority[source_db], target_priority)
        candidates.setdefault(key, set()).add(canonical)
        literal_ranked.setdefault(literal_key, []).append(
            (rank, canonical, source_db)
        )
        normalized_ranked.setdefault(key, []).append(
            (rank, canonical, source_db)
        )

    def preferred(
        ranked: Mapping[str, list[tuple[tuple[int, int], str, str]]],
    ) -> dict[str, tuple[str, str]]:
        resolved: dict[str, tuple[str, str]] = {}
        for key, rows in ranked.items():
            best_rank = min(row[0] for row in rows)
            best = {
                (canonical, source_db)
                for rank, canonical, source_db in rows
                if rank == best_rank
            }
            if len(best) == 1:
                resolved[key] = next(iter(best))
        return resolved

    if isinstance(quality_map, Mapping):
        for canonical_id, entry in quality_map.items():
            if str(canonical_id).startswith("_") or not isinstance(entry, Mapping):
                continue
            match_rules = entry.get("match_rules")
            if isinstance(match_rules, Mapping) and match_rules.get(
                "deprecated_in_favor_of"
            ):
                continue
            if isinstance(match_rules, Mapping) and match_rules.get("negative_match_terms"):
                canonical, _ = canonical_owner(str(canonical_id), "ingredient_quality_map")
                negative_match_terms[canonical] = tuple(match_rules["negative_match_terms"])
            put(
                entry.get("standard_name") or canonical_id,
                canonical_id,
                "ingredient_quality_map",
                0,
            )
            for alias in entry.get("aliases") or ():
                put(alias, canonical_id, "ingredient_quality_map", 1)
            forms = entry.get("forms")
            if isinstance(forms, Mapping):
                for form_name, form in forms.items():
                    if (
                        isinstance(form, Mapping)
                        and form.get("alias_identity_scope")
                        == "source_preparation"
                    ):
                        # A branded/source preparation may be useful to the
                        # formulation matcher without being the chemical
                        # identity of the declared dose.  The source registry
                        # owns primary identity for these labels.
                        continue
                    if isinstance(form, Mapping) and form.get("alias_identity_scope") == "same_identity":
                        # Keep reviewed source clues local to the literal
                        # preparation; they must never become global aliases.
                        aliases = {CanonicalIdentityRegistry._key(value)
                                   for value in form.get("source_form_aliases") or ()
                                   if str(value or "").strip()}
                        canonical, _ = canonical_owner(str(canonical_id), "ingredient_quality_map")
                        for label in (form_name, *(form.get("aliases") or ())):
                            source_form_aliases.setdefault(
                                (canonical, CanonicalIdentityRegistry._key(label)), set()
                            ).update(aliases)
                    put(form_name, canonical_id, "ingredient_quality_map", 2)
                    if isinstance(form, Mapping):
                        for alias in form.get("aliases") or ():
                            put(alias, canonical_id, "ingredient_quality_map", 3)

    source_specs = (
        ("standardized_botanicals", "standardized_botanicals", "aliases"),
        ("botanical_ingredients", "botanical_ingredients", "aliases"),
        ("other_ingredients", "other_ingredients", "aliases"),
        ("proprietary_blends", "proprietary_blend_concerns", "blend_terms"),
    )
    for source_db, collection_key, alias_key in source_specs:
        database = databases.get(source_db)
        rows = database.get(collection_key) if isinstance(database, Mapping) else None
        if not isinstance(rows, (list, tuple)):
            continue
        for entry in rows:
            if not isinstance(entry, Mapping):
                continue
            standard_name = str(entry.get("standard_name") or "").strip()
            canonical_id = entry.get("id") or standard_name.lower().replace(" ", "_")
            record_unii(str(canonical_id), entry)
            put(standard_name, canonical_id, source_db, 0)
            for alias in entry.get(alias_key) or ():
                put(alias, canonical_id, source_db, 1)

    literal_preferred = preferred(literal_ranked)
    normalized_preferred = preferred(normalized_ranked)
    verified_preferred = {
        key: selected
        for key, selected in normalized_preferred.items()
        if all(
            canonical == selected[0] or source_db == selected[1]
            for _, canonical, source_db in normalized_ranked[key]
        )
    }

    return CanonicalIdentityRegistry(
        preferred_index=literal_preferred,
        normalized_preferred_index=normalized_preferred,
        verified_preferred_index=verified_preferred,
        candidates_index={
            key: tuple(sorted(values)) for key, values in candidates.items()
        },
        canonical_redirects=dict(canonical_redirects),
        standard_names=standard_names,
        source_form_aliases={key: frozenset(values) for key, values in source_form_aliases.items()},
        negative_match_terms=negative_match_terms,
        verified_uniis={key: frozenset(values) for key, values in verified_uniis.items()},
    )


def _validated_equivalence_redirects(
    databases: Mapping[str, Any],
) -> dict[tuple[str, str], tuple[str, str]]:
    """Validate and return reviewed exact-identity redirects.

    Equivalence data is intentionally stricter than parent/form relationships:
    only an explicit ``exact_equivalent`` record may collapse two registry IDs.
    """
    document = databases.get("canonical_equivalences")
    if not isinstance(document, Mapping):
        return {}
    rows = document.get("equivalences")
    if not isinstance(rows, list):
        raise ValueError("canonical_equivalences.equivalences must be a list")

    collections = canonical_registry_collections(databases)

    redirects: dict[tuple[str, str], tuple[str, str]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("canonical equivalence rows must be objects")
        if row.get("relation") != "exact_equivalent":
            raise ValueError(
                "canonical equivalence relation must be exact_equivalent"
            )
        if not isinstance(row.get("basis"), str) or not row["basis"].strip():
            raise ValueError("canonical equivalence rows require a review basis")
        if row.get("scope") != "all_identity_contexts":
            raise ValueError(
                "canonical equivalence rows must declare scope=all_identity_contexts"
            )
        source_db = str(row.get("source_db") or "")
        source_id = str(row.get("source_id") or "")
        target_db = str(row.get("target_db") or "")
        target_id = str(row.get("target_id") or "")
        if not source_db or not source_id or not target_db or not target_id:
            raise ValueError("canonical equivalence rows require source/target IDs")
        if (source_db, source_id) == (target_db, target_id):
            raise ValueError("canonical equivalence rows cannot be self-equivalences")
        if source_id not in collections.get(source_db, set()):
            raise ValueError(f"unknown source_id {source_id!r}")
        if target_id not in collections.get(target_db, set()):
            raise ValueError(f"unknown target_id {target_id!r}")
        key = (source_db, source_id)
        target = (target_db, target_id)
        existing = redirects.get(key)
        if existing is not None and existing != target:
            raise ValueError(f"conflicting canonical equivalence for {key!r}")
        redirects[key] = target

    for start in redirects:
        current = start
        seen: set[tuple[str, str]] = set()
        while current in redirects:
            if current in seen:
                raise ValueError(f"cyclic canonical equivalence at {current!r}")
            seen.add(current)
            current = redirects[current]
    return redirects


def canonical_registry_collections(
    databases: Mapping[str, Any],
) -> dict[str, set[str]]:
    collections: dict[str, set[str]] = {}
    quality_map = databases.get("ingredient_quality_map")
    if isinstance(quality_map, Mapping):
        collections["ingredient_quality_map"] = {
            str(key)
            for key, value in quality_map.items()
            if not str(key).startswith("_") and isinstance(value, Mapping)
        }
    for source_db, collection_key in (
        ("standardized_botanicals", "standardized_botanicals"),
        ("botanical_ingredients", "botanical_ingredients"),
        ("other_ingredients", "other_ingredients"),
        ("proprietary_blends", "proprietary_blend_concerns"),
    ):
        database = databases.get(source_db)
        values = database.get(collection_key) if isinstance(database, Mapping) else None
        collections[source_db] = {
            str(row.get("id"))
            for row in values or ()
            if isinstance(row, Mapping) and row.get("id")
        }
    return collections


def validated_canonical_parent_relationships(
    databases: Mapping[str, Any],
) -> set[tuple[str, str]]:
    """Return reviewed broad-to-specific identity relationships."""
    document = databases.get("canonical_equivalences")
    if not isinstance(document, Mapping):
        return set()
    rows = document.get("relationships", [])
    if not isinstance(rows, list):
        raise ValueError("canonical_equivalences.relationships must be a list")

    collections = canonical_registry_collections(databases)
    relationships: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("canonical relationship rows must be objects")
        if row.get("relation") != "broader_than":
            raise ValueError("canonical relationship must be broader_than")
        if not isinstance(row.get("basis"), str) or not row["basis"].strip():
            raise ValueError("canonical relationship rows require a review basis")
        if row.get("scope") != "specificity_resolution_only":
            raise ValueError(
                "canonical relationship rows must declare "
                "scope=specificity_resolution_only"
            )
        parent_db = str(row.get("parent_db") or "")
        parent_id = str(row.get("parent_id") or "")
        child_db = str(row.get("child_db") or "")
        child_id = str(row.get("child_id") or "")
        if parent_id not in collections.get(parent_db, set()):
            raise ValueError(f"unknown parent_id {parent_id!r}")
        if child_id not in collections.get(child_db, set()):
            raise ValueError(f"unknown child_id {child_id!r}")
        if parent_id == child_id:
            raise ValueError("canonical relationship cannot be self-referential")
        relationships.add((parent_id, child_id))

    for parent, child in relationships:
        pending = [child]
        seen: set[str] = set()
        while pending:
            current = pending.pop()
            if current == parent:
                raise ValueError(f"cyclic canonical relationship at {parent!r}")
            if current in seen:
                continue
            seen.add(current)
            pending.extend(
                descendant
                for ancestor, descendant in relationships
                if ancestor == current
            )
    return relationships


@dataclass(frozen=True, slots=True)
class LabelEvidence:
    field: str
    value: str
    kind: EvidenceKind


@dataclass(frozen=True, slots=True)
class IdentityDecision:
    disposition: IdentityDisposition
    source_label_name: str | None
    source_label_form: str | None
    label_display_name: str | None
    label_display_form: str | None
    canonical_id_before: str | None
    canonical_id: str | None
    evidence: tuple[LabelEvidence, ...]
    scoreable_identity: bool
    rationale: str

    @property
    def canonical_id_after(self) -> str | None:
        return self.canonical_id


def normalize_label_display(value: Any) -> str:
    """Apply the approved reversible display cleanup in its required order."""
    if value is None:
        return ""
    text = str(value)
    for glyph in ("™", "®", "℠"):
        text = text.replace(glyph, "")
    text = unicodedata.normalize("NFKC", text)
    text = _PARENTHESIZED_MARKER_RE.sub("", text)
    return " ".join(text.split()).strip()


def _text_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        if value.strip():
            yield value.strip()
        return
    if isinstance(value, Mapping):
        for key in ("name", "label", "value", "text", "ingredientGroup"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                yield candidate.strip()
                return
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _text_values(item)


def _form_values(value: Any) -> Iterable[str]:
    values = value if isinstance(value, (list, tuple)) else (value,)
    for item in values:
        if isinstance(item, Mapping):
            prefix = next(_text_values(item.get("prefix")), "")
            name = next(_text_values(item.get("name")), "")
            combined = " ".join(part for part in (prefix, name) if part).strip()
            if combined:
                yield combined
        else:
            yield from _text_values(item)


def _structured_group_values(row: Mapping[str, Any], value: Any) -> Iterable[str]:
    """DSLD group text that can name this line's identity.

    A blend group ("Proprietary Blend") classifies a container. On a row the
    cleaner did not keep as a structural blend header it names no substance,
    so it cannot replace the row's identity (269286 "Prosterol" saw palmetto
    filed under Proprietary Blend).
    """
    for text in _text_values(value):
        if "blend" in text.casefold() and not _is_structural_blend_header(row):
            continue
        yield text


def extract_label_evidence(row: Mapping[str, Any]) -> tuple[LabelEvidence, ...]:
    """Extract auditable evidence from ingredient-line fields only."""
    evidence: list[LabelEvidence] = []

    for field in (
        "raw_source_text",
        "raw_name",
        "source_name",
        "ingredientName",
        "name",
    ):
        for value in _text_values(row.get(field)):
            evidence.append(LabelEvidence(field, value, "source_name"))

    for value in _structured_group_values(row, row.get("ingredientGroup")):
        evidence.append(
            LabelEvidence("ingredientGroup", value, "structured_identity")
        )

    raw_taxonomy = row.get("raw_taxonomy")
    if isinstance(raw_taxonomy, Mapping):
        for value in _structured_group_values(row, raw_taxonomy.get("ingredientGroup")):
            evidence.append(
                LabelEvidence(
                    "raw_taxonomy.ingredientGroup",
                    value,
                    "structured_identity",
                )
            )

    for value in _text_values(row.get("label_nutrient_context")):
        evidence.append(
            LabelEvidence("label_nutrient_context", value, "structured_identity")
        )

    alternate_names = row.get("alternateNames")
    if isinstance(alternate_names, (list, tuple)):
        for index, item in enumerate(alternate_names):
            for value in _text_values(item):
                evidence.append(
                    LabelEvidence(
                        f"alternateNames[{index}]",
                        value,
                        "structured_identity",
                    )
                )
    else:
        for value in _text_values(alternate_names):
            evidence.append(
                LabelEvidence("alternateNames", value, "structured_identity")
            )

    for field in ("forms", "form", "raw_form", "source_label_form"):
        for index, value in enumerate(_form_values(row.get(field))):
            evidence_field = field
            if isinstance(row.get(field), (list, tuple)):
                evidence_field = f"{field}[{index}]"
            evidence.append(LabelEvidence(evidence_field, value, "source_form"))

    if (
        not any(item.kind == "source_form" for item in evidence)
        and isinstance(raw_taxonomy, Mapping)
    ):
        raw_forms = raw_taxonomy.get("forms")
        for index, value in enumerate(_form_values(raw_forms)):
            evidence_field = "raw_taxonomy.forms"
            if isinstance(raw_forms, (list, tuple)):
                evidence_field += f"[{index}]"
            evidence.append(LabelEvidence(evidence_field, value, "source_form"))

    return tuple(evidence)


def has_nonlive_microbial_derivative_evidence(row: Mapping[str, Any]) -> bool:
    """Recognize a row-owned preparation, never infer a replacement identity.

    Literal source names and their own forms can contradict organism taxonomy.
    Mass units, product prose, sibling rows and other ingredients cannot. A
    generic preparation form applies to its microbial owner; an unrelated
    named extract form (for example rice bran extract) does not.
    """
    evidence = extract_label_evidence(row)
    names = [item.value for item in evidence if item.kind == "source_name"]
    if not names:
        names = [str(row.get(key) or "") for key in (
            "source_label_name", "label_display_name",
        )]
    forms = [item.value for item in evidence if item.kind == "source_form"]
    for text in names:
        if re.search(r"\b(?:epicor|postbiotics?)\b", text, re.IGNORECASE):
            return True
        if _MICROBIAL_SOURCE_RE.search(text) and (
            _MICROBIAL_PREPARATION_RE.search(text)
            or _MICROBIAL_COMPONENT_RE.search(text)
        ):
            return True

    # On structural headers, forms describe sibling blend members rather than
    # the preparation of the header itself. Consumers evaluate those rows.
    if _is_structural_blend_header(row):
        return False
    microbial_owner = any(_MICROBIAL_SOURCE_RE.search(text) for text in names)
    component_owner = any(_MICROBIAL_COMPONENT_RE.search(text) for text in names)
    for text in forms:
        if _MICROBIAL_SOURCE_RE.search(text) and (
            component_owner
            or _MICROBIAL_PREPARATION_RE.search(text)
            or _MICROBIAL_COMPONENT_RE.search(text)
        ):
            return True
        unprefixed = _FORM_IDENTITY_PREFIX_RE.sub("", text).strip()
        if microbial_owner and (
            _MICROBIAL_PREPARATION_RE.fullmatch(unprefixed)
            or _MICROBIAL_COMPONENT_RE.search(text)
        ):
            return True
    return False


def _has_whole_microbial_identity(value: str) -> bool:
    """Distinguish organism identity from a microbial source in a food name.

    This does not establish viability. Generic words such as yeast identify
    an organism only as whole labels, not inside preparations like fermented
    rice. Scientific taxa retain the shared, bounded source vocabulary.
    """
    text = normalize_label_display(value.replace("_", " "))
    if has_nonlive_microbial_derivative_evidence({"name": text}):
        return False
    return bool(
        re.fullmatch(r"(?:(?:(?:brewer|baker)(?:['’]s|s['’]?)?|nutritional)\s+)?yeast|bacteria",
                     text, re.IGNORECASE)
        or any(match.group().casefold() not in {"yeast", "bacteria"}
               for match in _MICROBIAL_SOURCE_RE.finditer(text))
    )


def _is_blend_header_row(row: Mapping[str, Any]) -> bool:
    """The cleaner's blend-total header row."""
    return (
        row.get("cleaner_row_role") == "blend_header_total"
        or row.get("hierarchyType") == "blend_header"
    )


def is_identity_scoreable(disposition: str | None) -> bool:
    return disposition in _SCOREABLE_DISPOSITIONS


def _canonical(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _candidate_variants(value: str) -> tuple[str, ...]:
    display = normalize_label_display(value)
    variants = [display] if display else []
    match = _PARENTHESIZED_IDENTITY_RE.fullmatch(display)
    if match:
        variants.extend(
            part
            for part in (
                normalize_label_display(match.group(1)),
                normalize_label_display(match.group(2)),
            )
            if part
        )
    return tuple(dict.fromkeys(variants))


def _form_candidate_variants(value: str) -> tuple[str, ...]:
    """Return form identity candidates without changing the displayed label text."""
    variants = list(_candidate_variants(value))
    display = normalize_label_display(value)
    unprefixed = _FORM_IDENTITY_PREFIX_RE.sub("", display, count=1).strip()
    if unprefixed and unprefixed != display:
        variants.extend(_candidate_variants(unprefixed))
    return tuple(dict.fromkeys(variants))


def _resolved_canonicals(
    evidence: Iterable[LabelEvidence],
    resolve_candidate: CandidateResolver,
    canonical_parent_of: CanonicalParentPredicate | None = None,
) -> set[str]:
    resolved: set[str] = set()
    for item in evidence:
        item_resolved: list[str] = []
        for candidate in _candidate_variants(item.value):
            canonical_id = _canonical(resolve_candidate(candidate))
            if not canonical_id or canonical_id in item_resolved:
                continue
            if not item_resolved:
                item_resolved.append(canonical_id)
                continue
            first = item_resolved[0]
            if canonical_parent_of and (
                canonical_parent_of(first, canonical_id)
                or canonical_parent_of(canonical_id, first)
            ):
                item_resolved.append(canonical_id)
        resolved.update(item_resolved)
    return resolved


def _preferred_canonical(
    canonicals: set[str],
    canonical_parent_of: CanonicalParentPredicate | None,
) -> str | None:
    if len(canonicals) == 1:
        return next(iter(canonicals))
    if len(canonicals) < 2 or canonical_parent_of is None:
        return None

    descendants = {
        candidate
        for candidate in canonicals
        if not any(
            candidate != other and canonical_parent_of(candidate, other)
            for other in canonicals
        )
    }
    if len(descendants) != 1:
        return None
    specific = next(iter(descendants))
    if all(
        candidate == specific or canonical_parent_of(candidate, specific)
        for candidate in canonicals
    ):
        return specific
    return None


def _source_name(
    evidence: tuple[LabelEvidence, ...],
    resolved_canonical: str | None,
    resolve_candidate: CandidateResolver,
    *,
    prefer_literal_source: bool = True,
) -> str | None:
    sources = [item for item in evidence if item.kind == "source_name"]
    structured = [item for item in evidence if item.kind == "structured_identity"]
    if resolved_canonical:
        # Prefer the literal ingredient-line wording when it validates the
        # selected identity. This preserves branded preparations and explicit
        # source salts (for example, "Magtein Magnesium L-Threonate") instead
        # of collapsing them to a generic structured parent ("Magnesium"). A
        # literal that resolves to a conflicting identity is deliberately
        # skipped so repaired rows such as mislabeled DHA -> EPA retain the
        # corrected structured display.
        if prefer_literal_source:
            for item in sources:
                if any(
                    _canonical(resolve_candidate(value)) == resolved_canonical
                    for value in _candidate_variants(item.value)
                ):
                    return item.value
        for item in structured:
            variants = _candidate_variants(item.value)
            matches = (
                _canonical(resolve_candidate(value)) == resolved_canonical
                for value in variants
            )
            if any(matches):
                wrapper = _PARENTHESIZED_IDENTITY_RE.fullmatch(
                    normalize_label_display(item.value)
                )
                wrapper_sides_match = bool(
                    wrapper
                    and _canonical(resolve_candidate(wrapper.group(1)))
                    == resolved_canonical
                    and _canonical(resolve_candidate(wrapper.group(2)))
                    == resolved_canonical
                )
                if wrapper_sides_match:
                    literal_match = _LITERAL_PARENTHESIZED_IDENTITY_RE.fullmatch(
                        item.value
                    )
                    if literal_match:
                        return literal_match.group(1).strip()
                return item.value

    source = next((item.value for item in sources), None)
    if source:
        return source
    return structured[0].value if structured else None


def _identity_tokens(text: Any) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", normalize_label_display(text).casefold())
    return {t[:-1] if len(t) > 3 and t.endswith("s") else t for t in tokens}


def _label_spells_identity(label: Any, names: Iterable[str]) -> bool:
    """The printed name contains every word of one of the identity's names."""
    words = _identity_tokens(label)
    return any((tokens := _identity_tokens(name)) and tokens <= words for name in names)


def resolve_identity(
    row: Mapping[str, Any],
    supplied_canonical_id: str | None,
    resolve_candidate: CandidateResolver,
    *,
    taxonomy_coherent: bool = False,
    allow_unscoreable_taxonomy_only: bool = False,
    canonical_parent_of: CanonicalParentPredicate | None = None,
    canonical_registry: CanonicalIdentityRegistry | None = None,
    interaction_rules_of: Callable[[str], frozenset] | None = None,
    nested_member_names: tuple[str, ...] = (),
) -> IdentityDecision:
    """Resolve label identity without reproducing the external taxonomy matcher.

    ``supplied_canonical_id`` and callback results must already be canonical
    registry IDs; they are compared exactly. ``taxonomy_coherent`` carries the
    caller's canonical/standard-name/form/UNII confidence result.
    ``allow_unscoreable_taxonomy_only`` is reserved for rows the caller already
    classified as intentionally non-scorable; it records that context without
    inferring a canonical identity.
    ``canonical_registry`` supplies exact literal name/alias proof for source
    preparation exceptions; the general candidate resolver alone cannot.
    """
    evidence = extract_label_evidence(row)
    canonical_before = _canonical(supplied_canonical_id)

    structured_evidence = tuple(
        item for item in evidence if item.kind == "structured_identity"
    )
    primary_structured_evidence = tuple(
        item
        for item in structured_evidence
        if not item.field.startswith("alternateNames")
    )
    alternate_name_evidence = tuple(
        item
        for item in structured_evidence
        if item.field.startswith("alternateNames")
    )
    raw_evidence = tuple(item for item in evidence if item.kind == "source_name")
    form_evidence = tuple(item for item in evidence if item.kind == "source_form")
    resolved_structured_evidence = primary_structured_evidence
    structured_canonicals = _resolved_canonicals(
        resolved_structured_evidence,
        resolve_candidate,
        canonical_parent_of,
    )
    if not structured_canonicals:
        resolved_structured_evidence = alternate_name_evidence
        structured_canonicals = _resolved_canonicals(
            resolved_structured_evidence,
            resolve_candidate,
            canonical_parent_of,
        )
    raw_canonicals = _resolved_canonicals(
        raw_evidence,
        resolve_candidate,
        canonical_parent_of,
    )

    structured_canonical = _preferred_canonical(
        structured_canonicals,
        canonical_parent_of,
    )
    raw_canonical = _preferred_canonical(
        raw_canonicals,
        canonical_parent_of,
    )
    structured_disambiguated_by_literal = bool(
        structured_canonical is None
        and len(structured_canonicals) > 1
        and raw_canonical in structured_canonicals
    )
    if structured_disambiguated_by_literal:
        structured_canonical = raw_canonical
    literal_specific_over_structured_parent = bool(
        canonical_before
        and raw_canonical == canonical_before
        and canonical_registry is not None
        and raw_evidence
        and canonical_registry.literal_identity_matches(raw_evidence[0].value, canonical_before)
        and structured_canonical
        and structured_canonical != canonical_before
        and canonical_parent_of
        and canonical_parent_of(structured_canonical, canonical_before)
    )
    # The printed name is an exact curated alias of the supplied identity and the
    # resolver reads it as nothing else.
    label_names_supplied = bool(
        canonical_before
        and canonical_registry is not None
        and raw_evidence
        and raw_canonical in {None, canonical_before}
        and canonical_registry.literal_identity_matches(raw_evidence[0].value, canonical_before)
    )
    # A DSLD ingredientGroup is a group, never more specific than its row. It cannot
    # replace an identity the label names with a different plant, species, part or
    # preparation (Wheat Grass grouped as "Couch Grass", Green Bell Pepper as
    # "Capsicum", Ginger root extract as "Ginger"). It still repairs when the label
    # names the group's identity (as an alias or in so many words: "Neutral Protease"
    # under "Protease"), and may refine to a registered child. A role or catch-all
    # record (natural colors, a proprietary blend) is no specific identity to
    # protect, and a "Proprietary Blend" group keeps a branded complex named after
    # one member (TamaFlex) a blend. Keeping the label identity may never drop an
    # interaction rule the group's identity answers to; that stays a reviewed
    # identity-link decision (ADR-0005).
    label_names_supplied_over_structured_group = bool(
        label_names_supplied
        and _GENERAL_BLEND_ID not in {canonical_before, structured_canonical}
        and structured_canonical
        and structured_canonical != canonical_before
        and not canonical_registry.is_role_record(canonical_before)
        and not canonical_registry.literal_identity_matches(raw_evidence[0].value, structured_canonical)
        and not _label_spells_identity(
            raw_evidence[0].value, canonical_registry.standard_names_of(structured_canonical)
        )
        and not (canonical_parent_of and canonical_parent_of(canonical_before, structured_canonical))
        and (
            interaction_rules_of is None
            or interaction_rules_of(structured_canonical) <= interaction_rules_of(canonical_before)
        )
    )
    form_validates_specific_over_structured_parent = bool(
        canonical_before
        and structured_canonical
        and structured_canonical != canonical_before
        and (
            (canonical_parent_of and canonical_parent_of(structured_canonical, canonical_before))
            # The cleaner's bounded source-form resolver already establishes
            # preparation identity. A source organism is provenance, not a
            # competing preparation; require the actual declared form too.
            or row.get("cleaner_match_method") == "single_declared_nutrient_form"
        )
        and any(
            _canonical(resolve_candidate(candidate)) == canonical_before
            for item in form_evidence
            for candidate in _form_candidate_variants(item.value)
        )
    )
    # A sole, complete chemical-material form can identify a preparation
    # whose broad botanical group only describes its source (e.g. a branded
    # policosanol form under sugar cane wax). Retain the supplied identity
    # only when its source preparation has an exact curated alias; this cannot
    # promote a source-only, partial, mixed or conflicting chemical row.
    declared_forms = row.get("forms")
    if not declared_forms and isinstance(row.get("raw_taxonomy"), Mapping):
        declared_forms = row["raw_taxonomy"].get("forms")
    declared_material_validates_identity = bool(
        canonical_before
        and raw_canonical in {None, canonical_before, structured_canonical}
        and canonical_registry is not None
        and raw_evidence
        and canonical_registry.literal_identity_matches(
            normalize_label_display(raw_evidence[0].value).casefold().removesuffix(" extract"),
            canonical_before,
        )
        and isinstance(declared_forms, (list, tuple))
        and len(declared_forms) == 1
        and isinstance(declared_forms[0], Mapping)
        and str(declared_forms[0].get("name") or "").strip()
        and declared_forms[0].get("percent") in {None, 100, "100"}
        and declared_forms[0].get("quantity") in (None, [])
        and declared_forms[0].get("amount") is None
        and str(declared_forms[0].get("prefix") or "").strip().casefold() in {"", "as"}
        and str(declared_forms[0].get("category") or "").casefold()
            in {"non-nutrient/non-botanical", "complex carbohydrate"}
        and canonical_registry.literal_identity_matches(
            str(declared_forms[0].get("ingredientGroup") or ""), canonical_before
        )
        # An unresolved branded form keeps its honest form hold. A known
        # different chemical name cannot be overruled by its broad group.
        and not any(
            (form_identity := canonical_registry.resolve_verified_preferred(candidate))
            and form_identity[0] != canonical_before
            and not (
                canonical_parent_of
                and (
                    canonical_parent_of(form_identity[0], canonical_before)
                    or canonical_parent_of(canonical_before, form_identity[0])
                )
            )
            for candidate in _form_candidate_variants(str(declared_forms[0]["name"]))
        )
    )
    if declared_material_validates_identity:
        form_validates_specific_over_structured_parent = True

    # A complete, explicitly named botanical material is stronger than a
    # generic DSLD group. Resolve only curated literal forms (including the
    # shared comma-qualifier normalization), never a guessed species token.
    botanical_form_ids = []
    reviewed_botanical_source = bool(
        canonical_registry and canonical_before and raw_evidence
        and canonical_registry.literal_identity_matches(raw_evidence[0].value, canonical_before)
        and isinstance(declared_forms, (list, tuple)) and len(declared_forms) == 1
        and isinstance(declared_forms[0], Mapping)
        and str(declared_forms[0].get("category") or "").casefold() == "botanical"
        and str(row.get("category") or (row.get("raw_taxonomy") or {}).get("category") or "").casefold() == "botanical"
        and declared_forms[0].get("percent") in {None, 100, "100"}
        and declared_forms[0].get("quantity") in (None, [])
        and declared_forms[0].get("amount") is None
        and str(declared_forms[0].get("prefix") or "").strip().casefold() in {"", "as"}
        and canonical_registry._key(declared_forms[0].get("name"))
        in canonical_registry.source_form_aliases.get(
            (canonical_before, canonical_registry._key(raw_evidence[0].value)), frozenset())
    )
    if canonical_registry and isinstance(declared_forms, (list, tuple)) and not reviewed_botanical_source:
        for form in declared_forms:
            if not isinstance(form, Mapping) or str(form.get("category") or "").casefold() != "botanical":
                continue
            literal = str(form.get("name") or "")
            named = canonical_registry.resolve_verified_preferred(literal)
            if named is None:
                named = canonical_registry.resolve_verified_preferred(strip_label_identity_qualifiers(literal))
            if named and not canonical_registry.is_role_record(named[0]):
                botanical_form_ids.append(named[0])
    # A named extract may refine a generic source row without contradicting its
    # botanical identity. Keep the established parent only when the curated
    # interaction twin and an identical, unambiguous UNII agree on the plant;
    # this does not establish extract equivalence or infer marker content.
    botanical_form_same_material = bool(
        canonical_registry and canonical_before and botanical_form_ids
        and raw_canonical in {None, canonical_before}
        and len(declared_forms) == 1
        and all(
            cid == canonical_before or (
                BOTANICAL_INTERACTION_TWIN.get(cid) == canonical_before
                and len(canonical_registry.verified_uniis.get(cid, ())) == 1
                and canonical_registry.verified_uniis.get(cid)
                == canonical_registry.verified_uniis.get(canonical_before)
                and (interaction_rules_of is None
                     or interaction_rules_of(canonical_before) <= interaction_rules_of(cid))
            ) for cid in botanical_form_ids
        )
        and declared_forms[0].get("percent") in {None, 100, "100"}
        and declared_forms[0].get("quantity") in (None, [])
        and declared_forms[0].get("amount") is None
        and str(declared_forms[0].get("prefix") or "").strip().casefold() in {"", "as"}
    )
    botanical_form_conflict = bool(
        canonical_before and botanical_form_ids
        # Nutrient/marker plus source-plant rows are not whole botanical
        # materials (e.g. isoflavones plus soybean). Their existing owner wins.
        and all(isinstance(form, Mapping)
                and str(form.get("category") or "").casefold() == "botanical"
                for form in declared_forms)
        and str(row.get("category") or (row.get("raw_taxonomy") or {}).get("category") or "").casefold() == "botanical"
        and any(cid != canonical_before for cid in botanical_form_ids)
        and not botanical_form_same_material
        and not _is_blend_header_row(row)
        and not allow_unscoreable_taxonomy_only
    )
    botanical_material_canonical = None
    if botanical_form_conflict and len(declared_forms) == 1:
        form = declared_forms[0]
        target = botanical_form_ids[0]
        if (
            form.get("percent") in {None, 100, "100"}
            and form.get("quantity") in (None, [])
            and form.get("amount") is None
            and str(form.get("prefix") or "").strip().casefold() in {"", "as"}
            # An independently resolved printed identity cannot be overridden
            # by a contradictory form, even when the group repeats that name.
            and raw_canonical in {None, target}
            and (interaction_rules_of is None
                 or interaction_rules_of(canonical_before) <= interaction_rules_of(target))
        ):
            botanical_material_canonical = target

    microbial_derivative_conflict = bool(
        has_nonlive_microbial_derivative_evidence(row)
        and (
            # Older cleaner identities can still name a whole organism when
            # DSLD's category is TBD. The row's own preparation form is the
            # contradiction; a resolved category is not required to see it.
            (canonical_before and _has_whole_microbial_identity(canonical_before))
            or (
                structured_canonical
                and _has_whole_microbial_identity(structured_canonical)
                and any(
                    _has_whole_microbial_identity(item.value)
                    for item in resolved_structured_evidence
                )
            )
        )
    )
    exact_literal_match = (
        canonical_registry.resolve_verified_preferred(raw_evidence[0].value)
        if microbial_derivative_conflict and canonical_registry and raw_evidence
        else None
    )
    literal_preparation_canonical = (
        exact_literal_match[0]
        if exact_literal_match
        and not _has_whole_microbial_identity(exact_literal_match[0])
        else None
    )
    display_canonical = (
        canonical_before
        if declared_material_validates_identity or label_names_supplied_over_structured_group
        else raw_canonical
        if literal_specific_over_structured_parent
        else structured_canonical or raw_canonical
    )
    if microbial_derivative_conflict:
        display_canonical = literal_preparation_canonical
    source_name = _source_name(
        evidence,
        display_canonical,
        resolve_candidate,
        # When an explicit form is the only evidence validating a child of a
        # structured parent (Vitamin A -> beta-carotene, for example), retain
        # that structured parent as the label base. In ordinary clean/alias
        # cases the literal source wording remains the authoritative display.
        prefer_literal_source=(declared_material_validates_identity
                               or not form_validates_specific_over_structured_parent),
    )
    if literal_preparation_canonical or (botanical_form_conflict and raw_evidence):
        source_name = raw_evidence[0].value
    source_form = next(
        (item.value for item in evidence if item.kind == "source_form"),
        None,
    )
    if (row.get("canonical_source_db") == "botanical_ingredients"
            and " and " in str(row.get("plantPart") or "")):
        source_form = "; ".join(dict.fromkeys(
            item.value for item in evidence if item.kind == "source_form"
        )) or source_form
    display_name = normalize_label_display(source_name) or None
    display_form = normalize_label_display(source_form) or None

    # Non-scorability is a row role, not evidence against the substance: a row
    # the caller will not score keeps a supplied identity its own text proves.
    # A blend header keeps it too ("Caffeine Blend" -> caffeine): its total is
    # the blend's, so the identity is interaction-only like any kept identity.
    # The cleaner records that proof as the row's standardName ("Caffeine
    # Blend" -> Caffeine, "Lactobacillus" -> Probiotics, "Arginine" ->
    # L-Arginine); a stale id the row's text never named is not kept, nor is
    # one its label contradicts, nor a role or catch-all record (a
    # proprietary blend, an other-ingredient role), which is no substance.
    # Nor is an identity the cleaner took from one declared form when the row
    # lists several ("Bifidobacterium": B. bifidum, B. animalis lactis is not
    # B. lactis alone), or from a declared marker form ("Sawasabi Wasabi
    # powder": Total Isothiocyanate is not the plant; "Glycosides": Polydatin,
    # resveratrol's glucoside, is not resveratrol), or one a declared form
    # names as another substance ("Arginine" as whey protein isolate) unless
    # that form is a member of it ("Lactobacillus": L. acidophilus ...), or a
    # constituent its parent row names ("Arginine" in soy protein isolate).
    # An identity kept only on that standardName is for interactions alone
    # (NON_SCORING_IDENTITY_RATIONALE).
    label_proves_canonical = bool(canonical_before) and (
        structured_canonical == canonical_before
        or raw_canonical == canonical_before
        or taxonomy_coherent
    )
    declared_forms = {
        normalize_label_display(item.value).casefold()
        for item in form_evidence
        if item.field.startswith("forms[")
    }
    form_derived_identity = row.get("cleaner_match_method") in _FORM_DERIVED_MATCH_METHODS
    forms_contradict = form_derived_identity and (
        len(declared_forms) > 1
        or row.get("cleaner_match_method") == "single_declared_marker_form"
    )
    if canonical_before and canonical_registry is not None and not forms_contradict:
        def names_the_identity(form_canonical: str) -> bool:
            return (
                form_canonical == canonical_before
                or INTERACTION_SUBJECT_FAMILY.get(form_canonical) == canonical_before
                or bool(canonical_parent_of and canonical_parent_of(canonical_before, form_canonical))
            )

        form_canonicals = [
            _canonical(named[0])
            for item in form_evidence
            if item.field.startswith("forms[")
            for named in [canonical_registry.resolve_preferred(item.value)]
            if named
        ]
        if _is_blend_header_row(row):
            # A blend header's forms are its members ("Caffeine Blend":
            # Anhydrous Caffeine, Piperine). It keeps an identity only when its
            # printed name or a member names it, and, when members resolve, one
            # of them must ("Organic Adrenal Blend" of schisandra and rhodiola is
            # no adrenal tissue; a "Glutamic Acid" header of caseinate and whey
            # is those proteins' amino profile).
            identity_names = canonical_registry.standard_names_of(canonical_before)
            members = [
                (item.value, _canonical(named[0]) if named else None)
                for item in form_evidence
                if item.field.startswith("forms[")
                for named in [canonical_registry.resolve_preferred(item.value)]
            ]
            # BCM-95's "Total Curcuminoids complex (with Essential Oils)" lists the
            # turmeric-oil fraction it is made with (curcumin with turmeric
            # essential oils, PMID 25994138): part of a curcumin header, never a
            # contradiction. Only when the oil or an enclosing row names turmeric.
            turmeric_named = any(
                re.search(r"\bturmeric\b", str(name or ""), re.I)
                for name in [row.get("parentBlend"), *(row.get("_ancestor_blends") or [])]
            )
            turmeric_oil = [
                value for value, member in members
                if canonical_before == "curcumin"
                and (member == "volatile_oils" or re.search(r"\b(?:essential oils?|oleoresin)\b", value, re.I))
                and (turmeric_named or re.search(r"\bturmeric\b", value, re.I))
            ]
            members = [(value, member) for value, member in members if value not in turmeric_oil]
            member_names_identity = any(
                (member and names_the_identity(member)) or _label_spells_identity(value, identity_names)
                for value, member in members
            )
            printed_name = raw_evidence[0].value if raw_evidence else ""
            printed_names_identity = _label_spells_identity(printed_name, identity_names) or bool(
                turmeric_oil and canonical_registry.names_identity(
                    re.sub(r"\s+(?:complex|blend)$", "", printed_name.strip(), flags=re.I), canonical_before
                )
            )
            forms_contradict = not (
                (printed_names_identity or member_names_identity)
                and (member_names_identity or not any(member for _, member in members))
            )
        else:
            forms_contradict = not all(map(names_the_identity, form_canonicals))
    # A row listed under a parent (or any enclosing row) that names another
    # material is that material's constituent ("Arginine" in "Solae Soy
    # Protein isolate"; in Amino Acids in Cilantro), not the substance added
    # on its own; a family or category parent keeps it.
    enclosing = [row.get("parentBlend"), *(row.get("_ancestor_blends") or [])]
    for enclosing_name in (name for name in enclosing if name):
        if not canonical_before or canonical_registry is None:
            break
        parent_named = canonical_registry.resolve_preferred(enclosing_name)
        parent_canonical = _canonical(parent_named[0]) if parent_named else None
        if (
            parent_canonical
            and parent_canonical != canonical_before
            and not canonical_registry.is_role_record(parent_canonical)
            and INTERACTION_SUBJECT_FAMILY.get(canonical_before) != parent_canonical
            and not (canonical_parent_of and canonical_parent_of(parent_canonical, canonical_before))
        ):
            forms_contradict = True
            break
    standard_name_proves_canonical = bool(canonical_before) and (
        not raw_canonicals
        and canonical_registry is not None
        and not forms_contradict
        and not canonical_registry.is_role_record(canonical_before)
        and canonical_registry.literal_identity_matches(
            str(row.get("standardName") or ""), canonical_before
        )
    )
    retained_unscoreable_canonical = (
        canonical_before
        if label_proves_canonical or standard_name_proves_canonical
        else None
    )
    interaction_only_identity = (
        standard_name_proves_canonical and not label_proves_canonical
    )
    # Sean, 2026-10-20: this verified branded complex keeps its identity,
    # separately from the unscored blend-total role. Only the exact curated
    # brand and both printed constituents establish this narrow exception;
    # another brand, an anonymous blend or incomplete forms do not qualify.
    senactiv_names = canonical_registry.standard_names_of("NHA_SENACTIV") if canonical_registry else ()
    reviewed_senactiv_header = bool(
        canonical_before == "NHA_SENACTIV"
        and structured_canonical == _GENERAL_BLEND_ID
        and _is_blend_header_row(row)
        and allow_unscoreable_taxonomy_only
        and raw_evidence
        and canonical_registry is not None
        and canonical_registry.names_identity(raw_evidence[0].value, "NHA_SENACTIV")
        and normalize_label_display(raw_evidence[0].value).casefold()
        in {normalize_label_display(name).casefold() for name in (*senactiv_names, "Seneactiv")}
        and {normalize_label_display(item.value).casefold() for item in form_evidence}
        == {"panax notoginseng", "rosa roxburghii"}
        and {normalize_label_display(name).casefold() for name in nested_member_names}
        <= {"panax notoginseng", "rosa roxburghii"}
    )

    if display_name is None:
        disposition: IdentityDisposition = "missing_display_label"
        canonical_after = None
        rationale = "No displayable literal ingredient-line label was available."
    elif literal_preparation_canonical:
        disposition = (
            "clean" if literal_preparation_canonical == canonical_before else "repaired"
        )
        canonical_after = literal_preparation_canonical
        rationale = (
            "The exact literal label establishes the registered preparation identity; "
            "a supplied whole-organism identity cannot replace it."
        )
    elif microbial_derivative_conflict:
        disposition = "identity_conflict"
        canonical_after = None
        rationale = (
            "The literal source or its label form identifies a non-live microbial "
            "preparation; a supplied whole-organism identity cannot establish the "
            "preparation's canonical identity."
        )
    elif len(structured_canonicals) > 1 and structured_canonical is None:
        disposition = "identity_conflict"
        canonical_after = None
        rationale = (
            "Structured line evidence resolved to conflicting canonical identities: "
            + ", ".join(sorted(structured_canonicals))
            + "."
        )
    elif botanical_form_conflict:
        canonical_after = botanical_material_canonical
        disposition = "repaired" if canonical_after else "identity_conflict"
        rationale = (
            "The sole complete botanical material is explicitly named by a curated "
            "source-form alias; the generic structured group cannot replace it."
            if canonical_after else
            "Botanical source forms contradict the supplied identity; complete material "
            "ownership and preservation of interaction rules are not established."
        )
    elif reviewed_senactiv_header:
        disposition = "taxonomy_only"
        canonical_after = canonical_before
        rationale = (
            "The exact curated Senactiv brand and both printed constituents establish "
            "the branded complex; its blend total remains excluded from scoring."
        )
    elif structured_canonical is not None:
        if canonical_before is None and allow_unscoreable_taxonomy_only:
            disposition = "taxonomy_only"
            canonical_after = None
            rationale = (
                "The row was intentionally classified as non-scorable; its "
                "structured label evidence was retained without inferring a "
                "canonical identity."
            )
        elif canonical_before is None:
            disposition = "identity_conflict"
            canonical_after = None
            rationale = "No supplied canonical ID was available to validate or repair."
        elif (
            canonical_before == structured_canonical
            or literal_specific_over_structured_parent
            or form_validates_specific_over_structured_parent
            or label_names_supplied_over_structured_group
        ):
            disposition = "clean"
            canonical_after = canonical_before
            rationale = (
                "The unambiguous literal label selected the matching identity "
                "from conflicting structured fields."
                if structured_disambiguated_by_literal
                else (
                    "The literal label names the supplied identity; the structured line "
                    f"group {structured_canonical!r} names a different identity and stays "
                    "evidence only."
                )
                if label_names_supplied_over_structured_group
                and not literal_specific_over_structured_parent
                and not form_validates_specific_over_structured_parent
                else (
                    "The literal label validates the supplied specific identity; "
                    "the structured line identity is its registered parent."
                    if literal_specific_over_structured_parent
                    else (
                        ("An exact source alias and sole complete material form validate "
                         "the supplied preparation identity; the broad group is provenance."
                         if declared_material_validates_identity
                         else "An explicit label form validates the supplied specific identity; "
                              "the structured line identity is its registered parent.")
                        if form_validates_specific_over_structured_parent
                        else "Structured line identity agrees with the supplied canonical ID."
                    )
                )
            )
        else:
            disposition = "repaired"
            canonical_after = structured_canonical
            rationale = (
                "Unambiguous structured line identity replaced the supplied canonical ID "
                f"{canonical_before!r} with {structured_canonical!r}."
            )
    elif allow_unscoreable_taxonomy_only:
        disposition = "taxonomy_only"
        canonical_after = retained_unscoreable_canonical
        if canonical_after and interaction_only_identity:
            rationale = NON_SCORING_IDENTITY_RATIONALE
        elif canonical_after:
            rationale = (
                "The row was intentionally classified as non-scorable; its "
                "validated source identity was retained for non-scoring lineage."
            )
        else:
            rationale = NON_SCORABLE_NO_IDENTITY_RATIONALE
    elif canonical_before is None:
        disposition = "identity_conflict"
        canonical_after = None
        rationale = "No supplied canonical ID was available to validate or repair."
    elif len(raw_canonicals) > 1 and raw_canonical is None:
        disposition = "identity_conflict"
        canonical_after = None
        rationale = (
            "Raw label evidence resolved to conflicting canonical identities: "
            + ", ".join(sorted(raw_canonicals))
            + "."
        )
    elif raw_canonical is not None and raw_canonical != canonical_before:
        if canonical_parent_of and canonical_parent_of(
            canonical_before,
            raw_canonical,
        ):
            disposition = "repaired"
            canonical_after = raw_canonical
            rationale = (
                "Raw label evidence identifies a registered descendant of the "
                f"supplied canonical ID {canonical_before!r}: {raw_canonical!r}."
            )
        else:
            disposition = "identity_conflict"
            canonical_after = None
            rationale = (
                f"Raw label evidence resolves to {raw_canonical!r} and contradicts the "
                f"supplied canonical ID {canonical_before!r}."
            )
    elif raw_canonical == canonical_before:
        disposition = "clean"
        canonical_after = canonical_before
        rationale = "Raw label identity validates the supplied canonical ID."
    elif taxonomy_coherent:
        disposition = "taxonomy_only"
        canonical_after = canonical_before
        rationale = (
            "No line evidence resolved to a more specific identity; the external "
            "taxonomy confidence contract permits the supplied canonical ID."
        )
    else:
        disposition = "identity_conflict"
        canonical_after = None
        rationale = "The external taxonomy confidence contract was not satisfied."

    # Authored source exclusions constrain every resolution path, including
    # stale aliases, structured groups and authoritative UNII matches. Notes
    # may veto an identity but never establish a replacement species.
    if canonical_after and canonical_registry is not None:
        from identity.safety import negative_match_terms_veto

        source_notes = tuple(_text_values(row.get("notes")))
        if negative_match_terms_veto(
            [item.value for item in evidence if item.kind in {"source_name", "source_form"}]
            + list(source_notes),
            canonical_registry.negative_match_terms.get(canonical_after, ()),
        ):
            disposition = "identity_conflict"
            canonical_after = None
            rationale = "An authored source exclusion contradicts the proposed canonical identity."
            evidence += tuple(LabelEvidence("notes", note, "source_form") for note in source_notes)

    # A provisional taxonomy match must not replace the literal preparation
    # after the final decision declines to establish its identity. Keep the
    # structured evidence for diagnosis, but display the actual unknown label.
    if canonical_after is None and raw_evidence:
        source_name = raw_evidence[0].value
        display_name = normalize_label_display(source_name) or None

    scoreable = (
        not allow_unscoreable_taxonomy_only
        and is_identity_scoreable(disposition)
        and canonical_after is not None
    )
    return IdentityDecision(
        disposition=disposition,
        source_label_name=source_name,
        source_label_form=source_form,
        label_display_name=display_name,
        label_display_form=display_form,
        canonical_id_before=canonical_before,
        canonical_id=canonical_after,
        evidence=evidence,
        scoreable_identity=scoreable,
        rationale=rationale,
    )
