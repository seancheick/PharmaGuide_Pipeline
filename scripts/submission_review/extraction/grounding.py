"""Check that a reading is actually present in the photograph it cites.

Every field in a ``label_draft_v1`` names the image it was read from and quotes
the text it was read out of. Nothing has ever checked that the quote is really
there. This does, by comparing it against an independent OCR pass over the same
prepared bytes.

Why it is worth the trouble: published work on document extraction finds a
large accuracy gap between fields whose value can be located in the source and
fields whose value cannot — grounding separates a reading from a plausible
invention far better than any confidence number a model reports about itself.
It is also cheap, and it works on *any* producer, so a vision model's claims
can be tested against a reader that cannot hallucinate.

What it deliberately does not do: decide anything. It returns a report. No
field is approved, rejected or rewritten here, and an ungrounded field is a
thing for a human to look at, not an error.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

#: Fields worth checking, in the order a reviewer reads them.
_FIELD_PATHS = (
    ("identity", "brand"),
    ("identity", "product_name"),
    ("identity", "barcode_digits_seen"),
    ("serving", "size"),
    ("serving", "servings_per_container"),
    ("serving", "basis_text"),
)
_DIGITS = re.compile(r"\d+(?:[.,]\d+)?")


@dataclass(frozen=True)
class FieldGrounding:
    """One field's answer to: is this actually printed where it says it is?"""

    path: str
    grounded: bool
    reason: str
    photo_id: str | None = None

    def as_payload(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "grounded": self.grounded,
            "reason": self.reason,
            "photo_id": self.photo_id,
        }


@dataclass(frozen=True)
class GroundingReport:
    """Every checked field, and how much of the reading is supported."""

    fields: tuple[FieldGrounding, ...]

    @property
    def checked(self) -> int:
        return len(self.fields)

    @property
    def grounded(self) -> int:
        return sum(1 for entry in self.fields if entry.grounded)

    @property
    def ungrounded(self) -> tuple[FieldGrounding, ...]:
        return tuple(entry for entry in self.fields if not entry.grounded)

    @property
    def rate(self) -> float | None:
        """Share of checked fields found in the photograph, or None if none."""
        return None if not self.fields else self.grounded / len(self.fields)

    def as_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "grounding_report_v1",
            "checked": self.checked,
            "grounded": self.grounded,
            "rate": self.rate,
            "fields": [entry.as_payload() for entry in self.fields],
        }


def _normalize(text: str) -> str:
    """Compare the way a reader would, not the way a byte comparison would.

    OCR collapses spaces unpredictably — the same panel yields "500 mg" and
    "400mcgDFE" — so whitespace, case and unicode form must not decide whether
    a value is present. Without this the check reports false ungroundings and
    a reviewer learns to ignore it.
    """
    folded = unicodedata.normalize("NFKD", text).casefold()
    return re.sub(r"[\s ]+", "", folded)


def _page_text(page: Any) -> str:
    lines = getattr(page, "lines", ()) or ()
    return _normalize(" ".join(str(getattr(line, "text", "")) for line in lines))


def _iter_fields(draft: Mapping[str, Any]) -> Iterable[tuple[str, Mapping[str, Any]]]:
    for section, name in _FIELD_PATHS:
        field = (draft.get(section) or {}).get(name)
        if isinstance(field, Mapping):
            yield f"{section}.{name}", field
    for index, row in enumerate(draft.get("ingredient_rows") or []):
        if not isinstance(row, Mapping):
            continue
        for name in ("display_name", "amount", "percent_dv", "form_text"):
            field = row.get(name)
            if isinstance(field, Mapping):
                yield f"ingredient_rows[{index}].{name}", field
    other = draft.get("other_ingredients")
    if isinstance(other, Mapping) and isinstance(other.get("text"), Mapping):
        yield "other_ingredients.text", other["text"]


def _claimed_strings(value: Any) -> list[str]:
    """What a reader would have to see on the label for this value to be true."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        # Trailing zeros differ between "500" and "500.0"; compare as printed.
        text = f"{value:g}"
        variants = {text, text.replace(".", ",")}
        # Labels commonly use a thousands separator while the draft stores a
        # numeric value. Include that faithful printed form without accepting
        # any other number or doing fuzzy matching.
        if text.isdigit() and len(text) > 3:
            variants.add(f"{int(text):,}")
        elif "." in text:
            whole, fraction = text.split(".", 1)
            if whole.isdigit() and len(whole) > 3:
                variants.add(f"{int(whole):,}.{fraction}")
        return sorted(variants)
    if isinstance(value, Mapping):
        claimed: list[str] = []
        for key in ("value", "unit_text"):
            claimed.extend(_claimed_strings(value.get(key)))
        return claimed
    return []


def _missing_claims(value: Any, haystack: str) -> list[str]:
    """Return claims with no faithful printed representation in ``haystack``.

    A number can have several equivalent label spellings (``5000`` and
    ``5,000``). Those are alternatives, not separate claims: requiring every
    spelling would reject an honest reading merely because the label chose a
    thousands separator.
    """
    if isinstance(value, str):
        return [value] if value and _normalize(value) not in haystack else []
    if isinstance(value, bool) or value is None:
        return []
    if isinstance(value, (int, float)):
        variants = [text for text in _claimed_strings(value) if text]
        return [] if any(_normalize(text) in haystack for text in variants) else variants[:1]
    if isinstance(value, Mapping):
        missing: list[str] = []
        for key in ("value", "unit_text"):
            missing.extend(_missing_claims(value.get(key), haystack))
        return missing
    return []


def verify_grounding(
    draft: Mapping[str, Any], pages: Sequence[Any]
) -> GroundingReport:
    """Locate every read field in the photograph its source names."""
    by_photo = {
        getattr(page, "photo_id", None): (getattr(page, "input_id", None), _page_text(page))
        for page in pages
    }
    results: list[FieldGrounding] = []

    for path, field in _iter_fields(draft):
        if field.get("status") not in {"read", "partial"}:
            continue  # Nothing was claimed, so there is nothing to locate.
        sources = field.get("sources") or []
        if not sources:
            results.append(FieldGrounding(path, False, "no source cited"))
            continue
        source = sources[0] if isinstance(sources[0], Mapping) else {}
        photo_id = source.get("photo_id")
        page_context = by_photo.get(photo_id)
        if page_context is None:
            results.append(FieldGrounding(
                path, False, "cites a photograph that was not read", photo_id))
            continue
        input_id = source.get("input_id")
        page_input_id, haystack = page_context
        if input_id != page_input_id:
            results.append(FieldGrounding(
                path, False, "cited input does not belong to the photograph", photo_id))
            continue

        supporting = _normalize(str(source.get("supporting_text") or ""))
        if supporting and supporting not in haystack:
            results.append(FieldGrounding(
                path, False, "the quoted text is not in the photograph", photo_id))
            continue

        missing = _missing_claims(field.get("value"), haystack)
        # A number is the expensive thing to get wrong. Requiring only that
        # *something* claimed was found lets an invented dose pass whenever its
        # unit happens to be printed, which is always — so every digit-bearing
        # claim has to be located on its own.
        numeric_missing = [piece for piece in missing if _DIGITS.search(piece)]
        if numeric_missing:
            results.append(FieldGrounding(
                path, False,
                f"value not found in the photograph: {numeric_missing[0][:40]}",
                photo_id))
            continue
        # Numeric spelling variants are already resolved by _missing_claims.
        # Every remaining component must be present, including the unit: a
        # printed number cannot lend support to an unprinted unit.
        if missing:
            results.append(FieldGrounding(
                path, False, f"value not found in the photograph: {missing[0][:40]}",
                photo_id))
            continue
        results.append(FieldGrounding(path, True, "found in the photograph", photo_id))

    return GroundingReport(fields=tuple(results))
