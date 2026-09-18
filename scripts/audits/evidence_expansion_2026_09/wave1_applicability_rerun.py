#!/usr/bin/env python3
"""Re-run the 10 Wave 1 identities through the production applicability path (read-only).

For each identity this asks one question against real products: if the owner approved
the proposed record, would the canonical applicability owner apply it to the right
products and refuse the wrong ones?

A proposal that names no scope cannot be simulated, and that is itself the answer —
the blocker is not the matcher. Those identities are reported as still held, with the
reason recorded in the packet.

Nothing is written to scripts/data, scripts/products or scripts/dist; no score moves.

    python3 scripts/audits/evidence_expansion_2026_09/wave1_applicability_rerun.py --slim <slim.jsonl>
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import subprocess
import sys
import tempfile
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

# Only butterbur's proposal names a scope the owner could evaluate; the rest are held
# for reasons no matcher change addresses (population, exposure basis, dose gap).
SIMULATED_POLICIES = {
    "butterbur": {"entry": {"id": "CANDIDATE_INGR_BUTTERBUR", "ingredient": "Butterbur",
                            "matched_canonical_ids": ["butterbur"],
                            "applicability": {"scope": "ingredient",
                                              "required_form_terms": ["petadolex", "pa-free"],
                                              "dose_unit": "mg", "minimum_daily_dose": 150}},
                  "intent": "credit only products declaring the studied PA-free/Petadolex material "
                            "at the studied 150 mg/day"},
}


def load_baseline(ref: str, registry_loader):
    source = subprocess.run(["git", "show", f"{ref}:scripts/clinical_applicability.py"],
                            cwd=ROOT, capture_output=True, text=True, check=True).stdout
    tmp = Path(tempfile.mkdtemp()) / "clinical_applicability_baseline.py"
    tmp.write_text(source)
    spec = importlib.util.spec_from_file_location("clinical_applicability_baseline_rerun", tmp)
    module = importlib.util.module_from_spec(spec)
    sys.modules["clinical_applicability_baseline_rerun"] = module
    spec.loader.exec_module(module)
    module.reviewed_entries = registry_loader
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slim", required=True, type=Path)
    parser.add_argument("--baseline-ref", default="HEAD")
    args = parser.parse_args()

    import clinical_applicability as after
    before = load_baseline(args.baseline_ref, after.reviewed_entries)
    contexts = json.loads((OUT / "wave1_contexts.json").read_text())

    # Which products carry each Wave 1 identity, and which rows declare the studied material.
    wanted = {c["canonical_id"] for c in contexts["candidates"]}
    products_by_identity: dict[str, list[dict]] = collections.defaultdict(list)
    for line in args.slim.open():
        product = json.loads(line)
        for row in product["rows"]:
            if row.get("canonical_id") in wanted:
                products_by_identity[row["canonical_id"]].append(product)
                break

    # Enriched records are needed to run the real matcher.
    enriched_index: dict[str, dict] = {}
    needed = {p["dsld_id"]: p["brand_dir"] for identity in SIMULATED_POLICIES
              for p in products_by_identity.get(identity, [])}
    for brand in sorted(set(needed.values())):
        for path in sorted(glob.glob(str(ROOT / f"scripts/products/output_{brand}_enriched/enriched/*.json"))):
            for product in json.load(open(path)):
                dsld_id = str(product.get("dsld_id"))
                if needed.get(dsld_id) == brand:
                    enriched_index[dsld_id] = product

    results = []
    for candidate in contexts["candidates"]:
        identity = candidate["canonical_id"]
        products = products_by_identity.get(identity, [])
        row = {"canonical_id": identity, "label_name": candidate["label_name"],
               "products_with_identity": len(products),
               "scorer_class_before": candidate["scorer_compatibility"]["class"],
               "proposal": candidate["proposed_record_level_synthesis"]["proposal"]}
        simulated = SIMULATED_POLICIES.get(identity)
        if not simulated:
            row.update({
                "simulated": False,
                "outcome": "still held — no matcher change addresses this blocker",
                "blocker": candidate["scorer_compatibility"]["reason"][:400],
                "scorer_class_after": candidate["scorer_compatibility"]["class"]})
            results.append(row)
            continue
        entry = simulated["entry"]
        applied_before, applied_after, refused_after = [], [], []
        for product in products:
            enriched = enriched_index.get(product["dsld_id"])
            if enriched is None:
                continue
            old = before.assess_clinical_applicability(enriched, entry)
            new = after.assess_clinical_applicability(enriched, entry)
            record = {"dsld_id": product["dsld_id"], "brand": product["brand_name"],
                      "product_name": product["product_name"],
                      "before": f"{old['status']}:{old['reason_code']}",
                      "after": f"{new['status']}:{new['reason_code']}",
                      "rows": [{"name": r.get("name"), "form_id": r.get("form_id"),
                                "mg": r.get("quantity")} for r in product["rows"]
                               if r.get("canonical_id") == identity]}
            if old["status"] == "applicable":
                applied_before.append(record)
            (applied_after if new["status"] == "applicable" else refused_after).append(record)
        row.update({
            "simulated": True, "intent": simulated["intent"],
            "products_evaluated": len([p for p in products if p["dsld_id"] in enriched_index]),
            "applicable_before": len(applied_before), "applicable_after": len(applied_after),
            "newly_applicable": [r for r in applied_after if r["before"].split(":")[0] != "applicable"],
            "still_refused": collections.Counter(r["after"] for r in refused_after),
            "outcome": ("the owner can now apply the proposed scope"
                        if applied_after and not applied_before else
                        "no product satisfies the proposed scope"),
            "scorer_class_after": "A" if applied_after else candidate["scorer_compatibility"]["class"]})
        results.append(row)

    payload = {"_metadata": {
        "baseline_ref": args.baseline_ref,
        "identities": len(results),
        "simulated": sum(1 for r in results if r.get("simulated")),
        "note": "Applicability only. No record was created, no score computed or moved, "
                "no production data written."},
        "identities_detail": results}
    (OUT / "wave1_applicability_rerun.json").write_text(json.dumps(payload, indent=1, default=str))
    for row in results:
        print(f"{row['canonical_id']:<18} class {row['scorer_class_before']} -> {row['scorer_class_after']}  "
              f"{row['outcome']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
