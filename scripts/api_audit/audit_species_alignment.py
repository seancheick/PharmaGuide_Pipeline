#!/usr/bin/env python3
"""Cross-species/chemistry alias alignment audit.

Scans reference data files for entries where aliases reference Latin
binomials inconsistent with the entry's own latin_name / standard_name /
description. Catches two failure classes:

1. SAME_GENUS_DIFFERENT_SPECIES — alias has 'Genus species2' where the
   entry's primary binomial is 'Genus species1'. The Myrica cerifera /
   Myrica rubra (Yangmei) bug.

2. CROSS_GENUS — alias has a binomial whose genus differs from the
   entry's stated genus. The butternut tree (Juglans cinerea) /
   butternut squash (Cucurbita moschata) family-level bug.

Usage:
    python3 scripts/api_audit/audit_species_alignment.py
        # Scans all 4 reference data files

    python3 scripts/api_audit/audit_species_alignment.py --file <path>
        # Scan a specific file

    python3 scripts/api_audit/audit_species_alignment.py --strict
        # Exit non-zero if any SAME_GENUS issues found (release gate)

False positives are common — taxonomy synonyms (Phyllanthus emblica /
Emblica officinalis, Saccharina / Laminaria japonica, Sophora /
Styphnolobium japonicum) and regex parsing of word pairs like 'Coffee
bean' or 'Pine nut' as binomials. Each candidate must be hand-verified
via verify_cui.py and PubChem/UNII/NCBI Taxonomy before action.

Audit history: 2026-05-01 found 6 real chemistry violations across
botanical_ingredients.json and ingredient_quality_map.json (Myrica,
chopchini Smilax glabra, sarsaparilla stale CUI, catjang_cowpea wrong
CUI [lectin protein], butternut family conflation, IQM auricularia
genus-level CUI).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

DEFAULT_TARGETS = [
    ("botanical_ingredients.json", "botanical_ingredients", ["latin_name", "standard_name", "notes"]),
    ("ingredient_quality_map.json", None, ["standard_name", "description"]),
    ("harmful_additives.json", "harmful_additives", ["standard_name", "notes"]),
    ("banned_recalled_ingredients.json", "ingredients", ["standard_name", "reason", "notes"]),
    ("standardized_botanicals.json", "standardized_botanicals", ["latin_name", "standard_name", "notes"]),
    ("other_ingredients.json", "other_ingredients", ["standard_name", "notes"]),
]

BINOMIAL = re.compile(r"\b([A-Z][a-z]+)\s+([a-z][a-z\-]+)\b")

FALSE_POS_GENERA = {
    "Organic", "Fresh", "Dried", "Whole", "Raw", "Pure", "Standard",
    "Extract", "Powder", "Root", "Leaf", "Bark", "Fruit", "Seed",
    "Stem", "Flower", "Bud", "Skin", "Wood", "Aerial", "From",
    "True", "Wild", "Cultivated", "Asian", "Chinese", "Japanese",
    "Indian", "American", "European", "African", "Australian",
    "Eastern", "Western", "Northern", "Southern", "Black", "White",
    "Red", "Green", "Blue", "Yellow", "Pink", "Purple", "Brown",
    "Sea", "Mountain", "Forest", "Garden", "Sweet", "Bitter",
    "Spicy", "Hot", "Cold", "Holy", "Sacred", "Royal", "Common",
    "Greater", "Lesser", "Big", "Small", "Tiny", "Giant", "Large",
    "Brand", "And", "Or", "With", "Without", "For", "By",
    "Decaffeinated", "Standardized", "Non", "Caps",
    "Honey", "Bee", "Cream", "Milk", "Soy", "Coconut", "Almond",
    "Spanish", "Roman", "Russian", "French", "German",
    "Vitamin", "Active", "High", "Low", "Mid", "Iron", "Zinc",
    "Magnesium", "Calcium", "Sodium", "Potassium", "Manganese",
    "Selenium", "Copper", "Chromium", "Molybdenum", "Boron",
    "Free", "Plant", "Methylated", "Synthetic", "Natural",
}

FALSE_POS_SPECIES = {
    "and", "or", "the", "powder", "extract", "root", "leaf", "bark",
    "fruit", "seed", "stem", "flower", "from", "with", "non",
    "powdered", "fresh", "dried", "whole", "var", "subsp", "ssp",
    "cv", "f", "n", "raw", "spp", "ext", "concentrate", "juice",
    "berry", "berries", "rich", "free", "based", "complex",
    "containing", "blend",
}


def parse_binomials(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if not text:
        return out
    for m in BINOMIAL.finditer(text):
        g, s = m.group(1), m.group(2)
        if g in FALSE_POS_GENERA or s in FALSE_POS_SPECIES:
            continue
        out.append((g.lower(), s.lower()))
    return out


def collect_aliases(entry: dict) -> list[str]:
    """Pull aliases from parent + nested forms (IQM-style)."""
    aliases: list[str] = []
    aliases.extend(entry.get("aliases") or [])
    forms = entry.get("forms") or {}
    if isinstance(forms, dict):
        for fname, fdata in forms.items():
            if isinstance(fdata, dict):
                aliases.append(fname)
                aliases.extend(fdata.get("aliases") or [])
    return [a for a in aliases if isinstance(a, str)]


def primary_binomials(entry: dict, name_fields: list[str]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for f in name_fields:
        text = entry.get(f) or ""
        if isinstance(text, str):
            for p in parse_binomials(text[:300]):
                pairs.add(p)
    return pairs


def audit_file(path: Path, list_key: str | None, name_fields: list[str]):
    """Yield (severity, entry_id, std_pairs, alias, found_binomial)."""
    if not path.exists():
        return
    data = json.loads(path.read_text())
    if list_key:
        entries_iter = ((e.get("id", "?"), e) for e in data.get(list_key, []))
    else:
        entries_iter = (
            (k, v) for k, v in data.items()
            if not k.startswith("_") and isinstance(v, dict)
        )

    for eid, entry in entries_iter:
        std_pairs = primary_binomials(entry, name_fields)
        if not std_pairs:
            continue
        std_genera = {g for g, _ in std_pairs}
        for alias in collect_aliases(entry):
            for g, s in parse_binomials(alias):
                if (g, s) in std_pairs:
                    continue
                kind = "SAME_GENUS" if g in std_genera else "CROSS_GENUS"
                yield (kind, eid, sorted(std_pairs), alias, f"{g} {s}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--file", help="Specific file to audit (default: all)")
    p.add_argument("--strict", action="store_true",
                   help="Exit 1 if any SAME_GENUS issues found")
    args = p.parse_args()

    targets = DEFAULT_TARGETS
    if args.file:
        targets = [t for t in targets if t[0] == Path(args.file).name]
        if not targets:
            print(f"Unknown file: {args.file}")
            return 2

    same_genus_total = 0
    cross_genus_total = 0
    seen: set[tuple[str, str, str]] = set()  # de-dup

    for filename, list_key, name_fields in targets:
        path = DATA / filename
        if not path.exists():
            print(f"  SKIP {filename} — file not found")
            continue
        same_genus_file: list[tuple] = []
        cross_genus_file: list[tuple] = []
        for kind, eid, std, alias, found in audit_file(path, list_key, name_fields):
            key = (filename, eid, found.lower())
            if key in seen:
                continue
            seen.add(key)
            if kind == "SAME_GENUS":
                same_genus_file.append((eid, std, alias, found))
            else:
                cross_genus_file.append((eid, std, alias, found))

        same_genus_total += len(same_genus_file)
        cross_genus_total += len(cross_genus_file)

        print(f"\n{'=' * 70}")
        print(f"{filename}: {len(same_genus_file)} SAME_GENUS, {len(cross_genus_file)} CROSS_GENUS")
        print('=' * 70)
        if same_genus_file:
            print("\n  SAME_GENUS_DIFFERENT_SPECIES (HIGH RISK — Myrica-pattern):\n")
            for eid, std, alias, found in same_genus_file:
                print(f"    {eid:35s} std={std} alias={alias!r}  → {found}")
        if cross_genus_file:
            print("\n  CROSS_GENUS (review for taxonomy-update vs family-level mismatch):\n")
            for eid, std, alias, found in cross_genus_file:
                print(f"    {eid:35s} std={std} alias={alias!r}  → {found}")

    print(f"\n{'=' * 70}")
    print(f"TOTAL: {same_genus_total} SAME_GENUS, {cross_genus_total} CROSS_GENUS")
    print('=' * 70)
    print("\nNext steps for any SAME_GENUS finding:")
    print("  1. Verify CUIs via:  python3 scripts/api_audit/verify_cui.py --search '<binomial>'")
    print("  2. If genuinely different species: strip alias + create separate entry")
    print("  3. If taxonomy synonym (e.g. modern name change): keep alias, document in notes")
    print("  4. Update entry's CUI to species-specific concept if currently genus-level")

    if args.strict and same_genus_total > 0:
        print("\nSTRICT MODE: SAME_GENUS issues present — exiting non-zero (release gate)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
