#!/usr/bin/env python3
"""Read-only botanical CUI re-resolution candidate generator (Wave 9.F).

The Wave 9.F.1 sweep found that ~56% of botanical_ingredients.json CUIs are
corrupt: 60 are retired (do not resolve in UMLS) and ~225 resolve to entirely
unrelated concepts (viruses, body parts, lab procedures, wrong plants) — the
classic "ghost identifier" failure mode (a real CUI about the wrong topic).

This tool proposes the correct CUI for each flagged entry by performing a live
UMLS exact-name search on the entry's latin_name (the species binomial), then
standard_name as fallback. It WRITES NOTHING to scripts/data/. It emits a
candidate table the operator reviews and applies per-entry with TDD.

Confidence tiers:
  A_exact_latin_plant   — UMLS returns a concept whose name exactly matches the
                          latin_name (normalized) AND semantic type is a
                          botanical/organism/substance type. Highest confidence.
  B_exact_std_plant     — same, but matched on standard_name (common name).
  C_exact_name_other    — exact name match but semantic type is not an obvious
                          organism/substance type (needs eyeballing).
  D_review              — no exact match; multiple or fuzzy candidates listed.

Usage:
  python3 scripts/api_audit/botanical_cui_resolver.py \
    --file scripts/data/botanical_ingredients.json \
    --findings reports/botanical_ingredients_identifier_sweep/findings.jsonl \
    --cache reports/botanical_ingredients_identifier_sweep/_cache/umls.json \
    --out reports/botanical_ingredients_identifier_sweep/cui_candidates.json \
    [--exclude-id id1,id2,...]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from env_loader import _load_env  # noqa: E402
from verify_cui import UMLSClient  # noqa: E402

# Semantic types that legitimately describe a botanical source or its
# constituent substance.
ORGANISM_STY = {
    "Plant", "Fungus", "Bacterium", "Alga", "Eukaryote", "Archaeon",
    "Virus",  # only if intentional; flagged in tier anyway
}
SUBSTANCE_STY = {
    "Organic Chemical", "Pharmacologic Substance", "Biologically Active Substance",
    "Food", "Inorganic Chemical", "Chemical Viewed Functionally",
}


def _norm(name: str) -> str:
    """Normalize a botanical name for exact comparison."""
    if not name:
        return ""
    n = name.lower().strip()
    # hybrid marker and common qualifiers
    n = n.replace(" × ", " ").replace(" x ", " ").replace("×", " ")
    n = n.replace("(plant)", "").replace("(fungus)", "")
    n = " ".join(n.split())
    return n


def _classify(query_norm: str, results: list[dict]) -> tuple[str, dict | None]:
    """Return (tier, chosen_result) given normalized query and UMLS results."""
    exact = [r for r in results if _norm(r.get("name", "")) == query_norm]
    for r in exact:
        sts = set(r.get("semantic_types") or [])
        if sts & (ORGANISM_STY | SUBSTANCE_STY):
            return "exact_organism_or_substance", r
    if exact:
        return "exact_other_semantic_type", exact[0]
    return "review", None


def resolve_entry(client: UMLSClient, entry: dict) -> dict:
    latin = entry.get("latin_name") or ""
    std = entry.get("standard_name") or ""
    out = {
        "id": entry["id"],
        "standard_name": std,
        "latin_name": latin,
        "current_cui": entry.get("cui"),
        "proposed_cui": None,
        "proposed_name": None,
        "proposed_sty": None,
        "tier": "D_review",
        "candidates": [],
    }

    # Try latin first, then standard_name.
    for source, term in (("latin", latin), ("std", std)):
        if not term:
            continue
        qn = _norm(term)
        # search needs the raw (un-normalized) term for best recall
        results = client.search(term, max_results=8)
        # enrich each result with semantic types via lookup (cached)
        enriched = []
        for r in results[:8]:
            info = client.lookup_cui(r["cui"])
            if info:
                enriched.append({
                    "cui": r["cui"],
                    "name": info.get("name"),
                    "semantic_types": info.get("semantic_types"),
                })
        cls, chosen = _classify(qn, enriched)
        if chosen:
            tier = {
                ("latin", "exact_organism_or_substance"): "A_exact_latin_plant",
                ("std", "exact_organism_or_substance"): "B_exact_std_plant",
                ("latin", "exact_other_semantic_type"): "C_exact_name_other",
                ("std", "exact_other_semantic_type"): "C_exact_name_other",
            }[(source, cls)]
            out.update(
                proposed_cui=chosen["cui"],
                proposed_name=chosen["name"],
                proposed_sty=chosen["semantic_types"],
                tier=tier,
                candidates=enriched,
            )
            return out
        # keep candidates from latin search for review if nothing better
        if source == "latin" and enriched:
            out["candidates"] = enriched

    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--findings", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--exclude-id", default="")
    args = ap.parse_args()

    _load_env()
    api_key = os.environ.get("UMLS_API_KEY")
    if not api_key:
        print("UMLS_API_KEY not set", file=sys.stderr)
        return 2

    data = json.loads(Path(args.file).read_text())
    entries = {e["id"]: e for e in data["botanical_ingredients"]}

    findings = [json.loads(l) for l in Path(args.findings).read_text().splitlines() if l.strip()]
    exclude = {x for x in args.exclude_id.split(",") if x}
    # Open CUI findings = field cui, not seed, not already fixed.
    flagged_ids = []
    seen = set()
    for f in findings:
        if f.get("field") != "cui" or f.get("seed"):
            continue
        cid = f["canonical_id"]
        if cid in exclude or cid in seen or cid not in entries:
            continue
        seen.add(cid)
        flagged_ids.append(cid)

    client = UMLSClient(api_key=api_key, timeout_seconds=10.0, cache_path=Path(args.cache))

    results = []
    for i, cid in enumerate(sorted(flagged_ids), 1):
        try:
            results.append(resolve_entry(client, entries[cid]))
        except Exception as e:  # noqa: BLE001
            results.append({"id": cid, "tier": "E_error", "error": str(e)})
        if i % 25 == 0:
            print(f"  [{i}/{len(flagged_ids)}] resolved")
            # persist cache periodically
            try:
                client._save_cache()  # type: ignore[attr-defined]
            except Exception:
                pass

    # persist cache
    try:
        client._save_cache()  # type: ignore[attr-defined]
    except Exception:
        pass

    from collections import Counter
    tier_counts = Counter(r.get("tier") for r in results)
    payload = {
        "total": len(results),
        "tier_counts": dict(tier_counts),
        "candidates": results,
    }
    Path(args.out).write_text(json.dumps(payload, indent=2))
    print(json.dumps({"total": len(results), "tier_counts": dict(tier_counts)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
