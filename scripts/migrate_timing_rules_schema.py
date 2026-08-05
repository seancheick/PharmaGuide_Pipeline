#!/usr/bin/env python3
"""One-shot migration: timing_rules.json 5.3.0 -> 6.0.0.

This is a MECHANICAL schema migration, not a clinical edit. It moves every rule
onto the final field set and then marks all of them `needs_revision`, so nothing
renders until Section 2 verifies each rule individually against its source.

That ordering is the whole point. The derived `ingredient*_tags` come from the
app's former private alias map, which is *known* to contain unreachable targets
(`vitamin_b12` where the catalog emits `vitamin_b12_cobalamin`, `calcium_carbonate`
matching zero products, `soy`/`soy_protein` matching zero). Baking those in is
safe only because no migrated rule is publishable: Section 2 corrects the
identities one at a time and adds positive/negative catalog canaries before
setting `review_status: verified`.

What this script must never do: mark anything `verified`, or invent a clinical
value that is not already authored in the rule it is transforming.

Usage:  python3 scripts/migrate_timing_rules_schema.py [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parent / "data" / "timing_rules.json"
TARGET_SCHEMA_VERSION = "6.0.0"

# The app's former `_ingredientAliases`, transcribed verbatim so the migration is
# a faithful move rather than a silent re-authoring. Known-imperfect by design;
# see the module docstring.
LEGACY_ALIASES: dict[str, list[str]] = {
    "iron": ["iron"],
    "calcium": ["calcium"],
    "calcium carbonate": ["calcium_carbonate"],
    "zinc": ["zinc"],
    "copper": ["copper"],
    "magnesium": ["magnesium"],
    "vitamin c": ["vitamin_c"],
    "vitamin d": ["vitamin_d"],
    "vitamin e": ["vitamin_e"],
    "vitamin k": ["vitamin_k"],
    "vitamin b12": ["vitamin_b12"],
    "vitamin b complex": [
        "vitamin_b1",
        "vitamin_b2",
        "vitamin_b3",
        "vitamin_b5",
        "vitamin_b6",
        "vitamin_b12",
    ],
    "folate": ["folate", "vitamin_b9"],
    "omega-3": ["omega_3", "fish_oil", "epa", "dha"],
    "coq10": ["coq10"],
    "turmeric": ["turmeric", "curcumin"],
    "probiotics": ["probiotics", "probiotic"],
    "melatonin": ["melatonin"],
    "green tea extract": ["green_tea_extract", "egcg"],
    "caffeine": ["caffeine", "guarana"],
    "fiber": ["fiber", "psyllium", "inulin"],
    "nac": ["nac", "n_acetyl_cysteine"],
    "alpha-lipoic acid": ["alpha_lipoic_acid"],
    "collagen peptides": ["collagen"],
    "quercetin": ["quercetin"],
    "bromelain": ["bromelain"],
    "ashwagandha": ["ashwagandha"],
    "l-theanine": ["l_theanine"],
    "berberine": ["berberine"],
    "soy protein": ["soy", "soy_protein", "soy_isoflavones"],
}

# Second-side values that are context, not a stack item. Under the new schema the
# relation type carries this meaning, so these produce no ingredient2 identity.
CONTEXT_TERMS = {"food", "dietary fat", "sleep", "melatonin production"}

SOURCE_TYPE_TO_AUTHORITY = {
    "fda": "fda_label",
    "pubmed": "clinical_study",
    "nih_ods": "reference",
    "reference": "reference",
}


def tags_for(name: str) -> list[str]:
    """Resolve a free-text ingredient name to canonical tags."""
    key = name.strip().lower()
    if key in LEGACY_ALIASES:
        return list(LEGACY_ALIASES[key])
    # The app's old fallback: underscore the name and hope. Preserved so the
    # migration is faithful; Section 2 replaces these with verified tags.
    return [key.replace(" ", "_").replace("-", "_")]


def build_relation(rule: dict) -> dict:
    """Derive `timing_relation` from the legacy rule_type, inventing nothing."""
    rule_type = rule["rule_type"]
    ingredient2 = (rule.get("ingredient2") or "").strip().lower()

    if rule_type == "separate":
        hours = rule.get("separation_hours")
        if not isinstance(hours, int) or hours <= 0:
            raise ValueError(f"{rule['id']}: separate rule lacks separation_hours")
        if ingredient2 == "medications":
            return {"type": "separate_from_medications", "minimum_hours": hours}
        return {"type": "separate_from", "minimum_hours": hours}

    if rule_type == "take_with_food":
        return {"type": "with_food"}

    if rule_type == "take_on_empty_stomach":
        return {"type": "empty_stomach"}

    if rule_type == "take_together":
        # No relation type expresses "swallow these in the same mouthful",
        # because the plan removes that category entirely. These rules are all
        # headed for clinical review; carry them as with_food so they parse, and
        # let Section 2 reject or re-author them.
        return {"type": "with_food"}

    if rule_type == "time_of_day":
        # Only transcribe numbers the rule already authored. Melatonin's advice
        # states "30 to 60 minutes before your target bedtime" in its own text.
        if rule["id"] == "timing_melatonin_before_bed":
            return {
                "type": "before_event",
                "event": "intended_sleep",
                "minimum_minutes": 30,
                "maximum_minutes": 60,
            }
        # timing_magnesium_evening authors no interval and is already
        # daily_plan_eligible: false. It carries no defensible relation, so it
        # migrates as a with_food placeholder pending rejection in Section 2.
        return {"type": "with_food"}

    raise ValueError(f"{rule['id']}: unknown rule_type {rule_type!r}")


def category_for(rule: dict, relation: dict) -> str:
    if relation["type"] in ("separate_from", "separate_from_medications"):
        return "important_separation"
    if rule["rule_type"] == "take_together":
        return "optional"
    return "how_to_take"


def actionability_for(rule: dict, category: str) -> str:
    if category == "important_separation":
        return "recommended"
    if rule["rule_type"] == "take_together":
        return "informational"
    return "recommended"


def applies_to_for(relation: dict) -> str:
    # Binary separations are about two bottles and apply regardless of
    # formulation. Unary instructions are the ones that go wrong inside a
    # combination product, so they default to the conservative scope.
    if relation["type"] == "separate_from":
        return "any"
    return "standalone"


def authority_for(rule: dict) -> str:
    sources = rule.get("sources") or []
    if not sources:
        return "reference"
    return SOURCE_TYPE_TO_AUTHORITY.get(sources[0].get("source_type"), "reference")


def migrate_rule(rule: dict) -> dict:
    relation = build_relation(rule)
    category = category_for(rule, relation)

    out: dict = {
        "id": rule["id"],
        "ingredient1": rule["ingredient1"],
    }

    if rule.get("ingredient1_rxcuis"):
        out["ingredient1_rxcuis"] = rule["ingredient1_rxcuis"]
    else:
        out["ingredient1_tags"] = tags_for(rule["ingredient1"])

    ingredient2 = (rule.get("ingredient2") or "").strip()
    is_binary = relation["type"] == "separate_from"
    if is_binary:
        out["ingredient2"] = ingredient2
        if rule.get("ingredient2_rxcuis"):
            out["ingredient2_rxcuis"] = rule["ingredient2_rxcuis"]
        else:
            out["ingredient2_tags"] = tags_for(ingredient2)
    elif ingredient2 and ingredient2.lower() not in CONTEXT_TERMS:
        # Keep the authored display string, but no matchable identity: a unary
        # relation must not carry a second side.
        out["ingredient2"] = ingredient2

    out.update(
        {
            "timing_relation": relation,
            "category": category,
            "applies_to": applies_to_for(relation),
            "actionability": actionability_for(rule, category),
            "source_authority": authority_for(rule),
            # Nothing the migration touches is publishable. Section 2 promotes
            # rules one at a time, after source verification and canaries.
            "review_status": "needs_revision",
            "advice": rule["advice"],
            "mechanism": rule.get("mechanism"),
            "score_impact": rule["score_impact"],
            "evidence_level": rule["evidence_level"],
            "sources": rule.get("sources", []),
        }
    )

    min_dose = rule.get("min_dose")
    if min_dose:
        out["min_dose"] = {"tag": min_dose["ingredient"], "mg": min_dose["mg"]}

    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the file is already migrated; do not write",
    )
    args = parser.parse_args()

    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    metadata = data["_metadata"]

    if metadata.get("schema_version") == TARGET_SCHEMA_VERSION:
        print(f"already at schema {TARGET_SCHEMA_VERSION}; nothing to do")
        return 0
    if args.check:
        print(
            f"NOT MIGRATED: schema_version is {metadata.get('schema_version')!r}, "
            f"expected {TARGET_SCHEMA_VERSION!r}",
            file=sys.stderr,
        )
        return 1

    rules = data["timing_rules"]
    migrated = [migrate_rule(rule) for rule in rules]

    # Migration is lossless in count and identity: every rule in, every rule out.
    assert len(migrated) == len(rules), "rule count changed during migration"
    assert [r["id"] for r in migrated] == [r["id"] for r in rules], "ids reordered"
    assert all(
        r["review_status"] == "needs_revision" for r in migrated
    ), "migration must not publish any rule"

    metadata["schema_version"] = TARGET_SCHEMA_VERSION
    metadata["total_entries"] = len(migrated)
    data["timing_rules"] = migrated

    SOURCE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"migrated {len(migrated)} rules to schema {TARGET_SCHEMA_VERSION}")
    print("all rules are review_status=needs_revision and will not render")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
