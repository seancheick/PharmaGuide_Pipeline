# Probiotic applicability and certification audit — 2026-09-03

This is a versioned scoring-correctness/rubric batch, **not a released catalog**.
It uses the existing v4 scorer and evidence registries. Global pillar weights
remain Formulation 20, Dose 20, Evidence 20, Transparency 15, Verification 15,
Safety/Hygiene 10. Scoring is versioned **4.4.0**, config
**1.1.0-probiotic-applicability**.

## What changed

1. Certification identity requires the relevant strength, named variant,
   population and dosage form. A brand-level resemblance cannot establish an
   exact product certificate. Ambiguous matches remain uncredited and auditable.
   This is checked in both directions: a base product cannot inherit an Immune
   variant's certificate, and Alpha/Ripped/Burp-less editions cannot inherit a
   base SKU's certificate. Explicit reviewed product-line authority remains
   separate from SKU identity.
2. Marketing wording contributes **zero Evidence points**. Existing research
   support contributes up to 12; reviewed dose applicability contributes up to 8.
   The study's effect-direction limit applies to its own credit. Adding
   “Digestive support” cannot increase a product's evidence score.
3. Dose and Evidence share the source-owned strain assessment. The old clinical
   `cfu_per_day` stamp cannot stand in for a label measurement. Explicit daily
   servings are applied; variable or missing frequency is not guessed. AFU is
   never converted to CFU.
4. An assessed complete formula owns the full Dose dimension. It does not imply
   known individual strain quantities or independently reviewed strain claims.
5. Within Transparency, pure probiotic strain-allocation opacity is counted
   once. Stable source references survive the cleaner/enricher/B5 boundary.
   Mixed prebiotic/botanical blends and unresolved owners retain their penalties.
6. PMID 41750436 is recorded as related mechanistic evidence, not independent
   symptom replication, prevention of antibiotic-associated diarrhea, or an
   automatic publication-count bonus. See [research.md](research.md).

## Six real-label comparisons

Before means the prior candidate at `bc98fe2d`, **not the old phone catalog**.
Each product was fully re-enriched from its manifest-owned cleaned label and
scored with the production scorer. No target score was chosen.

| Product / ID | Before | After | F / D / E / T / V / S after |
|---|---:|---:|---|
| Seed DS-01 / `PG_SUB_35E0BD3374BF494B80FEABE87FC559E7` | 69.1 | 81.2 | 20 / 20 / 10.2 / 12 / 9 / 10 |
| Culturelle Digestive Daily / `250851` | 80.7 | 72.7 | 12.5 / 13.7 / 8 / 15 / 15 / 8.5 |
| Garden of Life 100B / `326762` | 80.5 | 63.8 | 17.5 / 10 / 8 / 9.3 / 9 / 10 |
| Nature’s Way Fortify Optima 100B / `327965` | 76.7 | 69.0 | 20 / 8.5 / 8 / 14.5 / 9 / 9 |
| Ritual Synbiotic+ / `299239` | 69.0 | 61.8 | 14.3 / 9.5 / 8 / 11.5 / 9 / 9.5 |
| Jarrow S. boulardii + MOS / `307727` | 66.4 | 62.4 | 12.5 / 11.4 / 8 / 15 / 6.5 / 9 |

All six remain `scored`, SAFE, with moderate score confidence. These are
engineering outputs of the rubric, not measured clinical rankings or head-to-head
evidence of superiority.

[comparators.json](comparators.json) records every public pillar, consumer
explanation, raw dimension component and deduction before/after, clinical record
and cited study, source ownership/applicability, certification record, and
verification/trust contribution. Raw category dimensions use their existing
normalization; do not sum raw /25 dimensions as if they were public /20 pillars.

### Disclosure deductions: what is distinct

- **Label transparency:** the individual strain quantities are not disclosed.
  Named identities and aggregate potency still receive their existing credit.
- **Strain-specific dose assessability:** a known strain identity does not prove
  an unknown individual dose. Existing native CFU bands describe industry potency,
  not verified clinical efficacy. Contextual research is not stacked by the
  number of undosed strains.
- **Whole-formula applicability:** a reviewed formula and total dose can be
  assessed without inventing strain allocations. Seed receives public Dose 20/20,
  while Transparency remains 12/15 and Evidence 10.2/20.
- **B5 within Transparency:** only the second charge for pure strain allocation
  is removed. Seed's B5 falls from 2.3096 to 0. Fortify retains the plant-prebiotic
  B5 (0.5385); Ritual retains PreforPro (0.52); Garden of Life retains PreforPro
  (0.6667). Garden of Life's separate B2 claim penalty remains unchanged.
- Manufacturer violations, sugar/additive policy and safety deductions are not
  silently removed or reweighted in this batch.

## Evidence and confidence limits

Research exists outside our curated applicability data. Missing a reviewed
strain-dose/context reference is **not evidence of poor performance**. The new
explanations distinguish unfavorable findings, research with unestablished
applicability, and an assessed formula. Score confidence is separate; this batch
does not redefine it as a publication count.

The native registry's 48 industry CFU band records are not clinical dose ranges;
the remaining M63 clinical-basis record is not signed off. No trial ranges were
fabricated to raise comparator scores. Targeted curation of exact strains,
studied doses, formulations, populations and outcomes remains necessary before
claiming broader dose-applicability coverage. Species-level material, including
the current S. boulardii record, is contextual evidence—not proof that any
commercial strain matches a trial strain.

The shared registry scope classifier still treats missing specificity metadata
as general research. LGG is one documented example: its separate backbone has
strain-specific sources, but the native registry lacks that explicit scope
field. The wording identifies this as **our registry's classification**, not
a claim that strain-specific LGG literature does not exist. Resolving this
requires native-evidence scope/dose curation, not a blanket score increase.

The live backbone citation check covered 202 entries, 448 distinct PMIDs and
463 PMID-entry claims, with zero missing IDs/title mismatches/title drift. Two
pre-existing suspects have documented dispositions. That is identifier/content
screening, **not a fresh efficacy audit of every clinical claim**. Only the Seed
paper addition received the full clinical review described in research.md here.

## Verification and handoff

The final read-only replay completed **15,415 products**, including 217 fully
re-enriched, deterministic cross-brand/category canaries and every submission.
All other products had each changed producer lane recomputed before scoring.
Input and implementation fingerprints were unchanged throughout the run.

- **1,014 numeric scores changed**; one additional product has offsetting
  pillar changes, giving 1,015 material records in the saved diff.
- **Zero route or score-status transitions.** 15,284 stay scored, 54 remain
  safety-suppressed, and 77 remain not scored. These are audited input counts,
  not a newly exported live catalog.
- **Zero Safety/Hygiene pillar changes.** All 79 verdict transitions are between
  SAFE and the existing quality-driven POOR verdict (67 SAFE→POOR, 12 reverse);
  no BLOCKED/CAUTION/NOT_SCORED verdict changes.
- 477 probiotic and 537 other-product numeric scores change. Other-product
  effects originate in certification identity, not new weights or botanical
  evidence rules. Ten omega products also lose existing certification-dependent
  Formulation/Transparency floors; those couplings were not added here.
- Confidence changes on 104 products under the existing confidence formula.
  This batch does not award confidence based on publication count.

[verification_review_queue.json](verification_review_queue.json) preserves the
534 lowered Verification results, including confirmed false-credit removals and
unresolved registry identities. Forty products gain Verification credit from
supported matches. **An uncredited certificate is not proof of no certification.**
Unrecognized flavor wording, botanical additions, or an abbreviated registry
name may still need individual source-backed mapping. This is a curation/review
queue, not permission to bulk restore bonuses. No new certificate validity was
asserted beyond the existing registry snapshot and reviewed overrides.

See [verification.md](verification.md) for completed checks and open gates;
[corpus_summary.json](corpus_summary.json) and
[material_product_changes.json](material_product_changes.json) retain the
comparison hashes, distributions and all material deltas. Report generations
preceding the last certification correction are superseded; these tracked
reports use `corpus_impact_reviewed.json` (SHA-256 beginning `97570a38`).

The user owns the next operational rebuild:

```bash
bash batch_run_all_datasets.sh --stages enrich,score --skip-release
```

After that run, verify fresh snapshot/release gates before any publish. The
read-only impact audit does not replace that rebuild. Phase 3's AI-extraction
pilot can then proceed independently; global weight calibration still requires
the blinded reviewer benchmark and its own scoring version.
