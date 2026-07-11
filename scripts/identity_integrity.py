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
                leading_matches = (
                    len(variants) > 1
                    and _canonical(resolve_candidate(variants[1]))
                    == resolved_canonical
                )
                if leading_matches:
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
) -> IdentityDecision:
    evidence = extract_label_evidence(row)
    canonical_before = _canonical(supplied_canonical_id)

    structured_evidence = tuple(
        item for item in evidence if item.kind in {"structured_identity", "source_form"}
    )
    resolved = _resolved_canonicals(structured_evidence, resolve_candidate)
    if not resolved:
        raw_evidence = tuple(item for item in evidence if item.kind == "source_name")
        resolved = _resolved_canonicals(raw_evidence, resolve_candidate)

    sole_canonical = next(iter(resolved)) if len(resolved) == 1 else None
    source_name = _source_name(evidence, sole_canonical, resolve_candidate)
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
    elif len(resolved) > 1:
        disposition = "identity_conflict"
        canonical_after = None
        rationale = (
            "Structured line evidence resolved to conflicting canonical identities: "
            + ", ".join(sorted(resolved))
            + "."
        )
    elif sole_canonical is not None:
        canonical_after = sole_canonical
        if canonical_before == sole_canonical:
            disposition = "clean"
            rationale = "Structured line identity agrees with the supplied canonical ID."
        else:
            disposition = "repaired"
            rationale = (
                "Unambiguous structured line identity replaced the supplied canonical ID "
                f"{canonical_before!r} with {sole_canonical!r}."
            )
    else:
        disposition = "taxonomy_only"
        canonical_after = canonical_before
        rationale = (
            "No line evidence resolved to a more specific identity; retained the supplied "
            "canonical ID."
        )

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
