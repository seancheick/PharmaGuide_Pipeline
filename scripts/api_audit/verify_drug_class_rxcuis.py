#!/usr/bin/env python3
"""Live RxNorm audit of every drug_classes.json member rxcui.

The artifact/build path validates that identifier STRINGS are non-empty, but it
does NOT resolve them — which is how a batch of retired/swapped rxcuis
(2026-07-24 audit) shipped undetected. This is the missing live gate: it queries
RxNorm for every (rxcui, name) pair and flags any that is retired (no current
name) or maps to a different drug than authored.

Live API, so NOT part of the fast test loop — run before a release:
    python3 scripts/api_audit/verify_drug_class_rxcuis.py            # all classes
    python3 scripts/api_audit/verify_drug_class_rxcuis.py class:acid_suppressants
Exit 0 = all resolve and match; exit 1 = at least one mismatch.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping

DRUG_CLASSES = Path(__file__).resolve().parent.parent / "data" / "drug_classes.json"
NAME_URL = "https://rxnav.nlm.nih.gov/REST/rxcui/{}/property.json?propName=RxNorm%20Name"


def rxnorm_name(rxcui: str, attempts: int = 3) -> str:
    """Return the current RxNorm Name for an rxcui ("" if none/retired).

    Retries transient failures; a persistent failure returns "ERR:..." which the
    caller treats as a problem (fail-closed — a network blip must never read as
    'this rxcui is fine')."""
    last = ""
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(NAME_URL.format(rxcui), timeout=15) as r:
                d = json.load(r)
            p = d.get("propConceptGroup", {}).get("propConcept", [])
            return p[0]["propValue"] if p else ""
        except Exception as e:  # noqa: BLE001
            last = f"ERR:{e}"
            time.sleep(1.0 * (2 ** attempt))
    return last


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def audit(
    classes: Mapping[str, Mapping[str, Any]],
    *,
    only: set[str] | None = None,
    name_fn: Callable[[str], str] = rxnorm_name,
    request_delay: float = 0.05,
) -> tuple[list[str], int]:
    """Return problems and checked count without conflating network and data."""
    problems: list[str] = []
    checked = 0
    for cid, drug_class in classes.items():
        if only and cid not in only:
            continue
        for rxcui, name in zip(
            drug_class["member_rxcuis"],
            drug_class["member_names"],
        ):
            live = name_fn(str(rxcui))
            checked += 1
            if live.startswith("ERR"):
                problems.append(
                    f"{cid}/{name} rxcui={rxcui}: RxNorm registry transport "
                    f"failure [{live}]"
                )
            elif not live:
                problems.append(
                    f"{cid}/{name} rxcui={rxcui}: no current RxNorm name "
                    "(retired?)"
                )
            elif _norm(live) != _norm(str(name)):
                problems.append(
                    f"{cid}/{name} rxcui={rxcui}: RxNorm says '{live}' "
                    "(WRONG DRUG)"
                )
            if request_delay:
                time.sleep(request_delay)
    return problems, checked


def main(argv: list[str]) -> int:
    classes = json.loads(DRUG_CLASSES.read_text())["classes"]
    only = set(argv[1:]) or None
    problems, checked = audit(classes, only=only)
    print(f"checked {checked} rxcuis across {len(only) if only else len(classes)} class(es)")
    if problems:
        print(f"\n{len(problems)} PROBLEM(S):", file=sys.stderr)
        for p in problems:
            print("  -", p, file=sys.stderr)
        return 1
    print("all rxcuis resolve to their authored drug.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
