# Legacy scope repair — the four null-direction records (2026-09-18)

Registry `scripts/data/backed_clinical_studies.json` 5.3.14 → **5.3.15**. Four entries repaired,
one at a time, each against its own live-fetched sources. **No scoring rule, weight, direction
multiplier or floor changed. No catalog rebuild, no release.** The null-direction multiplier stays
at 0.25 and is still a backlog decision.

## Measured impact

`scope_repair_projection.py` scores every product carrying a repaired record twice with the
production scorer (`score_product_v4`): baseline against the committed registry, candidate against
the repaired registry **with each product's embedded `clinical_matches` rebuilt exactly as the next
enrichment run would rebuild them**. Patching only the registry would have understated the repair,
because the scorer reads the match copy baked into the enriched product while the applicability
policy is read live.

| measure | value |
|---|---:|
| products carrying a repaired record | 2,446 |
| products scored both ways | 2,446 |
| **products whose Evidence changes** | **159** |
| products up | **0** |
| products down | 159 |
| mean Evidence delta (changed) | −0.90 |
| largest Evidence drop | −3.1 |
| largest total-score drop | −3.1 |
| products landing at Evidence 0.0 | 45 |

Changed by record: B12 74, boron 42, DIM 31, saw palmetto 15.
Changed by module: generic 129, multi/prenatal 20, fiber 6, omega 2, probiotic 1, B-complex 1.
2,287 of 2,446 are unchanged — a floor already sets their Evidence and the repaired record's points
sat below it.

**Every movement is downward.** That is the invariant this repair had to hold: removing a
misattribution may not manufacture credit. One draft violated it and was rejected — see boron below.

## 1. `INGR_VITAMIN_B12` — reference tier

**Was:** `systematic_review_meta` / `ingredient-human` / `null`, enrollment 200, tier_1, matching
2,176 products (1,640 multivitamin/prenatal). **Now:** `reference` / `reference` / `mixed`,
enrollment 6,276, tier_3.

Its sole source, re-fetched live: PMID 33809274 pooled **16 RCTs and 6,276 participants** in
*"patients without advanced neurological disorders or overt vitamin B12 deficiency"* and found no
effect on cognition or depression; only one study reported idiopathic fatigue, so no fatigue
analysis was possible. Stored enrollment was 200 — wrong by a factor of thirty.

That answer cannot be vitamin B12's ingredient-level efficacy direction across every product that
contains it. At reference tier the entry keeps the citation and states the question it answered,
and stops asserting a direction. Nutrient adequacy is untouched and **not duplicated**: it stays
with `nutrition_authority_floor` (10.0) and `rda_optimal_uls.json`. The NIH ODS Vitamin B12
Health-Professional fact sheet was added as the essentiality anchor after being read live on
2026-09-18 (the previous entry asserted what ODS says without citing it).

Also corrected: `endpoint_relevance_tags` was `glycemic_control`, and `key_endpoints` claimed
"nerve health ↑ / energy ↑ / CNS biomarkers ↑" — none of which the cited source supports.

**74 products change, all down** (mean −0.95, max −1.5); 2,102 are unchanged because a floor already
carries them. DSLD 252794 (Vitamin B12 1%, the 11.1/20 example) is **unchanged at 11.1** — the
nutrition-authority floor, not this record, was always carrying it.

## 2. `INGR_SAW_PALMETTO` — material and indication separated

**Was:** enrollment 833, six references, goal "Hormone Balance", tier_1, `permixon` alias.
**Now:** enrollment 369, three references, goal "Urinary Tract Health", tier_2, alias removed.
`rct_multiple` / `ingredient-human` / `null` unchanged — and now genuinely sourced.

Removed and documented as reviewed rejections:

- **PMID 29694707** — meta-analysis of the hexanic extract **Permixon only**; its methods state
  *"Articles studying S. repens extracts other than Permixon were excluded"* and it reports
  favourable nocturia and Qmax results. Material-specific; it may not lend a favourable result to
  the unspecified extracts these products contain.
- **NCT02121613 (PERLES)** — also Permixon, and the source of the stored 833 enrollment.
- **PMID 12006122** — an **androgenetic alopecia** trial of a botanical 5-alpha-reductase blend
  (LSESr plus beta-sitosterol, ten actively treated subjects) sitting on a record whose endpoints
  are AUA symptom score, IPSS, Qmax and nocturia. Off-axis on both indication and intervention.

What remains is exactly the generic-extract evidence: CAMUS (NCT00603304, n=369, null on AUA symptom
score at up to 960 mg/day over 72 weeks) and NCT00037154 (n=224). Enrollment now reads the largest
remaining trial, per the field's own convention.

**Not done, deliberately:** no form gate was added. Zero of 15,418 catalog products print
"Permixon", so a Permixon-scoped policy would gate nothing today; and 22 of the 138 matching products print saw
palmetto berry *powder* rather than the liposterolic *extract* the trials used (98 rows name an
extract, 23 are unqualified). That extract-vs-powder distinction is
a Wave-2 refinement, recorded here rather than built now. **15 products change, all down** (−0.1 to
−0.3, from the enrollment band).

## 3. `PRECLIN_DIM` — restricted to the material the trials used

**Was:** enrollment 62, category `metabolic_blood_sugar`, tag `digestive_health`, no applicability.
**Now:** enrollment 551, category `hormonal_endocrine`, tag `hormone_balance`, with a reviewed
applicability scope. `rct_single` / `ingredient-human` / `null` unchanged.

Both trials used **BioResponse DIM (BR-DIM)**, an absorption-enhanced branded complex:

- PMID 22075942 — 150 mg/day for 6 months in women with newly diagnosed low-grade cervical
  cytological abnormalities; **551 women analysed** (stored enrollment said 62), CIN2+ 9% vs 12%
  (RR 0.7, 95% CI 0.4–1.2), authors conclude DIM "is unlikely to have an effect on cytology or HPV
  infection".
- PMID 28560655 — 130 women on tamoxifen, BR-DIM 150 mg twice daily for 12 months; primary endpoint
  is a urinary estrogen-metabolite ratio, i.e. a biomarker.

The applicability scope now requires the source label to name `br-dim` or `bioresponse`, and excludes
`indole 3 carbinol` / `i3c`. Verified on real products through the production path: plain
"Diindolylmethane" returns `clinical_form_mismatch`, "Indole-3-Carbinol" returns
`clinical_form_excluded`.

**Consequence, stated plainly: the record now applies to zero catalog products.** Eleven products do
print BR-DIM or Indolplex, but those rows carry no resolved canonical id, so they never reached this
record and still do not — a normalization item, not an evidence one. This is decision class B
(valid evidence the architecture cannot safely apply): the record stays curated and honestly scoped,
and earns nothing. **31 products change, all down**, seventeen of them −3.1 to Evidence 0.0.

`evidence_level` was deliberately **not** promoted to `branded-rct` even though the material is
branded: the tier is identical in the pipeline (0.9) and would only raise this null record's
primary-evidence floor from 11.0 to 18.0. The branded material belongs in the applicability scope,
which is where it now lives.

## 4. `INGR_BORON` — two materials separated, and one rejected draft

**Was:** `observational` / `ingredient-human` / `null`, enrollment 30, four references, alias
`calcium fructoborate`, category `joint_bone`, endpoints claiming bone-turnover and inflammatory
markers. **Now:** `reference` / `reference` / `null`, enrollment 19, two references, fructoborate
alias removed and form excluded, category `sports_performance`.

Verified live, the four cited sources are **two materials and, on the boron side, one trial**:

- PMID 8508192 and PMID 7889885 report **the same trial** — 19 male bodybuilders, 10 on 2.5 mg/day
  boron and 9 on placebo for 7 weeks, same measures, "no significant effect of boron supplementation
  on any of the dependent variables". Two publications, one trial; the entry now says so.
- PMID 25433580 and PMID 24940052 are **calcium fructoborate**, a different compound, and positive
  on inflammatory markers and knee discomfort. Merging them let a plain-boron null speak for
  fructoborate products and a fructoborate positive speak for plain boron.

No cited source studied bone turnover, joint or inflammatory endpoints, so those `key_endpoints`
were removed. Eleven catalog products resolve to calcium fructoborate; verified through the
production path, they now return `clinical_form_excluded` while a plain "Boron" row still returns
`applicable`.

### The rejected draft

The first draft corrected `study_type` `observational` → `rct_single`, which is what the source is.
The projection showed that correction made the entry eligible for the primary-evidence floor and
**raised nine standalone boron products from Evidence 0.5 to 3.1** — a small null trial in
bodybuilders flooring a boron supplement at 3.1/20, because `_EFFECT_FLOOR_MULTIPLIER` credits
`null` at 0.25 inside the floor as well as the pipeline.

Falsifying the field back to `observational` to manage the score was not an option. The entry is
instead held at **reference tier**, the treatment `INGR_VITAMIN_A_BETA_CAROTENE` already carries:
real randomized sources that do not establish ingredient-level efficacy for what the products are
sold for. The source design is stated in `notes`, `key_endpoints` and the rationale rather than
misdescribed in `study_type`. Those nine products end at 0.0 instead of 3.1, and the projection's
rise column is zero.

**This is the clearest new argument for the parked null decision:** the null multiplier lives in the
floor too, so an accuracy fix anywhere near a null record can mint credit.

## Handoffs — routed, not written

`scope_repair_handoffs.json`. Nothing was written into another owner's files.

| handoff | owner | why it is not here |
|---|---|---|
| **DIM ↔ tamoxifen.** PMID 28560655: plasma endoxifen, 4-OH tamoxifen and N-desmethyl-tamoxifen all fell versus placebo (P<0.001) over 12 months. No DIM rule exists in `ingredient_interaction_rules.json` or `curated_interactions/` today. | interaction owner | A pharmacokinetic safety signal, not an efficacy direction. Severity, action wording, profile gate and alert copy are that owner's review. |
| **Indole-3-carbinol → canonical `diindolylmethane`.** 22 label rows printing I3C resolve to the DIM identity; I3C is DIM's precursor, a different compound. | identity / normalization owner | The DIM entry now excludes I3C, which protects that one record. The canonical conflation is unchanged and will reach anything else keyed on that identity. |
| **Nutrition-authority floor uses mass dominance.** DSLD 243259 carries 500 mcg B12 beside a 2 mg food blend, so B12 is not the mass-dominant active and the adequacy floor never fires; it ends at Evidence 0.0. | v4 scoring owner | Changing a floor is a scoring-rule change, which this project does not make. |

## Corrections to this project's own reports

`NULL_SCOPE_AUDIT.md` said saw palmetto matched **128** products and DIM **4**. Both were typed by
hand, not measured; the correct counts are 138 (137 outside the probiotic lane) and 46, and the
generated table in `GENERIC_EVIDENCE_NULL_DIRECTION_REVIEW.md` had them right all along. Both lines
are corrected in place with the correction noted.

## Verification ledger

| claim | command |
|---|---|
| all nine source abstracts re-read live before anything was written | `api_audit/pubmed_client.py` efetch on 33809274, 29694707, 12006122, 22075942, 28560655, 25433580, 24940052, 8508192, 7889885 |
| NIH ODS B12 fact sheet exists and states essentiality + RDA | read live 2026-09-18, ods.od.nih.gov/factsheets/VitaminB12-HealthProfessional/ |
| registry schema still valid | `python3 scripts/db_integrity_sanity_check.py` → 0 findings |
| every cited PMID still matches its entry | `python3 scripts/api_audit/verify_backed_studies_citations.py --strict` → PASSED, ok=460, mismatch 0, drift 0, not-found 0, 2 pre-existing acknowledged ghost-suspects |
| the four scopes behave as designed on real products | live `assess_clinical_applicability` probe: 205161 applicable, 278454/328296 `clinical_form_excluded`, 184988 `clinical_form_excluded`, 287472 `clinical_form_mismatch`, 294541 `not_curated` |
| catalog impact | `scope_repair_projection.py` → 159 changed, 0 up, 159 down |
| no regressions | `scripts/test.sh fast` → 15,749 passed, 66 skipped |

**Not touched:** the 34 `mixed` records, the `negative` multiplier, the `null` multiplier, every
pillar weight, the primary-evidence and nutrition-authority floors, and every other one of the 198
legacy records.
