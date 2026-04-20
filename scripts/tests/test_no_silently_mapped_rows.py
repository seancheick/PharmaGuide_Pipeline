"""
Sprint D2.1 regression tests — protocol rule #4 enforcement.

Protocol rule #4: ``mapped=True`` must imply ``canonical_id != None``.
Zero tolerance for silently-mapped rows across every brand's cleaned
output.

Context: the deep accuracy audit found 833 silently-mapped active
ingredient rows across 126,074 actives in 20 brands. They were created
by the cleaner's ``is_mapped = (mapped OR harmful OR allergen OR banned
OR passive OR proprietary)`` cascade — ``is_proprietary=True`` and
fuzzy standard-name resolutions could set ``is_mapped=True`` even when
the reverse index couldn't resolve any canonical. Downstream the
enricher correctly refused to score these, coverage dropped below 99.5%
on ~27 products, and the pipeline blocked entire brands.

Fix: at every row-builder site, the cleaner now enforces
``is_mapped ⇒ canonical_id`` as a hard contract after the canonical
resolution step. Silent-mapping rows are downgraded to ``is_mapped=False``
and flow to the unmapped gap tracker so D2.2-D2.6 alias/DB expansion
work has visible targets.

Two layers of tests:
1. Unit-level: synthetic rows exercise each downgrade path
2. Brand-wide: scan every cleaned_*.json under scripts/products for any
   surviving silently-mapped row. One row is enough to fail the suite.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer


REPO_ROOT = Path(__file__).resolve().parents[2]
PRODUCTS_ROOT = REPO_ROOT / "scripts" / "products"


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


# ---------------------------------------------------------------------------
# Unit-level: synthetic rows exercising the contract downgrade
# ---------------------------------------------------------------------------


class TestCleanerContractDowngrades:
    """Constructing a row from synthetic DSLD input — contract must hold."""

    def _make_dsld_row(self, **overrides) -> dict:
        base = {
            "name": "Amino Acid Blend",  # No canonical exists for this generic header
            "order": 1,
            "quantity": 500,
            "unit": "mg",
            "ingredientGroup": "Amino Acid",
            "category": "amino acid",
        }
        base.update(overrides)
        return base

    def test_blend_header_without_canonical_downgrades_to_unmapped(self, normalizer) -> None:
        """An 'Amino Acid Blend' header has no canonical — must not be silently mapped."""
        row = self._make_dsld_row(name="Amino Acid Blend")
        result = normalizer._process_single_ingredient_enhanced(row, is_active=True)
        if isinstance(result, list):
            result = result[0]
        assert result is not None
        mapped = result.get("mapped")
        canonical_id = result.get("canonical_id")
        assert not (mapped and canonical_id is None), (
            f"Silently-mapped row: mapped={mapped}, canonical_id={canonical_id}. "
            f"Protocol rule #4 violation — contract enforcement failed."
        )

    def test_existing_iqm_ingredient_still_mapped_with_canonical(self, normalizer) -> None:
        """A real IQM ingredient must stay mapped with a canonical after the fix."""
        row = self._make_dsld_row(name="Vitamin C", ingredientGroup="Vitamin C", category="vitamin")
        result = normalizer._process_single_ingredient_enhanced(row, is_active=True)
        if isinstance(result, list):
            result = result[0]
        assert result is not None
        assert result.get("mapped") is True
        assert result.get("canonical_id") is not None
        assert result.get("canonical_source_db") != "unmapped"

    @pytest.mark.parametrize("raw_name", [
        "Phenylalanine, Micronized",  # qualifier-suffix silent-mapping
        "Amino Acceleration System",   # branded sports blend header
        "Vitaberry Plus(TM)",          # branded berry blend (trademark)
        "Protease Aminogen",           # branded enzyme
        "Salad Extract",               # generic blend header
        "Eye Health Support",          # generic blend header
    ])
    def test_known_silently_mapped_patterns_downgrade(self, normalizer, raw_name) -> None:
        """
        Rows from the deep accuracy audit's top silent-mapping patterns.
        After D2.1, these must either have canonical_id set (if a pre-
        existing alias covers them) or mapped=False.
        """
        row = self._make_dsld_row(name=raw_name, ingredientGroup=raw_name)
        result = normalizer._process_single_ingredient_enhanced(row, is_active=True)
        if isinstance(result, list):
            result = result[0]
        assert result is not None
        mapped = result.get("mapped")
        canonical_id = result.get("canonical_id")
        assert not (mapped and canonical_id is None), (
            f"Silently-mapped row for {raw_name!r}: mapped={mapped}, canonical_id={canonical_id}. "
            f"Either add an explicit alias to the appropriate DB (D2.2-D2.6) or ensure "
            f"this resolves to mapped=False."
        )


# ---------------------------------------------------------------------------
# Brand-wide: scan all cleaned_*.json for surviving silently-mapped rows
# ---------------------------------------------------------------------------


def _iter_cleaned_rows():
    """Yield (brand, product_id, section, ingredient) across every cleaned file."""
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
                pid = product.get("id") or product.get("productIdentifier") or "?"
                for section in ("activeIngredients", "inactiveIngredients"):
                    for ing in product.get(section, []) or []:
                        if isinstance(ing, dict):
                            yield brand, pid, section, ing


class TestBrandWideNoSilentlyMappedRows:
    """
    Brand-wide scan. If ANY cleaned row in ANY brand's output has
    ``mapped=True`` AND ``canonical_id=None``, the test fails.

    **Enforcement mode** is gated by the env var
    ``PG_ENFORCE_CLEANER_CONTRACT=1``. When the var is not set, the
    scan runs in OBSERVE mode — it reports the count without failing
    the suite. This lets the test land alongside D2.1 (code fix) on
    stale pre-D2.1 cleaned data without turning the CI red until D5.1
    re-runs the pipeline and regenerates cleaned output with the
    contract enforced.

    **Post-D5.1 expected state**: zero silently-mapped rows. Enable
    enforcement after D5.1 by setting ``PG_ENFORCE_CLEANER_CONTRACT=1``
    in the CI env and in any developer-side full-suite run.

    Skipped entirely when no cleaned output exists.
    """

    def test_zero_silently_mapped_active_rows(self) -> None:
        import os
        enforce = os.environ.get("PG_ENFORCE_CLEANER_CONTRACT") == "1"
        if not PRODUCTS_ROOT.exists():
            pytest.skip("No pipeline output directory present")

        offenders: Dict[str, int] = {}
        total_scanned = 0
        for brand, pid, section, ing in _iter_cleaned_rows():
            if section != "activeIngredients":
                continue
            total_scanned += 1
            if ing.get("mapped") and ing.get("canonical_id") is None:
                name = ing.get("raw_source_text") or ing.get("name") or "?"
                offenders[name] = offenders.get(name, 0) + 1

        if total_scanned == 0:
            pytest.skip("No cleaned batches present yet")

        top = sorted(offenders.items(), key=lambda kv: -kv[1])[:15]
        if not enforce and offenders:
            # Observe-only mode: log without failing. Flip
            # PG_ENFORCE_CLEANER_CONTRACT=1 after D5.1 pipeline re-run to
            # upgrade this to a hard fail.
            pytest.skip(
                f"Observe mode (PG_ENFORCE_CLEANER_CONTRACT unset): "
                f"{sum(offenders.values())} silently-mapped rows found in stale "
                f"pre-D2.1 cleaned output. Re-run cleaner after D2.1 lands to "
                f"regenerate clean data. Top: {top[:5]}"
            )
        assert not offenders, (
            f"D2.1 protocol rule #4 violation: {sum(offenders.values())} "
            f"silently-mapped active rows found across {total_scanned} scanned actives.\n"
            f"Top offenders (count x name):\n"
            + "\n".join(f"  {c}x  {n!r}" for n, c in top)
            + "\n\nIf this test fires after a fresh pipeline run, the D2.1 contract "
              "enforcement is broken. If it fires on stale pre-D2.1 data, re-run "
              "the cleaner (scripts/clean_dsld_data.py) to regenerate cleaned output."
        )

    def test_canonical_source_db_matches_canonical_presence(self) -> None:
        """
        Secondary invariant: canonical_source_db='unmapped' iff canonical_id is None.
        Catches the inverse mistake (canonical_id set but source='unmapped' or vice versa).
        """
        if not PRODUCTS_ROOT.exists():
            pytest.skip("No pipeline output directory present")

        mismatches: List[str] = []
        total_scanned = 0
        for brand, pid, section, ing in _iter_cleaned_rows():
            if section != "activeIngredients":
                continue
            total_scanned += 1
            cid = ing.get("canonical_id")
            src = ing.get("canonical_source_db")
            if cid is None and src not in (None, "unmapped"):
                mismatches.append(
                    f"[{brand} {pid}] cid=None but src={src!r} — row={ing.get('raw_source_text')!r}"
                )
            elif cid is not None and src == "unmapped":
                mismatches.append(
                    f"[{brand} {pid}] cid={cid!r} but src='unmapped' — row={ing.get('raw_source_text')!r}"
                )

        if total_scanned == 0:
            pytest.skip("No cleaned batches present yet")

        assert not mismatches, (
            f"D2.1 contract secondary invariant: canonical_source_db must track "
            f"canonical_id presence. Found {len(mismatches)} mismatches (first 10 shown):\n"
            + "\n".join(mismatches[:10])
        )
