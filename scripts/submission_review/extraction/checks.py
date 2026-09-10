"""Typed findings a careful reader can reach without asking a model.

These run over a validated ``label_draft_v1`` and the evidence it was read
from. Two reasons they exist separately from the model:

*They are cheap and they are checkable.* A barcode that disagrees with the
submitted GTIN, a Supplement Facts panel nobody photographed, the same photo
twice — none of that needs inference, and a finding a program derives is worth
more to a reviewer than the same finding asserted by a model.

*They never decide anything.* Every result is a finding for a human to read.
Nothing here approves, rejects, resolves a duplicate, or mints an identity, and
a catalog hit is a candidate to compare against, never a disposition.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from ..gtin import canonical_gtin14_candidates, canonical_normalized_gtin14
from .envelope import DISCREPANCY_CODES, DISCREPANCY_SEVERITIES

#: Phrases that make label text look like an instruction to a reader that
#: executes text. The text is never altered: a label that says this is a
#: finding to record, and deleting it would destroy the evidence of it.
_INJECTION_MARKERS = (
    "ignore previous", "ignore all previous", "ignore your instructions",
    "disregard previous", "system prompt", "you are now", "act as",
    "new instructions", "override the", "respond only with",
)


def _finding(code: str, severity: str, detail: str,
             photo_ids: Sequence[str] = ()) -> dict[str, Any]:
    if code not in DISCREPANCY_CODES:
        raise ValueError(f"unknown discrepancy code {code!r}")
    if severity not in DISCREPANCY_SEVERITIES:
        raise ValueError(f"unknown severity {severity!r}")
    return {
        "code": code, "severity": severity, "detail": detail,
        "photo_ids": list(photo_ids),
    }


def _text_fields(value: Any) -> Iterable[str]:
    """Every string a model reported reading off the label, at any depth."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, nested in value.items():
            # Runtime provenance is authored by the worker, not read off a
            # photograph, so it is not label text.
            if key in {"schema_version", "provider", "model", "prompt_version",
                       "draft_origin", "evidence_snapshot", "sent_inputs"}:
                continue
            yield from _text_fields(nested)
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        for nested in value:
            yield from _text_fields(nested)


def run_checks(draft: Mapping[str, Any], *,
               submission_gtin: str | None = None,
               catalog_match: Mapping[str, Any] | None = None,
               ) -> list[dict[str, Any]]:
    """Findings derived from one draft and what is known about its submission.

    ``catalog_match`` is a lookup result supplied by the caller, which owns the
    identity index. Passing it in rather than reaching for the index keeps this
    module free of the corpus and testable without it.
    """
    findings: list[dict[str, Any]] = []
    roles = draft.get("photo_roles") or []

    findings.extend(_panel_findings(roles))
    findings.extend(_barcode_findings(draft, submission_gtin))
    findings.extend(_duplicate_photo_findings(draft))
    findings.extend(_injection_findings(draft))
    if catalog_match:
        findings.append(_finding(
            "catalog_candidate", "info",
            # Deliberately not a disposition: same barcode can mean a
            # different formulation, an older edition, or a quarantined entry.
            "This barcode already resolves in the catalog. Compare the labels "
            "before deciding; a match is not proof of the same product.",
        ))
    return findings


def _panel_findings(roles: Sequence[Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    facts_photos = [
        role for role in roles
        if isinstance(role, Mapping) and "supplement_facts" in (
            list(role.get("declared") or [])
            + [entry.get("role") for entry in role.get("inferred") or []
               if isinstance(entry, Mapping)]
        )
    ]
    if not facts_photos:
        findings.append(_finding(
            "facts_panel_missing", "critical",
            "No photograph shows a Supplement Facts panel.",
        ))
    for role in facts_photos:
        photo_id = role.get("photo_id")
        if role.get("readability") == "unreadable":
            findings.append(_finding(
                "facts_unreadable", "critical",
                "The Supplement Facts panel cannot be read.", [photo_id],
            ))
        if "cut_off" in (role.get("issues") or []):
            findings.append(_finding(
                "cut_off_text", "warning",
                "Text runs off the edge of the Supplement Facts photograph.",
                [photo_id],
            ))

    for role in roles:
        if not isinstance(role, Mapping):
            continue
        declared = set(role.get("declared") or [])
        inferred = {
            entry.get("role") for entry in role.get("inferred") or []
            if isinstance(entry, Mapping) and (entry.get("confidence") or 0) >= 0.8
        }
        # Only a confident disagreement is worth a reviewer's attention; an
        # uncertain reading of a photo slot is not evidence of anything.
        if declared and inferred and not (declared & inferred):
            findings.append(_finding(
                "declared_role_mismatch", "warning",
                f"Submitted as {', '.join(sorted(declared))} but reads as "
                f"{', '.join(sorted(str(role) for role in inferred))}.",
                [role.get("photo_id")],
            ))
    return findings


def _barcode_findings(draft: Mapping[str, Any],
                      submission_gtin: str | None) -> list[dict[str, Any]]:
    seen = (draft.get("identity") or {}).get("barcode_digits_seen")
    if not isinstance(seen, Mapping) or seen.get("status") not in {"read", "partial"}:
        return []
    printed = seen.get("value")
    if not isinstance(printed, str) or not printed.strip():
        return []
    if submission_gtin is None:
        return []
    # One canonicalization for the whole system: the same GTIN owner the app,
    # the database and the importer use. A second one here would eventually
    # disagree with all three.
    expected = canonical_normalized_gtin14(submission_gtin)
    if expected is None:
        return []
    if expected in canonical_gtin14_candidates(printed):
        return []
    return [_finding(
        "barcode_mismatch", "critical",
        f"The barcode on the label reads {printed.strip()}, which is not the "
        f"barcode this submission was filed under.",
    )]


def _duplicate_photo_findings(draft: Mapping[str, Any]) -> list[dict[str, Any]]:
    snapshot = draft.get("evidence_snapshot")
    if not isinstance(snapshot, Mapping):
        return []
    by_digest: dict[str, list[str]] = {}
    for photo_id, digest in snapshot.items():
        if isinstance(digest, str):
            by_digest.setdefault(digest, []).append(str(photo_id))
    duplicates = [ids for ids in by_digest.values() if len(ids) > 1]
    return [
        _finding(
            "multiple_products", "warning",
            "The same photograph was submitted more than once, so a panel may "
            "be missing.", sorted(ids),
        )
        for ids in duplicates
    ]


def _injection_findings(draft: Mapping[str, Any]) -> list[dict[str, Any]]:
    lowered = [text.lower() for text in _text_fields(draft) if isinstance(text, str)]
    hits = sorted({
        marker for marker in _INJECTION_MARKERS
        if any(marker in text for text in lowered)
    })
    if not hits:
        return []
    return [_finding(
        "injection_text_present", "warning",
        "Text on this label reads like an instruction "
        f"({', '.join(hits)}). It is kept exactly as printed and is a finding "
        "about the label, not something to act on.",
    )]
