"""
Wave 6.Z Slice Z1 — Cleaner Enzyme cid-Gap Fallback (TDD-first).

Inventory: reports/z_opaque_sub_inventory.md (Codex-revised count = 7 products)

Problem (verified by inventory):
  - 7 corpus products are real digestive-enzyme blends but their blend_header_total
    row carries canonical_id=None because the IQM alias resolver only checked
    the header name (e.g., "Proprietary Enzyme Blend", "Nordic Enzyme Blend")
    against the canonical reverse-index. It never used the product fullName
    as a fallback signal.
  - Result: anchor path (already enabled for digestive_enzymes by Wave 6.Z A.2b)
    cannot fire, products stay NOT_SCORED.

Z1 fix (cleaner-side only — no scorer, no IQM, no B5 changes):
  Add `_apply_z1_enzyme_cid_fallback(product_fullname, active_rows)` to
  EnhancedDSLDNormalizer. After existing context-canonical-override pass in
  normalize_product, invoke this fallback. It:
    G1 — checks product fullName OR header standardName against curated enzyme
         allowlist (12 v1 signals)
    G2 — requires ≥50% of nested children to carry enzyme tokens AND 0 children
         have usable individual doses
    G3 — if multiple blend headers exist, the enzyme header must be largest
         by mass OR product name clearly enzyme-primary
    G4 — overwrites canonical_id="digestive_enzymes" +
         canonical_source_db="ingredient_quality_map" (v1: this cid only)

Tests are TDD-first: they MUST FAIL on current main. After the production
change they MUST PASS.

Companion production diff (do NOT commit until user reviews):
  - scripts/enhanced_normalizer.py — new method `_apply_z1_enzyme_cid_fallback`
    + invocation at the end of the existing context-override block
    (around line 4244, after _apply_context_canonical_override loop)

Codex's split (per review):
  - 7 cleaner-level positives, one per real DSLD candidate
  - 2 negative guard tests (G1 over-fire, G2 child-dose)
  - 3 downstream scoring assertions on representative cases only (mirror A.2b)
"""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402
from score_supplements import SupplementScorer  # noqa: E402
from test_not_scored_truthful_diagnostics import (  # noqa: E402
    _make_blend_header_anchor_eligible,
)


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


@pytest.fixture(scope="module")
def scorer() -> SupplementScorer:
    return SupplementScorer()


# ---------------------------------------------------------------------------
# Cleaner-row-shape fixture builders (mirror cleaner output schema)
# ---------------------------------------------------------------------------


def _bh_row(name, std=None, qty=391.0, unit="mg", cid=None, src_db="unmapped"):
    """Blend header row in cleaner output shape."""
    return {
        "name": name,
        "standardName": std or name,
        "canonical_id": cid,
        "canonical_source_db": src_db,
        "quantity": qty,
        "unit": unit,
        "cleaner_row_role": "blend_header_total",
        "score_eligible_by_cleaner": False,
        "score_exclusion_reason": "blend_header_total",
        "isNestedIngredient": False,
        "proprietaryBlend": True,
    }


def _nested_child(name, std=None, qty=0.0, unit="NP"):
    """Display-only nested child row (qty=0, unit=NP by default)."""
    return {
        "name": name,
        "standardName": std or name,
        "canonical_id": None,
        "canonical_source_db": "unmapped",
        "quantity": qty,
        "unit": unit,
        "cleaner_row_role": "nested_display_only",
        "score_eligible_by_cleaner": False,
        "score_exclusion_reason": "nested_display_only",
        "isNestedIngredient": True,
        "proprietaryBlend": True,
    }


# ===========================================================================
# CLASS: 7 cleaner-level positives — one per real Z1 DSLD candidate
# Each fixture mirrors the actual blend header name + qty + nested children
# from the corpus (verified 2026-05-26 against enriched outputs).
# ===========================================================================


class TestZ1CleanerEnzymeCidFallback:

    def test_69692_gnc_digestive_enzyme_blend(self, normalizer):
        """DSLD 69692 GNC Women's Ultra Mega Digestive Enzyme Blend.
        BH='Proprietary Enzyme Blend' qty=44.84mg, 5 enzyme children."""
        rows = [
            _bh_row("Proprietary Enzyme Blend", qty=44.84, unit="mg"),
            _nested_child("Amylase"),
            _nested_child("Protease 4.5"),
            _nested_child("Lipase"),
            _nested_child("Protease 3"),
            _nested_child("Protease 6"),
        ]
        normalizer._apply_z1_enzyme_cid_fallback("Digestive Enzyme Blend", rows)
        assert rows[0]["canonical_id"] == "digestive_enzymes"
        assert rows[0]["canonical_source_db"] == "ingredient_quality_map"

    def test_184411_pure_encap_digestive_enzymes_ultra(self, normalizer):
        """DSLD 184411 Pure Encapsulations Digestive Enzymes Ultra.
        BH='Proprietary Enzyme Blend' qty=391mg, 13 enzyme children."""
        rows = [
            _bh_row("Proprietary Enzyme Blend", qty=391.0, unit="mg"),
            _nested_child("Amylase"),
            _nested_child("Protease"),
            _nested_child("Protease 6"),
            _nested_child("Glucoamylase"),
            _nested_child("Lactase"),
            _nested_child("Lipase"),
        ]
        normalizer._apply_z1_enzyme_cid_fallback("Digestive Enzymes Ultra", rows)
        assert rows[0]["canonical_id"] == "digestive_enzymes"
        assert rows[0]["canonical_source_db"] == "ingredient_quality_map"

    def test_232243_life_extension_extraordinary_enzymes(self, normalizer):
        """DSLD 232243 Life Extension Extraordinary Enzymes.
        BH='Nutrient Absorption Blend' qty=200mg, 12 enzyme children.
        Signal lives in product fullName ('extraordinary enzymes'),
        NOT in header standardName ('Nutrient Absorption Blend')."""
        rows = [
            _bh_row("Nutrient Absorption Blend", qty=200.0, unit="mg"),
            _nested_child("Protease SP"),
            _nested_child("Protease"),
            _nested_child("Acid Protease"),
            _nested_child("Lipase"),
            _nested_child("Cellulase"),
            _nested_child("Trypsin"),
        ]
        normalizer._apply_z1_enzyme_cid_fallback("Extraordinary Enzymes", rows)
        assert rows[0]["canonical_id"] == "digestive_enzymes"
        assert rows[0]["canonical_source_db"] == "ingredient_quality_map"

    def test_250719_nordic_naturals_nordic_flora_digestive_enzymes(self, normalizer):
        """DSLD 250719 Nordic Naturals Nordic Flora Digestive Enzymes.
        BH='Nordic Enzyme Blend' qty=300mg, 12 enzyme children."""
        rows = [
            _bh_row("Nordic Enzyme Blend", qty=300.0, unit="mg"),
            _nested_child("Vegetarian Pancreatin Analog"),
            _nested_child("Amylase"),
            _nested_child("Protease"),
            _nested_child("Lipase"),
            _nested_child("Papain"),
        ]
        normalizer._apply_z1_enzyme_cid_fallback("Nordic Flora Digestive Enzymes", rows)
        assert rows[0]["canonical_id"] == "digestive_enzymes"
        assert rows[0]["canonical_source_db"] == "ingredient_quality_map"

    def test_277667_pure_encap_digezyme_chewables(self, normalizer):
        """DSLD 277667 Pure Encapsulations Digestive Enzyme Chewables / DigeZyme.
        BH='DigeZyme' qty=50mg, 5 enzyme children. Signal in header standardName."""
        rows = [
            _bh_row("DigeZyme", qty=50.0, unit="mg"),
            _nested_child("Protease"),
            _nested_child("Lipase"),
            _nested_child("Alpha-Amylase"),
            _nested_child("Lactase"),
            _nested_child("Cellulase"),
        ]
        normalizer._apply_z1_enzyme_cid_fallback(
            "Digestive Enzyme Chewables Natural Mixed Berry Flavor", rows
        )
        assert rows[0]["canonical_id"] == "digestive_enzymes"
        assert rows[0]["canonical_source_db"] == "ingredient_quality_map"

    def test_278021_pure_encap_pancreatic_vegenzymes(self, normalizer):
        """DSLD 278021 Pure Encapsulations Pancreatic VegEnzymes.
        BH='Proprietary Enzyme Blend' qty=200mg, 3 enzyme children.
        'vegenzymes' signal lives in product fullName."""
        rows = [
            _bh_row("Proprietary Enzyme Blend", qty=200.0, unit="mg"),
            _nested_child("Protease 4.5"),
            _nested_child("Lipase"),
            _nested_child("Amylase"),
        ]
        normalizer._apply_z1_enzyme_cid_fallback("Pancreatic VegEnzymes", rows)
        assert rows[0]["canonical_id"] == "digestive_enzymes"
        assert rows[0]["canonical_source_db"] == "ingredient_quality_map"

    def test_293957_pure_encap_digestive_enzymes_ultra_variant(self, normalizer):
        """DSLD 293957 Pure Encapsulations Digestive Enzymes Ultra (variant of 184411).
        Same shape: BH='Proprietary Enzyme Blend' qty=391mg, 13 enzyme children."""
        rows = [
            _bh_row("Proprietary Enzyme Blend", qty=391.0, unit="mg"),
            _nested_child("Amylase"),
            _nested_child("Protease"),
            _nested_child("Protease 6"),
            _nested_child("Glucoamylase"),
            _nested_child("Lactase"),
            _nested_child("Lipase"),
        ]
        normalizer._apply_z1_enzyme_cid_fallback("Digestive Enzymes Ultra", rows)
        assert rows[0]["canonical_id"] == "digestive_enzymes"
        assert rows[0]["canonical_source_db"] == "ingredient_quality_map"

    # ---------------------------------------------------------------------
    # 2 NEGATIVE GUARD TESTS — fallback MUST NOT fire on these shapes
    # ---------------------------------------------------------------------

    def test_negative_joint_health_no_enzyme_kw_g1_over_fire_guard(self, normalizer):
        """G1 over-fire guard: 'Joint Health Herb Blend' is NOT enzyme territory.
        Product fullName 'Joint Health' has no enzyme signal. The fallback
        must NOT overwrite the cid. This guards against allowlist drift —
        if someone naively maps 'health' or 'blend' to digestive_enzymes,
        this test fails."""
        rows = [
            _bh_row("Joint Health Herb Blend", qty=250.0, unit="mg"),
            _nested_child("Boswellia"),
            _nested_child("Turmeric"),
            _nested_child("Ginger"),
        ]
        normalizer._apply_z1_enzyme_cid_fallback("Joint Health", rows)
        assert rows[0]["canonical_id"] is None, (
            "Joint Health products must NOT be reassigned to digestive_enzymes — "
            "guards against G1 allowlist over-firing"
        )
        assert rows[0]["canonical_source_db"] == "unmapped"

    def test_negative_g3_dominance_minor_enzyme_bh_does_not_fire(self, normalizer):
        """G3 dominance guard (synthetic): a wellness multivitamin-style product
        with TWO blend headers — a dominant non-enzyme blend (1500mg) and a
        small accessory enzyme blend (50mg). G1 passes (enzyme signal in the
        small BH standardName) AND G2 passes (children are enzyme display-only)
        — but G3 must abort the cid assignment because:
          - largest BH by mass ("Wellness Proprietary Blend") is NOT enzyme-named
          - product fullName ("Wellness Formula") has no explicit enzyme signal
        Crediting the small accessory enzyme BH while the 30x bigger non-enzyme
        BH is opaque would be misleading. Same clinical-fidelity concern that
        deferred A1_whey_protein (where a 100mg cid'd blend stood next to a
        1600mg opaque blend).

        No current Z1 corpus product matches this shape (all 7 are single-BH),
        but the guard is required for 100K+ scaling — once this guard regresses,
        accessory enzyme BHs in multi-blend wellness products would silently
        credit the whole product."""
        rows = [
            _bh_row("Wellness Proprietary Blend", qty=1500.0, unit="mg"),
            _bh_row("Digestive Enzyme Blend", qty=50.0, unit="mg"),
            # Display-only enzyme children (would map to enzyme BH if linked)
            _nested_child("Protease"),
            _nested_child("Lipase"),
            _nested_child("Amylase"),
        ]
        normalizer._apply_z1_enzyme_cid_fallback("Wellness Formula", rows)
        # Neither header should be reassigned
        assert rows[0]["canonical_id"] is None, (
            "non-enzyme dominant blend must stay unmapped (G3 fails)"
        )
        assert rows[1]["canonical_id"] is None, (
            "minor accessory enzyme blend must NOT receive cid because it is "
            "not dominant AND product fullName is not explicitly enzyme-primary "
            "— guards against accessory-blend over-crediting at scale"
        )
        assert rows[0]["canonical_source_db"] == "unmapped"
        assert rows[1]["canonical_source_db"] == "unmapped"

    def test_negative_enzyme_kw_but_children_dosed_g2_child_dose_guard(self, normalizer):
        """G2 child-dose guard: product name says 'Digestive Enzymes Ultra' AND
        header is enzyme blend, but children carry usable individual mg doses.
        When children are dosed, score the children — NEVER credit the header.
        Mirrors the same guard logic that protects A.2b."""
        rows = [
            _bh_row("Proprietary Enzyme Blend", qty=400.0, unit="mg"),
            _nested_child("Protease", qty=200.0, unit="mg"),  # DOSED
            _nested_child("Lipase", qty=200.0, unit="mg"),    # DOSED
        ]
        normalizer._apply_z1_enzyme_cid_fallback("Digestive Enzymes Ultra", rows)
        assert rows[0]["canonical_id"] is None, (
            "G2 must abort the fallback when nested children carry usable individual doses"
        )
        assert rows[0]["canonical_source_db"] == "unmapped"


# ===========================================================================
# DOWNSTREAM SCORING — 3 representative cases (not all 7) per Codex
# Verify that once the cleaner assigns cid=digestive_enzymes, the existing
# A.2b anchor path fires correctly. Uses the existing A.2b helper.
# ===========================================================================


class TestZ1DownstreamAnchorScoring:

    @pytest.mark.parametrize("product_name,header_name,qty,unit", [
        ("Digestive Enzymes Ultra", "Proprietary Enzyme Blend", 391.0, "mg"),       # 184411/293957
        ("Extraordinary Enzymes", "Nutrient Absorption Blend", 200.0, "mg"),        # 232243
        ("Nordic Flora Digestive Enzymes", "Nordic Enzyme Blend", 300.0, "mg"),     # 250719
    ])
    def test_post_cleaner_fix_product_scores_via_blend_header_anchor(
        self, scorer, product_name, header_name, qty, unit
    ):
        """After cleaner fix, blend_header_total carries cid=digestive_enzymes.
        The existing A.2b anchor path (shipped commit efbfa604) should fire,
        producing score_basis='blend_header_anchor', verdict in {CAUTION, POOR},
        NEVER SAFE.

        These mimic the post-cleaner-fix enriched state for 3 of the 7 Z1
        candidates (the other 4 follow the same pattern; per Codex review
        we avoid a brittle 7-test slow harness here)."""
        product = _make_blend_header_anchor_eligible(
            header_name=header_name,
            header_std_name=header_name,
            header_canonical_id="digestive_enzymes",
            header_canonical_source_db="ingredient_quality_map",
            header_quantity=qty,
            header_unit=unit,
        )
        # Mirror real product name for traceability
        product["product_name"] = product_name
        product["fullName"] = product_name

        result = scorer.score_product(product)

        assert result["verdict"] != "NOT_SCORED"
        assert result["scoring_status"] == "scored"
        assert result["score_basis"] == "blend_header_anchor"
        assert "SCORED_VIA_BLEND_HEADER_ANCHOR" in result["flags"]
        assert result["verdict"] in {"CAUTION", "POOR"}, (
            f"anchor-scored product must never be SAFE; got {result['verdict']}"
        )
        findings = result["strict_scoring_contract"]["findings"]
        assert "scored_via_blend_header_anchor_path" in findings
