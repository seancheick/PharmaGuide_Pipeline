# Unread declared sources: 13 no-credit decisions (2026-11-13)

Receipts: one context per PMID in `source_finish_contexts.py`; applied by `apply_source_finish.py`.

| Record | PMID | Disposition | Main reason |
|---|---|---|---|
| BRAND_SETRIA | 24791752 | no credit | Glutathione body stores (exposure biomarker); Setria not named |
| BRAND_BIOCELL | 22486722 | no credit transferred | One positive OA trial; full text unread |
| BRAND_BIOCELL | 31221944 | no credit | Cosmetic skin endpoints in healthy women |
| INGR_LION_MANE | 18844328 | no credit transferred | 30-person MCI trial; benefit faded after stopping |
| INGR_INULIN | 35833477 | no credit | Microbiome surrogate; pooled preparations |
| PRECLIN_ASTAXANTHIN_GENERIC | 32755613 | no credit | Mostly null biomarkers; small or subgroup-only positives |
| PRECLIN_ASTAXANTHIN_GENERIC | 35091276 | no credit | Oxidative/inflammation biomarkers only |
| PRECLIN_ASTAXANTHIN_GENERIC | 38243785 | no credit | Fatigue rests on two studies; cognition not significant; exercise gains need training |
| INGR_BLACK_SEED_OIL | 21675032 | no credit | Seed capsules, no stated placebo, type 2 diabetes adjunct |
| INGR_BLACK_SEED_OIL | 37341696 | no credit | Small BP reductions; I² 84.7% / 97.3% |
| INGR_BLACK_SEED_OIL | 40210172 | no credit | Type 2 diabetes adjunct; several null outcomes |
| INGR_SEA_BUCKTHORN | 20554904 | no credit transferred | One dry-eye trial; mixed significance across ITT/PP |
| INGR_SEA_BUCKTHORN | 36043374 | no credit | Lipid effects only in abnormal-lipid subgroup; high heterogeneity |

## Method and checks

- No PMC full-text copy was found for any of the 13 (PubMed ID converter, 2026-11-13). Each decision was read
  from the live PubMed abstract and states only abstract facts; claims from the record's earlier
  2026-11-08 inulin review are labelled as such.
- Independent check: a fresh-context Claude agent re-fetched all 13 abstracts. It confirmed every
  number, record assignment and no-credit disposition, and asked for seven wording/provenance fixes
  (unsupported "sponsor-associated" and "contract research organization", "seed-powder", an earlier-review
  claim worded as abstract fact, omitted SOD/isoprostane and "marginally significant" findings). All were
  applied; a final self-review also changed "cognition is null" to "not significant".
- Agent review, not clinician review (review delegation, AGENTS.md, Sean 2026-11-06).

## Effect

- `assess_clinical_source_review` is now complete for all seven records.
- Products: 0 status or score changes in a 309-product main-vs-branch replay (249 held + 60 controls).
  The resolver treats an all-noncredit record as a hold unless it is reference-only
  (`evidence_resolver.py` noncontributing_complete, the 2026-10-28 register). Releasing these products
  needs a credit tier on the Evidence ladder or a decision to finish the record as reference-only (zero).
- Out of scope, held on purpose by a signed parent `scoring_eligible: false`: BRAND_THERACURMIN,
  PRECLIN_PQQ, INGR_LACTOFERRIN, INGR_COLLAGEN_PEPTIDES.

## Independent correction review — November 13, 2026

Codex source_review retrieved all13 new abstracts through live NCBI EFetch and verified the recorded quantitative findings. PMIDs38140277 and40276537 were additionally checked: acute randomized crossover trials, not reviews. Access wording states only that no PMC copy was found, not universal unavailability. Obsolete inulin/lion's-mane prerequisites were corrected while preserving unread Methods and applicability limitations.

Exactly seven records changed; all structured clinical fields, eligibility, directions and holds are unchanged. Both original and correction-only apply paths reproduce the registry in an independent in-memory check. Three fail-first regressions reproduced the defects; the source-finish file passes28 tests. Independent four-file correction diff SHA256:c54eaa0c76476052da4ee4b7d19d9c7edc58cd821be3f139816c92e2034d8e67. This closes factual corrections, not ingredient-tier consolidation or product release.

The source reviews retain positive limited findings (BioCell OA, lion's-mane MCI, inulin bowel function, astaxanthin exercise, black-seed diabetes/BP and sea-buckthorn dry-eye/lipids). Source-level no-credit decisions are not seven whole-ingredient zeros. Specific parent holds remain untouched.

## Psyllium authority source — November 13, 2026

Owner: INGR_PSYLLIUM_HUSK.references_structured, existing non-PMID authority-reference schema (BRAND_FORCEVAL precedent). FDA M007, posted May2,2023, retrieved/content-read by Codex and independent source_review: sections M007.10(f), M007.50(a), M007.52. PDF SHA256 ea8b654691f447fdedc5851e912c51bd066f186d75dbf35b1bd4836f57ebfa75. Official source URL is retained in the record. Recognition is for specified psyllium preparations and occasional constipation; specified granular forms are excluded and other monograph conditions apply. No general Dose, numerical credit or product compliance is inferred. The lipid context and its PMID remain unchanged; no invented PMID or nutrient-essentiality claim. Fail-first: missing authority reference. This is source retention, not20-point activation or completion of a new regulatory-authority scoring path.

## Ladder calibration — November 13, 2026

Accepted weak tier:5 Preliminary (Sean, explicit reply). Candidate fddc25c12 against e9896fc5e,
using18 frozen raw labels through Clean/Enrich/Score/Blob. Durable inputs, manifest, full records and
all-path differences are at `/Users/seancheick/pg_quality/evidence-close-20261113`.
All18 cleaned/enriched inputs and all non-Evidence pillars unchanged; safety and score status unchanged.
Assessment256990/328104 changes partial→complete through inherited blend completion, with the other
unreviewed-ingredients caveat retained.256990 crosses54.9→54.3 / Needs improvement→Poor;
293924 crosses85.6→90.0 / Very good→Excellent through nutritional authority.336897 is a mixed-purpose
formula despite its D3+K2 name, so it retains the mixed authority floor and pending assessment.
Psyllium remains0/pending; native probiotic and omega samples unchanged. Specifically signed glutamine
interpretation is retained (public10.4→8.5 from reference/floor calibration, not rewritten as a new grade).

Independent ladder_review found and reproduced two bugs: shared immune conversion5→5.9 and weak
efficacy plus exposure-only support6.5. Both corrected in fddc25c12; nine independent regressions pass.
Reviewer accepts the corrected source and full replay, not release qualification.
Controlled identical18 enriched inputs, one warm-up and three sequential runs per checkout:
baseline median2.908859s, candidate2.950555s (+1.43%); peak RSS194134016→193462272bytes.
Input SHA25656f9a3626cd986320906d62e8177f368ae26f4897248390802b7968d23fef95b;
all input objects unchanged. These bounded timings do not claim full-corpus throughput.

## First review queue triage — not activation

Independent source agents reviewed green tea38031409/19597519, maca20691074/25954318/36110519/36593713,
and citrus33141449. Limited preparation-scoped conclusions are supportable, but no grade has been
activated. Green tea's existing fat-oxidation attribution to19597519 is unsupported (that review measures
weight loss/maintenance); its older specific source/scope acceptance hold must be reconciled before
activation. Full38031409 reports heterogeneous preparations and low/moderate/very-low certainty by
outcome, not the abstract's blanket low-to-high description; included-source mapping remains separate.
Maca already has reviewed literature under maca_root, which the queue's maca identity does not reach.
Citrus has an incomplete applicability contract; drug-grade phlebotonics do not establish crude-mixture
benefit. No whole-family zero, preparation equivalence or clinical authorization is inferred here.

Green-tea correction: the October28 fourth/fifth signed rulings expressly retain source/scope
acceptance, and November6 routine-review delegation exempts that hold. INGR_GREEN_TEA now explicitly
sets scoring_eligible false; empty contexts, weak observed direction, references and preparation
boundaries remain. Unsupported energy/longevity/metabolic-rate/fat-oxidation wording and unrelated
endpoint tags are corrected to the reviewed weight/body-composition scope. Independent applied-diff
source review passes; exact one-record data_batch check passes;124 affected tests pass. Synthetic
preparation-matching fixtures explicitly supply synthetic eligibility; real-record tests retain the
hold and exact source-row guards. The earlier pending patch retains47 included-study PMIDs plus12
bibliography-only citations; this batch neither deletes nor newly certifies those mappings.

Green-tea six-label replay (2a3a1d985) independently reviewed: all inputs, Clean, exported blobs,
totals, pillars, completion states and safety unchanged. Only internal hold reasons change from
invalid applicability/no reviewed assessment to clinical_sources_ineligible. Scoped existing strict
citation verifier: four PMID claims pass, no mismatch, drift, ghost suspect or missing identifier.

Raw33canary pass identified10 stale expectations: five strong-floor totals -0.6, Boswellia moderate
-2.2, exposure-only creatine ethyl ester -0.2, and three unchanged-score blend completions. Current
owner probes identify KSM-66/CoQ10/beta-alanine15, Boswellia10, CEE2.2; no other frozen field changes.
Only those10 expectations are refreshed through the existing raw-input freeze tool, with causes in
the existing manifest changelog. Complete recheck remains the qualification result.


## PR477 authority-row review corrections — November 13, 2026

Two CodeRabbit findings independently reproduced after the initial green3a1d85543 checkpoint.
Owner: generic_evidence nutritional authority helpers, existing Evidence subject rows and prominent
source-row keys. Will NOT create a new clinical policy, public field or scorer. Class: behavioral.
An undosed Zinc blend member absent from ingredients_scorable was omitted despite a qualified
nutritional role. Separately, DL-Leucine could inherit full20 from L-Leucine through canonical-set
collapse. Both new regressions failed before correction. Eligibility and receipts now use the
Evidence subject collection with existing structural exclusions; full20 requires every purpose
row to qualify individually. Existing canonical-scoped mixed10 remains, including273823's
separately disclosed600mg Magnesium. No amount or preparation is borrowed for clinical credit.

401 owner/consumer tests pass;11 focused authority/receipt/derivation/isolation guards pass.
Independent review found a first-return fallback mutation alias; fail-first regression reproduced
it and established deep-copy semantics corrected it. Both prominent and fallback views derive
once per existing scoring scope; returned mutations do not affect input or later readers.

18 frozen raw labels through Clean/Enrich/Score/Blob against3a1d85543: public exports, totals,
pillars, completion and safety unchanged; Clean/Enrich unchanged. Only2219/Ravage internal metadata
now records the nondecisive10-point L-leucine nutritional floor, below its existing11.205 evidence.
Its obsolete zero-floor assertion is corrected while creatine-dose/source guards remain.
Final copy-isolation replay adds zero differences across all18 full records.

Same frozen18 enriched inputs and one warmup/three sequential timed runs: initial baseline median
2.987419s/RSS173637632; repeated baseline2.830703s/RSS202522624; final candidate2.873768s/RSS192004096.
Report observed variability, not a universal speed claim; no sustained regression observed. Input
hash56f9a3626cd986320906d62e8177f368ae26f4897248390802b7968d23fef95b unchanged. Independent final review
accepts source and bounded measurements. Fresh local and exact-head CI checkpoint pending.

Sean authorized PR477/236 integration and continuing work. App236 merged asb85aa7a8 and fetched
main contains qualifiedcbb20fe6. Pipeline merge waits for these corrected checks and review-thread
resolution. Valerian follow-up stays separately preserved at codex/evidence-valerian/f64572527.
No rebuild, catalog publication, installed-app delivery or release is claimed.

### Authority CI completion-copy correction

CI43523089618 shard5 exposed one old zero-credit copy pin for raw312894. Its
nine-amino-acid blend now retains the existing mixed nutritional-role floor10
(seven qualified undosed subjects; hydrochloride preparations do not qualify
for full20). It remains partial/not_yet_reviewed with the Evidence release
blocker.2505 remains0. Independent source/production review accepts the exact
score and blocker assertions; all73 A9 completion-scope tests pass. No production
change in this correction. f5 local checkpoint passed564 with24declared opt-ins.
