#!/usr/bin/env python3
"""Primary-mass floor — policy simulation over the pinned corpus (read-only).

The diagnostic established that this is a v4 calibration question, not an amla
question: the floor is decisive for a third of the catalog and raises the
published tier of a fifth of it, always upward. This script does NOT propose a
constant. It asks what MECHANISM the floor should be, by scoring the same corpus
under several mechanisms and reporting the same metrics for each.

Every constant below is a PLACEHOLDER chosen to reveal the shape of a mechanism,
not a proposal. Two capped-uplift values are run precisely so the reader sees a
curve rather than a number. Production is untouched: nothing here writes a
config, a registry or a product.

Three corrections to the first diagnostic run are carried here:

  * ISOLATION. generic_evidence.PRIMARY_FLOOR_ENABLED gates BOTH floors - the
    primary-mass floor and the DRI-essential nutrition-authority floor share one
    `if` block (generic_evidence.py:317). Flipping it therefore removed the
    authority floor too, so a DRI-essential product whose mass floor was above
    10.0 appeared to fall all the way to its pipeline score when the authority
    floor would have caught it at 10.0. That overstates what the mass floor is
    worth. Here only _primary_mass_floor is intercepted, so the authority floor
    stays live in every variant and stays out of the comparison.
  * ANCHOR RESOLUTION. The first run mapped the floor's canonical name back to a
    registry record by matching `standard_name`, which missed 40 products: the
    floor reports the matched ACTIVE's canonical id (`bcaa`), while the record is
    named "Branched Chain Amino Acids". The anchoring entry is already in the
    product's own resolved matches, so it is identified with the owner's
    _canonical_from_entry instead of a name lookup.
  * VOCABULARY. The four states and every summary cut are imported from the
    diagnostic rather than restated, so the two reports cannot drift.

    python3 scripts/audits/evidence_expansion_2026_09/primary_mass_floor_calibration.py --slim <slim.jsonl>
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from primary_mass_floor_diagnostic import (  # noqa: E402
    FLOOR_ROUTES, _cut, _evidence_pillar, _pct, _spread, _tier_rank)

# What each mechanism is trying to guarantee. The wording matters more than the
# numbers: the policy question is "what is this floor for?", and a mechanism that
# cannot be stated in one sentence cannot be calibrated.
POLICY_INTENT = {
    "baseline": "Current production. A primary active with qualifying evidence gets an "
                "ABSOLUTE MINIMUM Evidence value, regardless of what the evidence pipeline "
                "computed for the formula.",
    "no_primary_mass_floor": "No such guarantee. Evidence is whatever the pipeline earns. "
                             "The DRI nutrition-authority floor still applies - this isolates "
                             "the mass floor, it does not remove every floor.",
    "capped_uplift_3": "A BOUNDED GUARANTEE: being the primary active can add at most 3.0 raw "
                       "points on top of what the formula's evidence already earned. Rank order "
                       "between a weak and a strong evidence base survives.",
    "capped_uplift_5": "The same mechanism at 5.0, so the reader sees a curve and not a number.",
    "direction_ceiling": "An absolute minimum, but one that cannot claim more than the effect "
                         "direction supports: a positive_weak primary cannot reach the same "
                         "Evidence value as a positive_strong one.",
    "study_strength_scaled": "An absolute minimum scaled by the strength of the study behind it, "
                             "using the scorer's OWN study-type hierarchy "
                             "(STUDY_TYPE_BASE_POINTS) rather than a new invented ladder. A "
                             "single RCT anchors proportionally less than a systematic review.",
}

# Placeholder magnitudes. Stated here, together, so nobody has to hunt for them.
UPLIFT_CAPS = {"capped_uplift_3": 3.0, "capped_uplift_5": 5.0}
DIRECTION_CEILINGS = {"positive_strong": 14.0, "positive_weak": 9.0, "mixed": 6.0}
DIRECTION_CEILING_DEFAULT = 9.0


def build_policies(ge):
    """Each policy maps (floor, anchor entry, pipeline raw) -> new floor.

    The pipeline raw is what score_evidence produces for this product with the
    mass floor suppressed - the production number, not a reconstruction.
    """
    base_points = ge.STUDY_TYPE_BASE_POINTS
    strongest = base_points.get("systematic_review_meta") or 1.0

    def direction_of(entry):
        return ge._norm_text((entry or {}).get("effect_direction"))

    def study_of(entry):
        return ge._norm_text((entry or {}).get("study_type"))

    return {
        "baseline": None,
        "no_primary_mass_floor": lambda floor, entry, pipeline: 0.0,
        "capped_uplift_3": lambda floor, entry, pipeline: min(floor, pipeline + UPLIFT_CAPS["capped_uplift_3"]),
        "capped_uplift_5": lambda floor, entry, pipeline: min(floor, pipeline + UPLIFT_CAPS["capped_uplift_5"]),
        "direction_ceiling": lambda floor, entry, pipeline: min(
            floor, DIRECTION_CEILINGS.get(direction_of(entry), DIRECTION_CEILING_DEFAULT)),
        "study_strength_scaled": lambda floor, entry, pipeline: floor * (
            (base_points.get(study_of(entry)) or 0.0) / strongest),
    }


def install_policy_hook(ge, state: dict):
    """Intercept ONLY _primary_mass_floor.

    Deliberately not PRIMARY_FLOOR_ENABLED: that flag also gates the DRI
    nutrition-authority floor, and conflating the two is the error this run
    exists to correct.
    """
    original = ge._primary_mass_floor

    def hooked(product, matches, sub_clinical_canonicals):
        floor, canonical = original(product, matches, sub_clinical_canonicals)
        policy = state.get("policy")
        if policy is None or floor <= 0.0:
            return floor, canonical
        entry = anchor_entry(ge, matches, canonical)
        adjusted = round(float(policy(floor, entry, state.get("pipeline_raw") or 0.0)), 4)
        if adjusted <= 0.0:
            return 0.0, None
        return min(adjusted, floor), canonical

    ge._primary_mass_floor = hooked
    return original


def anchor_entry(ge, matches, canonical):
    """The record the floor anchored on, found the way the floor found it."""
    if not canonical:
        return None
    best = None
    for entry in matches or []:
        if not isinstance(entry, dict):
            continue
        if ge._canonical_from_entry(entry) != canonical:
            continue
        if best is None or ge._entry_raw_points(entry) > ge._entry_raw_points(best):
            best = entry
    return best


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slim", required=True, type=Path)
    parser.add_argument("--out", default="primary_mass_floor_calibration.json")
    parser.add_argument("--report", default="PRIMARY_MASS_FLOOR_CALIBRATION.md")
    args = parser.parse_args()

    assert threading.active_count() == 1, (
        "this simulation swaps a module-level function; a concurrent worker could "
        "observe another policy's hook and produce a plausible but wrong result")

    from score_supplements_v4 import score_product_v4
    from scoring_v4.modules import generic_evidence as ge

    state: dict = {"policy": None, "pipeline_raw": 0.0}
    install_policy_hook(ge, state)
    policies = build_policies(ge)
    variants = [name for name in policies if name != "baseline"]

    by_brand = collections.defaultdict(dict)
    corpus_size = 0
    for line in args.slim.open():
        product = json.loads(line)
        corpus_size += 1
        if product["module"] not in FLOOR_ROUTES:
            continue
        by_brand[product["brand_dir"]][str(product["dsld_id"])] = {
            "module": product["module"],
            "active_scorable_rows": sum(
                1 for row in product.get("rows") or []
                if row.get("role_classification") == "active_scorable"),
        }
    eligible = sum(len(v) for v in by_brand.values())

    rows: list[dict] = []
    for brand_dir in sorted(by_brand):
        wanted = by_brand[brand_dir]
        for path in sorted(glob.glob(str(ROOT / f"scripts/products/output_{brand_dir}_enriched/enriched/*.json"))):
            for enriched in json.load(open(path)):
                dsld_id = str(enriched.get("dsld_id"))
                meta = wanted.get(dsld_id)
                if meta is None:
                    continue

                state["policy"] = None
                probe = ge.score_evidence(json.loads(json.dumps(enriched)), apply_primary_floor=True)
                floor = (probe.get("components") or {}).get("primary_evidence_floor")
                if not floor:
                    continue
                probe_meta = probe.get("metadata") or {}
                authority = bool(probe_meta.get("nutrition_authority_floor_applied"))
                canonical = probe_meta.get("primary_evidence_floor_canonical")
                matches, _ = ge.resolved_clinical_matches(json.loads(json.dumps(enriched)))
                entry = anchor_entry(ge, matches, canonical)

                # The production pipeline value with the mass floor suppressed.
                # Used as the reference a bounded uplift is measured against.
                state["policy"] = policies["no_primary_mass_floor"]
                pipeline_raw = ge.score_evidence(
                    json.loads(json.dumps(enriched)), apply_primary_floor=True).get("score") or 0.0
                state["policy"] = None

                row = {
                    "dsld_id": dsld_id, "brand_dir": brand_dir, "module": meta["module"],
                    "floor_kind": "nutrition_authority" if authority else "primary_mass",
                    "floor_anchor_canonical": canonical,
                    "floor_anchor_record": (entry or {}).get("id"),
                    "direction": (entry or {}).get("effect_direction"),
                    "study_type": (entry or {}).get("study_type"),
                    "evidence_level": (entry or {}).get("evidence_level"),
                    "active_scorable_rows": meta["active_scorable_rows"],
                    "single_active": meta["active_scorable_rows"] == 1,
                    "raw_floor": round(float(floor), 4),
                    "raw_pipeline_without_floor": round(float(pipeline_raw), 4),
                    "policies": {},
                }

                for name in ["baseline"] + variants:
                    # An authority-floor product is invariant under every policy
                    # here: its mass floor was already below 10.0, and no policy
                    # raises a floor. Scoring it six times would only cost time.
                    if authority and name != "baseline":
                        row["policies"][name] = dict(row["policies"]["baseline"])
                        continue
                    state["policy"] = policies[name]
                    state["pipeline_raw"] = float(pipeline_raw)
                    try:
                        result = score_product_v4(json.loads(json.dumps(enriched)))
                    finally:
                        state["policy"] = None
                    pillar = _evidence_pillar(result)
                    row["policies"][name] = {
                        "evidence": pillar.get("score"),
                        "total": result.get("quality_score_v4_100"),
                        "tier": result.get("quality_tier"),
                        "archetype": (pillar.get("components") or {}).get("archetype"),
                        "archetype_reference_max": (pillar.get("components") or {}).get("reference"),
                    }
                row["archetype"] = row["policies"]["baseline"]["archetype"]
                row["archetype_reference_max"] = row["policies"]["baseline"]["archetype_reference_max"]
                rows.append(row)
        print(f"{brand_dir}: {len(rows)} floored so far", file=sys.stderr, flush=True)

    payload = build_comparison(rows, corpus_size, eligible, variants)
    (OUT / args.out).write_text(json.dumps(payload, indent=1))
    (OUT / args.report).write_text(render_comparison(payload))
    print(json.dumps(payload["_metadata"]["policies"], indent=1))
    return 0


def _delta(a, b):
    if a is None or b is None:
        return None
    return round(float(a) - float(b), 4)


def build_comparison(rows: list[dict], corpus_size: int, eligible: int, variants: list[str]) -> dict:
    """Every variant is measured against BASELINE, not against no-floor, so the
    numbers answer "what changes if we ship this?" rather than "how far is this
    from nothing?"."""
    ranks = _tier_rank()
    mass = [r for r in rows if r["floor_kind"] == "primary_mass"]

    summaries = {}
    for name in variants:
        moved = []
        up = down = 0
        crossings = collections.Counter()
        for row in mass:
            base, cand = row["policies"]["baseline"], row["policies"][name]
            evidence_delta = _delta(cand["evidence"], base["evidence"])
            total_delta = _delta(cand["total"], base["total"])
            if not evidence_delta and not total_delta and cand["tier"] == base["tier"]:
                continue
            entry = {**{k: row[k] for k in (
                "dsld_id", "brand_dir", "module", "direction", "study_type", "archetype",
                "archetype_reference_max", "single_active", "raw_floor",
                "raw_pipeline_without_floor", "floor_anchor_canonical", "floor_anchor_record")},
                "delta_from_floor": evidence_delta,
                "final_total_score_delta_from_floor": total_delta,
                "changes_tier": cand["tier"] != base["tier"],
                "baseline_evidence": base["evidence"], "policy_evidence": cand["evidence"],
                "baseline_tier": base["tier"], "policy_tier": cand["tier"]}
            moved.append(entry)
            if cand["tier"] != base["tier"]:
                crossings[f"{base['tier']} -> {cand['tier']}"] += 1
                if ranks.get(cand["tier"], 99) < ranks.get(base["tier"], 99):
                    up += 1
                else:
                    down += 1

        weak = [r for r in moved if r["direction"] == "positive_weak"]
        strong = [r for r in moved if r["direction"] == "positive_strong"]
        summaries[name] = {
            "intent": POLICY_INTENT[name],
            "products_changed": len(moved),
            "pct_of_corpus": round(100 * len(moved) / corpus_size, 2) if corpus_size else 0,
            "tier_changes": up + down,
            "tier_changes_downward": down,
            "tier_changes_upward": up,
            "tier_crossings": dict(crossings.most_common(12)),
            "evidence_delta": _spread(moved, "delta_from_floor"),
            "final_score_delta": _spread(moved, "final_total_score_delta_from_floor"),
            "by_direction": _cut(moved, "direction"),
            "by_study_type": _cut(moved, "study_type"),
            "by_module": _cut(moved, "module"),
            "by_archetype": _cut(moved, "archetype"),
            "by_active_count": _cut(moved, "single_active"),
            "positive_weak": {
                "products_changed": len(weak),
                "median_evidence_after": _pct(
                    [r["policy_evidence"] for r in weak if r["policy_evidence"] is not None], 0.5),
                "p90_evidence_after": _pct(
                    [r["policy_evidence"] for r in weak if r["policy_evidence"] is not None], 0.9),
                "evidence_delta": _spread(weak, "delta_from_floor"),
                "tier_changes": sum(1 for r in weak if r["changes_tier"]),
            },
            "positive_strong": {
                "products_changed": len(strong),
                "median_evidence_after": _pct(
                    [r["policy_evidence"] for r in strong if r["policy_evidence"] is not None], 0.5),
                "evidence_delta": _spread(strong, "delta_from_floor"),
                "tier_changes": sum(1 for r in strong if r["changes_tier"]),
            },
        }

    baseline_weak = [r for r in mass if r["direction"] == "positive_weak"]
    return {"_metadata": {
        "question": "What guarantee should primary_evidence_floor provide? Mechanisms are "
                    "compared first; constants are placeholders chosen to reveal each "
                    "mechanism's shape.",
        "simulation_only": "No production constant, config, registry or product was changed. "
                           "Only generic_evidence._primary_mass_floor is intercepted in-process.",
        "isolation": "The DRI nutrition-authority floor stays live in EVERY variant. It is a "
                     "different rule that happens to share the primary_evidence_floor component "
                     "key, and the first diagnostic run conflated them.",
        "corpus": {"products_scored": corpus_size,
                   "eligible_for_primary_mass_floor": eligible,
                   "receiving_a_nonzero_primary_mass_floor": len(mass),
                   "separate_dri_nutrition_authority_floor_population": len(rows) - len(mass)},
        "baseline_positive_weak_products": len(baseline_weak),
        "baseline_positive_weak_median_evidence": _pct(
            [r["policies"]["baseline"]["evidence"] for r in baseline_weak
             if r["policies"]["baseline"]["evidence"] is not None], 0.5),
        "placeholder_constants": {"uplift_caps": UPLIFT_CAPS,
                                  "direction_ceilings": DIRECTION_CEILINGS,
                                  "direction_ceiling_default": DIRECTION_CEILING_DEFAULT,
                                  "study_strength_scale": "STUDY_TYPE_BASE_POINTS[st] / "
                                                          "STUDY_TYPE_BASE_POINTS[systematic_review_meta]"},
        "policies": summaries,
    }, "products": rows}


def render_comparison(payload: dict) -> str:
    meta = payload["_metadata"]
    corpus = meta["corpus"]

    def spread(block):
        return f"{block['median']} / {block['p90']} / {block['max']}"

    out = [
        "# PRIMARY-MASS FLOOR — POLICY SIMULATION", "",
        "Simulation only. No production constant, config, registry or product changed.", "",
        "Each row is a MECHANISM, not a proposal. The constants are placeholders picked to reveal "
        "the shape of each mechanism; two uplift caps are run so the reader sees a curve. The "
        "policy question comes first: **what guarantee is this floor meant to provide?**", "",
        f"Corpus: {corpus['products_scored']:,} scored, "
        f"{corpus['eligible_for_primary_mass_floor']:,} on a floor-applying route, "
        f"{corpus['receiving_a_nonzero_primary_mass_floor']:,} receiving a primary-mass floor. "
        f"The {corpus['separate_dri_nutrition_authority_floor_population']:,} DRI "
        "nutrition-authority products are held out of every comparison and the authority floor "
        "stays live in every variant.", "",
        "| policy | products changed | % of corpus | Evidence delta med/p90/max | "
        "final-score delta med/p90/max | tier changes (down/up) |",
        "|---|---:|---:|---|---|---|",
    ]
    for name, block in meta["policies"].items():
        out.append(
            f"| `{name}` | {block['products_changed']:,} | {block['pct_of_corpus']} | "
            f"{spread(block['evidence_delta'])} | {spread(block['final_score_delta'])} | "
            f"{block['tier_changes']} ({block['tier_changes_downward']}/{block['tier_changes_upward']}) |")
    out += ["", "## What each mechanism claims", ""]
    for name, block in meta["policies"].items():
        out += [f"### `{name}`", "", block["intent"], "",
                f"- positive_weak changed: **{block['positive_weak']['products_changed']:,}**, "
                f"median Evidence after: **{block['positive_weak']['median_evidence_after']}**, "
                f"tier changes: {block['positive_weak']['tier_changes']:,}",
                f"- positive_strong changed: **{block['positive_strong']['products_changed']:,}**, "
                f"median Evidence after: **{block['positive_strong']['median_evidence_after']}**, "
                f"tier changes: {block['positive_strong']['tier_changes']:,}", ""]
        lines = ["| effect direction | products | Evidence delta med/p90/max | "
                 "final-score delta med/p90/max | changes tier |", "|---|---:|---|---|---:|"]
        for key, cut in block["by_direction"].items():
            lines.append(f"| `{key}` | {cut['products']} | {spread(cut['evidence_delta'])} | "
                         f"{spread(cut['final_score_delta'])} | {cut['changes_tier']} |")
        out += lines + [""]
    out += ["## Placeholder constants", "",
            "```", json.dumps(meta["placeholder_constants"], indent=1), "```", "",
            "Pick the mechanism first. These numbers exist to show what each mechanism does, not "
            "to be adopted.", ""]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
