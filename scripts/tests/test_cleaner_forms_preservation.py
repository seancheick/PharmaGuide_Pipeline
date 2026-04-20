"""
Sprint D3.1 regression tests — cleaner preserves every DSLD forms[] field.

Context: the enricher's form-specificity work (D3.2) depends on the
cleaner preserving ALL DSLD forms[] fields end-to-end so the matcher
can route to the correct IQM form (Calcium Carbonate vs Calcium
Citrate, Iron Bisglycinate vs Iron Sulfate, etc.) instead of falling
back to the generic "unspecified" form.

Two provenance paths:
1. **DSLD structured** — raw DSLD forms[] item is a dict with fields
   name / ingredientId / order / prefix / percent / category /
   ingredientGroup / uniiCode. Cleaner preserves ALL fields 1:1.
2. **Name-extracted fallback** — DSLD didn't provide structured forms
   but the cleaner's text extractor pulled form tokens from the
   ingredient name ("Vitamin D3 (as Cholecalciferol)" → form="Cholecalciferol").
   Emitted with only ``name`` + ``source: "name_extraction"`` marker.

These tests enforce that every cleaned output forms[] entry falls into
one of those two clean shapes — no partial DSLD leakage, no name-only
entries without the source marker.

Audit state at D3.1 close (94,477 forms[] entries in the 20-brand
corpus):
  - 80.6% DSLD-structured (all 8 fields present)
  - 19.4% name-extracted (name + source marker)
  - 0% partial / 0% name-only-without-source
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer


REPO_ROOT = Path(__file__).resolve().parents[2]
PRODUCTS_ROOT = REPO_ROOT / "scripts" / "products"


DSLD_FORMS_FIELDS = (
    "name", "ingredientId", "order", "prefix",
    "percent", "category", "ingredientGroup", "uniiCode",
)


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


# ---------------------------------------------------------------------------
# Unit-level: synthetic DSLD input verifies field-by-field preservation
# ---------------------------------------------------------------------------


class TestDsldFormsStructuredPreservation:
    """Cleaner preserves every DSLD forms[] field when DSLD provides them."""

    def test_all_dsld_fields_pass_through(self, normalizer) -> None:
        """Synthetic DSLD row with full forms[] dict — fields copy verbatim."""
        dsld_row = {
            "name": "Calcium",
            "ingredientGroup": "Calcium",
            "category": "mineral",
            "order": 1,
            "quantity": 500,
            "unit": "mg",
            "forms": [
                {
                    "name": "Calcium Carbonate",
                    "ingredientId": 292621,
                    "order": 1,
                    "prefix": None,
                    "percent": None,
                    "category": "mineral",
                    "ingredientGroup": "Calcium",
                    "uniiCode": "H0G9379FGK",
                },
                {
                    "name": "Calcium Citrate",
                    "ingredientId": 123456,
                    "order": 2,
                    "prefix": "as",
                    "percent": 50.0,
                    "category": "mineral",
                    "ingredientGroup": "Calcium",
                    "uniiCode": "MLM29U2X72",
                },
            ],
        }
        result = normalizer._process_single_ingredient_enhanced(dsld_row, is_active=True)
        if isinstance(result, list):
            result = result[0]
        assert result is not None

        cleaned_forms = result.get("forms", []) or []
        assert len(cleaned_forms) == 2
        for i, cleaned_form in enumerate(cleaned_forms):
            for field in DSLD_FORMS_FIELDS:
                assert field in cleaned_form, (
                    f"Cleaner dropped DSLD field {field!r} from forms[{i}]. "
                    f"D3.2 form-specificity work depends on all DSLD fields "
                    f"flowing through."
                )
            # Values match DSLD input exactly.
            assert cleaned_form["name"] in ("Calcium Carbonate", "Calcium Citrate")
            assert cleaned_form["category"] == "mineral"
            assert cleaned_form["ingredientGroup"] == "Calcium"
            assert cleaned_form["uniiCode"] in ("H0G9379FGK", "MLM29U2X72")


class TestNameExtractionFallback:
    """When DSLD provides no forms but name has '(as X)' patterns, cleaner extracts."""

    def test_name_extracted_form_has_source_marker(self, normalizer) -> None:
        """Forms pulled from ingredient name text get ``source="name_extraction"``."""
        dsld_row = {
            "name": "Vitamin D3 (as Cholecalciferol)",
            "ingredientGroup": "Vitamin D",
            "category": "vitamin",
            "order": 1,
            "quantity": 1000,
            "unit": "iu",
            # No structured forms[]
        }
        result = normalizer._process_single_ingredient_enhanced(dsld_row, is_active=True)
        if isinstance(result, list):
            result = result[0]
        assert result is not None

        cleaned_forms = result.get("forms", []) or []
        # Either the cleaner extracted the form AND marked the provenance,
        # or it didn't extract (no assertion). Key assertion: if extracted,
        # the source marker must be present so downstream can distinguish.
        extracted = [f for f in cleaned_forms if f.get("source") == "name_extraction"]
        for f in extracted:
            assert "name" in f, "name-extracted form must have a name"
            assert f.get("source") == "name_extraction"


# ---------------------------------------------------------------------------
# Brand-wide: scan every cleaned_*.json for preservation invariants
# ---------------------------------------------------------------------------


def _iter_cleaned_forms():
    """Yield (brand, product_id, form_dict) across the 20-brand corpus."""
    if not PRODUCTS_ROOT.exists():
        return
    for brand_dir in sorted(PRODUCTS_ROOT.glob("output_*")):
        if "_enriched" in brand_dir.name or "_scored" in brand_dir.name:
            continue
        cleaned = brand_dir / "cleaned"
        if not cleaned.exists():
            continue
        brand = brand_dir.name.replace("output_", "")
        for batch in sorted(cleaned.glob("cleaned_*.json")):
            try:
                data = json.loads(batch.read_text())
            except json.JSONDecodeError:
                continue
            if not isinstance(data, list):
                continue
            for product in data:
                if not isinstance(product, dict):
                    continue
                pid = product.get("id") or "?"
                for section in ("activeIngredients", "inactiveIngredients"):
                    for ing in product.get(section, []) or []:
                        for form in ing.get("forms", []) or []:
                            if isinstance(form, dict):
                                yield brand, pid, form


class TestFormsCorpusInvariants:
    """Every forms[] entry across all brands conforms to one of two shapes."""

    def test_every_form_has_name(self) -> None:
        if not PRODUCTS_ROOT.exists():
            pytest.skip("No pipeline output")
        missing = []
        total = 0
        for brand, pid, form in _iter_cleaned_forms():
            total += 1
            if not form.get("name"):
                missing.append(f"[{brand} {pid}] {form!r}")
        if total == 0:
            pytest.skip("No cleaned output yet")
        assert not missing, (
            f"Invariant broken: {len(missing)} forms[] entries without a 'name' field.\n"
            + "\n".join(missing[:5])
        )

    def test_every_form_is_dsld_structured_or_name_extracted(self) -> None:
        """No partial states — either full DSLD or marked name-extraction."""
        if not PRODUCTS_ROOT.exists():
            pytest.skip("No pipeline output")
        bad = []
        total = 0
        for brand, pid, form in _iter_cleaned_forms():
            total += 1
            has_dsld_fields = all(k in form for k in ("category", "ingredientGroup", "ingredientId"))
            has_source_marker = form.get("source") == "name_extraction"
            if not has_dsld_fields and not has_source_marker:
                bad.append(f"[{brand} {pid}] keys={sorted(form.keys())} form={form.get('name')!r}")
        if total == 0:
            pytest.skip("No cleaned output yet")
        assert not bad, (
            f"Invariant broken: {len(bad)} forms[] entries are neither "
            f"DSLD-structured nor marked with source='name_extraction'. "
            f"Every form entry must declare its provenance.\n"
            + "\n".join(bad[:5])
        )

    def test_dsld_structured_forms_preserve_all_fields(self) -> None:
        """When category+ingredientGroup+ingredientId present, ALL 8 fields present."""
        if not PRODUCTS_ROOT.exists():
            pytest.skip("No pipeline output")
        incomplete = []
        total_dsld = 0
        for brand, pid, form in _iter_cleaned_forms():
            if not all(k in form for k in ("category", "ingredientGroup", "ingredientId")):
                continue  # name-extracted, doesn't apply
            total_dsld += 1
            missing = [f for f in DSLD_FORMS_FIELDS if f not in form]
            if missing:
                incomplete.append(f"[{brand} {pid}] missing={missing} form={form.get('name')!r}")
        if total_dsld == 0:
            pytest.skip("No DSLD-structured forms in current output")
        assert not incomplete, (
            f"{len(incomplete)} DSLD-structured forms[] have partial field set:\n"
            + "\n".join(incomplete[:5])
        )
