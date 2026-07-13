"""Pure label-first ingredient identity and display-fidelity contract."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal


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
_PARENTHESIZED_MARKER_RE = re.compile(r"\((?:tm|r|sm)\)", re.IGNORECASE)
_PARENTHESIZED_IDENTITY_RE = re.compile(r"^(.+?)\s*\(([^()]*)\)\s*$")
_LITERAL_PARENTHESIZED_IDENTITY_RE = re.compile(
    r"^(.+?)\s*[\(（]([^()（）]*)[\)）]\s*$"
)


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


def extract_label_evidence(row: Mapping[str, Any]) -> tuple[LabelEvidence, ...]:
    """Extract auditable evidence from ingredient-line fields only."""
    evidence: list[LabelEvidence] = []

    for field in ("raw_source_text", "raw_name", "source_name", "name"):
        for value in _text_values(row.get(field)):
            evidence.append(LabelEvidence(field, value, "source_name"))

    for value in _text_values(row.get("ingredientGroup")):
        evidence.append(
            LabelEvidence("ingredientGroup", value, "structured_identity")
        )

    raw_taxonomy = row.get("raw_taxonomy")
    if isinstance(raw_taxonomy, Mapping):
        for value in _text_values(raw_taxonomy.get("ingredientGroup")):
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


def _resolved_canonicals(
    evidence: Iterable[LabelEvidence],
    resolve_candidate: CandidateResolver,
) -> set[str]:
    resolved: set[str] = set()
    for item in evidence:
        for candidate in _candidate_variants(item.value):
            canonical_id = _canonical(resolve_candidate(candidate))
            if canonical_id:
                resolved.add(canonical_id)
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
) -> str | None:
    structured = [item for item in evidence if item.kind == "structured_identity"]
    if resolved_canonical:
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

    source = next((item.value for item in evidence if item.kind == "source_name"), None)
    if source:
        return source
    return structured[0].value if structured else None


def resolve_identity(
    row: Mapping[str, Any],
    supplied_canonical_id: str | None,
    resolve_candidate: CandidateResolver,
    *,
    taxonomy_coherent: bool = False,
    allow_unscoreable_taxonomy_only: bool = False,
    canonical_parent_of: CanonicalParentPredicate | None = None,
) -> IdentityDecision:
    """Resolve label identity without reproducing the external taxonomy matcher.

    ``supplied_canonical_id`` and callback results must already be canonical
    registry IDs; they are compared exactly. ``taxonomy_coherent`` carries the
    caller's canonical/standard-name/form/UNII confidence result.
    ``allow_unscoreable_taxonomy_only`` is reserved for rows the caller already
    classified as intentionally non-scorable; it records that context without
    inferring a canonical identity.
    """
    evidence = extract_label_evidence(row)
    canonical_before = _canonical(supplied_canonical_id)

    structured_evidence = tuple(
        item for item in evidence if item.kind == "structured_identity"
    )
    raw_evidence = tuple(item for item in evidence if item.kind == "source_name")
    structured_canonicals = _resolved_canonicals(
        structured_evidence,
        resolve_candidate,
    )
    raw_canonicals = _resolved_canonicals(raw_evidence, resolve_candidate)

    structured_canonical = _preferred_canonical(
        structured_canonicals,
        canonical_parent_of,
    )
    raw_canonical = _preferred_canonical(
        raw_canonicals,
        canonical_parent_of,
    )
    display_canonical = structured_canonical or raw_canonical
    source_name = _source_name(evidence, display_canonical, resolve_candidate)
    source_form = next(
        (item.value for item in evidence if item.kind == "source_form"),
        None,
    )
    display_name = normalize_label_display(source_name) or None
    display_form = normalize_label_display(source_form) or None

    if display_name is None:
        disposition: IdentityDisposition = "missing_display_label"
        canonical_after = None
        rationale = "No displayable literal ingredient-line label was available."
    elif len(structured_canonicals) > 1 and structured_canonical is None:
        disposition = "identity_conflict"
        canonical_after = None
        rationale = (
            "Structured line evidence resolved to conflicting canonical identities: "
            + ", ".join(sorted(structured_canonicals))
            + "."
        )
    elif structured_evidence and structured_canonical is None:
        if allow_unscoreable_taxonomy_only:
            disposition = "taxonomy_only"
            canonical_after = None
            rationale = (
                "The row was intentionally classified as non-scorable; its "
                "unresolved structured label text is retained for display."
            )
        elif taxonomy_coherent and canonical_before is not None:
            disposition = "taxonomy_only"
            canonical_after = canonical_before
            rationale = (
                "Structured line text did not independently resolve to a canonical "
                "identity; the verified external taxonomy contract retains the "
                "supplied canonical ID without repairing it."
            )
        else:
            disposition = "identity_conflict"
            canonical_after = None
            rationale = "Direct structured line evidence could not be resolved."
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
        elif canonical_before == structured_canonical:
            disposition = "clean"
            canonical_after = structured_canonical
            rationale = "Structured line identity agrees with the supplied canonical ID."
        else:
            disposition = "repaired"
            canonical_after = structured_canonical
            rationale = (
                "Unambiguous structured line identity replaced the supplied canonical ID "
                f"{canonical_before!r} with {structured_canonical!r}."
            )
    elif allow_unscoreable_taxonomy_only:
        disposition = "taxonomy_only"
        canonical_after = None
        rationale = (
            "The row was intentionally classified as non-scorable; no canonical "
            "identity was inferred from raw label or form text."
        )
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

    scoreable = is_identity_scoreable(disposition) and canonical_after is not None
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
