"""Phase 2 regression tests for the 2026-05-22 unmapped-resolution batch.

Pins the expected end-state after the approved Lane A data edits land:

- A1: ``laminaria japonica aresch extract`` alias added to
  ``botanical_ingredients.kombu`` (UNII WE98HW412B for both — same plant,
  "Aresch" is the botanical authority suffix for *Laminaria japonica*
  Areschoug).
- A3: ``omega 3 fatty acids`` / ``omega-3 fatty acids`` aliases added to
  IQM ``fish_oil`` form ``fish oil (unspecified)``.
- A4: ``vitex chasteberry`` alias added to IQM ``chasteberry`` form
  ``chasteberry (unspecified)`` (UNII 433OSF3U8A match).
- B1: ``curcumin`` added to IQM ``Curcumin`` parent aliases (was empty);
  ``curcumin`` REMOVED from IQM ``turmeric`` form ``turmeric
  (unspecified)`` aliases (§8.5 misplacement — Curcumin UNII
  IT942ZTH98 ≠ Turmeric UNII 856YO1Z64F).
- N1: new ``clinically_relevant_strains`` entry
  ``STRAIN_PLANTARUM_LP01`` (Probiotical S.p.A. LMG P-21021).
- N2: new ``clinically_relevant_strains`` entry
  ``STRAIN_LACTIS_BS01`` (Probiotical S.p.A. LMG P-21384).

Deferred (separate batches): A2 NW coffee (green_coffee_bean entry §8.5
contaminated), A5 aloe vera (multiple §8.5 contaminations on
aloe_vera entry), A6/N3 Bb-02 strain (identity needs label co-strain
audit), Items 11/12 flax/soy (no canonical entry exists).
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SCRIPTS = os.path.join(_ROOT, "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)


# ---------------------------------------------------------------------------
# Direct DB-state assertions (no pipeline run needed)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def iqm() -> Dict[str, Any]:
    with open(os.path.join(_SCRIPTS, "data", "ingredient_quality_map.json")) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def botanicals() -> Dict[str, Any]:
    with open(os.path.join(_SCRIPTS, "data", "botanical_ingredients.json")) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def strains() -> Dict[str, Any]:
    with open(os.path.join(_SCRIPTS, "data", "clinically_relevant_strains.json")) as f:
        return json.load(f)


def _lc(values):
    return [(v or "").lower() for v in (values or [])]


# ---------------------------------------------------------------------------
# A1 — kombu alias
# ---------------------------------------------------------------------------

def test_a1_kombu_aliases_laminaria_japonica_aresch_extract(botanicals):
    """kombu entry must alias 'laminaria japonica aresch extract' so the
    Legion product label ("Laminaria japonica Aresch extract" x3) maps
    correctly. UNII WE98HW412B for both source and target."""
    for e in botanicals.get("botanical_ingredients", []):
        if isinstance(e, dict) and e.get("id") == "kombu":
            aliases = _lc(e.get("aliases", []))
            assert "laminaria japonica aresch extract" in aliases, (
                f"kombu must alias 'laminaria japonica aresch extract'. "
                f"Got: {e.get('aliases')}"
            )
            assert e.get("external_ids", {}).get("unii") == "WE98HW412B"
            return
    pytest.fail("kombu entry not found in botanical_ingredients.json")


# ---------------------------------------------------------------------------
# A3 — fish_oil (unspecified) 'omega 3 fatty acids' alias
# ---------------------------------------------------------------------------

def test_a3_fish_oil_aliases_omega_3_fatty_acids(iqm):
    """IQM fish_oil form 'fish oil (unspecified)' must alias the bare
    descriptor 'omega 3 fatty acids' (and the hyphenated variant
    'omega-3 fatty acids') so labels using that wording map without
    parent fallback."""
    form = (iqm.get("fish_oil", {}).get("forms", {})
            .get("fish oil (unspecified)") or {})
    aliases = _lc(form.get("aliases", []))
    assert "omega 3 fatty acids" in aliases or "omega-3 fatty acids" in aliases, (
        f"fish_oil (unspecified) must alias 'omega 3 fatty acids' (with or "
        f"without hyphen). Got aliases: {form.get('aliases')}"
    )


# ---------------------------------------------------------------------------
# A4 — chasteberry (unspecified) 'vitex chasteberry' alias
# ---------------------------------------------------------------------------

def test_a4_chasteberry_unspecified_aliases_vitex_chasteberry(iqm):
    """IQM chasteberry form 'chasteberry (unspecified)' must alias the
    common label phrasing 'vitex chasteberry'. UNII 433OSF3U8A for the
    new alias matches the chasteberry/Vitex agnus-castus parent."""
    form = (iqm.get("chasteberry", {}).get("forms", {})
            .get("chasteberry (unspecified)") or {})
    aliases = _lc(form.get("aliases", []))
    assert "vitex chasteberry" in aliases, (
        f"chasteberry (unspecified) must alias 'vitex chasteberry'. "
        f"Got: {form.get('aliases')}"
    )


# ---------------------------------------------------------------------------
# B1 — Curcumin parent gains 'curcumin'; Turmeric (unspecified) loses it
# ---------------------------------------------------------------------------

def test_b1a_curcumin_parent_aliases_includes_curcumin(iqm):
    """IQM Curcumin parent entry must list 'curcumin' (case-insensitive)
    in its parent-level aliases so bare 'Curcumin' label text matches
    the Curcumin parent (UNII IT942ZTH98) — not the §8.5-misplaced
    Turmeric form."""
    cur = iqm.get("curcumin", {})
    aliases = _lc(cur.get("aliases", []))
    assert "curcumin" in aliases, (
        f"Curcumin parent must alias 'curcumin'. Got: {cur.get('aliases')}"
    )
    # External identity preserved
    assert cur.get("external_ids", {}).get("unii") == "IT942ZTH98"


def test_b1b_turmeric_unspecified_form_does_not_alias_curcumin(iqm):
    """§8.5 fix: Turmeric (UNII 856YO1Z64F) is a different substance
    from Curcumin (UNII IT942ZTH98). The historical alias 'curcumin' on
    the turmeric (unspecified) form was a misplacement that intercepted
    bare 'curcumin' label text before the Curcumin parent could match.
    Removing it restores correct routing."""
    form = (iqm.get("turmeric", {}).get("forms", {})
            .get("turmeric (unspecified)") or {})
    aliases = _lc(form.get("aliases", []))
    assert "curcumin" not in aliases, (
        f"§8.5: 'curcumin' alias must be removed from Turmeric (unspecified) "
        f"form — Turmeric UNII 856YO1Z64F ≠ Curcumin UNII IT942ZTH98. "
        f"Got: {form.get('aliases')}"
    )


# ---------------------------------------------------------------------------
# N1 — STRAIN_PLANTARUM_LP01 new entry
# ---------------------------------------------------------------------------

def _find_strain(strains_db: Dict[str, Any], strain_id: str) -> Dict[str, Any] | None:
    for e in strains_db.get("clinically_relevant_strains", []):
        if isinstance(e, dict) and e.get("id") == strain_id:
            return e
    return None


def test_n1_lp01_strain_entry_exists(strains):
    """New entry: Lactiplantibacillus plantarum LP01 (Probiotical
    S.p.A., LMG P-21021). Sourced via 3 content-verified PMIDs
    (Vicariotto 2014 BV trial, Orlandoni 2021 IntegPRO, Moschonis
    2026 depression RCT)."""
    e = _find_strain(strains, "STRAIN_PLANTARUM_LP01")
    assert e is not None, "STRAIN_PLANTARUM_LP01 entry missing"
    assert "LP01" in (e.get("standard_name") or "")
    aliases = _lc(e.get("aliases", []))
    for required in ("lp01", "lp-01", "lmg p-21021"):
        assert required in aliases, (
            f"STRAIN_PLANTARUM_LP01 must alias '{required}'. Got: {e.get('aliases')}"
        )


# ---------------------------------------------------------------------------
# N2 — STRAIN_LACTIS_BS01 new entry
# ---------------------------------------------------------------------------

def test_n2_bs01_strain_entry_exists(strains):
    """New entry: Bifidobacterium animalis subsp. lactis BS01
    (Probiotical S.p.A., LMG P-21384). Sourced via 2 content-verified
    PMIDs (Del Piano 2010 evacuation RCT, Orlandoni 2021 IntegPRO)."""
    e = _find_strain(strains, "STRAIN_LACTIS_BS01")
    assert e is not None, "STRAIN_LACTIS_BS01 entry missing"
    assert "BS01" in (e.get("standard_name") or "")
    aliases = _lc(e.get("aliases", []))
    for required in ("bs01", "bs-01", "lmg p-21384"):
        assert required in aliases, (
            f"STRAIN_LACTIS_BS01 must alias '{required}'. Got: {e.get('aliases')}"
        )


# ---------------------------------------------------------------------------
# Metadata hygiene
# ---------------------------------------------------------------------------

def test_metadata_updated_after_batch(iqm, botanicals, strains):
    """Every touched data file must have an updated _metadata.last_updated
    timestamp and accurate total_entries count."""
    for db, label in [(iqm, "ingredient_quality_map"),
                      (botanicals, "botanical_ingredients"),
                      (strains, "clinically_relevant_strains")]:
        meta = db.get("_metadata", {})
        assert meta.get("schema_version"), f"{label}: schema_version missing"
        assert meta.get("last_updated"), f"{label}: last_updated missing"
        assert isinstance(meta.get("total_entries"), int), (
            f"{label}: total_entries must be int. Got: {meta.get('total_entries')}"
        )
