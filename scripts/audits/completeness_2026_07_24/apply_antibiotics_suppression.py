#!/usr/bin/env python3
"""Suppress the two dead antibiotics_broadspectrum depletion rules (Codex/PM).

`drug_ref.id = "antibiotics_broadspectrum"` is a synthetic non-rxcui id; the app
matches medications by numeric RxCUI, so these two rules can NEVER fire. Rather
than leave them silently displayed (unverified) or invent a rushed matcher, mark
them `needs_revision` — the app suppresses that status from display — until
Section 8 converts them to a real class:broad_spectrum_antibiotics with member
rxcuis. This removes the need for the gate's KNOWN_UNRESOLVED pass-exception:
the identifier gate skips suppressed entries and enforces only displayed ones.
Idempotent.
"""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[2] / "data" / "medication_depletions.json"
TARGETS = {"DEP_ANTIBIOTICS_BVITAMINS", "DEP_ANTIBIOTICS_VITAMINK"}
NOTE = (
    "drug_ref.id 'antibiotics_broadspectrum' is a synthetic non-RxCUI identifier; "
    "the app matches medications by numeric RxCUI, so this rule can never fire. "
    "Suppressed (needs_revision) pending Section 8 conversion to "
    "class:broad_spectrum_antibiotics with real member rxcuis. The mechanism/"
    "citation are sound — the defect is the drug identifier, not the evidence."
)


def main() -> int:
    doc = json.loads(PATH.read_text())
    changed = 0
    for e in doc["depletions"]:
        if e["id"] not in TARGETS:
            continue
        if e.get("citation_review_status") == "needs_revision":
            print(f"  skip (already suppressed): {e['id']}")
            continue
        e["citation_review_status"] = "needs_revision"
        e["citation_review_note"] = NOTE
        e["reviewer"] = "identifier-audit-2026-07-24"
        e["reviewed_at"] = "2026-07-24"
        changed += 1
        print(f"  suppressed (needs_revision): {e['id']}")
    PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    print(f"\n{changed} entr(y/ies) suppressed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
