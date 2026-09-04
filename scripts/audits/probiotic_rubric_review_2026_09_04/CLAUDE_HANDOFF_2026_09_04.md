# PharmaGuide — Claude Code continuation handoff
> Cloud transport update: read [CLOUD_START_HERE.md](CLOUD_START_HERE.md) first.
> The operator subsequently authorized a WIP checkpoint push. This document
> retains the original pause-state findings; its uncommitted/local-only wording
> below is historical. The known RED and acceptance limitations still apply.

## Frozen 2026-09-04: implementation paused at the user's request

**This is not a completion certificate.** The current continuation is saved locally,
uncommitted, with one confirmed RED regression awaiting its production fix. The
latest botanical data correction passes targeted tests but has not yet had its
independent feature-worktree review or final corpus comparison.

The user is closing the laptop and handing continuation to Claude Code. Resume
task by task, fix root causes, preserve one scoring system, review actual changed
products, and hand the evidence back to Codex for an independent audit. Do not
claim that all clinical work, calibration, the submission AI pilot, or release
is finished.

## 1. Open the right checkout first

- **Implementation worktree:** `/Users/seancheick/Downloads/dsld_clean/worktrees/probiotic-evidence-coverage`
- **Feature branch:** `codex/probiotic-evidence-coverage`
- **Last committed HEAD:** `cea87d01512cc6e88acc13aa8212e26815bbd6d7`
- A fresh fetch during handoff showed HEAD and its remote feature branch at
  the same commit (0 ahead / 0 behind). **The continuation itself is NOT committed
  or pushed.** Read the dirty tracked AND untracked files; a fresh clone alone
  will not contain this work.
- **Manifest-owned product inputs / large reports:** the original checkout
  `/Users/seancheick/Downloads/dsld_clean`.
  It is an input location, not the implementation checkout for this task.
- **Unchanged old-code control:** `/Users/seancheick/Downloads/dsld_clean/worktrees/continuation-baseline.1ZPh87`
  at `cea87d01`. Do not modify it.
- Flutter repository: `/Users/seancheick/PharmaGuide ai`; no edits/imports are
  required by this immediate continuation.

IMPORTANT: a final reviewer accidentally inspected the original checkout rather
than the feature worktree. That review did NOT validate the newest botanical
patch. Check absolute paths before every test/review; old code in the original
checkout is not evidence that the feature changes are missing.

Read the applicable AGENTS.md and glossary. Use systematic debugging, test-driven
development, receiving/requesting code review and verification-before-completion.
Use explicit ownership if delegating. Do not revert concurrent changes.

## 2. Standing authorization and safety boundaries

Proceed with the approved engineering/evidence continuation and read-only impact
audits. Commit/push small reviewed batches to the FEATURE branch after green tests.
Do not merge main, run the operational corpus pipeline, rebuild/export a catalog,
upload to Supabase, import the Flutter bundle, publish, or change global pillar
weights in this continuation.

The latest approved request specifically keeps the expensive pipeline paused
until rubric review, evidence applicability and benchmark readiness are resolved.
The user will decide when to run that pipeline. No invented clinical sign-off,
study identifiers, constituent doses, strain allocations or AFU-to-CFU conversion.

Use `scripts/test.sh fast` for development, never raw pytest or system Python.
For non-test diagnostics source `scripts/python_env.sh` and use `PG_PYTHON`.
Use focused tests while iterating; broad fast once after the final corpus impact.
Do not run full/release suites alongside a pipeline. The release/full tiers are
later gates, not permission to start shipping now.

Treat lower scores as findings to investigate, not automatically safer/correct.
Do not tune toward Seed/SuppCo or restore old scores to make them look nicer.
Do not confuse missing review, null study results, safety, dose fit and quality.

## 3. What is already implemented

For the full historical ledger and per-task proofs, read:
- [EXECUTION.md](/Users/seancheick/Downloads/dsld_clean/worktrees/probiotic-evidence-coverage/scripts/audits/probiotic_rubric_review_2026_09_04/EXECUTION.md)
- [Frozen rubric review](/Users/seancheick/Downloads/dsld_clean/worktrees/probiotic-evidence-coverage/scripts/audits/probiotic_rubric_review_2026_09_04/README.md)
- [Prior verified engineering checkpoint](/Users/seancheick/Downloads/dsld_clean/worktrees/probiotic-evidence-coverage/scripts/audits/probiotic_rubric_review_2026_09_04/verified_execution_summary.json)
- [Measured alternatives](/Users/seancheick/Downloads/dsld_clean/worktrees/probiotic-evidence-coverage/scripts/audits/probiotic_rubric_review_2026_09_04/verified_shadow_summary.json)

The README is a PRE-implementation review. Its old counts and open items must not
override the continuation ledger or executable code.

### Prior committed checkpoint

- Corrected live-organism versus yeast extract / fermentate / heat-treated
  preparation identity boundaries. Exact EpiCor ownership works without granting
  generic fermentates branded or live-organism evidence.
- Added outcome/population/regimen-aware native study contexts and combination
  restrictions using the existing assessment, not a second matcher.
- Repaired benchmark document → parser → analysis contracts and reviewer
  provenance. AI-assisted/exposed ratings cannot become independent validation.
- Corrected unrated form explanations: no authored form rating is not proof of a
  cheap or poor form. Kept safety meaning separate from quality/confidence.
- Audited probiotic CFU/count/disclosure incentives and cross-pillar duplication;
  measured five sensitivity alternatives. **These are diagnostics, NOT installed
  replacement rubrics or approved weights.**

### Current UNCOMMITTED continuation

- Individually resolved the previously held preparation families: ten Airborne
  generic dried fermentates; Jarrow whole yeast extract; Garden Immuno-LP20.
  Preserved whole-preparation and separately disclosed constituent amounts.
- Removed conflicting generic fermentate aliases and an unrelated Spirulina
  citation. No new form rating, inferred CFU or blanket clinical approval.
- Unified final identity ID + registry + preferred name through active rows,
  quality rows and scoring projections. Invalid or safety-only identities remain
  required unresolved exposures; they cannot disappear from the denominator or
  borrow IQM quality.
- Preserved botanical source identities separately from isolated markers;
  whole seaweed is not automatically isolated astaxanthin/fucoidan/fucoxanthin.
- Corrected PHGG/Sunfiber preparation handling while retaining ordinary guar
  credit. Corrected Sunfiber AG description without inventing an FDA claim.
- Corrected title-head routing after “with/plus/&”; all three affected MacuGuard
  controls retain their legitimate prior results.
- Reused strict source-owned active selection for clinical evidence and adjacent
  enrichment collectors. Quantified children own their own mass; parent totals
  remain RDA/UL lineage, not substitute clinical doses.
- Bound green-tea evidence to the actual source preparation; excluded black tea,
  whole-leaf/matcha and caffeine/theanine transfers. Added source-verified exact
  EGCG spellings; preserved genuine extract controls.
- Failed synergy unit conversions now remain unassessed instead of comparing raw
  numbers in incompatible units. No guessed IU/activity/DFE/compound factors.
- Added Lpc-37 Sisu/ChillEx contexts with primary null outcomes distinguished from
  exploratory findings; approval remains pending. Current inventory is 16
  contexts across eight identities, **not a systematic review of all 49 entries**.
- Repaired four invalid/stale test fixtures without weakening production guards.
- **Latest additional fix:** source-declared Boswellia resin extract and cranberry
  fruit concentrate regain their existing family evidence joins. Corrected
  unrelated OA→stress and urinary→immune/cardiometabolic claims, verified
  enrollment counts, removed untraceable registry counts, removed an inappropriate
  whole-plant Boswellia UNII, excluded unstudied source preparations and isolated
  constituent aliases. No new generic clinical-dose thresholds or multipliers.
  This latest patch still needs independent review and final corpus measurement.

Research notes in the audit directory document each preparation, label and
primary source. Do not replace them with guessed identity equivalence.

## 4. Exact verification status at pause

| Check | Observed result | Meaning |
|---|---|---|
| Prior committed checkpoint fast | 13,174 passed / 167 skipped | Prior code only |
| Continuation broad fast, before fixture corrections | 4 failed / 13,453 passed / 167 skipped | NOT a passing backstop |
| The four-failure focused reproduction | 4 failed / 43 passed | Confirmed invalid/stale fixtures |
| Corrected fixture slice | 47 passed, 1.48 s | Tests only; production unchanged |
| New botanical join/scope/data tests before fix | 14 failed | Correct RED |
| Botanical + clinical applicability + green-tea slice after fix | 158 passed, 2.04 s | Latest data correction locally green |
| Current primary-source mass regression | **1 failed / 3 passed, 0.15 s** | Confirmed production defect, still unfixed |

No release/full run, operational pipeline, upload or Flutter import ran here.
Background implementation is stopped. No test or corpus job was left running at
handoff. The one failed test is deliberately preserved, not xfailed or deleted.

### Existing whole-corpus report: diagnostic, NOT current final acceptance

`/Users/seancheick/Downloads/dsld_clean/reports/probiotic_rubric_review_2026_09_04/corpus_preparation_continuation_accepted.json`

Despite its filename, do NOT call it accepted. It predates the latest botanical
data change and the newly discovered mass-comparison defect.

- SHA-256: `187f6d3a166d5943db589d3a30a5a3e611eee380182668f9d6fa3d895ef6184a`
- Complete: 15,415 products scored; 8,078 fully re-enriched from cleaned inputs;
  899.9 seconds; zero audit errors.
- Frozen provenance: 174 input files, 267 implementation/reference files and
  two runner files unchanged DURING THAT RUN.
- Transitions: 13 not_scored→scored; 15,091 scored→scored;
  180 scored→not_scored; 77 unchanged not_scored; 54 unchanged safety-suppressed.
- Resulting totals then: 15,104 scored, 257 not_scored, 54 suppressed.
- 170 retained numerical changes; 171 changed pillar sets; Formulation 80,
  Dose 44, Evidence 97. No retained Transparency/Verification/Safety changes.
- 85 retained tier / 34 verdict changes; no retained confidence changes.
- Three module changes overall: two persistently suppressed generic→omega
  (222857/297651), plus 219865 generic→fiber_digestive becoming not_scored.
  Do not report all three as persistently suppressed.
- Readiness is retained in deduplicated changes/canaries for 9,128 IDs; no scored
  readiness violation in those records. Do not generalize that explicit
  per-record audit to all 15,415.
- 4,599 changed report records include metadata; they are NOT 4,599 changed scores.

The 180 additional holds are 156 safety-only-primary identity cases and 24
EDTA/mannitol cases with no eligible source-active rows. Do not re-admit them by
dropping required rows or reusing a safety-rule ID as chemical identity.

Controls from THAT report (not promised final/shipped scores):
Seed 81.2, Culturelle 72.7, Garden 57.4, Fortify 63.6, Ritual 55.9, Jarrow
S. boulardii + MOS 62.4, Solgar 75.8. Exact IDs live in the verification artifacts.
EpiCor remains 44, which is not a clinically validated judgment of poor quality.
MacuGuard, ordinary guar, EGCG and FucoThin preservation controls also passed.

### Comparison lineage to reuse, not re-create blindly

Old-code complete report:
`/Users/seancheick/Downloads/dsld_clean/reports/probiotic_rubric_review_2026_09_04/corpus_preparation_control_cea87d01_source_owners.json`
SHA `7f77ae2b205c23578fe181469daac590f1caab3c9874b16f5b38fa4f8e671d6e`;
15,415 scored / 7,791 fully re-enriched / zero errors.

Supplemental old-code report:
`/Users/seancheick/Downloads/dsld_clean/reports/probiotic_rubric_review_2026_09_04/corpus_synergy_control_cea87d01_287.json`
SHA `7500857536bb299af031b9d23874c7e7837e828c5ba8222e6f4fd2b8085c6a52`;
all 287 extra labels have IDENTICAL numerical summaries to that control.
The 7,791 + 287 union is 8,078. Supplemental metadata changes are not score changes.

The earlier `corpus_preparation_continuation.json` is interrupted/incomplete.
Never use it as an accepted baseline. Other intermediate reports remain history.
The harness is
`/Users/seancheick/Downloads/dsld_clean/worktrees/probiotic-evidence-coverage/scripts/audits/scoring_applicability_2026_09_03/audit_corpus.py`.
It authenticates input/control lineage and must write a NEW output path.
It is a read-only audit using production scoring, not a second production engine.
Non-selected rows do not receive every enrichment lane (notably synergy);
expand clean selection whenever a changed producer requires it.

## 5. FIRST unfinished task: exact owned-total mass comparison

Open:
`/Users/seancheick/Downloads/dsld_clean/worktrees/probiotic-evidence-coverage/scripts/tests/test_evidence_primary_source_ownership.py`

Current RED proves that a source-owned 100 mg phosphatidylserine row receives the
existing primary evidence floor alone, but loses it when its own 500 mg complex
total is present. This is **not proof of inadequate clinical dosing**.
The source-ref numerator now uses the real child; `_active_mass_index` still
lets the structural total compete in the denominator.

**No runtime fix has been applied.** `generic_evidence.py` is unchanged.

Implement one lineage-proven physical-source comparison shared by the relevant
primary mass/canonical helpers. Preserve actual doses, source references, all
weights and cutoffs. Before choosing an interface, inspect current code/tests.

Must cover:
- 213475: original parent `ingredientRows[1]` owns PS child
  `ingredientRows[1].nestedRows[0]`. A duplicate synthetic
  `activeIngredients[0]` must be linked through the actual original tree,
  not same-name/canonical inference.
- 218600: reverse hierarchy—PS 200 mg owns its supplying 1,000 mg complex.
  Use positive lineage, not generic ancestor assumptions.
- 218838: 500 mg complex, 100 mg PS and 60 mg PC are siblings with no owner
  links. Do NOT invent linkage from canonical/name similarity. Inspect actual
  source label/producer; if proof is missing, keep an explicit unresolved item.
- Real separate 500/1,000 mg actives and unrelated opaque/protein aggregates must
  STILL compete with a trace active.
- Never drop all `product_level_evidence` because any individual dose exists:
  that would make a 100 mg vitamin falsely dominate 25 g protein.
- Retain valid `label_active_projection` rows and legitimate standalone blend
  evidence (e.g. Relora). No inferred dose for undosed children.
- One-source immutability and exact row ownership remain mandatory.

The saved test has one RED and three passing unrelated-aggregate controls.
Expand tests first, then minimal implementation, targeted real-label probes and
the final complete comparison. No skip/xfail/expected-number rewrite to hide it.

## 6. Then close the newly exposed evidence-review gaps

### Review newest botanical patch independently

Read the ACTUAL feature files:
- `/Users/seancheick/Downloads/dsld_clean/worktrees/probiotic-evidence-coverage/scripts/tests/test_botanical_evidence_reachability.py`
- `/Users/seancheick/Downloads/dsld_clean/worktrees/probiotic-evidence-coverage/scripts/data/backed_clinical_studies.json`
- `/Users/seancheick/Downloads/dsld_clean/worktrees/probiotic-evidence-coverage/scripts/audits/probiotic_rubric_review_2026_09_04/botanical_evidence_reachability_research.md`

Check same-row scope, wrong-part negatives, missing/derived-form bypasses,
branded-vs-generic boundaries, canonical alias reachability and all affected
real products. Exact match restoration is not dose/standardization equivalence.
Review the existing shared evaluator, not just JSON/test output.

Source traps already caught:
- Boswellin Super PMID 39092235: **150/300 mg tablets twice daily**, hence
  300/600 mg/day for 90 days—not 150/300 mg/day.
- Aflapin PMID 35512759: 70 randomized / 67 completed; 100 mg/day, 30 days,
  standardized to 20% AKBA. Do not import frequency/details from similarly
  titled 2011 PMC3198257.
- Boswellia review PMID 32680575: 7 trials / 545 patients; OA endpoints.
- Cranberry PMID 37068952: APRIL 2023 Cochrane review, 50 studies / 8,857.
  November update is a different identifier. No overlap sum with PMID 34473789.
- Live GSRS: cranberry UNII 0MVO31Q3QS is fruit/preparation; Boswellia
  X7B7P649WQ is WHOLE plant, not an extract-equivalence identifier.

### Other numerical changes need explicit dispositions

These lost matches have no executed applicability rejection; empty
`rejected_evidence` is NOT a reviewed scientific denial:
- Astragalus: 74595, 863, 222704.
- Echinacea: 260118, 318188, 200789, 206905.
- Ceylon cinnamon: 330605, 269403, 271345 (do not borrow Cassia trials).
- Fermented black garlic: 302657 (not automatically aged-garlic extract).

For each: verify exact preparation/outcome/source; add a bounded legitimate join
or explicit scope restriction where supported; otherwise log a genuine incomplete
review and do not describe zero credit as evidence of ineffectiveness. Do not
bulk add aliases to recover a previous score.

Additional Dose changes needing attribution: 304643, 33167, 257098, 304628,
223536. They appear to change assessment method, not printed amount.
**Cognigrape 304628** especially: source is grape FRUIT extract, not seed.
Removing borrowed grape-seed evidence is correct; check that its own botanical
still reaches the appropriate assessment and that B6/B12 do not misleadingly
supply the whole-product dose story. Do not infer new branded clinical evidence.

Already understood controls:
- Green Tea Complex 20009: 150 mg extract child, NOT 400 mg parent total.
  Diagnostic candidate 49.7 / Evidence 6.3; neither old 12.5 nor accidental zero
  is the source-correct result.
- Acai 293874 losing cranberry research is a mismatched-identity removal.
- GoL turmeric 204681/274457: existing evidence newly reaches explicit 500 mg
  Curcuminoids child, not a borrowed 1,200 mg parent.
- Astaxanthin 294487 domain correction does not prove 12 mg is clinically inadequate.

## 7. Engineering acceptance sequence

1. Finish source-total fix and bounded evidence/preparation reviews above.
2. Reproduce each defect RED; fix in the existing producer/contract, then GREEN.
3. Inventory every affected family across manifest-owned real inputs. Expand
   full-clean replay selection if the existing 8,078 misses changed branches.
   If expanded, obtain same-input OLD-code controls; do not attribute input
   freshness differences to a code correction.
4. Freeze runtime/data; run one NEW read-only full 15,415-product comparison using
   matched controls. Do not overwrite or relabel existing reports.
5. Review every numerical/pillar/status/route delta by cause. Keep reported
   denominators separate; score, verdict, tier and metadata are different.
6. Run broad `scripts/test.sh fast` after the corpus run. All current focused
   tests, including the saved RED, must pass. Investigate failures, don't weaken
   assertions. State skips and missing historical fixtures honestly.
7. Independent spec, code/data and numerical reviews in the correct worktree.
   Any correction invalidates relevant frozen hashes; rerun proportionately.
8. Produce a compact new final report, exact unresolved queue and updated
   EXECUTION ledger. Do not overwrite the prior checkpoint summary.
9. Review diff for secrets, generated output accidents, obsolete helpers,
   wrong-source identifiers, duplicate producers and inconsistent free text.
10. Commit small coherent tested batches and push the feature branch only.
    Fetch first; preserve concurrent work. Return commit IDs, tests, artifact
    paths/hashes and precise limitations for Codex's independent audit.

Do not claim zero bugs forever; require zero KNOWN unaddressed engineering
defects in the accepted scope, tested adversarial boundaries and named residual
clinical/policy work. Failure is a stop-and-fix signal, not a waiver.

## 8. Roadmap from engineering completion to actual release

### A. Clinical curation and coverage

Continue high-value native contexts (BB536, HN001, DE111 and exact commercial
formula editions), using the coverage reports rather than brand favoritism.
Finish or explicitly classify every material active in the benchmark.
One entry at a time: live identifier content verification; exact preparation,
population, outcome, dose/regimen, trial-family overlap, primary vs exploratory
results and source quality. Cache research before edits, update associated free
text, add negative controls, then measure affected products.

The current 16 contexts/eight identities are a bounded source review. New contexts
still need qualified clinical approval; old Dr. Pham approval does not approve
new content automatically. Not-yet-reviewed and reviewed-null must stay separate.
The 180 new identity/non-scoreable holds require their own source-backed
resolution or explicit intentional exclusion, not invented primary identifiers.
Unresolved synergy threshold units remain unassessed until individually verified.

### B. Choose the category rubric and fair consumer semantics

Use the frozen CFU/count/cross-pillar ledger and five measured alternatives as
inputs, not a replacement model to paste into production.
Decide and ratify which facts belong to Formulation, Dose, Evidence and
Transparency; do not automatically reward more CFU or more strains.
Research strength, dose applicability, safety and review completeness must have
distinct meanings. Decide how incomplete composites are labelled/provisional,
instead of letting our missing research look like bad product quality.
No unreviewed “authority floor,” hidden reweighting or target-score optimization.

Measure the full probiotic population and the seven named controls, plus
low-dose studied strains, high-count unreviewed mixtures and modest-count
finished formulas. A correct ranking change can go either direction.
No final clinical rubric approval has happened yet.

### C. Independent blinded benchmark

The parser/provenance repair is implemented; independent validation is NOT.
Ratify the reviewer brief/statistical plan, recruit the actual fixed three-rater
panel including at least two licensed clinicians, and preserve assisted historical
ratings as exploratory. Freeze the approved CURRENT candidate, labels and sealed
engine key before distributing packets. Keep owner/challenge design private.
Do not open holdouts or manufacture reviewer attestations.
Use `/Users/seancheick/Downloads/dsld_clean/worktrees/probiotic-evidence-coverage/scripts/audits/v4_reviewer_benchmark/pending_v7/README.md`
and the current benchmark code/contracts; inspect before issuing operational commands.

Analyze locked independent responses with the canonical tools. Only if supported,
propose category corrections or a separate global-weight calibration release.
Choose on prespecified reviewer agreement and robustness, not prettier tiers.
Clinical/policy/statistical ratification is human work, not an agent-generated stamp.

### D. Operational rebuild, compatibility and publication — AFTER approval

Once engineering, evidence/rubric decisions and benchmark gates are satisfied,
ask the operator to run the canonical batch flow once (verify CURRENT CLI flags;
do not paste historical ad-hoc commands). Include Product_Submissions and all
manifest-owned datasets; avoid a stale submission artifact/fingerprint.

Then verify sequentially:
- correct dataset manifests/reference hashes and freshness;
- exact raw-row reconciliation and full eligible mapping;
- typed dose/UL readiness and authoritative safety suppression;
- no incomplete/not_scored rows in the live catalog;
- stamped/recomputed scores, routes, pillars, statuses and verdicts;
- source-faithful low-dose flags, preparation/evidence matching and synergy;
- reviewer-approved delta report and explicit exclusions;
- schema/projection/Flutter fixtures, warning equivalence and import parity;
- release/full test tiers AFTER the pipeline, not concurrently;
- version/checksum/core/detail/image consistency, dry-run remote/import checks.

Do not bypass gates to avoid rerunning; use approved targeted resumability where
hashes/manifests permit it. Actual main merge/publish, Supabase writes and phone
import require the operator's go-ahead at that stage. Archive reports and verify
the promoted version independently. Later calibration must carry its own version.

### E. Separate product-submission Phase 3

The label-photo AI extraction pilot is an independent workstream and is NOT closed
by this scoring batch. It can proceed under its own approved plan: benchmark real
labels, dose/unit/nesting fidelity, hallucinations and reviewer correction time;
choose a cost-effective provider from measurements; drafts cannot approve products.
Do not confuse it with “Phase 3” of this scoring review or deploy it opportunistically.

## 9. Frozen changed-code fingerprints

These bind the pause state, not the older corpus report:
- backed_clinical_studies.json:
  `57717eb87239ede7362afd40725eee3da7324d684643108a90c4e5b9920f950e`
- enrich_supplements_v3.py:
  `44887ed1e391b3e3d5c2e5ca1608900d3ebe9d72ae455f88ba15f6cfc48362d6`
- scoring_input_contract.py:
  `a50cfccd3bf43df8f2a717d96abd2e3d358a54974555441fbc3440f67d3194dd`
- UNMODIFIED generic_evidence.py:
  `2b701ed5285d0449e9a6afc6ff4b75929b9dee40d47ca397480ffb8beff6f4cb`
- UNCHANGED global quality_score.json:
  `18b7ff59dc1c4baa4e89562492ffa9338491bb618da42e4044900f805beae9e1`
- unfinished source-ownership test:
  `a556bc57d172735cc819c405c81138cae36f737ba40e2cf546d94ee834fd34a1`
- latest botanical reachability test:
  `5702a394e34f937f0ba198ae5fe81dd1b80cccfe219a73345ec063bc3a1dfecd`

## 10. Return package for Codex's independent audit

Send: feature commit range; changed files; exact RED/GREEN and final fast results;
new full-corpus report and hashes; same-input baseline proof; categorized numerical,
route and quarantine changes; source research; remaining clinical/policy decisions;
and a list of commands/state mutations actually performed.

Codex should independently fetch, inspect each claim in the actual worktree,
reproduce targeted gates, verify report hashes and reject any unsupported
completion claim. That audit happens when the user returns/shares Claude's work;
nothing keeps running while the laptop is closed.
