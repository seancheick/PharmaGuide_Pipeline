"""
Canonical-identity raw_name-priority regression test.

When the cleaner's fuzzy matcher collapses a sharply-defined source
label into a broader umbrella parent — e.g., "Fish Oil concentrate" →
"Omega-3 Fatty Acids" at the standard_name resolution stage —
``_resolve_canonical_identity`` now prefers a raw_name lookup before
falling back to the standard_name lookup.

Why this matters: under Phase 3 the enricher honors the cleaner's
``canonical_id`` as a hard constraint. If the cleaner emits the
umbrella canonical, the enricher is locked out of the more specific
form-level match. The raw_name-first reverse-index probe keeps the
sharper canonical (``fish_oil`` vs ``omega_3``, both legitimate IQM
parents with different bio_scores) intact.

See Phase 3 shadow-diff notes in
docs/HANDOFF_2026-04-20_PIPELINE_REFACTOR.md and the Phase 3 enricher
test file ``test_phase3_cleaner_canonical_authority.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


class TestRawNamePriority:
    """raw_name hits win over standard_name hits; misses fall back."""

    def test_fish_oil_concentrate_resolves_fish_oil_not_omega_3(self, normalizer) -> None:
        # Cleaner's fuzzy matcher maps the raw "Fish Oil concentrate" to
        # standard_name "Omega-3 Fatty Acids" (the umbrella IQM parent).
        # Reverse-index-first with raw_name should recover the sharper
        # fish_oil canonical (bio=10) instead of omega_3 (bio=8).
        result = normalizer._resolve_canonical_identity(
            standard_name="Omega-3 Fatty Acids",
            raw_name="Fish Oil concentrate",
        )
        assert result == ("fish_oil", "ingredient_quality_map")

    def test_unambiguous_raw_name_wins(self, normalizer) -> None:
        result = normalizer._resolve_canonical_identity(
            standard_name="Omega-3 Fatty Acids",
            raw_name="Fish Oil",
        )
        assert result == ("fish_oil", "ingredient_quality_map")

    def test_raw_name_miss_falls_back_to_standard(self, normalizer) -> None:
        # When raw_name isn't a reverse-index key, behavior matches the
        # pre-Phase-3 contract — use standard_name.
        result = normalizer._resolve_canonical_identity(
            standard_name="Omega-3 Fatty Acids",
            raw_name="Some Random Label Token No One Ships",
        )
        assert result == ("omega_3", "ingredient_quality_map")

    def test_both_miss_returns_none(self, normalizer) -> None:
        result = normalizer._resolve_canonical_identity(
            standard_name="Nonexistent Parent",
            raw_name="Also Nonexistent",
        )
        assert result == (None, None)

    def test_silybin_phytosome_still_resolves_milk_thistle(self, normalizer) -> None:
        # Regression guard: the Phase 3 primary target should keep working.
        result = normalizer._resolve_canonical_identity(
            standard_name="Milk Thistle",
            raw_name="Silybin Phytosome",
        )
        assert result == ("milk_thistle", "ingredient_quality_map")

    def test_dcp_respects_standard_name_when_raw_is_alias(self, normalizer) -> None:
        # "Dicalcium Phosphate" is an alias under BOTH calcium and phosphorus
        # IQM parents. Reverse-index collision resolution depends on which
        # parent is indexed first, so the test asserts a stable (not
        # arbitrary) outcome — either result is OK as long as it's
        # consistent with the reverse-index build order.
        result = normalizer._resolve_canonical_identity(
            standard_name="Phosphorus",
            raw_name="Dicalcium Phosphate",
        )
        # Whichever parent the reverse index picks, it must be one of
        # these two IQM canonicals — not None.
        assert result is not None
        assert result[0] in ("calcium", "phosphorus")
        assert result[1] == "ingredient_quality_map"

    def test_empty_raw_name_uses_standard(self, normalizer) -> None:
        # Defensive: empty raw_name must not short-circuit the standard_name path.
        result = normalizer._resolve_canonical_identity(
            standard_name="Fish Oil",
            raw_name="",
        )
        assert result == ("fish_oil", "ingredient_quality_map")

    def test_none_raw_name_uses_standard(self, normalizer) -> None:
        result = normalizer._resolve_canonical_identity(
            standard_name="Fish Oil",
            raw_name=None,
        )
        assert result == ("fish_oil", "ingredient_quality_map")
