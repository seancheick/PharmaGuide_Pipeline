#!/usr/bin/env python3
"""What does the primary-mass floor actually change? (read-only)

The calibration question this exists to answer, raised by the amla canary:

    should a positive_weak systematic-review record be able to take ~66% of the
    public Evidence pillar simply by being the mass-dominant active?

It measures; it changes nothing. No constant here is touched: not the 14.0/11.0
floors, not the 0.85 direction weight, not the archetype references, not the
20-point scale.

"How many products touch this rule?" is the wrong headline, and the first run of
this script printed it. Four populations have to be separated, and the word
"material" is deliberately not used for any of them - it was ambiguous enough to
hide the difference between the last three:

  1. ELIGIBLE / EVALUATED - the production route can invoke this floor, and it
                            produced a value for this product.
  2. DECISIVE             - disabling the floor changes public Evidence.
  3. FINAL-SCORE-CHANGING - disabling it changes the 0-100 score.
  4. TIER-CHANGING        - disabling it changes the published quality tier.

They nest. A product can be decisive without moving the total (a cap or a
rescale absorbs it) and can move the total without crossing a tier boundary.

Two corrections to the first run, both of which inflated it:

  * It called the evidence scorer with the floor forced on for EVERY product.
    Only three of the seven routes pass apply_primary_floor=True - generic,
    sports and fiber_digestive (generic.py:286, sports.py:45,
    fiber_digestive.py:44). multi_or_prenatal, probiotic, omega and b_complex
    never receive this floor, so scoring them with it measured a rule that does
    not run on them.
  * It counted the DRI-essential nutrition-authority floor (10.0) as a
    primary-mass floor. They share one component key but answer different
    questions - "an essential nutrient has evidence of necessity" is not "the
    mass-dominant active carries the formula". They are reported separately.

The counterfactual is taken through the production path, not a reimplementation:
generic_evidence.PRIMARY_FLOOR_ENABLED is the module's own kill switch, read at
call time by score_evidence, so flipping it re-runs score_product_v4 with every
other rule intact. Three invariants make that safe, and all three are asserted
rather than assumed - a global toggle is only honest if it cannot leak:

  * the flag is read at CALL time, not captured at import. Proved once at startup
    on a real floored product by _assert_kill_switch(), not taken on faith.
  * it is always restored, via try/finally, and re-checked before every pair, so
    an exception mid-product cannot silently disable the floor for the rest.
  * nothing runs concurrently. A worker observing another worker's temporary
    global would produce a plausible, wrong A/B, so the run asserts it is
    single-threaded instead of merely being written that way.

    python3 scripts/audits/evidence_expansion_2026_09/primary_mass_floor_diagnostic.py --slim <slim.jsonl>
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

# The routes that pass apply_primary_floor=True. Anything else cannot receive it.
FLOOR_ROUTES = {"generic", "sports", "fiber_digestive"}


def _assert_kill_switch(ge, enriched: dict) -> None:
    """Prove the toggle is read at call time, on a product we know gets a floor.

    If score_evidence had captured PRIMARY_FLOOR_ENABLED at import, flipping it
    here would change nothing and the whole A/B would silently report zero
    impact - the most expensive kind of wrong answer, because it looks like good
    news. So it is proved once against a real product instead of assumed.
    """
    blob = json.loads(json.dumps(enriched))
    assert ge.PRIMARY_FLOOR_ENABLED is True
    with_floor = (ge.score_evidence(blob, apply_primary_floor=True).get("components") or {})
    ge.PRIMARY_FLOOR_ENABLED = False
    try:
        without = (ge.score_evidence(json.loads(json.dumps(enriched)),
                                     apply_primary_floor=True).get("components") or {})
    finally:
        ge.PRIMARY_FLOOR_ENABLED = True
    assert with_floor.get("primary_evidence_floor"), "sample product should carry a floor"
    assert not without.get("primary_evidence_floor"), (
        "PRIMARY_FLOOR_ENABLED is not read at call time; this A/B would measure nothing")
    assert ge.PRIMARY_FLOOR_ENABLED is True


def _evidence_pillar(result: dict) -> dict:
    return ((result.get("quality_pillars_v4") or {}).get("evidence") or {})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slim", type=Path, help="Required unless --resummarize.")
    parser.add_argument("--out", default="primary_mass_floor_diagnostic.json")
    parser.add_argument("--resummarize", type=Path, help=(
        "Rebuild the summary from an existing run's per-product rows instead of "
        "re-scoring the corpus. Same build_payload(), so there is no second "
        "implementation of the vocabulary to drift from this one."))
    parser.add_argument("--report", help="Also render the markdown summary to this filename.")
    args = parser.parse_args()

    if not args.slim and not args.resummarize:
        parser.error("--slim is required unless --resummarize is given")

    if args.resummarize:
        previous = json.loads(args.resummarize.read_text())
        meta = previous["_metadata"]
        headline = meta.get("headline") or {}
        payload = build_payload(
            previous["products"],
            headline.get("products_scored") or meta["products_scored"],
            headline.get("eligible_for_primary_mass_floor")
            or meta["products_on_a_floor_applying_route"])
        (OUT / args.out).write_text(json.dumps(payload, indent=1))
        if args.report:
            (OUT / args.report).write_text(render_report(payload))
            print(f"report: {OUT / args.report}", file=sys.stderr)
        print(json.dumps(payload["_metadata"], indent=1))
        return 0

    assert threading.active_count() == 1, (
        "this A/B flips a module global; a concurrent worker could observe the "
        "temporary value and produce a plausible but wrong counterfactual")

    from score_supplements_v4 import score_product_v4
    from scoring_v4.modules import generic_evidence as ge
    import clinical_applicability as ca

    registry = ca.reviewed_entries()
    canonical_to_entry = {ge._canonical_text(entry.get("standard_name", "")): entry
                          for entry in registry.values()}

    by_brand = collections.defaultdict(dict)
    shipped_evidence = []
    for line in args.slim.open():
        product = json.loads(line)
        shipped_evidence.append(product.get("evidence") or 0.0)
        if product["module"] not in FLOOR_ROUTES:
            continue
        by_brand[product["brand_dir"]][str(product["dsld_id"])] = {
            "module": product["module"],
            "active_scorable_rows": sum(
                1 for row in product.get("rows") or []
                if row.get("role_classification") == "active_scorable"),
        }

    corpus = sorted(shipped_evidence)

    def percentile_of(value: float) -> float:
        below = sum(1 for v in corpus if v < value)
        return round(100 * below / len(corpus), 1) if corpus else 0.0

    rows: list[dict] = []
    proved_call_time = False
    eligible_products = sum(len(v) for v in by_brand.values())
    for brand_dir in sorted(by_brand):
        wanted = by_brand[brand_dir]
        for path in sorted(glob.glob(str(ROOT / f"scripts/products/output_{brand_dir}_enriched/enriched/*.json"))):
            for enriched in json.load(open(path)):
                dsld_id = str(enriched.get("dsld_id"))
                meta = wanted.get(dsld_id)
                if meta is None:
                    continue

                # Cheapest pass first: the evidence module alone tells us whether
                # a floor was even produced, and which of the two floors it is.
                probe = ge.score_evidence(json.loads(json.dumps(enriched)), apply_primary_floor=True)
                floor = (probe.get("components") or {}).get("primary_evidence_floor")
                if not floor:
                    continue
                probe_meta = probe.get("metadata") or {}
                floor_kind = ("nutrition_authority"
                              if probe_meta.get("nutrition_authority_floor_applied")
                              else "primary_mass")
                canonical = probe_meta.get("primary_evidence_floor_canonical")
                entry = canonical_to_entry.get(ge._canonical_text(canonical or ""))

                if not proved_call_time:
                    _assert_kill_switch(ge, enriched)
                    proved_call_time = True

                # Now the public counterfactual, through the production scorer.
                assert ge.PRIMARY_FLOOR_ENABLED is True, (
                    "the floor flag leaked from a previous product; every A/B "
                    "after this point would be measuring the wrong baseline")
                on = score_product_v4(json.loads(json.dumps(enriched)))
                ge.PRIMARY_FLOOR_ENABLED = False
                try:
                    off = score_product_v4(json.loads(json.dumps(enriched)))
                finally:
                    ge.PRIMARY_FLOOR_ENABLED = True

                ev_on, ev_off = _evidence_pillar(on), _evidence_pillar(off)
                evidence_with = ev_on.get("score")
                evidence_without = ev_off.get("score")
                total_with = on.get("quality_score_v4_100")
                total_without = off.get("quality_score_v4_100")
                tier_with, tier_without = on.get("quality_tier"), off.get("quality_tier")

                def delta(a, b):
                    if a is None or b is None:
                        return None
                    return round(float(a) - float(b), 4)

                evidence_delta = delta(evidence_with, evidence_without)
                total_delta = delta(total_with, total_without)
                decisive = bool(evidence_delta and evidence_delta > 0.0)
                components = ev_on.get("components") or {}
                pipeline = (probe.get("components") or {}).get("clinical_evidence_pipeline") or 0.0
                depth = (probe.get("components") or {}).get("depth_bonus") or 0.0

                rows.append({
                    "dsld_id": dsld_id,
                    "brand_dir": brand_dir,
                    "module": meta["module"],
                    "floor_kind": floor_kind,
                    "floor_anchor_canonical": canonical,
                    "direction": (entry or {}).get("effect_direction"),
                    "study_type": (entry or {}).get("study_type"),
                    "evidence_level": (entry or {}).get("evidence_level"),
                    "active_scorable_rows": meta["active_scorable_rows"],
                    "single_active": meta["active_scorable_rows"] == 1,
                    "raw_floor": round(float(floor), 4),
                    "raw_pipeline_without_floor": round(float(pipeline) + float(depth), 4),
                    "archetype": components.get("archetype"),
                    "archetype_reference_max": components.get("reference"),
                    "evidence_with_primary_floor": evidence_with,
                    "evidence_without_primary_floor": evidence_without,
                    "delta_from_floor": evidence_delta,
                    "floor_is_decisive": decisive,
                    "final_total_score_with_floor": total_with,
                    "final_total_score_without_floor": total_without,
                    "final_total_score_delta_from_floor": total_delta,
                    "tier_with_floor": tier_with,
                    "tier_without_floor": tier_without,
                    "tier_delta_from_floor": (None if tier_with == tier_without
                                              else f"{tier_without} -> {tier_with}"),
                    "public_evidence_percentile": percentile_of(float(evidence_with or 0.0)),
                    "share_of_pillar_pct": round(100 * float(evidence_with or 0) / 20, 1),
                })
        print(f"{brand_dir}: {len(rows)} evaluated so far", file=sys.stderr, flush=True)

    payload = build_payload(rows, len(corpus), eligible_products)
    (OUT / args.out).write_text(json.dumps(payload, indent=1))
    print(json.dumps(payload["_metadata"], indent=1))
    return 0


def _pct(values: list[float], q: float) -> float | None:
    """Plain nearest-rank percentile. statistics.quantiles interpolates, which
    invents a delta no product actually has; every number here must be one a
    real product produced."""
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return round(ordered[index], 2)


def _spread(rows: list[dict], key: str) -> dict:
    values = [r[key] for r in rows if r.get(key) is not None]
    if not values:
        return {"median": None, "p90": None, "max": None}
    return {"median": _pct(values, 0.5), "p90": _pct(values, 0.9), "max": round(max(values), 2)}


def _tier_rank() -> dict:
    """Published tier order, from the scoring config - not a list retyped here."""
    from scoring_v4.quality_score import _config
    return {band["name"]: index for index, band in enumerate(_config()["tiers"])}


def _cut(rows: list[dict], key: str) -> dict:
    grouped = collections.defaultdict(list)
    for row in rows:
        grouped[str(row.get(key))].append(row)
    return {name: {
        "products": len(subset),
        "evidence_delta": _spread(subset, "delta_from_floor"),
        "final_score_delta": _spread(subset, "final_total_score_delta_from_floor"),
        "changes_tier": sum(1 for r in subset if r["changes_tier"]),
    } for name, subset in sorted(grouped.items(), key=lambda kv: -len(kv[1]))}


def build_payload(rows: list[dict], corpus_size: int, eligible: int) -> dict:
    """The four states, kept explicit so nobody has to argue later about what a
    word like "material" meant:

        eligible/evaluated   - the production route can invoke this floor
        decisive             - disabling it changes public Evidence
        final-score-changing - disabling it changes the 0-100 score
        tier-changing        - disabling it changes the published tier

    They nest: every tier change is a score change is a decisive floor. Reporting
    only the outer state overstates the blast radius; only the inner one hides it.
    """
    ranks = _tier_rank()
    for row in rows:
        row["floor_evaluated"] = True
        row["changes_final_score"] = bool(row.get("final_total_score_delta_from_floor"))
        row["changes_tier"] = bool(row.get("tier_delta_from_floor"))

    mass = [r for r in rows if r["floor_kind"] == "primary_mass"]
    authority = [r for r in rows if r["floor_kind"] != "primary_mass"]
    decisive = [r for r in mass if r["floor_is_decisive"]]
    score_changing = [r for r in decisive if r["changes_final_score"]]
    tier_changing = [r for r in decisive if r["changes_tier"]]

    up = down = 0
    crossings = collections.Counter()
    for row in tier_changing:
        before, after = row["tier_without_floor"], row["tier_with_floor"]
        crossings[f"{before} -> {after}"] += 1
        if ranks.get(after, 99) < ranks.get(before, 99):
            up += 1
        else:
            down += 1

    weak = [r for r in decisive if r["direction"] == "positive_weak"]
    weak_at_or_above_13 = [r for r in weak if (r["evidence_with_primary_floor"] or 0) >= 13.0]

    return {"_metadata": {
        "question": "Of the products the primary-mass floor touches, how many are actually "
                    "elevated by it, and how far? Not how many touch the rule.",
        "measured_only": "No constant was changed: not the 14.0/11.0 floors, not the direction "
                         "weights, not the archetype references, not the 20-point scale. The "
                         "counterfactual flips generic_evidence.PRIMARY_FLOOR_ENABLED and re-runs "
                         "score_product_v4, so every other rule stays live.",
        "corrections_to_the_first_run": [
            "Only generic / sports / fiber_digestive pass apply_primary_floor=True. The first run "
            "scored all seven routes with the floor forced on, counting products that can never "
            "receive it in production.",
            "The DRI-essential nutrition-authority floor (10.0) shares the component key but is a "
            "different rule; it is reported separately instead of inside the total.",
            "'Material' is not used. Four explicit states are reported instead.",
        ],
        "INVALID_FOR_CALIBRATION": True,
        "SUPERSEDED_COUNTERFACTUAL": {
            "still_valid": "The population counts - products scored, eligible, receiving a "
                           "nonzero primary-mass floor, and the separated DRI nutrition-authority "
                           "population. None of those depend on the counterfactual.",
            "superseded": "Every DECISIVE count and every delta below. They were measured by "
                          "flipping PRIMARY_FLOOR_ENABLED, which gates BOTH floors: the "
                          "primary-mass floor and the DRI-essential nutrition-authority floor "
                          "share one `if` block (generic_evidence.py:317). A DRI-essential "
                          "product whose mass floor was above 10.0 therefore appeared to fall all "
                          "the way to its pipeline score, when the authority floor would have "
                          "caught it at 10.0 raw. That credits the mass floor with points another "
                          "rule would have supplied.",
            "worked_example": "Product 261812 (Airborne): reported here as Evidence 14.0 -> 8.7 "
                              "without the floor, delta 5.3. With the authority floor left live "
                              "the correct counterfactual is 14.0 -> 11.8, delta 2.2.",
            "replaced_by": "primary_mass_floor_calibration.json - its `no_primary_mass_floor` "
                           "policy intercepts only _primary_mass_floor, leaving the authority "
                           "floor live in every variant.",
            "also_fixed_there": "The 40 decisive products with no direction or study type are an "
                                "audit-side lookup defect, not a production normalization defect: "
                                "they are BCAA (16) and collagen (24), where the floor reports "
                                "the matched ACTIVE's canonical id (`bcaa`) while the record is "
                                "named 'Branched Chain Amino Acids'. The calibration run resolves "
                                "the anchor with _canonical_from_entry over the product's own "
                                "resolved matches instead of matching standard_name.",
        },
        "headline": {
            "products_scored": corpus_size,
            "eligible_for_primary_mass_floor": eligible,
            "receiving_a_nonzero_primary_mass_floor": len(mass),
            "decisive_for_public_evidence": len(decisive),
            "changes_final_0_100_score": len(score_changing),
            "changes_published_tier": len(tier_changing),
            "separate_dri_nutrition_authority_floor_population": len(authority),
        },
        "decisive_share_of_corpus_pct": round(100 * len(decisive) / corpus_size, 2) if corpus_size else 0,
        "tier_changing_share_of_corpus_pct": round(100 * len(tier_changing) / corpus_size, 2) if corpus_size else 0,
        "decisive_evidence_delta": _spread(decisive, "delta_from_floor"),
        "decisive_final_score_delta": _spread(decisive, "final_total_score_delta_from_floor"),
        "tier_crossings_upward": up,
        "tier_crossings_downward": down,
        "tier_crossings": dict(crossings.most_common()),
        "by_direction": _cut(decisive, "direction"),
        "by_study_type": _cut(decisive, "study_type"),
        "by_module": _cut(decisive, "module"),
        "by_archetype": _cut(decisive, "archetype"),
        "by_active_count": _cut(decisive, "single_active"),
        "by_raw_floor_value": _cut(decisive, "raw_floor"),
        "by_archetype_reference_max": _cut(decisive, "archetype_reference_max"),
        "positive_weak_decisive": {
            "products": len(weak),
            "share_of_decisive_pct": round(100 * len(weak) / len(decisive), 1) if decisive else 0,
            "median_public_evidence_after_rescale": _pct(
                [r["evidence_with_primary_floor"] for r in weak if r["evidence_with_primary_floor"] is not None], 0.5),
            "p90_public_evidence_after_rescale": _pct(
                [r["evidence_with_primary_floor"] for r in weak if r["evidence_with_primary_floor"] is not None], 0.9),
            "products_at_or_above_13_of_20": len(weak_at_or_above_13),
            "evidence_delta": _spread(weak, "delta_from_floor"),
            "final_score_delta": _spread(weak, "final_total_score_delta_from_floor"),
            "changes_tier": sum(1 for r in weak if r["changes_tier"]),
            "by_study_type": _cut(weak, "study_type"),
            "by_raw_floor_value": _cut(weak, "raw_floor"),
            "by_archetype": _cut(weak, "archetype"),
        },
        "floor_anchor_unresolved_in_registry": sum(1 for r in decisive if r["direction"] is None),
    }, "products": rows}


def render_report(payload: dict) -> str:
    """Render the markdown from the measured artifact.

    Every number below is read out of the payload. None is retyped: counts and
    medians in this project have drifted before because a human copied them into
    prose and the prose outlived the run.
    """
    meta = payload["_metadata"]
    head = meta["headline"]

    def spread(block: dict) -> str:
        return f"{block['median']} / {block['p90']} / {block['max']}"

    def table(cut: dict, label: str) -> list[str]:
        lines = [f"| {label} | products | Evidence delta med / p90 / max | "
                 "final-score delta med / p90 / max | changes tier |",
                 "|---|---:|---|---|---:|"]
        for name, block in cut.items():
            lines.append(f"| `{name}` | {block['products']} | {spread(block['evidence_delta'])} | "
                         f"{spread(block['final_score_delta'])} | {block['changes_tier']} |")
        return lines + [""]

    weak = meta["positive_weak_decisive"]
    out = [
        "# PRIMARY-MASS FLOOR — PRODUCTION ROUTES ONLY", "",
        "Measured, not changed. No scoring constant moved: not the 14.0/11.0 floors, not the "
        "0.85 direction weight, not the archetype references, not the 20-point scale.", "",
        "> # ⛔ INVALID FOR CALIBRATION", ">",
        "> **Do not quote any decisive count, Evidence delta, final-score delta or tier-change "
        "number from this report.** The counterfactual disabled BOTH the primary-mass floor and "
        "the DRI/nutrition-authority floor, so every delta credits the primary-mass rule with "
        "points the authority floor would have supplied.", ">",
        "> " + meta["SUPERSEDED_COUNTERFACTUAL"]["worked_example"], ">",
        "> Population and eligibility counts remain valid - they do not depend on the "
        "counterfactual. Everything downstream of them does not.", ">",
        "> **Use instead:** `" + meta["SUPERSEDED_COUNTERFACTUAL"]["replaced_by"].split(" - ")[0]
        + "` and its report `PRIMARY_MASS_FLOOR_CALIBRATION.md`.", "",
        "Four states, reported separately because the word *material* was ambiguous enough to "
        "hide the difference between the last three. They nest.", "",
        "```",
        f"Products scored:                         {head['products_scored']:>6,}",
        f"Eligible for primary-mass floor:         {head['eligible_for_primary_mass_floor']:>6,}",
        f"Actually receiving nonzero floor:        {head['receiving_a_nonzero_primary_mass_floor']:>6,}",
        f"Decisive for public Evidence:            {head['decisive_for_public_evidence']:>6,}",
        f"Changes final 0-100 score:               {head['changes_final_0_100_score']:>6,}",
        f"Changes published tier:                  {head['changes_published_tier']:>6,}",
        "",
        "Separate rule, same component key:",
        f"DRI/nutrition-authority floor:           {head['separate_dri_nutrition_authority_floor_population']:>6,}",
        "```", "",
        f"The decisive population is **{meta['decisive_share_of_corpus_pct']}%** of the scored "
        f"catalog; the tier-changing population is **{meta['tier_changing_share_of_corpus_pct']}%**.", "",
        f"- Evidence delta (median / p90 / max): **{spread(meta['decisive_evidence_delta'])}** of 20",
        f"- Final-score delta (median / p90 / max): **{spread(meta['decisive_final_score_delta'])}** of 100",
        f"- Tier crossings: **{meta['tier_crossings_upward']} upward, "
        f"{meta['tier_crossings_downward']} downward**", "",
        "| tier crossing | products |", "|---|---:|",
    ]
    out += [f"| {name} | {count} |" for name, count in meta["tier_crossings"].items()]
    out += ["", "## The decisive population", ""]
    out += table(meta["by_direction"], "effect direction")
    out += table(meta["by_study_type"], "study type")
    out += table(meta["by_module"], "module")
    out += table(meta["by_archetype"], "archetype")
    out += table(meta["by_active_count"], "single active?")
    out += table(meta["by_raw_floor_value"], "raw floor")
    out += table(meta["by_archetype_reference_max"], "archetype reference max")
    out += [
        "## `positive_weak` + primary-mass-floor decisive", "",
        "The population amla and white kidney bean exposed. The question was whether "
        "`13.2/20` is a rare edge or a systematic characteristic.", "",
        f"- products: **{weak['products']}** ({weak['share_of_decisive_pct']}% of all decisive)",
        f"- public Evidence after rescale — median **{weak['median_public_evidence_after_rescale']}**, "
        f"p90 **{weak['p90_public_evidence_after_rescale']}**",
        f"- at or above 13.0/20: **{weak['products_at_or_above_13_of_20']}**",
        f"- Evidence delta (median / p90 / max): {spread(weak['evidence_delta'])}",
        f"- final-score delta (median / p90 / max): {spread(weak['final_score_delta'])}",
        f"- changes published tier: **{weak['changes_tier']}**", "",
    ]
    out += table(weak["by_study_type"], "study type")
    out += table(weak["by_raw_floor_value"], "raw floor")
    out += table(weak["by_archetype"], "archetype")
    out += [
        "## Data-quality note", "",
        f"{meta['floor_anchor_unresolved_in_registry']} decisive products have a floor anchor whose "
        "canonical name does not resolve to a registry record, so their direction and study type "
        "are unknown here. They are counted, not guessed at.", "",
        "## Architecture debt logged, not fixed here", "",
        "`primary_evidence_floor` is one component key for two semantically different mechanisms: "
        "the primary-mass floor and the DRI-essential nutrition-authority floor. That shared key is "
        "what let the first run of this diagnostic conflate them. The arithmetic can stay identical; "
        "the keys should eventually differ so a reader cannot mistake one rule for the other.", "",
    ]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
