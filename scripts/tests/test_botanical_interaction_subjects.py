"""A resolved row answers to the interaction rules of the registry that owns it.

The enricher projects a recognized botanical or other-ingredient identity onto
its row as canonical_id + canonical_source_db (garlic_bulb /
botanical_ingredients). The interaction lookup read only canonical_id and
stamped every such row as an IQM subject, so a non-scorable botanical row was
dropped as an IQM blend child and never met the rules authored on its own
registry: licorice root, ginkgo leaf, blue cohosh, rue and the other
botanical-subject rules only fired for rows that had lost their canonical_id.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

DATA = SCRIPTS / "data"
IQM = "ingredient_quality_map"


def _rules() -> list:
    return json.loads((DATA / "ingredient_interaction_rules.json").read_text())["interaction_rules"]


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3

    return SupplementEnricherV3()


def _resolved_row(canonical_id: str, source_db: str) -> dict:
    """The fields the enricher stamps on a recognized non-scorable row."""
    return {
        "name": canonical_id,
        "raw_source_text": canonical_id,
        "standard_name": canonical_id,
        "canonical_id": canonical_id,
        "canonical_id_after": canonical_id,
        "canonical_source_db": source_db,
        "recognition_source": source_db,
        "recognized_entry_id": canonical_id,
        "matched_entry_id": canonical_id,
        "recognized_non_scorable": True,
        "scoreable_identity": False,
        "quantity": 500.0,
        "unit": "mg",
        "unit_normalized": "mg",
    }


def _fired(enricher, row: dict) -> set:
    product = {
        "dsld_id": "TEST_REGISTRY_SUBJECT",
        "product_name": "test",
        "ingredient_quality_data": {"ingredients_scorable": [], "ingredients": [row]},
    }
    profile = enricher._collect_interaction_profile(product)
    return {alert["rule_id"] for alert in profile.get("ingredient_alerts") or []}


@pytest.mark.parametrize(
    "rule_id,canonical_id,source_db",
    [
        (rule["id"], rule["subject_ref"]["canonical_id"], rule["subject_ref"]["db"])
        for rule in _rules()
        if rule["subject_ref"]["db"] in {"botanical_ingredients", "other_ingredients"}
    ],
)
def test_rule_on_a_non_iqm_registry_reaches_a_row_resolved_to_it(
    enricher, rule_id, canonical_id, source_db
):
    assert rule_id in _fired(enricher, _resolved_row(canonical_id, source_db))


@pytest.mark.parametrize("source_db", [None, "", IQM, "standardized_botanicals", "probiotic_data"])
def test_iqm_and_unroutable_registries_keep_the_iqm_subject(enricher, source_db):
    row = {"canonical_id": "turmeric", "canonical_source_db": source_db}
    assert enricher._derive_interaction_subject_ref(row) == {"db": IQM, "canonical_id": "turmeric"}


def test_botanical_row_is_a_botanical_subject(enricher):
    row = _resolved_row("garlic_bulb", "botanical_ingredients")
    assert enricher._derive_interaction_subject_ref(row) == {
        "db": "botanical_ingredients",
        "canonical_id": "garlic_bulb",
    }


@pytest.mark.parametrize(
    "row",
    [
        _resolved_row("licorice_root", "botanical_ingredients"),
        {
            "name": "CBD",
            "canonical_id": None,
            "recognition_source": "banned_recalled_ingredients",
            "recognized_entry_id": "BANNED_CBD_US",
            "quantity": 25.0,
            "unit": "mg",
        },
    ],
)
def test_a_row_listed_in_two_buckets_is_scanned_once(enricher, row):
    """The enricher lists one non-scorable row object in both ingredients and
    ingredients_skipped; scanning both copies doubled every alert."""
    product = {
        "dsld_id": "TEST_SCAN_ONCE",
        "product_name": "test",
        "ingredient_quality_data": {
            "ingredients_scorable": [],
            "ingredients": [row],
            "ingredients_skipped": [row],
        },
    }
    alerts = enricher._collect_interaction_profile(product)["ingredient_alerts"]
    assert alerts and len(alerts) == len({alert["rule_id"] for alert in alerts})


# ---------------------------------------------------------------------------
# Botanical twin: a botanical identity that is the same plant and part as an
# IQM parent answers to the rules authored on that parent. Before the twin,
# 184004 Artery Advantage (320 mg garlic bulb extract) and 311160 Black Garlic
# Extract shipped with no garlic warning because RULE_INGREDIENT_GARLIC is
# authored on (ingredient_quality_map, garlic).

FIXTURES = Path(__file__).parent / "fixtures"

# Pairs whose botanical and IQM records do not share a GSRS UNII, verified by
# species and part against GSRS and the rule text instead.
VERIFIED_WITHOUT_SHARED_UNII = {
    "aloe_vera": "Aloe vera leaf (GSRS ZY81Z83H0X); the rule covers oral leaf gel/latex",
    "american_ginseng": "P. quinquefolius root (GSRS 8W75VCV53Q); the IQM parent carries an "
    "American ginseng form and the rule names American ginseng",
    "andrographis": "Andrographis paniculata aerial parts on both records",
    "ashwagandha": "Withania somnifera on both records",
    "bacopa": "Bacopa monnieri (IQM GSRS DUB5K84ELI) on both records",
    "boswellia_serrata_resin": "B. serrata oleo-gum resin (GSRS 4PW41QCO2M), the boswellic "
    "acid source the rule describes; IQM carries a resin form",
    "citrus_bergamot": "Citrus bergamia fruit on both records",
    "cordyceps": "Cordyceps militaris; the IQM parent carries a militaris form and the rule "
    "names C. sinensis/militaris",
    "dong_quai": "Angelica sinensis root (GSRS B66F4574UG); IQM forms are root",
    "flaxseed": "Linum usitatissimum seed (GSRS 310OJT00CG); IQM forms are oil and meal",
    "gotu_kola": "Centella asiatica aerial parts (GSRS 7M867G6T1U) on both records",
    "gymnema_sylvestre": "Gymnema sylvestre leaf (GSRS 2ZK6ZS8392); IQM forms are leaf",
    "lion_s_mane": "Hericium erinaceus (GSRS Y62T8P9AAP); the rule names Hericium erinaceus",
    "maca_root": "Lepidium meyenii root (GSRS HP7119212T); IQM forms are root",
}

# Reviewed candidates that must not inherit the parent's rules.
REVIEWED_NOT_TWINNED = {
    # RULE_IQM_DANDELION_KIDNEY's diuretic, kidney and lithium claims rest on
    # leaf evidence (PMID 19678785, Taraxacum officinale folium); a root-only
    # product would inherit them. Root routing is a clinical-policy question.
    "dandelion_root": "dandelion",
}


def _botanicals() -> dict:
    rows = json.loads((DATA / "botanical_ingredients.json").read_text())["botanical_ingredients"]
    return {row["id"]: row for row in rows}


def _iqm() -> dict:
    return json.loads((DATA / "ingredient_quality_map.json").read_text())


def _unii(entry: dict):
    return (entry.get("external_ids") or {}).get("unii")


def _enrich_fixture(pid: int) -> dict:
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    raw = json.loads((FIXTURES / f"botanical_twin_{pid}_raw.json").read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    return enriched


@pytest.mark.parametrize("pid,canonical_id", [(184004, "garlic_bulb"), (311160, "black_garlic")])
def test_botanical_garlic_label_carries_the_garlic_rule(pid, canonical_id):
    enriched = _enrich_fixture(pid)
    alerts = [
        alert for alert in enriched["interaction_profile"]["ingredient_alerts"]
        if alert["rule_id"] == "RULE_INGREDIENT_GARLIC"
    ]
    assert alerts, f"{pid} carries no garlic rule"
    assert {alert["subject_ref"]["canonical_id"] for alert in alerts} == {canonical_id}
    assert "anticoagulants" in enriched["interaction_profile"]["drug_class_summary"]

    from build_final_db import classify_product_categories

    tags = classify_product_categories(enriched)["key_ingredient_tags"]
    assert canonical_id in tags and "garlic" in tags


def test_twin_ids_answer_to_their_iqm_parent():
    from identity.interaction import interaction_subject_ids, interaction_subject_refs

    assert interaction_subject_ids("garlic_bulb") == ["garlic_bulb", "garlic"]
    assert interaction_subject_ids("turmeric") == ["turmeric"]
    assert interaction_subject_refs("botanical_ingredients", "garlic_bulb") == [
        ("botanical_ingredients", "garlic_bulb"),
        (IQM, "garlic"),
    ]
    assert interaction_subject_refs(IQM, "vitamin_k2") == [(IQM, "vitamin_k2"), (IQM, "vitamin_k")]
    assert interaction_subject_refs("other_ingredients", "garlic_bulb") == [
        ("other_ingredients", "garlic_bulb")
    ]


def test_every_twin_is_a_verified_same_plant_pair():
    from identity.interaction import BOTANICAL_INTERACTION_TWIN

    botanicals, iqm = _botanicals(), _iqm()
    for botanical_id, iqm_id in BOTANICAL_INTERACTION_TWIN.items():
        assert botanical_id in botanicals, botanical_id
        assert iqm_id in iqm and not iqm_id.startswith("_"), iqm_id
        # Catalog tags carry no registry, so a renamed twin must not be an IQM id.
        assert botanical_id == iqm_id or botanical_id not in iqm, botanical_id
        shared = _unii(botanicals[botanical_id]) and _unii(botanicals[botanical_id]) == _unii(iqm[iqm_id])
        assert shared or botanical_id in VERIFIED_WITHOUT_SHARED_UNII, botanical_id
    for botanical_id, iqm_id in REVIEWED_NOT_TWINNED.items():
        assert BOTANICAL_INTERACTION_TWIN.get(botanical_id) != iqm_id, botanical_id


def test_every_botanical_record_of_a_ruled_iqm_parent_is_reviewed():
    """A same-id or same-UNII botanical record of a parent with rules needs a decision."""
    from identity.interaction import BOTANICAL_INTERACTION_TWIN

    botanicals, iqm = _botanicals(), _iqm()
    ruled = {
        rule["subject_ref"]["canonical_id"]
        for rule in _rules()
        if rule["subject_ref"]["db"] == IQM
    }
    unreviewed = []
    for iqm_id in sorted(ruled):
        parent_unii = _unii(iqm.get(iqm_id) or {})
        for botanical_id, row in botanicals.items():
            if botanical_id != iqm_id and not (parent_unii and _unii(row) == parent_unii):
                continue
            if BOTANICAL_INTERACTION_TWIN.get(botanical_id) == iqm_id:
                continue
            if REVIEWED_NOT_TWINNED.get(botanical_id) == iqm_id:
                continue
            unreviewed.append((botanical_id, iqm_id))
    assert unreviewed == []
