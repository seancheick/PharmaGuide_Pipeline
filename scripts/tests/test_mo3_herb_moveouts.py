"""MO-3: third move-out batch.

7 more plain-identity entries to bot. Same pattern as MO-1, MO-2.

Special-case: pine_bark_extract moves WITHOUT its 'pycnogenol' alias.
Pycnogenol® is the Horphag-branded standardized extract of French
maritime pine bark — its bonus entry will be added in a future
PROMOTE_V6_BRANDED batch (PB-N). Keeping 'pycnogenol' as a plain-
identity alias here would route Pycnogenol-labeled products to a
no-bonus path even after PB lands; dropping it now leaves them
unmapped (a fail-safe state) until PB recovers the route.

Entries

  huperzine_a          UNII 0111871I23  Huperzia serrata extract
  inulin               UNII JOS53KRJ01  Fructan fiber (chicory root etc.)
  l_theanine           UNII 8021PR16QO  Amino acid analog (Camellia sinensis)
  mulungu              UNII NU815YHH1S  Erythrina mulungu (coral tree)
  onion                UNII 492225Q21H  Allium cepa
  phosphatidylserine   UNII 394XK0IH40  PS (PS-family compound)
  pine_bark_extract    UNII 50JZ5Z98QY  Pinus pinaster (WITHOUT 'pycnogenol' alias)
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


@pytest.fixture(scope="module")
def bot_doc() -> Dict[str, Any]:
    with open(os.path.join(_ROOT, "scripts", "data", "botanical_ingredients.json")) as f:
        return json.load(f)


MO3_ENTRIES = [
    {"id": "huperzine_a", "unii": "0111871I23",
     "expected_aliases_subset": ["huperzia serrata extract"]},
    {"id": "inulin", "unii": "JOS53KRJ01",
     "expected_aliases_subset": ["chicory root inulin"]},
    {"id": "l_theanine", "unii": "8021PR16QO",
     "expected_aliases_subset": ["theanine"]},
    {"id": "mulungu", "unii": "NU815YHH1S",
     "expected_aliases_subset": ["erythrina mulungu"]},
    {"id": "onion", "unii": "492225Q21H",
     "expected_aliases_subset": ["allium cepa"]},
    {"id": "phosphatidylserine", "unii": "394XK0IH40",
     "expected_aliases_subset": ["phosphatidyl serine"]},
    {"id": "pine_bark_extract", "unii": "50JZ5Z98QY",
     "expected_aliases_subset": ["pinus pinaster", "maritime pine bark"]},
]


def _find(entries: List[Dict[str, Any]], eid: str) -> Dict[str, Any]:
    for e in entries:
        if isinstance(e, dict) and e.get("id") == eid:
            return e
    return {}


def _lc(values: List[str]) -> List[str]:
    return [(v or "").strip().lower() for v in (values or [])]


@pytest.mark.parametrize("entry", MO3_ENTRIES, ids=[e["id"] for e in MO3_ENTRIES])
def test_entry_removed_from_std(std_doc, entry):
    assert not _find(std_doc.get("standardized_botanicals", []), entry["id"])


@pytest.mark.parametrize("entry", MO3_ENTRIES, ids=[e["id"] for e in MO3_ENTRIES])
def test_entry_in_bot(bot_doc, entry):
    assert _find(bot_doc.get("botanical_ingredients", []), entry["id"])


@pytest.mark.parametrize("entry", MO3_ENTRIES, ids=[e["id"] for e in MO3_ENTRIES])
def test_unii_preserved(bot_doc, entry):
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    assert (e.get("external_ids") or {}).get("unii") == entry["unii"]


@pytest.mark.parametrize("entry", MO3_ENTRIES, ids=[e["id"] for e in MO3_ENTRIES])
def test_aliases_preserved(bot_doc, entry):
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    aliases = _lc(e.get("aliases", []))
    for required in entry["expected_aliases_subset"]:
        assert required in aliases, (
            f"bot entry '{entry['id']}' must preserve '{required}'. "
            f"Got: {e.get('aliases')}"
        )


@pytest.mark.parametrize("entry", MO3_ENTRIES, ids=[e["id"] for e in MO3_ENTRIES])
def test_no_bonus(bot_doc, entry):
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    assert (e.get("attributes") or {}).get("bonus_eligible") is False
    for v6 in ("standardization_basis", "marker_compounds", "bonus_rationale"):
        assert v6 not in e


def test_pine_bark_drops_pycnogenol_alias(bot_doc):
    """pine_bark_extract must NOT carry the 'pycnogenol' alias — the
    branded Pycnogenol® extract earns its own future PROMOTE_V6_BRANDED
    entry. Keeping the alias here would silently route Pycnogenol-
    labeled products to no-bonus even after PB lands."""
    e = _find(bot_doc.get("botanical_ingredients", []), "pine_bark_extract")
    aliases = _lc(e.get("aliases", []))
    assert "pycnogenol" not in aliases, (
        f"pine_bark_extract must drop 'pycnogenol' alias on move-out. "
        f"Got: {e.get('aliases')}"
    )


def test_mo3_net_count(std_doc, bot_doc):
    """MO-2 → 227/500. MO-3 → 220/507."""
    std_actual = len(std_doc.get("standardized_botanicals", []))
    bot_actual = len(bot_doc.get("botanical_ingredients", []))
    assert std_actual <= 220, f"std {std_actual} > 220"
    assert bot_actual >= 507, f"bot {bot_actual} < 507"


def test_metadata_invariant(std_doc, bot_doc):
    assert std_doc["_metadata"]["total_entries"] == len(std_doc["standardized_botanicals"])
    assert bot_doc["_metadata"]["total_entries"] == len(bot_doc["botanical_ingredients"])
