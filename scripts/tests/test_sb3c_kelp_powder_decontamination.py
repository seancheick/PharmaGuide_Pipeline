"""SB-3c: botanical_ingredients.kelp_powder species decontamination.

Third batch of the 2026-05-22 brown-algae §7.5/§8.5 decomposition,
following SB-3a (bladderwrack/Fucus on main, 5592047d) and SB-3b
(Ascophyllum/Saccharina/Undaria from IQM brown_kelp on
sb/3b-ascophyllum-saccharina-undaria, 483c2422).

Why this matters

After SB-3b, botanical_ingredients.kelp_powder (UNII 168S4EO8YJ =
Ascophyllum nodosum) still mixes 6+ species:

  - Ascophyllum nodosum         UNII 168S4EO8YJ  — entry's own UNII
  - Fucus vesiculosus           UNII 535G2ABX9M  — 'bladderwrack powder'
  - Undaria pinnatifida         UNII ICV1OK7M1S  — duplicate alias
                                                   (already in wakame
                                                   after SB-3b)
  - Alaria esculenta            UNII EJ9JK8J58D  — duplicate alias
                                                   (already covered by
                                                   alaria_esculenta entry)
  - Saccharina latissima        UNII 68CMP2MB55  — 'Laminaria saccharina'
  - Laminaria digitata          UNII 15E7C67EE8  — 'laminaria powder',
                                                   'laminaria digitata'
  - Ecklonia radiata / kurome   UNIIs QVY0X8DRIA / 802YF989GT
  - Generic "kelp" registry     UNII 3PC632V63J  — 'Kelp', 'icelandic
                                                   kelp', 'organic kelp'

The entry's latin_name was "Laminaria digitata" (UNII 15E7C67EE8) —
contradicting its actual UNII 168S4EO8YJ (Ascophyllum nodosum). That
identity drift is the root cause of the accumulated contamination.

SB-3c scope (this commit)

- Realign kelp_powder identity to its UNII:
  - latin_name: "Laminaria digitata" → "Ascophyllum nodosum"
  - notes: clarify Ascophyllum-specific identity, document deferred
    aliases for SB-3d.

- Migrate 3 clearly-misplaced aliases to their canonical homes:
  1. 'bladderwrack powder' (UNII 535G2ABX9M Fucus) →
     standardized_botanicals.bladderwrack (continues the SB-3a
     bladderwrack consolidation).
  2. 'brown kelp undaria pinnatifida powder' (UNII ICV1OK7M1S
     Undaria) — REMOVE from kelp_powder. Already in wakame after
     SB-3b; the duplicate here is residual contamination.
  3. 'alaria esculenta' (UNII EJ9JK8J58D Alaria) — REMOVE from
     kelp_powder. The alaria_esculenta entry already aliases this
     term as its primary identity; the duplicate here is residual
     contamination.

Out of scope (deferred to SB-3d)

- 'laminaria powder', 'laminaria digitata' (Laminaria digitata,
  UNII 15E7C67EE8) — needs new canonical entry.
- 'Laminaria saccharina', 'Laminaria saccharina, Powder' (Saccharina
  latissima, UNII 68CMP2MB55) — needs new canonical entry.
- 'ecklonia radiata' (UNII QVY0X8DRIA), 'ecklonia kurome' (UNII
  802YF989GT) — need new canonical entries.
- 'brown algae' (UNII 55P66J5H7N) — generic; resolve in SB-3d.
- 'Kelp', 'icelandic kelp', 'kelp extract', 'organic kelp', 'Kelp
  Leaf, Stem Extract' — generic kelp registry terms; retain in
  kelp_powder for now.
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


@pytest.fixture(scope="module")
def sbot() -> Dict[str, Any]:
    with open(os.path.join(_SCRIPTS, "data", "standardized_botanicals.json")) as f:
        return json.load(f)


def _lc(values: List[str]) -> List[str]:
    return [(v or "").strip().lower() for v in (values or [])]


def _find(entries: List[Dict[str, Any]], eid: str) -> Dict[str, Any]:
    for e in entries:
        if isinstance(e, dict) and e.get("id") == eid:
            return e
    return {}


def test_kelp_powder_latin_name_matches_its_unii(botanicals):
    """kelp_powder UNII is 168S4EO8YJ (Ascophyllum nodosum). Its
    latin_name must match — 'Laminaria digitata' is a different
    species (UNII 15E7C67EE8) and was the root cause of the
    accumulated multi-species contamination."""
    e = _find(botanicals.get("botanical_ingredients", []), "kelp_powder")
    assert e, "botanical_ingredients.kelp_powder missing"
    assert (e.get("external_ids") or {}).get("unii") == "168S4EO8YJ"
    assert e.get("latin_name", "").lower() == "ascophyllum nodosum", (
        f"kelp_powder latin_name must be 'Ascophyllum nodosum' to match "
        f"its UNII 168S4EO8YJ. Got: {e.get('latin_name')!r}"
    )


def test_kelp_powder_no_longer_aliases_bladderwrack_powder(botanicals):
    """Fucus vesiculosus (UNII 535G2ABX9M) is a different species from
    Ascophyllum (UNII 168S4EO8YJ). 'bladderwrack powder' must live in
    standardized_botanicals.bladderwrack, not in kelp_powder."""
    e = _find(botanicals.get("botanical_ingredients", []), "kelp_powder")
    aliases = _lc(e.get("aliases", []))
    assert "bladderwrack powder" not in aliases, (
        f"§8.5: 'bladderwrack powder' must NOT alias to kelp_powder "
        f"(Ascophyllum). Got: {e.get('aliases')}"
    )


def test_standardized_botanicals_bladderwrack_owns_bladderwrack_powder(sbot):
    """standardized_botanicals.bladderwrack (UNII 535G2ABX9M = Fucus
    vesiculosus) is the canonical home for 'bladderwrack powder'.
    Continues the SB-3a bladderwrack consolidation."""
    e = _find(sbot.get("standardized_botanicals", []), "bladderwrack")
    aliases = _lc(e.get("aliases", []))
    assert "bladderwrack powder" in aliases, (
        f"standardized_botanicals.bladderwrack must alias "
        f"'bladderwrack powder' (migrated from kelp_powder §8.5 "
        f"cleanup). Got: {e.get('aliases')}"
    )


def test_kelp_powder_no_longer_aliases_undaria_duplicate(botanicals):
    """'brown kelp undaria pinnatifida powder' lives in
    botanical_ingredients.wakame (UNII ICV1OK7M1S = Undaria pinnatifida)
    after SB-3b. The duplicate in kelp_powder is residual §8.5
    contamination and must be removed."""
    e = _find(botanicals.get("botanical_ingredients", []), "kelp_powder")
    aliases = _lc(e.get("aliases", []))
    assert "brown kelp undaria pinnatifida powder" not in aliases, (
        f"§8.5: 'brown kelp undaria pinnatifida powder' must NOT live "
        f"in kelp_powder — Undaria pinnatifida lives in wakame. Got: "
        f"{e.get('aliases')}"
    )


def test_kelp_powder_no_longer_aliases_alaria_duplicate(botanicals):
    """'alaria esculenta' is the primary alias of
    botanical_ingredients.alaria_esculenta (UNII EJ9JK8J58D). The
    duplicate in kelp_powder is residual §8.5 contamination and must
    be removed."""
    e = _find(botanicals.get("botanical_ingredients", []), "kelp_powder")
    aliases = _lc(e.get("aliases", []))
    assert "alaria esculenta" not in aliases, (
        f"§8.5: 'alaria esculenta' must NOT live in kelp_powder — "
        f"Alaria esculenta has its own canonical entry. Got: "
        f"{e.get('aliases')}"
    )


def test_kelp_powder_retains_ascophyllum_aliases(botanicals):
    """SB-3c keeps the Ascophyllum-correct aliases that SB-3b migrated
    into kelp_powder. These belong here (matching the entry's UNII)."""
    e = _find(botanicals.get("botanical_ingredients", []), "kelp_powder")
    aliases = _lc(e.get("aliases", []))
    for required in (
        "ascophyllum nodosum",
        "ascophyllum nodosum powder",
        "kelp powder",
        "norwegian kelp",
        "rockweed",
    ):
        assert required in aliases, (
            f"kelp_powder must retain Ascophyllum-correct alias "
            f"'{required}' (UNII 168S4EO8YJ matches entry). Got: "
            f"{e.get('aliases')}"
        )
