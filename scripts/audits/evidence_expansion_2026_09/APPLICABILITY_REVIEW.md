# Applicability-owner review — bounded repair (2026-09-17)

**STOP POINT.** No evidence record was created or approved, no score computed or moved, no scoring
weight or direction multiplier touched, no catalog rebuild, no release. Changes are confined to the
canonical applicability owner (`scripts/clinical_applicability.py`) and its tests.

Driven only by the four failures Wave 1 exposed against real products. Two were defects in the
canonical owner and are fixed. Two are not matcher problems at all, and the evidence for that is below.

## Corpus impact: none for existing records

`applicability_projection.py` runs the committed pre-repair owner and the repaired owner over every
enricher-owned clinical match in the corpus:

| measure | value |
|---|---:|
| products evaluated | 15,418 |
| clinical matches evaluated | 50,334 |
| products with a changed result | **0** |
| match results newly applicable | 0 |
| match results no longer applicable | 0 |

The repair changes nothing for the 202 legacy records. It changes what a *material-scoped* record can
express — which is what Wave 1 needed and none of the legacy records use.

## 1. Material/form applicability — FIXED

**The defect.** The same printed label row reaches the owner twice: as the label projection
(`activeIngredients`) and as the enriched projection (`ingredient_quality_data.ingredients`). Only the
enriched projection carries `form_id` / `matched_form`, the identity enrichment already resolved.
`_rows` deduplicates on `(ref, name, quantity, unit)` and yields the label copy first, so the resolved
identity was dropped before any scope could read it. Probed on Life Extension 61929: the linked row was
`Purple Butterbur CO2 extract` with `form_id: None`, and a scope naming "Petadolex" returned
`clinical_form_mismatch` at exactly the studied 150 mg/day.

**The fix.** `_resolved_identity_by_ref` indexes enrichment's resolved identity by the label row it
belongs to, and `_rows` merges only the fields the label row lacks. No second matcher, no new material
vocabulary — the owner now reads the identity the enricher already owns.

**Boundary kept:** a source-required scope (`require_source_label_form`) receives none of this. It
distrusts enrichment-derived names by design, and a test pins that.

## 2. Multi-row identity linking — FIXED

**The defect.** `_linked_rows` returned nothing whenever an identity owned more than one candidate row,
so Migra-Eeze (328579) and Petadolex Pro-Active (293376) could not be assessed at all.

**The fix.** Several owned rows resolve only when the reviewed scope itself names the material and
exactly one row carries it. Anything the scope cannot tell apart stays unresolved, and a scope with no
discriminating terms still returns nothing — an unmatched row may never lend its amount.

Tests cover: one candidate; several candidates with one discriminated match; two rows matching the same
scope (unresolved); several candidates with no discriminating scope (unresolved).

## 3. Population applicability — NOT a matcher problem

Investigated before proposing anything, and the answer is that the pipeline does not hold the facts a
population gate would need:

- The canonical condition vocabulary (`scripts/data/clinical_risk_taxonomy.json`) is a **user-profile**
  vocabulary: pregnancy, lactation, trying to conceive, surgery, hypertension, heart disease, diabetes,
  bleeding disorders, kidney/liver disease, thyroid, autoimmune, immunocompromised, seizure,
  high cholesterol. None of the Wave 1 populations appear — no menopause, no diminished ovarian
  reserve, no adrenal insufficiency, no mild cognitive impairment, no diagnosed erectile dysfunction.
- The product side carries DSLD `targetGroups`, which is coarse and largely dietary:
  "Adult (18 - 50 Years)", "Gluten Free", "Dairy Free", "Women (not pregnant or lactating)",
  "Children 4 or More Years of Age". It cannot express "postmenopausal" or "IVF patient".
- `clinical_applicability.py` already validates and carries a free-text `studied_population` into its
  decision (line ~241) but never compares it — because there is nothing on the product to compare to.

**Conclusion.** A studied population is a property of the *person*, not the product, and a product-level
Evidence pillar cannot know the person. Building a product-side population gate would mean inventing
product facts that do not exist. Two honest paths remain, neither of which is a matcher change:

1. **Curation-time** (what Wave 1 did): evidence confined to a clinical population does not become a
   generic record. Isoflavones and DHEA stay held for this reason.
2. **Personalized layer** (already exists): `user_condition_alerts` and the app's profile conditions are
   where population-restricted evidence could honestly surface, per user — not in the product score.

No field was added. Recommend deciding path 2 as its own project, not inside evidence expansion.

## 4. Exposure/intervention compatibility — NOT a matcher problem

Linoleic acid's evidence is whole-diet substitution (7.5–20 g/day, or % of dietary energy) against a
measured label median of 362 mg/day. There is nothing to compare on the product side: every product in
this catalog is a supplement exposure. The distinction lives entirely on the evidence side, where the
Wave 1 contexts already record it (`exposure_basis`: supplement_dose, dietary_substitution,
food_matrix, fortification, infusion).

**Conclusion.** This is a curation-time eligibility rule — dietary-substitution evidence does not
become a supplement-efficacy record — and it is already enforced by the review packet holding linoleic
acid. Adding an exposure comparison to the matcher would add a field the product side cannot populate.

## Wave 1 re-run through the production path

`wave1_applicability_rerun.py`, read-only, against real products:

| identity | class before | class after | outcome |
|---|:--:|:--:|---|
| butterbur | B | **A** | the owner can now apply the proposed scope |
| ginkgo | B | B | still held — material + population + 4x dose gap |
| isoflavones | B | B | still held — population (no product-side fact exists) |
| dhea | B | B | still held — population/indication, no stated dose |
| gotu_kola | B | B | still held — positive result ~200x the label median |
| linoleic_acid | B | B | still held — dietary-substitution exposure |
| tribulus | B | B | still held — ED signal confined to diagnosed men |
| horny_goat_weed | B | B | still held — no qualifying efficacy evidence exists |
| dandelion | B | B | still held — no qualifying evidence; null diuretic trial |
| d_ribose | B | B | still held — null in the best source; null semantics pending |

### Butterbur detail — 29 products evaluated

**Newly applicable (3):**

| product | rows | why |
|---|---|---|
| 61929 Life Extension | Purple Butterbur CO2 extract, Petadolex form, 75 mg | 75 mg x 2 servings = the studied 150 mg/day |
| 204072 Nature's Way Petadolex | Purple Butterbur (Petadolex) 150 mg | label text itself names the studied material |
| 293376 Nature's Way Petadolex Pro-Active | Petadolex form 50 mg (+ a second butterbur row) | 50 mg x 3 servings = 150 mg/day; the second row no longer blocks linking |

**Still refused (26):** 24 `clinical_form_mismatch` (unspecified butterbur), 1
`below_applicable_clinical_dose`, 1 `clinical_source_row_unresolved`.

**False-positive canary — Migra-Eeze (328579).** It carries an unspecified butterbur row at 150 mg
*and* a Petadolex-form petasin row at 22.5 mg. The repaired owner links the Petadolex row and then
refuses it as below the 150 mg floor. It does **not** let the unspecified 150 mg row lend its amount.
That is the invariant this repair had to preserve.

**Class A is not approval.** Butterbur's owner decision remains HOLD on safety grounds: the AAN stopped
recommending it in 2015, and NCCIH reports rare liver injury even for products labelled PA-free.

## What changed

| file | change |
|---|---|
| `scripts/clinical_applicability.py` | `_resolved_identity_by_ref` + merge in `_rows`; multi-row resolution in `_linked_rows`; `assess_clinical_applicability` passes the scope's `required_form_terms` as the discriminator |
| `scripts/tests/test_clinical_applicability.py` | 6 tests: resolved-material visibility, source-required refusal, unspecified material refused at matching dose, second row no longer blocking, two matching rows unresolved, no-discriminator unresolved |
| `scripts/audits/evidence_expansion_2026_09/applicability_projection.py` | read-only before/after corpus projection |
| `scripts/audits/evidence_expansion_2026_09/wave1_applicability_rerun.py` | read-only Wave 1 re-run |

## Remaining architectural limitations

1. **Population-restricted evidence has no honest product-level home.** It belongs to the personalized
   layer or to curation-time refusal. Unresolved by design, not by omission.
2. **Exposure basis is evidence-side only.** Enforced at curation time; the matcher cannot help.
3. **Material scoping depends on enrichment quality.** The owner now trusts `form_id`/`matched_form`
   for non-source-strict scopes. That is one owner, but it inherits the enricher's mapping errors — the
   `two matchers over one label` risk moves rather than disappearing. Source-required scopes remain the
   strict option when a label must speak for itself.
4. **Multi-row resolution needs a naming scope.** A dose-only scope still refuses multi-row identities.
   That is deliberate; revisit only with a real case.
5. **Null-direction semantics remain open** and are deliberately not touched here.
