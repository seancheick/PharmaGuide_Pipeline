"""
Sprint E1.2+ — one-product canary rebuild.

Runs the full Clean → Enrich → Score → Build pipeline for a single DSLD
product in memory, without writing brand-level batch files. Emits the
detail blob JSON to stdout (or --out) for shadow-diff against the
baseline at ``reports/baseline_v2026.04.21.224445/canaries/``.

Usage
-----
    python3 scripts/reports/canary_rebuild.py \
        --raw /Users/seancheick/Documents/DataSetDsld/staging/brands/Thorne/35491.json \
        --out reports/canary_rebuild/35491.json

Zero external API calls (the enricher uses cached reference data only).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


def rebuild_one(raw_path: Path) -> dict:
    """Load a raw DSLD JSON and run clean → enrich → score → build.
    Returns the final detail blob dict."""
    raw = json.loads(raw_path.read_text())

    # Stage 1: Clean
    from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402
    normalizer = EnhancedDSLDNormalizer()
    cleaned = normalizer.normalize_product(raw)

    # Stage 2: Enrich
    from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402
    enricher = SupplementEnricherV3()
    enriched, _errors = enricher.enrich_product(cleaned)

    # Stage 3: Score
    from score_supplements import SupplementScorer  # noqa: E402
    scorer = SupplementScorer()
    scored = scorer.score_product(enriched)

    # Stage 4: Build detail blob
    from build_final_db import build_detail_blob  # noqa: E402
    blob = build_detail_blob(enriched, scored)
    return blob


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--raw", required=True, type=Path, help="Raw DSLD product JSON")
    p.add_argument("--out", type=Path, default=None, help="Output path (default: stdout)")
    args = p.parse_args(argv)

    if not args.raw.is_file():
        sys.stderr.write(f"error: --raw {args.raw} not found\n")
        return 2

    blob = rebuild_one(args.raw)

    output = json.dumps(blob, indent=2, ensure_ascii=False, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n")
        sys.stdout.write(f"wrote {args.out} ({len(output)} bytes)\n")
    else:
        sys.stdout.write(output + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
