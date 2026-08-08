"""ONE markdown file per reviewer. Fill in the blanks, email it back.

Replaces the 4-file packet (brief + HTML + CSV + brand list). The CSV was the
defect: it asked a clinician to hand-sum six columns 120 times, and the first
returned sheet failed arithmetic on 38% of rows with a uniform +10 offset --
the quality-checks column silently dropped from the sum. It also carried an
invalid reviewer_slot, breaking the join the CSV existed to guarantee.

So: the reviewer never computes a total and never touches an ID. They write six
numbers and a few words. parse_review_doc.py does the arithmetic, restores the
frozen column contract, and reports anything missing.

Reads only the two blinded artifacts a reviewer may receive. Never opens either
baseline key. Emits no engine score, threshold, or split assignment.

Usage: python3 build_review_doc.py --slot 1 --reviewer-id KEVIN --out DIR
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS_DIR))

from serving_frequency import resolve_daily_serving_range  # noqa: E402

FREEZE = (Path(__file__).resolve().parents[2]
          / "reports" / "v4_reviewer_benchmark_2026_08_06_v6")

# Median amount implying 100% DV per ingredient|unit, derived from all 13,271
# shipped blobs (>=8 observations each). Used ONLY to flag internally
# contradictory rows -- e.g. zinc 90 mg declared as 100% DV, 8x the catalog's
# own 11 mg. It encodes no scoring policy and reveals nothing about the engine.
DV_REF = json.loads((Path(__file__).parent / "dv_reference.json").read_text())

HEADER = """# Supplement label review — {rid}

You need nothing except this file. Fill in the blanks under each product and
email the file back. **Please don't retype or reformat anything else.**

## What we're asking

We built software that scores supplement labels for quality. Before we trust
it, we want to know whether it agrees with a pharmacist reading the same label.
You score them blind; we compare afterwards. **We are not asking you to endorse
any product**, or to judge it for a particular patient.

## Three rules

1. **Don't look up what PharmaGuide says** about these products — app, website,
   or repository. Your independence is the whole point.
2. **If you accidentally see one of our scores, say so** in that product's
   `ODD:` line. It's not harmless — we drop that product — but not knowing is
   far worse.
3. **Don't compare notes** with the other reviewers until everyone's file is in.

## For each product

Read the label facts, then **verify the material dose, evidence, safety and
certification claims against primary or official sources** — PubMed, NIH ODS,
FDA, USP/NSF. That checking is the task; scoring off the label alone isn't.
List what you used on the `SOURCES:` line.

Then fill in the block. **Whole or half points only** (12, 12.5, 13).

| Line | Range | The question |
|---|---:|---|
| `FORMULATION` | 0–20 | Are the ingredient forms and formulation choices appropriate? 0 = materially poor · 10 = mixed/uncertain · 20 = consistently strong |
| `DOSE` | 0–20 | Are the daily doses plausibly effective without material excess? 0 = unusable or unsafe · 10 = partial/uncertain · 20 = well supported |
| `EVIDENCE` | 0–20 | Does human research support these actives, forms, doses **and intended use**? 0 = none comparable · 10 = limited/mixed · 20 = strong and directly comparable |
| `TRANSPARENCY` | 0–15 | Does the label disclose **identities, amounts, serving basis and blends**? 0 = materially opaque · 7.5 = partial · 15 = complete |
| `VERIFICATION` | 0–15 | Is there **product-specific** independent testing? 0 = contrary evidence · 7.5 = partial/mixed · 15 = strong product-specific proof. A certification named on the label is a *claim* — the question is whether the exact product appears in the certifier's own records. Brand- or facility-level claims are not product-specific. **If you cannot establish anything either way, enter 7.5** (our defined neutral) **and write `Verification 7.5 = neutral, nothing establishable` in `WHY:`** so we can tell that apart from a real partial-verification 7.5. |
| `QUALITY` | 0–10 | **Catalog/product-level** signals only: recalls, contamination, adulteration, substantiated manufacturing-quality problems, or material additive concerns. 0 = severe known concern · 5 = material caution/uncertainty · 10 = none known. **Ordinary dose-related risk belongs in DOSE and SAFETY — don't penalise the same ingredient a third time here.** |

**Don't add them up — we do that.**

`SAFETY:` is judged separately from quality. One of:

- `blocked` — safe use depends on a missing prerequisite (e.g. butterbur with no
  PA-free processing stated)
- `unsafe` — the labeled regimen itself creates a serious, established concern
- `caution` — elevated dose, uncertain long-term safety, or a narrower safety
  margin, without a clear expectation of serious harm
- `no_known_concern` — nothing known after you looked
- `not_assessed` — you genuinely couldn't judge

For `blocked`/`unsafe`/`caution`, name the substance or dose on the `DRIVER:`
line and cite it. **Under-warning is the worse error** — if torn, flag it.

**Exceeding a UL is not automatically `unsafe`.** A Tolerable Upper Intake Level
is a population risk threshold, not the dose where toxicity begins. Passing one
generally supports a dose penalty and often `caution`; reserve `unsafe` for a
labeled regimen posing a serious, reasonably established risk at that actual
dose, form and duration. Form matters — a total with the form unspecified
shouldn't mechanically become `unsafe`.

`CONFIDENCE:` `high` / `moderate` / `low`  ·  `LABEL ENOUGH?:` `yes` / `no`

`SOURCES:` semicolon-separated, each a PMID, DOI or official URL —
`PMID 12345678; https://ods.od.nih.gov/factsheets/Zinc-HealthProfessional/`.
Please prefer primary literature and official bodies (PubMed, NIH ODS, FDA,
NCCIH, USP/NSF) over consumer health sites.

**Evidence cutoff: assess information publicly available as of the date this
file was sent.** Certification directories and recall notices change; we need
all three reviewers judging the same world.

`ODD:` leave as `none` unless something compromised the *rating* — you saw a
score, found a conflict, or couldn't reach a source. **Our data defects don't
go here** (see below) — put those in `LABEL ENOUGH?: no`.

## Scope

Product-level, not personalised. Consider drug/condition interactions only where
they make the *product* a concern. Please don't score down for a personalised
interaction — that's handled elsewhere and wasn't asked of the software either.

Don't treat a missing fact as good or bad. If a label doesn't state third-party
testing, that's neither proof it happened nor that it didn't — put the
uncertainty in the score and lower your confidence.

**Totals and the rows printed underneath them.** Where the label itself prints
rows *underneath* an ingredient — its chemical forms, or the components of a
named blend — **the first amount is the total; do not add those rows to it.**
Example: `Magnesium 135 mg` printed above `55 mg` and `80 mg` of two magnesium
forms is 135 mg per serving, not 270 mg. Affected products carry a
`⚠ DATA NOTE` **naming the exact rows** we mean. Where you see no such note,
treat every row as its own separate ingredient and add them up normally —
several ingredients whose amounts happen to sum to another are not related.

## Our known data gaps — not your problem, don't report them

Our extraction is imperfect. Where a product is affected you'll see a
**`⚠ DATA NOTE`** right in its block. Across your {n} products: **{zero} have an
ingredient quantity of 0**, **{nounit} have an ingredient with no unit**, and
**{serving_untrusted} have a serving frequency whose provenance is not
trustworthy enough to use**.

For any of these: set `LABEL ENOUGH?: no`, mention it in `WHY:` if you like, and
move on. **Don't put them in `ODD:`** — that field excludes the product from the
analysis, and these are our defects, not protocol breaches.

**Which serving to dose against:** normally the **maximum** labeled daily
serving. For products whose frequency is flagged as untrusted, verify the
directions yourself; if you cannot, assume 1 serving per day and set confidence
`low`.

## Conflicts of interest

The {brands} brands in this set are listed at the end. If you have a financial,
employment, consulting or research relationship with any of them, you can't
review this set — it's all-or-nothing, since all reviewers rate all products.

## Time

This is {n} products with source checking. Realistically **10+ hours.** Work in
batches over several days — that's fine. **If that's too much, tell us before
you start**, not partway through; a smaller set means formally re-cutting the
study, which is a fine outcome but has to be decided up front.

If a product is genuinely unratable, still give six numbers — score what the
label supports, then set `CONFIDENCE: low`, `LABEL ENOUGH?: no` and
`SAFETY: not_assessed`. **Please don't leave any score blank**; a blank drops
that product for all three reviewers.

## Sending it back

Email this same file, filled in. Return to: `_______________`
By: `_______________`

Ask us anything about the process. The one thing we can't tell you is what our
software scored a product — that's the thing your review is testing.

---
"""

BLOCK = """
## {n}. {name}

**Brand:** {brand}
{facts}{notes}
```
ID: {bid}
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---
"""


def jload(raw, d):
    try:
        v = json.loads(raw) if raw else d
        return d if v is None else v
    except Exception:
        return d


def amt(a, u):
    if a in (None, "", "null"):
        return "amount NOT disclosed"
    u = (u or "").strip()
    return f"{a} {'unit not stated' if u in ('NP', 'unspecified', '') else u}"


def rollup(act):
    """Render the total-vs-forms relationship the freeze already resolved.

    This does NOT decide which rows are constituent forms of which -- that is
    settled once, from the label's own row nesting, by
    `v4_reviewer_benchmark_freeze._resolve_constituent_rollups`. Deciding it a
    second time here is what produced the defect: this file used to infer the
    relationship from arithmetic alone ("do the next 2-3 amounts add up to this
    one?"), with no identity signal whatsoever. On the shipped corpus that fired
    on 806 products, 79% of them chemically unrelated -- `Leucine 3000 ==
    Isoleucine 1500 + Valine 1500` (three separate BCAAs, and the
    industry-standard 2:1:1 ratio *guarantees* the sum matches), `GABA 200 ==
    Theanine 100 + Rhodiola 100`, `Folate 400mcg == B12 50mcg + Biotin 300mcg +
    Pantothenic Acid 50mg`.

    Fails closed: a packet frozen without the resolved relationship yields no
    note. A missing note costs the reviewer nothing (they read the rows as
    printed); a wrong one tells a pharmacist to score against half the dose.
    """
    for a in act:
        kids = a.get("constituent_child_indexes")
        if not kids:
            continue
        if any(not isinstance(i, int) or not 0 <= i < len(act) for i in kids):
            continue
        return a, [act[i] for i in kids]
    return None


def facts(row):
    L, notes = [], []
    s = jload(row.get("serving_info_json"), {})
    mn, mx = s.get("min_servings_per_day"), s.get("max_servings_per_day")
    if mn is not None or mx is not None:
        resolved_min, resolved_max, defaulted = resolve_daily_serving_range(
            {"serving_info": s}
        )
        cl = lambda v: None if v is None else (int(v) if float(v) == int(float(v)) else round(float(v), 3))
        a, b = cl(resolved_min), cl(resolved_max)
        if defaulted:
            notes.append(
                "servings-per-day provenance is not trustworthy — verify the labeled directions"
            )
        L.append(f"**Servings/day:** {a if a == b else f'{a}–{b}'}")

    act = jload(row.get("active_ingredients_json"), [])
    for a in act:
        q, dv = a.get("quantity"), a.get("daily_value_percent")
        u = (a.get("unit") or "").strip().lower()
        key = f"{(a.get('name') or '').strip().lower()}|{u}"
        if key in DV_REF and isinstance(q, (int, float)) and isinstance(dv, (int, float)) \
                and q > 0 and dv > 0:
            ratio = (q / (dv / 100.0)) / DV_REF[key]
            if ratio > 3 or ratio < 1 / 3:
                notes.append(f"**{a.get('name')} {q} {a.get('unit')} shown as {dv}% DV is "
                             f"internally inconsistent** (~{ratio:.0f}x off the usual "
                             "amount for that %DV) — one of the two figures is our "
                             "extraction error. Judge on whichever you find credible and "
                             "say which in `WHY:`")
    z = sum(1 for a in act if a.get("quantity") in (0, 0.0, "0"))
    nu = sum(1 for a in act if (a.get("unit") or "").strip() in ("NP", "unspecified", ""))
    if z:
        notes.append(f"{z} ingredient(s) show quantity 0 — our extraction gap, treat as undisclosed")
    if nu:
        notes.append(f"{nu} ingredient(s) have no unit — our extraction gap, treat as undisclosed")
    roll = rollup(act)
    if roll:
        parent, kids = roll
        forms = ", ".join(f"{k.get('name')} {k.get('quantity')}" for k in kids)
        # "already included in" rather than "are forms of": ~20 of these are a
        # blend total over its components (Turmeric Blend = turmeric + ginger +
        # black pepper), not one substance broken into its forms. The dose
        # instruction is identical either way; the chemical claim is not.
        notes.append(f"**{parent.get('name')} {parent.get('quantity')} "
                     f"{parent.get('unit')}** is the TOTAL, and the rows the label "
                     f"nests under it ({forms}) are already included in that total. "
                     "Do NOT add them to it")
    L.append("\n**Actives:**")
    L += [f"- {a.get('name')} — {amt(a.get('quantity'), a.get('unit'))}"
          + (f" ({a['daily_value_percent']}% DV)" if a.get("daily_value_percent") not in (None, "") else "")
          for a in act] or ["- none listed with an amount"]

    for b in (jload(row.get("proprietary_blend_facts_json"), {}) or {}).get("blends") or []:
        L.append(f"\n**Blend — {b.get('name') or 'unnamed'}** (total: "
                 f"{amt(b.get('amount') or b.get('total_amount'), b.get('unit') or b.get('total_unit'))})")
        L += [f"- {c.get('name')} — {amt(c.get('amount'), c.get('unit'))}"
              for c in (b.get("child_ingredients") or [])]

    ina = jload(row.get("inactive_ingredients_json"), [])
    L.append("\n**Other ingredients:** " + (", ".join(map(str, ina)) if ina else "none listed"))

    c = jload(row.get("certification_facts_json"), {})
    g = c.get("gmp") or {}
    claims = [n for n, v in (("GMP certified/compliant", g.get("gmp_certified_or_compliant")),
                             ("FDA-registered facility", g.get("fda_registered")),
                             ("NSF GMP", g.get("nsf_gmp")),
                             ("heavy-metal tested", c.get("heavy_metal_tested")),
                             ("purity verified", c.get("purity_verified")),
                             ("label accuracy verified", c.get("label_accuracy_verified"))) if v]
    # NAME ONLY. These are dicts carrying our own {"verified": true} verdict;
    # str(dict) leaked it into 20 blinded blocks and pre-answered the exact
    # pillar the reviewer is meant to judge independently.
    tp = [(t.get("name") if isinstance(t, dict) else t) for t in (c.get("third_party_programs") or [])]
    tp = [str(t) for t in tp if t]
    L.append("\n**Quality claims stated on the label:** "
             + (", ".join(claims + tp) if (claims or tp)
                else "none stated (not evidence testing didn't happen)"))
    L.append("*(These are label claims only. Whether the exact product appears in "
             "the certifier's own records is yours to establish.)*")
    return "\n".join(L), notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", required=True)
    ap.add_argument("--reviewer-id", required=True)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    packet = {r["benchmark_id"]: r for r in csv.DictReader((FREEZE / "reviewer_packet.csv").open())}
    resp = sorted((r for r in csv.DictReader((FREEZE / "reviewer_response_template.csv").open())
                   if r["reviewer_slot"] == a.slot), key=lambda r: int(r["reviewer_order"]))
    assert len(resp) == 120, len(resp)

    blocks, st = [], {"zero": 0, "nounit": 0, "serving_untrusted": 0}
    rollups = 0
    for i, r in enumerate(resp, 1):
        row = packet[r["benchmark_id"]]
        f, notes = facts(row)
        for n in notes:
            if "quantity 0" in n:
                st["zero"] += 1
            elif "no unit" in n:
                st["nounit"] += 1
            elif "servings-per-day provenance" in n:
                st["serving_untrusted"] += 1
            elif "is the TOTAL" in n:
                rollups += 1
        nt = ("\n\n> **⚠ DATA NOTE** — " + "; ".join(notes)) if notes else ""
        blocks.append(BLOCK.format(n=i, name=row["product_name"], brand=row["brand_name"],
                                   facts=f, notes=nt, bid=r["benchmark_id"]))

    brands = sorted({packet[r["benchmark_id"]]["brand_name"] for r in resp})
    doc = HEADER.format(rid=a.reviewer_id, n=len(resp), brands=len(brands), **st) \
        + "".join(blocks) \
        + "\n# Brands in this set (conflict check)\n\n" \
        + "\n".join(f"- {b}" for b in brands) + "\n"
    out = a.out / f"REVIEW_{a.reviewer_id}.md"
    out.write_text(doc)
    (a.out / f".slotmap_{a.reviewer_id}.json").write_text(json.dumps(
        {"slot": a.slot, "reviewer_id": a.reviewer_id,
         "order": {r["benchmark_id"]: r["reviewer_order"] for r in resp}}, indent=1))
    # A packet frozen before `parent_index` existed carries no nesting evidence,
    # so total-vs-forms notes correctly drop to 0. Print it rather than let a
    # silent zero read as "no such products in this slot".
    print(f"{out}  ({len(resp)} products, {len(doc)//1024} KB, data notes: {st}, "
          f"total-vs-forms: {rollups})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
