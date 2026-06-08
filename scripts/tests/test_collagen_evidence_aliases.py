"""P1 (safe slice): generic hydrolyzed-collagen-peptide evidence aliases.

Step-10 cohort review (collagen reviewer): 13 clearly-dosed hydrolyzed/peptide
collagen products read evidence=0 because the clinical-study matcher is exact/
label-text dependent and the "Hydrolyzed Collagen Peptides" study only carried
aliases ['collagen hydrolysate', 'collagen powder']. That study is
evidence_level=INGREDIENT-human (generic — NOT brand-specific), so generic
synonyms of hydrolyzed collagen peptides legitimately share its evidence.

GUARD: UC-II and BioCell are evidence_level=PRODUCT-human (brand-specific RCTs).
Generic "collagen peptides" must NOT match them — that would over-credit generic
collagen with branded evidence (the same clinical-integrity violation as aliasing
generic pine bark to Pycnogenol). Only the ingredient-level study gets the synonyms.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3(
        config_path=str(SCRIPTS_DIR / "config" / "enrichment_config.json")
    )


def _studies(enricher):
    return enricher.databases["backed_clinical_studies"]["backed_clinical_studies"]


def _study(enricher, name_startswith):
    return next(s for s in _studies(enricher)
               if str(s.get("standard_name", "")).startswith(name_startswith))


@pytest.mark.parametrize("label", [
    "Collagen Peptides",
    "Hydrolyzed Collagen",
    "Hydrolyzed Collagen Peptides",
    "Bovine Collagen Peptides",
    "Marine Collagen Peptides",
    "Collagen Peptides Powder",
    "Grass Fed Collagen",
])
def test_generic_hydrolyzed_synonyms_match_ingredient_study(enricher, label) -> None:
    study = _study(enricher, "Hydrolyzed Collagen Peptides")
    assert study.get("evidence_level") == "ingredient-human"  # generic, alias-safe
    matched = enricher._clinical_study_match([label], study)
    assert matched is not None, f"{label!r} should match Hydrolyzed Collagen Peptides"


def test_generic_collagen_does_not_match_brand_studies(enricher) -> None:
    """Brand-specific (product-human) studies must NOT absorb generic collagen."""
    uc2 = _study(enricher, "UC-II")
    biocell = _study(enricher, "BioCell")
    assert uc2.get("evidence_level") == "product-human"
    assert biocell.get("evidence_level") == "product-human"
    assert enricher._clinical_study_match(["Collagen Peptides"], uc2) is None
    assert enricher._clinical_study_match(["Collagen Peptides"], biocell) is None
