"""A blend header that keeps a specific identity is an interaction subject.

The label names the header after its substance ("Coenzyme Q10 complex 50 mg",
"Chondroitin Complex 290 mg", "Paractin ... Andrographis extract"), the enricher keeps that identity,
yet the interaction scan skipped every blend header, so the substance's rules
never fired (951a05415 capture: 30 such headers whose rule did not fire, coq10,
creatine, chondroitin, turmeric, quercetin among them). Identity is not
scorability: the header stays unscored, but its identity meets its rules.

The header's amount is the blend's, never the substance's dose (D1/D1c), so a
dose threshold reads "amount unknown"; and a header whose identity a row inside
it restates leaves that row, with its own amount, as the subject.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def enrich():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    cache = {}

    def run(name: str) -> dict:
        if name not in cache:
            raw = json.loads((FIXTURES / name).read_text())
            cache[name], _ = enricher.enrich_product(normalizer.normalize_product(raw))
        return cache[name]

    return run


def _alerts(enriched: dict, rule_id: str) -> list:
    return [
        alert for alert in enriched["interaction_profile"]["ingredient_alerts"]
        if alert["rule_id"] == rule_id
    ]


@pytest.mark.parametrize(
    "fixture,rule_id,header",
    [
        # 50 mg "Coenzyme Q10 complex" (CoQ10, MicroActive Q10-cyclodextrin), no children.
        ("interaction_header_coq10_247322_raw.json", "RULE_IQM_COQ10_HEART_DISEASE_STATINS", "Coenzyme Q10 complex"),
        # 290 mg "Chondroitin Complex" (chondroitin sulfate, white willow bark), no children.
        ("interaction_header_chondroitin_12144_raw.json", "RULE_IQM_CHONDROITIN", "Chondroitin Complex"),
        # 25 mg Paractin andrographis extract header over its andrographolide constituents.
        ("interaction_header_andrographis_231708_raw.json", "RULE_IQM_ANDROGRAPHIS",
         "Paractin (Bioactive 14-Neo-Andro Compound) Andrographis extract"),
    ],
)
def test_named_blend_header_meets_its_identitys_rules(enrich, fixture, rule_id, header):
    alerts = _alerts(enrich(fixture), rule_id)
    assert [alert["ingredient_name"] for alert in alerts] == [header]
    assert alerts[0]["condition_hits"] or alerts[0]["drug_class_hits"]


def test_blend_header_amount_is_not_its_substances_dose(enrich):
    """RULE_IQM_ANDROGRAPHIS's antiplatelet threshold (100 mg andrographolide) is not
    evaluated against the 25 mg Paractin header total."""
    (alert,) = _alerts(enrich("interaction_header_andrographis_231708_raw.json"), "RULE_IQM_ANDROGRAPHIS")
    (hit,) = [h for h in alert["drug_class_hits"] if h["drug_class_id"] == "antiplatelets"]
    evaluation = hit["dose_threshold_evaluation"]
    assert evaluation["evaluation_status"] == "amount_unknown"
    assert evaluation["evaluated"] is False


def test_header_restated_by_a_row_inside_it_leaves_that_row_the_subject(enrich):
    """180094 "Turmeric (Curcuma longa) Blend" lists turmeric inside it: the
    turmeric rule fires from that row, never again from the header."""
    enriched = enrich("interaction_header_turmeric_180094_raw.json")
    rows = enriched["ingredient_quality_data"]["ingredients"]
    (header,) = [r for r in rows if r.get("skip_reason") == "blend_header_total_weight_only"
                 and r.get("canonical_id") == "turmeric"]
    names = {alert["ingredient_name"] for alert in _alerts(enriched, "RULE_IQM_TURMERIC_LIVER")}
    assert names and header["raw_source_text"] not in names


def test_header_whose_strains_answer_its_rule_leaves_them_the_subject(enrich):
    """206362 "LAB4 Probiotics" lists strains that answer to the probiotics
    family: the immunocompromised caution stays on a strain row."""
    names = {
        alert["ingredient_name"]
        for alert in _alerts(enrich("interaction_header_probiotic_206362_raw.json"), "RULE_IQM_PROBIOTICS_IMMUNOCOMPROMISED")
    }
    assert names and "LAB4 Probiotics" not in names


def test_header_only_adds_what_no_other_row_warns_about(enrich):
    """59472 "Hydroxytyrosol/Tyrosol" (an olive_leaf header inside the omega
    blend) does not repeat the olive leaf rule that the 300 mg Polyphen-Oil
    olive extract row already fires at the same severity."""
    names = [
        alert["ingredient_name"]
        for alert in _alerts(enrich("interaction_header_olive_marker_59472_raw.json"), "RULE_IQM_OLIVE_LEAF_DIABETES")
    ]
    assert names == ["Polyphen-Oil Olive extract"]


def test_header_declared_plant_part_scopes_its_rules(enrich):
    """328719 "Stinging & Dwarf Nettle Extracts" declares root extracts: the
    nettle blood-pressure rule fires, the leaf-scoped glucose rule does not
    (nettle root -> BP only; Sean, 2026-09-26)."""
    enriched = enrich("interaction_header_nettle_root_328719_raw.json")
    assert _alerts(enriched, "RULE_IQM_STINGING_NETTLE_BLOOD_PRESSURE")
    assert not _alerts(enriched, "RULE_IQM_STINGING_NETTLE_DIABETES")
