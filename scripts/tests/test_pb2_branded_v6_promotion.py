"""PB-2: second PROMOTE_V6_BRANDED batch.

8 more branded extracts get the v6 contract. Same shape as PB-1.

Promoted:

  turmipure_gold              UNII IT942ZTH98  Naturex turmeric (curcumin)
  neurofactor                 UNII HOX6BEK27Q  Futureceuticals coffee fruit
  sharp_ps_green              UNII 394XK0IH40  Lipogen phosphatidylserine
  flowens                     UNII 0MVO31Q3QS  Frutarom cranberry PAC
  slendesta                   UNII 2A8I57T4MX  Kemin potato (PI2) satiety
  eps_7630                    UNII 4FY2944729  Schwabe Pelargonium sidoides
  life_s_dha                  UNII QGK4EZ8JB9  DSM algal DHA (Crypthecodinium)
  astaxanthin_haematococcus_pluvialis UNII 31T0FF0472  Algal astaxanthin
                                       (BioAstin / AstaReal / Zanthin brands)
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


PB2_ENTRIES = [
    {"id": "turmipure_gold", "unii": "IT942ZTH98",
     "marker_keyword": "curcumin", "brand_keyword": "naturex"},
    {"id": "neurofactor", "unii": "HOX6BEK27Q",
     "marker_keyword": "chlorogenic", "brand_keyword": "futureceuticals"},
    {"id": "sharp_ps_green", "unii": "394XK0IH40",
     "marker_keyword": "phosphatidylserine", "brand_keyword": "lipogen"},
    {"id": "flowens", "unii": "0MVO31Q3QS",
     "marker_keyword": "proanthocyanidin", "brand_keyword": "frutarom"},
    {"id": "slendesta", "unii": "2A8I57T4MX",
     "marker_keyword": "pi2", "brand_keyword": "kemin"},
    {"id": "eps_7630", "unii": "4FY2944729",
     "marker_keyword": "umckalin", "brand_keyword": "schwabe"},
    {"id": "life_s_dha", "unii": "QGK4EZ8JB9",
     "marker_keyword": "docosahexaenoic", "brand_keyword": "dsm"},
    {"id": "astaxanthin_haematococcus_pluvialis", "unii": "31T0FF0472",
     "marker_keyword": "astaxanthin", "brand_keyword": "haematococcus"},
]


def _find(entries, eid):
    for e in entries:
        if isinstance(e, dict) and e.get("id") == eid:
            return e
    return {}


def _lc(values):
    return [(v or "").strip().lower() for v in (values or [])]


@pytest.mark.parametrize("entry", PB2_ENTRIES, ids=[e["id"] for e in PB2_ENTRIES])
def test_present_in_std(std_doc, entry):
    assert _find(std_doc.get("standardized_botanicals", []), entry["id"])


@pytest.mark.parametrize("entry", PB2_ENTRIES, ids=[e["id"] for e in PB2_ENTRIES])
def test_has_unii(std_doc, entry):
    e = _find(std_doc.get("standardized_botanicals", []), entry["id"])
    assert (e.get("external_ids") or {}).get("unii") == entry["unii"]


@pytest.mark.parametrize("entry", PB2_ENTRIES, ids=[e["id"] for e in PB2_ENTRIES])
def test_has_v6_contract(std_doc, entry):
    e = _find(std_doc.get("standardized_botanicals", []), entry["id"])
    assert e.get("bonus_eligible") is True
    assert e.get("standardization_basis") == "branded_extract"
    markers = _lc(e.get("marker_compounds") or [])
    assert any(entry["marker_keyword"] in m for m in markers), (
        f"std.{entry['id']} marker_compounds must include "
        f"{entry['marker_keyword']!r}. Got: {e.get('marker_compounds')}"
    )
    rationale = (e.get("bonus_rationale") or "").lower()
    assert entry["brand_keyword"] in rationale, (
        f"std.{entry['id']} bonus_rationale must mention "
        f"{entry['brand_keyword']!r}. Got: {e.get('bonus_rationale')!r}"
    )
    assert (e.get("sources") or []), f"std.{entry['id']} sources[] empty"
