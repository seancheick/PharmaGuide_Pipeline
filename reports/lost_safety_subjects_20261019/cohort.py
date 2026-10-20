"""Replay cohort for the lost-safety-subject batch. Read-only over a replay --full records dir.

Affected: products with (a) a blend-header row carrying a specific (non-BLEND_*) identity,
(b) a row whose identity the enricher erased as non-scorable (taxonomy_only, canonical_id None,
canonical_id_before set), or (c) a row listed by missed_warnings.json. Controls: a seeded random
sample of the rest. argv: RECORDS_DIR MISSED_JSON N_CONTROLS OUT_JSON"""
import gzip, json, random, sys
from pathlib import Path

RECORDS, MISSED, N, OUT = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), sys.argv[4]
missed = {p for v in json.load(open(MISSED))["products"].values() for p in v}
header, erased, rest = set(), set(), []
for p in sorted(RECORDS.glob("*.json.gz")):
    pid = p.name[:-8]
    iqd = (json.load(gzip.open(p, "rt")).get("enriched") or {}).get("ingredient_quality_data") or {}
    hit = False
    for r in (iqd.get("ingredients") or []) + (iqd.get("ingredients_skipped") or []):
        cid = str(r.get("canonical_id") or "")
        if r.get("skip_reason") == "blend_header_total_weight_only" and cid and not cid.upper().startswith("BLEND_"):
            header.add(pid); hit = True
        if r.get("identity_disposition") == "taxonomy_only" and not cid and r.get("canonical_id_before"):
            erased.add(pid); hit = True
    if not hit and pid not in missed:
        rest.append(pid)
random.seed(20261019)
controls = sorted(random.sample(rest, N))
affected = sorted(header | erased | missed)
json.dump({"header": sorted(header), "erased": sorted(erased), "missed": sorted(missed), "affected": affected,
           "controls": controls}, open(OUT, "w"), indent=1)
print(f"header {len(header)} erased {len(erased)} missed {len(missed)} affected {len(affected)} controls {len(controls)}")
