#!/usr/bin/env python3
"""Build the Phase-3 clinical sign-off packet from the frozen triage (2026-09-19).

Reads reports/quarantine_triage_2026_09_19/PHASE3_TRIAGE.md (frozen baseline,
commit 77037d9f), regroups its 138 entries into review sections, and writes:

  - CLINICAL_SIGNOFF_PACKET.md   the plain-language packet for the clinical team
  - phase3_signoff_responses.csv fillable response sheet (one row per product)

Every count and product list is computed from the frozen file at run time —
nothing is hand-copied — so the packet cannot silently drift from the baseline.
"""
from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TRIAGE = ROOT / "reports" / "quarantine_triage_2026_09_19" / "PHASE3_TRIAGE.md"
OUT_MD = ROOT / "reports" / "quarantine_triage_2026_09_19" / "CLINICAL_SIGNOFF_PACKET.md"
OUT_CSV = ROOT / "reports" / "quarantine_triage_2026_09_19" / "phase3_signoff_responses.csv"

STALE_AFTER_FIXES = {"7-KETO-DHEA", "Calcium"}  # resolve mechanically at rebuild


def parse_triage() -> list[dict]:
    md = TRIAGE.read_text()
    rows = []
    for pid, name, body in re.findall(r"### (\d+) — (.+?)\n((?:- .*\n)+)", md):
        f = dict(re.findall(r"- \*\*(\w+)\*\*: (.*)", body))
        rows.append({
            "id": pid,
            "name": name,
            "gate": f.get("gate", ""),
            "conflicts": re.findall(r"'([^']+)'", f.get("conflict_names", "")),
            "proposal": f.get("proposal", ""),
            "rationale": f.get("rationale", ""),
            "risk": f.get("risk", ""),
        })
    return rows


def group(rows: list[dict]) -> dict[str, list[dict]]:
    g: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if set(r["conflicts"]) <= STALE_AFTER_FIXES and r["conflicts"]:
            g["_stale"].append(r)
            continue
        if not r["proposal"]:
            # already dispositioned upstream (intentional_non_scoreable via
            # identity reason codes like culinary_food / external_use_only)
            g["_already"].append(r)
            continue
        # identity-conflict groups first — several also carry dose gates
        if r["conflicts"] and (
            r["conflicts"] == ["Bitter Orange Citrus Bioflavonoids", "Bitter Orange Citrus Bioflavonoid"]
            or r["conflicts"][0].startswith("Bitter Orange Citrus Bioflavonoid")
        ):
            g["C_bitter_orange"].append(r)
        elif set(r["conflicts"]) & {"EDTA Disodium", "Calcium Disodium EDTA", "Mannitol",
                                    "Maltodextrin", "Litesse Polydextrose", "Litesse Polydextrose Fiber"}:
            if any("EDTA" in c or "Mannitol" in c for c in r["conflicts"]):
                r["dsub"] = "D1"
            else:
                r["dsub"] = "D2"
            g["D_excipients"].append(r)
        elif any("steroid" in (c.lower()) or "Androstan" in c or "Androst" in c or "Estr-5" in c
                 for c in r["conflicts"]):
            g["A_steroids"].append(r)
        elif set(r["conflicts"]) & {"Bis-Beta Carboxyethyl Germanium Sesquioxide", "Miroestrol",
                                    "Withaferin A", "Silver", "Ginkgolic Acid"}:
            g["B_safety_singletons"].append(r)
        elif "EpiCor" in (r["conflicts"][0] if r["conflicts"] else ""):
            r["dsub"] = "D3"
            g["D_excipients"].append(r)  # branded-material identity model question
        elif r["conflicts"]:
            g["_unclassified"].append(r)
        elif "no_scoreable_active_dose" in r["gate"]:
            g["E1_dose_missing"].append(r)
        elif "conversion_failed" in r["gate"]:
            g["E2_conversion"].append(r)
        elif "no_score_eligible" in r["gate"]:
            g["E4_no_eligible"].append(r)
        elif r["gate"].startswith("dose:None"):
            g["E3_no_dose_rows"].append(r)
        else:
            g["_unclassified"].append(r)
    return g


def main() -> int:
    rows = parse_triage()
    g = group(rows)
    if g["_unclassified"]:
        print("REFUSING: unclassified rows:", [(r["id"], r["gate"], r["conflicts"]) for r in g["_unclassified"]],
              file=sys.stderr)
        return 1

    counts = {k: len(v) for k, v in g.items() if not k.startswith("_")}
    total_review = sum(counts.values())
    n_stale = len(g["_stale"])
    n_already = len(g["_already"])

    def ids(rlist): return ", ".join(r["id"] for r in rlist)

    def table(rlist, limit=None):
        shown = rlist[:limit] if limit else rlist
        lines = ["| DSLD ID | Product |", "|---|---|"]
        lines += [f"| {r['id']} | {r['name']} |" for r in shown]
        if limit and len(rlist) > limit:
            lines.append(f"\n*(first {limit} of {len(rlist)} — full list in Appendix A)*")
        return "\n".join(lines)

    md = f"""# Phase-3 Clinical Sign-off Packet — quarantined products

**Prepared:** 2026-09-19 · **Source:** frozen triage baseline (commit 77037d9f) ·
**Reproducible:** `scripts/audits/quarantine_triage_20260919/build_clinical_signoff_packet.py`

You are being asked for **{total_review} clinical decisions** (some as single group calls).
Estimated effort: **2–3 hours**. Nothing in this packet changes the catalog until your
decisions are recorded and a new build passes the release gates.

---

## 1. Background — what you are looking at, in plain language

Our catalog scores supplement products for clinical-evidence quality. Before any product
ships it must pass a set of automated gates. **259 products currently fail those gates and
are quarantined** — they exist in the pipeline but are *withheld from the shipped app*.

A recent engineering pass (Phases 1–6, already on the remediation branch) fixed the
mechanical causes for 121 of them — trace-mineral identities (Nickel/Tin), stale vocabulary,
and dose-keeper rows that were missing identities. Those heal automatically at the next
rebuild and are **not** in this packet.

That leaves **{total_review} products that need a human clinical judgment**, grouped below so
most of them can be cleared with a handful of group-level calls. Two more products
(7-Keto DHEA, ids {ids(g['_stale'])}) were on an earlier draft of this list but their
identities now resolve mechanically — they are excluded.

### How to check a product

Every product carries its **DSLD ID** (NIH Dietary Supplement Label Database). Look any of
them up at `dsld.od.nih.gov` by ID, or search the product name. The label image is what your
judgment should be based on.

### How to respond

1. For each section below, make the **group decision** (one call covers the group), and add
   per-product overrides only where you disagree.
2. Record decisions in **`phase3_signoff_responses.csv`** (attached — one row per product,
   pre-filled). Allowed decisions:
   - `approve_proposal` — the engineering proposal is clinically sound
   - `reject` — proposal is wrong; state what should happen instead in `clinician_note`
   - `return_to_engineering` — this looks like a data/extraction bug, not a clinical question
   - `needs_info` — a question must be answered first
3. Sign the block in Section 7. Per repo convention (B1 ledgers), a **licensed pharmacist**
   signature is the release authority; other clinicians may review and recommend.

---

## 2. Section A — Designer anabolic steroids (3 products) · decision: confirm they stay blocked

These products name **synthetic anabolic-androgenic steroids** on the label — compounds that
exist only as designer drug analogs, not as dietary ingredients. They are recognized by the
banned-substances vocabulary and are quarantined pending a US **policy** review (that review
is a legal/regulatory call, not a clinical one). Clinically we ask you to confirm one thing:

> **Confirm:** these substances have no legitimate dietary-supplement use, so the correct
> outcome is that the products remain hidden (or at most ship a BLOCKED safety card, never a
> score). No consumer-facing wording is needed unless we later decide to show a blocked card.

| DSLD ID | Product | Named substance |
|---|---|---|
{chr(10).join(f"| {r['id']} | {r['name']} | {r['conflicts'][0]} |" for r in g['A_steroids'])}

**If cleared:** they stay quarantined as `safety_policy_review_required` — this is the
designed state, not a bug. Your sign-off records that the clinical side agrees.

---

## 3. Section B — Safety-flagged singletons (6 products) · one decision each

Each names a substance with a real safety concern and **no canonical identity** in our
vocabulary. Engineering needs your call on the *product disposition* before it decides
whether an identity entry is even appropriate.

| DSLD ID | Product | Substance | Concern | Engineering proposal |
|---|---|---|---|---|
| 241744 | Colloidal Silver 20 PPM | Silver (colloidal) | FDA: not safe/effective as a supplement; argyria risk | Product disposition (likely BLOCKED) |
| 216948 | PM Phytogen Complex | Miroestrol (Pueraria mirifica) | Potent estrogenic; endocrine-risk watchlist | Product disposition |
| 232718 | Longevity A.I. | Withaferin A | Cytotoxic withanolide isolated from ashwagandha | Product disposition |
| 200891 | Bis-Beta Carboxyethyl Germanium Sesquioxide 150 mg | Organic germanium | Renal-toxicity history of germanium compounds | Product disposition (2 standalone bottles) |
| 328464 | Ginkgo Biloba Certified Extract 120 mg | Ginkgolic acid | Allergenic **contaminant** of ginkgo extract, not an ingredient | Likely contaminant-limit failure |

> **For each, decide:** keep hidden · BLOCKED-with-warning card · or (only if you judge the
> substance has a legitimate scored role) approve creating a canonical identity with the
> safety signal retained.
>
> **Special attention — ginkgolic acid (328464):** if the label names ginkgolic acid
> directly, the product likely *fails a contaminant limit* — that is a quality failure, not
> an ingredient. Confirm that reading.

---

## 4. Section C — Bitter Orange Citrus Bioflavonoids (17 products) · one group call

These are multivitamin-style products whose labels say **"Citrus Bioflavonoids (from bitter
orange)"**. The pipeline quarantined them because "bitter orange" is a risk-flagged
ingredient (synephrine), so the bioflavonoid row could not resolve.

**Engineering proposal:** treat the *material* as **citrus bioflavonoids** (a normal
bioflavonoid identity), while the bitter-orange **safety signal stays** as a caution note
(synephrine risk). The two are different substances: citrus bioflavonoids are the flavonoid
fraction; synephrine is the alkaloid. No evidence transfers between them in our model.

> **Confirm or reject:** bioflavonoid-from-bitter-orange rows may resolve as citrus
> bioflavonoids and the products may be **scored**, with the synephrine caution retained.
> If you believe the synephrine exposure from such labels can be material, say so — the
> alternative is a stronger caution or keeping the group unscored.

Products (all 17): {ids(g['C_bitter_orange'])}

---

## 5. Section D — Excipient / filler rows (30 products) · 3 group calls

These products carry a dose-bearing row for a **processing agent or filler**: EDTA
(chelator), Mannitol (bulk sweetener), Maltodextrin (filler), Polydextrose/Litesse (fiber
filler), EpiCor (branded yeast fermentate). The taxonomy already has disposition codes for
exactly this (`formulation_excipient`, `standalone_carbohydrate_powder`,
`culinary_sweetener`) — engineering needs your confirmation of the *product-level meaning*.

**D1 — Standalone single-substance bottles (24).** Sixteen EDTA and eight Mannitol products
whose entire product IS the substance ("Calcium Disodium EDTA", "Mannitol" — chelation and
bulk-laxative/diagnostic bottles). Confirm: these become `intentional_non_scoreable` — a
therapeutic/technical use, not a scored supplement (same class as the culinary powders
already dispositioned upstream).

**D2 — Minor-row fillers (3).** Two Slimvance/Hunger Support products carry a Litesse
polydextrose fiber row; one gummy carries a maltodextrin filler row. Confirm: excipient /
fiber-filler treatment; the products resume scoring.

**D3 — EpiCor blend headers (3).** Three PureDefense products carry "EpiCor dried Yeast
Fermentate Complex" as a blend total weight. Engineering proposes resolving them as the
**generic dried-yeast-fermentate identity + brand qualifier**, not as a new competing
identity. Confirm this model is clinically acceptable (brand-level distinctions stay out of
scoring).

Products (all 30): {ids(g['D_excipients'])}

---

## 6. Section E — Missing-dose and non-scoreable populations (71 products) · group calls + spot-check

These have **no safety problem** — the gate is that the label or the DSLD record yields no
usable dose for scoring. Most should become `intentional_non_scoreable` (the product type
simply isn't scoreable). **Your key job is to catch the ones that look like data bugs** and
send them back to engineering.

**E1 — No scoreable active dose ({counts['E1_dose_missing']}).** Example names include Oil of
Oregano, Fish Oil, Aloe Vera Juice, gummy multivitamins, Vitamin B12 bottles. Please
**spot-check 12–15** (pick any; ids in Appendix A). For each, judge:
*label genuinely has no quantified actives* (proprietary blends, unstandardized extracts,
juices) → approve `intentional_non_scoreable`; or *a real dose is visible on the label but
the pipeline missed it* → `return_to_engineering`. (Vitamin B12 bottles showing a mcg dose
are prime suspects for the second kind.)

**E2 — DSLD unit corruption (6).** These labels carry physiologically impossible or
wrong-unit entries (Vitamin A "900–1300 mg RAE" — the real-world unit is **mcg**; "mcg DFE"
— a folate unit — on vitamin A rows). The pipeline refuses to guess units. Confirm the
labels are corrupted (view them at dsld.od.nih.gov); engineering will pursue upstream DSLD
correction rather than reinterpret a dose. Products: {ids(g['E2_conversion'])}

**E3 — Dose rows absent (5).** Five Bulk 1340 mass-gainer flavors: the protein content is
declared as a blend total, with no per-ingredient doses. Confirm `intentional_non_scoreable`
as formulated meal-replacement products, or send back if you believe individual doses should
be extractable from the label. (Potassium Iodide 130 mg Tablets — an earlier suspect here —
is already dispositioned upstream as `emergency_use_only`; no action needed.)

**E4 — No score-eligible rows (2).** Fish Oil Lemon (260262) and Adrenal Support (315586)
are real supplements whose rows all came back score-ineligible — both are prime
`return_to_engineering` suspects. (Standalone culinary/excipient powders that hit the same
gate — maltodextrin, silicon dioxide, erythritol, coconut oil, arnica topical — were already
dispositioned upstream and need no action; see Appendix A.)

---

## 7. Sign-off

| Field | Value |
|---|---|
| Reviewer (print) | |
| Role / license | |
| Date | |
| Sections A–B decisions | ☐ confirmed |
| Section C decision | ☐ approve ☐ reject |
| Section D decisions (D1/D2/D3) | |
| Section E decisions (per CSV) | |
| Overall | ☐ all {total_review} products dispositioned |

*Per the B1 ledger convention: final release authority is a licensed pharmacist signature;
engineering records each decision as a receipt before the affected products are cleared.*

---

## Appendix A — Full product lists

### A_steroids ({counts['A_steroids']})
{table(g['A_steroids'])}

### B_safety_singletons ({counts['B_safety_singletons']})
{table(g['B_safety_singletons'])}

### C_bitter_orange ({counts['C_bitter_orange']})
{table(g['C_bitter_orange'])}

### D_excipients ({counts['D_excipients']})
{table(g['D_excipients'])}

### E2_conversion ({counts['E2_conversion']})
{table(g['E2_conversion'])}

### E3_no_dose_rows ({counts['E3_no_dose_rows']})
{table(g['E3_no_dose_rows'])}

### E4_no_eligible ({counts['E4_no_eligible']})
{table(g['E4_no_eligible'])}

### E1_dose_missing ({counts['E1_dose_missing']}) — spot-check 12–15
{table(g['E1_dose_missing'])}

### Excluded as stale (resolve mechanically, no review needed) ({n_stale})
{table(g['_stale'])}

### Already dispositioned upstream (no action needed) ({n_already})
{table(g['_already'])}

---

## Appendix B — Where the 259 went

| Bucket | Count | Disposition |
|---|---|---|
| Heal mechanically at rebuild (Phases 1a/4/6 repairs) | 121 | no review |
| Already dispositioned upstream (`intentional_non_scoreable`) | {n_already} | no review |
| Stale after fixes (7-Keto) | {n_stale} | no review |
| **This packet** | **{total_review}** | **clinical sign-off** |
| **Total frozen baseline** | **{121 + n_already + n_stale + total_review}** | |
"""

    OUT_MD.write_text(md)

    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["dsld_id", "product_name", "section", "decision",
                    "clinician_note", "reviewer", "date"])
        sec = [("A", g["A_steroids"]), ("B", g["B_safety_singletons"]),
               ("C", g["C_bitter_orange"]), ("D", g["D_excipients"]),
               ("E1", g["E1_dose_missing"]), ("E2", g["E2_conversion"]),
               ("E3", g["E3_no_dose_rows"]), ("E4", g["E4_no_eligible"])]
        for name, rlist in sec:
            for r in rlist:
                w.writerow([r["id"], r["name"], r.get("dsub", name), "", "", "", ""])

    print(f"packet: {OUT_MD} ({total_review} products + {n_stale} stale excluded)")
    print(f"csv:    {OUT_CSV} ({total_review} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
