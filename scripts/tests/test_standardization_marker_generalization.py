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


class TestAnalyticalFractionMarkers:
    """Test analytical fractions (polysaccharides, saponins, isoflavones, bile acids) under dosed extracts/concentrates."""

    def test_noni_extract_polysaccharides(self, normalizer):
        rows = [
            _row(
                "certified organic Noni fruit extract",
                20000,
                "mg",
                category="herb",
                ingredientGroup="Noni",
                nestedRows=[
                    _row("Polysaccharides", 10000, "mg", category="plant", ingredientGroup="Polysaccharides"),
                ],
            )
        ]
        cleaned = normalizer.normalize_product(
            _make_dsld_product(2255, "Super Noni", rows)
        )
        polys = _rows_named(cleaned, ["Polysaccharides"])
        assert len(polys) == 1
        assert polys[0].get("cleaner_row_role") == "standardization_marker"
        assert polys[0].get("score_eligible_by_cleaner") is False
        assert polys[0].get("quantity") == 10000

    def test_soy_concentrate_isoflavones_and_saponins(self, normalizer):
        rows = [
            _row(
                "Soy Germ Isoflavones Concentrate",
                750,
                "mg",
                category="herb",
                ingredientGroup="Soy",
                nestedRows=[
                    _row("Isoflavones", 22.5, "mg", category="plant", ingredientGroup="Isoflavones"),
                    _row("Saponins", 22.5, "mg", category="plant", ingredientGroup="Saponins"),
                ],
            )
        ]
        cleaned = normalizer.normalize_product(
            _make_dsld_product(4147, "Soy Isoflavones", rows)
        )
        isoflavones = _rows_named(cleaned, ["Isoflavones"])
        saponins = _rows_named(cleaned, ["Saponins"])
        assert len(isoflavones) == 1 and isoflavones[0].get("cleaner_row_role") == "standardization_marker"
        assert len(saponins) == 1 and saponins[0].get("cleaner_row_role") == "standardization_marker"
        assert isoflavones[0].get("score_eligible_by_cleaner") is False
        assert saponins[0].get("score_eligible_by_cleaner") is False



class TestAnalyticalFractionCanaries:
    """The fraction vocabulary names chemical classes; structure decides the role.

    A constituent is a marker only when it is nested under a dosed parent
    extract/concentrate and is physically part of it. The same class sold on
    its own, an unrelated nested nutrient, a plain blend child and a child
    heavier than its parent all stay assessable.
    """

    @staticmethod
    def _role(normalizer, rows, name, dsld_id=990001):
        cleaned = normalizer.normalize_product(_make_dsld_product(dsld_id, "Canary", rows))
        found = _rows_named(cleaned, [name])
        assert len(found) == 1, found
        return found[0].get("cleaner_row_role")

    @pytest.mark.parametrize("name", ["Polysaccharides", "Soy Isoflavones", "Saponins"])
    def test_same_class_sold_as_a_standalone_active_stays_active(self, normalizer, name):
        rows = [_row(name, 500, "mg", category="plant", ingredientGroup=name)]
        assert self._role(normalizer, rows, name) == "active_scorable"

    def test_unrelated_nested_nutrient_is_not_a_marker(self, normalizer):
        rows = [_row("Acerola Cherry Extract", 250, "mg", category="herb", ingredientGroup="Acerola",
                     nestedRows=[_row("Vitamin C", 60, "mg", category="vitamin", ingredientGroup="Vitamin C")])]
        assert self._role(normalizer, rows, "Vitamin C") != "standardization_marker"

    def test_blend_child_is_not_automatically_a_marker(self, normalizer):
        rows = [_row("Proprietary Mushroom Blend", 1000, "mg", category="blend", ingredientGroup="Blend",
                     nestedRows=[_row("Polysaccharides", 300, "mg", category="plant",
                                      ingredientGroup="Polysaccharides")])]
        assert self._role(normalizer, rows, "Polysaccharides") != "standardization_marker"

    def test_child_heavier_than_its_parent_is_not_a_constituent(self, normalizer):
        # 294036-shaped label: a 1.2 mg extract cannot contain 12 mg of anything.
        rows = [_row("Cranberry Fruit Extract", 1.2, "mg", category="herb", ingredientGroup="Cranberry",
                     nestedRows=[_row("Proanthocyanidins", 12, "mg", category="plant",
                                      ingredientGroup="Proanthocyanidins")])]
        assert self._role(normalizer, rows, "Proanthocyanidins") != "standardization_marker"

    def test_gram_scale_parent_still_contains_its_marker(self, normalizer):
        # The mass bound compares in one unit: 1 g of extract holds 950 mg.
        rows = [_row("Reishi Mushroom Extract", 1, "Gram(s)", category="herb", ingredientGroup="Reishi",
                     nestedRows=[_row("Polysaccharides", 950, "mg", category="plant",
                                      ingredientGroup="Polysaccharides")])]
        assert self._role(normalizer, rows, "Polysaccharides") == "standardization_marker"

    def test_named_dose_basis_constituent_under_a_plain_extract_stays_active(self, normalizer):
        # Phase-3 (2026-09-19) rule: only an explicitly standardized parent
        # turns a named constituent such as curcuminoids into a marker.
        rows = [_row("Turmeric Rhizome Extract", 1, "Gram(s)", category="herb", ingredientGroup="Turmeric",
                     nestedRows=[_row("Curcuminoids", 950, "mg", category="plant",
                                      ingredientGroup="Curcuminoids")])]
        assert self._role(normalizer, rows, "Curcuminoids") == "active_scorable"

    def test_nested_extract_is_a_material_not_a_marker(self, normalizer):
        rows = [_row("Antioxidant Extract Complex", 500, "mg", category="herb", ingredientGroup="Blend",
                     nestedRows=[_row("Green Tea Catechins Extract", 200, "mg", category="herb",
                                      ingredientGroup="Green Tea")])]
        assert self._role(normalizer, rows, "Green Tea Catechins Extract") != "standardization_marker"
