#!/usr/bin/env python3
"""Live identity gate for medication_depletions.json drug references.

The drug-class gate (verify_drug_class_rxcuis.py) covers `type:class` refs via
drug_classes.json. This covers the OTHER load-bearing surface: the 20
`type:drug` entries that carry a DIRECT rxcui the app matches by numeric id.
A wrong/retired direct rxcui, or a non-numeric synthetic id, silently drops a
depletion warning (under-warning — the more dangerous failure).

Checks (fail-closed):
  - type:class  -> the referenced class:* exists in drug_classes.json
  - type:drug   -> id is numeric AND resolves in RxNorm AND the RxNorm name
                   matches the entry's display_name

Live API, so NOT part of the fast test loop — run before a release:
    python3 scripts/api_audit/verify_medication_depletion_identifiers.py
Exit 0 = all resolve/match; exit 1 = at least one problem.

Entries the app suppresses (citation_review_status in {needs_revision, rejected})
are NOT display surfaces, so their identifiers are not gated — a hidden rule
cannot mislead a user. Only DISPLAYED entries (unverified/verified) are enforced.
This replaces an earlier hardcoded KNOWN_UNRESOLVED pass-exception: a dead id now
either blocks the gate (if displayed) or is explicitly suppressed (if hidden).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_drug_class_rxcuis import rxnorm_name  # noqa: E402  (shared live lookup + retry)

DATA = Path(__file__).resolve().parent.parent / "data"
MED = DATA / "medication_depletions.json"
CLASSES = DATA / "drug_classes.json"

# Entries the app suppresses are not display surfaces, so their identifiers are
# not gated. Everything DISPLAYED is gated (a dead id there blocks the release).
SUPPRESSED_STATUSES = {"needs_revision", "rejected"}


def _is_suppressed(entry: dict) -> bool:
    return entry.get("citation_review_status") in SUPPRESSED_STATUSES


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def _name_matches(rxnorm: str, display_name: str) -> bool:
    rn, dn = _norm(rxnorm), _norm(display_name)
    if not rn:
        return False
    lead = dn.split("(")[0].strip()  # "furosemide (lasix)" -> "furosemide"
    return rn in dn or lead in rn or rn in lead


def audit(deps: list[dict], class_ids: set[str], name_fn=rxnorm_name):
    """Return (problems, tracked, checked). name_fn is injectable for tests."""
    problems: list[str] = []
    tracked: list[str] = []
    checked = 0
    for e in deps:
        eid = e.get("id", "?")
        # Suppressed entries are hidden by the app — a dead identifier on one
        # cannot cause a live missed-warning, so identity is not enforced (only
        # tracked). Displayed entries (unverified/verified) ARE enforced.
        if _is_suppressed(e):
            tracked.append(f"{eid}: suppressed ({e.get('citation_review_status')}) — identity not enforced")
            continue
        dr = e.get("drug_ref") or {}
        dtype, did = dr.get("type"), str(dr.get("id") or "")
        if dtype == "class":
            if did not in class_ids:
                problems.append(f"{eid}: class ref '{did}' not in drug_classes.json (dead warning)")
            continue
        if dtype != "drug":
            problems.append(f"{eid}: unknown drug_ref.type={dtype!r}")
            continue
        # type:drug — direct rxcui (on a DISPLAYED entry)
        if not did.isdigit():
            problems.append(f"{eid}: non-numeric drug rxcui '{did}' on a displayed entry (synthetic/dead id)")
            continue
        checked += 1
        live = name_fn(did)
        if not live or live.startswith("ERR"):
            problems.append(f"{eid}: rxcui {did} has no current RxNorm name (retired?) [{live}]")
        elif not _name_matches(live, dr.get("display_name", "")):
            problems.append(
                f"{eid}: rxcui {did} → RxNorm '{live}' does not match display_name "
                f"'{dr.get('display_name')}' (WRONG DRUG?)"
            )
    return problems, tracked, checked


def main() -> int:
    deps = json.loads(MED.read_text())["depletions"]
    class_ids = set(json.loads(CLASSES.read_text())["classes"].keys())
    problems, tracked, checked = audit(deps, class_ids)

    print(f"checked {checked} direct-drug rxcuis across {len(deps)} depletion entries")
    if tracked:
        print(f"\n{len(tracked)} suppressed (app-hidden, identity not enforced):")
        for t in tracked:
            print("  ~", t)
    if problems:
        print(f"\n{len(problems)} PROBLEM(S):", file=sys.stderr)
        for p in problems:
            print("  -", p, file=sys.stderr)
        return 1
    print("all direct-drug rxcuis + class refs resolve.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
