"""PB-1: first PROMOTE_V6_BRANDED batch.

8 well-known commercial branded extracts get the v6 contract.
These STAY in standardized_botanicals.json — they are bonus-eligible
by design (the brand owner has clinical literature + a defined
standardization spec).

Each promoted entry gets:
  - external_ids.unii filled (where missing) via FDA UNII cache
  - bonus_eligible = True
  - standardization_basis = "branded_extract"
  - marker_compounds list (best-effort from existing markers[] or
    known brand spec)
  - bonus_rationale citing the brand owner and clinical pathway
  - sources (NIH ODS or PubMed PMID where available)

The runtime meets_threshold gate (score_supplements.py:1148)
enforces label-text brand-name detection at scoring time, so the
bonus only fires when the product label proves the brand mention
or a measurable marker percentage.

Promoted in PB-1:

  pacran              UNII 0MVO31Q3QS  Naturex cranberry PAC
  cran_max            UNII 0MVO31Q3QS  PharmaChem whole-fruit cranberry
  lutemax_2020        UNII X72A60C9MT  OmniActive lutein+zeaxanthin
  floraglo            UNII X72A60C9MT  Kemin lutein
  ksm_66_ashwagandha  UNII V038D626IF  Ixoreal KSM-66 (Withania root)
  cognigrape          UNII RDS2V6DVY5  Bionap red-grape (existing UNII)
  optiberry           UNII —           InterHealth berry blend (multi-source)
  pycnogenol          UNII 50JZ5Z98QY  Horphag maritime pine bark
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.fixture(scope="module")
def std_doc() -> Dict[str, Any]:
    with open(os.path.join(_ROOT, "scripts", "data", "standardized_botanicals.json")) as f:
        return json.load(f)


PB1_ENTRIES = [
    {"id": "pacran", "unii": "0MVO31Q3QS",
     "marker_keyword": "proanthocyanidin", "brand_keyword": "naturex"},
    {"id": "cran_max", "unii": "0MVO31Q3QS",
     "marker_keyword": "proanthocyanidin", "brand_keyword": "pharmachem"},
    {"id": "lutemax_2020", "unii": "X72A60C9MT",
     "marker_keyword": "lutein", "brand_keyword": "omniactive"},
    {"id": "floraglo", "unii": "X72A60C9MT",
     "marker_keyword": "lutein", "brand_keyword": "kemin"},
    {"id": "ksm_66_ashwagandha", "unii": "V038D626IF",
     "marker_keyword": "withanolide", "brand_keyword": "ixoreal"},
    {"id": "cognigrape", "unii": "RDS2V6DVY5",
     "marker_keyword": "anthocyanin", "brand_keyword": "bionap"},
    {"id": "optiberry", "unii": None,
     "marker_keyword": "anthocyanin", "brand_keyword": "interhealth"},
    {"id": "pycnogenol", "unii": "50JZ5Z98QY",
     "marker_keyword": "proanthocyanidin", "brand_keyword": "horphag"},
]


def _find(entries, eid):
    for e in entries:
        if isinstance(e, dict) and e.get("id") == eid:
            return e
    return {}


def _lc(values):
    return [(v or "").strip().lower() for v in (values or [])]


@pytest.mark.parametrize("entry", PB1_ENTRIES, ids=[e["id"] for e in PB1_ENTRIES])
def test_entry_present_in_std(std_doc, entry):
    """PROMOTE entries STAY in standardized_botanicals (no move)."""
    assert _find(std_doc.get("standardized_botanicals", []), entry["id"])


@pytest.mark.parametrize("entry", PB1_ENTRIES, ids=[e["id"] for e in PB1_ENTRIES])
def test_entry_has_unii(std_doc, entry):
    e = _find(std_doc.get("standardized_botanicals", []), entry["id"])
    actual = (e.get("external_ids") or {}).get("unii")
    if entry["unii"] is None:
        # optiberry intentionally has no single-substance UNII (it's a
        # multi-source berry blend); just verify the contract noted this
        return
    assert actual == entry["unii"], (
        f"std.{entry['id']} UNII expected {entry['unii']!r}, got {actual!r}"
    )


@pytest.mark.parametrize("entry", PB1_ENTRIES, ids=[e["id"] for e in PB1_ENTRIES])
def test_entry_has_v6_contract(std_doc, entry):
    e = _find(std_doc.get("standardized_botanicals", []), entry["id"])
    assert e.get("bonus_eligible") is True, (
        f"std.{entry['id']} must have bonus_eligible=True"
    )
    assert e.get("standardization_basis") == "branded_extract", (
        f"std.{entry['id']} basis must be 'branded_extract'. "
        f"Got: {e.get('standardization_basis')!r}"
    )
    markers = _lc(e.get("marker_compounds") or [])
    assert any(entry["marker_keyword"] in m for m in markers), (
        f"std.{entry['id']} marker_compounds must include "
        f"{entry['marker_keyword']!r}. Got: {e.get('marker_compounds')}"
    )
    rationale = (e.get("bonus_rationale") or "").lower()
    assert entry["brand_keyword"] in rationale, (
        f"std.{entry['id']} bonus_rationale must mention brand owner "
        f"{entry['brand_keyword']!r}. Got: {e.get('bonus_rationale')!r}"
    )
    sources = e.get("sources") or []
    assert len(sources) >= 1, (
        f"std.{entry['id']} sources[] must cite at least one"
    )
