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

- [ ] Add red regression tests calling the existing modules. Required assertions:

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
- [ ] Run focused tests through `scripts/test.sh fast`; record genuine red failures.
- [ ] Implement the shared counting boundary. Reuse
  `clinical_strain_identity_key`/`clinical_strain_identity_matches` and registry;
  do not build a new strain matcher. Only exact aliases collapse. The existing
  total_strain_count is derived, not a sourced declaration, so ignore it for
  scoring in either direction. A count with no labels creates no disclosure.
  Resolve source-local structured forms using existing `label_owned_native_strains`
  before deduplication: exact+species-only siblings with the same display name
  are two identities; two distinct proven forms are also two. Never share one
  owner's form with its sibling. Pass whole-product source context through
  all scoring callers and the assembled enrichment payload. Test existing
  BB536/HOWARU fixtures plus these exact/unresolved and distinct-form cases.
- [ ] Apply raw formula `4 + 8 * exact/total + delivery + complement`, with
  missing components zero, penalties before clamp, maximum 16. Reuse source-
  owned exact matches and the same label identity keys in numerator/denominator.
  Keep the verified whole-formula AFU branch native and remove its old +5.
- [ ] Align consumers, descriptions, config version/fingerprint and existing
  tests. Preserve regressions for all source/certification/chemical boundaries.
- [ ] Run focused tests; review the full diff. Do not refresh locked final
  scores unless the measured change is attributable to this approved math.
- [ ] Independent spec compliance then code-quality review; resolve findings.

## Task 2 — frozen-input evidence, report and commit

Files: reuse `scripts/audits/rubric_proxy_removal_2026_09_14/score_packet.py`
and `diff_packet.py`; extend the existing boundary-audit replay/report only
when necessary rather than inventing another scorer/harness.

- [ ] Freeze baseline outputs for both existing packets from baseline commit
  before editing runtime code, or use an isolated exact baseline checkout.
- [ ] Run current scorer against the same 111 + 79 frozen inputs. Verify IDs,
  hashes, finite real public scores and six pillars through the existing diff.
- [ ] Read-only all-stored-probiotic comparison: same product input for baseline
  and candidate; count/refuse malformed batches; report corpus size, routed
  categories, score and pillar deltas, unavailable/stale inputs. This is not a
  fresh cleaned/enriched release. No output_* directories may be overwritten.
- [ ] Confirm expected movements and invariants: no Formulation size gain;
  only count/identity fixes can affect disclosure; Evidence, Verification,
  Safety unchanged; unknown species not promoted; AFU unchanged in Dose.
- [ ] Run `scripts/test.sh fast` on frozen code; do not edit during the run.
- [ ] Record measured results and outstanding broader roadmap items. Commit
  implementation and push main after fresh fetch/review; preserve user files.
- [ ] Continue the broader roadmap in bounded batches before any regeneration.

## Broader calibration tracking (not claimed complete)

- [ ] Probiotic correction above, end to end.
- [ ] Single/focused duo-trio/broad fairness using existing material-active roles.
- [ ] Generic dose hierarchy with preparation/population/outcome applicability.
- [ ] Indication-aware omega dosing; verify ratio proxy stays absent.
- [ ] Prenatal form appropriateness rather than premium-form assumptions.
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

- [ ] Red boundary regressions, implement, focused tests.
- [ ] Baseline/candidate frozen packet and real routed-corpus comparison.
- [ ] Independent spec and code-quality reviews; update measured fixture pins.
- [ ] Frozen full fast backstop before marking this batch complete.
