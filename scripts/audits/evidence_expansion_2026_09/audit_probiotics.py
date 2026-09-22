#!/usr/bin/env python3
"""Audit of Probiotic Species vs Strain Applicability across the catalog."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]

def run_probiotic_audit():
    # Load clinically relevant strains registry
    with open(ROOT / "scripts" / "data" / "clinically_relevant_strains.json") as f:
        strains_data = json.load(f)
    clinical_strains = strains_data.get("clinically_relevant_strains", [])
    
    # Map strain ID to standard_name, genus, species
    strain_registry = {}
    species_with_strain_evidence = set()
    for s in clinical_strains:
        sid = s.get("id")
        sname = s.get("standard_name", "")
        strain_registry[sid] = s
        
        # Extract genus + species
        parts = sname.split()
        if len(parts) >= 2:
            spec = f"{parts[0].lower()}_{parts[1].lower()}"
            species_with_strain_evidence.add(spec)

    print(f"Loaded {len(clinical_strains)} clinical strain entries.")
    print(f"Unique species with strain-level evidence: {len(species_with_strain_evidence)}")

    PROBIOTIC_GENERA = {
        'lactobacillus', 'bifidobacterium', 'streptococcus', 'bacillus', 'saccharomyces', 
        'limosilactobacillus', 'lacticaseibacillus', 'lactococcus', 'enterococcus', 
        'pediococcus', 'clostridium', 'akkermansia'
    }

    # Load all scored products
    scored_files = sorted(ROOT.glob("scripts/products/output_*/scored/*.json"))
    enriched_files = sorted(ROOT.glob("scripts/products/output_*/enriched/*.json"))

    # Map enriched data by dsld_id
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

    total_probiotic_products = 0
    species_only_products = 0
    exact_strain_products = 0
    mixed_species_strain_products = 0

    products_by_module = Counter()
    evidence_states = Counter()
    quality_assessment_statuses = Counter()

    aggregate_cfu_disclosed = 0
    per_strain_cfu_disclosed = 0
    no_cfu_disclosed = 0

    studied_formula_matches = 0

    # Categorization of research / applicability gap
    research_exists_strain_unresolvable = 0
    research_exists_unreviewed = 0
    genuinely_lacking_research = 0
    strain_applicable = 0

    species_declared_counts = Counter()
    strains_declared_counts = Counter()

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
            mod = p.get("_v4_module") or p.get("v4_module") or "unknown"
            q_status = p.get("quality_assessment_status") or "unknown"
            ev = (p.get("quality_pillars_v4") or {}).get("evidence") or {}
            ev_state = ev.get("evidence_result_state") or "unknown"

            ep = enriched_map.get(did, {})
            pdata = ep.get("probiotic_data") or ep.get("probiotic_detail") or {}
            
            # Check for probiotic presence
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

            total_probiotic_products += 1
            products_by_module[mod] += 1
            evidence_states[ev_state] += 1
            quality_assessment_statuses[q_status] += 1

            # Check CFU disclosure
            total_cfu = pdata.get("total_cfu") or pdata.get("cfu_count") or ep.get("total_cfu")
            if total_cfu and float(total_cfu or 0) > 0:
                aggregate_cfu_disclosed += 1
            else:
                # check rows for cfu units
                row_cfu = any(str(r.get("unit") or "").lower() in {"cfu", "afp", "cells"} for r in prob_rows)
                if row_cfu:
                    aggregate_cfu_disclosed += 1
                else:
                    no_cfu_disclosed += 1

            # Check per-strain dose disclosure
            rows_with_cfu = [r for r in prob_rows if str(r.get("unit") or "").lower() in {"cfu", "afp", "cells"} and float(r.get("quantity") or 0) > 0]
            if len(rows_with_cfu) > 1 or (len(prob_rows) == 1 and len(rows_with_cfu) == 1):
                per_strain_cfu_disclosed += 1

            # Check strains vs species
            clinical_strains_found = pdata.get("clinical_strains") or []
            exact_strains_in_prod = []
            for cs in clinical_strains_found:
                sid = cs.get("clinical_id") or cs.get("id")
                if sid in strain_registry:
                    exact_strains_in_prod.append(sid)
                    strains_declared_counts[sid] += 1

            # Check declared species
            species_in_prod = set()
            for r in prob_rows:
                r_text = f"{r.get('name', '')} {r.get('standard_name', '')}".lower()
                words = re.findall(r"[a-z]+", r_text)
                for idx, w in enumerate(words[:-1]):
                    if w in PROBIOTIC_GENERA:
                        species_in_prod.add(f"{w}_{words[idx+1]}")
                        species_declared_counts[f"{w}_{words[idx+1]}"] += 1

            if exact_strains_in_prod and len(species_in_prod) <= len(exact_strains_in_prod):
                exact_strain_products += 1
            elif exact_strains_in_prod and len(species_in_prod) > len(exact_strains_in_prod):
                mixed_species_strain_products += 1
            else:
                species_only_products += 1

            # Studied formula check
            formula_info = ev.get("metadata", {}).get("studied_formula_assessment") or {}
            if formula_info.get("status") == "assessed_studied_formula":
                studied_formula_matches += 1

            # Determine research vs applicability gap
            if exact_strains_in_prod:
                strain_applicable += 1
            elif any(s in species_with_strain_evidence for s in species_in_prod):
                # Research exists for strains within this species, but label gave only species
                research_exists_strain_unresolvable += 1
            elif species_in_prod:
                genuinely_lacking_research += 1
            else:
                genuinely_lacking_research += 1

    report = {
        "total_probiotic_products_audited": total_probiotic_products,
        "classification": {
            "species_only_products": species_only_products,
            "exact_strain_products": exact_strain_products,
            "mixed_species_and_strain_products": mixed_species_strain_products,
        },
        "by_module": dict(products_by_module),
        "quality_assessment_status": dict(quality_assessment_statuses),
        "evidence_result_states": dict(evidence_states),
        "cfu_disclosure": {
            "aggregate_cfu_disclosed": aggregate_cfu_disclosed,
            "per_strain_cfu_disclosed": per_strain_cfu_disclosed,
            "no_cfu_disclosed": no_cfu_disclosed,
        },
        "studied_formula_matches": studied_formula_matches,
        "research_applicability_breakdown": {
            "exact_strain_present_in_registry": strain_applicable,
            "research_exists_at_strain_level_but_label_is_species_only": research_exists_strain_unresolvable,
            "species_without_known_strain_research": genuinely_lacking_research,
        },
        "top_species_with_strain_research_on_species_only_labels": [
            (spec, count) for spec, count in species_declared_counts.most_common(15)
            if spec in species_with_strain_evidence
        ],
        "top_declared_exact_strains": strains_declared_counts.most_common(10),
    }

    out_file = ROOT / "scripts" / "audits" / "evidence_expansion_2026_09" / "probiotic_audit_report.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(report, f, indent=2)

    print("Probiotic Audit Summary:")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    run_probiotic_audit()
