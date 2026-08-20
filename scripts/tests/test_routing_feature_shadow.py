"""Manifest-owned routing feature measurement contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _row(canonical_id: str, quantity: float, unit: str, **extra) -> dict:
    return {
        "name": canonical_id.replace("_", " ").title(),
        "canonical_id": canonical_id,
        "quantity": quantity,
        "unit": unit,
        "mapped": True,
        "scoreable_identity": True,
        "score_eligible_by_cleaner": True,
        "raw_source_path": extra.pop("raw_source_path", canonical_id),
        **extra,
    }


def test_route_feature_vector_measures_label_intent_and_panel_shape() -> None:
    from scoring_v4.route_features import extract_route_features

    rows = [
        _row("psyllium_husk", 5, "g"),
        _row("vitamin_b1_thiamine", 10, "mg"),
        _row("vitamin_b6_pyridoxine", 5, "mg"),
        _row("vitamin_b12_cobalamin", 100, "mcg"),
        _row("vitamin_d", 25, "mcg"),
        _row("zinc", 10, "mg"),
    ]
    product = {
        "dsld_id": "F1",
        "fullName": "Daily Psyllium Fiber",
        "brand_name": "Example",
        "supplement_taxonomy": {"primary_type": "fiber_digestive"},
    }
    classification = {
        "route_module": "fiber_digestive",
        "route_reason": "profile_content:fiber_digestive",
        "route_confidence": "high",
        "ingredients": [
            {
                "row_ref": "psyllium_husk",
                "canonical_id": "psyllium_husk",
                "role": "primary",
            }
        ],
    }

    feature = extract_route_features(product, rows, classification)

    assert feature["title_fiber_intent"] is True
    assert feature["taxonomy_fiber_digestive"] is True
    assert feature["fiber_canonical_ids"] == ["psyllium_husk"]
    assert feature["fiber_primary_role"] is True
    assert feature["fiber_mass_mg"] == 5000.0
    assert 0.99 < feature["fiber_mass_share"] < 1.0
    assert feature["b_vitamin_count"] == 3
    assert feature["non_b_vitamin_count"] == 1
    assert feature["ade_k_vitamin_count"] == 1
    assert feature["mineral_count"] == 1


def test_route_feature_vector_separates_systemic_enzyme_from_digestive_context() -> None:
    from scoring_v4.route_features import extract_route_features

    systemic = extract_route_features(
        {"dsld_id": "E1", "fullName": "Nattokinase Enzyme"},
        [_row("nattokinase", 100, "mg")],
        {"route_module": "fiber_digestive", "ingredients": []},
    )
    digestive = extract_route_features(
        {"dsld_id": "E2", "fullName": "Digestive Enzyme Formula"},
        [_row("protease", 20_000, "HUT")],
        {"route_module": "fiber_digestive", "ingredients": []},
    )

    assert systemic["enzyme_canonical_ids"] == ["nattokinase"]
    assert systemic["title_digestive_intent"] is False
    assert systemic["systemic_enzyme_only"] is True
    assert digestive["title_digestive_intent"] is True
    assert digestive["digestive_enzyme_row_count"] == 1


def test_route_feature_vector_separates_observed_nutrition_fiber_from_context() -> None:
    from scoring_v4.route_features import extract_route_features

    observed = [
        _row(
            "fiber",
            3,
            "g",
            score_exclusion_reason="excluded_nutrition_fact",
        ),
        _row(
            "digestive_enzymes",
            0,
            "NP",
            score_exclusion_reason="nested_display_only",
        ),
    ]
    feature = extract_route_features(
        {"dsld_id": "O1", "fullName": "Break It Down"},
        [],
        {"route_module": "fiber_digestive", "ingredients": []},
        observed_rows=observed,
    )

    assert feature["fiber_row_count"] == 0
    assert feature["observed_fiber_row_count"] == 1
    assert feature["observed_nutrition_fiber_row_count"] == 1
    assert feature["observed_digestive_enzyme_row_count"] == 1
    assert feature["digestive_enzyme_context"] is True


def test_canonical_protein_intent_predicate_supports_requested_label_shapes() -> None:
    from scoring_v4.route_features import has_protein_product_intent

    for title in (
        "Whey Protein Isolate",
        "Protein Isolate - Whey",
        "Bare Protein",
        "Plant Protein",
        "Hydrolyzed Rice Protein",
        "Mass Gainer",
    ):
        assert has_protein_product_intent(title), title
    assert not has_protein_product_intent("Keratin Hair Support")


def test_shadow_report_reads_only_manifest_owned_enriched_rows(tmp_path: Path) -> None:
    from audits.routing_feature_shadow import build_shadow_report
    from stage_manifest import write_stage_manifest

    stage = tmp_path / "output_Example_enriched" / "enriched"
    stage.mkdir(parents=True)
    owned = stage / "enriched_cleaned_batch_1.json"
    stale_stage = tmp_path / "output_Stale_enriched" / "enriched"
    stale_stage.mkdir(parents=True)
    stray = stale_stage / "stale_batch.json"
    product = {
        "dsld_id": "P1",
        "fullName": "Vitamin C",
        "brand_name": "Example",
        "supplement_taxonomy": {"primary_type": "single_vitamin"},
        "ingredient_quality_data": {
            "ingredients_scorable": [_row("vitamin_c", 500, "mg")],
        },
    }
    owned.write_text(json.dumps([product]), encoding="utf-8")
    stray.write_text(json.dumps([{**product, "dsld_id": "STALE"}]), encoding="utf-8")
    write_stage_manifest(stage, "enrich", [owned], run_id="routing-shadow-test")

    report = build_shadow_report(tmp_path, generated_at="2026-08-20T00:00:00Z")

    assert report["mode"] == "measure_only"
    assert report["enforcement_enabled"] is False
    assert report["catalog_eligibility_changed"] is False
    assert report["product_count"] == 1
    assert report["manifest_owned_file_count"] == 1
    assert [row["dsld_id"] for row in report["features"]] == ["P1"]
    assert report["route_distribution"] == {"generic": 1}
    assert report["stamped_vs_recomputed_mismatch_count"] == 0
    assert len(report["report_sha256"]) == 64
