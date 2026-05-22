"""SB-3b: Ascophyllum / Saccharina / Undaria species split from IQM brown_kelp.

Second batch of the 2026-05-22 brown-algae §7.5/§8.5 decomposition,
following SB-3a (bladderwrack/Fucus, landed in 5592047d).

Why this matters

After SB-3a, IQM ``brown_kelp.forms['brown kelp powder']`` still mixed
three other distinct species under its alias list:

  - Ascophyllum nodosum (Rockweed)            UNII 168S4EO8YJ
  - Saccharina japonica (Kombu / J. kelp)     UNII WE98HW412B
  - Undaria pinnatifida (Wakame)              UNII ICV1OK7M1S

Each has a clean canonical home in ``botanical_ingredients.json``
(kelp_powder for Ascophyllum, kombu for Saccharina japonica, wakame
for Undaria) — they do NOT belong as aliases of the generic Laminaria
brown_kelp entry.

SB-3b scope (this commit)

- Remove the four Ascophyllum aliases from IQM brown_kelp form
  'brown kelp powder' (`'kelp powder'`, `'norwegian kelp'`,
  `'ascophyllum nodosum'`, `'rockweed'`).
- Add the same four aliases to ``botanical_ingredients.kelp_powder``
  (UNII 168S4EO8YJ — that entry already represents Ascophyllum
  identity; this commit consolidates the family with its canonical
  home).
- Remove the two Saccharina japonica aliases from IQM brown_kelp
  (`'brown seaweed (laminaria japonica) extract'`,
  `'Japanese Kelp extract'`).
- Add them to ``botanical_ingredients.kombu`` (UNII WE98HW412B —
  the canonical Saccharina japonica entry, already populated with
  Laminaria japonica / Saccharina japonica aliases).
- Remove the one Undaria pinnatifida alias from IQM brown_kelp
  (`'brown kelp undaria pinnatifida powder'`).
- Add it to ``botanical_ingredients.wakame`` (UNII ICV1OK7M1S —
  the canonical Undaria pinnatifida entry).

Generic-kelp aliases are retained in brown_kelp:
  - 'sea kelp', 'organic sea kelp', 'pacific kelp', 'atlantic kelp',
    'north atlantic kelp', 'brown seaweed', 'brown seaweed extract',
    'brown seaweed concentrate', 'Brown Seaweeds Kelp'

Out of scope (SB-3c / SB-3d)

- ``botanical_ingredients.kelp_powder`` still has other misplaced
  aliases ('laminaria powder', 'bladderwrack powder',
  'laminaria digitata', 'brown algae') that belong to different
  species — SB-3c will decontaminate those.
- New ``ascophyllum_nodosum`` canonical entry if SB-3c decides to
  split kelp_powder rather than just clean it → SB-3d.
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
def iqm() -> Dict[str, Any]:
    with open(os.path.join(_SCRIPTS, "data", "ingredient_quality_map.json")) as f:
        return json.load(f)


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


# Species → aliases that move from IQM brown_kelp to their canonical home
_ASCOPHYLLUM_ALIASES = (
    "kelp powder",
    "norwegian kelp",
    "ascophyllum nodosum",
    "rockweed",
)

_SACCHARINA_JAPONICA_ALIASES = (
    "brown seaweed (laminaria japonica) extract",
    "japanese kelp extract",
)

_UNDARIA_ALIASES = (
    "brown kelp undaria pinnatifida powder",
)


def test_iqm_brown_kelp_no_longer_carries_ascophyllum_aliases(iqm):
    """Ascophyllum nodosum (UNII 168S4EO8YJ — Rockweed) aliases must
    leave IQM brown_kelp. Different species from Laminaria; their
    canonical home is botanical_ingredients.kelp_powder."""
    bk = iqm.get("brown_kelp") or {}
    form = (bk.get("forms") or {}).get("brown kelp powder") or {}
    aliases = _lc(form.get("aliases", []))
    for forbidden in _ASCOPHYLLUM_ALIASES:
        assert forbidden not in aliases, (
            f"§8.5: Ascophyllum nodosum alias '{forbidden}' must NOT live "
            f"in IQM brown_kelp.forms['brown kelp powder'] — Ascophyllum "
            f"(UNII 168S4EO8YJ) is a different species from Laminaria "
            f"(UNII 4R2124HE76). Got: {form.get('aliases')}"
        )


def test_iqm_brown_kelp_no_longer_carries_saccharina_aliases(iqm):
    """Saccharina japonica (UNII WE98HW412B — Kombu / Japanese Kelp)
    aliases must leave IQM brown_kelp. Their canonical home is
    botanical_ingredients.kombu."""
    bk = iqm.get("brown_kelp") or {}
    form = (bk.get("forms") or {}).get("brown kelp powder") or {}
    aliases = _lc(form.get("aliases", []))
    for forbidden in _SACCHARINA_JAPONICA_ALIASES:
        assert forbidden not in aliases, (
            f"§8.5: Saccharina japonica alias '{forbidden}' must NOT live "
            f"in IQM brown_kelp — canonical home is botanical_ingredients."
            f"kombu. Got: {form.get('aliases')}"
        )


def test_iqm_brown_kelp_no_longer_carries_undaria_aliases(iqm):
    """Undaria pinnatifida (UNII ICV1OK7M1S — Wakame) aliases must
    leave IQM brown_kelp. Canonical home is botanical_ingredients.wakame."""
    bk = iqm.get("brown_kelp") or {}
    form = (bk.get("forms") or {}).get("brown kelp powder") or {}
    aliases = _lc(form.get("aliases", []))
    for forbidden in _UNDARIA_ALIASES:
        assert forbidden not in aliases, (
            f"§8.5: Undaria pinnatifida alias '{forbidden}' must NOT live "
            f"in IQM brown_kelp — canonical home is botanical_ingredients."
            f"wakame. Got: {form.get('aliases')}"
        )


def test_botanical_kelp_powder_owns_ascophyllum_aliases(botanicals):
    """botanical_ingredients.kelp_powder (UNII 168S4EO8YJ = Ascophyllum
    nodosum) must own the migrated Ascophyllum identity aliases."""
    e = _find(botanicals.get("botanical_ingredients", []), "kelp_powder")
    assert e, "botanical_ingredients.kelp_powder missing"
    assert (e.get("external_ids") or {}).get("unii") == "168S4EO8YJ"
    aliases = _lc(e.get("aliases", []))
    for required in _ASCOPHYLLUM_ALIASES:
        assert required in aliases, (
            f"botanical_ingredients.kelp_powder must alias '{required}' "
            f"(migrated from IQM brown_kelp §8.5 cleanup). Got: "
            f"{e.get('aliases')}"
        )


def test_botanical_kombu_owns_saccharina_aliases(botanicals):
    """botanical_ingredients.kombu (UNII WE98HW412B = Saccharina
    japonica / Laminaria japonica) must own the migrated Saccharina
    identity aliases."""
    e = _find(botanicals.get("botanical_ingredients", []), "kombu")
    assert e, "botanical_ingredients.kombu missing"
    assert (e.get("external_ids") or {}).get("unii") == "WE98HW412B"
    aliases = _lc(e.get("aliases", []))
    for required in _SACCHARINA_JAPONICA_ALIASES:
        assert required in aliases, (
            f"botanical_ingredients.kombu must alias '{required}' "
            f"(migrated from IQM brown_kelp §8.5 cleanup). Got: "
            f"{e.get('aliases')}"
        )


def test_botanical_wakame_owns_undaria_alias(botanicals):
    """botanical_ingredients.wakame (UNII ICV1OK7M1S = Undaria
    pinnatifida) must own the migrated Undaria identity alias."""
    e = _find(botanicals.get("botanical_ingredients", []), "wakame")
    assert e, "botanical_ingredients.wakame missing"
    assert (e.get("external_ids") or {}).get("unii") == "ICV1OK7M1S"
    aliases = _lc(e.get("aliases", []))
    for required in _UNDARIA_ALIASES:
        assert required in aliases, (
            f"botanical_ingredients.wakame must alias '{required}' "
            f"(migrated from IQM brown_kelp §8.5 cleanup). Got: "
            f"{e.get('aliases')}"
        )


def test_iqm_brown_kelp_keeps_generic_kelp_aliases(iqm):
    """SB-3b is scoped to the species split. Generic / ambiguous-species
    kelp aliases (Sea Kelp, Pacific/Atlantic kelp, brown seaweed) stay
    in brown_kelp — they represent the legitimate generic-kelp
    Laminaria pathway."""
    bk = iqm.get("brown_kelp") or {}
    form = (bk.get("forms") or {}).get("brown kelp powder") or {}
    aliases = _lc(form.get("aliases", []))
    for kept in (
        "sea kelp",
        "organic sea kelp",
        "pacific kelp",
        "atlantic kelp",
        "north atlantic kelp",
        "brown seaweed",
        "brown seaweed extract",
        "brown seaweed concentrate",
    ):
        assert kept in aliases, (
            f"SB-3b keeps generic-kelp aliases. '{kept}' must remain in "
            f"IQM brown_kelp.forms['brown kelp powder']. Got: "
            f"{form.get('aliases')}"
        )
