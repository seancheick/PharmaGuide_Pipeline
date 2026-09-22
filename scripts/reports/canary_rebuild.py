"""
One-product canary rebuild.

Runs Clean → Enrich → Score (v4) → Build for a single raw DSLD label in memory,
without writing brand-level batch files, and emits the detail blob. The canary
tests read ``reports/canary_rebuild/<id>.json``; rebuild them from the current
code whenever enrichment, scoring or the blob changes, or those tests check an
old build.

Usage
-----
    python3 scripts/reports/canary_rebuild.py \
        --raw ~/Downloads/PharmaGuide_Datasets/staging/brands/Nature_Made/19067.json \
        --out reports/canary_rebuild/19067.json

Zero external API calls (the enricher uses cached reference data only).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


def rebuild_one(raw_path: Path) -> dict:
    """Clean → enrich → score → build one raw DSLD label; return the detail blob."""
    raw = json.loads(raw_path.read_text())

    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact
    from build_final_db import build_detail_blob

    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    enriched, _errors = SupplementEnricherV3().enrich_product(cleaned)
    return build_detail_blob(enriched, build_scored_artifact(enriched))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--raw", required=True, type=Path, help="Raw DSLD product JSON")
    p.add_argument("--out", type=Path, default=None, help="Output path (default: stdout)")
    args = p.parse_args(argv)

    if not args.raw.is_file():
        sys.stderr.write(f"error: --raw {args.raw} not found\n")
        return 2

    output = json.dumps(rebuild_one(args.raw), indent=2, ensure_ascii=False, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n")
        sys.stdout.write(f"wrote {args.out} ({len(output)} bytes)\n")
    else:
        sys.stdout.write(output + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
