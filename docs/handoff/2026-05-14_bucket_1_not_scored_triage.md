# Bucket 1 (NOT_SCORED) triage — 2026-05-14

**Status:** Investigation complete. The 42 NOT_SCORED entries split
cleanly into 4 sub-patterns. Roughly half are genuine DSLD authoring
gaps (cannot be fixed without inventing data); the other half are
potentially fixable pipeline bugs across 3 distinct ingredient classes.

**Source manifest:** `scripts/dist/export_manifest.json`, generated
2026-05-14T09:29:08Z. All 42 share the same export-time error
signature: `"review_queue: NOT_SCORED verdict — mapping/dosage gate
failed upstream"`.

**Per-product scored-output signatures:**
- 38/42 → `scoring_status=not_applicable`, `score_basis=no_scorable_ingredients`,
  `flags=['NO_ACTIVES_DETECTED']`, `mapped_coverage=0.0`
- 4/42 → same but with `flags=['UNMAPPED_ACTIVE_INGREDIENT']` and
  `mapped_coverage>0` (Collagen with Peptan family + Aloe Vera Juice)

## Sub-pattern breakdown

| Cluster | Count | Fixable? | Where to look |
| --- | ---: | --- | --- |
| **A. MACROS_ONLY ingredientRows** | 18 | ❌ DSLD gap | n/a |
| **B-creatine. PEG-Creatine System** | 14 | ✅ Maybe | enricher IQM match for `PEG-Creatine System` |
| **B-blend. Opaque Proprietary Blend header only** | 2 | ❌ By policy | n/a |
| **C. Has compound, pipeline drops it** | 8 | ✅ Likely yes | enricher Pass 1 active classification |

**Bottom-line counts:**
- **Fixable now: 0–19** (Clusters B-creatine + C, pending investigation)
- **Not fixable (DSLD/policy): 23** (Clusters A + B-blend)
- **Goal in original handoff:** `excluded_by_gate < 20` after Bucket 1
  closes. Hitting that requires resolving most/all of Clusters B-creatine + C.

---

## Cluster A — MACROS_ONLY (18 entries) — NOT FIXABLE

All GNC single-ingredient oil softgels: Evening Primrose Oil (×13),
Pumpkin Seed Oil (×3), Flax Seed Oil (×2). DSLD's `ingredientRows`
contains ONLY the nutrition panel (`Calories`, `Total Fat`); the
actual oil compound (EPO / Pumpkin Seed Oil / Flax Seed Oil) is **not
enumerated as a structured ingredient**. The product name conveys it
("Evening Primrose Oil 1300") but the structured data only describes
the softgel shell + macros.

**Affected dsld_ids:** 1429, 3552, 11588, 17794, 26321, 33529, 36053,
36092, 57157, 65938, 69686, 74725, 75189, 75256, 75261, 79163, 229109,
328814.

**Decision:** these are correctly NOT_SCORED. The Batch 3 gate is doing
its job — refusing to score products where the active compound isn't in
the data. Per `docs/handoff/2026-05-13_data_quality_backlog.md`:
> "No fix that simply downgrades the gate severity. The gate exists for
> a reason: incoherent scores are worse than no score."

**Optional remediation:** if Sean wants to recover these, the only path
is product-name-based fallback parsing for single-ingredient labels
(`<botanical> Oil <quantity>` pattern). Risky — could mis-classify.
Probably not worth doing for 18 products.

---

## Cluster B-creatine — PEG-Creatine System (14 entries) — IQM SHIPPED 2026-05-14, CLEANER STILL BLOCKS

All GNC Creatine products: Amplified Creatine 189 (×12), Creatine
Strength Support, Creatine 189 Strength & Performance Support, Creatine
HCl 189.

`ingredientRows` typically contains a single row:
```
name: "PEG-Creatine System"
ingredientGroup: "Creatine"
category: "non-nutrient/non-botanical"
```

**Affected dsld_ids:** 4844, 4845, 5776, 5884, 18479, 25595, 30568,
31141, 42327, 67310, 69333, 74811, 74814, 210596.

### 2026-05-14 IQM-side fix (LANDED)

Added a dedicated `peg-creatine system` form to the `creatine_monohydrate`
parent in `ingredient_quality_map.json`:
- bio_score: 10 (class-equivalent to creatine HCl/citrate, NOT 6 like
  the (unspecified) fallback, NOT 14 like monohydrate gold standard)
- absorption_structured.value: 0.90 (conservative band [0.80, 0.95])
- Evidence-anchored to 3 WebFetch-verified PMIDs:
  - Herda 2009 PMID:19387397 (n=58, 30-day RCT, equivalent to monohydrate
    on 1RM at lower dose)
  - Camic 2010 PMID:21068676 (n=22, 28-day RCT vs placebo)
  - Camic 2014 PMID:23897021 (n=77, 28-day RCT vs placebo)
- Aliases: `peg-creatine system`, `peg-creatine`,
  `polyethylene glycosylated creatine`, `polyethylene-glycosylated creatine`
- 9 regression tests in `test_creatine_integrity.py` pin the form + its
  bio_score band + alias coverage + PMID evidence + taxonomy isolation
- Matcher simulation PASSES: raw `'PEG-Creatine System'` from DSLD now
  routes cleanly to the dedicated form with bio_score 10

Earlier draft attempted to alias PEG-Creatine to the (unspecified) form
at bio_score 6 — rejected by reviewer as too punitive (would put PEG
below creatine ethyl ester, a known failed pro-drug). Alternative draft
proposed aliasing to creatine_hydrochloride to lift the score — rejected
as semantically sloppy (PEG-Creatine is NOT creatine HCl). Final approach
follows project taxonomy principle: distinct compound → distinct form node.

Earlier draft also cited an incorrect Herda PMID (19164825 — actually a
2008 prostate-cancer study). PubMed eutils content-verification caught
the ghost reference; replaced with the correct PMID 19387397 pre-merge.

### Cleaner-side blocker (STILL ACTIVE — separate work needed)

End-to-end verification on dsld 4844 (Amplified Creatine 189) reveals
the cleaner DROPS the `PEG-Creatine System` raw active row before it
reaches the enricher:
```
raw_actives_count: 1          # cleaner sees the row in ingredientRows
activeIngredients: []         # but it disappears after classification
inactiveIngredients: [7]      # NOT routed to inactive either — just dropped
```

The drop is upstream of any IQM matching. The IQM fix is therefore
necessary but not sufficient — the 14 GNC creatine products will
continue to score as NOT_SCORED on the next pipeline rebuild until the
cleaner-side drop is also resolved.

**Where to look (cleaner-side):**
1. `scripts/enhanced_normalizer.py:_process_single_ingredient_enhanced`
   (line ~4630) — the per-row classifier that returns `None` to drop
   silently. Add a trace branch that logs the drop reason.
2. Walk the `_process_ingredients_enhanced` filter chain (line ~4518):
   `_is_active_source_form_wrapper`, `_is_structural_active_blend_leaf`,
   `_is_structural_active_form_display_only`,
   `_is_structural_active_display_only_leaf`, `_is_structural_form_container`,
   `_is_label_header`. The `forms[]=[]` plus the "System" suffix on the
   name might be triggering one of the structural-container checks even
   though the row has no children.
3. `_is_nutrition_fact` returns False for this row (verified separately),
   so it is NOT the drop site.

**Estimated effort:** 1-2 hours of cleaner-side tracing once someone
sits down with the live raw record.

This is the same shape as the original Bucket 3 issue (actives demoted
to inactive) and the Bucket 2 issue (Phase 4a label-descriptor drops).
Likely a missing entry in one of the cleaner's structural-container
allowlists, or an overly-aggressive `forms[]==[]` filter that fires on
single-row containers like this one.

---

## Cluster B-blend — Opaque Proprietary Blend (2 entries) — NOT FIXABLE

- 855: Oil Of Oregano — `Proprietary Blend|Proprietary Blend (Combination)`
- 18259: Extra Strength Probiotic 15 mg — `Proprietary Probiotic Blend|Bifidobacterium (mixed)`

Both have opaque blend headers as their only active row. Per the
4-state blend classifier policy, OPAQUE_BLEND products are intentionally
not scoreable (they route through B5 transparency penalty in the scorer
but the score itself is not computed).

**Decision:** correctly refused. Leave as-is.

---

## Cluster C — Has compound, pipeline drops it (8 entries) — LIKELY FIXABLE

Most diverse sub-pattern. 4 sub-clusters here:

### C1. Single-row oils where the row IS the compound (3 entries)

- 2247: Flax Seed Oil 1000 — has "Total Fat" only (basically MACROS_ONLY)
- 25935: DHA — `ingredientRows: Calories/Calories from Fat/Total Fat/Dextrose`. **Dextrose isn't the active**; DHA itself is missing.
- 78355: Coconut Oil — `Total Carbohydrates/Protein` etc.; no MCT/coconut oil compound row.

**Note:** these are basically MACROS_ONLY plus one or two non-macro
junk rows. Should be re-categorized as Cluster A.

### C2. Collagen with Peptan (3 entries)

- 203283: Collagen Types 1 and 3 with Peptan 500 mg
- 203354: Collagen Types 1 and 3 with Peptan 1000 mg
- 209444: Collagen Types 1 and 3 with Peptan and Vitamin C 500 mg

`ingredientRows` contains: `Calories | Protein | Vitamin C | hydrolyzed Collagen Types 1 and 3 (Blend)`.

Vitamin C maps; "hydrolyzed Collagen Types 1 and 3" doesn't. Result:
`mapped_coverage=0.5`, `unmapped_actives=['hydrolyzed Collagen Types 1 and 3']`,
flags=`['UNMAPPED_ACTIVE_INGREDIENT']`, gate refuses.

**Where to look:**
1. `scripts/data/ingredient_quality_map.json` — is there a `collagen`
   IQM entry? If yes, does it include `hydrolyzed Collagen Types 1 and 3`
   as a form/alias?
2. Why does the gate refuse instead of producing a partial score from
   Vitamin C alone? The "mapping/dosage gate failed upstream" message
   suggests the gate is strict about full coverage rather than partial.

**Likely fix paths:**
- IQM data: add `hydrolyzed Collagen Types 1 and 3` (and Peptan brand)
  as aliases of an existing `collagen_hydrolysate` entry, OR add a new
  entry if there isn't one.
- Possibly: relax the gate from requiring 100% coverage to allowing a
  partial score with a transparency penalty for unmapped actives.

### C3. Fish Oil 212518 (1 entry)

`ingredientRows` has the compound clearly: `name: "Total Fish Oil",
ingredientGroup: "Fish Oil", quantity: 475 mg`. The enriched record
shows `quality_data.ingredients_scorable=0` and
`quality_data.ingredients_skipped=0` — 5 raw actives went into the
enricher and 0 came out classified. **This is the clearest pipeline
bug** of the bunch.

**Where to look:**
1. Pass 1 active classification in `enrich_supplements_v3.py` —
   does it match "Total Fish Oil" against the IQM `fish_oil` entry?
2. Why does the enricher silently drop 5 raw actives without
   classifying them as either scorable or skipped?

This is the highest-yield single-entry fix in the cluster.

### C4. Aloe Vera Juice 214221 (1 entry)

`ingredientRows` has `Vitamin A`, `Calcium`, plus the active aloe.
`unmapped_actives=['less than 0.1%']` — the literal text "less than 0.1%"
is appearing in the actives list. Looks like a parsing/extraction bug
in the cleaner — that string is a label artifact ("aloe vera juice
(active less than 0.1% of sugar)") that's getting captured as if it
were an ingredient name.

**Where to look:**
1. `scripts/enhanced_normalizer.py` — what's capturing "less than 0.1%"
   into the active list?

---

## Recommended sequencing

1. **PEG-Creatine alias fix** (Cluster B-creatine, 14 entries) —
   highest count, simplest investigation. Add `PEG-Creatine System` →
   `creatine` IQM alias. Recover ~14 products with one data edit.

2. **Fish Oil 212518 single-product trace** (Cluster C3, 1 entry) —
   highest-yield real-bug investigation. Pinpoints whether the enricher
   has a silent-drop path that affects more than just this one product.

3. **Collagen with Peptan IQM gap** (Cluster C2, 3 entries) — single
   data edit (add `hydrolyzed Collagen Types 1 and 3` alias to
   `collagen_hydrolysate` IQM) recovers all 3.

4. **Aloe Vera "less than 0.1%" parsing** (Cluster C4, 1 entry) — small
   cleaner regex tightening.

5. **Cluster A acceptance** (18 entries) — document that these are
   correctly NOT_SCORED in the manifest's review_queue tooltip so
   reviewers don't keep re-triaging them.

**Optimistic outcome:** ~19 products recovered, bringing
`excluded_by_gate` from 42 → 23 (mostly Cluster A which is genuine
DSLD authoring debt). That hits the original handoff's
"<20 genuinely unshippable" target.

## What this triage IS and ISN'T

✅ This triage is: a single representative trace per sub-pattern, with
the root cause hypothesis named for each cluster, plus where in the
code to look.

❌ This triage is NOT: the actual fix work. The follow-on work
(Cluster B-creatine alias + Cluster C investigations) is a separate
session (estimated 2–4 hours of pipeline work + tests).

If you decide to pursue this, start with Cluster B-creatine (highest
count × lowest effort) and Cluster C3 (real bug, single product).
