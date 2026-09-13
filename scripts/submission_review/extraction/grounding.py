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
import math
import unicodedata
from dataclasses import dataclass
from collections import Counter
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
    rows: tuple[dict[str, Any], ...] = ()

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
            "rows": list(self.rows),
            "region_coordinate_space": "orientation_corrected_original",
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
    draft: Mapping[str, Any], pages: Sequence[Any], *, prepared_inputs: Sequence[Any] = ()
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

    return GroundingReport(fields=tuple(results), rows=tuple(_verify_rows(draft, pages, prepared_inputs)))


def _valid_box(line: Any, dimensions: tuple[int, int] | None) -> bool:
    values = [getattr(line, key, None) for key in ("left", "top", "right", "bottom")]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        return False
    left, top, right, bottom = values
    return (0 <= left < right and 0 <= top < bottom
            and (dimensions is None or (right <= dimensions[0] and bottom <= dimensions[1])))


def _original_region(band: Sequence[Any], prepared: Any, page: Any = None) -> dict[str, float] | None:
    # Only preparation's recorded integer pixel window proves this transform.
    size = getattr(prepared, "prepared_size", None)
    original = getattr(prepared, "original_size", None)
    window = getattr(prepared, "pixel_crop", None)
    if not size or not original or not window or any(v <= 0 for v in (*size, *original)):
        return None
    left, top, right, bottom = window
    if not (0 <= left < right <= original[0] and 0 <= top < bottom <= original[1]):
        return None
    x1, y1 = min(line.left for line in band), min(line.top for line in band)
    x2, y2 = max(line.right for line in band), max(line.bottom for line in band)
    if page is not None:
        try:
            x1, y1, x2, y2 = page.input_box(x1, y1, x2, y2)
        except ValueError:
            return None
    x = left + x1 / size[0] * (right - left)
    y = top + y1 / size[1] * (bottom - top)
    x2 = left + x2 / size[0] * (right - left)
    y2 = top + y2 / size[1] * (bottom - top)
    return {"x": x / original[0], "y": y / original[1],
            "w": (x2 - x) / original[0], "h": (y2 - y) / original[1]}


def _verify_rows(draft, pages, prepared_inputs):
    # Imported here because the adapter imports the extractor boundary.
    from .adapters.ocr_adapter import (
        _rows_from_lines, _AMOUNT, _PERCENT, _AMBIGUOUS_THOUSANDS, _standalone_amount,
        _BARE_NUMBER, _clean,
    )

    name_claims = Counter()
    for row in draft.get("ingredient_rows") or []:
        if not isinstance(row, Mapping):
            continue
        name = row.get("display_name") or {}
        if not isinstance(name.get("value"), str):
            continue
        name_claims.update({
            (_normalize(name["value"]), source.get("photo_id"), source.get("input_id"))
            for source in name.get("sources") or [] if isinstance(source, Mapping)
        })

    for index, row in enumerate(draft.get("ingredient_rows") or []):
        result = {"row_index": index, "status": "check_this", "reason": "row association could not be established",
                  "photo_id": None, "input_id": None, "region": None}
        if not isinstance(row, Mapping):
            yield result
            continue
        name, amount = row.get("display_name") or {}, row.get("amount") or {}
        if name.get("status") not in {"read", "partial"} or amount.get("status") not in {"read", "partial"}:
            result.update(status="not_checked", reason="a readable name, amount and unit are required")
            yield result
            continue
        sources = [source for field in (name, amount) for source in (field.get("sources") or [])]
        identities = {(s.get("photo_id"), s.get("input_id")) for s in sources if isinstance(s, Mapping)}
        if len(identities) == 1:
            result["photo_id"], result["input_id"] = next(iter(identities))
        if (not name.get("sources") or not amount.get("sources") or len(identities) != 1
                or any(not isinstance(s, Mapping) for s in sources)):
            result["reason"] = "name and amount sources disagree or are missing"
            yield result
            continue
        matching = [p for p in pages if (p.photo_id, p.input_id) == next(iter(identities))]
        if len(matching) != 1:
            result["status"] = "not_checked" if not matching else "check_this"
            result["reason"] = ("cited photograph/input is unavailable" if not matching
                                else "cited photograph/input is ambiguous")
            yield result
            continue
        page = matching[0]
        prepared_matches = [p for p in prepared_inputs if (p.photo_id, p.input_id) == (page.photo_id, page.input_id)]
        prepared = prepared_matches[0] if len(prepared_matches) == 1 else None
        size = getattr(prepared, "prepared_size", None)
        expected_size = size[::-1] if size and page.rotation_degrees in (90, 270) else size
        if (page.rotation_degrees not in (0, 90, 180, 270)
                or (page.image_size is not None and expected_size is not None
                    and page.image_size != expected_size)):
            result.update(status="not_checked", reason="OCR orientation geometry is invalid")
            yield result
            continue
        size = page.image_size or expected_size
        if not page.lines or any(not _valid_box(line, size) for line in page.lines):
            result.update(status="not_checked", reason="OCR geometry is missing or invalid")
            yield result
            continue
        if row.get("is_blend_header") or row.get("parent_index") is not None:
            result["reason"] = "blend hierarchy requires review"
            yield result
            continue
        value = amount.get("value")
        if not isinstance(value, Mapping) or not isinstance(name.get("value"), str):
            result["reason"] = "a readable name, amount and unit are required"
            yield result
            continue
        # The shared grouper splits dense rows by their nearest amount anchor.
        # That is useful for assembly but cannot prove ownership when a tall
        # name box overlaps two doses. Preserve this ambiguity before splitting.
        numeric_lines = [
            line for line in page.lines
            if (lambda text: _standalone_amount(text) or _PERCENT.fullmatch(text)
                or _BARE_NUMBER.fullmatch(text))(_clean(line.text).rstrip("*†‡ "))
        ]
        # Use the same anchor geometry as assembly, including a dose whose
        # unit OCR lost. Amount and %DV at the same height are one anchor.
        anchor_bands = _rows_from_lines(numeric_lines)
        ambiguous_name_boxes = {
            id(line) for line in page.lines if line not in numeric_lines
            and sum(any(min(line.bottom, anchor.bottom) > max(line.top, anchor.top)
                        for anchor in band) for band in anchor_bands) > 1
        }
        candidates = []
        for band in _rows_from_lines(page.lines):
            text = " ".join(line.text for line in sorted(band, key=lambda line: (line.top, line.left)))
            doses = list(_AMOUNT.finditer(text))
            # Exact whole-name comparison prevents a substring lending support
            # to a different ingredient. All doses in the group count, even if equal.
            stripped = _PERCENT.sub("", _AMOUNT.sub("", text)).strip(" *†‡")
            if _normalize(stripped) == _normalize(name["value"]):
                candidates.append((band, text, doses))
        if len(candidates) != 1:
            result["reason"] = "ingredient row is absent, repeated, or ambiguous"
            yield result
            continue
        band, text, doses = candidates[0]
        result["region"] = _original_region(band, prepared, page)
        if name_claims[(_normalize(name["value"]), page.photo_id, page.input_id)] > 1:
            result["reason"] = "multiple machine rows claim the same printed ingredient occurrence"
            yield result
            continue
        if any(id(line) in ambiguous_name_boxes for line in band):
            result["reason"] = "name geometry overlaps multiple amounts; row ownership is ambiguous"
            yield result
            continue
        if len(doses) != 1 or _AMBIGUOUS_THOUSANDS.search(text):
            result["reason"] = "multiple or ambiguous amounts in the row"
            yield result
            continue
        dose = doses[0]
        # Reject parser suffix matches such as 500 in 1500, negative doses,
        # or a decimal fragment. Unit equivalence never converts quantities.
        boundary_bad = dose.start() > 0 and text[dose.start() - 1] in "0123456789.,+-"
        number = value.get("value")
        matches = (not boundary_bad and isinstance(number, (int, float)) and not isinstance(number, bool)
                   and math.isfinite(number) and float(dose.group("value").replace(",", "")) == number
                   and isinstance(value.get("unit_text"), str)
                   and _normalize(dose.group("unit")) == _normalize(value["unit_text"]))
        if not matches:
            result["reason"] = "the row amount or unit does not match"
        elif any(s.get("supporting_text") and _normalize(str(s["supporting_text"])) not in _normalize(text)
                 and _normalize(str(s["supporting_text"])) != _normalize(name["value"]) for s in sources):
            result["reason"] = "source quotes disagree with the associated row"
        else:
            result.update(status="supported", reason="exact name, amount and unit found in one unambiguous OCR row")
        yield result
