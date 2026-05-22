"""SB-3d: new canonicals for Ecklonia / Laminaria digitata / Saccharina latissima.

Fourth batch of the 2026-05-22 brown-algae §7.5/§8.5 decomposition,
following SB-3a (main), SB-3b (sb/3b-...), and SB-3c (sb/3c-...).

Why this matters

After SB-3c, botanical_ingredients.kelp_powder is realigned to
Ascophyllum nodosum identity but still holds aliases that belong to
four other distinct species:

  - Ecklonia radiata          UNII QVY0X8DRIA
  - Ecklonia kurome           UNII 802YF989GT
  - Laminaria digitata         UNII 15E7C67EE8
  - Saccharina latissima       UNII 68CMP2MB55 (Laminaria saccharina)

Each needs its own canonical entry so that downstream products
labelled with the species name route to the correct identity rather
than the Ascophyllum kelp_powder generic.

SB-3d scope

- Create 4 new botanical_ingredients canonicals:
  1. ecklonia_radiata    (UNII QVY0X8DRIA)
  2. ecklonia_kurome     (UNII 802YF989GT)
  3. laminaria_digitata  (UNII 15E7C67EE8)
  4. saccharina_latissima (UNII 68CMP2MB55) — note: Saccharina
     latissima is the modern accepted name; older sources call it
     Laminaria saccharina.

- Remove the migrated aliases from kelp_powder.

- Update botanical_ingredients total_entries metadata: 482 → 486
  (4 new entries added).

Out of scope

- 'brown algae' (UNII 55P66J5H7N) — generic catch-all, stays in
  kelp_powder for now.
- 'laminaria powder' / 'Kelp Leaf, Stem Extract' / 'Kelp' / 'icelandic
  kelp' / 'kelp extract' / 'organic kelp' — generic kelp registry
  terms, stay in kelp_powder as the Ascophyllum-leaning generic catch.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SCRIPTS = os.path.join(_ROOT, "scripts")


@pytest.fixture(scope="module")
def botanicals() -> Dict[str, Any]:
    with open(os.path.join(_SCRIPTS, "data", "botanical_ingredients.json")) as f:
        return json.load(f)


def _lc(values: List[str]) -> List[str]:
    return [(v or "").strip().lower() for v in (values or [])]


def _find(entries: List[Dict[str, Any]], eid: str) -> Dict[str, Any]:
    for e in entries:
        if isinstance(e, dict) and e.get("id") == eid:
            return e
    return {}


# Per-species expected configuration
_NEW_ENTRIES = {
    "ecklonia_radiata": {
        "unii": "QVY0X8DRIA",
        "latin_name": "ecklonia radiata",
        "required_aliases": ["ecklonia radiata"],
    },
    "ecklonia_kurome": {
        "unii": "802YF989GT",
        "latin_name": "ecklonia kurome",
        "required_aliases": ["ecklonia kurome"],
    },
    "laminaria_digitata": {
        "unii": "15E7C67EE8",
        "latin_name": "laminaria digitata",
        "required_aliases": ["laminaria digitata", "laminaria powder"],
    },
    "saccharina_latissima": {
        "unii": "68CMP2MB55",
        "latin_name": "saccharina latissima",
        "required_aliases": [
            "saccharina latissima",
            "laminaria saccharina",
        ],
    },
}


@pytest.mark.parametrize("entry_id,spec", _NEW_ENTRIES.items())
def test_new_canonical_exists_with_correct_unii(botanicals, entry_id, spec):
    """Each new SB-3d canonical must exist with the species' verified UNII
    and a latin_name that matches."""
    e = _find(botanicals.get("botanical_ingredients", []), entry_id)
    assert e, f"botanical_ingredients.{entry_id} missing"
    assert (e.get("external_ids") or {}).get("unii") == spec["unii"], (
        f"{entry_id} UNII must be {spec['unii']}. Got: {e.get('external_ids')}"
    )
    assert spec["latin_name"] in (e.get("latin_name") or "").lower(), (
        f"{entry_id} latin_name must contain {spec['latin_name']!r}. "
        f"Got: {e.get('latin_name')!r}"
    )


@pytest.mark.parametrize("entry_id,spec", _NEW_ENTRIES.items())
def test_new_canonical_owns_required_aliases(botanicals, entry_id, spec):
    """Each new canonical must alias the species name(s) that were
    migrated out of kelp_powder."""
    e = _find(botanicals.get("botanical_ingredients", []), entry_id)
    aliases = _lc(e.get("aliases", []))
    for required in spec["required_aliases"]:
        assert required in aliases, (
            f"{entry_id} must alias {required!r}. Got: {e.get('aliases')}"
        )


def test_kelp_powder_no_longer_aliases_ecklonia(botanicals):
    """Ecklonia spp. now have dedicated canonicals. kelp_powder must
    not retain those aliases."""
    e = _find(botanicals.get("botanical_ingredients", []), "kelp_powder")
    aliases = _lc(e.get("aliases", []))
    for forbidden in ("ecklonia radiata", "ecklonia kurome"):
        assert forbidden not in aliases, (
            f"§8.5: kelp_powder must NOT alias {forbidden!r}. Got: {e.get('aliases')}"
        )


def test_kelp_powder_no_longer_aliases_laminaria_digitata(botanicals):
    """Laminaria digitata (UNII 15E7C67EE8) has a dedicated canonical
    now; kelp_powder (UNII 168S4EO8YJ = Ascophyllum) must not own its
    aliases."""
    e = _find(botanicals.get("botanical_ingredients", []), "kelp_powder")
    aliases = _lc(e.get("aliases", []))
    for forbidden in ("laminaria digitata", "laminaria powder"):
        assert forbidden not in aliases, (
            f"§8.5: kelp_powder must NOT alias {forbidden!r} — Laminaria "
            f"digitata is a different species. Got: {e.get('aliases')}"
        )


def test_kelp_powder_no_longer_aliases_saccharina(botanicals):
    """Saccharina latissima / Laminaria saccharina now has its own
    canonical."""
    e = _find(botanicals.get("botanical_ingredients", []), "kelp_powder")
    aliases = _lc(e.get("aliases", []))
    for forbidden in ("laminaria saccharina", "laminaria saccharina, powder"):
        assert forbidden not in aliases, (
            f"§8.5: kelp_powder must NOT alias {forbidden!r} — Saccharina "
            f"latissima is a different species. Got: {e.get('aliases')}"
        )


def test_botanical_ingredients_total_entries_updated(botanicals):
    """+4 entries from SB-3d (ecklonia_radiata, ecklonia_kurome,
    laminaria_digitata, saccharina_latissima). Combined with SB-2's
    coffee_bean_plain (+1 on main), this branch ships 5 new entries
    on top of HEAD-main's 482."""
    meta = botanicals.get("_metadata") or {}
    declared = meta.get("total_entries")
    actual = len(botanicals.get("botanical_ingredients", []))
    assert declared == actual, (
        f"_metadata.total_entries={declared} but actual={actual}. "
        f"Reconcile after SB-3d's +4 entries."
    )
    assert actual == 487, (
        f"Expected 487 entries after SB-3d (482 HEAD-main + 1 coffee_bean_plain "
        f"from SB-2 + 4 new SB-3d canonicals). Got: {actual}"
    )
