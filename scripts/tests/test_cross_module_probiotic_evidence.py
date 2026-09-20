"""Tests for cross-module probiotic evidence ownership and disposition seam.

Pins the single canonical probiotic Evidence owner contract:
1. Row role audit:
   - Yeast/bacterial source material, fermentate, or beta-glucan source rows
     (e.g. S. cerevisiae in Jarrow Beta Glucan or MegaFood Zinc) are NOT probiotic
     actives and must NOT route to probiotic evidence.
2. Exact-strain stub products:
   - Products in non-probiotic routes (generic, sports, fiber_digestive) containing
     exact strains with stubs (e.g. DE111, LP-115, LA-14) or pending clinical reviews
     receive 'native_research_review_incomplete' with score 0.0 and remain partial.
3. Species-only with strain literature:
   - Products declaring only species (e.g. Bacillus subtilis in Doctor's Best, Ora,
     Garden of Life Collagen) where strain research exists in the registry receive
     'research_present_applicability_unestablished' with score 0.0 (no points manufactured).
4. Product-level composition:
   - When companion actives earn applicable evidence points, the product-level state
     may be 'evaluated_applicable', but the probiotic component disposition in
     metadata['probiotic_component_evidence'] is strictly preserved.
5. Invariants:
   - Zero exact-strain credit granted to species-only.
   - Zero species->strain transfer.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from probiotic_measurements import is_probiotic_source_identity
from studied_formulas import assess_probiotic_component_disposition
from scoring_v4.modules.generic_evidence import score_evidence as score_generic_evidence
from scoring_v4.modules.fiber_digestive import score_fiber_digestive
from scoring_v4.modules.sports import score_sports
from tests.test_v4_generic_evidence_p133 import _ingredient, _match, _product


ROOT = Path(__file__).resolve().parents[2]


def _load_enriched_product(brand_dir: str, target_id: str) -> dict | None:
    """Load one enriched product from the locally-built corpus.

    ``scripts/products/`` is gitignored build output, so a clean checkout (a
    fresh worktree or CI) holds no corpus at all. When a brand's enriched
    directory is absent the behavior under test simply cannot be observed in
    this environment, so the test skips — matching the repo convention already
    used by ``test_red_yeast_rice_alias_coverage`` and
    ``test_v4_banned_form_evidence_gate`` ("enriched corpus not present").

    When the directory *is* present but the requested product is missing, the
    caller's assertion still fires: that is a real catalog regression and must
    never be silently skipped.
    """
    path = ROOT / "scripts/products" / brand_dir / "enriched"
    files = sorted(path.glob("*.json"))
    if not files:
        pytest.skip(f"enriched corpus not present ({brand_dir})")
    for f in files:
        try:
            d = json.load(open(f))
        except Exception:
            continue
        items = d if isinstance(d, list) else d.get("products", [d])
        for p in items:
            if str(p.get("dsld_id") or p.get("id")) == str(target_id):
                return p
    return None


class TestCrossModuleProbioticRowRoleAudit:
    """Verify that non-probiotic source material / fermentate rows are distinguished from live probiotic actives."""

    def test_megafood_zinc_s_cerevisiae_is_not_probiotic_active(self):
        """In MegaFood Zinc (177233), S. cerevisiae is nutritional yeast fermentation medium, not a probiotic active."""
        p = _load_enriched_product("output_MegaFood_enriched", "177233")
        assert p is not None, "MegaFood Zinc 177233 must exist in catalog"
        iqd = p.get("ingredient_quality_data") or {}
        prob_rows = [i for i in iqd.get("ingredients", []) if is_probiotic_source_identity(i)]
        assert prob_rows == [], "S. cerevisiae in MegaFood Zinc must not be classified as a probiotic active"
        disp = assess_probiotic_component_disposition(p)
        assert disp["has_probiotic_component"] is False

    def test_jarrow_beta_glucan_s_cerevisiae_is_not_probiotic_active(self):
        """In Jarrow Beta Glucan (264610, 307558), S. cerevisiae is beta-glucan source material, not a live probiotic active."""
        for did in ["264610", "307558"]:
            p = _load_enriched_product("output_Jarrow_Formulas_enriched", did)
            assert p is not None, f"Jarrow Beta Glucan {did} must exist in catalog"
            iqd = p.get("ingredient_quality_data") or {}
            prob_rows = [i for i in iqd.get("ingredients", []) if is_probiotic_source_identity(i)]
            assert prob_rows == [], f"S. cerevisiae extract in {did} must not be classified as a probiotic active"
            disp = assess_probiotic_component_disposition(p)
            assert disp["has_probiotic_component"] is False


class TestCrossModuleExactStrainDisposition:
    """Verify that exact-strain products in generic/sports/fiber modules delegate to canonical probiotic owner."""

    def test_garden_of_life_md_protein_de111_stub_is_native_review_incomplete(self):
        """Garden of Life MD Protein with DE111 (273676) routes through sports and has unreviewed strain stub DE111."""
        p = _load_enriched_product("output_Garden_of_life_enriched", "273676")
        assert p is not None, "DSLD 273676 must exist"
        disp = assess_probiotic_component_disposition(p)
        assert disp["has_probiotic_component"] is True
        assert disp["disposition_state"] == "native_research_review_incomplete"
        assert disp["evidence_score"] == 0.0

        # When evaluated by generic_evidence
        ev = score_generic_evidence(p, apply_primary_floor=True)
        assert ev["score"] == 0.0
        assert ev["metadata"]["evidence_result_state"] == "native_research_review_incomplete"
        assert ev["metadata"]["probiotic_component_evidence"] is not None
        assert ev["metadata"]["probiotic_component_evidence"]["disposition_state"] == "native_research_review_incomplete"

    def test_life_extension_digestive_enzymes_with_mtcc5856(self):
        """Life Extension Digestive Enzymes with MTCC 5856 (232295) routes through fiber_digestive."""
        p = _load_enriched_product("output_Life_Extension_enriched", "232295")
        assert p is not None, "DSLD 232295 must exist"
        disp = assess_probiotic_component_disposition(p)
        assert disp["has_probiotic_component"] is True
        # MTCC 5856 has pending study contexts in registry
        assert disp["disposition_state"] == "native_research_review_incomplete"
        assert disp["evidence_score"] == 0.0

        # Evaluated through fiber_digestive
        res = score_fiber_digestive(p)
        ev = res.dimensions["evidence"]
        assert ev.score == 0.0
        assert ev.metadata["evidence_result_state"] == "native_research_review_incomplete"


class TestCrossModuleSpeciesOnlyDisposition:
    """Verify species-only products with strain literature in registry get research_present_applicability_unestablished."""

    def test_doctors_best_digestive_enzymes_bacillus_subtilis(self):
        """Doctor's Best Digestive Enzymes (209440) has species-only Bacillus subtilis."""
        p = _load_enriched_product("output_Doctors_Best_enriched", "209440")
        assert p is not None, "DSLD 209440 must exist"
        disp = assess_probiotic_component_disposition(p)
        assert disp["has_probiotic_component"] is True
        assert disp["disposition_state"] == "research_present_applicability_unestablished"
        assert disp["evidence_score"] == 0.0

        # Evaluated through fiber_digestive
        res = score_fiber_digestive(p)
        ev = res.dimensions["evidence"]
        assert ev.score == 0.0
        assert ev.metadata["evidence_result_state"] == "research_present_applicability_unestablished"

    def test_garden_of_life_collagen_creamer_bacillus_subtilis(self):
        """Garden of Life Collagen Creamer (222870) routes through generic and has species-only Bacillus subtilis."""
        p = _load_enriched_product("output_Garden_of_life_enriched", "222870")
        assert p is not None, "DSLD 222870 must exist"
        disp = assess_probiotic_component_disposition(p)
        assert disp["has_probiotic_component"] is True
        assert disp["disposition_state"] == "research_present_applicability_unestablished"
        assert disp["evidence_score"] == 0.0

        ev = score_generic_evidence(p, apply_primary_floor=True)
        assert ev["score"] == 0.0
        assert ev["metadata"]["evidence_result_state"] == "research_present_applicability_unestablished"

    def test_ora_break_it_down_bacillus_subtilis(self):
        """Ora Break it Down (208587) has species-only Bacillus subtilis."""
        p = _load_enriched_product("output_Ora_enriched", "208587")
        assert p is not None, "DSLD 208587 must exist"
        disp = assess_probiotic_component_disposition(p)
        assert disp["has_probiotic_component"] is True
        assert disp["disposition_state"] == "research_present_applicability_unestablished"
        assert disp["evidence_score"] == 0.0

        res = score_fiber_digestive(p)
        ev = res.dimensions["evidence"]
        assert ev.score == 0.0
        assert ev.metadata["evidence_result_state"] == "research_present_applicability_unestablished"


class TestProductLevelCompanionComposition:
    """Verify companion active points do not erase probiotic component disposition in metadata."""

    def test_companion_points_preserve_probiotic_component_state(self):
        """Product with Vitamin C (earns points) + species-only Bacillus subtilis."""
        vit_c = _ingredient(name="Vitamin C", canonical_id="vitamin_c", quantity=500.0, unit="mg")
        prob = {
            "name": "Bacillus subtilis",
            "canonical_id": "bacillus_subtilis",
            "quantity": 0.0,
            "unit": "NP",
            "mapped": True,
            "category": "probiotic",
        }
        match_c = _match(
            id="INGR_VITAMIN_C",
            canonical_ids=["vitamin_c"],
            score_contribution="tier_1",
            effect_direction="positive_strong",
            min_clinical_dose=100.0,
            dose_lookup_key="vitamin_c",
        )
        product = _product(
            ingredients=[vit_c, prob],
            matches=[match_c],
            probiotic_data={
                "is_probiotic_product": True,
                "probiotic_blends": [
                    {
                        "name": "Bacillus subtilis",
                        "strains": ["Bacillus subtilis"],
                        "strain_identity_resolution": [{"strain": "Bacillus subtilis", "resolution": "species_only"}],
                    }
                ],
            },
        )
        ev = score_generic_evidence(product)
        # Vitamin C earned points
        assert ev["score"] > 0.0
        assert ev["metadata"]["evidence_result_state"] == "evaluated_applicable"

        # BUT probiotic component disposition is strictly preserved in metadata
        prob_comp = ev["metadata"].get("probiotic_component_evidence")
        assert prob_comp is not None
        assert prob_comp["has_probiotic_component"] is True
        assert prob_comp["disposition_state"] == "research_present_applicability_unestablished"
        assert prob_comp["reason"] == "species_only_with_strain_literature"
