"""Pipeline data-flow invariants over the real generated corpus.

Split out of test_pipeline_integrity.py: these tests load every enriched and
scored product under scripts/products, so they are generated-artifact tests
(ARTIFACT_TEST_FILES), not dev-loop unit tests. While they lived in the fast
file their output-dir glob matched nothing and they skipped silently; with the
path fixed, loading the whole corpus overran the fast tier's 120s limit.
"""

from __future__ import annotations

import pytest

from constants import DATA_DIR, SCRIPTS_DIR
from tests.test_pipeline_integrity import _load_json

# Enriched output: core enrichment data sections that must be present
ENRICHED_REQUIRED_KEYS = (
    "ingredient_quality_data",
    "delivery_data",
    "compliance_data",
    "certification_data",
    "match_ledger",
)

# Scored output: top-level keys every scored product must carry
SCORED_REQUIRED_KEYS = (
    "quality_score_status",
    "quality_score_v4_100",
    "quality_pillars_v4",
    "verdict",
    "scoring_metadata",
)

# Locate pipeline output directories (may or may not exist). Outputs live under
# scripts/products/; the old scripts/output_* glob matched nothing, so these
# data-flow tests skipped on every run.
_ENRICHED_DIRS = sorted((SCRIPTS_DIR / "products").glob("output_*_enriched/enriched"))
_SCORED_DIRS = sorted((SCRIPTS_DIR / "products").glob("output_*_scored/scored"))

ENRICHED_DIR_EXISTS = len(_ENRICHED_DIRS) > 0
SCORED_DIR_EXISTS = len(_SCORED_DIRS) > 0


def _collect_all_enriched_products() -> list[dict]:
    """Load every product from every enriched output directory."""
    products = []
    for enriched_dir in _ENRICHED_DIRS:
        for fp in sorted(enriched_dir.glob("*.json")):
            data = _load_json(fp)
            if isinstance(data, list):
                products.extend(data)
    return products


def _collect_all_scored_products() -> list[dict]:
    """Load every product from every scored output directory."""
    products = []
    for scored_dir in _SCORED_DIRS:
        for fp in sorted(scored_dir.glob("*.json")):
            data = _load_json(fp)
            if isinstance(data, list):
                products.extend(data)
    return products


def _clinical_entry_map() -> dict[str, dict]:
    """Return backed_clinical_studies entries keyed by id."""
    data = _load_json(DATA_DIR / "backed_clinical_studies.json") or {}
    entries = data.get("backed_clinical_studies", [])
    return {
        entry["id"]: entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("id")
    }



# ===================================================================
# Test Class 2: Pipeline Data Flow
# ===================================================================

class TestPipelineDataFlow:
    """Validate structural invariants of enriched and scored pipeline output."""

    # ------------------------------------------------------------------
    # 2a. Enriched output: required data sections
    # ------------------------------------------------------------------
    @pytest.mark.skipif(
        not ENRICHED_DIR_EXISTS,
        reason="No enriched output directories found; skipping enriched output tests",
    )
    def test_enriched_output_has_required_sections(self):
        """Every enriched product must carry the core enrichment data sections and match_ledger."""
        products = _collect_all_enriched_products()
        assert products, "Enriched output directories exist but contain no products"

        failures = []
        for idx, product in enumerate(products):
            pid = product.get("id") or product.get("dsld_id") or f"index-{idx}"
            missing_keys = [
                k for k in ENRICHED_REQUIRED_KEYS if k not in product
            ]
            if missing_keys:
                failures.append(f"Product {pid}: missing {missing_keys}")

        assert not failures, (
            f"{len(failures)} enriched product(s) missing required sections:\n  "
            + "\n  ".join(failures[:20])
        )

    # ------------------------------------------------------------------
    # 2b. Scored output: required fields
    # ------------------------------------------------------------------
    @pytest.mark.skipif(
        not SCORED_DIR_EXISTS,
        reason="No scored output directories found; skipping scored output tests",
    )
    def test_scored_output_has_required_fields(self):
        """Every scored product carries the v4 status, total, pillars, verdict and metadata."""
        products = _collect_all_scored_products()
        assert products, "Scored output directories exist but contain no products"

        failures = []
        for idx, product in enumerate(products):
            pid = product.get("dsld_id") or product.get("id") or f"index-{idx}"
            missing_keys = [
                k for k in SCORED_REQUIRED_KEYS if k not in product
            ]
            if missing_keys:
                failures.append(f"Product {pid}: missing {missing_keys}")

        assert not failures, (
            f"{len(failures)} scored product(s) missing required fields:\n  "
            + "\n  ".join(failures[:20])
        )

    # ------------------------------------------------------------------
    # 2c. Enrichment version consistency
    # ------------------------------------------------------------------
    @pytest.mark.skipif(
        not ENRICHED_DIR_EXISTS,
        reason="No enriched output directories found; skipping enrichment version test",
    )
    def test_enrichment_version_consistency(self):
        """All enriched products should share the same enrichment_version."""
        products = _collect_all_enriched_products()
        assert products, "Enriched output directories exist but contain no products"

        versions: set[str] = set()
        missing_version = 0
        for product in products:
            ev = product.get("enrichment_version")
            if ev is None:
                missing_version += 1
            else:
                versions.add(ev)

        assert missing_version == 0, (
            f"{missing_version} enriched product(s) have no 'enrichment_version' field"
        )
        assert len(versions) == 1, (
            f"Expected 1 enrichment_version across all products,"
            f" found {len(versions)}: {versions}"
        )

    @pytest.mark.skipif(
        not ENRICHED_DIR_EXISTS,
        reason="No enriched output directories found; skipping clinical passthrough test",
    )
    def test_enriched_clinical_matches_carry_current_optional_fields(self):
        """Enriched outputs should not contradict current clinical passthrough values.

        The checked-in enriched snapshots are not regenerated on every clinical
        DB metadata backfill. Runtime passthrough coverage for volatile fields
        such as enrollment, registry counts, auditability text, and endpoint
        tags is enforced by targeted schema/unit tests. This integrity check
        only guards against stale snapshots carrying conflicting values for the
        comparatively stable passthrough fields. Curated evidence-judgment
        fields such as effect_direction are intentionally allowed to drift
        ahead of checked-in enriched snapshots until those snapshots are
        regenerated.
        """
        products = _collect_all_enriched_products()
        assert products, "Enriched output directories exist but contain no products"

        source_by_id = _clinical_entry_map()
        failures = []

        for idx, product in enumerate(products):
            pid = product.get("dsld_id") or product.get("id") or f"index-{idx}"
            matches = ((product.get("evidence_data") or {}).get("clinical_matches") or [])
            for match in matches:
                study_id = match.get("id") or match.get("study_id")
                source = source_by_id.get(study_id)
                if not source:
                    continue
                for field in (
                    "published_studies_count",
                    "published_rct_count",
                    "published_meta_review_count",
                    "primary_outcome",
                ):
                    if source.get(field) is not None and match.get(field) is not None and match.get(field) != source.get(field):
                        failures.append(
                            f"Product {pid} clinical match {study_id}: conflicting {field} "
                            f"(enriched={match.get(field)!r}, source={source.get(field)!r})"
                        )
                        break
            if len(failures) >= 20:
                break

        assert not failures, (
            "Enriched clinical matches conflict with current passthrough fields:\n  "
            + "\n  ".join(failures[:20])
        )
