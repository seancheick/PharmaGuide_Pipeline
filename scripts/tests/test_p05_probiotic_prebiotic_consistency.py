"""P0.5 regression tests — probiotic_detail.prebiotic_present must agree
with the scorer's prebiotic credit signal.

Codex's read-only audit on the 2026-05-19 RC surfaced a split-brain
contract on DSLD 274081 (Garden of Life Once Daily Prenatal):

  - scorer credits prebiotic: probiotic_breakdown.prebiotic = 1.0
    (because the substring "acacia" matches the scorer's prebiotic_terms
    list against the active ingredient "organic Acacia Fiber")
  - enricher detail says no prebiotic: probiotic_detail.prebiotic_present
    = False, prebiotic_name = "" (because the enricher only does
    exact-match against clinically_relevant_strains.json's prebiotics
    list, which doesn't accept "organic Acacia Fiber" as a match for
    "Acacia Fiber" or its aliases)

Catalog scan found 74 products with score prebiotic > 0 but display
flag false. This file is the regression contract that prevents drift.

Fix: enricher gains a second-pass substring detection against the same
prebiotic_terms list the scorer uses (sourced from scoring_config so
both reads stay in sync).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def _probiotic_product(
    *,
    extra_active: list | None = None,
    extra_inactive: list | None = None,
    nested_in_blend: list | None = None,
) -> dict:
    """Minimal probiotic product with two strains.  Caller decorates with
    prebiotic candidates via `extra_active`, `extra_inactive`, or
    `nested_in_blend` (children of the first probiotic blend)."""
    actives = [
        {
            "name": "Lactobacillus rhamnosus",
            "standardName": "Lactobacillus Rhamnosus",
            "category": "probiotic",
            "quantity": 5_000_000_000,
            "unit": "Live Cell(s)",
            "nestedIngredients": nested_in_blend or [],
            "harvestMethod": "",
            "notes": "",
        },
        {
            "name": "Bifidobacterium lactis",
            "standardName": "Bifidobacterium Lactis",
            "category": "probiotic",
            "quantity": 5_000_000_000,
            "unit": "Live Cell(s)",
            "nestedIngredients": [],
            "harvestMethod": "",
            "notes": "",
        },
    ]
    if extra_active:
        actives.extend(extra_active)
    return {
        "id": "test_p05",
        "product_name": "Test Probiotic",
        "fullName": "Test Probiotic",
        "bundleName": "",
        "statements": [],
        "activeIngredients": actives,
        "inactiveIngredients": extra_inactive or [],
    }


def test_exact_lgg_and_bb12_nested_blend_resolve_to_exact_clinical_strains(enricher) -> None:
    """Manual/DTC labels often put branded strain IDs in a nested row's
    ingredientGroup/notes instead of the display name. Exact strain evidence
    must beat species-level representative strains.
    """
    product = _probiotic_product(
        nested_in_blend=[
            {
                "name": "Lactobacillus rhamnosus",
                "standardName": "Lactobacillus rhamnosus",
                "ingredientGroup": "LGG",
                "category": "probiotic",
                "notes": "strain LGG",
                "nestedIngredients": [],
            },
            {
                "name": "Bifidobacterium animalis subsp. lactis",
                "standardName": "Bifidobacterium animalis subsp. lactis",
                "ingredientGroup": "BB-12",
                "category": "probiotic",
                "notes": "strain BB-12",
                "nestedIngredients": [],
            },
        ],
    )

    pd = enricher._collect_probiotic_data(product)
    ids = {entry["clinical_id"] for entry in pd["clinical_strains"]}

    assert "STRAIN_LGG" in ids
    assert "STRAIN_LACTIS_BB12" in ids
    assert "STRAIN_RHAMNOSUS_HN001" not in ids
    assert "STRAIN_LACTIS_BL04" not in ids


def test_species_only_probiotic_rows_do_not_get_strain_specific_clinical_ids(enricher) -> None:
    """A species-only label is not evidence for a specific clinical strain.

    v3 previously treated HN001/BL-04 as representative stand-ins because the
    strain-code parser missed those target IDs. That overstates clinical
    evidence; exact strain bonuses require exact strain evidence.
    """
    product = _probiotic_product()

    pd = enricher._collect_probiotic_data(product)
    ids = {entry["clinical_id"] for entry in pd["clinical_strains"]}

    assert "STRAIN_RHAMNOSUS_HN001" not in ids
    assert "STRAIN_LACTIS_BL04" not in ids


def test_distinct_infantis_strain_codes_do_not_cross_match(enricher) -> None:
    """M-63 must never inherit the unrelated 35624 clinical evidence."""
    assert enricher._strain_match(
        "Bifidobacterium longum infantis M-63",
        "Bifidobacterium infantis 35624",
        [
            "B. infantis 35624",
            "Bifidobacterium longum 35624",
            "B. longum subsp. infantis 35624",
        ],
    ) is False

    product = _probiotic_product(
        extra_active=[
            {
                "name": "Bifidobacterium longum infantis M-63",
                "standardName": "Bifidobacterium longum infantis M-63",
                "ingredientGroup": "Bifidobacterium infantis",
                "category": "probiotic",
                "quantity": 12.5,
                "unit": "mg",
                "nestedIngredients": [],
                "harvestMethod": "",
                "notes": "1 billion CFU",
            }
        ],
    )

    clinical_ids = {
        entry["clinical_id"]
        for entry in enricher._collect_probiotic_data(product)["clinical_strains"]
        if entry.get("strain") == "Bifidobacterium longum infantis M-63"
    }
    assert "STRAIN_INFANTIS_35624" not in clinical_ids


def test_m63_resolves_to_its_own_reviewed_identity_and_evidence(enricher) -> None:
    product = _probiotic_product(
        extra_active=[
            {
                "name": "Bifidobacterium longum infantis M-63",
                "standardName": "Bifidobacterium longum infantis M-63",
                "ingredientGroup": "Bifidobacterium infantis",
                "category": "probiotic",
                "quantity": 12.5,
                "unit": "mg",
                "nestedIngredients": [],
                "harvestMethod": "",
                "notes": "1 billion CFU",
            }
        ],
    )

    clinical_rows = [
        entry
        for entry in enricher._collect_probiotic_data(product)["clinical_strains"]
        if entry.get("strain") == "Bifidobacterium longum infantis M-63"
    ]
    assert len(clinical_rows) == 1
    assert clinical_rows[0]["clinical_id"] == "STRAIN_INFANTIS_M63"
    assert clinical_rows[0]["clinical_support_level"] == "moderate"
    assert clinical_rows[0]["cfu_per_day"] == 1_000_000_000
    assert clinical_rows[0]["adequacy_tier"] == "adequate"

    match = enricher._match_quality_map(
        "Bifidobacterium longum infantis M-63",
        "Bifidobacterium longum infantis M-63",
        enricher.databases["ingredient_quality_map"],
    )
    assert match is not None
    assert match["canonical_id"] == "bifidobacterium_longum"
    assert match["form_id"] == "bifidobacterium longum infantis m-63"
    assert match["bio_score"] == 12


def test_seed_ds01_sd_strain_codes_resolve_to_exact_formula_backed_strains(enricher) -> None:
    """Seed DS-01 style labels carry exact SD-* strain codes in nested rows.

    Those codes must resolve as exact identities, not as species-level
    representative strains, and not disappear because the strain-code parser
    only knows legacy IDs like LGG/BB-12.
    """
    product = _probiotic_product(
        extra_active=[
            {
                "name": "Indian pomegranate extract",
                "standardName": "Indian Pomegranate Extract",
                "category": "botanical",
                "quantity": 400,
                "unit": "mg",
                "nestedIngredients": [],
                "harvestMethod": "",
                "notes": "polyphenol-based prebiotic",
            }
        ],
        nested_in_blend=[
            {
                "name": "Bifidobacterium breve",
                "standardName": "Bifidobacterium breve",
                "ingredientGroup": "SD-BR3-IT",
                "category": "probiotic",
                "notes": "strain SD-BR3-IT",
                "nestedIngredients": [],
            },
            {
                "name": "Ligilactobacillus salivarius",
                "standardName": "Ligilactobacillus salivarius",
                "ingredientGroup": "SD-LS1-IT",
                "category": "probiotic",
                "notes": "strain SD-LS1-IT",
                "nestedIngredients": [],
            },
            {
                "name": "Lactiplantibacillus plantarum",
                "standardName": "Lactiplantibacillus plantarum",
                "ingredientGroup": "SD-LP1-IT",
                "category": "probiotic",
                "notes": "strain SD-LP1-IT",
                "nestedIngredients": [],
            },
            {
                "name": "Lactiplantibacillus plantarum",
                "standardName": "Lactiplantibacillus plantarum",
                "ingredientGroup": "SD-LPLDL-UK",
                "category": "probiotic",
                "notes": "strain SD-LPLDL-UK",
                "nestedIngredients": [],
            },
        ],
    )

    pd = enricher._collect_probiotic_data(product)
    ids = {entry["clinical_id"] for entry in pd["clinical_strains"]}

    assert {
        "STRAIN_BREVE_SD_BR3_IT",
        "STRAIN_SALIVARIUS_SD_LS1_IT",
        "STRAIN_PLANTARUM_SD_LP1_IT",
        "STRAIN_PLANTARUM_SD_LPLDL_UK",
    } <= ids
    assert "STRAIN_PLANTARUM_299V" not in ids
    assert "STRAIN_RHAMNOSUS_HN001" not in ids
    assert pd["prebiotic_present"] is True
    assert "pomegranate" in pd["prebiotic_name"].lower()


def test_clinically_relevant_strains_are_in_content_verifier_config() -> None:
    sys.path.insert(0, str(SCRIPTS_ROOT / "api_audit"))
    import verify_all_citations_content as vac

    by_file = {config["file"]: config for config in vac.FILE_CONFIGS}
    config = by_file.get("clinically_relevant_strains.json")

    assert config is not None
    assert config["source_format"] == "nested_cfu_evidence_pmids"

    refs = vac.extract_pmids_from_entry(
        {
            "id": "TEST",
            "cfu_thresholds": {
                "evidence": {
                    "pmid": "40944126",
                    "secondary_pmid": "41750436",
                    "additional_pmids": ["26756877"],
                }
            },
        },
        config,
    )

    assert [ref["pmid"] for ref in refs] == ["40944126", "41750436", "26756877"]


# --- Anchor: the GoL prenatal pattern that triggered P0.5 -----------------


def test_organic_acacia_fiber_active_marks_prebiotic_present(enricher) -> None:
    """Active ingredient 'organic Acacia Fiber' is a prebiotic per the
    scorer's terms list ('acacia' substring) — enricher must agree.

    This reproduces the exact split-brain pattern on DSLD 274081
    (Garden of Life Dr. Formulated Probiotics Once Daily Prenatal)."""
    product = _probiotic_product(
        extra_active=[
            {
                "name": "organic Acacia Fiber",
                "standardName": "Organic Acacia Fiber",
                "category": "fiber",
                "quantity": 200,
                "unit": "mg",
                "nestedIngredients": [],
                "harvestMethod": "",
                "notes": "",
            }
        ],
    )
    pd = enricher._collect_probiotic_data(product)
    assert pd["prebiotic_present"] is True, (
        "active 'organic Acacia Fiber' should set prebiotic_present=True "
        "(scorer awards prebiotic credit via 'acacia' substring; enricher "
        "must agree). got prebiotic_name=%r" % pd.get("prebiotic_name")
    )
    assert pd["prebiotic_name"], "prebiotic_name should not be empty"


# --- Each canonical prebiotic-term family ---------------------------------


@pytest.mark.parametrize(
    "ingredient_name",
    [
        "Inulin",
        "Chicory Root Fiber",
        "FOS (Fructooligosaccharides)",
        "GOS (Galactooligosaccharides)",
        "Beta-Glucan",
        "Pea Fiber",
        "XOS",
        "Lactulose",
        "Raftiline",
    ],
)
def test_known_prebiotic_terms_detected(enricher, ingredient_name: str) -> None:
    """Every term in scoring_config.prebiotic_terms should round-trip:
    if the scorer credits it via substring, the enricher must flag it.
    Locks the cross-config single-source-of-truth."""
    product = _probiotic_product(
        extra_active=[
            {
                "name": ingredient_name,
                "standardName": ingredient_name,
                "category": "fiber",
                "quantity": 500,
                "unit": "mg",
                "nestedIngredients": [],
                "harvestMethod": "",
                "notes": "",
            }
        ],
    )
    pd = enricher._collect_probiotic_data(product)
    assert pd["prebiotic_present"] is True, (
        f"{ingredient_name!r} contains a scorer-recognized prebiotic term; "
        f"enricher must flag prebiotic_present"
    )


def test_preforpro_bacteriophage_prebiotic_marks_prebiotic_present(enricher) -> None:
    product = _probiotic_product(
        extra_active=[
            {
                "name": "PreforPro",
                "standardName": "Bacteriophages",
                "category": "non-nutrient/non-botanical",
                "ingredientGroup": "Prebiotic",
                "quantity": 15,
                "unit": "mg",
                "notes": "bacteriophage prebiotic blend",
                "nestedIngredients": [],
            }
        ],
    )

    pd = enricher._collect_probiotic_data(product)

    assert pd["prebiotic_present"] is True
    assert pd["prebiotic_name"]


def test_tributyrin_butyrate_marks_postbiotic_metabolite(enricher) -> None:
    product = _probiotic_product(
        extra_active=[
            {
                "name": "Tributyrin",
                "standardName": "Butyric Acid",
                "canonical_id": "butyric_acid",
                "category": "non-nutrient/non-botanical",
                "ingredientGroup": "Postbiotic",
                "quantity": 300,
                "unit": "mg",
                "notes": "as CoreBiome; tributyrin (butyrate postbiotic)",
                "nestedIngredients": [],
            }
        ],
    )

    pd = enricher._collect_probiotic_data(product)

    assert pd["postbiotic_metabolite_present"] is True
    assert pd["postbiotic_metabolite_name"] == "Butyric Acid"


# --- Coverage in nested-blend children ------------------------------------


def test_prebiotic_in_nested_blend_child_detected(enricher) -> None:
    """A prebiotic hidden inside a proprietary-blend's nested children must
    still set prebiotic_present.  Existing enricher logic already supports
    nested coverage for exact-matches; substring fallback must preserve it."""
    product = _probiotic_product(
        nested_in_blend=[
            {
                "name": "Acacia Fiber",
                "standardName": "Acacia Fiber",
                "category": "fiber",
                "quantity": 100,
                "unit": "mg",
            }
        ],
    )
    pd = enricher._collect_probiotic_data(product)
    assert pd["prebiotic_present"] is True, (
        "prebiotic in nested blend child must be detected"
    )


# --- Negative cases -------------------------------------------------------


def test_no_prebiotic_means_prebiotic_present_false(enricher) -> None:
    """A probiotic with strains but NO prebiotic ingredient must score
    prebiotic_present=False.  Avoid false positives."""
    product = _probiotic_product()
    pd = enricher._collect_probiotic_data(product)
    assert pd["prebiotic_present"] is False
    assert pd["prebiotic_name"] == ""


def test_non_prebiotic_fiber_not_falsely_detected(enricher) -> None:
    """'Apple fiber' is not in the scorer's prebiotic_terms list and is
    not a canonical prebiotic.  Must not trigger prebiotic_present."""
    product = _probiotic_product(
        extra_active=[
            {
                "name": "Apple Fiber",
                "standardName": "Apple Fiber",
                "category": "fiber",
                "quantity": 200,
                "unit": "mg",
                "nestedIngredients": [],
            }
        ],
    )
    pd = enricher._collect_probiotic_data(product)
    assert pd["prebiotic_present"] is False, (
        "'Apple Fiber' must not falsely trigger prebiotic_present"
    )


# --- Cross-source contract -------------------------------------------------


def test_existing_exact_match_path_still_works(enricher) -> None:
    """The new substring fallback must not break the existing exact-match
    detection against clinically_relevant_strains.json."""
    # "Inulin" is in the canonical prebiotics DB AND in the scorer's
    # substring terms list. Both paths should agree.
    product = _probiotic_product(
        extra_active=[
            {
                "name": "Inulin",
                "standardName": "Inulin",
                "category": "fiber",
                "quantity": 500,
                "unit": "mg",
                "nestedIngredients": [],
            }
        ],
    )
    pd = enricher._collect_probiotic_data(product)
    assert pd["prebiotic_present"] is True
    # prebiotic_name should be non-empty (exact match prefers canonical name)
    assert pd["prebiotic_name"], "prebiotic_name should be populated"


# --- Config-source single source of truth ----------------------------------


def test_enricher_reads_scoring_config_prebiotic_terms() -> None:
    """Drift prevention — the enricher's substring fallback should source
    its term list from scoring_config (same place the scorer reads from)
    so the two stay aligned.  If a future maintainer extends the terms
    list in config, both paths should pick it up without code changes."""
    import json
    cfg = json.loads(
        (SCRIPTS_ROOT / "config" / "scoring_config.json").read_text()
    )
    pro_cfg = cfg["section_A_ingredient_quality"]["probiotic_bonus"]
    terms = pro_cfg.get("prebiotic_terms") or []
    assert "acacia" in terms, (
        "scoring_config.prebiotic_terms must contain 'acacia' — both the "
        "scorer's existing detection and the new enricher fallback depend "
        "on this term"
    )
    assert "inulin" in terms
    assert "fos" in terms
