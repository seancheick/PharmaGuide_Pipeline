# Batch 6 source and implementation receipt — 2026-11-12

Agent source review, not clinician approval of new wording or held decisions. Authority: F1/F3 in
`DR_PHAM_REVIEW_20261111.md`; remaining-work handoff supplied by Sean. Baseline `1890f4e2d`.

Owner: `scripts/data/curated_interactions/curated_interactions_v1.json` (pairs), `drug_classes.json`
(membership), `medication_depletions.json` (unpublished depletion); evidence: ownership matrix,
`rg` of these concepts and existing `DSI_MAGNESIUM_BISPHOSPHONATE`/`DSI_LEVODOPA_IRON`.
Will NOT create: new severity, public field, registry or alternate matcher.

## Per-entry source checks and outcomes

| Entry | Source content checked live | Result and limit |
|---|---|---|
| `DSI_ISOTRETINOIN_VITAMIN_A` | [Generic isotretinoin §7.1](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=4e8516dc-a3c6-4d8f-aa14-2c37c6c8f6e6), [ABSORICA §7.1](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=3ef0cff8-19c1-4441-b780-fca6c7ee1615) | Major/avoid, supplemental vitamin A and oral isotretinoin. Labels advise avoiding concomitant vitamin A supplements because of additive isotretinoin-associated reactions. Not foods or unrelated retinoid drugs. |
| `DSI_ISOTRETINOIN_BETA_CAROTENE` | Same label plus [NIH ODS vitamin A](https://ods.od.nih.gov/factsheets/VitaminA-HealthProfessional/) | Separate canonical beta-carotene record. Provitamin A is not preformed retinol. Major applies F1's avoid and no-automatic-exemption decisions to the separately represented precursor. No equal-toxicity claim or extrapolation to lutein, lycopene, zeaxanthin or astaxanthin. |
| `DSI_CALCIUM_BISPHOSPHONATE` | [FOSAMAX §§2.6/7.1](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=14e931fd-2c5f-4d90-b7db-5980706f4a56), [ibandronate tablets §§2.2/2.3/7.1](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=6ca94cce-a2bb-421f-bd8f-6b14bc2bd985), [ACTONEL §§2.6/2.7/7.1](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=24ed00e0-25e2-49a8-97fc-66c1b417dc0b), [delayed-release risedronate §§2.2/2.3/7.1](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=c89430be-15f1-4b8b-ab7e-738de716ee7d) | Moderate/caution. Alendronate before other oral medicines by at least 30 minutes; ibandronate tablets by at least 60 minutes. ACTONEL fasting 30 minutes and calcium at a different time of day; delayed-release risedronate immediately after breakfast and calcium at a different time of day. No universal interval. |
| `DSI_MAGNESIUM_BISPHOSPHONATE` | Same four labels: multivalent-cation wording and explicit magnesium supplement/laxative wording | Major → Moderate, with all drug/formulation timing made explicit. F3 calls for reviewing magnesium alongside calcium. Sean requested the Moderate change in the batch-6 handoff. |
| `class:bisphosphonates` | RxNorm current properties and related SCD/SBD concepts; [BONIVA intravenous label](https://www.accessdata.fda.gov/drugsatfda_docs/label/2022/021858orig1s023lbl.pdf) | Remove IV-only zoledronic acid from positive membership and explicitly exclude it. Exclude current exact IV ibandronate products; ingredient ibandronate also covers oral tablets. App precedence bug found: positive ingredient overrides exact product exclusion. Companion bridge fix is required before claiming IV scope qualified. |
| `DEP_CARBIDOPA_LEVODOPA_B6` | [SINEMET, effective 2026-08-01](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=9b17b028-964a-473c-823d-81423535bd66): pharmacokinetics, B6 deficiency/seizures, management of B6 levels | New source record, `needs_revision`, no B1 approval. Label supports possible B6 reduction, postmarketing deficiency-associated seizures, levels before/periodically during treatment and supplementation when low. It expressly permits initiating/continuing SINEMET with B6 supplementation. No onset interval invented. Severity/evidence/copy and exact combination hydration remain unpublished. |

## Identity checks

Live `https://rxnav.nlm.nih.gov/REST/rxcui/{id}/properties.json` verified:
6064 isotretinoin; 46041 alendronate; 115264 ibandronate; 73056 risedronate; 77655 zoledronic acid;
6375 levodopa; 103990 carbidopa / levodopa (MIN). Carbidopa resolves by name to 2019.
The four-pair verifier checks C0042839 vitamin A, C0006675 calcium and C0024467 magnesium through UMLS,
and resolves `ref:beta_carotene` through the canonical identity owner.

Brand name queries: Absorica 1299198; Fosamax 114265; Boniva 541684; Actonel 753143; Sinemet 36572.
Atelvia exact-name query returns no current brand concept. Its current pack 1020066 is Active in RxNorm
history, named `{4 (risedronate sodium 35 MG Delayed Release Oral Tablet) } Pack [Atelvia]`, with
ingredient 73056 and pack product 1020064. Approximate result 1086104 is NotCurrent and is not accepted.
These are live source-resolution receipts, not proof that every app autocomplete path resolves them.

Ibandronate's current related SCD/SBD concepts: oral 904932/904934/904936/904946; IV
904952 (prefilled syringe), 904954 (Boniva prefilled syringe), 904955 (injection). The existing exclusion
field carries the IV products. No exclusions are inferred from similar names.

The depletion uses the exact combination MIN 103990, not ingredient 6375. The Flutter checker compares
selected/generic/ingredient RxCUIs; not every hydrated product necessarily includes the MIN. That
activation question is expressly held, not papered over with a broader levodopa reference. The builder
filters non-verified records before app publication, with a regression proving this record absent and an
approved CoQ10 record still present. No B1 approval is copied from an unrelated record.

## Batch 6b dispositions, not new warnings

**Digoxin + calcium:** LANOXIN §7.3's calcium arrhythmia statement applies to rapid intravenous
administration. It does not establish the same interaction for oral calcium supplements. No oral pair is
added. [LANOXIN](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=d91e3646-4c63-4512-ab22-db39c085c4dc).
Confirm the disposition with Dr. Pham; this is not a declaration that every calcium/digoxin context is clear.

**Levodopa + B6:** no blanket B6 warning for carbidopa/levodopa; regression checks every curated shard and
B6 subject rule with iron as a positive medicine-identity control. Actual levodopa without a decarboxylase
inhibitor remains a separate clinical question. The handoff's INBRIJA example is not sufficient evidence of
that regimen: its [current FDA label](https://www.accessdata.fda.gov/drugsatfda_docs/label/2026/209184s013.pdf)
indicates it for OFF episodes in patients treated with carbidopa/levodopa. A single-ingredient inhaler does
not imply the patient's other treatment lacks carbidopa.

**Nitrates/PDE5 + arginine/citrulline:** keep exact medicine and ingredient questions separate. The
[VIAGRA label](https://dailymed.nlm.nih.gov/dailymed/fda/fdaDrugXsl.cfm?setid=ae2079a2-f3a9-4739-9611-0742b71e4761)
contraindicates organic nitrate/nitrite combinations; this does not itself make amino-acid supplements
equivalent to nitrate drugs. [Mayo's arginine guidance](https://www.mayoclinic.org/drugs-supplements-l-arginine/art-20364681)
warns of potentially excessive blood-pressure lowering with nitrates or sildenafil. Direct studied
combination data are more qualified: [a tadalafil/arginine randomized study](https://pmc.ncbi.nlm.nih.gov/articles/PMC7261690/)
reported tolerability in selected ED patients; a [four-trial synthesis, PMID 33587304](https://pubmed.ncbi.nlm.nih.gov/33587304/)
found no significant additional adverse-event burden versus PDE5 inhibitors alone. A
[small citrulline plus transresveratrol/PDE5 pilot, PMID 30150102](https://pubmed.ncbi.nlm.nih.gov/30150102/)
cannot isolate citrulline or establish broad safety. Recommend qualified prescriber-review consideration,
not a formal contraindication, equalization of all PDE5 drugs, dose cutoff or universal timing rule.
The precise warning/severity remains Dr. Pham's decision; nothing added to production by this batch.

**Activated charcoal:** [AACT/EAPCCT position paper](https://www.clintox.org/wp-content/uploads/2016/04/Position-Statement-Single-Dose-Activated-Charcoal-1.pdf)
documents drug-specific oral absorption effects at varied charcoal doses and elapsed times. The poisoning
treatment evidence cannot establish one safe separation interval for every medicine or every supplement
dose. Recommend medicine/formulation-specific review, with oral GI exposure distinguished from other
routes; do not issue a universal two-hour rule. No new consumer rule until Dr. Pham approves its scope.

## Verification

- Fail first: new batch file 5 failed, 1 passed; failures were absent pairs, IV member still included,
  magnesium Major and absent hidden depletion. The already-correct no-blanket-B6 assertion passed.
- After applying: 6 passed. Related owner slice: 510 passed (103.56 seconds).
- Final batch test rerun after exact IV exclusions and source-name cleanup: 6 passed (0.19 seconds).
- `data_batch.py check --since 1890f4e2d`: exactly four pair entries, one class, one depletion; zero problems.
- Four-pair live verifier initially 4 valid, 0 errors, 2 name warnings from `Isotretinoin (oral)` versus
  RxNorm `isotretinoin`; exact identity name corrected while preserving oral scope in management.
  Final live verification: 4 valid, 0 warnings, 0 errors. Python correctness: 0 new, 10 existing findings.
- Behavioral data. No corpus, release, installation, device observation or clinical approval claimed.
  Combined local/CI checkpoint and consumer qualification are integrator-owned.


## Consumer follow-up and independent review

Atelvia's supported app search is the current-concept query
`https://rxnav.nlm.nih.gov/REST/approximateTerm.json?term=Atelvia&maxEntries=10&option=1`.
Re-fetched 2026-11-12: its named current result is pack 1020066, after an unnamed atom;
`https://rxnav.nlm.nih.gov/REST/rxcui/1020066/related.json?tty=IN` returns risedronate 73056.
The app already retains the named atom and hydrates that ingredient. No Atelvia-resolution defect
was reproduced. The broad research query's retired 1086104 was not the app's supported search result.
An adjacent source-transcription defect was reproduced: decimal API scores were parsed as integers,
all became zero, and a lower-scored candidate appeared first. The existing RxNorm service now preserves
double scores; regression covers decimal ordering, named-atom retention and pack-to-ingredient hydration.
Existing integer-score compatibility remains tested. RxNorm plus hydrator slice: 39 passed; analyzer clean.

The companion class bridge now lets an exact selected/generic product exclusion override its inherited
ingredient class. A generic identity also listed as a combination ingredient does not suppress another
valid ingredient. IV-ibandronate fail-first regression failed, then passed; bridge/hydrator slice: 22 passed,
analyzer clean. This is source/test qualification, not proof of a rebuilt bundle or installed app.

The B6 source guard checks both pair orientations and all authored shards; hidden depletion is tested
through the actual artifact builder. Final focused source tests: 6 passed. A seeded app checker test
shows Sinemet plus B6 gives no result while the same medication plus iron yields the authored concern.
That node passed and analyzer is clean. The seeded test proves matcher behavior, not full catalog/device
absence; source census supplies the separate curated-data evidence.
