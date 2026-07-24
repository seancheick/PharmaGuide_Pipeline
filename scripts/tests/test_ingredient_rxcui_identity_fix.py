"""Regression: ingredient/botanical external rxcui identity fix (2026-07-24 Codex live-RxNorm audit).

Codex's live RxNorm sweep found wrong-entity / retired rxcuis stored on the
top-level ``rxcui`` field of ingredient & botanical reference entries. Each was
content-verified against RxNorm historystatus before correction:

    32559   "osteum"                          -> 7631    "oleic acid"        (wrong entity)
    1310069 "Hypoxis hemerocallidea ..."      -> 258326  "St. John's wort extract" (wrong species)
    1306935 "Brazillian pepper extract"       -> 259314  "black pepper preparation" (wrong genus)
    253171  "golden seal root" (NotCurrent)   -> 1372255 "goldenseal extract" (retired)

These rxcuis are NON-load-bearing metadata: the interaction builder keys on
drug_classes.member_rxcuis, and ingredient/banned matching keys on UNII. The
final-db emitter (extract_identifiers) only emits cui/cas/pubchem_cid/unii, so
``rxcui`` never reaches a shipped blob. This test locks BOTH facts: the four
wrong ids are gone, and the emitter can never leak rxcui.
"""

import json
from pathlib import Path

from build_final_db import extract_identifiers

_DATA = Path(__file__).resolve().parent.parent / "data"
_FILES = [
    "ingredient_quality_map.json",
    "other_ingredients.json",
    "botanical_ingredients.json",
    "standardized_botanicals.json",
]

# stored wrong id -> (corrected id, minimum expected occurrences of the correction)
_WRONG = {"32559", "1310069", "1306935", "253171"}
_CORRECTED_MIN = {"7631": 1, "258326": 2, "259314": 3, "1372255": 1}


def _iter_rxcuis():
    """Yield every top-level string ``rxcui`` value across the reference files."""
    for fn in _FILES:
        data = json.loads((_DATA / fn).read_text(encoding="utf-8"))
        stack = [data]
        while stack:
            obj = stack.pop()
            if isinstance(obj, dict):
                rx = obj.get("rxcui")
                if isinstance(rx, str):
                    yield fn, rx
                stack.extend(obj.values())
            elif isinstance(obj, list):
                stack.extend(obj)


def test_wrong_ingredient_rxcuis_absent():
    hits = [(fn, rx) for fn, rx in _iter_rxcuis() if rx in _WRONG]
    assert not hits, f"wrong-entity/retired rxcuis still present: {hits}"


def test_corrected_ingredient_rxcuis_present():
    counts = {}
    for _fn, rx in _iter_rxcuis():
        counts[rx] = counts.get(rx, 0) + 1
    for rx, want in _CORRECTED_MIN.items():
        assert counts.get(rx, 0) >= want, (
            f"corrected rxcui {rx} expected >= {want} occurrence(s), got {counts.get(rx, 0)}"
        )


def test_extract_identifiers_never_emits_rxcui():
    """The blob emitter must never surface rxcui (top-level OR inside external_ids)."""
    entry = {
        "cui": "C1",
        "external_ids": {"cas": "1", "pubchem_cid": 2, "unii": "U", "rxcui": "9999"},
        "rxcui": "9999",
    }
    out = extract_identifiers(entry)
    assert out is not None
    assert "rxcui" not in out, f"rxcui leaked into blob identifiers: {out}"
    # sanity: the legit ids still emit (guards against a gutted emitter passing vacuously)
    assert out.get("unii") == "U" and out.get("cas") == "1" and out.get("cui") == "C1"
