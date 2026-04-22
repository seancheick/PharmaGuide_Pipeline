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

## Post-delivery async follow-up queue (added 2026-04-21 after verification)

Dr Pham's main 4 tasks are DELIVERED. These are **small async items** surfaced during the agent verification + clinical-reviewer pass. No rush — can be batched during any future touch of the data file.

### FU-1 — Re-confirm or re-classify 3 "strong" strains with unusual evidence type

Three strains currently tagged `evidence_strength: "strong"` but with evidence types that typically don't support a strong classification. Flipped to `dr_pham_signoff: true` on your prior authority; flagging so you can confirm or downgrade on next review.

| Strain | PMID | Evidence Type | Current Tag | Your Call |
|---|---|---|---|---|
| Bacillus clausii | 36018495 | narrative_review | strong | Confirm or downgrade to medium? |
| Lactobacillus paracasei 8700:2 | 36741903 | animal_model | strong | Confirm or downgrade to weak? |
| Lactobacillus paracasei L.CASEI 431 | 25926507 | animal_model | strong | Confirm or downgrade to weak? |

**Effort:** ~5 min — just reply with "keep" or "downgrade" per strain.

### FU-2 — Find better citations for 2 medium strains

Two medium-tier strains failed strict clinical validation and should have their PMIDs swapped:

| Strain | Current PMID | Problem | Recommended Action |
|---|---|---|---|
| Lactobacillus paracasei Lpc-37 | 39842252 | Abstract doesn't name the strain specifically. RCT is legitimate but strain attribution unverifiable from abstract; study endpoint (anxiety/depression) doesn't match claimed indication (caloric restriction / metabolic). Conclusion: "Probiotic supplementation did not enhance the effects of caloric restriction on body composition." | Verify full-text explicitly uses Lpc-37 + CFU dose, OR swap to a Lpc-37-specific RCT. |
| Escherichia coli Nissle 1917 | 35701435 | Engineered/synthetic-biology mouse-IBD mechanism paper using ECN-pE (GMO variant with overexpressed catalase + SOD). Does NOT support wild-type Nissle CFU-dose claim. | **SWAP REQUIRED** — Nissle 1917 has extensive human IBD/UC clinical evidence (e.g. candidate PMIDs 15043499, 10406200 — mesalamine-comparison UC-maintenance trials). Pick one and swap. |

**Effort:** ~15 min — skim PubMed, pick a citation each, tell engineering the PMIDs. Both `dr_pham_signoff` stay `false` until resolved.

### FU-3 — Review the 5 "weak, no better candidate" strains

These weak-evidence strains have no stronger PubMed citation available. They're flagged correctly as weak today. Review at your convenience — if you know of better evidence (industry reports, product-specific manufacturer clinical data, recent publications not in PubMed), flag the swap.

| Strain | Current PMID | Current Type | Note |
|---|---|---|---|
| Lactobacillus acidophilus NCFM | 24717228 | animal_model | Often studied in multi-strain blends; reviewer confirmed weak justified |
| Bacillus subtilis DE111 | 39631408 | animal_model | Swap candidate was niche ileostomy population; reviewer kept weak |
| Bifidobacterium lactis Bl-04 | 38665561 | limited | No human-RCT candidate found; reviewer kept weak |
| Lactobacillus fermentum ME-3 | 36644601 | animal_model | No human-RCT candidate found |
| Bifidobacterium longum 1714 | 41607522 | animal_model | Rare strain, very limited literature |
| Lactobacillus acidophilus DDS-1 | 32019158 | multicenter (mixed-strain) | Same study as UABla-12; single-strain attribution weak |
| Bifidobacterium lactis UABla-12 | 32019158 | multicenter (mixed-strain) | Same study as DDS-1 |
| Bifidobacterium breve M-16V | 40085083 | mixed-strain RCT | Swap candidate systematic review concluded "very low" quality, "no significant benefits" (reviewer-reversed) |

**Effort:** ~5–10 min skim. If you have no better citations, confirm "weak is honest" and flip `dr_pham_signoff: true` on each with `clinical_support_level: weak`. If you have better citations, flag them and engineering executes swap.

### Current sign-off state (post all updates)

- 32/42 strains signed off (`dr_pham_signoff: true`)
- 10/42 still pending: 8 weak (FU-3) + 2 needing re-citation (FU-2)
