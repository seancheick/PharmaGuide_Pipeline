#!/usr/bin/env python3
"""Did convergence quietly undo an owner decision? (read-only)

Four agent sessions edited overlapping areas of this repo. A green test suite
proves the code is self-consistent; it does not prove that a merge kept the
RIGHT version of a decision that two sessions implemented differently. The
failure this guards against is a "clean main" that silently resurrects an older
behaviour or drops a stronger fix - and every check below is one where a stale
snapshot survived somewhere in a branch or stash and could have won a merge.

Each check names the decision, the owner file, and what the wrong answer would
look like. Run it from any worktree; it reads that tree.

    python3 scripts/audits/convergence_semantic_regression.py
    python3 scripts/audits/convergence_semantic_regression.py --json --label post-push

EXIT SEMANTICS - strict, and deliberately unforgiving:

    every decision holds            -> 0
    any decision fails              -> 1
    a check raises                  -> 1 (a check that cannot run is not a pass)
    an owner file, key or id missing-> 1 (same reason)

An inability to inspect something is NEVER converted into a pass. A green run
here is a claim about a tree, so every run stamps the tree it evaluated: HEAD
SHA, whether that tree was dirty, the quality-score config version, the evidence
registry schema version and entry count, and the timestamp. "13/13 PASS" with no
SHA beside it is not evidence of anything.
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "scripts/data"
sys.path.insert(0, str(ROOT / "scripts"))

RESULTS: list[dict] = []


class Unattributable(RuntimeError):
    """The tree could not be identified, so no verdict about it can be trusted."""


def _git(*args: str) -> str:
    """Raises rather than returning a placeholder.

    An earlier version returned "unavailable: ..." on failure, and the caller fed
    that string to `bool()` to decide whether the tree was dirty - so a git
    failure silently became "dirty" and the run still reported a verdict about a
    tree it could not name. An inability to inspect is a failure, not a value.
    """
    try:
        return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception as exc:
        raise Unattributable(f"git {' '.join(args)} failed: {type(exc).__name__}: {exc}") from exc


def evaluated_state() -> dict:
    """What tree produced this verdict. Without it a PASS is unattributable."""
    config = json.loads((ROOT / "scripts/scoring_v4/config/quality_score.json").read_text())
    registry = json.loads((DATA / "backed_clinical_studies.json").read_text())
    dirty = _git("status", "--porcelain")
    return {
        "head_sha": _git("rev-parse", "HEAD"),
        "head_subject": _git("log", "-1", "--format=%s"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "worktree": str(ROOT),
        "tree_dirty": bool(dirty),
        "dirty_paths": [line[3:] for line in dirty.splitlines()] if dirty else [],
        "quality_score_config_version": config["_metadata"]["version"],
        "quality_score_config_schema": config["_metadata"]["schema_version"],
        "evidence_registry_schema_version": registry["_metadata"]["schema_version"],
        "evidence_registry_entries": registry["_metadata"]["total_entries"],
        "evaluated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def check(name: str, decision: str, wrong_answer: str):
    """Register one owner decision. The body returns (ok, detail)."""
    def wrap(fn):
        try:
            ok, detail = fn()
        except Exception as exc:  # a check that cannot run is a failure, not a pass
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        RESULTS.append({"check": name, "decision": decision, "ok": bool(ok),
                        "detail": detail, "regression_would_look_like": wrong_answer})
        return fn
    return wrap


def _registry() -> dict:
    payload = json.loads((DATA / "backed_clinical_studies.json").read_text())
    return {entry["id"]: entry for entry in payload["backed_clinical_studies"]}


def _text(entry: dict, *fields) -> str:
    out = []
    for field in fields:
        value = entry.get(field)
        if isinstance(value, list):
            out.extend(str(v) for v in value)
        elif value:
            out.append(str(value))
    return " ".join(out).lower()


# ── 1. vitamin D: two owners, and the split must survive ──────────────────────

@check("vitamin_d3_bone_claim_removed",
       "INGR_VITAMIN_D3 makes no bone claim; PMID 30293909 pooled 81 RCTs and found none.",
       "'Joint & Bone Health' or a bone endpoint back on the clinical record.")
def _():
    entry = _registry()["INGR_VITAMIN_D3"]
    leaked = [f for f in ("health_goals_supported", "key_endpoints") if "bone" in _text(entry, f)]
    outcomes = entry.get("applicability", {}).get("supported_outcomes") or []
    if any("bone" in str(o).lower() for o in outcomes):
        leaked.append("applicability.supported_outcomes")
    return not leaked, f"bone leaked into: {leaked}" if leaked else "no bone claim on the record"


@check("vitamin_d_bone_goal_still_synergy_owned",
       "The product-facing bone goal is owned by the bone_health synergy cluster, not the registry.",
       "vitamin d3 dropped from the cluster - products would lose a goal the physiology supports.")
def _():
    payload = json.loads((DATA / "synergy_cluster.json").read_text())
    cluster = next(c for c in payload["synergy_clusters"] if c["id"] == "bone_health")
    facts = {
        "vitamin d3 in ingredients": "vitamin d3" in cluster["ingredients"],
        "vitamin d3 is primary": "vitamin d3" in cluster["primary_ingredients"],
        "allow_single_ingredient": cluster.get("allow_single_ingredient") is True,
        "min dose 1000": cluster.get("min_effective_doses", {}).get("vitamin d3") == 1000,
        "nih_ods sourced": any(s.get("source_type") == "nih_ods" for s in cluster.get("sources", [])),
    }
    bad = [k for k, v in facts.items() if not v]
    return not bad, f"missing: {bad}" if bad else "cluster intact"


# ── 2. Wave 2 holds ───────────────────────────────────────────────────────────

@check("amla_still_held_at_reference_tier",
       "INGR_AMLA is curated but held: reference/reference earns no affirmative credit.",
       "study_type promoted to a scoring tier - amla would start moving product scores.")
def _():
    entry = _registry()["INGR_AMLA"]
    held = entry.get("study_type") == "reference" and entry.get("evidence_level") == "reference"
    return held, (f"study_type={entry.get('study_type')} evidence_level={entry.get('evidence_level')} "
                  f"effect_direction={entry.get('effect_direction')}")


@check("white_kidney_bean_unchanged",
       "INGR_WHITE_KIDNEY_BEAN stays approved and untouched pending the floor calibration.",
       "held or re-tiered - it was deliberately NOT held; 13.2 is a scorer question.")
def _():
    entry = _registry()["INGR_WHITE_KIDNEY_BEAN"]
    # The dose guard lives on the APPLICABILITY owner, not as a top-level
    # min_clinical_dose. Reading the wrong field made this check fail on a record
    # that was never touched - a false alarm is as bad as a missed one here.
    applicability = entry.get("applicability") or {}
    ok = (entry.get("effect_direction") == "positive_weak"
          and applicability.get("minimum_daily_dose") == 1000
          and applicability.get("dose_unit") == "mg")
    return ok, (f"effect_direction={entry.get('effect_direction')} "
                f"applicability.minimum_daily_dose={applicability.get('minimum_daily_dose')} "
                f"{applicability.get('dose_unit')}")


@check("null_earns_no_affirmative_credit",
       "null = 0.0 in ONE owner (quality_score.json), read by both the pipeline and the floor.",
       "null back at 0.25, or the floor re-hard-coding its own copy of the table.")
def _():
    config = json.loads((ROOT / "scripts/scoring_v4/config/quality_score.json").read_text())

    # Walk for the key instead of assuming a path. The table lives at
    # evidence_magnitudes/<module>/effect_direction_multipliers, and a hard-coded
    # path that silently finds nothing would report an empty dict as "no
    # violations" - a check that passes because it looked in the wrong place.
    def walk(node, path=""):
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            if key == "effect_direction_multipliers":
                yield f"{path}/{key}", value
            else:
                yield from walk(value, f"{path}/{key}")

    tables = dict(walk(config))
    from scoring_v4.modules import generic_evidence as ge
    module_null = ge.EFFECT_DIRECTION_MULTIPLIERS.get("null")
    one_owner = ge._EFFECT_FLOOR_MULTIPLIER is ge.EFFECT_DIRECTION_MULTIPLIERS
    nulls = {path: table.get("null") for path, table in tables.items()}
    ok = (len(tables) >= 2 and all(v == 0.0 for v in nulls.values())
          and module_null == 0.0 and one_owner)
    return ok, (f"config tables found={len(tables)} nulls={nulls} module={module_null} "
                f"floor_shares_the_table={one_owner}")


# ── 3. records retired on purpose must not come back ──────────────────────────

@check("retired_evidence_records_stay_retired",
       "BRAND_ALBION_MINERALS (5.3.5) and BRAND_PHOSPHATIDYLSERINE (5.3.13) were retired.",
       "either id back in the registry - a stale stash snapshot won a merge.")
def _():
    registry = _registry()
    back = [i for i in ("BRAND_ALBION_MINERALS", "BRAND_PHOSPHATIDYLSERINE") if i in registry]
    return not back, f"resurrected: {back}" if back else "both absent"


# ── 4. FDA safety ─────────────────────────────────────────────────────────────

@check("x10_recall_keeps_the_three_lot_scope",
       "The X10 recall names three lots; a stashed copy has lots=null.",
       "lots back to null - the recall would stop saying WHICH product is recalled.")
def _():
    payload = json.loads((DATA / "banned_recalled_ingredients.json").read_text())
    entry = next((e for e in payload["ingredients"]
                  if e.get("id") == "RECALLED_X10_NATURAL_ENHANCEMENT"), None)
    if entry is None:
        return False, "RECALLED_X10_NATURAL_ENHANCEMENT missing entirely"
    lots = (entry.get("recall_scope") or {}).get("lots")
    return bool(lots) and len(lots) >= 3, f"lots={lots}"


@check("health_fraud_novelty_is_two_questions",
       "Product novelty and adulterant novelty route independently; a known adulterant in an "
       "unknown product is news. extract_substances stops at FDA's closing boilerplate.",
       "bucketing on substance novelty alone - new products with known drugs go to informational.")
def _():
    source = (ROOT / "scripts/api_audit/fda_weekly_sync.py").read_text()
    facts = {
        "health_fraud_product_name exists": "def health_fraud_product_name(" in source,
        "product novelty computed": "product_is_new" in source,
        "boilerplate truncation noted": "boilerplate" in source,
    }
    bad = [k for k, v in facts.items() if not v]
    return not bad, f"missing: {bad}" if bad else "both novelty questions present"


# ── 5. safety behaviours a stash would have inverted ──────────────────────────

@check("blocked_products_still_ship_on_a_shared_upc",
       "A blocked formula is retained beside the scored one; it must not be deduped away.",
       "the stash test that DROPS the blocked row winning - bans would vanish silently.")
def _():
    source = (ROOT / "scripts/tests/test_build_final_db.py").read_text()
    keeps = "def test_shared_upc_retains_scored_and_blocked_formula_candidates" in source
    inverted = [n for n in ("def test_v4_dedup_keeps_scored_over_blocked_same_upc",
                            "def test_banned_inactive_forces_blocked_core_verdict_when_scorer_says_safe",
                            "def test_high_risk_exact_match_sets_caution_blocking_reason_without_banned_flag")
                if n in source]
    return keeps and not inverted, (
        f"current test present={keeps} retired-behaviour tests resurrected={inverted}")


@check("gras_excipient_clamp_and_neutral_unrated_form",
       "A GRAS excipient is a formulation-quality signal, not a clinical safety finding; an "
       "unrated form scores the panel's neutral floor rather than 0.",
       "either helper gone - 7,294 products lose Safety points with no real driver.")
def _():
    source = (ROOT / "scripts/scoring_v4/quality_score.py").read_text()
    facts = {
        "_low_severity_additive_magnitude": "def _low_severity_additive_magnitude(" in source,
        "_unrated_form_neutral_ratio": "def _unrated_form_neutral_ratio(" in source,
        "_omega_formulation_reason": "def _omega_formulation_reason(" in source,
    }
    bad = [k for k, v in facts.items() if not v]
    return not bad, f"missing: {bad}" if bad else "all three present"


# ── 6. findings that must stay findings ───────────────────────────────────────

@check("recovered_collagen_remains_a_finding_not_a_fix",
       "RECOVERED_COLLAGEN_PEPTIDES_V1 can anchor a primary-mass floor while absent from "
       "reviewed_entries(). That is a scoring-owner decision, deliberately NOT normalized away.",
       "silently registered or silently excluded - either would settle an open policy question "
       "inside a merge.")
def _():
    import clinical_applicability as ca
    registered = "RECOVERED_COLLAGEN_PEPTIDES_V1" in ca.reviewed_entries()
    counted = "decisive_anchored_on_a_recovered_match_not_in_the_registry" in (
        ROOT / "scripts/audits/evidence_expansion_2026_09/primary_mass_floor_calibration.py").read_text()
    covered = "RECOVERED_COLLAGEN_PEPTIDES_V1" in (
        ROOT / "scripts/tests/test_primary_mass_floor_diagnostic_contract.py").read_text()
    return (not registered) and counted and covered, (
        f"in_reviewed_entries={registered} counted_by_calibration={counted} "
        f"regression_covered={covered}")


@check("old_floor_diagnostic_stays_marked_invalid",
       "The contaminated kill-switch A/B must remain unusable as calibration evidence.",
       "the banner dropped by a regeneration - dramatic wrong numbers become quotable again.")
def _():
    report = ROOT / "scripts/audits/evidence_expansion_2026_09/PRIMARY_MASS_FLOOR_DIAGNOSTIC.md"
    if not report.exists():
        return False, "report missing"
    body = report.read_text()
    return "INVALID FOR CALIBRATION" in body, "banner present" if "INVALID FOR CALIBRATION" in body \
        else "banner missing"


@check("no_scoring_constants_moved",
       "The floor calibration is a measurement. No constant may change until it is decided.",
       "any of these moving - the freeze was broken mid-investigation.")
def _():
    from scoring_v4.modules import generic_evidence as ge
    expected = {"PRIMARY_FLOOR_STRONG": 14.0, "PRIMARY_FLOOR_MODERATE": 11.0,
                "PRIMARY_FLOOR_BRANDED_STRONG": 18.0, "PRIMARY_FLOOR_BRANDED_MODERATE": 17.0,
                "NUTRITION_AUTHORITY_FLOOR": 10.0}
    drifted = {k: getattr(ge, k, None) for k, v in expected.items() if getattr(ge, k, None) != v}
    return not drifted, f"drifted: {drifted}" if drifted else f"all held: {expected}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--label", default="", help=(
        "Which run this is, e.g. 'pre-push' or 'post-push'. The post-push run "
        "against a fresh fetch of origin/main is the authoritative one."))
    parser.add_argument("--out", type=Path, help="Also write the stamped result here.")
    args = parser.parse_args()

    try:
        state = evaluated_state()
    except Exception as exc:
        # Cannot identify the tree -> cannot make a claim about it.
        print(f"FAIL: could not stamp the evaluated state: {type(exc).__name__}: {exc}")
        return 1

    failed = [r for r in RESULTS if not r["ok"]]
    payload = {"label": args.label, "evaluated_state": state, "checks": len(RESULTS),
               "failed": len(failed), "verdict": "PASS" if not failed else "FAIL",
               "results": RESULTS}
    if args.out:
        args.out.write_text(json.dumps(payload, indent=1))

    if args.json:
        print(json.dumps(payload, indent=1))
    else:
        for result in RESULTS:
            print(f"[{'PASS' if result['ok'] else 'FAIL'}] {result['check']}")
            print(f"       {result['detail']}")
            if not result["ok"]:
                print(f"       decision: {result['decision']}")
                print(f"       regression: {result['regression_would_look_like']}")
        print()
        print(f"  tree      {state['head_sha'][:12]} ({state['branch']}) "
              f"{'DIRTY' if state['tree_dirty'] else 'clean'}")
        print(f"  config    {state['quality_score_config_version']}")
        print(f"  registry  schema {state['evidence_registry_schema_version']}, "
              f"{state['evidence_registry_entries']} entries")
        print(f"  at        {state['evaluated_at']}"
              + (f"   [{args.label}]" if args.label else ""))
        print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} owner decisions hold.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
