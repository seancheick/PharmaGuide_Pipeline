"""PB-3: third PROMOTE_V6_BRANDED batch — 9 final branded extracts.

Closes the PROMOTE_V6_BRANDED group from the audit (organic_gold_
standard_potentiating_nutrients defers to MO-6 since it's a
proprietary BLEND, not a single-ingredient brand).
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.fixture(scope="module")
def std_doc() -> Dict[str, Any]:
    with open(os.path.join(_ROOT, "scripts", "data", "standardized_botanicals.json")) as f:
        return json.load(f)


PB3_ENTRIES = [
    {"id": "bil_max",   "unii": "3CCB416HVP", "marker": "anthocyanin", "brand": "sabinsa"},
    {"id": "blue_max",  "unii": "DVH063L9QI", "marker": "anthocyanin", "brand": "sabinsa"},
    {"id": "chromax",   "unii": "S71T8B8Z6P", "marker": "chromium",    "brand": "nutrition 21"},
    {"id": "astazine",  "unii": "31T0FF0472", "marker": "astaxanthin", "brand": "bgg"},
    {"id": "fruitex_b_calcium_fructoborate", "unii": "7EW2EZ38LS",
     "marker": "fructoborate", "brand": "futureceuticals"},
    {"id": "microactive_melatonin", "unii": "JL5DK93RCL",
     "marker": "melatonin", "brand": "bioactives"},
    {"id": "sunactive_iron", "unii": "FZ7NYF5N8L",
     "marker": "iron", "brand": "taiyo"},
    {"id": "thermosil", "unii": "623B93YABH", "marker": "silicon", "brand": "thermosil"},
    {"id": "uniflex", "unii": None,
     "marker": "type ii collagen", "brand": "lonza"},
]


def _find(entries, eid):
    for e in entries:
        if isinstance(e, dict) and e.get("id") == eid:
            return e
    return {}


def _lc(values):
    return [(v or "").strip().lower() for v in (values or [])]


@pytest.mark.parametrize("entry", PB3_ENTRIES, ids=[e["id"] for e in PB3_ENTRIES])
def test_present_in_std(std_doc, entry):
    assert _find(std_doc.get("standardized_botanicals", []), entry["id"])


@pytest.mark.parametrize("entry", PB3_ENTRIES, ids=[e["id"] for e in PB3_ENTRIES])
def test_v6_contract(std_doc, entry):
    e = _find(std_doc.get("standardized_botanicals", []), entry["id"])
    if entry["unii"]:
        assert (e.get("external_ids") or {}).get("unii") == entry["unii"]
    assert e.get("bonus_eligible") is True
    assert e.get("standardization_basis") == "branded_extract"
    markers = _lc(e.get("marker_compounds") or [])
    assert any(entry["marker"] in m for m in markers), (
        f"std.{entry['id']} marker_compounds must include {entry['marker']!r}. "
        f"Got: {e.get('marker_compounds')}"
    )
    rationale = (e.get("bonus_rationale") or "").lower()
    assert entry["brand"] in rationale, (
        f"std.{entry['id']} rationale must mention {entry['brand']!r}. "
        f"Got: {e.get('bonus_rationale')!r}"
    )
    assert (e.get("sources") or [])
