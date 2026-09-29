"""Arms over the corrected replay (dose_proposal_v2.py outputs v2_*.jsonl).

missing  A: a row or group with no benchmark counts 0
         B: it is left out and the rest is rescaled (whole product: total over 80)
         C: it keeps today's fixed no-reference credit, 14.5/20 = 0.725
         R: Evidence's coverage-gap rule: an unbenchmarked main row earns 0 (the pillar
            is shown as not fully assessed); an unbenchmarked supporting row is left out
excess   E0: benefit capped at the benchmark, no Dose reduction (Safety only)
         E1: over UL at most 0.75, >=150% of UL at most 0.5 (v1)
         E2: over UL at most 0.75, >=150% of UL at most 0.25
legacy   L25: calcium/magnesium/... full at 25% of RDA (today)  L100: at 100% on multi routes
"""
import glob, json, statistics, sys
from collections import Counter, defaultdict

P = [json.loads(l) for f in sorted(glob.glob("/Users/seancheick/pg_quality/rr_fix/v2_[0-9].jsonl")) for l in open(f)]
NOREF = 14.5 / 20
CAPS = {"E0": (1.0, 1.0), "E1": (0.75, 0.5), "E2": (0.75, 0.25)}
TIERS = [95, 90, 80, 70, 55]


def credit(i, route, excess, legacy, d23):
    if i["state"] == "unknown":
        return (i.get("d23_credit") or 0.0) if d23 else 0.0
    c = i["credit"]
    if legacy == "L100" and i.get("kind") == "legacy" and route in {"multi_or_prenatal", "b_complex"}:
        c = min(i["pct_rda"] / 100.0, 1.0)
    ul = i.get("pct_ul")
    if ul is not None and ul >= 150:
        c = min(c, CAPS[excess][1])
    elif ul is not None and ul > 100:
        c = min(c, CAPS[excess][0])
    return c


def dose(p, missing="B", excess="E0", legacy="L25", d23=False):
    """Return (dose or None, how)."""
    means, present = {}, {}
    for g in ("main", "rest"):
        its = [i for i in p["items"] if i["group"] == g]
        present[g] = bool(its)
        vals = []
        for i in its:
            if i["state"] == "not_assessable":
                if missing == "A" or (missing == "R" and g == "main"):
                    vals.append(0.0)
                elif missing == "C":
                    vals.append(NOREF)
                continue
            vals.append(credit(i, p["route"], excess, legacy, d23))
        means[g] = sum(vals) / len(vals) if vals else None
    m, s = means["main"], means["rest"]
    if m is not None and s is not None:
        return 20 * (0.7 * m + 0.3 * s), "both groups"
    if m is not None:
        return 20 * m, "main only" if not present["rest"] else "main only (rest unassessable)"
    if s is not None:
        return 20 * s, "rest only" if not present["main"] else "rest only (main unassessable)"
    return None, "nothing assessable"


def total(p, d):
    other = (p["total"] or 0) - (p["dose_now"] or 0)
    return round(other * 100 / 80, 1) if d is None else round(other + d, 1)


def tier(x):
    return next((t for t in TIERS if x >= t), 0)


scored = [p for p in P if p.get("status") == "scored" and not p.get("skipped") and not p.get("error")]
probiotic = [p for p in P if p.get("skipped") == "probiotic CFU Dose unchanged"]
errors = [p for p in P if p.get("error")]
print(f"labels {len(P)}; scored non-probiotic {len(scored)}; probiotic unchanged {len(probiotic)}; "
      f"not scored {sum(1 for p in P if p.get('status') not in ('scored', None))}; errors {len(errors)}")
for e in errors:
    print("  ERROR", e["id"], e["error"][:160])


def summary(label, **arm):
    moves = Counter(); deltas = defaultdict(list); cross = 0; totals = []
    for p in scored:
        d, how = dose(p, **arm)
        t = total(p, d)
        if d is None:
            moves["unassessable"] += 1
        else:
            dd = d - (p["dose_now"] or 0)
            moves["up" if dd > 0.05 else "down" if dd < -0.05 else "same"] += 1
            deltas[p["route"]].append(dd)
        totals.append(t - p["total"])
        cross += tier(t) != tier(p["total"])
    print(f"{label:28s} down {moves['down']:3d} up {moves['up']:3d} same {moves['same']:3d} unassessable {moves['unassessable']:2d} "
          f"| total mean {statistics.mean(totals):+.2f} | tier crossings {cross}")
    return deltas


print("\n== arms (all scored non-probiotic labels) ==")
for missing in "ABCR":
    for excess in ("E0", "E1", "E2"):
        summary(f"missing {missing} excess {excess}", missing=missing, excess=excess)
summary("missing R excess E0 L100", missing="R", excess="E0", legacy="L100")
summary("missing R excess E0 D23", missing="R", excess="E0", d23=True)

print("\n== by route, Dose change, missing A / B / C (excess E0) ==")
per = {m: summary(f"(route pass {m})", missing=m, excess="E0") for m in "ABCR"}
for route in sorted(per["B"]):
    row = [f"{route:18s} n={len(per['B'][route]):3d}"]
    for m in "ABCR":
        v = per[m][route]
        row.append(f"{m}: mean {statistics.mean(v):+.2f} [{min(v):+.1f},{max(v):+.1f}]" if v else f"{m}: -")
    print("  ".join(row))

print("\n== where a missing benchmark decides the result ==")
for p in scored:
    d, how = dose(p, missing="B")
    if how in ("nothing assessable", "rest only (main unassessable)", "main only (rest unassessable)") or \
            (how == "rest only" and False):
        a, _ = dose(p, missing="A"); c, _ = dose(p, missing="C"); r, _ = dose(p, missing="R")
        print(f"  {p['id']:>7} {p['name'][:38]:38s} {p['route'][:8]:8s} {how:30s} Dose now {p['dose_now']:5.1f} | "
              f"A {a if a is None else round(a,1)!s:>5} tot {total(p,a):5.1f} | B {d if d is None else round(d,1)!s:>5} tot {total(p,d):5.1f} | "
              f"C {c if c is None else round(c,1)!s:>5} tot {total(p,c):5.1f} | R {round(r,1)!s:>5} tot {total(p,r):5.1f} | today {p['total']}")
cov = Counter()
for p in scored:
    main = [i for i in p["items"] if i["group"] == "main"]
    na = sum(1 for i in main if i["state"] == "not_assessable")
    cov["no main rows" if not main else "main fully benchmarked" if not na else "main all unbenchmarked" if na == len(main) else "main partly unbenchmarked"] += 1
print("  main-group benchmark coverage:", dict(cov))

print("\n== excess: products with a row over its UL (missing R) ==")
for p in scored:
    if any((i.get("pct_ul") or 0) > 100 for i in p["items"]):
        vals = {e: dose(p, missing="R", excess=e)[0] for e in CAPS}
        rows = "; ".join(f"{i['name']} {i['pct_ul']:.0f}% UL" for i in p["items"] if (i.get("pct_ul") or 0) > 100)
        print(f"  {p['id']:>7} {p['name'][:34]:34s} Dose now {p['dose_now']:5.1f} | E0 {vals['E0']:5.1f} E1 {vals['E1']:5.1f} E2 {vals['E2']:5.1f} "
              f"| Safety now {p.get('safety_now')} | {rows[:80]}")

print("\n== legacy 25% reference on multi routes: L25 vs L100 ==")
dl = []
for p in scored:
    if p["route"] in {"multi_or_prenatal", "b_complex"}:
        a, _ = dose(p, missing="R", legacy="L25"); b, _ = dose(p, missing="R", legacy="L100")
        if a is not None and b is not None and abs(a - b) > 0.05:
            dl.append((b - a, p))
print(f"  {len(dl)} of {sum(1 for p in scored if p['route'] in {'multi_or_prenatal','b_complex'})} multi/B-complex labels move; "
      f"mean {statistics.mean(x for x, _ in dl):+.2f}, min {min(x for x, _ in dl):+.1f}")

AGREED = sys.argv[1].split(",") if len(sys.argv) > 1 else []
if AGREED:
    print("\n== agreed products (missing R, excess E0; B and E1 for comparison) ==")
    extra = [json.loads(l) for l in open("/Users/seancheick/pg_quality/rr_fix/v2agreed.jsonl")]
    byid = {p["id"]: p for p in P + extra}
    for pid in AGREED:
        p = byid.get(pid)
        if not p or p.get("skipped") or p.get("error"):
            print("  ", pid, p and (p.get("skipped") or p.get("error"))); continue
        d, how = dose(p, missing="R"); a, _ = dose(p, missing="B"); e1, _ = dose(p, missing="R", excess="E1")
        print(f"  {pid:>7} {p['name'][:40]:40s} Dose {p['dose_now']:5.1f} -> R {d if d is None else round(d,1)!s:>5} (B {a if a is None else round(a,1)!s}, E1 {e1 if e1 is None else round(e1,1)!s}) "
              f"total {p['total']} -> {total(p,d)} [{how}]")
        for i in p["items"]:
            print(f"        {i['group']:4s} {str(i['role']):15s} {i['state']:14s} {'' if i['credit'] is None else round(i['credit'],2)!s:5s} {i['name'][:34]:34s} {i['note'][:70]} {i.get('regroup') or ''}")
