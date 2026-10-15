# Stale local corpus canaries — causes and receipts, October 15, 2026

Scope: 7 failures on main 47c746537 in the LOCAL_ONLY corpus canaries `test_v4_cross_module_canary_diversity.py` (328825, 325587, 178346, 286725) and `test_v4_gate_canary_diversity.py` (241706, 325587, 230149). They read the stored enriched corpus in `scripts/products`, re-enriched October 14. CI never runs them, which is why they went stale unnoticed.

## Method

Each canary was scored on today's stored corpus at two code states:

- **Pin commit 0fd9fb1a6 (October 8):** reproduces 5 of 6 pins.
- **Main:** fails all 6.

So 5 are code drift. For each, a bisect on the same enriched record found the first changed commit. 241706 matches on both code states, so it is enrichment/data drift; I traced it by re-enriching the raw label at both commits.

| Canary | Pin → now | Cause | Verdict |
|---|---|---|---|
| 328825 Thorne Curcumin Phytosome | 62.5 → 59.5; Formulation 10.5 → 7.5 | bf12ae68d (PR #143): phytosome/Meriva is the resolved form, so A3 delivery 3 → 0 | Correct under `.claude/rules/scoring.md` "distinct formulation qualities count once"; re-pinned |
| 325587 Transparent Labs Creatine HMB (both files) | 82.0 → 79.2 | bf12ae68d: BioPerine already earns A4 (kept); A3 3 → 0. cd2baf4f3: Sean's HMB provisional form ceiling (October 12) moves A1 10.98 → 11.25 | Correct; re-pinned |
| 178346 Spring Valley Probiotic 50B | 24.2 → 21.2 | bf12ae68d: "Acid and bile resistant strains" plus blister packs is an intrinsic strain claim, with no eligible delivery mechanism; survivability 3 → 0 | Correct; re-pinned |
| 286725 vitafusion Probiotic 5B (gummy) | 44.0 → 41.0 | bf12ae68d: the only basis was *Bacillus coagulans* spores (intrinsic) | Correct; re-pinned |
| 230149 OLLY Extra Strength Probiotic (gummy) | 70.7 → 67.7 | Same as 286725 | Correct; re-pinned |
| 241706 HUM Ripped Rooster | 38.4 → 36.4 | 85d4e8402 (October 11) narrowed `standardized_botanicals.json` green_tea markers from EGCG/catechins/polyphenols to polyphenols only. The label's "standardized to (50 mg) 50% Epigallocatechin Gallate" no longer earns the 4-point marker credit (botanical profile 15 → 12) | Follows the current curated rule; re-pinned. Policy question D28 below |

Separately found: since 2415ec8a7, IQM form selection needs the exact alias "50% EGCG", so a row that spells the marker out falls to "green tea extract (unspecified)". This is fixed by the alias receipt below.

## Alias receipt — `ingredient_quality_map.json` › green_tea_extract › "green tea extract (50% EGCG)" › `source_form_aliases`

- **Change:** add "50% Epigallocatechin Gallate".
- **Identity:** PubChem, checked 2026-10-15. "epigallocatechin gallate" and "EGCG" both resolve to CID 65064 (C22H18O11, InChIKey WMBWREPUVVBILR-WIYYLYMNSA-N). The synonym list includes "EGCG", "Epigallocatechin gallate" and "Epigallocatechin-3-gallate".
- **Negative control:** "epigallocatechin" (EGC) is CID 72277, C15H14O7, a different compound. It is not aliased, and a test pins that it does not match.
- **Applicability:** the alias only applies on a row whose own forms[] declare the percentage (the 2415ec8a7 own-row rule is unchanged).
- **Affected raw labels:** 4 in the staging corpus (BulkSupplements 252529, 253697, 253727; Hum 241706). A clean replay of main against main plus the alias from raw labels, through clean, enrich and `build_scored_artifact`, gives:
  - All 4 now resolve to the 50% EGCG form (bio 8 → 9).
  - The EGCG marker dose is restored (250 mg ×3; 50 mg).
  - Totals, tiers, safety and assessment states are unchanged; the botanical profile owns their Formulation.
  - The stored corpus picks this up only at the next re-enrich.

## D28 — open policy question (nothing changed)

Green tea standardization is now measured on total polyphenols (≥ 50%). EGCG is itself a polyphenol, so a declared EGCG percentage is a lower bound on total polyphenols. Should a declared EGCG percentage count toward the polyphenol threshold as that lower bound?

- **If yes:** 50% EGCG meets the threshold, and 45% EGCG gets the "near" tier.
- **If no:** the current rule stands, and EGCG-standardized extracts earn no standardization credit unless polyphenols are also printed.

Raw corpus: 31 green-tea rows declare 45% and 4 declare 50% "Epigallocatechin Gallate"; 15 declare 50% and 7 declare 45% "EGCG". This needs a source-checked decision, not a canary edit.
