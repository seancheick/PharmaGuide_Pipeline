# Null-direction records — scope audit (2026-09-18)

**Scope correctness first, direction semantics second.** Every source below was re-fetched live
from PubMed and read before anything here was written. No record was edited, no score moved, no
multiplier changed.

The finding is consistent across all four: **each record's `null` direction is the answer to a
narrower question than the record's identity claims.** Fixing the multiplier while leaving these
scopes in place would harden a misattribution rather than remove it.

| record | identity reach | what its sources actually asked | scope verdict |
|---|---:|---|---|
| `INGR_VITAMIN_B12` | 2,176 products | cognition/depression/fatigue in people **without** deficiency | over-broad |
| `INGR_SAW_PALMETTO` | 128 products | BPH/LUTS — but sources mix extracts and one is about hair loss | over-broad + off-axis citation |
| `PRECLIN_DIM` | 4 products | biomarker endpoints in cervical-abnormality and tamoxifen patients | over-broad |
| `INGR_BORON` | 679 products | two materials at once: calcium fructoborate vs plain boron | material conflation |

---

## 1. `INGR_VITAMIN_B12` — the canary, and the clearest defect

**Current state:** `systematic_review_meta` / `ingredient-human` / **null**, enrollment 200,
aliases `cobalamin`, `methylcobalamin`. Matches **2,176 products** (1,640 multivitamin/prenatal,
341 generic, 141 B-complex, 22 probiotic-lane, and a few fiber/sports/omega); for **168** it is the
only accepted match. `GENERIC_EVIDENCE_NULL_DIRECTION_REVIEW.md` reports 2,154 for the same record
because that pass excludes the probiotic lane — same corpus, different scope, not a disagreement.

**Its single source, verified live.** PMID 33809274 — *"Effects of Vitamin B12 Supplementation on
Cognitive Function, Depressive Symptoms, and Fatigue: A Systematic Review, Meta-Analysis, and
Meta-Regression."* Its stated population:

> in patients without advanced neurological disorders or overt vitamin B12 deficiency

**The defect.** That is a null answer to one narrow question: does B12 help cognition, mood or
idiopathic fatigue in people who are **not** deficient. The record then carries that direction for
the entire B12 identity — including the 1,640 multivitamins where B12 is present for nutritional
adequacy, not as a nootropic. The record's own text contradicts its direction:

> Vitamin B12 clearly benefits deficiency correction and neurologic or hematologic protection in
> deficient states.

and its `key_endpoints` still read `energy ↑ (deficiency)`, `fatigue ↓ (deficiency)`.

**Another owner already holds the rest.** DRI-essential nutrient necessity is owned by the dose and
nutrition-authority path, not by this registry: `nutrition_authority_floor` (10.0) in
`scripts/scoring_v4/config/quality_score.json`, applied through
`generic_evidence._dri_essential_identity_keys` — live on 672 products today — with
`scripts/data/rda_optimal_uls.json` owning the reference amounts. **Do not duplicate nutrient
authority into the clinical evidence registry.**

**Recommended repair (independent of any multiplier decision).** Narrow the record to the question
its source answered — cognition, depressive symptoms and idiopathic fatigue in adults without overt
deficiency — so it stops speaking for B12 generally. Whether that means a scoped record, a renamed
identity, or removal from the generic B12 identity is an owner decision; all three are better than
the status quo.

---

## 2. `INGR_SAW_PALMETTO` — over-broad, plus a citation that is not on this axis

**Current state:** `rct_multiple` / `ingredient-human` / **null**, enrollment 833, 128 products.

**Sources, verified live:**

- **PMID 29694707** — meta-analysis of the **hexanic extract Permixon specifically**, and it says so:
  > Articles studying S. repens extracts other than Permixon were excluded
- **PMID 12006122** — *androgenetic alopecia* (hair loss) with a botanical 5-alpha-reductase blend.
  This is **not saw palmetto monotherapy for BPH**, and it sits on a record whose endpoints are AUA
  symptom score, IPSS, peak urinary flow and nocturia. Off-axis citation.
- The CAMUS and PERLES entries carry NCT ids but no PMID.

**The defect.** The record's own notes say *"Evidence remains mixed"* while its direction field says
`null`. The literature splits by **material**: CAMUS (US extract, up to 960 mg/day) was null, while
the Permixon hexanic-extract synthesis is favourable. A single ingredient-level direction cannot
carry that split — the same material problem butterbur exposed, now in a record that already ships.

**Recommended repair.** Drop or re-file the alopecia citation, and decide the record by material:
either scope it to the extract its sources tested or keep it unscored until that is possible. Note
the applicability owner can now express material scoping (2026-09-17 repair).

---

## 3. `PRECLIN_DIM` — small, but generalises patient-population biomarker results

**Current state:** `rct_single` / `ingredient-human` / **null**, enrollment 62, 4 products.
(The `PRECLIN_` prefix with `ingredient-human` level is the known legacy naming inconsistency.)

**Sources, verified live:**

- **PMID 22075942** — 150 mg BioResponse DIM for 6 months in women with newly diagnosed low-grade
  cervical cytological abnormalities.
- **PMID 28560655** — BR-DIM 150 mg twice daily for 12 months in women **taking tamoxifen**; the
  primary endpoint is a urinary estrogen-metabolite ratio, i.e. a biomarker, and the record notes it
  also lowered tamoxifen metabolites.

**The defect.** Both are specific patient populations with biomarker or lesion endpoints; neither
asks whether DIM does anything for the "Hormone Balance" use these 4 products are sold for. The
tamoxifen finding is an **interaction** signal and belongs to the interaction owner, not to an
efficacy direction.

**Recommended repair.** Scope to the studied populations and endpoints; route the tamoxifen
interaction to `ingredient_interaction_rules` / `curated_interactions`.

---

## 4. `INGR_BORON` — two different materials inside one record

**Current state:** `observational` / `ingredient-human` / **null**, enrollment 30, 679 products,
aliases include **`calcium fructoborate`**.

**Sources, verified live — and they disagree because they are not the same material:**

- **PMID 25433580** — calcium fructoborate 112 mg/day or 56 mg/day for 30 days; reductions in CRP
  and lipid markers. Randomized, placebo-controlled.
- **PMID 24940052** — calcium fructoborate 110 mg twice daily; **improved** knee discomfort (WOMAC,
  MPQ) over 14 days. Randomized, placebo-controlled.
- **PMID 8508192 / 7889885** — plain boron 2.5 mg/day for 7 weeks in male bodybuilders; **no**
  effect on testosterone, lean mass or strength.

**Two defects.** (a) `study_type` is `observational`, but all four sources are randomized controlled
trials — the record understates its own evidence type. (b) The record merges a specific compound
(calcium fructoborate, positive on inflammation/discomfort biomarkers) with plain boron (null for
the ergogenic claim), then reports a single `null`.

**Recommended repair.** Separate the materials — calcium fructoborate is not plain boron — and
correct `study_type`. Only then is a direction meaningful.

---

## Measured impact of the candidate semantic

`null_direction_projection.py` ran the production scorer (`score_product_v4`) twice over every
product matching a null record — as shipped, and with the null multiplier set to 0 in both modules
that read it. Config and registry untouched; patched in memory only.

| measure | value |
|---|---:|
| products matching a null record | 2,446 |
| products scored both ways | 2,446 |
| **products whose Evidence changes** | **151** |
| mean Evidence delta (changed) | −0.71 |
| largest Evidence drop | −1.5 |
| largest total-score drop | −1.5 |

Changed by record: B12 74, boron 42, saw palmetto 24, DIM 14.
Changed by module: generic 121, multi/prenatal 20, fiber 6, omega 2, probiotic 1, B-complex 1.

**The impact is far smaller than the match count suggests, and the reason matters.** In every
changed product the null record *was* the whole dimension (Evidence 1.5 → 0.0, e.g. 243259 Vitamin
B-12 Organic Spray, 240875 Apple Cider Vinegar Gummies). Everywhere else a floor already sets the
score and the null record's points sit below it.

**Correction to this project's earlier report.** `GENERIC_EVIDENCE_NULL_DIRECTION_REVIEW.md`
originally said 249 products' "Evidence score rests entirely on evidence that did not show benefit".
That is wrong for the floor-carrying majority. Measured on product 252794 (Vitamin B12 1%,
Cyanocobalamin), whose shipped Evidence is often quoted as 11.1/20:

| | clinical_evidence_pipeline | primary_evidence_floor | dimension |
|---|---:|---:|---:|
| current (null = 0.25) | 1.35 | 10.0 (nutrition authority) | **10.0** |
| candidate (null = 0) | 0.0 | 10.0 (nutrition authority) | **10.0** |

The DRI-essential nutrition-authority floor carries that product, not the null B12 record. The
report has been corrected.

That does not weaken the semantic argument — a null trial should not add affirmative efficacy
points — but it does change the stakes: this is a ~151-product, ≤1.5-point correction, not a
catalog-wide repricing.

## What this means for the multiplier question

Both things are true at once and should be decided in this order:

1. **These four scopes are wrong today.** Three of the four would still be wrong if the multiplier
   were 0, because the record would then assert "no benefit demonstrated" about a question its
   sources never asked — which is worse for B12 than the current overcredit.
2. **The semantic defect is real and separate.** A rigorous null trial should raise confidence that
   benefit was not demonstrated; it should not add affirmative efficacy points.

Recommended sequence: repair scope first (per record, one at a time, with the usual verification),
then decide the direction semantics against a corpus where `null` means what it says.

**Not touched:** the 34 `mixed` records, the negative multiplier, any weight, any product score.
