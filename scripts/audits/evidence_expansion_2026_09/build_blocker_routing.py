#!/usr/bin/env python3
"""Route the Evidence=0 products that evidence curation cannot fix (read-only).

More papers will not move these products. Each blocker class belongs to an
existing canonical owner; this report hands them over and stays out of their
pipelines.

    python3 scripts/audits/evidence_expansion_2026_09/build_blocker_routing.py
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent

OWNERS = {
    "H": ("ingredient role / identity classification owner",
          "scripts/enrich_supplements_v3.py ingredient_quality_data role_classification "
          "(is_additive, blend_header_total_weight_only, nested_under_non_therapeutic_parent, "
          "excluded_nutrition_fact)",
          "The label's active rows were demoted before scoring, so no evidence record can reach them."),
    "C": ("identity normalization / applicability owner",
          "scripts/data/ingredient_quality_map.json canonical identities and "
          "scripts/clinical_applicability.py reviewed scopes",
          "A record exists but correctly does not join (form excluded, or one canonical lumps distinct materials), "
          "or the label identity is unresolved."),
    "E": ("clinical evidence registry owner (legacy backfill)",
          "scripts/data/backed_clinical_studies.json reference-type records",
          "The matched record is reference-only and can never carry efficacy points by design."),
    "F": ("clinical evidence registry owner",
          "formula-scoped applicability contracts",
          "Evidence is formula-scoped and cannot be attributed to one component."),
    "D": ("clinical evidence registry owner",
          "applicability dose bounds on the matched record",
          "The label dose falls outside the reviewed scope of an existing record."),
    "G": ("v4 scoring owner",
          "scripts/scoring_v4/modules/generic_evidence.py",
          "An accepted match carries points yet the pillar is 0 — inspect the scorer."),
}


def main() -> int:
    taxonomy = json.loads((OUT / "zero_evidence_taxonomy.json").read_text())
    products = taxonomy["products"]
    blocked = [p for p in products if not p["recoverable_by_curation_alone"]]

    by_letter = collections.Counter(p["primary"] for p in blocked)
    detail = collections.Counter(d for p in blocked for d in p["details"] if not d.startswith(("A_", "B_")))
    brands = collections.Counter(p["brand"] for p in blocked)
    identities = collections.Counter(c for p in blocked for c in p["active_canonicals"])

    rows = []
    for letter, count in sorted(by_letter.items()):
        owner, artefact, why = OWNERS[letter]
        examples = [p for p in blocked if p["primary"] == letter][:5]
        rows.append({"letter": letter, "products": count, "owner": owner, "artefact": artefact, "why": why,
                     "example_dsld_ids": [p["dsld_id"] for p in examples],
                     "example_products": [f"{p['brand']} — {p['product_name']}" for p in examples]})

    payload = {"_metadata": {
        "evidence_zero_products": len(products),
        "blocked_outside_evidence_curation": len(blocked),
        "recoverable_by_curation_alone": len(products) - len(blocked),
        "note": "Reported to the owners listed; this project changes none of their pipelines."},
        "by_class": rows,
        "detail_counts": dict(detail.most_common()),
        "top_brands": dict(brands.most_common(10)),
        "top_identities": dict(identities.most_common(20))}
    (OUT / "blocker_routing.json").write_text(json.dumps(payload, indent=1))

    lines = ["# Evidence=0 products that evidence curation cannot fix", "",
             f"{len(blocked)} of {len(products)} Evidence=0 products (non-probiotic lane). "
             "Adding papers will not move any of them. Each class is handed to its existing owner; "
             "this project modifies none of those pipelines.", "",
             "| class | products | owner | why | examples |", "|---|---:|---|---|---|"]
    for row in rows:
        lines.append(f"| {row['letter']} | {row['products']} | {row['owner']} | {row['why']} | "
                     f"{'; '.join(row['example_products'][:2])} |")
    lines += ["", "## Sub-reasons", "", "| detail | products |", "|---|---:|"] + \
             [f"| `{k}` | {v} |" for k, v in detail.most_common()] + \
             ["", "## Most affected brands", "", "| brand | products |", "|---|---:|"] + \
             [f"| {k} | {v} |" for k, v in brands.most_common(10)] + \
             ["", "## Identities appearing most often in blocked products", "",
              "| identity | products |", "|---|---:|"] + \
             [f"| `{k}` | {v} |" for k, v in identities.most_common(20)] + [""]
    (OUT / "BLOCKER_ROUTING.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(payload["_metadata"], indent=1))
    print(json.dumps({r["letter"]: r["products"] for r in rows}, indent=0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
