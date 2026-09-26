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


@pytest.mark.parametrize(
    "canonical_id,source_db,expected_db",
    [
        # The identity decision rewrote the id and left the registry behind.
        ("reishi", "botanical_ingredients", IQM),
        ("strawberry", "other_ingredients", "botanical_ingredients"),
        ("NHA_CHILI_PEPPER", "botanical_ingredients", "other_ingredients"),
        ("garlic_bulb", "botanical_ingredients", "botanical_ingredients"),
    ],
)
def test_a_registry_that_does_not_hold_the_id_is_not_its_subject(
    enricher, canonical_id, source_db, expected_db
):
    row = {"canonical_id": canonical_id, "canonical_source_db": source_db}
    assert enricher._derive_interaction_subject_ref(row) == {"db": expected_db, "canonical_id": canonical_id}


def test_stale_registry_blend_member_keeps_its_iqm_rules():
    """210555 GNC AMP Test 1700 lists "Reishi Mushroom powder" in a blend; its
    row carries the IQM id reishi under a stale botanical registry and met no
    reishi rule."""
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    raw = json.loads((Path(__file__).parent / "fixtures" / "stale_registry_210555_raw.json").read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    fired = {alert["rule_id"] for alert in enriched["interaction_profile"]["ingredient_alerts"]}
    assert "RULE_INGREDIENT_REISHI__AUTOIMMUNE" in fired

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
    ("elder_blossom", "elderberry"): "part: flower, the rule is on the fruit",
    ("elder_flower", "elderberry"): "part: flower, the rule is on the fruit",
    ("dgl_deglycyrrhizinated_licorice", "licorice"): "preparation: the rule excludes DGL",
    ("bergamot_essential_oil", "citrus_bergamot"): "preparation: essential oil, not fruit extract",
    ("chamomile_essential_oil", "chamomile"): "preparation: essential oil, not flower extract",
    ("vitex", "chasteberry"): "species: aliases name V. negundo and V. trifolia",
    ("cinnamon_bark_essential_oil", "cinnamon"): "preparation: essential oil, not bark extract",
    ("olive_fruit", "olive_leaf"): "part: fruit, the rule's evidence is leaf extract",
    ("coleus_forskohlii", "forskolin"): MARKER_OR_SOURCE,
    ("barberry_root", "berberine_supplement"): MARKER_OR_SOURCE,
    ("triphala_powder", "chromium"): MARKER_OR_SOURCE,
    ("wheat_barley_grass_blend", "vitamin_e"): MARKER_OR_SOURCE,
    # The record's UNII is CI 75300 (curcumin) but TurmiPure Gold is a turmeric
    # extract with unknown markers; the record needs correcting first.
    ("turmipure_gold", "curcumin"): "identity: record UNII is curcumin, brand is a turmeric extract",
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


def _standardized() -> dict:
    rows = json.loads((DATA / "standardized_botanicals.json").read_text())["standardized_botanicals"]
    return {row["id"]: row for row in rows}


def _record_species(row: dict, known: set) -> set:
    """A botanical record's species: its latin name, else the known binomials its
    own name, aliases and notes spell (standardized records carry no latin name)."""
    binomial = _binomial(row.get("latin_name"))
    if binomial:
        return {binomial}
    text = " ".join(
        str(part) for part in [row.get("standard_name"), row.get("notes"), *(row.get("aliases") or [])] if part
    ).lower()
    return {name for name in known if re.search(r"\b" + re.escape(name) + r"\b", text)}


def _twin_records() -> tuple[dict, dict]:
    """Every botanical and standardized record by registry, and the known binomials."""
    registries = {"botanical_ingredients": _botanicals(), "standardized_botanicals": _standardized()}
    known = {
        _binomial(row.get("latin_name")) for row in registries["botanical_ingredients"].values()
    } - {None}
    return registries, known


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
    """Same substance by UNII, or a species the IQM parent itself names, in every
    registry (botanical, standardized) that holds the twin's id."""
    from identity.interaction import BOTANICAL_INTERACTION_TWIN

    registries, known = _twin_records()
    iqm = _iqm()
    for twin_id, iqm_id in BOTANICAL_INTERACTION_TWIN.items():
        records = [rows[twin_id] for rows in registries.values() if twin_id in rows]
        assert records, twin_id
        assert iqm_id in iqm and not iqm_id.startswith("_"), iqm_id
        # Catalog tags carry no registry, so a renamed twin must not be an IQM id.
        assert twin_id == iqm_id or twin_id not in iqm, twin_id
        parent = iqm[iqm_id]
        for row in records:
            shared_unii = _unii(row) and _unii(row) == _unii(parent)
            named = any(_names_species(parent, name) for name in _record_species(row, known))
            assert shared_unii or named, twin_id
    for pair in REVIEWED_NOT_TWINNED:
        assert BOTANICAL_INTERACTION_TWIN.get(pair[0]) != pair[1], pair


def test_every_botanical_record_of_a_ruled_iqm_parent_is_reviewed():
    """A botanical or standardized record sharing the id, UNII or species of a
    parent with rules needs a decision (a standardized id that is itself an IQM
    id already meets that parent's rules)."""
    from identity.interaction import BOTANICAL_INTERACTION_TWIN

    registries, known = _twin_records()
    iqm = _iqm()
    ruled = {
        rule["subject_ref"]["canonical_id"]
        for rule in _rules()
        if rule["subject_ref"]["db"] == IQM
    }
    unreviewed = []
    for iqm_id in sorted(ruled):
        parent = iqm.get(iqm_id) or {}
        twin_species = set().union(*(
            _record_species(rows[b], known)
            for rows in registries.values()
            for b, target in BOTANICAL_INTERACTION_TWIN.items()
            if target == iqm_id and b in rows
        ))
        for registry, rows in registries.items():
            for record_id, row in rows.items():
                if registry == "standardized_botanicals" and record_id in iqm:
                    continue
                species = _record_species(row, known)
                candidate = (
                    record_id == iqm_id
                    or (_unii(parent) and _unii(row) == _unii(parent))
                    or bool(species & twin_species)
                    or any(_names_species(parent, name) for name in species)
                )
                if not candidate or BOTANICAL_INTERACTION_TWIN.get(record_id) == iqm_id:
                    continue
                if (record_id, iqm_id) not in REVIEWED_NOT_TWINNED:
                    unreviewed.append((registry, record_id, iqm_id))
    assert unreviewed == []


# ---------------------------------------------------------------------------
# Standardized botanicals. A standardized_botanicals row is not a routable
# interaction registry, so it keeps an IQM subject; an identity that is an IQM
# id already meets its rules. One whose id differs from its IQM parent
# (ginger_extract, garlic_std) met nothing: 231794 Life Extension Optimized
# Garlic (1200 mg garlic extract) carried no garlic warning.


@pytest.mark.parametrize(
    "pid,rule_id,parent_tag",
    [
        (16374, "RULE_IQM_GINGER_BLEEDING", "ginger"),  # GNC Total Cleanser, ginger root extract
        (231794, "RULE_INGREDIENT_GARLIC", "garlic"),  # Life Extension Optimized Garlic
        (201405, "RULE_IQM_STINGING_NETTLE_DIABETES", "stinging_nettle"),  # Solgar Male Multiple
    ],
)
def test_standardized_label_carries_its_iqm_twin_rule(pid, rule_id, parent_tag):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from build_final_db import classify_product_categories

    raw = json.loads((FIXTURES / f"standardized_twin_{pid}_raw.json").read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    fired = [a for a in enriched["interaction_profile"]["ingredient_alerts"] if a["rule_id"] == rule_id]
    assert len(fired) == 1, f"{pid}: {len(fired)} {rule_id} alerts"
    assert parent_tag in classify_product_categories(enriched)["key_ingredient_tags"]
