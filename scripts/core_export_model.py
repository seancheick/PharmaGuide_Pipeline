"""Canonical products_core column model and consumer projections.

The physical SQLite table is intentionally wider than the Flutter read model:
server/reporting columns and one-release compatibility aliases must not leak
into Drift merely because they exist in SQLite.  This module owns the ordered
physical model and derives both projections from that one definition.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


CORE_EXPORT_MODEL_VERSION = "1.1.0"

PRODUCTS_CORE_COLUMNS = (
    "dsld_id",
    "product_name",
    "brand_name",
    "brand_name_raw",
    "brand_family",
    "product_line",
    "upc_sku",
    "image_url",
    "image_is_pdf",
    "thumbnail_key",
    "detail_blob_sha256",
    "interaction_summary_hint",
    "decision_highlights",
    "product_status",
    "discontinued_date",
    "form_factor",
    "supplement_type",
    "score_display_100_equivalent",
    "score_100_equivalent",
    "grade",
    "verdict",
    "safety_verdict",
    "mapped_coverage",
    "quality_score_v4_100",
    "quality_score_status",
    "product_safety_status",
    "quality_assessment_status",
    "quality_tier",
    "quality_score_suppressed_reason",
    "v4_module",
    "quality_score_confidence",
    "score_unavailable_reason",
    "route_confidence",
    "v4_confidence",
    "score_model_version",
    "quality_score_version",
    "scoring_engine_version",
    "classification_schema_version",
    "v4_config_fingerprint",
    "pillar_formulation_v4",
    "pillar_dose_v4",
    "pillar_evidence_v4",
    "pillar_transparency_v4",
    "pillar_verification_v4",
    "pillar_safety_hygiene_v4",
    "score_ingredient_quality",
    "score_ingredient_quality_max",
    "score_safety_purity",
    "score_safety_purity_max",
    "score_evidence_research",
    "score_evidence_research_max",
    "score_brand_trust",
    "score_brand_trust_max",
    "percentile_rank",
    "percentile_top_pct",
    "percentile_category",
    "percentile_label",
    "percentile_cohort",
    "is_gluten_free",
    "is_dairy_free",
    "is_soy_free",
    "is_vegan",
    "is_vegetarian",
    "is_organic",
    "is_non_gmo",
    "has_banned_substance",
    "has_recalled_ingredient",
    "has_harmful_additives",
    "has_allergen_risks",
    "blocking_reason",
    "safety_signal_reason",
    "is_probiotic",
    "contains_sugar",
    "contains_sodium",
    "diabetes_friendly",
    "hypertension_friendly",
    "is_trusted_manufacturer",
    "has_third_party_testing",
    "has_full_disclosure",
    "cert_programs",
    "badges",
    "top_warnings",
    "flags",
    "ingredient_fingerprint",
    "key_nutrients_summary",
    "contains_stimulants",
    "contains_sedatives",
    "contains_blood_thinners",
    "share_title",
    "share_description",
    "share_highlights",
    "share_og_image_url",
    "primary_category",
    "secondary_categories",
    "contains_omega3",
    "contains_probiotics",
    "contains_collagen",
    "contains_adaptogens",
    "contains_nootropics",
    "key_ingredient_tags",
    "ingredients_text",
    "goal_matches",
    "goal_match_confidence",
    "goal_matches_underdosed",
    "dosing_summary",
    "servings_per_container",
    "net_contents_quantity",
    "net_contents_unit",
    "allergen_summary",
    "calories_per_serving",
    "image_thumbnail_url",
    "scoring_version",
    "output_schema_version",
    "enrichment_version",
    "scored_date",
    "export_version",
    "exported_at",
)

# These fields exist for server/reporting work or for the schema-2.4 migration
# boundary.  Every other physical field is part of the app's exact read set.
_SCHEMA3_REMOVED_COLUMNS = frozenset(
    {
        "score_display_100_equivalent",
        "score_100_equivalent",
        "v4_confidence",
        "score_ingredient_quality",
        "score_ingredient_quality_max",
        "score_safety_purity",
        "score_safety_purity_max",
        "score_evidence_research",
        "score_evidence_research_max",
        "score_brand_trust",
        "score_brand_trust_max",
    }
)

_SERVER_ONLY_COLUMNS = frozenset(
    {
        "brand_name_raw",
        "brand_family",
        "product_line",
        "v4_confidence",  # 2.4 compatibility alias; removed in schema 3.
        "quality_score_version",
        "scoring_engine_version",
        "classification_schema_version",
        "v4_config_fingerprint",
        "pillar_formulation_v4",
        "pillar_dose_v4",
        "pillar_evidence_v4",
        "pillar_transparency_v4",
        "pillar_verification_v4",
        "pillar_safety_hygiene_v4",
        "safety_signal_reason",
        "ingredients_text",
        # Kept physically for the schema-2.4 compatibility release, but no
        # longer read by Flutter. Schema 3 removes these columns entirely.
        *_SCHEMA3_REMOVED_COLUMNS,
    }
)

if not _SERVER_ONLY_COLUMNS <= set(PRODUCTS_CORE_COLUMNS):  # pragma: no cover
    raise RuntimeError("server projection names a column outside products_core")

APP_CORE_COLUMNS = tuple(
    name for name in PRODUCTS_CORE_COLUMNS if name not in _SERVER_ONLY_COLUMNS
)
SERVER_CORE_COLUMNS = tuple(
    name for name in PRODUCTS_CORE_COLUMNS if name in _SERVER_ONLY_COLUMNS
)


def _schema_major(export_schema_version: str) -> int:
    try:
        return int(str(export_schema_version).split(".", 1)[0])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"invalid export schema version: {export_schema_version!r}"
        ) from exc


def products_core_columns_for_schema(export_schema_version: str) -> tuple[str, ...]:
    """Physical products_core columns for one export-schema generation."""
    if _schema_major(export_schema_version) < 3:
        return PRODUCTS_CORE_COLUMNS
    return tuple(
        name for name in PRODUCTS_CORE_COLUMNS if name not in _SCHEMA3_REMOVED_COLUMNS
    )


def app_core_columns_for_schema(export_schema_version: str) -> tuple[str, ...]:
    physical = products_core_columns_for_schema(export_schema_version)
    return tuple(name for name in physical if name not in _SERVER_ONLY_COLUMNS)


def server_core_columns_for_schema(export_schema_version: str) -> tuple[str, ...]:
    physical = products_core_columns_for_schema(export_schema_version)
    return tuple(name for name in physical if name in _SERVER_ONLY_COLUMNS)


def build_projection_manifest(*, export_schema_version: str) -> dict[str, Any]:
    """Return a deterministic, content-addressed projection declaration."""
    physical_columns = products_core_columns_for_schema(export_schema_version)
    app_columns = app_core_columns_for_schema(export_schema_version)
    server_columns = server_core_columns_for_schema(export_schema_version)
    model_payload = {
        "model_version": CORE_EXPORT_MODEL_VERSION,
        "physical_columns": list(physical_columns),
        "app_core_columns": list(app_columns),
        "server_core_columns": list(server_columns),
    }
    encoded = json.dumps(
        model_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return {
        "model_version": CORE_EXPORT_MODEL_VERSION,
        "export_schema_version": str(export_schema_version),
        "model_sha256": f"sha256:{hashlib.sha256(encoded).hexdigest()}",
        "physical": {
            "column_count": len(physical_columns),
            "columns": list(physical_columns),
        },
        "app_core": {
            "column_count": len(app_columns),
            "columns": list(app_columns),
        },
        "server_core": {
            "column_count": len(server_columns),
            "columns": list(server_columns),
        },
    }
