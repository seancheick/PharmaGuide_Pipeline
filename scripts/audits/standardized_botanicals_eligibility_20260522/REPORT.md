# standardized_botanicals.json Bonus-Eligibility & §8.5 Audit — 2026-05-22

## Why this audit

User directive on 2026-05-22: *"any other ingredients that don't deserve to be in standardized botanical would also have to move out of there, maybe go to botanical or other ingredients"*.

`standardized_botanicals.json` entries trigger the `A5b_standardized_botanical = +1pt` bonus in `score_supplements.py:1133-1186` (per `scripts/config/scoring_config.json:105`). Entries that lack a real standardization marker, or whose aliases are contaminated across species, silently inflate product scores. This audit is the pre-cleanup snapshot.

## Method

For every entry in `standardized_botanicals.json` (201 total):

1. **Marker signal** — does the entry have a documented standardization marker? Detected via `standardization_marker` / `marker` field OR notes containing phrases like "standardized to", "% ", "standardised to", "minimum ".
2. **UNII §8.5 audit** — every alias is looked up via the offline FDA UNII cache (`scripts/data/fda_unii_cache.json`, 172,558 substances). Count of distinct UNIIs that aliases resolve to. Compared against the entry's `external_ids.unii`.
3. **Eligibility bucket** —
   - `YES`: has marker + has target UNII + aliases resolve to ≤1 UNII matching target.
   - `NO (no marker)`: missing documented standardization marker → does not earn the bonus by definition.
   - `REVIEW`: has marker but identifier verification incomplete (no target UNII, or aliases don't map cleanly).

## Headline numbers

| Bucket | Count | % of 201 |
|---|---|---|
| **YES eligible (clean)** | **8** | **4%** |
| NO (no marker) | 107 | 53% |
| REVIEW (has marker, identity needs cleanup) | 86 | 43% |
| Multi-UNII or missing target UNII contamination | **133** | **66%** |

**66% of the file has identifier contamination.** This is a §8.5 emergency at scale — not a one-off misplacement.

## Clean entries (the 8 currently safe)

These have a marker AND aliases all resolve to one UNII matching the entry's target UNII. Safe to keep as-is.

- `arjuna` (4 aliases, UNII clean, has marker)
- `banaba_leaf` (3 aliases)
- `echinacea_angustifolia` (2 aliases)
- `goldenseal` (3 aliases)
- `green_tea` (6 aliases)
- `levagen` (1 alias — branded)
- `resveratrol` (2 aliases)
- `tongkat_ali` (4 aliases)

## High-risk contamination examples (the worst offenders)

These mix 4–6 different chemical UNIIs under one entry — i.e., different species / preparations all bonus-scored as one identity:

- `boswellia` — 14 aliases → 5 distinct UNIIs (mixing AKBA isolates with whole-resin)
- `bilberry` — 6 aliases → 4 UNIIs (different fruit preparations + isolated anthocyanins)
- `nettle` — 4 aliases → 4 UNIIs (leaf vs root vs seed — distinct herbal uses)
- `ginger_extract` — 10 aliases → 5 UNIIs (gingerols, shogaols, whole rhizome variants)
- `pelargonium_sidoides` — 5 aliases → 4 UNIIs (different commercial extracts)
- `rhodiola` — 7 aliases → 5 UNIIs (R. rosea vs other species + isolated rosavins/salidroside)
- `grape_seed` — 5 aliases → 5 UNIIs (each alias resolves to a different substance)
- `cordyceps` — 7 aliases → 4 UNIIs (C. sinensis vs C. militaris vs mixed preparations)
- `turkey_tail` — 5 aliases → 4 UNIIs (PSK vs PSP vs whole-mushroom)
- `sea_buckthorn` — 8 aliases → 3 UNIIs (fruit oil vs seed oil vs whole-fruit)

## Clear "no marker" entries to MOVE OUT of standardized_botanicals

The 107 entries with no documented standardization marker should be relocated:
- **To `botanical_ingredients.json`** — for basic botanical mapping, no bonus
- Sample: `black_cohosh`, `bladderwrack`, `burdock_root`, `cranberry`, `dandelion`, `garlic`, `propolis`, `suma`, `wormwood`, plus all the contaminated multi-UNII entries that also lack a marker

## Critical §8.5 finding affecting current pipeline behavior

`bladderwrack` is in this audit as "no marker" but **clean §8.5**, meaning it's safe to alias to but doesn't deserve the bonus. Yet the IQM `brown_kelp` entry has 4 Fucus/Laminaria/Ascophyllum/Undaria species mixed (separate finding from the prior Phase 1 audit). Both files have bladderwrack-related contamination — should be co-resolved.

## Recommended cleanup batches (NOT executed — awaiting user direction)

Per `feedback_accuracy_rules` (no batch fixes) and the user's "clinically correct, no fast work" directive, the cleanup should be broken into per-category batches of 5–10 entries each:

| Batch | Scope | Estimated size | Risk |
|---|---|---|---|
| **C-A** | Remove the 107 "no marker" entries from standardized_botanicals → relocate to botanical_ingredients | 107 entries, ~10 batches of 10 | LOW per-entry (just moving) but shifts scores on ~hundreds of products |
| **C-B** | Decompose multi-UNII entries by species (`boswellia`, `bilberry`, `ginger_extract`, etc.) | 66 entries, ~10 batches of 6 | HIGH per-entry — requires per-species evidence review |
| **C-C** | Populate missing target UNII for REVIEW entries with markers | 86 entries | MEDIUM — `verify_unii.py` per entry |
| **C-D** | brown_kelp 4-species decomposition (already in plan as B2) | 1 entry, multi-step | HIGH |

## Open questions for user

1. **Scoring impact tolerance**: cleanup will REMOVE the +1 bonus from many products. Some products' total scores will drop. Acceptable? Or do we need a transition policy (e.g., flag affected products, grandfather scores for 30 days)?
2. **Priority order**: which batch family (C-A move-outs vs C-B decompose vs C-C populate-UNII) should land first?
3. **Marker definition**: is "standardized to N% bioactive X" the only acceptable signal, or do we also accept "branded extract with published phytochemical fingerprint" (e.g., Sensoril, KSM-66) even without a % marker?
4. **Scope cap per batch**: 8–12 items per `UNMAPPED_RESOLUTION_PROMPT.md`, or smaller for safety-critical entries?

## Files

- This report: `scripts/audits/standardized_botanicals_eligibility_20260522/REPORT.md`
- Raw audit script + output: `/private/tmp/claude-501/.../tasks/bqf64ho6t.output`
- Audit was run against `scripts/data/standardized_botanicals.json` schema 5.0.0, last_updated 2026-05-21, total_entries 201
- UNII cache used: `scripts/data/fda_unii_cache.json` (172,558 substances, refreshed 2026-05-22)

---

## Addendum: 2026-05-22 green_coffee_bean shadow-score audit

Before committing SB-2 (green_coffee_bean tutorial), ran a surgical
shadow-score check on the current enriched output (27 brands, 10k
products):

**Current state of `green_coffee_bean` matches**

- 100 products surface a `green coffee`-flavored active ingredient
- 67 of those route to `green_coffee_bean` via `standardized_botanicals`
- 53 of the 67 currently have `has_standardized_botanical=True` — i.e.,
  the +1 A5b bonus is granted today

**Pre-commit decision: revised SB-2 to PRESERVE plain aliases**

A first-draft SB-2 removed plain aliases (`coffea robusta`, `green
coffee bean extract`, etc.) on the theory that only Svetol- or
marker-explicit phrasings should match. A 10-product spot-check
proved that approach too aggressive:

- 5/10 spot-checked products have explicit chlorogenic-acid % evidence
  in their raw label text (legitimately bonus-eligible)
- 5/10 have no standardization signal (currently get an undeserved
  bonus through plain-alias matching)

The first-draft SB-2 would have wrongly stripped the bonus from the 5
legitimate cases — and roughly ~25 of the full 53 by extrapolation.

**Adopted approach** (lands in this commit):

1. KEEP all existing plain aliases in `green_coffee_bean` for runtime
   matching.
2. ADD branded/marker-explicit aliases (`Svetol`, `green coffee bean
   extract standardized to 45% chlorogenic acids`, etc.) for product
   labels that already include the standardization phrase.
3. ADD the new v6 schema fields (`bonus_eligible`,
   `standardization_basis`, `marker_compounds`, `bonus_rationale`,
   `sources`) for governance.
4. ADD `botanical_ingredients.coffee_bean_plain` for plain "Coffee
   Bean Extract" / "Coffea robusta Seed Extract" / "Coffee, Powder"
   labels that currently surface as UNMAPPED (GNC pid 213567, 316791,
   274620, 305837, etc.). These provide an identity-only home (no
   A5b bonus pathway).
5. Defer per-species §8.5 decomposition (Coffea arabica vs canephora,
   multi-UNII split) to a follow-up batch with proper per-product
   evidence review.

**Net score impact of revised SB-2**: 0 products. The runtime
`meets_threshold` gate already filters non-standardized labels;
no product loses or gains the bonus from this commit. The new
`coffee_bean_plain` entry resolves ~14 previously unmapped products
into a clean identity home without changing their score.
