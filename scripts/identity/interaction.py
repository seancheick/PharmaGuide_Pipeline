from __future__ import annotations

import re
from typing import Any


# The app joins catalog products to curated interaction rows through
# key_ingredient_tags. These tags must represent clean ingredient identity;
# regulatory posture is carried by verdict/safety fields and warnings.
INTERACTION_CANONICAL_ALIASES: dict[str, str] = {
    "BANNED_RED_YEAST_RICE": "red_yeast_rice",
    "banned_red_yeast_rice": "red_yeast_rice",
    "BANNED_CBD_US": "cbd",
    "banned_cbd_us": "cbd",
    "NOOTROPIC_VINPOCETINE": "vinpocetine",
    # Kava is canonicalized to its active-compound id `kavalactones` (used by
    # DSI_SEDATIVES_KAVA, the ingredient_interaction_rules.json subject, and
    # the catalog key_ingredient_tags). Normalize the risk-flavored
    # SSI_KAVA_ACETAMINOPHEN id onto it so both kava interactions join the
    # same product identity.
    "RISK_KAVA": "kavalactones",
    "risk_kava": "kavalactones",
    # Red yeast rice has two safety rules -- BANNED_RED_YEAST_RICE for declared
    # monacolin K / lovastatin, RISK_RED_YEAST_RICE for the generic botanical --
    # and both carry CUI C0763533, so a CUI or name lookup can land on either.
    # Only the banned id was normalized, so DSI_STATINS_RYR built with
    # `RISK_RED_YEAST_RICE` as its supplement identity and orphaned itself
    # against the `red_yeast_rice` allowlist entry that exists for it. The
    # shipped artifact carries `red_yeast_rice`; this restores that.
    "RISK_RED_YEAST_RICE": "red_yeast_rice",
    "risk_red_yeast_rice": "red_yeast_rice",
}

INTERACTION_TEXT_TAG_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\b(red\s+yeast\s+rice|monascus\s+purpureus|monacolin\s+k)\b",
            re.I,
        ),
        "red_yeast_rice",
    ),
    (re.compile(r"\b(cbd|cannabidiol)\b", re.I), "cbd"),
    (re.compile(r"\bvinpocetine\b", re.I), "vinpocetine"),
)


# Interaction subject family: an identity that answers to every interaction
# authored on its family as well as its own. Vitamin K1 and K2 are vitamers of
# vitamin K, and every vitamin K interaction (warfarin antagonism) is authored
# on `vitamin_k`; the 2026-07-28 identity split left them matching nothing.
# This is narrower than the IQM display group on purpose: beta-carotene rolls
# up to vitamin A for display but is a provitamin, not a vitamer, and must not
# inherit preformed-retinol interactions. Members must match the IQM
# `nutrient_group_id` (pinned by test_vitamin_k_interaction_subject.py).
INTERACTION_SUBJECT_FAMILY: dict[str, str] = {
    "vitamin_k1": "vitamin_k",
    "vitamin_k2": "vitamin_k",
}


# Botanical twin: a botanical_ingredients or standardized_botanicals identity
# that is the same species and plant part as an IQM parent answers to the
# interactions authored on that
# parent (RULE_INGREDIENT_GARLIC is authored on IQM `garlic`, so 320 mg of
# `garlic_bulb` warned about nothing). Interaction lookup only: scoring keeps
# the botanical identity. Each pair shares a GSRS UNII or is a species the IQM
# parent names. Same-species records left out (a marker or nutrient source,
# another part or preparation) are listed with their reasons in
# test_botanical_interaction_subjects.py, which requires a decision for every
# candidate.
BOTANICAL_INTERACTION_TWIN: dict[str, str] = {
    "aloe_vera": "aloe_vera",
    "aloe_vera_concentrated_gel": "aloe_vera",
    "american_ginseng": "ginseng",
    "american_ginseng_std": "ginseng",
    "andrographis": "andrographis",
    "ashwagandha": "ashwagandha",
    "ashwagandha_root": "ashwagandha",
    "astragalus_extract": "astragalus",
    "astragalus_root": "astragalus",
    "bacopa": "bacopa",
    "berberine": "berberine_supplement",
    "bitter_melon_fruit": "bitter_melon",
    "black_cohosh": "black_cohosh",
    "black_garlic": "garlic",
    "boswellia_serrata_resin": "boswellia",
    "cat_s_claw_bark": "cat_s_claw",
    "ceylon_cinnamon": "cinnamon",
    "chamomile": "chamomile",
    "chaste_tree": "chasteberry",
    "cinnamon": "cinnamon",
    "cinnamon_bark": "cinnamon",
    "citrus_bergamot": "citrus_bergamot",
    "citrus_bergamot_extract": "citrus_bergamot",
    "cordyceps": "cordyceps",
    "cordyceps_militaris": "cordyceps",
    "cordyceps_mushroom_powder": "cordyceps",
    "cran_max": "cranberry",
    "cranberry": "cranberry",
    "cranberry_fruit": "cranberry",
    "cranrx": "cranberry",
    "dandelion": "dandelion",
    "dandelion_root": "dandelion",
    "devil_s_claw": "devils_claw",
    "devils_claw_tuber": "devils_claw",
    "dong_quai": "dong_quai",
    "echinacea_angustifolia": "echinacea",
    "echinacea_extract": "echinacea",
    "echinacea_purpurea": "echinacea",
    "echinacea_purpurea_aerial": "echinacea",
    "echinacea_purpurea_herb": "echinacea",
    "echinacea_purpurea_root_extract": "echinacea",
    "elderberries": "elderberry",
    "evening_primrose": "evening_primrose_oil",
    "evening_primrose_seed_oil": "evening_primrose_oil",
    "fenugreek_seed": "fenugreek",
    "feverfew": "feverfew",
    "flaxseed": "flaxseed",
    "flowens": "cranberry",
    "garlic_bulb": "garlic",
    "garlic_std": "garlic",
    "ginger_extract": "ginger",
    "ginger_root": "ginger",
    "ginkgo_biloba": "ginkgo",
    "ginkgo_biloba_leaf": "ginkgo",
    "ginseng_root_panax": "ginseng",
    "goldenseal": "goldenseal",
    "gotu_kola": "gotu_kola",
    "gymnema_sylvestre": "gymnema_sylvestre",
    "hawthorn_flowering_tops": "hawthorn",
    "holy_basil_leaf": "holy_basil",
    "huperzine_a": "huperzine_a",
    "ksm_66_ashwagandha": "ashwagandha",
    "l_theanine": "l_theanine",
    "licorice_root": "licorice",
    "lion_s_mane": "lions_mane",
    "lions_mane_mushroom_powder": "lions_mane",
    "maca_root": "maca",
    "microactive_melatonin": "melatonin",
    "milk_thistle": "milk_thistle",
    "milk_thistle_seed": "milk_thistle",
    "nettle": "stinging_nettle",
    "nettle_leaf": "stinging_nettle",
    "nettle_root": "stinging_nettle",
    "nigella": "black_seed_oil",
    "olive_leaf_extract": "olive_leaf",
    "olive_leaf_powder": "olive_leaf",
    "pacran": "cranberry",
    "panax_ginseng": "ginseng",
    "passion_flower": "passionflower",
    "passionflower_herb": "passionflower",
    "psyllium_husk": "psyllium",
    "red_clover": "red_clover",
    "red_clover_flower": "red_clover",
    "reishi_mushroom": "reishi",
    "rhodiola_rosea_root": "rhodiola",
    "sage_leaf_extract": "sage",
    "saw_palmetto_berry": "saw_palmetto",
    "slimbione": "bitter_melon",
    "st_john_s_wort": "st_johns_wort",
    "tribulus_terrestris": "tribulus",
    "turmeric": "turmeric",
    "turmeric_root_powder": "turmeric",
    "valerian_root": "valerian",
    "white_willow_bark": "white_willow_bark",
    "wild_yam_root": "wild_yam",
    "yerba_mate_leaf": "yerba_mate",
}


# The IQM form a twin is, for parents whose rules are scoped by plant part
# (dandelion leaf diuresis, nettle leaf glucose; Sean, 2026-09-26). Every twin
# of a parent with a form-scoped rule declares one.
BOTANICAL_INTERACTION_TWIN_FORM: dict[str, str] = {
    "dandelion": "dandelion extract",
    "dandelion_root": "dandelion root",
    "nettle": "stinging nettle (unspecified)",
    "nettle_leaf": "stinging nettle leaf extract",
    "nettle_root": "stinging nettle root extract",
}


def interaction_twin_form(source_db: Any, canonical_id: Any) -> str | None:
    """The IQM form a botanical row (by its canonical_source_db) stands for."""
    if str(source_db or "").strip() not in ("botanical_ingredients", "standardized_botanicals"):
        return None
    return BOTANICAL_INTERACTION_TWIN_FORM.get(str(canonical_id or "").strip())

def _family_ids(canonical: str) -> list[str]:
    family = INTERACTION_SUBJECT_FAMILY.get(canonical)
    return [canonical, family] if family and family != canonical else [canonical]


def interaction_subject_refs(db: Any, canonical_id: Any) -> list[tuple[str, str]]:
    """Every (registry, id) interaction subject a resolved row answers to."""
    source_db = str(db or "").strip()
    canonical = str(canonical_id or "").strip()
    if not source_db or not canonical:
        return []
    if source_db == "ingredient_quality_map":
        refs = [(source_db, subject_id) for subject_id in _family_ids(canonical)]
    else:
        refs = [(source_db, canonical)]
    # A standardized botanical has no interaction registry of its own and keeps
    # an IQM subject, so its twin is looked up from there too.
    twin = (
        BOTANICAL_INTERACTION_TWIN.get(canonical)
        if source_db in ("ingredient_quality_map", "botanical_ingredients")
        else None
    )
    if twin:
        refs += [("ingredient_quality_map", subject_id) for subject_id in _family_ids(twin)]
    return list(dict.fromkeys(refs))


def interaction_subject_ids(canonical_id: Any) -> list[str]:
    """Every interaction subject an identity answers to: itself, its family, its IQM twin.

    Catalog tags carry no registry; a renamed twin id is never an IQM id.
    """
    canonical = str(canonical_id or "").strip()
    if not canonical:
        return []
    twin = BOTANICAL_INTERACTION_TWIN.get(canonical)
    ids = _family_ids(canonical) + (_family_ids(twin) if twin else [])
    return list(dict.fromkeys(ids))


# Units that record "no amount given" rather than a measured amount.
_NO_AMOUNT_UNITS = frozenset({"", "unspecified", "not provided", "unknown", "n/a", "na"})
# Outside a blend DSLD writes "0 NP" both for a nutrition-panel "0%" line and for
# an ingredient listed without an amount; the printed %DV tells them apart, and
# the cleaner keeps it as dailyValue: 0.0 for a printed 0%, None for no percent
# (register Q23). Raw corpus 2026-09-26: 141 "0 NP" vitamin/mineral rows print
# 0%, 18 print no percent (Vitamin B12 8, sodium 4).


def label_row_is_blend_child(row: dict) -> bool:
    """A row listed inside a blend (DSLD nestedRows or form children)."""
    path = str(row.get("raw_source_path") or row.get("source_path") or "").lower()
    return (
        row.get("cleaner_row_role") == "nested_display_only"
        or "nestedrows" in path
        or "child_ingredients" in path
    )


def label_row_establishes_presence(row: dict) -> bool:
    """Whether a label row shows the ingredient is in the product.

    A positive amount, a printed %DV above 0 (the cleaner's
    daily_value_no_amount role), a listing inside a blend, or a listing with no
    amount establish it. A measured zero ("Iron 0 mg", "Vitamin D 0 mcg", "0%",
    "Not Present", "0 NP" printed as 0% DV) does not. Presence says nothing
    about the amount: dose rules still read the row's own quantity (Sean,
    D1/D1c, 2026-09-26).
    """
    try:
        quantity = float(row.get("quantity"))
    except (TypeError, ValueError):
        quantity = None
    unit = str(row.get("unit") or "").strip().lower()
    if quantity is not None and quantity > 0 and unit not in _NO_AMOUNT_UNITS | {"np"}:
        return True
    if row.get("cleaner_row_role") == "daily_value_no_amount" or label_row_is_blend_child(row):
        return True
    if unit == "np":
        return row.get("dailyValue") is None
    return unit in _NO_AMOUNT_UNITS


def interaction_identity(canonical_id: Any) -> str | None:
    """The broadest subject an identity answers to (garlic_bulb -> garlic,
    vitamin_k2 -> vitamin_k): one plant or nutrient, one interaction card."""
    ids = interaction_subject_ids(canonical_id)
    return ids[-1] if ids else None

def normalize_interaction_canonical_id(value: Any) -> str | None:
    """Return the catalog-facing canonical used for interaction lookup."""
    if value is None:
        return None
    canonical = str(value).strip()
    if not canonical:
        return None
    return INTERACTION_CANONICAL_ALIASES.get(canonical, canonical)


def normalize_catalog_interaction_tag(value: Any) -> str | None:
    """Normalize a product-side ingredient tag for interaction lookup."""
    canonical = normalize_interaction_canonical_id(
        str(value or "").lower().replace(" ", "_")
    )
    return canonical or None


def interaction_tags_from_text(*values: Any) -> list[str]:
    text = " ".join(str(v) for v in values if str(v or "").strip())
    if not text:
        return []
    return [
        canonical_id
        for pattern, canonical_id in INTERACTION_TEXT_TAG_PATTERNS
        if pattern.search(text)
    ]
