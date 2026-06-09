#!/usr/bin/env python3
"""Generate a per-cohort v4 score-quality review report (markdown).

Purpose: make the human cohort-review gate FAST. A clinician/reviewer eyeballs
each cohort's distribution + the top/bottom exemplars + brand patterns + the
extreme outliers, and judges "do these scores make sense for this category?".

Reusable: run against any v4 catalog build.
    python3 scripts/cohort_score_review.py [catalog.db] [-o report.md]
Defaults: scripts/dist/pharmaguide_core.db  ->  scripts/reports/v4_cohort_score_review.md
"""
import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone

TIERS = ["Elite", "Excellent", "Strong", "Acceptable", "Weak", "Poor"]


def pctile(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    i = max(0, min(len(s) - 1, int(round((p / 100) * (len(s) - 1)))))
    return s[i]


def fmt(x):
    return "—" if x is None else f"{x:.1f}"


def cohort_rows(conn, where, params=()):
    return conn.execute(
        f"SELECT brand_name, product_name, quality_score_v4_100 AS s, "
        f"quality_tier AS t, v4_module AS m FROM products_core "
        f"WHERE quality_score_status='scored' AND ({where})",
        params,
    ).fetchall()


def summarize(name, rows, suppressed=0):
    out = [f"### {name}  ·  n={len(rows)}" + (f"  ·  suppressed={suppressed}" if suppressed else "")]
    if not rows:
        out.append("\n_(no scored products in this cohort)_\n")
        return "\n".join(out)
    scores = [r["s"] for r in rows if r["s"] is not None]
    out.append(
        f"\n- **score**: min {fmt(min(scores))} · p25 {fmt(pctile(scores,25))} · "
        f"median {fmt(pctile(scores,50))} · p75 {fmt(pctile(scores,75))} · "
        f"max {fmt(max(scores))} · mean {fmt(sum(scores)/len(scores))}"
    )
    tc = {t: 0 for t in TIERS}
    for r in rows:
        if r["t"] in tc:
            tc[r["t"]] += 1
    n = len(rows)
    out.append("- **tiers**: " + " · ".join(f"{t} {tc[t]} ({100*tc[t]//n}%)" for t in TIERS if tc[t]))
    top = sorted(rows, key=lambda r: r["s"], reverse=True)[:8]
    bot = sorted(rows, key=lambda r: r["s"])[:8]
    out.append("\n| ▲ Highest | score | tier | | ▼ Lowest | score | tier |")
    out.append("|---|---|---|---|---|---|---|")
    for i in range(max(len(top), len(bot))):
        th = top[i] if i < len(top) else None
        bo = bot[i] if i < len(bot) else None
        def cell(r):
            if not r:
                return "| | | "
            label = f"{(r['brand_name'] or '?')[:18]} — {(r['product_name'] or '')[:30]}"
            return f"| {label} | {fmt(r['s'])} | {r['t'] or '—'} "
        out.append(cell(th) + "|" + cell(bo) + "|")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("db", nargs="?", default="scripts/dist/pharmaguide_core.db")
    ap.add_argument("-o", "--output", default="scripts/reports/v4_cohort_score_review.md")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    q = lambda s, p=(): conn.execute(s, p).fetchall()

    total = q("SELECT count(*) n FROM products_core")[0]["n"]
    scored = q("SELECT count(*) n FROM products_core WHERE quality_score_status='scored'")[0]["n"]
    supp = q("SELECT count(*) n FROM products_core WHERE quality_score_status='suppressed_safety'")[0]["n"]
    try:
        dbv = json.load(open(os.path.join(os.path.dirname(args.db), "export_manifest.json")))["db_version"]
    except Exception:
        dbv = "(unknown)"

    L = []
    L.append(f"# v4 Cohort Score Review — build `{dbv}`")
    L.append(f"\n_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} from `{args.db}`._")
    L.append(f"\n**{total} products** · {scored} scored · {supp} suppressed (banned/unsafe — score withheld by design).")
    L.append("\nReview question per cohort: _do the top exemplars deserve their high score, do the "
             "bottom ones deserve their low score, and do reputable brands land where you'd expect?_")

    # Overall tiers
    L.append("\n## 1. Overall tier distribution")
    L.append("\n| Tier | n | % of scored |\n|---|---|---|")
    for t in TIERS:
        n = q("SELECT count(*) n FROM products_core WHERE quality_score_status='scored' AND quality_tier=?", (t,))[0]["n"]
        L.append(f"| {t} | {n} | {100*n//max(scored,1)}% |")

    # By scoring module
    L.append("\n## 2. By scoring module (`v4_module` — the scoring path)")
    mods = [r["m"] for r in q("SELECT DISTINCT v4_module m FROM products_core WHERE quality_score_status='scored' AND v4_module IS NOT NULL ORDER BY 1")]
    for m in mods:
        L.append("\n" + summarize(f"module: `{m}`", cohort_rows(conn, "v4_module=?", (m,))))

    # By consumer category (the review list)
    L.append("\n## 3. By consumer category")
    cats = [
        ("Prenatal", "lower(product_name) LIKE '%prenatal%' OR lower(coalesce(supplement_type,'')) LIKE '%prenatal%'"),
        ("Omega-3 / fish oil", "contains_omega3=1 OR primary_category='omega_3'"),
        ("Probiotic", "is_probiotic=1 OR contains_probiotics=1 OR primary_category='probiotic'"),
        ("Sports / performance", "v4_module='sports' OR primary_category='protein_powder'"),
        ("Herbal / botanical", "primary_category='herbal_botanical'"),
        ("Collagen", "contains_collagen=1"),
        ("Multivitamin", "primary_category='multivitamin'"),
    ]
    for label, where in cats:
        s = q(f"SELECT count(*) n FROM products_core WHERE quality_score_status='suppressed_safety' AND ({where})")[0]["n"]
        L.append("\n" + summarize(label, cohort_rows(conn, where), s))

    # By brand
    L.append("\n## 4. By brand")
    L.append("\n| Brand | n | mean | median | %Elite+Excellent | %Poor |\n|---|---|---|---|---|---|")
    brands = q("SELECT brand_name b, count(*) n FROM products_core WHERE quality_score_status='scored' AND brand_name IS NOT NULL GROUP BY 1 HAVING n>=10 ORDER BY n DESC LIMIT 40")
    for br in brands:
        rows = cohort_rows(conn, "brand_name=?", (br["b"],))
        scores = [r["s"] for r in rows]
        hi = sum(1 for r in rows if r["t"] in ("Elite", "Excellent"))
        po = sum(1 for r in rows if r["t"] == "Poor")
        L.append(f"| {br['b'][:28]} | {len(rows)} | {fmt(sum(scores)/len(scores))} | "
                 f"{fmt(pctile(scores,50))} | {100*hi//len(rows)}% | {100*po//len(rows)}% |")

    # Outliers to spot-check
    L.append("\n## 5. Outliers to spot-check (does the extreme make sense?)")
    L.append("\n**Top 15 overall (Elite — confirm they earn it):**\n")
    L.append("| Brand | Product | score | module |\n|---|---|---|---|")
    for r in q("SELECT brand_name b, product_name p, quality_score_v4_100 s, v4_module m FROM products_core WHERE quality_score_status='scored' ORDER BY s DESC LIMIT 15"):
        L.append(f"| {(r['b'] or '?')[:22]} | {(r['p'] or '')[:40]} | {fmt(r['s'])} | {r['m']} |")
    L.append("\n**Bottom 15 overall (confirm they deserve it):**\n")
    L.append("| Brand | Product | score | module |\n|---|---|---|---|")
    for r in q("SELECT brand_name b, product_name p, quality_score_v4_100 s, v4_module m FROM products_core WHERE quality_score_status='scored' ORDER BY s ASC LIMIT 15"):
        L.append(f"| {(r['b'] or '?')[:22]} | {(r['p'] or '')[:40]} | {fmt(r['s'])} | {r['m']} |")
    L.append("\n**Suppressed (banned/unsafe — score withheld; confirm each is genuinely unsafe):**\n")
    L.append("| Brand | Product | reason | verdict |\n|---|---|---|---|")
    for r in q("SELECT brand_name b, product_name p, quality_score_suppressed_reason rs, verdict v FROM products_core WHERE quality_score_status='suppressed_safety' ORDER BY brand_name LIMIT 40"):
        L.append(f"| {(r['b'] or '?')[:22]} | {(r['p'] or '')[:40]} | {r['rs'] or '—'} | {r['v']} |")

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"wrote {args.output} ({scored} scored, {supp} suppressed, {len(mods)} modules)")


if __name__ == "__main__":
    main()
