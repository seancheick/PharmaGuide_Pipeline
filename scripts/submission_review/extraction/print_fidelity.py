"""Measure what the shared preparation step costs genuine fine print.

Every candidate extractor reads the *same* prepared bytes. That makes
`photo_prep` a common-mode surface: if preparation has already destroyed the
6pt type on a Supplement Facts panel, both candidates fail on the same rows,
they agree with each other, and the benchmark reads that agreement as
confirmation. No amount of comparing readers can reveal it, because neither
reader can see what preparation removed.

So this module measures the one thing that is invisible from inside the
comparison: legibility of the *prepared* bytes against legibility of the same
render before preparation. It renders a Supplement Facts panel at a stated
point size, places it in a frame of a stated capture geometry, and reads both
copies with the same engine.

It calls the real `prepare_bundle`. A second copy of the resize-and-encode
rules here would measure a fiction.

    python3 -m scripts.submission_review.extraction.print_fidelity --json
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from .benchmark import _norm
from .extractor import EvidenceBundle, EvidencePhoto
from .photo_prep import prepare_bundle

#: The panel's width is not assumed: it is derived from this text set at the
#: requested point size, so the longest declaration fits instead of running
#: off the edge and being scored as a preparation loss. At 6pt it lands near
#: 2.5 inches, which is a 60-count bottle.
#: Fine print on a supplement label. 6pt is the floor the FDA's type-size
#: rules allow for the Facts panel on a small container (21 CFR 101.36).
FINE_PRINT_POINTS = 6.0

#: Common capture geometries, as (label, width, height). Portrait, because
#: that is how a bottle is held and how the Facts panel is shaped.
FRAMES: dict[str, tuple[int, int]] = {
    "phone-12mp": (3024, 4032),
    "phone-12mp-samsung": (3000, 4000),
    "camera-24mp": (4000, 6000),
    "phone-48mp": (6048, 8064),
}

#: The device step, mirroring `_sanitizeProductSubmissionPhoto` in the app's
#: lib/services/product_submission_photo_service.dart. Every submission photo
#: is already re-encoded on the phone before the server sees a byte, so a
#: measurement that starts at the server measures the wrong chain. These two
#: numbers are a model of that Dart call and must be changed with it.
DEVICE_SHORT_EDGE = 2400
DEVICE_QUALITY = 90

#: How much of the frame's width the panel spans. A user holding the bottle
#: close fills the frame; one photographing the whole bottle does not.
FRACTIONS: tuple[float, ...] = (0.25, 0.35, 0.50, 0.70, 0.90)

PANEL_LINES: tuple[str, ...] = (
    "Serving Size 2 Capsules",
    "Servings Per Container 30",
    "Amount Per Serving  % Daily Value",
    "Vitamin D3 (as cholecalciferol) 25 mcg (1,000 IU) 125%",
    "Vitamin K2 (as menaquinone-7) 90 mcg 75%",
    "Magnesium (as magnesium bisglycinate) 100 mg 24%",
    "Zinc (as zinc picolinate) 15 mg 136%",
    "Selenium (as L-selenomethionine) 55 mcg 100%",
    "Proprietary Herbal Blend 450 mg",
    "Ashwagandha Root Extract (Withania somnifera)",
    "Rhodiola Rosea Root Extract 3% rosavins",
    "Daily Value not established.",
    "Other Ingredients: Microcrystalline cellulose, vegetable",
    "magnesium stearate, silicon dioxide, hypromellose (capsule).",
)
TITLE = "Supplement Facts"
#: Rows whose indentation the reader must not confuse with a top-level row.
_INDENTED = frozenset({9, 10})

_REGULAR_FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
_BOLD_FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

_DIGIT_TOKEN = re.compile(r"[0-9][0-9.,]*\s*(?:mcg|mg|g|iu|cfu|%)?")
_SPACE = re.compile(r"\s+")
#: Words long enough that finding one is evidence of reading, not of luck.
_WORD = re.compile(r"[0-9a-z][0-9a-z.,'-]{2,}")
_PANEL_EMS: float | None = None


class PanelDoesNotFit(ValueError):
    """The requested panel cannot be photographed in the requested frame."""


@dataclass(frozen=True)
class Reading:
    """What one engine recovered from one copy of one render."""

    line_recall: float
    digit_recall: float
    lines_found: int
    lines_expected: int
    digits_found: int
    digits_expected: int
    missing_lines: tuple[str, ...]
    missing_digits: tuple[str, ...]


@dataclass(frozen=True)
class Rung:
    """One capture geometry, read before and after preparation."""

    frame: str
    fraction: float
    pixels_per_inch: float
    point_size: float
    #: Height, in the pixels the server is handed, of one em of the fine
    #: print. This is the number an OCR engine actually experiences, and it
    #: is measured after the phone's own re-encode, not before it.
    em_pixels: float
    capture_edge: int
    server_input_edge: int
    raw_bytes: int
    prepared_bytes: int | None
    prepared_edge: int | None
    resized: bool
    refused: str | None
    before: Reading | None
    after: Reading | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "frame": self.frame,
            "fraction": self.fraction,
            "pixels_per_inch": round(self.pixels_per_inch, 1),
            "point_size": self.point_size,
            "em_pixels": round(self.em_pixels, 2),
            "capture_edge": self.capture_edge,
            "server_input_edge": self.server_input_edge,
            "raw_bytes": self.raw_bytes,
            "prepared_bytes": self.prepared_bytes,
            "prepared_edge": self.prepared_edge,
            "resized": self.resized,
            "refused": self.refused,
            "before": None if self.before is None else vars(self.before),
            "after": None if self.after is None else vars(self.after),
        }


def panel_ems() -> float:
    """Width of the panel in ems of its body type, from real font metrics."""
    global _PANEL_EMS
    if _PANEL_EMS is None:
        from PIL import ImageFont

        reference = 240
        body = ImageFont.truetype(_REGULAR_FONT, reference)
        bold = ImageFont.truetype(_BOLD_FONT, reference)
        title = ImageFont.truetype(_BOLD_FONT, int(reference * 1.7))
        widest = title.getlength(TITLE)
        for index, line in enumerate(PANEL_LINES):
            text = "\u2020 " + line if index == 11 else line
            font = bold if index == 8 else body
            offset = reference * 1.2 if index in _INDENTED else 0.0
            widest = max(widest, offset + font.getlength(text))
        _PANEL_EMS = widest / reference + 2 * 0.9
    return _PANEL_EMS


def render_frame(
    frame: tuple[int, int],
    fraction: float,
    *,
    point_size: float = FINE_PRINT_POINTS,
) -> tuple[bytes, float]:
    """Render the panel at genuine `point_size` inside a capture-sized frame.

    Returns the PNG bytes and the pixels-per-inch of printed label. The type
    is rasterised at its final size — never rendered large and scaled down,
    which would hide exactly the loss this module exists to find.
    """
    from PIL import Image, ImageDraw, ImageFont

    width, height = frame
    panel_px = max(1, int(round(width * fraction)))
    body_px = panel_px / panel_ems()
    ppi = body_px * 72.0 / point_size
    body_px = max(1, int(round(body_px)))
    title_px = max(1, int(round(body_px * 1.7)))

    body = ImageFont.truetype(_REGULAR_FONT, body_px)
    bold = ImageFont.truetype(_BOLD_FONT, body_px)
    title = ImageFont.truetype(_BOLD_FONT, title_px)

    leading = max(1, int(round(body_px * 1.42)))
    margin = max(1, int(round(body_px * 0.9)))
    indent = max(1, int(round(body_px * 1.2)))
    panel_h = margin * 2 + title_px + leading * (len(PANEL_LINES) + 1)

    if panel_h > height:
        # Cropping here would measure a truncated panel and report the missing
        # rows as a preparation loss. The geometry is simply not photographable.
        raise PanelDoesNotFit(
            f"a panel spanning {fraction:.0%} of a {width}x{height} frame "
            f"is {panel_h}px tall"
        )

    canvas = Image.new("RGB", (width, height), (186, 186, 182))
    panel = Image.new("RGB", (panel_px, panel_h), (255, 255, 255))
    draw = ImageDraw.Draw(panel)
    draw.text((margin, margin), TITLE, font=title, fill=(0, 0, 0))
    y = margin + title_px + int(leading * 0.6)
    for index, line in enumerate(PANEL_LINES):
        x = margin + (indent if index in _INDENTED else 0)
        text = "\u2020 " + line if index == 11 else line
        draw.text((x, y), text, font=bold if index == 8 else body, fill=(0, 0, 0))
        y += leading
    draw.rectangle(
        (0, 0, panel_px - 1, panel_h - 1), outline=(0, 0, 0), width=max(1, body_px // 8)
    )
    canvas.paste(panel, ((width - panel_px) // 2, (height - panel_h) // 2))

    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG", optimize=False)
    return buffer.getvalue(), ppi


def device_encode(
    raw: bytes,
    *,
    short_edge: int = DEVICE_SHORT_EDGE,
    quality: int = DEVICE_QUALITY,
) -> bytes:
    """Re-encode the way the phone does before upload.

    Downscale only, preserving aspect, until the short side reaches
    `short_edge`. This is flutter_image_compress's own rule with an equal
    minWidth/minHeight pair, read from both platform implementations rather
    than from its documentation: Android computes
    `max(1, min(w/minW, h/minH))` and truncates, and iOS picks the scale from
    whichever side is proportionally larger and floors, which comes to the
    same thing. Rounding matches theirs, so the pixel counts here are the
    pixel counts a phone uploads.
    """
    from PIL import Image

    with Image.open(io.BytesIO(raw)) as image:
        frame = image.convert("RGB")
        scale = min(frame.width / short_edge, frame.height / short_edge)
        if scale > 1.0:
            frame = frame.resize(
                (int(frame.width / scale), int(frame.height / scale)),
                Image.LANCZOS,
            )
        buffer = io.BytesIO()
        frame.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def prepare(raw: bytes) -> bytes:
    """Run the production preparation over one photo and return what it sent."""
    digest = hashlib.sha256(raw).hexdigest()
    bundle = EvidenceBundle(
        submission_id="print-fidelity",
        evidence_revision=1,
        photos=(EvidencePhoto(photo_id="p1", sha256=digest, categories=("supplement_facts",)),),
    )
    prepared = prepare_bundle(bundle, reader=lambda _photo: raw)
    return prepared.photos[0].data


def _normalize(text: str) -> str:
    # Case and unicode folding belong to the subsystem's one normalizer.
    # What is local here is dropping whitespace entirely: OCR splits and
    # rejoins words at will, and the question is whether the characters
    # survived preparation, not how they were grouped.
    return _SPACE.sub("", _norm(text)).replace("’", "'")


def _digit_tokens(lines: Iterable[str]) -> tuple[str, ...]:
    found: list[str] = []
    for line in lines:
        for match in _DIGIT_TOKEN.finditer(line.casefold()):
            token = _SPACE.sub("", match.group(0)).strip(".,")
            if token and token not in found:
                found.append(token)
    return tuple(found)


def _tokens(line: str) -> tuple[str, ...]:
    """Words worth three characters, plus every number the line prints.

    Numbers are added explicitly because the word pattern would skip "25" and
    "90" as too short to be evidence — and those are the doses. A line is not
    recovered if its dose is not.
    """
    return tuple(_WORD.findall(_norm(line))) + _digit_tokens((line,))


def score(recovered: Sequence[str], expected: Sequence[str] = PANEL_LINES) -> Reading:
    """Score one reading: which printed lines and which numbers came back.

    Matching ignores the order of boxes and tolerates fragments on purpose:
    an engine may return one printed line as three overlapping boxes in any
    order, and that is the row-assembly problem, which belongs to the
    adapter. It does not tolerate reordered characters — "mcg 25" is a
    different reading from "25 mcg". The question here is only whether the
    characters survived preparation.
    """
    blob = _normalize(" ".join(recovered))
    missing_lines = tuple(
        line for line in expected
        if any(_normalize(token) not in blob for token in _tokens(line))
    )
    digits = _digit_tokens(expected)
    missing_digits = tuple(token for token in digits if _normalize(token) not in blob)
    return Reading(
        line_recall=(len(expected) - len(missing_lines)) / len(expected) if expected else 1.0,
        digit_recall=(len(digits) - len(missing_digits)) / len(digits) if digits else 1.0,
        lines_found=len(expected) - len(missing_lines),
        lines_expected=len(expected),
        digits_found=len(digits) - len(missing_digits),
        digits_expected=len(digits),
        missing_lines=missing_lines,
        missing_digits=missing_digits,
    )


def capture_ppi_of(frame: tuple[int, int], fraction: float, point_size: float) -> float:
    """Pixels per printed inch at capture, without rendering anything."""
    return frame[0] * fraction / panel_ems() * 72.0 / point_size


def _read(reader, data: bytes) -> tuple[str, ...]:
    page = reader.read(data, photo_id="p1", input_id="i0")
    return tuple(line.text for line in page.lines)


def measure(
    reader,
    *,
    frame_name: str = "phone-12mp",
    fraction: float = 0.5,
    point_size: float = FINE_PRINT_POINTS,
    on_device: bool = True,
) -> Rung:
    """Read one geometry before and after the server's preparation.

    With `on_device` set, "before" means *after the phone re-encoded it* —
    which is what the server is actually handed, and the only baseline that
    isolates what `photo_prep` itself costs.
    """
    from PIL import Image
    from .extractor import ExtractionError

    frame = FRAMES[frame_name]
    capture_edge = max(frame)
    em_at_capture = frame[0] * fraction / panel_ems()
    try:
        raw, capture_ppi = render_frame(frame, fraction, point_size=point_size)
    except PanelDoesNotFit:
        return Rung(
            frame=frame_name, fraction=fraction, pixels_per_inch=capture_ppi_of(frame, fraction, point_size),
            point_size=point_size, em_pixels=em_at_capture,
            capture_edge=capture_edge, server_input_edge=0, raw_bytes=0,
            prepared_bytes=None, prepared_edge=None, resized=False,
            refused="panel_does_not_fit", before=None, after=None,
        )

    if on_device:
        raw = device_encode(raw)
    with Image.open(io.BytesIO(raw)) as image:
        server_input_edge = max(image.size)
    # Everything downstream is described in the pixels the server was handed.
    shrink = server_input_edge / capture_edge
    ppi = capture_ppi * shrink
    em_pixels = em_at_capture * shrink

    before = score(_read(reader, raw))
    try:
        sent = prepare(raw)
    except ExtractionError as error:
        return Rung(
            frame=frame_name, fraction=fraction, pixels_per_inch=ppi,
            point_size=point_size, em_pixels=em_pixels,
            capture_edge=capture_edge, server_input_edge=server_input_edge,
            raw_bytes=len(raw), prepared_bytes=None, prepared_edge=None,
            resized=False, refused=error.code, before=before, after=None,
        )
    with Image.open(io.BytesIO(sent)) as image:
        edge = max(image.size)
    after = score(_read(reader, sent))
    return Rung(
        frame=frame_name, fraction=fraction, pixels_per_inch=ppi,
        point_size=point_size, em_pixels=em_pixels,
        capture_edge=capture_edge, server_input_edge=server_input_edge,
        raw_bytes=len(raw), prepared_bytes=len(sent), prepared_edge=edge,
        # True only when photo_prep's own ceiling fired, not when the phone
        # had already shrunk the photograph.
        resized=edge < server_input_edge, refused=None, before=before, after=after,
    )


def sweep(
    reader,
    *,
    frames: Sequence[str] = ("phone-12mp",),
    fractions: Sequence[float] = FRACTIONS,
    point_size: float = FINE_PRINT_POINTS,
    on_device: bool = True,
) -> list[Rung]:
    return [
        measure(reader, frame_name=name, fraction=fraction,
                point_size=point_size, on_device=on_device)
        for name in frames
        for fraction in fractions
    ]


def _table(rungs: Sequence[Rung]) -> str:
    head = (
        f"{'frame':<24} {'span':>5} {'ppi':>6} {'em px':>6} "
        f"{'in line':>8} {'in dig':>7} {'out line':>9} {'out dig':>8} {'note':<22}"
    )
    rows = [head, "-" * len(head)]
    for rung in rungs:
        note = rung.refused or ("photo_prep resized" if rung.resized else "")
        before = rung.before
        after = rung.after
        rows.append(
            f"{rung.frame:<24} {rung.fraction:>5.2f} {rung.pixels_per_inch:>6.0f} "
            f"{rung.em_pixels:>6.1f} "
            f"{'-' if before is None else f'{before.line_recall:>7.0%}'} "
            f"{'-' if before is None else f'{before.digit_recall:>7.0%}'} "
            f"{'-' if after is None else f'{after.line_recall:>9.0%}'} "
            f"{'-' if after is None else f'{after.digit_recall:>8.0%}'} {note:<22}"
        )
    return "\n".join(rows)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", nargs="*", default=["phone-12mp"], choices=sorted(FRAMES))
    parser.add_argument("--fractions", nargs="*", type=float, default=list(FRACTIONS))
    parser.add_argument("--points", type=float, default=FINE_PRINT_POINTS)
    parser.add_argument(
        "--no-device-step", action="store_true",
        help="skip the phone's own re-encode and measure the server step alone",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    from .adapters.rapidocr_reader import RapidOcrReader

    rungs = sweep(
        RapidOcrReader(),
        frames=args.frames,
        fractions=args.fractions,
        point_size=args.points,
        on_device=not args.no_device_step,
    )
    if args.json:
        json.dump([rung.as_dict() for rung in rungs], sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(_table(rungs))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI
    raise SystemExit(main())
