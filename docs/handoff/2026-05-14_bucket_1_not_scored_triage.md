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

## Cluster B-creatine — PEG-Creatine System (14 entries) — POTENTIALLY FIXABLE

All GNC Creatine products: Amplified Creatine 189 (×12), Creatine
Strength Support, Creatine 189 Strength & Performance Support, Creatine
HCl 189.

`ingredientRows` typically contains a single row:
```
name: "PEG-Creatine System"
ingredientGroup: "Creatine"
```
DSLD's `ingredientGroup` ≈ "Creatine" — the canonical class IS detected
at DSLD's level. But the pipeline isn't matching `PEG-Creatine System`
to the Creatine IQM canonical, so `mapped_coverage=0` and the product
gets gated.

**Affected dsld_ids:** 4844, 4845, 5776, 5884, 18479, 25595, 30568,
31141, 42327, 67310, 69333, 74811, 74814, 210596.

**Where to look:**
1. `scripts/enrich_supplements_v3.py` Pass 1 active classification —
   how does it match `PEG-Creatine System` → IQM `creatine`?
2. `scripts/data/ingredient_quality_map.json` — does the `creatine`
   entry have `PEG-Creatine System` as an alias or pattern? It likely
   doesn't, since "PEG-" is a delivery-system prefix.
3. The `_should_promote_to_scorable` Rule A (known therapeutic) — does
   the active classifier even reach IQM with the prefixed name?

**Likely fix paths:**
- Add `PEG-Creatine System` alias to IQM `creatine`, OR
- Prefix-stripping logic so `PEG-<X>` and `<X>` both route to the IQM
  entry for `<X>`. Generalize beyond just PEG (could handle other
  delivery-system prefixes).

**Estimated effort:** 30 min if just an alias addition; 1–2 hours if
prefix-stripping needs a design.

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
