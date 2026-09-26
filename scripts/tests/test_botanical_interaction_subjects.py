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
import re
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

MARKER_OR_SOURCE = "a source of the parent's compound or nutrient, not the same ingredient"
TEA_LEAF = (
    "tea leaf; canonical_equivalences.json records green_tea as broader than "
    "green_tea_extract, and theanine is a leaf constituent"
)
# Same-species candidates that must not inherit the parent's rules.
REVIEWED_NOT_TWINNED = {
    # The dandelion rule's diuretic, kidney and lithium claims rest on leaf
    # evidence (PMID 19678785, Taraxacum officinale folium); its glucose claims
    # cite root. IQM dandelion's only form already aliases "dandelion root", so
    # whether root carries the rule is a clinical-policy question.
    ("dandelion_root", "dandelion"): "part: the rule mixes leaf and root evidence",
    # The nettle rule's glucose claims cite leaf extract trials; root is a
    # different preparation (lectins, sterols; BPH use).
    ("nettle_root", "stinging_nettle"): "part: the rule's glucose evidence is leaf",
    ("elder_blossom", "elderberry"): "part: flower, the rule is on the fruit",
    ("elder_flower", "elderberry"): "part: flower, the rule is on the fruit",
    ("dgl_deglycyrrhizinated_licorice", "licorice"): "preparation: the rule excludes DGL",
    ("bergamot_essential_oil", "citrus_bergamot"): "preparation: essential oil, not fruit extract",
    ("chamomile_essential_oil", "chamomile"): "preparation: essential oil, not flower extract",
    ("vitex", "chasteberry"): "species: aliases name V. negundo and V. trifolia",
    ("amla_fruit", "chromium"): MARKER_OR_SOURCE,
    ("coleus_forskohlii_root", "forskolin"): MARKER_OR_SOURCE,
    ("japanese_knotweed", "resveratrol"): MARKER_OR_SOURCE,
    ("toothed_clubmoss", "huperzine_a"): MARKER_OR_SOURCE,
    ("turmeric", "curcumin"): MARKER_OR_SOURCE,
    ("turmeric_root_powder", "curcumin"): MARKER_OR_SOURCE,
    ("wheat_germ", "vitamin_e"): MARKER_OR_SOURCE,
    ("wheat_germ_oil", "vitamin_e"): MARKER_OR_SOURCE,
    ("wheatgrass_powder", "vitamin_e"): MARKER_OR_SOURCE,
    ("l_theanine", "green_tea_extract"): MARKER_OR_SOURCE,
    **{
        (tea, parent): TEA_LEAF
        for tea in (
            "black_tea_leaf", "green_tea", "green_tea_leaf", "matcha_tea_powder",
            "oolong_tea_leaf", "pu_erh_tea_leaf",
        )
        for parent in ("green_tea_extract", "l_theanine")
    },
}


def _botanicals() -> dict:
    rows = json.loads((DATA / "botanical_ingredients.json").read_text())["botanical_ingredients"]
    return {row["id"]: row for row in rows}


def _iqm() -> dict:
    return json.loads((DATA / "ingredient_quality_map.json").read_text())


def _unii(entry: dict):
    return (entry.get("external_ids") or {}).get("unii")


def _binomial(latin_name):
    match = re.match(r"\s*([A-Z][a-z]+)\s+([a-z][a-z-]+)", latin_name or "")
    if not match or match.group(2) in {"spp", "sp"}:
        return None
    return f"{match.group(1)} {match.group(2)}".lower()


def _names_species(iqm_entry: dict, binomial: str) -> bool:
    """The IQM parent names the species in its own aliases, forms or notes."""
    parts = [iqm_entry.get("standard_name"), iqm_entry.get("notes"), *(iqm_entry.get("aliases") or [])]
    for form_name, form in (iqm_entry.get("forms") or {}).items():
        parts += [form_name, form.get("notes"), *(form.get("aliases") or [])]
    text = " ".join(str(part) for part in parts if part).lower()
    return bool(re.search(r"\b" + re.escape(binomial) + r"\b", text))


def _enrich_fixture(pid: int) -> dict:
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    raw = json.loads((FIXTURES / f"botanical_twin_{pid}_raw.json").read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    return enriched


@pytest.mark.parametrize(
    "pid,canonical_id,rule_id,parent_tag",
    [
        (184004, "garlic_bulb", "RULE_INGREDIENT_GARLIC", "garlic"),
        (311160, "black_garlic", "RULE_INGREDIENT_GARLIC", "garlic"),
        # 100 mg yerba mate leaf extract in GNC Herbal Plus Energy Formula
        (74529, "yerba_mate_leaf", "RULE_IQM_YERBA_MATE_CARDIOVASCULAR", "yerba_mate"),
    ],
)
def test_botanical_label_carries_its_iqm_twin_rule(pid, canonical_id, rule_id, parent_tag):
    enriched = _enrich_fixture(pid)
    alerts = [
        alert for alert in enriched["interaction_profile"]["ingredient_alerts"]
        if alert["rule_id"] == rule_id
    ]
    assert len(alerts) == 1, f"{pid}: {len(alerts)} {rule_id} alerts"
    assert alerts[0]["subject_ref"] == {"db": "botanical_ingredients", "canonical_id": canonical_id}
    assert "anticoagulants" in enriched["interaction_profile"]["drug_class_summary"]

    from build_final_db import classify_product_categories

    tags = classify_product_categories(enriched)["key_ingredient_tags"]
    assert canonical_id in tags and parent_tag in tags


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
    """Same substance by GSRS UNII, or a species the IQM parent itself names."""
    from identity.interaction import BOTANICAL_INTERACTION_TWIN

    botanicals, iqm = _botanicals(), _iqm()
    for botanical_id, iqm_id in BOTANICAL_INTERACTION_TWIN.items():
        assert botanical_id in botanicals, botanical_id
        assert iqm_id in iqm and not iqm_id.startswith("_"), iqm_id
        # Catalog tags carry no registry, so a renamed twin must not be an IQM id.
        assert botanical_id == iqm_id or botanical_id not in iqm, botanical_id
        row, parent = botanicals[botanical_id], iqm[iqm_id]
        binomial = _binomial(row.get("latin_name"))
        shared_unii = _unii(row) and _unii(row) == _unii(parent)
        assert shared_unii or (binomial and _names_species(parent, binomial)), botanical_id
    for pair in REVIEWED_NOT_TWINNED:
        assert BOTANICAL_INTERACTION_TWIN.get(pair[0]) != pair[1], pair


def test_every_botanical_record_of_a_ruled_iqm_parent_is_reviewed():
    """A botanical sharing the id, UNII or species of a parent with rules needs a decision."""
    from identity.interaction import BOTANICAL_INTERACTION_TWIN

    botanicals, iqm = _botanicals(), _iqm()
    ruled = {
        rule["subject_ref"]["canonical_id"]
        for rule in _rules()
        if rule["subject_ref"]["db"] == IQM
    }
    unreviewed = []
    for iqm_id in sorted(ruled):
        parent = iqm.get(iqm_id) or {}
        twin_species = {
            _binomial(botanicals[b].get("latin_name"))
            for b, target in BOTANICAL_INTERACTION_TWIN.items()
            if target == iqm_id
        } - {None}
        for botanical_id, row in botanicals.items():
            binomial = _binomial(row.get("latin_name"))
            candidate = (
                botanical_id == iqm_id
                or (_unii(parent) and _unii(row) == _unii(parent))
                or (binomial and (binomial in twin_species or _names_species(parent, binomial)))
            )
            if not candidate or BOTANICAL_INTERACTION_TWIN.get(botanical_id) == iqm_id:
                continue
            if (botanical_id, iqm_id) not in REVIEWED_NOT_TWINNED:
                unreviewed.append((botanical_id, iqm_id))
    assert unreviewed == []
