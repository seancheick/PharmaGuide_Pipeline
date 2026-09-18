#!/usr/bin/env python3
"""Validate authored Wave 1 contexts against the shared contract (read-only).

Every context must pass ``clinical_evidence_schema.validate_ingredient_context``
with ``authoring=True`` — which refuses any review status other than
``source_verified_pending_clinical_review``, so a curation run cannot mint its
own approval — and every verbatim quote must be an exact substring of the live
abstract recorded by ``verify_shortlist.py``.

    python3 scripts/audits/evidence_expansion_2026_09/validate_wave1_contexts.py [--candidates-dir DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

from clinical_evidence_schema import validate_ingredient_context  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates-dir", type=Path)
    args = parser.parse_args()
    payload = json.loads((OUT / "wave1_contexts.json").read_text())
    known = {item["canonical_id"] for item in payload["candidates"]}
    problems: list[str] = []
    contexts = 0
    for candidate in payload["candidates"]:
        for context in candidate["contexts"]:
            contexts += 1
            errors = validate_ingredient_context(context, known_component_ids=known, authoring=True)
            for error in errors:
                problems.append(f"{context['context_id']}: {error}")
            if args.candidates_dir:
                stored = {r["pmid"]: r for r in json.loads(
                    (args.candidates_dir / f"{candidate['canonical_id']}.json").read_text())["records"]}
                # Records fetched outside the original per-identity retrieval still need a
                # committed source to verify their quotes against.
                supplemental = OUT / "wave1_supplemental_records.json"
                if supplemental.exists():
                    stored.update({r["pmid"]: r for r in json.loads(supplemental.read_text())["records"]})
                for pmid in context["source_pmids"]:
                    abstract = (stored.get(pmid) or {}).get("abstract") or ""
                    provenance = (context.get("dose") or {}).get("source_provenance") or {}
                    quote = provenance.get("quote")
                    if quote and provenance.get("pmid") == pmid and quote not in abstract:
                        problems.append(f"{context['context_id']}: dose quote is not a substring of PMID {pmid}")
                    for evidence in context.get("outcome_provenance") or []:
                        if evidence.get("pmid") == pmid and evidence.get("quote") not in abstract:
                            problems.append(
                                f"{context['context_id']}: outcome quote is not a substring of PMID {pmid}")
    print(json.dumps({"candidates": len(payload["candidates"]), "contexts": contexts,
                      "problems": len(problems)}, indent=1))
    for problem in problems[:60]:
        print("  ", problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
