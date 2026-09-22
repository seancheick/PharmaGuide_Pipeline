"""
Sprint D5.3 regression — detail blob top-level key contract.

Every product's detail blob MUST carry the keys the Flutter app consumes.
If the pipeline stops emitting any of these keys, the Flutter UI breaks
silently (empty sections, missing safety cards, profile-gated warnings
disappearing).

The contract is sampled from the current ``scripts/final_db_output``
build. When running locally without a build, the test is skipped with a
clear marker so CI on a clean environment doesn't fail spuriously.

Required keys audited here (mapped to consumer features):

| Key | Flutter consumer |
|---|---|
| ``ingredients`` | Active-ingredient section + ingredient-detail sheet |
| ``inactive_ingredients`` | Excipient density card |
| ``warnings`` | InteractionWarningsList (always shown) |
| ``warnings_profile_gated`` | InteractionWarningsList (profile-filtered) |
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
from pathlib import Path

import pytest

from release_artifact_paths import catalog_dist_dir, final_build_dir


# The one declaration of the top-level contract lives in the strict snapshot
# gate (audit_contract_sync.BLOB_TOP_LEVEL). This test used to carry its own
# third copy, which had drifted (interaction_summary optional here, required
# there; section_breakdown required long after it only carried zeros).
from audit_contract_sync import BLOB_TOP_LEVEL

REQUIRED_TOP_LEVEL_KEYS = {k for k, spec in BLOB_TOP_LEVEL.items() if spec.get("required")}
NULLABLE_TOP_LEVEL_KEYS = {k for k, spec in BLOB_TOP_LEVEL.items() if spec.get("presence") == "nullable"}
OPTIONAL_TOP_LEVEL_KEYS = {k for k, spec in BLOB_TOP_LEVEL.items() if spec.get("presence") == "conditional"}


def test_every_declared_key_has_one_presence_class() -> None:
    assert REQUIRED_TOP_LEVEL_KEYS | NULLABLE_TOP_LEVEL_KEYS | OPTIONAL_TOP_LEVEL_KEYS == set(BLOB_TOP_LEVEL)
    assert not (REQUIRED_TOP_LEVEL_KEYS & NULLABLE_TOP_LEVEL_KEYS)
    assert not (REQUIRED_TOP_LEVEL_KEYS & OPTIONAL_TOP_LEVEL_KEYS)
    for retired in ("section_breakdown", "omega3_detail", "quality_score_cap_v4"):
        assert retired not in BLOB_TOP_LEVEL


def test_an_undeclared_top_level_key_fails_the_gate(tmp_path) -> None:
    import subprocess
    import sys

    blobs = tmp_path / "detail_blobs"
    blobs.mkdir()
    blob = {key: [] for key in REQUIRED_TOP_LEVEL_KEYS}
    blob["some_new_unreviewed_block"] = {}
    (blobs / "1.json").write_text(json.dumps(blob))
    script = Path(__file__).resolve().parents[1] / "audit_contract_sync.py"
    result = subprocess.run(
        [sys.executable, str(script), "--build-dir", str(tmp_path), "--out", str(tmp_path / "r.json")],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "some_new_unreviewed_block" in result.stdout


def _find_blob_dir() -> Path | None:
    candidates = [final_build_dir() / "detail_blobs", catalog_dist_dir() / "detail_blobs"]
    for c in candidates:
        if c.is_dir() and any(c.glob("*.json")):
            return c
    return None


@pytest.fixture(scope="module")
def sample_blobs():
    blob_dir = _find_blob_dir()
    if blob_dir is None:
        pytest.skip(
            "No build artifact found under scripts/final_db_output or scripts/dist — "
            "run build_final_db.py first to exercise this contract test."
        )
    all_paths = sorted(blob_dir.glob("*.json"))
    # evenly spaced across the catalog, not the first files by name
    sample_paths = all_paths[:: max(1, len(all_paths) // 1000)]
    if not sample_paths:
        pytest.skip("No detail blobs to sample.")
    return [json.loads(p.read_text()) for p in sample_paths]


def test_every_blob_key_is_declared(sample_blobs) -> None:
    undeclared = {key for blob in sample_blobs for key in blob} - set(BLOB_TOP_LEVEL)
    assert not undeclared, f"undeclared detail-blob keys: {sorted(undeclared)}"


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
