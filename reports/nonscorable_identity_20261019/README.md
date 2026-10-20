# Non-scorable rows keep their identity (F2, option a) — October 20, 2026

Decision (coordinator, option a): restore identity on non-scorable **rows** only; blend headers
wait for a separate scoring follow-up; fix the botanical-routing leak in the same PR; only
score-eligible rows may route.

## Change

1. `identity_integrity.resolve_identity` (`retained_unscoreable_canonical`): a non-scorable row
   keeps its supplied identity when the cleaner's own `standardName` for the row is an exact
   registry name or alias of it, the label names no other identity, it is not a blend header
   (`cleaner_row_role == "blend_header_total"` / `hierarchyType == "blend_header"`), and it is not
   a role or catch-all record. A stale id the row never named stays out (Antimony guard).
2. `scoring_input_contract._classify_botanical_owner_type`: a blend total lent to a member
   (`is_lent_blend_mass`) cannot outrank non-botanical actives that carry their own label amounts
   (327570 Methyl B12: "Beet" borrowing a 242 mg Food Blend beside B12, B6, folate). With no such
   active, the lent member remains the route (Tart Cherry Fruit Complex unchanged).
3. `scoring_input_contract._named_in_title`: one word of a derived identity name (standard name,
   canonical id) is no title evidence; derived names match whole, the printed name (and a forms[]
   member's printed parent blend) by any word. 204521 "Raw Organic Fit Coffee": "Raw organic
   Svetol" (green_coffee_bean) no longer becomes the sole Evidence owner through "coffee".

## Measurement

Cohort: 940 labels whose identity was erased on the 951a05415 capture, 600 seeded controls and
204521 (1,540). `replay.py snapshot --full --blob`, main 625e90425 vs the final candidate.
Census: `retention_census.py` → `f2a_census.out`; every score move with its cause in
`f2a_score_moves.tsv`; every rule added per product in `f2a_rules_added.tsv`.

- 522 products gain row identities; **0 header identities**.
- **+85 interaction rules, 0 removed, 0 product_safety_status changes**: probiotics
  immunocompromised 45, L-arginine 27, yerba mate 8, aloe vera 3, lion's mane 1, ginseng 1.
- **30 score moves** (was 59 before the header exclusion and routing fix), all classified:
  - identity restored (probiotic strains, food powders, Pycnogenol, glutamic acid): 15;
  - routing (lent blend vs own-amount actives → generic): 8;
  - title (derived-name word no longer title evidence): 7.
- Raw canary check (`freeze_contract_snapshots.py --check`): 0 drifts. The earlier 204571 drift
  (Adrenal Daily Balance 60.4 → 44.8) came from the header "Organic Adrenal Blend" taking
  organ_extracts and owning Evidence through the title; headers are now excluded.

## Exposed alias defects

| Alias | Rows in this output | Verdict |
|---|---|---|
| "adrenal" → organ_extracts ("Organic Adrenal Blend") | none (header) | cleaner lane |
| "prostate" → organ_extracts ("Prostate Formula") | none (header) | cleaner lane |
| "Resveratrol analogs" → pterostilbene | 2 | correct: the raw row's form is Pterostilbene |
| "Glycosides" → resveratrol | 2 | form is Polydatin (resveratrol glucoside); a Trans-Resveratrol row sits beside it, no outcome change; noted |
| "oat grass" → oat_straw | 41 | within the entry's curated scope (Avena sativa aerial parts; EMA oat herb = aerial parts before flowering); not changed |

## For Sean

- Caffeine Blend headers (Ravage 1179/12800/28981) stay as on main: no caffeine warning. Not a
  regression; open until the header follow-up.
- L-arginine hypertension rule (no dose threshold) now fires for "Arginine" rows in whey amino
  profiles (27 products). Real concern or a threshold decision?
- Evidence title owners from flavor names: 278416 "…Juiced Greens Powder Apple" (Apple restored,
  Evidence 10.3 → 0) and 40089 Kids Gummy (coffeeberry/apple, 10.3 → 0).
- 259714 Essential Amino Complete: BCAA no longer owns Evidence through the derived word "amino";
  the remaining essential-amino owners have no evidence records (Evidence 10.4 → 0).
- Gamma-Carotene → vitamin_a (cleaner identity) now credits vitamin A evidence (297685/6, +3.3);
  gamma-carotene is a provitamin, not a vitamer.
