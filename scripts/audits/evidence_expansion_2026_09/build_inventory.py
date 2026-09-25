#!/usr/bin/env python3
"""Phase 1 evidence audit: Evidence=0 taxonomy, identity inventory, coverage (read-only).

Input is the slim corpus written by ``extract_corpus.py``; its evidence joins come
from the production seam, so nothing here re-derives matching. Identity keys use
the scorer's own key space (``generic_evidence._row_identity_keys`` /
``_entry_identity_keys``).

Three columns are kept apart everywhere: evidence strength, applicability, and
review completeness. The 202 legacy records carry no review state, so they are
reported as ``legacy_review_state_not_established``, never as reviewed.

Evidence=0 taxonomy (one primary letter per product, every applicable reason kept):
  H no active row at all              G accepted match with raw points > 0 (scorer defect candidate)
  E accepted matches, all zero-point  D rejected on dose
  C rejected on form/identity, no mapped active, or a record exists but never joined
  F formula/combination-only record
  B identity reviewed, no qualifying evidence (documented bounded search)
  A identity not reviewed (no record)

    python3 scripts/audits/evidence_expansion_2026_09/build_inventory.py --slim <slim.jsonl>
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

from clinical_applicability import reviewed_entries  # noqa: E402
from scoring_v4.modules import generic_evidence as ge  # noqa: E402

PROBIOTIC_LANE = "probiotic"
ACTIVE_ROLES = {"active_scorable", "recognized_non_scorable", "active_unmapped"}
DOSE_REASONS = {"clinical_dose_unresolved", "below_applicable_clinical_dose", "above_applicable_clinical_dose"}
FORM_REASONS = {"clinical_form_mismatch", "clinical_form_excluded", "clinical_identity_excluded",
                "clinical_delivery_mismatch", "clinical_source_label_unresolved", "clinical_source_row_unresolved"}
FORMULA_REASONS = {"formula_reference_not_individual_evidence"}
PRECEDENCE = "HGEDCFBA"
LOW_EVIDENCE = 8.0


def is_probiotic_row(row: dict) -> bool:
    return "probiotic" in str(row.get("category") or "").lower()


def reviewed_identity_keys() -> set[str]:
    """Identities with a documented bounded search that found no qualifying evidence.

    Only search logs written by this workflow count; none exist before Wave 1.
    """
    keys: set[str] = set()
    for path in OUT.glob("*search_log*.json"):
        for item in json.loads(path.read_text()).get("identities", []):
            if item.get("outcome") == "no_qualifying_evidence_in_documented_scope":
                keys.add(ge._canonical_text(item.get("canonical_id")))
    return keys


def _row_has_record(row: dict, index: dict) -> bool:
    return any(key in index for key in ge._row_identity_keys(row))


def is_evidence_target_row(row: dict) -> bool:
    """An active the enricher kept and the label delivers: not probiotic-lane, not demoted, not a 0-amount line."""
    return (not is_probiotic_row(row) and row.get("quantity") != 0
            and row.get("role_classification") in ACTIVE_ROLES)


def classify_zero(product: dict, reviewed_no_evidence: set[str], index: dict) -> tuple[str, list[str], list[str]]:
    """Primary letter, every applicable letter, and sub-reason codes for one Evidence=0 product."""
    reasons: set[str] = set()
    details: set[str] = set()
    all_rows = [r for r in product["rows"] if not is_probiotic_row(r)]
    rows = [r for r in all_rows if is_evidence_target_row(r)]
    if not rows:
        reasons.add("H")
        demoted = [r for r in all_rows if r.get("role_classification") not in ACTIVE_ROLES]
        if demoted:
            for reason in product.get("skipped_reasons_breakdown") or {"unrecorded": 1}:
                details.add(f"H_label_active_demoted_{reason}")
        else:
            details.add("H_only_zero_amount_panel_rows" if all_rows else "H_no_active_rows")
    registry = reviewed_entries()
    for match in product["accepted_matches"]:
        entry = registry.get(match["id"]) or match
        points = ge._entry_raw_points(entry) > 0
        reasons.add("G" if points else "E")
        details.add("G_accepted_match_with_points" if points else "E_accepted_match_zero_points")
    for rejected in product["rejected_matches"]:
        code = rejected.get("reason_code")
        letter = "D" if code in DOSE_REASONS else "F" if code in FORMULA_REASONS else "C"
        reasons.add(letter)
        details.add(f"{letter}_rejected_{code}")
    mapped = [r for r in rows if r.get("mapped") and r.get("canonical_id")]
    if rows and not mapped:
        reasons.add("C")
        details.add("C_no_mapped_active")
    joined = bool(product["accepted_matches"] or product["rejected_matches"])
    for row in mapped:
        if not _row_has_record(row, index):
            letter = "B" if ge._canonical_text(row["canonical_id"]) in reviewed_no_evidence else "A"
            reasons.add(letter)
            details.add(f"{letter}_{row['canonical_id']}")
        elif not joined:
            # Shares the scorer's key space with a record but the enricher never joined it:
            # usually a narrower record (Panax ginseng) under a broader canonical, or an excluded form.
            reasons.add("C")
            details.add("C_record_key_overlap_not_joined")
    primary = next(letter for letter in PRECEDENCE if letter in reasons) if reasons else "C"
    return primary, sorted(reasons, key=PRECEDENCE.index), sorted(details)


def recoverable_by_curation(product: dict, index: dict) -> bool:
    """Evidence curation alone could change this product: a mapped, dose-bearing active with no record."""
    return any(r.get("mapped") and r.get("canonical_id") and r.get("has_dose") and is_evidence_target_row(r)
               and not _row_has_record(r, index) for r in product["rows"])


def registry_index() -> dict[str, list[str]]:
    index: dict[str, list[str]] = collections.defaultdict(list)
    for entry_id, entry in reviewed_entries().items():
        for key in ge._entry_identity_keys(entry):
            index[key].append(entry_id)
    return index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slim", required=True, type=Path)
    args = parser.parse_args()
    products = [json.loads(line) for line in args.slim.open()]
    reviewed_no_evidence = reviewed_identity_keys()
    index = registry_index()
    registry = reviewed_entries()

    # ---- Evidence=0 taxonomy -------------------------------------------------------------------
    zero_rows, letters, letters_by_module, reason_sets = [], collections.Counter(), collections.Counter(), collections.Counter()
    detail_counts = collections.Counter()
    recoverable = collections.Counter()
    for p in products:
        if p["evidence"] != 0 or p["module"] == PROBIOTIC_LANE:
            continue
        primary, reasons, details = classify_zero(p, reviewed_no_evidence, index)
        can_recover = recoverable_by_curation(p, index)
        letters[primary] += 1
        letters_by_module[(p["module"], primary)] += 1
        reason_sets["+".join(reasons)] += 1
        detail_counts.update(d for d in details if not d.startswith(("A_", "B_")))
        recoverable[can_recover] += 1
        zero_rows.append({"dsld_id": p["dsld_id"], "brand": p["brand_name"], "product_name": p["product_name"],
                          "module": p["module"], "primary": primary, "reasons": reasons, "details": details,
                          "recoverable_by_curation_alone": can_recover,
                          "accepted_match_ids": [m["id"] for m in p["accepted_matches"]],
                          "rejected": p["rejected_matches"],
                          "active_canonicals": sorted({r.get("canonical_id") or f"unmapped:{r.get('name')}"
                                                       for r in p["rows"] if not is_probiotic_row(r)})})

    # ---- Identity inventory (non-probiotic lane) ----------------------------------------------
    ident = collections.defaultdict(lambda: {"slots": 0, "products": set(), "brands": set(), "forms": collections.Counter(),
                                             "evidence": {}, "dosed_slots": 0, "form_unmapped_slots": 0, "names": collections.Counter(),
                                             "categories": collections.Counter(), "modules": collections.Counter(),
                                             "roles": collections.Counter(), "keys": set()})
    normalization = collections.defaultdict(lambda: {"slots": 0, "products": set(), "brands": set()})
    total_slots = mapped_slots = 0
    for p in products:
        if p["module"] == PROBIOTIC_LANE:
            continue
        for row in p["rows"]:
            if not is_evidence_target_row(row):
                continue
            total_slots += 1
            if not (row.get("mapped") and row.get("canonical_id")):
                key = ge._canonical_text(row.get("standard_name") or row.get("name")) or "(blank)"
                bucket = normalization[key]
                bucket["slots"] += 1
                bucket["products"].add(p["dsld_id"])
                bucket["brands"].add(p["brand_name"])
                continue
            mapped_slots += 1
            item = ident[row["canonical_id"]]
            item["slots"] += 1
            item["products"].add(p["dsld_id"])
            item["brands"].add(p["brand_name"])
            item["forms"][row.get("form_id") or "(none)"] += 1
            item["evidence"][p["dsld_id"]] = p["evidence"]
            item["dosed_slots"] += bool(row.get("has_dose"))
            item["form_unmapped_slots"] += row.get("form_match_status") == "unmapped"
            item["names"][row.get("standard_name") or row.get("name")] += 1
            item["categories"][row.get("category") or "(none)"] += 1
            item["modules"][p["module"]] += 1
            item["roles"][row.get("role_classification")] += 1
            item["keys"] |= ge._row_identity_keys(row)

    inventory = []
    for canonical_id, item in ident.items():
        entry_ids = sorted({eid for key in item["keys"] for eid in index.get(key, ())})
        legacy = [registry[e] for e in entry_ids]
        ev = list(item["evidence"].values())
        contexts = sum(len(e.get("study_contexts") or []) for e in legacy)
        inventory.append({
            "canonical_id": canonical_id,
            "top_name": item["names"].most_common(1)[0][0],
            "category": item["categories"].most_common(1)[0][0],
            "slots": item["slots"], "products": len(item["products"]), "brands": len(item["brands"]),
            "dosed_slot_share": round(item["dosed_slots"] / item["slots"], 3),
            "form_unmapped_slot_share": round(item["form_unmapped_slots"] / item["slots"], 3),
            "top_forms": item["forms"].most_common(5),
            "modules": dict(item["modules"]),
            "row_roles": dict(item["roles"]),
            "evidence_mean": round(sum(ev) / len(ev), 2),
            "evidence_zero_products": sum(v == 0 for v in ev),
            "evidence_le8_products": sum(v <= LOW_EVIDENCE for v in ev),
            "registry_entry_ids_key_overlap": entry_ids,
            "registry_study_types": sorted({str(e.get("study_type")) for e in legacy}),
            "registry_effect_directions": sorted({str(e.get("effect_direction")) for e in legacy}),
            "registry_dose_reference": any(e.get("min_clinical_dose") is not None
                                           or (e.get("applicability") or {}).get("minimum_daily_dose") is not None
                                           for e in legacy),
            "study_contexts": contexts,
            "review_state": ("legacy_review_state_not_established" if legacy else
                             "reviewed_no_qualifying_evidence_in_documented_scope"
                             if ge._canonical_text(canonical_id) in reviewed_no_evidence else "not_reviewed"),
        })
    inventory.sort(key=lambda r: (-r["slots"], r["canonical_id"]))

    cumulative, cut_lines = 0, {}
    for rank, row in enumerate(inventory, 1):
        cumulative += row["slots"]
        row["cumulative_mapped_slot_share"] = round(cumulative / mapped_slots, 4)
        for cut in (0.8, 0.9, 0.95):
            if cut not in cut_lines and cumulative / mapped_slots >= cut:
                cut_lines[cut] = rank

    state_slots = collections.Counter()
    for row in inventory:
        state_slots[row["review_state"]] += row["slots"]
    category_rollup = collections.defaultdict(collections.Counter)
    for row in inventory:
        category_rollup[row["category"]][row["review_state"]] += row["slots"]

    norm_rows = sorted(({"normalized_name": k, "slots": v["slots"], "products": len(v["products"]),
                         "brands": len(v["brands"])} for k, v in normalization.items()),
                       key=lambda r: (-r["slots"], r["normalized_name"]))

    scored_non_probiotic = sum(p["module"] != PROBIOTIC_LANE for p in products)
    summary = {
        "built_from": str(args.slim.name),
        "scored_products": len(products),
        "scored_products_non_probiotic_lane": scored_non_probiotic,
        "evidence_zero_non_probiotic_lane": len(zero_rows),
        "evidence_zero_probiotic_lane": sum(p["evidence"] == 0 and p["module"] == PROBIOTIC_LANE for p in products),
        "taxonomy_primary": dict(sorted(letters.items(), key=lambda kv: PRECEDENCE.index(kv[0]))),
        "taxonomy_primary_by_module": {f"{m}:{l}": n for (m, l), n in sorted(letters_by_module.items())},
        "taxonomy_reason_sets": dict(reason_sets.most_common()),
        "taxonomy_detail_counts": dict(detail_counts.most_common()),
        "recoverable_by_curation_alone": recoverable[True],
        "blocked_or_already_matched": recoverable[False],
        "product_active_slots_non_probiotic": total_slots,
        "mapped_slots": mapped_slots,
        "unmapped_slots": total_slots - mapped_slots,
        "unique_mapped_identities": len(inventory),
        "identities_for_mapped_slot_share": {str(k): v for k, v in sorted(cut_lines.items())},
        "mapped_slots_by_review_state": dict(state_slots),
        "identities_by_review_state": dict(collections.Counter(r["review_state"] for r in inventory)),
        "documented_bounded_reviews": len(reviewed_no_evidence),
        "legacy_registry_entries": len(registry),
    }
    (OUT / "zero_evidence_taxonomy.json").write_text(json.dumps({"summary": summary, "products": zero_rows}, indent=1))
    (OUT / "inventory.json").write_text(json.dumps({"summary": summary, "category_rollup":
        {k: dict(v) for k, v in sorted(category_rollup.items())}, "identities": inventory}, indent=1))
    (OUT / "normalization_queue.json").write_text(json.dumps({"summary": {"unmapped_slots": total_slots - mapped_slots,
        "distinct_unmapped_names": len(norm_rows)}, "items": norm_rows}, indent=1))
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
