# v4 Purpose-Fit Scoring Staging Plan

Date: 2026-06-05

## North Star

PharmaGuide v4 should answer:

> How well does this product accomplish the job it claims to do?

The score should not mean "percent of theoretical perfection." It should mean
quality relative to the product's real category and stated purpose. This must be
earned by real signals, not by affine stretching or competitor-score chasing.

Safety verdict, quality score, confidence, and evidence strength remain separate:

- Quality score: formulation, dose, evidence, transparency, verification signals.
- Safety verdict: consumer-action warnings only.
- Confidence: parser/data completeness and route certainty.
- Evidence strength: how strong the evidence base is for the product's purpose.

## Current Measured State

Read-only snapshot over current enriched artifacts in `scripts/products`:

| Metric | Current |
|---|---:|
| Scored products | 10,060 |
| Max v4 score | 91.5 |
| Products >=90 | 5 |
| Products >=85 | 62 |
| Products >=80 | 372 |

Top examples:

| Product | Module | Score |
|---|---|---:|
| Thorne Creatine | sports | 91.5 |
| GNC Pro Performance Creatine Monohydrate 5000 mg | sports | 91.5 |
| Nordic Naturals Ultimate Omega-D3 Sport | omega | 89.3 |
| Nature Made Magnesium Citrate 250 mg | generic | 88.5 |
| Thorne Basic Prenatal | multi_or_prenatal | 88.4 |

Conclusion: v4 is no longer globally capped below 90. The remaining work should
be category-specific purpose-fit calibration, not a global score stretch.

## Score Semantics

Use these as public-facing quality bands after final calibration:

| Score | Meaning |
|---:|---|
| 95-100 | Elite: unusually complete for its purpose, fully disclosed, excellent evidence/verification |
| 90-94 | Excellent: clearly top-tier for its purpose, may still have transparent caveats |
| 80-89 | Strong/good: solid product with meaningful strengths and some limitations |
| 70-79 | Acceptable: usable product, but not top-tier |
| 55-69 | Weak/fair: meaningful quality or disclosure gaps |
| <55 | Poor: major quality, evidence, dosing, or transparency weaknesses |

These bands are targets for interpretation, not an instruction to force the
distribution.

## Tier 1: Finish Mechanical Ceiling Fixes

### 1. Omega Dose Band

Owner: Claude currently touching omega; Codex should not collide.

Purpose-fit rule:

- 500 mg EPA+DHA/day: partial/general health.
- 1000 mg EPA+DHA/day: strong consumer dose.
- 2000 mg EPA+DHA/day: full/high clinical consumer dose.
- 3000-4000+ mg/day: prescription-style context note, no extra quality credit.

Guardrails:

- Parent fish-oil mass still does not count as EPA+DHA.
- Aggregate EPA+DHA counts only when explicitly disclosed.
- Multi/prenatal adjunct omega should not nuke the whole product dose.
- Review top gainers and low-dose products after change.

### 2. Verification Reachability

Status: partially implemented.

Done:

- Product-cert -> GMP implication.
- Explicit manufacturer/facility GMP evidence -> B4b.
- Registry-discovered SKU/product-line certs can now score even if label text
  does not repeat the cert program.

Remaining:

- Re-run fresh enrichment so registry-discovered certs populate real scored
  artifacts.
- Audit top gainers for false positives.
- Refresh/expand cert registry sources where current registry coverage is thin.

Policy target:

- 5-6/8 verification = strong brand/facility quality.
- 8/8 verification = product-level certification plus traceability/COA strength.

### 3. Single-Ingredient Evidence Ceiling

Status: monitor, not immediate blocker.

Current state:

- Strong sports singles can already reach 90+.
- Thorne Creatine scores 91-91.5 with evidence 18/20.

Do not blindly raise all evidence floors to 20. Only revisit if a verified
excellent single remains capped below 90 for evidence-specific reasons.

Candidate future rule:

- 20/20 evidence reserved for ingredient with overwhelming human evidence,
  clinically relevant dose, positive direction, and no meaningful indication
  mismatch.
- 18/20 remains appropriate for strong but not uniquely definitive evidence.

### 4. Multi/Prenatal Purpose Fit

Status: partially implemented.

Done:

- Prenatal core split from DHA/choline complements.
- Prenatal critical nutrients use threshold adequacy instead of bio-weighted
  dose coverage.
- Targeted/essential multis use adult gap-filler anchor support instead of
  complete-multi missing-anchor punishment.

Remaining:

- Rerun fresh full pipeline after cert/enrichment changes.
- Audit Thorne Basic Prenatal, Pure PreNatal, Ritual Essential, FullWell,
  Needed, Designs for Health.
- Decide whether multi/prenatal dose 30 and evidence 15 should rebalance toward
  dose 25 / evidence 20.

Guardrail:

- A prenatal without DHA/choline can still be excellent as a prenatal multi.
  UI should say "consider separate DHA/choline depending on diet and clinician
  advice," not bury the score.

## Tier 2: Category Fairness Work

### Probiotic

Keep:

- Named strains matter.
- CFU disclosure matters.
- Per-strain CFU is premium.

Improve:

- Aggregate CFU should be acceptable disclosure, not near-zero dose.
- No CFU should hurt dose/confidence, not automatically imply unsafe.
- Exact strain aliases must beat species representative strains.
- Add verified entries for major strains such as LGG and BB-12 when supported.

### Botanical

Keep:

- Botanical profile should own true herb/extract products.
- Opaque blends should lose transparency.

Improve:

- Botanical no-reference dose floor should not overpower the entire score.
- Correct botanical ownership plus no dose reference should often mean lower
  confidence/partial dose, not automatic POOR.
- Continue using the classification contract to prevent nutrient-source and
  adjunct botanicals from hijacking the route.

## Tier 3: New Capability, Not Calibration

Do later, with verified data assets:

- Prebiotic profile.
- Postbiotic/synbiotic scoring.
- Probiotic indication-fit reference table.
- Seed/Ritual precision fixtures for exact branded strains.
- COA/batch lookup enrichment beyond DSLD.

Do not improvise these from intuition. They need provenance-backed reference
data and tests.

## Required Gates After Each Change

Run focused tests first, then a corpus or cohort pass only when needed.

Minimum gates:

- Targeted tests for changed module.
- No new `NOT_SCORED` growth except true no-usable-identity.
- No safety downgrade.
- Top gainers reviewed by product signal.
- Low scorers sampled by category.
- Premium cohort rerun:
  - Thorne
  - Pure Encapsulations
  - Ritual
  - Nordic Naturals
  - Life Extension
  - Designs for Health
  - FullWell
  - Needed
  - Transparent Labs

Acceptance principle:

Every score increase must come from a real product signal the old rubric failed
to credit. No hidden affine, no brand-only inflation, no competitor-score chase.
