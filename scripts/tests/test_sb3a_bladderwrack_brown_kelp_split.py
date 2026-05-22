"""SB-3a: Bladderwrack (Fucus vesiculosus) species split from IQM brown_kelp.

First batch of the 2026-05-22 brown-algae §7.5/§8.5 decomposition.

Why this matters

IQM ``brown_kelp.forms['brown kelp powder']`` historically mixed at
least six distinct brown-algae species under one entry:

  - Fucus vesiculosus (Bladderwrack)         UNII 535G2ABX9M
  - Laminaria spp. / generic kelp            UNII 4R2124HE76
  - Saccharina japonica (Kombu / J. kelp)    UNII WE98HW412B
  - Ascophyllum nodosum (Rockweed)           UNII 168S4EO8YJ
  - Undaria pinnatifida (Wakame)             UNII ICV1OK7M1S
  - Generic "brown seaweed"                  (varies)

10 distinct UNIIs in the aliases of a single form. Different species
have different bioactive profiles (fucoidan vs. fucoxanthin vs.
laminarin vs. iodine), different traditional uses, and different
regulatory profiles. Lumping them together silently mis-scored
~4 products with "Bladderwrack" labels (currently route to brown_kelp
generic-kelp pathway instead of the standardized fucoidan/iodine
pathway that lives in ``standardized_botanicals.bladderwrack``).

SB-3a Scope (this commit)

- Remove the Fucus-vesiculosus / bladderwrack aliases from
  ``IQM.brown_kelp.forms['brown kelp powder']``.
- Add the same aliases (with case variants) to
  ``standardized_botanicals.bladderwrack``, which already declares
  fucoidan + iodine as standardization markers and carries the correct
  Fucus vesiculosus UNII 535G2ABX9M.
- Verify the historical "Bladderwrack Whole Plant Extract" parent
  fallback (Ora pid=259887) now resolves to bladderwrack rather than
  brown_kelp.

Out of scope (deferred to SB-3b/c/d)

- Ascophyllum / rockweed split → SB-3b
- Saccharina japonica (Japanese kelp) cleanup → SB-3b
- Undaria (wakame) alias removal from brown_kelp → SB-3b
- botanical_ingredients.kelp_powder decontamination
  (Ecklonia / Alaria misplacements) → SB-3c
- New botanical canonicals for Ecklonia spp. → SB-3d
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
def sbot() -> Dict[str, Any]:
    with open(os.path.join(_SCRIPTS, "data", "standardized_botanicals.json")) as f:
        return json.load(f)


def _lc(values: List[str]) -> List[str]:
    return [(v or "").strip().lower() for v in (values or [])]


# Fucus / bladderwrack family — these must NOT live in IQM brown_kelp
# and MUST live in standardized_botanicals.bladderwrack.
_BLADDERWRACK_FAMILY = (
    "bladder wrack",
    "bladderwrack",
    "fucus vesiculosus",
    "fucus vesiculosus extract",
    "bladder wrack extract",
    "bladderwrack extract",
)


def test_iqm_brown_kelp_no_longer_carries_bladderwrack_aliases(iqm):
    """IQM brown_kelp form 'brown kelp powder' must NOT alias Fucus
    vesiculosus / bladderwrack. Bladderwrack (UNII 535G2ABX9M) is a
    different species from Laminaria/generic brown kelp (UNII
    4R2124HE76); the alias was a §7.5/§8.5 misplacement that routed
    bladderwrack labels to the generic kelp pathway instead of the
    standardized fucoidan/iodine bonus pathway."""
    bk = iqm.get("brown_kelp") or {}
    form = (bk.get("forms") or {}).get("brown kelp powder") or {}
    aliases = _lc(form.get("aliases", []))
    for forbidden in _BLADDERWRACK_FAMILY:
        assert forbidden not in aliases, (
            f"§8.5: bladderwrack family alias '{forbidden}' must NOT live "
            f"in IQM brown_kelp.forms['brown kelp powder'] — Fucus vesiculosus "
            f"is a different species from brown kelp / Laminaria. Aliases: "
            f"{form.get('aliases')}"
        )


def test_standardized_botanicals_bladderwrack_owns_the_aliases(sbot):
    """standardized_botanicals.bladderwrack (UNII 535G2ABX9M = Fucus
    vesiculosus) is the canonical home for all bladderwrack identity
    text. After SB-3a it must carry the full alias family migrated
    out of IQM brown_kelp PLUS the historical 'Bladderwrack Whole
    Plant Extract' label phrasing that surfaced in the 2026-05-22
    parent_fallback report (Ora pid=259887)."""
    entry = None
    for e in sbot.get("standardized_botanicals", []):
        if isinstance(e, dict) and e.get("id") == "bladderwrack":
            entry = e
            break
    assert entry is not None, "standardized_botanicals.bladderwrack missing"

    aliases = _lc(entry.get("aliases", []))
    for required in _BLADDERWRACK_FAMILY:
        assert required in aliases, (
            f"standardized_botanicals.bladderwrack must alias "
            f"'{required}' (migrated from IQM brown_kelp §8.5 cleanup). "
            f"Got: {entry.get('aliases')}"
        )
    # The label-text variant from Ora pid=259887
    assert "bladderwrack whole plant extract" in aliases, (
        f"standardized_botanicals.bladderwrack must alias "
        f"'bladderwrack whole plant extract' — historical parent_fallback "
        f"target for Ora pid=259887 (the Phase 1 Item 3 case). Got: "
        f"{entry.get('aliases')}"
    )

    # External identity preserved
    assert (entry.get("external_ids") or {}).get("unii") == "535G2ABX9M", (
        f"standardized_botanicals.bladderwrack must keep UNII 535G2ABX9M "
        f"(Fucus vesiculosus). Got: {entry.get('external_ids')}"
    )

    # Markers preserved — fucoidan + iodine are the standardization basis
    markers = _lc(entry.get("markers", []))
    assert "fucoidan" in markers, (
        f"standardized_botanicals.bladderwrack must keep 'fucoidan' marker "
        f"(the bonus-eligibility standardization basis). Got: "
        f"{entry.get('markers')}"
    )


def test_iqm_brown_kelp_keeps_generic_kelp_aliases(iqm):
    """SB-3a is scoped to the bladderwrack split. Generic Sea Kelp /
    Atlantic Kelp / Brown Seaweed aliases stay in brown_kelp — they
    are species-ambiguous and represent the legitimate generic-kelp
    pathway."""
    bk = iqm.get("brown_kelp") or {}
    form = (bk.get("forms") or {}).get("brown kelp powder") or {}
    aliases = _lc(form.get("aliases", []))
    for kept in ("sea kelp", "organic sea kelp", "brown seaweed"):
        assert kept in aliases, (
            f"SB-3a keeps generic kelp aliases. '{kept}' must remain in "
            f"brown_kelp. Got: {form.get('aliases')}"
        )
