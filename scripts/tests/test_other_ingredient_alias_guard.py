"""Guards against new alias collisions in inactive/additive reference data.

This is a release-gate test for the exact-collision class of failures behind
recent inactive-ingredient miscanonicalizations:

* alias-vs-alias steals:
    "mixed tocopherols" on both a generic preservative entry and the more
    specific tocopherol preservative entry
* alias-vs-standard steals:
    an alias on one entry exactly matching another entry's canonical
    standard_name, which makes lookup order matter

This test intentionally baselines the current legacy debt and blocks NEW
collisions only. It does not solve chemistry-invalid one-off aliases by
itself; that needs a stronger alias chemistry audit later.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FILES = {
    "other_ingredients": ROOT / "data" / "other_ingredients.json",
    "harmful_additives": ROOT / "data" / "harmful_additives.json",
}


# Baseline exact alias collisions present as of 2026-05-02.
# These are legacy ontology / descriptor overlaps in other_ingredients and
# harmful_additives. The test allows this exact set so the suite passes today,
# but any new collision must be reviewed and cleaned up before merge.
BASELINE_ALIAS_DUPLICATES = {
    "acacia gum",
    "annatto",
    "anthocyanins",
    "aqueous coating",
    "artificial flavor",
    "avicel",
    "beet juice powder",
    "beet powder",
    "beetroot powder",
    "blackstrap molasses",
    "blue #1",
    "blueberry natural flavor",
    "brilliant blue fcf",
    "calcium chloride",
    "cane sugar",
    "carboxymethyl cellulose",
    "carrot juice concentrate",
    "cassava starch",
    "cellulose coating",
    "cellulose gel",
    "cellulose gum",
    "cellulose powder",
    "cellulose, plant",
    "cherry flavor natural",
    "chlorophyllin",
    "cmc",
    "coconut oil, hydrogenated",
    "colloidal silicon dioxide",
    "confectioner's glaze",
    "croscamellose sodium",
    "croscarmellose sodium",
    "crospovidone",
    "d-sorbitol",
    "deionized water",
    "distilled water",
    "e412",
    "e414",
    "e415",
    "e460",
    "e466",
    "e471",
    "e551",
    "e570",
    "e904",
    "e967",
    "explotab",
    "fd&c blue #1",
    "fd&c blue no. 1",
    "fractionated coconut oil",
    "fruit and vegetable concentrates",
    "fruit and vegetable juice",
    "fumed silica",
    "glucose syrup",
    "glyceryl monooleate",
    "glyceryl monostearate",
    "guar gum",
    "gum acacia",
    "gum arabic",
    "hsh",
    "hydrogenated coconut oil",
    "hydrogenated starch hydrolysate",
    "hydroxypropyl methyl cellulose",
    "hydroxypropyl methylcellulose",
    "imo",
    "imo syrup",
    "ionic sea minerals",
    "ionic trace minerals",
    "isomalto-oligosaccharide",
    "isomaltooligosaccharides",
    "kollidon cl",
    "l-arabinose",
    "lac resin",
    "lactitol",
    "macrogol",
    "mag stearate",
    "magnesium stearate",
    "maize oil",
    "maltitol syrup",
    "maltose syrup",
    "manioc starch",
    "mcc",
    "methacrylic acid copolymer",
    "microcrystalline cellulose",
    "mixed berry flavor",
    "modified corn starch",
    "modified food starch",
    "modified starch",
    "molasses",
    "mono and diglycerides",
    "monoglycerides",
    "natural and artificial flavors",
    "natural and artificial orange flavor",
    "natural and organic fruit flavors",
    "natural apple flavor",
    "natural berry flavor",
    "natural berry flavors",
    "natural blueberry flavor",
    "natural cherry flavor",
    "natural cherry flavour",
    "natural chocolate flavor",
    "natural citrus flavors",
    "natural color",
    "natural colors from fruits",
    "natural flavor",
    "natural lemon flavor",
    "natural mint flavor",
    "natural mint oil",
    "natural orange flavor",
    "natural peppermint flavor",
    "natural raspberry flavor",
    "natural strawberry flavor",
    "natural vanilla",
    "natural vanilla flavor",
    "natural vanillin crystals",
    "natural yellow orange coloring",
    "octadecanoic acid",
    "octadecanoic acid magnesium salt",
    "orange flavor, natural",
    "organic cane sugar",
    "organic rice extract",
    "palm stearin",
    "pdx",
    "peg",
    "peppermint flavor natural",
    "pharmaceutical glaze",
    "plant cellulose",
    "plant fiber",
    "plant wax",
    "plant-based lubricant",
    "polyethylene oxide",
    "polyglycitol syrup",
    "polyvinylpyrrolidone",
    "povidone",
    "precipitated silica",
    "primojel",
    "pullulan capsule",
    "pvp",
    "rapeseed oil",
    "raw cane sugar",
    "red beet powder",
    "rice extract",
    "rice hulls",
    "silica gel",
    "silicified microcrystalline cellulose",
    "silicon dioxide",
    "sodium carboxymethyl starch",
    "sodium carboxymethylcellulose",
    "sodium copper chlorophyllin",
    "sorbitol",
    "spice extracts",
    "stearate",
    "stearic acid",
    "stearic acid magnesium salt",
    "strawberry flavor natural",
    "sunfiber",
    "synthetic amorphous silica",
    "tapioca flour",
    "trisodium citrate",
    "unrefined cane sugar",
    "vanilla flavor natural",
    "vanillin crystals",
    "vegetable",
    "vegetable glaze",
    "vegetable magnesium silicate",
    "vegetable magnesium stearate",
    "vegetable stearic acid",
    "vegetable wax",
    "vitamin u",
    "wood sugar",
}

BASELINE_ALIAS_VS_STANDARD_COLLISIONS = {
    "acacia gum",
    "beetroot powder",
    "blackstrap molasses",
    "calcium chloride",
    "cane sugar",
    "caramel color",
    "carboxymethyl cellulose",
    "cellulose gum",
    "croscarmellose sodium",
    "crospovidone",
    "deionized water",
    "fd&c blue #1",
    "fd&c blue no. 1",
    "glyceryl monooleate",
    "guar gum",
    "hydrogenated coconut oil",
    "hydrogenated starch hydrolysate",
    "hydroxypropyl methylcellulose",
    "isomaltooligosaccharides",
    "l-arabinose",
    "magnesium stearate",
    "microcrystalline cellulose",
    "modified food starch",
    "modified starch",
    "mono and diglycerides",
    "natural apple flavor",
    "natural berry flavor",
    "natural berry flavors",
    "natural blueberry flavor",
    "natural chocolate flavor",
    "natural citrus flavor",
    "natural color",
    "natural coloring",
    "natural glaze",
    "natural lemon flavor",
    "natural mint flavor",
    "natural orange flavor",
    "natural strawberry flavor",
    "natural vanilla flavor",
    "palm stearin",
    "polyglycitol syrup",
    "povidone",
    "purified water",
    "rapeseed oil",
    "rice bran extract",
    "shellac",
    "silicon dioxide",
    "sodium carboxymethylcellulose",
    "sodium copper chlorophyllin",
    "sodium starch glycolate",
    "sorbitol",
    "stearic acid",
    "sunfiber",
    "tapioca starch",
    "trisodium citrate",
    "vegetable (descriptor)",
    "vegetable lubricant",
    "vegetable magnesium silicate",
    "vitamin u",
    "xanthan gum",
}


def _load_entries() -> list[dict]:
    entries: list[dict] = []
    for key, path in FILES.items():
        data = json.loads(path.read_text())
        entries.extend(data.get(key, []))
    return entries


def _alias_duplicates(entries: list[dict]) -> set[str]:
    alias_map: dict[str, set[str]] = defaultdict(set)
    for entry in entries:
        entry_id = entry.get("id", "")
        for alias in entry.get("aliases") or []:
            if isinstance(alias, str) and alias.strip():
                alias_map[alias.strip().lower()].add(entry_id)
    return {
        alias for alias, ids in alias_map.items()
        if len(ids) > 1
    }


def _alias_vs_standard_collisions(entries: list[dict]) -> set[str]:
    alias_map: dict[str, set[str]] = defaultdict(set)
    standard_map: dict[str, set[str]] = defaultdict(set)
    for entry in entries:
        entry_id = entry.get("id", "")
        standard_name = (entry.get("standard_name") or "").strip().lower()
        if standard_name:
            standard_map[standard_name].add(entry_id)
        for alias in entry.get("aliases") or []:
            if isinstance(alias, str) and alias.strip():
                alias_map[alias.strip().lower()].add(entry_id)

    collisions = set()
    for label, alias_ids in alias_map.items():
        standard_ids = standard_map.get(label, set())
        if standard_ids and len(alias_ids | standard_ids) > 1:
            collisions.add(label)
    return collisions


def test_no_new_cross_entry_exact_alias_duplicates():
    entries = _load_entries()
    duplicates = _alias_duplicates(entries)
    unexpected = sorted(duplicates - BASELINE_ALIAS_DUPLICATES)
    assert not unexpected, (
        "New cross-entry exact alias duplicates found in inactive/additive data:\n  - "
        + "\n  - ".join(unexpected)
        + "\n\nIf one is intentional, remove the ambiguity or explicitly baseline it after review."
    )


def test_no_new_alias_matches_another_entries_standard_name():
    entries = _load_entries()
    collisions = _alias_vs_standard_collisions(entries)
    unexpected = sorted(collisions - BASELINE_ALIAS_VS_STANDARD_COLLISIONS)
    assert not unexpected, (
        "New alias-vs-standard collisions found in inactive/additive data:\n  - "
        + "\n  - ".join(unexpected)
        + "\n\nThese make canonicalization depend on lookup order and must be reviewed."
    )
