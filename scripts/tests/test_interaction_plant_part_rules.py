"""Dandelion and nettle interaction claims follow the plant part their evidence covers.

Sean, 2026-09-26: split the rules by plant part. The dandelion diuretic claims
(kidney disease, antihypertensives, lithium) rest on leaf evidence: PMID
19678785 is a Taraxacum officinale folium trial, and the EU monographs give the
diuretic indication for the leaf and for root with herb, none for root alone.
The nettle glucose claims rest on a nettle leaf trial (PMID 24273930) and the
EU nettle-leaf monograph is the diuretic one; the root monograph covers only
benign prostatic hyperplasia. The nettle blood-pressure claim covers every part
(PMID 35800714; root extract in rats, PMID 12020933), so it has its own
unscoped rule. Before the split every dandelion or nettle root
label carried the leaf claims, while a label resolved to the botanical root
record carried nothing.

A part-scoped rule (form_scope_match "fail_open") stays silent only for a
label-confirmed form outside its scope; an unknown or inferred form still warns
(the G1 fail-open doctrine).
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
DANDELION_DIURETIC = "RULE_IQM_DANDELION_KIDNEY"
DANDELION_GLUCOSE = "RULE_IQM_DANDELION_GLUCOSE"
NETTLE = "RULE_IQM_STINGING_NETTLE_DIABETES"
NETTLE_BP = "RULE_IQM_STINGING_NETTLE_BLOOD_PRESSURE"


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3

    return SupplementEnricherV3()


@pytest.fixture(scope="module")
def normalizer():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    return EnhancedDSLDNormalizer()


def _fired(enricher, normalizer, pid: int) -> set:
    raw = json.loads((FIXTURES / f"plant_part_{pid}_raw.json").read_text())
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
    return {
        alert["rule_id"]
        for alert in enriched["interaction_profile"]["ingredient_alerts"]
        if "DANDELION" in alert["rule_id"] or "NETTLE" in alert["rule_id"]
    }


@pytest.mark.parametrize(
    "pid,expected",
    [
        # Nutricost Dandelion Root 1575 mg: "Dandelion root 4:1 extract" (IQM)
        (223501, {DANDELION_GLUCOSE}),
        # Milk Thistle X: "Dandelion root extract", the common root spelling
        (229831, {DANDELION_GLUCOSE}),
        # GNC Liver Cleanser: "Dandelion root powder" (botanical dandelion_root)
        (228932, {DANDELION_GLUCOSE}),
        # OLLY Beat The Bloat: "Dandelion Leaf Extract"
        (315977, {DANDELION_DIURETIC, DANDELION_GLUCOSE}),
        # BulkSupplements Stinging Nettle Root Extract 1000 mg: the blood-pressure
        # evidence covers the root (PMID 12020933), the glucose trial does not
        (330073, {NETTLE_BP}),
        # GNC Mega Men Staminol: "Nettle leaf powder" (botanical nettle_leaf)
        (228119, {NETTLE, NETTLE_BP}),
    ],
)
def test_claims_follow_the_labelled_plant_part(enricher, normalizer, pid, expected):
    assert _fired(enricher, normalizer, pid) == expected


def _profile(enricher, row: dict) -> set:
    product = {
        "dsld_id": "TEST_PLANT_PART",
        "product_name": "test",
        "ingredient_quality_data": {"ingredients_scorable": [row], "ingredients": [row]},
    }
    alerts = enricher._collect_interaction_profile(product)["ingredient_alerts"]
    return {alert["rule_id"] for alert in alerts}


@pytest.mark.parametrize(
    "form_id,form_match_status,expected",
    [
        ("dandelion root", "mapped", {DANDELION_GLUCOSE}),
        ("dandelion leaf", "mapped", {DANDELION_DIURETIC, DANDELION_GLUCOSE}),
        ("dandelion extract", "mapped", {DANDELION_DIURETIC, DANDELION_GLUCOSE}),
        # No confirmed part: the leaf claims still fire.
        ("dandelion root", "n/a", {DANDELION_DIURETIC, DANDELION_GLUCOSE}),
        (None, "n/a", {DANDELION_DIURETIC, DANDELION_GLUCOSE}),
    ],
)
def test_an_unconfirmed_part_fails_open(enricher, form_id, form_match_status, expected):
    row = {
        "name": "Dandelion", "raw_source_text": "Dandelion", "standard_name": "Dandelion",
        "canonical_id": "dandelion", "canonical_source_db": "ingredient_quality_map",
        "form_id": form_id, "form_match_status": form_match_status,
        "quantity": 500.0, "unit": "mg", "unit_normalized": "mg",
    }
    assert _profile(enricher, row) == expected


def test_every_twin_of_a_part_scoped_parent_declares_its_part():
    from identity.interaction import BOTANICAL_INTERACTION_TWIN, BOTANICAL_INTERACTION_TWIN_FORM

    iqm = json.loads((SCRIPTS / "data" / "ingredient_quality_map.json").read_text())
    rules = json.loads((SCRIPTS / "data" / "ingredient_interaction_rules.json").read_text())
    scoped = {
        rule["subject_ref"]["canonical_id"]
        for rule in rules["interaction_rules"]
        if rule.get("form_scope") and rule["subject_ref"]["db"] == "ingredient_quality_map"
    }
    for botanical_id, parent in BOTANICAL_INTERACTION_TWIN.items():
        if parent in scoped:
            assert botanical_id in BOTANICAL_INTERACTION_TWIN_FORM, botanical_id
    for botanical_id, form in BOTANICAL_INTERACTION_TWIN_FORM.items():
        parent = BOTANICAL_INTERACTION_TWIN[botanical_id]
        assert form in iqm[parent]["forms"], (botanical_id, form)


def test_dandelion_part_forms_score_like_the_whole_plant_form():
    """The split exists for interaction scope only: a part form carries exactly
    the whole-plant form's scoring fields, so no product score moves."""
    forms = json.loads((SCRIPTS / "data" / "ingredient_quality_map.json").read_text())["dandelion"]["forms"]
    fields = ("bio_score", "absorption", "absorption_structured", "dosage_importance")
    whole = {field: forms["dandelion extract"].get(field) for field in fields}
    for part in ("dandelion root", "dandelion leaf"):
        assert {field: forms[part].get(field) for field in fields} == whole, part


@pytest.mark.parametrize("mode,flagged", [("fail_open", False), ("all", False), ("fail-open", True), ("confirmed", True)])
def test_the_integrity_check_rejects_an_unknown_form_scope_match(mode, flagged):
    """A misspelt mode falls back to the default match, which silences an
    unknown part: the opposite of fail-open."""
    from db_integrity_sanity_check import check_ingredient_interaction_rules

    rules = json.loads((SCRIPTS / "data" / "ingredient_interaction_rules.json").read_text())
    rule = next(r for r in rules["interaction_rules"] if r["id"] == NETTLE)
    findings: list = []
    check_ingredient_interaction_rules(findings, {"interaction_rules": [dict(rule, form_scope_match=mode)]}, "rules")
    assert any(f.path.endswith(".form_scope_match") for f in findings) is flagged
