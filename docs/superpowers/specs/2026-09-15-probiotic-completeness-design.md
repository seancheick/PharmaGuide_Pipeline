# Probiotic Formulation completeness correction

Baseline: `b2ff64d2`. Owner requested preparation followed by implementation,
with exact math and canary expectations shown before implementation. This is
the first bounded change in the broader calibration roadmap, not a release.

## Decision and alternatives

Use completeness rather than strain-count/CFU-size ladders in the existing
Formulation module. Identity-only repair leaves the CFU and diversity proxies;
a wholesale scorer replacement adds drift. Neither is selected.

Raw components: valid total potency disclosure 4; exact label-owned identity
completeness `8 * exact_count / total_count` (zero if no label identities);
existing delivery/survivability 0–3; existing prebiotic complement 0–1. Remove
the CFU-size (5) and species-count (4) components, without reallocating them.
Raw maximum and public normalization reference become 16. Existing penalties
are subtracted before clamping. Public Formulation remains
`round(clamp(raw / 16 * 20, 0, 20), 1)` in the existing assembler.

The prebiotic component remains the current limited rubric signal in this
batch; it is not evidence that every substrate has a clinical target of 3 g.
Its substrate-specific review remains in the broader fiber work. No prebiotic
is required for full **identity** credit. An otherwise perfect standalone
probiotic without this optional point has a mathematical public ceiling of
98.8, not a new final-score cap.

## One source of identity/counting truth

Keep exact matching and source ownership in `studied_formulas` and the existing
measurement boundary. Move the shared counting helper out of the Dose module
into `probiotic_measurements` so enrichment and all three pillars can use it.
Count distinct nonblank label names, not bare clinical IDs. Use existing exact
registry normalization to collapse registered aliases of the same identity;
unregistered names remain distinct and cannot become researched strains.

`total_strain_count` is a derived summary, not an independently sourced label
declaration. Ignore it for scoring counts in either direction. Count actual
distinct label identities instead. A count alone, a malformed value, or
detached clinical IDs cannot produce named-strain or dose disclosure.
Count duplicate projections once. Exact identity numerator must be re-proved
against source rows and registry, intersected with label identities, and never
exceed the denominator. Clinical sign-off is not required for physical identity.

Keys must be source-local before deduplication: a species display name with
an owned structured BB536 form becomes the proven BB536 identity; a sibling
with the same display name but no form remains unresolved/species-only. Two
different owned forms sharing a display name remain two identities. Reuse
the existing source/form resolver in `studied_formulas`, never infer a
form from a sibling. All scoring callers must provide the whole product for
this proof; enrichment uses its assembled native payload and source label rows.
An actual source-owned identity may supply a missing projected blend name;
a detached clinical ID may not. Pin the HOWARU and BB536 existing regressions.

Identity-only proof must not require a clinical projection: an exact label
remains exact if `clinical_strains` is absent. Resolve each actual biological
form on its own owner for identity completeness, while keeping the original
multi-form row unresolved for individual-dose allocation. Three fully named,
registered source identities earn 8/8 even when two share an aggregate amount;
only the separately measured identity earns per-strain CFU disclosure. Keep
conflicting source representations and existing BLOCKED/HOLD policy fail-closed.

Keep the same keys for count/disclosure consumers, with no new public schema.
Dose and Transparency use the same denominator and alias keys. Preserve all
existing CFU ownership checks, including the ban on splitting aggregate CFU.
Do not change dose tiers, trial applicability or source-approval decisions.

An already verified complete-formula AFU match keeps its native disclosure
and complete-formula identity credit (4 + 8), delivery and complement (3 + 1).
Remove its parallel 5-point potency bonus too. AFU never becomes CFU or
independent per-strain efficacy. Unknown formula matches do not get this path.

## Frozen canary expectations (before implementation)

All rows below assume valid potency disclosure, delivery 3, no penalties and
no optional prebiotic credit. They are arithmetic expectations, not test results.

| Case | Identity raw /8 | Formulation /20 |
|---|---:|---:|
| 1 exact of 1 | 8 | 18.8 |
| 5 exact of 5 | 8 | 18.8 |
| 2 exact of 4 | 4 | 13.8 |
| Species-only | 0 | 8.8 |
| Same identity, 1 vs 50 billion total CFU | unchanged | unchanged |
| Duplicate spelling/projection of the same strain | unchanged | unchanged |

Adding the existing full prebiotic complement to a complete canary yields
16/16 raw and 20/20 public. Changing the summary count cannot change any
disclosure/identity component. Two labels, one measured, summary count one:
Dose disclosure 5/10, not 10/10. Count-only payload: no identity/disclosure.
Evidence, safety and verification stay unchanged by identity-only mutations.

## Verification and handoff

Test regressions red first through `scripts/test.sh fast`. Update old ladder
tests to the new invariant rather than merely updating final numbers. Verify
native-AFU, species-only, null-outcome, source ownership, prebiotic ownership,
chemical-form dose references, certification scope and citation checks.
Use frozen real packets and a read-only whole stored-corpus comparison with
input/config fingerprints; never select thresholds from those results.
Version/fingerprint the canonical config and inspect exported bonus wording.
Run frozen-code fast suite before committing implementation. No operational
Clean/Enrich/Score, catalog regeneration, deployment or release in this batch.

## Remaining roadmap — not completed by this correction

Next bounded batches: focused single/duo/trio/broad fairness; generic reference
hierarchy; indication-aware omega; prenatal form appropriateness; substrate-
specific fiber; ingredient-specific sports evidence; review-coverage wording.
Re-verify already-landed ratio/gummy/marketing-proxy/cap removals rather than
implementing them again. Each category needs excellent, weak-verification,
underdosed, unnecessary-complexity and unreviewed canaries with pillar/reason
checks. Only after the combined benchmark is stable: refresh submissions,
full catalog from Clean, category/pillar deltas, release tests and Flutter
artifact verification; release remains a separate final decision.
