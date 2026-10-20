"""Rows a DSLD group still repairs away from the cleaner's identity where the printed name, with
preparation words removed, names the cleaner's identity (the wheat grass / bell pepper class).
Read-only. argv: RECORDS_DIR OUT_JSON"""
import collections, gzip, json, logging, re, sys
from pathlib import Path

logging.disable(logging.CRITICAL)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402

RECORDS, OUT = Path(sys.argv[1]), sys.argv[2]
registry = SupplementEnricherV3()._current_canonical_identity_registry()
PREP = r"\b(organic|raw|certified|whole|dried|freeze[- ]dried|juice|powder|powdered|concentrate|extract|leaf|leaves|fruit|root)\b"


def stripped(text):
    return re.sub(r"\s+", " ", re.sub(PREP, " ", re.sub(r"[,()]", " ", str(text or "").lower()))).strip()


hits = collections.defaultdict(list)
for p in sorted(RECORDS.glob("*.json.gz")):
    iqd = (json.load(gzip.open(p, "rt")).get("enriched") or {}).get("ingredient_quality_data") or {}
    for r in iqd.get("ingredients") or []:
        before, after = r.get("canonical_id_before"), r.get("canonical_id")
        if r.get("identity_disposition") != "repaired" or not before or before == after:
            continue
        label = r.get("raw_source_text") or ""
        core = stripped(label)
        names = {stripped(n) for n in registry.standard_names_of(before)}
        if core and (core in names or registry.literal_identity_matches(core, before)):
            group = (r.get("raw_taxonomy") or {}).get("ingredientGroup")
            hits[(label, before, after, group)].append(p.name[:-8])
print(len(hits), "label/identity pairs;", sum(len(v) for v in hits.values()), "rows")
for (label, before, after, group), ids in sorted(hits.items(), key=lambda kv: -len(kv[1])):
    print(f"{len(ids):3d} {label!r:42} cleaner={before:22} -> {after:22} group={group!r} e.g. {ids[:3]}")
json.dump([[list(k), v] for k, v in hits.items()], open(OUT, "w"), indent=1)
