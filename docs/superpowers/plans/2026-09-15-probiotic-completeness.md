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
