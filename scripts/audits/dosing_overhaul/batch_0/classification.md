# Batch 0 — Therapeutic-entry disposition (keep vs migrate)

Goal of the dosing overhaul: `rda_therapeutic_dosing.json` becomes **botanical + collagen only**; non-botanical
bioactives move to `rda_optimal_uls.json` (where the v4 generic dose path actually reads them). This doc records
the disposition of the current 48 entries and the method used.

## Method (code-verified)

An entry is **consumed** (must be kept here) iff one of:
1. **Botanical-routed** — `botanical_profile._is_botanical_active(row)` is true for products carrying it. That is
   true when the enricher tags `raw_taxonomy.category == "botanical"` **or** the entry name/alias is in
   `botanical_ingredients.json` (`_botanical_identity_set()`, 3478 names).
2. **Collagen-routed** — matched by `collagen_profile` (aliases `uc-ii`/`nem`/`biocell`/`gelatin`/`collagen`).

Static name-match against `botanical_ingredients.json` (run via the live module functions) is authoritative for the
"in the identity set" half. The "enricher tags it botanical" half is **product-dependent** and is confirmed against
a freshly-enriched corpus at migration time (verify-before-remove gate), not assumed.

Asymmetric risk: migrating a *consumed* entry → score regression (bad); keeping an inert one → harmless. So anything
with *any* consumption signal is kept, and ambiguous plant-isolates are confirmed before removal.

## KEEP — botanical name-matched (18) + collagen (5) = 23

**Botanical (name-matched in `botanical_ingredients.json`):**
Ashwagandha, Bacopa, **Curcumin** (`curcuma longa`), **L-Theanine** (`theanine`), **Resveratrol**
(`polygonum cuspidatum`), Rhodiola, Saw Palmetto, St John's Wort, Valerian, Lion's Mane, **Phosphatidylserine**,
Ginkgo, **Astaxanthin**, Black Seed Oil, Maca, Milk Thistle, Cordyceps, Reishi.

> Surprises vs the original plan: **L-Theanine, Phosphatidylserine, Curcumin, Resveratrol, Astaxanthin** are
> name-matched as botanical → they are consumed and **stay**. (Resveratrol keep contradicts the v4 dev's
> "migrate" hypothesis — the static evidence, `polygonum cuspidatum` in the identity set, wins; reconfirm on
> corpus if a synthetic-resveratrol product never carries the knotweed identity.)

**Collagen (consumed via `collagen_profile`):** Collagen Peptides, UC-II, BioCell, Gelatin, NEM.

## MIGRATE candidates — not consumed by the botanical/collagen paths (25)

**Clearly non-botanical bioactives (safe to migrate after the standard verify-before-remove check):**
- Already in `rda_optimal_uls.json` — inert copy REMOVED in Batch 1 (commit pending): Alpha-Lipoic Acid, CoQ10,
  Taurine, Creatine. (Zero-delta: none is botanical-name-matched and none is botanical by nature → never reachable
  via the botanical/collagen dose adapters; all 4 confirmed present in optimal-uls so no coverage lost.)
- Add to optimal-uls (verify) then remove: Beta-Alanine, Citrulline Malate, GABA, Glucosamine Sulfate,
  Hyaluronic Acid, Melatonin, MSM, NAC, Ubiquinol, Magnesium L-Threonate, NMN, L-Citrulline, PQQ, HMB, SAM-e.

**CORRECTION (Batch 1 finding) — Lutein is KEPT, not migrated.** `marigold` / `marigold extract` IS in
`botanical_ingredients.json` (id `marigold`), so marigold-derived lutein products are botanical-routed and the
Lutein therapeutic entry IS consumed for them. The Lutein-in-both-files state is therefore CORRECT dual-routing
(marigold-extract → therapeutic/botanical path; isolated lutein → optimal-uls/generic path), not a dead duplicate.
So Batch 1 removed 4, not 5; KEEP count is 24 (19 botanical incl. Lutein + 5 collagen).

**FLAGGED — plant-derived isolates NOT in the identity set; confirm enricher taxonomy on corpus BEFORE removal:**
- **Berberine** (plant alkaloid; v4 dev hypothesized botanical — static says not name-matched → must check enricher tag)
- **Quercetin** (flavonoid)
- **DIM** (from cruciferous)
- **5-HTP** (from Griffonia simplicifolia seed)
> If any of these is tagged `raw_taxonomy.category == "botanical"` on real products, it is consumed → keep here
> instead of migrating. Resolve in the migration batch with a freshly-enriched corpus, not by guessing.

**Special case:** **Probiotics (General)** — unit is `CFU`, which does not fit the mg/g RDA-proxy schema in
`rda_optimal_uls.json`. Needs its own handling decision before any move; do not force-migrate.

## Notes

- `_metadata.total_entries` was already correct (48) at the time of this audit — no fix needed (the session-start
  read of 44 was stale; committed `eec0e3ba` had already bumped it).
- The 5 collagen entries' PMIDs were content-verified (12/12 match, 0 mismatch) via the extended
  `verify_all_citations_content.py` — Batch 2 is a confirm, done.
