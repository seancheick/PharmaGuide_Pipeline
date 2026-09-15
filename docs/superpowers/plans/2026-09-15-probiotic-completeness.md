# Probiotic completeness implementation plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan. Steps use checkbox syntax for tracking.

**Goal:** Implement the owner's approved count-neutral identity/Formulation
correction and verify it without rebuilding or publishing the catalog.

**Architecture:** Existing measurement/identity owners supply shared counts;
existing category modules and six-pillar assembler retain all authority.
Only the canonical scoring config owns weights and references. No new schema.

**Tech Stack:** Python 3.13.3; `scripts/test.sh fast`; existing frozen packets.

Spec: `docs/superpowers/specs/2026-09-15-probiotic-completeness-design.md`.
The owner explicitly requested prepare then implement; exact component math
and expected canaries were presented before implementation.

## Task 1 — shared label denominator and count-neutral Formulation

This is one tightly coupled production change. Use one implementation owner
for these files; no simultaneous worker edits to them.

Files:
- `scripts/probiotic_measurements.py`: shared label identity/count helpers.
- `scripts/enrich_supplements_v3.py`: replace private unique-name counter.
- `scripts/scoring_v4/modules/probiotic_dose.py`: consume count/key helpers;
  remove local duplicate counting/key logic, retain actual dose calculation.
- `scripts/scoring_v4/modules/probiotic_transparency.py`: same counts/keys;
  no credit for count-only/ID-only payloads.
- `scripts/scoring_v4/modules/probiotic_formulation.py`: ratio identity, remove
  CFU-size/diversity and corresponding AFU-size bonus.
- `scripts/scoring_v4/modules/probiotic.py`: current raw cap/documentation.
- `scripts/scoring_v4/config/quality_score.json`: version 1.6.0-probiotic-completeness,
  raw cap/category cap/reference all 16, public weights unchanged.
- `scripts/scoring_v4/config/config_fingerprint_history.json`: append new hash.
- `scripts/build_final_db.py`: component-derived identity bonus wording, never
  imply that identity proves efficacy or retain a removed size/diversity bonus.
- `scripts/GLOSSARY.md`: define completeness; remove stale count semantics.
- Tests: existing probiotic formulation/dose/transparency suites, native
  provenance, `test_probiotic_structured_form_identity.py`, studied formula,
  tradeoffs, config/version pins; add bounded
  completeness regression file if that keeps fixtures simpler.

- [x] Add red regression tests calling the existing modules. Required assertions:

  ```python
  assert single_identity_points == five_fully_identified_points == 8
  assert half_identified_points == 4
  assert species_only_identity_points == 0
  assert formulation_at_1_billion == formulation_at_50_billion
  assert one_measured_of_two_disclosure_points == 5
  assert count_only_named_identity_points == 0
  ```

  Use real registry names and source-owned label rows, not fake clinical IDs.
  Include aliases, duplicate projections, whitespace/malformed names, bool/
  fractional/nonfinite/negative counts, missing label list, stale lower/higher
  counts, unmapped names and species-general IDs. An unknown name must remain
  in the denominator; it cannot disappear because no registry match exists.
- [x] Run focused tests through `scripts/test.sh fast`; record genuine red failures.
- [x] Implement the shared counting boundary. Reuse
  `clinical_strain_identity_key`/`clinical_strain_identity_matches` and registry;
  do not build a new strain matcher. Only exact aliases collapse. The existing
  total_strain_count is derived, not a sourced declaration, so ignore it for
  scoring in either direction. A count with no labels creates no disclosure.
  Resolve source-local structured forms through the existing registry/label
  resolver before deduplication, independently of clinical projections:
  exact+species-only siblings with the same display name
  are two identities; two distinct proven forms are also two. Never share one
  owner's form with its sibling. Pass whole-product source context through
  all scoring callers and the assembled enrichment payload. Test existing
  BB536/HOWARU fixtures plus these exact/unresolved and distinct-form cases.
  Identity-only resolution stays in `studied_formulas.py`; native clinical
  rows and their stricter individual-measurement proof remain unchanged.
- [x] Apply raw formula `4 + 8 * exact/total + delivery + complement`, with
  missing components zero, penalties before clamp, maximum 16. Reuse source-
  owned exact matches and the same label identity keys in numerator/denominator.
  Keep the verified whole-formula AFU branch native and remove its old +5.
- [x] Align consumers, descriptions, config version/fingerprint and existing
  tests. Preserve regressions for all source/certification/chemical boundaries.
- [x] Run focused tests; review the full diff. Do not refresh locked final
  scores unless the measured change is attributable to this approved math.
- [x] Independent spec compliance then code-quality review; resolve findings.

## Task 2 — frozen-input evidence, report and commit

Files: reuse `scripts/audits/rubric_proxy_removal_2026_09_14/score_packet.py`
and `diff_packet.py`; extend the existing boundary-audit replay/report only
when necessary rather than inventing another scorer/harness.

- [x] Freeze baseline outputs for both existing packets from baseline commit
  before editing runtime code, or use an isolated exact baseline checkout.
- [x] Run current scorer against the same 111 + 79 frozen inputs. Verify IDs,
  hashes, finite real public scores and six pillars through the existing diff.
- [x] Read-only all-stored-probiotic comparison: same product input for baseline
  and candidate; count/refuse malformed batches; report corpus size, routed
  categories, score and pillar deltas, unavailable/stale inputs. This is not a
  fresh cleaned/enriched release. No output_* directories may be overwritten.
- [x] Confirm expected movements and invariants: no Formulation size gain;
  only count/identity fixes can affect disclosure; Evidence, Verification,
  Safety unchanged; unknown species not promoted; AFU unchanged in Dose.
- [x] Run `scripts/test.sh fast` on frozen code; do not edit during the run.
- [x] Record measured results and outstanding broader roadmap items. Commit
  implementation and push main after fresh fetch/review; preserve user files.
- [ ] Continue the broader roadmap in bounded batches before any regeneration.

Completed runtime: `41a7699e4840274debf25d4d0ae5a15cc79c8a31`.
Final fast suite: **15,492 passed, 66 skipped**, zero failures (458.94s).
Independent spec and quality reviews approved the frozen candidate.
Both fixed packets (111 + 79) have zero unexpected movements. All 553 stored
probiotic inputs were replayed against baseline `b2ff64d2`; input hashes,
routes and statuses match. Evidence, Verification and Safety are unchanged.
Five Dose and two Transparency changes trace to shared membership/disclosure
corrections, not new adequacy thresholds. Full results and limits are in
`scripts/audits/scoring_boundary_audit_2026_09_15/README.md`.
This closes the probiotic batch only. No operational regeneration or release ran.

### Final identity-source clarification

The first implementation unnecessarily required `clinical_strains` projections
for the exact numerator. This contradicts identity/efficacy separation and is
superseded: independently revalidated actual label rows and their own forms
can prove exact identity without a clinical projection. The canonical resolver
owns this proof; projected blend names, detached IDs or derived counts cannot
authorize it. Conflicting source paths, wrong species/codes and ambiguous
matches fail closed. Existing BLOCKED/HOLD policy remains intact.

Exact component canaries, presented before this correction:

- LGG source row, no clinical projection: identity **8/8**.
- LGG plus a HOWARU row explicitly naming NCFM and HN001: identity **8/8**,
  count 3. Only LGG has individual CFU, so the separate Dose disclosure
  component remains **10/3**, Transparency disclosure **7/3**.
- Add one unresolved strain: identity **6/8**, count 4; no allocated blend CFU.
- Repeating a source alias changes neither identity nor quantity.
- An ID/projection without actual source proof still gets zero exact credit.

No new clinical rows, tested-dose matches or positive study outcomes are created.

## Broader calibration tracking (not claimed complete)

- [x] Probiotic correction above, end to end.
- [ ] Single/focused duo-trio/broad fairness using existing material-active roles.
- [ ] Generic dose hierarchy with preparation/population/outcome applicability.
- [ ] Indication-aware omega dosing; verify ratio proxy stays absent.
- [ ] Prenatal form appropriateness rather than premium-form assumptions.
  The form-ownership code batch is done (1.7.0, below); the folate/B12 IQM source
  audit and the presence-floor/B-complex structure decisions remain.
- [ ] Ingredient-specific fiber dosing; no universal substrate-equivalence claim.
- [ ] Ingredient-specific sports evidence and dose ownership.
- [ ] Reviewed-versus-unreviewed evidence explanation using existing states.
- [ ] Verify blanket gummy and organic/Non-GMO/natural points stay absent;
  astaxanthin/CoQ10 final-score caps remain absent.
- [ ] Per-archetype excellent/weak-verification/underdose/unnecessary-complexity/
  incomplete-review fixed canaries, with pillar/reason expectations.
- [ ] Combined benchmark stable before Product Submissions refresh, full catalog
  from Clean, category/pillar deltas, release tests and Flutter artifact review.

High-end canaries must meet real rules; no copied scorer or 98–100 tuning.
Missing applicable evidence remains explicit, never invented to complete a row.

### Referenced scoring discussion incorporated (2026-09-15)

Reviewed the available scoring discussion in **PharmaGuide Evidence Scan**
(conversation `6a4cbd7f-1bc0-83ea-a7b1-59f4fdfa1690`). Its latest long response
is truncated by retrieval; the preceding consolidated recommendations and
follow-ups cover the scoring principles below. This is advisory input, not a
second implementation specification or a source of clinical facts.

The owner reports that Dr. Pham read and approved the review. Continue the
engineering/source checks; do not make obtaining another signature the
blocker. Preserve historical provenance rather than silently rewriting old
attribution or inventing a countersignature date/version.

Adopt within the existing roadmap and contracts:

- Invariance/property tests alongside exact canaries: no Evidence gains from
  marketing or badges, no wrong-SKU verification gains, no arbitrary CFU or
  ingredient-count gains, and no improved disclosure score after disclosure is
  removed. A changed evidence synthesis can legitimately move either way.
- Keep strength, applicability, effect direction and review completeness
  distinguishable using existing metadata. Incomplete review is not evidence
  of absence, and a high-quality null study is not positive efficacy support.
- Benchmark pillar reasons and relative rankings as well as total scores;
  separately inspect false-high and false-low cases. Reuse the current
  benchmark owner; do not expose sealed keys or mislabel old AI-assisted
  ratings as a new independent blinded validation.
- Preserve exact botanical material/part/preparation matching and trial-family
  deduplication as cross-category regressions, not probiotic-only protections.
- Explicitly state unknowns and the limits of the safety review. An absence of
  known flags is not proof of safety for every person. Personal fit remains
  separate from the catalog product-quality score.

Do not copy proposed new enums, four internal scores, new visible score tiers,
universal near-dose tolerances, or suggested Verification cutoffs. The current
six-pillar/config owners remain authoritative. Some thread counts and claims
that aggregate-potency max-8 was already implemented are historical proposals,
not current code evidence. Audit any such change before adopting it.

For omega, distinguish nutrition-authority evidence from disease-prevention
efficacy: neither an ingredient amount nor a marketing indication creates an
RCT result. A source-supported nutrition reference can remain explicit without
being represented as a general cardiovascular treatment benefit.

### Verified next-batch findings (2026-09-15; not implemented here)

- Prenatal/multivitamin Dose multiplies RDA coverage by
  `0.75 + bio_score / 60`. This is an ordinal quality rating, not a measured
  absorption fraction. Unknown form scores receive 1.0 and can exceed known
  forms. Remove this duplicate form weighting without changing source amounts,
  DFE conversions, critical-nutrient thresholds or the shared safety rules.
- Prenatal Formulation ranks forms three ways: IQM panel average, premium-form
  count, and a separate preferred-form table. B-complex has another preferred-
  form table. Keep IQM as the form-quality owner; remove redundant rankings
  rather than adding a fourth exception table. Derive new component ceilings
  explicitly before changing references (prenatal: retained 12+2; B-complex:
  retained 10+8+3+2), and test actual source-bound inputs.
- Canonical folate/B12 data needs a narrow source audit, not a module-only
  workaround: folic acid is currently bio_score 6 versus 5-MTHF 14; B12 module
  preferences contradict the IQM ordering. Some B12 values have explicit
  historical clinical locks. Preserve attribution and verify the specific
  evidence before any numeric replacement; never relabel an engineering audit
  as a new clinical sign-off.
- Primary sources checked: [NIH pregnancy](https://ods.od.nih.gov/factsheets/Pregnancy-HealthProfessional/)
  distinguishes folic-acid NTD-prevention evidence from 5-MTHF; [CDC](https://www.cdc.gov/folic-acid/data-research/mthfr/index.html)
  does not support saying methylfolate is essential for common MTHFR variants;
  [NIH B12](https://ods.od.nih.gov/factsheets/VitaminB12-HealthProfessional/)
  does not establish a supplemental form or sublingual absorption advantage.
  These are different questions from acute 5-MTHF plasma-response studies.
- Omega's ratio bonus is already absent, but current Dose still increases
  toward 2 g/day without requiring an indication, and Evidence awards a
  cardiovascular relevance bonus at 1 g/day without establishing that context.
  [NIH omega-3](https://ods.od.nih.gov/factsheets/Omega3FattyAcids-HealthProfessional/)
  separates adult nutritional intake, pregnancy DHA, existing coronary disease
  and prescription triglyceride treatment. Preserve those boundaries rather
  than selecting whichever target makes a product score highest.
- Fiber currently uses one 1/3/5/7 g ladder plus a name-based type bonus. The
  next adapter must use existing source-linked ingredient amounts and curated
  references, not lend total dietary fiber to a named substrate. Generic
  fiber disclosure is not an ingredient-specific efficacy target.
- The existing archetype suite has one "ideal" and one combined "failure"
  per archetype, not the requested five isolated variants. Its probiotic ideal
  has only 8/20 Evidence and is not a 98-100 candidate. Keep that honest
  research-limited control; do not raise its expected score or invent evidence.
  Add separate demonstrably achievable excellent/weak-verification/underdose/
  complexity/incomplete-review fixtures through the same production seam.
- Generic Evidence has a reproduced fail-open direction default:
  `_entry_raw_points` returns 5.0 for the same five-point row with a missing,
  `unresolved`, misspelled, or `positive_strong` direction. Explicit `null`
  returns 1.25 and `negative` returns zero. The next Evidence boundary batch
  must stop unknown direction from inheriting positive efficacy. Preserve
  legitimate nutrition-authority support and the distinction between study
  quality and a positive outcome; do not relabel unknown rows as negative.
  The public `score_evidence` reproduction likewise returns 6.48 for missing,
  unresolved, misspelled or positive-strong direction on the same test row.
  A read-only census of stored enrichment found 50,332 clinical projections,
  all with recognized directions (13,079 positive-weak, 8,129 mixed, 25,832
  positive-strong, 3,292 null). This demonstrates a boundary defect, not that
  those stored rows currently contain unknown directions. Recovered matches
  and public-caller behavior still require the regression gate.
- The generic primary-evidence comments reserve raw 19–20 for multi-active
  breadth, but the current public reference is already 18: the locked
  single-molecule fixture receives public 20 from raw 18. The comment alone
  does not prove a public single-ingredient ceiling defect. Audit source-bound
  single, duo/trio, broad, trace-ingredient and added-irrelevant-active contrasts
  before changing policy, and correct stale descriptions rather than "fixing"
  behavior that already meets the fairness goal. Keep material-active/source
  ownership checks intact.

### Next bounded implementation: vitamin form ownership

Exact math presented to the owner before implementation:

- Multi/prenatal: retain panel form quality (0–12, current weighted IQM mean
  and neutral floor) and disclosure structure (0–2). Remove premium-form
  diversity (0–4) and key-form name ranking (0–5). Positive ceiling, category
  cap and public Formulation reference become **14**. Existing penalties and
  presence floor remain; public weight remains 20.
- B-complex: retain core panel coverage (0–10), IQM form quality (0–8), focus
  purity (0–3), disclosure (0–2). Remove preferred-form name ranking (0–7).
  Positive ceiling, raw cap and public reference become **23**.
- Multi/prenatal Dose: remove only the ordinal `bio_score` multiplier from
  RDA/AI coverage. Keep the existing source-bound adequacy, DFE and unit
  handling, population/critical nutrient checks, complements and safety.
- Canary: equal IQM 12 and complete disclosure gives prenatal raw
  `12 * 12/15 + 2 = 11.6`, public **16.6/20**, regardless of preferred-form
  names or how many equally rated ingredients are present. IQM 15 gives
  raw 14 / public 20. The current neutral-floor policy is not silently changed.
- Canary: complete, focused B panel at IQM 12 gives
  `10 + 8 * 12/15 + 3 + 2 = 21.4`, public **18.6/20**; IQM 15 gives 23 / 20.
  Name substitutions alone do not add points. A new unrelated active still
  changes focus by the existing rule; missing disclosure still loses credit.
- Canary: 100% RDA under UL gives coverage-unit credit **1.0**, whether
  bio_score is 6, 12, 15 or unavailable. A genuinely low RDA percentage and
  a genuine UL violation retain the current dose response.

Implementation ownership: the existing multi/prenatal Formulation and Dose,
B-complex adapter, canonical quality config/fingerprint, bounded tests and
export references to the removed components. No replacement form table,
new schema, or IQM numeric edits in this code batch. Preserve explicit B12
clinical locks; the source-data audit is a separate attributable correction,
not an implied clinical sign-off.

- [x] Red boundary regressions, implement, focused tests.
- [x] Baseline/candidate frozen packet and real routed-corpus comparison.
- [x] Independent spec and code-quality reviews; update measured fixture pins.
- [x] Frozen full fast backstop before marking this batch complete.

Completed (Claude, 2026-09-15; awaiting Codex adversarial audit). Config
`1.7.0-vitamin-form-ownership`, fingerprint `32da1b7296417cad`. Baseline
`a7b676e4`; the replayed candidate tree is `b5e7499b`, and the committed scoring
code is identical to it. After review, only two tests changed. Final fast suite:
**15,519 passed, 66 skipped, 2 xfailed**, zero failures. Measured results,
unexpected movements and limits are in
`scripts/audits/scoring_boundary_audit_2026_09_15/README.md`.

Decisions this batch surfaced, deliberately not changed in it:

- The multi/prenatal and generic presence floor applies only when positive
  points minus penalties is at or below zero. A product with slightly more
  positive signal scores below a floored one. This non-monotonic band held 44
  scored multis at baseline and holds 120 after the positive ceiling dropped
  from 23 to 14; floored products rose from 45 to 178. Absolute formulation
  penalties now weigh against a 14-point reference.
- B-complex Formulation is now 15/23 panel structure and 8/23 IQM form quality.
  A complete, focused panel with mediocre forms (209616, average rating 10)
  moves Excellent → Exceptional. Decide whether that structure share is intended.
- Folate/B12 IQM source values remain the separate attributable data audit above.
- Evidence still lets an unresolved effect direction inherit positive credit.
  It is pinned as a strict xfail in `test_vitamin_form_ownership.py` for the
  Evidence boundary batch.

Audit of the completed probiotic batch (Claude, 2026-09-15):

- Reproduced HIGH regression, not yet fixed. The shared collector predicate
  reads `raw_category` when the cleaner `category` is empty. DSLD labels
  Spirulina "bacteria", so 63308 and 31062 flip to `is_probiotic_product` on the
  next re-enrichment; the pre-batch enricher read only `category`. Decide the
  cyanobacteria/algae eligibility rule before any Clean/Enrich run.
- Seventeen slow real-catalog canaries (omega p161 ×9, cross-module probiotic ×7,
  generic 184661) already fail at `a7b676e4`. `test_profiles.py` excludes them
  from `fast`, so refresh them before release gates.
- The stored vitamin corpus (2,073 multi/prenatal + 146 B-complex) is
  score-identical between `b2ff64d2` and `a7b676e4`.
