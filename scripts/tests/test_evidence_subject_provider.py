"""One provider of Evidence subjects (evidence_zero_rootcause_20260929, lane 1).

The scoring contract decides which rows own a product's Evidence
(``evidence_owner_canonicals``); the scorer scores only the enricher's clinical
matches. The enricher used to match over its own row list, which drops
label-level projections (``product_level_evidence``), so 489 products had
owners the matcher never visited. Both sides now read
``scoring_input_contract.get_evidence_subject_rows``.

Fixtures are real DSLD labels from the 2026-09-29 corpus:
- 251549 DIM-plus: DIM 100 mg exists only as a blend projection.
- 54775 Sytrinol: the branded total exists only as a projection.
- 278019 Pancreatic Enzyme Formula: every enzyme row is a projection.
- 321604 Ultra Triple Action Joint Health: "UC-II Proprietary Cartilage
  Blend" (forms: Cartilage, Potassium Chloride) projects UC-II.
- 176055 Amplified Creatine XXX: creatine owns Evidence; the amino-acid blend
  and L-glutamine projections do not.
- 19505 Rebel Fruit Blast: D-aspartic acid sits undosed in a blend total.
"""

import json
import logging
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402
from evidence_resolver import evidence_owner_canonicals  # noqa: E402
from scoring_input_contract import get_evidence_subject_rows  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.fixture(scope="module")
def enriched(enricher):
    from enhanced_normalizer import EnhancedDSLDNormalizer

    logging.disable(logging.INFO)
    normalizer = EnhancedDSLDNormalizer()
    out = {}
    for dsld_id in ("251549", "54775", "278019", "321604", "176055", "19505"):
        raw = json.loads((FIXTURES / f"evidence_subject_{dsld_id}_raw.json").read_text())
        out[dsld_id], _ = enricher.enrich_product(normalizer.normalize_product(raw))
    return out


def _canonicals(rows):
    return {str(r.get("canonical_id") or "").strip().lower() for r in rows} - {""}


def _matches(product):
    return {
        m.get("id"): set(m.get("matched_canonical_ids") or [])
        for m in product["evidence_data"]["clinical_matches"]
    }


@pytest.mark.parametrize("dsld_id", ["251549", "54775", "278019"])
def test_every_evidence_owner_comes_from_the_one_provider(enriched, dsld_id):
    product = enriched[dsld_id]
    owners = evidence_owner_canonicals(product)
    assert owners
    assert owners <= _canonicals(get_evidence_subject_rows(product))


@pytest.mark.parametrize("dsld_id", ["251549", "54775", "278019"])
def test_the_enricher_matches_over_every_evidence_owner(enricher, enriched, dsld_id):
    product = enriched[dsld_id]
    visited = _canonicals(
        enricher._evidence_subject_ingredients_for_enrichment(
            product, ingredient_quality_data=product["ingredient_quality_data"],
        )
    )
    assert evidence_owner_canonicals(product) <= visited


def test_dim_projection_reaches_its_reviewed_record(enriched):
    assert "diindolylmethane" in _matches(enriched["251549"]).get("PRECLIN_DIM", set())


def test_branded_projection_reaches_its_branded_record(enriched):
    assert "sytrinol" in _matches(enriched["54775"]).get("BRAND_SYTRINOL", set())


def test_a_branded_blend_projection_reaches_its_branded_record(enriched):
    assert "uc_ii_proprietary_cartilage_blend" in _matches(enriched["321604"]).get("BRAND_UCII", set())


@pytest.mark.xfail(strict=True, reason=(
    "Lane 2: a blend header's DSLD forms mix member actives (glucosamine "
    "sulfate, bromelain: they keep their evidence) with carriers (UC-II's "
    "potassium chloride); no owner yet decides which form is a carrier. "
    "Moves no points on 321604 or 239447 (UC-II wins the top slot)."
))
def test_a_carrier_form_on_a_blend_earns_no_evidence(enriched):
    assert "INGR_POTASSIUM" not in _matches(enriched["321604"])


def test_only_evidence_owners_are_added_beyond_the_label_actives(enricher, enriched):
    product = enriched["176055"]
    iqd = product["ingredient_quality_data"]
    label_actives = _canonicals(
        enricher._primary_active_ingredients_for_enrichment(product, ingredient_quality_data=iqd)
    )
    visited = _canonicals(
        enricher._evidence_subject_ingredients_for_enrichment(product, ingredient_quality_data=iqd)
    )
    assert "creatine_monohydrate" in visited
    assert visited <= label_actives | evidence_owner_canonicals(product)
    assert "l_glutamine" not in visited


def test_a_blend_total_is_not_a_member_dose_for_applicability(enriched):
    """The blend total lent to D-aspartic acid is not its amount, so it cannot
    satisfy the reviewed 3 g/day minimum."""
    for match in enriched["19505"]["evidence_data"]["clinical_matches"]:
        if match["id"] == "INGR_D_ASPARTIC_ACID":
            assert (match.get("applicability_assessment") or {}).get("status") != "applicable"
