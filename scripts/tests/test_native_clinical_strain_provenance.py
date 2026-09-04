"""Native probiotic evidence requires a reviewed canonical registry identity."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4.modules.probiotic_evidence import score_evidence  # noqa: E402
import studied_formulas  # noqa: E402
from studied_formulas import independent_clinical_strains  # noqa: E402


def _clinical_row(**fields) -> dict:
    return {
        "strain": "Invented strain X",
        "clinical_support_level": "strong",
        "indication_primary": "digestive",
        **fields,
    }


def _product(**fields) -> dict:
    return {
        "product_name": "Digestive probiotic",
        "probiotic_data": {
            "clinical_strains": [_clinical_row(**fields)],
        },
    }


def _owned_product(
    *,
    owner_name: str | None = None,
    include_source_ref: bool = False,
    quantity: float | int | None = None,
    unit: str = "CFU",
    **fields,
) -> dict:
    row = _clinical_row(**fields)
    ref = "ingredientRows[0]"
    label = (
        owner_name
        or row.get("label_name")
        or row.get("strain")
        or row.get("standard_name")
        or row.get("name")
        or "Invented strain X"
    )
    if include_source_ref:
        row["source_row_ref"] = ref
        row.setdefault("label_name", label)
    row_quantity = quantity
    if row_quantity is None:
        row_quantity = row.get("cfu_per_day")
    has_cfu = row_quantity is not None and float(row_quantity) > 0
    product = {
        "product_name": "Digestive probiotic",
        "activeIngredients": [{
            "name": label,
            "raw_source_path": ref,
            "quantity": row_quantity or 0,
            "unit": unit if has_cfu else "NP",
            "cleaner_row_role": "active_scorable",
            "score_eligible_by_cleaner": True,
        }],
        "serving_basis": {
            "basis_count": 1,
            "basis_unit": "capsule",
            "min_servings_per_day": 1,
            "max_servings_per_day": 1,
            "servings_per_day_source": "servingSizes",
        },
        "probiotic_data": {
            "clinical_strains": [row],
            "probiotic_blends": [{
                "name": label,
                "strains": [label],
                "raw_source_path": ref,
                "cfu_data": {
                    "has_cfu": has_cfu,
                    "cfu_count": row_quantity if has_cfu else None,
                    "raw_source_path": ref,
                    "evidence_scope": "row_level",
                },
            }],
        },
    }
    return product


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"clinical_id": "INVENTED_STRAIN_X"},
        {
            "clinical_id": "INVENTED_STRAIN_X",
            "dr_pham_signoff": True,
            "review_status": "clinician_verified",
            "research_match_status": "exact_strain",
        },
        {
            "clinical_id": "STRAIN_INFANTIS_M63",
            "strain": "Bifidobacterium longum subsp. infantis M-63",
            "dr_pham_signoff": True,
            "review_status": "clinician_verified",
            "research_match_status": "exact_strain",
        },
        {
            "clinical_id": "STRAIN_BREVE_SD_BR3_IT",
            "strain": "Bifidobacterium breve SD-BR3-IT",
            "dr_pham_signoff": True,
            "review_status": "clinician_verified",
            "research_match_status": "exact_strain",
            "evidence_scope": "strain_specific",
        },
        {"clinical_id": "STRAIN_LGG", "strain": "LGG", "research_match_status": "rejected"},
        {"clinical_id": "STRAIN_LGG", "strain": "LGG", "research_match_status": "invented_status"},
        {"clinical_id": "STRAIN_LGG", "strain": "LGG", "research_match_status": "none"},
        {"clinical_id": "STRAIN_LGG", "strain": "LGG", "research_match_status": "pending_review"},
    ],
)
def test_unproven_native_rows_cannot_award_evidence_or_indication_credit(
    fields: dict,
) -> None:
    product = _product(**fields)

    assert independent_clinical_strains(product) == []
    evidence = score_evidence(product)
    assert evidence["metadata"]["native_clinical_strain_evidence_score"] == 0
    assert evidence["components"]["dose_applicability"] == 0


@pytest.mark.parametrize("status", [None, "exact_strain", "species_level"])
def test_reviewed_lgg_registry_identity_retains_native_support(status: str | None) -> None:
    fields = {
        "clinical_id": "STRAIN_LGG",
        "strain": "Lactobacillus rhamnosus GG",
        "clinical_support_level": "high",
    }
    if status is not None:
        fields["research_match_status"] = status
    product = _owned_product(include_source_ref=True, **fields)

    assert independent_clinical_strains(product) == product["probiotic_data"]["clinical_strains"]
    assert score_evidence(product)["metadata"]["native_clinical_strain_evidence_score"] == 8


@pytest.mark.parametrize(
    "fields",
    [
        {"strain": "Invented strain X"},
        {"strain": None},
        {"strain": ""},
        {"strain": "   "},
        {"strain": "Lactobacillus rhamnosus"},
        {"strain": "Lactobacillus rhamnosus HN001"},
        {"strain": "Bifidobacterium rhamnosus GG"},
        {"strain": "Lactobacillus rhamnosus GGX"},
        {"strain": "GG"},
        {"strain": "Invented strain X", "standard_name": "Lactobacillus rhamnosus GG"},
        {"strain": "Invented strain X", "name": "LGG"},
    ],
)
def test_real_clinical_id_cannot_authorize_wrong_or_missing_row_identity(fields: dict) -> None:
    product = _product(
        clinical_id="STRAIN_LGG",
        research_match_status="exact_strain",
        **fields,
    )

    assert independent_clinical_strains(product) == []
    assert score_evidence(product)["score"] == 0


def test_legacy_name_fallback_without_primary_strain_identity_cannot_earn_credit() -> None:
    product = _owned_product(
        clinical_id="STRAIN_LGG",
        strain=None,
        name="LGG",
        owner_name="LGG",
        research_match_status="exact_strain",
        include_source_ref=True,
    )

    assessment = studied_formulas.assess_probiotic_evidence(product)
    assert independent_clinical_strains(product) == []
    assert assessment["strain_assessments"][0]["research_accepted"] is False
    assert assessment["strain_assessments"][0]["status"] == "strain_identity_mismatch"
    assert score_evidence(product)["score"] == 0


@pytest.mark.parametrize(
    "clinical_id,strain,owner_name",
    [
        ("STRAIN_LGG", "Lactobacillus rhamnosus GG", "LGG"),
        ("STRAIN_LGG", "Lactobacillus rhamnosus GG", "  lgg®  "),
        ("STRAIN_LGG", "Lactobacillus rhamnosus GG", "ATCC 53103"),
        ("STRAIN_LGG", "Lactobacillus rhamnosus GG", "Lactobacillus rhamnosus GG:"),
        ("STRAIN_LGG", "Lactobacillus rhamnosus GG", "Lacticaseibacillus rhamnosus GG"),
        ("STRAIN_LONGUM_BB536", "Bifidobacterium longum BB536", "BB536"),
        ("STRAIN_LONGUM_BB536", "Bifidobacterium longum BB536", "B. longum BB536"),
        ("STRAIN_ACIDOPHILUS_NCFM", "Lactobacillus acidophilus NCFM", "Lactobacillus acidophilus (NCFM)"),
        ("STRAIN_LACTIS_HN019", "Bifidobacterium lactis HN019", "Bifidobacterium lactis (HN019)"),
    ],
)
def test_exact_registry_aliases_preserve_independent_native_evidence(
    clinical_id: str, strain: str, owner_name: str,
) -> None:
    product = _owned_product(
        clinical_id=clinical_id,
        strain=strain,
        owner_name=owner_name,
        include_source_ref=True,
    )

    assert independent_clinical_strains(product) == product["probiotic_data"]["clinical_strains"]


@pytest.mark.parametrize(
    "clinical_id,strain",
    [
        # Identity verified 2026-09-03, not additional efficacy/dose claims:
        # https://www.novonesis.com/en/biosolutions/human-health/l-rhamnosus-lgg
        ("STRAIN_LGG", "Lactobacillus rhamnosus LGG"),
        ("STRAIN_LGG", "L. rhamnosus LGG"),
        ("STRAIN_LGG", "L. rhamnosus GG, LGG"),
        # https://www.novonesis.com/en/biosolutions/human-health/b-lactis-bb-12
        ("STRAIN_LACTIS_BB12", "Bifidobacterium animalis lactis BB-12"),
        ("STRAIN_LACTIS_BB12", "Bifidobacterium animalis subsp. lactis (BB-12)"),
        # https://www.iff.com/health-sciences/our-products/howaru-ncfm/
        ("STRAIN_ACIDOPHILUS_NCFM", "HOWARU Lactobacillus acidophilus NCFM"),
        ("STRAIN_ACIDOPHILUS_NCFM", "HOWARU L. acidophilus NCFM"),
        # IFF identifies both B. lactis and animalis subsp. lactis spellings:
        # https://www.iff.com/media/stories/exploring-the-microbiome-the-key-to-unlocking-your-health-potential/
        ("STRAIN_LACTIS_BI07", "Bifidobacterium animalis lactis Bi-07"),
        ("STRAIN_LACTIS_BI07", "B. animalis lactis BI-07"),
        ("STRAIN_LACTIS_BL04", "Bifidobacterium animalis lactis BL-04"),
        ("STRAIN_LACTIS_BL04", "B. animalis lactis BL-04"),
        # https://www.iff.com/health-sciences/our-products/howaru-bl-04/
        ("STRAIN_LACTIS_BL04", "Bifidobacterium lactis strain Bl-04"),
        # https://www.iff.com/health-sciences/our-products/howaru-hn019/
        ("STRAIN_LACTIS_HN019", "Bifidobacterium lactis strain HN019"),
        ("STRAIN_LACTIS_HN019", "HOWARU Bifidobacterium animalis lactis HN019"),
        ("STRAIN_LACTIS_HN019", "HOWARU B. lactis HN019"),
        # https://www.iff.com/health-sciences/our-products/howaru-lpc-37/
        ("STRAIN_PARACASEI_LPC37", "Lactobacillus paracasei strain Lpc-37"),
        # Final bounded corpus aliases, identities checked 2026-09-03:
        # https://www.iff.com/health-sciences/our-products/howaru-hn001/
        ("STRAIN_RHAMNOSUS_HN001", "HOWARU L. rhamnosus HN001"),
        ("STRAIN_RHAMNOSUS_HN001", "HOWARU Lactobacillus rhamnosus HN001"),
        # https://blis.co.nz/blis-k12/
        ("STRAIN_K12", "BLIS K12 S. salivarius K12"),
        # https://www.tga.gov.au/resources/resources/compositional-guidelines/streptococcus-salivarius-m18
        ("STRAIN_M18", "BLIS M18 S. salivarius M18"),
        # https://lactospore.com/
        ("STRAIN_COAGULANS_MTCC5856", "Lactospore Bacillus coagulans MTCC5856"),
        # https://www.probi.com/about-us/lp299v-probiotic-strain/
        ("STRAIN_PLANTARUM_299V", "Lactobacillus plantarum Lp299v"),
        ("STRAIN_PLANTARUM_299V", "Lactobacillus plantarum LP299v"),
        # Probi strain list, page 12, explicitly pairs both DSM identifiers:
        # https://www.probi.com/media/luqcopej/probi_booklet_selectedstudies_clinbac.pdf
        ("STRAIN_PLANTARUM_HEAL9", "Lactobacillus plantarum DSM 15312"),
        ("STRAIN_PARACASEI_8700", "Lactobacillus paracasei DSM 13434"),
        # https://www.novonesis.com/en/biosolutions/human-health/dietary-supplements/l-casei-431
        ("STRAIN_CASEI_431", "L. paracasei, L. CASEI 431"),
        # FDA GRN 872, section 2.1: UAS Labs' exact strain identity.
        # https://www.fda.gov/media/135325/download
        ("STRAIN_LACTIS_UABla12", "Bifidobacterium animalis lactis UABla-12"),
    ],
)
def test_verified_corpus_spelling_variants_keep_exact_native_identity(
    clinical_id: str, strain: str,
) -> None:
    product = _owned_product(
        clinical_id=clinical_id,
        strain=strain,
        owner_name=strain,
        include_source_ref=True,
    )

    assert independent_clinical_strains(product) == product["probiotic_data"]["clinical_strains"]
    assert score_evidence(product)["metadata"]["native_clinical_strain_evidence_score"] > 0


@pytest.mark.parametrize(
    "clinical_id,strain",
    [
        ("STRAIN_LGG", "Bifidobacterium rhamnosus LGG"),
        ("STRAIN_LGG", "Lactobacillus acidophilus LGG"),
        ("STRAIN_LACTIS_BB12", "Bifidobacterium animalis lactis BB-120"),
        ("STRAIN_LACTIS_BB12", "Lactobacillus animalis lactis BB-12"),
        ("STRAIN_LACTIS_BL04", "Bifidobacterium animalis lactis Bl-07"),
        ("STRAIN_ACIDOPHILUS_NCFM", "HOWARU Lactobacillus acidophilus"),
        ("STRAIN_ACIDOPHILUS_NCFM", "Lactobacillus acidophilus (CUL60)"),
        ("STRAIN_SACCHAROMYCES", "Saccharomyces cerevisiae"),
        ("STRAIN_RHAMNOSUS_HN001", "HOWARU Bifidobacterium rhamnosus HN001"),
        ("STRAIN_RHAMNOSUS_HN001", "HOWARU Lactobacillus rhamnosus HN019"),
        ("STRAIN_K12", "BLIS M18 S. salivarius M18"),
        ("STRAIN_M18", "BLIS K12 S. salivarius K12"),
        ("STRAIN_COAGULANS_MTCC5856", "Lactospore Bacillus coagulans MTCC5857"),
        ("STRAIN_PLANTARUM_299V", "Lactobacillus plantarum LP299VX"),
        ("STRAIN_PLANTARUM_HEAL9", "Lactobacillus plantarum DSM 13434"),
        ("STRAIN_PARACASEI_8700", "Lactobacillus paracasei DSM 15312"),
        ("STRAIN_CASEI_431", "L. paracasei, L. CASEI 432"),
        ("STRAIN_LACTIS_UABla12", "Bifidobacterium animalis lactis BB-12"),
        ("STRAIN_LACTIS_BB12", "Bifidobacterium animalis lactis UABla-12"),
        ("STRAIN_REUTERI_DSM17938", "L. reuteri 1E1"),
    ],
)
def test_verified_aliases_do_not_authorize_other_species_or_strain_codes(
    clinical_id: str, strain: str,
) -> None:
    product = _product(clinical_id=clinical_id, strain=strain, research_match_status="exact_strain")

    assert independent_clinical_strains(product) == []
    assert score_evidence(product)["score"] == 0


def test_reviewed_formula_reference_cannot_be_spoofed_as_independent_strain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = copy.deepcopy(studied_formulas._clinical_strain_registry())
    registry["STRAIN_BREVE_SD_BR3_IT"]["cfu_thresholds"]["dr_pham_signoff"] = True
    monkeypatch.setattr(studied_formulas, "_clinical_strain_registry", lambda: registry)
    product = _owned_product(
        clinical_id="STRAIN_BREVE_SD_BR3_IT",
        strain="Bifidobacterium breve SD-BR3-IT",
        research_match_status="exact_strain",
        evidence_scope="strain_specific",
        include_source_ref=True,
    )

    assert independent_clinical_strains(product) == []


def test_pending_strain_dose_keeps_disclosure_without_clinical_adequacy() -> None:
    from scoring_v4.modules.probiotic_dose import score_dose

    product = _owned_product(
        strain="Bifidobacterium longum subsp. infantis M-63",
        clinical_id="STRAIN_INFANTIS_M63",
        cfu_per_day=10_000_000_000,
        adequacy_tier="good",
        include_source_ref=True,
    )
    product["probiotic_data"].update({
        "total_strain_count": 1,
        "total_billion_count": 10,
        "guarantee_type": "at_expiration",
    })

    dose = score_dose(product)
    assert dose["components"]["per_strain_cfu_disclosure"] == 10
    assert dose["components"]["cfu_adequacy"] == 0


def test_pending_strain_cannot_supply_an_aggregate_clinical_dose_proxy() -> None:
    from scoring_v4.modules.probiotic_dose import (
        AGGREGATE_CFU_LOW_TIER_PRESENCE_FLOOR,
        score_dose,
    )

    product = _owned_product(
        strain="Bifidobacterium longum subsp. infantis M-63",
        clinical_id="STRAIN_INFANTIS_M63",
        clinical_support_level="high",
        include_source_ref=True,
    )
    product["probiotic_data"].update({
        "total_strain_count": 1,
        "total_billion_count": 10,
        "guarantee_type": "at_expiration",
    })

    dose = score_dose(product)
    assert dose["components"]["per_strain_cfu_disclosure"] == 0
    assert dose["components"]["cfu_adequacy"] == AGGREGATE_CFU_LOW_TIER_PRESENCE_FLOOR
    assert dose["metadata"]["aggregate_cfu_proxy"]["reason"] == (
        "aggregate_cfu_without_clinical_strain_mapping_floor"
    )


def test_unreviewed_strains_keep_label_diversity_but_no_clinical_code_credit() -> None:
    from scoring_v4.modules.probiotic_formulation import score_formulation

    product = _owned_product(
        clinical_id="STRAIN_BREVE_SD_BR3_IT",
        strain="Bifidobacterium breve SD-BR3-IT",
        include_source_ref=True,
    )
    product["probiotic_data"].update({
        "total_strain_count": 4,
        "clinical_strain_count": 4,
    })

    formulation = score_formulation(product)
    assert formulation["components"]["named_species_diversity"] == 4
    assert formulation["components"]["clinical_strain_codes"] == 0
    assert formulation["metadata"]["clinical_strain_count"] == 0


@pytest.fixture(scope="module")
def clinical_enricher():
    from enrich_supplements_v3 import SupplementEnricherV3

    return SupplementEnricherV3()


def _label_product(strain: str) -> dict:
    return {
        "id": "strain-identity-contract",
        "product_name": "Probiotic capsule",
        "activeIngredients": [{
            "name": strain,
            "raw_source_text": strain,
            "raw_source_path": "ingredientRows[0]",
            "category": "probiotic",
            "quantity": 10_000_000_000,
            "unit": "CFU",
            "notes": "10 billion CFU",
            "cleaner_row_role": "active_scorable",
            "score_eligible_by_cleaner": True,
        }],
        "inactiveIngredients": [],
    }


@pytest.mark.parametrize("strain", [
    "Lactobacillus acidophilus",
    "Lactobacillus acidophilus (CUL 60)",
    "Bifidobacterium rhamnosus GG",
    "L. reuteri 1E1",
])
def test_producer_cannot_export_a_badge_for_a_different_strain(
    clinical_enricher, strain: str,
) -> None:
    from build_final_db import build_detail_blob
    from scoring_v4.modules.probiotic_dose import score_dose

    product = _label_product(strain)
    product["probiotic_data"] = clinical_enricher._collect_probiotic_data(product)
    blob = build_detail_blob(product, {})

    assert blob["probiotic_detail"]["clinical_strains"] == []
    assert blob["probiotic_detail"]["clinical_strain_count"] == 0
    assert len(blob["ingredients"]) == 1
    assert blob["ingredients"][0]["adequacy_tier"] is None
    assert blob["ingredients"][0]["clinical_support_level"] is None
    assert blob["ingredients"][0]["display_badge"] == "no_data"
    assert product["probiotic_data"]["total_strain_count"] == 1
    assert product["probiotic_data"]["total_cfu"] == 10_000_000_000
    assert product["probiotic_data"]["probiotic_blends"][0]["strains"] == [strain]
    dose = score_dose(product)
    assert dose["metadata"]["per_strain_cfu_disclosed_count"] == 1
    assert dose["components"]["per_strain_cfu_disclosure"] == 10
    assert dose["components"]["cfu_adequacy"] == 0


@pytest.mark.parametrize("strain,clinical_id,status", [
    ("Lactobacillus rhamnosus LGG", "STRAIN_LGG", "species_level"),
    ("Bifidobacterium animalis lactis BB-12", "STRAIN_LACTIS_BB12", "species_level"),
    ("Bifidobacterium longum subsp. infantis M-63", "STRAIN_INFANTIS_M63", "pending_review"),
    ("Bifidobacterium breve SD-BR3-IT", "STRAIN_BREVE_SD_BR3_IT", "pending_review"),
])
def test_producer_keeps_verified_alias_and_exact_pending_identity(
    clinical_enricher, strain: str, clinical_id: str, status: str,
) -> None:
    from build_final_db import build_detail_blob

    product = _label_product(strain)
    product["probiotic_data"] = clinical_enricher._collect_probiotic_data(product)
    blob = build_detail_blob(product, {})

    rows = blob["probiotic_detail"]["clinical_strains"]
    assert len(rows) == 1
    assert rows[0]["clinical_id"] == clinical_id
    assert rows[0]["research_match_status"] == status
    assert rows[0]["cfu_per_day"] == 10_000_000_000
