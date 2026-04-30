"""
Sprint D1.4 regression tests — D-Mannose + branded fiber DB routing.

Context: D-Mannose is clinically validated for UTI prophylaxis (Kranjcec
2014, JAMA Urol RCT). Prior to D1.4 it existed only in
harmful_additives.json (flagged as bulk-sweetener misuse) without an IQM
entry, so products declaring D-Mannose as an active got the harmful-
additive penalty and ZERO quality credit.

Similarly, VitaFiber (BioNeutra's branded IMO prebiotic fiber) and
CreaFibe Cellulose (branded MCC variant) had no DB entry — 4 rows each
landed in the silently-mapped set.

Fix:
1. Added ``d_mannose`` to ingredient_quality_map.json with bio_score=9,
   dosage_importance=1.5, primary UTI alias set, Kranjcec 2014 reference.
2. Added ``d-mannose`` to cross_db_overlap_allowlist (IQM + harmful +
   standardized_botanicals = intentional multi-DB).
3. Confirmed ADD_D_MANNOSE severity_level="low" in harmful_additives so
   the enricher's active-source suppression (see
   ``_recognition_blocks_scoring`` policy) correctly applies IQM quality
   score without piling on the harmful penalty.
4. Added NHA_VITAFIBER_IMO + NHA_CREAFIBE_CELLULOSE to
   other_ingredients.json as non-scoring fiber carriers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3

DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


@pytest.fixture(scope="module")
def iqm() -> dict:
    return json.loads((DATA_DIR / "ingredient_quality_map.json").read_text())


# ---------------------------------------------------------------------------
# IQM d_mannose entry — schema invariants
# ---------------------------------------------------------------------------


class TestDMannoseInIqm:
    """The IQM entry must exist with verified identifiers and scorable form."""

    def test_d_mannose_key_present(self, iqm) -> None:
        assert "d_mannose" in iqm, (
            "D-Mannose IQM entry missing. Without it, UTI products scoring "
            "D-Mannose as active get zero quality credit + full harmful penalty."
        )

    def test_d_mannose_has_verified_cui(self, iqm) -> None:
        entry = iqm["d_mannose"]
        # UMLS C0024742 is the verified D-Mannose concept (GeneralizedChemical).
        assert entry.get("cui") == "C0024742"

    def test_d_mannose_has_primary_form(self, iqm) -> None:
        forms = iqm["d_mannose"].get("forms", {})
        assert "d-mannose" in forms
        form = forms["d-mannose"]
        assert form.get("bio_score") == 9
        assert form.get("dosage_importance") == 1.5
        ext = form.get("external_ids", {})
        assert ext.get("unii") == "PHA4727WTP"
        assert ext.get("cas") == "530-26-7"


class TestDMannoseEnricherMatch:
    """The enricher resolves D-Mannose label variants to d_mannose with bio_score=9."""

    @pytest.mark.parametrize("raw", [
        "D-Mannose",
        "d-mannose",
        "D Mannose",
        "d mannose",
        "Mannose",
        "D-Mannose Powder",
        "Pure D-Mannose",
    ])
    def test_variants_score(self, enricher, iqm, raw) -> None:
        result = enricher._match_quality_map(raw, raw, iqm)
        assert result is not None, f"{raw!r} did not match IQM"
        assert result.get("canonical_id") == "d_mannose", (
            f"{raw!r} resolved to {result.get('canonical_id')!r}; must be 'd_mannose'."
        )
        assert result.get("bio_score") == 9

    def test_d_mannose_phase3_constraint_path(self, enricher, iqm) -> None:
        # Cleaner (post-D1.4) will emit canonical_id='d_mannose' via
        # reverse-index on the IQM entry. Phase 3 hard-constraint should
        # confirm the match stays on d_mannose.
        result = enricher._match_quality_map(
            "D-Mannose", "D-Mannose", iqm, cleaner_canonical_id="d_mannose",
        )
        assert result is not None
        assert result.get("canonical_id") == "d_mannose"
        assert result.get("bio_score") == 9


# ---------------------------------------------------------------------------
# Cross-DB overlap allowlist guard
# ---------------------------------------------------------------------------


class TestDMannoseCrossDbOverlapAllowlist:
    """D-Mannose is intentionally in IQM + harmful_additives + standardized_botanicals."""

    def test_d_mannose_in_overlap_allowlist(self) -> None:
        data = json.loads((DATA_DIR / "cross_db_overlap_allowlist.json").read_text())
        terms = [e.get("term_normalized", "").lower() for e in data.get("allowed_overlaps", [])]
        assert "d-mannose" in terms, (
            "D-Mannose must be in cross_db_overlap_allowlist to document its "
            "intentional presence across IQM (scoring), harmful_additives "
            "(sweetener-misuse signal, severity=low), and standardized_botanicals "
            "(evidence bonus)."
        )


# ---------------------------------------------------------------------------
# Harmful_additives entry kept at severity_level="low"
# ---------------------------------------------------------------------------


class TestDMannoseHarmfulLowSeverity:
    """The harmful_additives entry stays at low severity (quality signal only)."""

    def test_d_mannose_harmful_severity_low(self) -> None:
        data = json.loads((DATA_DIR / "harmful_additives.json").read_text())
        entries = [
            e for e in data.get("harmful_additives", [])
            if isinstance(e, dict) and e.get("id") == "ADD_D_MANNOSE"
        ]
        assert len(entries) == 1
        assert entries[0].get("severity_level") == "low", (
            "ADD_D_MANNOSE must stay severity_level='low' so the enricher's "
            "active-source suppression policy (_recognition_blocks_scoring) "
            "correctly lets IQM quality credit fire without penalty pile-on."
        )


# ---------------------------------------------------------------------------
# VitaFiber + CreaFibe — branded fiber routing
# ---------------------------------------------------------------------------


class TestBrandedFiberRouting:
    """VitaFiber + CreaFibe resolve to other_ingredients (non-scoring carriers)."""

    @pytest.mark.parametrize("raw,expected_id", [
        ("VitaFiber", "NHA_VITAFIBER_IMO"),
        ("VitaFiber Prebiotic", "NHA_VITAFIBER_IMO"),
        ("vitafiber imo", "NHA_VITAFIBER_IMO"),
        ("CreaFibe", "NHA_CREAFIBE_CELLULOSE"),
        ("creafibe cellulose", "NHA_CREAFIBE_CELLULOSE"),
    ])
    def test_branded_fiber_resolves_to_other_ingredients(
        self, normalizer, raw, expected_id,
    ) -> None:
        result = normalizer._resolve_canonical_identity(raw, raw_name=raw)
        assert result is not None, f"{raw!r} did not resolve"
        canonical_id, source_db = result
        assert canonical_id == expected_id, (
            f"{raw!r} resolved to {canonical_id!r}; expected {expected_id!r}."
        )
        assert source_db == "other_ingredients"

    def test_vitafiber_entry_schema(self) -> None:
        """Phase 4c (2026-04-30) canonicalized `fiber_plant` → `filler`. The
        prebiotic-fiber dimension now lives in `functional_roles[]`."""
        data = json.loads((DATA_DIR / "other_ingredients.json").read_text())
        entries = [
            e for e in data.get("other_ingredients", [])
            if isinstance(e, dict) and e.get("id") == "NHA_VITAFIBER_IMO"
        ]
        assert len(entries) == 1
        entry = entries[0]
        assert entry.get("category") == "filler"
        assert "prebiotic_fiber" in (entry.get("functional_roles") or [])
        assert entry.get("is_additive") is True
        assert entry.get("cui_status") == "governed_null"

    def test_creafibe_entry_schema(self) -> None:
        """Phase 4c canonicalized `fiber_plant` → `filler`."""
        data = json.loads((DATA_DIR / "other_ingredients.json").read_text())
        entries = [
            e for e in data.get("other_ingredients", [])
            if isinstance(e, dict) and e.get("id") == "NHA_CREAFIBE_CELLULOSE"
        ]
        assert len(entries) == 1
        entry = entries[0]
        assert entry.get("category") == "filler"
        assert "prebiotic_fiber" in (entry.get("functional_roles") or [])
        assert entry.get("is_additive") is True
