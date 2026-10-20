"""Printed omega constituent amounts are not carrier oil, on seven NIH DSLD labels."""
import copy
import json
from pathlib import Path

import pytest

from scoring_input_contract import epa_dha_amounts_per_serving
from scoring_v4.modules.omega_formulation import _epa_dha_and_oil_mass_mg, _is_parent_oil_row

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def carrier_products():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact

    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    products = {}
    for pid in ("179661", "180107", "315329", "82715", "74302", "231416", "259484"):
        raw = json.loads((FIXTURES / f"omega_carrier_{pid}_raw.json").read_text())
        enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
        products[pid] = (enriched, build_scored_artifact(copy.deepcopy(enriched)))
    return products


@pytest.mark.parametrize("pid,epa_dha_mg,carrier_mg", [
    ("179661", 600, 2400), ("180107", 500, 2000),
    ("315329", 50, 0), ("82715", 500, 2000),
    ("74302", 50, 0), ("231416", 500, 918), ("259484", 2000, 4500),
])
def test_printed_constituent_amount_is_not_carrier_oil(carrier_products, pid, epa_dha_mg, carrier_mg):
    enriched, _ = carrier_products[pid]
    epa, dha, combined = epa_dha_amounts_per_serving(enriched)
    assert max(epa + dha, combined) == epa_dha_mg
    assert _epa_dha_and_oil_mass_mg(enriched) == {
        "epa_dha_mg": epa_dha_mg, "oil_mg": carrier_mg,
    }


def test_aggregate_only_label_cannot_earn_concentration_credit(carrier_products):
    _, scored = carrier_products["74302"]
    concentration = scored["_v4_module_breakdown"]["dimensions"]["formulation"]["metadata"]["epa_dha_concentration"]
    assert concentration["epa_dha_mg"] == 50
    assert concentration["oil_mg"] == 0
    assert concentration["status"] == "missing_oil_mass"
    assert concentration["score"] == 0
    assert "ratio" not in concentration


@pytest.mark.parametrize("source,is_carrier", [
    ("EPA/DHA", False), ("Omega-3 EPA & DHA", False),
    ("Total Omega-3 Fatty Acids", False),
    ("Fish Oil (EPA/DHA)", True), ("Fish Oil concentrate", True),
    ("Omega-3 Fatty Acid Ethyl Ester", True),
])
def test_carrier_classifier_reads_printed_material_before_identity(source, is_carrier):
    # The enricher may map a constituent row to fish_oil; its printed material
    # still decides whether the amount measures source oil.
    assert _is_parent_oil_row({"name": source, "raw_source_text": source,
                               "canonical_id": "fish_oil"}) is is_carrier
