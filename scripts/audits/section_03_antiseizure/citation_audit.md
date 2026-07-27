# Citation content-audit — `medication_depletions.json` + `timing_rules.json`

**Date:** 2026-07-26 · **Method:** every PubMed URL in both files extracted, PMIDs
resolved live via PubMed esummary, title matched against the record's own
drug/nutrient claim. 87 citations across 59 records.

> This is **content** verification, not existence checking. The release gate
> `verify_depletion_timing_pmids.py` reported `valid: 87 invalid: 0` on this same
> set — every PMID resolves. A real PMID about the wrong topic is a *ghost
> reference*, and existence gates cannot see it.

## Ghost references — real PMIDs, unrelated content

Each of these is cited as evidence for a nutrient-depletion claim and is about
something else entirely.

| Record | Nutrient | PMID | What the paper is actually about |
|---|---|---|---|
| `DEP_ANTICONVULSANTS_VITAMINK` | vitamin K | 14506311 | Calcium channel antagonists and nicotine place preference in rodents |
| `DEP_OCP_MAGNESIUM` | magnesium | 23636014 | "Hypertension-related target organ damage: is it a continuum?" |
| `DEP_OCP_ZINC` | zinc | 23636014 | same paper, cited again for a different nutrient |
| `DEP_ANTIPSYCHOTICS_VITAMIND` | vitamin D | 25638514 | Oesophageal Doppler vs pulse-contour stroke-volume agreement |
| `DEP_ANTIPSYCHOTICS_COQ10` | CoQ10 | 18316143 | Microbial degradation of 14C-hexadecane **in soil** |
| `DEP_STIMULANTS_VITAMINC` | vitamin C | 10870150 | Methods of obtaining autogenous bone graft |
| `DEP_HIVPI_VITAMIND` | vitamin D | 21694637 | Biomarkers in eosinophilic esophagitis in children |
| `DEP_HIVPI_ZINC` | zinc | 12591569 | T2 relaxation time histograms in multiple sclerosis |
| `DEP_IMMUNOSUPPRESSANTS_MAGNESIUM` | magnesium | 16641596 | Pancreas-kidney transplantation timing |
| `DEP_IMMUNOSUPPRESSANTS_VITAMIND` | vitamin D | 19528952 | Microengraving to screen hybridomas for monoclonal antibodies |
| `DEP_BENZODIAZEPINES_MELATONIN` | melatonin | 2733455 | Philadelphia-positive chronic myelogenous leukemia |
| `DEP_BVITAMINS_INTERACTIONS` | zinc | 2132402 | Dietary omega-3 fatty acid manipulation |

**12 ghosts across 11 records, spanning 8 drug families.** Only the vitamin K one
falls inside Section 3.

## Borderline — on-topic but not evidence of depletion

Flagged for review rather than replacement; the paper is in the right subject
area but does not support the specific depletion claim.

| Record | PMID | Note |
|---|---|---|
| `DEP_NSAIDS_IRON` | 28242110 | "Peptic ulcer disease" — a general review; the iron-loss link is inferred |
| `DEP_STIMULANTS_MAGNESIUM` | 9368236 | Magnesium supplementation improving ADHD hyperactivity — a benefit trial, not evidence stimulants deplete magnesium |
| `DEP_BETABLOCKERS_COQ10` | 12392188 | Carvedilol inhibiting mitochondrial NADH-ubiquinone oxidoreductase — mechanistically adjacent, not a CoQ10-depletion measurement |

## Verified good (spot-checked, on-topic)

`DEP_STATINS_COQ10` (4 citations), `DEP_ANTACIDS_*` (all), `DEP_METFORMIN_*`,
`DEP_OCP_VITAMINB6`, `DEP_DIURETICS_*` (all — Sections 1 work),
`DEP_CORTICOSTEROIDS_*`, `DEP_SSRIS_SODIUM`, `DEP_LEVOTHYROXINE_*`,
`DEP_INSULINS_MAGNESIUM`, `DEP_ISONIAZID_VITAMINB6`, `DEP_METHOTREXATE_FOLATE`,
`DEP_COLCHICINE_VITAMINB12`, and all `timing_*` rules.

Sections 1 and 2 replaced their citations, and every one of those checks out —
the ghosts are concentrated in families that have not had a section audit yet.

## Section 3 replacement citations (content-verified against abstracts)

| Record | PMID | Verified content |
|---|---|---|
| VITAMIN D | 34847425 | *Impact of carbamazepine on vitamin D levels: a meta-analysis* (Epilepsy Res 2021) |
| CALCIUM | 15123011 | *Treatment of anticonvulsant drug-induced bone disease* (Epilepsy Behav 2004) |
| VITAMIN K | 16812962 | *Does vitamin K prophylaxis prevent bleeding in neonates exposed to enzyme-inducing antiepileptic drugs in utero?* (Can Fam Physician 2006) — **replaces ghost 14506311** |
| VITAMIN K | 8456897 | *Supplementation of vitamin K in pregnant women receiving anticonvulsant therapy prevents neonatal vitamin K deficiency* (Am J Obstet Gynecol 1993) |
| FOLATE | 6370643 | *Phenytoin-folic acid: a review* (Drug Intell Clin Pharm 1984) |
| FOLATE | 4175396 | *Impairment of intestinal deconjugation of dietary folate … megaloblastic anaemia associated with phenytoin therapy* (Lancet 1968) — the exact conjugase mechanism the record cites |
| L-CARNITINE | 8040784 | *Carnitine-dependent changes of metabolic fuel consumption during long-term treatment with valproic acid* (J Pediatr 1994) |
| VITAMIN B12 | 30896627 | *Effects of phenytoin on serum levels of homocysteine, vitamin B12, folate in patients with epilepsy: a systematic review and meta-analysis* (Medicine 2019) |
| BIOTIN | 9371938 / 9523856 | Mock et al. — biotin catabolism accelerated on long-term anticonvulsants (adults 1997 / children 1998). **Open question below.** |

### Open question — biotin scope

Section 3 moved BIOTIN onto `class:valproate`, but the two Mock studies enrol
patients on *anticonvulsants* generally (historically carbamazepine, phenytoin,
primidone cohorts). If they do not measure valproate specifically, citing them on
a valproate-scoped record is imprecise and the scope decision needs revisiting —
either widen the record, or keep it valproate-scoped and find valproate-specific
biotin evidence. **Unresolved: the drug-coverage check was interrupted.**

## The systemic fix this calls for

`verify_depletion_timing_pmids.py` is fail-closed on *existence* but blind to
*content* — which is why 12 ghosts shipped through a green gate. The durable fix
is a content gate: store an expected-topic assertion per citation (nutrient +
drug keywords) and fail when the live title/abstract does not contain it. That
turns "the PMID resolves" into "the PMID is about what we claim".

The interaction-rules file got exactly this treatment on 2026-07-02
(`verify_interaction_rules_citations.py`, 12 ghosts found and fixed). The
depletions file never did.
