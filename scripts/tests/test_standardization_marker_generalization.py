"""Regression coverage for the generalization reach of the standardization-marker rule.

The 2026-09-19 clinical-signoff fix re-roles a nested constituent of a *dosed
standardized botanical extract* as ``standardization_marker``: the extract keeps
the dose-bearing identity, the constituent keeps its declared quantity as
disclosure, and the constituent can no longer surface as an orphan identity
conflict (see ``test_clinical_signoff_engineering_fixes_20260919``).

That rule is deliberately STRUCTURAL, so it is not limited to the two products
named in the clinical packet. An independent row-level audit of the Phase-3
integration replay found it also reaches three Solgar products that were never
Phase-3 targets, with small tier-preserving score movements:

* 216776 Herbal Complex
* 44423 Deglycyrrhized Licorice Root Extract
* 77254 Male Multiple

Before accepting the generalized rule, the reach has to be justified rather than
assumed. These tests pin it, and pin the two properties the clinical team
required when it approved the rule:

1. every affected parent really is a *dosed standardized botanical extract*, so
   the constituent genuinely is a percentage disclosure of that parent; and
2. the declared constituent quantity survives (disclosure is preserved, not
   deleted), with the parent's dose untouched and still scoreable.

Safety independence for the same five products (216948, 232718 and these three)
is evidenced at the scored end-to-end level by the Phase-3 replay — the Safety
fields are byte-identical across both arms — because Safety is evaluated from
the label record, independently of score eligibility.

The fixtures below reproduce the archived frozen labels row-for-row
(``scripts/products/`` is gitignored build output, so synthetic rows are used).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer

from tests.test_clinical_signoff_engineering_fixes_20260919 import (
    _make_dsld_product,
    _row,
)


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


def _standardized_extract(name: str, mg: float, children: list) -> dict:
    """A dosed ``standardized <botanical> extract`` parent + its % constituents."""
    return _row(
        name,
        mg,
        "mg",
        category="herb",
        ingredientGroup=name,
        nestedRows=[
            _row(cname, cqty, cunit, category="plant", ingredientGroup=cname)
            for cname, cqty, cunit in children
        ],
    )


def _rows_named(cleaned: dict, names) -> list:
    wanted = {str(n).lower() for n in names}
    return [
        r
        for r in (cleaned.get("activeIngredients") or [])
        if str(r.get("name", "")).lower() in wanted
    ]


class TestHerbalComplexStandardizedExtracts:
    """216776 Herbal Complex: six dosed standardized extracts, six constituents."""

    def _rows(self) -> list:
        return [
            _standardized_extract(
                "standardized Astragalus extract", 100, [("Triterpene Glycosides", 0.5, "mg")]
            ),
            _standardized_extract(
                "standardized Cat's Claw extract", 100,
                [("Alkaloids", 3, "mg"), ("Polyphenols", 15, "mg")],
            ),
            _standardized_extract(
                "standardized Echinacea extract", 100, [("Echinacosides", 4, "mg")]
            ),
            _standardized_extract(
                "standardized Deglycyrrhized Licorice extract", 100,
                [("Glycyrrhizin", 1, "mg")],
            ),
            _standardized_extract(
                "standardized Elderberry extract", 100, [("Polyphenols", 30, "mg")]
            ),
            _standardized_extract(
                "standardized Olive leaf extract", 100, [("Oleuropein", 6, "mg")]
            ),
            # A raw botanical powder is NOT a standardized-extract parent and must
            # keep ordinary handling.
            _row("raw Echinacea powder", 20, "mg", category="herb", ingredientGroup="Echinacea"),
        ]

    def test_all_six_dosed_parents_survive_and_stay_scoreable(self, normalizer):
        cleaned = normalizer.normalize_product(
            _make_dsld_product(216776, "Herbal Complex", self._rows())
        )
        parents = [
            r
            for r in (cleaned.get("activeIngredients") or [])
            if "standardized" in str(r.get("name", "")).lower()
            and "extract" in str(r.get("name", "")).lower()
        ]
        assert len(parents) == 6, (
            f"expected 6 dosed standardized-extract parents, got "
            f"{[r.get('name') for r in parents]}"
        )
        for parent in parents:
            assert parent.get("quantity") == 100, (
                f"{parent.get('name')!r} lost its dose: {parent.get('quantity')}"
            )
            assert parent.get("score_eligible_by_cleaner") is not False, (
                f"{parent.get('name')!r} was de-eligibilised; the dose owner must "
                "remain scoreable and only its constituent becomes a marker"
            )

    def test_constituents_are_markers_and_keep_their_declared_quantity(self, normalizer):
        cleaned = normalizer.normalize_product(
            _make_dsld_product(216776, "Herbal Complex", self._rows())
        )
        constituents = _rows_named(
            cleaned,
            [
                "Triterpene Glycosides",
                "Alkaloids",
                "Polyphenols",
                "Echinacosides",
                "Glycyrrhizin",
                "Oleuropein",
            ],
        )
        assert constituents, "standardization constituents were dropped silently"
        for row in constituents:
            name = row.get("name")
            assert row.get("cleaner_row_role") == "standardization_marker", (
                f"{name!r} kept role {row.get('cleaner_row_role')!r}"
            )
            assert row.get("score_eligible_by_cleaner") is False, (
                f"{name!r} is still score eligible as an independent active"
            )
            assert row.get("quantity") and row.get("quantity") > 0, (
                f"{name!r} lost its declared disclosure quantity"
            )
            assert str(row.get("parentBlend") or "").strip(), (
                f"{name!r} lost its dosed-parent provenance"
            )
        # Both independent Polyphenols disclosures (Cat's Claw 15 mg, Elderberry
        # 30 mg) survive as separate rows rather than collapsing into one.
        polyphenols = sorted(
            r.get("quantity")
            for r in constituents
            if str(r.get("name", "")).lower() == "polyphenols"
        )
        assert polyphenols == [15, 30], f"polyphenols disclosures changed: {polyphenols}"


class TestDeglycyrrhizedLicorice:
    """44423: standardized extract 250 mg carries Glycyrrhizin 3 mg (<1%)."""

    def test_glycyrrhizin_is_marker_under_the_dosed_extract(self, normalizer):
        rows = [
            _standardized_extract(
                "standardized Deglycyrrhized Licorice extract", 250,
                [("Glycyrrhizin", 3, "mg")],
            ),
            _row("raw Licorice powder", 225, "mg", category="herb", ingredientGroup="Licorice"),
        ]
        cleaned = normalizer.normalize_product(
            _make_dsld_product(44423, "Deglycyrrhized Licorice Root Extract", rows)
        )
        parent = [
            r
            for r in (cleaned.get("activeIngredients") or [])
            if "deglycyrrhized licorice extract" in str(r.get("name", "")).lower()
        ]
        assert parent, "dosed standardised-extract parent lost"
        assert parent[0].get("quantity") == 250
        assert parent[0].get("score_eligible_by_cleaner") is not False

        glycyrrhizin = _rows_named(cleaned, ["Glycyrrhizin"])
        assert glycyrrhizin, "glycyrrhizin disclosure dropped"
        assert glycyrrhizin[0].get("cleaner_row_role") == "standardization_marker"
        assert glycyrrhizin[0].get("score_eligible_by_cleaner") is False
        assert glycyrrhizin[0].get("quantity") == 3


class TestMaleMultipleGinsenosides:
    """77254: two standardized ginseng parents, each with its own ginsenosides."""

    def _rows(self) -> list:
        return [
            _standardized_extract(
                "standardized American Ginseng extract", 25, [("Ginsenosides", 2.5, "mg")]
            ),
            _standardized_extract(
                "standardized Korean Ginseng extract", 25, [("Ginsenosides", 2, "mg")]
            ),
            _row("Eleuthero extract", 25, "mg", category="herb", ingredientGroup="Eleuthero"),
        ]

    def test_each_ginsenoside_disclosure_stays_with_its_own_parent(self, normalizer):
        cleaned = normalizer.normalize_product(
            _make_dsld_product(77254, "Male Multiple", self._rows())
        )
        ginsenosides = _rows_named(cleaned, ["Ginsenosides"])
        assert len(ginsenosides) == 2, (
            f"expected two ginsenoside disclosures, got {[r.get('name') for r in ginsenosides]}"
        )
        for row in ginsenosides:
            assert row.get("cleaner_row_role") == "standardization_marker", (
                f"ginsenoside kept role {row.get('cleaner_row_role')!r}"
            )
            assert row.get("score_eligible_by_cleaner") is False
            assert "ginseng" in str(row.get("parentBlend") or "").lower(), (
                f"ginsenoside lost its ginseng parent: {row.get('parentBlend')!r}"
            )
        assert sorted(r.get("quantity") for r in ginsenosides) == [2, 2.5]

    def test_non_standardized_extract_sibling_is_not_a_marker_parent(self, normalizer):
        cleaned = normalizer.normalize_product(
            _make_dsld_product(77254, "Male Multiple", self._rows())
        )
        eleuthero = _rows_named(cleaned, ["Eleuthero extract"])
        assert eleuthero, "non-standardized extract sibling lost"
        assert all(r.get("score_eligible_by_cleaner") is not False for r in eleuthero), (
            "a plain extract must not be treated as a marker parent"
        )
