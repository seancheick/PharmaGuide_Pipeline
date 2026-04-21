"""
Sprint D5.3 regression — detail blob top-level key contract.

Every product's detail blob MUST carry the keys the Flutter app consumes.
If the pipeline stops emitting any of these keys, the Flutter UI breaks
silently (empty sections, missing safety cards, profile-gated warnings
disappearing).

The contract is sampled from a live ``/tmp/pharmaguide_release_build``
build. When running locally without a build, the test is skipped with a
clear marker so CI on a clean environment doesn't fail spuriously.

Required keys audited here (mapped to consumer features):

| Key | Flutter consumer |
|---|---|
| ``ingredients`` | Active-ingredient section + ingredient-detail sheet |
| ``inactive_ingredients`` | Excipient density card |
| ``warnings`` | InteractionWarningsList (always shown) |
| ``warnings_profile_gated`` | InteractionWarningsList (profile-filtered) |
| ``section_breakdown`` | ScoreBreakdownCard |
| ``score_bonuses`` | Pros list |
| ``score_penalties`` | Cons list |
| ``interaction_summary`` | InteractionWarnings (condition/drug banners) |
| ``nutrition_detail`` | NutritionPanel |
| ``unmapped_actives`` | UnmappedActivesDisclosure |
| ``proprietary_blend_detail`` | BlendWarningBanner |
| ``certification_detail`` | CertificationDetailSection |
| ``evidence_data`` | EvidenceDetailSection |
| ``formulation_detail`` | FormulationDetailSection |
| ``manufacturer_detail`` | ManufacturerViolationsSection |
| ``probiotic_detail`` | ProbioticDetailSection |
| ``synergy_detail`` | SynergyDetailSection |
| ``serving_info`` | Refill reminder card |
| ``rda_ul_data`` | B7 UL aggregated-warning card (D4.3 teratogenicity) |

When ``collect_rda_ul_data: true`` in config, ``rda_ul_data`` always
present; when false, the key may still exist but with
``collection_reason="disabled_by_config"``. We accept both states for
the presence check.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


# MANDATORY top-level keys — must be present on every single product,
# regardless of its ingredients. If any is missing, Flutter crashes or
# renders a blank section.
REQUIRED_TOP_LEVEL_KEYS = {
    "ingredients",
    "inactive_ingredients",
    "warnings",
    "warnings_profile_gated",
    "section_breakdown",
    "score_bonuses",
    "score_penalties",
    "nutrition_detail",
    "unmapped_actives",
    "proprietary_blend_detail",
    "certification_detail",
    "evidence_data",
    "formulation_detail",
    "manufacturer_detail",
    "serving_info",
    "rda_ul_data",
}

# OPTIONAL top-level keys — only emitted by the enricher when the
# underlying feature applies (e.g. probiotic_detail only on products
# that contain a recognized probiotic strain; synergy_detail only on
# products with a matched synergy cluster). Tested separately so a
# simple supplement without probiotic/synergy doesn't fail the
# mandatory-contract scan.
OPTIONAL_TOP_LEVEL_KEYS = {
    "probiotic_detail",
    "synergy_detail",
    "interaction_summary",  # absent when no interaction rules match
    "omega3_audit",
    "non_gmo_audit",
    "supplement_type_audit",
    "proprietary_blend_audit",
    "audit",
}


def _find_blob_dir() -> Path | None:
    candidates = [
        Path("/tmp/pharmaguide_release_build/detail_blobs"),
        Path("/tmp/pharmaguide_build/detail_blobs"),
    ]
    for c in candidates:
        if c.is_dir() and any(c.glob("*.json")):
            return c
    return None


@pytest.fixture(scope="module")
def sample_blobs():
    blob_dir = _find_blob_dir()
    if blob_dir is None:
        pytest.skip(
            "No build artifact found under /tmp/pharmaguide_release_build — "
            "run build_final_db.py first to exercise this contract test."
        )
    sample_paths = sorted(blob_dir.glob("*.json"))[:100]
    if not sample_paths:
        pytest.skip("No detail blobs to sample.")
    return [json.loads(p.read_text()) for p in sample_paths]


def test_every_blob_has_required_top_level_keys(sample_blobs) -> None:
    """Only MANDATORY keys are checked — optional keys (probiotic_detail,
    synergy_detail, ...audit) may legitimately be absent on products that
    don't exercise those features.

    The 17 mandatory keys listed in REQUIRED_TOP_LEVEL_KEYS MUST be
    present on every product; if any is missing, Flutter crashes or
    renders a blank section.
    """
    missing_per_blob = {}
    for blob in sample_blobs:
        missing = REQUIRED_TOP_LEVEL_KEYS - set(blob.keys())
        if missing:
            missing_per_blob[blob.get("dsld_id", "?")] = sorted(missing)

    assert not missing_per_blob, (
        f"D5.3 regression: {len(missing_per_blob)} blobs missing MANDATORY "
        f"top-level keys. First 5:\n"
        + "\n".join(
            f"  [{did}] missing: {ks}"
            for did, ks in list(missing_per_blob.items())[:5]
        )
    )


def test_rda_ul_data_always_present(sample_blobs) -> None:
    """Even when collection is config-disabled, the key must exist with a
    collection_reason so downstream consumers (Flutter rda_ul renderer,
    scorer B7) can branch deterministically."""
    for blob in sample_blobs[:20]:
        ru = blob.get("rda_ul_data")
        assert isinstance(ru, dict), (
            f'[{blob.get("dsld_id")}] rda_ul_data must be a dict, got {type(ru).__name__}'
        )
        assert "collection_enabled" in ru or "collection_reason" in ru, (
            f'[{blob.get("dsld_id")}] rda_ul_data must carry collection_enabled '
            f"or collection_reason so consumers can distinguish "
            f"populated-vs-intentionally-empty."
        )


def test_warnings_profile_gated_is_a_list(sample_blobs) -> None:
    """Flutter's _parseWarnings expects both warnings and
    warnings_profile_gated to be lists (possibly empty)."""
    for blob in sample_blobs[:50]:
        wpg = blob.get("warnings_profile_gated")
        assert isinstance(wpg, list), (
            f'[{blob.get("dsld_id")}] warnings_profile_gated must be a list; '
            f"got {type(wpg).__name__}. Flutter's _parseWarnings relies on "
            f"this to concatenate with the main warnings list."
        )
