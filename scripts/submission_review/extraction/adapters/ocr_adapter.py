"""A deterministic reading of a Supplement Facts panel from OCR geometry.

This is the second extraction candidate, and its whole value is that it fails
differently from a vision model. It never asks anything to *understand* the
label: it takes recognised text with bounding boxes and reconstructs the panel
from where the words physically sit — rows from vertical bands, the amount from
the right-hand column, blend children from indentation.

Two consequences worth stating, because they are the reason for building it.

*Independence has to be real.* Agreement between two readers is only evidence
if they can fail differently. A rule engine parsing text that a vision model
also parsed would share every OCR mistake, and their agreement would mean
nothing. This path goes image -> OCR -> geometry -> rows, sharing no
intermediate representation with a model adapter. What both still share is the
prepared bytes from photo_prep, which is a genuine common-mode risk and is
tested rather than assumed.

*Determinism is a feature here.* The same bytes give the same answer every
time, which is what a frozen benchmark needs and what a sampled model cannot
promise.

The OCR engine itself is injected. Nothing in this module downloads or runs a
model, so the assembly rules can be tested exactly, and swapping engines never
changes the contract.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

from ..envelope import SCHEMA_VERSION, validate_label_draft_v1
from ..extractor import (
    ExtractionConfig,
    ExtractionError,
    ExtractionResult,
    PreparedBundle,
    Usage,
)

#: Bumped whenever an assembly rule changes: this is the immutable thing that
#: decides the output, so it plays the part a prompt version plays for a model.
#: Pixels a child must be indented past its header before nesting is
#: believed, whatever the text height says.
_MIN_INDENT_STEP = 8.0

RULES_VERSION = "ocr-geometry-v12"
PROVIDER = "ocr"

#: Units as labels print them. Case is preserved in the draft; matching is not.
_UNITS = (
    "mcg DFE", "mcg RAE", "mg NE", "billion CFU", "million CFU",
    "billion AFU", "million AFU",
    "mcg", "mg", "g", "IU", "CFU", "AFU", "mL", "L", "kcal",
)


def _spaced(unit: str) -> str:
    """Match a printed unit whether or not the engine kept its spaces.

    Real OCR output collapses whitespace unpredictably: RapidOCR returns
    "400mcgDFE" for the same panel where it returns "500 mg". A unit pattern
    that assumes spaces silently reads nothing on half the rows.
    """
    return r"\s*".join(re.escape(part) for part in unit.split())


_UNIT_PATTERN = "|".join(
    sorted((_spaced(u) for u in _UNITS), key=len, reverse=True))
#: "500 mg", "1,000 IU", "2.5 mcg DFE". A bare number is not an amount.
_AMOUNT = re.compile(
    rf"(?P<value>\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*"
    rf"(?P<unit>{_UNIT_PATTERN})\b",
    re.IGNORECASE,
)
_PERCENT = re.compile(r"(?P<value>\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*%")
#: A number the dose column prints on its own, with or without its unit.
#: It marks where a printed row sits even when OCR has lost the unit.
_BARE_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
#: OCR reads a thousands comma as a decimal point: "1,000 mg" arrives as
#: "1.000 mg" and would be read as 1 mg. Of 98,377 printed doses in the
#: catalog only 34 are a 1-999 value with exactly three decimals, against
#: 5,746 written with a thousands comma, so such a reading is refused rather
#: than guessed in either direction. A leading zero ("0.025") is unambiguous.
_AMBIGUOUS_THOUSANDS = re.compile(r"(?<![\d,.])[1-9]\d{0,2}\.\d{3}(?!\d)")


def _misread_dose(text: str) -> bool:
    """One or two letters glued to the front of a complete dose.

    OCR reads "10mcg" as "T0mcg"; the parser skipped the letter and returned
    0 mcg (DSLD 745). A name glued to its dose ("Chromium10mcg") has a longer
    prefix and is left alone.
    """
    match = re.fullmatch(r"([A-Za-z]{1,2})(\S.*)", text)
    return bool(match and _AMOUNT.fullmatch(match.group(2)))
#: Rows a panel prints that are not ingredients.
#: Panel furniture, matched with optional spacing for the same reason.
_NOT_A_ROW = re.compile(
    # "Amount per ..." and "Servings per ..." open no ingredient name, so they
    # are headings however OCR spaces them: "AmountPerTablet",
    # "ServingsPerContainer100". A word boundary after "per" missed both.
    r"^\s*(?:(?:supplement\s*facts|%\s*d\s*v|%?\s*daily\s*value"
    r"|serving\s*size|ingredients?)\b|amount\s*per|servings?\s*per)",
    re.IGNORECASE,
)
_OTHER_INGREDIENTS = re.compile(r"^\s*other\s+ingredients?\b", re.IGNORECASE)
_FOOTNOTE_START = re.compile(r"^\s*\+\s*(?:provides|[t†‡])", re.IGNORECASE)
_FACTS_HEADING = re.compile(r"\s*supplement\s*facts\s*", re.IGNORECASE)
_PANEL_END = re.compile(
    r"^\s*(?:other\s*ingredients?\b|warnings?\b|directions?\b|"
    r"[^\w]*daily\s*value\s*not\s*established|[^\w]*percent\s*daily\s*values?)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class OcrLine:
    """One recognised line and where it sits, in pixels from the top left."""

    text: str
    left: float
    top: float
    right: float
    bottom: float
    confidence: float | None = None

    @property
    def height(self) -> float:
        return max(0.0, self.bottom - self.top)

    @property
    def middle(self) -> float:
        return (self.top + self.bottom) / 2


@dataclass(frozen=True)
class OcrPage:
    """Everything one engine read from one photograph."""

    photo_id: str
    input_id: str
    lines: tuple[OcrLine, ...] = field(default_factory=tuple)


class OcrReader(Protocol):
    """The only thing an engine has to offer. No engine lives in this module."""

    def read(self, data: bytes, *, photo_id: str, input_id: str) -> OcrPage:
        """Return recognised lines with geometry, or raise."""


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _standalone_amount(text: str) -> bool:
    """A complete dose-column box, optionally enclosed in parentheses.

    Labels can print a blend child's dose as '(600 mg)'. Only unwrap a whole
    pair: '(from 125 mg)' and constituent equations remain formulation text,
    never row anchors. Unit recognition stays with the existing amount parser.
    """
    text = _clean(text).rstrip("*†‡ ")
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    return _AMOUNT.fullmatch(text) is not None


def _rows_from_lines(lines: Sequence[OcrLine]) -> list[list[OcrLine]]:
    """Group lines into printed rows by vertical overlap.

    A Facts panel prints a row as several boxes at the same height: the name on
    the left, the amount on the right. Grouping by band is what recovers the
    association a flat text dump destroys.
    """
    # Panel headings are never rows, and serving size is read from the page
    # separately. Left in, a heading chains into the rows below it and a band
    # that begins with one is dropped whole, taking real rows with it.
    lines = [line for line in lines
             if not (_NOT_A_ROW.match(_clean(line.text)) or _SERVING_SIZE.match(_clean(line.text)))]
    ordered = sorted(lines, key=lambda line: (line.middle, line.left))

    def same_band(left: OcrLine, right: OcrLine) -> bool:
        # A wrapped label line can overlap the amount box rather than the
        # first name box. Treat overlap as a connected component so that the
        # amount bridges the whole printed row even when OCR tie-breaks put it
        # before the final wrapped line.
        vertical_overlap = min(left.bottom, right.bottom) - max(left.top, right.top)
        tolerance = max(left.height, right.height) * 0.5
        return vertical_overlap >= 0 or abs(left.middle - right.middle) <= tolerance

    # Build connected vertical components rather than comparing only with the
    # last line. This handles a row whose boxes overlap as A→C and B→C but not
    # A→B (common when a name wraps beside a right-hand amount).
    rows: list[list[OcrLine]] = []
    for line in ordered:
        matches = [
            band for band in rows
            if any(same_band(line, member) for member in band)
        ]
        if not matches:
            rows.append([line])
            continue
        target = matches[0]
        target.append(line)
        for other in matches[1:]:
            target.extend(other)
            rows.remove(other)

    separated: list[list[OcrLine]] = []
    for band in rows:
        # Dense print has slightly overlapping boxes on adjacent rows. Distinct
        # amount-only boxes anchor those rows; overlap alone must not collapse
        # two doses. Keep the connected-component behavior for wrapped names
        # sharing one amount, and do not use parenthetical form doses as anchors.
        #
        # A row is anchored by any number the right-hand columns print for it,
        # not only a dose with its unit: OCR loses units ("5 g" read as "59")
        # and some rows print only a %DV. Anchoring on unit-bearing doses
        # alone sent every row above the first such dose into that dose's
        # row. Numbers at the same height are one printed row.
        numbers = sorted(
            (line for line in band if (lambda text: _standalone_amount(text)
                                       or _PERCENT.fullmatch(text)
                                       or _BARE_NUMBER.fullmatch(text))(
                _clean(line.text).rstrip("*†‡ "))),
            key=lambda line: line.middle,
        )
        anchors: list[list[OcrLine]] = []
        for line in numbers:
            last = anchors[-1][-1] if anchors else None
            if last is not None and line.middle - last.middle <= min(line.height, last.height) * 0.5:
                anchors[-1].append(line)
            else:
                anchors.append([line])
        centres = [sum(item.middle for item in group) / len(group) for group in anchors]
        if len(centres) > 1:
            buckets: list[list[OcrLine]] = [[] for _ in centres]
            for line in band:
                index = min(range(len(centres)), key=lambda i: abs(line.middle - centres[i]))
                buckets[index].append(line)
            separated.extend(bucket for bucket in buckets if bucket)
        else:
            separated.append(band)
    rows = separated
    for band in rows:
        band.sort(key=lambda line: (line.middle, line.left))
    rows.sort(key=lambda band: min(line.middle for line in band))
    return rows


def _source(page: OcrPage, supporting: str) -> list[dict[str, str]]:
    return [{
        "input_id": page.input_id,
        "photo_id": page.photo_id,
        "supporting_text": supporting[:280],
    }]


def _read_field(page: OcrPage, value: Any, supporting: str) -> dict[str, Any]:
    """A field this engine actually read, cited to the line it read it from."""
    return {
        "value": value,
        "status": "read",
        # A rule engine has no opinion about its own certainty, and inventing
        # one would be the very number that must never authorize an approval.
        "confidence": None,
        "sources": _source(page, supporting),
    }


def _unread_field(status: str = "unreadable") -> dict[str, Any]:
    return {"value": None, "status": status, "confidence": None, "sources": []}


def _parse_amount(text: str) -> tuple[dict[str, Any], str] | None:
    match = _AMOUNT.search(text)
    if match is None:
        return None
    value = float(match.group("value").replace(",", ""))
    # The printed unit crosses exactly as printed; normalising here would throw
    # away the only record of what the label said.
    return {"value": value, "unit_text": match.group("unit")}, match.group(0)


def _parse_percent(text: str) -> tuple[float, str] | None:
    match = _PERCENT.search(text)
    if match is None:
        return None
    return float(match.group("value").replace(",", "")), match.group(0)


def _row_indent(band: Sequence[OcrLine]) -> float:
    return min(line.left for line in band)


def _ingredient_rows(page: OcrPage, rows: Sequence[Sequence[OcrLine]]) -> list[dict[str, Any]]:
    """Rows as the panel prints them, including the ones that cannot be read.

    Indentation carries the blend structure: a child of a proprietary blend is
    printed further right than its header. That is the only signal a panel
    gives, and it is geometry, which is why this adapter can see it at all.
    """
    built: list[dict[str, Any]] = []
    indents: list[float] = []
    footer_started = False
    for band in rows:
        joined = _clean(" ".join(line.text for line in band))
        if not joined or _NOT_A_ROW.match(joined) or _SERVING_SIZE.match(joined):
            continue
        if _OTHER_INGREDIENTS.match(joined):
            # This disclosure terminates the facts panel. Subsequent OCR lines
            # are its wrapped contents, not additional active ingredients.
            break
        if footer_started:
            continue
        if _FOOTNOTE_START.match(joined):
            # Footnote text can wrap across many bands; once it starts, none of
            # those lines belong in the ingredient table.
            footer_started = True
            continue

        amount_lines = [line for line in band if _parse_amount(_clean(line.text))]
        # A bare number standing apart in the dose column is a dose whose unit
        # OCR lost ("5 g" read as "59"), not part of the ingredient's name. A
        # number right beside the name ("Vitamin B" | "12") is still the name.
        text_right = max((line.right for line in band
                          if not _BARE_NUMBER.fullmatch(_clean(line.text).rstrip("*†‡ "))
                          and line not in amount_lines
                          and not _PERCENT.fullmatch(_clean(line.text))), default=None)
        lost_units = [
            line for line in band
            if _BARE_NUMBER.fullmatch(_clean(line.text).rstrip("*†‡ "))
            and (text_right is None or line.left - text_right > line.height * 2)
        ]
        # A name always prints left of its dose. A name box starting right of
        # the dose column belongs to a second column of the panel (DSLD 778),
        # and joined here it would carry this row's dose to another
        # ingredient. Only a box that is a dose and nothing else marks the
        # column: a box packing name and dose together would mark it at the
        # name's own edge and throw the rest of the name away.
        dose_column = min((line.left for line in amount_lines
                           if _standalone_amount(line.text)), default=None)
        name_lines = [
            line for line in band
            if line not in amount_lines and line not in lost_units
            and not _PERCENT.fullmatch(_clean(line.text))
            and (dose_column is None or line.left < dose_column)
        ]
        # Left-edge sorting is useful for pairing a single row, but wrapped
        # names can have a one-pixel horizontal jitter. Restore their printed
        # reading order before joining them.
        name_lines.sort(key=lambda line: (line.top, line.left))
        name_text = _clean(" ".join(line.text for line in name_lines))
        amount_text = _clean(" ".join(line.text for line in amount_lines)) or joined
        if not name_text and amount_lines:
            # A compact OCR box may contain both the name and amount. Remove
            # the measured portion rather than calling the whole line an
            # ingredient name.
            match = _AMOUNT.search(amount_text)
            name_text = _clean((amount_text[:match.start()] + amount_text[match.end():]) if match else amount_text)
            if _PERCENT.fullmatch(name_text):
                name_text = ""
        # The row's dose is a box that is only a dose. A number inside a
        # parenthetical is a constituent ("(5% Hydrastine = 6.25 mg)"), and
        # on a dense panel the one above can share this band: taking the
        # first number in the joined text read 6.25 mg for a 25 mg row.
        pure_doses = [line for line in amount_lines
                      if _standalone_amount(line.text)]
        misread = [line for line in amount_lines
                   if _misread_dose(_clean(line.text).rstrip("*†‡ "))]
        dose_text = (_clean(" ".join(line.text for line in pure_doses))
                     if pure_doses else amount_text)
        amount = None if (misread and not pure_doses) else _parse_amount(dose_text)
        percent = _parse_percent(amount_text)
        if percent is None:
            separate_percent = [line for line in band if _PERCENT.fullmatch(_clean(line.text))]
            if len(separate_percent) == 1:
                percent = _parse_percent(separate_percent[0].text)
        # Applied here, to OCR text, and not in _parse_amount itself: that
        # parser also reads typed DSLD transcriptions, where "1.575 g" is a
        # real 1.575 g and there is no comma for OCR to have misread.
        # Multiple dose boxes can be alternate serving columns or adjacent
        # ingredients. Geometry has not resolved that basis; even equal values
        # do not establish which column belongs to this row.
        ambiguous_amount = len(pure_doses) > 1 or (
            amount is not None and bool(_AMBIGUOUS_THOUSANDS.search(amount[1])))
        if ambiguous_amount:
            amount = None
        if amount is None and (lost_units or misread):
            # A dose is printed here; it just cannot be read as one.
            ambiguous_amount = True
        ambiguous_percent = percent is not None and bool(_AMBIGUOUS_THOUSANDS.search(percent[1]))
        if ambiguous_percent:
            percent = None
        # A line that is only a heading with no number is still a printed row
        # (a blend header), so it is kept rather than dropped.
        if not name_text and amount is None and not ambiguous_amount:
            continue

        row: dict[str, Any] = {
            "display_name": _read_field(page, name_text, name_text) if name_text else _unread_field(),
            "amount": None,
            "percent_dv": None,
            "form_text": None,
            "parent_index": None,
            "is_blend_header": False,
            "status": "read" if name_text else "partial",
        }
        if amount is not None:
            row["amount"] = _read_field(page, amount[0], amount[1])
        else:
            # Printed but ambiguous is unreadable; nothing printed is absent.
            row["amount"] = _unread_field("unreadable" if ambiguous_amount else "not_present")
            row["status"] = "partial"
        if percent is not None:
            row["percent_dv"] = _read_field(page, percent[0], percent[1])
        elif ambiguous_percent:
            row["percent_dv"] = _unread_field()

        indent = _row_indent(band)
        # A real panel indents a blend child by roughly a character width;
        # OCR returns the left edge of same-level rows jittering by a pixel or
        # two. A tolerance below that jitter reads ordinary rows as children of
        # whatever preceded them, so the step has to be a visible one.
        step = max(_MIN_INDENT_STEP, max(line.height for line in band) * 0.6)
        parent = None
        for index in range(len(built) - 1, -1, -1):
            # The nearest earlier row printed meaningfully further left is the
            # header. Equal indent, or a pixel of noise, means a sibling.
            if indents[index] + step <= indent:
                parent = index
                break
        if parent is not None:
            row["parent_index"] = parent
            built[parent]["is_blend_header"] = True
        built.append(row)
        indents.append(indent)
    return built


def _largest_text(page: OcrPage) -> tuple[str, str] | None:
    """The tallest printed line, which on a front label is the brand or name."""
    candidates = [line for line in page.lines if _clean(line.text)]
    if not candidates:
        return None
    tallest = max(candidates, key=lambda line: (line.height, -line.top))
    text = _clean(tallest.text)
    return (text, text) if text else None


def _find_line(page: OcrPage, pattern: re.Pattern[str]) -> tuple[str, str] | None:
    for line in page.lines:
        text = _clean(line.text)
        match = pattern.search(text)
        if match:
            return match.group("value").strip(), text
    return None


_SERVING_SIZE = re.compile(r"serving\s*size[:\s]*(?P<value>.+)", re.IGNORECASE)
_SERVINGS_PER = re.compile(
    # Package words only. "Servings Per Bottle" is a container count; "Servings
    # Per Day" is not, and reading it as one puts a wrong value on a gated field.
    r"servings?\s*per\s*(?:container|bottle|package|pack|packet|box|bag|jar"
    r"|tube|canister|pouch|tub|can)[:\s]+(?P<value>[\w.,/ ]+)", re.IGNORECASE)


class OcrLabelAdapter:
    """Assembles a label_draft_v1 from OCR geometry, and nothing else."""

    def __init__(self, reader: OcrReader) -> None:
        self._reader = reader

    @property
    def prompt_sha256(self) -> str:
        """The immutable rules this reading is attributable to.

        A model binds its answers to a prompt; this binds them to the assembly
        rules, so a benchmarked configuration cannot silently become a
        different one.
        """
        return hashlib.sha256(
            f"{PROVIDER}:{RULES_VERSION}:{_UNIT_PATTERN}".encode()
        ).hexdigest()

    def extract(
        self, bundle: PreparedBundle, config: ExtractionConfig
    ) -> ExtractionResult:
        if config.provider != PROVIDER or config.prompt_version != RULES_VERSION:
            raise ExtractionError(
                "provider_unavailable", "unsupported OCR configuration", usage=Usage())
        try:
            pages = [
                self._reader.read(photo.data, photo_id=photo.photo_id,
                                  input_id=photo.input_id)
                for photo in bundle.photos
            ]
        except ExtractionError:
            raise
        except Exception as error:  # noqa: BLE001 - engines are a boundary
            raise ExtractionError(
                "model_failure", "the OCR engine failed", usage=Usage()) from error

        by_photo = {page.photo_id: page for page in pages}
        facts = self._panel(bundle, by_photo)
        front = self._front(bundle, by_photo) or facts

        rows: list[dict[str, Any]] = []
        serving_size: dict[str, Any] = _unread_field()
        servings_per: dict[str, Any] = _unread_field()
        if facts is not None:
            bands = _rows_from_lines(facts.lines)
            rows = _ingredient_rows(facts, bands)
            found = _find_line(facts, _SERVING_SIZE)
            if found:
                serving_size = _read_field(facts, found[0], found[1])
            found = _find_line(facts, _SERVINGS_PER)
            if found:
                servings_per = _read_field(facts, found[0], found[1])

        identity_source = _largest_text(front) if front is not None else None
        brand = (_read_field(front, identity_source[0], identity_source[1])
                 if front is not None and identity_source else _unread_field())

        draft = {
            "schema_version": SCHEMA_VERSION,
            "draft_origin": "model",
            "provider": config.provider,
            "model": config.model,
            "prompt_version": config.prompt_version,
            "evidence_revision": bundle.evidence_revision,
            "evidence_snapshot": bundle.snapshot,
            "sent_inputs": [photo.as_sent_input() for photo in bundle.photos],
            "photo_roles": [
                {
                    "photo_id": photo.photo_id,
                    "declared": list(photo.categories),
                    # Geometry cannot say what a photograph is *of*; claiming
                    # otherwise would be the kind of guess this adapter exists
                    # to avoid.
                    "inferred": [],
                    "readability": "ok" if by_photo[photo.photo_id].lines else "unreadable",
                    "issues": [],
                }
                for photo in bundle.photos
            ],
            "identity": {
                "brand": brand,
                # A front label prints the brand and the product name in the
                # same style; separating them is semantics, not geometry.
                "product_name": _unread_field(),
                "barcode_digits_seen": None,
            },
            "serving": {
                "size": serving_size,
                "servings_per_container": servings_per,
                "basis_text": _unread_field(),
                "amount": None,
            },
            "ingredient_rows": rows,
            "other_ingredients": {"text": None, "disclosure_hint": "unknown"},
            "statements": [],
            "discrepancies": [],
            # No rows read means no reading happened, whatever the engine
            # returned. Saying so is more useful than an empty panel.
            "abstained": not rows,
            "abstain_reason": None if rows else "no ingredient rows were readable",
            "overall_confidence": None,
        }
        return ExtractionResult(validate_label_draft_v1(draft), Usage())

    @staticmethod
    def _panel(bundle: PreparedBundle, pages: dict[str, OcrPage]) -> OcrPage | None:
        headings = [
            (page, line) for page in pages.values() for line in page.lines
            if _FACTS_HEADING.fullmatch(line.text)
        ]
        if len(headings) > 1:
            # Multiple panels may be different editions. Do not pick one or
            # combine their doses merely because a slot was tagged Facts.
            return None
        if headings:
            page, heading = headings[0]
            # Retain original coordinates and input provenance; this selects
            # OCR boxes, not a second image-preparation pipeline. The heading
            # anchors a bounded column, with room for a separate amount column.
            left = heading.left - heading.height * 0.5
            right = heading.right + max(
                heading.height * 6, (heading.right - heading.left) * 0.75)
            lines = [line for line in page.lines
                     if line.top >= heading.top and line.left >= left
                     and line.right <= right]
            end = min((line.top for line in lines if _PANEL_END.match(line.text)),
                      default=float("inf"))
            return OcrPage(page.photo_id, page.input_id,
                           tuple(line for line in lines if line.top < end))
        # A tightly cropped, explicitly tagged panel may lack its heading.
        # Untagged marketing text containing a dose is not enough evidence.
        declared = [pages[photo.photo_id] for photo in bundle.photos
                    if "supplement_facts" in photo.categories
                    and photo.photo_id in pages]
        return declared[0] if len(declared) == 1 else None

    @staticmethod
    def _front(bundle: PreparedBundle, pages: dict[str, OcrPage]) -> OcrPage | None:
        for photo in bundle.photos:
            if "front_identity" in photo.categories:
                return pages.get(photo.photo_id)
        return None
