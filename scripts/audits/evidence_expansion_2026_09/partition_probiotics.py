#!/usr/bin/env python3
"""Strict Mutually Exclusive Partition of Probiotic Products."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

PROBIOTIC_GENERA = {
    'lactobacillus', 'bifidobacterium', 'streptococcus', 'bacillus', 'saccharomyces', 
    'limosilactobacillus', 'lacticaseibacillus', 'lactococcus', 'enterococcus', 
    'pediococcus', 'clostridium', 'akkermansia'
}

def load_strains_registry():
    with open(ROOT / "scripts/data/clinically_relevant_strains.json") as f:
        strains_data = json.load(f)
    clinical_strains = strains_data.get("clinically_relevant_strains", [])
    
    strain_registry = {s["id"]: s for s in clinical_strains}
    species_with_strain_evidence = set()
    for s in clinical_strains:
        sname = s.get("standard_name", "")
        parts = sname.split()
        if len(parts) >= 2:
            spec = f"{parts[0].lower()}_{parts[1].lower()}"
            species_with_strain_evidence.add(spec)
            
    return strain_registry, species_with_strain_evidence

def run_partition():
    strain_registry, species_with_strain_evidence = load_strains_registry()

    scored_files = sorted(ROOT.glob("scripts/products/output_*/scored/*.json"))
    enriched_files = sorted(ROOT.glob("scripts/products/output_*/enriched/*.json"))

    enriched_map = {}
    for ef in enriched_files:
        try:
            with open(ef) as f:
                data = json.load(f)
        except Exception:
            continue
        prods = data if isinstance(data, list) else data.get("products", [data])
        for p in prods:
            if isinstance(p, dict):
                did = str(p.get("dsld_id") or p.get("id") or "")
                if did:
                    enriched_map[did] = p

    # Also load manual product submissions (e.g. Seed DS-01)
    manual_files = sorted(ROOT.glob("manual_labels/product_submissions/*.json"))
    for mf in manual_files:
        try:
            with open(mf) as f:
                p = json.load(f)
            if isinstance(p, dict):
                did = str(p.get("dsld_id") or p.get("id") or "")
                if did and did not in enriched_map:
                    enriched_map[did] = p
        except Exception:
            pass

    probiotic_products = []
    seen_ids = set()

    for sf in scored_files:
        try:
            with open(sf) as f:
                data = json.load(f)
        except Exception:
            continue
        prods = data if isinstance(data, list) else data.get("products", [data])
        for p in prods:
            if not isinstance(p, dict):
                continue
            did = str(p.get("dsld_id") or p.get("id") or "")
            if not did:
                continue

            ep = enriched_map.get(did, {})
            pdata = ep.get("probiotic_data") or ep.get("probiotic_detail") or {}
            mod = p.get("_v4_module") or p.get("v4_module") or "unknown"

            iqd = ep.get("ingredient_quality_data") or {}
            ings = iqd.get("ingredients") or []
            prob_rows = []
            for ing in ings:
                cid = str(ing.get("canonical_id") or "").lower()
                name = str(ing.get("name") or "").lower()
                std = str(ing.get("standard_name") or "").lower()
                if any(g in cid or g in name or g in std for g in PROBIOTIC_GENERA) or "probiotic" in cid or "probiotic" in name:
                    prob_rows.append(ing)

            has_prob = (
                mod == "probiotic"
                or p.get("is_probiotic") is True
                or p.get("contains_probiotics") is True
                or pdata.get("is_probiotic") is True
                or pdata.get("is_probiotic_product") is True
                or (pdata.get("total_strain_count") or 0) > 0
                or bool(prob_rows)
            )

            if not has_prob:
                continue

            if did in seen_ids:
                print(f"WARNING: Duplicate product ID {did}")
                continue
            seen_ids.add(did)

            # Analyze exact strains vs species
            clinical_strains_found = pdata.get("clinical_strains") or []
            exact_strains = []
            for cs in clinical_strains_found:
                sid = cs.get("clinical_id") or cs.get("id")
                if sid in strain_registry:
                    exact_strains.append(sid)

            species_in_prod = set()
            for r in prob_rows:
                r_text = f"{r.get('name', '')} {r.get('standard_name', '')}".lower()
                words = re.findall(r"[a-z]+", r_text)
                for idx, w in enumerate(words[:-1]):
                    if w in PROBIOTIC_GENERA:
                        species_in_prod.add(f"{w}_{words[idx+1]}")

            ev = (p.get("quality_pillars_v4") or {}).get("evidence") or {}
            ev_state = ev.get("evidence_result_state") or "unknown"
            q_status = p.get("quality_assessment_status") or "unknown"
            ev_score = ev.get("score") or 0.0

            # Identity category
            if exact_strains and not species_in_prod:
                ident_cat = "exact_strain_only"
            elif exact_strains and species_in_prod:
                # Check if every species is represented by the exact strains
                strain_species = set()
                for sid in exact_strains:
                    s_info = strain_registry.get(sid, {})
                    parts = s_info.get("standard_name", "").split()
                    if len(parts) >= 2:
                        strain_species.add(f"{parts[0].lower()}_{parts[1].lower()}")
                if species_in_prod.issubset(strain_species):
                    ident_cat = "exact_strain_only"
                else:
                    ident_cat = "mixed_exact_and_species"
            elif species_in_prod or prob_rows:
                # Species only
                # Check if strain literature exists for any declared species
                has_literature = any(s in species_with_strain_evidence for s in species_in_prod)
                if has_literature:
                    ident_cat = "species_only_literature_exists"
                else:
                    ident_cat = "species_only_no_strain_literature"
            else:
                ident_cat = "probiotic_class_unspecified"

            probiotic_products.append({
                "dsld_id": did,
                "name": p.get("product_name"),
                "brand": p.get("brand_name"),
                "module": mod,
                "identity_category": ident_cat,
                "evidence_state": ev_state,
                "evidence_score": ev_score,
                "assessment_status": q_status,
                "exact_strains": exact_strains,
                "species": sorted(species_in_prod),
            })

    total = len(probiotic_products)
    print(f"Total Probiotic Products: {total}")
    print(f"Unique DSLD IDs: {len(seen_ids)}")
    assert len(seen_ids) == total, "Duplicates found!"

    # Breakdown by identity_category
    cat_counts = Counter(p["identity_category"] for p in probiotic_products)
    print("\nIdentity Category Counts:")
    for k, v in cat_counts.items():
        print(f"  {k}: {v}")

    # Cross tabulation: identity_category x evidence_state
    cross_tab = defaultdict(Counter)
    cross_tab_status = defaultdict(Counter)
    for p in probiotic_products:
        cross_tab[p["identity_category"]][p["evidence_state"]] += 1
        cross_tab_status[p["identity_category"]][p["assessment_status"]] += 1

    print("\nCross-Tabulation: Identity Category x Evidence State:")
    for cat in sorted(cross_tab.keys()):
        print(f"\n[{cat}] (Total: {cat_counts[cat]}):")
        for state, count in cross_tab[cat].most_common():
            print(f"    {state}: {count}")

    print("\nCross-Tabulation: Identity Category x Assessment Status:")
    for cat in sorted(cross_tab_status.keys()):
        print(f"\n[{cat}] (Total: {cat_counts[cat]}):")
        for status, count in cross_tab_status[cat].most_common():
            print(f"    {status}: {count}")

    # Save detailed data
    out_file = ROOT / "scripts/audits/evidence_expansion_2026_09/probiotic_partition_data.json"
    with open(out_file, "w") as f:
        json.dump({
            "total_count": total,
            "unique_ids_count": len(seen_ids),
            "category_counts": dict(cat_counts),
            "cross_tab_evidence_state": {k: dict(v) for k, v in cross_tab.items()},
            "cross_tab_assessment_status": {k: dict(v) for k, v in cross_tab_status.items()},
            "products": probiotic_products,
        }, f, indent=2)
    print(f"\nSaved partition data to {out_file}")

if __name__ == "__main__":
    run_partition()
