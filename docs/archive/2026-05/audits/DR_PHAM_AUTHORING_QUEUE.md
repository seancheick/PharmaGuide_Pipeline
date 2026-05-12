# Dr Pham — Sprint E1 Authoring Queue

> **What this is:** the four pieces of writing we need from you before we can ship Sprint E1 to the app. Everything here is net-new — not a redo of what you've already done.
> **When you need it by:** end of Sprint E1 (~2 weeks from 2026-04-21). You're at the end, so the pipeline team will build everything else first. You can start whenever.
> **Format:** for each task below, there's a spreadsheet/JSON file ready for you to fill in. We'll send it when pipeline is ready.

---

## Task 1 — Banned substance "stack-add" warning copy (~143 entries)

### The problem
Today, when a user scans a product and the app detects a banned ingredient (like CBD or ephedra), the app's "Add to my stack" button has no warning. It just adds it. We need a safety speed-bump — a red banner that says "wait, this is banned, are you sure?"

### What you write
**Two short lines for each of the ~143 banned ingredients** in `banned_recalled_ingredients.json`.

| Field | What it is | Limit | Example (for CBD) |
|---|---|---|---|
| **One-liner** | The red banner title | ≤ 80 chars | "Contains cannabidiol — not a lawful US dietary supplement ingredient." |
| **Body** | Short explanation under the banner | ≤ 200 chars | "FDA has not approved CBD as a dietary supplement. May interact with liver enzymes and prescription medications. Consult your doctor." |

### Rules
- Plain language. No jargon. Written for a patient, not a pharmacist.
- Action-framed ("Talk to your doctor" is better than "Hepatic metabolism concern").
- No clinical hedging ("may possibly theoretically" — just say it).
- Cite the regulatory reason in the body if you can (FDA, DEA, EU ban, etc.).

### Good vs bad
❌ Bad: `"Hepatic cytochrome P450 induction observed in in-vitro studies."` (jargon)
❌ Bad: `"This product may not be safe."` (vague)
✅ Good: `"Banned by FDA in 2004. Caused heart attacks and strokes in young adults. Do not use."`

### What happens after you write
- Engineering adds these two fields to the data file
- A build-time check fails if any banned ingredient is missing the copy
- The Flutter app shows the red banner when a user tries to stack a banned product

---

## Task 2 — Rewrite condition-specific warnings to "talks to everyone" (expected < 50 entries)

### The problem
Today, some warnings say things like `"Not recommended during pregnancy"` but the app is showing them to everyone — including men. That's noise. The user learns to ignore warnings.

Two paths to fix it. You pick (or help us pick) which.

### Path A (preferred) — rewrite the copy to talk to everyone
Reword the warning so it's safe to show to any user:

❌ Before: `"Not recommended during pregnancy."` (shown to men → noise)
✅ After: `"May affect pregnancy — talk to your doctor if pregnant or planning to become pregnant."` (safe to show everyone)

You rewrite maybe 30–50 of these. We'll send you the list after engineering identifies them.

### Path B — leave the copy alone, let the app filter
Keep the specific wording but change the warning's flag from `critical` (always show) to `suppress` (only show if user's profile matches).

This is quicker but relies on users filling in their profile (pregnancy, liver disease, etc.). Many don't.

### Our recommendation
**Path A for anything truly dangerous** (liver disease warnings, bleeding disorders, etc. — things you'd want anyone to pause on).
**Path B for lifestyle-specific things** (pregnancy-only, children-only, elderly-specific).

You decide per-warning. We'll give you the list with a dropdown for A vs B.

---

## Task 3 — Fill in missing warning copy (count TBD, probably a few dozen)

### The problem
Some warnings in the app currently show as blank — or worse, show the raw code like `"ban_ingredient"` as the warning title. That's because somewhere along the way, the authored copy got skipped.

### What we'll do
Engineering will run a validator that lists every warning with empty copy. That becomes your authoring queue.

### What you write
For each missing warning, fill in whichever copy fields apply (same format as what you did for banned_recalled last time):

- **`safety_warning_one_liner`** — short alert title (≤ 80 chars)
- **`safety_warning`** — full detail (≤ 300 chars)
- **`alert_headline`** — alternative headline field (some warning types use this instead)
- **`alert_body`** — alternative body field

You only fill the ones that apply to the warning type. Engineering will label each row in the queue with which fields are needed.

### Rules
Same as Task 1 — plain language, action-framed, no jargon.

---

## Task 4 — Approve probiotic dose thresholds (one-time decision, ~20 strains)

### The problem
Probiotics are measured in **CFU** (colony forming units — how many live bugs per dose). Today our scorer doesn't know what's a "good" dose vs a "low" dose for each strain. We need thresholds.

### What you approve
A table like this (engineering drafts a starter version; you review + sign off):

| Strain | Low | Adequate | Good | Excellent | Source |
|---|---|---|---|---|---|
| Lactobacillus acidophilus | < 1B CFU | 1–5B | 5–10B | > 10B | (clinical trial citation) |
| Bifidobacterium lactis BB-12 | < 1B | 1–10B | 10–20B | > 20B | (citation) |
| Saccharomyces boulardii | < 2.5B | 2.5–5B | 5–10B | > 10B | (citation) |
| ... (~20 top strains in our catalog) | | | | | |

### What we need from you
1. For each of the ~20 strains we list: **confirm the threshold ranges** or adjust them.
2. **Cite the clinical source** for each (PMID, NCCIH, or manufacturer clinical-dose studies — whatever you trust).
3. Flag any strain you don't have strong evidence for — we'll mark it "evidence_weak" and the app won't score it.

### Rules
Same rigor as `backed_clinical_studies.json`. No thresholds without evidence. Better to leave a strain unscored than to guess.

### What happens after you approve
- 194 probiotic products currently scoring 0 on "Ingredient Quality" will finally get scored
- Users see a meaningful score instead of a misleading zero

---

## Summary — your four inboxes

| # | Task | What you write | Volume | When |
|---|---|---|---|---|
| 1 | Banned-substance stack-add warning | 2 short lines per entry | ~143 entries × 2 lines = ~286 short strings | End of Sprint E1 |
| 2 | Rewrite condition-specific warnings | Pick Path A/B per warning, rewrite if A | < 50 rewrites | End of Sprint E1 |
| 3 | Fill in missing warning copy | 1–4 fields per warning | A few dozen (exact count TBD) | End of Sprint E1 |
| 4 | Approve probiotic dose thresholds | Review + confirm table + add citations | ~20 strains, one-time | End of Sprint E1 |

Total estimated writing time: **~1–2 working days** spread across the 2-week sprint window. You set the pace.

---

## What you're NOT being asked to do

Just to be clear — we're NOT asking you to:

- ❌ Redo the safety_warning / safety_warning_one_liner copy you already wrote for the 2,413 banned entries (that work is shipped and live)
- ❌ Rewrite the harmful_additive Dr Pham fields (mechanism_of_harm, population_warnings — all shipped)
- ❌ Re-author the alert_headline / alert_body fields for interactions (all shipped)
- ❌ Do any scoring-model work. That's engineering.
- ❌ Touch any code. Engineering handles that.

Your scope = authoring safety-copy + approving clinical thresholds. Same role as Sprint D.

---

## Questions?

Engineering will send you:
- Task 1: a CSV with 143 rows, two empty columns for you to fill
- Task 2: a CSV with ~50 rows, each with the current warning + a dropdown for Path A/B + a column for rewritten copy
- Task 3: a CSV generated by the validator — content TBD
- Task 4: a draft threshold table with citations in markdown

All four will land in your inbox once the pipeline work they depend on is ready (probably mid-sprint, around Day 7).

If any of the rules above don't make sense or you'd change the approach — flag it before you start writing. Cheaper to adjust the spec than redo the copy.

---

## Post-delivery async follow-up queue (added 2026-04-21 after verification) — ✅ COMPLETE

Dr Pham's main 4 tasks are DELIVERED. Post-delivery async items were also completed same-day (2026-04-21). See "Resolution" column below — all 13 decisions executed + API-verified + committed. **42/42 strains now signed off.**

### FU-1 — Re-confirm or re-classify 3 "strong" strains with unusual evidence type ✅ RESOLVED 2026-04-21

Dr Pham's verdict: **downgrade all three.**

| Strain | PMID | Was | Now | Resolution |
|---|---|---|---|---|
| Bacillus clausii | 36018495 | strong (narrative_review) | **medium / moderate** | Dr Pham: downgrade. Narrative review evidence type doesn't support strong classification. |
| Lactobacillus paracasei 8700:2 | 36741903 | strong (animal_model) | **weak / weak** | Dr Pham: downgrade. Animal-model evidence type doesn't support strong classification. |
| Lactobacillus paracasei L.CASEI 431 | 25926507 | strong (animal_model) | **weak / weak** | Dr Pham: downgrade. Animal-model evidence type doesn't support strong classification. |

All three retain `dr_pham_signoff: true` (she reconfirmed authorship while adjusting classification). Prior classifications preserved at `evidence.previous_evidence_strength` / `evidence.previous_clinical_support_level` for audit.

### FU-2 — Find better citations for 2 medium strains ✅ RESOLVED 2026-04-21

| Strain | Old PMID | New PMID | Resolution |
|---|---|---|---|
| Lactobacillus paracasei Lpc-37 | 39842252 | **33385020** | Dr Pham's pick. *Neurobiology of Stress* (2020), the Sisu Study — strain-specific clinical evidence. Evidence upgraded medium / moderate. API-verified by agent. |
| Escherichia coli Nissle 1917 | 35701435 | **15479682** | Dr Pham's pick. Kruis et al., *Gut* (2004) — the gold-standard RCT comparing Nissle 1917 vs. mesalazine for UC maintenance (n=327, multicenter, double-blind). Evidence upgraded **strong / high**. API-verified by agent. |

Both flipped `dr_pham_signoff: true`. Prior citations preserved at `evidence.previous_citation` for audit.

### FU-3 — 8 weak strains — Dr Pham verdict: "weak is honest across the board" ✅ RESOLVED 2026-04-21

All 8 flipped `dr_pham_signoff: true` with `clinical_support_level: weak` honest tag. Scorer caps their contribution at 50% per E1.3.2 tier rules.

| Strain | PMID | Confirmed weak |
|---|---|---|
| Lactobacillus acidophilus NCFM | 24717228 | ✅ |
| Bacillus subtilis DE111 | 39631408 | ✅ |
| Bifidobacterium lactis Bl-04 | 38665561 | ✅ |
| Lactobacillus fermentum ME-3 | 36644601 | ✅ |
| Bifidobacterium longum 1714 | 41607522 | ✅ |
| Lactobacillus acidophilus DDS-1 | 32019158 | ✅ |
| Bifidobacterium lactis UABla-12 | 32019158 | ✅ |
| Bifidobacterium breve M-16V | 40085083 | ✅ |

### Final sign-off state (post Dr Pham's FU-1/2/3 resolution)

- **42/42 strains signed off** (`dr_pham_signoff: true`)
- All 42 PMIDs API-verified — zero hallucinated citations
- 2 upgrades (Lpc-37 weak→medium, Nissle 1917 medium→strong)
- 3 downgrades (Clausii strong→medium, 2× L. paracasei strong→weak)
- 8 weak confirmations with scorer-enforced 50% cap
- Metadata: `clinically_relevant_strains.json` v2.2.4 → v2.2.5
