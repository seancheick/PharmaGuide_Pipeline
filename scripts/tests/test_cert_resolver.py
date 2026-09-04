"""Unit tests for scripts/cert_resolver.py.

These tests build their own in-memory CertRegistry fixtures so they do not
depend on the on-disk cert_registry.json snapshot. They lock the
behavioral contract described in docs/plans/SCORING_V4_PROPOSAL.md §10:
conservative thresholds, scope hierarchy, brand-fuzzy matching, overrides
winning over registry, and the audit-only (no scoring effect) shape.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from cert_resolver import (  # noqa: E402
    CertRegistry,
    CertResolution,
    discover_verified_programs,
    normalize_brand,
    normalize_product,
    normalize_program,
    resolve,
    _sku_dose_tokens,
)


# --- Fixtures ---------------------------------------------------------------


def _make_registry(
    records: list[dict] | None = None,
    overrides: list[dict] | None = None,
    recency_status: str = "fresh",
    snapshot_date: str = "2026-05-18",
    snapshot_age_days: int = 0,
) -> CertRegistry:
    """Build an in-memory CertRegistry for tests.

    Default recency = fresh. Use `recency_status="scoring_blocked"` (with an
    explicit `snapshot_age_days` like 1977) to test the recency gate.
    """
    registry = CertRegistry()
    for r in records or []:
        program = r.get("program") or ""
        # auto-populate normalized fields if not present
        r.setdefault("brand_normalized", normalize_brand(r.get("brand", "")))
        r.setdefault("product_normalized", normalize_product(r.get("product", "")))
        # inject recency the same way CertRegistry.load() does
        r.setdefault("_snapshot_date", snapshot_date)
        r.setdefault("_snapshot_age_days", snapshot_age_days)
        r.setdefault("_recency_status", recency_status)
        registry.records_by_program.setdefault(program, []).append(r)
        registry.recency_by_program.setdefault(
            program,
            {
                "snapshot_date": snapshot_date,
                "age_days": snapshot_age_days,
                "status": recency_status,
            },
        )
    for o in overrides or []:
        brand = normalize_brand(o.get("brand", ""))
        product = normalize_product(o.get("product", ""))
        registry.overrides_by_brand_product.setdefault((brand, product), []).append(o)
    return registry


# --- Normalization ----------------------------------------------------------


class TestNormalization:
    def test_normalizers_reuse_exact_registry_values(self) -> None:
        normalize_brand.cache_clear()
        normalize_product.cache_clear()
        normalize_program.cache_clear()

        assert normalize_brand("Performance Cache Brand LLC") == "performance cache"
        assert normalize_product("Performance Cache Product 250 mg Capsules") == "performance cache product"
        assert normalize_program("NSF Certified for Sport") == "NSF Sport"

        for _ in range(3):
            normalize_brand("Performance Cache Brand LLC")
            normalize_product("Performance Cache Product 250 mg Capsules")
            normalize_program("NSF Certified for Sport")

        assert normalize_brand.cache_info().hits == 3
        assert normalize_product.cache_info().hits == 3
        assert normalize_program.cache_info().hits == 3

    def test_normalize_brand_strips_legal_suffixes(self) -> None:
        assert normalize_brand("Thorne Research, Inc.") == "thorne research"
        assert normalize_brand("Garden of Life LLC") == "garden of life"
        assert normalize_brand("Acme Brands Holdings Corporation") == "acme"

    def test_normalize_brand_handles_accents(self) -> None:
        assert normalize_brand("Crème Brûlée Co.") == "creme brulee"

    def test_normalize_product_strips_form_factors(self) -> None:
        assert normalize_product("Magnesium Bisglycinate 200 mg Capsules") == "magnesium bisglycinate"
        # "5000 IU" is a dose-number+unit pair, fully stripped (not just the IU)
        assert normalize_product("Vitamin D3 5000 IU Softgels") == "vitamin d3"
        # Hyphens convert to spaces so "Multi-Vitamin" tokenizes correctly
        assert normalize_product("Multi-Vitamin Elite") == "multi vitamin elite"

    def test_normalize_program_canonicalizes(self) -> None:
        assert normalize_program("NSF Certified for Sport") == "NSF Sport"
        assert normalize_program("NSF for Sport") == "NSF Sport"
        assert normalize_program("USP Verified") == "USP Verified"
        assert normalize_program("USP") == "USP Verified"
        assert normalize_program("Informed Sport") == "Informed Sport"
        assert normalize_program("IFOS 5 Star") == "IFOS"
        assert normalize_program("ConsumerLab Approved") == "ConsumerLab"
        assert normalize_program("CL Approved") == "ConsumerLab"
        assert normalize_program("Non-GMO Project Verified") == "Non-GMO Project"

    def test_normalize_program_passes_through_unknown(self) -> None:
        # Conservative — don't drop unknown programs, just pass through.
        assert normalize_program("Some Other Cert") == "Some Other Cert"


# --- CertResolution -------------------------------------------------------


class TestCertResolution:
    def test_scores_points_only_for_sku_and_product_line(self) -> None:
        assert CertResolution("NSF Sport", "sku").scores_points() is True
        assert CertResolution("NSF Sport", "product_line").scores_points() is True
        assert CertResolution("NSF Sport", "brand_only").scores_points() is False
        assert CertResolution("NSF Sport", "needs_review").scores_points() is False
        assert CertResolution("NSF Sport", "claimed_only").scores_points() is False

    def test_to_dict_strips_none(self) -> None:
        r = CertResolution("NSF Sport", "sku", match_confidence=0.95)
        d = r.to_dict()
        assert d["program"] == "NSF Sport"
        assert d["scope"] == "sku"
        assert d["match_confidence"] == 0.95
        assert "notes" not in d  # None values dropped


# --- Resolver behavior ------------------------------------------------------


class TestResolverHappyPath:
    def test_exact_brand_exact_product_returns_sku(self) -> None:
        registry = _make_registry(
            records=[
                {
                    "program": "NSF Sport",
                    "brand": "Thorne Research, Inc.",
                    "product": "Thorne Research Magnesium Bisglycinate",
                    "record_id": "TEST_001",
                    "verified_at": "2020-12-18",
                }
            ]
        )
        out = resolve("Thorne Research, Inc.", "Magnesium Bisglycinate", ["NSF Certified for Sport"], registry)
        assert len(out) == 1
        assert out[0].scope == "sku"
        assert out[0].match_confidence == 1.0
        assert out[0].record_id == "TEST_001"

    def test_brand_fuzzy_matches_thorne_short_form(self) -> None:
        """Thorne vs Thorne Research must match via token-subset aliasing."""
        registry = _make_registry(
            records=[
                {
                    "program": "NSF Sport",
                    "brand": "Thorne Research, Inc.",
                    "product": "Thorne Research Magnesium Bisglycinate",
                }
            ]
        )
        out = resolve("Thorne", "Magnesium Bisglycinate", ["NSF Certified for Sport"], registry)
        assert len(out) == 1
        assert out[0].scope == "sku"

    def test_brand_match_blocks_short_substring_collision(self) -> None:
        """LTH must not verify CVS Health just because it appears inside
        "Health"; registry cert false positives are worse than missed bonuses."""
        registry = _make_registry(
            records=[
                {
                    "program": "NSF Sport",
                    "brand": "LTH",
                    "product": "GLOW Omega-3 Fish Oil",
                }
            ]
        )
        out = resolve("CVS Health", "Fish Oil 1000 mg", ["NSF Sport"], registry)
        assert len(out) == 1
        assert out[0].scope == "claimed_only"

    def test_brand_match_blocks_partial_word_collision(self) -> None:
        registry = _make_registry(
            records=[
                {
                    "program": "Informed Sport",
                    "brand": "VITAL",
                    "product": "Energy",
                }
            ]
        )
        out = resolve("vitafusion", "B Complex Energy Wild Strawberry", ["Informed Sport"], registry)
        assert len(out) == 1
        assert out[0].scope == "claimed_only"

    def test_brand_match_blocks_shared_generic_token_collision(self) -> None:
        registry = _make_registry(
            records=[
                {
                    "program": "NSF Sport",
                    "brand": "OIAM Performance",
                    "product": "Protein - Vanilla",
                }
            ]
        )
        out = resolve("GNC Pro Performance", "100% Whey Protein Vanilla", ["NSF Sport"], registry)
        assert len(out) == 1
        assert out[0].scope == "claimed_only"


class TestRegistryDiscovery:
    def test_discovers_sku_cert_without_label_claim(self) -> None:
        registry = _make_registry(
            records=[
                {
                    "program": "USP Verified",
                    "brand": "Ritual",
                    "product": "Ritual Essential for Women Multivitamin 18+",
                    "record_id": "USP_RITUAL_EFW",
                    "verified_at": "2026-05-18",
                }
            ]
        )

        out = discover_verified_programs(
            "Ritual",
            "Ritual Essential for Women 18+",
            registry,
        )

        assert len(out) == 1
        assert out[0].program == "USP Verified"
        assert out[0].scope == "sku"
        assert out[0].record_id == "USP_RITUAL_EFW"
        assert "registry_discovered_product_match" in (out[0].notes or "")

    def test_discovery_does_not_emit_brand_only_cert(self) -> None:
        registry = _make_registry(
            records=[
                {
                    "program": "USP Verified",
                    "brand": "Ritual",
                    "product": "Ritual Essential Protein Daily Shake",
                }
            ]
        )

        out = discover_verified_programs("Ritual", "Ritual Synbiotic+", registry)

        assert out == []

    def test_ifos_discovery_requires_marine_product_context(self) -> None:
        registry = _make_registry(
            records=[
                {
                    "program": "IFOS",
                    "brand": "GNC Hong Kong Limited",
                    "product": "GNC EPA& Algae DHA& CoQ-10 3in 1",
                    "record_id": "IFOS_GNC_EPA_DHA_COQ10",
                }
            ]
        )

        plain_coq10 = discover_verified_programs("GNC", "CoQ-10 100 mg", registry)
        b_complex = discover_verified_programs("GNC", "B-Complex 50", registry)

        assert plain_coq10 == []
        assert b_complex == []

    def test_ifos_discovery_keeps_real_marine_product_match(self) -> None:
        registry = _make_registry(
            records=[
                {
                    "program": "IFOS",
                    "brand": "GNC Hong Kong Limited",
                    "product": "Triple Strength Fish Oil Mini",
                    "record_id": "IFOS_GNC_FISH_OIL",
                }
            ]
        )

        out = discover_verified_programs("GNC", "Triple Strength Fish Oil Mini", registry)

        assert len(out) == 1
        assert out[0].scope == "sku"
        assert out[0].record_id == "IFOS_GNC_FISH_OIL"


class TestResolverConservativeThresholds:
    def test_borderline_product_match_lands_needs_review(self) -> None:
        """Thorne Vitamin D vs THORNE RESEARCH MULTI-VITAMIN ELITE — borderline
        token overlap, must NOT auto-classify as sku."""
        registry = _make_registry(
            records=[
                {
                    "program": "NSF Sport",
                    "brand": "Thorne Research, Inc.",
                    "product": "Thorne Research Multi-Vitamin Elite",
                }
            ]
        )
        out = resolve("Thorne", "Vitamin D", ["NSF Certified for Sport"], registry)
        assert len(out) == 1
        assert out[0].scope == "needs_review"

    def test_no_brand_match_returns_claimed_only(self) -> None:
        registry = _make_registry(
            records=[
                {
                    "program": "NSF Sport",
                    "brand": "Thorne Research, Inc.",
                    "product": "Magnesium Bisglycinate",
                }
            ]
        )
        out = resolve("Garden of Life", "Once Daily Prenatal Probiotic", ["NSF Sport"], registry)
        assert len(out) == 1
        assert out[0].scope == "claimed_only"

    def test_brand_match_no_product_match_returns_brand_only(self) -> None:
        registry = _make_registry(
            records=[
                {
                    "program": "NSF Sport",
                    "brand": "Thorne Research, Inc.",
                    "product": "Creatine Monohydrate",
                }
            ]
        )
        # User asks for a Thorne product that ISN'T in the NSF registry
        out = resolve("Thorne", "Niacin Extended Release 500 mg", ["NSF Sport"], registry)
        assert len(out) == 1
        assert out[0].scope == "brand_only"

    def test_dose_variant_conflict_lands_needs_review_not_sku(self) -> None:
        """SKU cert matching must not strip dose differences into a false
        positive. Nature Made CoQ10 200 mg is not the same certified SKU as
        Nature Made CoQ10 100 mg."""
        registry = _make_registry(
            records=[
                {
                    "program": "USP Verified",
                    "brand": "Nature Made",
                    "product": "Nature Made CoQ10 100 Mg Softgels",
                }
            ]
        )
        out = resolve("Nature Made", "CoQ10 200 Mg Softgels", ["USP Verified"], registry)
        assert len(out) == 1
        assert out[0].scope == "needs_review"

    def test_delivery_form_conflict_lands_needs_review_not_sku(self) -> None:
        """A gummies listing must not SKU-verify a softgel claim just because
        form-factor words are normalized away for ingredient matching."""
        registry = _make_registry(
            records=[
                {
                    "program": "USP Verified",
                    "brand": "Nature Made",
                    "product": "Nature Made Vitamin D3 + K2 Gummies",
                }
            ]
        )
        out = resolve("Nature Made", "Vitamin D3 + K2 Softgels", ["USP Verified"], registry)
        assert len(out) == 1
        assert out[0].scope == "needs_review"

    def test_flavor_variant_conflict_lands_needs_review_not_sku(self) -> None:
        """Flavor-specific cert listings should not auto-SKU a product whose
        label omits that flavor. This caught IFOS matching a generic omega-3
        DSLD name to a Nutrasource Lemon Flavor record."""
        registry = _make_registry(
            records=[
                {
                    "program": "IFOS",
                    "brand": "Sports Research",
                    "product": "Omega-3 Fish Oil Lemon Flavor",
                }
            ]
        )
        out = resolve("Sports Research", "Omega-3 1055 mg Fish Oil 1250 mg", ["IFOS"], registry)
        assert len(out) == 1
        assert out[0].scope == "needs_review"

    def test_same_flavor_variant_still_resolves_sku(self) -> None:
        registry = _make_registry(
            records=[
                {
                    "program": "IFOS",
                    "brand": "Sports Research",
                    "product": "Omega-3 Fish Oil Lemon Flavor",
                }
            ]
        )
        out = resolve("Sports Research", "Omega-3 Fish Oil Lemon Flavor", ["IFOS"], registry)
        assert len(out) == 1
        assert out[0].scope == "sku"

    def test_base_registry_product_can_verify_flavored_label(self) -> None:
        """Some registries list product lines rather than every flavor. A base
        certified product can still verify a flavored label; the unsafe case is
        the reverse, where only a flavor-specific registry row exists."""
        registry = _make_registry(
            records=[
                {
                    "program": "Informed Choice",
                    "brand": "Transparent Labs",
                    "product": "Creatine HMB",
                }
            ]
        )
        out = resolve("Transparent Labs", "Creatine HMB Strawberry Lemonade", ["Informed Choice"], registry)
        assert len(out) == 1
        assert out[0].scope == "sku"

    def test_exact_normalized_product_wins_over_superset_token_match(self) -> None:
        """token_set_ratio can score both `10X Stim` and `10X Pump Non-Stim`
        as 100 for a `10X Stim` query. Exact normalized SKU must win."""
        registry = _make_registry(
            records=[
                {"program": "Informed Sport", "brand": "10X ATHLETIC", "product": "10X Pump Non-Stim"},
                {"program": "Informed Sport", "brand": "10X ATHLETIC", "product": "10X Stim"},
            ]
        )
        out = resolve("10X ATHLETIC", "10X Stim", ["Informed Sport"], registry)
        assert len(out) == 1
        assert out[0].scope == "sku"
        assert out[0].matched_product == "10X Stim"

    def test_stim_non_stim_conflict_lands_needs_review_without_exact_match(self) -> None:
        """If only a Non-Stim listing exists, it must not SKU-verify a Stim
        product just because token-set matching sees shared tokens."""
        registry = _make_registry(
            records=[
                {"program": "Informed Sport", "brand": "10X ATHLETIC", "product": "10X Pump Non-Stim"},
            ]
        )
        out = resolve("10X ATHLETIC", "10X Stim", ["Informed Sport"], registry)
        assert len(out) == 1
        assert out[0].scope == "needs_review"

    def test_exact_non_stim_product_still_resolves_sku(self) -> None:
        registry = _make_registry(
            records=[
                {"program": "Informed Sport", "brand": "10X ATHLETIC", "product": "10X Pump Non-Stim"},
            ]
        )
        out = resolve("10X ATHLETIC", "10X Pump Non-Stim", ["Informed Sport"], registry)
        assert len(out) == 1
        assert out[0].scope == "sku"


class TestSkuStrengthIdentity:
    @pytest.mark.parametrize("query,registered", [
        ("Wheybolic Alpha Chocolate Fudge", "Wheybolic Chocolate Fudge"),
        ("Wheybolic Ripped Chocolate Fudge", "Wheybolic Chocolate Fudge"),
        ("Amplified 100% Whey Protein Vanilla", "100% Whey"),
        ("Burp-less Fish Oil 1000 mg Softgels", "Fish Oil 1000 mg Softgels"),
        ("Super Strength Omega-3 EPA Fish Oil", "Super Fish Oil"),
        ("Calcium Plus Magnesium", "Calcium Plus"),
        ("Daily Probiotics Immune", "Daily Probiotics"),
    ])
    def test_query_named_addition_cannot_inherit_generic_sku(self, query, registered):
        registry = _make_registry(records=[{
            "program": "NSF Certified", "brand": "Example", "product": registered, "scope": "sku",
        }])

        assert not resolve("Example", query, ["NSF Certified"], registry)[0].scores_points()

    @pytest.mark.parametrize("scope", ["sku", "product_line"])
    def test_explicit_registry_line_authority_is_not_inferred_from_generic_sku(self, scope):
        registry = _make_registry(records=[{
            "program": "NSF Certified", "brand": "Example", "product": "Daily Probiotics",
            "scope": scope, "record_id": "EXPLICIT_LINE_FIXTURE",
        }])
        result = resolve("Example", "Daily Probiotics Immune", ["NSF Certified"], registry)[0]

        if scope == "product_line":
            assert result.scope == "product_line"
            assert result.scores_points()
        else:
            assert not result.scores_points()

    def test_query_sub_brand_cannot_hide_a_named_product_addition(self):
        registry = _make_registry(records=[{
            "program": "NSF Certified", "brand": "Example", "product": "Daily Probiotics", "scope": "sku",
        }])

        assert not resolve("Example Immune", "Daily Probiotics Immune",
                           ["NSF Certified"], registry)[0].scores_points()

    @pytest.mark.parametrize("strength", ["50B", "50b", "50 billion", "50 billion CFU", "50billionCFU"])
    def test_equivalent_billion_spellings_keep_strength_identity(self, strength):
        registry = _make_registry(records=[{
            "program": "NSF Certified", "brand": "Example",
            "product": "Immune Probiotics 50B Capsules",
        }])

        result = resolve("Example", f"Immune Probiotics {strength} Capsules",
                         ["NSF Certified"], registry)[0]

        assert result.scope == "sku"
        assert result.scores_points()
        assert _sku_dose_tokens(strength) == _sku_dose_tokens("50 billion CFU")

    @pytest.mark.parametrize("strength", ["100 Billion", "30 Billion", "100B", "30billionCFU"])
    def test_different_billion_strength_cannot_inherit_credit(self, strength):
        registry = _make_registry(records=[{
            "program": "NSF Certified", "brand": "Garden of Life",
            "product": "Dr. Formulated Probiotics Immune 50B",
        }])
        product = f"Probiotics {strength}"

        result = resolve("Garden of Life Dr. Formulated", product,
                         ["NSF Certified"], registry)[0]

        assert not result.scores_points()
        assert discover_verified_programs("Garden of Life Dr. Formulated", product, registry) == []

    @pytest.mark.parametrize(
        ("product", "certified_product"),
        [
            ("Probiotics 50B", "Immune Probiotics 50B"),
            ("Probiotics 50B", "Probiotics Digestive 50B"),
            ("Probiotics", "Immune Probiotics"),
            ("Daily Probiotics 50B", "Daily Immune Probiotics 50B"),
            ("Example Probiotics", "Example Immune Probiotics"),
            ("Daily Probiotics", "Daily Probiotics 50B"),
            ("Immune Probiotics 50 billion AFU", "Immune Probiotics 50 billion CFU"),
            ("Immune Probiotics 50 billion AFU", "Immune Probiotics 50B"),
        ],
    )
    def test_incomplete_or_conflicting_identity_cannot_inherit_credit(self, product, certified_product):
        registry = _make_registry(records=[{
            "program": "NSF Certified", "brand": "Example", "product": certified_product,
        }])

        assert not resolve("Example", product, ["NSF Certified"], registry)[0].scores_points()
        assert discover_verified_programs("Example", product, registry) == []

    @pytest.mark.parametrize("reverse", [False, True])
    def test_ambiguous_variants_do_not_pick_a_registry_row_by_order(self, reverse):
        records = [{
            "program": "NSF Certified", "brand": "Example", "product": product,
            "record_id": f"TEST_{index}",
        } for index, product in enumerate([
            "Daily Probiotics for Women Capsules", "Daily Probiotics for Men and Women Capsules",
        ])]
        registry = _make_registry(records=list(reversed(records)) if reverse else records)

        result = resolve("Example", "Daily Probiotics for Women Capsules", ["NSF Certified"], registry)[0]

        assert result.scope == "needs_review"
        assert not result.scores_points()
        assert "ambiguous" in (result.notes or "")
        assert result.record_id == "TEST_0"
        assert result.matched_product == records[0]["product"]
        assert "TEST_1" in result.notes

    @pytest.mark.parametrize(
        ("product", "expected"),
        [("Vitamin B12 1000 mcg", {"1000mcg"}),
         ("Vitamin B1 50 mg", {"50mg"}),
         ("Vitamin D3 5000 IU", {"5000iu"}),
         ("B-Complex 50", set())],
    )
    def test_billion_shorthand_does_not_consume_vitamin_identity(self, product, expected):
        assert _sku_dose_tokens(product) == expected

    @pytest.mark.parametrize("product", ["Vitamin B12 1000 mcg", "Vitamin D3 5000 IU", "Probiotics 50B"])
    def test_exact_product_with_strength_keeps_credit(self, product):
        registry = _make_registry(records=[{
            "program": "NSF Certified", "brand": "Example", "product": product,
        }])

        assert resolve("Example", product, ["NSF Certified"], registry)[0].scores_points()

    def test_reviewed_product_line_override_keeps_explicit_authority(self):
        registry = _make_registry(overrides=[{
            "brand": "Example", "product": "Probiotics 50 Billion",
            "program": "NSF Certified", "status": "verified", "scope": "product_line",
            "matched_product": "Daily Probiotics", "record_id": "REVIEWED_LINE",
        }])

        result = resolve("Example", "Probiotics 50 Billion", ["NSF Certified"], registry)[0]

        assert result.scope == "product_line"
        assert result.record_id == "REVIEWED_LINE"
        assert result.matched_product == "Daily Probiotics"
        assert result.scores_points()

    @pytest.mark.parametrize("query,registered", [
        ("D3 5000 IU", "Vitamin D3 5000 IU"),
        ("B12 1000 mcg", "Vitamin B12 1000 mcg"),
    ])
    def test_optional_vitamin_descriptor_is_not_a_variant(self, query, registered):
        registry = _make_registry(records=[{
            "program": "USP Verified", "brand": "Example", "product": registered,
        }])
        assert resolve("Example", query, ["USP Verified"], registry)[0].scores_points()

    @pytest.mark.parametrize(
        ("dsld_id", "product", "expected_scope"),
        [("326762", "Probiotics 100 Billion", "needs_review"),
         ("297668", "Probiotics 30 Billion", "needs_review"),
         ("326765", "Probiotics Immune 50 Billion", "sku")],
    )
    def test_real_garden_of_life_registry_keeps_credit_with_correct_strength(self, dsld_id, product, expected_scope):
        registry = _make_registry(records=[{
            "program": "NSF Certified", "brand": "Garden of Life",
            "product": "Dr. Formulated Probiotics Immune 50B", "record_id": "IMMUNE50_FIXTURE",
        }])

        result = resolve("Garden of Life Dr. Formulated", product,
                         ["NSF Certified"], registry, dsld_id=dsld_id)[0]

        assert result.scope == expected_scope
        if expected_scope == "sku":
            assert result.record_id == "IMMUNE50_FIXTURE"
        else:
            assert not result.scores_points()
            assert not any(match.program == "NSF Certified" for match in discover_verified_programs(
                "Garden of Life Dr. Formulated", product, registry, dsld_id=dsld_id
            ))


class TestSkuFormContext:
    @pytest.mark.parametrize("unit", ["Gummie(s)", "Gummy(ies)", "90 Gummy(ies)"])
    def test_printed_gummy_plural_unit_supplies_explicit_form(self, unit):
        registry = _make_registry(records=[{
            "program": "NSF Certified", "brand": "Example", "product": "Daily Probiotic",
            "product_form": "Gummy",
        }])
        result = resolve("Example", "Daily Probiotic", ["NSF Certified"], registry,
                         label_context={"netContents": [{"unit": unit}]})[0]

        assert result.scope == "sku"

    @pytest.mark.parametrize("unit", ["Take 2 Gummy(ies) Daily", "Immune Gummy(ies)", "Capsule(ies)"])
    def test_gummy_plural_adapter_does_not_admit_instructions_or_other_descriptors(self, unit):
        registry = _make_registry(records=[{
            "program": "NSF Certified", "brand": "Example", "product": "Daily Probiotic",
            "product_form": "Gummy",
        }])
        assert not resolve("Example", "Daily Probiotic", ["NSF Certified"], registry,
                           label_context={"netContents": [{"unit": unit}]})[0].scores_points()

    @pytest.mark.parametrize("brand,query,registry_brand,registered,form", [
        ("GNC TriFlex", "TriFlex", "GNC", "GNC Triflex", "tablet"),
        ("Garden of Life", "Kids Multivitamin Powder", "Garden of Life, LLC", "Garden of Life Kids Multivitamin Powder", "powder"),
        ("Kirkland Signature", "Adult Multivitamin Gummies", "Kirkland Signature", "Kirkland Signature Adult Multivitamin Gummies", "gummy"),
        ("GNC", "Zinc 50 mg", "GNC", "GNC Zinc 50 mg", "tablet"),
    ])
    def test_exact_literal_name_survives_removed_core_tokens(self, brand, query, registry_brand, registered, form):
        registry = _make_registry(records=[{
            "program": "NSF Certified", "brand": registry_brand, "product": registered,
        }])
        result = resolve(brand, query, ["NSF Certified"], registry,
                         label_context={"form_factor_canonical": form,
                                        "netContents": [{"unit": f"Vegetarian {form}(s)"}]})[0]

        assert result.scope == "sku"

    @pytest.mark.parametrize("query,registered", [
        ("Kids", "Kids Multivitamin"),
        ("Adult Multivitamin Gummies", "Adult Multivitamin Zero Sugar Gummies"),
        ("Probiotics", "Immune Probiotics"),
        ("Zinc 50 mg", "Zinc 100 mg"),
        ("Kids Multivitamin Gummies", "Kids Multivitamin Tablets"),
        ("Kids Multivitamin Gummies", "Adult Multivitamin Gummies"),
        ("", "Multivitamin"),
        ("Example", "Example"),
    ])
    def test_literal_name_guard_never_treats_empty_or_subset_names_as_equal(self, query, registered):
        registry = _make_registry(records=[{
            "program": "NSF Certified", "brand": "Example", "product": registered,
        }])

        assert not resolve("Example", query, ["NSF Certified"], registry)[0].scores_points()

    @pytest.mark.parametrize("material", ["Vegetarian", "Vegan"])
    def test_source_form_detail_does_not_dilute_matching_registry_brand_prefix(self, material):
        registry = _make_registry(records=[{
            "program": "NSF Certified", "brand": "Garden of Life",
            "product": "Dr. Formulated Probiotics Immune 50B", "product_form": "Capsule",
            "record_id": "IMMUNE50_FIXTURE",
        }])
        result = resolve(
            "Garden of Life Dr. Formulated", "Probiotics Immune 50 Billion",
            ["NSF Certified"], registry,
            label_context={"form_factor_canonical": "capsule",
                           "netContents": [{"unit": f"{material} Capsule(s)"}]},
        )[0]

        assert result.scope == "sku"
        assert result.record_id == "IMMUNE50_FIXTURE"

    @pytest.mark.parametrize("query,form", [
        ("Probiotics 100 Billion", "capsule"),
        ("Probiotics Immune 100 Billion", "capsule"),
        ("Probiotics 50 Billion", "capsule"),
        ("Probiotics Immune 50 Billion", "tablet"),
    ])
    def test_identity_ranking_cannot_bypass_variant_guards(self, query, form):
        registry = _make_registry(records=[{
            "program": "NSF Certified", "brand": "Garden of Life",
            "product": "Dr. Formulated Probiotics Immune 50B", "product_form": "Capsule",
        }])
        result = resolve(
            "Garden of Life Dr. Formulated", query, ["NSF Certified"], registry,
            label_context={"form_factor_canonical": form,
                           "netContents": [{"unit": f"Vegetarian {form}(s)"}]},
        )[0]

        assert not result.scores_points()

    @pytest.mark.parametrize("registered_form", ["Caplet", "Caplets"])
    def test_source_caplet_form_matches_singular_and_plural_registry_form(self, registered_form):
        registry = _make_registry(records=[{
            "program": "USP Verified", "brand": "Nature Made",
            "product": f"Nature Made Vitamin C 500 mg with Rose Hips {registered_form}",
        }])
        result = resolve(
            "Nature Made", "Vitamin C 500 mg With Rose Hips", ["USP Verified"], registry,
            label_context={"form_factor_canonical": "caplet",
                           "netContents": [{"unit": "Caplet(s)"}]},
        )[0]

        assert result.scope == "sku"

    def test_caplet_identity_normalization_does_not_equate_tablet_form(self):
        registry = _make_registry(records=[{
            "program": "USP Verified", "brand": "Nature Made",
            "product": "Nature Made Vitamin C 500 mg with Rose Hips Caplets",
        }])
        assert not resolve(
            "Nature Made", "Vitamin C 500 mg With Rose Hips", ["USP Verified"], registry,
            label_context={"form_factor_canonical": "tablet"},
        )[0].scores_points()

    @pytest.mark.parametrize("form", ["Capsules", "Tablets", "Softgels", "Gummies", "Powder", "Liquid"])
    def test_missing_registry_form_needs_review(self, form):
        registry = _make_registry(records=[{
            "program": "USP Verified", "brand": "Example", "product": f"Vitamin D3 5000 IU {form}",
        }])

        result = resolve("Example", "D3 5000 IU", ["USP Verified"], registry)[0]

        assert result.scope == "needs_review"
        assert not result.scores_points()

    def test_structured_registry_form_also_requires_product_form_evidence(self):
        registry = _make_registry(records=[{
            "program": "USP Verified", "brand": "Example", "product": "Vitamin D3 5000 IU",
            "product_form": "Capsule",
        }])

        assert not resolve("Example", "D3 5000 IU", ["USP Verified"], registry)[0].scores_points()

    @pytest.mark.parametrize("form_field", ["form_factor_canonical", "form_factor"])
    def test_explicit_canonical_form_can_complete_registry_identity(self, form_field):
        registry = _make_registry(records=[{
            "program": "USP Verified", "brand": "Example", "product": "Vitamin D3 5000 IU Capsules",
        }])

        result = resolve("Example", "D3 5000 IU", ["USP Verified"], registry,
                         label_context={form_field: "capsule"})[0]

        assert result.scores_points()

    def test_conflicting_title_and_canonical_form_cannot_match_either_variant(self):
        registry = _make_registry(records=[{
            "program": "USP Verified", "brand": "Example", "product": "Vitamin D3 5000 IU Capsules",
        }])

        assert not resolve("Example", "D3 5000 IU Softgels", ["USP Verified"], registry,
                           label_context={"form_factor_canonical": "capsule"})[0].scores_points()

    def test_form_descriptor_context_does_not_change_reviewed_override_key_or_id(self):
        registry = _make_registry(overrides=[{
            "brand": "Example", "product": "Daily Probiotic", "program": "USP Verified",
            "scope": "product_line", "status": "verified", "dsld_id": "reviewed-id",
            "record_id": "REVIEWED_LINE",
        }])
        context = {"form_factor_canonical": "capsule", "netContents": [{"unit": "Vegetarian Capsule(s)"}]}

        result = resolve("Example", "Daily Probiotic", ["USP Verified"], registry,
                         dsld_id="reviewed-id", label_context=context)[0]
        wrong_id = resolve("Example", "Daily Probiotic", ["USP Verified"], registry,
                           dsld_id="different-id", label_context=context)[0]

        assert result.record_id == "REVIEWED_LINE"
        assert result.scope == "product_line"
        assert result.scores_points()
        assert not wrong_id.scores_points()


class TestResolverScoring:
    def test_no_scoring_for_brand_only_or_claimed_only(self) -> None:
        registry = _make_registry(
            records=[
                {
                    "program": "NSF Sport",
                    "brand": "Thorne Research, Inc.",
                    "product": "Some Other Product",
                }
            ]
        )
        # Thorne brand exists, this specific product doesn't
        out = resolve("Thorne", "Magnesium Citrate 600 mg", ["NSF Sport"], registry)
        assert len(out) == 1
        assert out[0].scores_points() is False  # brand_only → no B4a

    def test_no_scoring_for_no_brand_match(self) -> None:
        registry = _make_registry(records=[])
        out = resolve("Acme", "Something", ["NSF Sport"], registry)
        assert out[0].scope == "claimed_only"
        assert out[0].scores_points() is False


class TestOverrides:
    def test_verified_override_wins_over_registry_miss(self) -> None:
        registry = _make_registry(
            records=[],
            overrides=[
                {
                    "brand": "Transparent Labs",
                    "product": "KSM-66",
                    "program": "Informed Sport",
                    "status": "verified",
                    "scope": "sku",
                    "record_id": "OVR_001",
                }
            ],
        )
        out = resolve("Transparent Labs", "KSM-66", ["Informed Sport"], registry)
        assert len(out) == 1
        assert out[0].scope == "sku"
        assert out[0].record_id == "OVR_001"
        assert out[0].notes == "curated override"

    def test_pending_review_override_returns_needs_review(self) -> None:
        registry = _make_registry(
            overrides=[
                {
                    "brand": "Some Brand",
                    "product": "Some Product",
                    "program": "NSF Sport",
                    "status": "pending_review",
                    "scope": "sku",
                    "record_id": "OVR_002",
                }
            ],
        )
        out = resolve("Some Brand", "Some Product", ["NSF Sport"], registry)
        assert out[0].scope == "needs_review"
        assert out[0].record_id == "OVR_002"

    def test_rejected_override_downgrades_to_claimed_only(self) -> None:
        registry = _make_registry(
            records=[
                {
                    # Even if registry says match, override says no
                    "program": "NSF Sport",
                    "brand": "Disputed Brand",
                    "product": "Disputed Product",
                }
            ],
            overrides=[
                {
                    "brand": "Disputed Brand",
                    "product": "Disputed Product",
                    "program": "NSF Sport",
                    "status": "rejected",
                    "reason": "NSF confirmed not certified for this SKU",
                }
            ],
        )
        out = resolve("Disputed Brand", "Disputed Product", ["NSF Sport"], registry)
        assert out[0].scope == "claimed_only"
        assert "rejected" in (out[0].notes or "")

    def test_dsld_specific_override_applies_only_to_matching_dsld_id(self) -> None:
        registry = _make_registry(
            overrides=[
                {
                    "brand": "Nature Made",
                    "product": "Vitamin D3 2000 IU",
                    "program": "USP Verified",
                    "status": "verified",
                    "scope": "product_line",
                    "record_id": "USP_D3_SOFTGEL",
                    "dsld_id": "12154",
                }
            ],
        )

        matching = resolve(
            "Nature Made",
            "Vitamin D3 2000 IU",
            ["USP Verified"],
            registry,
            dsld_id="12154",
        )
        wrong_id = resolve(
            "Nature Made",
            "Vitamin D3 2000 IU",
            ["USP Verified"],
            registry,
            dsld_id="274365",
        )
        no_id = resolve("Nature Made", "Vitamin D3 2000 IU", ["USP Verified"], registry)

        assert matching[0].scope == "product_line"
        assert matching[0].record_id == "USP_D3_SOFTGEL"
        assert wrong_id[0].scope == "claimed_only"
        assert no_id[0].scope == "claimed_only"


class TestMultipleClaimedPrograms:
    def test_each_program_resolved_independently(self) -> None:
        """Thorne Mg with 3 claimed programs: NSF Sport (SKU), NSF Certified
        (claimed_only — separate registry), USP (claimed_only — no registry)."""
        registry = _make_registry(
            records=[
                {
                    "program": "NSF Sport",
                    "brand": "Thorne Research, Inc.",
                    "product": "Thorne Research Magnesium Bisglycinate",
                }
                # No NSF Certified or USP records — those resolve to claimed_only
            ]
        )
        out = resolve(
            "Thorne",
            "Magnesium Bisglycinate",
            ["NSF Certified for Sport", "NSF Certified", "USP Verified"],
            registry,
        )
        assert len(out) == 3
        scope_map = {r.program: r.scope for r in out}
        assert scope_map["NSF Sport"] == "sku"
        assert scope_map["NSF Certified"] == "claimed_only"
        assert scope_map["USP Verified"] == "claimed_only"


class TestEmptyInputs:
    def test_no_claimed_programs_returns_empty(self) -> None:
        registry = _make_registry()
        out = resolve("Brand", "Product", [], registry)
        assert out == []

    def test_empty_program_string_skipped(self) -> None:
        registry = _make_registry()
        out = resolve("Brand", "Product", [""], registry)
        assert out == []


# --- Recency gate ----------------------------------------------------------


class TestRecencyGate:
    """The recency gate is the safety net Codex flagged: stale snapshots can
    still match (so audits remain useful), but they must not grant scoring
    points. CertResolution.scores_points() returns False whenever the snapshot
    is scoring_blocked, regardless of scope."""

    def test_fresh_snapshot_scores_points(self) -> None:
        registry = _make_registry(
            records=[
                {
                    "program": "NSF Sport",
                    "brand": "Thorne Research, Inc.",
                    "product": "Thorne Research Magnesium Bisglycinate",
                }
            ],
            recency_status="fresh",
            snapshot_age_days=5,
        )
        out = resolve("Thorne", "Magnesium Bisglycinate", ["NSF Certified for Sport"], registry)
        assert out[0].scope == "sku"
        assert out[0].recency_status == "fresh"
        assert out[0].scoring_blocked_reason is None
        assert out[0].scores_points() is True

    def test_warn_snapshot_still_scores(self) -> None:
        """Snapshot 90-180d old is `warn` — still scores but reviewer should refresh."""
        registry = _make_registry(
            records=[
                {
                    "program": "NSF Sport",
                    "brand": "Thorne Research, Inc.",
                    "product": "Thorne Research Magnesium Bisglycinate",
                }
            ],
            recency_status="warn",
            snapshot_age_days=120,
        )
        out = resolve("Thorne", "Magnesium Bisglycinate", ["NSF Certified for Sport"], registry)
        assert out[0].scope == "sku"
        assert out[0].recency_status == "warn"
        assert out[0].scoring_blocked_reason is None
        assert out[0].scores_points() is True

    def test_stale_snapshot_matches_but_blocks_scoring(self) -> None:
        """Snapshot > 180 days = scoring_blocked. Match still works (audit-useful)
        but scores_points() must return False."""
        registry = _make_registry(
            records=[
                {
                    "program": "NSF Sport",
                    "brand": "Thorne Research, Inc.",
                    "product": "Thorne Research Magnesium Bisglycinate",
                }
            ],
            recency_status="scoring_blocked",
            snapshot_age_days=1977,  # 2020 PDF case
        )
        out = resolve("Thorne", "Magnesium Bisglycinate", ["NSF Certified for Sport"], registry)
        assert out[0].scope == "sku"  # match still works for audit
        assert out[0].recency_status == "scoring_blocked"
        assert out[0].scoring_blocked_reason is not None
        assert "1977d" in out[0].scoring_blocked_reason
        assert out[0].scores_points() is False  # but no points granted

    def test_unknown_recency_blocks_scoring(self) -> None:
        """Missing snapshot_date → unknown → conservative scoring_blocked."""
        registry = _make_registry(
            records=[
                {
                    "program": "NSF Sport",
                    "brand": "Thorne Research, Inc.",
                    "product": "Thorne Research Magnesium Bisglycinate",
                }
            ],
            recency_status="unknown",
            snapshot_date=None,
            snapshot_age_days=None,
        )
        out = resolve("Thorne", "Magnesium Bisglycinate", ["NSF Certified for Sport"], registry)
        assert out[0].scope == "sku"
        assert out[0].scoring_blocked_reason is not None
        assert out[0].scores_points() is False


# --- Multi-source registry --------------------------------------------------


class TestMultiSourceRegistry:
    """Verify that records from multiple program registries (NSF Sport +
    NSF/ANSI 173) can co-exist and resolve independently."""

    def test_product_matches_in_two_independent_programs(self) -> None:
        registry = _make_registry(
            records=[
                {
                    "program": "NSF Sport",
                    "brand": "Thorne Research, Inc.",
                    "product": "Thorne Research Magnesium Bisglycinate",
                    "record_id": "NSF_SPORT_TEST",
                },
                {
                    "program": "NSF Certified",
                    "brand": "Thorne, Inc.",
                    "product": "Thorne Magnesium Bisglycinate",
                    "record_id": "NSF_173_TEST",
                },
            ]
        )
        out = resolve(
            "Thorne",
            "Magnesium Bisglycinate",
            ["NSF Certified for Sport", "NSF Certified"],
            registry,
        )
        scope_map = {r.program: r.scope for r in out}
        assert scope_map["NSF Sport"] == "sku"
        assert scope_map["NSF Certified"] == "sku"
        # Each resolution carries its own record_id
        ids = {r.record_id for r in out if r.record_id}
        assert ids == {"NSF_SPORT_TEST", "NSF_173_TEST"}

    def test_only_loaded_programs_can_resolve_to_sku(self) -> None:
        """USP Verified claimed but no USP registry → claimed_only.
        Must NOT cross-match to NSF Sport records (different program)."""
        registry = _make_registry(
            records=[
                {
                    "program": "NSF Sport",
                    "brand": "Thorne Research, Inc.",
                    "product": "Thorne Research Magnesium Bisglycinate",
                }
            ]
        )
        out = resolve("Thorne", "Magnesium Bisglycinate", ["USP Verified"], registry)
        assert len(out) == 1
        assert out[0].program == "USP Verified"
        assert out[0].scope == "claimed_only"  # not found in any USP registry
        assert out[0].scores_points() is False
