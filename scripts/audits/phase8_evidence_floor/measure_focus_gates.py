"""Phase 8 spike — measure the primary-ingredient evidence floor at each focus gate
vs the no-floor baseline. Reports verdict shifts by category + key products."""
import json, glob, sys
from collections import Counter, defaultdict
sys.path.insert(0, "/Users/seancheick/Downloads/dsld_clean/scripts")
import scoring_v4.modules.generic_evidence as ge
from score_supplements_v4 import score_product_v4

# load corpus once
products = []
for p in glob.glob("/Users/seancheick/Downloads/dsld_clean/scripts/products/output_*_enriched/enriched/enriched_cleaned_batch_*.json"):
    try:
        d = json.loads(open(p).read())
    except Exception:
        continue
    for it in (d if isinstance(d, list) else d.get("products", [])):
        if isinstance(it, dict) and it.get("dsld_id") is not None:
            products.append(it)
print(f"loaded {len(products)} products\n", flush=True)

def run(enabled, focus_max):
    ge.PRIMARY_FLOOR_ENABLED = enabled
    ge.PRIMARY_FLOOR_FOCUS_MAX = focus_max
    out = {}
    for it in products:
        try:
            o = score_product_v4(it)
        except Exception:
            continue
        out[str(it.get("dsld_id"))] = (o["v4_verdict"], o["raw_score_v4_100"], o["v4_module"])
    return out

base = run(False, 0)
print("baseline (no floor) scored\n", flush=True)

KSM = {str(it.get("dsld_id")) for it in products
       if "ksm" in (it.get("product_name") or "").lower() and "transparent" in (it.get("brand_name") or "").lower()}

for fmax in (1, 2, 3):
    cur = run(True, fmax)
    flips = Counter()
    by_mod_lift = defaultdict(int)
    poor_to_safe = 0
    for did, (v1, s1, mod) in base.items():
        v2, s2, _ = cur.get(did, (v1, s1, mod))
        if v1 != v2:
            flips[(v1, v2)] += 1
            by_mod_lift[mod] += 1
            if v1 in ("POOR", "CAUTION") and v2 == "SAFE":
                poor_to_safe += 1
    nfloored = sum(1 for did in cur if cur[did][1] != base.get(did, (None, cur[did][1]))[1])
    ksm_v = [cur[d] for d in KSM if d in cur]
    print(f"=== FOCUS_MAX <= {fmax} ===")
    print(f"  products whose score changed vs baseline: {nfloored} ({round(100*nfloored/len(base))}%)")
    print(f"  verdict flips vs baseline: {dict(flips.most_common())}")
    print(f"  POOR/CAUTION -> SAFE: {poor_to_safe}")
    print(f"  KSM-66: {ksm_v}")
    print(flush=True)
