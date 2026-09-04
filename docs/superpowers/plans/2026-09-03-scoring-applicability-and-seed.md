# Scoring applicability and Seed — implementation checklist

> **For agentic workers:** Use test-first implementation and separate spec/correctness review. This executes the user's approved correctness/evidence steps 1–2; extraction Phase 3 and weight calibration remain later work.

**Goal:** Correct product-certification, nutrient-dose, clinical-applicability and explanation errors across all brands, and assess Seed DS-01 using verified formula-level AFU evidence without a fabricated CFU conversion.

**Architecture:** Keep the existing enrichment → typed scoring input → v4 scorer → export ownership. Fix the canonical producers and shared matching rules, not individual scores. Formula research must match the disclosed formulation, native unit, daily dose and studied outcomes. Unmatched evidence is an applicability/review state, not a negative-quality assertion.

**Tech stack:** Python 3.13, project pytest runner, JSON curated evidence, manifest-owned corpus.

## Scope and boundaries

- No scoring weights/tier changes, no clinical auto-approval, no Supabase publication.
- Preserve the baseline corpus and compare from enriched/cleaned inputs, never blob replay.
- Do not use product names alone to award certification or formula research.
- Use `scripts/test.sh fast` for iteration; complete integrated gates after corpus verification, not concurrently with the pipeline.
- No invented identifiers or broad clinical assertions: verify each added study's content and record applicability/limitations.

## 1. Certification identity (`scripts/cert_resolver.py`, resolver tests)

- [x] Reproduce Men/Women cross-match and dose/form normalization bypass with RED tests; keep a genuine same-SKU positive control.
- [x] Fix variant guards before fuzzy ranking can award SKU/program credit, including explicit population and strength conflicts; preserve documented product-line semantics.
- [x] Run focused tests and inventory all currently credited registry pairs for equivalent conflicts across brands.

## 2. Parent-nutrient exposure (`enrich_supplements_v3.py`, dose lineage tests)

- [x] RED tests for parent nutrient `(as source)` amounts without Daily Value and explicit compound-mass negatives.
- [x] Fix exposure authority at the declared parent relationship, keeping compound-only rows conservative; never strip arbitrary parentheses into nutrient proof.
- [x] Re-enrich Ritual fixture; verify D, Mg and Zn are assessed as present with exact label amounts, and genuine compound/UL uncertainty still fails closed.

## 3. Evidence applicability (clinical matcher/shared scorer, data and tests)

- [x] Trace identity, form, route of administration, dose, population and endpoint use; reproduce zinc capsule versus high-dose lozenge miscredit.
- [x] Introduce the smallest shared applicability contract needed, carried into enrichment, `resolved_clinical_matches`, `assessment_readiness.py` evidence states, scoring, confidence and audit reporting; retain match/rejection provenance. Identity-only linked evidence cannot count as reviewed support after rejection.
- [x] Correct the affected authored records one at a time with content-verified sources; do not infer therapeutic evidence from nutritional identity or mere citation existence.
- [x] Audit primary-ingredient floors against actual matching dose/form and limit public explanations to the supported scope; no arbitrary weight changes.

## 4. Accurate pillar explanations (`scoring_v4/quality_score.py`, explanation tests)

- [x] RED test for full amount disclosure with missing unrelated claim bonuses.
- [x] Derive explanation from actual component facts; keep shared consumer wording consistent.

## 5. Seed formula evidence (reviewed registry, probiotic dose/evidence, readiness tests)

- [x] Cache primary-source research for PMID 41599868 and directly applicable companion studies: formula/strains, AFU, pomegranate, population, endpoints, attrition, funding and limits.
- [x] RED exact-formula positive tests and negatives for changed strain, dose, unit, prebiotic and name-only match.
- [x] Implement native-AFU formula assessment with explicit provenance; never invent CFU or per-strain quantities, and never extend formula results to each strain.
- [x] Replace the unconditional AFU readiness gate through the shared measurement/assessment owner, consumed by both `assessment_readiness.py` and `probiotic_dose.py`; reject caller-authored success stamps and preserve incomplete results for unmatched/invalid AFU. Update the current anti-fabrication tests, not just the score module.
- [x] Prove Seed reaches scoring only when all relevant readiness requirements are genuinely satisfied; report exact new pillars and explanation.

## 6. Cross-brand verification and handoff

- [x] Freeze baseline hashes/scores; inventory all exposed certifications, affected nutrient rows and evidence matches.
- [x] Reproducible stratified spot-check across multiple brands plus all affected known canaries (215 full re-enrichment cases).
- [x] Run baseline/candidate corpus comparison for routes, scores, pillars, statuses and verdicts; review every changed class of behavior (15,415 products; final report hash and results in `scripts/audits/scoring_applicability_2026_09_03/verification.md`).
- [x] Focused regressions and independent spec/correctness review; preserve actual label ownership and reject contradictory strain forms without erasing generic taxonomy descriptors.
- [x] Integrated fast tests against the frozen implementation: 12,773 passed, 42 skipped, zero failures; post-test input/source/reference hashes match the final corpus audit.
- [ ] Operational enrichment/scoring rebuild followed by release gates against fresh artifacts. This is the operator handoff, not permission to bypass the old-artifact freshness failure.
- [x] Commit verified slices; report what changed, affected counts, unresolved exceptions, and the single required operational rebuild/release step. Certification and clinical implementation are local commits `50651e5b` and `4fa4ece8`; this audit/checklist is the final documentation slice. Phase 3, calibration, operational rebuild and publication remain pending.

## Initial verified baseline

Pipeline HEAD `3f7fc754`; staged catalog `2026.09.03.205958`, schema 2.4.0, scoring 4.3.1. Ritual score 81.6 rounds to 82; Youtheory 77.4 rounds to 77; Seed is not scored for the missing AFU-compatible reference. Earlier green structural gates did not establish study/product applicability.
