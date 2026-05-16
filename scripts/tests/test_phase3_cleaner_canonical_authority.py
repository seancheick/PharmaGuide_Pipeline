"""
Phase 3 regression tests — enricher honors the cleaner's canonical_id as
a hard constraint on IQM parent selection.

Context: the cleaner emits ``canonical_id`` on every active ingredient via
its 17k-entry reverse index. Before Phase 3 the enricher re-derived the
parent by text matching, which caused medical-accuracy bugs:

- "Silybin Phytosome (Siliphos)" labels resolved to the ``lecithin`` parent
  because "phospholipid complex" is an alias there, even though the cleaner
  correctly flagged ``canonical_id='milk_thistle'``.
- "Dicalcium Phosphate" in a phosphorus-bearing multivitamin resolved to
  ``calcium`` because DCP is an alias on both calcium and phosphorus, even
  though the cleaner correctly flagged ``canonical_id='phosphorus'``
  (via DSLD ingredientGroup=Phosphorus).

After Phase 3, ``_match_quality_map(... cleaner_canonical_id=<parent>)``
filters the candidate pool to that parent only, so text-inferred
cross-parent matches cannot win. If no form under the constrained parent
matches, we fall back to a parent-level (unspecified-form) match under
the cleaner's canonical rather than returning a wrong-parent match.

See docs/HANDOFF_2026-04-20_PIPELINE_REFACTOR.md § Phase 3.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3

IQM_PATH = Path(__file__).parent.parent / "data" / "ingredient_quality_map.json"


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


@pytest.fixture(scope="module")
def iqm() -> dict:
    return json.loads(IQM_PATH.read_text())


# ---------------------------------------------------------------------------
# Silybin Phytosome — the canonical Phase 3 target
# ---------------------------------------------------------------------------


class TestSilybinPhytosomeConstraint:
    """When cleaner says milk_thistle, enricher must not route to lecithin."""

    def test_silybin_phytosome_honors_cleaner_milk_thistle(self, enricher, iqm) -> None:
        # Simulating the failure pattern: label text includes phospholipid
        # complex cues that would otherwise text-match to lecithin.
        result = enricher._match_quality_map(
            ing_name="Silybin Phytosome (Siliphos)",
            std_name="Milk Thistle",
            quality_map=iqm,
            cleaner_canonical_id="milk_thistle",
        )
        assert result is not None
        assert result.get("canonical_id") == "milk_thistle", (
            f"Expected milk_thistle, got {result.get('canonical_id')}. "
            f"form_id={result.get('form_id')}, matched_alias={result.get('matched_alias')}"
        )

    def test_cleaner_canonical_enforced_flag_set(self, enricher, iqm) -> None:
        result = enricher._match_quality_map(
            ing_name="Silybin Phytosome (Siliphos)",
            std_name="Silymarin",
            quality_map=iqm,
            cleaner_canonical_id="milk_thistle",
        )
        assert result is not None
        # Flag is attached to every match the cleaner-canonical constraint touches,
        # whether or not it actually filtered anything out.
        assert result.get("cleaner_canonical_id") == "milk_thistle"


# ---------------------------------------------------------------------------
# Phosphorus / DCP — the other Phase 3 target
# ---------------------------------------------------------------------------


class TestPhosphorusDCPConstraint:
    """When cleaner says phosphorus, enricher must not route DCP to calcium."""

    def test_dcp_with_cleaner_phosphorus_resolves_phosphorus(self, enricher, iqm) -> None:
        result = enricher._match_quality_map(
            ing_name="Dicalcium Phosphate",
            std_name="Phosphorus",
            quality_map=iqm,
            cleaner_canonical_id="phosphorus",
        )
        assert result is not None
        assert result.get("canonical_id") == "phosphorus", (
            f"Expected phosphorus, got {result.get('canonical_id')}. "
            f"Cleaner constraint must beat text-inferred calcium alias."
        )

    def test_dcp_with_cleaner_calcium_resolves_calcium(self, enricher, iqm) -> None:
        # The 1 legitimate DCP-as-calcium row in production: DSLD's
        # ingredientGroup is Calcium and the product supplements calcium
        # via DCP. The cleaner canonical wins here too.
        result = enricher._match_quality_map(
            ing_name="Dicalcium Phosphate",
            std_name="Calcium",
            quality_map=iqm,
            cleaner_canonical_id="calcium",
        )
        assert result is not None
        assert result.get("canonical_id") == "calcium"


# ---------------------------------------------------------------------------
# Graceful fallback when the constrained parent has no matching form
# ---------------------------------------------------------------------------


class TestParentFallbackWhenConstrainedPoolEmpty:
    """Constraint to a real IQM parent with zero candidate matches returns a parent-level match."""

    def test_unknown_form_under_cleaner_canonical_falls_back_to_parent(self, enricher, iqm) -> None:
        # Text that would never match anything meaningful under milk_thistle,
        # but the cleaner has flagged milk_thistle via an earlier reverse-index
        # hit (e.g., a branded token cleaned away before the enricher sees it).
        result = enricher._match_quality_map(
            ing_name="xyzzy_nonsense_token_12345",
            std_name="xyzzy_nonsense_token_12345",
            quality_map=iqm,
            cleaner_canonical_id="milk_thistle",
        )
        assert result is not None
        assert result.get("canonical_id") == "milk_thistle"
        # Falling back to a parent-level match (may be unspecified form).
        assert result.get("cleaner_canonical_fallback") is True
        assert result.get("cleaner_canonical_enforced") is True

    @pytest.mark.parametrize(
        ("cleaner_canonical", "label_name", "forms", "wrong_canonicals"),
        [
            (
                "vitamin_e",
                "Vitamin E",
                [{"name": "Alpha-Tocopherol"}, {"name": "Brassica napus"}],
                {"canola_oil", "sunflower_oil"},
            ),
            (
                "phosphorus",
                "Phosphorus",
                [{"name": "Dicalcium Phosphate"}],
                {"calcium", "dicalcium_phosphate"},
            ),
            (
                "dha",
                "DHA",
                [{"name": "ethyl ester"}],
                {"fish_oil", "algae_oil"},
            ),
            (
                "calcium",
                "Calcium",
                [{"name": "Calcium Ascorbate"}],
                {"vitamin_c"},
            ),
            (
                "curcumin",
                "Curcumin",
                [{"name": "Turmeric Extract"}],
                {"turmeric"},
            ),
            (
                "coffee_fruit",
                "Coffee Fruit Extract",
                [{"name": "Caffeine"}],
                {"caffeine"},
            ),
            (
                "nmn",
                "Nicotinamide Mononucleotide",
                [{"name": "Niacinamide"}],
                {"vitamin_b3_niacin"},
            ),
            (
                "nadh",
                "NADH",
                [{"name": "Niacinamide"}],
                {"vitamin_b3_niacin"},
            ),
            (
                "nicotinamide_riboside",
                "Nicotinamide Riboside",
                [{"name": "Niacinamide"}],
                {"vitamin_b3_niacin"},
            ),
            (
                "probiotics",
                "Probiotic Blend",
                [{"name": "Lactobacillus acidophilus"}],
                {"lactobacillus_acidophilus"},
            ),
            (
                "magnesium",
                "Magnesium",
                [{"name": "Magnesium Ascorbate"}],
                {"vitamin_c"},
            ),
        ],
    )
    def test_cleaned_forms_with_only_off_parent_candidates_fall_back_to_cleaner_parent(
        self,
        enricher,
        iqm,
        cleaner_canonical,
        label_name,
        forms,
        wrong_canonicals,
    ) -> None:
        result = enricher._match_quality_map(
            ing_name=label_name,
            std_name=label_name,
            quality_map=iqm,
            cleaned_forms=forms,
            cleaner_canonical_id=cleaner_canonical,
        )
        assert result is not None
        assert result.get("canonical_id") == cleaner_canonical
        assert result.get("canonical_id") not in wrong_canonicals
        assert result.get("cleaner_canonical_id") == cleaner_canonical
        assert result.get("cleaner_canonical_enforced") is True

    @pytest.mark.parametrize(
        ("cleaner_canonical", "label_name", "forms", "expected_canonical"),
        [
            ("vitamin_k", "Vitamin K", [{"name": "Phytonadione"}], "vitamin_k1"),
            (
                "turmeric",
                "Turmeric",
                [{"name": "Meriva Turmeric Phytosome Curcuminoids"}],
                "curcumin",
            ),
        ],
    )
    def test_reviewed_cross_parent_policy_exceptions_still_score_specific_active(
        self,
        enricher,
        iqm,
        cleaner_canonical,
        label_name,
        forms,
        expected_canonical,
    ) -> None:
        result = enricher._match_quality_map(
            ing_name=label_name,
            std_name=label_name,
            quality_map=iqm,
            cleaned_forms=forms,
            cleaner_canonical_id=cleaner_canonical,
        )
        assert result is not None
        assert result.get("canonical_id") == expected_canonical
        assert result.get("cleaner_canonical_id") == cleaner_canonical
        assert result.get("cleaner_canonical_cross_parent_allowed") is True

    def test_turmeric_plain_curcumin_text_does_not_cross_to_curcumin(
        self, enricher, iqm
    ) -> None:
        result = enricher._match_quality_map(
            ing_name="Turmeric",
            std_name="Turmeric",
            quality_map=iqm,
            cleaned_forms=[{"name": "Curcumin C3 Complex"}],
            cleaner_canonical_id="turmeric",
        )
        assert result is not None
        assert result.get("canonical_id") == "turmeric"
        assert result.get("canonical_id") != "curcumin"
        assert result.get("cleaner_canonical_enforced") is True
        assert result.get("cleaner_canonical_cross_parent_allowed") is not True


class TestNonIqmCanonicalAuthority:
    """Cleaner authority also applies to non-IQM source/risk canonicals."""

    @pytest.mark.parametrize(
        ("source_id", "label_name", "forms", "blocked_canonical"),
        [
            ("tomato", "Tomato Extract", [{"name": "Lycopene"}], "lycopene"),
            ("broccoli", "Broccoli Sprout Extract", [{"name": "Sulforaphane"}], "sulforaphane"),
            ("green_tea", "Green Tea Extract", [{"name": "Caffeine"}], "caffeine"),
            ("coffee_fruit", "Coffee Fruit Extract", [{"name": "Caffeine"}], "caffeine"),
            ("acerola_cherry", "Acerola Cherry Extract", [{"name": "Vitamin C"}], "vitamin_c"),
            ("moringa", "Moringa Leaf", [{"name": "Mixed Carotenoids"}], "vitamin_a"),
            ("yerba_mate", "Yerba Mate Extract", [{"name": "Caffeine"}], "caffeine"),
            ("japanese_knotweed", "Japanese Knotweed Extract", [{"name": "Trans-Resveratrol"}], "resveratrol"),
            ("sophora_japonica", "Sophora japonica Flower Extract", [{"name": "Quercetin"}], "quercetin"),
            ("lemon", "Lemon", [{"name": "Vitamin B9 (Folate)"}], "vitamin_b9_folate"),
            ("cayenne_pepper", "Cayenne Pepper", [{"name": "Capsaicin"}], "capsaicin"),
            ("horny_goat_weed", "Horny Goat Weed", [{"name": "Flavones"}], "flavones"),
            ("kanna_sceletium", "Kanna Sceletium", [{"name": "Mesembrine"}], "mesembrine"),
        ],
    )
    def test_botanical_source_rows_do_not_score_as_marker_canonicals(
        self,
        enricher,
        source_id,
        label_name,
        forms,
        blocked_canonical,
    ) -> None:
        result = enricher._collect_ingredient_quality_data({
            "activeIngredients": [{
                "name": label_name,
                "standardName": label_name,
                "quantity": 100,
                "unit": "mg",
                "forms": forms,
                "canonical_source_db": "botanical_ingredients",
                "canonical_id": source_id,
            }],
            "inactiveIngredients": [],
        })
        row = (result["ingredients"] or result["ingredients_skipped"])[0]
        assert row.get("canonical_id") != blocked_canonical
        assert row.get("scoreable_identity") is False

    def test_green_tea_source_can_still_score_as_green_tea_extract(
        self, enricher
    ) -> None:
        result = enricher._collect_ingredient_quality_data({
            "activeIngredients": [{
                "name": "Green Tea Extract",
                "standardName": "Green Tea",
                "quantity": 100,
                "unit": "mg",
                "forms": [],
                "canonical_source_db": "botanical_ingredients",
                "canonical_id": "green_tea",
            }],
            "inactiveIngredients": [],
        })
        row = result["ingredients"][0]
        assert row.get("canonical_id") == "green_tea_extract"
        assert row.get("role_classification") == "active_scorable"
        assert row.get("scoreable_identity") is True

    @pytest.mark.parametrize(
        ("risk_id", "label_name", "normal_canonical"),
        [
            ("RISK_YOHIMBE", "Yohimbe Bark Extract", "yohimbe"),
            ("RISK_GARCINIA_CAMBOGIA", "Garcinia Cambogia", "garcinia_cambogia"),
            ("BANNED_7_KETO_DHEA", "7-Keto DHEA", "7_keto_dhea"),
        ],
    )
    def test_risk_cleaner_rows_preserve_safety_canonical_while_quality_scoring(
        self,
        enricher,
        risk_id,
        label_name,
        normal_canonical,
    ) -> None:
        result = enricher._collect_ingredient_quality_data({
            "activeIngredients": [{
                "name": label_name,
                "standardName": label_name,
                "quantity": 100,
                "unit": "mg",
                "canonical_source_db": "banned_recalled_ingredients",
                "canonical_id": risk_id,
            }],
            "inactiveIngredients": [],
        })
        row = result["ingredients"][0]
        assert row.get("canonical_id") == normal_canonical
        assert row.get("safety_canonical_id") == risk_id
        assert row.get("safety_canonical_source_db") == "banned_recalled_ingredients"
        assert row.get("safety_canonical_preserved") is True
        assert row.get("role_classification") == "active_scorable"
        assert row.get("scoreable_identity") is True


# ---------------------------------------------------------------------------
# Legacy path remains intact when cleaner_canonical_id is absent / non-IQM
# ---------------------------------------------------------------------------


class TestLegacyBehaviorPreserved:
    """Calls without cleaner_canonical_id behave exactly as before Phase 3."""

    def test_no_cleaner_canonical_uses_text_inference(self, enricher, iqm) -> None:
        # Classic cross-parent case; without a cleaner canonical the existing
        # preferred_parent inference decides (vitamin_c via std_name).
        result = enricher._match_quality_map(
            ing_name="Calcium Ascorbate",
            std_name="Vitamin C",
            quality_map=iqm,
        )
        assert result is not None
        assert result.get("canonical_id") == "vitamin_c"
        assert "cleaner_canonical_enforced" not in result

    def test_non_iqm_canonical_id_ignored_as_hard_filter(self, enricher, iqm) -> None:
        # If the cleaner resolved to a botanical (not in IQM), we must NOT
        # hard-filter IQM candidates — the enricher's non-IQM fallback chain
        # should still route the ingredient normally. Passing a canonical
        # that is NOT an IQM key simulates the call-site's own guard returning
        # something truthy-but-external: this must be harmless.
        result = enricher._match_quality_map(
            ing_name="Ashwagandha Root Extract",
            std_name="Ashwagandha",
            quality_map=iqm,
            cleaner_canonical_id="ashwagandha_not_in_iqm_sentinel",
        )
        # Whether or not IQM produces a match, the non-IQM canonical should
        # not leak into the enforcement telemetry.
        if result is not None:
            assert result.get("cleaner_canonical_enforced") is not True
            assert result.get("cleaner_canonical_fallback") is not True

    def test_none_canonical_no_telemetry_leak(self, enricher, iqm) -> None:
        result = enricher._match_quality_map(
            ing_name="Vitamin D3",
            std_name="Vitamin D",
            quality_map=iqm,
            cleaner_canonical_id=None,
        )
        assert result is not None
        assert "cleaner_canonical_enforced" not in result
        assert "cleaner_canonical_fallback" not in result
