#!/usr/bin/env python3
"""Primary-mass floor — policy simulation over the pinned corpus (read-only).

The diagnostic established that this is a v4 calibration question, not an amla
question. This script does NOT propose a constant. It asks what MECHANISM the
floor should be, by scoring the same corpus under several mechanisms and
reporting the same metrics for each. Production is untouched: nothing here
writes a config, a registry or a product.

WHY THE EARLIER A/B WAS THROWN AWAY
-----------------------------------
generic_evidence.PRIMARY_FLOOR_ENABLED gates BOTH floors. The primary-mass floor
and the DRI-essential nutrition-authority floor share one `if` block
(generic_evidence.py:317). Flipping that flag therefore removed the authority
floor too, so a DRI-essential product whose mass floor was above 10.0 looked as
though it fell all the way to its pipeline score when the authority floor would
have caught it at 10.0 raw. Every delta from that run credited the mass floor
with points a different rule supplies.

Here only generic_evidence._primary_mass_floor is intercepted. The authority
floor stays live in every variant, and that is asserted per product rather than
asserted in prose.

CONTRACTS THIS RUN ENFORCES (it aborts rather than reporting a violation)
------------------------------------------------------------------------
1. BASELINE REPRODUCTION. Baseline is scored with the hook UNINSTALLED, so it is
   production by construction, not merely equal to it. Every product is then
   scored a second time through the installed-but-passthrough hook and the two
   must agree on Evidence, total and tier. A transparent hook is the precondition
   for every other number here.
2. ISOLATION. Where the authority floor applies at baseline it must still apply
   with the mass floor removed, and the resulting raw score must still clear
   NUTRITION_AUTHORITY_FLOOR. Product 261812 is carried as a named regression
   case in the report.
3. NO NEW DIRECTION SEMANTICS. direction_ceiling reuses
   EFFECT_DIRECTION_MULTIPLIERS and PRIMARY_FLOOR_MODERATE. There is no second
   table of what a direction is worth.
4. HIERARCHY. study_strength_scaled is checked for inversions introduced
   downstream by the archetype rescale, within archetype and direction.

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

# A product carried through the report as a named regression case for the
# isolation contract: under the old flag-based A/B it read 14.0 -> 8.7; with the
# authority floor left live the honest answer is 14.0 -> 11.8.
ISOLATION_REGRESSION_PRODUCT = "261812"

UPLIFT_CAPS = {"capped_uplift_3": 3.0, "capped_uplift_5": 5.0}

# Where a cap is applied is policy-significant, so it is stated rather than left
# implicit in the code. Every policy here operates in RAW Evidence space, inside
# _primary_mass_floor, BEFORE the archetype rescale. That is the space the floor
# constants themselves live in (14.0 / 11.0 / 10.0), so a cap expressed there
# means the same thing for every product. The same number applied on the public
# 0-20 scale would NOT: public = raw / archetype_reference * 20, so a 3.0 public
# cap is 2.7 raw under an 18.0 reference and 2.55 under a 17.0 one, and the
# policy would silently mean something different per archetype. A public-space
# cap is a coherent alternative policy, but it needs a different hook (the
# rescale happens in the quality-score assembler, not in generic_evidence) and it
# would have to decide what it means for archetypes with different references.
CAP_SPACE = ("raw Evidence space, inside _primary_mass_floor, BEFORE the archetype rescale - "
             "the same space the 14.0/11.0/10.0 floor constants live in. A cap of the same "
             "magnitude applied on the public 0-20 scale would mean a different raw amount per "
             "archetype (18.0 vs 17.0 references), so it is NOT interchangeable.")

POLICY_INTENT = {
    "baseline": "Current production. A primary active with qualifying evidence gets an ABSOLUTE "
                "MINIMUM Evidence value, regardless of what the evidence pipeline computed for "
                "the formula.",
    "no_primary_mass_floor": "No such guarantee. Evidence is whatever the pipeline earns - but "
                             "the DRI nutrition-authority floor still applies. This isolates the "
                             "mass floor; it does not remove every floor.",
    "capped_uplift_3": "A BOUNDED GUARANTEE: being the primary active can add at most 3.0 raw "
                       "points on top of what the formula's evidence already earned. Rank order "
                       "between a weak and a strong evidence base survives instead of collapsing "
                       "to a shared minimum.",
    "capped_uplift_5": "The same mechanism at 5.0, so the reader sees a curve and not a number.",
    "direction_ceiling": "Still an absolute minimum, but only a positive_strong primary may "
                         "anchor on the STRONG floor base. Every weaker direction anchors on the "
                         "MODERATE base the scorer already defines, weighted by the direction "
                         "multiplier the scorer already owns. No new direction table.",
    "study_strength_scaled": "An absolute minimum scaled by the strength of the study behind it, "
                             "using the scorer's OWN study-type hierarchy (STUDY_TYPE_BASE_POINTS) "
                             "rather than a new invented ladder. A single RCT anchors "
                             "proportionally less than a systematic review.",
}


def build_policies(ge):
    """Each policy maps (floor, anchoring entry, pipeline raw) -> new floor.

    `pipeline raw` is what score_evidence produces for this product with the mass
    floor suppressed and the authority floor still live - the production number,
    not a reconstruction.
    """
    base_points = ge.STUDY_TYPE_BASE_POINTS
    strongest = base_points.get("systematic_review_meta") or 1.0

    def direction_of(entry):
        return ge._norm_text((entry or {}).get("effect_direction"))

    def study_of(entry):
        return ge._norm_text((entry or {}).get("study_type"))

    def direction_ceiling(floor, entry, pipeline):
        # Reuses the two owners that already exist: the MODERATE floor base and
        # EFFECT_DIRECTION_MULTIPLIERS. Deliberately NOT a second table of what a
        # direction is worth - that is exactly the duplication this project keeps
        # removing elsewhere.
        direction = direction_of(entry)
        if direction == "positive_strong":
            return floor
        multiplier = ge.EFFECT_DIRECTION_MULTIPLIERS.get(direction, 0.0)
        return min(floor, ge.PRIMARY_FLOOR_MODERATE * multiplier)

    return {
        "baseline": None,
        "no_primary_mass_floor": lambda floor, entry, pipeline: 0.0,
        "capped_uplift_3": lambda floor, entry, pipeline: min(
            floor, pipeline + UPLIFT_CAPS["capped_uplift_3"]),
        "capped_uplift_5": lambda floor, entry, pipeline: min(
            floor, pipeline + UPLIFT_CAPS["capped_uplift_5"]),
        "direction_ceiling": direction_ceiling,
        "study_strength_scaled": lambda floor, entry, pipeline: floor * (
            (base_points.get(study_of(entry)) or 0.0) / strongest),
    }


def anchor_entry(ge, matches, canonical):
    """The record the floor anchored on, found the way the floor found it.

    NOT by reverse-matching the registry's `standard_name` against the floor's
    canonical id. That is how an earlier run lost 40 products: the floor reports
    the matched ACTIVE's canonical id (`bcaa`) while the record is named
    "Branched Chain Amino Acids". The anchoring entry is already in the product's
    own resolved matches, so it is identified with the scorer's own accessor.
    """
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


def signature(result: dict):
    pillar = _evidence_pillar(result)
    return (pillar.get("score"), result.get("quality_score_v4_100"), result.get("quality_tier"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slim", type=Path, help="Required unless --resummarize.")
    parser.add_argument("--out", default="primary_mass_floor_calibration.json")
    parser.add_argument("--report", default="PRIMARY_MASS_FLOOR_CALIBRATION.md")
    parser.add_argument("--resummarize", type=Path, help=(
        "Rebuild the comparison from a previous run's per-product rows instead of "
        "re-scoring. Same build_comparison(), so there is no second implementation."))
    args = parser.parse_args()

    if not args.slim and not args.resummarize:
        parser.error("--slim is required unless --resummarize is given")

    if args.resummarize:
        previous = json.loads(args.resummarize.read_text())
        meta = previous["_metadata"]
        pop = meta["populations"]
        variants = [n for n in meta["policies"]]
        payload = build_comparison(previous["products"], pop["products_scored"],
                                   pop["eligible_for_primary_mass_floor"], variants,
                                   meta["contracts"]["detail"])
        (OUT / args.out).write_text(json.dumps(payload, indent=1))
        (OUT / args.report).write_text(render_comparison(payload))
        print(json.dumps(payload["_metadata"]["populations"], indent=1))
        return 0

    assert threading.active_count() == 1, (
        "this simulation swaps a module-level function; a concurrent worker could "
        "observe another policy's hook and produce a plausible but wrong result")

    from score_supplements_v4 import score_product_v4
    from scoring_v4.modules import generic_evidence as ge
    import clinical_applicability as ca

    reviewed = ca.reviewed_entries()
    state: dict = {"policy": None, "pipeline_raw": 0.0}
    original_floor_fn = ge._primary_mass_floor

    def hooked(product, matches, sub_clinical_canonicals):
        floor, canonical = original_floor_fn(product, matches, sub_clinical_canonicals)
        policy = state.get("policy")
        if policy is None or floor <= 0.0:
            return floor, canonical
        entry = anchor_entry(ge, matches, canonical)
        adjusted = round(float(policy(floor, entry, state.get("pipeline_raw") or 0.0)), 4)
        if adjusted <= 0.0:
            return 0.0, None
        return min(adjusted, floor), canonical

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
    contract_violations: list[dict] = []
    for brand_dir in sorted(by_brand):
        wanted = by_brand[brand_dir]
        for path in sorted(glob.glob(str(ROOT / f"scripts/products/output_{brand_dir}_enriched/enriched/*.json"))):
            for enriched in json.load(open(path)):
                dsld_id = str(enriched.get("dsld_id"))
                meta = wanted.get(dsld_id)
                if meta is None:
                    continue
                blob = lambda: json.loads(json.dumps(enriched))

                ge._primary_mass_floor = original_floor_fn
                state["policy"] = None
                probe = ge.score_evidence(blob(), apply_primary_floor=True)
                floor = (probe.get("components") or {}).get("primary_evidence_floor")
                if not floor:
                    continue
                probe_meta = probe.get("metadata") or {}
                authority_at_baseline = bool(probe_meta.get("nutrition_authority_floor_applied"))
                canonical = probe_meta.get("primary_evidence_floor_canonical")
                matches, _ = ge.resolved_clinical_matches(blob())
                entry = anchor_entry(ge, matches, canonical)

                # CONTRACT 1 - baseline is production, by construction: scored with
                # the hook uninstalled entirely.
                production = score_product_v4(blob())

                ge._primary_mass_floor = hooked
                # ...and proved transparent: the same product through the
                # installed-but-passthrough hook must land on the same numbers.
                passthrough = score_product_v4(blob())
                if signature(production) != signature(passthrough):
                    contract_violations.append({
                        "contract": "baseline_reproduction", "dsld_id": dsld_id,
                        "production": signature(production), "hooked_passthrough": signature(passthrough)})

                # The pipeline value with the mass floor suppressed and the
                # authority floor left live. Doubles as the isolation evidence.
                state["policy"] = policies["no_primary_mass_floor"]
                no_floor_probe = ge.score_evidence(blob(), apply_primary_floor=True)
                state["policy"] = None
                pipeline_raw = float(no_floor_probe.get("score") or 0.0)
                no_floor_meta = no_floor_probe.get("metadata") or {}
                authority_without_mass_floor = bool(
                    no_floor_meta.get("nutrition_authority_floor_applied"))

                # CONTRACT 2 - removing the mass floor must not remove authority credit.
                if authority_at_baseline and not authority_without_mass_floor:
                    contract_violations.append({
                        "contract": "authority_floor_survives", "dsld_id": dsld_id,
                        "detail": "authority floor applied at baseline but not with the mass floor removed"})
                if authority_without_mass_floor and pipeline_raw + 1e-6 < ge.NUTRITION_AUTHORITY_FLOOR:
                    contract_violations.append({
                        "contract": "authority_floor_value", "dsld_id": dsld_id,
                        "raw_without_mass_floor": pipeline_raw,
                        "expected_at_least": ge.NUTRITION_AUTHORITY_FLOOR})

                row = {
                    "dsld_id": dsld_id, "brand_dir": brand_dir, "module": meta["module"],
                    "floor_kind": "nutrition_authority" if authority_at_baseline else "primary_mass",
                    "floor_anchor_canonical": canonical,
                    "floor_anchor_record": (entry or {}).get("id"),
                    "floor_anchor_standard_name": (entry or {}).get("standard_name"),
                    # Some floors anchor on a RECOVERED match carried on the product
                    # blob rather than on a record in the reviewed registry. A 14.0
                    # floor resting on an entry no reviewer currently owns is worth
                    # counting; it is not fixed here, the freeze holds.
                    "floor_anchor_in_reviewed_registry": (entry or {}).get("id") in reviewed,
                    "direction": (entry or {}).get("effect_direction"),
                    "study_type": (entry or {}).get("study_type"),
                    "evidence_level": (entry or {}).get("evidence_level"),
                    "active_scorable_rows": meta["active_scorable_rows"],
                    "single_active": meta["active_scorable_rows"] == 1,
                    "raw_floor": round(float(floor), 4),
                    "raw_without_mass_floor": round(pipeline_raw, 4),
                    "authority_floor_at_baseline": authority_at_baseline,
                    "authority_floor_without_mass_floor": authority_without_mass_floor,
                    "policies": {},
                }

                base_sig = signature(production)
                row["policies"]["baseline"] = {
                    "evidence": base_sig[0], "total": base_sig[1], "tier": base_sig[2],
                    "archetype": (_evidence_pillar(production).get("components") or {}).get("archetype"),
                    "archetype_reference_max": (
                        _evidence_pillar(production).get("components") or {}).get("reference"),
                }
                for name in variants:
                    # An authority-floor product is invariant under every policy
                    # here: its mass floor was already below 10.0 and no policy
                    # raises a floor. Scoring it five more times only costs time.
                    if authority_at_baseline:
                        row["policies"][name] = dict(row["policies"]["baseline"])
                        continue
                    state["policy"] = policies[name]
                    state["pipeline_raw"] = pipeline_raw
                    try:
                        result = score_product_v4(blob())
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
                ge._primary_mass_floor = original_floor_fn
                row["archetype"] = row["policies"]["baseline"]["archetype"]
                row["archetype_reference_max"] = row["policies"]["baseline"]["archetype_reference_max"]
                rows.append(row)
        print(f"{brand_dir}: {len(rows)} floored so far, "
              f"{len(contract_violations)} contract violations", file=sys.stderr, flush=True)

    ge._primary_mass_floor = original_floor_fn
    payload = build_comparison(rows, corpus_size, eligible, variants, contract_violations)
    (OUT / args.out).write_text(json.dumps(payload, indent=1))
    (OUT / args.report).write_text(render_comparison(payload))
    print(json.dumps(payload["_metadata"]["contracts"], indent=1))
    print(json.dumps(payload["_metadata"]["populations"], indent=1))
    return 2 if contract_violations else 0


def _delta(a, b):
    if a is None or b is None:
        return None
    return round(float(a) - float(b), 4)


def hierarchy_inversions(rows: list[dict], policy: str, ge_base_points: dict) -> list[dict]:
    """Does the archetype rescale invert the study-type hierarchy downstream?

    Compared within (archetype, direction) so the only thing varying is study
    type. Across archetypes the references differ by design, and that is a
    property of the archetype system at baseline too - not something a floor
    policy introduces.
    """
    grouped = collections.defaultdict(lambda: collections.defaultdict(list))
    for row in rows:
        if row["floor_kind"] != "primary_mass":
            continue
        value = row["policies"][policy]["evidence"]
        if value is None or not row["study_type"]:
            continue
        grouped[(row["archetype"], row["direction"])][row["study_type"]].append(float(value))

    inversions = []
    for (archetype, direction), by_study in grouped.items():
        medians = {st: _pct(values, 0.5) for st, values in by_study.items()}
        for stronger, stronger_median in medians.items():
            for weaker, weaker_median in medians.items():
                if ge_base_points.get(stronger, 0) <= ge_base_points.get(weaker, 0):
                    continue
                if weaker_median is not None and stronger_median is not None and weaker_median > stronger_median:
                    inversions.append({
                        "archetype": archetype, "direction": direction,
                        "stronger_study_type": stronger, "stronger_median_evidence": stronger_median,
                        "weaker_study_type": weaker, "weaker_median_evidence": weaker_median})
    return inversions


def build_comparison(rows, corpus_size, eligible, variants, contract_violations) -> dict:
    """Every variant is measured against the PRODUCTION baseline, so the numbers
    answer "what changes if we ship this?" rather than "how far is this from
    nothing?"."""
    from scoring_v4.modules import generic_evidence as ge

    ranks = _tier_rank()
    mass = [r for r in rows if r["floor_kind"] == "primary_mass"]
    authority_population = [r for r in rows if r["floor_kind"] != "primary_mass"]

    decisive, shadowed_authority, shadowed_pipeline = [], [], []
    for row in mass:
        base = row["policies"]["baseline"]["evidence"]
        without = row["policies"]["no_primary_mass_floor"]["evidence"]
        # Which value is BINDING once the mass floor is gone, not merely which
        # rule was available. nutrition_authority_floor_applied is set whenever an
        # essential nutrient is mass-dominant, including when the pipeline already
        # scored above 10.0 and the authority floor changes nothing.
        authority_is_binding = (
            row["authority_floor_without_mass_floor"]
            and abs(row["raw_without_mass_floor"] - ge.NUTRITION_AUTHORITY_FLOOR) < 1e-6)
        row["authority_floor_is_binding_without_mass_floor"] = authority_is_binding
        if _delta(base, without):
            decisive.append(row)
        elif authority_is_binding:
            shadowed_authority.append(row)
        else:
            shadowed_pipeline.append(row)

    summaries = {}
    for name in variants:
        moved, gains = [], []
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
                "raw_without_mass_floor", "floor_anchor_canonical", "floor_anchor_record")},
                "delta_from_floor": evidence_delta,
                "final_total_score_delta_from_floor": total_delta,
                "changes_tier": cand["tier"] != base["tier"],
                "baseline_evidence": base["evidence"], "policy_evidence": cand["evidence"],
                "baseline_tier": base["tier"], "policy_tier": cand["tier"]}
            moved.append(entry)
            if evidence_delta and evidence_delta > 0:
                gains.append(entry)
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
            "unexpected_gains_under_a_weaker_floor": len(gains),
            "unexpected_gain_examples": gains[:5],
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
                "p90_evidence_after": _pct(
                    [r["policy_evidence"] for r in strong if r["policy_evidence"] is not None], 0.9),
                "evidence_delta": _spread(strong, "delta_from_floor"),
                "tier_changes": sum(1 for r in strong if r["changes_tier"]),
            },
            "study_hierarchy_inversions": hierarchy_inversions(rows, name, ge.STUDY_TYPE_BASE_POINTS),
        }
        # Answering "did this policy invert the evidence hierarchy?" needs the
        # baseline to compare against. The metric groups PRODUCT Evidence by the
        # anchor's study type, and a product's Evidence is not only its anchor -
        # the pipeline sums its other matches too - so some orderings are already
        # inverted before any policy runs. Only inversions this policy ADDS are
        # attributable to it.
        baseline_inversions = hierarchy_inversions(rows, "baseline", ge.STUDY_TYPE_BASE_POINTS)
        baseline_keys = {(i["archetype"], i["direction"], i["stronger_study_type"],
                          i["weaker_study_type"]) for i in baseline_inversions}
        introduced = [i for i in summaries[name]["study_hierarchy_inversions"]
                      if (i["archetype"], i["direction"], i["stronger_study_type"],
                          i["weaker_study_type"]) not in baseline_keys]
        summaries[name]["study_hierarchy_inversions_present_at_baseline"] = len(baseline_inversions)
        summaries[name]["study_hierarchy_inversions_introduced_by_this_policy"] = introduced

    regression = next((r for r in rows if r["dsld_id"] == ISOLATION_REGRESSION_PRODUCT), None)
    baseline_weak = [r for r in mass if r["direction"] == "positive_weak"]
    return {"_metadata": {
        "question": "What guarantee should primary_evidence_floor provide? Mechanisms are "
                    "compared first; constants are placeholders chosen to reveal each "
                    "mechanism's shape.",
        "simulation_only": "No production constant, config, registry or product was changed. Only "
                           "generic_evidence._primary_mass_floor is intercepted in-process.",
        "contracts": {
            "violations": len(contract_violations),
            "detail": contract_violations[:20],
            "baseline_reproduction": "Baseline is scored with the hook UNINSTALLED, so it is "
                                     "production by construction. Every product is additionally "
                                     "scored through the installed-but-passthrough hook and the "
                                     "two must agree on Evidence, total and tier.",
            "isolation": "Only _primary_mass_floor is intercepted; the DRI nutrition-authority "
                         "floor stays live in every variant. Where it applied at baseline it must "
                         "still apply with the mass floor removed, and the raw result must still "
                         "clear NUTRITION_AUTHORITY_FLOOR.",
            "isolation_regression_product": ISOLATION_REGRESSION_PRODUCT,
            "isolation_regression_detail": (
                {"baseline_evidence": regression["policies"]["baseline"]["evidence"],
                 "evidence_without_mass_floor":
                     regression["policies"]["no_primary_mass_floor"]["evidence"],
                 "raw_without_mass_floor": regression["raw_without_mass_floor"],
                 "authority_floor_without_mass_floor": regression["authority_floor_without_mass_floor"],
                 "note": "The old flag-based A/B read 14.0 -> 8.7 for this product because it "
                         "disabled the authority floor as well."}
                if regression else "not present in this corpus slice"),
            "cap_space": CAP_SPACE,
            "direction_ceiling_owner": "EFFECT_DIRECTION_MULTIPLIERS and PRIMARY_FLOOR_MODERATE, "
                                       "read live from generic_evidence. No second direction table.",
            "direction_ceiling_effective_values": {
                **{"positive_strong": "exempt - may still anchor on PRIMARY_FLOOR_STRONG"},
                **{d: round(ge.PRIMARY_FLOOR_MODERATE * m, 4)
                   for d, m in ge.EFFECT_DIRECTION_MULTIPLIERS.items()
                   if m > 0 and d != "positive_strong"}},
            "study_strength_scale": {
                st: round(points / (ge.STUDY_TYPE_BASE_POINTS.get("systematic_review_meta") or 1), 4)
                for st, points in ge.STUDY_TYPE_BASE_POINTS.items()},
        },
        "populations": {
            "products_scored": corpus_size,
            "eligible_for_primary_mass_floor": eligible,
            "receiving_a_nonzero_primary_mass_floor": len(mass),
            "primary_floor_decisive_with_authority_floor_intact": len(decisive),
            "primary_floor_shadowed_by_authority_floor": len(shadowed_authority),
            "primary_floor_shadowed_by_the_pipeline": len(shadowed_pipeline),
            "changes_final_score": summaries["no_primary_mass_floor"]["products_changed"],
            "changes_tier": summaries["no_primary_mass_floor"]["tier_changes"],
            "separate_dri_nutrition_authority_population": len(authority_population),
            "decisive_anchored_on_a_recovered_match_not_in_the_registry": sum(
                1 for r in decisive if not r.get("floor_anchor_in_reviewed_registry")),
            "decisive_with_no_resolvable_anchor_record": sum(
                1 for r in decisive if not r.get("floor_anchor_record")),
        },
        "baseline_positive_weak_products": len(baseline_weak),
        "baseline_positive_weak_median_evidence": _pct(
            [r["policies"]["baseline"]["evidence"] for r in baseline_weak
             if r["policies"]["baseline"]["evidence"] is not None], 0.5),
        "placeholder_constants": {
            "uplift_caps": UPLIFT_CAPS,
            "applied_in": CAP_SPACE,
            "direction_ceiling": "derived, not tabulated - PRIMARY_FLOOR_MODERATE x "
                                 "EFFECT_DIRECTION_MULTIPLIERS[direction]",
            "study_strength_scale": "STUDY_TYPE_BASE_POINTS[st] / "
                                    "STUDY_TYPE_BASE_POINTS[systematic_review_meta]",
        },
        "policies": summaries,
    }, "products": rows}


def render_comparison(payload: dict) -> str:
    meta = payload["_metadata"]
    pop = meta["populations"]
    contracts = meta["contracts"]

    def spread(block):
        return f"{block['median']} / {block['p90']} / {block['max']}"

    out = [
        "# PRIMARY-MASS FLOOR — POLICY SIMULATION", "",
        "Simulation only. No production constant, config, registry or product changed.", "",
        f"**Contract violations: {contracts['violations']}.** Baseline is scored with the hook "
        "uninstalled, so it is production by construction; each product is then re-scored through "
        "the passthrough hook and the two must agree on Evidence, total and tier.", "",
        "```",
        f"Products scored:                              {pop['products_scored']:>6,}",
        f"Eligible for primary-mass floor:              {pop['eligible_for_primary_mass_floor']:>6,}",
        f"Receiving a nonzero primary-mass floor:       {pop['receiving_a_nonzero_primary_mass_floor']:>6,}",
        f"  decisive (authority floor left intact):     {pop['primary_floor_decisive_with_authority_floor_intact']:>6,}",
        f"  shadowed by the DRI authority floor:        {pop['primary_floor_shadowed_by_authority_floor']:>6,}",
        f"  shadowed by the evidence pipeline:          {pop['primary_floor_shadowed_by_the_pipeline']:>6,}",
        f"Changes final 0-100 score:                    {pop['changes_final_score']:>6,}",
        f"Changes published tier:                       {pop['changes_tier']:>6,}",
        "",
        "Held out of every comparison, authority floor live in all variants:",
        f"DRI/nutrition-authority population:           {pop['separate_dri_nutrition_authority_population']:>6,}",
        "```", "",
        f"Of the decisive products, **{pop['decisive_anchored_on_a_recovered_match_not_in_the_registry']:,}** "
        "anchor their floor on a RECOVERED match carried on the product blob rather than on a "
        "record in the reviewed registry, and "
        f"**{pop['decisive_with_no_resolvable_anchor_record']:,}** have no resolvable anchor record "
        "at all. Counted, not fixed: the freeze holds.", "",
        "The two shadowed rows matter: removing the primary-mass floor produces no shipped change "
        "for those products, and for a real reason. Counting them as affected would overstate the "
        "rule exactly the way the first run did.", "",
        "## Isolation regression case", "",
        "```", json.dumps(contracts["isolation_regression_detail"], indent=1), "```", "",
        "## Where a cap is applied", "", contracts["cap_space"], "",
        "## Direction ceiling — derived, not tabulated", "",
        contracts["direction_ceiling_owner"], "",
        "```", json.dumps(contracts["direction_ceiling_effective_values"], indent=1), "```", "",
        "## Policy comparison", "",
        "| policy | products changed | % of corpus | Evidence delta med/p90/max | "
        "final-score delta med/p90/max | tier changes (down/up) | unexpected gains | "
        "inversions introduced |",
        "|---|---:|---:|---|---|---|---:|---:|",
    ]
    for name, block in meta["policies"].items():
        out.append(
            f"| `{name}` | {block['products_changed']:,} | {block['pct_of_corpus']} | "
            f"{spread(block['evidence_delta'])} | {spread(block['final_score_delta'])} | "
            f"{block['tier_changes']:,} ({block['tier_changes_downward']:,}/{block['tier_changes_upward']:,}) | "
            f"{block['unexpected_gains_under_a_weaker_floor']} | "
            f"{len(block['study_hierarchy_inversions_introduced_by_this_policy'])} |")
    out += ["", "Every mechanism here weakens or leaves the floor unchanged, so **unexpected "
            "gains should be 0**. A nonzero count means a policy raised a product's Evidence, "
            "which would be a defect in the mechanism, not a finding about the floor.", ""]

    for name, block in meta["policies"].items():
        out += [f"### `{name}`", "", block["intent"], "",
                f"- positive_weak changed: **{block['positive_weak']['products_changed']:,}**, "
                f"median Evidence after: **{block['positive_weak']['median_evidence_after']}**, "
                f"p90 **{block['positive_weak']['p90_evidence_after']}**, "
                f"tier changes {block['positive_weak']['tier_changes']:,}",
                f"- positive_strong changed: **{block['positive_strong']['products_changed']:,}**, "
                f"median Evidence after: **{block['positive_strong']['median_evidence_after']}**, "
                f"p90 **{block['positive_strong']['p90_evidence_after']}**, "
                f"tier changes {block['positive_strong']['tier_changes']:,}",
                f"- study-hierarchy inversions: **{len(block['study_hierarchy_inversions'])}** "
                f"observed, {block['study_hierarchy_inversions_present_at_baseline']} already "
                f"present at baseline, "
                f"**{len(block['study_hierarchy_inversions_introduced_by_this_policy'])} "
                f"introduced by this policy**", ""]
        for label, key in (("effect direction", "by_direction"), ("study type", "by_study_type"),
                           ("module", "by_module"), ("archetype", "by_archetype"),
                           ("single active?", "by_active_count")):
            lines = [f"| {label} | products | Evidence delta med/p90/max | "
                     "final-score delta med/p90/max | changes tier |", "|---|---:|---|---|---:|"]
            for key_name, cut in block[key].items():
                lines.append(f"| `{key_name}` | {cut['products']} | {spread(cut['evidence_delta'])} | "
                             f"{spread(cut['final_score_delta'])} | {cut['changes_tier']} |")
            out += lines + [""]
        if block["study_hierarchy_inversions_introduced_by_this_policy"]:
            out += ["Inversions INTRODUCED by this policy (within archetype and direction):", "",
                    "```", json.dumps(
                        block["study_hierarchy_inversions_introduced_by_this_policy"][:10],
                        indent=1), "```", ""]

    out += ["## Placeholder constants", "",
            "```", json.dumps(meta["placeholder_constants"], indent=1), "```", "",
            "Pick the mechanism first. These numbers exist to show what each mechanism does, not "
            "to be adopted.", ""]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
