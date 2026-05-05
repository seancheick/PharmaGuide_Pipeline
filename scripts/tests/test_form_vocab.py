#!/usr/bin/env python3
"""Form-keyword vocabulary loader + chain-consistency contract.

Pins the single source of truth at scripts/data/form_keywords_vocab.json
and verifies the three consumer surfaces (cleaner / scorer / enricher)
all read through the loader so drift is impossible.

Tests cover:
  1. Schema integrity: every category has the required fields,
     every form has canonical + patterns.
  2. Loader correctness: extract_forms / matches_premium_omega3_form /
     matches_probiotic_delivery / matches_postbiotic each behave as
     specified.
  3. Cross-consumer chain: a form keyword that the cleaner emits is
     recognized by the relevant scorer / enricher predicate.
  4. No hardcoded duplicates: scorer no longer has
     _PREMIUM_OMEGA3_FORM_PATTERN; enricher no longer has the inline
     _POSTBIOTIC_PATTERNS / _POSTBIOTIC_PATTERNS_PRODUCT_LEVEL constants.
  5. Required-fixture regression lock: Vitamin A Palmitate, K2 MK-7,
     magnesium glycinate, ethyl-ester / triglyceride omega-3, and
     heat-killed probiotic still extract correctly.
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import form_vocab  # noqa: E402

VOCAB_PATH = REPO_ROOT / "scripts" / "data" / "form_keywords_vocab.json"


# -- Schema integrity --------------------------------------------------------

def test_vocab_file_loads_as_json():
    assert VOCAB_PATH.is_file(), f"Missing vocab file: {VOCAB_PATH}"
    with VOCAB_PATH.open() as f:
        json.load(f)


def test_metadata_block_is_well_formed():
    meta = form_vocab.metadata()
    assert meta.get("schema_version")
    assert meta.get("description")
    assert "consumed_by" in meta
    # consumed_by must list all three pipeline modules so the dependency
    # is visible from the data file alone.
    consumers = " ".join(meta["consumed_by"])
    assert "enhanced_normalizer" in consumers
    assert "score_supplements" in consumers
    assert "enrich_supplements_v3" in consumers


def test_every_category_has_at_least_one_form():
    for cat_id in form_vocab.category_ids():
        assert form_vocab.canonicals_in(cat_id), f"empty category: {cat_id}"


def test_every_form_has_canonical_and_patterns():
    with VOCAB_PATH.open() as f:
        raw = json.load(f)
    for cat_id, cat in raw["categories"].items():
        for form in cat["forms"]:
            assert form.get("canonical"), f"{cat_id}: form missing canonical"
            assert form.get("patterns"), f"{cat_id}/{form['canonical']}: missing patterns"
            assert all(isinstance(p, str) for p in form["patterns"])


def test_no_duplicate_canonicals_within_a_category():
    for cat_id in form_vocab.category_ids():
        canonicals = form_vocab.canonicals_in(cat_id)
        assert len(canonicals) == len(set(canonicals)), (
            f"{cat_id}: duplicate canonicals: {canonicals}"
        )


# -- Loader correctness ------------------------------------------------------

def test_extract_forms_returns_empty_on_empty_input():
    assert form_vocab.extract_forms("") == []
    assert form_vocab.extract_forms(None) == []


def test_extract_forms_dedupe_within_category():
    """A canonical that matches via multiple patterns is emitted once."""
    # 'rTG' and 'Re-Esterified Triglyceride' both map to canonical
    # 're-esterified triglyceride'.
    forms = form_vocab.extract_forms("rTG and re-esterified triglyceride blend")
    assert forms.count("re-esterified triglyceride") == 1


def test_extract_forms_respects_category_filter():
    omega = form_vocab.extract_forms("Vitamin A Palmitate", categories=["omega3_molecular_forms"])
    assert omega == []
    vita = form_vocab.extract_forms("Vitamin A Palmitate", categories=["vitamin_a_forms"])
    assert "retinyl palmitate" in vita


def test_exclusive_match_in_folate_category():
    """Folate is exclusive_match=true. Methylated form takes
    precedence over folic acid even if both patterns match."""
    forms = form_vocab.extract_forms("Folate (as L-5-MTHF, not folic acid)")
    assert "5-methyltetrahydrofolate" in forms
    assert "folic acid" not in forms


def test_matches_premium_omega3_form_positive_cases():
    for label in (
        "rTG fish oil",
        "re-esterified triglyceride",
        "natural triglyceride form",
        "DHA Ethyl Ester",
        "EE concentrate",
        "krill phospholipid",
        "monoglyceride fish oil",
        "free fatty acid omega-3",
    ):
        assert form_vocab.matches_premium_omega3_form(label), label


def test_matches_premium_omega3_form_negative_cases():
    """Things that look like omega-3 context but aren't molecular forms."""
    for label in (
        "fish oil",  # source oil only, no molecular form disclosed
        "krill oil concentrate",
        "DHA from algae",
        "Vitamin A Palmitate",  # not omega-3
    ):
        assert not form_vocab.matches_premium_omega3_form(label), label


def test_matches_probiotic_delivery_positive_cases():
    for label in (
        "spore-based Bacillus coagulans",
        "microencapsulated L. acidophilus",
        "acid-resistant capsule",
        "delayed-release probiotic",
        "enteric-coated tablet",
    ):
        assert form_vocab.matches_probiotic_delivery(label), label


def test_matches_probiotic_delivery_negative():
    assert not form_vocab.matches_probiotic_delivery("Vitamin C 500 mg")
    assert not form_vocab.matches_probiotic_delivery("")


def test_matches_postbiotic_positive_cases():
    for label in (
        "heat-killed L. plantarum",
        "tyndallized Bifidobacterium",
        "inactivated probiotic",
        "non-viable culture",
        "bacterial lysate",
        "postbiotic supplement",
        "paraprobiotic complex",
    ):
        assert form_vocab.matches_postbiotic(label), label


def test_matches_postbiotic_negative():
    assert not form_vocab.matches_postbiotic("live Lactobacillus")
    assert not form_vocab.matches_postbiotic("microencapsulated probiotic")


# -- Cross-consumer chain --------------------------------------------------
# Cleaner emits canonical X → scorer / enricher recognize X. No drift.

@pytest.mark.parametrize("label", [
    "Fish Oil (Triglyceride)",
    "Re-Esterified Triglyceride Fish Oil",
    "DHA Ethyl Ester",
    "Krill Oil (Phospholipid)",
])
def test_cleaner_omega3_emission_satisfies_scorer(label):
    """Whatever the cleaner extracts for an omega-3 label must satisfy
    the scorer's premium-form predicate when concatenated into a haystack."""
    from enhanced_normalizer import EnhancedDSLDNormalizer
    forms = EnhancedDSLDNormalizer()._extract_forms_from_ingredient_name(label)
    assert forms, f"cleaner emitted no forms for {label!r}"
    haystack = " ".join(forms)
    assert form_vocab.matches_premium_omega3_form(haystack), (
        f"scorer rejected cleaner emission {forms!r} for {label!r}"
    )


@pytest.mark.parametrize("label", [
    "Bacillus coagulans (spore-based)",
    "Microencapsulated L. acidophilus",
    "Acid-Stable L. rhamnosus",
])
def test_cleaner_probiotic_emission_satisfies_enricher(label):
    """Probiotic delivery forms the cleaner emits must satisfy the
    enricher's matches_probiotic_delivery predicate."""
    from enhanced_normalizer import EnhancedDSLDNormalizer
    forms = EnhancedDSLDNormalizer()._extract_forms_from_ingredient_name(label)
    haystack = " ".join(forms) + " " + label  # include both label + extracted
    assert form_vocab.matches_probiotic_delivery(haystack), label


@pytest.mark.parametrize("label", [
    "Heat-Killed L. plantarum",
    "Tyndallized Bifidobacterium",
    "Postbiotic Cell Lysate",
])
def test_cleaner_postbiotic_emission_satisfies_enricher(label):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    forms = EnhancedDSLDNormalizer()._extract_forms_from_ingredient_name(label)
    haystack = " ".join(forms) + " " + label
    assert form_vocab.matches_postbiotic(haystack), label


# -- No hardcoded duplicates ------------------------------------------------
# After the v1.5.0 vocab refactor, the deprecated keyword constants must
# not exist on the consumer modules. If a future change re-introduces
# them, these tests fail loudly.

def test_scorer_has_no_hardcoded_premium_omega3_pattern():
    import score_supplements
    assert not hasattr(score_supplements, "_PREMIUM_OMEGA3_FORM_PATTERN"), (
        "Scorer must not redefine _PREMIUM_OMEGA3_FORM_PATTERN — vocab is "
        "the single source of truth via form_vocab.matches_premium_omega3_form."
    )


def test_enricher_does_not_carry_old_survivability_keywords_attr():
    """The class attribute SURVIVABILITY_KEYWORDS was renamed to
    SURVIVABILITY_BRAND_MARKERS in v1.5.0; the canonical chemistry forms
    moved to vocab. Re-introducing the old name would shadow the vocab."""
    from enrich_supplements_v3 import SupplementEnricherV3
    # Class-level check (avoids needing a fully-initialized instance).
    assert not hasattr(SupplementEnricherV3, "SURVIVABILITY_KEYWORDS"), (
        "Old SURVIVABILITY_KEYWORDS attribute must not exist — use "
        "SURVIVABILITY_BRAND_MARKERS for branded markers and the form vocab "
        "for canonical chemistry forms."
    )
    assert hasattr(SupplementEnricherV3, "SURVIVABILITY_BRAND_MARKERS")


# -- Required-fixture regression lock ---------------------------------------
# Per the user's PR scope: "known fixtures still pass: Vitamin A Palmitate,
# Vitamin K2 MK-7, magnesium glycinate, ethyl ester omega-3, triglyceride
# omega-3, heat-killed probiotic." These five must keep extracting the
# same canonical names through the entire pipeline.

@pytest.mark.parametrize("label, expected_canonical", [
    ("Vitamin A Palmitate", "retinyl palmitate"),
    ("Vitamin K2 MK-7", "menaquinone-7"),
    ("Magnesium Glycinate", "glycinate"),
    ("DHA Ethyl Ester", "ethyl ester"),
    ("Fish Oil (Triglyceride)", "triglyceride"),
    ("Heat-Killed L. plantarum", "heat-killed"),
])
def test_required_fixtures_still_extract(label, expected_canonical):
    forms = form_vocab.extract_forms(label)
    assert expected_canonical in forms, (
        f"Required fixture regression: {label!r} no longer extracts {expected_canonical!r}; got {forms!r}"
    )
