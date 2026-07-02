#!/usr/bin/env python3
"""Phase 2 (smart-flagging rework) — author `direction` + `materiality` on every
sub-rule of ingredient_interaction_rules.json that still lacks them.

Two axes (see plan `it-does-hold-up-jazzy-hamming.md`):

  materiality  presence | dose_dependent | unknown
      ALL rules handled here get `presence`. Verified: none of the untagged
      sub-rules carry a dose_threshold / min_effective_dose (the dose_dependent
      set was authored in Phase 3). presence == never dose-suppressed ==
      fail-safe: a presence rule fires at any dose and is never hidden.

  direction    harmful | beneficial | neutral | unknown   (human-authored)
      - drug-class interactions            -> harmful (drug<->supplement risk)
      - condition rules                    -> harmful, minus the explicit
                                              beneficial/neutral OVERRIDE set
      - pregnancy / lactation              -> content-classified per row:
            "Continue X under prenatal care"/"recommended preconception"
                                            -> beneficial
            "generally compatible/acceptable" standard nutrient
                                            -> neutral
            a harm signal or avoid/contra/caution/monitor severity
                                            -> harmful
            bare "Limited safety data", no harm mechanism
                                            -> unknown  (asserting harm would
                                               overstate an unestablished risk)
      - ttc                                -> explicit OVERRIDE (7 rows)

Every non-harmful decision is enumerated in OVERRIDE (or matched by an explicit
content rule) from a full per-row read of the data, so the classification is
auditable rather than a blind sweep. Idempotent: rows already carrying a
`direction` are skipped, so re-running never double-writes or disturbs the
Phase-3 floored/beneficial set.

Usage:
    python3 scripts/tools/migrate_phase2_direction_materiality.py            # dry-run
    python3 scripts/tools/migrate_phase2_direction_materiality.py --apply    # write
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "ingredient_interaction_rules.json"

NEW_VERSION = "6.2.0"
NEW_DATE = "2026-07-02"

PREG_KEYS = {"pregnancy_lactation", "pregnancy", "lactation"}

# (canonical_id, sub_rule_key) -> direction. Every beneficial/neutral condition
# row + all 7 ttc rows, read one-by-one from the clinical text.
OVERRIDE = {
    # liver_disease — hepatoprotective, used IN liver disease
    ("milk_thistle", "liver_disease"): "beneficial",
    # heart_disease
    ("coq10", "heart_disease"): "beneficial",          # HF adjunct, up-EF (Q-SYMBIO)
    ("magnesium", "heart_disease"): "neutral",         # protective + renal caveat
    ("omega_3", "heart_disease"): "neutral",           # cardioprotective + high-dose AF
    ("hawthorn", "heart_disease"): "neutral",          # HF adjunct + glycoside interaction
    ("vitamin_d", "heart_disease"): "neutral",         # moderate good / high-dose monitor
    ("vitamin_b7_biotin", "heart_disease"): "neutral", # troponin assay interference
    # thyroid_disorder
    ("vitamin_b7_biotin", "thyroid_disorder"): "neutral",  # TSH/T4 assay interference
    ("selenium", "thyroid_disorder"): "neutral",       # therapeutic + selenosis at excess
    ("bacopa", "thyroid_disorder"): "neutral",         # animal-only, clinical effect uncertain
    # high_cholesterol — lipid-lowering benefit for the condition
    ("berberine_supplement", "high_cholesterol"): "beneficial",
    ("citrus_bergamot", "high_cholesterol"): "beneficial",
    ("garlic", "high_cholesterol"): "beneficial",
    ("coq10", "high_cholesterol"): "neutral",          # statin-depletion context, no harm
    ("vitamin_b3_niacin", "high_cholesterol"): "neutral",  # lipid effect / no CV benefit
    # hypertension (condition) — BP-lowering, limited evidence = mixed
    ("rhodiola", "hypertension"): "neutral",
    ("tribulus", "hypertension"): "neutral",
    # seizure_disorder — mixed / limited (anticonvulsant signals or debunked concern)
    ("BANNED_CBD_US", "seizure_disorder"): "neutral",
    ("borage_seed_oil", "seizure_disorder"): "neutral",
    ("evening_primrose_oil", "seizure_disorder"): "neutral",
    ("melatonin", "seizure_disorder"): "neutral",
    # statins — CoQ10 has NO adverse PK interaction (mitigates myopathy)
    ("coq10", "statins"): "neutral",
    # lactation — galactagogue, "affects milk supply" is the intended/known effect
    ("fenugreek", "lactation"): "neutral",
    # benign standard nutrients whose `pregnancy` row is a "use labs/guidance"
    # monitor (not an excess-harm) — pinned neutral to match their generally-
    # compatible `pregnancy_lactation` sibling. vitamin_a/vitamin_c/vitamin_e/
    # iodine stay harmful: those carry a real dose-sensitive excess harm.
    ("vitamin_d", "pregnancy"): "neutral",
    ("nac", "pregnancy"): "neutral",
    # ttc (trying to conceive) — all 7 untagged rows, read per-entry
    ("coq10", "ttc"): "beneficial",                    # oocyte quality
    ("vitamin_b12_cobalamin", "ttc"): "beneficial",    # recommended preconception
    ("vitamin_b9_folate", "ttc"): "beneficial",        # folic acid, down-NTD 69%
    ("vitamin_d", "ttc"): "beneficial",                # repletion supports fertility
    ("saw_palmetto", "ttc"): "harmful",                # antiandrogenic, impairs conception
    ("wild_yam", "ttc"): "harmful",                    # phytoestrogen disrupts ovulation
    ("chasteberry", "ttc"): "unknown",                 # hormone-active, genuinely mixed
}

# pregnancy/lactation harm signals — any match => harmful (checked AFTER the
# beneficial + neutral content rules, so standard nutrients are not swept in).
_HARM = re.compile(
    r"bleed|platelet|uterotonic|abortifacient|emmenagogue|teratogen|hepatotox|"
    r"toxic|contraindicat|not recommended|do not use|discontinue|avoid|unsafe|"
    r"stimulant|sympathomimetic|sympathetic|hormone-active|hormonally active|"
    r"hormone claims|hormone-active claims|neonatal|preterm|cortisol|glycyrrhizin|"
    r"phytoestrogen|estrogen|androgen|serotonin|milk supply|counteract|prolactin|"
    r"cytotoxic|endocrine|developmental|caffeine|thujone|pulegone|pyrrolizidine|"
    r"nephrotox|arrhythmi|bilirubin|kernicterus|goitrogen|wolff-chaikoff|"
    r"within (the )?\w*\s*range|dose-sensitive|excess|insulin-mimetic|abort",
    re.I,
)
_HARM_SEV = {"avoid", "contraindicated", "caution", "monitor"}


def classify_direction(canon: str, key: str, sr: dict) -> tuple[str, str]:
    """Return (direction, reason). Caller sets materiality=presence."""
    ov = OVERRIDE.get((canon, key))
    if ov:
        return ov, "override"

    if key == "ttc":
        raise ValueError(f"unhandled ttc row not in OVERRIDE: {canon}")

    if key in PREG_KEYS:
        head = (sr.get("alert_headline") or "").strip()
        note = (sr.get("informational_note") or "").strip()
        mech = (sr.get("mechanism") or "").strip()
        sev = (sr.get("severity") or "").strip().lower()
        low = f"{head} || {note} || {mech}".lower()
        if head.lower().startswith("continue") or \
           "standard prenatal support" in low or "recommended preconception" in low:
            return "beneficial", "preg:continue-under-care"
        if "generally compatible" in low or "generally acceptable" in low:
            return "neutral", "preg:standard-nutrient"
        if sev in _HARM_SEV or _HARM.search(low):
            return "harmful", f"preg:harm(sev={sev or '-'})"
        return "unknown", "preg:limited-data"

    # drug-class interactions + non-override condition rows
    return "harmful", "default-harmful"


def _iter_subrules(rule: dict):
    for x in (rule.get("condition_rules") or []):
        yield x.get("condition_id"), x
    for x in (rule.get("drug_class_rules") or []):
        yield x.get("drug_class_id"), x
    pl = rule.get("pregnancy_lactation")
    if isinstance(pl, dict):
        yield "pregnancy_lactation", pl


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the file (default: dry-run)")
    args = ap.parse_args()

    orig = RULES_PATH.read_text()
    doc = json.loads(orig)
    rules = doc["interaction_rules"]

    dir_counts, tagged, skipped = Counter(), 0, 0
    for r in rules:
        canon = (r.get("subject_ref") or {}).get("canonical_id", "")
        for key, sr in _iter_subrules(r):
            if sr.get("direction"):          # already tagged (Phase 3 or prior run)
                skipped += 1
                continue
            if sr.get("dose_thresholds") or sr.get("min_effective_dose"):
                # Guard: a floor implies dose_dependent — must be Phase-3 authored,
                # never bulk-stamped presence here.
                raise SystemExit(f"REFUSING: {canon}/{key} has a floor but no direction")
            direction, _reason = classify_direction(canon, key, sr)
            sr["direction"] = direction
            sr["materiality"] = "presence"
            dir_counts[direction] += 1
            tagged += 1

    print(f"tagged {tagged} sub-rules (skipped {skipped} already-tagged)")
    for d, c in dir_counts.most_common():
        print(f"  {c:4d}  {d}")

    if not args.apply:
        print("\n(dry-run — pass --apply to write)")
        return 0

    md = doc["_metadata"]
    md["schema_version"] = NEW_VERSION
    md["last_updated"] = NEW_DATE
    md.setdefault("migration", {}).setdefault("completed_migrations", []).append({
        "from": "6.1.3",
        "to": NEW_VERSION,
        "date": NEW_DATE,
        "summary": (
            "Smart-flagging Phase 2: authored direction + materiality on the "
            f"{tagged} sub-rules that still lacked them (condition_rules, "
            "drug_class_rules, pregnancy_lactation blocks). materiality=presence "
            "for all (none carry a dose_threshold; presence == never dose-"
            "suppressed). direction: drug-class + non-nutrient condition rows "
            "harmful; beneficial for condition-supportive nutrients "
            "(milk_thistle/liver, coq10/heart, berberine|garlic|bergamot/"
            "cholesterol, folate|B12|fish_oil|inositol|coq10|vitamin_d preconception/"
            "pregnancy); neutral for standard pregnancy nutrients + diagnostic-"
            "interference (biotin assays) + mixed-evidence rows; unknown for "
            "bare 'limited safety data' pregnancy rows (fail-open, always fires). "
            "Advisory-only: score-neutral and, until the app router lands "
            "(Phase 4), behavior-neutral. Applied via "
            "scripts/tools/migrate_phase2_direction_materiality.py."
        ),
    })

    RULES_PATH.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n")
    # re-parse to prove validity
    json.loads(RULES_PATH.read_text())
    print(f"\nwrote {RULES_PATH} (schema_version -> {NEW_VERSION})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
