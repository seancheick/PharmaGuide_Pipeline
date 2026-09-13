"""One conservative photo-section vocabulary for OCR and reviewer guidance.

These are located text observations, not identity or completeness checks.
Never infer a front panel from missing text, or treat a hint as verification.
"""
from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING

from ..gtin import canonical_gtin14_candidates

if TYPE_CHECKING:
    from .adapters.ocr_adapter import OcrPage

RULES_VERSION = "photo-sections-v2"
MAX_LINES = 2000
MAX_SUPPORT_TEXT = 200

# Whole headings, or a heading followed by a colon. A mention embedded in
# marketing prose ("read the Supplement Facts") is deliberately not enough.
FACTS_HEADING = re.compile(r"^\s*supp[li]ement\s*facts\s*:?\s*$", re.I)
_HEADINGS = (
    ("supplement_facts", FACTS_HEADING),
    ("ingredient_disclosure", re.compile(r"^(?:other\s*)?ingredients?\s*(?::|$)", re.I)),
    ("directions_warnings", re.compile(
        r"^(?:directions(?:\s*for\s*use)?|suggested\s*use|recommended\s*use|"
        r"(?:product\s*)?warnings?|allergens\s*&\s*warnings|caution)\s*(?::|$)", re.I)),
    ("lot_expiry", re.compile(r"^(?:lot|batch|exp(?:iry|iration)?|best\s*by)\s*[:#]\s*\S", re.I)),
)
_UPC = re.compile(r"^(?:u\.?p\.?c\.?|gtin|ean|barcode)\s*[:#-]?\s*([0-9 \t\u00a0-]+)$", re.I)


def suggest_photo_roles(page: OcrPage) -> list[dict]:
    """Return at most one located observation per role, in reading order."""
    suggestions = {}
    for line in page.lines[:MAX_LINES]:
        # Do not collapse newlines into digits or turn an empty box into proof.
        text = line.text.strip()
        if not text or len(text) > MAX_SUPPORT_TEXT or "\n" in text or "\r" in text:
            continue
        box = {key: getattr(line, key) for key in ("left", "top", "right", "bottom")}
        if (not all(math.isfinite(value) and value >= 0 for value in box.values())
                or box["right"] <= box["left"] or box["bottom"] <= box["top"]):
            continue
        roles = [role for role, pattern in _HEADINGS if pattern.search(text)]
        code = _UPC.fullmatch(text)
        if code and canonical_gtin14_candidates(code.group(1)):
            roles.append("barcode")
        for role in roles:
            try:
                coordinates = page.input_box(*(box[key] for key in ('left', 'top', 'right', 'bottom')))
            except ValueError:
                continue
            input_box = dict(zip(('left', 'top', 'right', 'bottom'), coordinates))
            suggestions.setdefault(role, {"role": role, "text": text, "box": input_box})
    return list(suggestions.values())


def guidance_for_page(page: OcrPage, *, declared: tuple[str, ...]) -> dict:
    suggestions = suggest_photo_roles(page)
    roles = {item["role"] for item in suggestions}
    return {
        "rules_version": RULES_VERSION,
        "status": "suggestions" if suggestions else ("unknown" if page.lines else "unreadable"),
        "declared": list(declared),
        "suggestions": suggestions,
        "coordinate_space": "prepared_image_pixels",
        "possible_role_mismatch": bool(declared and roles and not roles.intersection(declared)),
    }
