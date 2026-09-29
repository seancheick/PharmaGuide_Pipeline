"""Read-only Dose-model proposal, corrected replay (review of 2026-09-28).

Changes from dose_proposal.py (v1), each answering a reproduced review finding:
  G1 a row whose DSLD forms are the same compound as another row's (Calcium in
     "Calcium HMB") is that compound's salt, not a claim: supporting group.
  G2 a main-group row lighter than 25% of the heaviest main row
     (scoring_input_contract._ROLE_MASS_MAJOR_FRACTION) is supporting: the
     100 mg whey line beside a 1.6 g EAA complex.
  B1 BCAA and EAA are assessed once, as a set, through the sports owners
     (sports_helpers.group_bcaa / group_eaa, declared aggregate rows); a lone
     or incomplete set gets no set benchmark (L-Leucine 5 g is not 5 g BCAA).
  B2 botanical benchmarks through botanical_profile._dosing_entry_for/_range_mg.
Every row keeps what the arms need (uncapped credit, % UL, % RDA, reference),
so the report script evaluates the missing-benchmark and excess options
without re-running the pipeline. Nothing in the repo changes.
"""
import glob, json, logging, re, sys
code = sys.argv[1]
sys.path.insert(0, f"{code}/scripts"); logging.disable(logging.CRITICAL)
from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3
from scoring_v4.scored_artifact import build_scored_artifact
from scoring_v4.exposure import row_exposure
from scoring_v4.modules.generic_helpers import get_active_ingredients
from scoring_v4.modules import generic_dose as gd
from scoring_v4.modules import sports_helpers as sh
from scoring_v4.modules import botanical_profile as bp
from scoring_input_contract import (classify_ingredient_roles, is_lent_blend_mass, is_nutrition_fact_declaration,
                                    _role_mass_mg, _ROLE_MASS_MAJOR_FRACTION)
import scoring_v4.quality_score_config as qc

CFG = qc.config()
JOINT = CFG["category_magnitudes"]["joint_support"]["target_dose_mg"]
SPORTS = [
    (sh.CREATINE_CANONICALS, 3000, "daily", "creatine 3-10 g/day band"),
    (sh.BETA_ALANINE_CANONICALS, 4000, "daily", "beta-alanine 4-6 g/day band"),
    (sh.HMB_CANONICALS, 3000, "daily", "HMB 3-6 g/day band"),
    (sh.CAFFEINE_CANONICALS, 200, "per_use", "caffeine 200-400 mg per use band"),
    (sh.BETAINE_CANONICALS, 2500, "per_use", "betaine >=2.5 g band"),
    (sh.TAURINE_CANONICALS, 1000, "per_use", "taurine >=1 g band"),
    (sh.ALPHA_GPC_CANONICALS, 600, "per_use", "alpha-GPC >=600 mg band"),
    (sh.ATP_CANONICALS, 400, "per_use", "ATP >=400 mg band"),
    (sh.SPORTS_PROTEIN_CANONICALS, 20000, "per_use", "protein 20-40 g band"),
    (sh.CITRULLINE_CANONICALS, 6000, "per_use", "L-citrulline 6-8 g band"),
]
ROOTS = ["frozen_proposal", "frozen_ranged", "frozen_offlist", "frozen_targeted", "frozen_chloride"]
D23 = {"tesnor_pomegranate_cocoa_blend": 200.0, "sytrinol": 300.0}
RANK = {"primary": 0, "claim_prominent": 1, "major": 2, "adjunct": 3, None: 4}


def raw_at(raw, path):
    node = {"ingredientRows": raw.get("ingredientRows") or []}
    for key, idx in re.findall(r"(\w+)\[(\d+)\]", path or ""):
        try:
            node = (node.get(key) or [])[int(idx)]
        except (IndexError, AttributeError):
            return {}
    return node if isinstance(node, dict) else {}


def forms_key(raw, row):
    names = [re.sub(r"[^a-z0-9]", "", str(f.get("name") or "").lower()) for f in raw_at(raw, row.get("raw_source_path")).get("forms") or []]
    return frozenset(n for n in names if n)


def hidden_contents(product, raw, row):
    """A blend heading hides amounts when a direct content has no printed amount,
    or when it lists two or more DSLD forms and no content rows (GNC style). When
    every direct content is dosed, the heading is represented by its contents."""
    r = raw_at(raw, row.get("raw_source_path"))
    kids = r.get("nestedRows") or []
    if not kids:
        return len(r.get("forms") or []) >= 2
    for k in kids:
        q = (k.get("quantity") or [{}])[0]
        if not q.get("quantity") or str(q.get("unit") or "").upper() == "NP":
            return True
    return False


def amount(product, row, basis, unit="mg"):
    return row_exposure(product, row, basis=basis, unit=unit).benchmark_amount


def rda_row(product, canonical):
    for a in (product.get("rda_ul_data") or {}).get("adequacy_results") or []:
        if gd._norm_text(a.get("canonical_id")) == canonical and a.get("scoring_eligible") is not False:
            return a
    return None


def item(state, credit=None, note="", **kw):
    return dict(state=state, credit=credit, note=note, **kw)


def assess(product, raw, row, route):
    canonical = gd._norm_text(row.get("canonical_id"))
    if row.get("evidence_type") == "blend_anchor_mass" and row.get("evidence_scope") == "blend_level":
        if canonical in D23:
            got = amount(product, row, "daily")
            d23 = None if got is None else min(got / D23[canonical], 1.0)
        else:
            d23 = None
        if hidden_contents(product, raw, row) or canonical in D23:
            return item("unknown", note="blend total; contents' amounts hidden", d23_credit=d23)
        if raw_at(raw, row.get("raw_source_path")).get("nestedRows"):
            return None  # every content is dosed and assessed on its own row
    if canonical in {"melatonin"}:
        got = amount(product, row, "daily")
        return item("unknown", note="melatonin, no own amount") if got is None else \
            item("assessed", min(got / 0.3, 1.0), f"{got:g} mg/day vs 0.3 (sleep band low edge)")
    for canons, bench, basis, src in SPORTS:
        if canonical in canons:
            got = amount(product, row, basis)
            return item("unknown", note=src + ", no own amount") if got is None else \
                item("assessed", min(got / bench, 1.0), f"{got:g} mg {basis} vs {bench} ({src})")
    for key, bench in JOINT.items():
        if canonical.startswith(key):
            got = amount(product, row, "daily")
            return item("unknown", note="joint target, no own amount") if got is None else \
                item("assessed", min(got / bench, 1.0), f"{got:g} mg/day vs {bench} (joint target)")
    if route == "fiber_digestive":
        grams = product["_proposal_dims"]["dose"]["metadata"].get("fiber_grams_daily_benchmark")
        if grams:
            return item("assessed", min(grams / 7.0, 1.0), f"{grams:g} g fiber/day vs 7 g (fiber full band)")
    if canonical in gd._DIETARY_INTAKE_DOMINANT_CANONICALS:
        return item("not_assessable", note="dietary-intake nutrient, no supplement benchmark")
    a = rda_row(product, canonical)
    if a is not None and a.get("pct_rda") is not None:
        kind = gd._adequacy_reference_kind(canonical)
        full = gd.WINDOW_RDA_THRESHOLD if kind == "legacy" else gd.WINDOW_FULL_ADEQUACY_PCT
        pct = float(a["pct_rda"])
        return item("assessed", min(pct / full, 1.0), f"{pct:.0f}% of RDA/AI vs {full:g}% ({kind})",
                    pct_rda=pct, full=full, kind=kind, pct_ul=a.get("pct_ul"), panel=True)
    entry = bp._dosing_entry_for(row)
    rng = bp._range_mg(entry) if entry else None
    if rng and rng[0] > 0:
        got = amount(product, row, "daily")
        return item("unknown", note="therapeutic range, no own amount") if got is None else \
            item("assessed", min(got / rng[0], 1.0), f"{got:g} mg/day vs {rng[0]:g} ({entry.get('standard_name')} range low)")
    if row.get("quantity") in (None, 0, 0.0):
        return item("unknown", note="no amount on the label")
    return item("not_assessable", note="declared, no applicable benchmark")


def set_items(product, rows, roles):
    """BCAA / EAA assessed once as a set through the sports owners (B1)."""
    dosed = sh.sports_dosed_rows(product)
    out, members = [], set()
    eaa = sh.group_eaa(dosed)
    if eaa["complete"] and eaa["total_g"]:
        ms = [r for r in rows if gd._norm_text(r.get("canonical_id")) in sh.EAA_CANONICALS | sh.EAA_AGGREGATE_CANONICALS]
        members |= {id(r) for r in ms}
        mg = eaa["total_g"] * 1000
        out.append(dict(name="EAA total", role=min((roles.get(id(r)) for r in ms), key=RANK.get, default=None), mass=mg,
                        **item("assessed", min(mg / 8000, 1.0), f"{mg:g} mg per use vs 8000 (complete EAA >=8 g band)")))
    bcaa = sh.group_bcaa(dosed)
    agg = [r for r in rows if gd._norm_text(r.get("canonical_id")) in sh.BCAA_AGGREGATE_CANONICALS and not is_lent_blend_mass(r)]
    agg_mg = max((amount(product, r, "per_use") or 0 for r in agg), default=0)
    bcaa_mg = max(agg_mg, (bcaa["total_g"] * 1000) if bcaa["complete"] else 0)
    if bcaa_mg and not (eaa["complete"] and eaa["total_g"]):
        ms = [r for r in rows if gd._norm_text(r.get("canonical_id")) in sh.BCAA_CANONICALS | sh.BCAA_AGGREGATE_CANONICALS]
        members |= {id(r) for r in ms}
        out.append(dict(name="BCAA total", role=min((roles.get(id(r)) for r in ms), key=RANK.get, default=None), mass=bcaa_mg,
                        **item("assessed", min(bcaa_mg / 5000, 1.0), f"{bcaa_mg:g} mg per use vs 5000 (BCAA >=5 g band)")))
    elif eaa["complete"] and eaa["total_g"]:
        members |= {id(r) for r in rows if gd._norm_text(r.get("canonical_id")) in sh.BCAA_AGGREGATE_CANONICALS}
    return out, members


def load(pid):
    f = [g for r in ROOTS for g in glob.glob(f"/Users/seancheick/pg_quality/rr_fix/{r}/*/{pid}.json")] + \
        glob.glob(f"/Users/seancheick/pg_quality/rr_20260928/frozen/*/{pid}.json")
    return json.load(open(f[0]))


def propose(pid):
    raw = load(pid)
    en, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    art = build_scored_artifact(en)
    pillars = art.get("quality_pillars_v4") or {}
    base = dict(id=pid, name=en.get("product_name"), route=art.get("_v4_module"), status=art.get("quality_score_status"),
                total=art.get("quality_score_v4_100"), dose_now=(pillars.get("dose") or {}).get("score"),
                safety_now=(pillars.get("safety_hygiene") or pillars.get("safety") or {}).get("score"))
    if base["status"] != "scored" or base["route"] == "probiotic":
        return dict(base, items=[], skipped=base["status"] if base["status"] != "scored" else "probiotic CFU Dose unchanged")
    en["_proposal_dims"] = art["_v4_module_breakdown"]["dimensions"]
    rows = get_active_ingredients(en)
    roles = {id(r): role.get("role") for r, role in zip(rows, classify_ingredient_roles(en, rows=rows))}
    items = []
    if base["route"] == "omega":
        meta = en["_proposal_dims"]["dose"].get("metadata") or {}
        per_day = meta.get("per_day_min_mg", meta.get("per_day_mg")) or 0.0
        items.append(dict(name="EPA+DHA", role="primary", mass=None,
                          **(item("assessed", min(per_day / 2000.0, 1.0), f"{per_day:g} mg EPA+DHA/day vs 2000") if per_day
                             else item("unknown", note="EPA/DHA not declared (oil mass is not EPA/DHA)"))))
    else:
        agg_items, members = set_items(en, rows, roles)
        items += agg_items
        aggregate_paths = {str(r.get("raw_source_path")) for r in rows if r.get("evidence_type") == "sports_primary_dose"}
        keys = {id(r): forms_key(raw, r) for r in rows}
        for r in rows:
            if is_lent_blend_mass(r) or is_nutrition_fact_declaration(r) or id(r) in members:
                continue
            if r.get("evidence_type") != "sports_primary_dose" and str(r.get("raw_source_path")) in aggregate_paths:
                continue
            role, why = roles.get(id(r)), None
            k = keys[id(r)]
            if k and role == "claim_prominent" and any(keys[id(o)] == k and o is not r and roles.get(id(o)) == "primary" for o in rows):
                role, why = "adjunct", "salt of the primary compound (G1)"
            canon = gd._norm_text(r.get("canonical_id"))
            if canon in sh.BCAA_CANONICALS | sh.EAA_CANONICALS:
                it = item("not_assessable", note="single amino acid outside a complete set; no own benchmark")
            else:
                it = assess(en, raw, r, base["route"])
                if it is None:
                    continue
            items.append(dict(name=r.get("name"), role=role, regroup=why, mass=_role_mass_mg(r), **it))
    # G2: trace main rows are supporting.
    if base["route"] not in {"multi_or_prenatal", "b_complex"}:
        tier = next((t for t in ({"primary", "claim_prominent"}, {"major"}) if any(i["role"] in t for i in items)), set())
        heaviest = max((i["mass"] or 0 for i in items if i["role"] in tier), default=0)
        for i in items:
            i["group"] = "main" if i["role"] in tier else "rest"
            if i["group"] == "main" and i["mass"] and heaviest and i["mass"] < _ROLE_MASS_MAJOR_FRACTION * heaviest:
                i["group"], i["regroup"] = "rest", f"under 25% of the heaviest main row (G2)"
        if not tier:
            for i in items:
                i["group"] = "main"
    else:
        for i in items:
            i["group"] = "main" if i.get("panel") else "rest"
    return dict(base, items=items)


if __name__ == "__main__":
    for pid in sys.argv[2].split(","):
        try:
            res = propose(pid)
        except Exception as exc:
            res = dict(id=pid, error=repr(exc)[:300])
        print(json.dumps(res, default=str), flush=True)
