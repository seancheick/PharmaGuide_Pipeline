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

## Queue reuse audit, ranks6–25 — November13 (read-only)

This is an owner/receipt inventory, not20 new completed reviews. Queue matching is heuristic and
misses several existing owners. No points or completion follow from this table.

| Queue identity | Existing owner / minimum remaining work |
|---|---|
| fiber | Form-specific Nov2 research exists; umbrella placeholder cannot inherit it. |
| isoflavones | First structured Evidence conclusion; distinguish named mixtures, foods and isolated compounds. |
| valerian | INGR_VALERIAN has a finished signed reference-only review; canonical reachability needs real-row verification. |
| 5_htp | INGR_5HTP exists, with source/applicability gaps; not a new literature search. |
| acai_berry | Existing pulp-source review; extract/powder applicability remains unresolved. |
| olive_leaf | olive_leaf_powder has Nov7 source review; canonical/form matching and remaining source scope unfinished. |
| nattokinase | INGR_NATTOKINASE review complete for exact NSK-SD target engagement; no generic preparation transfer. |
| lemon_balm | Existing source/access packet; Methods/membership/preparation qualification unfinished. |
| chamomile | Existing sleep-source packet; retain oral versus inhaled-oil boundary and reconcile anxiety wording. |
| pine_bark_extract | BRAND_PYCNOGENOL exists; generic placeholder cannot inherit branded findings. |
| fenugreek | Reuse Nov10 review; quantitative source reconciliation and proprietary preparation scope unfinished. |
| black_cohosh | Specific signed A048 hold persists; stale favorable-safety copy conflicts with retained source correction. |
| green_coffee_bean | Existing Nov4 packet; conflicting syntheses, source integrity and standardized preparation scope unfinished. |
| pumpkin | Existing source separates whole seed and extract; actual seed/flesh/oil/extract rows need scoped assessment. |
| chlorella | Specific signed A056 hold persists; comparative-strength/universal effective-dose wording needs correction. |
| dandelion | Related dandelion_root owner cites a fresh-leaf pilot; no blanket canonical alias or root efficacy transfer. |
| yohimbe | Existing Dose-only source/authority review; finish Evidence separately and preserve safety restrictions. |
| astragalus | Existing source-specific hold and heterogeneous immune-marker findings; no generic protection activation. |
| st_johns_wort | Specific signed A113 hold persists; exact extract/population acceptance and independent safety rules remain. |
| oi_beetroot_powder | Existing literature and INGR_BEETROOT sources; verify preparation correspondence before joining owners. |

Receipts: held_source_closure_20261028 patches and DR_PHAM_RULINGS, evidence_review_batch1_20261102
research, evidence_backed_970_20261104/decisions/green_coffee_bean.json, and current clinical/literature
verification provenance. The source agents rechecked live content for16039414/25196580/19678785/
37952511/29037431 and NCCIH yohimbe; other source-access histories remain dated receipts, not new
retrieval claims. Prior valid research must be reused, while its unfinished applicability stays honest.


## Valerian identity and completed-review wiring — November 13, 2026

Owner: IQM `valerian` aliases/match rules, `EnhancedDSLDNormalizer` authored exclusion,
`SupplementEnricherV3::_match_quality_map_impl`, and existing `INGR_VALERIAN.canonical_id`.
Will NOT create: a chemical registry, new marker policy, new review disposition or clinical grade.

FDA https://precision.fda.gov/uniisearch/srs/unii/34NDB285PM and NLM
https://meshb.nlm.nih.gov/record/ui?ui=C037133 independently identify valerenic acid as the
C15H22O2 constituent, not whole valerian root. Main and independent receipt agent read both.
Four chemical aliases no longer establish root identity. Existing parent-local form clues remain
scoped to an already identified root. Exact material exclusions reject isolated chemical names;
root notes retain their full ingredient context. Other-ingredient salt exclusions retain their
original independent-note semantics. A stale cleaner root identity cannot override the authored
chemical exclusion during Enrich. No blanket constituent-to-marker reclassification was added.

Eight initial cases failed before correction; an independent reviewer then reproduced root-note
identity loss, which was fixed. Expanded controls cover singular/plural/preparation labels, with
and without the verified UNII, misleading ingredient groups, stale Enrich identities, preserved
mass, valid root notes and conflicting material notes. Owner/marker/safety slice123 passed;
identity integrity124 passed; resolver/cache/form consumers523 passed. Additional final cache and
UNII controls are recorded in the durable receipts.

The existing INGR_VALERIAN source review is already reference-only/closed_no_credit, authorized
under the October28 BRIEF and retained patch. Source33086877/PMC7585905 was re-read live by main
and an independent agent. Its pooled sleep result is not significant; a whole-root subgroup is
not a universal efficacy conclusion. Only the missing canonical link is added; the existing
context, reviewer/provenance limitations, source scope and zero-credit decision are unchanged.
Three resolver regressions failed before that link and pass after it.

Five frozen raw products:12853,213353,328079,333775 and creatine control184096. Identity correction
keeps actual root warnings/actions/severities and removes only false chemical attribution.
328079/333775 have nested constituent disclosures, not standalone chemical supplements: existing
role handling leaves those rows active/unresolved, so both become not_scored with incomplete
safety assessment. This conservative hold is explicit and constituent-role handling remains open.
Canonical wiring completes root-only12853/213353 at unchanged scores55.4/57.9 and unchanged safety;
chemical-containing products remain held. Independent full-record review accepts these effects.

Performance investigation reproduced11082 redundant static-name expansions on a repeated unresolved
lookup. Existing variant derivation is now a bounded pure string-to-immutable-tuple cache; matching
order and row-specific exclusions remain live. Warm sodium-alginate/alginic-acid controls pass.
The five-label full Clean/Enrich/Score/Blob replay is exactly unchanged by this optimization.
One warmup plus three uncontended runs: baseline median0.455770s; initial correction1.111928s
(rejected); final0.450986s. Peak RSS442236928→382664704bytes. Frozen raw input hash
27d1a9db98da890dc5e4ffe6dcf11b49810bfba27373e37aa605913697855b81; fresh input copies per run.
This bounded measurement does not claim corpus-wide speed. Final local qualification passes564 tests/24 declared opt-in skips in146.73s; skip guard passes.
These follow-up changes are not covered by the already-green PR477 SHA3a1d85543.


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


## Black cohosh and Chlorella source corrections — November 13, 2026

Owner: existing INGR_BLACK_COHOSH and INGR_CHLORELLA records in backed_clinical_studies;
will NOT create a grade, Dose benchmark, registry or new clinical determination. Behavioral
source-transcription/existing-hold enforcement batch. A048/A056 verification and October28 fifth
ruling retain specific holds. Parent scoring_eligible=false now makes those holds explicit.

Main and independent source_review read live PubMed abstracts15565808,16039414,17565936,19609225,
29037431,35331862,23234816. Black-cohosh copy now distinguishes uncontrolled improvement, a null
whole-population primary analysis with positive subgroup, active-comparator/33%attrition, and
12-month placebo-null findings; universal safety/regimen claims removed. Chlorella copy retains
biomarker findings while identifying subgroup limitations, unequal metformin doses in the adjunct
trial, null lipid outcomes and modeled dose-response limitations. Unsupported longevity goals and
muscle-recovery attribution removed. Historical effect directions, all references, NCT inventories,
Dose semantics and empty contexts preserved; no aggregate trial/enrollment validation claimed.
Both record update dates reflect November13. This is agent source review, not clinician review.

Four regressions failed first;472 source-owner tests pass. Exact data_batch check proves only the
two named records changed. Scoped strict citation verifier:7claims/7PMIDs pass,0mismatch/drift/ghost
or missing. Independent applied-diff review passes. Seven frozen labels243701,338997,251578,311326,
273825 plus312587/293955 controls: public blobs, scores/pillars/status/safety unchanged; five affected
labels only change internal hold reasons, two controls unchanged. Last_updated metadata corrected
after this replay; final combined candidate qualification remains pending. No products released.
Durable receipts and exact apply script: cohosh-chlorella-* under the existing evidence-close folder.
### Authority CI completion-copy correction

CI43523089618 shard5 exposed one old zero-credit copy pin for raw312894. Its
nine-amino-acid blend now retains the existing mixed nutritional-role floor10
(seven qualified undosed subjects; hydrochloride preparations do not qualify
for full20). It remains partial/not_yet_reviewed with the Evidence release
blocker.2505 remains0. Independent source/production review accepts the exact
score and blocker assertions; all73 A9 completion-scope tests pass. No production
change in this correction. f5 local checkpoint passed564 with24declared opt-ins.

### Valerian explicit constituent disclosure — qualified locally

Owner: Clean::_is_standardization_marker_row and existing standardized_botanicals;
Enrich::_derive_disclosed_marker_percentage now delegates existing max-not-sum
ratio and whole-word matching to normalization.py. Owner search covered matrix,
glossary and marker stems. No new registry, public field, tolerance or grade.
A private transient flag carries raw parent/child proof through existing flattening.
Clean additionally requires an exact registered child name, exact registered extract
parent alias, direct child, one identical serving basis, exact quantity operators,
explicit matching printed percentage and the existing parent mass bound. The
0.8% form-quality threshold is not used to reject a genuine0.3% disclosure.

Two source-disclosure regressions failed before implementation. Independent review
found three modified-name false positives; all failed first and exact-name matching
corrected them. Final owner/identity/Enrich/signoff slice:384passed in65.14s.
Five frozen full-label replays:328079 restores57.9/complete;333775 restores59.6
but stayspartial on separate Evidence review. Root and constituent amounts and all
interaction summaries unchanged; three controls unchanged. Final exact-name guard
adds zero artifact differences. Independent review accepts source and measured deltas.
Same five raw inputs, warmup plus three timed runs: median0.496126s/RSS442073088
before;0.488896s/RSS424476672 after; inputsha27d1a9db98da890dc5e4ffe6dcf11b49810bfba27373e37aa605913697855b81 unchanged.
No observed regression in this bounded measurement; no corpus speed claim.
Final seven-label cohosh/chlorella replay equals the earlier reviewed correction
across full records (zero additional differences). Receipts:valerian-marker-* and
cohosh-chlorella-final-* under the existing external evidence-close directory.

### Review queue ranks26–50 reuse screen

Read-only record/receipt triage is not25completed reviews. Most are unfinished
applicability or preparation-specific studies; explicit bromelain/saffron holds
remain. Psyllium was the strongest reuse hypothesis: stable full raw probes330038
(huskpowder) and76810(seedhuskpowder) already resolve through INGR_PSYLLIUM_HUSK
to reviewed human support and complete Evidence.17192 generic Psyllium correctly
stayspending because source-labelled husk is unresolved. No wiring defect found,
no new grade or schema change. Generic control is not verified whole seed.
Receipts:external psyllium-probe/stable.jsonl and full records. Queue is stale;
recompute only after integrated final rebuild. L-phenylalanine authority and
horsetail preparation-specific record reconciliation remain investigation candidates.

Combined follow-up checkpoint46bc015e6: `scripts/test.sh local` passes564tests,24declaredopt-ins in152.69s; skipguardpasses. PR478qualifies this source; exactCIpending.


## DOI and official-document source references (2026-11-13)

Sean approved extending existing review records to DOI-only papers and official authority documents.
Owner: `clinical_evidence_schema` source identity/provenance, `clinical_applicability` review and
preparation matching, `evidence_resolver` eligibility, and existing `references_structured` citation
projection. Evidence: source-pointer caller search and independent source-review seam audit.
Will NOT create: a registry, fake PMID, automatic authority tier, new Dose gate or parallel scorer.

`source_references` contains compact `doi`/`url` pointers; PMID pointers retain their meaning.
Aliases join only through the parent's explicitly declared references. Retraction, concern and
source eligibility holds follow aliases. Selected contexts project only their declared citations,
with independent copies; native recorded contexts retain their source pointers without credit.
Typed provenance identifiers must all be context-bound; a valid publisher URL may locate full text.
Independent review caught a foreign-PMID/invalid-locator loophole; regression tests failed first,
then passed after fixing the shared validator. No clinical records or numerical grades changed.

Validation: 1,252 named owner/consumer tests passed in 28.94s; Python correctness reports no new
findings. On 18 identical frozen enriched products, complete scored artifacts differ only by scoring
timestamps; no scores, safety, completion, warnings or citations changed. Warm median 2.8859s before
and 2.8641s after; peak RSS 197,918,720 vs 222,691,328 bytes. Both runs preserve inputs exactly.
The small single-process memory difference is recorded, not evidence of a sustained regression.
Receipts: `/Users/seancheick/pg_quality/evidence-close-20261113/source-refs-*` and `nonpubmed-*`.
Combined local and exact-branch CI qualification remain pending. This source-format batch alone does
not finish inulin or proline: exact preparation, guideline/exposure scoring and source-bound wording
still need their separate reviewed activation. The current PMID-only signed glutamine interpretation
is unchanged; native numerical DOI attribution is not activated by this batch.

### Source-reference qualification completed

PR479 head bdbbc4e5f90d370cb8304b6adef4177671a6fcbb passed all eight shards and Merge readiness
in run43530197799. Local checks:564 passed,24 declared opt-in skips,skip guard passed. Full raw
Clean→Enrich→Score→detail-blob comparison:18 products,zero changed records/paths. PR478 also passed
all eight shards/merge readiness on ec2a36d16 in43528681544. Main-integration approval requested for
both; neither has been released. PR477 and app236 are already merged under supplied approval.

## Exact Orafti GR authority review and wiring

Owner: existing INGR_INULIN study_contexts/applicability, clinical_applicability::qualifying_purpose_outcomes,
generic_evidence::_effect_direction_assessment/_primary_mass_floor and quality_score::_pillar_evidence.
Evidence: caller/config search, reviewed context selection, actual primary source and same-input probes.
Will NOT create: a registry, essential-nutrient classification, general inulin equivalence, new numerical
magnitude, Dose benchmark, ingredient amount gate or parallel source-selection rule.

EFSA DOI10.2903/j.efsa.2015.3951 full publisher opinion and live Crossref identity/title independently
read by root and research agents. Primary material Methods identify Orafti GR as native chicory with
mean DP10; the source does not establish equivalence to P95/HPX/Synergy1/FOS. Retained existing four
source contexts and parent mixed finding. The authority condition12g/day stays a source fact; Dose
remains separate. Known mixed findings and gas from27492975 remain;41233756 is separate FrutafitHD
same-use evidence, not exact-GR replication. The authority's unpublished2012 study may overlap the
later27492975 report, so this is authority credit, not added trial-count credit. No safety clearance.

The schema already recognized guideline hierarchy but purpose selection ignored it. A fail-first
regression now qualifies that hierarchy only in a guideline context. Existing source interpretation
joins DOI aliases and may select an existing magnitude through floor_key; exact context, canonical
source, source-row and review/hold qualification remain required. Only the explicit reviewed INGR_INULIN
context selects cap_total20; a guideline or brand name alone never supplies20. Multiplier-only signed
glutamine behavior stays unchanged. Public copy identifies the authority basis.

Independent review reproduced a conflicting same-source/use null context being ignored. Its regression
failed with20, then passed after the recorded-tier owner checked the existing qualifying-outcome view
for conflicting completed source conclusions. Independent follow-up ran8 controls successfully.
Focused guards cover record/source holds,pending review,non-authority role,unrelated preparations and
100mg versus12g Evidence equality. Complete current owner/consumer slice:1336passed28.23s.
Data_batch proves only backed_clinical_studies/INGR_INULIN changed.

No exact Orafti GR label was found in the current brand corpus search. Actual Jarrow307711 prints
Orafti Synergy1 and stays held; no current product is claimed released by this scoped review.
Full19raw replay preserves all scores,completion,safety,warnings and amounts. Expected differences:
config lineage fingerprints;307711 diagnostic source/preparation reason and rejected-match metadata.
Its quality remains59.4 and Evidence incomplete. Same18enriched inputs: warmmedian2.7864s→2.8346s,
RSS215891968→217432064,inputs unchanged. Receipt files:inulin-before/after,comparison,perf andtests under
/Users/seancheick/pg_quality/evidence-close-20261113. Combined local and exact-candidate CI pending.

The PubMed-wide citation CLI does not cover backed_clinical_studies; its unsupported-file response
is not a passed verification. The new DOI's live metadata and complete source content were checked
separately. Existing PubMed source facts/identifiers are retained; no API result was auto-applied.

Inulin combined local checkpoint:564passed,24declaredopt-ins,142.89s;skipguardpassed. Final diff clarifies that unspecified retail preparation transfer remains unestablished; the new exactGR authority scope is separate. ExactcandidateCI still required.

## Named Bimuno B-GOS review and citation repairs (November 13, 2026)

Owner: existing backed_clinical_studies::INGR_BIMUNO_GOS, clinical_applicability source/preparation
selection and generic_evidence positive_weak magnitude. Evidence: IQM/prebiotics owner searches,
primary Methods/Results and actual raw219289 label. Will NOT create: generic-prebiotic equivalence,
a new canonical, numerical scale, Dose benchmark, amount gate or safety conclusion.

Full primary30109908 explicitly identifies Clasado Bimuno B-GOS.91randomized,83per-protocol,
two-week crossover periods and two-week washout;2.75gpreparation/1.37gactiveGOS. Bloating,
flatulence/abdominal-pain between-group scores improve; urgency atweek2; stool/QOL/mood nulls.
No formal primary hierarchy is invented. Short duration, completer analysis, uncertain prospective
ranking and commercial/investigator overlap support Preliminary5 under the accepted rubric.
26218845 (40olderadults,10weekperiods) preserves biomarkers, increasedCRP and clinicalnulls;
19053980 is a finished abstract-only noncredit source decision preserving positive IBS findings.
Neither is counted as independent clinical replication. Root and two research agents independently
checked source identity, preparation, outcomes and limitations. All6scanned citations pass scoped
strictverification; this is not wholecatalogcitationclearance.

29raw Clean→Enrich→Score→blob comparison against33bef8568: actual219289 prints BiMuno900mg and
changes partial→complete with score82.4/Evidence16 unchanged (existing probiotic route). Synthetic
namedmaterial100/900/2750mg cases earn5; genericGOS/XOS/alphaGOS remain unresolved.294036/240067
remainpartial with unchanged15/16Evidence; pending-state diagnostics become explicit. All29scores,
safety/warnings, physical identity, amounts and nonEvidencepillars unchanged.18identicalenriched
performance2.836825→2.896323s median, RSS215941120→210190336; inputhashunchanged. Sourceowner slice
1968pass with2stale syntheticprebioticstatepins; those2nowpass, retaining nopoints and incomplete
source-row protections. Pythoncorrectness0new10existing. Local/CI qualification pending.

Two originalcitationblockers corrected separately: rice23782948 titleNBSP→space and BacoMind
DOI10.3923/jpt.2008.425.434 entry-scoped reviewedghost acknowledgment after officialpublisher
identitycheck.8tests and21claimstrictscope pass; no efficacy or clinicaleligibility change.

Maca is NOT activated in this batch. Its verifiedgelatinizedsource proposal is retained externally.
A proposed global exclusion-completion change failed21valid existing-zero controls and contradicted
ADR0007's namednontransfer rule; it was reverted completely. Existing finishedzero policy remains.
Maca's old maca_root literature identity and explicitly unfinished applicability inventory require
bounded owner reconciliation before its proposed context can safely activate. No generic/color/female
zero or benefit is inferred from that unresolved work. Receipts: evidence-close-20261113/maca-review,
prebiotics-review,bgos-before/after comparisons (baseline=maca-bgos-before),bgos-owners/local/citations.

Bimuno final local checkpoint:564passed,24declaredopt-ins,144.51s;skipguardpassed. ExactcandidateCIpending; no integration/release.



Bimuno CI43536465267 identified two valid regressions for275464, not stale test pins.
Owner: INGR_BIMUNO_GOS::applicability (parent and two reviewed source contexts); actual label
Acacia Fiber4g/Acacia senegal and IQM acacia-fiber identity establish distinct material from B-GOS.
Independent source_review verified the material exclusion; official identity reference:
https://eur-lex.europa.eu/legal-content/en/TXT/?uri=CELEX%3A32026R0196 (E414 specification).
Explicit acacia fiber/acacia gum/gum arabic/Acacia senegal nontransfer uses the existing excluded-form
owner and ADR0007 finite zero. Required Bimuno term and its source findings remain unchanged.
Fail-first2fail/1pass; unchanged real-label tests plus Bimuno controls8pass; four alias edgecases
and named/generic controls10pass. Exact one-entry data_batch check passed. Two frozen fullraw/blob
replays:275464 remainspartial53.4 due to other unfinished Evidence but Acacia review correctlyfinishes;
219289 remainscomplete82.4. Safety/warnings/amounts/identity/Dose unchanged; only reviewed-state and
clinical-record metadata differences. Independent raw/diff review approved. Local/CI rerun pending.
Receipts: evidence-close-20261113/acacia-fix. No new canonical, clinical policy or warning.

## Scoped maca and glucomannan reviews (November 13, 2026)

Owner: backed_clinical_studies::INGR_MACA / INGR_GLUCOMANNAN, literature_evidence_records::maca,
and existing context_effect_direction_interpretations; owner searches and source receipts retained
in next-review. Will NOT create: a canonical, grade, Dose gate, registry or safety conclusion.

Maca36593713: verified gelatinized material,88randomized/80completers, approximately5g/day12weeks;
AMS positive, secondary IIEF/IPSS positive, testosterone null. Preliminary5 with preparation and
population boundaries. Four earlier literature source reviews preserved; canonical maca_root aligns
to actual maca identity. The existing unfinished applicability inventory remains open for excluded
preparations/populations through the bounded resolver correction, not a new maintenance-citation hold.

Konjac glucomannan: full EFSA1258 DOI10.2903/j.efsa.2009.1258 cholesterol conclusion receives the
accepted authority20. General-population scope,4g/day source condition retained without a new
Evidence dose gate or Dose benchmark.2017/2024 lipid reviews retain positive/null/low-certainty facts;
2014 weight null and GI effects retained. Parent mixed remains; no invented enrollment or study count.
Independent source and raw-output review completed. Actual reviewer is agent, not clinician.

Qualification:1996 owner tests passed with3 diagnosed issues subsequently fixed;25 follow-up passed.
10 scoped citation claims passed; Python correctness0new/10existing. Local564passed,24declared opt-ins
in144.17s; skip guard passed.32 frozen raw records replayed: gelatinized204624/273735 gain5 and finish;
306225 glucomannan gains20 and finishes. Extract/black/red maca stay held. Safety, warnings, amounts,
identity, Dose and other pillars unchanged.18 identical enriched performance median2.761951→2.813728s,
RSS217759744→218120192; inputhash unchanged. Receipts: next-review/scoped-reviews-*.
CI pending. Separate Bimuno/acacia regression found in481 remains under repair; no integration/release.



## Soy extract and psyllium authority batch (November13)
Owner: existing INGR_PSYLLIUM_HUSK and new reviewed entry INGR_SOY_ISOFLAVONES in the existing
registry; generic_evidence context interpretation; existing source-form applicability. No new
canonical/registry/grade, dose gate or safety conclusion. Root and independent agents verified
full Nahas17913408/Taku22433977 and FDA M007; source receipts under next-review.
Soy source17913408 supports Preliminary5 for the reviewed soybean-isoflavone extract class;
parent mixed retained with eight sources, nine scoped contexts. Hot-flush positives separate from
lipid/vaginal nulls, newer mixed/null symptom evidence, depression null, composition-dependent bone
findings and Alsitan combination.80randomized/76completers,2GIwithdrawals,9/10monthdiscrepancy,
100mg reported isoflavones/250mgextract retained without aglycone conversion or brand/%gate.
Independent overmatch probes failed5cases before tightening source-owned extract+soy+isoflavone
requirements and explicit material exclusions. Source notes on actual269819 bind extract to its
own row; unrelated rows cannot lend it.16final scopedtests pass; independent boundary reviewaccepts.
FDA adult husk authority20 coexists with unchanged lipidreview; granular/pediatric/whole-seed
boundaries and unread18985059 remain. Code membership correction is separate4accd14ab.
37raw fullartifact/blob:33003886.4→91.4 and7681079.4→84.4 (Evidence15→20,alreadycomplete);
soy1055partial→complete at unchanged67.6/Evidence15;269819 alreadycomplete75.6/Evidence20unchanged;
genericpsyllium17192held0unchanged. Safety/warnings/identity/amounts/Dose/otherpillars unchanged.
18same-input performance2.861568→2.866558s(+0.17%),RSS216186880→215826432,hashunchanged.
1651ownerspassed with1stalepsycontext-count assertion; corrected to preserve unique lipid-source
review and unreadsource guard;16followups pass.16soy source-ID claims (8PMID+8DOI) strictpass aftertwo title-copy
corrections;31psyllium source-ID claims passed earlier same-run check. Python0new10existing; exact2dataentries.
Final local/CI and inherited PR482three stale testpins remain to qualify; this is not integration
or release. Title-only final punctuation corrections postdate rawsnapshot and do not alter findings.
### PR 481 integration review corrections (November 13, 2026)

Two independently reproduced review findings were corrected before approved integration.
Owner: `evidence_resolver.py::_held_clinical_source_ids`; evidence: `rg -n
'_held_clinical_source_ids|reference_source_ids' scripts/evidence_resolver.py
scripts/clinical_evidence_schema.py`. Will NOT create a second identifier parser or
relax affirmative source identity. A held reference with a valid PMID and conflicting
DOI/URL metadata previously lost its hold, even when the PMID remained in the declared
inventory. Six failing regressions cover eligibility, retraction and concern holds with
conflicting and malformed URLs. Each independently declared pointer now uses the existing
parser for holds; inconsistent composite references still cannot establish positive identity.

Owner: existing Bimuno context population and `clinical_applicability.py::assess_context_population`.
The retained primary Methods exclude pregnancy and lactation. The compressed wording
`Pregnancy/lactation ... exclusions` failed the lactation parser, granting 5 points on an
explicit breastfeeding target. Separate source-faithful exclusion sentences fix that case;
pregnancy and ordinary adult controls remain enforced. This is Evidence population scope,
not a new personal-safety decision. Only `INGR_BIMUNO_GOS` changed in the curated file.

Independent source/code review accepted both corrections. The three affected owner files
pass 1,022 tests. Exact before/after raw replay of 29 frozen real labels has zero differences
across cleaned, enriched, scored and detail-blob records. Counterfactual breastfeeding and
conflicting-reference cases exercise the repaired paths. Same-input 18-product timing is
2.975 to 2.966 seconds; inputs remained unchanged. Durable receipts:
`/Users/seancheick/pg_quality/evidence-close-20261113/bgos-review-fixes-*`.

The combined local checkpoint passed 564 tests with 24 declared opt-ins; the skip guard passed. Python correctness reported zero new findings.

### Chamomile source review (November 13, 2026)

Owner: `backed_clinical_studies.json::INGR_CHAMOMILE`, existing clinical-context
applicability and `quality_score.json::evidence_magnitudes.generic.context_effect_direction_interpretations`;
evidence: `rg -n 'INGR_CHAMOMILE|context_effect_direction_interpretations' scripts/data/backed_clinical_studies.json scripts/scoring_v4/config/quality_score.json`.
Will NOT create another registry, grade, status, dose threshold or safety owner.

The previously unread retained source PMID39106912 was recovered in full. Its ten oral
trials used heterogeneous preparations; five contributed to the PSQI pool, with high
heterogeneity and nine trials at high risk of bias. It does not establish universal sleep
benefit or anxiety efficacy. The unsupported legacy aggregate enrollment/trial counts were
removed; overlapping reviews are not counted as independent trials. Original structured
metadata for the retained source and its unchanged neutral Dose proof are preserved.

PMID19593179 supports Preliminary5 for the source-owned oral German chamomile extract
class under the accepted weak-evidence rubric. Root independently read the primary full
Methods/Results at https://pmc.ncbi.nlm.nih.gov/articles/PMC3600416/?uid=0c76b720a2a9as16 .
The small adult GAD trial had a marginal positive primary HAM-A comparison and nonsignificant
secondary comparisons. The 220–1100mg daily values are verified response-guided titration
levels, not separately randomized arms or a fixed general Dose benchmark. The existing
`not_applicable` dose basis avoids falsely recording discrete assigned arms. A prenatal-target
control confirms that the existing population owner rejects transfer; no new pregnancy policy.

The parent is mixed, not universally positive. Separate finished no-additional-credit source
contexts retain the null relapse primary endpoint (27912875), null controlled insomnia findings
(21939549), heterogeneous review (31006899), and inhaled-oil trial (39545336). Abstract-only
access is stated where full Methods were unavailable. Root and research agents performed the
review; no clinician authorship is claimed. Source_review independently checked the 2024 and
2011 full texts and applicability semantics; root supplied the independently read 2009 full text.
Roman chamomile, essential/leaf oil, isolated apigenin, powder and children do not borrow adult
extract credit. Existing separate oil holds and neutral Dose policy remain.

Eight new source/material/population cases passed after three positive-extract cases first failed
on the old record. The complete source-owner file passed514 tests before the inherited hold fixes;
531 combined source/config tests then passed, plus the prenatal control. The scoped live strict
citation check passed all13 source-identifier claims, with no title drift or unresolved identifier.
The unrelated all-citations script covers zero claims in this register and is not counted as proof.

Forty-seven frozen real labels were compared through Clean/Enrich/Score and detail blobs.
312872 and330559 gain5 and complete;79940 gains5 but remains partial for its separate unreviewed
plain chamomile row.321971 moves64.7→64.9 (Evidence5→5.2 under existing product aggregation)
and completes. Infant246009 completes with unchanged total82.4/Evidence16 from its probiotic:
chamomile is explicitly population-rejected and contributes no credit. No safety, warning,
identity, amount, Dose or other-pillar changes were found by root or independent review.
The 47-product same-input timing moves4.900→5.094seconds; inputs remain unchanged.
Receipts, source texts, raw captures, complete path comparisons and performance measurements:
`/Users/seancheick/pg_quality/evidence-close-20261113/next-review/chamomile/`.

Final inherited-fix replay equals the independently reviewed47-label candidate with zero complete-record/blob differences. Local checkpoint:564passed,24declaredopt-ins,143.82seconds;skipguardpassed. Python correctness:0new,10existing. Exact data_batch scope:INGR_CHAMOMILE only.

### Olive-leaf authority-copy correction (November 13, 2026)

Owner: `ingredient_quality_map.json::olive_leaf.forms[olive leaf extract standardized].notes`;
evidence: `rg -n 'EFSA-approved health claim|olive oil' scripts/data/ingredient_quality_map.json`.
Will NOT create a clinical authority rule, change form ratings or modify the approved consumer note.
Root and literature_receipts independently checked the official EFSA2033 identity and the
EU432/2012 olive-oil claim text. The regulation specifies qualifying olive oil; the former
leaf note incorrectly implied a leaf-extract authority claim. Replaced only that sentence with
an explicit oil-versus-leaf limitation. Source: https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?from=EN&uri=CELEX%3A32012R0432
and https://www.efsa.europa.eu/en/efsajournal/pub/2033 . The direct consolidated HTML page
returned a robot challenge; the official indexed/PDF claim text was available. This is a factual
attribution correction, not a new clinical recommendation or comprehensive legal-compliance review.

The new regression failed on the original sentence.47 affected IQM/source-note tests pass.
Exact data_batch scope is olive_leaf only. Four raw label replays (216776,212273,278237,185288)
show only the intended standardized-leaf notes in216776 changing, apart from known generated
timestamps; complete score/status/safety/identity/amount records are unchanged. Receipts:
`next-review/plant-batch/olive-copy-*` under the durable Evidence-close receipt directory.
