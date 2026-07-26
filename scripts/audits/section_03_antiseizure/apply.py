#!/usr/bin/env python3
"""Section 3 — antiseizure medication relationships, made mechanism-specific.

Seven DEP_ANTICONVULSANTS_* records were attributed to ``class:anticonvulsants``
(40 members spanning CYP inducers, a CYP inhibitor, and renally-cleared drugs).
Each record's own mechanism prose already named the real actors.  This moves the
attribution onto the prose, splitting by the two mechanisms that actually exist,
and suppresses the one record whose evidence does not support shipping.

Idempotent: re-running makes no further change.  Every rxcui below was verified
live against RxNorm on 2026-07-26.

    python3 scripts/audits/section_03_antiseizure/apply.py [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"
CLASSES_PATH = DATA / "drug_classes.json"
DEPLETIONS_PATH = DATA / "medication_depletions.json"

INDUCERS = "class:enzyme_inducing_antiseizure_medications"
VALPROATE = "class:valproate"

INDUCER_DISPLAY = "Enzyme-inducing antiseizure medications"
VALPROATE_DISPLAY = "Valproate (valproic acid, divalproex / Depakote)"

# RxNorm-verified 2026-07-26. One moiety, four dispensed forms — the salt on the
# label must not decide whether the patient is warned.
VALPROATE_CLASS = {
    "display_name": "Valproate (valproic acid, divalproex / Depakote)",
    "description": (
        "The valproate moiety across its dispensed salts. Pharmacologically the "
        "opposite of the enzyme-inducing antiseizure drugs: valproate INHIBITS "
        "CYP450, so it causes none of the induction-driven depletions (vitamin D, "
        "vitamin K, calcium, folate) and instead depletes L-carnitine (acylcarnitine "
        "conjugation) and biotin (biotinidase inhibition)."
    ),
    "member_rxcuis": ["266856", "9919", "40254", "11118"],
    "member_names": ["divalproex sodium", "sodium valproate", "valproate", "valproic acid"],
    "rxclass_id": "N03AG01",
    "atc_codes": ["N03AG01"],
    "notes": (
        "Valproate moiety across its dispensed salts (Depakote is divalproex). "
        "Deliberately separate from class:enzyme_inducing_antiseizure_medications: "
        "valproate INHIBITS CYP450, so it shares none of the induction-driven "
        "depletions (vitamin D, vitamin K, calcium, folate). It carries its own "
        "chemistry instead — acylcarnitine conjugation (L-carnitine) and "
        "biotinidase inhibition (biotin). All 4 rxcuis content-verified against "
        "RxNorm 2026-07-26."
    ),
}

# (entry_id, new drug_ref id, new display_name)
REATTRIBUTIONS = [
    ("DEP_ANTICONVULSANTS_CALCIUM", INDUCERS, INDUCER_DISPLAY),
    ("DEP_ANTICONVULSANTS_VITAMINK", INDUCERS, INDUCER_DISPLAY),
    ("DEP_ANTICONVULSANTS_FOLATE", INDUCERS, INDUCER_DISPLAY),
    ("DEP_ANTICONVULSANTS_LCARNITINE", VALPROATE, VALPROATE_DISPLAY),
    ("DEP_ANTICONVULSANTS_BIOTIN", VALPROATE, VALPROATE_DISPLAY),
]

# Prose that named drugs now outside the record's scope.  Changing a drug_ref
# without changing the text it contradicts is how stale wording reaches the app.
TEXT_REWRITES = {
    "DEP_ANTICONVULSANTS_FOLATE": {
        "mechanism": (
            "Phenytoin and carbamazepine impair folate absorption and metabolism "
            "through multiple mechanisms: inhibiting intestinal folate conjugase, "
            "competing with folate transport, inhibiting dihydrofolate reductase, "
            "and accelerating hepatic folate catabolism via CYP induction. "
            "Phenobarbital and primidone share the CYP-induction pathway."
        ),
        "recommendation": (
            "Low-dose folic acid (0.4–1 mg/day) is generally recommended for "
            "patients on enzyme-inducing AEDs. Women of childbearing age should "
            "take 4–5 mg/day under medical supervision. Discuss folate "
            "supplementation with your neurologist before starting."
        ),
    },
    "DEP_ANTICONVULSANTS_BIOTIN": {
        "mechanism": (
            "Valproic acid accelerates biotin catabolism via beta-oxidation of the "
            "valproyl side chain and impairs biotinidase activity needed for biotin "
            "recycling; it may also compete with biotin for intestinal transport."
        ),
        "recommendation": (
            "Consider biotin supplementation (5–10 mg/day) for patients on "
            "valproate, especially if experiencing hair thinning or skin changes."
        ),
        "alert_body": (
            "Valproate can gradually reduce biotin levels with long-term use over "
            "months. Some people notice hair thinning or skin changes."
        ),
    },
}

# Its own mechanism hedges ("may reduce", "may also increase"), evidence_level is
# "probable", and the source is an NLM catalog record rather than a study — not
# enough to ship a B12 claim.  Suppressed, not deleted: the signal is plausible
# and returns if a real citation is found.
B12_ID = "DEP_ANTICONVULSANTS_VITAMINB12"
B12_NOTE = (
    "Section 3 (2026-07-26): suppressed pending citation. The mechanism is hedged "
    "(\"may reduce\", \"may also increase\"), evidence_level is only \"probable\", "
    "and the sole source is an NLM catalog entry rather than a study. Attributing "
    "a B12 depletion claim to a whole antiseizure class on that basis over-warns. "
    "Re-enable only with a content-verified PMID and a drug-specific scope."
)

# The inducer-class note recorded a deferral that Section 3 has now resolved.
STALE_NOTE_FRAGMENT = "its biotin/L-carnitine depletion records stay on class:anticonvulsants"
NEW_INDUCER_NOTE = (
    "Curated enzyme-inducer subset of class:anticonvulsants (carbamazepine, "
    "phenytoin, phenobarbital, primidone). Carries every induction-driven "
    "depletion: vitamin D, vitamin K, calcium, folate. Valproate is excluded "
    "because it INHIBITS CYP450 — its biotin and L-carnitine records live on "
    "class:valproate (Section 3, 2026-07-26). Oxcarbazepine remains excluded as a "
    "weaker, dose-dependent inducer pending separate review; carbamazepine-biotin "
    "is likewise deferred (the valproate evidence is far stronger and the two act "
    "by different mechanisms). All 4 rxcuis content-verified against RxNorm."
)


def _load(path: Path):
    return json.loads(path.read_text())


def _save(path: Path, blob) -> None:
    path.write_text(json.dumps(blob, indent=2, ensure_ascii=False) + "\n")


def apply(check_only: bool = False) -> int:
    classes_blob = _load(CLASSES_PATH)
    depl_blob = _load(DEPLETIONS_PATH)
    classes = classes_blob["classes"]
    by_id = {e["id"]: e for e in depl_blob["depletions"]}
    changes: list[str] = []

    # 1. class:valproate ----------------------------------------------------
    if classes.get(VALPROATE) != VALPROATE_CLASS:
        classes[VALPROATE] = VALPROATE_CLASS
        changes.append(f"+ {VALPROATE} ({len(VALPROATE_CLASS['member_rxcuis'])} members)")

    # 2. inducer-class note (records a deferral Section 3 resolved) ----------
    inducer = classes[INDUCERS]
    if STALE_NOTE_FRAGMENT in (inducer.get("notes") or ""):
        inducer["notes"] = NEW_INDUCER_NOTE
        changes.append(f"~ {INDUCERS}.notes refreshed")

    # 3. metadata ------------------------------------------------------------
    total = sum(len(c.get("member_rxcuis") or []) for c in classes.values())
    meta = classes_blob["_metadata"]
    # total_entries and total_classes are both the class count here — the
    # metadata contract reads total_entries, the schema test reads total_classes.
    wanted = {
        "total_classes": len(classes),
        "total_entries": len(classes),
        "total_members": total,
        "last_updated": "2026-07-26",
    }
    if any(meta.get(k) != v for k, v in wanted.items()):
        meta.update(wanted)
        changes.append(f"~ _metadata: {len(classes)} classes / {total} members")

    # 4. re-attributions, one record at a time -------------------------------
    for entry_id, class_id, display in REATTRIBUTIONS:
        ref = by_id[entry_id]["drug_ref"]
        if ref.get("id") != class_id or ref.get("display_name") != display:
            ref["type"] = "class"
            ref["id"] = class_id
            ref["display_name"] = display
            changes.append(f"~ {entry_id} -> {class_id}")

    # 5. prose that the new scope contradicts --------------------------------
    for entry_id, fields in TEXT_REWRITES.items():
        for field, text in fields.items():
            if by_id[entry_id].get(field) != text:
                by_id[entry_id][field] = text
                changes.append(f"~ {entry_id}.{field}")

    # 6. B12 suppression ------------------------------------------------------
    b12 = by_id[B12_ID]
    if b12.get("citation_review_status") != "needs_revision":
        b12["citation_review_status"] = "needs_revision"
        b12["citation_review_note"] = B12_NOTE
        changes.append(f"~ {B12_ID} -> needs_revision (suppressed)")

    if not changes:
        print("Section 3: already applied (no changes).")
        return 0

    print("Section 3 changes:")
    for c in changes:
        print(f"  {c}")
    if check_only:
        print("\n--check: nothing written.")
        return 1

    _save(CLASSES_PATH, classes_blob)
    _save(DEPLETIONS_PATH, depl_blob)
    print(f"\nWrote {CLASSES_PATH.name} and {DEPLETIONS_PATH.name}.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report without writing")
    sys.exit(apply(check_only=ap.parse_args().check))
