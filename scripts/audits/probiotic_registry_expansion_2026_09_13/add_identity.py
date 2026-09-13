#!/usr/bin/env python3
"""Add ONE strain identity to clinically_relevant_strains.json and prove it resolves.

Usage: add_identity.py <spec.json> <identity_id> [--universe universe.json]

Each identity is a stub: no evidence, no sign-off, no dose tiers. It records
that a printed strain designation is recognized (identity_verification says
how) so a label can resolve to "exact strain, not yet reviewed" instead of
falling through to species-only. Refuses duplicates, refuses an alias that
already belongs to another identity, and asserts every expected label string
resolves through the production matcher.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from studied_formulas import clinical_strain_identity_matches  # noqa: E402

REG = ROOT / "scripts/data/clinically_relevant_strains.json"
TODAY = "2026-09-13"


def _key(v):
    return re.sub(r"[^a-z0-9]+", "", str(v or "").lower())


def main():
    spec_path, ident = sys.argv[1], sys.argv[2]
    universe = None
    if "--universe" in sys.argv:
        universe = json.load(open(sys.argv[sys.argv.index("--universe") + 1]))
    spec = json.load(open(spec_path))[ident]
    raw = REG.read_text()
    reg = json.loads(raw)
    entries = reg["clinically_relevant_strains"]
    if any(e["id"] == ident for e in entries):
        sys.exit(f"REFUSED {ident}: already present")
    names = [spec["standard_name"], *spec["aliases"]]
    owned = {}
    for e in entries:
        for n in [e["standard_name"], *e.get("aliases", [])]:
            owned[_key(n)] = e["id"]
    clashes = {n: owned[_key(n)] for n in names if _key(n) in owned}
    if clashes:
        sys.exit(f"REFUSED {ident}: alias already owned {clashes}")
    entry = {
        "id": ident,
        "standard_name": spec["standard_name"],
        "aliases": spec["aliases"],
        "evidence_level": "unreviewed",
        "key_benefits": [],
        "notable_studies": "Strain designation recognized on product labels; no clinical evidence review has been performed for this identity.",
        "identity_verification": {
            "status": spec["verification"],
            "source_pmids": spec.get("pmids", []),
            "deposit_ids": spec.get("deposits", []),
            "supplier": spec.get("supplier"),
            "verified_on": TODAY,
            "method": "PubMed title/abstract read for the designation and species; label-only when no literature hit",
            "note": spec.get("note"),
        },
        "cfu_thresholds": {
            "indication_primary": None,
            "tiers_cfu_per_day": None,
            "dr_pham_signoff": False,
            "evidence": None,
        },
        "study_contexts": [],
    }
    # Prove resolution through the production matcher before writing.
    for label in spec["expect_labels"]:
        if not clinical_strain_identity_matches(label, entry):
            sys.exit(f"REFUSED {ident}: expected label does not resolve: {label!r}")
    # Text-level insertion: the file is not byte-stable through json.dumps.
    anchor = "\n  ],\n  \"prebiotics\""
    if raw.count(anchor) != 1:
        sys.exit("REFUSED: registry array anchor not found exactly once")
    block = ",\n" + "\n".join("    " + line for line in json.dumps(entry, indent=2, ensure_ascii=True).splitlines())
    raw = raw.replace(anchor, block + anchor, 1)
    count = len(entries) + 1
    raw, n1 = re.subn(r'"total_entries": \d+', f'"total_entries": {count}', raw, count=1)
    raw, n2 = re.subn(r'"last_updated": "[0-9-]+"', f'"last_updated": "{TODAY}"', raw, count=1)
    if n1 != 1 or n2 != 1:
        sys.exit("REFUSED: metadata fields not found exactly once")
    parsed = json.loads(raw)
    assert len(parsed["clinically_relevant_strains"]) == count == parsed["_metadata"]["total_entries"]
    REG.write_text(raw)
    entries = parsed["clinically_relevant_strains"]
    covered = 0
    if universe is not None:
        for r in universe:
            if clinical_strain_identity_matches(r["label"], entry):
                covered += r["products"]
    print(f"ADDED {ident} entries={len(entries)} labels_ok={len(spec['expect_labels'])} corpus_slots={covered} verification={spec['verification']}")


if __name__ == "__main__":
    main()
