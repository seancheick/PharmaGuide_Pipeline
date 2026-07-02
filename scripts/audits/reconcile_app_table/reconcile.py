#!/usr/bin/env python3
"""Dual-source reconciliation audit (Phase 4 foundation).

Compares the Flutter app's hand-authored condition-threshold table
(`lib/services/warnings/condition_thresholds.dart`) against the pipeline's
`ingredient_interaction_rules.json`, entry by entry, so the const table can be
migrated into the pipeline (single source of truth) and then retired.

The two encodings map like this:
    app `ConditionThreshold.positive()`        <-> pipeline direction=beneficial, materiality=presence
    app `ConditionThreshold.aboveDose(minDose)`<-> pipeline direction=harmful,   materiality=dose_dependent,
                                                    min_effective_dose.value ~= minDose

Read-only. Emits a categorized report:
    MATCH        pipeline already agrees with the app entry
    DISAGREE     pipeline has the pair but direction/materiality/floor conflict
    TO_MIGRATE   app has a clinical decision the pipeline does not encode yet
    PIPELINE_ONLY(informational) pipeline floors a pair the app never gated

Usage:  python3 scripts/audits/reconcile_app_table/reconcile.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
RULES = REPO / "scripts" / "data" / "ingredient_interaction_rules.json"
# App repo lives next to the pipeline repo (path has a space).
APP_TABLE = Path(
    "/Users/seancheick/PharmaGuide ai/lib/services/warnings/condition_thresholds.dart"
)


# --------------------------------------------------------------------------
# Parse the Dart const table.
# --------------------------------------------------------------------------

def parse_app_table(text: str) -> dict[tuple[str, str], dict]:
    """Return {(condition, ingredient): {kind, min_dose, unit}}."""
    # Isolate the `conditionThresholds = { ... };` literal.
    start = text.index("const Map<String, Map<String, ConditionThreshold>> conditionThresholds")
    body = text[start : text.index("\n};", start)]

    out: dict[tuple[str, str], dict] = {}
    # Condition blocks:  'ttc': { ... },  — split on top-level `'key': {`.
    cond_iter = list(re.finditer(r"'([a-z_]+)':\s*\{", body))
    for i, m in enumerate(cond_iter):
        cond = m.group(1)
        seg_start = m.end()
        seg_end = cond_iter[i + 1].start() if i + 1 < len(cond_iter) else len(body)
        seg = body[seg_start:seg_end]
        for em in re.finditer(
            r"'([a-z0-9_]+)':\s*ConditionThreshold\.(positive|aboveDose)\s*\(",
            seg,
        ):
            ingredient, kind = em.group(1), em.group(2)
            entry = {"kind": kind, "min_dose": None, "unit": None}
            if kind == "aboveDose":
                tail = seg[em.end() : em.end() + 200]
                md = re.search(r"minDose:\s*([\d.]+)", tail)
                du = re.search(r"doseUnit:\s*'([^']+)'", tail)
                if md:
                    entry["min_dose"] = float(md.group(1))
                if du:
                    entry["unit"] = du.group(1)
            out[(cond, ingredient)] = entry
    return out


# --------------------------------------------------------------------------
# Canonical base-ingredient normalization — so pipeline `vitamin_b3_niacin`
# reconciles with app `niacin`, and form variants (magnesium_glycinate,
# cinnamon_bark_extract) collapse to their base rule. Without this the audit
# emits FALSE NEGATIVES (real disagreements filed as benign "no rule").
# --------------------------------------------------------------------------

_ALIASES = {
    "vitamin_b3_niacin": "niacin", "vitamin_b_3_niacin": "niacin",
    "vitamin_b3": "niacin", "vitamin_b_3": "niacin",
    "vitamin_d3": "vitamin_d",
    "myo_inositol": "inositol", "d_chiro_inositol": "inositol",
}
_FORM_SUFFIXES = (
    "_bark_extract_dried", "_bark_extract", "_bark", "_extract", "_dried",
    "_glycinate", "_citrate",
)


def base(name: str) -> str:
    n = (name or "").strip().lower()
    n = _ALIASES.get(n, n)
    for suf in _FORM_SUFFIXES:
        if n.endswith(suf) and len(n) > len(suf):
            n = n[: -len(suf)]
            break
    return _ALIASES.get(n, n)


# --------------------------------------------------------------------------
# Index the pipeline by (condition, base-canonical_id).
# --------------------------------------------------------------------------

def index_pipeline(rules: list[dict]) -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for r in rules:
        canon = (r.get("subject_ref") or {}).get("canonical_id")
        if not canon:
            continue
        for cr in r.get("condition_rules") or []:
            cond = str(cr.get("condition_id") or "").lower()
            med = cr.get("min_effective_dose") or {}
            out[(cond, base(canon))] = {
                "direction": cr.get("direction"),
                "materiality": cr.get("materiality"),
                "floor": med.get("value"),
                "unit": med.get("unit"),
                "severity": cr.get("severity"),
            }
    return out


def classify(app: dict, pipe: dict | None) -> tuple[str, str]:
    if pipe is None:
        return "TO_MIGRATE", "pipeline has no rule for this (condition, ingredient)"
    d, m = pipe.get("direction"), pipe.get("materiality")
    if app["kind"] == "positive":
        if d == "beneficial":
            return "MATCH", "both beneficial"
        if d is None:
            return "TO_MIGRATE", "pipeline rule exists but unclassified; app says beneficial"
        return "DISAGREE", f"app=beneficial  pipeline direction={d} materiality={m} floor={pipe.get('floor')}"
    # aboveDose
    if d == "harmful" and m == "dose_dependent":
        pf, au = pipe.get("floor"), app["min_dose"]
        if pf is not None and au is not None and abs(float(pf) - float(au)) > 1e-6:
            return "DISAGREE", f"floor mismatch: app={au}{app['unit']}  pipeline={pf}{pipe.get('unit')}"
        if pf is None:
            return "TO_MIGRATE", f"pipeline harmful/dose_dependent but no floor; app floor={app['min_dose']}{app['unit']}"
        return "MATCH", f"both dose_dependent @ ~{pf}"
    if d is None:
        return "TO_MIGRATE", f"pipeline unclassified; app says aboveDose {app['min_dose']}{app['unit']}"
    return "DISAGREE", f"app=harmful/dose_dependent({app['min_dose']}{app['unit']})  pipeline direction={d} materiality={m}"


def main() -> int:
    if not APP_TABLE.exists():
        print(f"App table not found: {APP_TABLE}", file=sys.stderr)
        return 2
    app = parse_app_table(APP_TABLE.read_text(encoding="utf-8"))
    pipe = index_pipeline(json.loads(RULES.read_text(encoding="utf-8"))["interaction_rules"])

    buckets: dict[str, list[str]] = {"MATCH": [], "DISAGREE": [], "TO_MIGRATE": []}
    seen: set[tuple[str, str]] = set()
    for cond, ing in sorted(app):
        bkey = (cond, base(ing))
        if bkey in seen:  # dedupe form variants that collapse to the same base
            continue
        seen.add(bkey)
        cat, why = classify(app[(cond, ing)], pipe.get(bkey))
        buckets[cat].append(f"  {cond:<20} {bkey[1]:<20} {why}")

    print(f"App base-ingredient pairs: {len(seen)}  |  pipeline condition-rule pairs: {len(pipe)}\n")
    for cat in ("DISAGREE", "TO_MIGRATE", "MATCH"):
        print(f"=== {cat} ({len(buckets[cat])}) ===")
        if cat == "TO_MIGRATE":
            print("  (app has a suppression decision the pipeline does NOT encode -> the")
            print("   pipeline currently FIRES. Migrate to preserve, or the app's clinical")
            print("   suppression is lost once the const table is retired.)")
        print("\n".join(sorted(buckets[cat])) or "  (none)")
        print()
    # Self-check: guard against a silent regex breakage that would make the
    # report falsely empty (and thus falsely "reconciled").
    assert len(app) > 40, f"app-table parse looks broken (only {len(app)} entries)"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
