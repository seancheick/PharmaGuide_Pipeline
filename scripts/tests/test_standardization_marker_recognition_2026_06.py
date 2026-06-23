"""Standardization-marker recognition (2026-06, unmapped-triage marker pass).

Bare standardization-marker rows ("Rosavins", "Salidrosides", "Astragaloside")
appear on labels as sub-rows of a standardized botanical (e.g. "Rhodiola ...
3% rosavins / 1% salidroside"). They are NOT standalone scorable actives, and
the parent botanical already owns any marker credit via the Identity-vs-
Bioactivity split (botanical_marker_contributions.json + delivers_markers).

This locks the ONLY correct disposition for a bare marker row: recognized for
label fidelity (leaves the unmapped queue), routed through `other_ingredients`
so it is **provably credit-free** — NOT a scorable active, NOT an A5b
standardized-botanical anchor (canonical_source_db != "standardized_botanicals"),
and NO Section C clinical contribution (canonical_id absent from
botanical_marker_contributions → delivers_markers == []).

SCOPE — deliberately excluded, with protective guards below:
  - "AKBA" is a real IQM-scorable parent (`akba`, bio 5.0). Recognizing it as a
    marker would STRIP credit — test_akba_stays_iqm_scorable locks that out.
  - "Silibinins" ≡ the IQM `silibinin` flavonolignan (a form under `milk_thistle`,
    scorable). It is the milk-thistle active, not a context-only marker, so it is
    handled in the verified-alias batch (double-count risk), NOT here.
"""
import copy
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3
from score_supplements import SupplementScorer

# Verified-clean standardization markers: no IQM/botanical/standardized identity,
# currently true unmapped actives (recognizing them removes zero credit). Each was
# per-item identity-checked; markers whose compound IS an IQM identity are deferred
# to the alias batch and NOT listed here — silibinin (->milk_thistle), caffeoylquinic
# acids / chlorogenic acid, isoflavones, hypericin are all IQM-scored.
CLEAN_MARKERS = [
    # batch 1 — Rhodiola / Astragalus
    "Rosavins", "Salidrosides", "Astragaloside",
    # batch 2 — St John's Wort / Ginkgo / English ivy
    "Dianthrones", "Flavone Glycosides", "Terpene Lactone", "Hederacoside C",
]


@pytest.fixture(scope="module")
def normalizer():
    return EnhancedDSLDNormalizer()


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.fixture(scope="module")
def scorer():
    return SupplementScorer()


def _single_active_product(name, qty_mg=50):
    return {
        "id": f"marker-test-{name}",
        "fullName": "Marker Recognition Test",
        "brandName": "Test Brand",
        "offMarket": 0,
        "events": [],
        "ingredientRows": [
            {"name": name, "category": "", "ingredientGroup": "",
             "quantity": [{"quantity": qty_mg, "unit": "mg"}], "forms": [], "nestedRows": []}
        ],
        "otherIngredients": {"ingredients": []},
    }


def _clean_enrich(normalizer, enricher, name):
    cleaned = normalizer.normalize_product(_single_active_product(name))
    enriched, _ = enricher.enrich_product(copy.deepcopy(cleaned))
    return enriched


# ── recognition + non-scorable disposition ──────────────────────────────────
@pytest.mark.parametrize("name", CLEAN_MARKERS)
def test_marker_recognized_via_other_ingredients(enricher, name):
    rec = enricher._is_recognized_non_scorable(name, name)
    assert rec is not None, f"{name!r} should be recognized (currently unmapped)"
    assert rec.get("recognition_source") == "other_ingredients", (
        f"{name!r} must route through the credit-free other_ingredients lane, got {rec}"
    )


@pytest.mark.parametrize("name", CLEAN_MARKERS)
def test_marker_is_not_a_scorable_active(normalizer, enricher, name):
    enriched = _clean_enrich(normalizer, enricher, name)
    iqd = enriched["ingredient_quality_data"]
    scorable = [r.get("name") for r in iqd.get("ingredients_scorable", [])]
    assert name not in scorable, f"{name!r} must NOT be a scorable active"
    assert iqd.get("unmapped_scorable_count", 0) == 0, (
        f"{name!r} must leave the enricher unmapped queue"
    )


# ── zero-credit lock (the whole point: provably no score movement) ───────────
@pytest.mark.parametrize("name", CLEAN_MARKERS)
def test_marker_creates_no_a5b_or_section_c_credit(normalizer, enricher, scorer, name):
    enriched = _clean_enrich(normalizer, enricher, name)
    # A5b gate: a marker-only product must not present a standardized-botanical anchor
    assert scorer._has_standardized_botanical_anchor(enriched) is False, (
        f"{name!r} must not trip the A5b standardized-botanical anchor"
    )
    # A5b points source: marker not collected into the standardized_botanicals list
    std_bots = (enriched.get("formulation_data") or {}).get("standardized_botanicals") or []
    std_names = " ".join(str(s).lower() for s in std_bots)
    assert name.lower() not in std_names, f"{name!r} must not feed A5b points"
    # Section C: no clinical evidence contribution from a bare marker row
    clinical = (enriched.get("evidence_data") or {}).get("clinical_matches") or []
    assert len(clinical) == 0, f"{name!r} must not add Section C clinical credit, got {clinical}"


# ── leaves the cleaner unmapped snapshot ─────────────────────────────────────
@pytest.mark.parametrize("name", CLEAN_MARKERS)
def test_marker_leaves_cleaner_unmapped_queue(normalizer, name):
    snap = normalizer.get_unmapped_snapshot()
    normalizer.normalize_product(_single_active_product(name))
    delta = normalizer.get_unmapped_delta(snap)
    unmapped_names = [u.get("name") for u in delta.get("unmapped", [])]
    assert name not in unmapped_names, f"{name!r} must not appear in the unmapped delta"


# ── protective guards: do NOT let the marker pass strip real IQM identities ──
def test_akba_stays_iqm_scorable(normalizer, enricher):
    """AKBA has its own IQM identity (bio 5.0) — it is NOT a context-only marker."""
    enriched = _clean_enrich(normalizer, enricher, "AKBA")
    iqd = enriched["ingredient_quality_data"]
    scorable = iqd.get("ingredients_scorable", [])
    akba = [r for r in scorable if (r.get("canonical_id") or "").lower() == "akba"]
    assert akba, "AKBA must remain an IQM-scorable active (canonical_id=akba)"
    assert (akba[0].get("canonical_source_db") or "") == "ingredient_quality_map"


def test_silibinin_stays_milk_thistle_iqm(normalizer, enricher):
    """'silibinin' is a milk_thistle IQM form — the milk-thistle active, not a
    context-only marker. Guards against a future marker batch stripping it."""
    enriched = _clean_enrich(normalizer, enricher, "Silibinin")
    iqd = enriched["ingredient_quality_data"]
    scorable = [(r.get("canonical_id") or "").lower() for r in iqd.get("ingredients_scorable", [])]
    assert "milk_thistle" in scorable or "silibinin" in scorable, (
        "silibinin must remain an IQM-scorable milk_thistle form, not a non-scorable marker"
    )
