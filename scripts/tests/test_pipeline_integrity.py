"""
Pipeline Integrity Tests

Automated test suite that validates the structural integrity of:
  1. All reference databases in scripts/data/ (schema, metadata, IDs)
  2. Enriched pipeline output (required enrichment fields)
  3. Scored pipeline output (required scoring fields)
  4. Ingredient mapping data (IQM forms, clinical strains)

These tests are designed to catch schema drift, broken cross-references,
and silent data corruption before they propagate downstream.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports (normalized to avoid ".." in __file__)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from constants import DATA_DIR, SCRIPTS_DIR

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

REQUIRED_SCHEMA_VERSION = "4.0.0"

# Required fields inside every _metadata block
REQUIRED_METADATA_FIELDS = ("description", "purpose", "schema_version")

# Enriched output: core enrichment data sections that must be present
ENRICHED_REQUIRED_KEYS = (
    "ingredient_quality_data",
    "delivery_data",
    "compliance_data",
    "certification_data",
    "match_ledger",
)

# Scored output: top-level keys every scored product must carry
SCORED_REQUIRED_KEYS = ("quality_score", "verdict", "scoring_metadata")

# Locate pipeline output directories (may or may not exist)
_ENRICHED_DIRS = sorted(SCRIPTS_DIR.glob("output_*_enriched/enriched"))
_SCORED_DIRS = sorted(SCRIPTS_DIR.glob("output_*_scored/scored"))

ENRICHED_DIR_EXISTS = len(_ENRICHED_DIRS) > 0
SCORED_DIR_EXISTS = len(_SCORED_DIRS) > 0


def _load_json(path: Path):
    """Return parsed JSON data, or None on failure."""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def _find_primary_array(data: dict) -> list | None:
    """Heuristic: return the first top-level list value that is not _metadata."""
    for key, val in data.items():
        if key == "_metadata":
            continue
        if isinstance(val, list):
            return val
    return None


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


def _all_database_files() -> list[Path]:
    """Return all .json files in DATA_DIR, sorted by name."""
    return sorted(DATA_DIR.glob("*.json"))


# ===================================================================
# Test Class 1: Database Schema Integrity
# ===================================================================

class TestDatabaseSchemaIntegrity:
    """Validate the structural integrity of every .json file in scripts/data/."""

    @pytest.fixture(scope="class")
    def db_files(self) -> list[Path]:
        """Collect all .json database files from DATA_DIR."""
        files = _all_database_files()
        assert files, f"No .json files found in {DATA_DIR}"
        return files

    # ------------------------------------------------------------------
    # 1a. Every database file must carry a _metadata block
    # ------------------------------------------------------------------
    def test_all_databases_have_metadata(self, db_files):
        """Every .json in data/ must have a '_metadata' object with the required fields."""
        missing = []
        for fp in db_files:
            data = _load_json(fp)
            if data is None:
                missing.append(f"{fp.name}: could not parse JSON")
                continue
            if not isinstance(data, dict):
                missing.append(f"{fp.name}: top-level value is not an object")
                continue
            meta = data.get("_metadata")
            if meta is None:
                missing.append(f"{fp.name}: missing '_metadata' key")
                continue
            for field in REQUIRED_METADATA_FIELDS:
                if field not in meta:
                    missing.append(f"{fp.name}: _metadata missing '{field}'")

        assert not missing, (
            f"{len(missing)} metadata issue(s) found:\n  " + "\n  ".join(missing)
        )

    # ------------------------------------------------------------------
    # 1b. schema_version must be uniform across all databases
    # ------------------------------------------------------------------
    def test_schema_version_uniform(self, db_files):
        """All database files must declare schema_version == '{REQUIRED_SCHEMA_VERSION}'."""
        mismatches = []
        for fp in db_files:
            data = _load_json(fp)
            if data is None or not isinstance(data, dict):
                continue
            meta = data.get("_metadata", {})
            sv = meta.get("schema_version")
            if sv is None:
                mismatches.append(f"{fp.name}: schema_version not declared")
            elif sv != REQUIRED_SCHEMA_VERSION:
                mismatches.append(
                    f"{fp.name}: schema_version='{sv}'"
                    f" (expected '{REQUIRED_SCHEMA_VERSION}')"
                )

        assert not mismatches, (
            f"{len(mismatches)} schema_version mismatch(es):\n  " + "\n  ".join(mismatches)
        )

    # ------------------------------------------------------------------
    # 1c. No duplicate IDs inside any single database file
    # ------------------------------------------------------------------
    def test_no_duplicate_ids(self, db_files):
        """No file should contain duplicate 'id' values in its primary array."""
        duplicates = []
        for fp in db_files:
            data = _load_json(fp)
            if data is None or not isinstance(data, dict):
                continue
            primary = _find_primary_array(data)
            if primary is None:
                continue

            ids = [
                item["id"]
                for item in primary
                if isinstance(item, dict) and "id" in item
            ]
            seen: set[str] = set()
            file_dupes: list[str] = []
            for id_val in ids:
                if id_val in seen:
                    file_dupes.append(id_val)
                seen.add(id_val)

            if file_dupes:
                duplicates.append(f"{fp.name}: duplicate IDs -> {file_dupes}")

        assert not duplicates, (
            "Duplicate IDs found:\n  " + "\n  ".join(duplicates)
        )

    # ------------------------------------------------------------------
    # 1d. total_entries must match actual array length (when declared)
    # ------------------------------------------------------------------
    def test_total_entries_accurate(self, db_files):
        """If _metadata.total_entries is declared, it must match the actual count."""
        mismatches = []
        for fp in db_files:
            data = _load_json(fp)
            if data is None or not isinstance(data, dict):
                continue
            meta = data.get("_metadata", {})
            total_declared = meta.get("total_entries")
            if total_declared is None or not isinstance(total_declared, int):
                continue

            primary = _find_primary_array(data)
            if primary is None:
                continue

            actual = len(primary)
            if actual != total_declared:
                mismatches.append(
                    f"{fp.name}: declared {total_declared}, actual {actual}"
                )

        assert not mismatches, (
            "total_entries mismatch(es):\n  " + "\n  ".join(mismatches)
        )

    # ------------------------------------------------------------------
    # 1e. id_redirects cross-references: supersedes <-> redirects <-> banned
    # ------------------------------------------------------------------
    def test_id_redirects_cross_references(self):
        """All supersedes_ids must have redirects; redirect canonical_ids must exist in banned DB."""
        banned_path = DATA_DIR / "banned_recalled_ingredients.json"
        redirects_path = DATA_DIR / "id_redirects.json"

        if not banned_path.exists():
            pytest.skip("banned_recalled_ingredients.json not found")
        if not redirects_path.exists():
            pytest.skip("id_redirects.json not found")

        banned_data = _load_json(banned_path)
        redirects_data = _load_json(redirects_path)

        assert banned_data is not None, "Could not parse banned_recalled_ingredients.json"
        assert redirects_data is not None, "Could not parse id_redirects.json"

        # Build set of canonical IDs in banned DB
        banned_ingredients = banned_data.get("ingredients", [])
        banned_ids: set[str] = {
            item["id"]
            for item in banned_ingredients
            if isinstance(item, dict) and "id" in item
        }

        # Collect all supersedes_ids declared in banned DB
        all_supersedes: set[str] = set()
        for item in banned_ingredients:
            if not isinstance(item, dict):
                continue
            sids = item.get("supersedes_ids")
            if isinstance(sids, list):
                all_supersedes.update(s for s in sids if isinstance(s, str))

        # Build redirects lookup
        redirects_list = redirects_data.get("redirects", [])
        redirect_deprecated: set[str] = set()
        redirect_canonical: set[str] = set()
        for r in redirects_list:
            if not isinstance(r, dict):
                continue
            dep = r.get("deprecated_id")
            can = r.get("canonical_id")
            if dep:
                redirect_deprecated.add(dep)
            if can:
                redirect_canonical.add(can)

        errors = []

        # Every supersedes_id should appear as a deprecated_id in id_redirects
        missing_redirects = all_supersedes - redirect_deprecated
        for mid in sorted(missing_redirects):
            errors.append(
                f"supersedes_id '{mid}' has no redirect entry in id_redirects.json"
            )

        # Every redirect canonical_id should exist in banned DB
        orphaned = redirect_canonical - banned_ids
        for oid in sorted(orphaned):
            errors.append(
                f"id_redirects canonical_id '{oid}' not found in banned_recalled_ingredients.json"
            )

        assert not errors, (
            f"{len(errors)} cross-reference error(s):\n  " + "\n  ".join(errors)
        )


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
        """Every scored product must have quality_score, verdict, and scoring_metadata."""
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


# ===================================================================
# Test Class 3: Ingredient Mapping Integrity
# ===================================================================

class TestIngredientMappingIntegrity:
    """Validate the ingredient_quality_map.json (IQM) and related mapping databases."""

    @pytest.fixture(scope="class")
    def iqm_data(self) -> dict:
        """Load and return the full ingredient_quality_map.json."""
        iqm_path = DATA_DIR / "ingredient_quality_map.json"
        assert iqm_path.exists(), f"IQM file not found: {iqm_path}"
        data = _load_json(iqm_path)
        assert data is not None, "Could not parse ingredient_quality_map.json"
        return data

    @pytest.fixture(scope="class")
    def iqm_entries(self, iqm_data) -> dict:
        """Return only the ingredient entries (exclude _metadata)."""
        return {k: v for k, v in iqm_data.items() if k != "_metadata"}

    # ------------------------------------------------------------------
    # 3a. Every form must have score, bio_score, aliases
    # ------------------------------------------------------------------
    def test_iqm_forms_have_required_fields(self, iqm_entries):
        """Every form in every IQM ingredient must have 'score', 'bio_score', and 'aliases'."""
        required_form_fields = ("score", "bio_score", "aliases")
        failures = []

        for ingredient_key, ingredient in iqm_entries.items():
            if not isinstance(ingredient, dict):
                continue
            forms = ingredient.get("forms")
            if not isinstance(forms, dict):
                failures.append(f"{ingredient_key}: 'forms' key missing or not a dict")
                continue

            for form_name, form_data in forms.items():
                if not isinstance(form_data, dict):
                    failures.append(f"{ingredient_key}/{form_name}: form value is not a dict")
                    continue
                missing = [
                    f for f in required_form_fields if f not in form_data
                ]
                if missing:
                    failures.append(f"{ingredient_key}/{form_name}: missing {missing}")

        assert not failures, (
            f"{len(failures)} IQM form issue(s):\n  " + "\n  ".join(failures[:30])
        )

    # ------------------------------------------------------------------
    # 3b. All aliases must be strings
    # ------------------------------------------------------------------
    def test_iqm_aliases_are_strings(self, iqm_entries):
        """Every alias in every IQM form must be a string (not None, int, etc.)."""
        failures = []

        for ingredient_key, ingredient in iqm_entries.items():
            if not isinstance(ingredient, dict):
                continue
            forms = ingredient.get("forms", {})
            if not isinstance(forms, dict):
                continue

            for form_name, form_data in forms.items():
                if not isinstance(form_data, dict):
                    continue
                aliases = form_data.get("aliases", [])
                if not isinstance(aliases, list):
                    alias_type = type(aliases).__name__
                    failures.append(
                        f"{ingredient_key}/{form_name}:"
                        f" 'aliases' is {alias_type}, not list"
                    )
                    continue
                for idx, alias in enumerate(aliases):
                    if not isinstance(alias, str):
                        a_type = type(alias).__name__
                        failures.append(
                            f"{ingredient_key}/{form_name}:"
                            f" alias[{idx}] is {a_type}"
                            f" ({alias!r})"
                        )

        assert not failures, (
            f"{len(failures)} non-string alias(es):\n  " + "\n  ".join(failures[:30])
        )

    # ------------------------------------------------------------------
    # 3c. Clinical strains must all have non-empty id
    # ------------------------------------------------------------------
    def test_clinical_strains_have_ids(self):
        """All entries in clinically_relevant_strains.json must have a non-empty 'id'."""
        strains_path = DATA_DIR / "clinically_relevant_strains.json"
        if not strains_path.exists():
            pytest.skip("clinically_relevant_strains.json not found")

        data = _load_json(strains_path)
        assert data is not None, "Could not parse clinically_relevant_strains.json"

        # The primary array key is 'clinically_relevant_strains'
        strains = data.get("clinically_relevant_strains")
        if strains is None:
            # Fall back to heuristic
            strains = _find_primary_array(data)
        assert strains is not None, "No primary array found in clinically_relevant_strains.json"

        failures = []
        for idx, entry in enumerate(strains):
            if not isinstance(entry, dict):
                failures.append(f"index {idx}: entry is not a dict")
                continue
            entry_id = entry.get("id")
            if not entry_id or not isinstance(entry_id, str) or not entry_id.strip():
                name = entry.get("standard_name", f"index-{idx}")
                failures.append(f"'{name}': id is missing or empty")

        assert not failures, (
            f"{len(failures)} strain(s) with missing/empty id:\n  " + "\n  ".join(failures)
        )

    # ------------------------------------------------------------------
    # 3d. No database entry should have an empty standard_name
    # ------------------------------------------------------------------
    def test_no_empty_standard_names(self):
        """No entry in any database file should have an empty or whitespace-only 'standard_name'."""
        failures = []

        for fp in _all_database_files():
            data = _load_json(fp)
            if data is None or not isinstance(data, dict):
                continue
            primary = _find_primary_array(data)
            if primary is None:
                continue

            for idx, item in enumerate(primary):
                if not isinstance(item, dict):
                    continue
                # Only check entries that actually declare a standard_name field
                if "standard_name" not in item:
                    continue
                sn = item["standard_name"]
                if not sn or not isinstance(sn, str) or not sn.strip():
                    entry_id = item.get("id", f"index-{idx}")
                    failures.append(f"{fp.name}/{entry_id}: standard_name is empty or blank")

        assert not failures, (
            f"{len(failures)} empty standard_name(s):\n  " + "\n  ".join(failures[:30])
        )
